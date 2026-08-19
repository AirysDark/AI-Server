#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include "renderer.h"

namespace gene {

static LRESULT CALLBACK GeneWndProc(HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam) {
    auto* renderer = reinterpret_cast<Renderer*>(GetWindowLongPtrW(hwnd, GWLP_USERDATA));
    switch (msg) {
    case WM_CLOSE:
        if (renderer) renderer->shutdown();
        else DestroyWindow(hwnd);
        return 0;
    case WM_DESTROY:
        PostQuitMessage(0);
        return 0;
    default:
        return DefWindowProcW(hwnd, msg, wParam, lParam);
    }
}

bool Renderer::initialize(uint32_t width, uint32_t height) {
    _width = width;
    _height = height;

    HINSTANCE instance = GetModuleHandleW(nullptr);
    const wchar_t* className = L"GeneRuntimeWindow";

    WNDCLASSW wc{};
    wc.lpfnWndProc = GeneWndProc;
    wc.hInstance = instance;
    wc.lpszClassName = className;
    wc.hCursor = LoadCursor(nullptr, IDC_ARROW);
    wc.hbrBackground = reinterpret_cast<HBRUSH>(COLOR_WINDOW + 1);

    RegisterClassW(&wc);

    RECT rect{0, 0, static_cast<LONG>(_width), static_cast<LONG>(_height)};
    AdjustWindowRect(&rect, WS_OVERLAPPEDWINDOW, FALSE);

    HWND hwnd = CreateWindowExW(
        0, className, L"Gené Runtime",
        WS_OVERLAPPEDWINDOW,
        CW_USEDEFAULT, CW_USEDEFAULT,
        rect.right - rect.left,
        rect.bottom - rect.top,
        nullptr, nullptr, instance, nullptr);

    if (!hwnd) return false;

    _window = hwnd;
    _running = true;
    SetWindowLongPtrW(hwnd, GWLP_USERDATA, reinterpret_cast<LONG_PTR>(this));
    ShowWindow(hwnd, SW_SHOW);
    UpdateWindow(hwnd);
    return true;
}

void Renderer::pollEvents() {
    MSG msg{};
    while (PeekMessageW(&msg, nullptr, 0, 0, PM_REMOVE)) {
        if (msg.message == WM_QUIT) {
            _running = false;
            continue;
        }
        TranslateMessage(&msg);
        DispatchMessageW(&msg);
    }
}

bool Renderer::running() const { return _running; }

void Renderer::draw(const Model&) {
    if (!_window) return;
    HWND hwnd = static_cast<HWND>(_window);
    PAINTSTRUCT ps{};
    HDC dc = BeginPaint(hwnd, &ps);
    if (dc) {
        RECT client{};
        GetClientRect(hwnd, &client);
        FillRect(dc, &client, reinterpret_cast<HBRUSH>(COLOR_WINDOW + 1));
        SetBkMode(dc, TRANSPARENT);
        SetTextColor(dc, RGB(20, 20, 20));
        const wchar_t* text = L"Gené Runtime\n\nPMX model loaded.\n3D renderer next.";
        DrawTextW(dc, text, -1, &client, DT_CENTER | DT_VCENTER | DT_NOPREFIX);
        EndPaint(hwnd, &ps);
    }
}

void Renderer::present() {
    if (_window) InvalidateRect(static_cast<HWND>(_window), nullptr, TRUE);
}

void Renderer::setWindowTitle(const std::string& title) {
    if (!_window) return;
    int length = MultiByteToWideChar(CP_UTF8, 0, title.c_str(), -1, nullptr, 0);
    if (length <= 0) return;
    std::wstring wide(static_cast<size_t>(length), L'\0');
    MultiByteToWideChar(CP_UTF8, 0, title.c_str(), -1, wide.data(), length);
    SetWindowTextW(static_cast<HWND>(_window), wide.c_str());
}

void Renderer::shutdown() {
    if (_window) {
        DestroyWindow(static_cast<HWND>(_window));
        _window = nullptr;
    }
    _running = false;
}

}
