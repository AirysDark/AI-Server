#pragma once

#include <Arduino.h>

struct CharacterPose {
    int16_t eyeOffsetX;
    int16_t eyeOffsetY;
    int16_t mouthWidth;
    int16_t mouthHeight;
    int16_t bodyBob;
    uint8_t blink;
};

CharacterPose characterPose(const char* animation, uint32_t frame);
