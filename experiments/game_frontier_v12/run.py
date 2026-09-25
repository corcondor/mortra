"""Only mutation proposals learn; all candidate evaluation and selection is v1.1."""
import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import random
import time
from types import FunctionType

from experiments.game_frontier_v11 import runner as frozen
from experiments.game_frontier_v11_holdout import audit as holdout
from experiments.game_frontier_v11_replication import run as replication
from .proposal import Context, ContextualUCB, FAMILIES, Outcome, reward, sample

io = frozen.base
SEEDS = [2101, 2202, 2303, 2404, 2505, 2606, 2707, 2808]
SMOKE_SEEDS = [3101, 3202, 3303]
CONDITIONS = ["adaptive", "uniform", "random", "size_only"]
PROTOCOL = {
    "name": "frontier-v1.2-contextual-ucb-proposal", "seeds": SEEDS, "smoke_seeds": SMOKE_SEEDS,
    "algorithm": "independent UCB1 tables by (floor(log2 reachable states), B80 reached/unreached)",
    "context_features_used": ["reachable-state log2 bin", "B80 reached/unreached"],
    "other_context": "rule/variable/action counts, board area and selection D recorded; not used as additional UCB keys",
    "reward": "D_candidate-D_parent iff valid AND full_info>=.8 AND final_selection_success>=.8; otherwise 0",
    "ucb": "mean((reward/D_span+1)/2)+sqrt(2*log(total_context_trials)/arm_trials); untried arms first",
    "D_span": "log2(max_checkpoint)-log2(min_checkpoint)=13; derived normalization only",
    "probability": "uniform over UCB maximizers; uniform over all 14 arms throughout generation 1",
    "update_timing": "after every slot including invalid/no-op/unresolved (zero utility, not task failure); selection after eight slots",
    "rng": "consume original uniform family draw before mutate; generation 1 uses it; later adaptive UCB tie RNG=derive(seed,generation,slot,'proposal')",
    "freeze": "v1.1 c0f9f7b2c55d01bdb300b1ebb060f55b6c4d0902, 18 hashes; baseline 483d1592e5cd0d2b23d474cc79e217b121fd1fbe",
    "selection": "frozen choose('mortra') for adaptive/uniform; frozen random and size_only controls",
    "holdout_seed_root": replication.TASK_SEED_ROOT,
    "holdout_timing": "only after all 32 Stage 2 evolution runs finish, then freeze all task sets before evaluation",
    "holdout_sampling": "unchanged replication protocol; up to 500 distance>=4 unused pairs, shortage census",
    "holdout_exclusion": "union of all same-genome selection pairs from this experiment's initial pools and candidates",
    "prior_experiment_inputs": [], "pass_criterion": None,
    "smoke_gate": "correctness only: finite changing probabilities, equal slots, reproducible frozen player, replayable proposal history; no performance gate",
    "stopping": "Stage 0, independent three-seed Stage 1, eight-seed Stage 2 then report and stop; no retuning",
    "counterfactual_audit": "descriptive association on observed proposed arms only, not causal untried-arm counterfactuals",
}


def config(stage=2):
    cfg = frozen.config(2)
    cfg.update(stage=stage, seeds=SMOKE_SEEDS if stage == 1 else SEEDS,
               conditions=CONDITIONS[:2] if stage == 1 else CONDITIONS,
               generations=5 if stage == 1 else 10)
    return cfg


def provenance(stage=2):
    p = io.provenance(config(stage), config(stage)["seeds"])
    p["source_hashes_lf"] = holdout.verified_sources()
    files = [*sorted((io.ROOT / "experiments/game_frontier_v12").glob("*.py")),
             io.ROOT / "scripts/evaluate_autonomous_game_frontier_v12.py",
             io.ROOT / "tests/test_autonomous_game_frontier_v12.py",
             io.ROOT / ".github/workflows/autonomous-game-frontier-v12.yml",
             io.ROOT / "docs/research/FRONTIER-V12-PREREGISTRATION-20260925.md",
             io.ROOT / "experiments/game_frontier_v11_replication/run.py",
             io.ROOT / "experiments/game_frontier_v11_holdout/audit.py",
             io.ROOT / "experiments/game_frontier_v11_generation_holdout/audit.py"]
    p["v12_source_hashes_lf"] = {x.relative_to(io.ROOT).as_posix(): hashlib.sha256(x.read_text(encoding="utf-8").encode()).hexdigest() for x in files}
    p["protocol"] = PROTOCOL
    p["protocol_sha256"] = holdout.digest(PROTOCOL)
    return p


def context_of(genome, parent):
    return Context(parent["oracle"]["reachable_states"], len(genome["rules"]), len(genome["domains"]),
                   genome["actions"], genome["domains"][0] * genome["domains"][1], parent["D"] or 0., parent["B80"])


