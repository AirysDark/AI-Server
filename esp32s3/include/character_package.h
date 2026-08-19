#pragma once

#include <Arduino.h>

struct CharacterPackage {
    String id;
    String name;
    String renderer;
    uint16_t width = 320;
    uint16_t height = 480;
    String root;
};

class CharacterPackageManager {
public:
    bool begin();
    bool load(const String& root);
    bool scan();
    const CharacterPackage& active() const { return _active; }
private:
    CharacterPackage _active;
};
