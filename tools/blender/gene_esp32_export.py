"""Gené -> ESP32-S3 character exporter.

Run inside Blender 5.x with the Gené/MMD scene loaded.
The exporter renders selected animation Actions to numbered PNG frames
and writes an ESP32 character.json package. PNG is used as the master
export because Blender can preserve alpha; convert to RGB565/BMP later
for the final SD package if required by the target renderer.

Usage:
    1. Open the Gené .blend scene.
    2. Select the Gené armature/model.
    3. Edit ANIMATION_ACTIONS below to match the actions in the file.
    4. Run this script from Blender's Scripting workspace.
"""

import bpy
import json
import os
from pathlib import Path

CHARACTER_ID = "gene"
CHARACTER_NAME = "Gené"
DISPLAY_NAME = "ジェネ"
OUTPUT_SIZE = (320, 480)
FPS = 15
OUTPUT_ROOT = Path(bpy.path.abspath("//gene_esp32"))

# Map our AI animation names to Blender Action names.
# Replace the right-hand values with the actual Action names in the scene.
ANIMATION_ACTIONS = {
    "idle": "idle",
    "blink": "blink",
    "talking": "talking",
    "thinking": "thinking",
    "happy": "happy",
    "excited": "excited",
    "curious": "curious",
    "surprised": "surprised",
    "sad": "sad",
    "angry": "angry",
    "sleepy": "sleepy",
    "greeting": "greeting",
    "confused": "confused",
    "offline": "idle",
}


def find_armature():
    for obj in bpy.context.selected_objects:
        if obj.type == 'ARMATURE':
            return obj
    for obj in bpy.context.scene.objects:
        if obj.type == 'ARMATURE':
            return obj
    return None


def action_by_name(name):
    return bpy.data.actions.get(name)


def render_action(armature, action, animation_name, out_dir):
    armature.animation_data_create()
    armature.animation_data.action = action
    start, end = map(int, action.frame_range)
    scene = bpy.context.scene
    scene.render.resolution_x = OUTPUT_SIZE[0]
    scene.render.resolution_y = OUTPUT_SIZE[1]
    scene.render.resolution_percentage = 100
    scene.render.fps = FPS
    scene.render.image_settings.file_format = 'PNG'
    scene.render.film_transparent = True
    out_dir.mkdir(parents=True, exist_ok=True)

    for frame in range(start, end + 1):
        scene.frame_set(frame)
        scene.render.filepath = str(out_dir / f"frame_{frame - start:04d}.png")
        bpy.ops.render.render(write_still=True)


def main():
    armature = find_armature()
    if not armature:
        raise RuntimeError("No armature found. Select the Gené armature before running the exporter.")

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    animations = {}
    missing = []

    for export_name, action_name in ANIMATION_ACTIONS.items():
        action = action_by_name(action_name)
        if not action:
            missing.append({"animation": export_name, "action": action_name})
            continue
        render_action(armature, action, export_name, OUTPUT_ROOT / export_name)
        animations[export_name] = export_name

    manifest = {
        "id": CHARACTER_ID,
        "name": CHARACTER_NAME,
        "display_name": DISPLAY_NAME,
        "renderer": "cartoon_frames",
        "resolution": list(OUTPUT_SIZE),
        "fps": FPS,
        "animations": animations,
        "missing_actions": missing,
        "source": "Blender/MMD scene",
    }
    (OUTPUT_ROOT / "character.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Gené ESP32 export complete: {OUTPUT_ROOT}")
    if missing:
        print("Missing Blender Actions:")
        for item in missing:
            print(f"  {item['animation']} <- {item['action']}")


if __name__ == "__main__":
    main()