def outcome_of(result):
    if result is None:
        return Outcome(False, False, None, None, None, None, None)
    full = result["full_info"]["success_rate"] if result["full_info"] else None
    eligible = bool(result["valid"] and full is not None and full >= .8 and result["final_success"] is not None and result["final_success"] >= .8)
    return Outcome(result["valid"], eligible, result["D"], result["B80"], result["B90"], result["final_success"], full)


def delta_crossing(child, parent):
    return {"child": child, "parent": parent, "delta": child-parent if child is not None and parent is not None else None,
            "censored": child is None or parent is None}


def proposal(learner, context, condition, seed, generation, slot):
    rng = random.Random(io.derive(seed, generation, slot, "mutation"))
    arms = frozen.SIZE_FAMILIES if condition == "size_only" else FAMILIES
    original = rng.choice(arms)
    if condition == "adaptive":
        decision = learner.decision(context, generation)
        family = original if generation == 1 else sample(decision["probabilities"], random.Random(io.derive(seed, generation, slot, "proposal")))
    else:
        decision = {"context_key": context.key(), "context": asdict(context),
                    "probabilities": {a: 1/len(arms) if a in arms else 0. for a in FAMILIES}}
        family = original
    return family, rng, decision


def run_condition(cfg, seed, condition, chosen, directory, prov, emit):
    directory.mkdir(parents=True, exist_ok=False)
    genome = chosen["genome"]
    parent = frozen.train_candidate(genome, chosen["prepared"], cfg, seed,
        {"generation": 0, "candidate": 0, "mutation": "initial", "parent_hash": None}, directory)
    learner = ContextualUCB(math.log2(cfg["checkpoints"][-1] / cfg["checkpoints"][0]))
    candidates, frontier, history = [parent], [parent], []
    for generation in range(1, cfg["generations"] + 1):
        current, genomes = [], []
        context = context_of(genome, parent)
        for slot in range(cfg["candidates"]):
            cpu = time.process_time()
            family, rng, decision = proposal(learner, context, condition, seed, generation, slot)
            proposal_cpu = time.process_time() - cpu
            meta = {"generation": generation, "candidate": slot, "mutation": family, "parent_hash": parent["game_hash"]}
            event = {**meta, "decision": decision, "proposal_cpu_seconds": proposal_cpu, "parent_B80": parent["B80"], "parent_B90": parent["B90"]}
            result = None
            try:
                g = frozen.mutate(genome, family, rng, cfg["max_board"])
            except ValueError as exc:
                event.update(status="INVALID", reason=str(exc))
            else:
                prepared = frozen.prepare(g, cfg, seed)
                result = frozen.train_candidate(g, prepared, cfg, seed, meta, directory)
                candidates.append(result)
                current.append(result)
                genomes.append(g)
                event.update(status=result["classification"], game_hash=result["game_hash"])
            outcome = outcome_of(result)
            cpu = time.process_time()
            value = learner.update(context, family, outcome) if condition == "adaptive" else reward(context.selection_D, outcome)
            event.update(outcome=asdict(outcome), reward=value,
                         delta_D_selection=outcome.D-context.selection_D if outcome.D is not None else None,
                         delta_B80=delta_crossing(outcome.B80, parent["B80"]),
                         delta_B90=delta_crossing(outcome.B90, parent["B90"]),
                         posterior_after=learner.snapshot() if condition == "adaptive" else None,
                         update_cpu_seconds=time.process_time()-cpu)
            history.append(event)
            emit(f"{condition} G{generation} C{slot} {family} {event['status']} reward={value} D={outcome.D}")
            io.write_json(directory / "proposal_history.json", history)
            io.write_json(directory / "partial_results.json", {"status": "RUNNING", "candidates": candidates, "frontier": frontier})
        offers = [frozen.feedback(r) for r in current]
        selected = frozen.choose("mortra" if condition in ("adaptive", "uniform") else condition,
            frozen.feedback(parent), offers, random.Random(io.derive(seed, generation, "selection")), cfg["checkpoints"][-1])
        index = next((i for i, c in enumerate(offers) if c is selected), None)
        if index is not None:
            parent, genome = current[index], genomes[index]
        for h in history:
            if h["generation"] == generation:
                h["selected"] = index is not None and h.get("game_hash") == parent["game_hash"] and h["candidate"] == parent["candidate"]
        frontier.append(parent)
        emit(f"SELECT {condition} G{generation} hash={parent['game_hash']} D={parent['D']} S={parent['final_success']}")
    assert len(history) == cfg["generations"] * cfg["candidates"]
    result = {"status": "COMPLETED", "stage": cfg["stage"], "seed": seed, "condition": condition, "config": cfg,
              "provenance": {**prov, **provenance(cfg["stage"])}, "candidates": candidates, "frontier": frontier,
              "mutation_history": history, "proposal_posterior": learner.snapshot() if condition == "adaptive" else None}
    io.write_json(directory / "results.json", result)
    io.write_json(directory / "proposal_history.json", history)
    validate_run(result)
    return result


