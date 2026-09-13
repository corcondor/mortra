"""Frozen old/edited acquisition and value-goal synthesis, with fresh cohorts.

All challenges are frozen before either normal learner starts. No acquired
definition, relation, or successful evaluation affects their selection.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.run_theory_formation import write, source_seal
from scripts.verify_theory_tasks import freeze
from math_os_prototype.theory_domain import Domain
from math_os_prototype.representation_progress import digest


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def summarize(rows):
    costs = {k: sum(r["costs"].get(k, 0) for r in rows) for k in set().union(*(r["costs"] for r in rows))}
    return {"solved": sum(r["solved"] for r in rows), "tasks": len(rows),
        "states": sum(r["states_explored"] for r in rows), "costs": costs,
        "seconds": sum(r["seconds"] for r in rows),
        "normal_work": sum(r["normal_work_used"] for r in rows),
        "independent_replay_work": sum(r["independent_replay_work"]["used"] for r in rows),
        "description_bits": rows[0]["library_cost"]["active_bits"]+sum(r["program_bits"] or 0 for r in rows),
        "library_cost": rows[0]["library_cost"]}


def evidence(state):
    dsl = state["dsl"]
    relations = {r["id"]: r for r in dsl["semantic_relations"]}
    edges = []
    for use in dsl["semantic_uses"]:
        for rid in use["proofs"]:
            relation = relations[rid]
            d = next(d for d in dsl["definitions"] if d["id"] == relation["definition"])
            later = [g for g in dsl["definitions"] if g["born"] > use["cycle"] and
                     digest(use["after"]) in g.get("acquisition_sources", [])]
            equation_based = [g for g in dsl["definitions"] if g["born"] > use["cycle"] and
                              any(rid in s["proofs"] for s in g.get("semantic_sources", []))]
            edges.append({"original_definition": d, "relation": relation,
                          "later_use": use, "subsequent_acquisitions": later,
                          "later_equation_based_acquisitions": equation_based})
    return {"definitions": dsl["definitions"], "discoveries": dsl["semantic_discoveries"],
        "relations": dsl["semantic_relations"], "uses": len(dsl["semantic_uses"]),
        "edges": edges, "all_costs": state["costs"], "seconds": state["seconds"],
        "projections": sum(r["kind"] == "projection" for r in relations.values()),
        "abstraction_from_equivalent_view": sum(bool(d.get("semantic_sources")) for d in dsl["definitions"]),
        "fold_structure_nonclaim": "No panel-structure procedure use is demonstrated by frame observations."}


def render(t):
    if "series_parameter" in t:
        return t["series_parameter"]
    op = t["op"]
    if op == "use":
        return "D"+str(t["abstraction"])+"("+", ".join(k+"="+render(v) for k, v in t["arguments"].items())+")"
    if op in {"var", "const", "natural"}:
        return str(t.get("name", t.get("value")))
    if op == "word":
        return "word("+",".join(t["letters"])+")"
    label = next((":"+str(t[k]) for k in ("label", "binding", "procedure") if k in t), "")
    return op+label+"("+", ".join(render(a) for a in t.get("args", []))+")"


def ascii_evidence(trace):
    edge = next(iter(trace["edges"]), None)
    if edge is None:
        return "No complete witnessed edge from acquired definition to edited execution.\n"
    d, r, u = edge["original_definition"], edge["relation"], edge["later_use"]
    return (f"Acquired D{d['index']} [{d['id']}] := {render(d['template'])}\n"
            f"  -> discovered {r['id']}: body = {render(r['right'])}\n"
            f"  -> proof: {r['proof']['kind']}, QQ, {len(r['proof']['residuals'])} states, "
            f"{len(r['proof']['free_variables'])} independent argument/state symbols\n"
            f"  -> rewritten program at cycle {u['cycle']}: {render(u['before'])} => {render(u['after'])}\n"
            f"  -> executed: representation calls = {u['execution_cost'].get('representation_calls', 0)}, "
            f"semantic nodes = {u['execution_cost'].get('semantic_nodes', 0)}; independent replay retained\n"
            f"Later acquisitions using this exact execution: {len(edge['subsequent_acquisitions'])}.\n"
            f"Separately, later abstractions using this equation on corpus forms: {len(edge['later_equation_based_acquisitions'])}.\n"
            "These are different dependency edges; an equivalent implementation is not a new mathematical function.\n")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--plan", type=Path, default=ROOT/"configs/theory-semantic-evaluation.json")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--development-seed", type=int)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    plan = read(args.plan)
    config = read(ROOT/plan["training_config"])
    seeds = [args.development_seed] if args.development_seed is not None else plan["regression_seeds"]+plan["fresh_seeds"]
    # Freeze every target, its class, and its independent witness before learning.
    challenges = {}
    for seed in seeds:
        tasks, witnesses = freeze(config, seed)
        challenges[seed] = tasks
        write(args.output/f"challenge-{seed}.json", tasks)
        write(args.output/f"witnesses-{seed}.json", witnesses)
    write(args.output/"plan.json", plan)
    write(args.output/"config.json", config)
    seal = source_seal()
    harness = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    record = {"sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "workflow_run_id": os.environ.get("GITHUB_RUN_ID"), "repository": os.environ.get("GITHUB_REPOSITORY"),
        "source_seal": seal, "harness_sha256": harness, "commands": [], "process_seconds": {},
        "seeds": seeds, "development": args.development_seed is not None, "errors": [], "passed": False}
    write(args.output/"verification.json", record)
    start = time.perf_counter()
    def run(name, *options):
        command = [sys.executable, str(ROOT/"scripts/run_theory_formation.py"),
                   "--config", str(args.output/"config.json"), "--output", str(args.output/name), *map(str, options)]
        record["commands"].append(command)
        write(args.output/"verification.json", record)
        began = time.perf_counter()
        with (args.output/(name+".log")).open("w", encoding="utf-8") as log:
            result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=600)
        record["process_seconds"][name] = time.perf_counter()-began
        if result.returncode:
            raise RuntimeError(f"{name} failed: {result.returncode}")
        if not read(args.output/name/"verification.json")["sources_unchanged"]:
            raise AssertionError("normal run source changed")
    try:
        for name, options in [("old", []), ("edited", ["--semantic-edits"])]:
            run(name+"-first", *options, "--cycles", config["budget"]["cycles"]//2)
            run(name+"-resumed", *options, "--resume", args.output/(name+"-first")/"state.json")
        old, edited = [read(args.output/(n+"-resumed")/"state.json") for n in ("old", "edited")]
        trace = evidence(edited)
        write(args.output/"semantic-evidence.json", trace)
        (args.output/"ascii.txt").write_text(ascii_evidence(trace), encoding="ascii")
        record["discovery"] = {"relations": len(trace["relations"]), "uses": trace["uses"],
            "projections": trace["projections"], "equivalent_view_acquisitions": trace["abstraction_from_equivalent_view"],
            "complete_edges_to_next_acquisition": sum(bool(e["subsequent_acquisitions"]) for e in trace["edges"]),
            "execution_without_represented_call": sum(u["execution_cost"].get("representation_calls", 0) == 0
                                                       for u in edited["dsl"]["semantic_uses"])}
        record["acquisition"] = {n: {"seconds": s["seconds"], "costs": s["costs"], "definitions": len(s["dsl"]["definitions"]),
            "execution_count": len(s["dsl"]["executions"]), "dependency_depth": max([d["depth"] for d in s["dsl"]["definitions"]] or [0])}
                                for n, s in [("old", old), ("edited", edited)]}
        record["cohorts"] = {}
        domain = Domain(config["domain"])
        training_values = {}
        for name, state in [("old", old), ("edited", edited)]:
            training_values[name] = {tuple(c["values_or_normal_form"]) for c in state["concepts"].values() if c["type"] == "scalar"}
            training_values[name].update(tuple(r["result"]) for r in state["dsl"]["executions"]
                                         if domain.type_of(r["primitive"]) == "scalar")
        for seed, tasks in challenges.items():
            rows = {}
            for name, condition in plan["conditions"].items():
                if len(condition) not in (2, 3) or (len(condition) == 3 and condition[2] != "uncached"):
                    raise ValueError("condition is archive, execution mode, optional uncached syntax")
                archive, mode = condition[:2]
                options = ["--execution-mode", mode, "--queries", args.output/f"challenge-{seed}.json"]
                if len(condition) == 3:
                    options += ["--uncached-syntax"]
                if archive == "initial":
                    options += ["--condition", "initial-only"]
                else:
                    options += ["--knowledge", args.output/(archive+"-resumed")/"state.json"]
                run(f"{seed}-{name}", *options)
                rows[name] = read(args.output/f"{seed}-{name}"/"queries.json")
            b, c = rows["B-edited"], rows["C-edit-disabled"]
            common = [i for i in range(len(tasks)) if all(rs[i]["solved"] for rs in rows.values())]
            union_seen = training_values["old"] | training_values["edited"]
            unseen = [i for i, t in enumerate(tasks) if tuple(t["values"]) not in union_seen]
            cohort = {"role": "development" if args.development_seed is not None else
                      "regression" if seed in plan["regression_seeds"] else "fresh_frozen_generalization",
                "conditions": {n: summarize(rs) for n, rs in rows.items()},
                "same_archive_edit_ablation": all(x["archive_digest"] == y["archive_digest"] for x, y in zip(b, c)),
                "budget_respected": all(r["states_explored"] <= t["budget"]["states"] and r["work"]["used"] <= t["budget"]["work"]
                                        for rs in rows.values() for t, r in zip(tasks, rs)),
                "size_bounds_nonbinding": all(r["costs"]["size_refusals"] == 0 for rs in rows.values() for r in rs),
                "edit_gain": [x["task"] for x, y in zip(b, c) if x["solved"] and not y["solved"]],
                "edit_loss": [y["task"] for x, y in zip(b, c) if y["solved"] and not x["solved"]],
                "common_solved": {n: {"count": len(common), "states": sum(rs[i]["states_explored"] for i in common),
                    "seconds": sum(rs[i]["seconds"] for i in common),
                    "bits_with_library": rs[0]["library_cost"]["active_bits"]+sum(rs[i]["program_bits"] for i in common)} for n, rs in rows.items()},
                "semantically_unseen": {n: {"count": len(unseen), "solved": sum(rs[i]["solved"] for i in unseen)} for n, rs in rows.items()}}
            cohort["interpreter_only_pairs"] = []
            for name, condition in plan["conditions"].items():
                if len(condition) != 3:
                    continue
                for other, base in plan["conditions"].items():
                    if base != condition[:2]:
                        continue
                    checked_fields = ("solved", "program", "states_explored", "work", "semantic_rewrite_trace")
                    cohort["interpreter_only_pairs"].append({"cached": other, "uncached": name,
                        "same_archive": all(a["archive_digest"] == b["archive_digest"] for a, b in zip(rows[other], rows[name])),
                        "same_computation": all(all(a[k] == b[k] for k in checked_fields) for a, b in zip(rows[other], rows[name]))})
            record["cohorts"][str(seed)] = cohort
            write(args.output/"verification.json", record)
        record["sources_unchanged"] = seal == source_seal() and harness == hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        record["passed"] = record["sources_unchanged"] and all(
            c["same_archive_edit_ablation"] and c["budget_respected"] and c["size_bounds_nonbinding"] and
            all(p["same_archive"] and p["same_computation"] for p in c["interpreter_only_pairs"])
            for c in record["cohorts"].values())
    except Exception as exc:
        import traceback
        record["errors"].append(traceback.format_exc())
    record["wall_seconds"] = time.perf_counter()-start
    record["artifact_sha256"] = {str(p.relative_to(args.output)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(args.output.rglob("*.json")) if p.name != "verification.json"}
    write(args.output/"verification.json", record)
    print(json.dumps({k: v for k, v in record.items() if k not in {"source_seal", "commands", "artifact_sha256"}}, indent=2))
    return 0 if record["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
