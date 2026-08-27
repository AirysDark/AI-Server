"""Conversation bridge: persist and load directly from the selected archive file."""
import threading, time
from brain import learn_from_conversation as _brain_learn
from brain import record_feedback as _brain_feedback
from core import server_impl
from core.ai_manager import load_archived_conversation, save_archived_conversation
from core.learning import record_feedback as record_conversation_feedback
_context=threading.local()

def selected_id(): return getattr(_context,"conversation_id",None)
def learn_message(user,reply,memory_path=None): return _brain_learn(user,reply,memory_path)
def selected_conversation(uid,ai_id):
    cid=selected_id()
    if cid:
        data=load_archived_conversation(uid,ai_id,cid)
        if data is not None:return data
    return {"conversation":[],"memory":{},"proactive_state":{}}
def save_message(uid,ai_id,*args):
    """Persist a chat message while supporting both old and new server signatures.

    Old: save_message(uid, ai_id, user_message, ai_reply, image=None)
    New: save_message(uid, ai_id, conversation_id, user_message, ai_reply, image=None)
    """
    if len(args) == 2:
        cid=selected_id(); user_message,ai_reply=args; image=None
    elif len(args) == 3:
        cid=selected_id(); user_message,ai_reply,image=args
    elif len(args) == 4:
        cid,user_message,ai_reply,image=args
    else:
        raise TypeError(f"save_message() expected 4 to 6 total positional arguments, got {len(args)+2}")
    cid=str(cid or selected_id() or "").strip()
    if not cid: raise IOError("No conversation selected")
    data=load_archived_conversation(uid,ai_id,cid) or {"conversation":[],"memory":{},"proactive_state":{},"created":time.time()}
    now=time.time(); user_text=str(user_message or ""); ai_text=str(ai_reply or "")
    data.setdefault("conversation",[]).append({"user":user_text,"ai":ai_text,"AI":ai_text,"assistant":ai_text,"user_message":user_text,"ai_reply":ai_text,"image":image,"time":now,"timestamp":now})
    data["updated"]=now; save_archived_conversation(uid,ai_id,cid,data)
    saved=load_archived_conversation(uid,ai_id,cid)
    if not saved or not saved.get("conversation") or saved["conversation"][-1].get("user_message")!=user_text or saved["conversation"][-1].get("ai_reply")!=ai_text: raise IOError("Conversation persistence verification failed")
    return saved

def _install_context_wrappers():
    if getattr(server_impl,"_direct_chat_archive_installed",False):return
    original_get,original_post=server_impl.AIHandler.do_GET,server_impl.AIHandler.do_POST
    def do_get(handler):
        path=handler.path.split("?",1)[0]
        if path=="/api/user":
            from core.ai_manager import active_ai
            uid,ai_id=active_ai(handler)
            if not uid:return handler.send_json({"error":"Authentication required"},status=401)
            from core.auth import cookie
            cid=cookie(handler,"AI_chat")
            data=load_archived_conversation(uid,ai_id,cid) if cid else {"conversation":[],"memory":{},"proactive_state":{}}
            return handler.send_json(data or {"conversation":[],"memory":{},"proactive_state":{}},uid,200,ai_id)
        return original_get(handler)
    def do_post(handler):
        path=handler.path.split("?",1)[0]
        if path=="/chat":
            from core.auth import cookie
            _context.conversation_id=cookie(handler,"AI_chat")
            try:return original_post(handler)
            finally:_context.conversation_id=None
        return original_post(handler)
    server_impl.AIHandler.do_GET=do_get; server_impl.AIHandler.do_POST=do_post; server_impl._direct_chat_archive_installed=True

def apply():
    server_impl.save_conversation=save_message
    server_impl.load_conversation=selected_conversation
    server_impl.learn_from_conversation=learn_message
    _install_context_wrappers()
    return server_impl

def feedback(uid,ai_id,message_index,rating): return record_conversation_feedback(uid,ai_id,message_index,rating)
def feedback_for_reply(message,reply,rating,learning_path=None): return _brain_feedback(message,reply,rating,learning_path)
