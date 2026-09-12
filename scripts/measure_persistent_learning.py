"""Evaluation only. Execute an immutable validated checkout via its normal entry.

No solver, candidate generator, rewrite strategy, or procedure is added to the
learning process. Held-out tasks go through existing Theory.settle on discarded
copies. This interface does not route theory spaces to new task observables.
"""
from pathlib import Path
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import argparse
import csv
import hashlib
import json
import os
import random
import statistics
import subprocess
import sys
import time
import traceback
from unittest.mock import patch

CONTROL = Path(__file__).resolve().parents[1]
# Set before imports: every mathematical function below comes from the baseline.
ROOT = Path(os.environ.get("MORTRA_BASELINE_ROOT", CONTROL)).resolve()
sys.path.insert(0, str(ROOT))
from math_os_prototype.theory_formation import Theory
from math_os_prototype import theory_formation as theory_module
from math_os_prototype.theory_domain import Domain, term, size
from math_os_prototype.representation_progress import digest
from scripts.run_theory_formation import source_seal, write
from scripts.verify_theory_formation import replay


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def median(values):
    return statistics.median(values) if values else None


def seal(state):
    state.pop("sha256", None)
    state["sha256"] = digest(state)
    return state


def make_suite(config, seed, contexts):
    """External regression/transfer questions; never a training generator.

    Predeclared algebraic families are evaluators' knowledge, not discoveries.
    Contexts exceed the learner's term-size bound. Truths and falsehoods are not
    filtered using success. No answers or contexts are supplied to normal runs.
    """
    d, rng = Domain(config["domain"]), random.Random(seed)
    zero, one = term("const", value="0"), term("const", value="1")
    variables = [term("var", name=n) for n in d.names]
    rows = []
    for i in range(contexts):
        x = deepcopy(rng.choice(variables))
        while size(x) <= 12:
            op = rng.choice([v for v in d.operations if v in {"neg", "add", "mul", "diff", "pull"}])
            if op in {"add", "mul"}:
                x = term(op, x, deepcopy(rng.choice(variables)))
            elif op == "pull":
                x = term(op, x, label=rng.choice(list(d.actions)))
            else:
                x = term(op, x)
        y, z = rng.choice(variables), rng.choice(variables)
        pairs = [
            ("zero", term("add", x, zero), x),
            ("involution", term("neg", term("neg", x)), x),
            ("commutativity", term("add", x, y), term("add", y, x)),
            ("associativity", term("add", term("add", x, y), z), term("add", x, term("add", y, z))),
            ("perturbed", term("add", x, one), x),
            ("independent", x, term("add", y, z)),
        ]
        if d.kind == "differential_ring":
            pairs += [
                ("derivation-add", term("diff", term("add", x, y)), term("add", term("diff", x), term("diff", y))),
                ("product-rule", term("diff", term("mul", x, y)), term("add", term("mul", term("diff", x), y), term("mul", x, term("diff", y)))),
            ]
        else:
            g, h = rng.choice(list(d.actions)), rng.choice(list(d.actions))
            pull = lambda t, label: term("pull", t, label=label)
            pairs += [
                ("action-add", pull(term("add", x, y), g), term("add", pull(x, g), pull(y, g))),
                ("action-order", pull(pull(x, g), h), pull(pull(x, h), g)),
            ]
        for family, left, right in pairs:
            if size(left) <= config["budget"]["term_size"] and size(right) <= config["budget"]["term_size"]:
                raise AssertionError("held-out syntax fits the training bound")
            rows.append({"id": f"H-{i:02}-{family}", "family": family,
                         "left": left, "right": right, "kind": "equality",
                         "origin": "external_evaluation", "trained_on": False})
    return rows


def evaluation_copy(state, disabled=()):
    """Discard training history, retain the same executable archive and scope.

    Copying and initialization are charged separately from answer runtime. All
    changes made by settle are thrown away before the next held-out task.
    """
    e = Theory(state["config"], **state["flags"])
    for key in ["concepts", "theorems", "representations", "procedures",
                "proof_dependencies", "representation_dependencies", "active_concepts"]:
        e.state[key] = deepcopy(state[key])
    e.state["cycle"] = state["cycle"]
    e.state["rewrite_rules"] = [deepcopy(r) for r in state["rewrite_rules"] if r["theorem"] not in disabled]
    return e


