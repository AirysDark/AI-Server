"""PythonAnywhere WSGI entry point for AI-server.

This adapts the existing AIHandler to PythonAnywhere's WSGI web worker.
The standalone `python3 server.py` mode remains available for LAN use.
"""
import io
import os
import sys

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)
os.chdir(PROJECT_DIR)

from server import AIHandler  # noqa: E402


class _WSGIConnection:
    def __init__(self, request_bytes):
        self._rfile = io.BytesIO(request_bytes)
        self._wfile = io.BytesIO()

    def makefile(self, mode, buffering=None):
        return self._rfile if "r" in mode else self._wfile

    def settimeout(self, value):
        pass

    def gettimeout(self):
        return None

    def shutdown(self, how):
        pass

    def close(self):
        pass


class _WSGIRequestHandler(AIHandler):
    def setup(self):
        self.connection = self.request
        self.rfile = self.connection.makefile("rb", self.rbufsize)
        self.wfile = self.connection.makefile("wb", self.wbufsize)

    def finish(self):
        pass

    def address_string(self):
        return self.client_address[0]


def application(environ, start_response):
    method = environ.get("REQUEST_METHOD", "GET")
    path = environ.get("PATH_INFO") or "/"
    query = environ.get("QUERY_STRING", "")
    request_target = path + ("?" + query if query else "")

    header_lines = []
    for key, value in environ.items():
        if key.startswith("HTTP_"):
            header_lines.append(f"{key[5:].replace('_', '-')}: {value}")
    if environ.get("CONTENT_TYPE"):
        header_lines.append(f"Content-Type: {environ['CONTENT_TYPE']}")
    if environ.get("CONTENT_LENGTH"):
        header_lines.append(f"Content-Length: {environ['CONTENT_LENGTH']}")

    body_length = int(environ.get("CONTENT_LENGTH") or 0)
    body = environ["wsgi.input"].read(body_length) if body_length else b""
    raw_request = (
        f"{method} {request_target} HTTP/1.1\r\n"
        + "\r\n".join(header_lines)
        + "\r\n\r\n"
    ).encode("iso-8859-1") + body

    connection = _WSGIConnection(raw_request)
    handler = _WSGIRequestHandler.__new__(_WSGIRequestHandler)
    handler.request = connection
    handler.requestline = ""
    handler.client_address = (environ.get("REMOTE_ADDR", "127.0.0.1"), 0)
    handler.server = type("WSGIServer", (), {"server_name": "ai-server.ddns.net", "server_port": 80})()

    # Python 3.13's SimpleHTTPRequestHandler expects the
    # directory attribute when AIHandler.do_GET() falls back to
    # super().do_GET(). The normal socket server supplies this
    # through the handler initialization, but our WSGI adapter
    # constructs the handler manually, so set it explicitly.
    handler.directory = PROJECT_DIR

    handler.setup()
    handler.handle_one_request()

    response = connection._wfile.getvalue()
    separator = response.find(b"\r\n\r\n")
    if separator < 0:
        start_response("500 Internal Server Error", [("Content-Type", "text/plain; charset=utf-8")])
        return [b"Invalid HTTP response from AI server"]

    header_block = response[:separator].decode("iso-8859-1")
    response_body = response[separator + 4:]
    lines = header_block.split("\r\n")
    status_parts = lines[0].split(" ", 2)
    status = f"{status_parts[1]} {status_parts[2]}" if len(status_parts) >= 3 else "500 Internal Server Error"

    response_headers = []
    for line in lines[1:]:
        if ":" not in line:
            continue
        name, value = line.split(":", 1)
        if name.lower() in ("transfer-encoding", "connection", "server", "date"):
            continue
        response_headers.append((name.strip(), value.strip()))

    if not any(name.lower() == "content-length" for name, _ in response_headers):
        response_headers.append(("Content-Length", str(len(response_body))))

    start_response(status, response_headers)
    return [response_body]
