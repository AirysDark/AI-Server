"""Conversation archive API."""
import json
import os
import re
import time
import uuid

from core.ai_manager import active_ai, ai_root, load_conversation, save_conversation_data
from core.storage import load_json, save_json


def _safe(value):
    return re.sub(r"[^A-Za-z0-9_-]", "", str(value or ""))[:100]


def _paths(uid, ai_id):
    root = ai_root(uid, ai_id)
    archive = os.path.join(root, "conversations")
    return root, archive, os.path.join(root, "conversation.json")


def _title(data):
    explicit = str(data.get("title", "")).strip() if isinstance(data, dict) else ""
    if explicit:
        return explicit[:80]
    # Automatically name a conversation from its first user message.
    for item in data.get("conversation", []):
        text = str(item.get("user", item.get("content", ""))).strip()
        if text:
            text = " ".join(text.split())
            return text[:60] + ("..." if len(text) > 60 else "")
    return "New chat"


def _archive_current(uid, ai_id):
    _, archive, _ = _paths(uid, ai_id)
    data = load_conversation(uid, ai_id)
    if not data.get("conversation"):
        return None
    os.makedirs(archive, exist_ok=True)
    cid = "C-" + uuid.uuid4().hex[:16]
    now = time.time()
    record = {"conversation_id": cid, "title": _title(data), "created": data.get("created", now), "updated": data.get("updated", now), "data": data}
    save_json(os.path.join(archive, cid + ".json"), record)
    return record


def list_chats(uid, ai_id):
    _, archive, _ = _paths(uid, ai_id)
    os.makedirs(archive, exist_ok=True)
    result = []
    for name in os.listdir(archive):
        if not name.endswith(".json"):
            continue
        try:
            record = load_json(os.path.join(archive, name), {})
            if isinstance(record, dict) and record.get("conversation_id"):
                result.append({k: record.get(k) for k in ("conversation_id", "title", "created", "updated")})
        except Exception:
            continue
    current_data = load_conversation(uid, ai_id)
    if current_data.get("conversation"):
        result.append({"conversation_id": "current", "title": _title(current_data), "created": current_data.get("created", 0), "updated": current_data.get("updated", time.time()), "current": True})
    result.sort(key=lambda x: x.get("updated", 0) or 0, reverse=True)
    return result


def new_chat(uid, ai_id):
    _archive_current(uid, ai_id)
    now = time.time()
    data = {"conversation": [], "memory": {}, "proactive_state": {}, "created": now, "updated": now}
    save_conversation_data(uid, ai_id, data)
    return {"ok": True, "conversation_id": "current"}


def open_chat(uid, ai_id, conversation_id):
    if conversation_id == "current":
        return load_conversation(uid, ai_id)
    _, archive, _ = _paths(uid, ai_id)
    path = os.path.join(archive, _safe(conversation_id) + ".json")
    record = load_json(path, None)
    if not isinstance(record, dict) or not isinstance(record.get("data"), dict):
        return None
    current = load_conversation(uid, ai_id)
    if current.get("conversation"):
        _archive_current(uid, ai_id)
    data = record["data"]
    data["updated"] = time.time()
    save_conversation_data(uid, ai_id, data)
    return data


def rename_chat(uid, ai_id, conversation_id, title):
    title = " ".join(str(title or "").strip().split())[:80]
    if not title:
        return False
    if conversation_id == "current":
        data = load_conversation(uid, ai_id)
        if not data.get("conversation"):
            return False
        data["title"] = title
        data["updated"] = time.time()
        save_conversation_data(uid, ai_id, data)
        return True
    _, archive, _ = _paths(uid, ai_id)
    path = os.path.join(archive, _safe(conversation_id) + ".json")
    record = load_json(path, None)
    if not isinstance(record, dict) or not isinstance(record.get("data"), dict):
        return False
    record["title"] = title
    record["updated"] = time.time()
    record["data"]["title"] = title
    record["data"]["updated"] = record["updated"]
    save_json(path, record)
    return True


def install_handler_routes(handler_class, server_module):
    """Install chat routes on the legacy HTTP handler for local serving."""
    if getattr(handler_class, "_chat_routes_installed", False):
        return
    original_get = handler_class.do_GET
    original_post = handler_class.do_POST

    def do_get(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/chats":
            uid, ai_id = active_ai(self)
            if not uid:
                return self.send_json({"ok": False, "error": "Authentication required"}, None, 401)
            return self.send_json({"ok": True, "ai_id": ai_id, "chats": list_chats(uid, ai_id)}, uid, 200, ai_id)
        return original_get(self)

    def do_post(self):
        path = self.path.split("?", 1)[0]
        if path not in ("/api/chats/new", "/api/chats/open", "/api/chats/rename"):
            return original_post(self)
        uid, ai_id = active_ai(self)
        if not uid:
            return self.send_json({"ok": False, "error": "Authentication required"}, None, 401)
        try:
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        except Exception:
            return self.send_json({"ok": False, "error": "Invalid JSON"}, uid, 400, ai_id)
        if path == "/api/chats/new":
            return self.send_json(new_chat(uid, ai_id), uid, 200, ai_id)
        conversation_id = str(data.get("conversation_id", "")).strip()
        if not conversation_id:
            return self.send_json({"ok": False, "error": "conversation_id required"}, uid, 400, ai_id)
        if path == "/api/chats/rename":
            if not rename_chat(uid, ai_id, conversation_id, data.get("title")):
                return self.send_json({"ok": False, "error": "Unable to rename conversation"}, uid, 400, ai_id)
            return self.send_json({"ok": True, "conversation_id": conversation_id}, uid, 200, ai_id)
        result = open_chat(uid, ai_id, conversation_id)
        if result is None:
            return self.send_json({"ok": False, "error": "Conversation not found"}, uid, 404, ai_id)
        return self.send_json({"ok": True, "conversation_id": conversation_id}, uid, 200, ai_id)

    handler_class.do_GET = do_get
    handler_class.do_POST = do_post
    handler_class._chat_routes_installed = True
