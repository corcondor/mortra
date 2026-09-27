"""Saved checkpoint audit only. Never return truth to a learner."""
import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from experiments.noisy_rgb_v2_redundancy_audit.quotient import analyze_table, partitions
from experiments.noisy_rgb_v2_redundancy_audit.truth_table import static_table
from experiments.noisy_rgb_predictive_v2.snapshots import confirmed_graph
from .core import signature, signature_id
from experiments.noisy_rgb_v2_redundancy_audit.artifacts import EXECUTION


def dump(path, value):
    with path.open('x', encoding='utf-8') as f:
        json.dump(value, f, indent=2, allow_nan=False)


def checkpoint_metrics(state, meta, cache, events, attempts, table, layers, arm, evaluation):
    reps = list(map(tuple, state['representatives']))
    labels = {tuple(h): v for h, v in state['public_labels']}
    at_cache = {(): table['start']}
    def at(history):
        h = tuple(history)
        if h not in at_cache:
            at_cache[h] = table['transitions'][at(h[:-1])][h[-1]]
        return at_cache[h]
    def cached(h, r, e):
        pair = tuple(sorted((h+e, r+e)))
        return 'SAME' if pair[0] == pair[1] else cache.get(pair, {}).get('result', 'NOT_COMPARED')
    assert all(c['id'] <= state['evidence_version'] for c in cache.values())
    truth = layers[-1]
    groups = defaultdict(list)
    signatures = {}
    membership = {}
    for item in state['nodes']:
        if item['status'] != 'provisional':
            continue
        node = SimpleNamespace(**dict(item, history=tuple(item['history']), outgoing=dict(item['outgoing']),
            belief=SimpleNamespace(**item['belief'])))
        value = signature(node, reps, labels, cached)
        key = signature_id(value)
        signatures[key] = value
        groups[key].append((node.history, truth[at(node.history)]))
        membership[node.history] = key
    if arm == 'B':
        assert membership == {tuple(h): k for h, k in state['family_membership']}, 'Saved family signature mismatch'
    size = list(map(len, groups.values()))
    history_probes, history_repeats = Counter(), Counter()
    for (history,suffix),count in attempts.items():
        history_probes[history] += count
        history_repeats[history] += max(count-1,0)
    registry={f['id']: f for f in state.get('family_scheduler_memory',{}).get('registry',[])}
    family_rows = [dict(id=key, nodes=len(members), true_classes=len({c for h, c in members}),
                        class_counts=dict(Counter(c for h, c in members)), members=members,
                        current_members_probe_attempts=sum(history_probes[h] for h,c in members),
                        current_members_repeated_probe_attempts=sum(history_repeats[h] for h,c in members),
                        scheduling_family_lifetime_trials=(sum(n for e,n in registry[key]['trials']) if key in registry else None),
                        signature=signatures[key]) for key, members in sorted(groups.items())]
    active_wrong = 0
    ever_wrong = 0
    active_merged = 0
    historical_merges = 0
    for n in state['nodes']:
        c = truth[at(n['history'])]
        if n['status'] == 'merged':
            active_merged += 1
            active_wrong += any(truth[at(reps[q])] != c for q in n['belief']['existing_candidates'])
        for m in n.get('merge_records', []):
            historical_merges += 1
            ever_wrong += any(truth[at(reps[q])] != c for q in m['representatives'])
    qtruth=[truth[at(h)] for h in reps]
    provisional_truth={c for members in groups.values() for h,c in members}
    edges=confirmed_graph(state,'V2')
    errors=[(q,a,t) for (q,a),t in edges.items() if truth[table['transitions'][at(reps[q])][a]] != qtruth[t]]
    model=dict(confirmed_representative_count=len(reps), represented_confirmed_true_classes=len(set(qtruth)),
        represented_provisional_true_classes=len(provisional_truth), represented_union_true_classes=len(set(qtruth)|provisional_truth),
        true_predictive_classes=len(set(truth)), known_transitions=len(edges), transition_errors=errors,
        transition_prediction_error=len(errors)/len(edges) if edges else None)
    if evaluation:
        for name in ('confirmed_representative_count','represented_confirmed_true_classes',
                     'represented_provisional_true_classes','represented_union_true_classes','true_predictive_classes','known_transitions'):
            assert model[name] == evaluation['model_audit'][name], (name,model[name],evaluation['model_audit'][name])
        assert len(errors) == len(evaluation['model_audit']['transition_errors'])
    heldout = evaluation['heldout'] if evaluation else {}
    control = evaluation['control'] if evaluation else {}
    union = model.get('represented_union_true_classes')
    family_counts = state.get('family_counts', {})
    row = dict(arm=arm, seed=meta['seed'], camera=meta['camera'], checkpoint=meta['target_exposures'],
        actual_exposures=meta['actual_exposures'], actions=meta['environment_actions'],
        checkpoint_reached=meta['requested_checkpoint_reached'], provisional_nodes=sum(size),
        families=len(groups) if arm == 'B' else None, signature_families=len(groups),
        mean_nodes_per_family=float(np.mean(size)) if size else 0,
        p50_nodes_per_family=float(np.percentile(size, 50)) if size else 0,
        p95_nodes_per_family=float(np.percentile(size, 95)) if size else 0,
        max_nodes_per_family=max(size, default=0), pure_families=sum(r['true_classes']==1 for r in family_rows),
        mixed_families=sum(r['true_classes']>1 for r in family_rows),
        max_classes_per_family=max((r['true_classes'] for r in family_rows), default=0),
        confirmed_representatives=model.get('confirmed_representative_count'),
        represented_confirmed_classes=model.get('represented_confirmed_true_classes'),
        represented_provisional_classes=model.get('represented_provisional_true_classes'),
        represented_union_classes=union,
        exposures_per_represented_class=meta['actual_exposures']/union if union else None,
        actions_per_represented_class=meta['environment_actions']/union if union else None,
        probe_count=events['active_probe'], repeated_probe_count=sum(max(n-1, 0) for n in attempts.values()),
        family_shared_scheduling_decisions=family_counts.get('family_shared_scheduling_decisions', 0),
        avoided_redundant_probe_opportunities=family_counts.get('avoided_redundant_probe_opportunities', 0),
        completed_family_probes=family_counts.get('completed_probe_attempts'),
        family_saturations=family_counts.get('saturations', 0), family_reactivations=family_counts.get('reactivations', 0),
        empirical_merges=state['counts'].get('empirical_merges', 0), unmerges=state['counts'].get('unmerges', 0),
        active_merged_nodes=active_merged, wrong_empirical_merges_active=active_wrong,
        historical_merge_records=historical_merges, wrong_empirical_merges_ever=ever_wrong,
        known_transitions=model.get('known_transitions'), transition_errors=len(model.get('transition_errors', [])),
        transition_error_rate=model.get('transition_prediction_error'),
        heldout_cases=heldout.get('cases', 0), heldout_status=heldout.get('status', 'NOT_EVALUATED'),
        control_success=control.get('success'), control_status=control.get('status', 'NOT_EVALUATED'),
        acquisition_cpu_seconds=meta['acquisition_cpu_seconds'], acquisition_wall_seconds=meta['acquisition_wall_seconds'],
        peak_memory_bytes=meta['peak_memory_bytes'],
        heldout_cpu_seconds=heldout.get('cpu_seconds'), control_cpu_seconds=control.get('cpu_seconds'),
        heldout_exposures=heldout.get('exposure_sets'), control_exposures=control.get('probe_exposures'))
    for name in ('correct_unique','wrong_unique','unresolved','coverage_including_NEW'):
        row['heldout_'+name] = heldout.get(name)
        row['heldout_'+name+'_rate'] = heldout.get(name+'_rate')
        row['heldout_'+name+'_partial_rate'] = heldout.get(name+'_partial_rate')
    return row, family_rows


