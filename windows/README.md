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

## HTTPS certificate requirement

The client intentionally performs normal Windows/.NET TLS certificate validation. It does **not** disable certificate validation or accept arbitrary server certificates.

The production hostname is:

`ai-server.ddns.net`

Therefore the HTTPS certificate served by the production server must include `ai-server.ddns.net` in its certificate names/SANs. A certificate issued only for `webapp-3180826.pythonanywhere.com` is not valid for the custom hostname and will produce a `RemoteCertificateNameMismatch` error in the Windows client.

If that error appears, fix the HTTPS/custom-domain certificate on the PythonAnywhere deployment rather than weakening the Windows client certificate validation.

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

## TLS diagnostics

Connection failures display the exception and nested inner exceptions in the Windows UI. This is intentional so certificate, TLS, DNS, proxy, and other transport problems can be diagnosed without silently bypassing HTTPS security.
