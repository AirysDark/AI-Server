#pragma once
#include <cstdint>
#include <string>
#include "gene_model.h"

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

    uint32_t _width = 1280;
    uint32_t _height = 720;
    uint32_t _bufferWidth = 0;
    uint32_t _bufferHeight = 0;
    bool _running = false;
    void* _window = nullptr;
    void* _backBufferDC = nullptr;
    void* _backBufferBitmap = nullptr;
    void* _backBufferOldBitmap = nullptr;
};
}
