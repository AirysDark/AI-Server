"""Per-AI local GGUF model upload and configuration routes."""
import os
import re
import tempfile
from core.ai_manager import active_ai, ai_root, load_settings, save_settings
from core.auth import current_user

MAX_LOCAL_MODEL_BYTES = 2 * 1024 * 1024 * 1024
CHUNK_SIZE = 1024 * 1024


def _safe_model_name(name):
    name = os.path.basename(str(name or "")).strip()
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    if not name.lower().endswith(".gguf"):
        name += ".gguf"
    return name[:160]


def _model_dir(uid, ai_id):
    path = os.path.join(ai_root(uid, ai_id), "local_models")
    os.makedirs(path, exist_ok=True)
    return path


def _install(handler_class):
    if getattr(handler_class, "_local_model_routes_installed", False):
        return
    original_post = handler_class.do_POST
    original_get = handler_class.do_GET

    def do_get(handler):
        path = handler.path.split("?", 1)[0]
        if path != "/api/local-model":
            return original_get(handler)
        uid, ai_id = active_ai(handler)
        if not uid:
            return handler.send_json({"error": "Authentication required"}, status=401)
        settings = load_settings(uid, ai_id)
        configured = str(settings.get("local_model_path") or "").strip()
        exists = bool(configured and os.path.isfile(configured))
        size = os.path.getsize(configured) if exists else 0
        return handler.send_json({
            "ok": True,
            "configured": exists,
            "filename": os.path.basename(configured) if configured else "",
            "size": size,
            "path": configured if exists else "",
            "provider": settings.get("api_provider", "huggingface"),
        }, uid, 200, ai_id)

    def do_post(handler):
        path = handler.path.split("?", 1)[0]
        if path != "/api/local-model":
            return original_post(handler)
        uid, ai_id = active_ai(handler)
        if not uid:
            return handler.send_json({"error": "Authentication required"}, status=401)
        content_length = int(handler.headers.get("Content-Length", "0") or 0)
        if content_length <= 0:
            return handler.send_json({"error": "No model file uploaded"}, uid, 400, ai_id)
        if content_length > MAX_LOCAL_MODEL_BYTES:
            return handler.send_json({"error": "Local model is larger than the 2 GB upload limit"}, uid, 413, ai_id)
        name = _safe_model_name(handler.headers.get("X-Local-Model-Name", "local_model.gguf"))
        directory = _model_dir(uid, ai_id)
        target = os.path.abspath(os.path.join(directory, name))
        temp_path = target + ".uploading"
        received = 0
        try:
            with open(temp_path, "wb") as output:
                while received < content_length:
                    chunk = handler.rfile.read(min(CHUNK_SIZE, content_length - received))
                    if not chunk:
                        raise IOError("Upload ended before the complete model was received")
                    output.write(chunk)
                    received += len(chunk)
            if received != content_length:
                raise IOError("Incomplete model upload")
            os.replace(temp_path, target)
            settings = load_settings(uid, ai_id)
            settings["api_provider"] = "local"
            settings["api_token"] = ""
            settings["hf_token"] = ""
            settings["openai_token"] = ""
            settings["google_token"] = ""
            settings["openrouter_token"] = ""
            settings["api_endpoint"] = ""
            settings["api_model"] = name
            settings["local_model_path"] = target
            settings.setdefault("features", {})["online_ai"] = True
            save_settings(uid, ai_id, settings)
            return handler.send_json({"ok": True, "filename": name, "size": received, "path": target, "provider": "local"}, uid, 200, ai_id)
        except Exception as exc:
            try:
                os.remove(temp_path)
            except OSError:
                pass
            print("LOCAL MODEL UPLOAD ERROR:", exc)
            return handler.send_json({"error": str(exc)[:500]}, uid, 500, ai_id)

    handler_class.do_GET = do_get
    handler_class.do_POST = do_post
    handler_class._local_model_routes_installed = True


def install_handler_routes(handler_class):
    _install(handler_class)
