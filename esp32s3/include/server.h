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
    bool isConnected() const;
    bool serverReachable();
    bool sendMessage(const String& message, String& response);
    bool loadConversations(String& response);
    bool loadConversation(const String& conversationId, String& response);
    const String& lastError() const { return _lastError; }

private:
    bool request(const String& method, const String& path, const String& body, String& response);
    void setError(const String& error);
    String _lastError;
};
