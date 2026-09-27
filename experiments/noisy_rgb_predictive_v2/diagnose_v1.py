"""Exact read-only replay of V1 from saved statistics, never a sensor."""
import argparse
import ast
from collections import Counter
import gzip
import hashlib
import inspect
import json
from pathlib import Path
import time

import numpy as np

from experiments.noisy_rgb_discovery.core import Emission, Statistics
from experiments.noisy_rgb_discovery.evaluate import replay, truth
from experiments.noisy_rgb_discovery.sensor import make_game
from experiments.noisy_rgb_discovery.run import write
from experiments.noisy_rgb_version_space import core
from experiments.noisy_rgb_version_space.runtime import ResourceLimit


def minimum_cover(masks, universe):
    """Exact finite set cover of the recorded exclusions, not unobserved tests."""
    if not universe:
        return []
    masks = [(tuple(e), mask & universe) for e, mask in masks if mask & universe]
    assert universe == __import__('functools').reduce(int.__or__, (m for _, m in masks), 0)
    masks.sort(key=lambda x: (len(x[0]), x[0]))
    # Equal or subset masks cannot improve the minimum cardinality.
    masks = [(e,m) for i,(e,m) in enumerate(masks) if not any(
        (m | n) == n and (m != n or j < i) for j,(_,n) in enumerate(masks) if i != j)]
    memo = {0: ()}
    def solve(left):
        if left in memo:
            return memo[left]
        bits = [1 << b for b in range(left.bit_length()) if left >> b & 1]
        pivot = min(bits, key=lambda b: sum(bool(m & b) for _,m in masks))
        best = None
        for e,mask in masks:
            if mask & pivot:
                candidate = tuple(sorted((e,)+solve(left & ~mask)))
                if best is None or (len(candidate),candidate) < (len(best),best):
                    best = candidate
        memo[left] = best
        return best
    return list(solve(universe))


