"""Multi-AI conversation rooms."""
import copy, json, os, re, time, uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Lock, Event
from core.ai_manager import list_ais, load_settings, ai_root
from core.auth import current_user
from core.config import USERS_DIR, MAX_AIS_PER_ACCOUNT
from core.storage import load_json, save_json
from core.server_impl import ask_online, think, clean_reply, features, ai_profile

_ROOM_LOCKS={}; _ROOM_LOCKS_GUARD=Lock(); _AI_EXECUTOR=ThreadPoolExecutor(max_workers=8)
_TALK_STOPS={}; _TALK_GUARD=Lock()
def _room_lock(uid,cid):
    with _ROOM_LOCKS_GUARD:return _ROOM_LOCKS.setdefault(f"{uid}:{cid}",Lock())
def _talk_key(uid,cid):return f"{uid}:{cid}"
def _stop_talk(uid,cid):
    with _TALK_GUARD:
        e=_TALK_STOPS.get(_talk_key(uid,cid))
        if e:e.set()
        _TALK_STOPS.pop(_talk_key(uid,cid),None)
def _safe(v,prefix=None):
    t=re.sub(r"[^A-Za-z0-9_-]","",str(v or ""))[:100]; return t if not prefix or t.startswith(prefix) else ""
def _root(uid):return os.path.join(USERS_DIR,_safe(uid),"multi_chats")
def _rooms(uid):
    p=os.path.join(_root(uid),"rooms");os.makedirs(p,exist_ok=True);return p
def _path(uid,cid):return os.path.join(_rooms(uid),_safe(cid)+".json")
def _new_id():return "MC-"+uuid.uuid4().hex[:16]

def _default_talk_settings(ais):
    return {"enabled":False,"instructions":"Talk naturally to the other AIs. Recognize each participant by name, respond to what they just said, and continue the discussion naturally. Stay in character according to your own AI settings and personality.","relationship":"The AIs are participants in the same conversation. Define their relationship here so they understand how they should interact with each other.","names":{ai_id:"" for ai_id in ais},"delay_seconds":0.5}
def _normalize_talk_settings(room):
    d=_default_talk_settings(room.get("ais",[]));s=room.get("talk_settings")
    if not isinstance(s,dict):s=d
    s.setdefault("enabled",False);s.setdefault("instructions",d["instructions"]);s.setdefault("relationship",d["relationship"]);s.setdefault("names",{});s.setdefault("delay_seconds",.5)
    try:s["delay_seconds"]=max(0,min(10,float(s.get("delay_seconds",.5))))
    except Exception:s["delay_seconds"]=.5
    for a in room.get("ais",[]):s["names"].setdefault(a,"")
    s["names"]={str(k):str(v or "")[:80] for k,v in s["names"].items() if str(k) in room.get("ais",[])};room["talk_settings"]=s;return s
def _room_title(room):
    t=str(room.get("title","")).strip()
    if t:return t[:80]
    for x in room.get("conversation",[]):
        if x.get("type")=="user" and str(x.get("text","")).strip():
            z=" ".join(str(x["text"]).split());return z[:60]+("..." if len(z)>60 else "")
    return "New conversation"
def _save_index(uid,rooms):os.makedirs(_root(uid),exist_ok=True);save_json(os.path.join(_root(uid),"index.json"),rooms)
def _list(uid):
    result=[]
    for n in os.listdir(_rooms(uid)):
        if not n.startswith("MC-") or not n.endswith(".json"):continue
        try:
            r=load_json(os.path.join(_rooms(uid),n),None)
            if isinstance(r,dict):result.append({"conversation_id":_safe(r.get("conversation_id") or n[:-5],"MC-"),"title":_room_title(r),"ais":r.get("ais",[]),"created":r.get("created",0),"updated":r.get("updated",0)})
        except Exception:pass
    result.sort(key=lambda x:x.get("updated",0) or 0,reverse=True);_save_index(uid,result);return result
