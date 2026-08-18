"""Direct conversation archive API.

Archived conversations are the source of truth. There is no current.json
working buffer for chat selection. Opening a chat reads that exact archive
file and returns its contents directly to the client.
"""
import json
import os
import re
import time
import uuid

from core.ai_manager import active_ai, ai_root, conversations_root, load_conversation, save_conversation_data, load_archived_conversation
from core.storage import load_json, save_json


def _safe(value):
    return re.sub(r"[^A-Za-z0-9_-]", "", str(value or ""))[:100]


def _title(data):
    explicit = str(data.get("title", "")).strip() if isinstance(data, dict) else ""
    if explicit:
        return explicit[:80]
    for item in data.get("conversation", []):
        text = str(item.get("user", item.get("content", ""))).strip()
        if text:
            text = " ".join(text.split())
            return text[:60] + ("..." if len(text) > 60 else "")
    return "New chat"


def _normalise_record(record, conversation_id=None):
    if not isinstance(record, dict):
        return None
    data = record.get("data") if isinstance(record.get("data"), dict) else record
    if not isinstance(data, dict):
        return None
    data.setdefault("conversation", [])
    return {
        "conversation_id": conversation_id or record.get("conversation_id") or "",
        "title": record.get("title") or data.get("title") or _title(data),
        "created": record.get("created", data.get("created", 0)),
        "updated": record.get("updated", data.get("updated", 0)),
        "data": data,
    }


def _archive_current(uid, ai_id):
    """Keep existing live conversation compatibility, but archive it as a chat."""
    data = load_conversation(uid, ai_id)
    if not data.get("conversation"):
        return None
    archive = conversations_root(uid, ai_id)
    os.makedirs(archive, exist_ok=True)
    cid = "C-" + uuid.uuid4().hex[:16]
    now = time.time()
    record = {"conversation_id": cid, "title": _title(data), "created": data.get("created", now), "updated": data.get("updated", now), "data": data}
    save_json(os.path.join(archive, cid + ".json"), record)
    return record


def list_chats(uid, ai_id):
    archive = conversations_root(uid, ai_id)
    os.makedirs(archive, exist_ok=True)
    result = []
    for name in os.listdir(archive):
        if not name.endswith(".json") or name == "current.json":
            continue
        path = os.path.join(archive, name)
        try:
            record = _normalise_record(load_json(path, {}), os.path.splitext(name)[0])
            if record and record["conversation_id"] and record["data"].get("conversation"):
                result.append({k: record.get(k) for k in ("conversation_id", "title", "created", "updated")})
        except Exception:
            continue
    result.sort(key=lambda x: x.get("updated", 0) or 0, reverse=True)
    return result


def new_chat(uid, ai_id):
    """Start a new live chat without using current.json as a selected-chat buffer."""
    return {"ok": True, "conversation_id": "new"}


def open_chat(uid, ai_id, conversation_id):
    """Return the selected archived conversation directly; never copy it to current.json."""
    conversation_id = _safe(conversation_id)
    if not conversation_id or conversation_id == "current":
        return None
    record = _normalise_record(load_archived_conversation(uid, ai_id, conversation_id), conversation_id)
    if record is None:
        path = os.path.join(conversations_root(uid, ai_id), conversation_id + ".json")
        record = _normalise_record(load_json(path, None), conversation_id)
    if record is None:
        return None
    data = record["data"]
    return data


def rename_chat(uid, ai_id, conversation_id, title):
    title = " ".join(str(title or "").strip().split())[:80]
    if not title or conversation_id in ("", "current", "new"):
        return False
    path = os.path.join(conversations_root(uid, ai_id), _safe(conversation_id) + ".json")
    record = load_json(path, None)
    if not isinstance(record, dict):
        return False
    if isinstance(record.get("data"), dict):
        record["data"]["title"] = title
        record["data"]["updated"] = time.time()
    record["title"] = title
    record["updated"] = time.time()
    save_json(path, record)
    return True


def install_handler_routes(handler_class, server_module):
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
        return self.send_json({"ok": True, "conversation_id": conversation_id, "conversation": result.get("conversation", []), "data": result}, uid, 200, ai_id)

    handler_class.do_GET = do_get
    handler_class.do_POST = do_post
    handler_class._chat_routes_installed = True
