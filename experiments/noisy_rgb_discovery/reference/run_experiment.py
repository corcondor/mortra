from __future__ import annotations
import json, math, sys, importlib.util
from pathlib import Path
from collections import deque, defaultdict, Counter
import numpy as np

ROOT=Path(__file__).resolve().parent
SOURCE=ROOT/'source'
sys.path.insert(0,str(SOURCE))
from physics3d import PhysicsArena3D

# Load the previously tested MORTRA V2 fixed-field solver directly from its frozen excerpt.
spec=importlib.util.spec_from_file_location('v2_frozen_excerpt',SOURCE/'v2_source_excerpt.py')
v2=importlib.util.module_from_spec(spec); sys.modules[spec.name]=v2; spec.loader.exec_module(v2)
solve_fixed_field=v2.solve_fixed_field

SEEDS=(94027000,94027001,94027002,94027003)
ACTIONS=range(5)
ACTION_NAMES=PhysicsArena3D.action_names
STYLES=range(4)

class DelayedJumpArena(PhysicsArena3D):
    """Same 3D geometry, but jump impulse is latent for one transition.

    The rendered RGB never exposes the pending impulse bit. Hence the same four
    RGB views can correspond to two states with different next-step dynamics.
    This is the controlled partial-observability test.
    """
    def raw_step(self,s,a):
        x,y,z,h,pending=s
        # Integrate the previously hidden jump impulse first.
        if pending:
            if self.valid_body(x,y,z+1):
                z += 1
            pending=0
        # Then apply the visible control.
        if a==1: h=(h-1)%4
        elif a==2: h=(h+1)%4
        elif a==0:
            dx,dy=((1,0),(0,1),(-1,0),(0,-1))[h]
            nx,ny=x+dx,y+dy
            if self.valid_body(nx,ny,z): x,y=nx,ny
        elif a==3:
            if self.supported(x,y,z): pending=1
        elif a==4: pass
        else: raise ValueError(a)
        # If a horizontal/control step ends unsupported, gravity resolves now.
        # The only latent variable retained is a just-issued jump impulse.
        if not pending:
            while z>1 and not self.supported(x,y,z):
                if self.valid_body(x,y,z-1): z-=1
                else: break
        return (x,y,z,h,pending)

    def render_rgb(self,raw,style=0,size=24):
        # Hide the pending jump impulse from every camera.
        x,y,z,h,_=raw
        views=[np.array(v,copy=True) for v in self.render_views((x,y,z,h,0),size)]
        # Four deterministic camera/sensor layouts. They alter pixels, not physics.
        if style==0:
            out=views
        elif style==1:
            order=(1,2,0,3)
            out=[np.rot90(views[i],1).copy() for i in order]
        elif style==2:
            order=(2,0,1,3)
            out=[np.fliplr(views[i]).copy() for i in order]
        elif style==3:
            order=(0,2,1,3)
            out=[]
            for j,i in enumerate(order):
                v=np.roll(views[i],shift=(j%2,(j+1)%2),axis=(0,1))
                # fixed sensor channel remapping; still raw RGB input to the constructor
                if j%2: v=v[..., [1,2,0]]
                out.append(np.ascontiguousarray(v))
        else: raise ValueError(style)
        # Raw pixels themselves are the observation. No SHA/fingerprint/coordinate descriptor.
        return tuple(np.ascontiguousarray(v) for v in out)

    def obs_bytes(self,raw,style=0,size=24):
        return b''.join(v.tobytes() for v in self.render_rgb(raw,style,size))


def enumerate_hidden(game:DelayedJumpArena):
    q=deque([game.start_raw]); seen={game.start_raw}; trans={}
    while q:
        s=q.popleft()
        for a in ACTIONS:
            t=game.raw_step(s,a); trans[(s,a)]=t
            if t not in seen:
                seen.add(t); q.append(t)
    return sorted(seen),trans


def deterministic_bisim(nodes,trans,goal):
    # Exact partition refinement for a finite deterministic labelled transition system.
    cls={n:int(bool(goal[n])) for n in nodes}
    while True:
        sigs={}
        new={}; next_id=0
        for n in nodes:
            sig=(bool(goal[n]), tuple(cls[trans[(n,a)]] for a in ACTIONS))
            if sig not in sigs:
                sigs[sig]=next_id; next_id+=1
            new[n]=sigs[sig]
        if all(new[n]==cls[n] for n in nodes):
            return new
        # canonicalize old labels are arbitrary; equality of partitions, not numeric ids.
        old_groups=defaultdict(set); new_groups=defaultdict(set)
        for n in nodes: old_groups[cls[n]].add(n); new_groups[new[n]].add(n)
        if {frozenset(v) for v in old_groups.values()} == {frozenset(v) for v in new_groups.values()}:
            return new
        cls=new


