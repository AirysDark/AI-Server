#pragma once

// AI Server connection configuration.
// Do not commit real credentials.
namespace AiConfig {
constexpr const char* SERVER_BASE_URL = "https://ai-server.ddns.net";
constexpr const char* SERVER_WS_URL   = "wss://ai-server.ddns.net";
constexpr const char* DEVICE_NAME     = "ESP32-S3-AI";
constexpr const char* ACCOUNT_EMAIL   = "YOUR_AI_SERVER_EMAIL";
constexpr const char* ACCOUNT_PASSWORD = "YOUR_AI_SERVER_PASSWORD";
constexpr unsigned long WIFI_TIMEOUT_MS = 20000;
constexpr unsigned long SERVER_TIMEOUT_MS = 15000;
constexpr unsigned long RECONNECT_INTERVAL_MS = 5000;
}
