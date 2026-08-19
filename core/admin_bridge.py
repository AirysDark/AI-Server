"""Install admin routes on the existing AIHandler without altering normal APIs."""
import json
from urllib.parse import urlparse, parse_qs
from core.admin_api import ADMIN_COOKIE, handle_get, handle_post


def install_handler_routes(handler_cls):
    if getattr(handler_cls, "_admin_routes_installed", False):
        return
    original_get = handler_cls.do_GET
    original_post = handler_cls.do_POST

    def do_get(self):
        parsed = urlparse(self.path)
        if handle_get(self, parsed.path, parse_qs(parsed.query)):
            return
        return original_get(self)

    def do_post(self):
        parsed = urlparse(self.path)
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
                # Login is the only admin action that returns a deferred response
                # so the authentication cookie can be attached before the body.
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
