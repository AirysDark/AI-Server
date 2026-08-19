# AI Server Windows Companion

A small Windows desktop companion for AI Server.

## UI

- Compact rectangular chat panel anchored to the lower-left corner.
- Always-on-top, borderless window.
- Normal text input and send button.
- Conversation history displayed in the panel.
- AI messages appear immediately when received.
- A floating circular AI avatar appears above/near the panel when the AI proactively wants the user's attention.
- Clicking the floating avatar opens/focuses the chat panel.
- The companion can be minimized to the notification area without closing the connection.

## Behaviour

The app connects to the configured AI Server account and uses the currently selected AI. It should consume the same AI identity/settings as the web application rather than creating a second AI configuration.

The server should be responsible for deciding when an AI has a proactive message. The desktop client displays that event as a floating avatar notification and shows the text in the chat panel.

## Suggested implementation

Use WinUI 3 or WPF. The existing Windows project is the natural home for this client.

The client should support:

- configurable server URL
- authenticated session/cookie or token
- selected AI identity
- reconnect on network loss
- live incoming messages without refresh
- typing indicator
- notification/floating avatar state
- drag-to-reposition panel if desired
- start with Windows option
- close/minimize to tray

Keep API credentials out of source control and Windows app binaries. The server remains the authority for AI API tokens and provider configuration.