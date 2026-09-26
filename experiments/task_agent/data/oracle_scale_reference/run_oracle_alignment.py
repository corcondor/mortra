import json, copy, math, sys, time
from collections import deque, defaultdict
from pathlib import Path
import numpy as np
from scipy.sparse import csr_matrix, identity
from scipy.sparse.linalg import splu

Q=0.90
CAP=4096
ROOT=Path('/mnt/data/reg70/registration')
SEEDS=list(range(73000000,73000010))

class Engine:
    def __init__(self,g):
        self.g=g; self.domains=tuple(g['domains']); self.initial=tuple(g['initial']); self.num_actions=g['actions']
        self.walls=frozenset(map(tuple,g['walls']))
        self.rules_by_action={a:[r for r in g['rules'] if r['action']==a] for a in range(self.num_actions)}
    def step(self,s,a):
        for r in self.rules_by_action[a]:
            if not all({'eq':s[c['var']]==c['value'],'ne':s[c['var']]!=c['value'],'lt':s[c['var']]<c['value'],'ge':s[c['var']]>=c['value']}[c['op']] for c in r['guard']): continue
            nxt=list(s)
            for e in r['assign']:
                i,val=e['var'],e['value']
                if e['op']=='set': nxt[i]=val
                elif e['op']=='add': nxt[i]=s[i]+val
                elif e['op']=='add_mod': nxt[i]=(s[i]+val)%self.domains[i]
                else: nxt[i]=s[val]%self.domains[i]
            if any(not 0<=v<n for v,n in zip(nxt,self.domains)) or tuple(nxt[:2]) in self.walls: return s
            return tuple(nxt)
        return s

class Learner:
    def __init__(self,num_actions):
        self.num_actions=num_actions; self.state_to_id={}; self.id_to_state=[]; self.node_visits={}; self.action_visits={}; self.counts={}; self.dest_map={}
    @classmethod
    def from_json(cls,x):
        L=cls(x['num_actions']); L.id_to_state=[tuple(s) for s in x['states']]; L.state_to_id={tuple(s):int(i) for s,i in x['state_to_id']}
        L.node_visits={int(u):int(n) for u,n in x['node_visits']}
        L.action_visits={(int(k[0]),int(k[1])):int(n) for k,n in x['action_visits']}
        L.counts={(int(k[0]),int(k[1])):{int(v):int(n) for v,n in vals} for k,vals in x['counts']}
        L.dest_map={(int(k[0]),int(k[1])):int(v) for k,v in x['dest_map']}
        return L
    def get_or_add_id(self,s):
        s=tuple(s)
        if s not in self.state_to_id:
            self.state_to_id[s]=len(self.id_to_state); self.id_to_state.append(s)
        return self.state_to_id[s]
    def record_transition(self,u,a,v):
        self.action_visits[(u,a)]=self.action_visits.get((u,a),0)+1
        d=self.counts.setdefault((u,a),{}); d[v]=d.get(v,0)+1
        self.dest_map[(u,a)]=max(d.items(),key=lambda kv:(kv[1],-kv[0]))[0]

def modal_successors(L,u):
    out={}
    for a in range(L.num_actions):
        d=L.counts.get((u,a))
        if d: out[a]=max(d.items(),key=lambda kv:(kv[1],-kv[0]))[0]
    return out

class Exact:
    def __init__(self,x): self.x=tuple(x)
    def matches(self,s): return tuple(s)==self.x
class VarEq:
    def __init__(self,i,v): self.i=i; self.v=v
    def matches(self,s): return s[self.i]==self.v
class Seq:
    def __init__(self,goals): self.goals=goals
    @property
    def initial_memory(self): return 0
    def advance(self,m,s):
        m=int(m)
        while m<len(self.goals) and self.goals[m].matches(s): m+=1
        return m
    def accepting(self,m): return int(m)>=len(self.goals)
    def progress(self,m): return min(1.0,int(m)/len(self.goals))
class All:
    def __init__(self,goals): self.goals=goals; self.accept_mask=(1<<len(goals))-1
    @property
    def initial_memory(self): return 0
    def advance(self,m,s):
        m=int(m)
        for i,p in enumerate(self.goals):
            if p.matches(s): m|=1<<i
        return m
    def accepting(self,m): return int(m)==self.accept_mask
    def progress(self,m): return int(m).bit_count()/len(self.goals)
