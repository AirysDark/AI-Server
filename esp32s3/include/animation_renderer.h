#pragma once

#include <Arduino.h>
#include <FS.h>
#include <TFT_eSPI.h>
#include "frame_player.h"
#include "bmp_renderer.h"

class AnimationRenderer {
public:
    void begin(TFT_eSPI* display, fs::FS* fs);
    void setCharacterRoot(const String& root);
    bool play(AnimationState state, const String& name, uint16_t fps = 12, bool loop = true);
    void update(uint32_t now = millis());
    bool usingFrames() const { return _frames.active(); }
private:
    TFT_eSPI* _tft = nullptr;
    fs::FS* _fs = nullptr;
    String _root;
    FramePlayer _frames;
    BmpRenderer _bmp;
    String _lastPath;
};
