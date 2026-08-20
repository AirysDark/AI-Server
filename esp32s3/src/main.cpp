#include <Arduino.h>
#include "config.h"
#include "pins.h"
#include "server.h"
#include "display.h"
#include "touch.h"
#include "sdcard.h"
#include "chat.h"
#include "character.h"
#include "character_package.h"

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
CharacterPackageManager packages;

// The ESP32-S3 is a display endpoint. It stays idle here until the
// network renderer starts sending actual rendered AI frames.
static bool waitingForRenderedAi = false;

void setup() {
    Serial.begin(115200);
    delay(500);
    display.begin();
    display.showBoot();
    touch.begin();
    chat.begin();
    character.begin();
    sdcard.begin();
    packages.begin();
    if (sdcard.mounted() && packages.scan()) {
        Serial.printf("[CHARACTER] loaded %s (%s) from %s\n", packages.active().name.c_str(), packages.active().renderer.c_str(), packages.active().root.c_str());
    }
    character.loadFromSD();
    server.begin();

    display.showWiFi("connecting...");
    if (!server.connectWiFi(AI_WIFI_SSID, AI_WIFI_PASSWORD)) {
        character.setAnimation("offline");
        display.updateCharacter(character.animation().state());
        display.showError(server.lastError());
        return;
    }

    display.showWiFi(WiFi.localIP().toString());
    display.showServer("checking...");
    if (!server.serverReachable()) {
        character.setAnimation("offline");
        display.updateCharacter(character.animation().state());
        display.showServer("offline: " + server.lastError());
        return;
    }

    display.showServer("online");

    if (String(AiConfig::ACCOUNT_EMAIL) != "YOUR_AI_SERVER_EMAIL" &&
        String(AiConfig::ACCOUNT_PASSWORD) != "YOUR_AI_SERVER_PASSWORD") {
        character.setAnimation("thinking");
        display.showServer("logging in...");
        if (!server.login(AiConfig::ACCOUNT_EMAIL, AiConfig::ACCOUNT_PASSWORD)) {
            character.setAnimation("sad");
            display.updateCharacter(character.animation().state());
            display.showError("Login: " + server.lastError());
            return;
        }

        Serial.println("[AUTH] logged in");
        String chats;
        if (server.loadConversations(chats)) {
            Serial.println("[CHAT] Conversations loaded:");
            Serial.println(chats);
        }
    } else {
        display.showServer("online - credentials not configured");
    }

    // Initialization is complete. Do not draw the old placeholder cartoon.
    // The next stage is the rendered AI frame transport.
    waitingForRenderedAi = true;
    display.showWaitingForRender();
}

void loop() {
    touch.update();

    static unsigned long lastCheck = 0;
    if (millis() - lastCheck >= AiConfig::RECONNECT_INTERVAL_MS) {
        lastCheck = millis();
        if (WiFi.status() != WL_CONNECTED) {
            waitingForRenderedAi = false;
            display.showWiFi("disconnected");
            WiFi.reconnect();
        } else if (!waitingForRenderedAi) {
            display.showWiFi(WiFi.localIP().toString());
            display.showServer("online");
            waitingForRenderedAi = true;
            display.showWaitingForRender();
        }
    }

    // Deliberately no local animation loop here. The ESP32-S3 is now a
    // receiver/display target for the Python/Gene rendered AI stream.
    delay(10);
}
