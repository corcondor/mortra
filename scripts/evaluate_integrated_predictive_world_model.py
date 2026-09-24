"""Formal same-experience evaluation of frozen OLD and predictive perception.

Only this harness and the external evaluator are new. Every algorithm source is
checked against source_sha.json before and after execution. Partial completion,
unknown predictions, allocation refusal and assertion failures are not successes.
"""
from __future__ import annotations

import os
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from dataclasses import asdict
import argparse
import copy
import csv
import gc
import hashlib
import json
from pathlib import Path
import platform
import random
import shutil
import subprocess
import sys
import time
import traceback

import numpy as np
import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import evaluate_adaptive_refinement as old
from scripts import integrated_predictive_evaluation as ev
from mortra_predictive_perception.adapters import ResponseSymbolizer, load_legacy_visual
from mortra_predictive_perception.optimized import SweepResponseSymbolizer
from mortra_predictive_perception.shared_data import save_episodes, load_episodes
from mortra_predictive_perception.world import ObservedWorld

CONDITIONS = ("OLD", "NEW-ABS", "NEW-DELTA")
PRIOR = Path("data/integrated-predictive-experience-20260924")


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value, exclusive=False):
    with Path(path).open("x" if exclusive else "w", encoding="utf-8") as f:
        json.dump(value, f, indent=2, allow_nan=False)


def frozen_check(output):
    for relative, expected in read(Path(output)/"source_sha.json").items():
        if sha(ROOT/relative) != expected:
            raise RuntimeError(f"Frozen algorithm source changed: {relative}")


def resources():
    info = psutil.Process().memory_info()
    peak = getattr(info, "peak_wset", None)
    if peak is None and sys.platform != "win32":
        import resource
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == "darwin" else 1024)
    return {"rss_bytes": info.rss, "process_peak_working_set_bytes": peak,
            "process_cpu_seconds": time.process_time(), "available_physical_bytes": psutil.virtual_memory().available}


def log(output, **fields):
    fields["timestamp"] = datetime.now(timezone.utc).isoformat()
    line = json.dumps(fields, allow_nan=False)
    print(line, flush=True)
    with (Path(output)/"run.log").open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def protocol():
    historical = old.default_config()
    cases = []
    for domain, specs in (("finite", historical["finite_systems"]), ("partial", historical["partial_systems"])):
        for i, spec in enumerate(specs):
            cases.append({"domain": domain, "spec": spec, "id": f"{domain}_{spec['seed']}",
                          "prior": str(PRIOR/f"{domain}_{i:03d}.json"), "evaluation_seed": spec["seed"]+300000})
    for domain, steps, trials in (("MicroGame", historical["game_steps"], historical["game_trials"]),
                                 ("raw_visual", 2500, 50)):
        for seed in historical["games"]:
            cases.append({"domain": domain, "id": f"{domain}_{seed}",
                          "spec": {"seed": seed, "actions": 5, "steps": steps},
                          "evaluation_seed": seed+300000, "evaluation_trials": trials,
                          "prior": str(PRIOR/f"game_{seed}.json") if domain == "MicroGame" else None})
    return {"schema": 1, "conditions": CONDITIONS, "cases": cases, "planning_horizon": historical["planning_horizon"],
            "evaluation_goals": historical["evaluation_goals"], "workers": 2,
            "training_data": "reuse saved observation/action experience; re-render missing raw frames once under fixed seeds",
            "heldout_data": "one common uniform-action collector with independent seed; no model selects its heldout input",
            "finite_heldout_steps": "same as each existing training interaction budget",
            "raw_heldout": "existing trial counts and horizon; identical saved trajectories for perception/memory",
            "complete_system": "separate closed-loop decisions, same environment/reset/objective/budget; never used to fit",
            "source_of_truth": "current frozen working tree, not previous success metrics",
            "new_internal_constants_added": [], "new_q": None,
            "old_fixed_field_q": 0.9, "unknown": "explicit; no majority or self-loop imputation in NEW",
            "finite_raw_encoding": "original discrete observation IDs as one numeric feature; ordinal predicate bias is disclosed",
            "false_merge": "different true predictive classes merged / all differently classed history pairs",
            "false_split": "same true predictive class split / all same-class history pairs",
            "predictive_violation": "different true predictive classes merged / all model-equal history pairs",
            "predictive_violation_note": "same over-merge numerator, different denominator; not independent evidence",
            "state_metric": "OLD encoded state vs NEW belief; NEW sensory-symbol diagnostics separately retained",
            "future_error": "next raw observation MSE on predicted heldout transitions; unknown count and coverage reported",
            "old_response_readout": "training-only action-conditioned delta mean; evaluation readout, not an OLD algorithm change",
            "memory_scope": "frozen observed-prefix model; not all consistent unseen worlds",
            "allocation_policy": "do not attempt a reference feature allocation larger than currently available physical memory; record RESOURCE UNAVAILABLE, NOT RUN",
            "timeouts": None, "algorithm_retuning_after_results": False}


