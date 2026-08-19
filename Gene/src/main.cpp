#include <iostream>
#include "gene_model.h"
#include "animation.h"
#include "renderer.h"

int main(int argc, char** argv) {
    std::cout << "Gené Runtime - VS2022\n";
    gene::Model model;
    if (argc > 1) {
        if (!model.loadPmx(argv[1])) {
            std::cerr << "Failed to open PMX: " << argv[1] << '\n';
            return 1;
        }
        std::cout << "PMX header loaded successfully.\n";
    } else {
        std::cout << "Usage: GeneRuntime.exe <path-to-gene.pmx>\n";
    }

    gene::AnimationPlayer player;
    player.add({"idle", 120, 30.0f});
    player.add({"talking", 60, 30.0f});
    player.add({"thinking", 90, 30.0f});
    player.play("idle");

    gene::Renderer renderer;
    renderer.initialize();
    renderer.setWindowTitle("Gené Runtime");
    renderer.draw(model);
    return 0;
}