class Branch:
    def __init__(self,A,CA,B,CB): self.A=A; self.CA=CA; self.B=B; self.CB=CB
    @property
    def initial_memory(self): return 0
    def advance(self,m,s):
        m=int(m)
        if m==0:
            if self.A.matches(s): m=1
            elif self.B.matches(s): m=2
        if m==1 and self.CA.matches(s): return 3
        if m==2 and self.CB.matches(s): return 3
        return m
    def accepting(self,m): return int(m)==3
    def progress(self,m): return (0.,.5,.5,1.)[int(m)]

def pred(p): return Exact(p['state']) if p['kind']=='exact' else VarEq(p['var'],p['value'])
def task_from(spec):
    if spec['op']=='SEQ': return Seq([pred(p) for p in spec['goals']])
    if spec['op']=='ALL': return All([pred(p) for p in spec['goals']])
    if spec['op']=='BRANCH': return Branch(pred(spec['A']),pred(spec['CA']),pred(spec['B']),pred(spec['CB']))
    raise ValueError(spec['op'])

def reachable(adj,goals):
    rev=[[] for _ in adj]
    for u,row in enumerate(adj):
        for v in row: rev[v].append(u)
    seen=set(goals); q=deque(seen)
    while q:
        v=q.popleft()
        for u in rev[v]:
            if u not in seen: seen.add(u); q.append(u)
    return seen

class Planner:
    def build(self,L,task,state,memory):
        if tuple(state) not in L.state_to_id: return None
        m0=task.advance(memory,state); z0=(L.state_to_id[tuple(state)],m0)
        index={z0:0}; states=[z0]; actions=[]; q=deque([z0])
        while q:
            u,m=q.popleft(); row={}
            for a,v in modal_successors(L,u).items():
                mn=task.advance(m,L.id_to_state[v]); z=(v,mn)
                if z not in index: index[z]=len(states); states.append(z); q.append(z)
                row[a]=index[z]
            actions.append(row)
        n=len(states); rr=[];cc=[];ww=[]
        for i,row in enumerate(actions):
            if row:
                w=1/len(row)
                for j in row.values(): rr.append(i);cc.append(j);ww.append(w)
        K=csr_matrix((ww,(rr,cc)),shape=(n,n),dtype=float)
        goals=[i for i,(_,m) in enumerate(states) if task.accepting(m)]
        reach=reachable([list(r.values()) for r in actions],goals) if goals else set()
        psi=None
        if goals:
            g=np.zeros(n); g[goals]=1
            psi=splu(identity(n,format='csc')-Q*K.tocsc()).solve(g)
        return states,index,actions,reach,psi
    def choose(self,L,task,state,memory,model):
        if model is None: return None
        states,index,actions,reach,psi=model
        if psi is None:return None
        z=(L.state_to_id[tuple(state)],task.advance(memory,state)); i=index.get(z)
        if i is None or i not in reach:return None
        c=[(float(psi[j]),-a,a) for a,j in actions[i].items() if j in reach]
        return max(c)[2] if c else None

def fields(L,state,task,memory):
    u0=L.state_to_id[tuple(state)]; initial=(u0,task.advance(memory,state))
    states=[initial]; index={initial:0}; actions=[]; virtual=[]; q=deque([initial]); A=L.num_actions
    while q:
        u,m=q.popleft(); row={}
        for a in range(A):
            visits=L.action_visits.get((u,a),0)
            if visits==0:
                row[a]=-1-len(virtual); virtual.append((u,m,a)); continue
            counts=L.counts.get((u,a));
            if not counts: raise RuntimeError('tried without counts')
            v=max(counts,key=lambda x:(counts[x],-x)); z=(v,task.advance(m,L.id_to_state[v]))
            if z not in index: index[z]=len(states); states.append(z); q.append(z)
            row[a]=index[z]
        actions.append(row)
    nr=len(states); rr=[];cc=[];ww=[]
    for i,row in enumerate(actions):
        for a,j in list(row.items()):
            if j<0: j=nr+(-j-1); row[a]=j
            rr.append(i);cc.append(j);ww.append(1/A)
    n=nr+len(virtual); K=csr_matrix((ww,(rr,cc)),shape=(n,n)); src=np.zeros((n,2))
    for i,(_,m,_) in enumerate(virtual,nr): src[i]=[1.0,math.exp(task.progress(m))]
    vals=np.zeros_like(src)
    if virtual: vals=splu(identity(n,format='csc')-Q*K.tocsc()).solve(src)
    return states,actions,virtual,vals,src