def prepare_case(case, output, config):
    folder = Path(output)/"datasets"/case["id"]
    folder.mkdir(parents=True, exist_ok=False)
    spec, domain = case["spec"], case["domain"]
    seed, action_count = spec["seed"], spec["actions"]
    start = time.process_time()
    if domain in ("finite", "partial"):
        prior = read(ROOT/case["prior"])
        assert prior["spec"] == spec
        train = [(np.array([[float(o)] for _, o in prior["stream"]]), [int(a) for a, _ in prior["stream"][1:]])]
        table, emissions = old.finite_world(spec["n"], action_count, seed, spec["kind"])
        state = 0
        evaluation_states, observations, actions = [state], [np.array([float(emissions[state])])], []
        rng = random.Random(case["evaluation_seed"])
        for _ in range(spec["steps"]):
            action = rng.randrange(action_count)
            state = int(table[state, action])
            actions.append(action)
            observations.append(np.array([float(emissions[state])]))
            evaluation_states.append(state)
        heldout = [(observations, actions)]
        hidden = [evaluation_states]
    else:
        legacy = load_legacy_visual(ROOT/"scripts/evaluate_visual_state_construction.py")
        environment = old.base if domain == "MicroGame" else legacy
        game = environment.MicroGame(seed=seed)
        game.generate_random(wall_density=.18)
        np.random.seed(seed+700000)
        state = game.get_initial_state()
        frames = [environment.render_visual_frame(game, state, 0).reshape(-1)]
        actions = []
        if domain == "MicroGame":
            controls = [int(a) for a, _ in read(ROOT/case["prior"])["stream"][1:]]
            assert len(controls) == spec["steps"]
        else:
            constructor = legacy.VisualStateConstructor(num_actions=action_count)
            current = constructor.map_observation_to_cluster(frames[0].reshape(24,24))
            visits = Counter()
        for t in range(spec["steps"]):
            if domain == "MicroGame":
                action = controls[t]
            else:
                action = min(range(action_count), key=lambda a: visits[current, a])
                visits[current, action] += 1
            state = game.step(state, action)
            frame = environment.render_visual_frame(game, state, t+1)
            frames.append(frame.reshape(-1))
            actions.append(action)
            if domain == "raw_visual":
                nxt = constructor.map_observation_to_cluster(frame)
                constructor.record_transition(current, action, nxt)
                current = nxt
        train = [(frames, actions)]
        np.random.seed(seed+900000)
        rng = random.Random(case["evaluation_seed"])
        heldout, hidden = [], []
        for trial in range(case["evaluation_trials"]):
            state = game.get_initial_state()
            frames = [environment.render_visual_frame(game, state, trial*100).reshape(-1)]
            actions, states = [], [state]
            for t in range(config["planning_horizon"]):
                action = rng.randrange(action_count)
                state = game.step(state, action)
                frames.append(environment.render_visual_frame(game,state,trial*100+t+1).reshape(-1))
                actions.append(action)
                states.append(state)
            heldout.append((frames, actions))
            hidden.append(states)
        environment_record = {key:sorted(value) if isinstance(value,set) else value
                              for key,value in vars(game).items() if not isinstance(value,random.Random)}
        save(folder/"environment_evaluator_only.json", environment_record, exclusive=True)
    train_manifest = save_episodes(folder/"train.npz", train)
    eval_manifest = save_episodes(folder/"heldout.npz", heldout)
    save(folder/"hidden_evaluator_only.json", hidden, exclusive=True)
    manifest = {"case": case, "train": train_manifest, "heldout": eval_manifest,
                "hidden_evaluator_only_sha256": sha(folder/"hidden_evaluator_only.json"),
                "collector_cpu_seconds": time.process_time()-start,
                "prior_stream_sha256": sha(ROOT/case["prior"]) if case["prior"] else None}
    save(folder/"manifest.json", manifest, exclusive=True)
    return manifest


