# AI-Server Windows Client

Visual Studio 2022 WPF client for the live AI-Server backend.

## Design

The Windows application is a thin client. AI logic, accounts, AI profiles, settings, memory, conversations, model selection and online AI calls remain on the server.

Default server:

`https://ai-server.ddns.net`

This means the Windows application does not contain a second copy of the AI backend. Server-side changes can be deployed without rebuilding the Windows client as long as the API contract remains compatible.

## Build

1. Install Visual Studio 2022 with the **.NET desktop development** workload.
2. Install the .NET 8 SDK/runtime supported by your VS2022 installation.
3. Open `windows/AI-Server.Windows.sln`.
4. Select `AI-Server.Windows` as the startup project.
5. Build and run.

## Implemented API integration

The client currently uses the existing AI-Server routes:

- `GET /api/health`
- `POST /api/auth/login`
- `POST /api/auth/register`
- `POST /api/auth/logout`
- `GET /api/auth/me`
- `GET /api/ais`
- `POST /api/ai/select`
- `POST /api/ai/create`
- `POST /api/ai/delete`
- `GET /api/settings`
- `POST /api/settings`
- `GET /api/user`
- `POST /chat`
- `POST /api/profile_photo`
- `POST /api/ai_photo`

Authentication uses the server's existing HTTP session cookie, so credentials and AI state remain server-side.