def diagnose(folder, output):
    output.mkdir(parents=True, exist_ok=False)
    saved = json.loads((folder/'result.json').read_text())
    assert saved['arm'] == 'V'
    table_saved = json.loads((folder/'partial_table.json').read_text())
    hashes = {name.replace('\\','/'): value for name,value in
              json.loads((folder/'artifact_hashes.json').read_text()).items()}
    used_files = ['result.json','partial_table.json','events.jsonl.gz','calibration.json']
    for n in (8,16,32):
        used_files += [f'statistics_{n}/statistics_index.json',f'statistics_{n}/statistics.bin.gz',
                      f'training_{n}/queries.jsonl.gz']
    for name in used_files:
        assert hashlib.sha256((folder/name).read_bytes()).hexdigest() == hashes[name], name
    _,_,_,partition = truth(make_game(saved['seed']), tuple(range(5)), 12)
    game = make_game(saved['seed'])
    cls_cache = {}
    def cls(h):
        h = tuple(h)
        if h not in cls_cache:
            cls_cache[h] = partition[replay(game,h)]
        return cls_cache[h]
    calibration = json.loads((folder/'calibration.json').read_text())
    usage = Counter()
    context = ['other']
    cal_sensor = next(s for s in saved['acquisition_sensors'] if s['namespace']=='calibration-v1')
    budget = dict(actions=cal_sensor['environment_actions'], exposures=cal_sensor['exposures'])
    class StoredStatistics(Statistics):
        def __init__(self, n):
            super().__init__(None)
            self.n = n
            keys = json.loads((folder/f'statistics_{n}/statistics_index.json').read_text())
            self.keys = [(tuple(h),rep) for h,rep in keys]
            with gzip.open(folder/f'statistics_{n}/statistics.bin.gz','rb') as f:
                data = np.frombuffer(f.read(),'<f4').reshape(-1,2,1728)
            self.saved = {key: Emission(row[0],row[1],n) for key,row in zip(self.keys,data)}
            assert len(self.saved) == len(data) == len(self.keys)
        def summary(self,h,rep=0):
            key = (tuple(h),rep)
            if key not in self.cache:
                if budget['exposures']+self.n > 500000:
                    raise ResourceLimit('exposure_sets')
                if budget['actions']+len(h) > 1000000:
                    raise ResourceLimit('environment_actions')
                assert key == self.keys[len(self.cache)], ('query order', self.n, key)
                self.cache[key] = self.saved[key]
                budget['exposures'] += self.n
                budget['actions'] += len(h)
                usage[context[0]+'_queries'] += 1
                usage[context[0]+'_exposures'] += self.n
                usage[context[0]+'_actions'] += len(h)
            return self.cache[key]
    stats = {n:StoredStatistics(n) for n in (8,16,32)}
    source = Path(core.__file__).read_text()
    syntax = ast.parse(source)
    block = next(n for n in ast.walk(syntax) if isinstance(n,ast.If)
                 and ast.unparse(n.test).startswith('consistency and'))
    class TracedEvidence(core.Evidence):
        def compare(self,*args,**kwargs):
            frame = inspect.currentframe().f_back
            previous = context[0]
            if frame.f_code.co_name == 'resolve' and block.lineno <= frame.f_lineno <= block.end_lineno:
                context[0] = 'consistency'
            try:
                return super().compare(*args,**kwargs)
            finally:
                context[0] = previous
    original = gzip.open(folder/'events.jsonl.gz','rt',encoding='utf-8')
    ignored = {'calibrated','resource_limit','acquisition_frozen'}
    def next_original():
        for line in original:
            row = json.loads(line)
            if row['event'] not in ignored:
                row.pop('elapsed_seconds',None)
                return row
        return None
    counts, suffix_use, minima = Counter(), Counter(), Counter()
    evidence = table = None
    details = gzip.open(output/'membership_diagnostics.jsonl.gz','wt',encoding='utf-8')
    def emit(row):
        expected = next_original()
        actual = json.loads(json.dumps(row))
        assert actual == expected, (row['event'], actual, expected)
        counts['exact_events_replayed'] += 1
        if row['event'] != 'candidate_set':
            return
        h = tuple(row['history'])
        reps = table.S[:row['representative_count']]
        new_class = cls(h) not in {cls(r) for r in reps}
        counts['candidate_snapshots'] += 1
        counts['true_class_unrepresented_snapshots'] += new_class
        outcomes, unresolved = Counter(), []
        masks = Counter()
        suffixes = list(table.E)
        if 'probe' in row and tuple(row['probe']) not in suffixes:
            suffixes.append(tuple(row['probe']))
        for q,r in enumerate(reps):
            values = []
            for e in suffixes:
                pair = tuple(sorted((h+e,tuple(r)+e)))
                cert = evidence.cache.get((pair,row['stage']))
                result = core.SAME if pair[0]==pair[1] else cert['result'] if cert else 'NOT_MEASURED'
                values.append(result)
                if result == core.DIFFERENT:
                    masks[e] |= 1 << q
            outcome = core.DIFFERENT if core.DIFFERENT in values else core.SAME if all(v==core.SAME for v in values) else core.UNRESOLVED
            outcomes[outcome] += 1
            if outcome == core.UNRESOLVED:
                unresolved.append(dict(representative=q,history=r))
        for item in row['exclusions']:
            suffix_use[str(tuple(item['suffix']))] += 1
            masks[tuple(item['suffix'])] |= 1 << item['q']
        unique = len(row['candidates']) == 1 and row['stage']==32
        subset = None
        if unique:
            universe = ((1 << len(reps))-1) & ~(1 << row['candidates'][0])
            subset = minimum_cover(list(masks.items()),universe)
            minima[len(subset)] += 1
        if new_class or unique:
            details.write(json.dumps(dict(event_index=counts['exact_events_replayed'],history=h,
                membership_query=table.counts['membership_queries'], stage=row['stage'],
                candidates=row['candidates'], representative_count=len(reps),
                true_class_unrepresented=new_class, pair_outcomes=outcomes,
                unresolved_blockers=unresolved, last_unresolved_pair=unresolved[-1] if unresolved else None,
                minimum_recorded_suffix_subset=subset, active_suffixes=suffixes))+'\n')
        if new_class:
            counts.update({'unrepresented_'+k:v for k,v in outcomes.items()})
    evidence = TracedEvidence(stats,calibration['threshold'],saved['camera'],emit)
    table = core.CandidateLearner(evidence,tuple(range(5)),emit)
    started = time.perf_counter()
    try:
        _, status = table.learn()
    except ResourceLimit as exc:
        status = 'INCOMPLETE_RESOURCE_LIMIT'
        assert str(exc) == saved['resource_reason']
    assert next_original() is None
    assert status == saved['status']
    assert json.loads(json.dumps(table.S)) == table_saved['S']
    assert json.loads(json.dumps(table.E)) == table_saved['E']
    assert budget['exposures'] == saved['acquisition_exposure_sets']
    assert budget['actions'] == saved['acquisition_environment_actions']
    assert counts['true_class_unrepresented_snapshots'] == saved['acquisition_audit']['true_class_unrepresented']
    for s in stats.values():
        assert list(s.cache) == s.keys
    details.close()
    original.close()
    result = dict(seed=saved['seed'],camera=saved['camera'],passed=True,mode='READ_ONLY_SAVED_STATISTICS',
        new_sensor_operations=0,recorded_status=status,counts=counts,cost_attribution=usage,
        suffix_first_exclusion_usage=suffix_use,minimum_subset_size_histogram=minima,
        replay_cpu_wall_seconds=time.perf_counter()-started,
        notes=['Costs attribute only first uncached saved queries to their original call site.',
               'Minimum subsets use only certificates already recorded at that event; exact minimum cardinality.',
               'NOT_MEASURED pairs remain unresolved; no new RGB was acquired.',
               'A last unresolved pair is a recorded blocker, not a counterfactual proof that removing it would create a state.'])
    write(output/'diagnosis.json',result)
    print(json.dumps(result),flush=True)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    folders=[f.parent for f in args.input.rglob('result.json')]
    assert len(folders)==1
    diagnose(folders[0],args.output)


if __name__=='__main__':
    main()
