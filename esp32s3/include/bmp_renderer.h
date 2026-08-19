#pragma once

#include <Arduino.h>
#include <FS.h>
#include <TFT_eSPI.h>

class BmpRenderer {
public:
    void begin(TFT_eSPI* display);
    bool draw(fs::FS& fs, const String& path, int16_t x = 0, int16_t y = 0);
private:
    TFT_eSPI* _tft = nullptr;
    bool read16(File& f, uint16_t& value);
    bool read32(File& f, uint32_t& value);
};