def _load(uid,cid):
    cid=_safe(cid,"MC-");r=load_json(_path(uid,cid),None) if cid else None
    if not isinstance(r,dict) or r.get("conversation_id")!=cid:return None
    r.setdefault("conversation",[]);r.setdefault("ais",[]);r.setdefault("pending_ai",[]);_normalize_talk_settings(r);return r
def _valid_ai_ids(uid,ids):
    available={x["ai_id"] for x in list_ais(uid)};out=[]
    for x in ids or []:
        x=str(x)
        if x in available and x not in out:out.append(x)
    return out
def new_room(uid):
    ais=list_ais(uid);selected=[x["ai_id"] for x in ais[:1]];now=time.time();r={"conversation_id":_new_id(),"title":"New conversation","ais":selected,"conversation":[],"pending_ai":[],"talk_settings":_default_talk_settings(selected),"created":now,"updated":now};save_json(_path(uid,r["conversation_id"]),r);_list(uid);return r
def rename_room(uid,cid,title):
    with _room_lock(uid,cid):
        r=_load(uid,cid);title=" ".join(str(title or "").strip().split())[:80]
        if not r or not title:return False
        r["title"]=title;r["updated"]=time.time();save_json(_path(uid,cid),r)
    _list(uid);return True
def delete_room(uid,cid):
    _stop_talk(uid,cid)
    with _room_lock(uid,cid):
        r=_load(uid,cid)
        if not r:return False
        try:os.remove(_path(uid,cid))
        except FileNotFoundError:return False
    _list(uid);return True
def set_participants(uid,cid,ids):
    with _room_lock(uid,cid):
        r=_load(uid,cid);valid=_valid_ai_ids(uid,ids)
        if not r or not valid:return None
        r["ais"]=valid;_normalize_talk_settings(r);r["updated"]=time.time();save_json(_path(uid,cid),r)
    _list(uid);return r
def get_talk_settings(uid,cid):
    r=_load(uid,cid);return copy.deepcopy(r["talk_settings"]) if r else None
def save_talk_settings(uid,cid,data):
    with _room_lock(uid,cid):
        r=_load(uid,cid)
        if not r:return None
        s=_normalize_talk_settings(r)
        if isinstance(data,dict):
            if "instructions" in data:s["instructions"]=str(data.get("instructions") or "")[:4000]
            if "relationship" in data:s["relationship"]=str(data.get("relationship") or "")[:4000]
            if isinstance(data.get("names"),dict):
                for a in r["ais"]:
                    if a in data["names"]:s["names"][a]=str(data["names"].get(a) or "")[:80]
            if "delay_seconds" in data:
                try:s["delay_seconds"]=max(0,min(10,float(data["delay_seconds"])))
                except Exception:pass
            if "enabled" in data:s["enabled"]=bool(data["enabled"])
        r["talk_settings"]=s;r["updated"]=time.time();save_json(_path(uid,cid),r);return copy.deepcopy(s)
def _participant_name(r,aid,ai):return r.get("talk_settings",{}).get("names",{}).get(aid,"").strip() or ai.get("ai_name","AI")
def _transcript(r):return "\n".join(("User: "+str(x.get("text",""))) if x.get("type")=="user" else str(x.get("ai_name","AI"))+": "+str(x.get("text","")) for x in r.get("conversation",[])[-50:])
def _reply(uid,aid,r,prompt):
    settings=load_settings(uid,aid);enabled=features(settings);memory=load_json(os.path.join(ai_root(uid,aid),"brain_memory.json"),{});context=ai_profile({"memory":memory if isinstance(memory,dict) else {},"conversation":r.get("conversation",[])},prompt,settings);participants=[]
    all_ais=list_ais(uid)
    for pid in r.get("ais",[]):
        ai=next((x for x in all_ais if x["ai_id"]==pid),None)
        if ai:participants.append(f"- {_participant_name(r,pid,ai)} (AI ID: {pid})")
    s=r.get("talk_settings",{});me=next((x for x in all_ais if x["ai_id"]==aid),{"ai_name":"AI"})
    full=f"""You are participating in a multi-AI conversation.
Your name: {_participant_name(r,aid,me)}
Other participants:
{chr(10).join(participants)}

Relationship between participants:
{s.get('relationship','')}

Multi-chat instructions:
{s.get('instructions','')}

Conversation so far:
{_transcript(r)}

Respond naturally as yourself. Recognize the other AIs by their names. Address them directly when appropriate. Do not pretend to be another participant."""
    if prompt:full+="\n\nLatest event:\n"+prompt
    reply=clean_reply(ask_online(full,settings,context)) if enabled["online_ai"] else None
    if not reply:reply=clean_reply(think(full,settings,os.path.join(ai_root(uid,aid),"brain_memory.json"),os.path.join(ai_root(uid,aid),"learning_replies.json")))
    return reply or "I couldn't get an AI response right now."
