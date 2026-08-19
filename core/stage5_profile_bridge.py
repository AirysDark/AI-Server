"""AI profile-photo storage bridge.

AI profile photos live inside the selected AI's persistent directory and are
normalized to profile/default.png. Legacy account-root images are migrated on
server startup.
"""
from io import BytesIO
import os
import shutil
import re
from email.parser import BytesParser
from email.policy import default
from PIL import Image
from core import server_impl
from core.ai_manager import account_root, ai_root, get_ai_registry, load_settings, save_settings
from core.config import USERS_DIR


def profile_dir(uid, ai_id):
    return os.path.join(ai_root(uid, ai_id), "profile")


def _png_bytes(data):
    with Image.open(BytesIO(data)) as image:
        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGBA")
        out = BytesIO()
        image.save(out, format="PNG", optimize=True)
        return out.getvalue()


def _ensure_default():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    directory = os.path.join(root, "profile")
    path = os.path.join(directory, "default.png")
    if os.path.isfile(path):
        return path
    os.makedirs(directory, exist_ok=True)
    image = Image.new("RGBA", (256, 256), (48, 48, 56, 255))
    image.save(path, format="PNG", optimize=True)
    return path


def _active_ai_for(uid):
    account = get_ai_registry().get("accounts", {}).get(uid, {})
    return account.get("active_ai") or ((account.get("ais") or [{}])[0].get("ai_id"))


def _migrate_account(uid):
    ai_id = _active_ai_for(uid)
    if not ai_id:
        return
    root = account_root(uid)
    if not os.path.isdir(root):
        return
    target = profile_dir(uid, ai_id)
    os.makedirs(target, exist_ok=True)
    settings = load_settings(uid, ai_id)
    current_name = os.path.basename(str(settings.get("profile_photo", "")))
    image_files = []
    for name in os.listdir(root):
        path = os.path.join(root, name)
        if os.path.isfile(path) and name.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif")):
            image_files.append(path)
    if not image_files:
        return
    chosen = next((p for p in image_files if os.path.basename(p) == current_name), image_files[-1])
    try:
        with open(chosen, "rb") as handle:
            converted = _png_bytes(handle.read())
        with open(os.path.join(target, "default.png"), "wb") as handle:
            handle.write(converted)
        settings["profile_photo"] = f"/users/{uid}/ais/{ai_id}/profile/default.png"
        save_settings(uid, ai_id, settings)
    except Exception:
        return
    legacy = os.path.join(target, "legacy")
    os.makedirs(legacy, exist_ok=True)
    for path in image_files:
        try:
            shutil.move(path, os.path.join(legacy, os.path.basename(path)))
        except Exception:
            pass


def _read_uploaded_file(handler):
    content_type = handler.headers.get("Content-Type", "")
    length = int(handler.headers.get("Content-Length", 0))
    raw = handler.rfile.read(length)
    parsed = BytesParser(policy=default).parsebytes((f"Content-Type: {content_type}\r\n\r\n").encode() + raw)
    if not parsed.is_multipart():
        return None
    for part in parsed.iter_parts():
        disposition = part.get("Content-Disposition", "")
        if 'name="file"' not in disposition:
            continue
        match = re.search(r'filename="([^"]*)"', disposition)
        return part.get_payload(decode=True), (match.group(1) if match else "profile.png")
    return None


def _install():
    if getattr(server_impl, "_profile_storage_bridge_installed", False):
        return
    original_get = server_impl.AIHandler.do_GET
    original_post = server_impl.AIHandler.do_POST

    def do_get(handler):
        if handler.path.split("?", 1)[0] == "/profile/default.png":
            path = _ensure_default()
            with open(path, "rb") as handle:
                data = handle.read()
            handler.send_response(200)
            handler.send_header("Content-Type", "image/png")
            handler.send_header("Cache-Control", "public, max-age=3600")
            handler.send_header("Content-Length", str(len(data)))
            handler.end_headers()
            handler.wfile.write(data)
            return
        return original_get(handler)

    def do_post(handler):
        if handler.path.split("?", 1)[0] != "/api/profile_photo":
            return original_post(handler)
        from core.ai_manager import active_ai
        uid, ai_id = active_ai(handler)
        if not uid or not ai_id:
            return handler.send_json({"error": "Authentication required"}, status=401)
        uploaded = _read_uploaded_file(handler)
        if not uploaded or not uploaded[0]:
            return handler.send_json({"error": "No image uploaded"}, uid, 400, ai_id)
        data, _name = uploaded
        try:
            converted = _png_bytes(data)
        except Exception as exc:
            return handler.send_json({"error": f"Invalid image: {exc}"}, uid, 400, ai_id)
        directory = profile_dir(uid, ai_id)
        os.makedirs(directory, exist_ok=True)
        with open(os.path.join(directory, "default.png"), "wb") as handle:
            handle.write(converted)
        url = f"/users/{uid}/ais/{ai_id}/profile/default.png"
        settings = load_settings(uid, ai_id)
        settings["profile_photo"] = url
        save_settings(uid, ai_id, settings)
        return handler.send_json({"ok": True, "profile_photo": url}, uid, 200, ai_id)

    server_impl.AIHandler.do_GET = do_get
    server_impl.AIHandler.do_POST = do_post
    server_impl._profile_storage_bridge_installed = True


def apply():
    _ensure_default()
    for uid in get_ai_registry().get("accounts", {}):
        _migrate_account(uid)
    _install()
    return server_impl
