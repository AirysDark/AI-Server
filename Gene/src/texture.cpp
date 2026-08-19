#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <wincodec.h>
#include <combaseapi.h>
#include <filesystem>
#include <algorithm>
#include <cctype>
#include <string>
#include "texture.h"

#pragma comment(lib, "windowscodecs.lib")

namespace gene {
namespace {
struct ComInit {
    HRESULT hr;
    ComInit():hr(CoInitializeEx(nullptr,COINIT_MULTITHREADED)){}
    ~ComInit(){if(SUCCEEDED(hr))CoUninitialize();}
};

static std::wstring widePath(const std::string& path)
{
    int n=MultiByteToWideChar(CP_UTF8,0,path.c_str(),-1,nullptr,0);
    if(n<=0)return{};
    std::wstring w(size_t(n),L'\0');
    MultiByteToWideChar(CP_UTF8,0,path.c_str(),-1,w.data(),n);
    w.resize(size_t(n-1));
    return w;
}

static bool mmdUsesImageAlpha(const std::string& path)
{
    std::string ext=std::filesystem::path(path).extension().string();
    std::transform(ext.begin(),ext.end(),ext.begin(),[](unsigned char c){return char(std::tolower(c));});
    // Match MMD Tools: BMP alpha is ignored. JPEG has no meaningful alpha.
    if(ext==".bmp" || ext==".jpg" || ext==".jpeg") return false;
    return true;
}
}

bool TextureLoader::load(const std::string&path,TextureInfo&info)
{
    info={};
    info.path=path;
    info.useAlpha=mmdUsesImageAlpha(path);
    if(!std::filesystem::exists(path))return false;

    ComInit com;
    if(com.hr!=S_OK&&com.hr!=S_FALSE)return false;

    IWICImagingFactory*factory=nullptr;
    HRESULT hr=CoCreateInstance(CLSID_WICImagingFactory,nullptr,CLSCTX_INPROC_SERVER,IID_PPV_ARGS(&factory));
    if(FAILED(hr))return false;

    IWICBitmapDecoder*decoder=nullptr;
    std::wstring w=widePath(path);
    hr=factory->CreateDecoderFromFilename(w.c_str(),nullptr,GENERIC_READ,WICDecodeMetadataCacheOnLoad,&decoder);
    if(FAILED(hr)){factory->Release();return false;}

    IWICBitmapFrameDecode*frame=nullptr;
    hr=decoder->GetFrame(0,&frame);
    if(FAILED(hr)){decoder->Release();factory->Release();return false;}

    IWICFormatConverter*converter=nullptr;
    hr=factory->CreateFormatConverter(&converter);
    if(SUCCEEDED(hr))
        hr=converter->Initialize(frame,GUID_WICPixelFormat32bppRGBA,WICBitmapDitherTypeNone,nullptr,0.0,WICBitmapPaletteTypeCustom);

    UINT width=0,height=0;
    if(SUCCEEDED(hr))hr=converter->GetSize(&width,&height);
    if(FAILED(hr)||!width||!height){
        if(converter)converter->Release();
        frame->Release();
        decoder->Release();
        factory->Release();
        return false;
    }

    std::vector<uint8_t>pixels(size_t(width)*height*4);
    hr=converter->CopyPixels(nullptr,width*4,static_cast<UINT>(pixels.size()),pixels.data());
    if(SUCCEEDED(hr)){
        if(!info.useAlpha)
            for(size_t i=3;i<pixels.size();i+=4)pixels[i]=255;
        info.width=width;
        info.height=height;
        info.pixels=std::move(pixels);
    }

    converter->Release();
    frame->Release();
    decoder->Release();
    factory->Release();
    return SUCCEEDED(hr);
}
}
