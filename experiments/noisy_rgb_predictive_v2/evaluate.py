"""Checkpoint-only evaluator; ground truth is confined to this module."""
import ast
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import time

import numpy as np

from experiments.noisy_rgb_discovery.core import Statistics
from experiments.noisy_rgb_discovery.evaluate import replay,truth
from experiments.noisy_rgb_discovery.sensor import make_game
from experiments.noisy_rgb_discovery.source import environment_class
from experiments.noisy_rgb_discovery.run import write
from experiments.noisy_rgb_version_space.core import SAME,DIFFERENT,UNRESOLVED,stability
from experiments.noisy_rgb_version_space.runtime import Budget,ResourceLimit,stage_sensors
from .core import CandidateBelief,AdaptiveDiscriminationTree,EMPIRICAL
from .snapshots import load_statistics,verify_checkpoint,confirmed_graph
from .public_labels import PublicLabels,labelled_game,labelled_stages


class FrozenEvidence:
    def __init__(self,prototypes,statistics,threshold):
        self.prototypes,self.statistics,self.threshold=prototypes,statistics,threshold
        self.cache={}
        self.reference_cache={}
        self.score=Statistics(None)
        self.version=0
    def compare(self,h,r,e=(),stage=32):
        key=(tuple(h),tuple(r),tuple(e))
        if key in self.cache:
            return self.cache[key]
        words=(tuple(h)+tuple(e),tuple(r)+tuple(e))
        values=[]
        for n in (8,16,32):
            for j in (0,1):
                proto=self.prototypes[n].get((words[1],j))
                if proto is None:
                    return dict(result=UNRESOLVED,id=None,stage=32,reason='prototype_unobserved_at_checkpoint')
                current=self.statistics[n].summary(words[0],j)
                values.append(self.score.z(current,proto))
        result=dict(result=stability(values,self.threshold,32),id=None,stage=32,scores=values)
        self.cache[key]=result
        return result
    def cached_result(self,h,r,e):
        pair=tuple(sorted((tuple(h)+tuple(e),tuple(r)+tuple(e))))
        if pair[0]==pair[1]:
            return SAME
        if pair not in self.reference_cache:
            values=[]
            for n in (8,16,32):
                for j in (0,1):
                    a=self.prototypes[n].get((pair[0],j))
                    b=self.prototypes[n].get((pair[1],j))
                    if a is None or b is None:
                        return UNRESOLVED
                    values.append(self.score.z(a,b))
            self.reference_cache[pair]=stability(values,self.threshold,32)
        return self.reference_cache[pair]


class FrozenReadout:
    def __init__(self,state,arm,evidence,label_equality=None):
        self.state,self.arm,self.evidence=state,arm,evidence
        self.reps=list(map(tuple,state['representatives']))
        self.tree=AdaptiveDiscriminationTree(evidence,lambda e:None)
        self.probes=[(a,) for a in range(5)]+[(a,b) for a in range(5) for b in range(5)]
        for q,r,e,c in state.get('tree_witnesses',[]):
            self.tree.witnesses[q,r,tuple(e)]=c
        self.trans=confirmed_graph(state,arm)
        self.nodes={tuple(n['history']):n for n in state.get('nodes',[])}
        self.label_equality=label_equality or (lambda h,r,e:UNRESOLVED)
    def classify(self,h,active=True):
        if self.arm=='V1':
            candidates=set(range(len(self.reps)))
            for e in map(tuple,self.state['suffixes']):
                candidates={q for q in candidates if self.evidence.compare(h,self.reps[q],e)['result']!=DIFFERENT}
                if not candidates:
                    break
            return CandidateBelief(candidates,False,'V1_CLOSED_WORLD_ASSUMPTION')
        belief,_=self.tree.classify(h,self.reps,recognize_replay=False)
        used=[]
        if active:
            while belief.existing_candidates and len(used)<len(self.probes):
                available=[e for e in self.probes if e not in used]
                depth=min(map(len,available))
                qs=sorted(belief.existing_candidates)
                def score(e):
                    return sum(self.evidence.cached_result(self.reps[q],self.reps[r],e)!=DIFFERENT
                               for q in qs for r in qs)/len(qs)+1
                e=min((e for e in available if len(e)==depth),key=lambda e:(score(e),e))
                used.append(e)
                belief.existing_candidates={q for q in qs if self.evidence.compare(h,self.reps[q],e)['result']!=DIFFERENT}
        certified=[]
        for q in sorted(belief.existing_candidates):
            observed={a for a,_ in self.nodes.get(self.reps[q],{}).get('outgoing',[])}==set(range(5))
            outcomes=[self.evidence.cache.get((tuple(h),self.reps[q],e),{}).get('result',UNRESOLVED)
                      for e in [()]+self.probes]
            labels=all(self.label_equality(h,self.reps[q],e)==SAME for e in [()]+self.probes)
            certified.append(observed and labels and all(x==SAME for x in outcomes))
        if certified and all(certified):
            belief.new_state_possible=False
            belief.identity_scope=EMPIRICAL
        return belief


