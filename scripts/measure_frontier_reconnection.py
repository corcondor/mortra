"""Paired frozen-code experiment for one active-frontier connection change.

No mathematical solver or discovery procedure is implemented here. Each arm
runs the existing normal entry. The same prior question generator is reused;
the challenge bound limits prover input, not overall runtime or rule matching.
"""
from pathlib import Path
from copy import deepcopy
from datetime import datetime, timezone
import argparse
import json
import os
import platform
import subprocess
import sys
import time
import traceback

CONTROL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CONTROL))
from scripts.measure_persistent_learning import (
    read, make_suite, evaluate, final_comparison, descendants, metrics,
    Theory, Domain, size, digest, write)


def trace_dormant(before, after):
    dormant = set(before["concepts"])-set(before["expanded"])
    d = Domain(before["config"]["domain"])
    peers = [before["concepts"][c]["definition"] for c in before["active_concepts"]]
    expansion = {e["concept"]: e["cycle"] for e in after["events"] if e["kind"] == "concept_expanded"}
    insertion = {}
    for event in after["events"]:
        if event["kind"] == "active_frontier_refreshed":
            for cid in set(event["active"])-set(event["previous"]):
                insertion.setdefault(cid, event["cycle"])
    invented_cycles = {row["cycle"] for row in after["decisions"] if row["chosen"]["kind"] == "invent"}
    rows = []
    for cid in sorted(dormant):
        c = before["concepts"][cid]
        syntax = list(d.compose(c["definition"], peers))
        small = [t for t in syntax if size(t) <= before["config"]["budget"]["term_size"]]
        eligible = [t for t in small if digest(t) not in set(before["seen"])]
        ec = expansion.get(cid)
        children = [k for k, x in after["concepts"].items() if cid in x["parents"] and ec is not None and x["born"] >= ec]
        later = [k for k, t in after["theorems"].items() if k not in before["theorems"]
                 and cid in t.get("concepts", []) and ec is not None and t["born"] >= ec]
        rows.append({"concept": cid, "acquisition_cycle": c["born"], "definition": c["definition"],
            "stored_before": True, "size": c["size"], "type": c["type"],
            "active_before": cid in before["active_concepts"], "expanded_before": False,
            "eligible_syntax_at_old_stop": len(eligible),
            "old_blocking_stage": "size_budget" if not small else "seen_filter" if not eligible else "frontier_insertion",
            "present_after": cid in after["concepts"], "frontier_insertion_cycle": insertion.get(cid),
            "expansion_cycle": ec, "scheduled_by_existing_policy": ec in invented_cycles if ec is not None else False,
            "new_child_concepts": children, "new_directly_dependent_theorems": later,
            "trace_note": "stored parent/dependency links only; no inferred unrecorded operand dependencies"})
    return rows


