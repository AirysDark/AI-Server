#include "display.h"
#include "pins.h"
#include "cartoon_renderer.h"
#include <TFT_eSPI.h>
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

void AiDisplay::showWaitingForRender(const String& renderer) {
    // Keep the hardware in a deterministic READY state until the
    // network renderer starts supplying actual AI frames.
    static TFT_eSPI waitingTft;
    waitingTft.init();
    waitingTft.setRotation(0);
    waitingTft.fillScreen(TFT_BLACK);
    waitingTft.setTextDatum(MC_DATUM);
    waitingTft.setTextColor(TFT_WHITE, TFT_BLACK);
    waitingTft.drawString("AI DISPLAY", waitingTft.width() / 2, waitingTft.height() / 2 - 45, 4);
    waitingTft.setTextColor(TFT_CYAN, TFT_BLACK);
    waitingTft.drawString("WAITING FOR RENDERED AI", waitingTft.width() / 2, waitingTft.height() / 2, 2);
    waitingTft.setTextColor(TFT_DARKGREY, TFT_BLACK);
    waitingTft.drawString(renderer, waitingTft.width() / 2, waitingTft.height() / 2 + 35, 1);
    Serial.println("[DISPLAY] READY - waiting for rendered AI");
}

void AiDisplay::showBoot() { Serial.println("[DISPLAY] AI Server ESP32-S3 client"); }
void AiDisplay::showWiFi(const String& status) { Serial.println("[DISPLAY] WiFi: " + status); }
void AiDisplay::showServer(const String& status) { Serial.println("[DISPLAY] Server: " + status); }
void AiDisplay::showMessage(const String& sender, const String& message) { Serial.println("[" + sender + "] " + message); }
void AiDisplay::showError(const String& message) { Serial.println("[DISPLAY ERROR] " + message); }
