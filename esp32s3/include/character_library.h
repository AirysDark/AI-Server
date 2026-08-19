#pragma once

#include <Arduino.h>

struct CharacterDefinition {
    const char* id;
    const char* name;
    const char* renderer;
    uint16_t width;
    uint16_t height;
};

const CharacterDefinition* findCharacter(const String& id);
