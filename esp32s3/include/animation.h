#pragma once

#include <Arduino.h>

enum class AnimationState : uint8_t { Idle, Thinking, Talking, Happy, Sad, Angry, Surprised, Sleepy, Offline };

class AnimationEngine {
public:
    void begin();
    void update(uint32_t now = millis());
    void setState(AnimationState state, uint32_t durationMs = 0, bool loop = true);
    AnimationState state() const { return _state; }
    bool running() const { return _running; }
    const char* stateName() const;
private:
    AnimationState _state = AnimationState::Idle;
    uint32_t _started = 0;
    uint32_t _duration = 0;
    bool _loop = true;
    bool _running = false;
};
