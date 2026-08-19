#include <Arduino.h>
#include "config.h"
#include "pins.h"
#include "server.h"
#include "display.h"
#include "touch.h"
#include "sdcard.h"
#include "chat.h"
#include "character.h"

#ifndef AI_WIFI_SSID
#define AI_WIFI_SSID "YOUR_WIFI_SSID"
#endif
#ifndef AI_WIFI_PASSWORD
#define AI_WIFI_PASSWORD "YOUR_WIFI_PASSWORD"
#endif

AiServerClient server;
AiDisplay display;
AiTouch touch;
AiSdCard sdcard;
ChatManager chat;
CharacterController character;

void setup() {
    Serial.begin(115200);
    delay(500);
    display.begin();
    display.showBoot();
    touch.begin();
    chat.begin();
    character.begin();
    sdcard.begin();
    character.loadFromSD();
    Serial.printf("[CHARACTER] %s renderer=%s\n", character.config().name.c_str(), character.config().renderer.c_str());
    server.begin();
    display.updateCharacter(character.animation().state());
    display.showWiFi("connecting...");
    if (!server.connectWiFi(AI_WIFI_SSID, AI_WIFI_PASSWORD)) { character.setAnimation("offline"); display.updateCharacter(character.animation().state()); display.showError(server.lastError()); return; }
    display.showWiFi(WiFi.localIP().toString());
    display.showServer("checking...");
    if (!server.serverReachable()) { character.setAnimation("offline"); display.updateCharacter(character.animation().state()); display.showServer("offline: " + server.lastError()); return; }
    display.showServer("online");
    if (String(AiConfig::ACCOUNT_EMAIL) != "YOUR_AI_SERVER_EMAIL" && String(AiConfig::ACCOUNT_PASSWORD) != "YOUR_AI_SERVER_PASSWORD") {
        character.setAnimation("thinking");
        display.showServer("logging in...");
        if (!server.login(AiConfig::ACCOUNT_EMAIL, AiConfig::ACCOUNT_PASSWORD)) { character.setAnimation("sad"); display.showError("Login: " + server.lastError()); return; }
        character.setAnimation("happy", 1500, false);
        Serial.println("[AUTH] logged in");
        String chats;
        if (server.loadConversations(chats)) { Serial.println("[CHAT] Conversations loaded:"); Serial.println(chats); }
    } else display.showServer("online - credentials not configured");
}

void loop() {
    touch.update();
    character.update();
    static AnimationState lastState = AnimationState::Offline;
    static uint32_t lastFrame = 0;
    const AnimationState current = character.animation().state();
    const uint32_t frame = millis() / 100;
    if (current != lastState || frame != lastFrame) {
        lastState = current;
        lastFrame = frame;
        display.updateCharacter(current, frame);
    }
    static unsigned long lastCheck = 0;
    if (millis() - lastCheck >= AiConfig::RECONNECT_INTERVAL_MS) {
        lastCheck = millis();
        if (WiFi.status() != WL_CONNECTED) { character.setAnimation("offline"); display.showWiFi("disconnected"); WiFi.reconnect(); }
    }
    delay(10);
}
