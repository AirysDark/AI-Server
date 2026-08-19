#include "animation.h"

namespace gene {
void AnimationPlayer::add(const AnimationClip& clip) { _clips[clip.name] = clip; }
bool AnimationPlayer::play(const std::string& name, bool loop) {
    auto it = _clips.find(name);
    if (it == _clips.end()) return false;
    _current = &it->second; _frame = 0; _time = 0.0f; _loop = loop; return true;
}
void AnimationPlayer::update(float deltaSeconds) {
    if (!_current || _current->frameCount == 0 || _current->fps <= 0) return;
    _time += deltaSeconds;
    const float frameDuration = 1.0f / _current->fps;
    while (_time >= frameDuration) {
        _time -= frameDuration;
        ++_frame;
        if (_frame >= _current->frameCount) {
            if (_loop) _frame = 0;
            else _frame = _current->frameCount - 1;
        }
    }
}
const AnimationClip* AnimationPlayer::current() const { return _current; }
}
