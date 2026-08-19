# Gené Runtime

Standalone Visual Studio 2022 C++20 project for the custom Gené character engine.

This project intentionally does not depend on Blender or an MMD application. The runtime is being built around the original PMX model format and its textures, with a lightweight animation system designed to eventually produce/play optimized character assets for the ESP32-S3.

## Open in Visual Studio 2022

Open `GeneRuntime.sln`.

Configurations:

- Debug | x64
- Release | x64

## Current milestone

The first milestone validates that a PMX file can be opened and recognized as a PMX file, and provides the initial model, texture, animation and renderer interfaces.

Example:

`GeneRuntime.exe "C:\\path\\to\\jene_PSO2.pmx"`

The renderer is intentionally a stub at this stage. The next implementation step is the PMX geometry/material/bone/morph decoder, followed by the real Windows renderer.
