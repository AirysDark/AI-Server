"""Conversation storage helpers.

Keeps conversation persistence separate from HTTP routing and AI provider code.
"""
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
    save_conversation_data(uid, ai_id, data)


def append_message(uid, ai_id, role, content, **extra):
    data = get_conversation(uid, ai_id)
    message = {"role": role, "content": content}
    message.update(extra)
    data["conversation"].append(message)
    save_conversation(uid, ai_id, data)
    return message
