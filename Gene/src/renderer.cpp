#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <algorithm>
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

    case WM_DESTROY:
        PostQuitMessage(0);
        return 0;

    case WM_ERASEBKGND:
        return 1;

    default:
        return DefWindowProcW(hwnd, msg, wParam, lParam);
    }
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
        {
            _running = false;
        }
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
    HDC dc = GetDC(hwnd);
    if (dc == nullptr)
        return;

    RECT client = {};
    GetClientRect(hwnd, &client);
    FillRect(dc, &client, reinterpret_cast<HBRUSH>(COLOR_WINDOW + 1));

    const std::vector<Vertex>& vertices = model.vertices();
    const std::vector<uint32_t>& indices = model.indices();

    if (vertices.empty() || indices.size() < 3)
    {
        DrawTextW(dc, L"Gene Runtime\n\nNo renderable PMX geometry.", -1, &client,
            DT_CENTER | DT_VCENTER | DT_NOPREFIX);
        ReleaseDC(hwnd, dc);
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
        minX = std::min(minX, vertex.position.x);
        maxX = std::max(maxX, vertex.position.x);
        minY = std::min(minY, vertex.position.y);
        maxY = std::max(maxY, vertex.position.y);
        minZ = std::min(minZ, vertex.position.z);
        maxZ = std::max(maxZ, vertex.position.z);
    }

    float centerX = (minX + maxX) * 0.5f;
    float centerY = (minY + maxY) * 0.5f;
    float centerZ = (minZ + maxZ) * 0.5f;
    float span = std::max(std::max(maxX - minX, maxY - minY), std::max(maxZ - minZ, 0.001f));
    float windowSpan = static_cast<float>(std::min(client.right - client.left, client.bottom - client.top));
    float scale = windowSpan * 0.78f / span;

    std::vector<POINT> projected(vertices.size());

    for (size_t i = 0; i < vertices.size(); ++i)
    {
        const Vec3& position = vertices[i].position;
        float x = (position.x - centerX) * scale;
        float y = (position.y - centerY) * scale;
        float z = (position.z - centerZ) * scale;

        projected[i].x = static_cast<LONG>((client.right + client.left) * 0.5f + x - z * 0.35f);
        projected[i].y = static_cast<LONG>((client.bottom + client.top) * 0.5f - y - z * 0.20f);
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

    ReleaseDC(hwnd, dc);
}

void Renderer::present()
{
    if (_window != nullptr)
        InvalidateRect(static_cast<HWND>(_window), nullptr, FALSE);
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

    if (hwnd != nullptr)
        DestroyWindow(hwnd);
}

}
