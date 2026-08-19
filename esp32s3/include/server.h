#pragma once

#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include "config.h"

class AiServerClient {
public:
    bool begin();
    bool connectWiFi(const char* ssid, const char* password);
    bool login(const char* email, const char* password);
    bool selectAi(const String& aiId);
    bool isConnected() const;
    bool isAuthenticated() const { return _sessionCookie.length() > 0; }
    bool serverReachable();
    bool sendMessage(const String& message, String& response);
    bool loadConversations(String& response);
    bool loadConversation(const String& conversationId, String& response);
    const String& lastError() const { return _lastError; }
    const String& selectedAi() const { return _selectedAi; }

private:
    bool request(const String& method, const String& path, const String& body, String& response, bool authenticated = true);
    bool captureCookies(HTTPClient& http);
    void setError(const String& error);
    String _lastError;
    String _sessionCookie;
    String _selectedAi;
};
