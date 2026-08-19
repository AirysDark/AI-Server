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
        if (renderer) renderer->shutdown(); else DestroyWindow(hwnd);
        return 0;
    case WM_PAINT:
        if (renderer) renderer->paint();
        else { PAINTSTRUCT ps{}; BeginPaint(hwnd, &ps); EndPaint(hwnd, &ps); }
        return 0;
    case WM_ERASEBKGND:
        return 1;
    case WM_SIZE:
        return 0;
    case WM_DESTROY:
        PostQuitMessage(0);
        return 0;
    default:
        return DefWindowProcW(hwnd, msg, wParam, lParam);
    }
}

void Renderer::destroyBackBuffer()
{
    HDC dc = static_cast<HDC>(_backBufferDC);
    HBITMAP bitmap = static_cast<HBITMAP>(_backBufferBitmap);
    HBITMAP oldBitmap = static_cast<HBITMAP>(_backBufferOldBitmap);
    if (dc) { if (oldBitmap) SelectObject(dc, oldBitmap); DeleteDC(dc); }
    if (bitmap) DeleteObject(bitmap);
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
    if (!memoryDC) { ReleaseDC(hwnd, windowDC); return false; }
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
    if (!bitmap || !pixels) { if (bitmap) DeleteObject(bitmap); DeleteDC(memoryDC); return false; }
    HBITMAP oldBitmap = static_cast<HBITMAP>(SelectObject(memoryDC, bitmap));
    _backBufferDC = memoryDC;
    _backBufferBitmap = bitmap;
    _backBufferOldBitmap = oldBitmap;
    _backBufferPixels = pixels;
    _bufferWidth = uint32_t(width);
    _bufferHeight = uint32_t(height);
    _zBuffer.assign(size_t(width) * size_t(height), std::numeric_limits<float>::infinity());
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
    RECT rect{0, 0, LONG(_width), LONG(_height)};
    AdjustWindowRect(&rect, WS_OVERLAPPEDWINDOW, FALSE);
    HWND hwnd = CreateWindowExW(0, className, L"Gene Runtime", WS_OVERLAPPEDWINDOW,
        CW_USEDEFAULT, CW_USEDEFAULT, rect.right - rect.left, rect.bottom - rect.top,
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
        else { TranslateMessage(&msg); DispatchMessageW(&msg); }
    }
}

bool Renderer::running() const { return _running; }

void Renderer::clearBackBuffer(uint32_t color)
{
    if (!_backBufferPixels) return;
    auto* dst = static_cast<uint32_t*>(_backBufferPixels);
    const size_t pixels = size_t(_bufferWidth) * size_t(_bufferHeight);
    std::fill(dst, dst + pixels, color);
    std::fill(_zBuffer.begin(), _zBuffer.end(), std::numeric_limits<float>::infinity());
}

static inline float edge(float ax, float ay, float bx, float by, float px, float py)
{
    return (px - ax) * (by - ay) - (py - ay) * (bx - bx);
}

