"""Multi-AI conversation rooms."""
import copy, json, os, re, time, uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Lock, Event
from core.ai_manager import list_ais, load_settings, ai_root
from core.auth import current_user
from core.config import USERS_DIR, MAX_AIS_PER_ACCOUNT
from core.storage import load_json, save_json
from core.server_impl import ask_online, think, clean_reply, features, ai_profile

_ROOM_LOCKS = {}; _ROOM_LOCKS_GUARD = Lock(); _AI_EXECUTOR = ThreadPoolExecutor(max_workers=8)
_TALK_STOPS = {}; _TALK_GUARD = Lock()

def _room_lock(uid,cid):
    with _ROOM_LOCKS_GUARD: return _ROOM_LOCKS.setdefault(f"{uid}:{cid}",Lock())
def _talk_key(uid,cid): return f"{uid}:{cid}"
def _stop_talk(uid,cid):
    with _TALK_GUARD:
        event=_TALK_STOPS.get(_talk_key(uid,cid))
        if event: event.set()
        _TALK_STOPS.pop(_talk_key(uid,cid),None)
def _safe(value,prefix=None):
    text=re.sub(r"[^A-Za-z0-9_-]","",str(value or ""))[:100]
    return text if not prefix or text.startswith(prefix) else ""
def _root(uid): return os.path.join(USERS_DIR,_safe(uid),"multi_chats")
def _rooms(uid):
    path=os.path.join(_root(uid),"rooms"); os.makedirs(path,exist_ok=True); return path
def _path(uid,cid): return os.path.join(_rooms(uid),_safe(cid)+".json")
def _new_id(): return "MC-"+uuid.uuid4().hex[:16]

def _default_talk_settings(ais):
    return {"enabled":False,"instructions":"Talk naturally to the other AIs. Recognize each participant by name, respond to what they just said, and continue the discussion naturally. Stay in character according to your own AI settings and personality.","relationship":"The AIs are participants in the same conversation. Define their relationship here so they understand how they should interact with each other.","names":{ai_id:"" for ai_id in ais},"delay_seconds":0.5}

def _normalize_talk_settings(room):
    d=_default_talk_settings(room.get("ais",[])); s=room.get("talk_settings")
    if not isinstance(s,dict): s=d
    s.setdefault("enabled",False); s.setdefault("instructions",d["instructions"]); s.setdefault("relationship",d["relationship"]); s.setdefault("names",{}); s.setdefault("delay_seconds",0.5)
    try: s["delay_seconds"]=max(0,min(10,float(s.get("delay_seconds",.5))))
    except Exception: s["delay_seconds"]=.5
    for ai_id in room.get("ais",[]): s["names"].setdefault(ai_id,"")
    s["names"]={str(k):str(v or "")[:80] for k,v in s["names"].items() if str(k) in room.get("ais",[])}
    room["talk_settings"]=s; return s

def _room_title(room):
    title=str(room.get("title","")).strip()
    if title:return title[:80]
    for x in room.get("conversation",[]):
        if x.get("type")=="user" and str(x.get("text","")).strip():
            t=" ".join(str(x["text"]).split()); return t[:60]+("..." if len(t)>60 else "")
    return "New conversation"
def _save_index(uid,rooms): os.makedirs(_root(uid),exist_ok=True); save_json(os.path.join(_root(uid),"index.json"),rooms)
def _list(uid):
    result=[]
    for name in os.listdir(_rooms(uid)):
        if not name.startswith("MC-") or not name.endswith(".json"): continue
        try:
            room=load_json(os.path.join(_rooms(uid),name),None)
            if isinstance(room,dict): result.append({"conversation_id":_safe(room.get("conversation_id") or name[:-5],"MC-"),"title":_room_title(room),"ais":room.get("ais",[]),"created":room.get("created",0),"updated":room.get("updated",0)})
        except Exception: pass
    result.sort(key=lambda x:x.get("updated",0) or 0,reverse=True); _save_index(uid,result); return result

def _load(uid,cid):
    cid=_safe(cid,"MC-"); room=load_json(_path(uid,cid),None) if cid else None
    if not isinstance(room,dict) or room.get("conversation_id")!=cid:return None
    room.setdefault("conversation",[]); room.setdefault("ais",[]); room.setdefault("pending_ai",[]); _normalize_talk_settings(room); return room

