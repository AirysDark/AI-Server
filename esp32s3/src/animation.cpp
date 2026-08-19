#include "animation.h"

void AnimationEngine::begin() {
    _state = AnimationState::Idle;
    _started = millis();
    _duration = 0;
    _loop = true;
    _running = true;
}

void AnimationEngine::setState(AnimationState state, uint32_t durationMs, bool loop) {
    _state = state;
    _started = millis();
    _duration = durationMs;
    _loop = loop;
    _running = true;
}

void AnimationEngine::update(uint32_t now) {
    if (!_running || !_duration || _loop) return;
    if (now - _started >= _duration) {
        _running = false;
        _state = AnimationState::Idle;
        _started = now;
    }
}

const char* AnimationEngine::stateName() const {
    switch (_state) {
        case AnimationState::Idle: return "idle";
        case AnimationState::Thinking: return "thinking";
        case AnimationState::Talking: return "talking";
        case AnimationState::Happy: return "happy";
        case AnimationState::Sad: return "sad";
        case AnimationState::Angry: return "angry";
        case AnimationState::Surprised: return "surprised";
        case AnimationState::Sleepy: return "sleepy";
        case AnimationState::Offline: return "offline";
    }
    return "idle";
}
