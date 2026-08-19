#include "display.h"
#include "pins.h"
#include <SPI.h>

namespace {
uint32_t frameCounter = 0;
}

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
}

void AiDisplay::drawCharacter(AnimationState state, uint32_t frame) {
    // Renderer hook: state/frame are now available to a TFT driver.
    // Keep this layer independent of the final ILI9488/ST7796 controller.
    Serial.printf("[CHARACTER] state=%s frame=%lu\n", [&]() -> const char* {
        switch (state) {
            case AnimationState::Idle: return "idle";
            case AnimationState::Thinking: return "thinking";
            case AnimationState::Talking: return "talking";
            case AnimationState::Happy: return "happy";
            case AnimationState::Sad: return "sad";
            case AnimationState::Angry: return "angry";
            case AnimationState::Surprised: return "surprised";
            case AnimationState::Sleepy: return "sleepy";
            case AnimationState::Offline: return "offline";
        }
        return "idle";
    }(), static_cast<unsigned long>(frame));
}

void AiDisplay::updateCharacter(AnimationState state, uint32_t frame) {
    drawCharacter(state, frame);
}

void AiDisplay::showBoot() { Serial.println("[DISPLAY] AI Server ESP32-S3 client"); }
void AiDisplay::showWiFi(const String& status) { Serial.println("[DISPLAY] WiFi: " + status); }
void AiDisplay::showServer(const String& status) { Serial.println("[DISPLAY] Server: " + status); }
void AiDisplay::showMessage(const String& sender, const String& message) { Serial.println("[" + sender + "] " + message); }
void AiDisplay::showError(const String& message) { Serial.println("[DISPLAY ERROR] " + message); }