def summarize_pair(before, after, before_eval, after_eval):
    trace = trace_dormant(before, after)
    expanded = {r["concept"] for r in trace if r["expansion_cycle"] is not None}
    children = {c for r in trace for c in r["new_child_concepts"]}
    theorems = {t for r in trace for t in r["new_directly_dependent_theorems"]}
    seen = set(theorems)
    while True:
        more = {t for t, deps in after["proof_dependencies"].items() if set(deps) & seen}
        if more <= seen:
            break
        seen |= more
    relevant = {t for row in after_eval["rows"] if row["status"] in {"proved", "disproved"}
                for t in row["dependencies"] if t in seen}
    return {"dormant_trace": trace, "newly_expanded_acquired_concepts": sorted(expanded),
        "concept_to_later_concept": sorted(children), "concept_to_theorem": sorted(theorems),
        "related_later_theorems": sorted(seen), "heldout_used_related_theorems": sorted(relevant),
        "new_representation_ids": sorted(set(after["representations"])-set(before["representations"])),
        "before_metrics": metrics(before), "after_metrics": metrics(after),
        "paired_heldout": final_comparison(before_eval, after_eval),
        "policy_unchanged": all(d["policy"] == "least_visited_then_cost" for s in [before, after] for d in s["decisions"]),
        "scope_note": "same fixed signatures, source-level connection only; archive capacity unchanged"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--expected-after", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    base = read(CONTROL/"configs/persistent-learning.json")
    base.update(domains=["theory-ring", "theory-fold-frames"], conditions=["learn"], proof_node_budget=32)
    shas = {label: subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=path, text=True).strip()
            for label, path in [("before", args.before), ("after", args.after)]}
    if shas["before"] != base["baseline_sha"] or shas["after"] != args.expected_after:
        raise ValueError("paired checkout SHA mismatch")
    result = {"origin": "paired_frontier_reconnection", "repository": os.environ.get("GITHUB_REPOSITORY"),
        "workflow_run_id": os.environ.get("GITHUB_RUN_ID"), "shas": shas,
        "command": sys.argv, "python": sys.version, "platform": platform.platform(),
        "generated_at": datetime.now(timezone.utc).isoformat(), "plan": base,
        "infrastructure_passed": False,
        "challenge": {}, "arms": {}, "domains": {}, "errors": []}
    write(args.output/"verification.json", result)
    suites, oracles = {}, {}
    # Freeze both arm plans and every challenge before either learner runs.
    for domain in base["domains"]:
        config = read(args.before/"configs"/(domain+".json"))
        if config != read(args.after/"configs"/(domain+".json")):
            raise ValueError("paired domain or resource input changed")
        config["budget"].update(base["budget_override"])
        config["seed"] = base["seed"]
        suites[domain] = make_suite(config, base["heldout_seed"], base["heldout_contexts"])
        d = Domain(config["domain"])
        oracles[domain] = {t["id"]: d.settle(t["left"], t["right"], t["kind"]) for t in suites[domain]}
        initial = Theory(config).snapshot()
        k0 = evaluate(initial, suites[domain], oracles[domain], repeats=base["evaluation_repeats"], proof_node_budget=32)
        if not (0 < k0["summary"]["solved_count"] < k0["summary"]["eligible_heldout_count"]):
            raise ValueError("challenge is not mixed at K0; halt, do not retune the live suite")
        write(args.output/(domain+"-challenge.json"), suites[domain])
        write(args.output/(domain+"-oracle.json"), oracles[domain])
        write(args.output/(domain+"-K0.json"), k0)
        result["challenge"][domain] = {"sha256": digest(suites[domain]), "K0": k0["summary"],
            "definition": "per-call exact-prover input <=32 AST nodes; matching and wall time separately reported",
            "not_claimed": "new unknown mathematics; this is success under a fixed proof-input resource bound"}
    for label in shas:
        plan = deepcopy(base)
        plan["baseline_sha"] = shas[label]
        plan["baseline_actions_run"] = base["baseline_actions_run"] if label == "before" else os.environ.get("GITHUB_RUN_ID", "current-local-run")
        write(args.output/(label+"-plan.json"), plan)
    write(args.output/"verification.json", result)
    for label, path in [("before", args.before), ("after", args.after)]:
        command = [sys.executable, str(CONTROL/"scripts/measure_persistent_learning.py"),
                   "--plan", str(args.output/(label+"-plan.json")), "--output", str(args.output/label)]
        env = dict(os.environ, MORTRA_BASELINE_ROOT=str(path.resolve()))
        started = time.perf_counter()
        with (args.output/(label+".log")).open("w", encoding="utf-8") as log:
            process = subprocess.run(command, env=env, cwd=path, stdout=log, stderr=subprocess.STDOUT)
        result["arms"][label] = {"command": command, "wall_seconds": time.perf_counter()-started, "returncode": process.returncode}
        write(args.output/"verification.json", result)
        if process.returncode:
            raise RuntimeError(f"{label} stopped; preserve this run")
    reports = {label: read(args.output/label/"verification.json") for label in shas}
    for label, report in reports.items():
        if not report["infrastructure_passed"] or report["heldout_sha256"] != {k: digest(v) for k, v in suites.items()}:
            raise AssertionError(f"{label} changed frozen questions or failed")
    for domain in base["domains"]:
        states, evaluations = {}, {}
        for label, report in reports.items():
            path = args.output/label/report["results"][domain+"-learn"]["final_state"]
            states[label], evaluations[label] = read(path), read(path.parent/"heldout.json")
            unlimited = evaluate(states[label], suites[domain], oracles[domain], repeats=base["evaluation_repeats"])
            write(args.output/(domain+"-"+label+"-unlimited.json"), unlimited)
        pair = summarize_pair(states["before"], states["after"], evaluations["before"], evaluations["after"])
        write(args.output/(domain+"-concept-trace.json"), pair.pop("dormant_trace"))
        relevant = pair["heldout_used_related_theorems"]
        if relevant:
            state = states["after"]
            root = min(relevant, key=lambda tid: (state["theorems"][tid]["born"], tid))
            ablation = evaluate(state, suites[domain], oracles[domain], disabled=descendants(state, root),
                                repeats=base["evaluation_repeats"], proof_node_budget=32)
            write(args.output/(domain+"-related-ablation.json"), ablation)
            pair["related_acquisition_ablation"] = {"root": root, "disabled": sorted(descendants(state, root)),
                                                    **final_comparison(ablation, evaluations["after"])}
        else:
            pair["related_acquisition_ablation"] = {"status": "no_restored-concept-descendant_used_on_challenge"}
        result["domains"][domain] = pair
        write(args.output/"verification.json", result)
    result["infrastructure_passed"] = True
    result["new_solver_or_strategy_added"] = False
    write(args.output/"verification.json", result)
    print(json.dumps({"shas": shas, "run": result["workflow_run_id"], "infrastructure_passed": True}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        if "--output" in sys.argv:
            path = Path(sys.argv[sys.argv.index("--output")+1])/"verification.json"
            if path.is_file():
                failed = read(path)
                failed["infrastructure_passed"] = False
                failed["errors"].append(traceback.format_exc())
                write(path, failed)
        raise
