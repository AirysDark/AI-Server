#pragma once
#include <cstdint>
#include <string>
#include <vector>

namespace gene {
struct TextureInfo {
    uint32_t width{};
    uint32_t height{};
    std::string path;
    std::vector<uint8_t> pixels; // RGBA8
    // MMD Tools only uses image alpha when the source image format supports it.
    // In particular, BMP alpha is ignored even when WIC exposes a 32-bit RGBA buffer.
    bool useAlpha = true;
    bool loaded() const noexcept { return width != 0 && height != 0 && pixels.size() == size_t(width) * height * 4; }
};
class TextureLoader {
public:
    bool load(const std::string& path, TextureInfo& info);
};
}
