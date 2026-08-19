#pragma once
#include <cstdint>
#include <string>
#include <vector>

namespace gene {
struct Vec3 { float x{}, y{}, z{}; };
struct Quaternion { float x{}, y{}, z{}, w{1.0f}; };
struct Bone { std::string name; std::string englishName; int parent{-1}; Vec3 position{}; Quaternion rotation{}; };
struct Morph { std::string name; std::string englishName; int panel{}; uint8_t type{}; uint32_t offsetCount{}; float weight{}; };

class Model {
public:
    bool loadPmx(const std::string& path);
    bool loadTextures(const std::string& directory);
    bool loaded() const noexcept { return _loaded; }
    float pmxVersion() const noexcept { return _version; }
    uint32_t vertexCount() const noexcept { return _vertexCount; }
    uint32_t indexCount() const noexcept { return _indexCount; }
    uint32_t materialCount() const noexcept { return _materialCount; }
    const std::vector<Bone>& bones() const noexcept { return _bones; }
    const std::vector<Morph>& morphs() const noexcept { return _morphs; }
    const std::string& textureDirectory() const noexcept { return _textureDirectory; }
private:
    bool _loaded = false;
    float _version = 0.0f;
    uint32_t _vertexCount = 0;
    uint32_t _indexCount = 0;
    uint32_t _materialCount = 0;
    std::string _textureDirectory;
    std::vector<Bone> _bones;
    std::vector<Morph> _morphs;
};
}