def _finish_ai(uid,cid,aid,prompt,snapshot,mode=None):
    try:
        reply=_reply(uid,aid,snapshot,prompt);ai=next((x for x in list_ais(uid) if x["ai_id"]==aid),None)
        if not ai:return
        e={"type":"ai","ai_id":aid,"ai_name":_participant_name(snapshot,aid,ai),"text":reply,"time":time.time()};
        if mode:e["mode"]=mode
        with _room_lock(uid,cid):
            r=_load(uid,cid)
            if not r:return
            r["conversation"].append(e);r["pending_ai"]=[x for x in r.get("pending_ai",[]) if x!=aid];r["updated"]=time.time();save_json(_path(uid,cid),r)
        _list(uid)
    except Exception:
        with _room_lock(uid,cid):
            r=_load(uid,cid)
            if r:r["pending_ai"]=[x for x in r.get("pending_ai",[]) if x!=aid];save_json(_path(uid,cid),r)
def send_message(uid,cid,text):
    with _room_lock(uid,cid):
        r=_load(uid,cid);text=str(text or "").strip()
        if not r or not text or not r.get("ais"):return None
        now=time.time();ids=list(r["ais"]);r["conversation"].append({"type":"user","text":text,"time":now});r["pending_ai"]=list(dict.fromkeys(r.get("pending_ai",[])+ids));r["updated"]=now
        if r.get("title")=="New conversation":r["title"]=_room_title(r)
        snap=copy.deepcopy(r);save_json(_path(uid,cid),r)
    _list(uid)
    for aid in ids:_AI_EXECUTOR.submit(_finish_ai,uid,cid,aid,text,snap)
    return {"room":r,"responses":[]}
def _talk_loop(uid,cid):
    with _TALK_GUARD:
        stop=_TALK_STOPS.get(_talk_key(uid,cid))
    if not stop:return
    try:
        while not stop.is_set():
            with _room_lock(uid,cid):
                r=_load(uid,cid)
                if not r or not r.get("talk_settings",{}).get("enabled") or not r.get("ais"):break
            with _room_lock(uid,cid):snap=copy.deepcopy(_load(uid,cid))
            if not snap:break
            ids=list(snap["ais"])
            for aid in ids:
                if stop.is_set():break
                with _room_lock(uid,cid):snap=copy.deepcopy(_load(uid,cid))
                if not snap:break
                prev=snap.get("conversation",[])[-1] if snap.get("conversation") else None
                prompt="Start the next turn naturally." if not prev else f"Respond to {prev.get('ai_name','the other AI')}: {prev.get('text','')}"
                _finish_ai(uid,cid,aid,prompt,snap,"ai_to_ai")
                delay=float(_load(uid,cid).get("talk_settings",{}).get("delay_seconds",.5) or .5)
                if stop.wait(delay):break
    finally:
        with _TALK_GUARD:_TALK_STOPS.pop(_talk_key(uid,cid),None)
        with _room_lock(uid,cid):
            r=_load(uid,cid)
            if r:r["talk_settings"]["enabled"]=False;r["updated"]=time.time();save_json(_path(uid,cid),r)
