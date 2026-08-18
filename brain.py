import json
import os
import random
import re
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEMORY_FILE = os.path.join(BASE_DIR, "memory.json")
LEARNING_FILE = os.path.join(BASE_DIR, "learning", "replies.json")
TRAINING_FILE = os.path.join(BASE_DIR, "learning", "training.json")


def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    if os.path.dirname(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def default_memory():
    return {"profile": {}, "facts": {}, "preferences": {}, "personality": {}, "conversations": [], "learning_mode": True}


def remember(memory, category, key, value):
    memory.setdefault(category, {})
    memory[category][key.lower().strip()] = str(value).strip()


def learn_from_conversation(user, reply, memory_path=None):
    path = memory_path or MEMORY_FILE
    memory = load_json(path, default_memory())
    memory.setdefault("conversations", [])
    memory["conversations"].append({"time": datetime.now().isoformat(), "user": user, "AI": reply})
    memory["conversations"] = memory["conversations"][-500:]

    text = str(user).lower()
    if "my name is " in text:
        remember(memory, "profile", "name", str(user).split("my name is ", 1)[1])

    for key in ["i like", "i love", "i prefer", "i use", "my project"]:
        if key in text:
            remember(memory, "facts", key, user)

    save_json(path, memory)


def learn_reply(trigger, reply, learning_path=None):
    path = learning_path or LEARNING_FILE
    data = load_json(path, {})
    item = data.get(trigger.lower().strip(), {"score": 0, "uses": 0})
    item["reply"] = str(reply).strip()
    item["uses"] += 1
    item["learned"] = datetime.now().isoformat()
    data[trigger.lower().strip()] = item
    save_json(path, data)


def find_reply(message, learning_path=None):
    data = load_json(learning_path or LEARNING_FILE, {})
    for key, item in data.items():
        if key in message.lower():
            return item.get("reply")
    return None


def decide(message):
    lower = message.lower()
    if any(k in lower for k in ["photo", "picture", "cat", "image", "meme", "send me"]):
        return {"action": "send_image"}
    return {"action": "text"}


def think(message, settings=None, memory_path=None, learning_path=None):
    memory = load_json(memory_path or MEMORY_FILE, default_memory())
    text = str(message).strip()
    lower = text.lower()

    if lower == "/learn":
        memory["learning_mode"] = True
        save_json(memory_path or MEMORY_FILE, memory)
        return "Learning mode enabled."

    decision = decide(text)
    if decision.get("action") == "send_image":
        return "Here is a picture for you!"

    learned = find_reply(text, learning_path)
    if learned:
        return learned

    if "what is my name" in lower:
        return "Your name is " + memory.get("profile", {}).get("name", "unknown")

    return random.choice(["Tell me more.", "I am learning from our conversations.", "I will remember useful details."])