void Renderer::drawTexturedTriangle(const Vertex& a, const Vertex& b, const Vertex& c,
                                    const Material& material, const TextureInfo* texture)
{
    struct P { float x{}, y{}, depth{}, invDepth{}, u{}, v{}, nx{}, ny{}, nz{}; } p[3];
    const float cameraZ = _modelCenterZ + _cameraDistance;
    const float cx = float(_bufferWidth) * 0.5f;
    const float cy = float(_bufferHeight) * 0.53f;
    auto project = [&](const Vertex& v) {
        P q{};
        const float x = v.position.x - _modelCenterX;
        const float y = v.position.y - _modelCenterY;
        q.depth = cameraZ - v.position.z;
        if (q.depth < 0.001f) q.depth = 0.001f;
        q.invDepth = 1.0f / q.depth;
        q.x = cx + x * _focalLength * q.invDepth;
        q.y = cy - y * _focalLength * q.invDepth;
        q.u = v.uv.x;
        q.v = 1.0f - v.uv.y;
        q.nx = v.normal.x; q.ny = v.normal.y; q.nz = v.normal.z;
        return q;
    };
    p[0] = project(a); p[1] = project(b); p[2] = project(c);
    const float area = edge(p[0].x,p[0].y,p[1].x,p[1].y,p[2].x,p[2].y);
    if (std::fabs(area) < 0.00001f) return;
    const bool doubleSided = (material.flags & 0x01u) != 0;
    if (!doubleSided && area >= 0.0f) return;
    const int minX = std::max(0, int(std::floor(std::min({p[0].x,p[1].x,p[2].x}))));
    const int maxX = std::min(int(_bufferWidth)-1, int(std::ceil(std::max({p[0].x,p[1].x,p[2].x}))));
    const int minY = std::max(0, int(std::floor(std::min({p[0].y,p[1].y,p[2].y}))));
    const int maxY = std::min(int(_bufferHeight)-1, int(std::ceil(std::max({p[0].y,p[1].y,p[2].y}))));
    if (minX > maxX || minY > maxY) return;
    auto* dst = static_cast<uint32_t*>(_backBufferPixels);
    const bool textured = texture && texture->loaded() && texture->width > 0 && texture->height > 0;
    const uint8_t materialAlpha = uint8_t(std::clamp(material.diffuse[3] * 255.0f, 0.0f, 255.0f));
    for (int y=minY; y<=maxY; ++y) for (int x=minX; x<=maxX; ++x) {
        const float px=float(x)+0.5f, py=float(y)+0.5f;
        float w0=edge(p[1].x,p[1].y,p[2].x,p[2].y,px,py);
        float w1=edge(p[2].x,p[2].y,p[0].x,p[0].y,px,py);
        float w2=edge(p[0].x,p[0].y,p[1].x,p[1].y,px,py);
        if (!((w0 >= 0.0f && w1 >= 0.0f && w2 >= 0.0f) || (w0 <= 0.0f && w1 <= 0.0f && w2 <= 0.0f))) continue;
        w0/=area; w1/=area; w2/=area;
        const float invDepth=w0*p[0].invDepth+w1*p[1].invDepth+w2*p[2].invDepth;
        if (invDepth<=0.0f) continue;
        const float depth=1.0f/invDepth;
        const size_t pos=size_t(y)*size_t(_bufferWidth)+size_t(x);
        if (depth >= _zBuffer[pos]) continue;
        const float u=(w0*p[0].u*p[0].invDepth+w1*p[1].u*p[1].invDepth+w2*p[2].u*p[2].invDepth)/invDepth;
        const float v=(w0*p[0].v*p[0].invDepth+w1*p[1].v*p[1].invDepth+w2*p[2].v*p[2].invDepth)/invDepth;
        uint8_t sr=220,sg=220,sb=220,textureAlpha=255;
        if (textured) {
            const float uu=u-std::floor(u), vv=v-std::floor(v);
            const uint32_t tx=std::min(texture->width-1,uint32_t(std::max(0.0f,uu*float(texture->width))));
            const uint32_t ty=std::min(texture->height-1,uint32_t(std::max(0.0f,vv*float(texture->height))));
            const uint8_t* s=&texture->pixels[(size_t(ty)*texture->width+tx)*4];
            sr=s[0]; sg=s[1]; sb=s[2]; textureAlpha=texture->useAlpha ? s[3] : 255u;
        }
        const uint8_t sa=uint8_t((uint16_t(materialAlpha)*uint16_t(textureAlpha)+127u)/255u);
        if (sa<12) continue;
        const float nx=w0*p[0].nx+w1*p[1].nx+w2*p[2].nx;
        const float ny=w0*p[0].ny+w1*p[1].ny+w2*p[2].ny;
        const float nz=w0*p[0].nz+w1*p[1].nz+w2*p[2].nz;
        const float nl=std::sqrt(nx*nx+ny*ny+nz*nz);
        const float light=nl>0.0001f ? (0.35f+0.65f*std::fabs(nz/nl)) : 1.0f;
        const uint8_t r=uint8_t(std::clamp(float(sr)*std::max(0.0f,material.diffuse[0])*light,0.0f,255.0f));
        const uint8_t g=uint8_t(std::clamp(float(sg)*std::max(0.0f,material.diffuse[1])*light,0.0f,255.0f));
        const uint8_t b=uint8_t(std::clamp(float(sb)*std::max(0.0f,material.diffuse[2])*light,0.0f,255.0f));
        if (sa<255) {
            const uint32_t d=dst[pos]; const unsigned a8=sa, ia=255-a8;
            dst[pos]=0xFF000000u|(((unsigned(r)*a8+((d>>16)&255u)*ia)/255u)<<16)|(((unsigned(g)*a8+((d>>8)&255u)*ia)/255u)<<8)|((unsigned(b)*a8+(d&255u)*ia)/255u);
        } else dst[pos]=0xFF000000u|(uint32_t(r)<<16)|(uint32_t(g)<<8)|uint32_t(b);
        _zBuffer[pos]=depth;
    }
}

void Renderer::loadModelTextures(const Model& model)
{
    if (_texturesLoaded && _textureRoot == model.textureDirectory()) return;
    _textures.clear(); _textureRoot=model.textureDirectory(); _textures.resize(model.textures().size());
    for (size_t i=0;i<model.textures().size();++i) {
        std::filesystem::path rel(model.textures()[i]);
        std::filesystem::path path=rel.is_absolute()?rel:std::filesystem::path(_textureRoot)/rel;
        path=path.lexically_normal();
        if (!std::filesystem::exists(path)) { auto fallback=std::filesystem::path(_textureRoot)/rel.filename(); if (std::filesystem::exists(fallback)) path=fallback; }
        TextureLoader loader; if (!loader.load(path.string(),_textures[i])) _textures[i].path=path.string();
    }
    _texturesLoaded=true;
}

