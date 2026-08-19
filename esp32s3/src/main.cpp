#include <Arduino.h>
#include "pins.h"

void setup() {
    Serial.begin(115200);
    delay(500);

    pinMode(Pins::TFT_CS, OUTPUT);
    pinMode(Pins::TFT_DC, OUTPUT);
    pinMode(Pins::TFT_RESET, OUTPUT);
    pinMode(Pins::TFT_LED, OUTPUT);
    pinMode(Pins::RTP_CS, OUTPUT);
    pinMode(Pins::SD_CS, OUTPUT);

    // Keep all SPI chip-select devices deselected during startup.
    digitalWrite(Pins::TFT_CS, HIGH);
    digitalWrite(Pins::RTP_CS, HIGH);
    digitalWrite(Pins::SD_CS, HIGH);

    // Backlight on for initial hardware test.
    digitalWrite(Pins::TFT_LED, HIGH);

    Serial.println();
    Serial.println("AI-Server ESP32-S3 hardware test");
    Serial.printf("SPI: SCK=%d MOSI=%d MISO=%d\n",
                  Pins::SPI_SCK, Pins::SPI_MOSI, Pins::SPI_MISO);
    Serial.printf("TFT: CS=%d DC=%d RST=%d LED=%d\n",
                  Pins::TFT_CS, Pins::TFT_DC, Pins::TFT_RESET, Pins::TFT_LED);
    Serial.printf("RTP: IRQ=%d CS=%d\n", Pins::RTP_IRQ, Pins::RTP_CS);
    Serial.printf("CTP: INT=%d SDA=%d RST=%d SCL=%d\n",
                  Pins::CTP_INT, Pins::CTP_SDA, Pins::CTP_RST, Pins::CTP_SCL);
    Serial.printf("SD:  CS=%d\n", Pins::SD_CS);
}

void loop() {
    delay(1000);
}