def evaluation_reader(state,arm,prototypes,threshold,seed,bias,output,phase,budget):
    if arm=='V1':
        sensors,stats=stage_sensors(make_game(seed),bias,output,phase,budget)
        return sensors,FrozenReadout(state,arm,FrozenEvidence(prototypes,stats,threshold))
    reference=PublicLabels(state.get('public_labels',[]))
    observed=PublicLabels()
    sensors,stats=labelled_stages(labelled_game(seed),bias,output,phase,budget,observed)
    def equality(h,r,e):
        x=observed.records.get(tuple(h)+tuple(e))
        y=reference.records.get(tuple(r)+tuple(e))
        return UNRESOLVED if x is None or y is None else (SAME if x==y else DIFFERENT)
    return sensors,FrozenReadout(state,arm,FrozenEvidence(prototypes,stats,threshold),equality)


def audit(state,arm,game):
    _,_,_,partition=truth(game,tuple(range(5)),12)
    reps=list(map(tuple,state['representatives']))
    qtruth=[partition[replay(game,h)] for h in reps]
    provisional=[tuple(n['history']) for n in state.get('nodes',[]) if n['status']=='provisional']
    provision_truth={partition[replay(game,h)] for h in provisional}
    edges=confirmed_graph(state,arm)
    errors=[]
    for (q,a),t in edges.items():
        target=partition[replay(game,reps[q]+(a,))]
        if target!=qtruth[t]:
            errors.append([q,a,t,target,qtruth[t]])
    return dict(confirmed_representative_count=len(reps),provisional_node_count=len(provisional),
        represented_confirmed_true_classes=len(set(qtruth)),represented_provisional_true_classes=len(provision_truth),
        represented_union_true_classes=len(set(qtruth)|provision_truth),true_predictive_classes=len(set(partition.values())),
        confirmed_over_split=len(reps)-len(set(qtruth)),known_transitions=len(edges),transition_errors=errors,
        transition_prediction_error=len(errors)/len(edges) if edges else None,
        note='Provisional history nodes are not confirmed states. Union coverage is reported separately.'),partition,qtruth


def evaluate_checkpoint(folder,output,seed,camera,arm,bias):
    verify_checkpoint(folder)
    output.mkdir(parents=True,exist_ok=False)
    state=json.loads((folder/'state.json').read_text())
    metadata=json.loads((folder/'checkpoint.json').read_text())
    prototypes=load_statistics(folder)
    game=make_game(seed)
    model_audit,partition,qtruth=audit(state,arm,game)
    write(output/'model_audit.json',model_audit)
    budget=Budget(max_actions=10000000,max_exposures=2000000,max_wall_seconds=1800)
    sensors,readout=evaluation_reader(state,arm,prototypes,metadata['threshold'],seed,bias,output,'heldout',budget)
    rng=np.random.default_rng(seed+1000000)
    totals=Counter()
    sizes=[]
    started,cpu=time.perf_counter(),time.process_time()
    status='COMPLETED'
    try:
        with gzip.open(output/'heldout_cases.jsonl.gz','wt',encoding='utf-8') as stream:
            for episode in range(200):
                h=()
                for step in range(25):
                    h+=(int(rng.integers(5)),)
                    belief=readout.classify(h)
                    candidates=sorted(belief.existing_candidates)
                    target=partition[replay(game,h)]
                    unique=len(candidates)==1 and not belief.new_state_possible
                    correct=unique and qtruth[candidates[0]]==target
                    covered=target in {qtruth[q] for q in candidates}
                    new_is_true=target not in set(qtruth)
                    totals['cases']+=1
                    totals['correct_unique']+=correct
                    totals['wrong_unique']+=unique and not correct
                    totals['unresolved']+=not unique
                    totals['candidate_coverage']+=covered
                    totals['coverage_including_NEW']+=covered or (belief.new_state_possible and new_is_true)
                    totals['NEW_possible']+=belief.new_state_possible
                    sizes.append(len(candidates))
                    stream.write(json.dumps(dict(episode=episode,step=step+1,history=h,belief=belief.record(),
                        true_class=target,correct_unique=correct,candidate_coverage=covered,new_class_unrepresented=new_is_true))+'\n')
    except ResourceLimit as exc:
        status='INCOMPLETE_EVALUATION_RESOURCE_'+str(exc)
    finally:
        for sensor in sensors.values():
            sensor.close()
    result=dict(status=status,planned_cases=5000,**totals,mean_candidate_set_size=float(np.mean(sizes)) if sizes else None,
                environment_actions=budget.actions,exposure_sets=budget.exposures,
                cpu_seconds=time.process_time()-cpu,wall_seconds=time.perf_counter()-started)
    for key in ('correct_unique','wrong_unique','unresolved','candidate_coverage','coverage_including_NEW'):
        result[key+'_rate']=totals[key]/5000 if totals['cases']==5000 else None
        result[key+'_partial_rate']=totals[key]/totals['cases'] if totals['cases'] else None
    write(output/'heldout_summary.json',result)
    control_result=control(state,arm,prototypes,metadata['threshold'],seed,bias,output)
    verify_checkpoint(folder)
    combined=dict(checkpoint=metadata,model_audit=model_audit,heldout=result,control=control_result,frozen_inputs_unchanged=True)
    write(output/'result.json',combined)
    return combined