def fit_new(episodes, heldout, actions, target, folder):
    # Both implementations receive fresh read-only instances of the same saved
    # experience; the caller checks that data hashes remain unchanged.
    models, costs = [], {}
    for name, cls in (("reference", ResponseSymbolizer), ("sweep", SweepResponseSymbolizer)):
        wall, cpu = time.perf_counter(), time.process_time()
        model = cls(actions, target)
        for obs, controls in episodes:
            model.add_episode(obs, controls)
        model.fit()
        costs[name] = {"wall_seconds": time.perf_counter()-wall, "cpu_seconds": time.process_time()-cpu}
        models.append(model)
    reference, sweep = models
    assert reference.report == sweep.report, "Reference/sweep report (including BIC/features) mismatch"
    assert reference.export_tree() == sweep.export_tree(), "Reference/sweep threshold/tree mismatch"
    start = time.process_time()
    train_symbols = ev.new_symbols(sweep, episodes)
    test_symbols = ev.new_symbols(sweep, heldout)
    assert train_symbols == ev.new_symbols(reference, episodes), "Training symbol mismatch"
    assert test_symbols == ev.new_symbols(reference, heldout), "Heldout symbol mismatch"
    for a,b in zip(reference._leaves(reference.tree), sweep._leaves(sweep.tree), strict=True):
        assert a.action_means.keys() == b.action_means.keys()
        for action in a.action_means:
            np.testing.assert_array_equal(a.action_means[action], b.action_means[action])
    costs["equivalence_and_encoding_cpu"] = time.process_time()-start
    save(folder/f"{target}_tree.json", sweep.export_tree())
    save(folder/f"{target}_equivalence.json", {"all_training_and_heldout_symbols_equal": True,
         "selected_features_thresholds_BIC_equal": True, "leaf_means_equal": True, "costs": costs,
         "sweep_work": sweep.work})
    del reference, models
    gc.collect()
    world = ObservedWorld(actions)
    start = time.process_time()
    for symbols, (_, controls) in zip(train_symbols, episodes, strict=True):
        world.add_episode(symbols, controls)
    world.freeze()
    costs["world_and_quotient_cpu"] = time.process_time()-start
    forbidden = {"q", "discount", "goal", "reward", "max_history", "max_history_depth", "confidence_threshold"}
    assert not forbidden & vars(sweep).keys()
    assert not forbidden & vars(world).keys()
    return sweep, world, train_symbols, test_symbols, costs


