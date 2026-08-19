#pragma once
#include <cstdint>
#include <string>
#include <unordered_map>

namespace gene {
struct AnimationClip { std::string name; uint32_t frameCount{}; float fps{30.0f}; };
class AnimationPlayer {
public:
    void add(const AnimationClip& clip);
    bool play(const std::string& name, bool loop = true);
    void update(float deltaSeconds);
    const AnimationClip* current() const;
    uint32_t frame() const noexcept { return _frame; }
private:
    std::unordered_map<std::string, AnimationClip> _clips;
    const AnimationClip* _current = nullptr;
    uint32_t _frame = 0;
    float _time = 0.0f;
    bool _loop = true;
};
}
