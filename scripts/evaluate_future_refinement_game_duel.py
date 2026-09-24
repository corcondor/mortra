"""Development game construction after the user's explicit Stage-1 redirection.

Frozen learners, frozen OLD collector/readout, existing game editor. The common
legacy visual encoder supplies opaque symbols, not hidden simulator state.
This is not a Stage-1 pass or a blinded capability benchmark.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict, deque
import copy
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import random
import subprocess
import sys
import time
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.evaluate_future_refinement_small_ab import (
    FutureRefinementCore, old, save, sha, verify_sources,
)
from mortra_predictive_perception.adapters import load_legacy_visual
from scripts.active_world_discovery_v2 import make_classifier
from scripts.integrated_predictive_evaluation import heap_bytes

CONFIG = {
    "purpose": "development game construction; user redirected away from Stage 1",
    "stage1_status": "NOT ASSERTED PASSED; no Stage-1 rerun",
    "seeds": [201, 302, 403], "edits": 3,
    "exploration_steps": old.default_config()["game_steps"],
    "trials": old.default_config()["game_trials"],
    "horizon": old.default_config()["planning_horizon"],
    "collector": "frozen OLD HistoryModel + IdentificationPolicy; single shared stream",
    "symbols": "existing make_classifier; existing full-game visual renderer; common to both",
    "reasoner": "evaluate_fixed_field_congruence.solve_fixed_field, q=0.90",
    "readout": "frozen OLD run_game expected successor value; smallest action tie",
    "environment_editor": "evaluate_autonomous_game_design_loop unchanged definitions",
    "random_baseline": "independent subprocess, one Boolean result per trial",
    "oracle": "evaluation-only exhaustive BFS, stop at first goal or exhausted graph",
    "unknown": "missing action rows omitted; no fallback actions",
    "q_scope": "OLD shared downstream reasoner only; absent from NEW core",
    "observation_caveat": "legacy noisy image encoder is frozen, not a new raw-visual experiment",
    "acceptance_caveat": "legacy wording 'unsolvable' means self-player failed; oracle is separate",
    "oracle_gate": "oracle-unsolvable proposals rejected for both designers",
}


def legacy_design():
    path = ROOT / "scripts/evaluate_autonomous_game_design_loop.py"
    names = {"MicroGame", "critique_game", "get_free_inner_cells",
             "apply_targeted_mutation", "decide_acceptance", "render_game_map"}
    tree = ast.parse(path.read_bytes(), filename=str(path))
    nodes = [n for n in tree.body if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name in names]
    assert {n.name for n in nodes} == names
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches
    ns = dict(np=np, random=random, math=math, defaultdict=defaultdict,
              deque=deque, plt=plt, patches=patches, NUM_ACTIONS=5)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), ns)
    return SimpleNamespace(**{name: ns[name] for name in names})


def from_definition(definition, design):
    game = design.MicroGame(width=definition["width"], height=definition["height"])
    for name, value in definition.items():
        if name in ("walls", "hazards"):
            value = set(map(tuple, value))
        elif name.endswith("_pos") or name in ("teleport_a", "teleport_b"):
            value = tuple(value) if value is not None else None
        setattr(game, name, value)
    return game


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def exact_solvability(game):
    start = game.get_initial_state()
    queue, parents = deque([start]), {start: None}
    while queue:
        state = queue.popleft()
        if game.is_goal(state):
            word = []
            while parents[state] is not None:
                state, action = parents[state]
                word.append(action)
            return {"solvable": True, "shortest_actions": list(reversed(word)),
                    "visited": len(parents), "scope": "evaluation only; never passed to player/editor"}
        for action in range(5):
            nxt = game.step(state, action)
            if nxt not in parents:
                parents[nxt] = (state, action)
                queue.append(nxt)
    return {"solvable": False, "shortest_actions": None, "visited": len(parents),
            "scope": "exhausted finite reachable graph"}


def random_trials(game, trials, horizon, seed):
    rng = random.Random(seed)
    records = []
    for trial in range(trials):
        state, actions = game.get_initial_state(), []
        states = [state]
        while len(actions) < horizon and not game.is_goal(state):
            action = rng.randrange(5)
            actions.append(action)
            state = game.step(state, action)
            states.append(state)
        records.append({"trial": trial, "actions": actions, "states": states,
                        "success": bool(game.is_goal(state))})
    successes = sum(int(row["success"]) for row in records)
    assert 0 <= successes <= trials and len(records) == trials
    return {"trials": trials, "successes": successes, "records": records}


class FrozenEncoder:
    """Apply learned history rules to new histories, without adding evidence."""
    def __init__(self, learner, condition):
        self.learner, self.condition = learner, condition
        if condition == "NEW":
            self.view = copy.copy(learner)
            for name in ("nodes",):
                setattr(self.view, name, list(getattr(learner, name)))
            for name in ("root_index", "child_index", "_suffix_cache"):
                setattr(self.view, name, dict(getattr(learner, name)))
            self.key_to_block = {key: learner.model["blocks"][i]
                                 for i, key in enumerate(learner.leaf_keys)}

    def begin(self, obs):
        if self.condition == "OLD":
            self.context = (int(obs),)
        else:
            self.node = self.view._intern_root(int(obs))
        return self.state()

    def advance(self, action, obs):
        if self.condition == "OLD":
            # Exactly the historical OLD run_game inference context.
            self.context = (self.context + (action, int(obs)))[-13:]
        else:
            self.node = self.view._intern_child(self.node, action, int(obs))
        return self.state()

    def state(self):
        if self.condition == "OLD":
            return self.learner.encode(self.context)
        key, _ = self.view._classify(self.node)
        return self.key_to_block.get(key)


def planner_model(learner, condition):
    if condition == "OLD":
        return learner.model["K"], learner.model["rows"], list(learner.labels)
    counts = defaultdict(Counter)
    blocks = learner.model["blocks"]
    for (s, a), row in learner.leaf_counts.items():
        for v, n in row.items():
            counts[blocks[s], a][blocks[v]] += n
    rows = {key: {v: Fraction(n, sum(row.values())) for v, n in row.items()}
            for key, row in counts.items()}
    labels = learner.quotient_labels()
    K = []
    for s in range(len(labels)):
        choices = [rows[s, a] for a in learner.actions if (s, a) in rows]
        row = defaultdict(Fraction)
        for choice in choices:
            for v, p in choice.items():
                row[v] += p / len(choices)
        # Historical reasoner terminal convention, not a claimed observed T_a.
        K.append(dict(row) if choices else {s: Fraction(1)})
    return K, rows, [labels[s] for s in range(len(labels))]


def collect(game, seed, render, steps, progress):
    np.random.seed(seed + 700000)
    classify, prototypes, _ = make_classifier()
    learner = old.HistoryModel(5)
    policy = old.IdentificationPolicy(5, seed + 100000)
    hidden = game.get_initial_state()
    first = int(classify(render(game, hidden, 0)))
    learner.begin(first)
    observations, actions, truth = [first], [], [hidden]
    previous = None
    for step in range(1, steps + 1):
        partition = tuple(learner.mapping), tuple(learner.model["blocks"])
        action = policy.choose(learner.state(), learner.policy_counts(), partition != previous)
        previous = partition
        hidden = game.step(hidden, action)
        obs = int(classify(render(game, hidden, step)))
        learner.observe(action, obs, step)
        observations.append(obs)
        actions.append(action)
        truth.append(hidden)
        if step % 200 == 0:
            progress(phase="shared_collection", step=step)
    # Goal labels are added only after exploration, matching OLD run_game.
    goals = sorted({obs for obs, st in zip(observations, truth) if game.is_goal(st)})
    return learner, classify, prototypes, {"observations": observations, "actions": actions}, truth, goals


def play(game, learner, condition, classify, render, goal_labels, seed, config):
    K, rows, labels = planner_model(learner, condition)
    targets = [s for s, label in enumerate(labels) if label in goal_labels]
    then = time.process_time()
    psi = old.base.solve_fixed_field(old.dense(K), targets, q=.90)[0] if targets else None
    trials = []
    for trial in range(config["trials"]):
        # Per-trial noise pairing, independent of how early another player stops.
        np.random.seed(seed + 900000 + trial)
        state = game.get_initial_state()
        encoder = FrozenEncoder(learner, condition)
        z = encoder.begin(classify(render(game, state, 0), eval_mode=True))
        actions, states, model_states, reason = [], [state], [z], "budget"
        for step in range(config["horizon"] + 1):
            if game.is_goal(state):
                reason = "goal"; break
            if step == config["horizon"]:
                break
            choices = {} if z is None else {a: rows[z, a] for a in range(5) if (z, a) in rows}
            if psi is None or not choices:
                reason = "unobserved_goal" if psi is None else "unknown_state_or_action"
                break
            action = max(sorted(choices), key=lambda a: sum(float(p) * psi[v] for v, p in choices[a].items()))
            state = game.step(state, action)
            z = encoder.advance(action, classify(render(game, state, step + 1), eval_mode=True))
            actions.append(action); states.append(state); model_states.append(z)
        trials.append({"trial": trial, "success": bool(game.is_goal(state)), "reason": reason,
                       "actions": actions, "states": states, "model_states": model_states})
    summary = learner.summary()
    return {"condition": condition, "trials": trials, "successes": sum(t["success"] for t in trials),
            "states": len(K), "edges": sum(len(row) for row in rows.values()),
            "unknown_rows": len(K) * 5 - len(rows), "observed_goal_labels": goal_labels,
            "summary": summary, "model_memory_bytes": heap_bytes(learner),
            "planning_cpu_seconds": time.process_time() - then}


def design_metrics(game, result, rand):
    records = result["trials"]
    successes = [r for r in records if r["success"]]
    success = len(successes) / len(records)
    random_success = rand["successes"] / rand["trials"]
    action_counts = Counter(a for r in records for a in r["actions"])
    total = sum(action_counts.values())
    visited = {(s[0], s[1]) for r in records for s in r["states"]}
    floor = {(x, y) for x in range(1, game.width - 1) for y in range(1, game.height - 1)} - game.walls
    loops = sum(len(r["states"]) - len(set(map(tuple, r["states"]))) for r in records)
    return {
        "success_rate": round(success, 4), "random_success_rate": round(random_success, 4),
        "strategic_gap": round(success-random_success, 4),
        "mean_actions_to_goal": round(float(np.mean([len(r["actions"]) for r in successes])), 2) if successes else CONFIG["horizon"],
        "state_coverage": result["states"], "edge_coverage": result["edges"],
        "unique_successful_trajectories": len({tuple((s[0],s[1]) for s in r["states"]) for r in successes}),
        "action_entropy": round(-sum((n/total)*math.log2(n/total) for n in action_counts.values()), 3) if total else 0,
        "repeated_loop_rate": round(loops/max(1,total),4),
        "dead_end_rate": sum(r["reason"] == "unknown_state_or_action" for r in records)/len(records),
        "unexplored_regions": len(floor-visited),
    }


def render_result(design, game, results, path, seed):
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(12, 6))
    for ax, condition in zip(axes, ("OLD", "NEW")):
        record = results[condition]["trials"][0]
        # Validate every saved transition before displaying it.
        state = game.get_initial_state()
        assert tuple(record["states"][0]) == state
        for a, expected in zip(record["actions"], record["states"][1:]):
            state = game.step(state, a)
            assert state == tuple(expected)
        assert bool(game.is_goal(state)) == record["success"]
        xy = [(s[0], s[1]) for s in record["states"]]
        design.render_game_map(ax, game, f"Seed {seed} | {condition} | trial 0\nSuccess {record['success']} | {len(record['actions'])} actions", [xy])
    fig.suptitle("Redrawn recorded actions; first trial, no success selection")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def run(seed, out):
    out.mkdir(parents=True, exist_ok=False)
    def progress(**record):
        line = json.dumps({"utc": datetime.now(timezone.utc).isoformat(), "seed": seed, **record})
        print(line, flush=True)
        with (out / "run.log").open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    sources = verify_sources()
    for name in ("scripts/evaluate_future_refinement_game_duel.py", "scripts/evaluate_autonomous_game_design_loop.py",
                 "scripts/evaluate_visual_state_construction.py", "mortra_predictive_perception/adapters.py",
                 "scripts/integrated_predictive_evaluation.py"):
        sources[name] = sha(ROOT / name)
    save(out / "source_sha.json", sources)
    save(out / "config.json", CONFIG)
    save(out / "source_snapshot.json", {
        "timestamp": datetime.now(timezone.utc).isoformat(), "command": sys.argv,
        "branch": subprocess.check_output(["git","branch","--show-current"],cwd=ROOT,text=True).strip(),
        "HEAD": subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
        "status": subprocess.check_output(["git","status","--short"],cwd=ROOT,text=True),
        "run_id": os.environ.get("GITHUB_RUN_ID"),
    })
    save(out / "seeds.json", {"environment":seed,"collector":seed+100000,
                               "render_train":seed+700000,"render_play":seed+900000,
                               "random":seed+500000,"mutation":seed+600000})
    design = legacy_design()
    visual = load_legacy_visual(ROOT / "scripts/evaluate_visual_state_construction.py")
    initial = design.MicroGame(seed=seed)
    initial.generate_random(wall_density=.18)
    save(out / "game_initial.json", initial.to_dict())
    cache = {}

    def evaluate(game):
        key = digest(game.to_dict())
        if key in cache:
            return cache[key]
        directory = out / "games" / key
        directory.mkdir(parents=True)
        save(directory / "game_definition.json", game.to_dict())
        oracle = exact_solvability(game)
        save(directory / "oracle_solvability.json", oracle)
        progress(game=key, phase="evaluation_start", oracle_solvable=oracle["solvable"])
        subprocess.run([sys.executable, str(Path(__file__).resolve()), "--random-worker", str(directory),
                        "--seed", str(seed)], check=True, cwd=ROOT)
        rand = json.loads((directory / "random_raw_trials.json").read_text())
        started = time.process_time()
        learner, classify, prototypes, data, truth, goals = collect(game, seed, visual.render_visual_frame,
                                                                   CONFIG["exploration_steps"], progress)
        old_cpu = time.process_time()-started
        save(directory / "shared_trajectory.json", data)
        save(directory / "evaluation_hidden_states.json", truth)
        save(directory / "shared_dataset_hash.json", {"sha256": digest(data), "conditions": ["OLD","NEW"]})
        new = FutureRefinementCore(tuple(range(5)))
        new.begin(data["observations"][0])
        started = time.process_time()
        for step, (a,o) in enumerate(zip(data["actions"], data["observations"][1:]), 1):
            new.observe(a,o)
            if step % 200 == 0:
                progress(game=key, phase="NEW_replay", step=step, states=len(new.model["groups"]))
        new_cpu = time.process_time()-started
        assert not any(hasattr(new,n) for n in ("goal","q","discount","reward"))
        results = {}
        for condition, model, cpu in (("OLD",learner,old_cpu),("NEW",new,new_cpu)):
            result = play(game, model, condition, classify, visual.render_visual_frame, goals, seed, CONFIG)
            result["training_cpu_seconds"] = cpu
            result["training_cost_scope"] = "collector+encoding+OLD" if condition == "OLD" else "same symbol stream replay only"
            result["design_metrics"] = design_metrics(game, result, rand)
            save(directory / f"{condition.lower()}_play.json", result)
            results[condition] = result
        render_result(design, game, results, directory / "first_trial.png", seed)
        reduced = {"game_hash":key, "oracle":oracle,
                   "conditions":{c:{k:v for k,v in r.items() if k not in ("trials","summary")}
                                 for c,r in results.items()}}
        cache[key] = reduced
        progress(game=key, phase="evaluation_complete", successes={c:r["successes"] for c,r in results.items()})
        return reduced

    initial_result = evaluate(initial)
    save(out / "stage2_play_comparison.json", initial_result)
    finals = {}
    for designer in ("OLD", "NEW"):
        current, result = initial.copy(), initial_result
        rng = random.Random(seed+600000)
        history = []
        for iteration in range(1, CONFIG["edits"]+1):
            metrics = result["conditions"][designer]["design_metrics"]
            critique = design.critique_game(metrics)
            candidate, description = design.apply_targeted_mutation(current, critique, rng)
            candidate_result = evaluate(candidate)
            accepted, reason = design.decide_acceptance(metrics, candidate_result["conditions"][designer]["design_metrics"], critique)
            if not candidate_result["oracle"]["solvable"]:
                accepted, reason = False, "Rejected: external oracle proved unreachable goal"
            history.append({"iteration":iteration,"critique":critique,"mutation":description,
                            "before_game":result["game_hash"],"candidate_game":candidate_result["game_hash"],
                            "accepted":accepted,"reason":reason})
            if accepted:
                current, result = candidate, candidate_result
            progress(designer=designer, iteration=iteration, accepted=accepted, mutation=description)
        directory = out / f"designer_{designer.lower()}"
        save(directory / "game_final.json", current.to_dict())
        save(directory / "designer_history.json", history)
        # Each game was cross-played with frozen, paired inputs before seeing results.
        own = result["conditions"][designer]["successes"] > 0
        other = result["conditions"]["NEW" if designer == "OLD" else "OLD"]["successes"] > 0
        finals[designer] = {"result":result,"accepted_edits":sum(h["accepted"] for h in history),
                            "attack_win":bool(result["oracle"]["solvable"] and own and not other),
                            "self_failure":not own,"universal_hard":result["oracle"]["solvable"] and not own and not other,
                            "universal_easy":own and other}
    save(out / "stage3_game_duel.json", finals)
    save(out / "metrics.json", {"seed":seed,"evaluated_unique_games":len(cache),"initial":initial_result,"finals":finals})
    for name,value in sources.items():
        assert sha(ROOT/name) == value, f"Frozen source changed: {name}"
    progress(phase="COMPLETE", unique_games=len(cache))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed",type=int,choices=CONFIG["seeds"],required=True)
    parser.add_argument("--output",type=Path)
    parser.add_argument("--random-worker",type=Path)
    args = parser.parse_args()
    if args.random_worker:
        directory = args.random_worker
        game = from_definition(json.loads((directory/"game_definition.json").read_text()), legacy_design())
        save(directory/"random_raw_trials.json",random_trials(game,CONFIG["trials"],CONFIG["horizon"],args.seed+500000))
    else:
        if args.output is None:
            parser.error("--output required")
        run(args.seed,args.output.resolve())


if __name__ == "__main__":
    main()
