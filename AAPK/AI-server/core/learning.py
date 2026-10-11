"""Learning boundary for the local/fake AI and feedback system."""
from brain import learn_from_conversation as _learn_from_conversation
from brain import record_feedback as _record_feedback
from core.conversations import get_conversation, save_conversation


def learn_message(user, reply, memory_path=None):
    return _learn_from_conversation(user, reply, memory_path)


def learn(uid, ai_id):
    data = get_conversation(uid, ai_id)
    conversation = data.get("conversation", [])
    if not conversation:
        return None
    result = None
    for item in conversation:
        if not isinstance(item, dict):
            continue
        user = item.get("user", item.get("content", ""))
        reply = item.get("ai", item.get("reply", ""))
        if user and reply:
            result = _learn_from_conversation(user, reply)
    return result


def record_feedback(uid, ai_id, message_index, feedback):
    data = get_conversation(uid, ai_id)
    messages = data.get("conversation", [])
    try:
        index = int(message_index)
    except (TypeError, ValueError):
        return False
    if index < 0 or index >= len(messages):
        return False
    if feedback not in ("up", "down", "positive", "negative", 1, -1):
        return False
    message = messages[index]
    if not isinstance(message, dict):
        return False
    user = str(message.get("user", message.get("content", ""))).strip()
    reply = str(message.get("ai", message.get("reply", ""))).strip()
    if not user or not reply:
        return False
    message["feedback"] = feedback
    rating = 1 if feedback in ("up", "positive", 1) else -1
    _record_feedback(user, reply, rating)
    save_conversation(uid, ai_id, data)
    return True
