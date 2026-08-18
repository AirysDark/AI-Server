"""Conversation storage helpers.

Keeps conversation persistence separate from HTTP routing and AI provider code.
Both sides of every exchange are persisted in the configured AI-Server storage.
"""
from time import time

from core.ai_manager import load_conversation, save_conversation_data


def get_conversation(uid, ai_id):
    data = load_conversation(uid, ai_id)
    if not isinstance(data, dict):
        data = {"conversation": [], "memory": {}, "proactive_state": {}}
    data.setdefault("conversation", [])
    data.setdefault("memory", {})
    data.setdefault("proactive_state", {})
    return data


def save_conversation(uid, ai_id, data):
    """Persist the complete conversation without dropping existing messages."""
    if not isinstance(data, dict):
        data = {"conversation": []}
    data.setdefault("conversation", [])
    data.setdefault("memory", {})
    data.setdefault("proactive_state", {})
    data["updated"] = time()
    save_conversation_data(uid, ai_id, data)


def append_message(uid, ai_id, role, content, **extra):
    data = get_conversation(uid, ai_id)
    message = {"role": role, "content": content}
    message.update(extra)
    data["conversation"].append(message)
    save_conversation(uid, ai_id, data)
    return message


def append_exchange(uid, ai_id, user_message, ai_reply, image=None):
    """Persist the user's message and AI reply together."""
    data = get_conversation(uid, ai_id)
    now = time()
    data["conversation"].append({
        "user": str(user_message or ""),
        "ai": str(ai_reply or ""),
        "image": image,
        "time": now,
    })
    data["updated"] = now
    data.setdefault("created", now)
    save_conversation_data(uid, ai_id, data)
    return data
