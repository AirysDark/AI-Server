#pragma once

#include <Arduino.h>
#include <FS.h>
#include "animation.h"

struct AnimationClip {
    String directory;
    uint16_t frameCount = 0;
    uint16_t fps = 12;
    bool loop = true;
};

class FramePlayer {
public:
    void begin();
    bool loadClip(fs::FS& fs, const String& root, const String& animation);
    void play(AnimationState state, const String& animation, uint16_t fps = 12, bool loop = true);
    void update(uint32_t now = millis());
    const String& framePath() const { return _framePath; }
    uint16_t frame() const { return _frame; }
    bool active() const { return _active; }
private:
    fs::FS* _fs = nullptr;
    AnimationClip _clip;
    AnimationState _state = AnimationState::Idle;
    String _root;
    String _framePath;
    uint16_t _frame = 0;
    uint32_t _lastFrameAt = 0;
    bool _active = false;
};
