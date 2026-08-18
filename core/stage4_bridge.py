"""Stage 4 conversation/learning compatibility bridge."""
from brain import learn_from_conversation as _brain_learn
from brain import record_feedback as _brain_feedback
from core import server_impl
from core.conversations import get_conversation, save_conversation as _save_conversation
from core.learning import record_feedback as record_conversation_feedback


def learn_message(user, reply, memory_path=None):
    """Keep the legacy learning call signature while using the Stage 4 boundary."""
    return _brain_learn(user, reply, memory_path)


def save_message(uid, ai_id, user_message, ai_reply, image=None):
    """Persist every exchange in a backwards-compatible format.

    Older clients used ``AI`` while the current server uses ``ai``. Store both
    spellings, plus both timestamp names, so an existing client can never
    silently lose the assistant side when the page is refreshed.
    """
    data = get_conversation(uid, ai_id)
    now = __import__("time").time()
    user_text = str(user_message or "")
    ai_text = str(ai_reply or "")
    data.setdefault("conversation", []).append({
        "user": user_text,
        "ai": ai_text,
        "AI": ai_text,
        "assistant": ai_text,
        "image": image,
        "time": now,
        "timestamp": now,
    })
    data["updated"] = now
    data.setdefault("created", now)
    _save_conversation(uid, ai_id, data)
    return data


def apply():
    """Route legacy conversation persistence/learning through Stage 4 modules."""
    server_impl.save_conversation = save_message
    server_impl.learn_from_conversation = learn_message
    return server_impl


def feedback(uid, ai_id, message_index, rating):
    return record_conversation_feedback(uid, ai_id, message_index, rating)


def feedback_for_reply(message, reply, rating, learning_path=None):
    return _brain_feedback(message, reply, rating, learning_path)