def _valid_ai_ids(uid,ids):
    available={x["ai_id"] for x in list_ais(uid)}; out=[]
    for x in ids or []:
        x=str(x)
        if x in available and x not in out: out.append(x)
    return out

def new_room(uid):
    ais=list_ais(uid); selected=[x["ai_id"] for x in ais[:1]]; now=time.time()
    room={"conversation_id":_new_id(),"title":"New conversation","ais":selected,"conversation":[],"pending_ai":[],"talk_settings":_default_talk_settings(selected),"created":now,"updated":now}
    save_json(_path(uid,room["conversation_id"]),room); _list(uid); return room

def rename_room(uid,cid,title):
    with _room_lock(uid,cid):
        room=_load(uid,cid); title=" ".join(str(title or "").strip().split())[:80]
        if not room or not title:return False
        room["title"]=title; room["updated"]=time.time(); save_json(_path(uid,cid),room)
    _list(uid); return True

def delete_room(uid,cid):
    _stop_talk(uid,cid)
    with _room_lock(uid,cid):
        room=_load(uid,cid)
        if not room:return False
        try: os.remove(_path(uid,cid))
        except FileNotFoundError:return False
    _list(uid); return True

def set_participants(uid,cid,ids):
    with _room_lock(uid,cid):
        room=_load(uid,cid); valid=_valid_ai_ids(uid,ids)
        if not room or not valid:return None
        room["ais"]=valid; _normalize_talk_settings(room); room["updated"]=time.time(); save_json(_path(uid,cid),room)
    _list(uid); return room

def get_talk_settings(uid,cid):
    room=_load(uid,cid); return copy.deepcopy(room["talk_settings"]) if room else None

def save_talk_settings(uid,cid,data):
    with _room_lock(uid,cid):
        room=_load(uid,cid)
        if not room:return None
        s=_normalize_talk_settings(room)
        if isinstance(data,dict):
            if "instructions" in data:s["instructions"]=str(data.get("instructions") or "")[:4000]
            if "relationship" in data:s["relationship"]=str(data.get("relationship") or "")[:4000]
            if isinstance(data.get("names"),dict):
                for ai_id in room["ais"]:
                    if ai_id in data["names"]:s["names"][ai_id]=str(data["names"].get(ai_id) or "")[:80]
            if "delay_seconds" in data:
                try:s["delay_seconds"]=max(0,min(10,float(data["delay_seconds"])))
                except Exception:pass
            if "enabled" in data:s["enabled"]=bool(data["enabled"])
        room["talk_settings"]=s; room["updated"]=time.time(); save_json(_path(uid,cid),room); return copy.deepcopy(s)

def _participant_name(room,ai_id,ai): return room.get("talk_settings",{}).get("names",{}).get(ai_id," ").strip() or ai.get("ai_name","AI")
def _transcript(room):
    return "\n".join(("User: "+str(x.get("text",""))) if x.get("type")=="user" else (str(x.get("ai_name","AI"))+": "+str(x.get("text",""))) for x in room.get("conversation",[])[-50:])

def _reply(uid,ai_id,room,prompt):
    settings=load_settings(uid,ai_id); enabled=features(settings); memory=load_json(os.path.join(ai_root(uid,ai_id),"brain_memory.json"),{})
    profile={"memory":memory if isinstance(memory,dict) else {},"conversation":room.get("conversation",[])}; context=ai_profile(profile,prompt,settings)
    participants=[]
    for pid in room.get("ais",[]):
        ai=next((x for x in list_ais(uid) if x["ai_id"]==pid),None)
        if ai: participants.append(f"- {_participant_name(room,pid,ai)} (AI ID: {pid})")
    s=room.get("talk_settings",{}); me=next((x for x in list_ais(uid) if x["ai_id"]==ai_id),{"ai_name":"AI"})
    full=f"""You are participating in a multi-AI conversation.
Your name: {_participant_name(room,ai_id,me)}
Other participants:\n{chr(10).join(participants)}

Relationship between participants:
{s.get('relationship','')}

Multi-chat instructions:
{s.get('instructions','')}

Conversation so far:
{_transcript(room)}

Respond naturally as yourself. Recognize the other AIs by their names. Address them directly when appropriate. Do not pretend to be another participant."""
    if prompt:full+="\n\nLatest event:\n"+prompt
    reply=clean_reply(ask_online(full,settings,context)) if enabled["online_ai"] else None
    if not reply:reply=clean_reply(think(full,settings,os.path.join(ai_root(uid,ai_id),"brain_memory.json"),os.path.join(ai_root(uid,ai_id),"learning_replies.json")))
    return reply or "I couldn't get an AI response right now."

