"""Gene Python MMD renderer using pymeshio 3.0.1."""
from __future__ import annotations
import math, os, sys
from pathlib import Path
import numpy as np
import pyglet
from pyglet import gl
from pyglet.graphics.shader import Shader, ShaderProgram
from PIL import Image
from pymeshio.pmx import reader as pmx_reader

VERTEX="""#version 330
in vec3 position; in vec3 normal; in vec2 uv; in vec4 diffuse;
out vec2 v_uv; out vec3 v_normal; out vec4 v_color;
uniform mat4 u_model; uniform mat4 u_view; uniform mat4 u_proj;
void main(){vec4 w=u_model*vec4(position,1.0);v_uv=uv;v_normal=mat3(u_model)*normal;v_color=diffuse;gl_Position=u_proj*u_view*w;}"""
FRAGMENT="""#version 330
in vec2 v_uv;in vec3 v_normal;in vec4 v_color;out vec4 fragColor;
uniform sampler2D u_texture;uniform int u_has_texture;uniform vec4 u_material;uniform vec3 u_light;
void main(){vec4 t=u_has_texture==1?texture(u_texture,v_uv):vec4(1.0);vec3 n=normalize(v_normal);float l=.40+.60*max(dot(n,normalize(u_light)),0.0);vec4 c=t*u_material*v_color;if(c.a<.003)discard;fragColor=vec4(c.rgb*l,c.a);}"""

def perspective(fov,aspect,near,far):
    f=1/math.tan(math.radians(fov)/2);m=np.zeros((4,4),dtype=np.float32);m[0,0]=f/aspect;m[1,1]=f;m[2,2]=(far+near)/(near-far);m[2,3]=2*far*near/(near-far);m[3,2]=-1;return m

def look_at(eye,target,up=(0,1,0)):
    eye=np.asarray(eye,np.float32);target=np.asarray(target,np.float32);up=np.asarray(up,np.float32);f=target-eye;f/=np.linalg.norm(f) or 1;s=np.cross(f,up);s/=np.linalg.norm(s) or 1;u=np.cross(s,f);m=np.eye(4,dtype=np.float32);m[0,:3],m[1,:3],m[2,:3]=s,u,-f;m[:3,3]=-m[:3,:3]@eye;return m

def field(o,*names,default=None):
    for n in names:
        if hasattr(o,n):return getattr(o,n)
    return default

def vec3(v,default=(0,0,0)):
    if v is None:return default
    try:
        if hasattr(v,"x") and hasattr(v,"y") and hasattr(v,"z"):return (float(v.x),float(v.y),float(v.z))
        a=list(v);return (float(a[0]),float(a[1]),float(a[2]))
    except Exception:return default

def vec2(v,default=(0,0)):
    if v is None:return default
    try:
        if hasattr(v,"x") and hasattr(v,"y"):return (float(v.x),float(v.y))
        a=list(v);return (float(a[0]),float(a[1]))
    except Exception:return default

def rgba(v):
    try:a=[float(x) for x in v];a += [1]*(4-len(a));return np.asarray(a[:4],np.float32)
    except:return np.ones(4,np.float32)

def mat4_uniform(program,name,value):
    """pyglet expects a flat 16-value sequence for mat4 uniforms."""
    a=np.asarray(value,dtype=np.float32).reshape(16)
    program[name]=tuple(float(x) for x in a)

class MaterialBatch:
    def __init__(self,program,vertices,indices,material,texture_path):
        self.program=program;self.material=rgba(field(material,"diffuse_color","diffuse",default=(1,1,1,1)));self.material[3]=float(field(material,"alpha",default=self.material[3]));p=[];n=[];u=[]
        for i in indices:
            v=vertices[i];p.extend(vec3(field(v,"position")));n.extend(vec3(field(v,"normal"),(0,1,0)));u.extend(vec2(field(v,"uv")))
        self.vlist=program.vertex_list(len(indices),gl.GL_TRIANGLES,position=("f",p),normal=("f",n),uv=("f",u),diffuse=("f",[1.0]*len(indices)*4));self.texture=None
        if texture_path and texture_path.exists():
            try:
                im=Image.open(texture_path).convert("RGBA").transpose(Image.Transpose.FLIP_TOP_BOTTOM);d=pyglet.image.ImageData(im.width,im.height,"RGBA",im.tobytes(),pitch=im.width*4);self.texture=d.get_texture()
            except Exception as e:print(" texture warning:",e)
    def draw(self):
        self.program["u_has_texture"]=1 if self.texture else 0
        if self.texture:self.program["u_texture"]=self.texture
        self.vlist.draw(gl.GL_TRIANGLES)

