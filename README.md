# AI Server

A self-hosted, multi-AI conversational server designed to provide a common backend for the web interface, Android client, Windows client, and other applications.

**Created by:** AirysDark  
**Powered by:** Python

## Live Server

**Public endpoint:** `https://ai-server.ddns.net`

The production application is hosted on PythonAnywhere and exposed through the No-IP hostname above.

## What AI Server Does

AI Server provides a complete personal-AI backend rather than only a chat endpoint. It manages users, multiple AI personalities, provider credentials, conversations, persistent memory/learning state, media, settings, and online AI requests.

### Core capabilities

- User registration, login, sessions, and password recovery
- Multiple independent AI profiles per account
- Active-AI selection and per-AI configuration
- Personality, instructions, traits, rules, and identity configuration
- Persistent conversations stored as individual `C-*.json` archives
- Conversation list, creation, opening, and renaming
- Direct loading of the selected conversation archive
- Last-used conversation restoration in the browser
- Persistent AI memory and learning/feedback state
- Proactive AI state/settings
- Profile photo support
- AI photo library and AI-specific photo storage
- Banner images
- Image uploads in conversations/settings
- Formatted/Markdown-style AI responses
- Online AI provider integration
- Provider/model selection per AI
- API endpoint and API-token configuration
- Automatic model discovery where supported
- Mobile-friendly web interface
- PythonAnywhere WSGI deployment
- HTTPS access through the public No-IP hostname

## Storage Architecture

Application code and persistent user data are intentionally separated.

```text
AI-Server/
    application code
    Python modules
    web interface
    configuration

AI-Server-Storage/
    users/
        U-.../
            ais/
                AI-.../
                    conversations/
                        C-....json
                    settings.json
                    photos/
                    ai_photos/
                    uploads/
                    learning/
                    memory/
                    ...
```

`AI-Server` is the application repository. `AI-Server-Storage` is the persistent data store.

Persistent conversations, user data, AI settings, photos, uploads, learning data, memory, and related state must remain in the storage area rather than becoming dependent on the application repository.

### Conversation source of truth

A conversation archive is the source of truth. The normal archive format is:

```json
{
  "conversation": [],
  "memory": {},
  "proactive_state": {},
  "created": 0,
  "updated": 0
}
```

The `conversation` property is an array containing the conversation entries.

**`current.json` is not used.** Selecting a conversation loads its actual `C-*.json` archive directly. The application does not copy a selected conversation into an intermediate `current.json` file.

## Conversation Management

The conversation system supports:

- Creating a new conversation
- Listing existing conversations
- Opening an exact conversation by ID
- Renaming conversations
- Multiple conversations for each AI
- Conversation timestamps
- Automatic titles based on conversation activity
- Direct archive loading after a chat is selected
- Browser restoration of the last-used conversation

### Last-chat restoration

The browser remembers the last selected conversation ID rather than copying conversation contents into browser storage.

```text
Select C-xxxxxxxx
        |
        v
save conversation ID
        |
        v
/index.html?chat=C-xxxxxxxx
        |
        v
POST /api/chats/open
        |
        v
load exact C-xxxxxxxx.json
        |
        v
render conversation
```

When the main chat page is opened without an explicit `chat` parameter, the browser checks the remembered conversation and attempts to load that exact archive for the active AI. Stale or unavailable saved chat state is ignored rather than becoming a new persistent conversation.

No conversation contents are duplicated into `localStorage`, and no `current.json` intermediary is required.

## AI Providers

Provider communication is separated from the chat interface so providers can be added or changed independently.

Current provider architecture includes:

```text
AI Server
   |
   +-- Hugging Face
   |
   +-- OpenAI
   |
   +-- Google AI Studio / Gemini
   |
   +-- additional compatible providers as implemented
```

### Hugging Face

Hugging Face is supported through its dedicated provider module. The server can work with configured Hugging Face models and provider routing.

If Hugging Face account-level inference credits are exhausted, individual model attempts can all fail with the same account billing/credit error; changing models does not bypass an exhausted account allowance.

### OpenAI

OpenAI is supported through its own provider implementation and can be configured from AI Settings.

### Google AI Studio / Gemini

Google AI Studio is supported through a dedicated Google provider module rather than being treated as a generic OpenAI provider.

