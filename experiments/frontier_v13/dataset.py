"""Recover immutable selection-only sources; never execute a candidate."""
import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess
import time
import zipfile

from .protocol import (ROOT, SEEDS, ARMS, CONFIG, AUDIT_RUN, AUDIT_HEAD, OLD_RUN,
                       OLD_HEAD, read, write, csv_write, digest)
from .features import extract, PARENT_METRICS, columns


def api(endpoint, binary=False):
    data = subprocess.check_output(['gh', 'api', 'repos/corcondor/mortra/' + endpoint])
    return data if binary else json.loads(data)


def listing(run, head):
    status = api('actions/runs/' + run)
    assert status['head_sha'] == head and status['conclusion'] == 'success'
    rows = api(f'actions/runs/{run}/artifacts?per_page=100')['artifacts']
    result = {}
    for r in rows:
        if r['name'] not in result or r['created_at'] > result[r['name']]['created_at']:
            result[r['name']] = r
    return result


def archive(item, log):
    assert not item['expired']
    blob = api(f'actions/artifacts/{item["id"]}/zip', binary=True)
    sha = hashlib.sha256(blob).hexdigest()
    if item.get('digest'):
        assert item['digest'] == 'sha256:' + sha
    log.append(dict(name=item['name'], id=item['id'], zip_sha256=sha,
                    size_bytes=len(blob), created_at=item['created_at']))
    return zipfile.ZipFile(io.BytesIO(blob))


def member(z, suffix):
    names = [n for n in z.namelist() if n == suffix or n.endswith('/' + suffix)]
    assert len(names) == 1, (suffix, names)
    return z.read(names[0])


def verify_sources(manifest):
    hashes = {**manifest['source_hashes'], **manifest['audit_source_hashes']}
    for name, sha in hashes.items():
        data = (ROOT/name).read_bytes().replace(b'\r\n', b'\n')
        assert hashlib.sha256(data).hexdigest() == sha, name
        ref = subprocess.check_output(['git', 'show', f'{AUDIT_HEAD}:{name}'], cwd=ROOT)
        assert hashlib.sha256(ref.replace(b'\r\n', b'\n')).hexdigest() == sha
    return hashes


def parent_inputs(parent, evolution):
    matches = [i for i, p in enumerate(evolution['frontier']) if p['game_hash'] == parent['game_hash']]
    assert matches == parent['generations']
    generation = min(matches)
    record = evolution['frontier'][generation]
    assert record['D'] == parent['D_parent']
    history = evolution['mutation_history']
    past = [e for e in history if e['generation'] <= generation]
    if generation < 10:
        event = history[generation*8]
        assert event['candidate'] == 0 and event['parent_hash'] == parent['game_hash']
        decision = event['decision']
        actual = True
    else:
        # Terminal parents have no recorded next proposal. Keep this diagnostic separate.
        import math
        ctx = parent['context']
        table = evolution['proposal_posterior'].get(parent['context_id'],
                    {a: {'count': 0, 'reward_sum': 0.} for a in ARMS})
        counts = {a: table[a]['count'] for a in ARMS}
        means = {a: table[a]['reward_sum']/counts[a] if counts[a] else None for a in ARMS}
        total = sum(counts.values())
        scores = {a: (means[a]/13+1)/2 + math.sqrt(2*math.log(max(1, total))/counts[a]) if counts[a] else None for a in ARMS}
        ties = [a for a in ARMS if not counts[a]]
        if not ties:
            best = max(scores.values()); ties = [a for a in ARMS if scores[a] == best]
        decision = dict(context=ctx, counts=counts, mean_rewards=means, ucb=scores,
                        probabilities={a: 1/len(ties) if a in ties else 0. for a in ARMS})
        actual = False
    learning = record['learning'][-1] if record['learning'] else {}
    metrics = {k: record[k] for k in ('D', 'B50', 'B80', 'B90', 'final_success')}
    metrics.update(reachable_states=record['oracle']['reachable_states'],
                   full_info_success=record['full_info']['success_rate'] if record['full_info'] else None,
                   state_coverage=learning.get('state_coverage'), edge_coverage=learning.get('edge_coverage'))
    assert set(metrics) == set(PARENT_METRICS)
    # Only past selection rewards enter the model. No trajectories/tasks/holdout are exposed.
    clean_past = [dict(mutation=e['mutation'], reward=e['reward'],
                       outcome={k: e['outcome'][k] for k in ('valid', 'eligible')}) for e in past]
    assert len(clean_past) == 8*generation
    return metrics, decision, clean_past, generation, actual


def label_of(row, evaluation, genome):
    assert row['mutation_attempts'] == 1 and row['parent_unchanged']
    if genome is None:
        assert evaluation is None and row['candidate_hash'] is None
    else:
        assert digest(genome) == row['candidate_hash'] == evaluation['game_hash']
    if evaluation:
        full = evaluation['full_info']['success_rate'] if evaluation['full_info'] else None
        eligible = bool(evaluation['valid'] and full is not None and full >= .8 and
                        evaluation['final_success'] is not None and evaluation['final_success'] >= .8)
        assert row['eligible'] == eligible and row['valid'] == evaluation['valid']
        assert row['D_candidate'] == evaluation['D']
    else:
        assert not row['eligible'] and not row['valid']
    expected = row['D_candidate'] - row['D_parent'] if row['eligible'] else 0.
    assert row['reward'] == expected
    return {k: row[k] for k in ('reward', 'valid', 'eligible', 'delta_D', 'reward_category')}


