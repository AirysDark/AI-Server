"""Per-AI Telegram Bot integration.

Each AI can have its own Telegram bot token. Incoming Telegram messages are
routed to that AI's existing personality, instructions, memory context and
selected online provider. Webhooks are used so PythonAnywhere does not need a
long-running polling worker.
"""
import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from urllib.parse import urlparse

from brain import think
from online_ai import ask_online
from core.ai_manager import ai_root, load_settings, save_settings
from core.auth import clean_id, current_user
from core.config import PUBLIC_URL
from core.server_impl import ai_profile, clean_reply, features
from core.storage import load_json, save_json


def _token(settings):
    return str(settings.get("telegram_bot_token") or "").strip()


def _secret(settings):
    secret = str(settings.get("telegram_webhook_secret") or "").strip()
    if secret:
        return secret
    token = _token(settings)
    if not token:
        return ""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _api(token, method, payload=None):
    if not token:
        raise RuntimeError("Telegram bot token is not configured")
    url = f"https://api.telegram.org/bot{token}/{method}"
    body = json.dumps(payload or {}).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"Telegram HTTP {exc.code}: {detail[:500]}")
    except Exception as exc:
        raise RuntimeError(f"Telegram connection failed: {exc}")
    if not data.get("ok"):
        raise RuntimeError(data.get("description") or "Telegram API request failed")
    return data.get("result")


def _chat_file(uid, ai_id, chat_id):
    safe_uid = clean_id(uid); safe_ai = clean_id(ai_id)
    safe_chat = re.sub(r"[^0-9_-]", "", str(chat_id))[:80]
    return os.path.join(ai_root(safe_uid, safe_ai), "telegram_chats", f"{safe_chat}.json")


def _load_chat(uid, ai_id, chat_id):
    data = load_json(_chat_file(uid, ai_id, chat_id), {"conversation": []})
    if not isinstance(data, dict):
        data = {"conversation": []}
    if not isinstance(data.get("conversation"), list):
        data["conversation"] = []
    return data


def _save_chat(uid, ai_id, chat_id, data):
    save_json(_chat_file(uid, ai_id, chat_id), data)


def _telegram_reply(uid, ai_id, chat_id, text, sender_name=""):
    settings = load_settings(uid, ai_id)
    chat = _load_chat(uid, ai_id, chat_id)
    memory = load_json(os.path.join(ai_root(uid, ai_id), "brain_memory.json"), {})
    profile = {"memory": memory if isinstance(memory, dict) else {}, "conversation": chat.get("conversation", [])}
    context = ai_profile(profile, text, settings)
    sender = f"\nTelegram user name: {sender_name}" if sender_name else ""
    prompt = f"You are replying through Telegram.{sender}\n\nUser message:\n{text}"
    enabled = features(settings)
    reply = clean_reply(ask_online(prompt, settings, context)) if enabled["online_ai"] else None
    if not reply:
        memory_path = os.path.join(ai_root(uid, ai_id), "brain_memory.json")
        learning_path = os.path.join(ai_root(uid, ai_id), "learning_replies.json")
        reply = clean_reply(think(prompt, settings, memory_path, learning_path))
    reply = reply or "I couldn't get a response right now."
    chat["conversation"].append({"role": "user", "text": text, "name": sender_name, "time": __import__("time").time()})
    chat["conversation"].append({"role": "assistant", "text": reply, "time": __import__("time").time()})
    chat["conversation"] = chat["conversation"][-50:]
    _save_chat(uid, ai_id, chat_id, chat)
    return reply


def _send_text(token, chat_id, text):
    # Telegram sendMessage has a 4096-character text limit.
    text = str(text or "").strip() or "..."
    for start in range(0, len(text), 4000):
        _api(token, "sendMessage", {"chat_id": chat_id, "text": text[start:start + 4000]})


def _webhook_url(uid, ai_id):
    base = PUBLIC_URL.rstrip("/")
    return f"{base}/api/telegram/webhook/{clean_id(uid)}/{clean_id(ai_id)}"


def connect(uid, ai_id):
    settings = load_settings(uid, ai_id)
    token = _token(settings)
    if not token:
        raise RuntimeError("Enter a Telegram Bot Token first")
    bot = _api(token, "getMe")
    secret = _secret(settings)
    settings["telegram_webhook_secret"] = secret
    settings["telegram_bot_username"] = bot.get("username", "")
    settings["telegram_bot_id"] = bot.get("id")
    settings["telegram_enabled"] = True
    save_settings(uid, ai_id, settings)
    _api(token, "setWebhook", {
        "url": _webhook_url(uid, ai_id),
        "secret_token": secret,
        "allowed_updates": ["message"],
        "drop_pending_updates": False,
    })
    return {
        "enabled": True,
        "username": bot.get("username", ""),
        "id": bot.get("id"),
        "webhook_url": _webhook_url(uid, ai_id),
    }