def unanimous_action(belief,trans,psi):
    if belief.new_state_possible or not belief.existing_candidates:
        return None
    choices=[]
    for q in sorted(belief.existing_candidates):
        options=[(float(psi[t]),a) for (s,a),t in trans.items() if s==q]
        if not options:
            return None
        score,a=min(options,key=lambda x:(-x[0],x[1]))
        if score<=0:
            return None
        choices.append(a)
    return choices[0] if len(set(choices))==1 else None


def control(state,arm,prototypes,threshold,seed,bias,output):
    game=environment_class()(seed,'state_opaque')
    reps=list(map(tuple,state['representatives']))
    trans=confirmed_graph(state,arm)
    labels=[]
    label_actions=0
    for q,h in enumerate(reps):
        raw=game.start_raw
        for a in h:
            raw=game.raw_step(raw,a)
            label_actions+=1
        labels.append(dict(q=q,history=h,public_goal=bool(game.raw_goal(raw))))
    goals=[r['q'] for r in labels if r['public_goal']]
    solver_source=Path('scripts/evaluate_autonomous_game_design_loop.py').read_bytes()
    fn=[n for n in ast.parse(solver_source).body if isinstance(n,ast.FunctionDef) and n.name=='solve_fixed_field']
    env={'np':np}
    exec(compile(ast.Module(body=fn,type_ignores=[]),'frozen_solver','exec'),env)
    K=np.zeros((len(reps),len(reps)))
    for (q,a),t in trans.items():
        K[q,t]+=1/5
    psi,iterations,residual,converged=env['solve_fixed_field'](K,goals,q=.90)
    budget=Budget(max_actions=1000000,max_exposures=500000,max_wall_seconds=1800)
    sensors,reader=evaluation_reader(state,arm,prototypes,threshold,seed,bias,output,'control',budget)
    raw,h=game.start_raw,()
    belief=CandidateBelief({0},False,'EXACT_RESET')
    trace=[]
    status='CONTROL_HORIZON'
    cpu=time.process_time()
    try:
        for step in range(60):
            if game.raw_goal(raw):
                status='SUCCESS'
                break
            if not goals:
                status='NO_OBSERVED_GOAL'
                break
            action=unanimous_action(belief,trans,psi)
            if action is None:
                belief=reader.classify(h,active=True)
                action=unanimous_action(belief,trans,psi)
                if action is None:
                    status='UNRESOLVED'
                    break
            previous=belief.record()
            next_candidates={trans[q,action] for q in belief.existing_candidates if (q,action) in trans}
            assert len(next_candidates)>0 and all((q,action) in trans for q in belief.existing_candidates)
            raw=game.raw_step(raw,action)
            h+=(action,)
            belief=CandidateBelief(next_candidates,False,'FROZEN_OBSERVED_TRANSITION')
            observed=reader.classify(h,active=False)
            # Visual disagreement reopens identity. Missing prototypes also
            # keep uncertainty; there is no true-state fallback.
            if not next_candidates.issubset(observed.existing_candidates):
                belief=observed
            trace.append(dict(step=step+1,action=action,before=previous,after=belief.record(),
                              visual_candidates=observed.record(),public_goal=bool(game.raw_goal(raw))))
        if game.raw_goal(raw):
            status='SUCCESS'
    except ResourceLimit as exc:
        status='INCOMPLETE_CONTROL_RESOURCE_'+str(exc)
    finally:
        for sensor in sensors.values():
            sensor.close()
    result=dict(status=status,success=bool(game.raw_goal(raw)),control_steps=len(trace),trace=trace,
        goal_labels=labels,goal_label_actions=label_actions,probe_replay_actions=budget.actions,
        probe_exposures=budget.exposures,total_environment_actions=label_actions+budget.actions+len(trace),
        cpu_seconds=time.process_time()-cpu,q=.90,iterations=iterations,residual=residual,converged=converged,
        solver_sha256=hashlib.sha256(solver_source).hexdigest(),
        unknown_transition_rule='absent, never completed as a self-loop; K is the substochastic known-edge operator')
    write(output/'control.json',result)
    return result