def policy_action(L,state,task,memory,kind):
    states,actions,virtual,vals,src=fields(L,state,task,memory)
    if not virtual:
        # same local count fallback
        return min(range(L.num_actions), key=lambda a:(L.action_visits.get((L.state_to_id[tuple(state)],a),0),a)), {'changed':False}
    row=actions[0]
    gs={a:float(vals[j,0]) for a,j in row.items()}; ts={a:float(vals[j,1]) for a,j in row.items()}
    ga=max(row,key=lambda a:(gs[a],-a))
    const=np.all(src[len(states):,1]==src[len(states),1])
    ta=max(row,key=lambda a:(ts[a],-a))
    if const: ta=ga
    if kind=='generic': a=ga
    elif kind=='current': a=ta
    elif kind=='normalized':
        gmax=gs[ga]
        cand=[x for x in row if gs[x]>0 and gs[x] >= Q*gmax - 1e-15]
        if const or not cand: a=ga
        else:
            ratios={x:ts[x]/gs[x] for x in cand}
            a=max(cand,key=lambda x:(ratios[x],-x))
    else: raise ValueError(kind)
    return a, {'changed':a!=ga,'ga':ga,'gs':gs,'ts':ts}

def run_episode(snapshot,engine,task,start,kind):
    L=copy.deepcopy(snapshot); P=Planner(); state=tuple(start); memory=task.advance(task.initial_memory,state); L.get_or_add_id(state)
    steps=0; explore=0; changes=0
    while steps<CAP:
        if task.accepting(memory): return True,steps,explore,changes
        model=P.build(L,task,state,memory); a=P.choose(L,task,state,memory,model)
        if a is None:
            a,tel=policy_action(L,state,task,memory,kind); explore+=1; changes+=int(tel['changed'])
        u=L.get_or_add_id(state); ns=engine.step(state,a); v=L.get_or_add_id(ns); L.record_transition(u,a,v); state=ns; memory=task.advance(memory,state); steps+=1
    return False,CAP,explore,changes

def load_seed(seed):
    d=ROOT/str(seed); g=json.load(open(d/'genome.json')); sj=json.load(open(d/'snapshot_512.json')); tasks=json.load(open(d/'tasks.json'))
    return Engine(g),Learner.from_json(sj),tasks



class TrueOracle:
    """Exact full-world task distances, used only as an evaluation upper bound."""
    def __init__(self, engine, roots, task):
        self.engine=engine; self.task=task
        # Close the true deterministic world from all states already known at episode start.
        states=list(dict.fromkeys(tuple(s) for s in roots)); ids={s:i for i,s in enumerate(states)}; edges=[]; q=deque(states)
        # queue above cannot be used with append semantics cleanly, so use index scan.
        i=0
        while i<len(states):
            row=[]; s=states[i]
            for a in range(engine.num_actions):
                ns=engine.step(s,a)
                if ns not in ids:
                    ids[ns]=len(states); states.append(ns)
                row.append(ids[ns])
            edges.append(row); i+=1
        self.states=states; self.ids=ids; self.edges=edges
        # Enumerate all task-memory values that can occur by product BFS from every state and every plausible initial memory.
        # Simpler and exact for these finite task automata: start product from every world state at task.initial_memory,
        # then close under all actions. This covers every product state reachable from an episode start.
        products=[]; pids={}; pq=deque()
        for s in states:
            m=task.advance(task.initial_memory,s); z=(ids[s],m)
            if z not in pids: pids[z]=len(products); products.append(z); pq.append(z)
        pedges=[]
        while pq:
            u,m=pq.popleft(); zi=pids[(u,m)]
            while len(pedges)<=zi: pedges.append([])
            row=[]
            for a,v in enumerate(edges[u]):
                mn=task.advance(m,states[v]); zn=(v,mn)
                if zn not in pids: pids[zn]=len(products); products.append(zn); pq.append(zn)
                row.append(pids[zn])
            pedges[zi]=row
        rev=[[] for _ in products]
        goals=[]
        for i,row in enumerate(pedges):
            if task.accepting(products[i][1]): goals.append(i)
            for j in row: rev[j].append(i)
        INF=10**9
        dist=[INF]*len(products); dq=deque()
        for g in goals: dist[g]=0; dq.append(g)
        while dq:
            v=dq.popleft()
            for u in rev[v]:
                if dist[u]==INF: dist[u]=dist[v]+1; dq.append(u)
        self.pids=pids; self.dist=dist
    def action(self,state,memory):
        s=tuple(state); u=self.ids[s]; best=None
        vals={}
        for a,v in enumerate(self.edges[u]):
            ns=self.states[v]; mn=self.task.advance(memory,ns); j=self.pids.get((v,mn)); d=self.dist[j] if j is not None else 10**9
            vals[a]=d
            key=(d,a)
            if best is None or key<best[0]: best=(key,a)
        return best[1], vals


