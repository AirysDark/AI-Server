# AI Server

A Python-based AI server deployed through PythonAnywhere and exposed through a No-IP hostname for use by the Android client and other applications.

## Live Server

**Public endpoint:**

`https://ai-server.ddns.net`

The Android application is already confirmed to communicate successfully with this endpoint.

## Deployment

The production deployment currently uses:

- **PythonAnywhere** for hosting
- **Python 3.13.1** for the active WSGI environment
- **uWSGI** as the PythonAnywhere web worker
- **No-IP** for the public hostname
- **HTTPS** for client connections

### PythonAnywhere project

```text
/home/AirysDarkX2/Kitty-server
```

PythonAnywhere WSGI configuration:

```text
/var/www/airysdarkx2_pythonanywhere_com_wsgi.py
```

Project WSGI module:

```text
/home/AirysDarkX2/Kitty-server/wsgi.py
```

## DNS

The public hostname is:

```text
ai-server.ddns.net
```

The working No-IP record is:

```text
Type:   CNAME
Host:   ai-server
Target: webapp-3180826.pythonanywhere.com
TTL:    60 seconds
```

This CNAME points the No-IP hostname to the PythonAnywhere web application.

## Current Python Environment

The active PythonAnywhere WSGI runtime has been verified as:

```text
Python executable:
/usr/local/bin/uwsgi

Python version:
3.13.1
```

The `requests` dependency has also been verified directly inside the active WSGI environment:

```text
REQUESTS IMPORT: SUCCESS
REQUESTS VERSION: 2.32.3
REQUESTS FILE:
/usr/local/lib/python3.13/site-packages/requests/__init__.py
```

The project's WSGI application was also verified:

```text
WSGI IMPORT: SUCCESS
application object loaded successfully.
```

## Architecture

```text
Android App
    |
    | HTTPS
    v
https://ai-server.ddns.net
    |
    | No-IP CNAME
    v
webapp-3180826.pythonanywhere.com
    |
    | PythonAnywhere Web App
    v
WSGI
    |
    v
wsgi.py
    |
    v
server.py
    |
    v
AIHandler
    |
    v
online_ai.py
    |
    v
requests / online AI API
```

## Main Files

| File | Purpose |
|---|---|
| `server.py` | Main HTTP server and request handling |
| `online_ai.py` | Online AI/API functionality |
| `wsgi.py` | PythonAnywhere WSGI adapter |
| `requirements.txt` | Python dependencies |
| `AI_SERVER_CONTEXT.txt` | Full deployment/debug history and known-good configuration |

## WSGI Adapter

The project uses a WSGI adapter so the existing HTTP request handler can run under PythonAnywhere.

The adapter was specifically corrected for the Python 3.13 environment. One historical failure was:

```text
AttributeError: 'WSGIHandler' object has no attribute 'directory'
```

The WSGI adapter was updated to correctly handle the handler's required attributes.

Another historical issue was a typo in the PythonAnywhere WSGI file:

```python
from wsgi import applicatio
```

The correct import is:

```python
from wsgi import application
```

The final WSGI import test succeeded.

## Resolved Requests Issue

An earlier deployment error reported:

```text
ModuleNotFoundError: No module named 'requests'
```

This is **resolved**.

The active PythonAnywhere WSGI environment currently imports:

```text
requests 2.32.3
```

Do not treat `requests` installation as the current problem unless a new error specifically demonstrates that it has become unavailable.

## Known-Good State

The following are confirmed working:

- [x] PythonAnywhere web application
- [x] Python 3.13.1 WSGI runtime
- [x] WSGI application import
- [x] `requests` import
- [x] No-IP DNS
- [x] CNAME routing
- [x] HTTPS endpoint
- [x] `ai-server.ddns.net`
- [x] Android client connectivity

## Development Guidance

When debugging a new problem, start from the current known-good deployment instead of repeating historical fixes.

In particular, do **not** automatically:

- reinstall `requests`
- change the Python version
- replace the No-IP CNAME
- revert the WSGI adapter
- assume the custom domain is offline

Only revisit those components if new evidence shows that one of them has actually failed.

## Next Areas to Test

Future development/debugging should concentrate on application-level behavior:

1. Android chat/API endpoint requests
2. GET endpoints
3. POST endpoints
4. JSON request and response handling
5. Online AI requests
6. Authentication and API keys, where applicable
7. Server-side exceptions
8. HTTP status codes
9. Android-side error handling
10. Correct production AI responses

## Repository

GitHub:

https://github.com/AirysDark/Kitty-server

> The GitHub repository is currently named `Kitty-server`, but the application and deployment are referred to as **AI Server**.

## Deployment Context

For the complete historical deployment/debugging context, see:

```text
AI_SERVER_CONTEXT.txt
```