def interaction_context_graph(game:DelayedJumpArena,style:int,max_nodes=20000):
    """Discover the graph using only reset, actions and four-view RGB equality.

    Each context is (raw RGB pixels, previous action). Hidden raw state is recorded
    only in a parallel audit field and is never part of the node key or expansion decision.
    """
    start_obs=game.obs_bytes(game.start_raw,style)
    start_key=(start_obs,-1)
    key_to_id={start_key:0}; id_to_key=[start_key]; paths=[tuple()]
    goal={0:game.raw_goal(game.start_raw)}
    trans={}; hidden_seen=defaultdict(set); hidden_seen[0].add(game.start_raw)
    q=deque([0]); replay_actions=0
    while q:
        u=q.popleft(); path=paths[u]
        # Replay only public actions from reset to reach this visual-history context.
        raw=game.start_raw; prev=-1
        for a in path:
            raw=game.raw_step(raw,a); prev=a; replay_actions+=1
        assert (game.obs_bytes(raw,style),prev)==id_to_key[u]
        hidden_seen[u].add(raw)
        for a in ACTIONS:
            nxt=game.raw_step(raw,a)
            key=(game.obs_bytes(nxt,style),a)
            if key not in key_to_id:
                if len(id_to_key)>=max_nodes: raise RuntimeError('context graph cap')
                v=len(id_to_key); key_to_id[key]=v; id_to_key.append(key); paths.append(path+(a,)); q.append(v)
                goal[v]=game.raw_goal(nxt)
            else: v=key_to_id[key]
            hidden_seen[v].add(nxt)
            trans[(u,a)]=v
    nodes=list(range(len(id_to_key)))
    assert len(trans)==len(nodes)*5
    return {'nodes':nodes,'trans':trans,'goal':goal,'id_to_key':id_to_key,'paths':paths,
            'hidden_seen':hidden_seen,'replay_actions':replay_actions}


def project_rgb_only(context_graph):
    # Drop previous-action history, retaining only current raw RGB. This is the k=0 baseline.
    obs_to_id={}; ctx_to_obs={}; hidden=defaultdict(set); goal=defaultdict(bool)
    for u,(obs,prev) in enumerate(context_graph['id_to_key']):
        if obs not in obs_to_id: obs_to_id[obs]=len(obs_to_id)
        o=obs_to_id[obs];ctx_to_obs[u]=o;hidden[o]|=context_graph['hidden_seen'][u];goal[o]|=context_graph['goal'][u]
    counts=defaultdict(Counter)
    for (u,a),v in context_graph['trans'].items(): counts[(ctx_to_obs[u],a)][ctx_to_obs[v]]+=1
    conflicts=[{'obs':o,'action':a,'successors':len(c),'counts':dict(c)} for (o,a),c in counts.items() if len(c)>1]
    modal={(o,a):c.most_common(1)[0][0] for (o,a),c in counts.items()}
    return {'nodes':list(range(len(obs_to_id))),'counts':counts,'modal':modal,'goal':dict(goal),'hidden':hidden,'conflicts':conflicts,
            'obs_to_id':obs_to_id,'ctx_to_obs':ctx_to_obs}


def partition_pair_metrics(pred,truth,nodes):
    tp=fp=fn=tn=0
    n=len(nodes)
    for i in range(n):
        for j in range(i+1,n):
            a,b=nodes[i],nodes[j]; ps=pred[a]==pred[b]; ts=truth[a]==truth[b]
            if ps and ts: tp+=1
            elif ps and not ts: fp+=1
            elif (not ps) and ts: fn+=1
            else: tn+=1
    precision=tp/(tp+fp) if tp+fp else 1.0
    recall=tp/(tp+fn) if tp+fn else 1.0
    f1=2*precision*recall/(precision+recall) if precision+recall else 1.0
    return {'tp':tp,'fp':fp,'fn':fn,'tn':tn,'precision':precision,'recall':recall,'f1':f1}


