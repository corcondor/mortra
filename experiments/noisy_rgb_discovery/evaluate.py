"""Evaluator only: hidden-state enumeration runs after the learner is frozen."""
from collections import defaultdict, deque
import gzip
import hashlib
import json

import numpy as np

from .core import Statistics, predict_from_rgb
from .sensor import Sensor


def replay(game, word):
    raw = game.start_raw
    for a in word:
        raw = game.raw_step(raw, a)
    return raw


def truth(game, actions, size):
    queue = deque([game.start_raw])
    paths = {game.start_raw: ()}
    trans = {}
    while queue:
        s = queue.popleft()
        for a in actions:
            t = game.raw_step(s, a)
            trans[(s, a)] = t
            if t not in paths:
                paths[t] = paths[s]+(a,)
                queue.append(t)
    nodes = sorted(paths)
    outputs = {s: game.obs_bytes(s, 0, size) for s in nodes}
    ids = {}
    part = {s: ids.setdefault(outputs[s], len(ids)) for s in nodes}
    while True:
        labels = {}
        new = {}
        for s in nodes:
            key = (outputs[s], tuple(part[trans[(s, a)]] for a in actions))
            new[s] = labels.setdefault(key, len(labels))
        if len(set(new.values())) == len(set(part.values())):
            part = new
            break
        part = new
    return nodes, trans, outputs, part


def audit_model(game, model, actions, size):
    nodes, transitions, outputs, partition = truth(game, actions, size)
    q_truth = {q: partition[replay(game, h)] for q, h in enumerate(model['reps'])}
    errors = []
    for (q, a), t in sorted(model['trans'].items()):
        actual = partition[transitions[(replay(game, model['reps'][q]), a)]]
        if q_truth[t] != actual:
            errors.append(dict(q=q, action=a, predicted_class=q_truth[t], true_class=actual))
    visible_groups = defaultdict(set)
    for s in nodes:
        visible_groups[outputs[s]].add(partition[s])
    ambiguous_outputs = {o for o, classes in visible_groups.items() if len(classes) > 1}
    return dict(hidden_states=len(nodes), observation_preserving_quotient=len(set(partition.values())),
                learned_states=len(model['reps']), represented_true_classes=len(set(q_truth.values())),
                duplicate_true_class_representations=len(q_truth)-len(set(q_truth.values())),
                action_transition_count=len(model['trans']), action_transition_errors=errors,
                same_observation_different_future_groups=len(ambiguous_outputs)), partition, outputs, ambiguous_outputs, q_truth


def heldout(game, bias, model, suffixes, train, threshold, output, seed, batch, size):
    audit, partition, outputs, ambiguous, q_truth = audit_model(game, model, train.port.actions, size)
    # This truth is never given to the trained recognizer or its input adapter.
    sensor = Sensor(game, bias, 'heldout-v1', output / 'heldout', batch, size)
    statistics = Statistics(sensor.port, train.noise_floor)
    prototypes = [[train.summary(tuple(h)+tuple(e)) for e in suffixes] for h in model['reps']]
    rng = np.random.default_rng(seed+1000000)
    records = []
    try:
        for episode in range(200):
            history = ()
            for step in range(25):
                action = int(rng.integers(len(sensor.port.actions)))
                history += (action,)
                full = predict_from_rgb(statistics, history, suffixes, prototypes, threshold)
                passive = predict_from_rgb(statistics, history, [()], [[p[0]] for p in prototypes], threshold)
                raw = replay(game, history)
                target = partition[raw]
                record = dict(episode=episode, step=step+1, history=history, target_class=target,
                              ambiguous_current_observation=outputs[raw] in ambiguous)
                for label, result in [('adaptive_suffixes', full), ('empty_suffix_readout', passive)]:
                    predicted = result['predicted']
                    record[label] = dict(**result,
                        correct=predicted is not None and q_truth[predicted] == target,
                        nearest_correct=q_truth[result['nearest']] == target)
                records.append(record)
        with gzip.open(output / 'heldout_cases.jsonl.gz', 'wt', encoding='utf-8') as stream:
            for row in records:
                stream.write(json.dumps(row)+'\n')
        totals = {}
        for label in ('adaptive_suffixes', 'empty_suffix_readout'):
            totals[label] = dict(cases=len(records), correct=sum(r[label]['correct'] for r in records),
                unresolved=sum(r[label]['predicted'] is None for r in records),
                nearest_correct=sum(r[label]['nearest_correct'] for r in records),
                ambiguous_cases=sum(r['ambiguous_current_observation'] for r in records),
                ambiguous_correct=sum(r['ambiguous_current_observation'] and r[label]['correct'] for r in records))
        totals['sensor'] = sensor.metrics()
        totals['distinct_visited_true_classes'] = len({r['target_class'] for r in records})
        return audit, totals
    finally:
        sensor.close()
