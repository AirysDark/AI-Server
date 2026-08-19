#pragma once

#include <Arduino.h>
#include "animation.h"

struct CharacterConfig {
    String name = "AI";
    String renderer = "cartoon";
    uint16_t width = 320;
    uint16_t height = 480;
};

class CharacterController {
public:
    void begin();
    void update();
    bool loadFromSD(const char* path = "/characters/character.json");
    void setAnimation(const String& name, uint32_t durationMs = 0, bool loop = true);
    const CharacterConfig& config() const { return _config; }
    AnimationEngine& animation() { return _animation; }
private:
    CharacterConfig _config;
    AnimationEngine _animation;
};
