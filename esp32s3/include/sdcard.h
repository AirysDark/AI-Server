#pragma once

#include <Arduino.h>

class AiSdCard {
public:
    bool begin();
    bool mounted() const { return _mounted; }

private:
    bool _mounted = false;
};