def validate_run(result):
    cfg, seed, condition = result["config"], result["seed"], result["condition"]
    model = ContextualUCB(13)
    history = result["mutation_history"]
    assert len(history) == cfg["generations"] * 8
    for index, event in enumerate(history):
        generation, slot = divmod(index, 8)
        generation += 1
        assert (event["generation"], event["candidate"]) == (generation, slot)
        context = Context(**event["decision"]["context"])
        arm, _, d = proposal(model, context, condition, seed, generation, slot)
        assert arm == event["mutation"] and d == event["decision"]
        outcome = Outcome(**event["outcome"])
        value = model.update(context, arm, outcome) if condition == "adaptive" else reward(context.selection_D, outcome)
        assert value == event["reward"]
        if condition == "adaptive":
            assert model.snapshot() == event["posterior_after"]
    assert model.snapshot() == (result["proposal_posterior"] or {})
    return True


def seed_callable(stage):
    namespace = dict(frozen.run_seed.__globals__)
    namespace.update(config=config, CONDITIONS=config(stage)["conditions"], run_condition=run_condition)
    return FunctionType(frozen.run_seed.__code__, namespace, frozen.run_seed.__name__, frozen.run_seed.__defaults__)


def evolve(stage, seed, output):
    assert seed in config(stage)["seeds"]
    before = holdout.verified_sources()
    seed_callable(stage)(stage, seed, output)
    assert before == holdout.verified_sources()
    io.write_json(Path(output) / "source_snapshot.json", provenance(stage))


def register(output):
    out = Path(output)
    out.mkdir(parents=True, exist_ok=False)
    for name, value in (("source_snapshot", provenance()), ("config", config()), ("protocol", PROTOCOL),
                        ("rng_seeds", {"stage1": SMOKE_SEEDS, "stage2": SEEDS, "holdout_root": replication.TASK_SEED_ROOT})):
        io.write_json(out / (name + ".json"), value)


def smoke_check(input_dir, output):
    out = Path(output)
    out.mkdir(parents=True, exist_ok=False)
    seen, starts, changed, checkpoints = set(), {}, {}, 0
    for p in sorted(Path(input_dir).rglob("results.json")):
        r = replication.read(p)
        assert r["status"] == "COMPLETED" and r["config"] == config(1)
        validate_run(r)
        key = r["seed"], r["condition"]
        assert key not in seen
        seen.add(key)
        starts.setdefault(r["seed"], set()).add(r["frontier"][0]["game_hash"])
        if r["condition"] == "adaptive":
            changed[r["seed"]] = any(len(set(h["decision"]["probabilities"].values())) > 1 for h in r["mutation_history"])
        checked = set()
        for record in r["frontier"]:
            if record["game_hash"] in checked:
                continue
            checked.add(record["game_hash"])
            g = replication.read(p.parent / "games" / record["game_hash"] / "genome.json")
            b = {"genome": g, "archived_final": record, "holdout_tasks": [], "player_seed": io.derive(r["seed"], record["game_hash"], "player")}
            paired, _ = holdout.paired_learning(b)
            assert all(row["holdout"] is None for row in paired)
            checkpoints += len(paired)
    assert seen == {(s, c) for s in SMOKE_SEEDS for c in CONDITIONS[:2]}
    assert all(len(v) == 1 for v in starts.values()) and all(changed.values())
    io.write_json(out / "smoke_gate.json", {"status": "CORRECTNESS_GATE_PASSED", "runs": len(seen),
        "proposal_updated": changed, "player_checkpoints_reproduced": checkpoints,
        "holdout_generated": False, "performance_used_as_gate": False})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("register", "evolve", "smoke-check", "freeze", "audit", "summarize"))
    parser.add_argument("--stage", type=int, choices=(1, 2), default=2)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--frozen", type=Path)
    parser.add_argument("--evolution", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.mode == "register": register(args.output)
    elif args.mode == "evolve": evolve(args.stage, args.seed, args.output)
    elif args.mode == "smoke-check": smoke_check(args.input, args.output)
    else:
        from . import audit
        if args.mode == "freeze": audit.freeze(args.input, args.output)
        elif args.mode == "audit": audit.audit_seed(args.frozen, args.output, args.seed)
        else: audit.summarize(args.input, args.frozen, args.evolution, args.output)