def make_class_control(nodes,trans,goal,part):
    classes=sorted(set(part.values())); remap={c:i for i,c in enumerate(classes)}
    c_of={n:remap[part[n]] for n in nodes}; N=len(classes)
    dest={}; goal_c=set()
    for n in nodes:
        c=c_of[n]
        if goal[n]: goal_c.add(c)
        for a in ACTIONS:
            d=c_of[trans[(n,a)]]
            if (c,a) in dest and dest[(c,a)]!=d:
                raise AssertionError('partition not transition-consistent')
            dest[(c,a)]=d
    K=np.zeros((N,N),float)
    for c in range(N):
        for a in ACTIONS: K[c,dest[(c,a)]] += 1/5
    psi=np.zeros(N)
    if goal_c: psi,*_=solve_fixed_field(K,sorted(goal_c),q=.90)
    return c_of,dest,psi,goal_c


def eval_k1_control(game,style,graph,part,horizon=60):
    c_of,dest,psi,goal_c=make_class_control(graph['nodes'],graph['trans'],graph['goal'],part)
    key_to_id={k:i for i,k in enumerate(graph['id_to_key'])}
    raw=game.start_raw; prev=-1; actions=[]; states=[raw]
    for t in range(horizon):
        if game.raw_goal(raw): break
        key=(game.obs_bytes(raw,style),prev); u=key_to_id[key]; c=c_of[u]
        vals=[psi[dest[(c,a)]] for a in ACTIONS]
        a=int(np.argmax(vals))
        raw=game.raw_step(raw,a);prev=a;actions.append(a);states.append(raw)
    return {'success':game.raw_goal(raw),'steps':len(actions),'actions':actions,'names':[ACTION_NAMES[a] for a in actions],
            'states':states}


def eval_k0_control(game,style,k0,horizon=60):
    nodes=k0['nodes']; idx={o:i for o,i in k0['obs_to_id'].items()};N=len(nodes)
    K=np.zeros((N,N),float)
    for o in nodes:
        avail=[]
        for a in ACTIONS:
            if (o,a) in k0['modal']:
                d=k0['modal'][(o,a)];K[o,d]+=1/5;avail.append(a)
            else: K[o,o]+=1/5
    goals=[o for o in nodes if k0['goal'].get(o,False)]
    psi=np.zeros(N)
    if goals: psi,*_=solve_fixed_field(K,goals,q=.90)
    raw=game.start_raw;actions=[];states=[raw]
    for t in range(horizon):
        if game.raw_goal(raw):break
        o=idx[game.obs_bytes(raw,style)]
        vals=[]
        for a in ACTIONS:
            d=k0['modal'].get((o,a),o); vals.append(psi[d])
        a=int(np.argmax(vals));raw=game.raw_step(raw,a);actions.append(a);states.append(raw)
    return {'success':game.raw_goal(raw),'steps':len(actions),'actions':actions,'names':[ACTION_NAMES[a] for a in actions],
            'states':states}


