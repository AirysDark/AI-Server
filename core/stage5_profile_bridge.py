"""AI profile-photo storage bridge.

Keeps AI profile photos inside the selected AI's persistent directory and
normalizes uploaded/legacy images to profile/default.png.
"""
from io import BytesIO
import os
import shutil
from PIL import Image
from core import server_impl
from core.ai_manager import account_root, ai_root, get_ai_registry, load_settings, save_settings, active_ai
from core.config import USERS_DIR

_PROFILE_DIR_NAME = "profile"


def profile_dir(uid, ai_id):
    return os.path.join(ai_root(uid, ai_id), _PROFILE_DIR_NAME)


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


def _migrate_account(uid):
    registry = get_ai_registry().get("accounts", {}).get(uid, {})
    ai_id = registry.get("active_ai") or ((registry.get("ais") or [{}])[0].get("ai_id"))
    if not ai_id:
        return
    root = account_root(uid)
    if not os.path.isdir(root):
        return
    target = profile_dir(uid, ai_id)
    os.makedirs(target, exist_ok=True)
    settings = load_settings(uid, ai_id)
    current = settings.get("profile_photo", "")
    current_name = os.path.basename(str(current)) if current else ""
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


def _install():
    if getattr(server_impl, "_profile_storage_bridge_installed", False):
        return
    original_save_upload = server_impl.save_upload
    original_get = server_impl.AIHandler.do_GET

    def save_upload(data, name, directory):
        try:
            root = os.path.abspath(USERS_DIR)
            candidate = os.path.abspath(directory)
            relative = os.path.relpath(candidate, root)
            if relative != os.pardir and len(relative.split(os.sep)) == 1:
                uid = relative
                registry = get_ai_registry().get("accounts", {}).get(uid, {})
                ai_id = registry.get("active_ai") or ((registry.get("ais") or [{}])[0].get("ai_id"))
                if ai_id:
                    target = profile_dir(uid, ai_id)
                    os.makedirs(target, exist_ok=True)
                    with open(os.path.join(target, "default.png"), "wb") as handle:
                        handle.write(_png_bytes(data))
                    return "default.png"
        except Exception:
            pass
        return original_save_upload(data, name, directory)

    def do_get(handler):
        if handler.path.split("?", 1)[0] == "/profile/default.png":
            path = _ensure_default()
            try:
                with open(path, "rb") as handle:
                    data = handle.read()
                handler.send_response(200)
                handler.send_header("Content-Type", "image/png")
                handler.send_header("Content-Length", str(len(data)))
                handler.end_headers()
                handler.wfile.write(data)
                return
            except Exception:
                pass
        return original_get(handler)

    server_impl.save_upload = save_upload
    server_impl.AIHandler.do_GET = do_get
    server_impl._profile_storage_bridge_installed = True


def apply():
    _ensure_default()
    for uid in get_ai_registry().get("accounts", {}):
        _migrate_account(uid)
    _install()
    return server_impl