class GeneWindow(pyglet.window.Window):
    def __init__(self,path):
        super().__init__(width=1280,height=800,caption="Gene Python MMD Renderer",resizable=True,vsync=True);self.program=ShaderProgram(Shader(VERTEX,"vertex"),Shader(FRAGMENT,"fragment"));self.model=np.eye(4,dtype=np.float32);self.yaw=0;self.pitch=math.radians(8);self.distance=35;self.target=np.array([0,10,0],np.float32);self.drag=False;self.batches=[];self.load(path)
    def load(self,path):
        print("========================================\n Gene Python MMD Renderer\n========================================\nPMX:",path);m=pmx_reader.read_from_file(str(path));v=m.vertices;idx=[int(x) for x in m.indices];mats=m.materials;tex=field(m,"textures",default=[])
        print("PMX loaded successfully.\nVersion:",m.version,"\nVertices:",len(v),"\nIndices:",len(idx),"\nMaterials:",len(mats),"\nTextures:",len(tex),"\nBones:",len(m.bones),"\nMorphs:",len(m.morphs))
        cursor=0
        for mi,mat in enumerate(mats):
            count=int(field(mat,"vertex_count","face_count","index_count",default=0) or 0);count=max(0,min(count,len(idx)-cursor));part=idx[cursor:cursor+count];cursor+=count;tp=None;ti=field(mat,"texture_index",default=-1)
            if isinstance(ti,int) and 0<=ti<len(tex):
                raw=str(tex[ti]).replace("\\",os.sep).replace("/",os.sep);c=(path.parent/raw).resolve();tp=c if c.exists() else next((x.resolve() for x in path.parent.rglob(Path(raw).name)),None)
            print(f"Material {mi}: indices={len(part)} texture={tp or 'none'}")
            if len(part)>=3:self.batches.append(MaterialBatch(self.program,v,part,mat,tp))
        if cursor<len(idx):self.batches.append(MaterialBatch(self.program,v,idx[cursor:],mats[-1] if mats else None,None))
        p=np.asarray([vec3(field(x,"position")) for x in v],dtype=np.float32);lo,hi=p.min(0),p.max(0);self.target=(lo+hi)/2;self.distance=max(float(np.max(hi-lo))*1.5,5);print("Bounds:",lo.tolist(),hi.tolist());print("Render batches:",len(self.batches))
    def on_draw(self):
        self.clear();gl.glEnable(gl.GL_DEPTH_TEST);gl.glDisable(gl.GL_CULL_FACE);gl.glEnable(gl.GL_BLEND);gl.glBlendFunc(gl.GL_SRC_ALPHA,gl.GL_ONE_MINUS_SRC_ALPHA);a=max(self.width/max(self.height,1),.1);cp=math.cos(self.pitch);eye=self.target+np.array([math.sin(self.yaw)*cp*self.distance,math.sin(self.pitch)*self.distance,math.cos(self.yaw)*cp*self.distance],np.float32);mat4_uniform(self.program,"u_model",self.model);mat4_uniform(self.program,"u_view",look_at(eye,self.target));mat4_uniform(self.program,"u_proj",perspective(45,a,.05,10000));self.program["u_light"]=(-.4,.8,.6)
        for b in self.batches:self.program["u_material"]=b.material;b.draw()
    def on_mouse_press(self,x,y,button,modifiers):self.drag=button==pyglet.window.mouse.LEFT
    def on_mouse_release(self,x,y,button,modifiers):self.drag=False
    def on_mouse_drag(self,x,y,dx,dy,buttons,modifiers):
        if self.drag:self.yaw-=dx*.01;self.pitch=max(-1.4,min(1.4,self.pitch+dy*.01))
    def on_mouse_scroll(self,x,y,sx,sy):self.distance=max(.5,min(1000,self.distance*math.pow(.88,sy)))
    def on_key_press(self,symbol,modifiers):
        if symbol==pyglet.window.key.ESCAPE:self.close()
        elif symbol==pyglet.window.key.R:self.yaw=0;self.pitch=math.radians(8)

def main():
    p=Path(sys.argv[1]).expanduser().resolve() if len(sys.argv)>1 else Path(__file__).parent/"jene_PSO2.pmx"
    if not p.exists():print("ERROR: PMX not found:",p);return 1
    GeneWindow(p);pyglet.app.run();return 0
if __name__=="__main__":raise SystemExit(main())