class ProofInputBudgetExceeded(RuntimeError):
    def __init__(self, requested, limit):
        self.requested, self.limit = requested, limit
        super().__init__(f"prover input requires {requested} AST nodes; limit {limit}")


def evaluate(state, suite, oracle, *, disabled=(), repeats=1, proof_node_budget=None):
    original = digest(state)
    rows = []
    for task in suite:
        samples = []
        for _ in range(repeats):
            start = time.perf_counter()
            e = evaluation_copy(state, disabled)
            if proof_node_budget is not None:
                if type(proof_node_budget) is not int or proof_node_budget < 1:
                    raise ValueError("positive prover input budget required")
                original_settle = e.domain.settle
                def limited_settle(left, right, kind="equality"):
                    requested = size(left)+size(right)
                    if requested > proof_node_budget:
                        raise ProofInputBudgetExceeded(requested, proof_node_budget)
                    return original_settle(left, right, kind)
                e.domain.settle = limited_settle
            e.conjecture(task["left"], task["right"], kind=task["kind"])
            qid = next(iter(e.state["conjectures"]), None)
            if qid is not None:
                e.state["conjectures"][qid]["provenance"] = "external_evaluation"
            setup = time.perf_counter()-start
            matching_seconds = 0.0
            original_rewrite = theory_module.rewrite
            def measured_rewrite(*args, **kwargs):
                nonlocal matching_seconds
                began = time.perf_counter()
                try:
                    return original_rewrite(*args, **kwargs)
                finally:
                    matching_seconds += time.perf_counter()-began
            start = time.perf_counter()
            if qid is not None:
                try:
                    # Instrument only this discarded evaluation, not the learner.
                    with patch.object(theory_module, "rewrite", measured_rewrite):
                        e.settle(qid)
                except ProofInputBudgetExceeded as exc:
                    e.state["conjectures"][qid].update(status="budget_exceeded", certificate={
                        "reason": str(exc), "requested_prover_input_nodes": exc.requested,
                        "proof_node_budget": exc.limit, "proof_was_executed": False})
                q = e.state["conjectures"][qid]
            else:
                # The baseline deliberately does not pose syntactically x=x.
                # Do not add a fallback solver or count this as unsolved math.
                assert task["left"] == task["right"]
                q = {"status": "not_queued_reflexive", "attempts": [],
                     "certificate": {"reason": "existing conjecture method omits identical expressions"}}
            elapsed = time.perf_counter()-start
            status = "proved" if q["status"] == "proved_redundant" else q["status"]
            if status in {"proved", "disproved"} and status != oracle[task["id"]]["status"]:
                raise AssertionError("held-out answer disagrees with independent exact check")
            deps = q["certificate"].get("dependencies", []) if q["status"] == "proved_redundant" else sorted({t for a in q["attempts"] for t in a["dependencies"]})
            if not set(deps) <= set(state["theorems"]):
                raise AssertionError("evaluation used knowledge not in snapshot")
            costs = e.state["costs"]
            samples.append({"status": status, "runtime": elapsed, "copy_seconds": setup,
                            "prover_calls": costs.get("certification", {}).get("proof_calls", 0),
                            "prover_input_ast_nodes": costs.get("certification", {}).get("semantic_nodes", 0),
                            "search_nodes": costs.get("rewrite", {}).get("rule_matches_checked", 0),
                            "matching_seconds": matching_seconds,
                            "certification_seconds": costs.get("certification", {}).get("seconds", 0),
                            "dependencies": deps, "certificate": q["certificate"],
                            "dependency_note": "not recorded before the blocked prover call" if status == "budget_exceeded" else "recorded by existing solver"})
        base = samples[0]
        if any((s["status"], s["dependencies"], s["prover_calls"], s["search_nodes"]) !=
               (base["status"], base["dependencies"], base["prover_calls"], base["search_nodes"]) for s in samples):
            raise AssertionError("repeat changed deterministic result")
        rows.append({"task": task["id"], "family": task["family"], **base,
                     "runtime": median([s["runtime"] for s in samples]), "samples": samples,
                     "exact_training_query_seen": any(q.get("left") == task["left"] and q.get("right") == task["right"] for q in state["conjectures"].values()),
                     "reuse_scope": "same-domain new expression, not a new domain or theory"})
    assert original == digest(state), "held-out evaluation mutated the learning state"
    eligible = [r for r in rows if r["status"] != "not_queued_reflexive"]
    return {"rows": rows, "summary": {
        "solved_count": sum(r["status"] in {"proved", "disproved"} for r in rows),
        "proved_count": sum(r["status"] == "proved" for r in rows),
        "refuted_count": sum(r["status"] == "disproved" for r in rows),
        "median_search_nodes": median([r["search_nodes"] for r in eligible]),
        "median_proof_cost": median([r["prover_input_ast_nodes"] for r in eligible]),
        "median_prover_calls": median([r["prover_calls"] for r in eligible]),
        "median_runtime": median([r["runtime"] for r in eligible]),
        "total_prover_calls": sum(r["prover_calls"] for r in rows),
        "total_prover_input_ast_nodes": sum(r["prover_input_ast_nodes"] for r in rows),
        "total_rule_inspections": sum(r["search_nodes"] for r in rows),
        "median_matching_seconds": median([median([s["matching_seconds"] for s in r["samples"]]) for r in eligible]),
        "median_certification_seconds": median([median([s["certification_seconds"] for s in r["samples"]]) for r in eligible]),
        "cross_task_reuse_count": sum(bool(r["dependencies"]) for r in rows),
        "procedure_reuse_count": sum(len(r["dependencies"]) for r in rows),
        "representation_reuse_count": 0,
        "search_node_unit": "rule candidates inspected by existing rewrite; NOT prover-tree nodes",
        "proof_cost_unit": "AST nodes sent to existing exact prover; NOT CPU instructions",
        "representation_note": "Theory.settle has no stored-space routing; no new route supplied by harness",
        "budget_exceeded_count": sum(r["status"] == "budget_exceeded" for r in rows),
        "proof_node_budget": proof_node_budget,
        "budget_note": "per-call prover-input AST bound, enforced before exact proof; not a total runtime bound",
        "heldout_count": len(rows), "eligible_heldout_count": len(eligible),
        "not_queued_reflexive_count": len(rows)-len(eligible),
        "median_population": "fixed questions actually queued; identical-expression omissions reported separately",
        "snapshot_unchanged": True}}


