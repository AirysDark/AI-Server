#pragma once
#include <cstdint>
#include <string>
#include <vector>

namespace gene {
struct Vec3 { float x{}, y{}, z{}; };
struct Quaternion { float x{}, y{}, z{}, w{1.0f}; };
struct Bone { std::string name; int parent{-1}; Vec3 position{}; Quaternion rotation{}; };
struct Morph { std::string name; float weight{}; };

class Model {
public:
    bool loadPmx(const std::string& path);
    bool loadTextures(const std::string& directory);
    bool loaded() const noexcept { return _loaded; }
    const std::vector<Bone>& bones() const noexcept { return _bones; }
    const std::vector<Morph>& morphs() const noexcept { return _morphs; }
private:
    bool _loaded = false;
    std::vector<Bone> _bones;
    std::vector<Morph> _morphs;
};
}
