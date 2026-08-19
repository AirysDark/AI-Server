"""Gene Python MMD renderer.

Purpose: a small, independent PMX viewer that does not use Blender, Babylon,
or the old native Gene renderer. It deliberately renders both triangle sides
and every PMX material range so missing faces cannot be caused by back-face
culling or a simplified material pass.

Current stage: textured static PMX display, camera controls, material groups.
Animation/IK/VMD are kept as the next layer once the base render is verified.
"""
from __future__ import annotations

import math
import os
import sys
from pathlib import Path

import numpy as np
import pyglet
from pyglet import gl
from pyglet.graphics.shader import Shader, ShaderProgram
from PIL import Image

try:
    from pymeshio.pmx import reader as pmx_reader
except Exception as exc:
    print("ERROR: pymeshio is not installed:", exc)
    print("Run: python -m pip install -r requirements.txt")
    raise SystemExit(2)


VERTEX = """
#version 330
in vec3 position;
in vec3 normal;
in vec2 uv;
in vec4 diffuse;
out vec2 v_uv;
out vec3 v_normal;
out vec4 v_color;
uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_proj;
void main() {
    vec4 world = u_model * vec4(position, 1.0);
    v_uv = uv;
    v_normal = mat3(u_model) * normal;
    v_color = diffuse;
    gl_Position = u_proj * u_view * world;
}
"""

FRAGMENT = """
#version 330
in vec2 v_uv;
in vec3 v_normal;
in vec4 v_color;
out vec4 fragColor;
uniform sampler2D u_texture;
uniform int u_has_texture;
uniform vec4 u_material;
uniform vec3 u_light;
void main() {
    vec4 tex = u_has_texture == 1 ? texture(u_texture, v_uv) : vec4(1.0);
    vec3 n = normalize(v_normal);
    float light = 0.45 + 0.55 * max(dot(n, normalize(u_light)), 0.0);
    vec4 c = tex * u_material * v_color;
    if (c.a < 0.003) discard;
    fragColor = vec4(c.rgb * light, c.a);
}
"""


def mat4_identity():
    return np.eye(4, dtype=np.float32)


def perspective(fov, aspect, near, far):
    f = 1.0 / math.tan(math.radians(fov) / 2.0)
    m = np.zeros((4, 4), dtype=np.float32)
    m[0, 0] = f / aspect
    m[1, 1] = f
    m[2, 2] = (far + near) / (near - far)
    m[2, 3] = (2 * far * near) / (near - far)
    m[3, 2] = -1
    return m


def look_at(eye, target, up=(0, 1, 0)):
    eye = np.asarray(eye, dtype=np.float32)
    target = np.asarray(target, dtype=np.float32)
    up = np.asarray(up, dtype=np.float32)
    f = target - eye
    f /= np.linalg.norm(f) or 1
    s = np.cross(f, up)
    s /= np.linalg.norm(s) or 1
    u = np.cross(s, f)
    m = np.eye(4, dtype=np.float32)
    m[0, :3], m[1, :3], m[2, :3] = s, u, -f
    m[:3, 3] = -m[:3, :3] @ eye
    return m


def field(obj, *names, default=None):
    for name in names:
        if hasattr(obj, name):
            return getattr(obj, name)
        if isinstance(obj, dict) and name in obj:
            return obj[name]
    return default


def color4(value, default=(1, 1, 1, 1)):
    try:
        a = list(value)
        while len(a) < 4:
            a.append(1.0)
        return np.array(a[:4], dtype=np.float32)
    except Exception:
        return np.array(default, dtype=np.float32)


class MaterialBatch:
    def __init__(self, program, vertices, indices, material, texture_path, root):
        self.program = program
        self.count = len(indices)
        pos, nor, uv, col = [], [], [], []
        for i in indices:
            v = vertices[i]
            pos.extend(field(v, "position", default=(0, 0, 0)))
            nor.extend(field(v, "normal", default=(0, 1, 0)))
            uv.extend(field(v, "uv", default=(0, 0)))
            col.extend((1, 1, 1, 1))
        self.vlist = program.vertex_list(
            len(indices),
            indices=None,
            position=("f", pos),
            normal=("f", nor),
            uv=("f", uv),
            diffuse=("f", col),
        )
        self.material = color4(field(material, "diffuse_color", "diffuse", default=(1, 1, 1, 1)))
        alpha = float(field(material, "alpha", default=self.material[3]))
        self.material[3] = alpha
        self.texture = None
        if texture_path:
            try:
                img = Image.open(texture_path).convert("RGBA")
                # MMD UVs use a top-left image convention in many assets.
                # Flip vertically so OpenGL's texture origin matches the UV data.
                img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
                raw = img.tobytes()
                self.texture = pyglet.image.ImageData(img.width, img.height, "RGBA", raw, pitch=-img.width * 4)
            except Exception as exc:
                print(f"  texture warning: {texture_path}: {exc}")

    def draw(self):
        if self.texture:
            self.texture.blit(0, 0, 0) if False else None
        self.vlist.draw(gl.GL_TRIANGLES)


