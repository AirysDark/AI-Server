#include "gene_model.h"
#include <algorithm>
#include <cmath>
#include <cstring>
#include <fstream>
#include <utility>

namespace gene {
namespace {
class Reader {
public:
    explicit Reader(std::istream& in) : _in(in) {}
    template<class T> bool read(T& v) { _in.read(reinterpret_cast<char*>(&v), sizeof(T)); return bool(_in); }
    bool bytes(void* p, std::streamsize n) { _in.read(reinterpret_cast<char*>(p), n); return bool(_in); }
    bool u8(uint8_t& v) { return read(v); }
    bool u16(uint16_t& v) { return read(v); }
    bool i32(int32_t& v) { return read(v); }
    bool u32(uint32_t& v) { return read(v); }
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
bool validIndex(uint8_t s) { return s == 1 || s == 2 || s == 4; }
}

bool Model::fail(const std::string& message) { _loaded = false; _error = message; return false; }

bool Model::loadPmx(const std::string& path)
{
    _loaded = false;
    _error.clear();
    _vertices.clear();
    _baseVertices.clear();
    _indices.clear();
    _materials.clear();
    _baseMaterials.clear();
    _textures.clear();
    _bones.clear();
    _morphs.clear();
    _indexCount = 0;

    std::ifstream in(path, std::ios::binary);
    if (!in) return fail("cannot open file");
    Reader r(in);
    char magic[4]{};
    if (!in.read(magic, 4) || std::memcmp(magic, "PMX ", 4) != 0) return fail("invalid PMX signature");

    uint8_t headerSize{};
    if (!r.f32(_version) || !r.u8(headerSize) || headerSize != 8) return fail("invalid PMX header");
    uint8_t h[8]{};
    if (!r.bytes(h, 8)) return fail("truncated PMX header");
    const uint8_t encoding = h[0], uvCount = h[1], vertexIndexSize = h[2], textureIndexSize = h[3];
    const uint8_t materialIndexSize = h[4], boneIndexSize = h[5], morphIndexSize = h[6], rigidBodyIndexSize = h[7];
    if (encoding > 1 || uvCount > 4 || !validIndex(vertexIndexSize) || !validIndex(textureIndexSize) ||
        !validIndex(materialIndexSize) || !validIndex(boneIndexSize) || !validIndex(morphIndexSize) || !validIndex(rigidBodyIndexSize))
        return fail("invalid PMX index configuration");

    std::string s;
    for (int i = 0; i < 4; ++i) if (!r.text(s, encoding)) return fail("failed PMX strings");

    uint32_t count{};
    float f{};
    int32_t idx{};
    if (!r.u32(count) || count > 10000000) return fail("invalid vertex count");
    _vertices.resize(count);
    for (uint32_t vi = 0; vi < count; ++vi) {
        auto& v = _vertices[vi];
        if (!r.vec3(v.position.x, v.position.y, v.position.z) || !r.vec3(v.normal.x, v.normal.y, v.normal.z) || !r.f32(v.uv.x) || !r.f32(v.uv.y))
            return fail("failed vertex " + std::to_string(vi));
        for (uint8_t n = 0; n < uvCount; ++n) for (int c = 0; c < 4; ++c) if (!r.f32(f)) return fail("failed additional UV");
        uint8_t weight{};
        if (!r.u8(weight)) return fail("failed weight type");
        v.weightType = weight;
        for (int n = 0; n < 4; ++n) { v.boneIndices[n] = -1; v.boneWeights[n] = 0.0f; }
        switch (weight) {
        case 0:
            if (!r.index(idx, boneIndexSize, true)) return fail("bad BDEF1");
            v.boneIndices[0] = idx; v.boneWeights[0] = 1.0f; break;
        case 1: {
            float w{};
            if (!r.index(v.boneIndices[0], boneIndexSize, true) || !r.index(v.boneIndices[1], boneIndexSize, true) || !r.f32(w)) return fail("bad BDEF2");
            v.boneWeights[0] = w; v.boneWeights[1] = 1.0f - w; break;
        }
        case 2:
        case 4:
            for (int n = 0; n < 4; ++n) if (!r.index(v.boneIndices[n], boneIndexSize, true)) return fail("bad BDEF4/QDEF");
            for (int n = 0; n < 4; ++n) if (!r.f32(v.boneWeights[n])) return fail("bad BDEF4/QDEF weights");
            break;
        case 3: {
            float w{}, tmp{};
            if (!r.index(v.boneIndices[0], boneIndexSize, true) || !r.index(v.boneIndices[1], boneIndexSize, true) || !r.f32(w)) return fail("bad SDEF");
            for (int n = 0; n < 9; ++n) if (!r.f32(tmp)) return fail("bad SDEF data");
            v.boneWeights[0] = w; v.boneWeights[1] = 1.0f - w; break;
        }
        default: return fail("unknown vertex weight type " + std::to_string(weight));
        }
        if (!r.f32(f)) return fail("failed edge scale");
    }

    if (!r.u32(_indexCount) || _indexCount > 30000000) return fail("invalid index count");
    _indices.resize(_indexCount);
    for (uint32_t i = 0; i < _indexCount; ++i) {
        if (!r.index(idx, vertexIndexSize, false) || idx < 0 || uint32_t(idx) >= _vertices.size()) return fail("invalid vertex index");
        _indices[i] = uint32_t(idx);
    }

    if (!r.u32(count) || count > 1000000) return fail("invalid texture count");
    _textures.resize(count);
    for (auto& texture : _textures) if (!r.text(texture, encoding)) return fail("failed texture path");

    if (!r.u32(count) || count > 1000000) return fail("invalid material count");
    _materials.reserve(count);
    for (uint32_t i = 0; i < count; ++i) {
        Material m{};
        if (!r.text(m.name, encoding) || !r.text(m.englishName, encoding)) return fail("failed material name");
        for (float& x : m.diffuse) if (!r.f32(x)) return fail("failed diffuse");
        for (float& x : m.specular) if (!r.f32(x)) return fail("failed specular");
        if (!r.f32(f)) return fail("failed specular power");
        for (float& x : m.ambient) if (!r.f32(x)) return fail("failed ambient");
        if (!r.u8(m.flags)) return fail("failed material flags");
        for (float& x : m.edgeColor) if (!r.f32(x)) return fail("failed edge color");
        if (!r.f32(m.edgeSize)) return fail("failed edge size");
        if (!r.index(idx, textureIndexSize, true)) return fail("failed texture index"); m.textureIndex = idx;
        if (!r.index(idx, textureIndexSize, true)) return fail("failed sphere index"); m.sphereTextureIndex = idx;
        if (!r.u8(m.sphereMode) || !r.u8(m.toonFlag)) return fail("failed sphere/toon flags");
        if (m.toonFlag == 0) { if (!r.index(idx, textureIndexSize, true)) return fail("failed toon index"); }
        else if (!r.u8(m.toonTextureIndex)) return fail("failed toon texture");
        if (!r.text(s, encoding)) return fail("failed material memo");
        int32_t faces{};
        if (!r.i32(faces) || faces < 0) return fail("invalid material face count");
        m.indexCount = uint32_t(faces);
        _materials.push_back(std::move(m));
    }

    if (!r.u32(count) || count > 1000000) return fail("invalid bone count");
    _bones.reserve(count);
    for (uint32_t i = 0; i < count; ++i) {
        Bone b{};
        if (!r.text(b.name, encoding) || !r.text(b.englishName, encoding) || !r.vec3(b.position.x, b.position.y, b.position.z)) return fail("failed bone");
        if (!r.index(idx, boneIndexSize, true)) return fail("failed bone parent"); b.parent = idx;
        int32_t transformDepth{}; uint16_t flags{};
        if (!r.i32(transformDepth) || !r.u16(flags)) return fail("failed bone depth/flags");
        if (flags & 0x0001) { if (!r.index(idx, boneIndexSize, true)) return fail("bad bone connection"); }
        else for (int n = 0; n < 3; ++n) if (!r.f32(f)) return fail("bad bone offset");
        if (flags & (0x0100 | 0x0200)) { if (!r.index(idx, boneIndexSize, true) || !r.f32(f)) return fail("bad bone inherit"); }
        if (flags & 0x0400) for (int n = 0; n < 3; ++n) if (!r.f32(f)) return fail("bad fixed axis");
        if (flags & 0x0800) for (int n = 0; n < 6; ++n) if (!r.f32(f)) return fail("bad local axis");
        if (flags & 0x2000) if (!r.i32(idx)) return fail("bad external parent");
        if (flags & 0x0020) {
            if (!r.index(idx, boneIndexSize, true)) return fail("bad IK target");
            int32_t loopCount{}, linkCount{};
            if (!r.i32(loopCount) || loopCount < 0 || !r.f32(f) || !r.i32(linkCount) || linkCount < 0 || linkCount > 100000) return fail("bad IK");
            for (int32_t k = 0; k < linkCount; ++k) {
                uint8_t hasLimit{};
                if (!r.index(idx, boneIndexSize, true) || !r.u8(hasLimit)) return fail("bad IK link");
                if (hasLimit) for (int n = 0; n < 6; ++n) if (!r.f32(f)) return fail("bad IK limit");
            }
        }
        _bones.push_back(std::move(b));
    }

    if (!r.u32(count) || count > 1000000) return fail("invalid morph count");
    _morphs.reserve(count);
    for (uint32_t i = 0; i < count; ++i) {
        Morph m{}; uint8_t type{};
        if (!r.text(m.name, encoding) || !r.text(m.englishName, encoding) || !r.u8(m.panel) || !r.u8(type) || !r.u32(m.offsetCount)) return fail("failed morph header");
        m.type = static_cast<MorphType>(type); m.offsets.resize(m.offsetCount);
        for (auto& o : m.offsets) {
            o.type = m.type;
            switch (type) {
            case 0: case 9:
                if (!r.index(o.index, morphIndexSize, true) || !r.f32(o.weight)) return fail("bad group/flip morph"); break;
            case 1:
                if (!r.index(o.index, vertexIndexSize, false) || !r.f32(o.position.x) || !r.f32(o.position.y) || !r.f32(o.position.z)) return fail("bad vertex morph"); break;
            case 2:
                if (!r.index(o.index, boneIndexSize, true) || !r.f32(o.position.x) || !r.f32(o.position.y) || !r.f32(o.position.z) || !r.f32(o.rotation.x) || !r.f32(o.rotation.y) || !r.f32(o.rotation.z) || !r.f32(o.rotation.w)) return fail("bad bone morph"); break;
            case 3: case 4: case 5: case 6: case 7:
                if (!r.index(o.index, vertexIndexSize, false)) return fail("bad UV morph index");
                for (float& x : o.uv) if (!r.f32(x)) return fail("bad UV morph"); break;
            case 8:
                if (!r.index(o.index, materialIndexSize, true) || !r.u8(o.operation) || o.operation > 1) return fail("bad material morph operation");
                for (float& x : o.diffuse) if (!r.f32(x)) return fail("bad material diffuse morph");
                for (float& x : o.specular) if (!r.f32(x)) return fail("bad material specular morph");
                if (!r.f32(o.shininess)) return fail("bad material shininess morph");
                for (float& x : o.ambient) if (!r.f32(x)) return fail("bad material ambient morph");
                for (float& x : o.edgeColor) if (!r.f32(x)) return fail("bad material edge morph");
                if (!r.f32(o.edgeSize)) return fail("bad material edge size morph");
                for (float& x : o.textureFactor) if (!r.f32(x)) return fail("bad texture factor morph");
                for (float& x : o.sphereTextureFactor) if (!r.f32(x)) return fail("bad sphere factor morph");
                for (float& x : o.toonTextureFactor) if (!r.f32(x)) return fail("bad toon factor morph");
                break;
            case 10:
                if (!r.index(o.index, rigidBodyIndexSize, true) || !r.u8(o.localFlag) || !r.f32(o.velocity.x) || !r.f32(o.velocity.y) || !r.f32(o.velocity.z) || !r.f32(o.torque.x) || !r.f32(o.torque.y) || !r.f32(o.torque.z)) return fail("bad impulse morph");
                break;
            default: return fail("unsupported morph type " + std::to_string(type));
            }
        }
        _morphs.push_back(std::move(m));
    }

    _baseVertices = _vertices;
    _baseMaterials = _materials;
    _loaded = true;
    return true;
}

bool Model::setMorphWeight(const std::string& name, float value)
{
    for (auto& morph : _morphs) if (morph.name == name) { morph.value = value; updateMorphs(); return true; }
    return false;
}

void Model::clearMorphWeights()
{
    for (auto& morph : _morphs) morph.value = 0.0f;
    updateMorphs();
}

void Model::applyMorph(size_t index, float weight, std::vector<float>& weights, std::vector<uint8_t>& visiting)
{
    if (index >= _morphs.size() || std::fabs(weight) < 1e-7f || visiting[index]) return;
    visiting[index] = 1;
    const auto& morph = _morphs[index];
    if (morph.type == MorphType::Group || morph.type == MorphType::Flip) {
        for (const auto& offset : morph.offsets)
            if (offset.index >= 0 && size_t(offset.index) < _morphs.size())
                applyMorph(size_t(offset.index), weight * offset.weight, weights, visiting);
    } else {
        weights[index] += weight;
    }
    visiting[index] = 0;
}

void Model::updateMorphs()
{
    _vertices = _baseVertices;
    _materials = _baseMaterials;
    std::vector<float> weights(_morphs.size(), 0.0f);
    std::vector<uint8_t> visiting(_morphs.size(), 0);
    for (size_t i = 0; i < _morphs.size(); ++i)
        if (std::fabs(_morphs[i].value) > 1e-7f) applyMorph(i, _morphs[i].value, weights, visiting);

    for (size_t i = 0; i < _morphs.size(); ++i) {
        const float weight = weights[i];
        if (std::fabs(weight) < 1e-7f) continue;
        const auto& morph = _morphs[i];
        if (morph.type == MorphType::Vertex) {
            for (const auto& o : morph.offsets) if (o.index >= 0 && size_t(o.index) < _vertices.size()) {
                _vertices[o.index].position.x += o.position.x * weight;
                _vertices[o.index].position.y += o.position.y * weight;
                _vertices[o.index].position.z += o.position.z * weight;
            }
        } else if (morph.type >= MorphType::UV && morph.type <= MorphType::UV4) {
            for (const auto& o : morph.offsets) if (o.index >= 0 && size_t(o.index) < _vertices.size()) {
                _vertices[o.index].uv.x += o.uv[0] * weight;
                _vertices[o.index].uv.y += o.uv[1] * weight;
            }
        } else if (morph.type == MorphType::Material) {
            for (const auto& o : morph.offsets) {
                auto apply = [&](Material& mat) {
                    if (o.operation == 1) {
                        for (int n = 0; n < 4; ++n) mat.diffuse[n] += o.diffuse[n] * weight;
                        for (int n = 0; n < 3; ++n) mat.specular[n] += o.specular[n] * weight;
                        for (int n = 0; n < 3; ++n) mat.ambient[n] += o.ambient[n] * weight;
                        for (int n = 0; n < 4; ++n) mat.edgeColor[n] += o.edgeColor[n] * weight;
                        mat.edgeSize += o.edgeSize * weight;
                    } else {
                        for (int n = 0; n < 4; ++n) mat.diffuse[n] *= 1.0f + (o.diffuse[n] - 1.0f) * weight;
                        for (int n = 0; n < 3; ++n) mat.specular[n] *= 1.0f + (o.specular[n] - 1.0f) * weight;
                        for (int n = 0; n < 3; ++n) mat.ambient[n] *= 1.0f + (o.ambient[n] - 1.0f) * weight;
                        for (int n = 0; n < 4; ++n) mat.edgeColor[n] *= 1.0f + (o.edgeColor[n] - 1.0f) * weight;
                        mat.edgeSize *= 1.0f + (o.edgeSize - 1.0f) * weight;
                    }
                };
                if (o.index < 0) for (auto& mat : _materials) apply(mat);
                else if (size_t(o.index) < _materials.size()) apply(_materials[o.index]);
            }
        }
    }
}
}
