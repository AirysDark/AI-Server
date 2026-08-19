#pragma once
#include <cstdint>
#include <string>
#include <vector>

namespace gene {
struct Vec2 { float x{}, y{}; };
struct Vec3 { float x{}, y{}, z{}; };
struct Quaternion { float x{}, y{}, z{}, w{1.0f}; };

struct Vertex {
    Vec3 position{};
    Vec3 normal{};
    Vec2 uv{};
    uint8_t weightType{};
    int32_t boneIndices[4]{-1, -1, -1, -1};
    float boneWeights[4]{1.0f, 0.0f, 0.0f, 0.0f};
};

struct Material {
    std::string name;
    std::string englishName;
    float diffuse[4]{1.0f, 1.0f, 1.0f, 1.0f};
    float specular[3]{0.0f, 0.0f, 0.0f};
    float ambient[3]{0.0f, 0.0f, 0.0f};
    uint8_t flags{};
    float edgeColor[4]{0.0f, 0.0f, 0.0f, 1.0f};
    float edgeSize{};
    int32_t textureIndex{-1};
    int32_t sphereTextureIndex{-1};
    uint8_t sphereMode{};
    uint8_t toonFlag{};
    uint8_t toonTextureIndex{};
    uint32_t indexCount{};
};

struct Bone {
    std::string name;
    std::string englishName;
    int parent{-1};
    Vec3 position{};
    Quaternion rotation{};
};

enum class MorphType : uint8_t { Group=0, Vertex=1, Bone=2, UV=3, UV1=4, UV2=5, UV3=6, UV4=7, Material=8, Flip=9, Impulse=10 };

struct MorphOffset {
    MorphType type{};
    int32_t index{-1};
    Vec3 position{};
    Quaternion rotation{};
    float weight{};
    float uv[4]{};
    uint8_t operation{};
    float diffuse[4]{};
    float specular[3]{};
    float shininess{};
    float ambient[3]{};
    float edgeColor[4]{};
    float edgeSize{};
    float textureFactor[4]{};
    float sphereTextureFactor[4]{};
    float toonTextureFactor[4]{};
    uint8_t localFlag{};
    Vec3 velocity{};
    Vec3 torque{};
};

struct Morph {
    std::string name;
    std::string englishName;
    uint8_t panel{};
    MorphType type{};
    uint32_t offsetCount{};
    std::vector<MorphOffset> offsets;
    float value{};
};

class Model {
public:
    bool loadPmx(const std::string& path);
    bool loadTextures(const std::string& directory) { _textureDirectory = directory; return true; }
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
    const std::string& error() const noexcept { return _error; }
    bool setMorphWeight(const std::string& name, float value);
    void clearMorphWeights();
    void updateMorphs();
private:
    bool fail(const std::string& message);
    void applyMorph(size_t index, float weight, std::vector<float>& weights, std::vector<uint8_t>& visiting);
    bool _loaded = false;
    float _version = 0.0f;
    uint32_t _indexCount = 0;
    std::string _textureDirectory;
    std::string _error;
    std::vector<Vertex> _vertices;
    std::vector<Vertex> _baseVertices;
    std::vector<uint32_t> _indices;
    std::vector<Material> _materials;
    std::vector<Material> _baseMaterials;
    std::vector<std::string> _textures;
    std::vector<Bone> _bones;
    std::vector<Morph> _morphs;
};
}
