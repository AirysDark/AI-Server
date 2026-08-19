#pragma once

#include <Arduino.h>
#include "animation.h"

class AiDisplay {
public:
    void begin();
    void updateCharacter(AnimationState state, uint32_t frame = 0);
    void showBoot();
    void showWiFi(const String& status);
    void showServer(const String& status);
    void showMessage(const String& sender, const String& message);
    void showError(const String& message);
private:
    void drawCharacter(AnimationState state, uint32_t frame);
};
