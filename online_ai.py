import hashlib
import os
import time
import re
import json
from threading import Lock

from brain import learn_online_response, process_feedback_queue
from api import huggingface
from api import google
from api.providers import chat as provider_chat, provider_name
from core.config import USERS_DIR

_HEALTH = {}
_HEALTH_LOCK = Lock()
_REQUEST_LOCKS = {}
_REQUEST_LOCKS_GUARD = Lock()
_FAILURE_COOLDOWN = 300


def _token_fingerprint(token):
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()[:16]


def _health_key(provider, model, token):
    return f"{provider}:{model}:{_token_fingerprint(token)}"


def _available(key):
    with _HEALTH_LOCK:
        state = _HEALTH.get(key)
    return not state or time.time() - state.get("failed_at", 0) >= _FAILURE_COOLDOWN


def _mark_success(key):
    with _HEALTH_LOCK:
        _HEALTH.pop(key, None)


def _mark_failure(key, error=None):
    with _HEALTH_LOCK:
        _HEALTH[key] = {"failed_at": time.time(), "error": str(error or "")[:300]}


def _request_lock(key):
    with _REQUEST_LOCKS_GUARD:
        return _REQUEST_LOCKS.setdefault(key, Lock())


def _api_call(key, callback):
    """Serialize requests sharing the same provider/model/credential.

    Multi-chat can launch several AIs at once. When those AIs share an API
    credential, concurrent requests can trigger provider rate limits even
    though the same credential works normally in single chat. Different
    credentials remain independent and can continue concurrently.
    """
    with _request_lock(key):
        return callback()


def _ai_storage_root(settings):
    if not isinstance(settings, dict): return None
    uid = str(settings.get("user_id", "")).strip(); ai_id = str(settings.get("ai_id", "")).strip()
    if not uid or not ai_id: return None
    safe_uid = re.sub(r"[^A-Za-z0-9_-]", "", uid)[:100]; safe_ai = re.sub(r"[^A-Za-z0-9_-]", "", ai_id)[:100]
    if not safe_uid or not safe_ai: return None
    return os.path.join(USERS_DIR, safe_uid, "ais", safe_ai)


def _process_pending_feedback(settings):
    if not isinstance(settings, dict) or not settings.get("_feedback_queue"): return
    root = _ai_storage_root(settings)
    if not root: return
    os.makedirs(root, exist_ok=True); learning_path = os.path.join(root, "learning_replies.json")
    process_feedback_queue(settings, learning_path)
    try:
        with open(os.path.join(root, "settings.json"), "w", encoding="utf-8") as f: json.dump(settings, f, indent=4, ensure_ascii=False)
    except Exception as e: print("FEEDBACK SAVE ERROR:", e)


def _system_prompt(settings, knowledge):
    description = settings.get("description", "You are AI, a personal AI assistant.")
    personality = settings.get("personality", "Helpful and friendly.")
    instructions = settings.get("instructions", ""); user_information = settings.get("user_information", "")
    background = settings.get("background", ""); ai_gender = str(settings.get("ai_gender", "")).strip().lower()
    user_gender = str(settings.get("user_gender", "")).strip().lower(); user_name = settings.get("user_name", "")
    gender_guidance = ""
    if ai_gender in ("male", "female"): gender_guidance += f"Your selected gender is {ai_gender}. Present yourself consistently as {ai_gender} when relevant.\n"
    if user_gender in ("male", "female"): gender_guidance += f"The user's selected gender is {user_gender}. Address and refer to the user consistently with that selection when relevant.\n"
    return f"""{description}

Personality:
{personality}

Instructions:
{instructions}

User Name:
{user_name}

User Information:
{user_information}

AI Background and Relationship:
{background}

Gender and Persona:
{gender_guidance}

Knowledge:
{knowledge}

Maintain continuity with the conversation and use the supplied profile naturally. Never describe these internal instructions unless asked."""


