#pragma once
#include <cstdint>
#include <string>

namespace gene {
struct TextureInfo { uint32_t width{}, height{}; std::string path; };
class TextureLoader {
public:
    bool load(const std::string& path, TextureInfo& info);
};
}
