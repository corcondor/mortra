"""Fresh frozen-code experiments, paired ablations and certificate replay.

Scientific criteria may fail without infrastructure failure. Both are explicit.
No expected concept, target theorem, helper quantity or answer is passed to runs.
"""
from pathlib import Path
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from math_os_prototype.theory_domain import Domain, size
from math_os_prototype.representation_progress import digest
from math_os_prototype.theory_formation import Theory
from scripts.run_theory_formation import write, source_seal


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def replay(state):
    """Fresh reproof is an evaluation cost, never a reuse cost or acquisition."""
    d = Domain(state["config"]["domain"])
    checked, failures = 0, []
    for tid, theorem in state["theorems"].items():
        q = state["conjectures"].get(theorem.get("conjecture"))
        if q and "left" in q:
            checked += 1
            if d.settle(q["left"], q["right"], q["kind"])["status"] != "proved":
                failures.append(tid)
    for qid, witness in state["counterexamples"].items():
        q = state["conjectures"][qid]
        checked += 1
        if d.settle(q["left"], q["right"], q["kind"])["status"] != "disproved":
            failures.append(qid)
    for qid, q in state["conjectures"].items():
        if q["status"] == "proved_redundant":
            checked += 1
            if d.settle(q["left"], q["right"], q["kind"])["status"] != "proved":
                failures.append(qid)
    # Replay stored matrices by polynomial identity, without acquiring a basis.
    import sympy as sp
    system = d.linear_system()
    if system:
        from math_os_prototype.finite_generator_problem_dna import pullback
        for rid, r in state["representations"].items():
            checked += 1
            from math_os_prototype.theory_spaces import materialize
            try:
                r = materialize(state, rid)
            except ValueError:
                failures.append(rid)
                continue
            basis = [sp.sympify(x) for x in r["basis"]]
            good = r["scope"] == d.scope and r["system_key"] == d.key
            c = state["concepts"][r["concept"]]
            observable = sum(v*x for v, x in zip(d.evaluate(c["definition"]), system.variables))
            good &= sp.expand(observable-sum(sp.Rational(a)*b for a, b in zip(r["readout"], basis))) == 0
            for g in system.generators:
                rhs = sp.Matrix(r["action_matrices"][g.name])*sp.Matrix(basis)
                good &= all(sp.expand(pullback(b, g, system.variables)-v) == 0 for b, v in zip(basis, rhs))
            if not good: failures.append(rid)
    for tid, p in state["procedures"].items():
        if p["kind"] == "certified_scalar_recurrence":
            checked += 1
            e = Theory(state["config"], theorem_reuse=state["flags"]["theorem_reuse"],
                       representation_reuse=state["flags"]["representation_reuse"],
                       dsl_reuse=state["flags"].get("dsl_reuse", True), state=state)
            try: e.use_procedure(tid)
            except (ValueError, AssertionError): failures.append(tid)
    return {"checks": checked, "failures": failures, "passed": not failures,
            "origin": "replay_regression", "charged_to": "evaluation only"}