def summarize_seed(seed,outdir):
    game=DelayedJumpArena(seed,'state_opaque')
    hidden,hidden_trans=enumerate_hidden(game)
    hidden_goal={s:game.raw_goal(s) for s in hidden}
    gt=deterministic_bisim(hidden,hidden_trans,hidden_goal)

    style_graphs={s:interaction_context_graph(game,s) for s in STYLES}
    # Combine four visual/camera layouts as disconnected observation copies.
    nodes=[]; trans={};goal={}; hidden_sets={}; local_to_global={}
    for style,g in style_graphs.items():
        for u in g['nodes']:
            n=(style,u); nodes.append(n);goal[n]=g['goal'][u];hidden_sets[n]=g['hidden_seen'][u];local_to_global[(style,u)]=n
        for (u,a),v in g['trans'].items():trans[((style,u),a)]=(style,v)
    learned=deterministic_bisim(nodes,trans,goal)

    # Audit mapping to exact hidden predictive classes (never used by the learner).
    truth={}; harmful_context_alias=[]
    for n in nodes:
        gs={gt[h] for h in hidden_sets[n]}
        if len(gs)!=1: harmful_context_alias.append({'node':str(n),'gt_classes':sorted(gs),'hidden_count':len(hidden_sets[n])})
        truth[n]=min(gs)
    pair=partition_pair_metrics(learned,truth,nodes)
    learned_to_gt=defaultdict(set); gt_to_learned=defaultdict(set); class_styles=defaultdict(set)
    for n in nodes:
        learned_to_gt[learned[n]].add(truth[n]);gt_to_learned[truth[n]].add(learned[n]);class_styles[learned[n]].add(n[0])
    purity_bad={str(k):sorted(v) for k,v in learned_to_gt.items() if len(v)>1}
    completeness_bad={str(k):sorted(v) for k,v in gt_to_learned.items() if len(v)>1}
    full_style_classes=sum(len(v)==4 for v in class_styles.values())

    # k=0 diagnostic per style
    k0_by_style={s:project_rgb_only(g) for s,g in style_graphs.items()}
    k0_conflicts=sum(len(k['conflicts']) for k in k0_by_style.values())
    k0_harmful_obs=0; k0_max_gt=1
    for k in k0_by_style.values():
        for hs in k['hidden'].values():
            gs={gt[h] for h in hs};k0_max_gt=max(k0_max_gt,len(gs));k0_harmful_obs+=int(len(gs)>1)

    controls=[]
    for style in STYLES:
        c1=eval_k1_control(game,style,style_graphs[style],
            # restrict global learned partition to local nodes; labels may be global ids and are fine
            {u:learned[(style,u)] for u in style_graphs[style]['nodes']})
        c0=eval_k0_control(game,style,k0_by_style[style])
        controls.append({'style':style,'k0':c0,'k1':c1})

    result={
        'seed':seed,'hidden_reachable_states':len(hidden),'hidden_predictive_classes':len(set(gt.values())),
        'styles':4,'context_nodes_total':len(nodes),'context_nodes_per_style':{str(s):len(g['nodes']) for s,g in style_graphs.items()},
        'interaction_replay_actions':sum(g['replay_actions'] for g in style_graphs.values()),
        'k0_current_rgb_only':{'nondeterministic_state_action_pairs':k0_conflicts,'harmfully_aliased_rgb_nodes':k0_harmful_obs,
                               'max_hidden_predictive_classes_in_one_rgb':k0_max_gt},
        'k1_rgb_plus_previous_action':{'harmful_context_aliases':len(harmful_context_alias),'learned_predictive_classes':len(set(learned.values())),
                                       'pairwise_partition':pair,'purity_violations':purity_bad,'completeness_violations':completeness_bad,
                                       'classes_containing_all_4_camera_layouts':full_style_classes,
                                       'total_learned_classes':len(class_styles)},
        'controls':controls,
        'limitations':[
            'RGB observations are deterministic and exact; no learned tolerance to continuous pixel noise is tested.',
            'Camera layouts are deterministic remappings/rotations/reorderings of the four rendered views, not a photorealistic engine with arbitrary extrinsics.',
            'Partition refinement is a controlled predictive-state construction algorithm supplied for this experiment; MORTRA did not invent the algorithm.',
            'Hidden states are used only after learning for audit and ground-truth bisimulation comparison.'
        ]
    }
    outdir.mkdir(parents=True,exist_ok=True)
    # Avoid dumping pixel byte keys; save compact evidence.
    (outdir/'result.json').write_text(json.dumps(result,indent=2,default=list)+'\n')
    return result


def main():
    out=ROOT/'results';out.mkdir(exist_ok=True)
    results=[]
    for seed in SEEDS:
        print('seed',seed,flush=True);results.append(summarize_seed(seed,out/str(seed)))
    summary={
      'status':'COMPLETE_CONTROLLED_RGB_PREDICTIVE_STATE_TEST',
      'seeds':list(SEEDS),
      'aggregate':{
        'hidden_states':sum(r['hidden_reachable_states'] for r in results),
        'k0_nondeterministic_pairs':sum(r['k0_current_rgb_only']['nondeterministic_state_action_pairs'] for r in results),
        'k0_harmful_rgb_nodes':sum(r['k0_current_rgb_only']['harmfully_aliased_rgb_nodes'] for r in results),
        'k1_harmful_context_aliases':sum(r['k1_rgb_plus_previous_action']['harmful_context_aliases'] for r in results),
        'k1_partition_precision_min':min(r['k1_rgb_plus_previous_action']['pairwise_partition']['precision'] for r in results),
        'k1_partition_recall_min':min(r['k1_rgb_plus_previous_action']['pairwise_partition']['recall'] for r in results),
        'k1_camera_invariance_all':all(r['k1_rgb_plus_previous_action']['classes_containing_all_4_camera_layouts']==r['k1_rgb_plus_previous_action']['total_learned_classes'] for r in results),
        'k0_control_successes':sum(c['k0']['success'] for r in results for c in r['controls']),
        'k1_control_successes':sum(c['k1']['success'] for r in results for c in r['controls']),
        'control_cases':sum(len(r['controls']) for r in results),
      },
      'per_seed':results
    }
    (out/'summary.json').write_text(json.dumps(summary,indent=2,default=list)+'\n')
    print(json.dumps(summary['aggregate'],indent=2))

if __name__=='__main__':main()
