#include "frame_player.h"

static String frameName(const String& root, const String& animation, uint16_t index) {
    char name[24];
    snprintf(name, sizeof(name), "frame_%04u.bmp", index);
    return root + "/" + animation + "/" + name;
}

void FramePlayer::begin() {
    _active = false;
    _frame = 0;
    _framePath = "";
}

bool FramePlayer::loadClip(fs::FS& fs, const String& root, const String& animation) {
    _fs = &fs;
    _root = root;
    _clip = AnimationClip();
    _clip.directory = animation;
    uint16_t count = 0;
    String path = frameName(root, animation, count);
    while (fs.exists(path)) {
        ++count;
        path = frameName(root, animation, count);
        if (count == 4095) break;
    }
    if (!count) return false;
    _clip.frameCount = count;
    _frame = 0;
    _framePath = frameName(root, animation, 0);
    return true;
}

void FramePlayer::play(AnimationState state, const String& animation, uint16_t fps, bool loop) {
    if (!_fs || !loadClip(*_fs, _root, animation)) {
        _active = false;
        return;
    }
    _state = state;
    _clip.fps = max<uint16_t>(1, fps);
    _clip.loop = loop;
    _lastFrameAt = millis();
    _active = true;
}

void FramePlayer::update(uint32_t now) {
    if (!_active || !_clip.frameCount) return;
    const uint32_t interval = 1000UL / max<uint16_t>(1, _clip.fps);
    if (now - _lastFrameAt < interval) return;
    _lastFrameAt = now;
    ++_frame;
    if (_frame >= _clip.frameCount) {
        if (_clip.loop) _frame = 0;
        else { _frame = _clip.frameCount - 1; _active = false; }
    }
    _framePath = frameName(_root, _clip.directory, _frame);
}