def build(output):
    out = Path(output); out.mkdir(parents=True, exist_ok=False)
    write(out/'config.json', CONFIG)
    logs = []
    audit = listing(AUDIT_RUN, AUDIT_HEAD)
    original = listing(OLD_RUN, OLD_HEAD)
    with archive(audit['theory-registration'], logs) as z:
        manifest = json.loads(member(z, 'frozen_manifest.json'))
        frozen = verify_sources(manifest)
        inputs = {s: json.loads(member(z, f'inputs/{s}.json')) for s in SEEDS}
        for s, x in inputs.items():
            assert hashlib.sha256(member(z, f'inputs/{s}.json')).hexdigest() == manifest['input_hashes'][f'inputs/{s}.json']
    write(out/'frozen_manifest.json', dict(baseline='483d1592e5cd0d2b23d474cc79e217b121fd1fbe',
          audit_run=AUDIT_RUN, audit_head=AUDIT_HEAD, original_run=OLD_RUN, original_head=OLD_HEAD,
          protected_hashes=frozen, experiment_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()))
    feature_rows, label_rows, groups, availability = [], [], [], []
    t0 = time.perf_counter()
    for seed in SEEDS:
        with archive(original[f'v12-evolution-{seed}'], logs) as z:
            evolution = json.loads(member(z, 'adaptive/results.json'))
        assert evolution['seed'] == seed and evolution['provenance']['git_head'] == OLD_HEAD
        assert evolution['condition'] == 'adaptive' and len(evolution['frontier']) == 11
        parents = {p['parent_id']: p for p in inputs[seed]['parents']}
        prepared = {}
        for pid, p in parents.items():
            assert digest(p['genome']) == p['game_hash']
            info = parent_inputs(p, evolution)
            prepared[pid] = info
            metrics, decision, events, gen, actual = info
            availability.append(dict(parent_id=pid, seed=seed, earliest_generation=gen,
                past_proposals=len(events), recorded_proposal_available=actual,
                metrics={k: v is not None for k, v in metrics.items()},
                ucb_probabilities=decision['probabilities'], parent_hash=p['game_hash']))
        del evolution
        with archive(audit[f'theory-landscape-{seed}'], logs) as z:
            source = gzip.GzipFile(fileobj=io.BytesIO(member(z, 'records.jsonl.gz')))
            for line in source:
                rec = json.loads(line)
                row = rec['row']; pid = row['parent_id']; p = parents[pid]
                assert row['seed'] == seed and row['parent_hash'] == p['game_hash']
                assert row['D_parent'] == p['D_parent']
                target = label_of(row, rec['evaluation'], rec['genome'])
                metrics, decision, events, _, _ = prepared[pid]
                features = extract(p['genome'], rec['genome'], row['primitive'], metrics, decision, events)
                row_id = len(feature_rows)
                feature_rows.append({'row_id': row_id, **features})
                label_rows.append({'row_id': row_id, **target})
                groups.append(dict(row_id=row_id, seed=seed, parent_id=pid, parent_hash=p['game_hash'],
                    candidate_hash=row['candidate_hash'], primitive=row['primitive'], replicate=row['replicate']))
        print(f'RECOVERED {seed} cumulative_rows={len(feature_rows)}', flush=True)
    assert len(feature_rows) == 7000 and len(availability) == 50
    assert len({(g['parent_id'], g['primitive'], g['replicate']) for g in groups}) == 7000
    for pid in {g['parent_id'] for g in groups}:
        pool = [g for g in groups if g['parent_id'] == pid]
        assert len(pool) == 140
        assert {(r['primitive'], r['replicate']) for r in pool} == {(a, n) for a in ARMS for n in range(10)}
    for seed in SEEDS:
        train = {g['parent_hash'] for g in groups if g['seed'] != seed}
        test = {g['parent_hash'] for g in groups if g['seed'] == seed}
        assert not train & test
    names = list(features)
    assert all(list(r)[1:] == names for r in feature_rows)
    assert not any(s in n for n in names for s in ('seed', 'hash', 'replicate', 'generation', 'path', 'filename', 'candidate_D'))
    csv_write(out/'data/features.csv', feature_rows)
    csv_write(out/'data/labels.csv', label_rows)
    csv_write(out/'data/fold_assignments.csv', groups)
    write(out/'data/parent_availability.json', availability)
    write(out/'feature_schema.json', dict(columns=names, sets={m: columns(names, m) for m in CONFIG['feature_sets']},
        static_definitions=dict(spatial='undirected four-neighbor passability adjacency, not action reachability',
            dependency='writer-rule to reader-rule; SCC condensation longest path in vertices; cycles count cyclic SCCs',
            AST='ordered syntax scalar leaves excluding rendering/wall-list ordering',
            rule_diff='SequenceMatcher over canonical ordered syntax; rule-index dependency deltas are syntactic, not semantic alignment',
            absent_genome='mutation did not return a genome, observable before evaluator; zero deltas plus availability bit'),
        known_parent_metrics='existing selection-time evaluations only; full-info/coverage already observed before proposal'))
    write(out/'dataset_manifest.json', dict(rows=7000, parents=50, seeds=SEEDS, archives=logs,
          parent_availability=availability, candidate_evaluations=0, new_mutations=0,
          dataset_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (out/'data').iterdir()},
          build_wall_seconds=time.perf_counter()-t0))
    write(out/'diagnostics/leakage_audit.json', dict(status='STAGE0_DATA_GATES_PASSED',
          post_evaluation_features=False, identifier_features=False, game_holdout_access=False,
          parent_hashes_cross_folds_disjoint=True, full_genome_hash_checks=True,
          separate_features_labels=True, temporal_cut='earliest occurrence before slot 0',
          available_artifacts_only=[r['name'] for r in logs]))
    assert verify_sources(manifest) == frozen
