"""Install admin routes on the existing AIHandler without altering normal APIs."""
import json
import os
import re
from urllib.parse import urlparse, parse_qs
from core.admin_api import ADMIN_COOKIE, admin_user, handle_get, handle_post, upload_file
from core.logging_setup import ERROR_LOG, ACCESS_LOG


def _read_lines(path, limit=500):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            lines = handle.readlines()
        return [line.rstrip("\n") for line in lines[-limit:]]
    except OSError:
        return []


def _error_log_data():
    application = _read_lines(ERROR_LOG)
    access = []
    for line in _read_lines(ACCESS_LOG, 1000):
        if re.search(r"\s[45]\d\d\s", line):
            access.append(line)
    return {
        "ok": True,
        "application_errors": application,
        "http_errors": access,
        "application_count": len(application),
        "http_count": len(access),
        "error_log": ERROR_LOG,
        "access_log": ACCESS_LOG,
    }


def _serve_admin_page(handler, original_get):
    """Serve admin.html with the Errors option injected without editing the page source."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "admin.html")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            html = handle.read()
        marker = '<button onclick="tab(\'adminpass\')">Admin Password</button>'
        button = marker + '<button class="danger" onclick="location.href=\'/admin-errors.html\'">Errors</button>'
        if marker in html and "/admin-errors.html" not in html:
            html = html.replace(marker, button, 1)
        output = html.encode("utf-8")
        handler.send_response(200)
        handler.send_header("Content-Type", "text/html; charset=utf-8")
        handler.send_header("Content-Length", str(len(output)))
        handler.end_headers()
        handler.wfile.write(output)
        return
    except Exception:
        return original_get(handler)


def install_handler_routes(handler_cls):
    if getattr(handler_cls, "_admin_routes_installed", False):
        return
    original_get = handler_cls.do_GET
    original_post = handler_cls.do_POST

    def do_get(self):
        parsed = urlparse(self.path)
        if parsed.path in ("/admin", "/admin/"):
            return _serve_admin_page(self, original_get)
        if parsed.path == "/admin.html":
            return _serve_admin_page(self, original_get)
        if parsed.path == "/api/admin/errors":
            if not admin_user(self):
                return self.send_json({"ok": False, "error": "Administrator authentication required"}, status=401)
            return self.send_json(_error_log_data())
        if handle_get(self, parsed.path, parse_qs(parsed.query)):
            return
        return original_get(self)

    def do_post(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/admin/file/upload":
            if not admin_user(self):
                return self.send_json({"ok": False, "error": "Administrator authentication required"}, status=401)
            query = parse_qs(parsed.query)
            uid = (query.get("uid") or [""])[0]
            path = (query.get("path") or [""])[0]
            length = int(self.headers.get("Content-Length", 0) or 0)
            raw = self.rfile.read(length)
            result, status = upload_file(self, uid, path, raw, self.headers.get("Content-Type", ""))
            return self.send_json(result, status=status)
        if parsed.path.startswith("/api/admin/"):
            length = int(self.headers.get("Content-Length", 0) or 0)
            try:
                data = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
            except Exception:
                return self.send_json({"ok": False, "error": "Invalid JSON request"}, status=400)
            handled, result = handle_post(self, parsed.path, data)
            if not handled:
                return original_post(self)
            if result is not None:
                response, status, token = result
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                if token:
                    self.send_header("Set-Cookie", f"{ADMIN_COOKIE}={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age=86400")
                output = json.dumps(response, ensure_ascii=False).encode("utf-8")
                self.send_header("Content-Length", str(len(output)))
                self.end_headers()
                self.wfile.write(output)
            return
        return original_post(self)

    handler_cls.do_GET = do_get
    handler_cls.do_POST = do_post
    handler_cls._admin_routes_installed = True
