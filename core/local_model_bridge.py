"""Per-AI local GGUF model upload and configuration routes."""
import json
import os
import re
from core.ai_manager import active_ai, ai_root, load_settings, save_settings

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


def _store_model(uid, ai_id, name, reader, content_length):
    if content_length <= 0:
        raise ValueError("No model file uploaded")
    if content_length > MAX_LOCAL_MODEL_BYTES:
        raise ValueError("Local model is larger than the 2 GB upload limit")
    name = _safe_model_name(name)
    target = os.path.abspath(os.path.join(_model_dir(uid, ai_id), name))
    temp_path = target + ".uploading"
    received = 0
    try:
        with open(temp_path, "wb") as output:
            while received < content_length:
                chunk = reader.read(min(CHUNK_SIZE, content_length - received))
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
        return {"ok": True, "filename": name, "size": received, "path": target, "provider": "local"}
    except Exception:
        try:
            os.remove(temp_path)
        except OSError:
            pass
        raise


def _status(uid, ai_id):
    settings = load_settings(uid, ai_id)
    configured = str(settings.get("local_model_path") or "").strip()
    exists = bool(configured and os.path.isfile(configured))
    size = os.path.getsize(configured) if exists else 0
    return {"ok": True, "configured": exists, "filename": os.path.basename(configured) if configured else "", "size": size, "path": configured if exists else "", "provider": settings.get("api_provider", "huggingface")}


def handle_wsgi_upload(environ, start_response):
    """Handle the large model upload before WSGI reads the whole request into RAM."""
    class CookieHandler:
        def __init__(self, cookie):
            self.headers = {"Cookie": cookie or ""}
    handler = CookieHandler(environ.get("HTTP_COOKIE", ""))
    uid, ai_id = active_ai(handler)
    if not uid:
        body = json.dumps({"error": "Authentication required"}).encode()
        start_response("401 Unauthorized", [("Content-Type", "application/json"), ("Content-Length", str(len(body)))])
        return [body]
    try:
        content_length = int(environ.get("CONTENT_LENGTH") or 0)
        result = _store_model(uid, ai_id, environ.get("HTTP_X_LOCAL_MODEL_NAME", "local_model.gguf"), environ["wsgi.input"], content_length)
        body = json.dumps(result, ensure_ascii=False).encode("utf-8")
        start_response("200 OK", [("Content-Type", "application/json; charset=utf-8"), ("Content-Length", str(len(body)))])
        return [body]
    except ValueError as exc:
        body = json.dumps({"error": str(exc)}).encode("utf-8")
        start_response("413 Request Entity Too Large", [("Content-Type", "application/json"), ("Content-Length", str(len(body)))])
        return [body]
    except Exception as exc:
        print("LOCAL MODEL WSGI UPLOAD ERROR:", exc)
        body = json.dumps({"error": str(exc)[:500]}).encode("utf-8")
        start_response("500 Internal Server Error", [("Content-Type", "application/json"), ("Content-Length", str(len(body)))])
        return [body]


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
        return handler.send_json(_status(uid, ai_id), uid, 200, ai_id)

    def do_post(handler):
        path = handler.path.split("?", 1)[0]
        if path != "/api/local-model":
            return original_post(handler)
        uid, ai_id = active_ai(handler)
        if not uid:
            return handler.send_json({"error": "Authentication required"}, status=401)
        try:
            content_length = int(handler.headers.get("Content-Length", "0") or 0)
            result = _store_model(uid, ai_id, handler.headers.get("X-Local-Model-Name", "local_model.gguf"), handler.rfile, content_length)
            return handler.send_json(result, uid, 200, ai_id)
        except ValueError as exc:
            return handler.send_json({"error": str(exc)}, uid, 413, ai_id)
        except Exception as exc:
            print("LOCAL MODEL UPLOAD ERROR:", exc)
            return handler.send_json({"error": str(exc)[:500]}, uid, 500, ai_id)

    handler_class.do_GET = do_get
    handler_class.do_POST = do_post
    handler_class._local_model_routes_installed = True


def install_handler_routes(handler_class):
    _install(handler_class)
