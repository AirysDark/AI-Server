#include <iostream>
#include <exception>
#include "gene_model.h"
#include "animation.h"
#include "renderer.h"

static void waitForExit() {
    std::cout << "\nPress Enter to close..." << std::flush;
    std::cin.get();
}

int main(int argc, char** argv) {
    try {
        std::cout << "========================================\n";
        std::cout << " Gené Runtime - VS2022\n";
        std::cout << "========================================\n\n";

        gene::Model model;

        if (argc > 1) {
            std::cout << "Loading PMX: " << argv[1] << "\n";
            if (!model.loadPmx(argv[1])) {
                std::cerr << "ERROR: Failed to load PMX.\n";
                waitForExit();
                return 1;
            }
            std::cout << "PMX loaded successfully.\n";
            std::cout << "Version:    " << model.pmxVersion() << "\n";
            std::cout << "Vertices:   " << model.vertexCount() << "\n";
            std::cout << "Indices:    " << model.indexCount() << "\n";
            std::cout << "Materials:  " << model.materialCount() << "\n";
            std::cout << "Bones:      " << model.bones().size() << "\n";
            std::cout << "Morphs:     " << model.morphs().size() << "\n";
        } else {
            std::cout << "No PMX supplied.\n";
            std::cout << "Usage: GeneRuntime.exe <path-to-gene.pmx>\n";
        }

        gene::AnimationPlayer player;
        player.add({"idle", 120, 30.0f});
        player.add({"talking", 60, 30.0f});
        player.add({"thinking", 90, 30.0f});
        player.play("idle");

        gene::Renderer renderer;
        if (!renderer.initialize(800, 600)) {
            std::cerr << "ERROR: Renderer initialization failed.\n";
            waitForExit();
            return 2;
        }
        renderer.setWindowTitle("Gené Runtime");
        renderer.draw(model);

        std::cout << "\nRuntime initialized successfully.\n";
        std::cout << "Renderer is currently a development stub; the 3D window is the next milestone.\n";
        waitForExit();
        return 0;
    }
    catch (const std::exception& e) {
        std::cerr << "FATAL ERROR: " << e.what() << "\n";
        waitForExit();
        return 10;
    }
    catch (...) {
        std::cerr << "FATAL ERROR: Unknown exception.\n";
        waitForExit();
        return 11;
    }
}
