"""Conversation bridge: persist archives, repair stale chats, and generate images."""
import os, threading, time
from brain import learn_from_conversation as _brain_learn
from brain import record_feedback as _brain_feedback
from api.image_generation import generate_to_directory, is_image_request
from core import server_impl
from core.ai_manager import (
    ai_photo_dir,
    ensure_archived_conversation,
    load_archived_conversation,
    load_settings,
    save_archived_conversation,
)
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
    cid,data=ensure_archived_conversation(uid,ai_id,cid)
    _context.conversation_id=cid
    now=time.time(); user_text=str(user_message or ""); ai_text=str(ai_reply or "")
    data.setdefault("conversation",[]).append({"user":user_text,"ai":ai_text,"AI":ai_text,"assistant":ai_text,"user_message":user_text,"ai_reply":ai_text,"image":image,"time":now,"timestamp":now})
    data["updated"]=now; save_archived_conversation(uid,ai_id,cid,data)
    saved=load_archived_conversation(uid,ai_id,cid)
    if not saved or not saved.get("conversation") or saved["conversation"][-1].get("user_message")!=user_text or saved["conversation"][-1].get("ai_reply")!=ai_text: raise IOError("Conversation persistence verification failed")
    return saved

def _token_for_image(settings):
    return str(settings.get("hf_token") or settings.get("api_token") or os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_API_TOKEN") or "").strip()

def _install_chat_result_wrapper():
    if getattr(server_impl,"_image_generation_chat_installed",False): return
    original_chat_result=server_impl._chat_result
    def chat_result(uid,ai_id,conversation_id,message,image_data=None,image_name=None):
        # Never fail a chat merely because the browser supplied a stale conversation id.
        cid,_=ensure_archived_conversation(uid,ai_id,conversation_id)
        _context.conversation_id=cid
        result=original_chat_result(uid,ai_id,cid,message,image_data,image_name)
        settings=load_settings(uid,ai_id)
        features=settings.get("features",{}) if isinstance(settings.get("features"),dict) else {}
        generation_enabled=features.get("image_generation",features.get("automatic_images",False)) is True
        prompt=str(message or "").strip()
        if generation_enabled and not image_data and is_image_request(prompt):
            try:
                filename,model=generate_to_directory(
                    _token_for_image(settings),
                    prompt,
                    ai_photo_dir(uid,ai_id),
                    model=settings.get("image_generation_model"),
                )
                image_url=f"/users/{uid}/ais/{ai_id}/ai_photos/{filename}"
                result["image"]=image_url
                result["image_generated"]=True
                result["image_model"]=model
                archive=load_archived_conversation(uid,ai_id,cid)
                if archive and archive.get("conversation"):
                    archive["conversation"][-1]["image"]=image_url
                    archive["conversation"][-1]["image_generated"]=True
                    archive["updated"]=time.time()
                    save_archived_conversation(uid,ai_id,cid,archive)
                print("CHAT IMAGE GENERATED:",f"ai_id={ai_id}",f"conversation_id={cid}",f"model={model}",f"image={image_url}")
            except Exception as exc:
                # Chat text still succeeds; existing photo-library behavior remains a fallback.
                result["image_generation_error"]=str(exc)[:500]
                print("CHAT IMAGE GENERATION FAILED:",str(exc)[:1000])
        return result
    server_impl._chat_result=chat_result
    server_impl._image_generation_chat_installed=True

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
    _install_chat_result_wrapper()
    _install_context_wrappers()
    return server_impl

def feedback(uid,ai_id,message_index,rating): return record_conversation_feedback(uid,ai_id,message_index,rating)
def feedback_for_reply(message,reply,rating,learning_path=None): return _brain_feedback(message,reply,rating,learning_path)
