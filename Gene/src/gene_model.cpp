#include "gene_model.h"
#include <fstream>
#include <cstring>
#include <utility>
#include <vector>
#include <string>

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
        int32_t byteCount{};
        if (!i32(byteCount) || byteCount < 0 || byteCount > 64 * 1024 * 1024) return false;
        std::string raw(static_cast<size_t>(byteCount), '\0');
        if (byteCount && !bytes(raw.data(), byteCount)) return false;
        if (encoding == 0) {
            out.clear();
            for (size_t i = 0; i + 1 < raw.size(); i += 2) {
                const uint16_t c = uint8_t(raw[i]) | (uint16_t(uint8_t(raw[i + 1])) << 8);
                out.push_back(c < 128 && !(c >= 0xD800 && c <= 0xDFFF) ? char(c) : '?');
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

bool Model::fail(const std::string& message) { _loaded = false; _error = message; return false; }

bool Model::loadPmx(const std::string& path)
{
    _loaded = false;
    _error.clear();
    _vertices.clear();
    _indices.clear();
    _materials.clear();
    _textures.clear();
    _bones.clear();
    _morphs.clear();
    _indexCount = 0;

    std::ifstream in(path, std::ios::binary);
    if (!in) return fail("cannot open file");
    Reader r(in);

    char magic[4]{};
    if (!in.read(magic, 4) || std::memcmp(magic, "PMX ", 4) != 0)
        return fail("invalid PMX signature");

    uint8_t headerSize{};
    if (!r.f32(_version) || !r.u8(headerSize)) return fail("truncated PMX header");
    if (headerSize != 8) return fail("invalid PMX header size: " + std::to_string(headerSize));

    uint8_t header[8]{};
    if (!r.bytes(header, 8)) return fail("truncated PMX header data");

    const uint8_t encoding = header[0];
    const uint8_t uvCount = header[1];
    const uint8_t vertexIndexSize = header[2];
    const uint8_t textureIndexSize = header[3];
    const uint8_t materialIndexSize = header[4];
    const uint8_t boneIndexSize = header[5];
    const uint8_t morphIndexSize = header[6];
    const uint8_t rigidBodyIndexSize = header[7];

    auto validIndex = [](uint8_t s) { return s == 1 || s == 2 || s == 4; };
    if (encoding > 1) return fail("unsupported text encoding " + std::to_string(encoding));
    if (uvCount > 4) return fail("invalid additional UV count " + std::to_string(uvCount));
    if (!validIndex(vertexIndexSize) || !validIndex(textureIndexSize) ||
        !validIndex(materialIndexSize) || !validIndex(boneIndexSize) ||
        !validIndex(morphIndexSize) || !validIndex(rigidBodyIndexSize))
        return fail("invalid PMX index size in header");

    std::string name, english, comment, englishComment;
    if (!r.text(name, encoding) || !r.text(english, encoding) ||
        !r.text(comment, encoding) || !r.text(englishComment, encoding))
        return fail("failed reading model strings");

    // ---------------------------------------------------------------------
    // Vertices
    // ---------------------------------------------------------------------
    uint32_t vertexCount{};
    if (!r.u32(vertexCount) || vertexCount > 10000000) return fail("invalid vertex count");
    _vertices.resize(vertexCount);

    for (uint32_t vi = 0; vi < vertexCount; ++vi) {
        auto& v = _vertices[vi];
        if (!r.vec3(v.position.x, v.position.y, v.position.z) ||
            !r.vec3(v.normal.x, v.normal.y, v.normal.z) ||
            !r.f32(v.uv.x) || !r.f32(v.uv.y))
            return fail("failed vertex " + std::to_string(vi));

        float f{};
        for (uint8_t n = 0; n < uvCount; ++n)
            for (int c = 0; c < 4; ++c)
                if (!r.f32(f)) return fail("failed additional UV at vertex " + std::to_string(vi));

        uint8_t weight{};
        int32_t idx{};
        if (!r.u8(weight)) return fail("failed weight type at vertex " + std::to_string(vi));

        switch (weight) {
        case 0: // BDEF1
            if (!r.index(idx, boneIndexSize, true)) return fail("bad BDEF1 at vertex " + std::to_string(vi));
            break;
        case 1: // BDEF2
            if (!r.index(idx, boneIndexSize, true) || !r.index(idx, boneIndexSize, true) || !r.f32(f))
                return fail("bad BDEF2 at vertex " + std::to_string(vi));
            break;
        case 2: // BDEF4
        case 4: // QDEF (PMX 2.1)
            for (int n = 0; n < 4; ++n)
                if (!r.index(idx, boneIndexSize, true)) return fail("bad BDEF4/QDEF index at vertex " + std::to_string(vi));
            for (int n = 0; n < 4; ++n)
                if (!r.f32(f)) return fail("bad BDEF4/QDEF weights at vertex " + std::to_string(vi));
            break;
        case 3: // SDEF: bones + weight + C + R0 + R1
            if (!r.index(idx, boneIndexSize, true) || !r.index(idx, boneIndexSize, true))
                return fail("bad SDEF bones at vertex " + std::to_string(vi));
            for (int n = 0; n < 10; ++n)
                if (!r.f32(f)) return fail("bad SDEF data at vertex " + std::to_string(vi));
            break;
        default:
            return fail("unknown vertex weight type " + std::to_string(weight));
        }

        if (!r.f32(f)) return fail("failed edge scale at vertex " + std::to_string(vi));
    }

    // ---------------------------------------------------------------------
    // Surface / triangle indices
    // ---------------------------------------------------------------------
    if (!r.u32(_indexCount) || _indexCount > 30000000) return fail("invalid index count");
    _indices.resize(_indexCount);
    for (uint32_t i = 0; i < _indexCount; ++i) {
        int32_t idx{};
        if (!r.index(idx, vertexIndexSize, false) || idx < 0 || uint32_t(idx) >= vertexCount)
            return fail("invalid vertex index " + std::to_string(i));
        _indices[i] = uint32_t(idx);
    }

    // ---------------------------------------------------------------------
    // Texture paths
    // ---------------------------------------------------------------------
    uint32_t textureCount{};
    if (!r.u32(textureCount) || textureCount > 1000000) return fail("invalid texture count");
    _textures.resize(textureCount);
    for (uint32_t i = 0; i < textureCount; ++i)
        if (!r.text(_textures[i], encoding)) return fail("failed texture path " + std::to_string(i));

    // ---------------------------------------------------------------------
    // Materials
    // ---------------------------------------------------------------------
    uint32_t materialCount{};
    if (!r.u32(materialCount) || materialCount > 1000000) return fail("invalid material count");
    _materials.reserve(materialCount);

    for (uint32_t i = 0; i < materialCount; ++i) {
        Material m{};
        float f{};
        int32_t idx{};

        if (!r.text(m.name, encoding) || !r.text(m.englishName, encoding))
            return fail("failed material name " + std::to_string(i));
        for (int n = 0; n < 4; ++n) if (!r.f32(f)) return fail("failed material diffuse " + std::to_string(i));
        for (int n = 0; n < 3; ++n) if (!r.f32(f)) return fail("failed material specular " + std::to_string(i));
        if (!r.f32(f)) return fail("failed material specular power " + std::to_string(i));
        for (int n = 0; n < 3; ++n) if (!r.f32(f)) return fail("failed material ambient " + std::to_string(i));

        uint8_t flags{};
        if (!r.u8(flags)) return fail("failed material flags " + std::to_string(i));
        for (int n = 0; n < 4; ++n) if (!r.f32(f)) return fail("failed material edge colour " + std::to_string(i));
        if (!r.f32(f)) return fail("failed material edge size " + std::to_string(i));

        if (!r.index(idx, textureIndexSize, true)) return fail("failed material texture index " + std::to_string(i));
        m.textureIndex = idx;
        if (!r.index(idx, textureIndexSize, true)) return fail("failed material sphere texture index " + std::to_string(i));
        m.sphereTextureIndex = idx;

        uint8_t sphereMode{};
        if (!r.u8(sphereMode)) return fail("failed material sphere mode " + std::to_string(i));
        uint8_t toonFlag{};
        if (!r.u8(toonFlag)) return fail("failed material toon flag " + std::to_string(i));
        if (toonFlag == 0) {
            if (!r.index(idx, textureIndexSize, true)) return fail("failed material toon texture " + std::to_string(i));
        } else {
            uint8_t toon{};
            if (!r.u8(toon)) return fail("failed material toon index " + std::to_string(i));
        }

        std::string memo;
        if (!r.text(memo, encoding)) return fail("failed material memo " + std::to_string(i));
        int32_t faces{};
        if (!r.i32(faces) || faces < 0) return fail("invalid material face count " + std::to_string(i));
        m.indexCount = uint32_t(faces);
        _materials.push_back(std::move(m));
    }

    // ---------------------------------------------------------------------
    // BONES -- this MUST be parsed before morphs in PMX.
    // The PMX/MMDTools order is: materials -> bones -> morphs.
    // ---------------------------------------------------------------------
    uint32_t boneCount{};
    if (!r.u32(boneCount) || boneCount > 1000000) return fail("invalid bone count");
    _bones.reserve(boneCount);

    for (uint32_t i = 0; i < boneCount; ++i) {
        Bone b{};
        if (!r.text(b.name, encoding) || !r.text(b.englishName, encoding) ||
            !r.vec3(b.position.x, b.position.y, b.position.z))
            return fail("failed bone strings/position " + std::to_string(i));

        int32_t parent{};
        if (!r.index(parent, boneIndexSize, true)) return fail("failed bone parent " + std::to_string(i));
        b.parent = parent;

        // PMX contains transform/depth BEFORE the 16-bit bone flags.
        int32_t transformDepth{};
        if (!r.i32(transformDepth)) return fail("failed bone transform depth " + std::to_string(i));

        uint16_t flags{};
        if (!r.u16(flags)) return fail("failed bone flags " + std::to_string(i));

        int32_t idx{};
        float f{};

        // Connection destination / offset.
        if (flags & 0x0001) {
            if (!r.index(idx, boneIndexSize, true)) return fail("bad bone connection " + std::to_string(i));
        } else {
            for (int n = 0; n < 3; ++n) if (!r.f32(f)) return fail("bad bone position offset " + std::to_string(i));
        }

        // Rotation/translation inheritance.
        if (flags & (0x0100 | 0x0200)) {
            if (!r.index(idx, boneIndexSize, true) || !r.f32(f))
                return fail("bad bone inherit data " + std::to_string(i));
        }

        // Fixed axis.
        if (flags & 0x0400)
            for (int n = 0; n < 3; ++n) if (!r.f32(f)) return fail("bad bone fixed axis " + std::to_string(i));

        // Local X/Z axes.
        if (flags & 0x0800)
            for (int n = 0; n < 6; ++n) if (!r.f32(f)) return fail("bad bone local axis " + std::to_string(i));

        // External parent key.
        if (flags & 0x2000) {
            if (!r.i32(idx)) return fail("bad external parent key " + std::to_string(i));
        }

        // IK block.
        if (flags & 0x0020) {
            if (!r.index(idx, boneIndexSize, true)) return fail("bad IK target " + std::to_string(i));

            int32_t loopCount{};
            if (!r.i32(loopCount) || loopCount < 0) return fail("invalid IK loop count on bone " + std::to_string(i));
            if (!r.f32(f)) return fail("bad IK loop angle " + std::to_string(i));

            int32_t linkCount{};
            if (!r.i32(linkCount) || linkCount < 0 || linkCount > 100000)
                return fail("invalid IK link count on bone " + std::to_string(i));

            for (int32_t k = 0; k < linkCount; ++k) {
                if (!r.index(idx, boneIndexSize, true)) return fail("bad IK link on bone " + std::to_string(i));
                uint8_t hasLimit{};
                if (!r.u8(hasLimit) || hasLimit > 1) return fail("bad IK limit flag on bone " + std::to_string(i));
                if (hasLimit)
                    for (int n = 0; n < 6; ++n) if (!r.f32(f)) return fail("bad IK limit data on bone " + std::to_string(i));
            }
        }

        _bones.push_back(std::move(b));
    }

    // ---------------------------------------------------------------------
    // MORPHS -- parsed after bones, exactly as PMX/MMDTools specifies.
    // ---------------------------------------------------------------------
    uint32_t morphCount{};
    if (!r.u32(morphCount) || morphCount > 1000000) return fail("invalid morph count");
    _morphs.reserve(morphCount);

    for (uint32_t i = 0; i < morphCount; ++i) {
        Morph m{};
        if (!r.text(m.name, encoding) || !r.text(m.englishName, encoding))
            return fail("failed morph name " + std::to_string(i));

        uint8_t panel{}, type{};
        if (!r.u8(panel) || !r.u8(type) || !r.u32(m.offsetCount))
            return fail("failed morph header " + std::to_string(i));
        m.panel = panel;
        m.type = type;

        for (uint32_t j = 0; j < m.offsetCount; ++j) {
            float f{};
            int32_t idx{};
            switch (type) {
            case 0: // Group
                if (!r.index(idx, morphIndexSize, true) || !r.f32(f)) return fail("bad group morph " + std::to_string(i));
                break;
            case 1: // Vertex
                if (!r.index(idx, vertexIndexSize, true)) return fail("bad vertex morph index " + std::to_string(i));
                for (int n = 0; n < 3; ++n) if (!r.f32(f)) return fail("bad vertex morph data " + std::to_string(i));
                break;
            case 2: // Bone
                if (!r.index(idx, boneIndexSize, true)) return fail("bad bone morph index " + std::to_string(i));
                for (int n = 0; n < 7; ++n) if (!r.f32(f)) return fail("bad bone morph data " + std::to_string(i));
                break;
            case 3: case 4: case 5: case 6: case 7: // UV / additional UV
                if (!r.index(idx, vertexIndexSize, true)) return fail("bad UV morph index " + std::to_string(i));
                for (int n = 0; n < 4; ++n) if (!r.f32(f)) return fail("bad UV morph data " + std::to_string(i));
                break;
            case 8: // Material: index + calc mode + 28 floats
                if (!r.index(idx, materialIndexSize, true)) return fail("bad material morph index " + std::to_string(i));
                { uint8_t calcMode{}; if (!r.u8(calcMode)) return fail("bad material morph calc mode " + std::to_string(i)); }
                for (int n = 0; n < 28; ++n) if (!r.f32(f)) return fail("bad material morph data " + std::to_string(i));
                break;
            case 9: // Flip (PMX 2.1)
                if (_version < 2.1f) return fail("flip morph in PMX 2.0");
                if (!r.index(idx, morphIndexSize, true) || !r.f32(f)) return fail("bad flip morph " + std::to_string(i));
                break;
            case 10: // Impulse (PMX 2.1): rigid-body index + local flag + 6 floats
                if (_version < 2.1f) return fail("impulse morph in PMX 2.0");
                if (!r.index(idx, rigidBodyIndexSize, true)) return fail("bad impulse rigid-body index " + std::to_string(i));
                { uint8_t localFlag{}; if (!r.u8(localFlag)) return fail("bad impulse local flag " + std::to_string(i)); }
                for (int n = 0; n < 6; ++n) if (!r.f32(f)) return fail("bad impulse morph data " + std::to_string(i));
                break;
            default:
                return fail("unsupported morph type " + std::to_string(type) + " at morph " + std::to_string(i));
            }
        }
        _morphs.push_back(std::move(m));
    }

    // We intentionally stop here. The runtime only needs geometry, materials,
    // bones and morphs at this stage. Display frames/physics can be added later
    // without affecting the PMX data already parsed above.
    _loaded = true;
    return true;
}

} // namespace gene
