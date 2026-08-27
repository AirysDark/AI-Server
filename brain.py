import json
import os
import random
import re
import time
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
try:
    from core.config import STORAGE_DIR, USERS_DIR, LEARNING_DIR
except Exception:
    STORAGE_DIR = BASE_DIR
    USERS_DIR = os.path.join(BASE_DIR, "users")
    LEARNING_DIR = os.path.join(BASE_DIR, "learning")

MEMORY_FILE = os.path.join(STORAGE_DIR, "memory.json")
LEARNING_FILE = os.path.join(LEARNING_DIR, "replies.json")
TRAINING_FILE = os.path.join(LEARNING_DIR, "training.json")
FEEDBACK_FILE = os.path.join(LEARNING_DIR, "feedback.json")

# Conservative defaults for CPU-only hosting. They can still be overridden by environment variables.
LOCAL_MODEL_PATH = os.path.abspath(os.getenv("AI_LOCAL_MODEL", os.path.join(BASE_DIR, "models", "SmolLM2-1.7B-Instruct-Q3_K_M.gguf")))
LOCAL_MODEL_THREADS = max(1, int(os.getenv("AI_LOCAL_MODEL_THREADS", "2")))
LOCAL_MODEL_CTX = max(512, int(os.getenv("AI_LOCAL_MODEL_CTX", "1024")))
LOCAL_MODEL_MAX_TOKENS = max(16, int(os.getenv("AI_LOCAL_MODEL_MAX_TOKENS", "64")))
LOCAL_MODEL_TEMPERATURE = float(os.getenv("AI_LOCAL_MODEL_TEMPERATURE", "0.75"))
LOCAL_PROMPT_CHARS = max(1000, int(os.getenv("AI_LOCAL_PROMPT_CHARS", "12000")))
_LOCAL_LLMS = {}
_LOCAL_LLM_ERRORS = {}


def _model_path(settings=None):
    configured = str((settings or {}).get("local_model_path") or "").strip()
    if configured:
        candidate = os.path.abspath(configured)
        if os.path.isfile(candidate):
            return candidate
        print("LOCAL AI MODEL PATH NOT FOUND:", candidate)
    return LOCAL_MODEL_PATH


def _load_local_llm(settings=None):
    model_path = _model_path(settings)
    if model_path in _LOCAL_LLMS:
        return _LOCAL_LLMS[model_path]
    if not os.path.isfile(model_path):
        error = f"Local GGUF model not found: {model_path}"
        _LOCAL_LLM_ERRORS[model_path] = error
        print("LOCAL AI LOAD ERROR:", error)
        return None
    try:
        from llama_cpp import Llama
        print("LOCAL AI LOADING:", model_path)
        llm = Llama(model_path=model_path, n_ctx=LOCAL_MODEL_CTX, n_threads=LOCAL_MODEL_THREADS, n_batch=64, verbose=False)
        _LOCAL_LLMS[model_path] = llm
        _LOCAL_LLM_ERRORS.pop(model_path, None)
        print("LOCAL AI READY:", model_path)
        return llm
    except Exception as exc:
        _LOCAL_LLM_ERRORS[model_path] = f"Local LLM initialization failed: {exc}"
        print("LOCAL AI LOAD ERROR:", _LOCAL_LLM_ERRORS[model_path])
        return None


def load_json(path, default):
    if not os.path.exists(path): return default
    try:
        with open(path, "r", encoding="utf-8") as f: return json.load(f)
    except Exception: return default


def save_json(path, data):
    if os.path.dirname(path): os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f: json.dump(data, f, indent=4, ensure_ascii=False)


def default_memory(): return {"profile": {}, "facts": {}, "preferences": {}, "personality": {}, "conversations": [], "learning_mode": True}

def remember(memory, category, key, value): memory.setdefault(category, {})[key.lower().strip()] = str(value).strip()