def metrics(state):
    depths = {}
    def depth(tid, path=()):
        if tid in path: raise AssertionError("dependency cycle")
        if tid not in depths:
            depths[tid] = 1+max([depth(p, path+(tid,)) for p in state["proof_dependencies"].get(tid, [])] or [0])
        return depths[tid]
    for tid in state["theorems"]: depth(tid)
    def operators(t):
        return [t["op"]]+[v for c in t["args"] for v in operators(c)]
    concepts = state["concepts"]
    acquired = [c for c in concepts.values() if not c["seed"]]
    recent = [q for q in state["conjectures"].values() if "left" in q and q["born"] > state["cycle"]-250]
    reps = state["representations"]
    # Exact row-space classification is measurement only, never returned to search.
    import sympy as sp
    families = Counter()
    for r in reps.values():
        variables = sorted(set().union(*(sp.sympify(b).free_symbols for b in r["basis"])), key=str)
        matrix = sp.Matrix([[sp.expand(sp.sympify(b)).coeff(v) for v in variables] for b in r["basis"]])
        rows = matrix.rref()[0]
        families[digest([r["scope"], list(map(str, variables)), str(rows)])] += 1
    seen = len(set(state["seen"]))
    return {
        "cycle": state["cycle"], "knowledge_size": {k: len(state[k]) for k in ["concepts", "theorems", "representations", "procedures", "counterexamples"]},
        "new_semantic_representations": len(families),
        "semantic_concepts_acquired": len(acquired), "representation_records": len(reps),
        "maximum_dependency_depth": max(depths.values(), default=0),
        "mean_dependency_depth": statistics.mean(depths.values()) if depths else 0,
        "proof_dependency_depths": depths,
        "cross_task_reuse_self_generated": len(state["downstream"]),
        "procedure_kinds": dict(Counter(p["kind"] for p in state["procedures"].values())),
        "representation_reuse_count": sum(r["reuse_count"] for r in reps.values()),
        "procedure_reuse_count": sum(p["reuse_count"] for p in state["procedures"].values()),
        "archive_concepts": len(concepts), "active_concepts": len(state["active_concepts"]),
        "archived_rules": len(state["rewrite_rules"]),
        "active_rules": len(state["rewrite_rules"]) if state["flags"]["theorem_reuse"] else 0,
        "recorded_active_rule_ids": len(state["active_rules"]),
        "active_rule_note": "effective matching reads rules(), not the potentially stale active_rules bookkeeping field",
        "archived_unexpanded_concepts": sum(cid not in state["expanded"] for cid in concepts),
        "inactive_unexpanded_concepts": sum(cid not in state["expanded"] and cid not in state["active_concepts"] for cid in concepts),
        "generator_distribution": dict(Counter(v for c in acquired for v in operators(c["definition"]))),
        "recent_query_constructor_distribution": dict(Counter(q["left"]["op"] for q in recent)),
        "representation_family_distribution": dict(families),
        "frontier_diversity": dict(Counter((r["term"]["op"]) for r in state["pending_terms"])),
        "unique_terms_seen": seen,
        "non_new_semantic_fraction_proxy": 1-len(concepts)/seen if seen else None,
        "duplicate_rate_note": "non-new fraction includes unadmitted terms at concept cap; not a pure duplicate rate",
        "near_duplicate_rate": None, "near_duplicate_note": "no certified approximate equivalence metric in this baseline",
        "acquisition_costs": state["costs"], "training_seconds": state["seconds"],
        "stop_reason": state.get("stop_reason", "initialization"),
        "provenance": {k: len(v) for k, v in state["task_origins"].items()},
    }


