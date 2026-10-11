"""Small Requests-compatible fallback used when requests is unavailable.
Only the HTTP features used by online_ai.py are implemented.
"""
import json as _json
import urllib.request
import urllib.error

class RequestException(Exception):
    pass

class Response:
    def __init__(self, status_code, body, headers=None):
        self.status_code = status_code
        self._body = body
        self.headers = headers or {}
        self.text = body.decode("utf-8", "replace")

    def json(self):
        return _json.loads(self.text)

def _request(method, url, headers=None, json=None, timeout=45):
    data = None
    req_headers = dict(headers or {})
    if json is not None:
        data = _json.dumps(json).encode("utf-8")
        req_headers.setdefault("Content-Type", "application/json")
    request = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return Response(response.status, response.read(), dict(response.headers.items()))
    except urllib.error.HTTPError as exc:
        return Response(exc.code, exc.read(), dict(exc.headers.items()) if exc.headers else {})
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RequestException(str(exc)) from exc

def get(url, headers=None, timeout=45):
    return _request("GET", url, headers=headers, timeout=timeout)

def post(url, headers=None, json=None, timeout=45):
    return _request("POST", url, headers=headers, json=json, timeout=timeout)
