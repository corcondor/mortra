from __future__ import annotations
import copy, hashlib, json, math, random
import numpy as np
from PIL import Image, ImageDraw

class PhysicsArena3D:
    _GLOBAL={}
    num_actions=5
    action_names=('forward','yaw_left','yaw_right','jump','wait')
    def __init__(self,seed=0,observation_mode='state_opaque'):
        self.seed=int(seed); self.observation_mode=observation_mode
        self.width=self.height=7; self.zmax=3
        self.start_raw=(1,1,1,0,0) # east
        self.goal=(5,5,2)
        # outer walls and a raised goal platform at z=1
        self.solid=set()
        for x in range(7):
            for z in (1,2):
                self.solid.add((x,0,z)); self.solid.add((x,6,z))
        for y in range(7):
            for z in (1,2):
                self.solid.add((0,y,z)); self.solid.add((6,y,z))
        self.solid.add((5,5,1))
        # deterministic obstacle placement away from reserved path
        import random
        rng=random.Random(seed)
        reserved={(x,1) for x in range(1,5)}|{(4,y) for y in range(1,6)}|{(5,5),(1,1)}
        candidates=[(x,y) for x in range(1,6) for y in range(1,6) if (x,y) not in reserved]
        rng.shuffle(candidates)
        for x,y in candidates[:4]:
            self.solid.add((x,y,1)); self.solid.add((x,y,2))
        # one low crate adds height geometry but not on reserved path
        if len(candidates)>4:
            x,y=candidates[4]; self.solid.add((x,y,1))
        self._tok_to_raw={}; self._raw_to_tok={}; self._render_cache={}; self.alias_collisions=0
        self.mask=int.from_bytes(hashlib.sha256(f'physics3d:{seed}'.encode()).digest()[:16],'big')
    def copy(self): return copy.deepcopy(self)
    def spec(self):
        return {'seed':self.seed,'mode':self.observation_mode,'size':[self.width,self.height,self.zmax],
                'start_raw':self.start_raw,'goal':self.goal,'solid':sorted(self.solid),
                'physics':{'gravity':'one level per step when unsupported','jump':'one-level impulse','heading':4}}
    def to_dict(self): return self.spec()
    def is_solid(self,x,y,z):
        if z<=0: return True # floor
        return (x,y,z) in self.solid
    def supported(self,x,y,z): return self.is_solid(x,y,z-1)
    def valid_body(self,x,y,z):
        return 0<=x<self.width and 0<=y<self.height and 1<=z<=self.zmax and not self.is_solid(x,y,z)
    def raw_step(self,s,a):
        x,y,z,h,vz=s
        if a==1: h=(h-1)%4
        elif a==2: h=(h+1)%4
        elif a==0:
            dx,dy=((1,0),(0,1),(-1,0),(0,-1))[h]
            nx,ny=x+dx,y+dy
            if self.valid_body(nx,ny,z): x,y=nx,ny
        elif a==3:
            if self.supported(x,y,z): vz=1
        elif a==4: pass
        else: raise ValueError(a)
        # discrete vertical physics after control
        if vz>0:
            if self.valid_body(x,y,z+1): z+=1
            vz=0
        elif not self.supported(x,y,z):
            if self.valid_body(x,y,z-1): z-=1
            vz=-1 if not self.supported(x,y,z) else 0
        else: vz=0
        return (x,y,z,h,vz)
    def raw_goal(self,s): return s[:3]==self.goal
    def _opaque_token(self,raw):
        b=json.dumps(list(raw),separators=(',',':')).encode()
        val=int.from_bytes(b,'big')^self.mask
        return (val,len(b))
    def render_views(self,raw,size=48):
        key=(raw,size)
        if key in self._render_cache: return self._render_cache[key]
        views=[]
        # top
        im=Image.new('RGB',(size,size),(220,228,235)); d=ImageDraw.Draw(im); cell=size/self.width
        for x in range(self.width):
            for y in range(self.height):
                hs=[z for z in range(1,self.zmax+1) if (x,y,z) in self.solid]
                if hs:
                    shade=80+35*max(hs); d.rectangle((x*cell,y*cell,(x+1)*cell-1,(y+1)*cell-1),fill=(shade,shade,shade))
        gx,gy,gz=self.goal; d.rectangle((gx*cell,gy*cell,(gx+1)*cell-1,(gy+1)*cell-1),outline=(20,180,50),width=2)
        x,y,z,h,vz=raw; cx=(x+.5)*cell; cy=(y+.5)*cell; r=max(2,cell*.25)
        d.ellipse((cx-r,cy-r,cx+r,cy+r),fill=(220,35,35)); dx,dy=((1,0),(0,1),(-1,0),(0,-1))[h]; d.line((cx,cy,cx+dx*cell*.45,cy+dy*cell*.45),fill=(255,255,0),width=2)
        views.append(np.array(im,dtype=np.uint8))
        # x-z front aggregated over y
        im=Image.new('RGB',(size,size),(195,220,245)); d=ImageDraw.Draw(im); cw=size/self.width; ch=size/(self.zmax+1)
        d.rectangle((0,size-ch,size,size),fill=(120,110,90))
        for xx in range(self.width):
            for zz in range(1,self.zmax+1):
                if any((xx,yy,zz) in self.solid for yy in range(self.height)):
                    d.rectangle((xx*cw,size-(zz+1)*ch,(xx+1)*cw-1,size-zz*ch-1),fill=(110,110,115))
        d.rectangle((gx*cw,size-(gz+1)*ch,(gx+1)*cw-1,size-gz*ch-1),outline=(20,180,50),width=2)
        d.ellipse(((x+.25)*cw,size-(z+.75)*ch,(x+.75)*cw,size-(z+.25)*ch),fill=(220,35,35))
        views.append(np.array(im,dtype=np.uint8))
        # y-z side
        im=Image.new('RGB',(size,size),(195,220,245)); d=ImageDraw.Draw(im); cw=size/self.height
        d.rectangle((0,size-ch,size,size),fill=(120,110,90))
        for yy in range(self.height):
            for zz in range(1,self.zmax+1):
                if any((xx,yy,zz) in self.solid for xx in range(self.width)):
                    d.rectangle((yy*cw,size-(zz+1)*ch,(yy+1)*cw-1,size-zz*ch-1),fill=(105,105,110))
        d.rectangle((gy*cw,size-(gz+1)*ch,(gy+1)*cw-1,size-gz*ch-1),outline=(20,180,50),width=2)
        d.ellipse(((y+.25)*cw,size-(z+.75)*ch,(y+.75)*cw,size-(z+.25)*ch),fill=(220,35,35))
        views.append(np.array(im,dtype=np.uint8))
        # simple first person raycast
        W=H=size; arr=np.zeros((H,W,3),dtype=np.uint8); arr[:H//2,:,:]=(130,190,235); arr[H//2:,:,:]=(85,80,70)
        px,py=x+.5,y+.5; heading=(0,math.pi/2,math.pi,3*math.pi/2)[h]
        fov=math.pi/2
        for col in range(W):
            ang=heading+(col/(W-1)-.5)*fov; hitdist=7.0; hitheight=0; goalhit=False
            for dist in np.linspace(.15,7,100):
                rx=int(px+math.cos(ang)*dist); ry=int(py+math.sin(ang)*dist)
                if not (0<=rx<self.width and 0<=ry<self.height): hitdist=dist;hitheight=2;break
                hs=[zz for zz in range(1,self.zmax+1) if (rx,ry,zz) in self.solid]
                if hs:
                    hitdist=dist; hitheight=max(hs); goalhit=(rx,ry)==(gx,gy); break
            wallh=int(min(H*.9,(H*.55*hitheight/max(.4,hitdist))))
            y0=max(0,H//2-wallh//2); y1=min(H-1,H//2+wallh//2)
            shade=int(max(45,190-18*hitdist)); color=(30,190,60) if goalhit else (shade,shade,shade)
            arr[y0:y1+1,col,:]=color
        # HUD for current z/vertical state, deterministic pixels
        arr[1:3,1:1+min(W-2,6*z),:]=(240,210,30)
        views.append(arr)
        self._render_cache[key]=tuple(views)
        return self._render_cache[key]
    def _visual_token(self,raw):
        views=self.render_views(raw)
        h=hashlib.sha256()
        for v in views:h.update(v.tobytes())
        dig=h.digest()[:16]
        return (int.from_bytes(dig[:8],'big'),int.from_bytes(dig[8:],'big'))
    def token_for(self,raw):
        raw=tuple(raw)
        tok=self._opaque_token(raw) if self.observation_mode=='state_opaque' else self._visual_token(raw)
        if tok in self._tok_to_raw and self._tok_to_raw[tok]!=raw:
            self.alias_collisions+=1; raise RuntimeError(f'observation alias {tok}: {self._tok_to_raw[tok]} vs {raw}')
        global_key=(self.seed,self.observation_mode,tok)
        if global_key in PhysicsArena3D._GLOBAL and PhysicsArena3D._GLOBAL[global_key]!=raw:
            self.alias_collisions+=1; raise RuntimeError(f'global observation alias {tok}: {PhysicsArena3D._GLOBAL[global_key]} vs {raw}')
        self._tok_to_raw[tok]=raw; self._raw_to_tok[raw]=tok
        PhysicsArena3D._GLOBAL[global_key]=raw
        return tok
    def raw_from(self,tok):
        tok=tuple(tok)
        if tok in self._tok_to_raw:return self._tok_to_raw[tok]
        raw=PhysicsArena3D._GLOBAL.get((self.seed,self.observation_mode,tok))
        if raw is None: raise KeyError(tok)
        self._tok_to_raw[tok]=raw;self._raw_to_tok[raw]=tok
        return raw
    def get_initial_state(self): return self.token_for(self.start_raw)
    def step(self,state,action):
        raw=self.raw_from(state); nxt=self.raw_step(raw,int(action)); return self.token_for(nxt)
    def is_goal(self,state): return self.raw_goal(self.raw_from(state))