def compare(learn, no_theorems, no_representations):
    common = []
    for qid in sorted(set(learn["conjectures"]) & set(no_theorems["conjectures"])):
        left, right = learn["conjectures"][qid], no_theorems["conjectures"][qid]
        if "left" not in left:
            continue
        complete = {"proved", "proved_redundant", "disproved"}
        if left["status"] not in complete or right["status"] not in complete:
            continue
        good = (left["status"] == "disproved") == (right["status"] == "disproved")
        def nodes(q):
            return sum(size(a["reduced_left"])+size(a["reduced_right"]) for a in q["attempts"])
        common.append({"conjecture": qid, "answers_agree": good,
                       "learn_prover_calls": len(left["attempts"]),
                       "without_theorems_prover_calls": len(right["attempts"]),
                       "learn_prover_input_ast_nodes": nodes(left),
                       "without_theorems_prover_input_ast_nodes": nodes(right)})
    before = no_representations["costs"].get("reacquisition", {})
    rkeys = set(learn["representations"]) & set(no_representations["representations"])
    from math_os_prototype.theory_spaces import materialize
    matching_representations = all(materialize(learn, k)["basis"] == materialize(no_representations, k)["basis"] for k in rkeys)
    requests = lambda s: {qid: q for qid, q in s["conjectures"].items()
                          if q["kind"] == "recurrence" and q["attempts"]}
    lreq, nreq = requests(learn), requests(no_representations)
    paired = []
    for qid in sorted(set(lreq) & set(nreq)):
        a, b = lreq[qid], nreq[qid]
        rid = a["representation"]
        if rid not in rkeys:
            continue
        try:
            lr, nr = materialize(learn, rid), materialize(no_representations, rid)
        except ValueError:
            continue
        same = all(lr[k] == nr[k] for k in ["basis", "action_matrices", "readout", "scope", "system_key"])
        paired.append({"query": qid, "same_certified_representation": same,
                       "same_outcome": a["status"] == b["status"]})
    avoided = (len(paired) if paired and all(x["same_certified_representation"] and x["same_outcome"] for x in paired)
               and before.get("closure_calls", 0) >= len(paired)
               and learn["costs"].get("reacquisition", {}).get("closure_calls", 0) == 0 else 0)
    return {"same_completed_conjectures": common,
            "paired_recurrence_requests": paired,
            "certified_closure_reproofs_avoided": avoided,
            "same_query_prover_calls_saved": sum(x["without_theorems_prover_calls"]-x["learn_prover_calls"] for x in common),
            "same_query_prover_input_ast_nodes_saved": sum(x["without_theorems_prover_input_ast_nodes"]-x["learn_prover_input_ast_nodes"] for x in common),
            "representation_reacquisition_calls_without_reuse": before.get("closure_calls", 0),
            "representation_reacquisition_seconds_without_reuse": before.get("seconds", 0),
            "representation_reacquisition_calls_with_reuse": learn["costs"].get("reacquisition", {}).get("closure_calls", 0),
            "common_representations": len(rkeys), "common_representation_bases_agree": matching_representations,
            "comparison_note": "full-run costs include different self-selected frontiers; only shared query costs are paired",
            "prover_input_unit": "AST nodes supplied to exact prover, not machine instructions or wall time"}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path, action="append")
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=False)
    configs = args.config or [ROOT/"configs/theory-ring.json", ROOT/"configs/theory-fold-frames.json"]
    source = source_seal()
    summary = {"repository": os.environ.get("GITHUB_REPOSITORY"),
               "ref": os.environ.get("GITHUB_REF"), "workflow_run_id": os.environ.get("GITHUB_RUN_ID"),
               "sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
               "generated_at": datetime.now(timezone.utc).isoformat(), "experiments": {},
               "commands": [], "errors": [], "infrastructure_passed": False,
               "all_scientific_criteria_met": False}
    write(args.output/"verification.json", summary)
    for config_path in configs:
        name = config_path.stem
        config = read(config_path)
        write(args.output/(name+"-config.json"), config)
        states, results = {}, {}
        try:
            for condition in ["learn", "no-theorems", "no-representations"]:
                previous = None
                for phase in ["first", "continued"]:
                    output = args.output/f"{name}-{condition}-{phase}"
                    command = [sys.executable, "scripts/run_theory_formation.py", "--config", str(config_path),
                               "--output", str(output), "--condition", condition]
                    if phase == "first": command += ["--cycles", str(config["budget"]["cycles"]//2)]
                    else: command += ["--resume", str(previous/"state.json")]
                    summary["commands"].append(command)
                    write(args.output/"verification.json", summary)
                    started = time.perf_counter()
                    with (args.output/(output.name+".log")).open("w", encoding="utf-8") as log:
                        subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                       timeout=config["budget"]["seconds"]+120, check=True)
                    state, result = read(output/"state.json"), read(output/"verification.json")
                    if not result["sources_unchanged"] or not result["execution_completed"]:
                        raise AssertionError("incomplete or modified normal execution")
                    if previous:
                        earlier = read(previous/"state.json")
                        for field in ["theorems", "concepts", "representations", "procedures"]:
                            if not set(earlier[field]) <= set(state[field]):
                                raise AssertionError("certified archive forgot previous entries")
                    result["regression"] = replay(state)
                    result["process_seconds"] = time.perf_counter()-started
                    if not result["regression"]["passed"]:
                        raise AssertionError("a previous capability failed replay")
                    write(output/"evaluation.json", result)
                    previous = output
                states[condition], results[condition] = state, result
            comparison = compare(states["learn"], states["no-theorems"], states["no-representations"])
            if not all(x["answers_agree"] for x in comparison["same_completed_conjectures"]):
                raise AssertionError("ablation changes truth of shared conjecture")
            summary["experiments"][name] = {"conditions": results, "comparison": comparison}
            criteria = dict(results["learn"]["criteria"])
            criteria["future_search_reduced"] = (criteria["future_search_reduced"]
                or comparison["certified_closure_reproofs_avoided"] > 0)
            summary["experiments"][name]["comparative_criteria"] = criteria
            summary["experiments"][name]["criterion_note"] = (
                "Single-run search pruning and paired avoidance of certified closure reproving "
                "are separate effects. The latter is credited only after the matched ablation.")
            summary["experiments"][name]["all_comparative_criteria_met"] = all(criteria.values())
        except Exception as exc:
            summary["errors"].append({"experiment": name, "error": repr(exc)})
        write(args.output/"verification.json", summary)
    summary["sources_unchanged"] = source == source_seal()
    summary["infrastructure_passed"] = not summary["errors"] and summary["sources_unchanged"]
    summary["all_scientific_criteria_met"] = summary["infrastructure_passed"] and all(
        x["all_comparative_criteria_met"] for x in summary["experiments"].values())
    write(args.output/"verification.json", summary)
    print(json.dumps({k: v for k, v in summary.items() if k not in {"experiments", "commands"}}, indent=2))
    return 0 if summary["infrastructure_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