def run_case(case, output, config):
    frozen_check(output)
    case_start, cpu_start = time.perf_counter(), time.process_time()
    folder = Path(output)/"cases"/case["id"]
    folder.mkdir(parents=True, exist_ok=False)
    data_dir = Path(output)/"datasets"/case["id"]
    manifest = read(data_dir/"manifest.json")
    train = load_episodes(data_dir/"train.npz", manifest["train"]["sha256"])
    heldout = load_episodes(data_dir/"heldout.npz", manifest["heldout"]["sha256"])
    observations_count = sum(len(acts) for _, acts in train)
    dimension, history = train[0][0][0].size, max(len(acts) for _, acts in train)
    actions = tuple(range(case["spec"]["actions"]))
    feature_count = dimension + history * (dimension + len(actions))
    array_bytes = observations_count * feature_count * 9
    allocation = {"reference_feature_and_valid_bytes": array_bytes,
                  "available_physical_bytes": psutil.virtual_memory().available}
    progress = lambda stage: save(folder/"progress.json", {"stage": stage, "resources": resources(),
                                                          "wall_seconds": time.perf_counter()-case_start})
    result = {"case": case, "allocation": allocation, "conditions": {}, "status": "RUNNING"}
    try:
        if array_bytes > allocation["available_physical_bytes"]:
            result.update(status="RESOURCE UNAVAILABLE - NOT RUN", reason="Unmodified reference allocation exceeds available physical memory; no data/history truncation")
            for condition in CONDITIONS:
                result["conditions"][condition] = {"status": "NOT RUN; complete paired comparison unavailable"}
            return result
        if case["domain"] not in ("finite", "partial"):
            from scripts.integrated_predictive_visual_evaluation import evaluate
            result["conditions"] = evaluate(case,train,heldout,data_dir/"hidden_evaluator_only.json",
                                             config,ROOT,folder,fit_new,save,progress)
            frozen_check(output)
            assert sha(data_dir/"train.npz") == manifest["train"]["sha256"]
            assert sha(data_dir/"heldout.npz") == manifest["heldout"]["sha256"]
            result["status"] = "COMPLETE"
            return result
        progress("OLD training")
        stream = [(None, int(train[0][0][0][0]))] + [(int(a), int(obs[0])) for a, obs in zip(train[0][1], train[0][0][1:], strict=True)]
        start = time.process_time()
        old_model = old.replay_stream(stream, len(actions), "split_merge")
        old_fit_cpu = time.process_time()-start
        old_train, old_test = ev.old_contexts(train, old_model), ev.old_contexts(heldout, old_model)
        old_initial = {old_train[0][0]}
        old_view = ev.NeutralModel(actions, dict(enumerate(old_model.labels)), old_model.model["rows"], old_initial)
        old_support = ev.raw_support_by_state(train, old_train)
        means = ev.old_response_means(train, old_train)
        trained = {"OLD": (old_model, old_view, old_train, old_test, old_support, means, old_fit_cpu)}
        for condition, target in (("NEW-ABS", "absolute"), ("NEW-DELTA", "delta")):
            progress(f"{condition} reference then sweep then equality assertion")
            trained[condition] = fit_new(train, heldout, actions, target, folder)
        progress("External evaluation only; hidden truth opened after all fits")
        # Hidden information is first loaded here, after every learner is frozen.
        spec = case["spec"]
        table, emissions = old.finite_world(spec["n"], len(actions), spec["seed"], spec["kind"])
        hidden = read(data_dir/"hidden_evaluator_only.json")
        truth_partition = old.true_partition(table, emissions)["blocks"]
        truth = [truth_partition[h] for episode in hidden for h in episode]
        raw = [row for obs, _ in heldout for row in obs]
        goals = sorted(set(map(int, emissions)))[:config["evaluation_goals"]]
        for condition in CONDITIONS:
            start = time.process_time()
            if condition == "OLD":
                model, view, train_states, test_states, support, means, fit_cpu = trained[condition]
                state_keys = [s for seq in test_states for s in seq]
                quality = ev.common_partition(state_keys, truth)
                quality.update(ev.response_error(heldout, test_states, lambda s,a: means[s,a], "delta"))
                memory, selected = ev.ambiguity_diagnostics(raw, truth, state_keys)
                memory["recursive_full_history_agreement"] = None
                memory["reason"] = "OLD does not expose recursive belief; not applicable"
                depths = {}
                for obs, acts in heldout:
                    context = (int(obs[0][0]),)
                    for a, following in zip(acts, obs[1:], strict=True):
                        depth = model._classify(context)[1]
                        depths[depth] = depths.get(depth,0)+1
                        context = (context+(int(a), int(following[0])))[-13:]
                labels = [None] * len(model.leaf_keys)
                for i,s in enumerate(model.mapping): labels[s] = model.contexts[i][-1]
                audit = ev.audit_operator(labels, [actions]*len(labels), model.leaf_counts,
                                          model.model["blocks"], model.model["rows"])
                memory_bytes = ev.heap_bytes(vars(model))
                quality.update(states=len(model.labels), symbols=len(set(model.labels)), selected_history_depth_distribution=depths,
                               fit_cpu=fit_cpu, perception_cpu=0.0, model_memory_bytes=memory_bytes,
                               unknown_state_fraction=sum(s is None for s in state_keys)/len(state_keys))
                def encoder(obs, acts):
                    # Neutral inference consumes OLD emissions, not OLD decisions.
                    return int(obs[-1][0])
                complete_start = time.process_time()
                complete, _ = old.evaluate_goals(model, lambda s,a: int(table[s,a]), lambda s,t: int(emissions[s]),
                                               [0], goals, config["planning_horizon"], spec["seed"])
                complete["reasoning_and_rollout_cpu"] = time.process_time()-complete_start
                complete["success_at_reset"] = sum(g == int(emissions[0]) for g in goals)
                costs = {"old_world_fit_cpu": fit_cpu, "perception_cpu": 0.0, "recursive_belief_cpu": 0.0,
                         "independent_replay_cpu": 0.0, "reasoning_cpu": complete["reasoning_and_rollout_cpu"]}
                assert audit["eps_action"] == 0
            else:
                perception, world, train_symbols, test_symbols, fit_costs = trained[condition]
                records, test_states, memory_costs = ev.memory_records(world, heldout, test_symbols)
                save(folder/f"{condition}_belief_records.json", records)
                state_keys = [b for seq in test_states for b in seq]
                quality = ev.common_partition(state_keys, truth)
                symbol_quality = ev.common_partition([s for seq in test_symbols for s in seq], truth)
                quality.update(ev.response_error(heldout, test_symbols, perception.predict_response, perception.target))
                memory, selected = ev.ambiguity_diagnostics(raw, truth, state_keys)
                symbol_ambiguity, _ = ev.ambiguity_diagnostics(raw, truth, [s for seq in test_symbols for s in seq])
                memory.update(steps=len(records), agreement_count=sum(r["agrees"] for r in records),
                              recursive_full_history_agreement=sum(r["agrees"] for r in records)/len(records),
                              unknown_steps=sum(r["unknown"] for r in records),
                              contradiction_steps=sum(r["contradiction"] for r in records),
                              known_nonempty_steps=sum(not r["unknown"] and not r["contradiction"] for r in records),
                              symbol_collision_pairs=symbol_ambiguity["collision_pairs"],
                              mean_belief_size=float(np.mean([r["belief_size"] for r in records])))
                assert all(r["agrees"] for r in records), "Recursive/full-history disagreement"
                indices = {a:i for i,a in enumerate(world.actions)}
                counts = {(s,indices[a]): c for (s,a),c in world.counts.items()}
                audit = ev.audit_operator(world.labels, [actions]*len(world.labels), counts,
                                          world.certificate["blocks"], world.certificate["rows"])
                assert audit["eps_action"] == 0
                audit["new_world_contains_q"] = False
                audit["q_check"] = "live model/perception attributes asserted; frozen NEW construction and reasoning have no q parameter"
                view = ev.NeutralModel(actions, world.emissions, world.operators, world.initial)
                train_states = [[world.certificate["blocks"][p] for p in path] for _,_,path in world.episodes]
                support = ev.raw_support_by_state(train, train_states)
                quality.update(states=len(world.emissions), symbols=perception.report.generated_symbols,
                               selected_history_depth_distribution=ev.available_depths(perception,heldout),
                               selected_history_depth_max=perception.report.selected_history_depth,
                               symbol_partition=symbol_quality,
                               fit_cpu=fit_costs["sweep"]["cpu_seconds"]+fit_costs["world_and_quotient_cpu"],
                               perception_cpu=fit_costs["sweep"]["cpu_seconds"],
                               model_memory_bytes=ev.heap_bytes((vars(perception),vars(world))),
                               unknown_state_fraction=sum(ev.UNKNOWN in b for b in state_keys)/len(state_keys),
                               contradiction_fraction=sum(not b for b in state_keys)/len(state_keys))
                encoder = perception.encode_history
                complete = ev.new_rollouts(world, perception, table, emissions, goals, support, config["planning_horizon"])
                costs = {"perception_cpu": fit_costs["sweep"]["cpu_seconds"],
                         "reference_validation_fit_cpu": fit_costs["reference"]["cpu_seconds"],
                         "equivalence_and_encoding_cpu": fit_costs["equivalence_and_encoding_cpu"],
                         "world_and_quotient_cpu": fit_costs["world_and_quotient_cpu"],
                         "reasoning_cpu": complete["reasoning_cpu"], **memory_costs}
            memory["future_prediction_on_ambiguous_cases"] = ev.future_support_quality(heldout,test_states,view,support,selected)
            neutral = ev.neutral_rollouts(view, encoder, table, emissions, goals, support, config["planning_horizon"])
            costs["neutral_reasoning_cpu"] = neutral["reasoning_cpu"]
            costs["evaluation_total_cpu"] = time.process_time()-start
            result["conditions"][condition] = {"status": "COMPLETE", "world_model": quality, "memory": memory,
                                               "operator": audit, "neutral": neutral, "complete_system": complete,
                                               "compute": costs, "resource_sample": resources()}
        frozen_check(output)
        assert sha(data_dir/"train.npz") == manifest["train"]["sha256"]
        assert sha(data_dir/"heldout.npz") == manifest["heldout"]["sha256"]
        result["status"] = "COMPLETE"
        return result
    except MemoryError:
        result.update(status="RESOURCE UNAVAILABLE - NOT COMPLETED", exception=traceback.format_exc())
        return result
    except Exception:
        result.update(status="EXECUTION ERROR - NOT A CAPABILITY RESULT", exception=traceback.format_exc())
        return result
    finally:
        result["wall_seconds"] = time.perf_counter()-case_start
        result["cpu_seconds"] = time.process_time()-cpu_start
        result["resources"] = resources()
        save(folder/"result.json", result)
        progress(result["status"])