def ai_talk(uid,cid,enabled=None):
    if enabled is False:
        _stop_talk(uid,cid)
        with _room_lock(uid,cid):
            r=_load(uid,cid)
            if not r:return None
            r["talk_settings"]["enabled"]=False;r["updated"]=time.time();save_json(_path(uid,cid),r)
        _list(uid);return {"room":r,"responses":[]}
    with _room_lock(uid,cid):
        r=_load(uid,cid)
        if not r or not r.get("ais"):return None
        r["talk_settings"]["enabled"]=True;r["updated"]=time.time();save_json(_path(uid,cid),r);snap=copy.deepcopy(r)
    with _TALK_GUARD:
        key=_talk_key(uid,cid)
        if key in _TALK_STOPS and not _TALK_STOPS[key].is_set():return {"room":snap,"responses":[]}
        _TALK_STOPS[key]=Event()
    _list(uid);_AI_EXECUTOR.submit(_talk_loop,uid,cid);return {"room":snap,"responses":[]}
def _json_body(h):
    n=int(h.headers.get("Content-Length",0) or 0);return json.loads(h.rfile.read(n).decode("utf-8")) if n else {}
def install_handler_routes(handler_class):
    if getattr(handler_class,"_multi_chat_routes_installed",False):return
    original_get=handler_class.do_GET;original_post=handler_class.do_POST
    def do_get(self):
        path=self.path.split("?",1)[0];uid=current_user(self)
        if path.startswith("/api/multi-chats") and not uid:return self.send_json({"ok":False,"error":"Authentication required"},status=401)
        if path=="/api/multi-chats":return self.send_json({"ok":True,"rooms":_list(uid),"ais":list_ais(uid),"max_ais":MAX_AIS_PER_ACCOUNT},uid)
        if path=="/api/multi-chats/open":
            from urllib.parse import parse_qs,urlparse
            cid=parse_qs(urlparse(self.path).query).get("conversation_id",[""])[0];r=_load(uid,cid)
            if not r:return self.send_json({"ok":False,"error":"Conversation not found"},uid,404)
            return self.send_json({"ok":True,"room":r},uid)
        if path=="/api/multi-chats/settings":
            from urllib.parse import parse_qs,urlparse
            cid=parse_qs(urlparse(self.path).query).get("conversation_id",[""])[0];s=get_talk_settings(uid,cid)
            if s is None:return self.send_json({"ok":False,"error":"Conversation not found"},uid,404)
            return self.send_json({"ok":True,"settings":s},uid)
        return original_get(self)
    def do_post(self):
        path=self.path.split("?",1)[0];routes={"/api/multi-chats/new","/api/multi-chats/rename","/api/multi-chats/delete","/api/multi-chats/participants","/api/multi-chats/message","/api/multi-chats/talk","/api/multi-chats/settings"}
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
            r=set_participants(uid,cid,data.get("ais"))
            if not r:return self.send_json({"ok":False,"error":"Select at least one valid AI"},uid,400)
            return self.send_json({"ok":True,"room":r},uid)
        if path=="/api/multi-chats/settings":
            s=save_talk_settings(uid,cid,data)
            if s is None:return self.send_json({"ok":False,"error":"Conversation not found"},uid,404)
            if data.get("enabled") is True:ai_talk(uid,cid,True)
            elif data.get("enabled") is False:ai_talk(uid,cid,False)
            return self.send_json({"ok":True,"settings":s},uid)
        if path=="/api/multi-chats/message":
            r=send_message(uid,cid,data.get("message"));
            if not r:return self.send_json({"ok":False,"error":"Conversation not found or no participants"},uid,400)
            return self.send_json(r,uid)
        if path=="/api/multi-chats/talk":
            r=ai_talk(uid,cid,data.get("enabled",True));
            if not r:return self.send_json({"ok":False,"error":"Conversation not found or no participants"},uid,400)
            return self.send_json(r,uid)
    handler_class.do_GET=do_get;handler_class.do_POST=do_post;handler_class._multi_chat_routes_installed=True