def _finish_ai(uid,cid,ai_id,prompt,snapshot,mode=None):
    try:
        reply=_reply(uid,ai_id,snapshot,prompt); ai=next((x for x in list_ais(uid) if x["ai_id"]==ai_id),None)
        if not ai:return
        entry={"type":"ai","ai_id":ai_id,"ai_name":_participant_name(snapshot,ai_id,ai),"text":reply,"time":time.time()}
        if mode:entry["mode"]=mode
        with _room_lock(uid,cid):
            room=_load(uid,cid)
            if not room:return
            room["conversation"].append(entry); room["pending_ai"]=[x for x in room.get("pending_ai",[]) if x!=ai_id]; room["updated"]=time.time(); save_json(_path(uid,cid),room)
        _list(uid)
    except Exception:
        with _room_lock(uid,cid):
            room=_load(uid,cid)
            if room:room["pending_ai"]=[x for x in room.get("pending_ai",[]) if x!=ai_id]; save_json(_path(uid,cid),room)

def send_message(uid,cid,text):
    with _room_lock(uid,cid):
        room=_load(uid,cid); text=str(text or "").strip()
        if not room or not text or not room.get("ais"):return None
        now=time.time(); ids=list(room["ais"]); room["conversation"].append({"type":"user","text":text,"time":now}); room["pending_ai"]=list(dict.fromkeys(room.get("pending_ai",[])+ids)); room["updated"]=now
        if room.get("title")=="New conversation":room["title"]=_room_title(room)
        snapshot=copy.deepcopy(room); save_json(_path(uid,cid),room)
    _list(uid)
    for ai_id in ids:_AI_EXECUTOR.submit(_finish_ai,uid,cid,ai_id,text,snapshot)
    return {"room":room,"responses":[]}

def _talk_loop(uid,cid):
    key=_talk_key(uid,cid)
    try:
        while True:
            with _TALK_GUARD:
                stop=_TALK_STOPS.get(key)
            if not stop or stop.is_set():break
            with _room_lock(uid,cid):
                room=_load(uid,cid)
                if not room or not room.get("talk_settings",{}).get("enabled") or not room.get("ais"):break
                ids=list(room["ais"]); last=room.get("conversation",[])[-1] if room.get("conversation") else None
            for ai_id in ids:
                if stop.is_set():break
                with _room_lock(uid,cid):
                    room=_load(uid,cid)
                    if not room or not room.get("talk_settings",{}).get("enabled"):stop.set();break
                    snapshot=copy.deepcopy(room)
                prompt="Start the conversation naturally." if not last else f"Respond naturally to {last.get('ai_name','the other AI')}: {last.get('text','')}"
                _finish_ai(uid,cid,ai_id,prompt,snapshot,"ai_to_ai")
                with _room_lock(uid,cid):
                    room=_load(uid,cid); last=room.get("conversation",[])[-1] if room and room.get("conversation") else last
                if stop.wait(float(room.get("talk_settings",{}).get("delay_seconds",.5) if room else .5)):break
    finally:
        with _TALK_GUARD:_TALK_STOPS.pop(key,None)
        with _room_lock(uid,cid):
            room=_load(uid,cid)
            if room:room["talk_settings"]["enabled"]=False; save_json(_path(uid,cid),room)
        _list(uid)

def ai_talk(uid,cid,enabled=None):
    if enabled is False:
        _stop_talk(uid,cid)
        with _room_lock(uid,cid):
            room=_load(uid,cid)
            if not room:return None
            room["talk_settings"]["enabled"]=False; save_json(_path(uid,cid),room)
        _list(uid); return {"room":room,"responses":[]}
    with _room_lock(uid,cid):
        room=_load(uid,cid)
        if not room or not room.get("ais"):return None
        room["talk_settings"]["enabled"]=True; room["updated"]=time.time(); save_json(_path(uid,cid),room); snapshot=copy.deepcopy(room)
    key=_talk_key(uid,cid)
    with _TALK_GUARD:
        existing=_TALK_STOPS.get(key)
        if existing and not existing.is_set():return {"room":snapshot,"responses":[]}
        _TALK_STOPS[key]=Event()
    _list(uid); _AI_EXECUTOR.submit(_talk_loop,uid,cid); return {"room":snapshot,"responses":[]}

