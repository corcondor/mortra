from __future__ import annotations
import hashlib, itertools, json, math, sys, time
from pathlib import Path
from collections import defaultdict
import numpy as np

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import run_experiment as R
from lstar_active import LStarMoore

ACTIONS=tuple(range(5))

class NoisyDelayedJumpArena(R.DelayedJumpArena):
    """Same hidden dynamics, stochastic raw-RGB sensor only.

    Every sample receives independent pixel noise, low-frequency texture/illumination,
    and continuous subpixel image-plane camera translation.  The pending jump bit
    remains invisible, as in the previous partial-observation test.
    """
    def _frac_shift(self, img:np.ndarray, dx:float, dy:float)->np.ndarray:
        # bilinear periodic shift. It is a sensor-plane camera jitter, not a state change.
        ix=math.floor(dx); iy=math.floor(dy); ax=dx-ix; ay=dy-iy
        a=np.roll(img,(iy,ix),(0,1)).astype(np.float32)
        b=np.roll(img,(iy,ix+1),(0,1)).astype(np.float32)
        c=np.roll(img,(iy+1,ix),(0,1)).astype(np.float32)
        d=np.roll(img,(iy+1,ix+1),(0,1)).astype(np.float32)
        return (1-ay)*((1-ax)*a+ax*b)+ay*((1-ax)*c+ax*d)

    def noisy_rgb(self, raw, style:int, sample_key:int, size:int=16,
                  pixel_sigma:float=4.0, jitter:float=0.65, texture_amp:float=5.0):
        clean=self.render_rgb(raw,style,size)
        out=[]
        # deterministic random sensor draw keyed only by public experiment sampling key;
        # it never depends on hidden-state labels beyond the clean image being observed.
        seed_bytes=hashlib.sha256(f'{self.seed}:{style}:{sample_key}'.encode()).digest()[:8]
        rng=np.random.default_rng(int.from_bytes(seed_bytes,'big'))
        for vi,v in enumerate(clean):
            x=v.astype(np.float32)
            dx=float(rng.uniform(-jitter,jitter)); dy=float(rng.uniform(-jitter,jitter))
            x=self._frac_shift(x,dx,dy)
            # Low-frequency zero-mean color texture, different every exposure.
            gh=gw=4
            coarse=rng.normal(0.0,texture_amp,(gh,gw,3)).astype(np.float32)
            tex=np.repeat(np.repeat(coarse,math.ceil(size/gh),0),math.ceil(size/gw),1)[:size,:size]
            # Global continuous exposure/white-balance drift.
            gain=rng.normal(1.0,0.018,(1,1,3)).astype(np.float32)
            bias=rng.normal(0.0,2.0,(1,1,3)).astype(np.float32)
            x=x*gain+bias+tex+rng.normal(0.0,pixel_sigma,x.shape)
            out.append(np.clip(np.rint(x),0,255).astype(np.uint8))
        return tuple(out)


    def noisy_batch(self, raw, style:int, word_key:bytes, batch:int=24, size:int=16,
                    pixel_sigma:float=4.0, jitter:float=0.65, texture_amp:float=5.0, camera_bias=(0.0,0.0)):
        clean=self.render_rgb(raw,style,size)
        seed_bytes=hashlib.sha256(str(self.seed).encode()+b":"+str(style).encode()+b":"+word_key).digest()[:8]
        rng=np.random.default_rng(int.from_bytes(seed_bytes,'big'))
        outs=[]
        for v in clean:
            base=v.astype(np.float32)
            dx=rng.uniform(-jitter,jitter,batch)+float(camera_bias[0]); dy=rng.uniform(-jitter,jitter,batch)+float(camera_bias[1])
            ix=np.floor(dx).astype(int); iy=np.floor(dy).astype(int); ax=(dx-ix).astype(np.float32); ay=(dy-iy).astype(np.float32)
            X=np.empty((batch,size,size,3),dtype=np.float32)
            for iix in (-1,0):
                for iiy in (-1,0):
                    m=(ix==iix)&(iy==iiy)
                    if not np.any(m): continue
                    a=np.roll(base,(iiy,iix),(0,1)); b=np.roll(base,(iiy,iix+1),(0,1)); c=np.roll(base,(iiy+1,iix),(0,1)); d=np.roll(base,(iiy+1,iix+1),(0,1))
                    aa=ax[m,None,None,None]; bb=ay[m,None,None,None]
                    X[m]=(1-bb)*((1-aa)*a+aa*b)+bb*((1-aa)*c+aa*d)
            coarse=rng.normal(0.0,texture_amp,(batch,4,4,3)).astype(np.float32)
            rep=math.ceil(size/4); tex=np.repeat(np.repeat(coarse,rep,1),rep,2)[:,:size,:size,:]
            gain=rng.normal(1.0,0.018,(batch,1,1,3)).astype(np.float32); bias=rng.normal(0.0,2.0,(batch,1,1,3)).astype(np.float32)
            X=X*gain+bias+tex+rng.normal(0.0,pixel_sigma,X.shape).astype(np.float32)
            outs.append(np.clip(np.rint(X),0,255).astype(np.uint8))
        return tuple(outs)

