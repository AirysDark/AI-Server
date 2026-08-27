"""HTTP application implementation for AI-Server.

The root ``server.py`` is the public entry point. Storage, authentication,
AI lifecycle, conversation persistence and provider selection are maintained
by their dedicated modules and installed by the compatibility bridges.
"""
from http.server import SimpleHTTPRequestHandler
import json, os, uuid, re, random, time, shutil
from urllib.parse import urlparse, parse_qs, unquote
from email.parser import BytesParser
from email.policy import default
from brain import think
from online_ai import ask_online
from core.config import USERS_DIR


def features(settings):
    f = settings.get("features", {})
    return {
        "online_ai": f.get("online_ai", True),
        "learning": f.get("learning", True),
        "long_term_memory": f.get("long_term_memory", True),
        "relevant_memory": f.get("relevant_memory", True),
        "automatic_images": f.get("automatic_images", False),
        "proactive_images": f.get("proactive_images", False),
    }


def random_image(uid, ai_id):
    directory = ai_photo_dir(uid, ai_id)
    os.makedirs(directory, exist_ok=True)
    files = [x for x in os.listdir(directory) if x.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif"))]
    if not files:
        return None
    return f"/users/{uid}/ais/{ai_id}/ai_photos/{random.choice(files)}"


def clean_reply(value):
    if not isinstance(value, str):
        return value
    for marker in ("[Sends a photo]", "[Sends a playful photo", "[Shows image]", "[Uploads image]"):
        value = value.replace(marker, "")
    return value.strip()


def ai_profile(profile, message, settings):
    lines = []
    for key, label in (("ai_name", "Name"), ("description", "Description"), ("personality", "Personality"), ("instructions", "Instructions"), ("user_name", "User name"), ("user_information", "User information")):
        if settings.get(key):
            lines.append(f"{label}: {settings[key]}")
    config = settings.get("config", {})
    if config.get("traits"):
        lines.append("Traits: " + ", ".join(map(str, config["traits"])))
    if config.get("rules"):
        lines.append("Rules: " + " | ".join(map(str, config["rules"])))
    if profile.get("memory"):
        lines.append("Memory: " + json.dumps(profile["memory"], ensure_ascii=False))
    recent = profile.get("conversation", [])[-RECENT_CONTEXT_MESSAGES:]
    if recent:
        lines.append("Recent conversation: " + json.dumps(recent, ensure_ascii=False))
    return "\n".join(lines)


def save_conversation(uid, ai_id, conversation_id, user_message, ai_reply, image=None):
    conversation_id = clean_id(conversation_id)
    if not conversation_id or conversation_id == "current":
        raise ValueError("A valid conversation_id is required")
    data = load_archived_conversation(uid, ai_id, conversation_id)
    if data is None:
        raise ValueError("Conversation not found")
    now = time.time()
    data.setdefault("conversation", []).append({"user": user_message, "ai": ai_reply, "image": image, "time": now})
    data["updated"] = now
    data.setdefault("created", now)
    save_archived_conversation(uid, ai_id, conversation_id, data)


def safe_name(name):
    return re.sub(r"[^A-Za-z0-9._-]", "_", os.path.basename(str(name or "upload.bin")))[:120]


def save_upload(data, name, directory):
    os.makedirs(directory, exist_ok=True)
    filename = safe_name(name)
    with open(os.path.join(directory, filename), "wb") as handle:
        handle.write(data)
    return filename


def _chat_result(uid, ai_id, conversation_id, message, image_data=None, image_name=None):
    conversation_id = clean_id(conversation_id)
    if not conversation_id or conversation_id == "current":
        raise ValueError("A valid conversation_id is required")
    settings = load_settings(uid, ai_id)
    enabled = features(settings)
    profile = load_archived_conversation(uid, ai_id, conversation_id)
    if profile is None:
        raise ValueError("Conversation not found")
    image_path = None
    if image_data and image_name:
        name = save_upload(image_data, image_name, upload_dir(uid, ai_id))
        image_path = f"/users/{uid}/ais/{ai_id}/uploads/{name}"
    prompt = str(message or "").strip()
    if image_path:
        prompt = (prompt + " " if prompt else "") + f"[Attached Image: {image_path}]"
    scoped_memory = os.path.join(ai_root(uid, ai_id), "brain_memory.json")
    scoped_learning = os.path.join(ai_root(uid, ai_id), "learning_replies.json")
    context = ai_profile(profile, prompt, settings)
    reply = clean_reply(ask_online(prompt, settings, context, image_path=image_path)) if enabled["online_ai"] else None
    if not reply:
        reply = clean_reply(think(prompt, settings, scoped_memory, scoped_learning))
    if not reply:
        reply = "I couldn't get an AI response right now."
    lower = prompt.lower()
    wants_image = enabled["automatic_images"] and any(k in lower for k in ("send a photo", "send me a photo", "send a picture", "send me a picture", "show me a photo", "show me a picture"))
    if "[Attached Image:" not in prompt and enabled["automatic_images"] and any(k in lower for k in ("photo", "picture", "image")):
        wants_image = True
    if wants_image and not image_path:
        image_path = random_image(uid, ai_id)
    if enabled["learning"]:
        learn_from_conversation(prompt, reply, scoped_memory)
    save_conversation(uid, ai_id, conversation_id, message or "", reply, image_path)
    return {"reply": reply, "user_id": uid, "ai_id": ai_id, "conversation_id": conversation_id, "image": image_path}


class AIHandler(SimpleHTTPRequestHandler):
    def send_auth(self, token):
        self.send_header("Set-Cookie", f"AI_session={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=2592000")

    def send_active_cookie(self, ai_id):
        self.send_header("Set-Cookie", f"AI_active={ai_id}; Path=/; SameSite=Lax; Max-Age=31536000")

    def send_json(self, data, uid=None, status=200, ai_id=None, session_token=None):
        output = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        if uid:
            self.send_header("Set-Cookie", f"AI_user={uid}; Path=/; Max-Age=31536000; SameSite=Lax")
        if ai_id:
            self.send_active_cookie(ai_id)
        if session_token:
            self.send_auth(session_token)
        self.send_header("Content-Length", str(len(output)))
        self.end_headers()
        self.wfile.write(output)

    def translate_path(self, path):
        """Serve /users/* from AI-Server-Storage instead of the code repo."""
        parsed_path = urlparse(path).path
        if parsed_path == "/users" or parsed_path.startswith("/users/"):
            relative = unquote(parsed_path[len("/users"):]).lstrip("/")
            root = os.path.abspath(USERS_DIR)
            target = os.path.abspath(os.path.join(root, relative))
            if target == root or target.startswith(root + os.sep):
                return target
            return root
        return super().translate_path(path)

    def auth_required(self):
        uid = current_user(self)
        if not uid:
            self.send_json({"ok": False, "error": "Authentication required"}, status=401)
            return None
        return uid

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        if path == "/api/health":
            return self.send_json({"ok": True, "server": "AI", "host": PUBLIC_HOSTNAME, "port": PORT, "url": PUBLIC_URL})
        if path == "/api/proactive":
            uid, ai_id = active_ai(self)
            if not uid:
                return self.send_json({"ok": False, "error": "Authentication required"}, status=401)
            proactive_fn = globals().get("proactive")
            if not proactive_fn:
                return self.send_json({"message": None, "ok": True}, uid, 200, ai_id)
            return self.send_json(proactive_fn(uid, ai_id, query.get("last_activity", [0])[0]) or {"message": None}, uid, 200, ai_id)
        if path == "/api/auth/me":
            uid = current_user(self)
            if not uid:
                return self.send_json({"authenticated": False})
            account = get_accounts().get("users", {}).get(uid, {})
            return self.send_json({"authenticated": True, "user_id": uid, "email": account.get("email"), "username": account.get("username"), "max_ais": MAX_AIS_PER_ACCOUNT, "ais": list_ais(uid)})
        if path == "/api/settings":
            uid, ai_id = active_ai(self)
            if not uid:
                return self.send_json({"error": "Authentication required"}, status=401)
            return self.send_json(load_settings(uid, ai_id), uid, 200, ai_id)
        if path == "/api/user":
            uid, ai_id = active_ai(self)
            if not uid:
                return self.send_json({"error": "Authentication required"}, status=401)
            conversation_id = clean_id(cookie(self, "AI_chat"))
            data = load_archived_conversation(uid, ai_id, conversation_id) if conversation_id else None
            return self.send_json(data if data is not None else load_conversation(uid, ai_id), uid, 200, ai_id)
        if path == "/api/ais":
            uid = self.auth_required()
            if uid:
                return self.send_json({"ais": list_ais(uid), "max": MAX_AIS_PER_ACCOUNT}, uid)
        super().do_GET()

    def do_POST(self):
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            content_type = self.headers.get("Content-Type", "")
            if path == "/chat":
                uid, ai_id = active_ai(self)
                if not uid:
                    return self.send_json({"error": "Authentication required"}, status=401)
                conversation_id = clean_id(cookie(self, "AI_chat"))
                if not conversation_id:
                    return self.send_json({"error": "No active conversation selected"}, uid, 400, ai_id)
                length = int(self.headers.get("Content-Length", 0))
                if "multipart/form-data" in content_type:
                    raw = self.rfile.read(length)
                    parsed_form = BytesParser(policy=default).parsebytes((f"Content-Type: {content_type}\r\n\r\n").encode() + raw)
                    fields, image_data, image_name = {}, None, None
                    if parsed_form.is_multipart():
                        for part in parsed_form.iter_parts():
                            disposition = part.get("Content-Disposition", "")
                            name_match = re.search(r'name="([^"]+)"', disposition)
                            filename_match = re.search(r'filename="([^"]*)"', disposition)
                            if not name_match:
                                continue
                            if filename_match:
                                image_name = filename_match.group(1)
                                image_data = part.get_payload(decode=True)
                            else:
                                fields[name_match.group(1)] = part.get_content()
                    result = _chat_result(uid, ai_id, conversation_id, fields.get("message", ""), image_data, image_name)
                else:
                    data = json.loads(self.rfile.read(length).decode("utf-8"))
                    requested_id = clean_id(data.get("conversation_id"))
                    if requested_id:
                        conversation_id = requested_id
                    result = _chat_result(uid, ai_id, conversation_id, data.get("message", ""))
                return self.send_json(result, uid, 200, ai_id)
            if path in ("/api/profile_photo", "/api/ai_photo"):
                uid, ai_id = active_ai(self)
                if not uid:
                    return self.send_json({"error": "Authentication required"}, status=401)
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length)
                parsed_form = BytesParser(policy=default).parsebytes((f"Content-Type: {content_type}\r\n\r\n").encode() + raw)
                file_data, file_name = None, None
                if parsed_form.is_multipart():
                    for part in parsed_form.iter_parts():
                        disposition = part.get("Content-Disposition", "")
                        if 'name="file"' in disposition:
                            match = re.search(r'filename="([^"]*)"', disposition)
                            file_name = match.group(1) if match else None
                            file_data = part.get_payload(decode=True)
                            break
                if not file_data:
                    return self.send_json({"error": "No image uploaded"}, uid, 400, ai_id)
                if path == "/api/profile_photo":
                    name = save_upload(file_data, file_name or "profile.jpg", account_root(uid))
                    url = f"/users/{uid}/{name}"
                    settings = load_settings(uid, ai_id)
                    settings["profile_photo"] = url
                    save_settings(uid, ai_id, settings)
                    return self.send_json({"ok": True, "profile_photo": url}, uid, 200, ai_id)
                name = save_upload(file_data, file_name or "ai_photo.jpg", ai_photo_dir(uid, ai_id))
                return self.send_json({"ok": True, "image": f"/users/{uid}/ais/{ai_id}/ai_photos/{name}"}, uid, 200, ai_id)
            if path == "/api/settings":
                uid, ai_id = active_ai(self)
                if not uid:
                    return self.send_json({"error": "Authentication required"}, status=401)
                length = int(self.headers.get("Content-Length", 0))
                data = json.loads(self.rfile.read(length).decode("utf-8"))
                save_settings(uid, ai_id, data)
                return self.send_json(load_settings(uid, ai_id), uid, 200, ai_id)
            if path == "/api/ai/select":
                uid = self.auth_required()
                if not uid:
                    return
                length = int(self.headers.get("Content-Length", 0))
                data = json.loads(self.rfile.read(length).decode("utf-8"))
                ai_id = clean_id(data.get("ai_id"))
                if not set_active(uid, ai_id):
                    return self.send_json({"error": "AI not found"}, uid, 404)
                return self.send_json({"ok": True, "ai_id": ai_id}, uid, 200, ai_id)
            if path == "/api/ai/create":
                uid = self.auth_required()
                if not uid:
                    return
                ai_id = create_ai(uid)
                if not ai_id:
                    return self.send_json({"error": "Maximum of 3 AIs reached"}, uid, 400)
                return self.send_json({"ok": True, "ai_id": ai_id}, uid, 200, ai_id)
            if path == "/api/ai/delete":
                uid = self.auth_required()
                if not uid:
                    return
                length = int(self.headers.get("Content-Length", 0))
                data = json.loads(self.rfile.read(length).decode("utf-8"))
                ai_id = clean_id(data.get("ai_id"))
                if not delete_ai(uid, ai_id):
                    return self.send_json({"error": "Cannot delete AI"}, uid, 400)
                return self.send_json({"ok": True}, uid)
            if path == "/api/auth/logout":
                token = cookie(self, "AI_session")
                sessions = get_sessions()
                sessions.pop(token, None)
                save_json(SESSIONS_FILE, sessions)
                return self.send_json({"ok": True})
            if path in ("/api/auth/login", "/api/auth/register"):
                length = int(self.headers.get("Content-Length", 0))
                data = json.loads(self.rfile.read(length).decode("utf-8"))
                accounts = get_accounts()
                users = accounts.setdefault("users", {})
                email = normalize_email(data.get("email"))
                password = str(data.get("password", "")).strip()
                if not valid_email(email) or len(password) < 6:
                    return self.send_json({"error": "Valid email and password of at least 6 characters required"}, status=400)
                existing = next(((user_id, user) for user_id, user in users.items() if normalize_email(user.get("email")) == email), None)
                if path.endswith("register"):
                    if existing:
                        return self.send_json({"error": "Account already exists"}, status=409)
                    uid = "U-" + uuid.uuid4().hex[:16]
                    users[uid] = {"email": email, "username": str(data.get("username", "")).strip()[:60], "password": hash_password(password)}
                    save_json(AUTH_FILE, accounts)
                    ensure_first_ai(uid)
                else:
                    if not existing or not verify_password(password, existing[1].get("password", "")):
                        return self.send_json({"error": "Invalid email or password"}, status=401)
                    uid = existing[0]
                    ensure_first_ai(uid)
                token = create_session(uid)
                return self.send_json({"ok": True, "user_id": uid, "ais": list_ais(uid)}, uid, 200, session_token=token)
            self.send_error(404)
        except Exception as exc:
            print("SERVER ERROR:", exc)
            try:
                self.send_json({"ok": False, "error": str(exc)}, status=500)
            except Exception:
                pass
