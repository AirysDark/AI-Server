#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <algorithm>
#include <vector>
#include "renderer.h"

namespace gene {
static LRESULT CALLBACK GeneWndProc(HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam) {
    auto* renderer = reinterpret_cast<Renderer*>(GetWindowLongPtrW(hwnd, GWLP_USERDATA));
    if (msg == WM_CLOSE) { if (renderer) renderer->shutdown(); else DestroyWindow(hwnd); return 0; }
    if (msg == WM_DESTROY) { PostQuitMessage(0); return 0; }
    return DefWindowProcW(hwnd, msg, wParam, lParam);
}

bool Renderer::initialize(uint32_t width, uint32_t height) {
    _width=width; _height=height;
    HINSTANCE instance=GetModuleHandleW(nullptr); const wchar_t* cls=L"GeneRuntimeWindow";
    WNDCLASSW wc{}; wc.lpfnWndProc=GeneWndProc; wc.hInstance=instance; wc.lpszClassName=cls;
    wc.hCursor=LoadCursor(nullptr,IDC_ARROW); wc.hbrBackground=reinterpret_cast<HBRUSH>(COLOR_WINDOW+1); RegisterClassW(&wc);
    RECT r{0,0,(LONG)_width,(LONG)_height}; AdjustWindowRect(&r,WS_OVERLAPPEDWINDOW,FALSE);
    HWND hwnd=CreateWindowExW(0,cls,L"Gene Runtime",WS_OVERLAPPEDWINDOW,CW_USEDEFAULT,CW_USEDEFAULT,r.right-r.left,r.bottom-r.top,nullptr,nullptr,instance,nullptr);
    if(!hwnd) return false; _window=hwnd; _running=true; SetWindowLongPtrW(hwnd,GWLP_USERDATA,(LONG_PTR)this); ShowWindow(hwnd,SW_SHOW); UpdateWindow(hwnd); return true;
}
void Renderer::pollEvents(){ MSG msg{}; while(PeekMessageW(&msg,nullptr,0,0,PM_REMOVE)){ if(msg.message==WM_QUIT){_running=false;continue;} TranslateMessage(&msg);DispatchMessageW(&msg);} }
bool Renderer::running() const{return _running;}

void Renderer::draw(const Model& model) {
    if(!_window) return;
    HWND hwnd=(HWND)_window; HDC dc=GetDC(hwnd); if(!dc)return;
    RECT c{}; GetClientRect(hwnd,&c); FillRect(dc,&c,(HBRUSH)(COLOR_WINDOW+1));
    const auto& v=model.vertices(); const auto& ind=model.indices();
    if(v.empty()||ind.size()<3){ DrawTextW(dc,L"Gené Runtime\n\nNo renderable PMX geometry.",-1,&c,DT_CENTER|DT_VCENTER|DT_NOPREFIX); ReleaseDC(hwnd,dc); return; }
    float minX=v[0].position.x,maxX=minX,minY=v[0].position.y,maxY=minY,minZ=v[0].position.z,maxZ=minZ;
    for(const auto& p:v){minX=std::min(minX,p.position.x);maxX=std::max(maxX,p.position.x);minY=std::min(minY,p.position.y);maxY=std::max(maxY,p.position.y);minZ=std::min(minZ,p.position.z);maxZ=std::max(maxZ,p.position.z);}
    float cx=(minX+maxX)*.5f,cy=(minY+maxY)*.5f,cz=(minZ+maxZ)*.5f;
    float span=std::max({maxX-minX,maxY-minY,maxZ-minZ,.001f}); float scale=std::min(c.right-c.left,c.bottom-c.top)*.78f/span;
    std::vector<POINT> p(v.size());
    for(size_t i=0;i<v.size();++i){float x=(v[i].position.x-cx)*scale,y=(v[i].position.y-cy)*scale,z=(v[i].position.z-cz)*scale;p[i].x=(LONG)((c.right+c.left)*.5f+x-z*.35f);p[i].y=(LONG)((c.bottom+c.top)*.5f-y-z*.2f);}
    HPEN pen=CreatePen(PS_SOLID,1,RGB(60,60,60)); HGDIOBJ old=SelectObject(dc,pen);
    size_t tris=ind.size()/3, step=tris>30000?(tris/30000)+1:1;
    for(size_t t=0;t<tris;t+=step){uint32_t a=ind[t*3],b=ind[t*3+1],d=ind[t*3+2];if(a>=p.size()||b>=p.size()||d>=p.size())continue;MoveToEx(dc,p[a].x,p[a].y,nullptr);LineTo(dc,p[b].x,p[b].y);LineTo(dc,p[d].x,p[d].y);LineTo(dc,p[a].x,p[a].y);}
    SelectObject(dc,old);DeleteObject(pen); SetBkMode(dc,TRANSPARENT); DrawTextW(dc,L"Gené Runtime - PMX geometry",-1,&c,DT_TOP|DT_CENTER|DT_NOPREFIX); ReleaseDC(hwnd,dc);
}
void Renderer::present(){}
void Renderer::setWindowTitle(const std::string& title){if(!_window)return;int n=MultiByteToWideChar(CP_UTF8,0,title.c_str(),-1,nullptr,0);if(n<=0)return;std::wstring w((size_t)n,L'\0');MultiByteToWideChar(CP_UTF8,0,title.c_str(),-1,w.data(),n);SetWindowTextW((HWND)_window,w.c_str());}
void Renderer::shutdown(){if(_window){DestroyWindow((HWND)_window);_window=nullptr;}_running=false;}
}
