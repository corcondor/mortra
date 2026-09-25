"""Replay frozen full-info policies, alongside separately labelled linear solves."""
from collections import deque
import hashlib
import math
from pathlib import Path
import time
from types import FunctionType
import numpy as np
from scipy.sparse import csc_matrix, eye
from scipy.sparse.linalg import splu

from experiments.game_frontier_v11 import measurement as frozen
from .data import original, read, write, csv_write, source_files, frozen_sources
from .maths import path_attenuation


def shortest_path(edges, start, goal):
    todo=deque([start]); back={start:None}
    while todo:
        u=todo.popleft()
        if u==goal: break
        for v in edges[u]:
            if v not in back: back[v]=u; todo.append(v)
    assert goal in back
    path=[goal]
    while path[-1]!=start: path.append(back[path[-1]])
    return path[::-1]


def diagnose(b, a):
    engine=original.frozen.Engine(b['genome'])
    stats,graph=original.frozen.oracle(engine,original.config()['oracle_cap'])
    assert graph is not None and stats==b['archived_final']['oracle']
    states,edges,ids=graph
    labels=frozen.OpaqueMap(b['diagnostic_seed']); learner=frozen.StructuralLearner(engine.num_actions)
    for s in states: learner.get_or_add_id(labels.encode(s))
    for u,row in enumerate(edges):
        for action,v in enumerate(row): learner.record_transition(u,action,v)
    K=learner.build_k_support(); n=len(K)
    assert np.allclose(K.sum(axis=1),1,atol=1e-14)
    matrix=eye(n,format='csc')-.9*csc_matrix(K)
    lu=splu(matrix)
    norm_vector=lu.solve(np.ones(n))
    # Nonnegative resolvent: infinity norm is the largest row sum, computed by R*1.
    norm=float(np.max(norm_vector))
    field_cache={}
    def solver(k, target, **kwargs):
        assert k is K
        if target not in field_cache:
            approx=frozen.solve_fixed_field(k,target,**kwargs)
            g=np.zeros(n);g[target]=1
            exact=lu.solve(g)
            residual=float(np.max(np.abs(g+.9*K@exact-exact)))
            field_cache[target]=(approx,exact,residual)
        return field_cache[target][0]
    space=dict(frozen.run_fixed_field_policy.__globals__); space['solve_fixed_field']=solver
    policy=FunctionType(frozen.run_fixed_field_policy.__code__,space,frozen.run_fixed_field_policy.__name__,frozen.run_fixed_field_policy.__defaults__)
    trace={};port=frozen.make_port(engine,labels,trace)
    attenuation=[];diagnostics=[];resolvents=[]
    rng_state=np.random.get_state()
    try:
        for split,tasks,archived in (('selection',b['archived_final']['tasks'],a['full_info_selection']),
                                     ('holdout',b['holdout_tasks'],a['full_info_holdout'])):
            assert len(tasks)==len(archived['task_results'])
            for task,saved in zip(tasks,archived['task_results']):
                s,t=tuple(task['start']),tuple(task['target']);u,v=ids[s],ids[t]
                port.reset(labels.encode(s));np.random.seed(task['rng_seed'])
                ok,steps,reason=policy(port,labels.encode(s),labels.encode(t),K,learner.state_to_id,learner.counts,max_steps=original.config()['horizon'])
                assert (bool(ok),steps,reason)==(saved['success'],saved['core_reported_steps'],saved['reason'])
                assert hashlib.sha256(frozen.canonical(trace).encode()).hexdigest()==saved['trajectory_sha256']
                approx,exact,residual=field_cache[v];psi=approx[0]
                path=shortest_path(edges,u,v)
                weights=[K[i,j] for i,j in zip(path,path[1:])]
                base=dict(seed=b['seed'],game_hash=b['game_hash'],split=split,task_id=task['task_id'],
                          world_classification=a['classification'],success=bool(ok))
                attenuation.append(dict(**base,**path_attenuation(weights),
                    local_support_mean=float(np.mean([np.count_nonzero(K[i]) for i in path[:-1]])),
                    path=path,path_weights=list(map(float,weights)),start_psi_frozen=float(psi[u]),start_psi_exact=float(exact[u])))
                visited=[ids[tuple(s)] for s in trace['states']]
                cut=next((i for i,node in enumerate(visited) if node!=v and psi[node]<1e-7),None)
                ranking_drops=sum(exact[j]<=exact[i] for i,j in zip(visited,visited[1:]))
                cycle=len(set(visited))<len(visited)
                category=('SUCCESS' if ok else 'A_START_BELOW_CUTOFF' if psi[u]<1e-7 else
                          'C_READOUT_CYCLE' if cycle else 'B_PATH_FAILS_AFTER_START' if psi[u]>=1e-7 else 'D_OTHER')
                diagnostics.append(dict(**base,category=category,core_reason=reason,actions=len(trace['actions']),
                    exact_start_below_cutoff=bool(exact[u]<1e-7),frozen_start_below_cutoff=bool(psi[u]<1e-7),
                    cutoff_crossing_step=cut,cycle=cycle,exact_field_nonincreasing_chosen_edges=int(ranking_drops),
                    modal_successor_error=False,trajectory_sha256=saved['trajectory_sha256']))
                resolvents.append(dict(**base,N=n,spectral_radius_K=1.,spectral_radius_basis='complete nonnegative row-stochastic K',
                    row_sum_error=float(np.max(np.abs(K.sum(axis=1)-1))),resolvent_inf_norm=norm,
                    start_psi_exact=float(exact[u]),start_psi_frozen=float(psi[u]),linear_solve_residual=residual,
                    frozen_iterations=approx[1],frozen_increment_residual=approx[2],frozen_converged=approx[3],
                    max_field_difference=float(np.max(np.abs(exact-psi))),
                    min_positive_exact_on_success_path=min((float(exact[i]) for i in visited if exact[i]>0),default=None) if ok else None,
                    cutoff_crossing_step=cut))
    finally: np.random.set_state(rng_state)
    return attenuation,diagnostics,resolvents


def run(source, output, seed, smoke=False):
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    hashes=frozen_sources();_,bundles,audits=source_files(source,require_evolution=False)
    chosen=[k for k in sorted(bundles) if k[0]==seed]
    if smoke:
        assert seed==2101
        chosen=[k for k in chosen if any(r['condition']=='adaptive' and r['generation'] in (0,5,10) for r in read(bundles[k])['references'])]
        assert len(chosen)==3
    rows=[[],[],[]];t0=time.process_time()
    with (out/'run.log').open('x',encoding='utf-8',buffering=1) as log:
        try:
            for key in chosen:
                b,a=read(bundles[key]),read(audits[key])
                result=diagnose(b,a)
                for dst,src in zip(rows,result): dst.extend(src)
                for name,rs in zip(('task_path_attenuation','reasoner_failure_diagnostics','resolvent_diagnostics'),rows):
                    csv_write(out/(name+'.csv'),rs)
                msg=f"COMPLETE {key} tasks={len(result[0])}";print(msg,flush=True);log.write(msg+'\n')
            assert hashes==frozen_sources()
            write(out/'completed.json',dict(status='COMPLETED',worlds=len(chosen),tasks=len(rows[0]),CPU_seconds=time.process_time()-t0))
        except BaseException as exc:
            write(out/'incomplete.json',dict(status='RUN_NOT_COMPLETED',reason=repr(exc)));raise
