"""Stage 4 conversation/learning compatibility bridge."""
from brain import learn_from_conversation as _brain_learn
from brain import record_feedback as _brain_feedback
from core import server_impl
from core.conversations import get_conversation, save_conversation as _save_conversation
from core.learning import record_feedback as record_conversation_feedback


def learn_message(user, reply, memory_path=None):
    return _brain_learn(user, reply, memory_path)


def save_message(uid, ai_id, user_message, ai_reply, image=None):
    """Authoritative persistence boundary for a complete chat exchange."""
    data = get_conversation(uid, ai_id)
    now = __import__("time").time()
    user_text = str(user_message or "")
    ai_text = str(ai_reply or "")
    entry = {
        "user": user_text,
        "ai": ai_text,
        "AI": ai_text,
        "assistant": ai_text,
        "user_message": user_text,
        "ai_reply": ai_text,
        "image": image,
        "time": now,
        "timestamp": now,
    }
    data.setdefault("conversation", [])
    data["conversation"].append(entry)
    data["updated"] = now
    data.setdefault("created", now)

    # Write the complete exchange, then verify that the exact record survived
    # the storage boundary. This prevents a successful chat response from
    # being returned when only one side was actually persisted.
    _save_conversation(uid, ai_id, data)
    saved = get_conversation(uid, ai_id)
    if not saved.get("conversation") or saved["conversation"][-1].get("user_message") != user_text or saved["conversation"][-1].get("ai_reply") != ai_text:
        _save_conversation(uid, ai_id, data)
        saved = get_conversation(uid, ai_id)
    if not saved.get("conversation") or saved["conversation"][-1].get("user_message") != user_text or saved["conversation"][-1].get("ai_reply") != ai_text:
        raise IOError("Conversation persistence verification failed")
    return saved


def apply():
    server_impl.save_conversation = save_message
    server_impl.learn_from_conversation = learn_message
    return server_impl


def feedback(uid, ai_id, message_index, rating):
    return record_conversation_feedback(uid, ai_id, message_index, rating)


def feedback_for_reply(message, reply, rating, learning_path=None):
    return _brain_feedback(message, reply, rating, learning_path)
