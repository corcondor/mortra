from __future__ import annotations
import hashlib,itertools,json,math,sys,time
from pathlib import Path
from collections import defaultdict
import numpy as np

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import run_experiment as R
from noisy_active import NoisyDelayedJumpArena

ACTIONS=tuple(range(5))

class Summary:
    __slots__=('mean','var','n','goal')
    def __init__(self,mean,var,n,goal):self.mean=mean;self.var=var;self.n=n;self.goal=bool(goal)

class RGBDistributionOracle:
    """reset/action -> repeated raw RGB samples. No hidden state to the learner."""
    def __init__(self,g,style,batch=24,size=16,noise_floor=.01,camera_bias=(0.0,0.0)):
        self.g=g;self.style=int(style);self.batch=int(batch);self.size=int(size);self.noise_floor=float(noise_floor);self.camera_bias=tuple(float(x) for x in camera_bias)
        self.cache={};self.query_count=0;self.query_actions=0;self.exposures=0;self.hashes=set();self.duplicates=0
    def raw_after(self,w):
        s=self.g.start_raw
        for a in w:s=self.g.raw_step(s,int(a));self.query_actions+=1
        return s
    def summary(self,w,rep=0):
        w=tuple(w);key=(w,int(rep))
        if key in self.cache:return self.cache[key]
        raw=self.raw_after(w)
        wb=json.dumps([list(w),int(rep)],separators=(',',':')).encode()
        vb=self.g.noisy_batch(raw,self.style,wb,self.batch,self.size,camera_bias=self.camera_bias)
        X=np.concatenate([v.reshape(self.batch,-1) for v in vb],axis=1).astype(np.float32)/255.
        for i in range(self.batch):
            h=hashlib.sha256(X[i].tobytes()).digest()
            if h in self.hashes:self.duplicates+=1
            self.hashes.add(h);self.exposures+=1
        ans=Summary(X.mean(0),X.var(0,ddof=1),self.batch,self.g.raw_goal(raw))
        self.cache[key]=ans;self.query_count+=1
        return ans
    def z(self,a:Summary,b:Summary):
        if a.goal!=b.goal:return float('inf')
        den=a.var/a.n+b.var/b.n+self.noise_floor**2
        return float(np.sqrt(np.mean((a.mean-b.mean)**2/den)))


def calibration_threshold(seed=95027000,style=0,batch=24,size=16,words=100,margin=1.18):
    """Uses only repeat photographs of the exact same public action history."""
    g=NoisyDelayedJumpArena(seed,'state_opaque');o=RGBDistributionOracle(g,style,batch,size)
    W=[()]
    for d in range(1,6):
        for w in itertools.product(ACTIONS,repeat=d):
            W.append(w)
            if len(W)>=words:break
        if len(W)>=words:break
    zs=[]
    for w in W:
        zs.append(o.z(o.summary(w,0),o.summary(w,1)))
    mx=max(zs);thr=mx*margin
    return thr,{'pilot_seed':seed,'style':style,'batch':batch,'size':size,'histories':len(W),
                'repeat_z_min':min(zs),'repeat_z_median':float(np.median(zs)),'repeat_z_p99':float(np.quantile(zs,.99)),
                'repeat_z_max':mx,'margin':margin,'threshold':thr,'pixel_duplicates':o.duplicates,
                'exposures':o.exposures,'queries':o.query_count}

