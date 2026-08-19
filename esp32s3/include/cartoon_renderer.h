#pragma once

#include <Arduino.h>
#include "animation.h"

class CartoonRenderer {
public:
    void begin();
    void render(AnimationState state, uint32_t frame);
    void setTalkingLevel(uint8_t level);
private:
    uint8_t _talkingLevel = 0;
};
