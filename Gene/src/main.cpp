#include <chrono>
#include <exception>
#include <filesystem>
#include <iostream>
#include <string>
#include <thread>
#include "gene_model.h"
#include "animation.h"
#include "renderer.h"

int main(int argc, char** argv)
{
    std::cout << "========================================\n"
              << " Gene Runtime - VS2022\n"
              << "========================================\n\n";

    gene::Model model;
    std::filesystem::path pmxPath = argc > 1 ? std::filesystem::path(argv[1]) : std::filesystem::path("jene_PSO2.pmx");
    std::cout << "PMX: " << pmxPath.string() << "\n";

    if (!std::filesystem::exists(pmxPath)) {
        std::cerr << "ERROR: PMX file was not found.\n";
        std::cerr << "Expected: " << std::filesystem::absolute(pmxPath).string() << "\n\n";
        std::cerr << "Put jene_PSO2.pmx beside GeneRuntime.exe.\nPress Enter to close...";
        std::cin.get();
        return 1;
    }

    if (!model.loadPmx(pmxPath.string())) {
        std::cerr << "ERROR: PMX file exists but could not be loaded.\n";
        if (!model.error().empty()) std::cerr << "Reason: " << model.error() << "\n";
        std::cerr << "\nPress Enter to close...";
        std::cin.get();
        return 1;
    }

    model.loadTextures(pmxPath.parent_path().empty() ? std::filesystem::current_path().string() : pmxPath.parent_path().string());

    std::cout << "PMX loaded successfully.\n"
              << "Version:   " << model.pmxVersion() << "\n"
              << "Vertices:  " << model.vertexCount() << "\n"
              << "Indices:   " << model.indexCount() << "\n"
              << "Materials: " << model.materialCount() << "\n"
              << "Textures:  " << model.textures().size() << "\n"
              << "Bones:     " << model.bones().size() << "\n"
              << "Morphs:    " << model.morphs().size() << "\n\n";

    // Optional test hook: GeneRuntime.exe model.pmx "Morph Name" 1.0
    if (argc >= 4) {
        try {
            const float value = std::stof(argv[3]);
            if (!model.setMorphWeight(argv[2], value))
                std::cerr << "WARNING: Morph not found: " << argv[2] << "\n";
            else
                std::cout << "Morph active: " << argv[2] << " = " << value << "\n";
        } catch (const std::exception&) {
            std::cerr << "WARNING: Invalid morph value: " << argv[3] << "\n";
        }
    }

    gene::AnimationPlayer player;
    player.add({"idle", 120, 30.0f});
    player.add({"talking", 60, 30.0f});
    player.add({"thinking", 90, 30.0f});
    player.play("idle");

    gene::Renderer renderer;
    if (!renderer.initialize(1280, 720)) {
        std::cerr << "ERROR: Failed to create Gene window.\nPress Enter to close...";
        std::cin.get();
        return 1;
    }
    renderer.setWindowTitle("Gene Runtime");

    auto previous = std::chrono::steady_clock::now();
    while (renderer.running()) {
        auto now = std::chrono::steady_clock::now();
        float delta = std::chrono::duration<float>(now - previous).count();
        previous = now;

        renderer.pollEvents();
        player.update(delta);
        renderer.draw(model);
        std::this_thread::sleep_for(std::chrono::milliseconds(16));
    }

    renderer.shutdown();
    return 0;
}
