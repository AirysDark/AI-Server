"""Multi-AI conversation rooms.

Multi-chat is deliberately separate from normal C-*.json conversations.
All room data is stored under each user's persistent AI-Server-Storage tree.
"""
import copy, json, os, re, time, uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Lock, Event
from core.ai_manager import list_ais, load_settings, ai_root
from core.auth import current_user
from core.config import USERS_DIR, MAX_AIS_PER_ACCOUNT
from core.storage import load_json, save_json
from core.server_impl import ask_online, think, clean_reply, features, ai_profile

_ROOM_LOCKS = {}
_ROOM_LOCKS_GUARD = Lock()
_AI_EXECUTOR = ThreadPoolExecutor(max_workers=8)
_TALK_STOPS = {}
_TALK_GUARD = Lock()


def _room_lock(uid, cid):
    key = f"{uid}:{cid}"
    with _ROOM_LOCKS_GUARD:
        return _ROOM_LOCKS.setdefault(key, Lock())


def _talk_key(uid, cid):
    return f"{uid}:{cid}"


def _talk_stop(uid, cid):
    key = _talk_key(uid, cid)
    with _TALK_GUARD:
        return _TALK_STOPS.setdefault(key, Event())


def _stop_talk(uid, cid):
    key = _talk_key(uid, cid)
    with _TALK_GUARD:
        event = _TALK_STOPS.get(key)
        if event:
            event.set()
        _TALK_STOPS.pop(key, None)


def _safe(value, prefix=None):
    text = re.sub(r"[^A-Za-z0-9_-]", "", str(value or ""))[:100]
    if prefix and not text.startswith(prefix):
        return ""
    return text


def _root(uid):
    return os.path.join(USERS_DIR, _safe(uid), "multi_chats")


def _rooms(uid):
    path = os.path.join(_root(uid), "rooms")
    os.makedirs(path, exist_ok=True)
    return path


def _path(uid, cid):
    return os.path.join(_rooms(uid), _safe(cid) + ".json")


def _new_id():
    return "MC-" + uuid.uuid4().hex[:16]


def _default_talk_settings(ais):
    return {
        "enabled": False,
        "instructions": "Talk naturally to the other AIs. Recognize each participant by name, respond to what they just said, and continue the discussion naturally. Do not address the user unless the user has joined the conversation. Stay in character according to your own AI settings and personality.",
        "names": {ai_id: "" for ai_id in ais},
        "delay_seconds": 0.5,
    }


def _normalize_talk_settings(room):
    current = room.get("talk_settings")
    defaults = _default_talk_settings(room.get("ais", []))
    if not isinstance(current, dict):
        current = defaults
    current.setdefault("enabled", False)
    current.setdefault("instructions", defaults["instructions"])
    current.setdefault("names", {})
    current.setdefault("delay_seconds", 0.5)
    current["delay_seconds"] = max(0.0, min(10.0, float(current.get("delay_seconds", 0.5) or 0.5)))
    for ai_id in room.get("ais", []):
        current["names"].setdefault(ai_id, "")
    current["names"] = {str(k): str(v or "")[:80] for k, v in current["names"].items() if str(k) in room.get("ais", [])}
    room["talk_settings"] = current
    return current


def _room_title(room):
    title = str(room.get("title", "")).strip()
    if title:
        return title[:80]
    for item in room.get("conversation", []):
        if item.get("type") == "user" and str(item.get("text", "")).strip():
            text = " ".join(str(item["text"]).split())
            return text[:60] + ("..." if len(text) > 60 else "")
    return "New conversation"


def _save_index(uid, rooms):
    os.makedirs(_root(uid), exist_ok=True)
    save_json(os.path.join(_root(uid), "index.json"), rooms)


def _list(uid):
    result = []
    root = _rooms(uid)
    for name in os.listdir(root):
        if not name.startswith("MC-") or not name.endswith(".json"):
            continue
        try:
            room = load_json(os.path.join(root, name), None)
            if not isinstance(room, dict):
                continue
            cid = _safe(room.get("conversation_id") or name[:-5], "MC-")
            if not cid:
                continue
            result.append({"conversation_id": cid, "title": _room_title(room), "ais": room.get("ais", []), "created": room.get("created", 0), "updated": room.get("updated", 0)})
        except Exception:
            continue
    result.sort(key=lambda x: x.get("updated", 0) or 0, reverse=True)
    _save_index(uid, result)
    return result


