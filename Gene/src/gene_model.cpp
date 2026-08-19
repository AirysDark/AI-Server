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
    bool f32(float& v) { return read(v); }
    bool index(int32_t& out, uint8_t size, bool signedIndex) {
        if (size == 1) { uint8_t v{}; if (!read(v)) return false; out = signedIndex ? int8_t(v) : v; return true; }
        if (size == 2) { uint16_t v{}; if (!read(v)) return false; out = signedIndex ? int16_t(v) : v; return true; }
        if (size == 4) { int32_t v{}; if (!read(v)) return false; out = v; return true; }
        return false;
    }
    bool text(std::string& out, uint8_t encoding) {
        int32_t bytesCount{};
        if (!i32(bytesCount) || bytesCount < 0 || bytesCount > 64 * 1024 * 1024) return false;
        std::string raw(static_cast<size_t>(bytesCount), '\0');
        if (bytesCount && !bytes(raw.data(), bytesCount)) return false;
        if (encoding == 0) {
            out.clear();
            for (size_t i = 0; i + 1 < raw.size(); i += 2) {
                const uint16_t c = uint8_t(raw[i]) | (uint16_t(uint8_t(raw[i + 1])) << 8);
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

bool skipVertices(Reader& r, uint32_t count, uint8_t uvCount, uint8_t boneIndexSize) {
    for (uint32_t i = 0; i < count; ++i) {
        float f{};
        for (int n = 0; n < 8 + uvCount * 4; ++n) if (!r.f32(f)) return false;
        uint8_t weight{}; if (!r.u8(weight)) return false;
        int32_t idx{};
        switch (weight) {
        case 0: // BDEF1
            if (!r.index(idx, boneIndexSize, false)) return false;
            break;
        case 1: // BDEF2
            if (!r.index(idx, boneIndexSize, false) || !r.index(idx, boneIndexSize, false) || !r.f32(f)) return false;
            break;
        case 2: // BDEF4
        case 4: // QDEF
            for (int n = 0; n < 4; ++n) if (!r.index(idx, boneIndexSize, false)) return false;
            for (int n = 0; n < 4; ++n) if (!r.f32(f)) return false;
            break;
        case 3: // SDEF
            if (!r.index(idx, boneIndexSize, false) || !r.index(idx, boneIndexSize, false)) return false;
            for (int n = 0; n < 9; ++n) if (!r.f32(f)) return false;
            break;
        default:
            return false;
        }
        if (!r.f32(f)) return false; // edge scale
    }
    return true;
}

bool skipMaterials(Reader& r, uint32_t count, uint8_t textureIndexSize) {
    for (uint32_t i = 0; i < count; ++i) {
        std::string s;
        if (!r.text(s, 1) || !r.text(s, 1)) return false;
        float f{};
        for (int n = 0; n < 4; ++n) if (!r.f32(f));
        for (int n = 0; n < 3; ++n) if (!r.f32(f));
        if (!r.f32(f)) return false;
        for (int n = 0; n < 3; ++n) if (!r.f32(f)) return false;
        uint8_t flags{}; if (!r.u8(flags)) return false;
        for (int n = 0; n < 4; ++n) if (!r.f32(f)) return false;
        if (!r.f32(f)) return false;
        int32_t idx{};
        if (!r.index(idx, textureIndexSize, true) || !r.index(idx, textureIndexSize, true)) return false;
        uint8_t toon{}; if (!r.u8(toon)) return false;
        if (toon == 0) { if (!r.index(idx, textureIndexSize, true)) return false; }
        else { uint8_t one{}; if (!r.u8(one)) return false; }
        if (!r.text(s, 1)) return false;
        int32_t faces{}; if (!r.i32(faces) || faces < 0) return false;
    }
    return true;
}
}

bool Model::loadPmx(const std::string& path) {
    _loaded = false;
    _bones.clear(); _morphs.clear();
    _vertexCount = _indexCount = _materialCount = 0;

    std::ifstream in(path, std::ios::binary);
    if (!in) return false;
    char magic[4]{};
    if (!in.read(magic, 4) || std::memcmp(magic, "PMX ", 4) != 0) return false;

    Reader r(in);
    if (!r.f32(_version)) return false;
    uint8_t headerSize{};
    if (!r.u8(headerSize) || headerSize < 8 || headerSize > 8) return false;
    uint8_t header[8]{};
    if (!r.bytes(header, headerSize)) return false;

    const uint8_t encoding = header[0];
    const uint8_t uvCount = header[1];
    const uint8_t vertexIndexSize = header[2];
    const uint8_t textureIndexSize = header[3];
    const uint8_t materialIndexSize = header[4];
    const uint8_t boneIndexSize = header[5];
    const uint8_t morphIndexSize = header[6];
    if ((vertexIndexSize != 1 && vertexIndexSize != 2 && vertexIndexSize != 4) ||
        (textureIndexSize != 1 && textureIndexSize != 2 && textureIndexSize != 4) ||
        (materialIndexSize != 1 && materialIndexSize != 2 && materialIndexSize != 4) ||
        (boneIndexSize != 1 && boneIndexSize != 2 && boneIndexSize != 4) ||
        (morphIndexSize != 1 && morphIndexSize != 2 && morphIndexSize != 4)) return false;

    std::string name, english, comment;
    if (!r.text(name, encoding) || !r.text(english, encoding) ||
        !r.text(comment, encoding) || !r.text(comment, encoding)) return false;

    if (!r.u32(_vertexCount) || !skipVertices(r, _vertexCount, uvCount, boneIndexSize)) return false;
    if (!r.u32(_indexCount)) return false;
    int32_t idx{};
    for (uint32_t i = 0; i < _indexCount; ++i) if (!r.index(idx, vertexIndexSize, false)) return false;

    uint32_t textures{};
    if (!r.u32(textures)) return false;
    for (uint32_t i = 0; i < textures; ++i) if (!r.text(name, encoding)) return false;

    if (!r.u32(_materialCount) || !skipMaterials(r, _materialCount, textureIndexSize)) return false;

    uint32_t morphCount{};
    if (!r.u32(morphCount)) return false;
    for (uint32_t i = 0; i < morphCount; ++i) {
        Morph m{};
        if (!r.text(m.name, encoding) || !r.text(m.englishName, encoding)) return false;
        uint8_t panel{};
        if (!r.u8(panel) || !r.u8(m.type)) return false;
        m.panel = panel;
        if (!r.u32(m.offsetCount)) return false;
        for (uint32_t j = 0; j < m.offsetCount; ++j) {
            float f{};
            switch (m.type) {
            case 0: // group
                if (!r.index(idx, morphIndexSize, false) || !r.f32(m.weight)) return false;
                break;
            case 1: // vertex
                if (!r.index(idx, vertexIndexSize, false)) return false;
                for (int n = 0; n < 3; ++n) if (!r.f32(f)) return false;
                break;
            case 2: // bone
                if (!r.index(idx, boneIndexSize, false)) return false);
                for (int n = 0; n < 3; ++n) if (!r.f32(f)) return false;
                for (int n = 0; n < 4; ++n) if (!r.f32(f)) return false;
                break;
            case 3: // UV
            case 4: // additional UV1
            case 5: // additional UV2
            case 6: // additional UV3
            case 7: // additional UV4
                if (!r.index(idx, vertexIndexSize, false)) return false;
                for (int n = 0; n < 4; ++n) if (!r.f32(f)) return false;
                break;
            case 8: // material
                if (!r.index(idx, materialIndexSize, true)) return false;
                if (!r.f32(f)) return false;
                for (int n = 0; n < 3; ++n) if (!r.f32(f)) return false;
                for (int n = 0; n < 4; ++n) if (!r.f32(f)) return false;
                for (int n = 0; n < 4; ++n) if (!r.f32(f)) return false;
                for (int n = 0; n < 3; ++n) if (!r.f32(f)) return false;
                for (int n = 0; n < 3; ++n) if (!r.f32(f)) return false;
                break;
            default:
                return false;
            }
        }
        _morphs.push_back(std::move(m));
    }

    uint32_t boneCount{};
    if (!r.u32(boneCount)) return false;
    _bones.reserve(boneCount);
    for (uint32_t i = 0; i < boneCount; ++i) {
        Bone b{};
        if (!r.text(b.name, encoding) || !r.text(b.englishName, encoding)) return false;
        if (!r.f32(b.position.x) || !r.f32(b.position.y) || !r.f32(b.position.z)) return false;
        if (!r.index(b.parent, boneIndexSize, true)) return false;
        uint16_t flags{};
        if (!r.read(flags)) return false;
        if (flags & 0x0001) { if (!r.index(idx, boneIndexSize, true)) return false; }
        else { float f{}; if (!r.f32(f) || !r.f32(f) || !r.f32(f)) return false; }
        if (flags & 0x0100 || flags & 0x0200) {
            if (!r.index(idx, boneIndexSize, true)) return false;
            float f{}; if (!r.f32(f)) return false;
        }
        if (flags & 0x0400) { float f{}; for (int n=0;n<3;++n) if(!r.f32(f)) return false; }
        if (flags & 0x0800) { float f{}; for (int n=0;n<3;++n) if(!r.f32(f)) return false; for(int n=0;n<3;++n) if(!r.f32(f)) return false; }
        if (flags & 0x2000) { if (!r.i32(idx)) return false; }
        _bones.push_back(std::move(b));
    }

    _loaded = true;
    return true;
}

bool Model::loadTextures(const std::string& directory) {
    if (!_loaded) return false;
    _textureDirectory = std::filesystem::path(directory).lexically_normal().string();
    return std::filesystem::exists(_textureDirectory) && std::filesystem::is_directory(_textureDirectory);
}
}
