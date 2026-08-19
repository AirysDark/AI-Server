#pragma once
#include <cstdint>
#include <string>
#include <vector>

namespace gene {
struct Vec2 { float x{}, y{}; };
struct Vec3 { float x{}, y{}, z{}; };
struct Quaternion { float x{}, y{}, z{}, w{1.0f}; };
struct Vertex { Vec3 position{}; Vec3 normal{}; Vec2 uv{}; };
struct Material { std::string name; std::string englishName; int32_t textureIndex{-1}; int32_t sphereTextureIndex{-1}; uint32_t indexCount{}; };
struct Bone { std::string name; std::string englishName; int parent{-1}; Vec3 position{}; Quaternion rotation{}; };
struct Morph { std::string name; std::string englishName; int panel{}; uint8_t type{}; uint32_t offsetCount{}; float weight{}; };

class Model {
public:
    bool loadPmx(const std::string& path);
    bool loadTextures(const std::string& directory);
    bool loaded() const noexcept { return _loaded; }
    float pmxVersion() const noexcept { return _version; }
    uint32_t vertexCount() const noexcept { return static_cast<uint32_t>(_vertices.size()); }
    uint32_t indexCount() const noexcept { return _indexCount; }
    uint32_t materialCount() const noexcept { return static_cast<uint32_t>(_materials.size()); }
    const std::vector<Vertex>& vertices() const noexcept { return _vertices; }
    const std::vector<Material>& materials() const noexcept { return _materials; }
    const std::vector<Bone>& bones() const noexcept { return _bones; }
    const std::vector<Morph>& morphs() const noexcept { return _morphs; }
    const std::vector<uint32_t>& indices() const noexcept { return _indices; }
    const std::vector<std::string>& textures() const noexcept { return _textures; }
    const std::string& textureDirectory() const noexcept { return _textureDirectory; }
private:
    bool _loaded = false;
    float _version = 0.0f;
    uint32_t _indexCount = 0;
    std::string _textureDirectory;
    std::vector<Vertex> _vertices;
    std::vector<uint32_t> _indices;
    std::vector<Material> _materials;
    std::vector<std::string> _textures;
    std::vector<Bone> _bones;
    std::vector<Morph> _morphs;
};
}
