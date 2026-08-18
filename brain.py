import json
import os
import random
import re
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEMORY_FILE = os.path.join(BASE_DIR, "memory.json")
LEARNING_FILE = os.path.join(BASE_DIR, "learning", "replies.json")
TRAINING_FILE = os.path.join(BASE_DIR, "learning", "training.json")
FEEDBACK_FILE = os.path.join(BASE_DIR, "learning", "feedback.json")
FAKE_AI_UPGRADE_NOTICE = "For full AI add Hugging Face token."


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
    path = memory_path or MEMORY_FILE; memory = load_json(path, default_memory()); memory.setdefault("conversations", [])
    entry = {"time": datetime.now().isoformat(), "user": user, "AI": reply}
    if memory["conversations"] and memory["conversations"][-1].get("user") == user and memory["conversations"][-1].get("AI") == reply: return
    memory["conversations"].append(entry); memory["conversations"] = memory["conversations"][-500:]
    text = str(user).lower()
    if "my name is " in text: remember(memory, "profile", "name", str(user).split("my name is ", 1)[1])
    for key in ["i like", "i love", "i prefer", "i use", "my project"]:
        if key in text: remember(memory, "facts", key, user)
    save_json(path, memory)


def learn_online_response(user, reply, settings=None):
    settings = settings or {}; uid = str(settings.get("user_id", "")).strip(); ai_id = str(settings.get("ai_id", "")).strip()
    if not uid or not ai_id: return
    safe_uid = re.sub(r"[^A-Za-z0-9_-]", "", uid)[:100]; safe_ai = re.sub(r"[^A-Za-z0-9_-]", "", ai_id)[:100]
    learn_from_conversation(user, reply, os.path.join(BASE_DIR, "users", safe_uid, "ais", safe_ai, "brain_memory.json"))


def learn_reply(trigger, reply, learning_path=None):
    path = learning_path or LEARNING_FILE; data = load_json(path, {}); key = trigger.lower().strip(); item = data.get(key, {"score": 0, "uses": 0})
    item["reply"] = str(reply).strip(); item["uses"] = item.get("uses", 0) + 1; item["learned"] = datetime.now().isoformat(); data[key] = item; save_json(path, data)


def record_feedback(trigger, reply, rating, learning_path=None, feedback_path=None):
    rating = 1 if str(rating).lower() in ("up", "1", "positive", "good") else -1
    path = learning_path or LEARNING_FILE; data = load_json(path, {}); key = str(trigger).lower().strip(); item = data.get(key, {"score": 0, "uses": 0})
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
        safe_uid = re.sub(r"[^A-Za-z0-9_-]", "", uid)[:100]; safe_ai = re.sub(r"[^A-Za-z0-9_-]", "", ai_id)[:100]
        save_json(os.path.join(BASE_DIR, "users", safe_uid, "ais", safe_ai, "settings.json"), settings)


def find_reply(message, learning_path=None):
    data = load_json(learning_path or LEARNING_FILE, {})
    for key, item in data.items():
        if key in message.lower(): return item.get("reply")
    return None


def decide(message):
    if any(k in message.lower() for k in ["photo", "picture", "cat", "image", "meme", "send me"]): return {"action": "send_image"}
    return {"action": "text"}


def fake_reply(text):
    text = str(text).strip()
    if not text: return FAKE_AI_UPGRADE_NOTICE
    if FAKE_AI_UPGRADE_NOTICE.lower() in text.lower(): return text
    return f"{text}\n\n{FAKE_AI_UPGRADE_NOTICE}"


def think(message, settings=None, memory_path=None, learning_path=None):
    settings = settings if isinstance(settings, dict) else {}
    process_feedback_queue(settings, learning_path)
    memory = load_json(memory_path or MEMORY_FILE, default_memory()); text = str(message).strip(); lower = text.lower()
    if lower == "/learn":
        memory["learning_mode"] = True; save_json(memory_path or MEMORY_FILE, memory); reply = fake_reply("Learning mode enabled."); learn_from_conversation(text, reply, memory_path); return reply
    if decide(text).get("action") == "send_image":
        reply = fake_reply("Here is a picture for you!"); learn_from_conversation(text, reply, memory_path); return reply
    learned = find_reply(text, learning_path)
    if learned:
        reply = fake_reply(learned); learn_from_conversation(text, reply, memory_path); return reply
    if "what is my name" in lower:
        reply = fake_reply("Your name is " + memory.get("profile", {}).get("name", "unknown")); learn_from_conversation(text, reply, memory_path); return reply
    reply = fake_reply(random.choice(["Tell me more.", "I am learning from our conversations.", "I will remember useful details."])); learn_from_conversation(text, reply, memory_path); return reply

# Importing this module also installs the conversation HTTP routes once
# AIHandler has finished being defined. This keeps the conversation API
# available in both standalone server.py and the PythonAnywhere WSGI app.
try:
    import chats_api  # noqa: E402,F401
except Exception as _chat_routes_error:
    print("CHAT ROUTES LOAD ERROR:", _chat_routes_error)