Google settings support:

- Google AI Studio API key
- Google Gemini model selection
- Blank model field for automatic model selection
- Google model discovery through the API
- Filtering for models capable of the required generation operation
- Preferred-model selection with fallback to another available Gemini model
- Explicit model selection when the user wants to force a model
- Google-native API authentication and request handling

The intended Google workflow is:

```text
Provider: Google AI Studio
API Key: <user's Google AI Studio key>
API Model: blank

        |
        v
Google provider discovers available models
        |
        v
Select a suitable available Gemini model
        |
        v
Send request
```

Leaving the model blank means the backend can select an available model instead of permanently depending on a retired model name.

## AI Settings

The AI Settings page separates configuration from the main chat interface.

Settings include the areas supported by the current application, including:

- AI name/identity
- User information used by the AI
- Personality
- System instructions
- Traits
- Rules
- Provider/API selection
- API token/key
- API endpoint
- API model
- Online AI configuration
- Learning configuration
- Memory configuration
- Proactive behavior/state
- Image configuration
- Profile image
- AI photo functionality
- Banner image

Settings are saved per AI so switching between AIs changes the associated configuration and persistent state.

## Media Features

The application supports media associated with users and AIs.

### Profile photos

Profile images are stored in persistent user storage and served through the `/users/...` route. The web application supports profile-photo upload and cache-busted image refresh.

### AI photos

AI photos are stored in the AI's persistent photo area and can be managed through the photo library functionality.

### Banners

AI banner images can be uploaded from the main interface or AI Settings and persisted with the AI's settings.

### Conversation images

The chat interface supports image input where enabled by the configured provider/model.

## Learning and Memory

AI Server separates conversation archives from longer-lived AI state.

- **Conversation:** the actual chronological chat archive
- **Memory:** persistent AI/user information associated with the AI
- **Learning:** feedback/learning state used by the application
- **Proactive state:** state used by proactive behavior features

This prevents conversation history from having to be converted into a separate permanent format just to support memory or learning.

## Authentication and Accounts

The authentication layer provides:

- Account registration
- Login/logout/session handling
- Password recovery/reset functionality
- Authenticated API access
- Per-user AI ownership
- Per-user persistent storage

One account can contain multiple separate AI profiles according to the application's account limits/configuration.

## Web Interface

Current primary pages include:

```text
login.html
    Account login

register.html
    Account creation

forgot_password.html
    Password recovery

reset_password.html
    Password reset

setup.html
    Initial AI/account setup

select_ai.html
    Choose the active AI

index.html
    Main chat interface

chats.html
    Conversation management

ai_settings.html
    AI configuration and media settings

photo_library.html
    AI photo library
```

### Main chat interface

The chat page provides:

- Current AI identity/header
- Banner/profile presentation
- Conversation display
- Message input
- Image input
- Send controls
- AI typing/status feedback
- Navigation to AI selection
- Navigation to AI Settings
- Navigation to Conversations
- Navigation to the photo library
- Persistent conversation loading

## API Architecture

The application exposes HTTP API routes for authentication, settings, users, AI management, conversations, media, and online AI operations.

Important conversation routes include:

```text
GET  /api/chats
POST /api/chats/new
POST /api/chats/open
POST /api/chats/rename
```

The selected conversation is identified by its `C-*` conversation ID.

Other application areas include routes for:

```text
/api/auth/...
/api/settings
/api/user
/api/profile_photo
/api/ai_photo
```

The exact route implementation should be treated as the source of truth in the current codebase when adding or changing endpoints.

## Application Architecture

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
   +--------------------+--------------------+
   |                    |                    |
   v                    v                    v
core/auth.py       core/ai_manager.py   core/conversations.py
   |                    |                    |
   +--------------------+--------------------+
                        |
                        v
                 core/learning.py
                        |
                        v
                  API providers
             +----------+----------+
             |          |          |
             v          v          v
        Hugging Face OpenAI   Google AI Studio
