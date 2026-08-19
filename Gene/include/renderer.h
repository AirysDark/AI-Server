#pragma once
#include <cstdint>
#include <string>
#include <vector>
#include "gene_model.h"
#include "texture.h"

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
                              const TextureInfo* texture, float zBias);

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
    float _modelScale = 1.0f;
};
}