def causal_replays(state, limit):
    """Re-run existing later recurrence requests with/without the stored closure.

    These are replay/regression requests, not external held-out successes.
    No new readout matching, recurrence evaluator, or action planner is added.
    """
    evidence = []
    requests = [x for x in state["downstream"] if x["kind"] == "closure_used_for_new_recurrence"]
    for request in requests[:limit]:
        rid, tid = request["representation"], request["new_theorem"]
        label = state["theorems"][tid]["certificate"]["label"]
        pair = {}
        for enabled in [True, False]:
            e = evaluation_copy(state)
            e.flags["theorem_reuse"] = True
            e.flags["representation_reuse"] = enabled
            start = time.perf_counter()
            e.derive(rid, label)
            pair["stored" if enabled else "disabled"] = {"seconds": time.perf_counter()-start,
                "costs": e.state["costs"], "certificate": e.state["theorems"][tid]["certificate"]}
        if pair["stored"]["certificate"] != pair["disabled"]["certificate"]:
            raise AssertionError("paired closure ablation changed result")
        evidence.append({"representation": rid, "later_theorem": tid,
                         "acquired_cycle": state["representations"][rid]["born"],
                         "used_cycle": request["cycle"], "origin": "replay_regression", **pair})
    return evidence


def descendants(state, root):
    disabled = {root}
    while True:
        more = {t for t, deps in state["proof_dependencies"].items() if set(deps) & disabled}
        if more <= disabled: return disabled
        disabled |= more