def run_oracle_episode(snapshot,engine,task,start):
    L=copy.deepcopy(snapshot); P=Planner(); state=tuple(start); memory=task.advance(task.initial_memory,state); L.get_or_add_id(state)
    oracle=TrueOracle(engine, snapshot.id_to_state, task)
    steps=0; explore=0; oracle_changes=0
    while steps<CAP:
        if task.accepting(memory): return True,steps,explore,oracle_changes
        model=P.build(L,task,state,memory); planned=P.choose(L,task,state,memory,model)
        if planned is None:
            # Compare to generic at the exact same learned state, but execute exact oracle-optimal exploration action.
            ga,_=policy_action(L,state,task,memory,'generic')
            a,_vals=oracle.action(state,memory); explore+=1; oracle_changes+=int(a!=ga)
        else:
            a=planned
        u=L.get_or_add_id(state); ns=engine.step(state,a); v=L.get_or_add_id(ns); L.record_transition(u,a,v); state=ns; memory=task.advance(memory,state); steps+=1
    return False,CAP,explore,oracle_changes


import zipfile, ast, glob
from collections import Counter,defaultdict
# caches
world_cache={}; oracle_cache={}; task_cache={}
def get(seed,tid):
    if seed not in world_cache:
        eng,snap,tasks=load_seed(seed); world_cache[seed]=(eng,snap,tasks); task_cache[seed]={t['task_id']:t for t in tasks}
    eng,snap,tasks=world_cache[seed]; td=task_cache[seed][tid]; key=(seed,tid)
    if key not in oracle_cache:
        oracle_cache[key]=(task_from(td['spec']), TrueOracle(eng,snap.id_to_state,task_from(td['spec'])))
    return oracle_cache[key]


counts=Counter(); ratios=[]; pos_shifts=[]; neg_shifts=[]; bytype=defaultdict(Counter)
for zp in sorted(glob.glob('/mnt/data/fresh70-shard-*.zip')):
    with zipfile.ZipFile(zp) as z:
        for name in z.namelist():
            if not name.endswith('mechanism_telemetry.jsonl'): continue
            for raw in z.open(name):
                row=json.loads(raw)
                if row.get('policy')!='task_virtual_frontier' or not row.get('virtual_field_decision') or not row.get('task_signal_available'): continue
                seed=int(row['seed']); tid=int(row['task_id']); tt=row['task_type']; task,orc=get(seed,tid)
                state=ast.literal_eval(row['world_state']); memory=ast.literal_eval(row['memory']); oa,vals=orc.action(state,memory)
                ga=int(row['generic_counterfactual_action']); gs={int(k):float(v) for k,v in row['generic_scores'].items()}; ts={int(k):float(v) for k,v in row['task_scores'].items()}
                do=vals[oa]; dg=vals[ga]
                if do>=10**8 or dg>=10**8: continue
                counts['signal_finite']+=1; bytype[tt]['signal_finite']+=1
                if do<dg:
                    counts['oracle_strictly_better_than_generic']+=1; bytype[tt]['oracle_strictly_better_than_generic']+=1
                    # relative task perturbation in direction oracle vs current generic winner
                    shift=(ts[oa]-gs[oa])-(ts[ga]-gs[ga])
                    gap=gs[ga]-gs[oa]
                    if shift>1e-12: counts['shift_toward_oracle']+=1; bytype[tt]['shift_toward_oracle']+=1; pos_shifts.append(shift)
                    elif shift<-1e-12: counts['shift_away_oracle']+=1; bytype[tt]['shift_away_oracle']+=1; neg_shifts.append(shift)
                    else: counts['shift_zero_oracle']+=1; bytype[tt]['shift_zero_oracle']+=1
                    if gap>1e-15:
                        ratios.append(shift/gap)
                        if shift>=gap-1e-12: counts['enough_to_cross_oracle']+=1; bytype[tt]['enough_to_cross_oracle']+=1
                elif do==dg:
                    counts['generic_oracle_tied_true']+=1; bytype[tt]['generic_oracle_tied_true']+=1

import numpy as np
out={'counts':dict(counts),'bytype':{k:dict(v) for k,v in bytype.items()}}
if ratios:
    arr=np.array(ratios,float)
    out['shift_over_generic_gap']={'n':len(arr),'mean':float(arr.mean()),'median':float(np.median(arr)),'p10':float(np.quantile(arr,.1)),'p90':float(np.quantile(arr,.9)),'positive_fraction':float(np.mean(arr>0)),'ge1_fraction':float(np.mean(arr>=1))}
print(json.dumps(out,indent=2))
json.dump(out,open('/mnt/data/oracle_alignment_analysis.json','w'),indent=2)
