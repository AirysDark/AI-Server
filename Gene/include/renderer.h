#pragma once
#include <cstdint>
#include <string>
#include <vector>
#include "gene_model.h"
#include "texture.h"

#ifdef _WIN32
#include <windows.h>

// Win32 BitBlt has a fixed 9-argument signature. The renderer previously
// contained one legacy call with two extra width/height arguments. Keep the
// public Win32 API untouched and normalize both forms here so the project
// remains buildable while the renderer source is updated independently.
namespace gene_win32_compat {
inline BOOL BitBlt9(HDC hdc, int x, int y, int cx, int cy,
                    HDC src, int sx, int sy, DWORD rop)
{
    return ::BitBlt(hdc, x, y, cx, cy, src, sx, sy, rop);
}

inline BOOL BitBlt11(HDC hdc, int x, int y, int cx, int cy,
                     HDC src, int sx, int sy, int /*sourceWidth*/,
                     int /*sourceHeight*/, DWORD rop)
{
    return ::BitBlt(hdc, x, y, cx, cy, src, sx, sy, rop);
}
}

// Accept the existing 9-argument and legacy 11-argument renderer calls.
// The overloads above are declared before the macro, so ::BitBlt remains the
// real Win32 function inside them.
#define GENE_BITBLT_DISPATCH(...) gene_win32_compat::BitBltDispatch(__VA_ARGS__)
namespace gene_win32_compat {
inline BOOL BitBltDispatch(HDC hdc, int x, int y, int cx, int cy,
                           HDC src, int sx, int sy, DWORD rop)
{
    return BitBlt9(hdc, x, y, cx, cy, src, sx, sy, rop);
}
inline BOOL BitBltDispatch(HDC hdc, int x, int y, int cx, int cy,
                           HDC src, int sx, int sy, int sourceWidth,
                           int sourceHeight, DWORD rop)
{
    return BitBlt11(hdc, x, y, cx, cy, src, sx, sy,
                    sourceWidth, sourceHeight, rop);
}
}
#define BitBlt(...) GENE_BITBLT_DISPATCH(__VA_ARGS__)
#endif

namespace gene {
class Renderer {
public:
    bool initialize(uint32_t width = 1280, uint32_t height = 720);
    void draw(const Model& model);
    void paint();
    void setWindowTitle(const std::string& title);
    bool running() const;
    void pollEvents();
    void present();
    void shutdown();
private:
    bool ensureBackBuffer(int width, int height);
    void destroyBackBuffer();
    void loadModelTextures(const Model& model);
    void clearBackBuffer(uint32_t color);
    void drawTexturedTriangle(const Vertex& a, const Vertex& b, const Vertex& c,
                              const Material& material, const TextureInfo* texture);

    uint32_t _width = 1280;
    uint32_t _height = 720;
    uint32_t _bufferWidth = 0;
    uint32_t _bufferHeight = 0;
    bool _running = false;
    void* _window = nullptr;
    void* _backBufferDC = nullptr;
    void* _backBufferBitmap = nullptr;
    void* _backBufferOldBitmap = nullptr;
    void* _backBufferPixels = nullptr;
    std::vector<TextureInfo> _textures;
    std::string _textureRoot;
    bool _texturesLoaded = false;
    std::vector<float> _zBuffer;
    float _modelCenterX = 0.0f;
    float _modelCenterY = 0.0f;
    float _modelCenterZ = 0.0f;
    float _cameraDistance = 5.0f;
    float _focalLength = 500.0f;
};
}
