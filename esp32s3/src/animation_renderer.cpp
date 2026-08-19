#include "animation_renderer.h"

void AnimationRenderer::begin(TFT_eSPI* display, fs::FS* fs) {
    _tft = display;
    _fs = fs;
    _frames.begin();
    _bmp.begin(display);
}

void AnimationRenderer::setCharacterRoot(const String& root) { _root = root; }

bool AnimationRenderer::play(AnimationState state, const String& name, uint16_t fps, bool loop) {
    if (!_fs || _root.isEmpty()) return false;
    if (!_frames.loadClip(*_fs, _root, name)) return false;
    _frames.play(state, name, fps, loop);
    _lastPath = "";
    return true;
}

void AnimationRenderer::update(uint32_t now) {
    _frames.update(now);
    if (!_frames.active() && _lastPath.isEmpty()) return;
    const String path = _frames.framePath();
    if (!path.isEmpty() && path != _lastPath) {
        _bmp.draw(*_fs, path);
        _lastPath = path;
    }
}
