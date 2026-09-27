"""Post-freeze-only evaluation. Hidden classes never flow back to learning."""
import ast
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import time

import numpy as np

from experiments.noisy_rgb_discovery.core import predict_from_rgb
from experiments.noisy_rgb_discovery.evaluate import audit_model, replay, truth
from experiments.noisy_rgb_discovery.run import write
from experiments.noisy_rgb_discovery.source import environment_class
from .core import DIFFERENT, stability
from .runtime import Budget, ResourceLimit, stage_sensors


def frozen_candidates(history, suffixes, prototypes, statistics, threshold, arm):
    if arm == 'H':
        return predict_from_rgb(statistics[8], history, suffixes, prototypes[8][0], threshold)['candidates']
    candidates = list(range(len(prototypes[8][0])))
    for j, e in enumerate(suffixes):
        if not candidates:
            break
        values = {q: [] for q in candidates}
        for n in (8, 16, 32):
            stats = statistics[n]
            for rep in (0, 1):
                x = stats.summary(tuple(history)+tuple(e), rep)
                # Vectorize only the unchanged RGB score, not the decisions.
                p = [prototypes[n][rep][q][j] for q in candidates]
                means = np.stack([s.mean for s in p])
                variances = np.stack([s.var/s.n for s in p])
                zs = np.sqrt(np.mean((means-x.mean)**2/(variances+x.var/x.n+stats.noise_floor**2), axis=1))
                for q, z in zip(candidates, zs):
                    values[q].append(float(z))
        candidates = [q for q in candidates if stability(values[q], threshold, 32) != DIFFERENT]
    return candidates


def prototypes_for(model, suffixes, statistics, arm):
    return {n: {rep: [[s.summary(tuple(h)+tuple(e), rep) for e in suffixes] for h in model['reps']]
                for rep in ((0,) if arm == 'H' else (0, 1))}
            for n, s in statistics.items()}


def heldout(game, bias, model, suffixes, prototypes, threshold, output, seed, arm):
    audit, partition, _, _, q_truth = audit_model(game, model, tuple(range(game.num_actions)), 12)
    budget = Budget(max_actions=10000000, max_exposures=2000000, max_wall_seconds=1800)
    sensors, statistics = stage_sensors(game, bias, output, 'heldout', budget)
    rng = np.random.default_rng(seed+1000000)
    totals, sizes = Counter(), []
    start, cpu = time.perf_counter(), time.process_time()
    status = 'COMPLETED'
    try:
        with gzip.open(output/'heldout_cases.jsonl.gz', 'wt', encoding='utf-8') as stream:
            for episode in range(200):
                history = ()
                for step in range(25):
                    budget.check()
                    history += (int(rng.integers(game.num_actions)),)
                    candidates = frozen_candidates(history, suffixes, prototypes, statistics, threshold, arm)
                    target = partition[replay(game, history)]
                    predicted = candidates[0] if len(candidates) == 1 else None
                    correct = predicted is not None and q_truth[predicted] == target
                    covered = target in {q_truth[q] for q in candidates}
                    totals['cases'] += 1
                    totals['correct_unique'] += correct
                    totals['wrong_unique'] += predicted is not None and not correct
                    totals['unresolved'] += predicted is None
                    totals['candidate_coverage'] += covered
                    sizes.append(len(candidates))
                    stream.write(json.dumps(dict(episode=episode, step=step+1, history=history,
                        candidates=candidates, predicted=predicted, true_class=target,
                        correct_unique=correct, candidate_coverage=covered))+'\n')
    except ResourceLimit as error:
        status = 'INCOMPLETE_EVALUATION_RESOURCE_LIMIT_'+str(error)
    finally:
        for sensor in sensors.values():
            sensor.close()
    result = dict(status=status, **totals, planned_cases=5000,
                  mean_candidate_size=float(np.mean(sizes)) if sizes else None,
                  p95_candidate_size=float(np.percentile(sizes, 95)) if sizes else None,
                  wall_seconds=time.perf_counter()-start, cpu_seconds=time.process_time()-cpu,
                  sensors=[dict(namespace=s.namespace, **s.metrics()) for s in sensors.values()])
    for key in ('correct_unique', 'wrong_unique', 'unresolved', 'candidate_coverage'):
        result[key+'_rate'] = totals[key]/5000 if totals['cases'] == 5000 else None
    audit['predictive_transition_error'] = len(audit['action_transition_errors'])/audit['action_transition_count']
    audit['over_split'] = audit['duplicate_true_class_representations']
    audit['under_merge'] = audit['over_split']
    audit['under_merge_definition'] = 'same true class remains represented by multiple learned states'
    return audit, result