class StatisticalObservationTable:
    def __init__(self,o:RGBDistributionOracle,threshold:float):
        self.o=o;self.T=float(threshold);self.S=[()];self.E=[()]
        self.eq_calls=0;self.max_z_same=0.;self.min_z_diff=float('inf')
    def out_same(self,w1,w2):
        if tuple(w1)==tuple(w2):return True
        a=self.o.summary(w1);b=self.o.summary(w2);z=self.o.z(a,b);self.eq_calls+=1
        same=z<=self.T
        if same:self.max_z_same=max(self.max_z_same,z)
        else:self.min_z_diff=min(self.min_z_diff,z)
        return same
    def row_same(self,s,t):
        return all(self.out_same(tuple(s)+tuple(e),tuple(t)+tuple(e)) for e in self.E)
    def groups(self,seqs=None):
        seqs=self.S if seqs is None else list(seqs);groups=[]
        # Conservative complete-link assignment reduces non-transitive chaining.
        for s in seqs:
            placed=False
            for G in groups:
                if all(self.row_same(s,r) for r in G):G.append(s);placed=True;break
            if not placed:groups.append([s])
        return groups
    def group_index(self,s,groups):
        hits=[i for i,G in enumerate(groups) if all(self.row_same(s,r) for r in G)]
        if len(hits)!=1:return None
        return hits[0]
    def close_consistent(self,max_pass=1000):
        for _ in range(max_pass):
            G=self.groups();added=None
            # closure: every one-step extension matches exactly one existing row class
            for s in list(self.S):
                for a in ACTIONS:
                    t=s+(a,);idx=self.group_index(t,G)
                    if idx is None:
                        if t not in self.S:added=t;break
                if added:break
            if added:
                self.S.append(added);continue
            # consistency: members of one current row class must have same successor row classes
            newe=None
            for group in G:
                for i in range(len(group)):
                    for j in range(i+1,len(group)):
                        s,t=group[i],group[j]
                        for a in ACTIONS:
                            if not self.row_same(s+(a,),t+(a,)):
                                # find existing suffix witnessing this successor-row difference
                                for e in self.E:
                                    if not self.out_same(s+(a,)+e,t+(a,)+e):
                                        newe=(a,)+e;break
                                if newe is None:newe=(a,)
                                break
                        if newe:break
                    if newe:break
                if newe:break
            if newe:
                if newe not in self.E:self.E.append(newe)
                else: raise RuntimeError('inconsistent but no new suffix')
                continue
            return G
        raise RuntimeError('table did not stabilize')
    def machine(self):
        G=self.close_consistent(); reps=[g[0] for g in G];trans={};goal={}
        for q,s in enumerate(reps):
            goal[q]=self.o.summary(s).goal
            for a in ACTIONS:
                idx=self.group_index(s+(a,),G)
                if idx is None:raise RuntimeError('not closed at machine construction')
                trans[(q,a)]=idx
        start=self.group_index((),G)
        return {'groups':G,'reps':reps,'trans':trans,'goal':goal,'start':start}
    def predicted_q(self,m,w):
        q=m['start']
        for a in w:q=m['trans'][(q,a)]
        return q
    def counterexample(self,m,depth=2):
        perturb=[()]
        for d in range(1,depth+1):perturb.extend(itertools.product(ACTIONS,repeat=d))
        for q,s in enumerate(m['reps']):
            for x in perturb:
                qp=q
                for a in x:qp=m['trans'][(qp,a)]
                r=m['reps'][qp]
                # Compare all current distinguishing experiments from actual vs predicted history.
                actual=s+tuple(x)
                if not self.row_same(actual,r):return actual
        return None
    def learn(self,max_rounds=20,depth=2):
        log=[]
        for r in range(max_rounds):
            m=self.machine();cex=self.counterexample(m,depth)
            log.append({'round':r,'states':len(m['reps']),'S':len(self.S),'E':len(self.E),'counterexample':cex is not None,
                        'rgb_queries':self.o.query_count,'query_actions':self.o.query_actions,'exposures':self.o.exposures})
            if cex is None:return m,log
            for k in range(len(cex)+1):
                p=cex[:k]
                if p not in self.S:self.S.append(p)
        return self.machine(),log


def execute_raw(g,w):
    s=g.start_raw
    for a in w:s=g.raw_step(s,a)
    return s

def hidden_audit(g,m):
    hidden,tr=R.enumerate_hidden(g);gt=R.deterministic_bisim(hidden,tr,{s:g.raw_goal(s) for s in hidden})
    qgt={q:gt[execute_raw(g,s)] for q,s in enumerate(m['reps'])};errs=[]
    for q,s in enumerate(m['reps']):
        raw=execute_raw(g,s)
        if m['goal'][q]!=g.raw_goal(raw):errs.append(('goal',q))
        for a in ACTIONS:
            if qgt[m['trans'][(q,a)]]!=gt[tr[(raw,a)]]:errs.append(('tr',q,a))
    return {'hidden_states':len(hidden),'hidden_predictive_classes':len(set(gt.values())),'machine_states':len(m['reps']),
            'mapped_gt_classes':len(set(qgt.values())),'duplicate_gt_mappings':len(qgt)-len(set(qgt.values())),
            'transition_errors':len(errs),'first_errors':errs[:5]}

def control(g,m,horizon=60):
    n=len(m['reps']);K=np.zeros((n,n))
    for q in range(n):
        for a in ACTIONS:K[q,m['trans'][(q,a)]]+=.2
    goals=[q for q,v in m['goal'].items() if v];psi=np.zeros(n)
    if goals:psi,*_=R.solve_fixed_field(K,goals,q=.90)
    q=m['start'];raw=g.start_raw;acts=[]
    for _ in range(horizon):
        if g.raw_goal(raw):break
        vals=[psi[m['trans'][(q,a)]] for a in ACTIONS];a=int(np.argmax(vals));acts.append(a);q=m['trans'][(q,a)];raw=g.raw_step(raw,a)
    return {'success':g.raw_goal(raw),'steps':len(acts),'actions':acts,'names':[R.ACTION_NAMES[a] for a in acts]}

def structural_merge(machines):
    nodes=[];tr={};goal={}
    for style,m in machines.items():
        for q in range(len(m['reps'])):
            n=(style,q);nodes.append(n);goal[n]=m['goal'][q]
            for a in ACTIONS:tr[(n,a)]=(style,m['trans'][(q,a)])
    p=R.deterministic_bisim(nodes,tr,goal);G=defaultdict(list)
    for n,c in p.items():G[c].append(n)
    return {'classes':len(G),'all_styles_classes':sum(len({x[0] for x in xs})==len(machines) for xs in G.values()),'groups':G}

def learn_one(seed,style,T,batch=24,size=16,max_rounds=20):
    g=NoisyDelayedJumpArena(seed,'state_opaque');o=RGBDistributionOracle(g,style,batch,size);L=StatisticalObservationTable(o,T);m,log=L.learn(max_rounds=max_rounds)
    return g,o,L,m,log

if __name__=='__main__':
    T,cal=calibration_threshold();print('CAL',json.dumps(cal,indent=2))
    st=time.time();g,o,L,m,log=learn_one(95027000,0,T,max_rounds=10)
    print('elapsed',time.time()-st);print(json.dumps({'audit':hidden_audit(g,m),'control':control(g,m),'log':log,'duplicates':o.duplicates,'queries':o.query_count,'actions':o.query_actions,'E':[list(e) for e in L.E]},indent=2))