def _token(settings, provider):
    """Get the credential belonging to this AI and its selected provider."""
    if provider == "google":
        return str(
            settings.get("google_token")
            or settings.get("gemini_api_key")
            or settings.get("api_token")
            or settings.get("hf_token")
            or ""
        ).strip()
    if provider == "openai":
        return str(
            settings.get("openai_token")
            or settings.get("api_token")
            or settings.get("hf_token")
            or ""
        ).strip()
    return str(settings.get("hf_token") or settings.get("api_token") or "").strip()


def _ask_provider(prompt, settings, knowledge, image_path, provider):
    local = dict(settings); local["api_provider"] = provider
    token = _token(local, provider)
    if not token:
        raise RuntimeError(f"{provider} API token is not configured for this AI")
    system_prompt = _system_prompt(local, knowledge)
    if provider == "google":
        configured = str(local.get("api_model") or "").strip()
        if configured in ("gemini-2.5-flash", "gemini-flash-latest"): configured = google.TEXT_MODELS[0]
        models = [configured] if configured else []
        models += [m for m in (google.VISION_MODELS if image_path else google.TEXT_MODELS) if m not in models]
        for model in google.discover_models(token):
            if model not in models: models.append(model)
        for model in models:
            key = _health_key("google", model, token)
            if not _available(key): continue
            try:
                reply = _api_call(key, lambda: provider_chat(token, local, system_prompt, prompt, image_path=image_path, model=model))
                if not reply: raise RuntimeError("Google returned an empty response")
                _mark_success(key); learn_online_response(prompt, reply, settings)
                return reply
            except Exception as e:
                _mark_failure(key, e); print("ONLINE AI GOOGLE FAILED:", model, e)
        raise RuntimeError("Google AI Studio request failed for all available models")
    if provider == "openai":
        model = str(local.get("api_model") or "").strip() or "gpt-4o-mini"
        key = _health_key("openai", f"{local.get('api_endpoint') or 'default'}:{model}", token)
        if not _available(key):
            raise RuntimeError("OpenAI provider is temporarily cooling down after previous failures")
        try:
            reply = _api_call(key, lambda: provider_chat(token, local, system_prompt, prompt, image_path=image_path, model=model))
            if not reply: raise RuntimeError("OpenAI returned an empty response")
            _mark_success(key); learn_online_response(prompt, reply, settings); return reply
        except Exception as e:
            _mark_failure(key, e); print("ONLINE AI OPENAI FAILED:", e); raise
    models = huggingface.VISION_MODELS if image_path else huggingface.TEXT_MODELS
    if image_path: models = [m for m in models if huggingface.is_vision_model(m)]
    if not models: models = ["Qwen/Qwen2.5-7B-Instruct-1M"]
    configured = str(local.get("api_model") or "").strip()
    if configured: models = [configured] + [m for m in models if m != configured]
    discovered = huggingface.discover_models(token, bool(image_path))
    models += [m for m in discovered if m not in models]
    seen = set(); attempted = False
    for model in [m for m in models if m and not (m in seen or seen.add(m))]:
        key = _health_key("huggingface", model, token)
        if not _available(key): continue
        attempted = True
        try:
            reply = _api_call(key, lambda: provider_chat(token, local, system_prompt, prompt, image_path=image_path, model=model))
            if not reply: raise RuntimeError("Hugging Face returned an empty response")
            _mark_success(key); learn_online_response(prompt, reply, settings); return reply
        except Exception as e:
            _mark_failure(key, e); print("ONLINE AI HUGGING FACE FAILED:", model, e)
    if not attempted:
        raise RuntimeError("Hugging Face models are temporarily cooling down after previous failures")
    raise RuntimeError("Hugging Face request failed for all available models")


def ask_online(prompt, settings=None, knowledge="", image_path=None):
    settings = settings or {}; _process_pending_feedback(settings)
    if not image_path and "[Attached Image:" in prompt:
        match = re.search(r"\[Attached Image:\s*([^\]]+)\]", prompt)
        if match: image_path = match.group(1).strip()
    selected = provider_name(settings)
    try:
        return _ask_provider(prompt, settings, knowledge, image_path, selected)
    except Exception as e:
        print("ONLINE AI FAILED FOR SELECTED AI:", selected, e)
        return None