class EmissionSummary:
    __slots__=('mean','var','self_z','n','word')
    def __init__(self, mean,var,self_z,n,word):
        self.mean=mean;self.var=var;self.self_z=float(self_z);self.n=int(n);self.word=tuple(word)

class StatisticalRGBOracle:
    """Noisy raw-RGB membership oracle with a statistical emission alphabet.

    Hidden coordinates/state and clean images are unavailable to the learner.
    Each queried reset/action history gets a batch of independently perturbed raw
    RGB exposures. Emission equality is decided from raw-pixel sample statistics.
    Predictive state is then learned from action-conditioned future emissions.
    """
    def __init__(self,game:NoisyDelayedJumpArena,style:int,batch:int=24,z_threshold:float=1.22,
                 noise_floor:float=0.01,image_size:int=16):
        assert batch>=4 and batch%2==0
        self.g=game; self.style=int(style); self.batch=int(batch); self.z_threshold=float(z_threshold)
        self.noise_floor=float(noise_floor); self.image_size=int(image_size)
        self.cache={}; self.summaries={}; self.classes=[]; self.class_members=[]; self.obs_pool=self.classes
        self.queries=0; self.actions=0; self.rendered_exposures=0
        self.pixel_hashes=set(); self.pixel_duplicates=0; self.sample_serial=0
        D=4*self.image_size*self.image_size*3
        rng=np.random.default_rng(20260927)
        self._screen_idx=np.sort(rng.choice(D,size=min(256,D),replace=False))
        self.screen_fallback_full_scans=0

    def _raw_after(self,w):
        raw=self.g.start_raw
        for a in w:
            raw=self.g.raw_step(raw,int(a)); self.actions+=1
        return raw

    @staticmethod
    def _flatten(views):
        return np.concatenate([v.reshape(-1) for v in views]).astype(np.float32)/255.0

    def _summary(self,w):
        w=tuple(w)
        if w in self.summaries:return self.summaries[w]
        raw=self._raw_after(w)
        word_key=json.dumps(list(w),separators=(',',':')).encode()
        vb=self.g.noisy_batch(raw,self.style,word_key,self.batch,self.image_size)
        X=np.concatenate([v.reshape(self.batch,-1) for v in vb],axis=1).astype(np.float32)/255.0
        for i in range(self.batch):
            hh=hashlib.sha256(X[i].tobytes()).digest()
            if hh in self.pixel_hashes:self.pixel_duplicates+=1
            self.pixel_hashes.add(hh); self.rendered_exposures+=1
        mu=X.mean(axis=0); var=X.var(axis=0,ddof=1)
        h=self.batch//2
        m1=X[:h].mean(axis=0);m2=X[h:].mean(axis=0)
        v1=X[:h].var(axis=0,ddof=1);v2=X[h:].var(axis=0,ddof=1)
        denom=v1/h+v2/h+self.noise_floor**2
        self_z=float(np.sqrt(np.mean((m1-m2)**2/denom)))
        ss=EmissionSummary(mu,var,self_z,self.batch,w); self.summaries[w]=ss
        return ss

    def _z(self,a:EmissionSummary,b:EmissionSummary):
        denom=a.var/a.n+b.var/b.n+self.noise_floor**2
        return float(np.sqrt(np.mean((a.mean-b.mean)**2/denom)))

    def _class_id(self,s:EmissionSummary):
        if not self.classes:
            self.classes.append(s); self.class_members.append([s.word]); return 0
        # Cheap raw-pixel subset screen is only a computational shortlist. If it
        # finds no match we scan every remaining class with the full raw-pixel test.
        scr=s.mean[self._screen_idx]
        d=np.array([np.mean((r.mean[self._screen_idx]-scr)**2) for r in self.classes])
        k=min(12,len(self.classes)); cand=np.argpartition(d,k-1)[:k]
        tested=set(int(x) for x in cand)
        best=None; bestz=float('inf')
        for j in cand:
            z=self._z(s,self.classes[int(j)])
            if z<bestz:bestz=z;best=int(j)
        if bestz<=self.z_threshold:
            self.class_members[best].append(s.word); return best
        self.screen_fallback_full_scans+=1
        for j,r in enumerate(self.classes):
            if j in tested:continue
            z=self._z(s,r)
            if z<bestz:bestz=z;best=j
        if bestz<=self.z_threshold:
            self.class_members[best].append(s.word); return best
        self.classes.append(s); self.class_members.append([s.word]); return len(self.classes)-1

    def out(self,w):
        w=tuple(w)
        if w in self.cache:return self.cache[w]
        s=self._summary(w); cid=self._class_id(s)
        raw=self.g.start_raw
        for a in w: raw=self.g.raw_step(raw,int(a))
        ans=(cid,bool(self.g.raw_goal(raw)))
        self.cache[w]=ans; self.queries+=1
        return ans

