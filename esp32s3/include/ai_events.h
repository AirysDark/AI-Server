#pragma once

#include <Arduino.h>
#include "animation.h"

struct AiAnimationCommand {
    String character;
    String animation;
    uint16_t fps = 12;
    uint32_t durationMs = 0;
    bool loop = true;
};

bool parseAnimationCommand(const String& json, AiAnimationCommand& command);
AnimationState animationStateFromName(const String& name);
