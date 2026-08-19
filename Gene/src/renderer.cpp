#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <string>
#include <vector>
#include "renderer.h"

namespace gene {

static LRESULT CALLBACK GeneWndProc(HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam)
{
    Renderer* renderer = reinterpret_cast<Renderer*>(GetWindowLongPtrW(hwnd, GWLP_USERDATA));

    switch (msg)
    {
    case WM_CLOSE:
        if (renderer != nullptr)
            renderer->shutdown();
        else
            DestroyWindow(hwnd);
        return 0;

    case WM_PAINT:
        if (renderer != nullptr)
            renderer->paint();
        else
        {
            PAINTSTRUCT ps = {};
            BeginPaint(hwnd, &ps);
            EndPaint(hwnd, &ps);
        }
        return 0;

    case WM_ERASEBKGND:
        return 1;

    case WM_SIZE:
        if (renderer != nullptr)
        {
            int width = LOWORD(lParam);
            int height = HIWORD(lParam);
            if (width > 0 && height > 0)
                renderer->ensureBackBuffer(width, height);
        }
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

    if (dc != nullptr)
    {
        if (oldBitmap != nullptr)
            SelectObject(dc, oldBitmap);
        DeleteDC(dc);
    }

    if (bitmap != nullptr)
        DeleteObject(bitmap);

    _backBufferDC = nullptr;
    _backBufferBitmap = nullptr;
    _backBufferOldBitmap = nullptr;
    _bufferWidth = 0;
    _bufferHeight = 0;
}

bool Renderer::ensureBackBuffer(int width, int height)
{
    if (_window == nullptr || width <= 0 || height <= 0)
        return false;

    if (_backBufferDC != nullptr &&
        _backBufferBitmap != nullptr &&
        _bufferWidth == static_cast<uint32_t>(width) &&
        _bufferHeight == static_cast<uint32_t>(height))
        return true;

    destroyBackBuffer();

    HWND hwnd = static_cast<HWND>(_window);
    HDC windowDC = GetDC(hwnd);
    if (windowDC == nullptr)
        return false;

    HDC memoryDC = CreateCompatibleDC(windowDC);
    HBITMAP bitmap = CreateCompatibleBitmap(windowDC, width, height);
    ReleaseDC(hwnd, windowDC);

    if (memoryDC == nullptr || bitmap == nullptr)
    {
        if (memoryDC != nullptr)
            DeleteDC(memoryDC);
        if (bitmap != nullptr)
            DeleteObject(bitmap);
        return false;
    }

    HBITMAP oldBitmap = static_cast<HBITMAP>(SelectObject(memoryDC, bitmap));

    _backBufferDC = memoryDC;
    _backBufferBitmap = bitmap;
    _backBufferOldBitmap = oldBitmap;
    _bufferWidth = static_cast<uint32_t>(width);
    _bufferHeight = static_cast<uint32_t>(height);

    RECT rect = { 0, 0, width, height };
    FillRect(memoryDC, &rect, reinterpret_cast<HBRUSH>(COLOR_WINDOW + 1));
    return true;
}

bool Renderer::initialize(uint32_t width, uint32_t height)
{
    _width = width;
    _height = height;

    HINSTANCE instance = GetModuleHandleW(nullptr);
    const wchar_t* className = L"GeneRuntimeWindow";

    WNDCLASSW wc = {};
    wc.lpfnWndProc = GeneWndProc;
    wc.hInstance = instance;
    wc.lpszClassName = className;
    wc.hCursor = LoadCursorW(nullptr, IDC_ARROW);
    wc.hbrBackground = reinterpret_cast<HBRUSH>(COLOR_WINDOW + 1);
    RegisterClassW(&wc);

    RECT rect = { 0, 0, static_cast<LONG>(_width), static_cast<LONG>(_height) };
    AdjustWindowRect(&rect, WS_OVERLAPPEDWINDOW, FALSE);

    HWND hwnd = CreateWindowExW(
        0,
        className,
        L"Gene Runtime",
        WS_OVERLAPPEDWINDOW,
        CW_USEDEFAULT,
        CW_USEDEFAULT,
        rect.right - rect.left,
        rect.bottom - rect.top,
        nullptr,
        nullptr,
        instance,
        nullptr);

    if (hwnd == nullptr)
        return false;

    _window = hwnd;
    _running = true;
    SetWindowLongPtrW(hwnd, GWLP_USERDATA, reinterpret_cast<LONG_PTR>(this));

    RECT client = {};
    GetClientRect(hwnd, &client);
    ensureBackBuffer(client.right - client.left, client.bottom - client.top);

    ShowWindow(hwnd, SW_SHOW);
    UpdateWindow(hwnd);
    return true;
}

void Renderer::pollEvents()
{
    MSG msg = {};
    while (PeekMessageW(&msg, nullptr, 0, 0, PM_REMOVE))
    {
        if (msg.message == WM_QUIT)
            _running = false;
        else
        {
            TranslateMessage(&msg);
            DispatchMessageW(&msg);
        }
    }
}

bool Renderer::running() const
{
    return _running;
}

void Renderer::draw(const Model& model)
{
    if (_window == nullptr)
        return;

    HWND hwnd = static_cast<HWND>(_window);
    RECT client = {};
    GetClientRect(hwnd, &client);

    int clientWidth = client.right - client.left;
    int clientHeight = client.bottom - client.top;
    if (clientWidth <= 0 || clientHeight <= 0)
        return;

    if (!ensureBackBuffer(clientWidth, clientHeight))
        return;

    HDC dc = static_cast<HDC>(_backBufferDC);
    FillRect(dc, &client, reinterpret_cast<HBRUSH>(COLOR_WINDOW + 1));

    const std::vector<Vertex>& vertices = model.vertices();
    const std::vector<uint32_t>& indices = model.indices();

    if (vertices.empty() || indices.size() < 3)
    {
        DrawTextW(dc, L"Gene Runtime\n\nNo renderable PMX geometry.", -1, &client,
            DT_CENTER | DT_VCENTER | DT_NOPREFIX);
        return;
    }

    float minX = vertices[0].position.x;
    float maxX = minX;
    float minY = vertices[0].position.y;
    float maxY = minY;
    float minZ = vertices[0].position.z;
    float maxZ = minZ;

    for (const Vertex& vertex : vertices)
    {
        if (vertex.position.x < minX) minX = vertex.position.x;
        if (vertex.position.x > maxX) maxX = vertex.position.x;
        if (vertex.position.y < minY) minY = vertex.position.y;
        if (vertex.position.y > maxY) maxY = vertex.position.y;
        if (vertex.position.z < minZ) minZ = vertex.position.z;
        if (vertex.position.z > maxZ) maxZ = vertex.position.z;
    }

    float centerX = (minX + maxX) * 0.5f;
    float centerY = (minY + maxY) * 0.5f;
    float centerZ = (minZ + maxZ) * 0.5f;

    float spanX = maxX - minX;
    float spanY = maxY - minY;
    float spanZ = maxZ - minZ;
    float span = spanX;
    if (spanY > span) span = spanY;
    if (spanZ > span) span = spanZ;
    if (span < 0.001f) span = 0.001f;

    int windowSize = clientWidth < clientHeight ? clientWidth : clientHeight;
    float scale = static_cast<float>(windowSize) * 0.78f / span;

    std::vector<POINT> projected(vertices.size());
    for (size_t i = 0; i < vertices.size(); ++i)
    {
        const Vec3& position = vertices[i].position;
        float x = (position.x - centerX) * scale;
        float y = (position.y - centerY) * scale;
        float z = (position.z - centerZ) * scale;
        projected[i].x = static_cast<LONG>(clientWidth * 0.5f + x - z * 0.35f);
        projected[i].y = static_cast<LONG>(clientHeight * 0.5f - y - z * 0.20f);
    }

    HPEN pen = CreatePen(PS_SOLID, 1, RGB(60, 60, 60));
    HGDIOBJ oldPen = SelectObject(dc, pen);

    size_t triangleCount = indices.size() / 3;
    size_t step = triangleCount > 30000 ? (triangleCount / 30000) + 1 : 1;

    for (size_t triangle = 0; triangle < triangleCount; triangle += step)
    {
        uint32_t a = indices[triangle * 3];
        uint32_t b = indices[triangle * 3 + 1];
        uint32_t c = indices[triangle * 3 + 2];
        if (a >= projected.size() || b >= projected.size() || c >= projected.size())
            continue;

        MoveToEx(dc, projected[a].x, projected[a].y, nullptr);
        LineTo(dc, projected[b].x, projected[b].y);
        LineTo(dc, projected[c].x, projected[c].y);
        LineTo(dc, projected[a].x, projected[a].y);
    }

    SelectObject(dc, oldPen);
    DeleteObject(pen);

    SetBkMode(dc, TRANSPARENT);
    DrawTextW(dc, L"Gene Runtime - PMX geometry", -1, &client,
        DT_TOP | DT_CENTER | DT_NOPREFIX);
}

void Renderer::paint()
{
    HWND hwnd = static_cast<HWND>(_window);
    if (hwnd == nullptr)
        return;

    PAINTSTRUCT ps = {};
    HDC windowDC = BeginPaint(hwnd, &ps);
    if (windowDC == nullptr)
    {
        EndPaint(hwnd, &ps);
        return;
    }

    RECT client = {};
    GetClientRect(hwnd, &client);
    int width = client.right - client.left;
    int height = client.bottom - client.top;

    if (width > 0 && height > 0 && ensureBackBuffer(width, height))
    {
        HDC bufferDC = static_cast<HDC>(_backBufferDC);
        BitBlt(windowDC, 0, 0, width, height, bufferDC, 0, 0, SRCCOPY);
    }

    EndPaint(hwnd, &ps);
}

void Renderer::present()
{
    if (_window != nullptr)
    {
        HWND hwnd = static_cast<HWND>(_window);
        InvalidateRect(hwnd, nullptr, FALSE);
        UpdateWindow(hwnd);
    }
}

void Renderer::setWindowTitle(const std::string& title)
{
    if (_window == nullptr)
        return;

    int length = MultiByteToWideChar(CP_UTF8, 0, title.c_str(), -1, nullptr, 0);
    if (length <= 0)
        return;

    std::wstring wide(static_cast<size_t>(length), L'\0');
    MultiByteToWideChar(CP_UTF8, 0, title.c_str(), -1, wide.data(), length);
    SetWindowTextW(static_cast<HWND>(_window), wide.c_str());
}

void Renderer::shutdown()
{
    HWND hwnd = static_cast<HWND>(_window);
    _window = nullptr;
    _running = false;

    destroyBackBuffer();

    if (hwnd != nullptr)
        DestroyWindow(hwnd);
}

}
