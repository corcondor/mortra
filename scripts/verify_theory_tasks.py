"""Freeze finite observation synthesis tasks before acquisition; compare A/B/C.

The task contains a complete-model value specification, never its constructing
program. Witnesses stay in the evaluator directory and are not an input to the
normal process. Learning sees no evaluation result.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import random
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from math_os_prototype.theory_domain import Domain, term, size
from scripts.run_theory_formation import write, source_seal
from scripts.verify_theory_dsl import inspect


def freeze(config, seed=917331):
    d = Domain(config["domain"])
    rng = random.Random(seed)
    def tree(depth):
        if not depth:
            return rng.choice(d.seeds())
        op = rng.choice([o for o in d.operations if o in {"pull", "add", "mul", "neg"}])
        children = [tree(depth-1)]
        if op in {"add", "mul"}:
            children.append(tree(depth-1))
        return term(op, *children, **({"label": rng.choice(list(d.actions))} if op == "pull" else {}))
    tasks, witnesses, seen = [], [], set()
    for depth in [0]*4+[2]*4+[4]*8+[6]*8:
        # Rejection only removes duplicate specifications, before any learner runs.
        for _ in range(1000):
            p = tree(depth)
            value = [str(x) for x in d.evaluate(p)]
            key = tuple(value)
            if key not in seen:
                break
        else:
            raise ValueError("insufficient distinct frozen specifications")
        seen.add(key)
        task = {"id": f"external-{len(tasks):02d}", "scope": d.scope, "values": value,
                "budget": {"states": 512, "depth": 64, "program_size": 4096,
                           "expanded_size": 4096, "work": 1_000_000}}
        tasks.append(task)
        witnesses.append({"task": task["id"], "source_depth": depth,
                          "primitive_nodes": size(p), "program": p})
    return tasks, witnesses


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT/"configs/theory-dsl-fold.json")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--challenge-seed", type=int, default=917331)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    config = json.loads(args.config.read_text(encoding="utf-8"))
    tasks, witnesses = freeze(config, args.challenge_seed)
    write(args.output/"challenge.json", tasks)
    write(args.output/"evaluator-witnesses.json", witnesses)
    write(args.output/"config.json", config)
    sources = source_seal()
    record = {"sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "workflow_run_id": os.environ.get("GITHUB_RUN_ID"), "source_seal": sources,
              "challenge_seed": args.challenge_seed, "commands": [], "errors": [], "passed": False,
              "process_seconds": {}}
    record["protocol"] = "value-synthesis-structural-only-ablation-v2"
    record["harness_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    record["all_targets_primitive_expressible_within_bounds"] = all(
        w["primitive_nodes"] <= t["budget"]["program_size"] and
        w["primitive_nodes"] <= t["budget"]["expanded_size"] and
        w["source_depth"] <= t["budget"]["depth"] for w, t in zip(witnesses, tasks))
    record["work_unit_definition"] = (
        "expanded data visits + complete-model AST node evaluations + action steps "
        "+ rational multiply-adds; charged before execution. Not bit complexity. "
        "Scope/type/retrieval overhead is included in wall time, with lookup counts.")
    began = time.perf_counter()
    def run(name, *options):
        command = [sys.executable, str(ROOT/"scripts/run_theory_formation.py"),
                   "--config", str(args.config.resolve()), "--output", str(args.output/name), *map(str, options)]
        record["commands"].append(command)
        write(args.output/"verification.json", record)
        with (args.output/(name+".log")).open("w", encoding="utf-8") as log:
            started = time.perf_counter()
            try:
                result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=900)
            finally:
                record["process_seconds"][name] = time.perf_counter()-started
        if result.returncode:
            raise RuntimeError(f"{name} stopped: return code {result.returncode}")
    try:
        run("A-initial", "--condition", "initial-only", "--queries", args.output/"challenge.json")
        run("learn-first", "--cycles", config["budget"]["cycles"]//2)
        run("learn-resumed", "--resume", args.output/"learn-first/state.json")
        for name, condition in [("B-acquired", "learn"), ("C-disabled", "no-dsl")]:
            run(name, "--condition", condition, "--knowledge", args.output/"learn-resumed/state.json",
                "--queries", args.output/"challenge.json")
        rows = {n: json.loads((args.output/n/"queries.json").read_text(encoding="utf-8"))
                for n in ["A-initial", "B-acquired", "C-disabled"]}
        state = json.loads((args.output/"learn-resumed/state.json").read_text(encoding="utf-8"))
        write(args.output/"acquisition-summary.json", inspect(state))
        record["conditions"] = {n: {"solved": sum(r["solved"] for r in rs),
            "total": len(rs), "states_explored": sum(r["states_explored"] for r in rs),
            "median_states": statistics.median(r["states_explored"] for r in rs),
            "seconds": sum(r["seconds"] for r in rs),
            "process_seconds": record["process_seconds"][n],
            "work_used": sum(r["work"]["used"] for r in rs),
            "library_bits_once": rs[0]["library_cost"]["active_bits"],
            "solved_program_bits": sum(r["program_bits"] or 0 for r in rs),
            "suite_description_bits": rs[0]["library_cost"]["active_bits"]+sum(r["program_bits"] or 0 for r in rs),
            "costs": {k: sum(r["costs"].get(k, 0) for r in rs)
                      for k in set().union(*(r["costs"] for r in rs))}} for n, rs in rows.items()}
        record["previously_unsolved_to_solved"] = [b["task"] for a, b in zip(rows["A-initial"], rows["B-acquired"])
                                                   if not a["solved"] and b["solved"]]
        record["lost_solutions"] = [a["task"] for a, b in zip(rows["A-initial"], rows["B-acquired"])
                                    if a["solved"] and not b["solved"]]
        record["initial_mixed"] = 0 < record["conditions"]["A-initial"]["solved"] < len(tasks)
        record["budget_respected"] = all(r["states_explored"] <= t["budget"]["states"]
                                         and r["work"]["used"] <= t["budget"]["work"]
                                         for rs in rows.values() for r, t in zip(rs, tasks))
        record["size_bounds_nonbinding"] = all(r["costs"]["size_refusals"] == 0 for rs in rows.values() for r in rs)
        a, b = rows["A-initial"], rows["B-acquired"]
        record["common_solved_search_cost"] = [{"task": x["task"], "initial": x["states_explored"],
            "acquired": y["states_explored"]} for x, y in zip(a, b) if x["solved"] and y["solved"]]
        b, c = rows["B-acquired"], rows["C-disabled"]
        record["structural_ablation_only"] = all(
            x["archive_digest"] == y["archive_digest"] and
            [op for op in x["enabled_operations"] if not op.startswith("definition:")] == y["enabled_operations"] and
            not y["definitions_used"] and y["costs"].get("macro_expansions", 0) == 0
            for x, y in zip(b, c))
        record["structural_macro_gain_tasks"] = [x["task"] for x, y in zip(b, c) if x["solved"] and not y["solved"]]
        record["structural_macro_lost_tasks"] = [y["task"] for x, y in zip(b, c) if y["solved"] and not x["solved"]]
        common = [i for i in range(len(tasks)) if all(rs[i]["solved"] for rs in rows.values())]
        record["common_solved_comparison"] = {n: {
            "count": len(common), "states": sum(rs[i]["states_explored"] for i in common),
            "seconds": sum(rs[i]["seconds"] for i in common),
            "description_bits_with_library_once": rs[0]["library_cost"]["active_bits"]+sum(rs[i]["program_bits"] for i in common)
            } for n, rs in rows.items()}
        # Classify semantic overlap afterwards; never select targets with this.
        domain = Domain(config["domain"])
        seen = {tuple(v["values_or_normal_form"]) for v in state["concepts"].values() if v["type"] == "scalar"}
        for row in state["dsl"]["corpus"]:
            if domain.type_of(row["primitive"]) == "scalar":
                seen.add(tuple(str(v) for v in domain.evaluate(row["primitive"])))
        for row in state["dsl"]["executions"]:
            if domain.type_of(row["primitive"]) == "scalar":
                seen.add(tuple(str(v) for v in row["result"]))
        record["semantic_overlap"] = {t["id"]: tuple(t["values"]) in seen for t in tasks}
        record["unseen_semantic_tasks"] = {n: {"count": sum(not record["semantic_overlap"][t["id"]] for t in tasks),
            "solved": sum(r["solved"] and not record["semantic_overlap"][r["task"]] for r in rs)} for n, rs in rows.items()}
        record["acquisition_costs"] = state["costs"]
        record["acquisition_seconds"] = state["seconds"]
        record["sources_unchanged"] = sources == source_seal()
        record["harness_unchanged"] = record["harness_sha256"] == hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        record["passed"] = (record["sources_unchanged"] and record["structural_ablation_only"] and record["budget_respected"]
            and record["all_targets_primitive_expressible_within_bounds"] and record["size_bounds_nonbinding"]
            and record["initial_mixed"] and record["harness_unchanged"])
    except Exception as exc:
        record["errors"].append(f"{type(exc).__name__}: {exc}")
    record["wall_seconds"] = time.perf_counter()-began
    record["artifact_sha256"] = {str(p.relative_to(args.output)): hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in sorted(args.output.rglob("*.json")) if p.name != "verification.json"}
    write(args.output/"verification.json", record)
    print(json.dumps({k: v for k, v in record.items() if k not in {"source_seal", "commands", "artifact_sha256"}}, indent=2))
    return 0 if record["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
