"""Gene Python MMD renderer.

Independent PMX viewer: no Blender, no Babylon and no native Gene renderer.
The first target is a stable, complete textured PMX render. It deliberately
disables back-face culling and renders every material index range so geometry
cannot disappear simply because a face is wound the opposite way.
"""
from __future__ import annotations
import math, os, sys
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
in vec3 position; in vec3 normal; in vec2 uv; in vec4 diffuse;
out vec2 v_uv; out vec3 v_normal; out vec4 v_color;
uniform mat4 u_model; uniform mat4 u_view; uniform mat4 u_proj;
void main(){ vec4 world=u_model*vec4(position,1.0); v_uv=uv; v_normal=mat3(u_model)*normal; v_color=diffuse; gl_Position=u_proj*u_view*world; }
"""
FRAGMENT = """
#version 330
in vec2 v_uv; in vec3 v_normal; in vec4 v_color; out vec4 fragColor;
uniform sampler2D u_texture; uniform int u_has_texture; uniform vec4 u_material; uniform vec3 u_light;
void main(){ vec4 tex=u_has_texture==1?texture(u_texture,v_uv):vec4(1.0); vec3 n=normalize(v_normal); float l=.40+.60*max(dot(n,normalize(u_light)),0.0); vec4 c=tex*u_material*v_color; if(c.a<.003) discard; fragColor=vec4(c.rgb*l,c.a); }
"""

def perspective(fov, aspect, near, far):
    f=1.0/math.tan(math.radians(fov)/2.0); m=np.zeros((4,4),dtype=np.float32)
    m[0,0]=f/aspect; m[1,1]=f; m[2,2]=(far+near)/(near-far); m[2,3]=(2*far*near)/(near-far); m[3,2]=-1
    return m

def look_at(eye,target,up=(0,1,0)):
    eye=np.asarray(eye,dtype=np.float32); target=np.asarray(target,dtype=np.float32); up=np.asarray(up,dtype=np.float32)
    f=target-eye; f/=np.linalg.norm(f) or 1; s=np.cross(f,up); s/=np.linalg.norm(s) or 1; u=np.cross(s,f)
    m=np.eye(4,dtype=np.float32); m[0,:3],m[1,:3],m[2,:3]=s,u,-f; m[:3,3]=-m[:3,:3]@eye; return m

def field(obj,*names,default=None):
    for name in names:
        if hasattr(obj,name): return getattr(obj,name)
        if isinstance(obj,dict) and name in obj: return obj[name]
    return default

def rgba(value,default=(1,1,1,1)):
    try:
        a=list(value); a += [1.0]*(4-len(a)); return np.asarray(a[:4],dtype=np.float32)
    except Exception: return np.asarray(default,dtype=np.float32)

class MaterialBatch:
    def __init__(self,program,vertices,indices,material,texture_path):
        self.program=program; self.material=rgba(field(material,"diffuse_color","diffuse",default=(1,1,1,1)))
        self.material[3]=float(field(material,"alpha",default=self.material[3])); pos=[]; nor=[]; uv=[]; col=[]
        for index in indices:
            v=vertices[index]; pos.extend(field(v,"position",default=(0,0,0))); nor.extend(field(v,"normal",default=(0,1,0))); uv.extend(field(v,"uv",default=(0,0))); col.extend((1,1,1,1))
        self.vlist=program.vertex_list(len(indices),position=("f",pos),normal=("f",nor),uv=("f",uv),diffuse=("f",col))
        self.texture=None
        if texture_path and texture_path.exists():
            try:
                image=Image.open(texture_path).convert("RGBA").transpose(Image.Transpose.FLIP_TOP_BOTTOM)
                data=pyglet.image.ImageData(image.width,image.height,"RGBA",image.tobytes(),pitch=image.width*4)
                self.texture=data.get_texture()
            except Exception as exc: print(f"  texture warning: {texture_path}: {exc}")
    def draw(self):
        self.program["u_has_texture"]=1 if self.texture else 0
        if self.texture: self.program["u_texture"]=self.texture
        self.vlist.draw(gl.GL_TRIANGLES)

class GeneWindow(pyglet.window.Window):
    def __init__(self,pmx_path):
        super().__init__(width=1280,height=800,caption="Gene Python MMD Renderer",resizable=True,vsync=True)
        self.program=ShaderProgram(Shader(VERTEX,"vertex"),Shader(FRAGMENT,"fragment")); self.model_matrix=np.eye(4,dtype=np.float32)
        self.camera_yaw=0.0; self.camera_pitch=math.radians(8); self.camera_distance=35.0; self.target=np.array([0,10,0],dtype=np.float32); self.drag=False; self.batches=[]
        self.load(pmx_path)
    def load(self,path):
        print("========================================\n Gene Python MMD Renderer\n========================================\nPMX:",path)
        model=pmx_reader.read_from_file(str(path)); vertices=model.vertices; faces=list(model.faces); materials=model.materials
        print("PMX loaded successfully."); print("Version:",field(model,"version",default="?")); print("Vertices:",len(vertices)); print("Faces:",len(faces)); print("Materials:",len(materials)); print("Bones:",len(field(model,"bones",default=[]))); print("Morphs:",len(field(model,"morphs",default=[])))
        cursor=0; textures=field(model,"textures",default=[])
        for mi,mat in enumerate(materials):
            count=int(field(mat,"vertex_count","face_count",default=0) or 0)
            if count<=0: continue
            start=cursor//3; end=min(cursor+count,len(faces)*3)//3; flat=[int(x) for f in faces[start:end] for x in f]; cursor=end*3; tex_path=None; ti=field(mat,"texture_index",default=-1)
            if isinstance(ti,int) and 0<=ti<len(textures):
                raw=str(textures[ti]).replace("\\",os.sep).replace("/",os.sep); candidate=(path.parent/raw).resolve()
                if candidate.exists(): tex_path=candidate
                else:
                    matches=list(path.parent.rglob(Path(raw).name)); tex_path=matches[0].resolve() if matches else None
            print(f"Material {mi}: indices={len(flat)} texture={tex_path or 'none'}")
            if flat: self.batches.append(MaterialBatch(self.program,vertices,flat,mat,tex_path))
        if cursor<len(faces)*3:
            flat=[int(x) for f in faces[cursor//3:] for x in f]
            if flat: self.batches.append(MaterialBatch(self.program,vertices,flat,materials[0] if materials else None,None)); print("Warning: rendered remaining unassigned faces.")
        p=np.asarray([field(v,"position",default=(0,0,0)) for v in vertices],dtype=np.float32); lo,hi=p.min(axis=0),p.max(axis=0); self.target=(lo+hi)*.5; self.camera_distance=max(float(np.max(hi-lo))*1.5,5.0)
        print("Bounds:",lo.tolist(),hi.tolist()); print("Render batches:",len(self.batches))
    def on_draw(self):
        self.clear(); gl.glEnable(gl.GL_DEPTH_TEST); gl.glDepthFunc(gl.GL_LEQUAL); gl.glDisable(gl.GL_CULL_FACE); gl.glEnable(gl.GL_BLEND); gl.glBlendFunc(gl.GL_SRC_ALPHA,gl.GL_ONE_MINUS_SRC_ALPHA)
        aspect=max(self.width/max(self.height,1),.1); cp=math.cos(self.camera_pitch); eye=self.target+np.array([math.sin(self.camera_yaw)*cp*self.camera_distance,math.sin(self.camera_pitch)*self.camera_distance,math.cos(self.camera_yaw)*cp*self.camera_distance],dtype=np.float32)
        self.program["u_model"]=self.model_matrix; self.program["u_view"]=look_at(eye,self.target); self.program["u_proj"]=perspective(45,aspect,.05,10000); self.program["u_light"]=(-.4,.8,.6)
        for batch in self.batches: self.program["u_material"]=batch.material; batch.draw()
    def on_mouse_press(self,x,y,button,modifiers): self.drag=button==pyglet.window.mouse.LEFT
    def on_mouse_release(self,x,y,button,modifiers):
        if button==pyglet.window.mouse.LEFT: self.drag=False
    def on_mouse_drag(self,x,y,dx,dy,buttons,modifiers):
        if self.drag: self.camera_yaw-=dx*.01; self.camera_pitch=max(-1.4,min(1.4,self.camera_pitch+dy*.01))
    def on_mouse_scroll(self,x,y,scroll_x,scroll_y): self.camera_distance=max(.5,min(1000,self.camera_distance*math.pow(.88,scroll_y)))
    def on_key_press(self,symbol,modifiers):
        if symbol==pyglet.window.key.ESCAPE: self.close()
        elif symbol==pyglet.window.key.R: self.camera_yaw=0; self.camera_pitch=math.radians(8)

def main():
    pmx=Path(sys.argv[1]).expanduser().resolve() if len(sys.argv)>1 else Path(__file__).resolve().parent/"jene_PSO2.pmx"
    if not pmx.exists(): print("ERROR: PMX not found:",pmx); print(r"Usage: python main.py D:\path\to\model.pmx"); input("Press Enter to close..."); return 1
    GeneWindow(pmx); pyglet.app.run(); return 0
if __name__=="__main__": raise SystemExit(main())
