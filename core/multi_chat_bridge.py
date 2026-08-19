"""Multi-AI conversation rooms.

Multi-chat is deliberately separate from normal C-*.json conversations.
All room data is stored under each user's persistent AI-Server-Storage tree.
"""
import copy, json, os, re, time, uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from core.ai_manager import list_ais, load_settings, ai_root
from core.auth import current_user
from core.config import USERS_DIR, MAX_AIS_PER_ACCOUNT
from core.storage import load_json, save_json
from core.server_impl import ask_online, think, clean_reply, features, ai_profile

_ROOM_LOCKS = {}
_ROOM_LOCKS_GUARD = Lock()
_AI_EXECUTOR = ThreadPoolExecutor(max_workers=8)


def _room_lock(uid, cid):
    key = f"{uid}:{cid}"
    with _ROOM_LOCKS_GUARD:
        return _ROOM_LOCKS.setdefault(key, Lock())


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
            result.append({
                "conversation_id": cid,
                "title": _room_title(room),
                "ais": room.get("ais", []),
                "created": room.get("created", 0),
                "updated": room.get("updated", 0),
            })
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
    return room


def _valid_ai_ids(uid, ids):
    available = {x["ai_id"] for x in list_ais(uid)}
    out = []
    for ai_id in ids if isinstance(ids, list) else []:
        ai_id = str(ai_id)
        if ai_id in available and ai_id not in out:
            out.append(ai_id)
    return out


def new_room(uid):
    ais = list_ais(uid)
    selected = [x["ai_id"] for x in ais[:1]]
    now = time.time()
    room = {
        "conversation_id": _new_id(),
        "title": "New conversation",
        "ais": selected,
        "conversation": [],
        "pending_ai": [],
        "created": now,
        "updated": now,
    }
    save_json(_path(uid, room["conversation_id"]), room)
    _list(uid)
    return room


def rename_room(uid, cid, title):
    lock = _room_lock(uid, cid)
    with lock:
        room = _load(uid, cid)
        title = " ".join(str(title or "").strip().split())[:80]
        if not room or not title:
            return False
        room["title"] = title
        room["updated"] = time.time()
        save_json(_path(uid, room["conversation_id"]), room)
    _list(uid)
    return True


def delete_room(uid, cid):
    lock = _room_lock(uid, cid)
    with lock:
        room = _load(uid, cid)
        if not room:
            return False
        try:
            os.remove(_path(uid, room["conversation_id"]))
        except FileNotFoundError:
            return False
    _list(uid)
    return True


def set_participants(uid, cid, ids):
    lock = _room_lock(uid, cid)
    with lock:
        room = _load(uid, cid)
        valid = _valid_ai_ids(uid, ids)
        if not room or not valid:
            return None
        room["ais"] = valid
        room["updated"] = time.time()
        save_json(_path(uid, room["conversation_id"]), room)
    _list(uid)
    return room


def _transcript(room):
    lines = []
    for item in room.get("conversation", [])[-30:]:
        if item.get("type") == "user":
            lines.append("User: " + str(item.get("text", "")))
        elif item.get("type") == "ai":
            lines.append(str(item.get("ai_name", "AI")) + ": " + str(item.get("text", "")))
    return "\n".join(lines)


def _reply(uid, ai_id, room, prompt):
    settings = load_settings(uid, ai_id)
    enabled = features(settings)
    memory = load_json(os.path.join(ai_root(uid, ai_id), "brain_memory.json"), {})
    profile = {"memory": memory if isinstance(memory, dict) else {}, "conversation": room.get("conversation", [])}
    context = ai_profile(profile, prompt, settings)
    room_context = _transcript(room)
    full_prompt = prompt
    if room_context:
        full_prompt = "You are participating in a multi-AI conversation. Continue naturally as yourself.\n\nConversation:\n" + room_context + "\n\nRespond to the latest message.\n" + prompt
    reply = None
    if enabled["online_ai"]:
        reply = clean_reply(ask_online(full_prompt, settings, context))
    if not reply:
        reply = clean_reply(think(full_prompt, settings, os.path.join(ai_root(uid, ai_id), "brain_memory.json"), os.path.join(ai_root(uid, ai_id), "learning_replies.json")))
    return reply or "I couldn't get an AI response right now."


def _finish_ai(uid, cid, ai_id, prompt, snapshot, mode=None):
    """Run one AI independently and publish its response as soon as it finishes."""
    try:
        reply = _reply(uid, ai_id, snapshot, prompt)
        ai = next((x for x in list_ais(uid) if x["ai_id"] == ai_id), None)
        if not ai:
            return
        entry = {
            "type": "ai",
            "ai_id": ai_id,
            "ai_name": ai["ai_name"],
            "text": reply,
            "time": time.time(),
        }
        if mode:
            entry["mode"] = mode
        lock = _room_lock(uid, cid)
        with lock:
            room = _load(uid, cid)
            if not room:
                return
            room["conversation"].append(entry)
            pending = [x for x in room.get("pending_ai", []) if x != ai_id]
            room["pending_ai"] = pending
            room["updated"] = time.time()
            if room.get("title") == "New conversation":
                room["title"] = _room_title(room)
            save_json(_path(uid, cid), room)
        _list(uid)
    except Exception:
        lock = _room_lock(uid, cid)
        with lock:
            room = _load(uid, cid)
            if room:
                room["pending_ai"] = [x for x in room.get("pending_ai", []) if x != ai_id]
                room["updated"] = time.time()
                save_json(_path(uid, cid), room)


