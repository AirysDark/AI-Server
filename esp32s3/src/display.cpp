#include "display.h"
#include "pins.h"
#include "cartoon_renderer.h"
#include <SPI.h>

static CartoonRenderer cartoon;

void AiDisplay::begin() {
    pinMode(Pins::TFT_LED, OUTPUT);
    pinMode(Pins::TFT_RESET, OUTPUT);
    pinMode(Pins::TFT_CS, OUTPUT);
    pinMode(Pins::TFT_DC, OUTPUT);
    digitalWrite(Pins::TFT_LED, HIGH);
    digitalWrite(Pins::TFT_CS, HIGH);
    digitalWrite(Pins::TFT_DC, HIGH);
    digitalWrite(Pins::TFT_RESET, HIGH);
    SPI.begin(Pins::SPI_SCK, Pins::SPI_MISO, Pins::SPI_MOSI, Pins::TFT_CS);
    cartoon.begin();
}

void AiDisplay::drawCharacter(AnimationState state, uint32_t frame) {
    cartoon.render(state, frame);
}

void AiDisplay::updateCharacter(AnimationState state, uint32_t frame) {
    drawCharacter(state, frame);
}

void AiDisplay::showBoot() { Serial.println("[DISPLAY] AI Server ESP32-S3 client"); }
void AiDisplay::showWiFi(const String& status) { Serial.println("[DISPLAY] WiFi: " + status); }
void AiDisplay::showServer(const String& status) { Serial.println("[DISPLAY] Server: " + status); }
void AiDisplay::showMessage(const String& sender, const String& message) { Serial.println("[" + sender + "] " + message); }
void AiDisplay::showError(const String& message) { Serial.println("[DISPLAY ERROR] " + message); }
