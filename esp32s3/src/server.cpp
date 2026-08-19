#include "server.h"

namespace {
const char* COOKIE_HEADERS[] = {"Set-Cookie"};
}

bool AiServerClient::begin() {
    _lastError = "";
    _sessionCookie = "";
    _selectedAi = "";
    return true;
}

bool AiServerClient::connectWiFi(const char* ssid, const char* password) {
    WiFi.mode(WIFI_STA);
    WiFi.begin(ssid, password);
    const unsigned long started = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - started < AiConfig::WIFI_TIMEOUT_MS) delay(250);
    if (WiFi.status() != WL_CONNECTED) { setError("WiFi connection timeout"); return false; }
    return true;
}

bool AiServerClient::isConnected() const { return WiFi.status() == WL_CONNECTED; }
void AiServerClient::setError(const String& error) { _lastError = error; }

bool AiServerClient::captureCookies(HTTPClient& http) {
    const String header = http.header("Set-Cookie");
    if (!header.length()) return false;
    const int semi = header.indexOf(';');
    const String cookie = semi >= 0 ? header.substring(0, semi) : header;
    if (!cookie.length()) return false;
    const int eq = cookie.indexOf('=');
    if (eq < 1) return false;
    const String name = cookie.substring(0, eq);
    const String prefix = name + "=";
    int existing = _sessionCookie.indexOf(prefix);
    if (existing >= 0) {
        int end = _sessionCookie.indexOf(';', existing);
        if (end < 0) end = _sessionCookie.length();
        _sessionCookie = _sessionCookie.substring(0, existing) + cookie + _sessionCookie.substring(end);
    } else {
        if (_sessionCookie.length()) _sessionCookie += "; ";
        _sessionCookie += cookie;
    }
    return true;
}

bool AiServerClient::request(const String& method, const String& path, const String& body, String& response, bool authenticated) {
    if (!isConnected()) { setError("WiFi not connected"); return false; }
    HTTPClient http;
    http.collectHeaders(COOKIE_HEADERS, 1);
    const String url = String(AiConfig::SERVER_BASE_URL) + path;
    http.setConnectTimeout(AiConfig::SERVER_TIMEOUT_MS);
    http.setTimeout(AiConfig::SERVER_TIMEOUT_MS);
    if (!http.begin(url)) { setError("HTTP begin failed"); return false; }
    http.addHeader("Content-Type", "application/json");
    http.addHeader("X-AI-Device", AiConfig::DEVICE_NAME);
    if (authenticated && _sessionCookie.length()) http.addHeader("Cookie", _sessionCookie);
    int code = method == "GET" ? http.GET() : method == "POST" ? http.POST(body) : -1;
    if (code < 0) setError("HTTP request failed");
    captureCookies(http);
    response = http.getString();
    http.end();
    if (code < 200 || code >= 300) { setError("HTTP status " + String(code)); return false; }
    return true;
}

bool AiServerClient::login(const char* email, const char* password) {
    JsonDocument doc;
    doc["email"] = email;
    doc["password"] = password;
    String body, response;
    serializeJson(doc, body);
    if (!request("POST", "/api/auth/login", body, response, false)) return false;
    JsonDocument result;
    if (deserializeJson(result, response)) { setError("Invalid login response"); return false; }
    if (!result["ok"].as<bool>()) { setError(result["error"].as<String>()); return false; }
    JsonArray ais = result["ais"].as<JsonArray>();
    if (ais.isNull() || !ais.size()) { setError("Login returned no AI"); return false; }
    _selectedAi = ais[0].as<String>();
    return selectAi(_selectedAi);
}

bool AiServerClient::selectAi(const String& aiId) {
    JsonDocument doc;
    doc["ai_id"] = aiId;
    String body, response;
    serializeJson(doc, body);
    if (!request("POST", "/api/ai/select", body, response)) return false;
    _selectedAi = aiId;
    return true;
}

bool AiServerClient::serverReachable() {
    String response;
    return request("GET", "/api/health", "", response, false);
}

bool AiServerClient::loadConversations(String& response) {
    return request("GET", "/api/chats", "", response);
}

bool AiServerClient::loadConversation(const String& conversationId, String& response) {
    JsonDocument doc;
    doc["conversation_id"] = conversationId;
    String body;
    serializeJson(doc, body);
    return request("POST", "/api/chats/open", body, response);
}

bool AiServerClient::sendMessage(const String& message, String& response) {
    JsonDocument doc;
    doc["message"] = message;
    String body;
    serializeJson(doc, body);
    return request("POST", "/chat", body, response);
}