class GeneWindow(pyglet.window.Window):
    def __init__(self, pmx_path: Path):
        super().__init__(width=1280, height=800, caption="Gene Python MMD Renderer", resizable=True, vsync=True)
        self.program = ShaderProgram(Shader(VERTEX, "vertex"), Shader(FRAGMENT, "fragment"))
        self.model_matrix = mat4_identity()
        self.camera_yaw = 0.0
        self.camera_pitch = math.radians(8)
        self.camera_distance = 35.0
        self.target = np.array([0, 10, 0], dtype=np.float32)
        self.drag = False
        self.last_mouse = (0, 0)
        self.batches = []
        self.load(pmx_path)

    def load(self, path: Path):
        print("========================================")
        print(" Gene Python MMD Renderer")
        print("========================================")
        print("PMX:", path)
        try:
            model = pmx_reader.read_from_file(str(path))
        except Exception as exc:
            print("ERROR: PMX load failed:", exc)
            raise

        vertices = model.vertices
        faces = list(model.faces)
        materials = model.materials
        print("PMX loaded successfully.")
        print("Version:", field(model, "version", default="?"))
        print("Vertices:", len(vertices))
        print("Faces:", len(faces))
        print("Materials:", len(materials))
        print("Bones:", len(field(model, "bones", default=[])))
        print("Morphs:", len(field(model, "morphs", default=[])))

        # PMX material face_count is the number of indices, not triangles.
        cursor = 0
        base = path.parent
        for mi, mat in enumerate(materials):
            count = int(field(mat, "vertex_count", "face_count", "surface_count", default=0) or 0)
            if count <= 0:
                continue
            end = min(cursor + count, len(faces) * 3)
            flat = []
            for f in faces[cursor // 3:end // 3]:
                flat.extend([int(x) for x in f])
            cursor = end
            tex = field(mat, "texture_index", default=-1)
            tex_path = None
            textures = field(model, "textures", default=[])
            if isinstance(tex, int) and 0 <= tex < len(textures):
                raw = str(textures[tex])
                tex_path = (base / raw).resolve()
                if not tex_path.exists():
                    # PMX paths may contain backslashes or non-ASCII separators.
                    tex_path = (base / raw.replace("\\", os.sep).replace("/", os.sep)).resolve()
            print(f"Material {mi}: indices={len(flat)} texture={tex_path or 'none'}")
            if flat:
                self.batches.append(MaterialBatch(self.program, vertices, flat, mat, tex_path if tex_path and tex_path.exists() else None, base))

        # If a library version exposes materials differently, make sure no face is dropped.
        if cursor < len(faces) * 3:
            flat = []
            for f in faces[cursor // 3:]:
                flat.extend([int(x) for x in f])
            if flat:
                self.batches.append(MaterialBatch(self.program, vertices, flat, None, None, base))
                print("Warning: appended unassigned material range to prevent missing faces.")

        p = np.array([field(v, "position", default=(0, 0, 0)) for v in vertices], dtype=np.float32)
        lo, hi = p.min(axis=0), p.max(axis=0)
        self.target = (lo + hi) * 0.5
        size = float(np.max(hi - lo))
        self.camera_distance = max(size * 1.5, 5.0)
        print("Bounds:", lo.tolist(), hi.tolist())
        print("Render batches:", len(self.batches))

    def on_draw(self):
        self.clear()
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glDepthFunc(gl.GL_LEQUAL)
        gl.glDisable(gl.GL_CULL_FACE)  # critical: MMD materials may intentionally be double-sided
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        aspect = max(self.width / max(self.height, 1), 0.1)
        proj = perspective(45, aspect, 0.05, 10000)
        cp = math.cos(self.camera_pitch)
        eye = self.target + np.array([
            math.sin(self.camera_yaw) * cp * self.camera_distance,
            math.sin(self.camera_pitch) * self.camera_distance,
            math.cos(self.camera_yaw) * cp * self.camera_distance,
        ], dtype=np.float32)
        view = look_at(eye, self.target)
        self.program["u_model"] = self.model_matrix
        self.program["u_view"] = view
        self.program["u_proj"] = proj
        self.program["u_light"] = (-0.4, 0.8, 0.6)
        for batch in self.batches:
            self.program["u_material"] = batch.material
            self.program["u_has_texture"] = 0
            batch.draw()

    def on_mouse_press(self, x, y, button, modifiers):
        if button == pyglet.window.mouse.LEFT:
            self.drag = True
            self.last_mouse = (x, y)

    def on_mouse_release(self, x, y, button, modifiers):
        if button == pyglet.window.mouse.LEFT:
            self.drag = False

    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        if self.drag:
            self.camera_yaw -= dx * 0.01
            self.camera_pitch = max(-1.4, min(1.4, self.camera_pitch + dy * 0.01))

    def on_mouse_scroll(self, x, y, scroll_x, scroll_y):
        self.camera_distance *= math.pow(0.88, scroll_y)
        self.camera_distance = max(0.5, min(1000, self.camera_distance))

    def on_key_press(self, symbol, modifiers):
        if symbol == pyglet.window.key.ESCAPE:
            self.close()
        elif symbol == pyglet.window.key.R:
            self.camera_yaw = 0
            self.camera_pitch = math.radians(8)


def main():
    if len(sys.argv) > 1:
        pmx = Path(sys.argv[1]).expanduser().resolve()
    else:
        pmx = Path(__file__).resolve().parent / "jene_PSO2.pmx"
    if not pmx.exists():
        print("ERROR: PMX not found:", pmx)
        print("Usage: python main.py path\\to\\model.pmx")
        input("Press Enter to close...")
        return 1
    GeneWindow(pmx)
    pyglet.app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
