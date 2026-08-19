#include "display.h"
#include "pins.h"

void AiDisplay::begin() {
    pinMode(Pins::TFT_LED, OUTPUT);
    digitalWrite(Pins::TFT_LED, HIGH);
}

void AiDisplay::showBoot() {
    Serial.println("[DISPLAY] AI Server ESP32-S3 client");
}

void AiDisplay::showWiFi(const String& status) {
    Serial.println("[DISPLAY] WiFi: " + status);
}

void AiDisplay::showServer(const String& status) {
    Serial.println("[DISPLAY] Server: " + status);
}

void AiDisplay::showMessage(const String& sender, const String& message) {
    Serial.println("[" + sender + "] " + message);
}

void AiDisplay::showError(const String& message) {
    Serial.println("[DISPLAY ERROR] " + message);
}