def acquisition_audit(game, events_path, representatives, output):
    _, _, _, partition = truth(game, tuple(range(game.num_actions)), 12)
    cache = {}
    def cls(h):
        h = tuple(h)
        if h not in cache:
            cache[h] = partition[replay(game, h)]
        return cache[h]
    q_truth = [cls(h) for h in representatives]
    counts = Counter({k: 0 for k in ('candidate_set_checks', 'true_class_unrepresented',
        'candidate_set_false_exclusion_count', 'different_witness_checks', 'spurious_split_witnesses',
        'suffix_witness_checks', 'spurious_suffix_witnesses')})
    sizes, assigned = [], defaultdict(set)
    with gzip.open(events_path, 'rt', encoding='utf-8') as source, gzip.open(
            output/'false_exclusions_and_witnesses.jsonl.gz', 'wt', encoding='utf-8') as sink:
        for row in source:
            r = json.loads(row)
            if r['event'] == 'candidate_set':
                candidates = r['candidates']
                target = cls(r['history'])
                true_reps = {q for q in range(r['representative_count']) if q_truth[q] == target}
                counts['candidate_set_checks'] += 1
                sizes.append(len(candidates))
                if not true_reps:
                    counts['true_class_unrepresented'] += 1
                elif not true_reps.intersection(candidates):
                    counts['candidate_set_false_exclusion_count'] += 1
                    sink.write(json.dumps(dict(kind='candidate_false_exclusion', true_representatives=sorted(true_reps),
                                              true_class=target, original_event=r))+'\n')
                if len(candidates) == 1:
                    assigned[candidates[0]].add(target)
            elif r['event'] == 'comparison' and r['result'] == DIFFERENT and r['stage'] == 32:
                counts['different_witness_checks'] += 1
                if cls(r['history_a']) == cls(r['history_b']):
                    counts['spurious_split_witnesses'] += 1
                    sink.write(json.dumps(dict(kind='spurious_difference', original_event=r))+'\n')
            elif r['event'] == 'suffix_added':
                counts['suffix_witness_checks'] += 1
                if cls(r['history_a']) == cls(r['history_b']):
                    counts['spurious_suffix_witnesses'] += 1
                    sink.write(json.dumps(dict(kind='spurious_suffix', original_event=r))+'\n')
    return dict(**counts, mean_candidate_size=float(np.mean(sizes)) if sizes else None,
                p95_candidate_size=float(np.percentile(sizes, 95)) if sizes else None,
                observed_assignment_false_merge_states=sum(len(s) > 1 for s in assigned.values()),
                assigned_true_classes={q: sorted(s) for q, s in assigned.items()},
                true_classes=len(set(partition.values())), represented_true_classes=len(set(q_truth)),
                over_split=len(q_truth)-len(set(q_truth)),
                false_exclusion_unit='membership-stage snapshots, not independent histories')


def control(seed, model, output):
    # Extract only the existing solver definition; never import the legacy
    # experiment's top-level execution or feed hidden graph information to it.
    path = Path('scripts/evaluate_autonomous_game_design_loop.py')
    data = path.read_bytes()
    functions = [n for n in ast.parse(data).body if isinstance(n, ast.FunctionDef) and n.name == 'solve_fixed_field']
    assert len(functions) == 1
    namespace = {'np': np}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(path), 'exec'), namespace)
    game = environment_class()(seed, 'state_opaque')
    goals, label_actions, labels = [], 0, []
    for q, h in enumerate(model['reps']):
        raw = game.start_raw
        for a in h:
            raw = game.raw_step(raw, a)
            label_actions += 1
        success = bool(game.raw_goal(raw))
        labels.append(dict(state=q, actions=h, public_goal=success))
        if success:
            goals.append(q)
    K = np.zeros((len(model['reps']), len(model['reps'])))
    for (q, a), t in model['trans'].items():
        K[q, t] += 1/game.num_actions
    psi, iterations, residual, converged = namespace['solve_fixed_field'](K, goals, q=.90)
    raw, q, actions, states = game.start_raw, model['start'], [], [model['start']]
    for _ in range(60):
        if game.raw_goal(raw) or not goals:
            break
        a = int(np.argmax([psi[model['trans'][q, a]] for a in range(game.num_actions)]))
        actions.append(a)
        raw = game.raw_step(raw, a)
        q = model['trans'][q, a]
        states.append(q)
    result = dict(goal_label_acquisition_actions=label_actions, goal_labels=labels,
                  public_goal_nodes=goals, control_success=bool(game.raw_goal(raw)),
                  control_steps=len(actions), control_action_sequence=actions, predicted_states=states,
                  q=.90, horizon=60, solver_iterations=iterations, solver_residual=residual,
                  solver_converged=converged, source_sha=hashlib.sha256(data).hexdigest(),
                  control_mode='frozen_transition_tracking; no visual relocalization or relearning')
    write(output/'control.json', result)
    return result
