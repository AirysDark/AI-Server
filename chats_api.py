"""Direct conversation archive API. Each C-*.json is an independent chat."""
import json, os, re, time, uuid
from core.ai_manager import active_ai, conversations_root, load_archived_conversation, save_archived_conversation
from core.storage import load_json, save_json

def _safe(value): return re.sub(r"[^A-Za-z0-9_-]", "", str(value or ""))[:100]
def _title(data):
    explicit=str(data.get("title","")).strip() if isinstance(data,dict) else ""
    if explicit:return explicit[:80]
    for item in data.get("conversation",[]):
        text=str(item.get("user",item.get("user_message",item.get("content","")))).strip()
        if text:
            text=" ".join(text.split()); return text[:60]+("..." if len(text)>60 else "")
    return "New chat"
def _normalise_record(record,cid=None):
    if not isinstance(record,dict):return None
    data=record.get("data") if isinstance(record.get("data"),dict) else record
    if not isinstance(data,dict) or not isinstance(data.get("conversation"),list):return None
    return {"conversation_id":cid or record.get("conversation_id") or "","title":record.get("title") or data.get("title") or _title(data),"created":record.get("created",data.get("created",0)),"updated":record.get("updated",data.get("updated",0)),"data":data}

def list_chats(uid,ai_id):
    root=conversations_root(uid,ai_id); os.makedirs(root,exist_ok=True); result=[]
    for name in os.listdir(root):
        if not name.endswith(".json") or name=="current.json":continue
        try:
            record=_normalise_record(load_json(os.path.join(root,name),{}),os.path.splitext(name)[0])
            if record and record["conversation_id"] and record["data"].get("conversation"):
                result.append({k:record.get(k) for k in ("conversation_id","title","created","updated")})
        except Exception:continue
    result.sort(key=lambda x:x.get("updated",0) or 0,reverse=True); return result

def new_chat(uid,ai_id):
    cid="C-"+uuid.uuid4().hex[:16]; now=time.time(); data={"conversation":[],"memory":{},"proactive_state":{},"created":now,"updated":now,"title":"New chat"}
    save_archived_conversation(uid,ai_id,cid,data); return {"ok":True,"conversation_id":cid,"data":data}

def open_chat(uid,ai_id,cid):
    cid=_safe(cid)
    if not cid or cid=="current":return None
    return load_archived_conversation(uid,ai_id,cid)

def rename_chat(uid,ai_id,cid,title):
    cid=_safe(cid); title=" ".join(str(title or "").strip().split())[:80]
    if not title or not cid or cid=="current":return False
    path=os.path.join(conversations_root(uid,ai_id),cid+".json"); record=load_json(path,None)
    if not isinstance(record,dict):return False
    target=record.get("data") if isinstance(record.get("data"),dict) else record
    target["title"]=title; target["updated"]=time.time()
    save_json(path,record); return True

def install_handler_routes(handler_class,server_module):
    if getattr(handler_class,"_chat_routes_installed",False):return
    original_get,original_post=handler_class.do_GET,handler_class.do_POST
    def do_get(self):
        if self.path.split("?",1)[0]=="/api/chats":
            uid,ai_id=active_ai(self)
            if not uid:return self.send_json({"ok":False,"error":"Authentication required"},None,401)
            return self.send_json({"ok":True,"ai_id":ai_id,"chats":list_chats(uid,ai_id)},uid,200,ai_id)
        return original_get(self)
    def do_post(self):
        path=self.path.split("?",1)[0]
        if path not in ("/api/chats/new","/api/chats/open","/api/chats/rename"):return original_post(self)
        uid,ai_id=active_ai(self)
        if not uid:return self.send_json({"ok":False,"error":"Authentication required"},None,401)
        try:
            length=int(self.headers.get("Content-Length",0)); data=json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        except Exception:return self.send_json({"ok":False,"error":"Invalid JSON"},uid,400,ai_id)
        if path=="/api/chats/new":return self.send_json(new_chat(uid,ai_id),uid,200,ai_id)
        cid=str(data.get("conversation_id","")).strip()
        if not cid:return self.send_json({"ok":False,"error":"conversation_id required"},uid,400,ai_id)
        if path=="/api/chats/rename":
            if not rename_chat(uid,ai_id,cid,data.get("title")):return self.send_json({"ok":False,"error":"Unable to rename conversation"},uid,400,ai_id)
            return self.send_json({"ok":True,"conversation_id":cid},uid,200,ai_id)
        result=open_chat(uid,ai_id,cid)
        if result is None:return self.send_json({"ok":False,"error":"Conversation not found"},uid,404,ai_id)
        # Return the archive payload both directly and under data so all existing clients can consume it.
        return self.send_json({"ok":True,"conversation_id":cid,"conversation":result.get("conversation",[]),"memory":result.get("memory",{}),"proactive_state":result.get("proactive_state",{}),"created":result.get("created"),"updated":result.get("updated"),"data":result},uid,200,ai_id)
    handler_class.do_GET=do_get; handler_class.do_POST=do_post; handler_class._chat_routes_installed=True
