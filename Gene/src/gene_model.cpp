#include "gene_model.h"
#include <filesystem>
#include <fstream>
#include <cstring>
#include <utility>

namespace gene {
namespace {
class Reader {
public:
    explicit Reader(std::istream& in) : _in(in) {}
    template<class T> bool read(T& v) { _in.read(reinterpret_cast<char*>(&v), sizeof(T)); return bool(_in); }
    bool bytes(void* p, std::streamsize n) { _in.read(reinterpret_cast<char*>(p), n); return bool(_in); }
    bool u8(uint8_t& v) { return read(v); }
    bool i32(int32_t& v) { return read(v); }
    bool u32(uint32_t& v) { return read(v); }
    bool u16(uint16_t& v) { return read(v); }
    bool f32(float& v) { return read(v); }
    bool index(int32_t& out, uint8_t size, bool signedIndex) {
        if (size == 1) { uint8_t v{}; if (!read(v)) return false; out = signedIndex ? int8_t(v) : int32_t(v); return true; }
        if (size == 2) { uint16_t v{}; if (!read(v)) return false; out = signedIndex ? int16_t(v) : int32_t(v); return true; }
        if (size == 4) { int32_t v{}; if (!read(v)) return false; out = v; return true; }
        return false;
    }
    bool vec3(float& x, float& y, float& z) { return f32(x) && f32(y) && f32(z); }
    bool text(std::string& out, uint8_t encoding) {
        int32_t bytesCount{};
        if (!i32(bytesCount) || bytesCount < 0 || bytesCount > 64 * 1024 * 1024) return false;
        std::string raw(static_cast<size_t>(bytesCount), '\0');
        if (bytesCount && !bytes(raw.data(), bytesCount)) return false;
        if (encoding == 0) {
            out.clear();
            for (size_t i = 0; i + 1 < raw.size(); i += 2) {
                uint16_t c = uint8_t(raw[i]) | (uint16_t(uint8_t(raw[i + 1])) << 8);
                out.push_back(c < 128 ? char(c) : '?');
            }
        } else {
            out = std::move(raw);
        }
        return true;
    }
private:
    std::istream& _in;
};
}

bool Model::loadPmx(const std::string& path)
{
    _loaded = false;
    _vertices.clear();
    _indices.clear();
    _materials.clear();
    _textures.clear();
    _bones.clear();
    _morphs.clear();
    _indexCount = 0;

    std::ifstream in(path, std::ios::binary);
    if (!in) return false;

    char magic[4]{};
    if (!in.read(magic, 4) || std::memcmp(magic, "PMX ", 4) != 0) return false;

    Reader r(in);
    uint8_t headerSize{};
    if (!r.f32(_version) || !r.u8(headerSize) || headerSize != 8) return false;

    uint8_t header[8]{};
    if (!r.bytes(header, headerSize)) return false;

    const uint8_t encoding = header[0];
    const uint8_t uvCount = header[1];
    const uint8_t vertexIndexSize = header[2];
    const uint8_t textureIndexSize = header[3];
    const uint8_t materialIndexSize = header[4];
    const uint8_t boneIndexSize = header[5];
    const uint8_t morphIndexSize = header[6];

    auto validIndex = [](uint8_t s) { return s == 1 || s == 2 || s == 4; };
    if (!validIndex(vertexIndexSize) || !validIndex(textureIndexSize) ||
        !validIndex(materialIndexSize) || !validIndex(boneIndexSize) ||
        !validIndex(morphIndexSize)) return false;

    std::string name, english, comment, englishComment;
    if (!r.text(name, encoding) || !r.text(english, encoding) ||
        !r.text(comment, encoding) || !r.text(englishComment, encoding)) return false;

    uint32_t vertexCount{};
    if (!r.u32(vertexCount) || vertexCount > 10000000) return false;
    _vertices.resize(vertexCount);

    for (auto& v : _vertices)
    {
        if (!r.vec3(v.position.x, v.position.y, v.position.z) ||
            !r.vec3(v.normal.x, v.normal.y, v.normal.z) ||
            !r.f32(v.uv.x) || !r.f32(v.uv.y)) return false;

        float f{};
        for (uint8_t n = 0; n < uvCount; ++n)
            for (int c = 0; c < 4; ++c)
                if (!r.f32(f)) return false;

        uint8_t weight{};
        if (!r.u8(weight)) return false;
        int32_t idx{};

        switch (weight)
        {
        case 0: // BDEF1
            if (!r.index(idx, boneIndexSize, true)) return false;
            break;
        case 1: // BDEF2
            if (!r.index(idx, boneIndexSize, true) ||
                !r.index(idx, boneIndexSize, true) || !r.f32(f)) return false;
            break;
        case 2: // BDEF4
        case 4: // QDEF
            for (int n = 0; n < 4; ++n)
                if (!r.index(idx, boneIndexSize, true)) return false;
            for (int n = 0; n < 4; ++n)
                if (!r.f32(f)) return false;
            break;
        case 3: // SDEF
            if (!r.index(idx, boneIndexSize, true) || !r.index(idx, boneIndexSize, true)) return false;
            for (int n = 0; n < 9; ++n)
                if (!r.f32(f)) return false;
            break;
        default:
            return false;
        }

        // Edge scale
        if (!r.f32(f)) return false;
    }

    if (!r.u32(_indexCount) || _indexCount > 30000000) return false;
    _indices.resize(_indexCount);
    for (auto& value : _indices)
    {
        int32_t idx{};
        if (!r.index(idx, vertexIndexSize, false) || idx < 0) return false;
        value = static_cast<uint32_t>(idx);
    }

    uint32_t textureCount{};
    if (!r.u32(textureCount) || textureCount > 1000000) return false;
    _textures.resize(textureCount);
    for (auto& texture : _textures)
        if (!r.text(texture, encoding)) return false;

    uint32_t materialCount{};
    if (!r.u32(materialCount) || materialCount > 1000000) return false;
    _materials.reserve(materialCount);

    for (uint32_t i = 0; i < materialCount; ++i)
    {
        Material m{};
        if (!r.text(m.name, encoding) || !r.text(m.englishName, encoding)) return false;

        float f{};
        for (int n = 0; n < 4; ++n) if (!r.f32(f)) return false; // diffuse
        for (int n = 0; n < 3; ++n) if (!r.f32(f)) return false; // specular
        if (!r.f32(f)) return false; // specular power
        for (int n = 0; n < 3; ++n) if (!r.f32(f)) return false; // ambient

        uint8_t flags{};
        if (!r.u8(flags)) return false;
        for (int n = 0; n < 4; ++n) if (!r.f32(f)) return false; // edge colour
        if (!r.f32(f)) return false; // edge size

        int32_t idx{};
        if (!r.index(idx, textureIndexSize, true)) return false;
        m.textureIndex = idx;
        if (!r.index(idx, textureIndexSize, true)) return false;
        m.sphereTextureIndex = idx;

        uint8_t sphereMode{};
        if (!r.u8(sphereMode)) return false;

        uint8_t toonFlag{};
        if (!r.u8(toonFlag)) return false;
        if (toonFlag == 0)
        {
            if (!r.index(idx, textureIndexSize, true)) return false;
        }
        else
        {
            uint8_t toonTexture{};
            if (!r.u8(toonTexture)) return false;
        }

        if (!r.text(m.name, encoding)) return false; // memo

        int32_t faces{};
        if (!r.i32(faces) || faces < 0) return false;
        m.indexCount = static_cast<uint32_t>(faces);
        _materials.push_back(std::move(m));
    }

    uint32_t morphCount{};
    if (!r.u32(morphCount) || morphCount > 1000000) return false;

    for (uint32_t i = 0; i < morphCount; ++i)
    {
        Morph m{};
        if (!r.text(m.name, encoding) || !r.text(m.englishName, encoding)) return false;

        uint8_t panel{}, type{};
        if (!r.u8(panel) || !r.u8(type) || !r.u32(m.offsetCount)) return false;
        m.panel = panel;
        m.type = type;

        for (uint32_t j = 0; j < m.offsetCount; ++j)
        {
            float f{};
            int32_t idx{};

            if (type == 0) // group
            {
                if (!r.index(idx, morphIndexSize, true) || !r.f32(m.weight)) return false;
            }
            else if (type == 1) // vertex
            {
                if (!r.index(idx, vertexIndexSize, true)) return false;
                for (int n = 0; n < 3; ++n) if (!r.f32(f)) return false;
            }
            else if (type == 2) // bone
            {
                if (!r.index(idx, boneIndexSize, true)) return false;
                for (int n = 0; n < 7; ++n) if (!r.f32(f)) return false;
            }
            else if (type >= 3 && type <= 7) // UV / additional UV
            {
                if (!r.index(idx, vertexIndexSize, true)) return false;
                for (int n = 0; n < 4; ++n) if (!r.f32(f)) return false;
            }
            else if (type == 8) // material
            {
                if (!r.index(idx, materialIndexSize, true)) return false;
                for (int n = 0; n < 16; ++n) if (!r.f32(f)) return false;
                if (!r.index(idx, textureIndexSize, true) || !r.index(idx, textureIndexSize, true)) return false;
                uint8_t toon{};
                if (!r.u8(toon)) return false;
                if (toon == 0)
                {
                    if (!r.index(idx, textureIndexSize, true)) return false;
                }
                else
                {
                    uint8_t one{};
                    if (!r.u8(one)) return false;
                }
            }
            else return false;
        }
        _morphs.push_back(std::move(m));
    }

    uint32_t boneCount{};
    if (!r.u32(boneCount) || boneCount > 1000000) return false;
    _bones.reserve(boneCount);

    for (uint32_t i = 0; i < boneCount; ++i)
    {
        Bone b{};
        if (!r.text(b.name, encoding) || !r.text(b.englishName, encoding) ||
            !r.vec3(b.position.x, b.position.y, b.position.z) ||
            !r.index(b.parent, boneIndexSize, true)) return false;

        uint16_t flags{};
        if (!r.u16(flags)) return false;

        int32_t idx{};
        float f{};

        // Tail position/index.
        if (flags & 0x0001)
        {
            if (!r.index(idx, boneIndexSize, true)) return false;
        }
        else
        {
            for (int n = 0; n < 3; ++n) if (!r.f32(f)) return false;
        }

        // Inherit rotation/translation.
        if (flags & 0x0100 || flags & 0x0200)
        {
            if (!r.index(idx, boneIndexSize, true) || !r.f32(f)) return false;
        }

        // Fixed axis.
        if (flags & 0x0400)
            for (int n = 0; n < 3; ++n) if (!r.f32(f)) return false;

        // Local axis: X and Z vectors.
        if (flags & 0x0800)
            for (int n = 0; n < 6; ++n) if (!r.f32(f)) return false;

        // External parent key.
        if (flags & 0x2000)
            if (!r.i32(idx)) return false;

        // IK data. This was the missing section that caused the PMX reader
        // to lose alignment when Gené's model reached its IK bones.
        if (flags & 0x0020)
        {
            if (!r.index(idx, boneIndexSize, true)) return false; // target
            uint32_t loopCount{};
            if (!r.u32(loopCount)) return false;
            if (!r.f32(f)) return false; // loop angle limit

            if (loopCount > 100000) return false;
            for (uint32_t k = 0; k < loopCount; ++k)
            {
                if (!r.index(idx, boneIndexSize, true)) return false;
                uint8_t hasLimit{};
                if (!r.u8(hasLimit)) return false;
                if (hasLimit)
                {
                    for (int n = 0; n < 6; ++n)
                        if (!r.f32(f)) return false;
                }
            }
        }

        _bones.push_back(std::move(b));
    }

    _loaded = true;
    return true;
}

bool Model::loadTextures(const std::string& directory)
{
    if (!_loaded) return false;
    _textureDirectory = std::filesystem::path(directory).lexically_normal().string();
    return std::filesystem::exists(_textureDirectory) && std::filesystem::is_directory(_textureDirectory);
}
}