def final_comparison(first, last):
    a, b = {r["task"]: r for r in first["rows"]}, {r["task"]: r for r in last["rows"]}
    solved = lambda r: r["status"] in {"proved", "disproved"}
    return {
        "newly_solved_heldout_tasks": [k for k in a if not solved(a[k]) and solved(b[k])],
        "lost_heldout_tasks": [k for k in a if solved(a[k]) and not solved(b[k])],
        "tasks_with_fewer_prover_calls": [k for k in a if solved(a[k]) and solved(b[k]) and b[k]["prover_calls"] < a[k]["prover_calls"]],
        "tasks_with_lower_prover_input": [k for k in a if solved(a[k]) and solved(b[k]) and b[k]["prover_input_ast_nodes"] < a[k]["prover_input_ast_nodes"]],
        "tasks_with_more_rule_search": [k for k in a if b[k]["search_nodes"] > a[k]["search_nodes"]],
        "initial": first["summary"], "final": last["summary"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--development-smoke", action="store_true")
    args = parser.parse_args()
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    plan = read(args.plan)
    if args.development_smoke:
        plan.update(snapshots=[0, 10], domains=["theory-ring"], conditions=["learn"], evaluation_repeats=1, heldout_contexts=1)
        plan["budget_override"]["cycles"] = 10
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if sha != plan["baseline_sha"] and not args.development_smoke:
        raise ValueError(f"baseline SHA mismatch: {sha}")
    subprocess.run(["git", "diff", "--exit-code", "--", "math_os_prototype", "scripts/run_theory_formation.py", "scripts/verify_theory_formation.py"], cwd=ROOT, check=True)
    source = source_seal()
    report = {"baseline_sha": sha, "baseline_verification_run": plan["baseline_actions_run"],
        "control_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=CONTROL, text=True).strip(),
        "repository": os.environ.get("GITHUB_REPOSITORY", "corcondor/mortra"),
        "ref": os.environ.get("GITHUB_REF"), "workflow_run_id": os.environ.get("GITHUB_RUN_ID"),
        "generated_at": datetime.now(timezone.utc).isoformat(), "python": sys.version,
        "development_only": args.development_smoke, "commands": [], "results": {}, "errors": []}
    write(args.output/"plan.json", plan)
    write(args.output/"source-seal.json", source)
    write(args.output/"verification.json", report)
    with (args.output/"environment.txt").open("w", encoding="utf-8") as stream:
        subprocess.run([sys.executable, "-m", "pip", "freeze"], stdout=stream, check=True)
    # Freeze ALL configs and questions before ANY learning process starts.
    suites, configs, oracles = {}, {}, {}
    for name in plan["domains"]:
        config = read(ROOT/"configs"/(name+".json"))
        config["budget"].update(plan["budget_override"])
        config["seed"] = plan["seed"]
        configs[name] = config
        suites[name] = make_suite(config, plan["heldout_seed"], plan["heldout_contexts"])
        write(args.output/(name+"-config.json"), config)
        write(args.output/(name+"-heldout.json"), suites[name])
        d = Domain(config["domain"])
        start = time.perf_counter()
        oracles[name] = {r["id"]: d.settle(r["left"], r["right"], r["kind"]) for r in suites[name]}
        write(args.output/(name+"-oracle.json"), {"origin": "evaluation only; not read by learner",
              "seconds": time.perf_counter()-start, "answers": oracles[name]})
    report["heldout_sha256"] = {n: digest(v) for n, v in suites.items()}
    write(args.output/"verification.json", report)
    table = []
    for name, config in configs.items():
        for condition in plan["conditions"]:
            key = name+"-"+condition
            directory = args.output/key
            directory.mkdir()
            previous, initial_eval, final_eval = None, None, None
            snapshots = []
            try:
                for checkpoint in plan["snapshots"]:
                    start = time.perf_counter()
                    output = directory/f"K{checkpoint:05}"
                    if checkpoint == 0:
                        output.mkdir()
                        state = Theory(config, theorem_reuse=condition != "no-theorems", representation_reuse=condition != "no-representations").snapshot()
                        write(output/"state.json", state)
                    else:
                        prior_cycle = read(previous/"state.json")["cycle"]
                        command = [sys.executable, str(ROOT/"scripts/run_theory_formation.py"),
                            "--config", str(args.output/(name+"-config.json")), "--output", str(output),
                            "--condition", condition, "--cycles", str(checkpoint-prior_cycle)]
                        if prior_cycle: command += ["--resume", str(previous/"state.json")]
                        report["commands"].append(command)
                        write(args.output/"verification.json", report)
                        with (directory/f"K{checkpoint:05}.log").open("w", encoding="utf-8") as log:
                            subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                           timeout=config["budget"]["seconds"]+180, check=True)
                        state = read(output/"state.json")
                        check = read(output/"verification.json")
                        if not check["execution_completed"] or not check["sources_unchanged"]:
                            raise AssertionError("normal run failed or modified code")
                        before = read(previous/"state.json")
                        for field in ["theorems", "concepts", "representations", "procedures"]:
                            if not set(before[field]) <= set(state[field]):
                                raise AssertionError("archive lost knowledge on resume")
                    row = metrics(state)
                    row.update(domain=name, condition=condition, checkpoint_requested=checkpoint,
                               process_and_snapshot_seconds=time.perf_counter()-start)
                    stopped = state["cycle"] < checkpoint
                    if condition == "learn" or checkpoint == 0 or checkpoint == plan["snapshots"][-1] or stopped:
                        final_eval = evaluate(state, suites[name], oracles[name], repeats=plan["evaluation_repeats"],
                                              proof_node_budget=plan.get("proof_node_budget"))
                        if initial_eval is None: initial_eval = final_eval
                        write(output/"heldout.json", final_eval)
                        row["heldout"] = final_eval["summary"]
                        row["newly_solved_heldout_tasks"] = final_comparison(initial_eval, final_eval)["newly_solved_heldout_tasks"]
                    write(output/"measurements.json", row)
                    snapshots.append(row)
                    table.append({"domain": name, "condition": condition, "cycle": row["cycle"],
                        **{k: row["knowledge_size"][k] for k in row["knowledge_size"]},
                        "new_semantic_representations": row["new_semantic_representations"],
                        "dependency_depth": row["maximum_dependency_depth"],
                        "self_generated_reuse": row["cross_task_reuse_self_generated"],
                        "heldout_solved_count": row.get("heldout", {}).get("solved_count"),
                        "heldout_median_search_cost": row.get("heldout", {}).get("median_search_nodes"),
                        "heldout_median_proof_cost": row.get("heldout", {}).get("median_proof_cost"),
                        "heldout_median_runtime": row.get("heldout", {}).get("median_runtime"),
                        "cross_task_reuse": row.get("heldout", {}).get("cross_task_reuse_count")})
                    print(json.dumps(table[-1]), flush=True)
                    write(args.output/"trajectory.json", table)
                    previous = output
                    if stopped: break
                final_state = state
                regression = replay(final_state)
                if not regression["passed"]: raise AssertionError("knowledge replay failed")
                write(directory/"regression.json", regression)
                comparison = final_comparison(initial_eval, final_eval)
                ablations = {}
                if condition == "learn":
                    all_rules = {r["theorem"] for r in state["rewrite_rules"]}
                    off = evaluate(state, suites[name], oracles[name], disabled=all_rules, repeats=plan["evaluation_repeats"],
                                   proof_node_budget=plan.get("proof_node_budget"))
                    write(directory/"no-active-rules-heldout.json", off)
                    ablations["all_rules_disabled"] = final_comparison(off, final_eval)
                    used = {t for r in final_eval["rows"] for t in r["dependencies"]}
                    if used:
                        root = min(used, key=lambda t: (state["theorems"][t]["born"], t))
                        for label, disabled in [("single", {root}), ("with-descendants", descendants(state, root))]:
                            removed = evaluate(state, suites[name], oracles[name], disabled=disabled, repeats=plan["evaluation_repeats"],
                                               proof_node_budget=plan.get("proof_node_budget"))
                            write(directory/(label+"-heldout.json"), removed)
                            ablations[label] = {"root": root, "disabled": sorted(disabled), **final_comparison(removed, final_eval)}
                    write(directory/"closure-causal-replays.json", causal_replays(state, plan["causal_replay_limit"]))
                report["results"][key] = {"snapshots": snapshots, "comparison": comparison,
                    "ablations": ablations, "final_state": str(previous.relative_to(args.output)/"state.json"),
                    "regression": regression}
            except Exception:
                report["errors"].append({"experiment": key, "traceback": traceback.format_exc()})
            write(args.output/"verification.json", report)
    if table:
        with (args.output/"trajectory.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(table[0]))
            writer.writeheader()
            writer.writerows(table)
    report["sources_unchanged"] = source == source_seal()
    report["infrastructure_passed"] = not report["errors"] and report["sources_unchanged"]
    report["capability_effects"] = {k: {f: v["comparison"][f] for f in [
        "newly_solved_heldout_tasks", "lost_heldout_tasks", "tasks_with_fewer_prover_calls", "tasks_with_lower_prover_input"]}
        for k, v in report["results"].items() if k.endswith("-learn")}
    report["new_general_algorithm_demonstrated"] = False
    write(args.output/"verification.json", report)
    (args.output/"report.md").write_text("# Fixed-Baseline Longitudinal Measurement\n\n"+
        "Baseline: `"+sha+"`. Run: `"+str(report["workflow_run_id"])+"`.\n\n"+
        "No acquisition/solver code changed. Held-out evaluation was discarded, never resumed.\n\n"+
        "Rule-search inspections, prover input AST nodes, and wall time are separate units. "
        "Recurrence replays are not external held-out successes. No new-domain transfer is claimed.\n\n"+
        "```json\n"+json.dumps(report["capability_effects"], indent=2)+"\n```\n\n"+
        "Full per-task outcomes, certificates, disabled-rule comparisons, diversity, snapshots and costs are in this artifact.\n",
        encoding="utf-8")
    print(json.dumps({k: report[k] for k in ["infrastructure_passed", "errors", "capability_effects"]}, indent=2))
    return 0 if report["infrastructure_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
