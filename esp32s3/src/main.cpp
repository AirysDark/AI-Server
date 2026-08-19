#include <Arduino.h>
#include "config.h"
#include "pins.h"
#include "server.h"
#include "display.h"
#include "touch.h"
#include "sdcard.h"
#include "chat.h"

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

void setup() {
    Serial.begin(115200);
    delay(500);

    display.begin();
    display.showBoot();
    touch.begin();
    chat.begin();

    Serial.println("[BOOT] AI Server ESP32-S3 client");
    Serial.printf("[PIN] SPI SCK=%d MOSI=%d MISO=%d\n", Pins::SPI_SCK, Pins::SPI_MOSI, Pins::SPI_MISO);
    Serial.printf("[PIN] TFT CS=%d DC=%d RESET=%d LED=%d\n", Pins::TFT_CS, Pins::TFT_DC, Pins::TFT_RESET, Pins::TFT_LED);
    Serial.printf("[PIN] RTP CS=%d IRQ=%d\n", Pins::RTP_CS, Pins::RTP_IRQ);
    Serial.printf("[PIN] CTP INT=%d SDA=%d RST=%d SCL=%d\n", Pins::CTP_INT, Pins::CTP_SDA, Pins::CTP_RST, Pins::CTP_SCL);
    Serial.printf("[PIN] SD CS=%d\n", Pins::SD_CS);

    sdcard.begin();
    server.begin();

    display.showWiFi("connecting...");
    if (!server.connectWiFi(AI_WIFI_SSID, AI_WIFI_PASSWORD)) {
        display.showError(server.lastError());
        return;
    }

    display.showWiFi(WiFi.localIP().toString());
    display.showServer("checking...");
    if (!server.serverReachable()) {
        display.showServer("offline: " + server.lastError());
        return;
    }
    display.showServer("online");

    if (String(AiConfig::ACCOUNT_EMAIL) != "YOUR_AI_SERVER_EMAIL" &&
        String(AiConfig::ACCOUNT_PASSWORD) != "YOUR_AI_SERVER_PASSWORD") {
        display.showServer("logging in...");
        if (!server.login(AiConfig::ACCOUNT_EMAIL, AiConfig::ACCOUNT_PASSWORD)) {
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
}

void loop() {
    touch.update();

    static unsigned long lastCheck = 0;
    if (millis() - lastCheck >= AiConfig::RECONNECT_INTERVAL_MS) {
        lastCheck = millis();
        if (WiFi.status() != WL_CONNECTED) {
            display.showWiFi("disconnected");
            WiFi.reconnect();
        }
    }

    delay(10);
}