def _load(uid, cid):
    cid = _safe(cid, "MC-")
    if not cid:
        return None
    room = load_json(_path(uid, cid), None)
    if not isinstance(room, dict) or room.get("conversation_id") != cid:
        return None
    room.setdefault("conversation", [])
    room.setdefault("ais", [])
    room.setdefault("pending_ai", [])
    _normalize_talk_settings(room)
    return room


def _valid_ai_ids(uid, ids):
    available = {x["ai_id"] for x in list_ais(uid)}
    return [ai_id for ai_id in [str(x) for x in ids] if ai_id in available and ai_id not in locals().get("out", [])]


def new_room(uid):
    ais = list_ais(uid)
    selected = [x["ai_id"] for x in ais[:1]
    now = time.time()
    room = {"conversation_id": _new_id(), "title": "New conversation", "ais": selected, "conversation": [], "pending_ai": [], "talk_settings": _default_talk_settings(selected), "created": now, "updated": now}
    save_json(_path(uid, room["conversation_id"]), room)
    _list(uid)
    return room


def rename_room(uid, cid, title):
    with _room_lock(uid, cid):
        room = _load(uid, cid); title = " ".join(str(title or "").strip().split())[:80]
        if not room or not title: return False
        room["title"] = title; room["updated"] = time.time(); save_json(_path(uid, room["conversation_id"]), room)
    _list(uid); return True


def delete_room(uid, cid):
    _stop_talk(uid, cid)
    with _room_lock(uid, cid):
        room = _load(uid, cid)
        if not room: return False
        try: os.remove(_path(uid, room["conversation_id"]))
        except FileNotFoundError: return False
    _list(uid); return True


def set_participants(uid, cid, ids):
    with _room_lock(uid, cid):
        room = _load(uid, cid)
        valid = _valid_ai_ids(uid, ids)
        if not room or not valid: return None
        room["ais"] = valid
        _normalize_talk_settings(room)
        room["updated"] = time.time(); save_json(_path(uid, room["conversation_id"]), room)
    _list(uid); return room


def get_talk_settings(uid, cid):
    room = _load(uid, cid)
    if not room: return None
    return copy.deepcopy(_normalize_talk_settings(room))


def save_talk_settings(uid, cid, data):
    with _room_lock(uid, cid):
        room = _load(uid, cid)
        if not room: return None
        settings = _normalize_talk_settings(room)
        if isinstance(data, dict):
            if "instructions" in data: settings["instructions"] = str(data.get("instructions") or "")[:4000]
            if "names" in data and isinstance(data["names"], dict):
                for ai_id in room["ais"]:
                    if ai_id in data["names"]: settings["names"][ai_id] = str(data["names"].get(ai_id) or "")[:80]
            if "delay_seconds" in data:
                try: settings["delay_seconds"] = max(0.0, min(10.0, float(data["delay_seconds"])))
                except Exception: pass
            if "enabled" in data: settings["enabled"] = bool(data["enabled"])
        room["talk_settings"] = settings; room["updated"] = time.time(); save_json(_path(uid, cid), room)
        return copy.deepcopy(settings)


def _transcript(room):
    lines = []
    for item in room.get("conversation", [])[-40:]:
        if item.get("type") == "user": lines.append("User: " + str(item.get("text", "")))
        elif item.get("type") == "ai": lines.append(str(item.get("ai_name", "AI")) + ": " + str(item.get("text", "")))
    return "\n".join(lines)


def _participant_name(room, ai_id, ai):
    custom = room.get("talk_settings", {}).get("names", {}).get(ai_id, "")
    return custom.strip() or ai.get("ai_name", "AI")


def _reply(uid, ai_id, room, prompt):
    settings = load_settings(uid, ai_id)
    enabled = features(settings)
    memory = load_json(os.path.join(ai_root(uid, ai_id), "brain_memory.json"), {})
    profile = {"memory": memory if isinstance(memory, dict) else {}, "conversation": room.get("conversation", [])}
    context = ai_profile(profile, prompt, settings)
    room_context = _transcript(room)
    participant_lines = []
    for participant_id in room.get("ais", []):
        participant = next((x for x in list_ais(uid) if x["ai_id"] == participant_id), None)
        if participant:
            participant_lines.append(f"- {_participant_name(room, participant_id, participant)} (AI ID: {participant_id})")
    participant_block = "\n".join(participant_lines)
    talk_instructions = room.get("talk_settings", {}).get("instructions", "")
    full_prompt = f"""You are one participant in a multi-AI conversation.

Your name in this room: {_participant_name(room, ai_id, next((x for x in list_ais(uid) if x["ai_id"] == ai_id), {"ai_name":"AI"}))}
Other participants:
{participant_block}

Multi-chat instructions:
{talk_instructions}

Conversation:
{room_context}

Respond naturally as yourself. Address other AIs by their names when appropriate. Do not pretend to be another participant."""
    if prompt:
        full_prompt += "\n\nLatest instruction/event:\n" + prompt
    reply = None
    if enabled["online_ai"]: reply = clean_reply(ask_online(full_prompt, settings, context))
    if not reply: reply = clean_reply(think(full_prompt, settings, os.path.join(ai_root(uid, ai_id), "brain_memory.json"), os.path.join(ai_root(uid, ai_id), "learning_replies.json")))
    return reply or "I couldn't get an AI response right now."


def _finish_ai(uid, cid, ai_id, prompt, snapshot, mode=None):
    try:
        reply = _reply(uid, ai_id, snapshot, prompt)
        ai = next((x for x in list_ais(uid) if x["ai_id"] == ai_id), None)
        if not ai: return
        entry = {"type":"ai","ai_id":ai_id,"ai_name":_participant_name(snapshot, ai_id, ai),"text":reply,"time":time.time()}
        if mode: entry["mode"] = mode
        with _room_lock(uid, cid):
            room = _load(uid, cid)
            if not room: return
            room["conversation"].append(entry)
            room["pending_ai"] = [x for x in room.get("pending_ai", []) if x != ai_id]
            room["updated"] = time.time(); save_json(_path(uid, cid), room)
        _list(uid)
    except Exception:
        with _room_lock(uid, cid):
            room = _load(uid, cid)
            if room:
                room["pending_ai"] = [x for x in room.get("pending_ai", []) if x != ai_id]; room["updated"] = time.time(); save_json(_path(uid, cid), room)


def send_message(uid, cid, text):
    with _room_lock(uid, cid):
        room = _load(uid, cid); text = str(text or "").strip()
        if not room or not text or not room.get("ais"): return None
        ai_ids = list(room["ais"]); now = time.time()
        room["conversation"].append({"type":"user","text":text,"time":now})
        room["pending_ai"] = list(dict.fromkeys(room.get("pending_ai", []) + ai_ids)); room["updated"] = now
        if room.get("title") == "New conversation": room["title"] = _room_title(room)
        snapshot = copy.deepcopy(room); save_json(_path(uid, room["conversation_id"]), room)
    _list(uid)
    for ai_id in ai_ids: _AI_EXECUTOR.submit(_finish_ai, uid, cid, ai_id, text, snapshot)
    return {"room": room, "responses": []}


def _talk_loop(uid, cid):
    stop = _talk_stop(uid, cid)
    try:
        while not stop.is_set():
            with _room_lock(uid, cid):
                room = _load(uid, cid)
                if not room: break
                settings = _normalize_talk_settings(room)
                if not settings.get("enabled") or len(room.get("ais", [])) < 1: break
                ai_ids = list(room["ais"])
                previous = room.get("conversation", [])[-1] if room.get("conversation") else None
            for ai_id in ai_ids:
                if stop.is_set(): break
                with _room_lock(uid, cid):
                    room = _load(uid, cid)
                    if not room: stop.set(); break
                    if not room.get("talk_settings", {}).get("enabled"): stop.set(); break
                    # Refresh the transcript before every AI speaks so each AI sees everything said immediately before it.
                    snapshot = copy.deepcopy(room)
                prompt = "Start the next turn naturally." if not previous else f"Respond to the latest message from the other participant:\n{previous.get('text','')}"
                _finish_ai(uid, cid, ai_id, prompt, snapshot, "ai_to_ai")
                with _room_lock(uid, cid):
                    current = _load(uid, cid)
                    if not current: stop.set(); break
                    previous = current.get("conversation", [])[-1] if current.get("conversation") else previous
                delay = float(current.get("talk_settings", {}).get("delay_seconds", 0.5) or 0.5)
                if stop.wait(delay): break
    finally:
        with _talk_guard_cleanup():
            pass
        with _TALK_GUARD:
            _TALK_STOPS.pop(_talk_key(uid, cid), None)
        with _room_lock(uid, cid):
            room = _load(uid, cid)
            if room:
                room["talk_settings"]["enabled"] = False
                room["updated"] = time.time(); save_json(_path(uid, cid), room)
        _list(uid)

class _talk_guard_cleanup:
    def __enter__(self): return self
    def __exit__(self, *args): return False


def ai_talk(uid, cid, enabled=None):
    if enabled is False:
        _stop_talk(uid, cid)
        with _room_lock(uid, cid):
            room = _load(uid, cid)
            if not room: return None
            room["talk_settings"]["enabled"] = False; room["updated"] = time.time(); save_json(_path(uid, cid), room)
        _list(uid); return {"room": room, "responses": []}
    with _room_lock(uid, cid):
        room = _load(uid, cid)
        if not room or not room.get("ais"): return None
        room["talk_settings"]["enabled"] = True; room["pending_ai"] = list(dict.fromkeys(room.get("pending_ai", [])))
        room["updated"] = time.time(); save_json(_path(uid, cid), room); snapshot = copy.deepcopy(room)
    key = _talk_key(uid, cid)
    with _TALK_GUARD:
        existing = _TALK_STOPS.get(key)
        if existing and not existing.is_set():
            return {"room": snapshot, "responses": []}
        _TALK_STOPS[key] = Event()
    _list(uid); _AI_EXECUTOR.submit(_talk_loop, uid, cid)
    return {"room": snapshot, "responses": []}


def _json_body(handler):
    length = int(handler.headers.get("Content-Length", 0) or 0)
    return json.loads(handler.rfile.read(length).decode("utf-8")) if length else {}


def install_handler_routes(handler_class):
    if getattr(handler_class, "_multi_chat_routes_installed", False): return
    original_get = handler_class.do_GET; original_post = handler_class.do_POST
    def do_get(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/multi-chats":
            uid=current_user(self)
            if not uid:return self.send_json({"ok":False,"error":"Authentication required"},status=401)
            return self.send_json({"ok":True,"rooms":_list(uid),"ais":list_ais(uid),"max_ais":MAX_AIS_PER_ACCOUNT},uid)
        if path == "/api/multi-chats/open":
            uid=current_user(self)
            if not uid:return self.send_json({"ok":False,"error":"Authentication required"},status=401)
            from urllib.parse import parse_qs,urlparse
            cid=parse_qs(urlparse(self.path).query).get("conversation_id",[""])[0];room=_load(uid,cid)
            if not room:return self.send_json({"ok":False,"error":"Conversation not found"},uid,404)
            return self.send_json({"ok":True,"room":room},uid)
        if path == "/api/multi-chats/settings":
            uid=current_user(self)
            if not uid:return self.send_json({"ok":False,"error":"Authentication required"},status=401)
            from urllib.parse import parse_qs,urlparse
            cid=parse_qs(urlparse(self.path).query).get("conversation_id",[""])[0];settings=get_talk_settings(uid,cid)
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
            if data.get("enabled") is True: ai_talk(uid,cid,True)
            elif data.get("enabled") is False: ai_talk(uid,cid,False)
            return self.send_json({"ok":True,"settings":settings,"room":_load(uid,cid)},uid)
        if path=="/api/multi-chats/message":
            result=send_message(uid,cid,data.get("message"))
            if not result:return self.send_json({"ok":False,"error":"Unable to send message. Select at least one AI."},uid,400)
            return self.send_json({"ok":True,**result},uid)
        result=ai_talk(uid,cid,data.get("enabled"))
        if not result:return self.send_json({"ok":False,"error":"Unable to start AI conversation. Select at least one AI."},uid,400)
        return self.send_json({"ok":True,**result},uid)
    handler_class.do_GET=do_get;handler_class.do_POST=do_post;handler_class._multi_chat_routes_installed=True
