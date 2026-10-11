"""Conversation storage helpers.

Keeps conversation persistence separate from HTTP routing and AI provider code.
Both sides of every exchange are persisted in the configured AI-Server storage.
"""
from time import time

from core.ai_manager import load_conversation, save_conversation_data


def get_conversation(uid, ai_id, chat_id=None):
    data = load_conversation(uid, ai_id, chat_id)
    if not isinstance(data, dict):
        data = {"conversation": [], "memory": {}, "proactive_state": {}}
    data.setdefault("conversation", [])
    data.setdefault("memory", {})
    data.setdefault("proactive_state", {})
    return data


def save_conversation(uid, ai_id, data, chat_id=None):
    """Persist the complete conversation to its archive."""
    if not isinstance(data, dict):
        data = {"conversation": []}
    data.setdefault("conversation", [])
    data.setdefault("memory", {})
    data.setdefault("proactive_state", {})
    data["updated"] = time()
    return save_conversation_data(uid, ai_id, data, chat_id)


def append_message(uid, ai_id, role, content, chat_id=None, **extra):
    data = get_conversation(uid, ai_id, chat_id)
    message = {"role": role, "content": content}
    message.update(extra)
    data["conversation"].append(message)
    save_conversation(uid, ai_id, data, chat_id)
    return message


def append_exchange(uid, ai_id, user_message, ai_reply, image=None, chat_id=None):
    """Persist the user's message and AI reply together."""
    data = get_conversation(uid, ai_id, chat_id)
    now = time()
    data["conversation"].append({
        "user": str(user_message or ""),
        "ai": str(ai_reply or ""),
        "image": image,
        "time": now,
    })
    data["updated"] = now
    data.setdefault("created", now)
    save_conversation_data(uid, ai_id, data, chat_id)
    return data
