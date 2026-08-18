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
    data = get_conversation(uid, ai_id)
    now = __import__("time").time()
    data.setdefault("conversation", []).append({
        "user": user_message,
        "ai": ai_reply,
        "image": image,
        "time": now,
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
