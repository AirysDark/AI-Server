#include "gene_model.h"
#include <fstream>
#include <array>

namespace gene {
static uint32_t readU32(std::istream& in) { std::array<unsigned char,4> b{}; in.read(reinterpret_cast<char*>(b.data()),4); return uint32_t(b[0]) | (uint32_t(b[1])<<8) | (uint32_t(b[2])<<16) | (uint32_t(b[3])<<24); }

bool Model::loadPmx(const std::string& path) {
    std::ifstream in(path, std::ios::binary);
    if (!in) return false;
    char magic[4]{}; in.read(magic, 4);
    if (std::string(magic,4) != "PMX ") return false;
    float version{}; in.read(reinterpret_cast<char*>(&version), sizeof(version));
    unsigned char headerSize{}; in.read(reinterpret_cast<char*>(&headerSize),1);
    std::vector<unsigned char> header(headerSize); in.read(reinterpret_cast<char*>(header.data()), headerSize);
    // This first milestone validates and opens PMX files. Full geometry decoding is next.
    _bones.clear(); _morphs.clear(); _loaded = true;
    return true;
}

bool Model::loadTextures(const std::string&) { return _loaded; }
}
