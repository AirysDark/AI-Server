"""Per-AI local GGUF model configuration and server-model selection routes."""
import json
import os
import re
from core.ai_manager import active_ai, ai_root, load_settings, save_settings

MAX_LOCAL_MODEL_BYTES = 2 * 1024 * 1024 * 1024
CHUNK_SIZE = 1024 * 1024
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(BASE_DIR, "models")


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


def _select_model(uid, ai_id, path, name=None):
    settings = load_settings(uid, ai_id)
    settings["api_provider"] = "local"
    for key in ("api_token", "hf_token", "openai_token", "google_token", "openrouter_token", "api_endpoint"):
        settings[key] = ""
    settings["api_model"] = name or os.path.basename(path)
    settings["local_model_path"] = os.path.abspath(path)
    settings.setdefault("features", {})["online_ai"] = True
    save_settings(uid, ai_id, settings)
    return settings


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
        _select_model(uid, ai_id, target, name)
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
    return {
        "ok": True,
        "configured": exists,
        "filename": os.path.basename(configured) if configured else "",
        "size": size,
        "path": configured if exists else "",
        "provider": settings.get("api_provider", "huggingface"),
    }


def _server_models():
    os.makedirs(MODELS_DIR, exist_ok=True)
    result = []
    for name in sorted(os.listdir(MODELS_DIR), key=str.lower):
        if not name.lower().endswith(".gguf"):
            continue
        path = os.path.abspath(os.path.join(MODELS_DIR, name))
        if os.path.isfile(path):
            try:
                result.append({"filename": name, "size": os.path.getsize(path)})
            except OSError:
                pass
    return result


def _select_server_model(uid, ai_id, filename):
    filename = os.path.basename(str(filename or ""))
    path = os.path.abspath(os.path.join(MODELS_DIR, filename))
    if (
        not filename.lower().endswith(".gguf")
        or not os.path.isfile(path)
        or os.path.dirname(path) != os.path.abspath(MODELS_DIR)
    ):
        raise ValueError("Model not found in the server models folder")
    _select_model(uid, ai_id, path, filename)
    return _status(uid, ai_id)


def _merge_settings_preserving_local_model(uid, ai_id, incoming):
    """Merge a normal settings save without losing the selected GGUF model.

    The settings page can POST an older in-memory copy immediately after the
    model dropdown selects a GGUF. That old copy contains api_provider=local
    but does not contain local_model_path, which previously erased the newly
    selected model and caused brain.py to fall back to the default SmolLM.
    """
    current = load_settings(uid, ai_id)
    if not isinstance(incoming, dict):
        incoming = {}

    incoming_provider = str(incoming.get("api_provider") or "").strip().lower()
    current_provider = str(current.get("api_provider") or "").strip().lower()

    # Start with the current settings so fields unknown to an older frontend
    # are not accidentally deleted by a full settings POST.
    merged = dict(current)
    merged.update(incoming)

    # If Local AI remains selected and the frontend omitted the path, keep the
    # exact server model that was selected by /api/local-models.
    local_requested = incoming_provider == "local" or (
        not incoming_provider and current_provider == "local"
    )
    if local_requested:
        current_path = str(current.get("local_model_path") or "").strip()
        incoming_path = str(incoming.get("local_model_path") or "").strip()
        if not incoming_path and current_path:
            merged["local_model_path"] = current_path

        current_model = str(current.get("api_model") or "").strip()
        incoming_model = str(incoming.get("api_model") or "").strip()
        if not incoming_model and current_model:
            merged["api_model"] = current_model

        merged["api_provider"] = "local"
        if merged.get("local_model_path"):
            merged.setdefault("features", {})["online_ai"] = True

    return merged


