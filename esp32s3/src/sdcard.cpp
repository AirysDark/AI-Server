#include "sdcard.h"
#include <SD.h>
#include <SPI.h>
#include "pins.h"

bool AiSdCard::begin() {
    SPI.begin(Pins::SD_SCK, Pins::SD_MISO, Pins::SD_MOSI, Pins::SD_CS);
    _mounted = SD.begin(Pins::SD_CS, SPI);
    if (!_mounted) {
        Serial.println("[SD] mount failed");
        return false;
    }
    Serial.printf("[SD] mounted, size=%llu MB\n", SD.cardSize() / (1024ULL * 1024ULL));
    return true;
}