def _json_body(h):
    n=int(h.headers.get("Content-Length",0) or 0); return json.loads(h.rfile.read(n).decode("utf-8")) if n else {}

def install_handler_routes(handler_class):
    if getattr(handler_class,"_multi_chat_routes_installed",False):return
    original_get=handler_class.do_GET; original_post=handler_class.do_POST
    def do_get(self):
        path=self.path.split("?",1)[0]
        if path=="/api/multi-chats":
            uid=current_user(self)
            if not uid:return self.send_json({"ok":False,"error":"Authentication required"},status=401)
            return self.send_json({"ok":True,"rooms":_list(uid),"ais":list_ais(uid),"max_ais":MAX_AIS_PER_ACCOUNT},uid)
        if path=="/api/multi-chats/open":
            uid=current_user(self)
            if not uid:return self.send_json({"ok":False,"error":"Authentication required"},status=401)
            from urllib.parse import parse_qs,urlparse
            cid=parse_qs(urlparse(self.path).query).get("conversation_id",[""])[0]; room=_load(uid,cid)
            if not room:return self.send_json({"ok":False,"error":"Conversation not found"},uid,404)
            return self.send_json({"ok":True,"room":room},uid)
        if path=="/api/multi-chats/settings":
            uid=current_user(self)
            if not uid:return self.send_json({"ok":False,"error":"Authentication required"},status=401)
            from urllib.parse import parse_qs,urlparse
            cid=parse_qs(urlparse(self.path).query).get("conversation_id",[""])[0]; settings=get_talk_settings(uid,cid)
            if settings is None:return self.send_json({"ok":False,"error":"Conversation not found"},uid,404)
            return self.send_json({"ok":True,"settings":settings},uid)
        return original_get(self)
    def do_post(self):
        path=self.path.split("?",1)[0]
        routes={"/api/multi-chats/new","/api/multi-chats/rename","/api/multi-chats/delete","/api/multi-chats/participants","/api/multi-chats/message","/api/multi-chats/talk","/api/multi-chats/settings"}
        if path not in routes:return original_post(self)
        uid=current_user(self)
        if not uid:return self.send_json({"ok":False,"error":"Authentication required"},status=401)
        try:data=_json_body(self)
        except Exception:return self.send_json({"ok":False,"error":"Invalid JSON"},uid,400)
        if path=="/api/multi-chats/new":return self.send_json({"ok":True,"room":new_room(uid)},uid)
        cid=str(data.get("conversation_id",""))
        if path=="/api/multi-chats/rename":
            if not rename_room(uid,cid,data.get("title")):return self.send_json({"ok":False,"error":"Unable to rename conversation"},uid,400)
            return self.send_json({"ok":True},uid)
        if path=="/api/multi-chats/delete":
            if not delete_room(uid,cid):return self.send_json({"ok":False,"error":"Conversation not found"},uid,404)
            return self.send_json({"ok":True},uid)
        if path=="/api/multi-chats/participants":
            room=set_participants(uid,cid,data.get("ais"))
            if not room:return self.send_json({"ok":False,"error":"Select at least one valid AI"},uid,400)
            return self.send_json({"ok":True,"room":room},uid)
        if path=="/api/multi-chats/settings":
            settings=save_talk_settings(uid,cid,data)
            if settings is None:return self.send_json({"ok":False,"error":"Conversation not found"},uid,404)
            if data.get("enabled") is True:ai_talk(uid,cid,True)
            elif data.get("enabled") is False:ai_talk(uid,cid,False)
            return self.send_json({"ok":True,"settings":settings,"room":_load(uid,cid)},uid)
        if path=="/api/multi-chats/message":
            result=send_message(uid,cid,data.get("message"))
            if not result:return self.send_json({"ok":False,"error":"Conversation not found or no participants"},uid,400)
            return self.send_json({"ok":True,**result},uid)
        if path=="/api/multi-chats/talk":
            result=ai_talk(uid,cid,data.get("enabled",True))
            if not result:return self.send_json({"ok":False,"error":"Conversation not found or no participants"},uid,400)
            return self.send_json({"ok":True,**result},uid)
    handler_class.do_GET=do_get; handler_class.do_POST=do_post; handler_class._multi_chat_routes_installed=True
