"""Pre-register and evaluate an archive-capacity study; never feed a learner.

All mathematical evaluation and ablation use the existing measurement API.
This file adds only fixed-input checks and provenance/dependency aggregation.
"""
from copy import deepcopy
from pathlib import Path
import argparse
import os
import sys

CONTROL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CONTROL))
from scripts.measure_persistent_learning import (
    ROOT, Theory, Domain, read, write, digest, make_suite, evaluate,
    final_comparison, descendants, source_seal)


def check_pair(low, high):
    a, b = deepcopy(low), deepcopy(high)
    lo, hi = a["budget_override"].pop("concepts"), b["budget_override"].pop("concepts")
    if a != b or (lo, hi) != (128, 256):
        raise ValueError("only concept archive capacity may differ")


def lineage(state):
    depths = {}
    def depth(cid, path=()):
        if cid in path:
            raise ValueError("cyclic concept genealogy")
        if cid not in depths:
            c = state["concepts"][cid]
            for parent in c["parents"]:
                if parent not in state["concepts"] or state["concepts"][parent]["born"] > c["born"]:
                    raise ValueError("missing or future parent")
            depths[cid] = max((1+depth(p, path+(cid,)) for p in c["parents"]), default=0)
        return depths[cid]
    for cid in state["concepts"]:
        depth(cid)
    return {"depths": depths, "maximum_recorded_concept_depth": max(depths.values(), default=0),
            "note": "expanded-parent genealogy only; not a complete operand/proof DAG"}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--prepare", action="store_true")
    args = p.parse_args()
    out = args.output.resolve()
    plans = {str(c): read(CONTROL/f"configs/persistent-learning-capacity-{c}.json") for c in (128, 256)}
    check_pair(plans["128"], plans["256"])
    plan = plans["128"]
    if args.prepare:
        out.mkdir(parents=True, exist_ok=False)
        record = {"repository": os.environ.get("GITHUB_REPOSITORY"), "run_id": os.environ.get("GITHUB_RUN_ID"),
                  "plans": plans, "source_seal": source_seal(), "challenge": {}, "infrastructure_passed": False}
        for name in plan["domains"]:
            config = read(ROOT/f"configs/{name}.json")
            config["budget"].update(plan["budget_override"])
            config["seed"] = plan["seed"]
            suite = make_suite(config, plan["heldout_seed"], plan["heldout_contexts"])
            d = Domain(config["domain"])
            oracle = {r["id"]: d.settle(r["left"], r["right"], r["kind"]) for r in suite}
            k0 = evaluate(Theory(config).snapshot(), suite, oracle,
                          proof_node_budget=plan["proof_node_budget"], repeats=plan["evaluation_repeats"])
            if not 0 < k0["summary"]["solved_count"] < k0["summary"]["eligible_heldout_count"]:
                raise ValueError("K0 challenge not mixed; no retuning")
            for label, value in [("challenge", suite), ("oracle", oracle), ("K0", k0)]:
                write(out/f"{name}-{label}.json", value)
            record["challenge"][name] = digest(suite)
        write(out/"verification.json", record)
        return
    record = read(out/"verification.json")
    if record["plans"] != plans or record["source_seal"] != source_seal():
        raise ValueError("frozen inputs or source changed")
    runs = {cap: read(out/cap/"verification.json") for cap in plans}
    for cap, run in runs.items():
        if not run["infrastructure_passed"] or run["baseline_sha"] != plan["baseline_sha"]:
            raise ValueError("normal run failed or wrong baseline")
        if run["heldout_sha256"] != record["challenge"]:
            raise ValueError("challenge changed")
        if read(out/cap/"source-seal.json") != record["source_seal"]:
            raise ValueError("learner used a different source")
    record["domains"] = {}
    for name in plan["domains"]:
        states, answers = {}, {}
        suite, oracle = read(out/f"{name}-challenge.json"), read(out/f"{name}-oracle.json")
        for cap, run in runs.items():
            file = out/cap/run["results"][name+"-learn"]["final_state"]
            states[cap], answers[cap] = read(file), read(file.parent/"heldout.json")
            write(out/f"{name}-{cap}-lineage.json", lineage(states[cap]))
            write(out/f"{name}-{cap}-unbounded.json", evaluate(states[cap], suite, oracle, repeats=plan["evaluation_repeats"]))
        low, high = states["128"], states["256"]
        added = set(high["theorems"])-set(low["theorems"])
        disabled = set().union(*(descendants(high, tid) for tid in added)) if added else set()
        ablated = evaluate(high, suite, oracle, disabled=disabled,
                          proof_node_budget=plan["proof_node_budget"], repeats=plan["evaluation_repeats"])
        write(out/f"{name}-extra-acquisitions-disabled.json", ablated)
        extra_concepts = set(high["concepts"])-set(low["concepts"])
        record["domains"][name] = {
            "capacity_comparison": final_comparison(answers["128"], answers["256"]),
            "additional_acquisition_ablation": final_comparison(ablated, answers["256"]),
            "disabled_theorems": sorted(disabled), "extra_concepts": sorted(extra_concepts),
            "children_of_extra_concepts": sorted(c for c, row in high["concepts"].items() if set(row["parents"]) & extra_concepts),
            "extra_concepts_expanded": sorted(extra_concepts & set(high["expanded"])),
            "extra_concept_theorems": sorted(t for t, row in high["theorems"].items() if set(row.get("concepts", [])) & extra_concepts),
            "new_representation_ids": sorted(set(high["representations"])-set(low["representations"])),
            "normal_results": {cap: run["results"][name+"-learn"] for cap, run in runs.items()}}
    record["infrastructure_passed"] = True
    record["mathematical_source_changed"] = False
    write(out/"verification.json", record)


if __name__ == "__main__":
    main()
