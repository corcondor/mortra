"""Read-only audit. No policy, game generator, simulator, or oracle is run.
BFS uses only recorded transitions; it does not enumerate environment states.
"""
from __future__ import annotations
import argparse, collections, gzip, hashlib, json, pathlib, zipfile

EXPECTED='326e01cad269f56b84b6e075a47c3e87fa3068cac73a27f2d9098b5aa9ba30ea'

def main(archive: pathlib.Path, output: pathlib.Path) -> None:
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest != EXPECTED: raise ValueError('Original artifact hash mismatch')
    z=zipfile.ZipFile(archive)
    root='v2_full_79020004_virtual_frontier/'
    prefix=root+'targeted/evaluations/evaluation_000/'
    read=lambda p: json.loads(z.read(p))
    game=read(prefix+'game.json'); learner=read(prefix+'learner.json'); metrics=read(prefix+'metrics.json')
    rows=[json.loads(line) for line in gzip.decompress(z.read(prefix+'actions.jsonl.gz')).splitlines()]
    groups=collections.defaultdict(list)
    for r in rows: groups[(r['phase'],r['trial'])].append(r)
    initial=tuple(groups[('training',None)][0]['state'])
    goal=tuple(game['goal_pos'])
    is_goal=lambda s: tuple(s[:2])==goal
    learned_states={tuple(s) for s in learner['id_to_state']}
    learned_edges=set()
    for key, counts in learner['counts']:
        u,a=key
        for v,count in counts:
            learned_edges.add((tuple(learner['id_to_state'][u]),a,tuple(learner['id_to_state'][v])))
    def reachability(edges):
        adj=collections.defaultdict(list)
        for u,a,v in sorted(edges): adj[u].append((a,v))
        q=collections.deque([initial]); prev={initial:None}
        hit=None
        while q:
            u=q.popleft()
            if is_goal(u): hit=u; break
            for a,v in adj[u]:
                if v not in prev: prev[v]=(u,a); q.append(v)
        if hit is None: return {'goal_reachable_on_recorded_edges':False,'recorded_path_length':None}
        acts=[]; cur=hit
        while prev[cur] is not None: cur,a=prev[cur]; acts.append(a)
        return {'goal_reachable_on_recorded_edges':True,'recorded_path_length':len(acts),'recorded_path_actions':list(reversed(acts))}
    result={'status':'READ_ONLY_TRACE_AUDIT','seed':79020004,'method':'virtual_frontier','evaluation':0,
        'commit':'5f8b36744a29327928c87d6db888f2f045dbea79','artifact_id':10917048485,
        'artifact_sha256':digest,'new_policy_runs':0,
        'initial_goal_position':game['goal_pos'],
        'learned_states':len(learned_states),'learned_pairs':len(learner['counts']),
        'recorded_transition_count':sum(count for key,count in learner['action_visits']),
        'goal_states_in_learned_model':sum(is_goal(s) for s in learned_states),
        'recorded_model_reachability':reachability(learned_edges),'phases':{}}
    for phase in ['mortra','random']:
        trials=sorted((trial,rr) for (p,trial),rr in groups.items() if p==phase)
        extra_edges=set(); seen_states=set(); successes=[]; sequences=collections.Counter()
        for trial,rr in trials:
            for prev,nxt in zip(rr,rr[1:]): assert prev['next_state']==nxt['state']
            assert tuple(rr[0]['state'])==initial
            sequences[tuple(r['action'] for r in rr)]+=1
            if is_goal(rr[-1]['next_state']): successes.append({'trial':trial,'steps':len(rr)})
            for r in rr:
                u,v=tuple(r['state']),tuple(r['next_state'])
                seen_states.update([u,v]); extra_edges.add((u,r['action'],v))
        assert len(trials)==50
        assert len(successes)==metrics['successes' if phase=='mortra' else 'random_successes']
        result['phases'][phase]={'trials':len(trials),'successes':len(successes),
          'actual_actions':sum(len(rr) for _,rr in trials),
          'unique_action_sequences':len(sequences),
          'constant_action_trials':sum(len({r['action'] for r in rr})==1 for _,rr in trials),
          'states_not_in_saved_learner':len(seen_states-learned_states),
          'transition_triples_not_in_saved_learner':len(extra_edges-learned_edges),
          'successful_trials':successes,
          'reachability_after_union_of_all_observed_phase_edges':reachability(learned_edges|extra_edges)}
    th=read(root+'targeted/history.json'); rh=read(root+'random_mutation/history.json')
    assert game==read(root+'targeted/game_initial.json')
    result['targeted']={'candidate_count':len(th)-1,'accepted':sum(bool(h['accepted']) for h in th[1:]),
        'candidate_successes':collections.Counter(str(h.get('candidate_metrics',{}).get('successes')) for h in th[1:]),
        'final_game_equals_initial':read(root+'targeted/game_final.json')==game}
    first=next((h for h in rh[1:] if h['accepted'] and h['metrics']['successes']>0),None)
    result['random_mutation_first_accepted_solved_candidate']={k:first[k] for k in ('iteration','mutation','decision_reason')} if first else None
    if first: result['random_mutation_first_accepted_solved_candidate'].update(goal_position=first['game']['goal_pos'],successes=first['metrics']['successes'])
    result['limitations']=['One outcome-selected failure case, development diagnosis only.',
        'Recorded random baseline data are used only in a diagnostic union; do not train a production learner on held-out evaluation traces.',
        'A path in the union of recorded transitions does not prove the current greedy field readout follows it.',
        'This script does not execute a revised policy or prove the proposed integration improves performance.']
    output.parent.mkdir(parents=True,exist_ok=True); output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('archive',type=pathlib.Path); p.add_argument('output',type=pathlib.Path); a=p.parse_args();main(a.archive,a.output)
