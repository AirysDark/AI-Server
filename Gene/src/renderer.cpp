#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <algorithm>
#include <cmath>
#include <filesystem>
#include <limits>
#include <string>
#include <vector>
#include "renderer.h"

namespace gene {
static LRESULT CALLBACK GeneWndProc(HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam)
{
    Renderer* renderer = reinterpret_cast<Renderer*>(GetWindowLongPtrW(hwnd, GWLP_USERDATA));
    switch (msg) {
    case WM_CLOSE:
        if (renderer) renderer->shutdown();
        else DestroyWindow(hwnd);
        return 0;
    case WM_PAINT:
        if (renderer) renderer->paint();
        else { PAINTSTRUCT ps{}; BeginPaint(hwnd, &ps); EndPaint(hwnd, &ps); }
        return 0;
    case WM_ERASEBKGND: return 1;
    case WM_SIZE: return 0;
    case WM_DESTROY: PostQuitMessage(0); return 0;
    default: return DefWindowProcW(hwnd, msg, wParam, lParam);
    }
}

void Renderer::destroyBackBuffer()
{
    HDC dc = static_cast<HDC>(_backBufferDC);
    HBITMAP bitmap = static_cast<HBITMAP>(_backBufferBitmap);
    HBITMAP oldBitmap = static_cast<HBITMAP>(_backBufferOldBitmap);
    if (dc != nullptr) {
        if (oldBitmap != nullptr) SelectObject(dc, oldBitmap);
        DeleteDC(dc);
    }
    if (bitmap != nullptr) DeleteObject(bitmap);
    _backBufferDC = nullptr;
    _backBufferBitmap = nullptr;
    _backBufferOldBitmap = nullptr;
    _backBufferPixels = nullptr;
    _bufferWidth = 0;
    _bufferHeight = 0;
    _zBuffer.clear();
}

bool Renderer::ensureBackBuffer(int width, int height)
{
    if (!_window || width <= 0 || height <= 0) return false;
    if (_backBufferDC && _bufferWidth == uint32_t(width) && _bufferHeight == uint32_t(height)) return true;

    destroyBackBuffer();
    HWND hwnd = static_cast<HWND>(_window);
    HDC windowDC = GetDC(hwnd);
    if (!windowDC) return false;

    HDC memoryDC = CreateCompatibleDC(windowDC);
    if (!memoryDC) {
        ReleaseDC(hwnd, windowDC);
        return false;
    }

    BITMAPINFO bi{};
    bi.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
    bi.bmiHeader.biWidth = width;
    bi.bmiHeader.biHeight = -height;
    bi.bmiHeader.biPlanes = 1;
    bi.bmiHeader.biBitCount = 32;
    bi.bmiHeader.biCompression = BI_RGB;

    void* pixels = nullptr;
    HBITMAP bitmap = CreateDIBSection(windowDC, &bi, DIB_RGB_COLORS, &pixels, nullptr, 0);
    ReleaseDC(hwnd, windowDC);

    if (!bitmap || !pixels) {
        if (bitmap) DeleteObject(bitmap);
        DeleteDC(memoryDC);
        return false;
    }

    HBITMAP oldBitmap = static_cast<HBITMAP>(SelectObject(memoryDC, bitmap));
    _backBufferDC = memoryDC;
    _backBufferBitmap = bitmap;
    _backBufferOldBitmap = oldBitmap;
    _backBufferPixels = pixels;
    _bufferWidth = uint32_t(width);
    _bufferHeight = uint32_t(height);
    return true;
}

bool Renderer::initialize(uint32_t width, uint32_t height)
{
    _width = width;
    _height = height;
    HINSTANCE instance = GetModuleHandleW(nullptr);
    const wchar_t* className = L"GeneRuntimeWindow";

    WNDCLASSW wc{};
    wc.lpfnWndProc = GeneWndProc;
    wc.hInstance = instance;
    wc.lpszClassName = className;
    wc.hCursor = LoadCursorW(nullptr, IDC_ARROW);
    wc.hbrBackground = nullptr;
    RegisterClassW(&wc);

    RECT rect{0, 0, (LONG)_width, (LONG)_height};
    AdjustWindowRect(&rect, WS_OVERLAPPEDWINDOW, FALSE);
    HWND hwnd = CreateWindowExW(
        0, className, L"Gene Runtime", WS_OVERLAPPEDWINDOW,
        CW_USEDEFAULT, CW_USEDEFAULT,
        rect.right - rect.left, rect.bottom - rect.top,
        nullptr, nullptr, instance, nullptr);

    if (!hwnd) return false;
    _window = hwnd;
    _running = true;
    SetWindowLongPtrW(hwnd, GWLP_USERDATA, reinterpret_cast<LONG_PTR>(this));

    RECT client{};
    GetClientRect(hwnd, &client);
    if (!ensureBackBuffer(client.right - client.left, client.bottom - client.top)) {
        DestroyWindow(hwnd);
        _window = nullptr;
        _running = false;
        return false;
    }

    ShowWindow(hwnd, SW_SHOW);
    UpdateWindow(hwnd);
    return true;
}

void Renderer::pollEvents()
{
    MSG msg{};
    while (PeekMessageW(&msg, nullptr, 0, 0, PM_REMOVE)) {
        if (msg.message == WM_QUIT) _running = false;
        else {
            TranslateMessage(&msg);
            DispatchMessageW(&msg);
        }
    }
}

bool Renderer::running() const { return _running; }

void Renderer::clearBackBuffer(uint32_t color)
{
    if (!_backBufferPixels) return;
    auto* dst = static_cast<uint32_t*>(_backBufferPixels);
    std::fill(dst, dst + size_t(_bufferWidth) * _bufferHeight, color);
}

static inline float edge(float ax, float ay, float bx, float by, float px, float py)
{
    return (px - ax) * (by - ay) - (py - ay) * (bx - ax);
}

void Renderer::drawTexturedTriangle(const Vertex& a, const Vertex& b, const Vertex& c,
                                    const TextureInfo* texture, float zBias)
{
    struct P { float x, y, z, u, v; } p[3]{};
    const float scale = _modelScale;
    const float cx = float(_bufferWidth) * 0.5f;
    const float cy = float(_bufferHeight) * 0.54f;

    auto project = [&](const Vertex& v) {
        P q{};
        q.x = cx + (v.position.x - _modelCenterX) * scale;
        q.y = cy - (v.position.y - _modelCenterY) * scale;
        q.z = (v.position.z - _modelCenterZ) + zBias;
        q.u = v.uv.x;
        q.v = 1.0f - v.uv.y;
        return q;
    };

    p[0] = project(a);
    p[1] = project(b);
    p[2] = project(c);

    float area = edge(p[0].x, p[0].y, p[1].x, p[1].y, p[2].x, p[2].y);
    if (std::fabs(area) < 0.0001f) return;
    if (area < 0.0f) {
        std::swap(p[1], p[2]);
        area = -area;
    }

    const int minX = std::max(0, (int)std::floor(std::min({p[0].x, p[1].x, p[2].x})));
    const int maxX = std::min((int)_bufferWidth - 1, (int)std::ceil(std::max({p[0].x, p[1].x, p[2].x})));
    const int minY = std::max(0, (int)std::floor(std::min({p[0].y, p[1].y, p[2].y})));
    const int maxY = std::min((int)_bufferHeight - 1, (int)std::ceil(std::max({p[0].y, p[1].y, p[2].y})));
    if (minX > maxX || minY > maxY) return;

    auto* dst = static_cast<uint32_t*>(_backBufferPixels);
    const bool textured = texture != nullptr && texture->loaded();
    const uint32_t flat = 0xFFD8D8D8u;

    for (int y = minY; y <= maxY; ++y) {
        for (int x = minX; x <= maxX; ++x) {
            const float px = x + 0.5f;
            const float py = y + 0.5f;
            float w0 = edge(p[1].x, p[1].y, p[2].x, p[2].y, px, py);
            float w1 = edge(p[2].x, p[2].y, p[0].x, p[0].y, px, py);
            float w2 = edge(p[0].x, p[0].y, p[1].x, p[1].y, px, py);
            if (w0 < 0 || w1 < 0 || w2 < 0) continue;
            w0 /= area; w1 /= area; w2 /= area;

            const float z = w0 * p[0].z + w1 * p[1].z + w2 * p[2].z;
            const size_t pos = size_t(y) * _bufferWidth + size_t(x);
            if (z >= _zBuffer[pos]) continue;
            _zBuffer[pos] = z;

            uint32_t src = flat;
            if (textured) {
                float u = w0 * p[0].u + w1 * p[1].u + w2 * p[2].u;
                float v = w0 * p[0].v + w1 * p[1].v + w2 * p[2].v;
                u -= std::floor(u);
                v -= std::floor(v);

                const uint32_t tx = std::min(texture->width - 1,
                    (uint32_t)std::max(0.0f, u * texture->width));
                const uint32_t ty = std::min(texture->height - 1,
                    (uint32_t)std::max(0.0f, v * texture->height));
                const uint8_t* s = &texture->pixels[(size_t(ty) * texture->width + tx) * 4];
                if (s[3] < 8) continue;

                src = uint32_t(s[2]) | (uint32_t(s[1]) << 8) |
                      (uint32_t(s[0]) << 16) | 0xFF000000u;
                if (s[3] < 255) {
                    const uint32_t d = dst[pos];
                    const unsigned a8 = s[3];
                    const unsigned ia = 255 - a8;
                    const unsigned r = ((src >> 16) & 255) * a8 + ((d >> 16) & 255) * ia;
                    const unsigned g = ((src >> 8) & 255) * a8 + ((d >> 8) & 255) * ia;
                    const unsigned b = (src & 255) * a8 + (d & 255) * ia;
                    src = 0xFF000000u | ((r / 255) << 16) | ((g / 255) << 8) | (b / 255);
                }
            }
            dst[pos] = src;
        }
    }
}

void Renderer::loadModelTextures(const Model& model)
{
    if (_texturesLoaded && _textureRoot == model.textureDirectory()) return;
    _textures.clear();
    _textureRoot = model.textureDirectory();
    _textures.resize(model.textures().size());

    for (size_t i = 0; i < model.textures().size(); ++i) {
        std::filesystem::path rel(model.textures()[i]);
        std::filesystem::path path = rel.is_absolute() ? rel : std::filesystem::path(_textureRoot) / rel;
        path = path.lexically_normal();
        if (!std::filesystem::exists(path)) {
            const auto fallback = std::filesystem::path(_textureRoot) / rel.filename();
            if (std::filesystem::exists(fallback)) path = fallback;
        }
        TextureLoader loader;
        if (!loader.load(path.string(), _textures[i])) _textures[i].path = path.string();
    }
    _texturesLoaded = true;
}

void Renderer::draw(const Model& model)
{
    if (!_window) return;
    HWND hwnd = static_cast<HWND>(_window);
    RECT client{};
    GetClientRect(hwnd, &client);
    const int width = client.right - client.left;
    const int height = client.bottom - client.top;
    if (width <= 0 || height <= 0 || !ensureBackBuffer(width, height)) return;

    clearBackBuffer(0xFFF2F2F2u);
    loadModelTextures(model);
    const auto& verts = model.vertices();
    const auto& idx = model.indices();
    if (verts.empty() || idx.size() < 3) {
        present();
        return;
    }

    float minX = verts[0].position.x, maxX = minX;
    float minY = verts[0].position.y, maxY = minY;
    float minZ = verts[0].position.z, maxZ = minZ;
    for (const auto& v : verts) {
        minX = std::min(minX, v.position.x); maxX = std::max(maxX, v.position.x);
        minY = std::min(minY, v.position.y); maxY = std::max(maxY, v.position.y);
        minZ = std::min(minZ, v.position.z); maxZ = std::max(maxZ, v.position.z);
    }

    _modelCenterX = (minX + maxX) * 0.5f;
    _modelCenterY = (minY + maxY) * 0.5f;
    _modelCenterZ = (minZ + maxZ) * 0.5f;
    const float span = std::max({maxX - minX, maxY - minY, maxZ - minZ, 0.001f});
    _modelScale = float(std::min(_bufferWidth, _bufferHeight)) * 0.78f / span;
    _zBuffer.assign(size_t(_bufferWidth) * _bufferHeight, std::numeric_limits<float>::infinity());

    const auto& mats = model.materials();
    size_t offset = 0;
    for (size_t mi = 0; mi < mats.size() && offset + 2 < idx.size(); ++mi) {
        const Material& mat = mats[mi];
        const size_t count = std::min<size_t>(mat.indexCount, idx.size() - offset);
        const TextureInfo* tex = nullptr;
        if (mat.textureIndex >= 0 && size_t(mat.textureIndex) < _textures.size() &&
            _textures[mat.textureIndex].loaded()) {
            tex = &_textures[mat.textureIndex];
        }
        for (size_t j = 0; j + 2 < count; j += 3) {
            const uint32_t ia = idx[offset + j];
            const uint32_t ib = idx[offset + j + 1];
            const uint32_t ic = idx[offset + j + 2];
            if (ia < verts.size() && ib < verts.size() && ic < verts.size())
                drawTexturedTriangle(verts[ia], verts[ib], verts[ic], tex, float(mi) * 0.0001f);
        }
        offset += count;
    }

    HDC dc = static_cast<HDC>(_backBufferDC);
    if (dc != nullptr) {
        SetBkMode(dc, TRANSPARENT);
        SetTextColor(dc, RGB(30, 30, 30));
        RECT textRect{8, 8, width - 8, 32};
        DrawTextW(dc, L"Gene Runtime - textured PMX", -1, &textRect, DT_LEFT | DT_NOPREFIX);
    }
    present();
}

void Renderer::paint()
{
    HWND hwnd = static_cast<HWND>(_window);
    if (!hwnd) return;

    PAINTSTRUCT ps{};
    HDC dc = BeginPaint(hwnd, &ps);
    RECT r{};
    GetClientRect(hwnd, &r);
    const int w = r.right - r.left;
    const int h = r.bottom - r.top;

    if (dc != nullptr && w > 0 && h > 0 && ensureBackBuffer(w, h)) {
        HDC bufferDC = static_cast<HDC>(_backBufferDC);
        // Win32 BitBlt signature is: dest DC, x, y, width, height,
        // source DC, source x, source y, raster operation.
        BitBlt(dc, 0, 0, w, h, bufferDC, 0, 0, SRCCOPY);
    }
    EndPaint(hwnd, &ps);
}

void Renderer::present()
{
    if (_window) InvalidateRect(static_cast<HWND>(_window), nullptr, FALSE);
}

void Renderer::setWindowTitle(const std::string& title)
{
    if (!_window) return;
    const int n = MultiByteToWideChar(CP_UTF8, 0, title.c_str(), -1, nullptr, 0);
    if (n <= 0) return;
    std::wstring w(size_t(n), L'\0');
    MultiByteToWideChar(CP_UTF8, 0, title.c_str(), -1, w.data(), n);
    SetWindowTextW(static_cast<HWND>(_window), w.c_str());
}

void Renderer::shutdown()
{
    HWND hwnd = static_cast<HWND>(_window);
    _window = nullptr;
    _running = false;
    destroyBackBuffer();
    if (hwnd) DestroyWindow(hwnd);
}
}