def execute_raw(game,word):
    s=game.start_raw
    for a in word:s=game.raw_step(s,a)
    return s


def audit_emissions(game,oracle:StatisticalRGBOracle):
    """Post-hoc only: compare statistical emission classes to clean visible RGB equivalence."""
    class_to_clean=defaultdict(set); clean_to_class=defaultdict(set)
    for w,out in oracle.cache.items():
        raw=execute_raw(game,w)
        clean=hashlib.sha256(game.obs_bytes(raw,oracle.style,oracle.image_size)).hexdigest()
        cid=out[0];class_to_clean[cid].add(clean);clean_to_class[clean].add(cid)
    return {
      'statistical_emission_classes':len(oracle.classes),
      'clean_visible_classes_seen':len(clean_to_class),
      'false_merge_classes':sum(len(v)>1 for v in class_to_clean.values()),
      'false_split_clean_classes':sum(len(v)>1 for v in clean_to_class.values()),
      'max_clean_per_stat_class':max((len(v) for v in class_to_clean.values()),default=0),
      'max_stat_per_clean_class':max((len(v) for v in clean_to_class.values()),default=0),
    }


def hidden_audit(game,m):
    hidden,hidden_trans=R.enumerate_hidden(game)
    gt=R.deterministic_bisim(hidden,hidden_trans,{s:game.raw_goal(s) for s in hidden})
    q_to_gt={};errors=[]
    for q,s in enumerate(m['reps']):q_to_gt[q]=gt[execute_raw(game,s)]
    for q,s in enumerate(m['reps']):
        raw=execute_raw(game,s)
        if bool(m['out'][q][1])!=bool(game.raw_goal(raw)):errors.append(('goal',q))
        for a in ACTIONS:
            q2=m['trans'][(q,a)];t=hidden_trans[(raw,a)]
            if q_to_gt[q2]!=gt[t]:errors.append(('transition',q,a))
    return {'hidden_states':len(hidden),'hidden_predictive_classes':len(set(gt.values())),
            'machine_states':len(m['reps']),'mapped_gt_classes':len(set(q_to_gt.values())),
            'duplicate_gt_mappings':len(q_to_gt)-len(set(q_to_gt.values())),'transition_errors':len(errors),
            'first_errors':errors[:5]}


def learn(seed,style=0,batch=24,z_threshold=1.22,depth=2,max_rounds=15):
    g=NoisyDelayedJumpArena(seed,'state_opaque')
    o=StatisticalRGBOracle(g,style,batch,z_threshold)
    L=LStarMoore(o);m,log=L.learn(max_rounds=max_rounds,depth=depth)
    return g,o,L,m,log

if __name__=='__main__':
    g,o,L,m,log=learn(95027000,0)
    print(json.dumps({'states':len(m['reps']),'queries':o.queries,'actions':o.actions,'emission_classes':len(o.classes),
      'pixel_duplicates':o.pixel_duplicates,'emission_audit':audit_emissions(g,o),'hidden_audit':hidden_audit(g,m),'log':log},indent=2))
