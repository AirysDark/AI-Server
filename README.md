# AI Server

A Python-based AI server deployed through PythonAnywhere and exposed through a No-IP hostname for use by the Android client, Windows client, web interface, and other applications.

## Live Server

**Public endpoint:**

`https://ai-server.ddns.net`

The production server is currently online and the clients communicate with this endpoint.

## Deployment

The production deployment uses:

- **PythonAnywhere** for hosting
- **Python 3.13.1** for the active WSGI environment
- **uWSGI** as the PythonAnywhere web worker
- **No-IP** for the public hostname
- **HTTPS** for client connections

The repository is deployed as the `AI-Server` project on PythonAnywhere.

## DNS

The public hostname is:

```text
ai-server.ddns.net
```

The production hostname is routed to the PythonAnywhere web application through No-IP.

## Current Python Environment

The active PythonAnywhere WSGI runtime uses:

```text
Python 3.13.1
```

The `requests` dependency is required by the server's external API providers.

## Architecture

The server has been refactored into separate application modules while retaining compatibility with the existing HTTP handler:

```text
Clients
   |
   | HTTPS
   v
https://ai-server.ddns.net
   |
   v
PythonAnywhere / uWSGI
   |
   v
wsgi.py
   |
   v
server.py
   |
   v
core/server_impl.py
   |
   +-------------------+-------------------+
   |                   |                   |
   v                   v                   v
core/auth.py      core/ai_manager.py   core/conversations.py
   |                   |                   |
   +-------------------+-------------------+
                       |
                       v
                  core/learning.py
                       |
                       v
                 API providers
                 +-----------+
                 |           |
                 v           v
            Hugging Face   OpenAI
```

### Application modules

- `core/auth.py` — authentication, sessions, users, and password handling
- `core/ai_manager.py` — AI registry, AI selection, creation/deletion, and AI filesystem paths
- `core/storage.py` — shared JSON/file persistence
- `core/conversations.py` — conversation loading and persistence
- `core/learning.py` — learning and feedback integration
- `api/huggingface.py` — Hugging Face provider communication
- `api/openai.py` — OpenAI provider communication
- `api/providers.py` — provider selection and common provider handling
- `api/routes.py` — API route support
- `chats_api.py` — conversation list, new chat, open chat, and chat rename operations

The obsolete mDNS discovery implementation has been removed. The server does not require mDNS/UDP 5353 for normal operation.

## Web Interface

The web interface is separated into focused pages:

```text
index.html
    Chat interface

ai_settings.html
    AI configuration

select_ai.html
    AI selection

chats.html
    Conversation list

photo_library.html
    AI photo library
```

### Chat features

The chat interface supports the current AI, conversation navigation, media, learning feedback, and formatted AI responses.

Conversation management includes:

- Multiple conversations per AI
- New conversation
- Opening previous conversations
- Conversation naming
- Press-and-hold conversation rename on supported devices
- Automatic initial conversation naming from the first user message

AI settings are deliberately separated from the chat interface and are accessed through **AI Settings** rather than being embedded in the chat page.

### AI settings

AI configuration includes:

- AI identity and user information
- Personality, instructions, traits, and rules
- Hugging Face API token
- OpenAI API token
- Provider selection
- API endpoint/model configuration
- Online AI settings
- Learning settings
- Memory settings
- Proactive AI settings
- Image settings
- Profile and banner images

The provider architecture is designed so additional compatible AI API providers can be added without coupling provider communication to the chat UI.

## Main Files

| File | Purpose |
|---|---|
| `server.py` | Main application entry point and compatibility HTTP server |
| `wsgi.py` | PythonAnywhere WSGI adapter |
| `core/server_impl.py` | Existing HTTP/application implementation during the modular refactor |
| `core/auth.py` | Authentication and session functionality |
| `core/ai_manager.py` | AI lifecycle and active-AI management |
| `core/storage.py` | Shared persistence helpers |
| `core/conversations.py` | Conversation persistence |
| `core/learning.py` | Learning/feedback integration |
| `chats_api.py` | Conversation API operations |
| `online_ai.py` | Compatibility entry point for online AI functionality |
| `api/providers.py` | AI provider abstraction |
| `api/huggingface.py` | Hugging Face API implementation |
| `api/openai.py` | OpenAI API implementation |
| `requirements.txt` | Python dependencies |
| `AI_SERVER_CONTEXT.txt` | Deployment/debug history and known-good configuration |

## Active AI Selection

The selected AI is maintained consistently across the application using the authenticated session and active-AI state. The same active AI is used by:

- Chat
- AI settings
- Conversations
- Learning/memory
- API requests
- Media/photo features

Switching AI should therefore switch the associated settings and conversations as well.

## WSGI Adapter

The project uses a WSGI adapter so the existing application can run under PythonAnywhere.

The adapter exposes:

```python
application
```

and imports the application through the modular server entry point.

Historical WSGI issues involving missing `current_user`/`active_ai` exports have been resolved by importing those values from their canonical `core` modules instead of relying on `server.py` to expose legacy globals.

## Known-Good Deployment State

The following production components have been verified during deployment/debugging:

- [x] PythonAnywhere web application
- [x] Python 3.13.1 WSGI runtime
- [x] WSGI application loading
- [x] `requests` dependency
- [x] No-IP hostname
- [x] HTTPS endpoint
- [x] `ai-server.ddns.net`
- [x] Client connectivity
- [x] Authentication
- [x] AI selection
- [x] AI settings
- [x] Multiple conversations
- [x] Conversation rename
- [x] Hugging Face provider
- [x] OpenAI provider integration
- [x] Modular application structure

## Development Guidance

When debugging a new problem, start from the current known-good deployment instead of repeating historical fixes.

In particular, do not automatically:

- reinstall `requests`
- change the Python version
- replace the No-IP routing
- reintroduce mDNS
- revert the WSGI adapter
- assume the custom domain is offline

Only revisit those components when new evidence shows that one has actually failed.

For application problems, check the PythonAnywhere error/server logs and the HTTP status codes for the affected endpoint first.

## Repository

urlAI-Server GitHub repositoryhttps://github.com/AirysDark/AI-Server

The GitHub repository is named `AI-Server`. Historical project references may use `Kitty-server`, but the application and deployment are referred to as **AI Server**.

## Deployment Context

For the complete historical deployment and debugging context, see:

```text
AI_SERVER_CONTEXT.txt
```