def handle_wsgi_upload(environ, start_response):
    class CookieHandler:
        def __init__(self, cookie):
            self.headers = {"Cookie": cookie or ""}

    handler = CookieHandler(environ.get("HTTP_COOKIE", ""))
    uid, ai_id = active_ai(handler)
    if not uid:
        body = json.dumps({"error": "Authentication required"}).encode()
        start_response(
            "401 Unauthorized",
            [("Content-Type", "application/json"), ("Content-Length", str(len(body)))],
        )
        return [body]
    try:
        content_length = int(environ.get("CONTENT_LENGTH") or 0)
        result = _store_model(
            uid,
            ai_id,
            environ.get("HTTP_X_LOCAL_MODEL_NAME", "local_model.gguf"),
            environ["wsgi.input"],
            content_length,
        )
        body = json.dumps(result, ensure_ascii=False).encode("utf-8")
        start_response(
            "200 OK",
            [
                ("Content-Type", "application/json; charset=utf-8"),
                ("Content-Length", str(len(body))),
            ],
        )
        return [body]
    except Exception as exc:
        body = json.dumps({"error": str(exc)[:500]}).encode("utf-8")
        start_response(
            "500 Internal Server Error",
            [("Content-Type", "application/json"), ("Content-Length", str(len(body)))],
        )
        return [body]


def _install(handler_class):
    if getattr(handler_class, "_local_model_routes_installed", False):
        return
    original_post = handler_class.do_POST
    original_get = handler_class.do_GET

    def do_get(handler):
        path = handler.path.split("?", 1)[0]
        if path not in ("/api/local-model", "/api/local-models"):
            return original_get(handler)
        uid, ai_id = active_ai(handler)
        if not uid:
            return handler.send_json({"error": "Authentication required"}, status=401)
        if path == "/api/local-models":
            return handler.send_json(
                {"ok": True, "models": _server_models(), "directory": MODELS_DIR},
                uid,
                200,
                ai_id,
            )
        return handler.send_json(_status(uid, ai_id), uid, 200, ai_id)

    def do_post(handler):
        path = handler.path.split("?", 1)[0]
        if path not in ("/api/local-model", "/api/local-models", "/api/settings"):
            return original_post(handler)

        uid, ai_id = active_ai(handler)
        if not uid:
            return handler.send_json({"error": "Authentication required"}, status=401)

        try:
            if path == "/api/settings":
                length = int(handler.headers.get("Content-Length", "0") or 0)
                incoming = json.loads(handler.rfile.read(length).decode("utf-8") or "{}")
                settings = _merge_settings_preserving_local_model(uid, ai_id, incoming)
                save_settings(uid, ai_id, settings)
                status = _status(uid, ai_id)
                print(
                    "LOCAL AI SETTINGS SAVED:",
                    status.get("filename") or "no local model",
                    status.get("path") or "",
                )
                return handler.send_json(settings, uid, 200, ai_id)

            if path == "/api/local-models":
                length = int(handler.headers.get("Content-Length", "0") or 0)
                data = json.loads(handler.rfile.read(length).decode("utf-8") or "{}")
                result = _select_server_model(uid, ai_id, data.get("filename"))
                print("LOCAL AI MODEL SELECTED:", result.get("filename"), result.get("path"))
                return handler.send_json(result, uid, 200, ai_id)

            content_length = int(handler.headers.get("Content-Length", "0") or 0)
            result = _store_model(
                uid,
                ai_id,
                handler.headers.get("X-Local-Model-Name", "local_model.gguf"),
                handler.rfile,
                content_length,
            )
            print("LOCAL AI MODEL UPLOADED:", result.get("filename"), result.get("path"))
            return handler.send_json(result, uid, 200, ai_id)
        except ValueError as exc:
            return handler.send_json({"error": str(exc)}, uid, 400, ai_id)
        except Exception as exc:
            print("LOCAL MODEL ROUTE ERROR:", exc)
            return handler.send_json({"error": str(exc)[:500]}, uid, 500, ai_id)

    handler_class.do_GET = do_get
    handler_class.do_POST = do_post
    handler_class._local_model_routes_installed = True


def install_handler_routes(handler_class):
    _install(handler_class)
