import os
import time
import re
import json

from brain import learn_online_response, process_feedback_queue
from api import huggingface
from api import google
from api.providers import chat as provider_chat, provider_name
from core.config import USERS_DIR

_HEALTH = {}
_FAILURE_COOLDOWN = 300


def _available(key):
    state = _HEALTH.get(key)
    return not state or time.time() - state.get("failed_at", 0) >= _FAILURE_COOLDOWN


def _mark_success(key):
    _HEALTH.pop(key, None)


def _mark_failure(key, error=None):
    _HEALTH[key] = {"failed_at": time.time(), "error": str(error or "")[:300]}


def _ai_storage_root(settings):
    """Return the user's AI directory from the central persistent storage."""
    if not isinstance(settings, dict):
        return None
    uid = str(settings.get("user_id", "")).strip()
    ai_id = str(settings.get("ai_id", "")).strip()
    if not uid or not ai_id:
        return None
    safe_uid = re.sub(r"[^A-Za-z0-9_-]", "", uid)[:100]
    safe_ai = re.sub(r"[^A-Za-z0-9_-]", "", ai_id)[:100]
    if not safe_uid or not safe_ai:
        return None
    return os.path.join(USERS_DIR, safe_uid, "ais", safe_ai)


def _process_pending_feedback(settings):
    if not isinstance(settings, dict) or not settings.get("_feedback_queue"):
        return
    root = _ai_storage_root(settings)
    if not root:
        return
    os.makedirs(root, exist_ok=True)
    learning_path = os.path.join(root, "learning_replies.json")
    process_feedback_queue(settings, learning_path)
    try:
        with open(os.path.join(root, "settings.json"), "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print("FEEDBACK SAVE ERROR:", e)


def _system_prompt(settings, knowledge):
    description = settings.get("description", "You are AI, a personal AI assistant.")
    personality = settings.get("personality", "Helpful and friendly.")
    instructions = settings.get("instructions", "")
    user_information = settings.get("user_information", "")
    background = settings.get("background", "")
    ai_gender = str(settings.get("ai_gender", "")).strip().lower()
    user_gender = str(settings.get("user_gender", "")).strip().lower()
    user_name = settings.get("user_name", "")
    gender_guidance = ""
    if ai_gender in ("male", "female"):
        gender_guidance += f"Your selected gender is {ai_gender}. Present yourself consistently as {ai_gender} when relevant.\n"
    if user_gender in ("male", "female"):
        gender_guidance += f"The user's selected gender is {user_gender}. Address and refer to the user consistently with that selection when relevant.\n"
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
    if provider == "huggingface":
        token = str(settings.get("hf_token", "")).strip()
        return token or os.getenv("HF_TOKEN", "").strip()
    token = str(settings.get("api_token", "") or settings.get("openai_token", "") or settings.get("hf_token", "")).strip()
    if token:
        return token
    if provider == "google":
        return os.getenv("GEMINI_API_KEY", "").strip()
    return os.getenv("OPENAI_API_KEY", "").strip()


def ask_online(prompt, settings=None, knowledge="", image_path=None):
    settings = settings or {}
    _process_pending_feedback(settings)

    provider = provider_name(settings)
    token = _token(settings, provider)
    if not token:
        print(f"ONLINE AI: no {provider} API token configured")
        return None

    system_prompt = _system_prompt(settings, knowledge)

    if not image_path and "[Attached Image:" in prompt:
        match = re.search(r"\[Attached Image:\s*([^\]]+)\]", prompt)
        if match:
            image_path = match.group(1).strip()

    if provider in ("openai", "google"):
        if provider == "google":
            configured_model = str(settings.get("api_model") or "").strip()
            models = []
            if configured_model:
                models.append(configured_model)
            if image_path:
                models += [m for m in google.VISION_MODELS if m not in models]
            else:
                models += [m for m in google.TEXT_MODELS if m not in models]
            discovered = google.discover_models(token)
            for model in discovered:
                if model not in models:
                    models.append(model)
            if not models:
                models = list(google.VISION_MODELS if image_path else google.TEXT_MODELS)
            label = "Google AI Studio"
            for model in models:
                health_key = f"google:{model}"
                if not _available(health_key):
                    continue
                try:
                    provider_settings = dict(settings)
                    reply = provider_chat(token, provider_settings, system_prompt, prompt, image_path=image_path, model=model)
                    _mark_success(health_key)
                    learn_online_response(prompt, reply, settings)
                    print("ONLINE AI USING GOOGLE AI STUDIO MODEL:", model)
                    return reply
                except Exception as e:
                    _mark_failure(health_key, e)
                    print("ONLINE AI GOOGLE AI STUDIO MODEL FAILED:", model, e)
            return None

        provider_settings = settings
        model = str(settings.get("api_model") or os.getenv("AI_OPENAI_MODEL") or "gpt-4o-mini").strip()
        health_key = f"openai:{settings.get('api_endpoint') or 'default'}:{model}"
        label = "OpenAI-compatible"
        if not _available(health_key):
            return None
        try:
            reply = provider_chat(token, provider_settings, system_prompt, prompt, image_path=image_path, model=model)
            _mark_success(health_key)
            learn_online_response(prompt, reply, settings)
            print("ONLINE AI USING PROVIDER:", label)
            return reply
        except Exception as e:
            _mark_failure(health_key, e)
            print(f"ONLINE AI {label.upper()} ERROR:", e)
            return None

    models = huggingface.VISION_MODELS if image_path else huggingface.TEXT_MODELS
    if image_path:
        models = [m for m in models if huggingface.is_vision_model(m)]
        models += [m for m in huggingface.discover_models(token, True) if huggingface.is_vision_model(m)]
    else:
        models = list(models) + huggingface.discover_models(token, False)

    seen = set()
    models = [m for m in models if m and not (m in seen or seen.add(m))]

    for model in models:
        health_key = f"huggingface:{model}"
        if not _available(health_key):
            continue
        try:
            provider_settings = dict(settings)
            provider_settings["api_provider"] = "huggingface"
            reply = provider_chat(token, provider_settings, system_prompt, prompt, image_path=image_path, model=model)
            _mark_success(health_key)
            learn_online_response(prompt, reply, settings)
            print("ONLINE AI USING HUGGING FACE MODEL:", model)
            return reply
        except Exception as e:
            _mark_failure(health_key, e)
            print("ONLINE AI HUGGING FACE MODEL FAILED:", model, e)

    return None