def learn_from_conversation(user, reply, memory_path=None):
    path = memory_path or MEMORY_FILE
    memory = load_json(path, default_memory())
    memory.setdefault("conversations", [])
    user_text = str(user or "")
    ai_text = str(reply or "")
    entry = {"time": datetime.now().isoformat(), "user": user_text, "ai": ai_text, "AI": ai_text}
    if memory["conversations"]:
        last = memory["conversations"][-1]
        if isinstance(last, dict) and last.get("user") == user_text and str(last.get("ai", last.get("AI", ""))) == ai_text: return
    memory["conversations"].append(entry); memory["conversations"] = memory["conversations"][-500:]
    text = user_text.lower()
    if "my name is " in text: remember(memory, "profile", "name", user_text.split("my name is ", 1)[1])
    for key in ["i like", "i love", "i prefer", "i use", "my project"]:
        if key in text: remember(memory, "facts", key, user_text)
    save_json(path, memory)


def learn_online_response(user, reply, settings=None):
    settings = settings or {}; uid = str(settings.get("user_id", "")).strip(); ai_id = str(settings.get("ai_id", "")).strip()
    if not uid or not ai_id: return
    safe_uid = re.sub(r"[^A-Za-z0-9_-]", "", uid)[:100]; safe_ai = re.sub(r"[^A-Za-z0-9_-]", "", ai_id)[:100]
    learn_from_conversation(user, reply, os.path.join(USERS_DIR, safe_uid, "ais", safe_ai, "brain_memory.json"))


def learn_reply(trigger, reply, learning_path=None):
    path = learning_path or LEARNING_FILE; data = load_json(path, {}); key = trigger.lower().strip(); item = data.get(key, {"score": 0, "uses": 0})
    item["reply"] = str(reply).strip(); item["uses"] = item.get("uses", 0) + 1; item["learned"] = datetime.now().isoformat(); data[key] = item; save_json(path, data)


def record_feedback(trigger, reply, rating, learning_path=None, feedback_path=None):
    rating = 1 if str(rating).lower() in ("up", "1", "positive", "good") else -1; path = learning_path or LEARNING_FILE; data = load_json(path, {}); key = str(trigger).lower().strip(); item = data.get(key, {"score": 0, "uses": 0})
    item["reply"] = str(reply).strip(); item["score"] = int(item.get("score", 0)) + rating; item["feedback"] = item.get("feedback", 0) + 1; item["last_feedback"] = datetime.now().isoformat(); data[key] = item; save_json(path, data)
    feedback = load_json(feedback_path or FEEDBACK_FILE, []); feedback.append({"time": datetime.now().isoformat(), "trigger": trigger, "reply": reply, "rating": rating}); save_json(feedback_path or FEEDBACK_FILE, feedback[-2000:]); return item["score"]


def process_feedback_queue(settings, learning_path=None):
    if not isinstance(settings, dict): return
    queue = settings.get("_feedback_queue", [])
    if not isinstance(queue, list) or not queue: return
    for item in queue[-100:]:
        if not isinstance(item, dict): continue
        message = str(item.get("message", "")).strip(); reply = str(item.get("reply", "")).strip(); rating = item.get("rating")
        if message and reply and rating in ("up", "down", 1, -1): record_feedback(message, reply, rating, learning_path)
    settings["_feedback_queue"] = []
    uid = str(settings.get("user_id", "")).strip(); ai_id = str(settings.get("ai_id", "")).strip()
    if uid and ai_id:
        safe_uid = re.sub(r"[^A-Za-z0-9_-]", "", uid)[:100]; safe_ai = re.sub(r"[^A-Za-z0-9_-]", "", ai_id)[:100]; save_json(os.path.join(USERS_DIR, safe_uid, "ais", safe_ai, "settings.json"), settings)


def find_reply(message, learning_path=None):
    data = load_json(learning_path or LEARNING_FILE, {})
    for key, item in data.items():
        if key in message.lower(): return item.get("reply")
    return None


