#include "server.h"

bool AiServerClient::begin() {
    _lastError = "";
    return true;
}

bool AiServerClient::connectWiFi(const char* ssid, const char* password) {
    WiFi.mode(WIFI_STA);
    WiFi.begin(ssid, password);

    const unsigned long started = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - started < AiConfig::WIFI_TIMEOUT_MS) {
        delay(250);
    }

    if (WiFi.status() != WL_CONNECTED) {
        setError("WiFi connection timeout");
        return false;
    }
    return true;
}

bool AiServerClient::isConnected() const {
    return WiFi.status() == WL_CONNECTED;
}

void AiServerClient::setError(const String& error) {
    _lastError = error;
}

bool AiServerClient::request(const String& method, const String& path, const String& body, String& response) {
    if (!isConnected()) {
        setError("WiFi not connected");
        return false;
    }

    HTTPClient http;
    const String url = String(AiConfig::SERVER_BASE_URL) + path;
    http.setConnectTimeout(AiConfig::SERVER_TIMEOUT_MS);
    http.setTimeout(AiConfig::SERVER_TIMEOUT_MS);

    if (!http.begin(url)) {
        setError("HTTP begin failed");
        return false;
    }

    http.addHeader("Content-Type", "application/json");
    http.addHeader("X-AI-Device", AiConfig::DEVICE_NAME);

    int code = -1;
    if (method == "GET") {
        code = http.GET();
    } else if (method == "POST") {
        code = http.POST(body);
    } else {
        setError("Unsupported HTTP method");
        http.end();
        return false;
    }

    response = http.getString();
    http.end();

    if (code < 200 || code >= 300) {
        setError("HTTP status " + String(code));
        return false;
    }
    return true;
}

bool AiServerClient::serverReachable() {
    String response;
    return request("GET", "/", "", response);
}

bool AiServerClient::loadConversations(String& response) {
    return request("GET", "/api/chats", "", response);
}

bool AiServerClient::loadConversation(const String& conversationId, String& response) {
    return request("GET", "/api/chats/" + conversationId, "", response);
}

bool AiServerClient::sendMessage(const String& message, String& response) {
    JsonDocument doc;
    doc["message"] = message;
    String body;
    serializeJson(doc, body);

    return request("POST", "/api/chat", body, response);
}