```

## Application Modules

- `server.py` — main application entry point and compatibility HTTP server
- `wsgi.py` — PythonAnywhere WSGI adapter
- `core/server_impl.py` — core HTTP/application implementation
- `core/auth.py` — authentication, sessions, users, and password handling
- `core/ai_manager.py` — AI registry, selection, lifecycle, and AI paths
- `core/storage.py` — shared JSON/file persistence helpers
- `core/conversations.py` — conversation persistence and loading
- `core/learning.py` — learning/feedback integration
- `api/providers.py` — provider abstraction/selection
- `api/huggingface.py` — Hugging Face provider
- `api/openai.py` — OpenAI provider
- `api/google.py` — Google AI Studio/Gemini provider and model discovery
- `api/routes.py` — API route support
- `chats_api.py` — conversation list/new/open/rename operations
- `online_ai.py` — online AI compatibility/integration layer

## Client Compatibility

The backend is designed to be shared by multiple clients:

- Web interface
- Android client
- Windows client
- Other HTTP/API clients

The public server endpoint is:

```text
https://ai-server.ddns.net
```

Clients should use the production hostname rather than depending on the local PythonAnywhere host name.

## Deployment

Production deployment uses:

- PythonAnywhere
- Python 3.13.1 active WSGI environment
- uWSGI
- No-IP DNS
- HTTPS
- `~/AI-Server` as the application directory
- `AI-Server-Storage` as persistent data storage

### Deploying updates

On PythonAnywhere:

```bash
cd ~/AI-Server
git pull origin main
```

Then reload the PythonAnywhere web application.

## Python Environment

The active PythonAnywhere WSGI runtime uses:

```text
Python 3.13.1
```

The `requests` dependency is required by the external API provider implementations.

## Security and Data Separation

API keys/tokens are AI-specific settings and should be treated as secrets. Never commit personal API keys to the Git repository or publish them in screenshots/logs.

Persistent user data belongs in `AI-Server-Storage`, not in source-controlled application directories.

The browser's last-chat mechanism stores only an identifier; it does not store conversation contents.

## Known-Good Deployment Components

The project has been deployed and debugged with the following components:

- [x] PythonAnywhere web application
- [x] Python 3.13.1 WSGI runtime
- [x] uWSGI
- [x] No-IP hostname
- [x] HTTPS endpoint
- [x] Authentication
- [x] Account creation/password flows
- [x] Multiple AI profiles
- [x] AI selection
- [x] AI settings
- [x] Conversation creation
- [x] Direct conversation opening
- [x] Conversation rename
- [x] Last-chat restoration
- [x] Persistent AI/user storage separation
- [x] Hugging Face provider
- [x] OpenAI provider
- [x] Google AI Studio/Gemini provider
- [x] Profile photos
- [x] AI photo storage/library
- [x] Banner images
- [x] Learning/memory state
- [x] Modular application structure

## Important Design Rules

These rules are part of the current architecture and should not be casually changed:

1. **Do not reintroduce `current.json`.** Conversation selection loads the actual `C-*.json` archive directly.
2. **Do not move persistent user/AI data into the application repository.** Use `AI-Server-Storage`.
3. **Do not change the native conversation archive format merely to simplify frontend rendering.**
4. **Treat the exact selected conversation ID as the archive identifier.**
5. **Keep provider-specific logic in provider modules.**
6. **Google AI Studio model selection should remain capable of automatic discovery when the model field is blank.**
7. **Do not store API keys in source control.**
8. **Inspect the current main branch before making changes rather than relying on historical snippets.**

## Development Guidance

When debugging production problems:

1. Check the current GitHub `main` branch.
2. Check the PythonAnywhere application/server logs.
3. Check the HTTP status and response body for the affected API endpoint.
4. Confirm whether the problem is frontend, API routing, provider communication, or persistent storage.
5. Avoid changing unrelated working components.

Do not automatically:

- reinstall `requests`
- change the Python version
- replace No-IP routing
- reintroduce mDNS/UDP 5353
- replace the WSGI adapter
- move persistent storage back into the application repository
- introduce `current.json`

## Repository

urlAI-Server GitHub repositoryhttps://github.com/AirysDark/AI-Server

The repository is named `AI-Server`. Historical references may use `Kitty-server`, but the project and deployed application are referred to as **AI Server**.

## Deployment Context

Additional historical deployment/debug information is maintained in:

```text
AI_SERVER_CONTEXT.txt
```

The README describes the intended/current architecture; the actual source code remains authoritative for implementation details.