#include "renderer.h"
#include <iostream>

namespace gene {
bool Renderer::initialize(uint32_t, uint32_t) { return true; }
void Renderer::draw(const Model& model) { if (!model.loaded()) return; }
void Renderer::setWindowTitle(const std::string& title) { std::cout << title << '\n'; }
}