def disconnect(uid, ai_id):
    settings = load_settings(uid, ai_id)
    token = _token(settings)
    if token:
        try:
            _api(token, "deleteWebhook", {"drop_pending_updates": False})
        except Exception:
            pass
    settings["telegram_enabled"] = False
    save_settings(uid, ai_id, settings)
    return {"enabled": False}


def status(uid, ai_id):
    settings = load_settings(uid, ai_id)
    token = _token(settings)
    if not token:
        return {"enabled": False, "configured": False, "username": ""}
    result = {"enabled": bool(settings.get("telegram_enabled")), "configured": True, "username": settings.get("telegram_bot_username", "")}
    if settings.get("telegram_enabled"):
        try:
            info = _api(token, "getWebhookInfo")
            result["webhook"] = info
        except Exception as exc:
            result["error"] = str(exc)
    return result


def _handle_webhook(handler, uid, ai_id):
    settings = load_settings(uid, ai_id)
    expected = _secret(settings)
    supplied = handler.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not expected or supplied != expected:
        return handler.send_json({"ok": False}, status=403)
    length = int(handler.headers.get("Content-Length", 0) or 0)
    try:
        update = json.loads(handler.rfile.read(length).decode("utf-8")) if length else {}
    except Exception:
        return handler.send_json({"ok": False}, status=400)
    message = update.get("message") or update.get("edited_message")
    if not isinstance(message, dict) or not message.get("text"):
        return handler.send_json({"ok": True})
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    text = str(message.get("text") or "").strip()
    if chat_id is None:
        return handler.send_json({"ok": True})
    token = _token(settings)
    if text.lower() == "/start":
        _send_text(token, chat_id, f"Hi! I'm {settings.get('ai_name') or 'your AI'}. Send me a message and I'll reply here.")
        return handler.send_json({"ok": True})
    if text.lower() in ("/reset", "/newchat"):
        _save_chat(uid, ai_id, chat_id, {"conversation": []})
        _send_text(token, chat_id, "Conversation reset.")
        return handler.send_json({"ok": True})
    sender = message.get("from") or {}
    sender_name = " ".join(x for x in (sender.get("first_name", ""), sender.get("last_name", "")) if x).strip()
    try:
        _api(token, "sendChatAction", {"chat_id": chat_id, "action": "typing"})
        reply = _telegram_reply(uid, ai_id, chat_id, text, sender_name)
        _send_text(token, chat_id, reply)
    except Exception as exc:
        print("TELEGRAM AI ERROR:", exc)
        try:
            _send_text(token, chat_id, "Sorry, I couldn't respond right now.")
        except Exception:
            pass
    return handler.send_json({"ok": True})


def install_handler_routes(handler_class):
    if getattr(handler_class, "_telegram_routes_installed", False):
        return
    original_get = handler_class.do_GET
    original_post = handler_class.do_POST

    def do_get(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/api/telegram/status":
            uid = current_user(self)
            if not uid:
                return self.send_json({"ok": False, "error": "Authentication required"}, status=401)
            from core.ai_manager import active_ai
            _, ai_id = active_ai(self)
            return self.send_json({"ok": True, **status(uid, ai_id)}, uid, 200, ai_id)
        return original_get(self)

    def do_post(self):
        parsed = urlparse(self.path)
        path = parsed.path
        match = re.fullmatch(r"/api/telegram/webhook/([A-Za-z0-9_-]+)/([A-Za-z0-9_-]+)", path)
        if match:
            return _handle_webhook(self, match.group(1), match.group(2))
        if path in ("/api/telegram/connect", "/api/telegram/disconnect"):
            uid = current_user(self)
            if not uid:
                return self.send_json({"ok": False, "error": "Authentication required"}, status=401)
            from core.ai_manager import active_ai
            _, ai_id = active_ai(self)
            try:
                result = connect(uid, ai_id) if path.endswith("connect") else disconnect(uid, ai_id)
                return self.send_json({"ok": True, **result}, uid, 200, ai_id)
            except Exception as exc:
                return self.send_json({"ok": False, "error": str(exc)}, uid, 400, ai_id)
        return original_post(self)

    handler_class.do_GET = do_get
    handler_class.do_POST = do_post
    handler_class._telegram_routes_installed = True