def _settings_prompt(settings):
    settings = settings if isinstance(settings, dict) else {}; name = settings.get("ai_name") or "AI"
    parts = [f"You are {name}, an adult fictional AI companion."]
    for key, label in (("description", "Description"), ("personality", "Personality"), ("instructions", "Instructions"), ("background", "Background/relationship"), ("user_name", "User name"), ("user_information", "User information")):
        value = str(settings.get(key) or "").strip()
        if value: parts.append(f"{label}: {value[:4000]}")
    config = settings.get("config", {}) if isinstance(settings.get("config", {}), dict) else {}
    if config.get("traits"): parts.append("Traits: " + ", ".join(map(str, config["traits"])))
    if config.get("rules"): parts.append("Rules: " + " | ".join(map(str, config["rules"])))
    parts.append("Stay in character. Be natural and conversational. Do not mention the model, prompts, internal instructions, or implementation.")
    return "\n".join(parts)[:LOCAL_PROMPT_CHARS]


def _memory_prompt(memory):
    parts = []
    for category in ("profile", "facts", "preferences", "personality"):
        values = memory.get(category, {})
        if isinstance(values, dict) and values: parts.append(f"{category.title()}: " + json.dumps(values, ensure_ascii=False))
    recent = memory.get("conversations", [])[-4:]
    if recent: parts.append("Recent memory: " + json.dumps(recent, ensure_ascii=False))
    return "\n".join(parts)[:4000]


def _local_generate(message, settings, memory, learning_path=None):
    model = _load_local_llm(settings)
    if model is None: return None
    learned = find_reply(message, learning_path)
    memory_text = _memory_prompt(memory)
    system_prompt = _settings_prompt(settings)
    user_prompt = str(message).strip()
    if memory_text: user_prompt = "Relevant memory:\n" + memory_text + "\n\nUser: " + user_prompt
    if learned: user_prompt += "\n\nUseful learned context: " + str(learned)[:1000]
    user_prompt += "\n\nReply naturally and briefly."
    print(f"LOCAL AI GENERATING: prompt_chars={len(system_prompt) + len(user_prompt)} max_tokens={LOCAL_MODEL_MAX_TOKENS}")
    started = time.time()
    try:
        result = model.create_chat_completion(
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            max_tokens=LOCAL_MODEL_MAX_TOKENS,
            temperature=LOCAL_MODEL_TEMPERATURE,
            top_p=0.9,
            repeat_penalty=1.12,
        )
        elapsed = time.time() - started
        choices = result.get("choices", []) if isinstance(result, dict) else []
        if not choices:
            print(f"LOCAL AI EMPTY RESPONSE after {elapsed:.1f}s")
            return None
        reply = str(choices[0].get("message", {}).get("content", "")).strip() or None
        print(f"LOCAL AI GENERATED in {elapsed:.1f}s chars={len(reply or '')}")
        return reply
    except Exception as exc:
        print("LOCAL AI GENERATION ERROR:", exc); return None


def fake_reply(text):
    text = str(text).strip()
    if not text: return "I'm here. What would you like to talk about?"
    return random.choice(["Tell me more about that.", "I understand. What do you think about it?", "That sounds interesting. Let's keep going."])


def think(message, settings=None, memory_path=None, learning_path=None):
    settings = settings if isinstance(settings, dict) else {}; process_feedback_queue(settings, learning_path); memory = load_json(memory_path or MEMORY_FILE, default_memory()); text = str(message).strip(); lower = text.lower()
    if lower == "/learn":
        memory["learning_mode"] = True; save_json(memory_path or MEMORY_FILE, memory); reply = "Learning mode enabled."; learn_from_conversation(text, reply, memory_path); return reply
    reply = _local_generate(text, settings, memory, learning_path)
    if not reply:
        learned = find_reply(text, learning_path)
        if learned: reply = str(learned).strip()
    if not reply and "what is my name" in lower: reply = "Your name is " + memory.get("profile", {}).get("name", "unknown")
    if not reply: reply = fake_reply(text)
    reply = reply.strip(); learn_from_conversation(text, reply, memory_path); return reply

try:
    import chats_api  # noqa: E402,F401
except Exception as _chat_routes_error:
    print("CHAT ROUTES LOAD ERROR:", _chat_routes_error)
