#include <chrono>
#include <iostream>
#include <thread>
#include "gene_model.h"
#include "animation.h"
#include "renderer.h"

int main(int argc, char** argv) {
    std::cout << "========================================\n"
              << " Gene Runtime - VS2022\n"
              << "========================================\n\n";

    gene::Model model;
    if (argc > 1) {
        std::cout << "Loading PMX: " << argv[1] << "\n";
        if (!model.loadPmx(argv[1])) {
            std::cerr << "Failed to load PMX.\n";
            std::cout << "Press Enter to close...\n";
            std::cin.get();
            return 1;
        }
        std::cout << "PMX loaded successfully.\n";
        std::cout << "Version:  " << model.pmxVersion() << "\n";
        std::cout << "Vertices: " << model.vertexCount() << "\n";
        std::cout << "Indices:  " << model.indexCount() << "\n";
        std::cout << "Materials:" << model.materialCount() << "\n";
        std::cout << "Bones:    " << model.bones().size() << "\n";
        std::cout << "Morphs:   " << model.morphs().size() << "\n\n";
    } else {
        std::cout << "No PMX supplied. Starting empty Gene runtime.\n\n";
    }

    gene::AnimationPlayer player;
    player.add({"idle", 120, 30.0f});
    player.add({"talking", 60, 30.0f});
    player.add({"thinking", 90, 30.0f});
    player.play("idle");

    gene::Renderer renderer;
    if (!renderer.initialize(1280, 720)) {
        std::cerr << "Failed to create Gene window.\n";
        std::cout << "Press Enter to close...\n";
        std::cin.get();
        return 1;
    }
    renderer.setWindowTitle("Gene Runtime");

    auto previous = std::chrono::steady_clock::now();
    while (renderer.running()) {
        const auto now = std::chrono::steady_clock::now();
        const float delta = std::chrono::duration<float>(now - previous).count();
        previous = now;

        renderer.pollEvents();
        player.update(delta);
        renderer.draw(model);
        renderer.present();
        std::this_thread::sleep_for(std::chrono::milliseconds(16));
    }

    renderer.shutdown();
    return 0;
}
