"""Frozen-source Stage 0/1 gate. No game run is allowed after a failed gate.

Learners receive only integer-coded observations/actions and episode boundaries.
Machine identities are used exclusively by the collector and external evaluator.
The supplied core, tests, fixtures and oracle are imported without modification.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import itertools
import json
from pathlib import Path
import random
import subprocess
import sys
import time
import tracemalloc
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor/future_refinement_core"
sys.path[:0] = [str(ROOT), str(VENDOR), str(VENDOR / "tests")]
from future_refinement_core import (
    FutureRefinementCore, certified_congruence_quotient,
    pair_relation_on_empirical_model,
)
from exact_moore_oracle import MooreMachine, partition_refinement
from microbench_fixtures import ALL_FIXTURES
from scripts import evaluate_adaptive_refinement as old

OLD_SHA = "b7810586055e74af7e7f07e89d911ce27ece84b9ed9dfc1845e565e795a9db9f"
CONFIG = {
    "schema": 1,
    "stage": "state-construction only; no reasoning",
    "random_seeds": list(range(961000, 961010)),
    "random_states": 4,
    "random_actions": 2,
    "random_episodes": 8,
    "random_episode_steps": 16,
    "fixture_collection": "all action words of length four, from fixture-declared initial states",
    "fixture_word_length": 4,
    "history_cap_new": None,
    "old_mode": "split_merge",
    "old_history": "unchanged default 6",
    "comparison_carrier": "identical observed occurrences, including resets, with final assignments",
    "false_merge_denominator": "occurrence pairs with different oracle classes",
    "false_split_denominator": "occurrence pairs with equal oracle classes",
    "complete_recovery_gate": "complete-table quotient must match oracle; history recovery is measured separately",
    "complete_recovery_caveat": "edge coverage does not prove history identifiability or sample sufficiency",
    "stop_on_failure": True,
    "core_changes_permitted": False,
    "stage2_seeds": [201, 302, 403],
    "stage3": "only after Stage 1 and Stage 2; not run by this gate program",
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)


def log(out, **record):
    record = {"utc": datetime.now(timezone.utc).isoformat(), **record}
    line = json.dumps(record, ensure_ascii=False)
    print(line, flush=True)
    with (out / "run.log").open("a", encoding="utf-8") as stream:
        stream.write(line + "\n")


def verify_sources():
    expected = json.loads((VENDOR / "SHA256.json").read_text(encoding="utf-8"))
    records = {}
    for name, digest in expected.items():
        actual = sha(VENDOR / name)
        if actual != digest:
            raise RuntimeError(f"Provided source changed: {name}")
        records[str((VENDOR / name).relative_to(ROOT))] = actual
    actual = sha(ROOT / "scripts/evaluate_adaptive_refinement.py")
    if actual != OLD_SHA:
        raise RuntimeError("OLD baseline SHA mismatch")
    records["scripts/evaluate_adaptive_refinement.py"] = actual
    for name in ("scripts/evaluate_fixed_field_congruence.py", "scripts/active_world_discovery_v2.py"):
        records[name] = sha(ROOT / name)
    records[str(Path(__file__).relative_to(ROOT))] = sha(__file__)
    records["vendor/future_refinement_core/SHA256.json"] = sha(VENDOR / "SHA256.json")
    return records


def coded_machine(machine):
    observations = {}
    labels = {s: observations.setdefault(machine.output[s], len(observations)) for s in machine.states}
    actions = {a: i for i, a in enumerate(machine.actions)}
    transitions = {(s, actions[a]): machine.step(s, a) for s in machine.states for a in machine.actions}
    return MooreMachine(machine.states, tuple(actions.values()), labels, transitions)


def record_episode(machine, initial, actions):
    hidden = [initial]
    observations = [machine.output[initial]]
    for action in actions:
        hidden.append(machine.step(hidden[-1], action))
        observations.append(machine.output[hidden[-1]])
    return {"observations": observations, "actions": list(actions)}, hidden


def collect_cases():
    cases = []
    for factory in ALL_FIXTURES:
        fixture = factory()
        machine = coded_machine(fixture.machine)
        words = list(itertools.product(machine.actions, repeat=CONFIG["fixture_word_length"]))
        episodes, hidden = [], []
        for start in fixture.initial_states:
            for word in words:
                episode, truth = record_episode(machine, start, word)
                episodes.append(episode)
                hidden.append(truth)
        cases.append((fixture.name, "fixture", machine, fixture.initial_states, episodes, hidden))
    # Preserve the supplied, observable-cue propagation example as a learner test.
    for depth in (1, 2, 3, 8):
        episodes, hidden, labels, transitions = [], [], {}, {}
        actions = (0, 1)
        for branch in (0, 1):
            states = [branch * (depth + 2) + t for t in range(depth + 2)]
            obs = [branch] + [2 + t for t in range(depth)] + [depth + 2 + branch]
            for s, o in zip(states, obs):
                labels[s] = o
                for a in actions:
                    transitions[s, a] = s
            word = [0] * depth + [1]
            for u, a, v in zip(states, word, states[1:]):
                transitions[u, a] = v
            episodes.append({"observations": obs, "actions": word})
            hidden.append(states)
        machine = MooreMachine(tuple(labels), actions, labels, transitions)
        cases.append((f"observable_cue_depth_{depth}", "fixture", machine,
                      (hidden[0][0], hidden[1][0]), episodes, hidden))
    # An intentionally partial stream tests UNKNOWN independently of accuracy.
    machine = MooreMachine((0, 1), (0, 1), {0: 0, 1: 1},
                           {(0, 0): 1, (0, 1): 0, (1, 0): 1, (1, 1): 1})
    episode, hidden = record_episode(machine, 0, (0,))
    cases.append(("unknown_transition", "fixture", machine, (0,), [episode], [hidden]))
    for seed in CONFIG["random_seeds"]:
        table, observations = old.finite_world(CONFIG["random_states"], CONFIG["random_actions"], seed, "random")
        machine = MooreMachine(tuple(range(len(table))), tuple(range(table.shape[1])),
                               dict(enumerate(map(int, observations))),
                               {(s, a): int(table[s, a]) for s in range(len(table)) for a in range(table.shape[1])})
        rng = random.Random(seed + 1000000)
        episodes, hidden = [], []
        for _ in range(CONFIG["random_episodes"]):
            word = [rng.choice(machine.actions) for _ in range(CONFIG["random_episode_steps"])]
            episode, truth = record_episode(machine, 0, word)
            episodes.append(episode)
            hidden.append(truth)
        cases.append((f"random_{seed}", "random", machine, (0,), episodes, hidden))
    return cases


def model_assignments(model, handles, condition):
    if condition == "OLD":
        return [model.encode(context) for context in handles]
    return [model.encode_known_history_node(node) for node in handles]


def partition_metrics(assignments, truth):
    joint = Counter(zip(assignments, truth))
    learned_counts, truth_counts = Counter(assignments), Counter(truth)
    pairs = lambda values: sum(n * (n - 1) // 2 for n in values)
    same_both = pairs(joint.values())
    same_learned = pairs(learned_counts.values())
    same_truth = pairs(truth_counts.values())
    all_pairs = len(truth) * (len(truth) - 1) // 2
    fm, fs = same_learned - same_both, same_truth - same_both
    witness = None
    for i in range(len(truth)):
        for j in range(i + 1, len(truth)):
            if (assignments[i] == assignments[j]) != (truth[i] == truth[j]):
                witness = {"left_occurrence": i, "right_occurrence": j,
                           "learned": [assignments[i], assignments[j]], "oracle": [truth[i], truth[j]],
                           "kind": "false_merge" if assignments[i] == assignments[j] else "false_split"}
                break
        if witness:
            break
    return {"false_merge_pairs": fm, "false_split_pairs": fs,
            "false_merge": fm / (all_pairs - same_truth) if all_pairs > same_truth else None,
            "false_split": fs / same_truth if same_truth else None,
            "pair_denominator": all_pairs, "exact_partition_agreement": not (fm or fs),
            "partition_agreement": 1 - (fm + fs) / all_pairs if all_pairs else 1.,
            "first_final_mismatch": witness}


def independent_residual(model, condition):
    counts, blocks = model.leaf_counts, model.model["blocks"]
    rows = defaultdict(lambda: defaultdict(list))
    for leaf in range(len(model.leaf_keys)):
        for action in model.actions:
            raw = counts.get((leaf, action), {})
            projected = Counter()
            for target, count in raw.items():
                projected[blocks[target]] += count
            n = sum(projected.values())
            rows[blocks[leaf]][action].append(
                {b: Fraction(count, n) for b, count in projected.items()} if n else {})
    residual = Fraction()
    for actions in rows.values():
        for group in actions.values():
            ref = group[0]
            for row in group[1:]:
                residual = max(residual, sum((abs(row.get(k, 0) - ref.get(k, 0)) for k in row.keys() | ref.keys()), Fraction()))
    return float(residual)


def fit_and_audit(episodes, truth, condition, out, case):
    n_actions = case["n_actions"]
    model = old.HistoryModel(n_actions) if condition == "OLD" else FutureRefinementCore(tuple(range(n_actions)))
    handles, trace, first_mismatch = [], [], None
    cpu = wall = 0.
    tracemalloc.start()
    position = step = 0
    for ep_index, episode in enumerate(episodes):
        for t, obs in enumerate(episode["observations"]):
            started, clock = time.process_time(), time.perf_counter()
            if t == 0:
                model.begin(obs)
            elif condition == "OLD":
                step += 1
                model.observe(episode["actions"][t - 1], obs, step)
            else:
                step += 1
                model.observe(episode["actions"][t - 1], obs)
            cpu += time.process_time() - started
            wall += time.perf_counter() - clock
            handles.append(model.current)
            position += 1
            labels = model_assignments(model, handles, condition)
            if first_mismatch is None:
                quality = partition_metrics(labels, truth[:position])
                if quality["first_final_mismatch"]:
                    first_mismatch = {"step": step, "episode": ep_index, "episode_step": t,
                                      **quality["first_final_mismatch"]}
            trace.append({"step": step, "episode": ep_index, "episode_step": t,
                          "leaves": len(model.leaf_keys), "blocks": len(model.model["groups"]),
                          "depth": max(model.depths if condition == "OLD" else model.leaf_depths, default=0)})
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assignments = model_assignments(model, handles, condition)
    quality = partition_metrics(assignments, truth)
    leaf_labels = [None] * len(model.leaf_keys)
    for i, leaf in enumerate(model.mapping):
        leaf_labels[leaf] = model.contexts[i][-1] if condition == "OLD" else model.nodes[i].observation
    relations = Counter()
    for u in range(len(leaf_labels)):
        for v in range(u + 1, len(leaf_labels)):
            relations[pair_relation_on_empirical_model(leaf_labels, model.actions, model.leaf_counts, u, v).relation.value] += 1
    missing_rows = sum((s, a) not in model.leaf_counts for s in range(len(leaf_labels)) for a in model.actions)
    certified_merge_members = [g for g in model.model["groups"].values() if len(g) > 1]
    unsafe_merge = any(any((s, a) not in model.leaf_counts for s in members for a in model.actions)
                       for members in certified_merge_members)
    belief = {"checked": 0, "equal": 0}
    if condition == "NEW":
        for ep in episodes:
            current = model.begin_belief(ep["observations"][0])
            for t in range(len(ep["observations"])):
                if t:
                    current = model.update_belief(current, ep["actions"][t-1], ep["observations"][t])
                rebuilt = model.reconstruct_belief(ep["observations"][:t+1], ep["actions"][:t])
                belief["checked"] += 1
                belief["equal"] += int(current == rebuilt)
    result = {**quality, "condition": condition, "occurrences": position,
              "learned_state_count": len(model.model["groups"]), "leaf_count": len(leaf_labels),
              "max_selected_history_depth": max(model.depths if condition == "OLD" else model.leaf_depths, default=0),
              "pair_relations": {name: relations[name] for name in ("UNKNOWN", "DIFFERENT", "EQUIVALENT")},
              "UNKNOWN_rows": missing_rows, "merged_with_missing_rows": unsafe_merge,
              "eps_action": independent_residual(model, condition),
              "cpu_seconds": cpu, "wall_seconds": wall, "traced_peak_bytes": peak,
              "model_heap_bytes": old.deep_bytes(model.__dict__), "belief": belief,
              "first_observed_partition_mismatch": first_mismatch,
              "unresolved": model.summary().get("sufficiency_counterexamples", []) if condition == "OLD" else model.unresolved}
    events = model.events if condition == "OLD" else [asdict(e) for e in model.split_events]
    save(out / "cases" / case["name"] / f"{condition}.json",
         {"metrics": result, "assignments": assignments, "events": events, "trace": trace})
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    sources = verify_sources()
    save(out / "source_sha.json", sources)
    save(out / "source_snapshot.json", {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "branch": subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip(),
        "HEAD": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "status": subprocess.check_output(["git", "status", "--short"], cwd=ROOT, text=True),
        "argv": sys.argv, "source_sha": sources})
    save(out / "config.json", CONFIG)
    save(out / "seeds.json", CONFIG["random_seeds"])
    xml = ET.parse(out / "oracle_tests.xml").getroot()
    test_cases = list(xml.iter("testcase"))
    failures = [c.attrib for c in test_cases if any(c.find(tag) is not None for tag in ("failure", "error", "skipped"))]
    demo = (out / "stage0_demo.log").read_text(encoding="utf-8-sig")
    oracle_passed = len(test_cases) == 26 and not failures
    propagation = demo.find("action='b'") >= 0 and demo.find("action='b'") < demo.find("action='a'")
    save(out / "oracle_validation.json", {"tests": len(test_cases), "failures": failures,
         "passed": oracle_passed, "demo_propagation": propagation, "exhaustive_machines": 5832,
         "exhaustive_scope": "complete-table quotient function, not history learner recovery"})
    if not oracle_passed or not propagation:
        log(out, status="STOPPED_STAGE_0_GATE")
        return
    cases = collect_cases()
    # Freeze every input before either condition sees any result.
    prepared = []
    for name, kind, machine, starts, episodes, hidden in cases:
        blocks = partition_refinement(machine)
        bmap = {s: b for b, members in enumerate(blocks) for s in members}
        truth = [bmap[s] for ep in hidden for s in ep]
        observed = {(s, a) for ep, history in zip(episodes, hidden) for s, a in zip(history, ep["actions"])}
        reachable = machine.reachable(starts)
        complete = {(s, a) for s in reachable for a in machine.actions} <= observed
        counts = defaultdict(Counter)
        for (s, a), v in machine.transition.items():
            counts[s, a][v] += 1
        q = certified_congruence_quotient([machine.output[s] for s in machine.states], machine.actions, counts)
        complete_oracle_match = all((q["blocks"][s] == q["blocks"][t]) == (bmap[s] == bmap[t])
                                    for s in machine.states for t in machine.states)
        meta = {"name": name, "kind": kind, "n_actions": len(machine.actions),
                "oracle_full_state_count": len(blocks), "oracle_observed_state_count": len(set(truth)),
                "reachable_state_action_coverage_complete": complete,
                "complete_table_quotient_matches_oracle": complete_oracle_match,
                "observed_hidden_states": len(set(s for ep in hidden for s in ep)),
                "reachable_hidden_states": len(reachable)}
        data_path = out / "shared_trajectories" / f"{name}.json"
        save(data_path, episodes)
        meta["input_sha256"] = sha(data_path)
        save(out / "evaluator_only" / f"{name}.json", {
            "observations": dict(machine.output), "transitions": [[s, a, v] for (s, a), v in machine.transition.items()],
            "hidden_trajectories": hidden, "oracle_partition": blocks})
        prepared.append((meta, episodes, truth))
    save(out / "dataset_manifest.json", [m for m, _, _ in prepared])
    log(out, status="INPUTS_FROZEN", cases=len(prepared))
    results = []
    for meta, episodes, truth in prepared:
        log(out, case=meta["name"], event="start")
        conditions = {}
        for condition in ("OLD", "NEW"):
            conditions[condition] = fit_and_audit(episodes, truth, condition, out, meta)
            log(out, case=meta["name"], condition=condition,
                states=conditions[condition]["learned_state_count"],
                false_merge_pairs=conditions[condition]["false_merge_pairs"],
                false_split_pairs=conditions[condition]["false_split_pairs"])
        results.append({**meta, "conditions": conditions})
    failures = []
    for result in results:
        new = result["conditions"]["NEW"]
        reasons = []
        if result["kind"] == "fixture" and new["false_merge_pairs"]:
            reasons.append("fixture_false_merge")
        if new["merged_with_missing_rows"]:
            reasons.append("UNKNOWN_rows_merged")
        if new["eps_action"] != 0:
            reasons.append("nonzero_action_residual")
        if not result["complete_table_quotient_matches_oracle"]:
            reasons.append("complete_table_oracle_mismatch")
        if new["belief"]["checked"] != new["belief"]["equal"]:
            reasons.append("recursive_belief_mismatch")
        if reasons:
            failures.append({"case": result["name"], "reasons": reasons,
                             "first_observed_mismatch": new["first_observed_partition_mismatch"],
                             "final_mismatch": new["first_final_mismatch"]})
    status = "STOPPED_STAGE_1_GATE" if failures else "STAGE_1_PASS"
    save(out / "stage1_state_quality.json", {"status": status, "results": results, "failures": failures,
         "interpretation": "A gate failure does not prove impossibility or universal model failure. Empirical congruence and true recovery are separate."})
    save(out / "stage2_play_comparison.json", {"status": "NOT_RUN_STAGE_1_GATE" if failures else "PENDING", "success": None})
    save(out / "stage3_game_duel.json", {"status": "NOT_RUN_STAGE_1_GATE" if failures else "PENDING_STAGE_2", "success": None})
    if verify_sources() != sources:
        raise RuntimeError("Sources changed during run")
    save(out / "metrics.json", {"status": status, "stage0_passed": True, "stage1_cases": len(results),
         "stage1_failures": failures, "stage2_run": False, "stage3_run": False})
    log(out, status=status, failure_cases=len(failures))


if __name__ == "__main__":
    main()