void Renderer::draw(const Model& model)
{
    if (!_window) return; HWND hwnd=static_cast<HWND>(_window); RECT client{}; GetClientRect(hwnd,&client);
    const int width=client.right-client.left, height=client.bottom-client.top; if (width<=0||height<=0||!ensureBackBuffer(width,height)) return;
    clearBackBuffer(0xFFF2F2F2u); loadModelTextures(model); const auto& verts=model.vertices(); const auto& idx=model.indices(); if (verts.empty()||idx.size()<3) { present(); return; }
    float minX=verts[0].position.x,maxX=minX,minY=verts[0].position.y,maxY=minY,minZ=verts[0].position.z,maxZ=minZ;
    for (const auto& v:verts) { minX=std::min(minX,v.position.x); maxX=std::max(maxX,v.position.x); minY=std::min(minY,v.position.y); maxY=std::max(maxY,v.position.y); minZ=std::min(minZ,v.position.z); maxZ=std::max(maxZ,v.position.z); }
    _modelCenterX=(minX+maxX)*0.5f; _modelCenterY=(minY+maxY)*0.5f; _modelCenterZ=(minZ+maxZ)*0.5f; const float span=std::max({maxX-minX,maxY-minY,maxZ-minZ,0.001f}); _cameraDistance=span*2.0f; _focalLength=float(std::min(_bufferWidth,_bufferHeight))*0.92f;
    std::vector<Vertex> skinned=verts; const auto& bones=model.bones();
    if (!bones.empty()) for (auto& v:skinned) { float sum=0.0f; for (int n=0;n<4;++n) { if (v.boneIndices[n]>=0&&size_t(v.boneIndices[n])<bones.size()) { v.boneWeights[n]=std::max(0.0f,v.boneWeights[n]); sum+=v.boneWeights[n]; } else { v.boneIndices[n]=-1; v.boneWeights[n]=0.0f; } } if (sum>0.000001f) { const float inv=1.0f/sum; for (float& w:v.boneWeights) w*=inv; } }
    const auto& mats=model.materials(); size_t offset=0;
    for (const auto& mat:mats) { if (offset>=idx.size()) break; const size_t count=std::min<size_t>(mat.indexCount,idx.size()-offset); const TextureInfo* tex=nullptr; if (mat.textureIndex>=0&&size_t(mat.textureIndex)<_textures.size()&&_textures[mat.textureIndex].loaded()) tex=&_textures[mat.textureIndex]; for (size_t j=0;j+2<count;j+=3) { const uint32_t ia=idx[offset+j],ib=idx[offset+j+2],ic=idx[offset+j+1]; if (ia<skinned.size()&&ib<skinned.size()&&ic<skinned.size()) drawTexturedTriangle(skinned[ia],skinned[ib],skinned[ic],mat,tex); } offset+=count; }
    HDC dc=static_cast<HDC>(_backBufferDC); if (dc) { SetBkMode(dc,TRANSPARENT); SetTextColor(dc,RGB(30,30,30)); RECT tr{8,8,width-8,32}; DrawTextW(dc,L"Gene Runtime - PMX",-1,&tr,DT_LEFT|DT_NOPREFIX); } present();
}

void Renderer::paint()
{
    HWND hwnd=static_cast<HWND>(_window); if (!hwnd) return; PAINTSTRUCT ps{}; HDC dc=BeginPaint(hwnd,&ps); RECT r{}; GetClientRect(hwnd,&r); const int w=r.right-r.left,h=r.bottom-r.top; if (dc&&w>0&&h>0&&ensureBackBuffer(w,h)) BitBlt(dc,0,0,w,h,static_cast<HDC>(_backBufferDC),0,0,SRCCOPY); EndPaint(hwnd,&ps);
}

void Renderer::present()
{
    HWND hwnd=static_cast<HWND>(_window); if (!hwnd||!_backBufferDC) return; HDC dc=GetDC(hwnd); if (dc) { const int w=int(_bufferWidth),h=int(_bufferHeight); if (w>0&&h>0) BitBlt(dc,0,0,w,h,static_cast<HDC>(_backBufferDC),0,0,SRCCOPY); ReleaseDC(hwnd,dc); }
}

void Renderer::setWindowTitle(const std::string& title)
{
    HWND hwnd=static_cast<HWND>(_window); if (!hwnd) return; const int required=MultiByteToWideChar(CP_UTF8,0,title.data(),int(title.size()),nullptr,0); if (required<=0) { SetWindowTextW(hwnd,L"Gene Runtime"); return; } std::wstring wide(size_t(required),L'\0'); MultiByteToWideChar(CP_UTF8,0,title.data(),int(title.size()),wide.data(),required); SetWindowTextW(hwnd,wide.c_str());
}

void Renderer::shutdown()
{
    HWND hwnd=static_cast<HWND>(_window); _window=nullptr; _running=false; destroyBackBuffer(); if (hwnd&&IsWindow(hwnd)) DestroyWindow(hwnd);
}

} // namespace gene