def send_message(uid, cid, text):
    lock = _room_lock(uid, cid)
    with lock:
        room = _load(uid, cid)
        text = str(text or "").strip()
        if not room or not text or not room.get("ais"):
            return None
        now = time.time()
        ai_ids = list(room["ais"])
        room["conversation"].append({"type": "user", "text": text, "time": now})
        room["pending_ai"] = list(dict.fromkeys(room.get("pending_ai", []) + ai_ids))
        room["updated"] = now
        if room.get("title") == "New conversation":
            room["title"] = _room_title(room)
        snapshot = copy.deepcopy(room)
        save_json(_path(uid, room["conversation_id"]), room)
    _list(uid)
    for ai_id in ai_ids:
        _AI_EXECUTOR.submit(_finish_ai, uid, cid, ai_id, text, snapshot)
    return {"room": room, "responses": []}


def ai_talk(uid, cid):
    """Start an AI-to-AI round in the background so each completed response appears live."""
    lock = _room_lock(uid, cid)
    with lock:
        room = _load(uid, cid)
        if not room or not room.get("ais"):
            return None
        ai_ids = list(room["ais"])
        pending = list(dict.fromkeys(room.get("pending_ai", []) + ai_ids))
        room["pending_ai"] = pending
        room["updated"] = time.time()
        save_json(_path(uid, cid), room)
        snapshot = copy.deepcopy(room)
    _list(uid)

    def round_table():
        last = "Continue the discussion with the other AIs. Add something useful, interesting, or relevant to the conversation."
        for ai_id in ai_ids:
            lock2 = _room_lock(uid, cid)
            with lock2:
                current = _load(uid, cid)
                if not current:
                    return
                context_room = copy.deepcopy(current)
            _finish_ai(uid, cid, ai_id, last, context_room, "ai_to_ai")
            lock3 = _room_lock(uid, cid)
            with lock3:
                current = _load(uid, cid)
                if not current or not current.get("conversation"):
                    return
                latest = current["conversation"][-1]
                last = "React to what the other participants just said:\n" + str(latest.get("text", ""))

    _AI_EXECUTOR.submit(round_table)
    return {"room": room, "responses": []}


def _json_body(handler):
    length = int(handler.headers.get("Content-Length", 0) or 0)
    return json.loads(handler.rfile.read(length).decode("utf-8")) if length else {}


def install_handler_routes(handler_class):
    if getattr(handler_class, "_multi_chat_routes_installed", False):
        return
    original_get = handler_class.do_GET
    original_post = handler_class.do_POST

    def do_get(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/multi-chats":
            uid = current_user(self)
            if not uid:
                return self.send_json({"ok": False, "error": "Authentication required"}, status=401)
            return self.send_json({"ok": True, "rooms": _list(uid), "ais": list_ais(uid), "max_ais": MAX_AIS_PER_ACCOUNT}, uid)
        if path == "/api/multi-chats/open":
            uid = current_user(self)
            if not uid:
                return self.send_json({"ok": False, "error": "Authentication required"}, status=401)
            from urllib.parse import parse_qs, urlparse
            cid = parse_qs(urlparse(self.path).query).get("conversation_id", [""])[0]
            room = _load(uid, cid)
            if not room:
                return self.send_json({"ok": False, "error": "Conversation not found"}, uid, 404)
            return self.send_json({"ok": True, "room": room}, uid)
        return original_get(self)

    def do_post(self):
        path = self.path.split("?", 1)[0]
        routes = {
            "/api/multi-chats/new", "/api/multi-chats/rename", "/api/multi-chats/delete",
            "/api/multi-chats/participants", "/api/multi-chats/message", "/api/multi-chats/talk"
        }
        if path not in routes:
            return original_post(self)
        uid = current_user(self)
        if not uid:
            return self.send_json({"ok": False, "error": "Authentication required"}, status=401)
        try:
            data = _json_body(self)
        except Exception:
            return self.send_json({"ok": False, "error": "Invalid JSON"}, uid, 400)
        if path == "/api/multi-chats/new":
            return self.send_json({"ok": True, "room": new_room(uid)}, uid)
        cid = str(data.get("conversation_id", ""))
        if path == "/api/multi-chats/rename":
            if not rename_room(uid, cid, data.get("title")):
                return self.send_json({"ok": False, "error": "Unable to rename conversation"}, uid, 400)
            return self.send_json({"ok": True}, uid)
        if path == "/api/multi-chats/delete":
            if not delete_room(uid, cid):
                return self.send_json({"ok": False, "error": "Conversation not found"}, uid, 404)
            return self.send_json({"ok": True}, uid)
        if path == "/api/multi-chats/participants":
            room = set_participants(uid, cid, data.get("ais"))
            if not room:
                return self.send_json({"ok": False, "error": "Select at least one valid AI"}, uid, 400)
            return self.send_json({"ok": True, "room": room}, uid)
        if path == "/api/multi-chats/message":
            result = send_message(uid, cid, data.get("message"))
            if not result:
                return self.send_json({"ok": False, "error": "Unable to send message. Select at least one AI."}, uid, 400)
            return self.send_json({"ok": True, **result}, uid)
        result = ai_talk(uid, cid)
        if not result:
            return self.send_json({"ok": False, "error": "Unable to start AI conversation. Select at least one AI."}, uid, 400)
        return self.send_json({"ok": True, **result}, uid)

    handler_class.do_GET = do_get
    handler_class.do_POST = do_post
    handler_class._multi_chat_routes_installed = True
