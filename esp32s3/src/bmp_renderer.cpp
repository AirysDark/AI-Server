#include "bmp_renderer.h"

void BmpRenderer::begin(TFT_eSPI* display) { _tft = display; }

bool BmpRenderer::read16(File& f, uint16_t& value) {
    uint8_t b[2];
    if (f.read(b, 2) != 2) return false;
    value = uint16_t(b[0]) | (uint16_t(b[1]) << 8);
    return true;
}

bool BmpRenderer::read32(File& f, uint32_t& value) {
    uint8_t b[4];
    if (f.read(b, 4) != 4) return false;
    value = uint32_t(b[0]) | (uint32_t(b[1]) << 8) | (uint32_t(b[2]) << 16) | (uint32_t(b[3]) << 24);
    return true;
}

bool BmpRenderer::draw(fs::FS& fs, const String& path, int16_t x, int16_t y) {
    if (!_tft || !fs.exists(path)) return false;
    File f = fs.open(path, FILE_READ);
    if (!f) return false;

    uint16_t signature;
    uint32_t fileSize, reserved, dataOffset;
    if (!read16(f, signature) || signature != 0x4D42 || !read32(f, fileSize) || !read32(f, reserved) || !read32(f, dataOffset)) { f.close(); return false; }

    uint32_t headerSize;
    int32_t width, height;
    uint16_t planes, depth;
    uint32_t compression;
    if (!read32(f, headerSize) || headerSize < 40 || !read32(f, reinterpret_cast<uint32_t&>(width)) || !read32(f, reinterpret_cast<uint32_t&>(height)) || !read16(f, planes) || !read16(f, depth) || !read32(f, compression)) { f.close(); return false; }
    if (planes != 1 || compression != 0 || (depth != 24 && depth != 16) || width <= 0 || height == 0) { f.close(); return false; }

    const bool topDown = height < 0;
    const uint32_t absHeight = topDown ? uint32_t(-height) : uint32_t(height);
    const uint32_t bytesPerPixel = depth / 8;
    const uint32_t rowBytes = ((uint32_t(width) * bytesPerPixel + 3) / 4) * 4;
    const uint16_t w = min<uint32_t>(width, _tft->width() - max<int16_t>(0, x));
    const uint16_t h = min<uint32_t>(absHeight, _tft->height() - max<int16_t>(0, y));

    if (!w || !h) { f.close(); return false; }
    uint8_t* row = static_cast<uint8_t*>(malloc(rowBytes));
    if (!row) { f.close(); return false; }

    _tft->startWrite();
    _tft->setAddrWindow(x, y, w, h);
    for (uint16_t outY = 0; outY < h; ++outY) {
        const uint32_t srcY = topDown ? outY : (absHeight - 1 - outY);
        f.seek(dataOffset + srcY * rowBytes);
        if (f.read(row, rowBytes) != rowBytes) { free(row); f.close(); _tft->endWrite(); return false; }
        for (uint16_t px = 0; px < w; ++px) {
            const uint8_t* p = row + px * bytesPerPixel;
            uint16_t color;
            if (depth == 24) color = _tft->color565(p[2], p[1], p[0]);
            else color = uint16_t(p[0]) | (uint16_t(p[1]) << 8);
            _tft->pushColor(color);
        }
    }
    _tft->endWrite();
    free(row);
    f.close();
    return true;
}
