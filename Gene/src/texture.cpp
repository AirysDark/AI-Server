#include "texture.h"
#include <fstream>

namespace gene {
bool TextureLoader::load(const std::string& path, TextureInfo& info) {
    std::ifstream file(path, std::ios::binary);
    if (!file) return false;
    info.path = path;
    return true;
}
}