def write_csv(path, rows):
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with Path(path).open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows({k:json.dumps(v) if isinstance(v,(dict,list)) else v for k,v in row.items()} for row in rows)


def summarize(output, config):
    results = [read(p) for p in sorted((Path(output)/"cases").glob("*/result.json"))]
    summary = {"status": "COMPLETE" if len(results)==len(config["cases"]) and all(r["status"]=="COMPLETE" for r in results) else "RUN NOT COMPLETED",
               "requested_cases": len(config["cases"]), "recorded_cases": len(results),
               "case_status_counts": dict(Counter(r["status"] for r in results)), "domains": {}}
    tables = {key:[] for key in ("world_model_comparison", "memory_validation", "neutral_evaluator", "complete_system", "compute_scaling")}
    audits = []
    for result in results:
        for condition in CONDITIONS:
            prefix = {"domain": result["case"]["domain"], "seed": result["case"]["spec"]["seed"], "condition": condition,
                      "status": result["status"]}
            data = result["conditions"].get(condition,{})
            for table, key in (("world_model_comparison","world_model"),("memory_validation","memory"),
                               ("neutral_evaluator","neutral"),("complete_system","complete_system"),("compute_scaling","compute")):
                fields = {k:v for k,v in data.get(key,{}).items() if k not in {"tasks", "symbol_partition"}}
                tables[table].append({**prefix, **fields})
            audits.append({**prefix, **data.get("operator",{})})
    for domain in dict.fromkeys(c["domain"] for c in config["cases"]):
        summary["domains"][domain] = {}
        subset = [r for r in results if r["case"]["domain"]==domain and r["status"]=="COMPLETE"]
        for condition in CONDITIONS:
            values = [r["conditions"][condition] for r in subset]
            entry = {"completed_environments": len(values)}
            for key in ("predictive_violation", "false_merge", "false_split", "future_error", "states", "symbols", "fit_cpu", "model_memory_bytes"):
                known = [v["world_model"][key] for v in values if v["world_model"].get(key) is not None]
                entry[key+"_environment_mean"] = float(np.mean(known)) if known else None
            for key in ("neutral", "complete_system"):
                total = sum(v[key]["trials"] for v in values)
                successes = sum(v[key]["successes"] for v in values)
                reset = sum(v[key]["success_at_reset"] for v in values)
                entry[key] = {"successes":successes, "trials":total, "success":successes/total if total else None,
                              "success_at_reset":reset}
            steps = sum(v["memory"].get("steps",0) for v in values)
            agreeing = sum(v["memory"].get("agreement_count",0) for v in values)
            entry["memory"] = {"steps":steps, "agreements":agreeing, "agreement":agreeing/steps if steps else None,
                               "unknown_steps":sum(v["memory"].get("unknown_steps",0) for v in values),
                               "contradiction_steps":sum(v["memory"].get("contradiction_steps",0) for v in values),
                               "same_observation_different_future_pairs":sum(v["memory"]["same_observation_different_future_pairs"] for v in values),
                               "collision_pairs":sum(v["memory"]["collision_pairs"] for v in values)}
            summary["domains"][domain][condition] = entry
    summary["compute"] = {"case_cpu_seconds":sum(r.get("cpu_seconds",0) for r in results),
                           "peak_worker_memory_bytes":max((r.get("resources",{}).get("process_peak_working_set_bytes") or 0 for r in results),default=0),
                           "note":"Includes reference equivalence and external evaluation; per-condition costs are separate in compute_scaling.csv"}
    for name, rows in tables.items(): write_csv(Path(output)/(name+".csv"), rows)
    save(Path(output)/"operator_audit.json",audits)
    save(Path(output)/"metrics.json",summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--prepare-only",action="store_true")
    parser.add_argument("--evaluate-prepared",action="store_true")
    parser.add_argument("--shard",type=int)
    parser.add_argument("--shards",type=int,default=30)
    parser.add_argument("--summarize-only",action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    frozen_check(output)
    if args.summarize_only:
        print(json.dumps(summarize(output,read(output/"config.json")),indent=2))
        return
    if not args.evaluate_prepared:
        config = protocol()
        save(output/"config.json",config,exclusive=True)
        save(output/"rng_seeds.json",[{"case":c["id"],"environment":c["spec"]["seed"],
             "heldout_actions":c["evaluation_seed"],"training_render":c["spec"]["seed"]+700000,
             "heldout_render":c["spec"]["seed"]+900000} for c in config["cases"]],exclusive=True)
        save(output/"environment.json",{"python":platform.python_version(),"numpy":np.__version__,
             "psutil":psutil.__version__,"platform":platform.platform(),"resources":resources(),
             "command":subprocess.list2cmdline([sys.executable,*sys.argv])},exclusive=True)
        harness = {}
        for path in (Path(__file__),ROOT/"scripts/integrated_predictive_evaluation.py",ROOT/"scripts/integrated_predictive_visual_evaluation.py"):
            harness[str(path.relative_to(ROOT))] = sha(path)
            shutil.copy2(path,output/"frozen_source"/"scripts"/path.name)
        save(output/"harness_sha.json",harness,exclusive=True)
        manifests = []
        for case in config["cases"]:
            manifests.append(prepare_case(case,output,config))
            log(output,event="dataset_saved",case=case["id"],train_sha256=manifests[-1]["train"]["sha256"])
        save(output/"shared_dataset_hashes.json",manifests,exclusive=True)
        log(output,event="all_shared_data_frozen",cases=len(manifests))
    else:
        config = read(output/"config.json")
        for path,expected in read(output/"harness_sha.json").items():
            assert sha(ROOT/path)==expected, "Harness changed after dataset freeze"
        assert len(read(output/"shared_dataset_hashes.json"))==len(config["cases"])
    if args.prepare_only:
        return
    suffix = "" if args.shard is None else f"_shard_{args.shard}"
    save(output/f"execution_command{suffix}.json",{"command":subprocess.list2cmdline([sys.executable,*sys.argv]),
         "timestamp":datetime.now(timezone.utc).isoformat()},exclusive=True)
    if args.shard is None:
        cases = config["cases"]
    else:
        assert args.shards == 30 and 0 <= args.shard < 30
        # Twenty independent finite/partial batches; ten separate image jobs.
        # A slow image reference check must not hold finite cases behind it.
        cases = [c for i,c in enumerate(config["cases"])
                 if (i % 20 if i < 120 else 20+i-120) == args.shard]
    execution_errors = []
    with ProcessPoolExecutor(max_workers=1 if args.shard is not None else config["workers"]) as pool:
        futures = {pool.submit(run_case,case,str(output),config):case for case in cases}
        for future in as_completed(futures):
            result = future.result()
            if result["status"].startswith("EXECUTION ERROR"):
                execution_errors.append(result["case"]["id"])
            log(output,event="case_finished",case=result["case"]["id"],status=result["status"],wall_seconds=result["wall_seconds"])
            summarize(output,config)
    frozen_check(output)
    summary = summarize(output,config)
    log(output,event="execution_finished",status=summary["status"],statuses=summary["case_status_counts"])
    if execution_errors:
        raise RuntimeError(f"Harness execution errors (not capability failures): {execution_errors}")


if __name__ == "__main__":
    main()