def analyze_arm(folder, arm, output, table):
    result = json.loads((folder/'result.json').read_text())
    source = json.loads((folder/'source_snapshot.json').read_text())
    if arm == 'A':
        assert source['commit'] == EXECUTION
    manifest = json.loads((folder/'artifact_hashes.json').read_text())
    normalized = {k.replace('\\','/'): v for k,v in manifest.items()}
    files = ['events.jsonl.gz', 'result.json', 'source_snapshot.json']
    checkpoints = []
    for path in folder.glob('checkpoint_*/checkpoint.json'):
        metadata = json.loads(path.read_text())
        checkpoints.append((metadata['event_prefix_count'], path.parent, metadata))
        files.extend(str(p.relative_to(folder)).replace('\\','/') for p in (path, path.parent/'state.json'))
    for name in files:
        assert hashlib.sha256((folder/name).read_bytes()).hexdigest() == normalized[name], name
    layers = partitions(table['transitions'], table['observations'])
    checkpoints.sort(key=lambda v: (v[0],v[2]['actual_exposures']))
    events, attempts, cache = Counter(), Counter(), {}
    rows = []
    def process(folder, meta):
        state = json.loads((folder/'state.json').read_text())
        evaluation = next((v for v in result.get('evaluations', [])
                           if v['checkpoint']['event_prefix_count']==meta['event_prefix_count']), None)
        row, families = checkpoint_metrics(state, meta, cache, events, attempts, table, layers, arm, evaluation)
        rows.append(row)
        with gzip.open(output/f'{arm}_{folder.name}_families.jsonl.gz', 'wt', encoding='utf-8') as f:
            for record in families:
                f.write(json.dumps(record)+'\n')
    pointer = 0
    with gzip.open(folder/'events.jsonl.gz', 'rt', encoding='utf-8') as stream:
        for line in stream:
            event = json.loads(line)
            while pointer < len(checkpoints) and event['event_index'] > checkpoints[pointer][0]:
                _, path, meta = checkpoints[pointer]
                process(path, meta)
                pointer += 1
            events[event['event']] += 1
            if event['event'] == 'active_probe':
                attempts[tuple(event['history']),tuple(event['selected'])] += 1
            if event['event'] == 'comparison' and event['stage'] == 32:
                cache[tuple(sorted(map(tuple,event['pair'])))] = {k: event[k] for k in ('id','result')}
    while pointer < len(checkpoints):
        _, path, meta = checkpoints[pointer]
        process(path, meta)
        pointer += 1
    return dict(arm=arm, source=source, acquisition_status=result['status'],
                acquisition_resource_reason=result.get('resource_reason'), rows=rows,
                acquisition_reused=arm=='A', total_cpu_seconds=result['total_cpu_seconds'],
                total_wall_seconds=result['total_wall_seconds'], peak_memory_bytes=result['peak_memory_bytes'])


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--a', type=Path, required=True)
    p.add_argument('--b', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    a = next(args.a.glob('*/result.json')).parent
    b = args.b
    ra, rb = (json.loads((root/'result.json').read_text()) for root in (a,b))
    assert (ra['seed'],ra['camera']) == (rb['seed'],rb['camera'])
    args.output.mkdir(parents=True, exist_ok=False)
    table = static_table(ra['seed'])
    structural, layers, _ = analyze_table(table['transitions'], list(zip(table['observations'],table['public_goal'])))
    structural['partition_equalities'] = {f'P{d}_equals_Pinf': layers[min(d,len(layers)-1)]==layers[-1] for d in (0,1,2)}
    structural['finite_partition_equalities'] = {f'P{i}_equals_P{j}': layers[min(i,len(layers)-1)]==layers[min(j,len(layers)-1)]
                                                for i,j in ((0,1),(0,2),(1,2))}
    rgb_layers = partitions(table['transitions'], table['observations'])
    structural['rgb_only_infinity_classes'] = len(set(rgb_layers[-1]))
    structural['public_labels_change_infinite_partition'] = rgb_layers[-1] != layers[-1]
    structural['scope'] = table['scope']
    dump(args.output/'structural_partitions.json', dict(structural=structural, partitions=layers, table=table))
    arms = [analyze_arm(a,'A',args.output,table), analyze_arm(b,'B',args.output,table)]
    dump(args.output/'comparison.json', dict(seed=ra['seed'],camera=ra['camera'],arms=arms,
        structural=structural, A_download=json.loads((args.a/'download_manifest.json').read_text()),
        new_audit_sensor_exposures=0, new_audit_environment_actions=0,
        static_transition_evaluations=table['offline_pure_transition_evaluations'],
        note='A is archived acquisition, not zero-cost training. B evaluation uses frozen V2 readout.'))
    dump(args.output/'hashes.json', {str(f.relative_to(args.output)):hashlib.sha256(f.read_bytes()).hexdigest()
                                  for f in args.output.rglob('*') if f.is_file()})


if __name__ == '__main__':
    main()
