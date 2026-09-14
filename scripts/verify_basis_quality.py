"""Primitive basis quality, not minimum cardinality or universal computation.

Counterfactuals change the actual typed source signature. Independent target
generation precedes learning. Normal acquisition receives no removed operator
specification, target witness or desired replacement definition.
"""
from pathlib import Path
import argparse
from copy import deepcopy
from itertools import combinations, product
import json
import os
import random
import statistics
import subprocess
import sys
import time
import traceback
import sympy as sp

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.run_theory_formation import write, source_seal
from scripts.verify_theory_tasks import freeze
from math_os_prototype.theory_domain import Domain, term
from math_os_prototype.theory_formation import Theory
from math_os_prototype.theory_semantic_edit import SymbolicScope
from math_os_prototype.runtime_typed_planner import initial_fact, RuntimePrimitive, PrimitiveResult, synthesize_typed_plan
from math_os_prototype.representation_progress import digest
from math_os_prototype import library_compression as lib
from math_os_prototype.representation_policy import dominates


def read(p):
    return json.loads(p.read_text(encoding="utf-8"))


def inventory(domain):
    arities = {"var": [], "const": [], "pull": ["scalar"], "neg": ["scalar"],
               "add": ["scalar", "scalar"], "mul": ["scalar", "scalar"],
               "eq": ["scalar", "scalar"], "not": ["predicate"], "and": ["predicate", "predicate"]}
    semantics = {"var": "declared frame entry", "const": "exact rational literal (normal seeds only 0,1)",
                 "pull": "f composed with the executable frame action", "add": "pointwise QQ addition",
                 "mul": "pointwise QQ multiplication", "neg": "pointwise additive inverse",
                 "eq": "pointwise exact equality", "not": "Boolean complement", "and": "Boolean conjunction"}
    return [{"name": op, "inputs": arities[op], "output": "predicate" if op in {"eq", "not", "and"} else "scalar",
             "parameters": domain.names if op == "var" else list(domain.actions) if op == "pull" else "QQ" if op == "const" else [],
             "preconditions": "declared names/actions, well-typed exact arguments; no legality claim",
             "semantics": semantics[op], "executor": "Domain.type_of -> Domain.evaluate.ev",
             "normal_generator": "Domain.seeds" if op in {"var", "const"} else "Domain.compose",
             "verification": "Domain.settle on complete declared model; SymbolicScope only for scalar polynomial arguments"}
            for op in ["var", "const", *domain.operations]]


def challenges(config, plan):
    tasks, witnesses = freeze(config, plan["challenge_seed"])
    d = Domain(config["domain"])
    rng = random.Random(plan["challenge_seed"])
    pool = d.seeds()
    predicates, seen = [], set()
    for _ in range(200):
        parent = rng.choice(pool)
        choices = list(d.compose(parent, pool[-24:]))
        rng.shuffle(choices)
        pool.extend(choices[:4])
        for candidate in choices:
            if d.type_of(candidate) != "predicate":
                continue
            values = list(map(str, d.evaluate(candidate)))
            if tuple(values) not in seen:
                seen.add(tuple(values))
                predicates.append(candidate)
                tasks.append({"id": "predicate-"+str(len(predicates)), "scope": d.scope,
                    "result_type": "predicate", "values": values, "budget": deepcopy(tasks[0]["budget"])})
                witnesses.append({"task": tasks[-1]["id"], "program": candidate})
            if len(predicates) == plan["predicate_count"]:
                break
        if len(predicates) == plan["predicate_count"]:
            break
    if len(predicates) != plan["predicate_count"]:
        raise ValueError("bounded target generator did not fill predicate cohort")
    for t in tasks:
        t["budget"].update(states=plan["search_states"], work=plan["search_work"])
    return tasks, witnesses


def action_reconstruction(domain, removed, budget):
    """Existing typed planner on exact action maps; no target word is supplied."""
    n = len(domain.models)
    identity = tuple(range(n))
    primitives = []
    for g, a in domain.actions.items():
        if "pull:"+g == removed or removed == "pull":
            continue
        def execute(args, g=g, a=a):
            old = args[0].value
            return PrimitiveResult({"map": tuple(old["map"][i] for i in a),
                                    "body": term("pull", old["body"], label=g)}, {"action": g})
        primitives.append(RuntimePrimitive(g, ("operator",), "operator", execute))
    target = domain.actions[removed.split(":", 1)[1]]
    started = time.perf_counter()
    p = synthesize_typed_plan([initial_fact("operator", {"map": identity, "body": lib.program_hole(0)})],
        primitives, ["operator"], max_states=budget, max_depth=64, fair=True,
        goal_predicates={"operator": lambda f: list(f.value["map"]) == target},
        value_key=lambda sort, value: digest(value["map"]))
    found = p.goals.get("operator")
    return {"removed": removed, "found": found is not None, "body": found.value["body"] if found else None,
            "map": list(found.value["map"]) if found else None, "target_map": target,
            "depth": found.depth if found else None, "search_nodes": p.states_explored,
            "seconds": time.perf_counter()-started,
            "proof": {"kind": "equal_action_maps_on_all_declared_states",
                "scope": domain.scope, "quantification": "all QQ-valued input functions on these states",
                "passed": list(found.value["map"]) == target} if found else None}


def macro_reconstruction(e, baseline, removed):
    """Audit autonomous macros after training; never feed this target back."""
    arity = {"neg": 1, "add": 2, "mul": 2}
    op = "pull" if removed.startswith("pull:") else removed
    if op not in arity and not removed.startswith("pull:"):
        return {"status": "unresolved", "reason": "no universal operator certificate in this bounded audit"}
    n = arity.get(op, 1)
    records = []
    for definition in e.state["dsl"]["definitions"]:
        sig = definition["signature"]
        if sig["result"] != "scalar" or list(sig["parameters"].values()) != ["scalar"]*n:
            continue
        names = list(sig["parameters"])
        target = term(op, *[{"series_parameter": name} for name in names],
                      **({"label": removed.split(":", 1)[1]} if op == "pull" else {}))
        left, right = SymbolicScope(e.vocabulary, sig), SymbolicScope(baseline.vocabulary, sig)
        lv, rv = left.values(definition["template"]), right.values(target)
        residuals = [sp.expand(a-b) for a, b in zip(lv, rv)]
        passed = all(sp.Poly(r, *left.symbols, domain=sp.QQ).is_zero for r in residuals)
        records.append({"definition": definition["id"], "template": definition["template"],
            "target": target, "passed": passed, "residuals": list(map(str, residuals)),
            "free_arguments": list(map(str, left.symbols)), "scope": e.domain.scope,
            "source_evidence": definition.get("source_evidence"), "costs": [left.cost, right.cost]})
    return {"status": "replaceable by learned macro" if any(r["passed"] for r in records) else "unresolved",
            "reason": "only independently symbolic certified matches count", "records": records}


def scalar_reconstruction(baseline, removed, budget):
    if removed not in {"neg", "add", "mul"}:
        return {"found": False, "status": "not covered by scalar operator certificate"}
    n = 1 if removed == "neg" else 2
    signature = {"parameters": {f"f{i}": "scalar" for i in range(n)}, "result": "scalar"}
    scope = SymbolicScope(baseline.vocabulary, signature)
    holes = [lib.program_hole(i) for i in range(n)]
    target = term(removed, *holes)
    desired = scope.key(scope.values(target))
    seeds = holes + baseline.domain.seeds()
    facts = [initial_fact("scalar", {"program": p, "values": scope.key(scope.values(p))}) for p in seeds]
    prototypes = {}
    for p in baseline.domain.compose(baseline.domain.seeds()[0], baseline.domain.seeds()[:1]):
        if p["op"] == removed or baseline.domain.type_of(p) != "scalar":
            continue
        prototypes[digest({k: v for k, v in p.items() if k != "args"})] = p
    operations = []
    for key, prototype in prototypes.items():
        def execute(args, prototype=prototype):
            p = dict(prototype, args=[a.value["program"] for a in args])
            return PrimitiveResult({"program": p, "values": scope.key(scope.values(p))}, {"scope": baseline.domain.scope})
        operations.append(RuntimePrimitive(key, ("scalar",)*len(prototype["args"]), "scalar", execute))
    started = time.perf_counter()
    plan = synthesize_typed_plan(facts, operations, ["scalar"], max_states=budget, max_depth=64, fair=True,
        goal_predicates={"scalar": lambda f: f.value["values"] == desired}, value_key=lambda s, v: v["values"])
    found = plan.goals.get("scalar")
    passed, proof = scope.equal(target, found.value["program"]) if found else (False, None)
    return {"found": passed, "body": found.value["program"] if found else None, "proof": proof,
            "search_nodes": plan.states_explored, "costs": scope.cost, "seconds": time.perf_counter()-started,
            "status": "certified symbolic witness" if passed else "unresolved within fixed search budget"}


def role_overlap(domain):
    pools, programs, seen = domain.seeds(), {}, set()
    started = time.perf_counter()
    evaluations = 0
    for depth in range(2):
        added, first_by_operation = [], {}
        for parent in pools[-24:]:
            for p in domain.compose(parent, pools[:12]):
                key = digest(p)
                if key in seen: continue
                seen.add(key)
                values = domain.evaluate(p)
                evaluations += 1
                programs.setdefault(p["op"], set()).add(domain.semantic_key(values))
                first_by_operation.setdefault(p["op"], p)
                if len(added) < 24: added.append(p)
        pools += list(first_by_operation.values())+added[:12]
    return {"pairs": [{"left": a, "right": b, "shared_observed_behaviors": len(programs[a] & programs[b]),
             "left_count": len(programs[a]), "right_count": len(programs[b]),
             "operator_equivalence_claim": False} for a, b in combinations(programs, 2)],
             "evaluations": evaluations, "seconds": time.perf_counter()-started,
             "scope": "bounded composed programs on all finite states; NOT arbitrary operator arguments"}


def necessity_certificate(domain, removed):
    """Small exact abstraction checks; not inference from failed task search."""
    if removed == "eq":
        table = [r for r in inventory(domain) if r["name"] != removed]
        reachable = {"scalar", "natural", "action_word"}
        while True:
            enlarged = reachable | {r["output"] for r in table if set(r["inputs"]) <= reachable}
            if enlarged == reachable: break
            reachable = enlarged
        return {"passed": "predicate" not in reachable, "kind": "typed_constructor_fixed_point",
                "reachable_types": sorted(reachable), "scope": "initial DSL, scalar arguments; no acquired wrappers"}
    if removed in {"not", "and"}:
        arity = 1 if removed == "not" else 2
        assignments = list(product([False, True], repeat=arity))
        # Constants overapproximate every scalar-only comparison at any state.
        reached = {tuple(a[i] for a in assignments) for i in range(arity)} | {tuple([b]*len(assignments)) for b in (False, True)}
        while True:
            new = set(reached)
            if "not" in domain.operations and removed != "not":
                new.update(tuple(not a for a in x) for x in reached)
            if "and" in domain.operations and removed != "and":
                new.update(tuple(a and b for a, b in zip(x, y)) for x in reached for y in reached)
            if new == reached: break
            reached = new
        target = tuple(not a[0] if removed == "not" else (a[0] and a[1]) for a in assignments)
        return {"passed": target not in reached, "kind": "complete_predicate_function_closure",
                "assignments": assignments, "reachable": sorted(reached), "target": target,
                "scope": "pointwise arbitrary predicate arguments; no predicate-to-scalar cast or predicate pullback"}
    return {"passed": False, "kind": "unresolved"}


def summary(rows, vocabulary_size):
    success = [r for r in rows if r["solved"]]
    depths = [r["found_plan_depth"] for r in success]
    return {"vocabulary_size": vocabulary_size, "solved": len(success), "tasks": len(rows),
            "representable_lower_bound": len(success), "representable_exact": None,
            "mean_found_length": statistics.mean(r["found_program_nodes"] for r in success) if success else None,
            "mean_found_depth": statistics.mean(depths) if depths else None,
            "median_found_depth": statistics.median(depths) if depths else None,
            "nodes": sum(r["states_explored"] for r in rows),
            "candidates": sum(r["costs"]["candidate_evaluations"] for r in rows),
            "seconds": sum(r["seconds"] for r in rows),
            "execution_seconds": sum(r["costs"]["evaluation_seconds"] for r in rows),
            "proof_calls": sum(r["costs"]["prover_calls"] for r in rows),
            "verification_checks": sum(r["costs"]["verification_checks"] for r in rows),
            "operation_branches": len(rows[0]["enabled_operations"]) if rows else 0,
            "normal_work": sum(r["normal_work_used"] for r in rows),
            "macro_uses": sum(bool(r["definitions_used"]) for r in rows),
            "shortest_claim": "first found by bounded existing planner, NOT a global minimum"}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--plan", type=Path, default=ROOT/"configs/theory-basis-quality.json")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--development", action="store_true")
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    plan = read(a.plan)
    config = read(ROOT/plan["config"])
    config["budget"].update(plan["budget_overrides"])
    if a.development:
        plan["challenge_seed"] = 923110
        config["budget"].update(cycles=20, library_pairs=120)
    write(a.output/"config.json", config)
    write(a.output/"plan.json", plan)
    tasks, witnesses = challenges(config, plan)
    if a.development:
        tasks = tasks[:2]+tasks[-2:]
    write(a.output/"tasks.json", tasks)
    write(a.output/"evaluator-witnesses.json", witnesses)
    baseline = Theory(config)
    table = inventory(baseline.domain)
    write(a.output/"inventory.json", table)
    names = [r["name"] for r in table]+["pull:"+g for g in baseline.domain.actions]
    if a.development:
        names = ["var", "const", "eq", "pull:A"]
    result = {"sha": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=ROOT).strip(),
        "source_seal": source_seal(), "workflow_run_id": os.environ.get("GITHUB_RUN_ID"),
        "development": a.development, "passed": False, "conditions": {}, "commands": [], "errors": [],
        "scope": baseline.domain.scope, "basis_schemas": len(table), "operator_families": len(baseline.domain.operations),
        "parameter_instantiated_operators": len(baseline.domain.operations)-1+len(baseline.domain.actions)}
    began = time.perf_counter()
    states, all_rows = {}, {}
    try:
        for name in ["B", *names]:
            excluded = [] if name == "B" else [name]
            e = Theory(config, primitive_exclusions=excluded)
            rows = [e.vocabulary.solve_observation(dict(t, scope=e.domain.scope), acquired=False, execution_mode="edited") for t in tasks]
            all_rows[name] = rows
            write(a.output/(name.replace(":", "-")+"-initial.json"), rows)
            result["conditions"][name] = summary(rows, len(table)-(name != "B" and ":" not in name))
            command = [sys.executable, str(ROOT/"scripts/run_theory_formation.py"), "--config", str((a.output/"config.json").resolve()),
                "--output", str((a.output/(name.replace(":", "-")+"-learn")).resolve()), "--refresh-corpus", "--eligible-sources", "--semantic-edits"]
            for key in excluded:
                command += ["--exclude-primitive", key]
            result["commands"].append(command)
            write(a.output/"verification.json", result)
            start = time.perf_counter()
            with (a.output/(name.replace(":", "-")+".log")).open("w", encoding="utf-8") as log:
                done = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, cwd=ROOT, timeout=plan["normal_timeout"])
            if done.returncode:
                raise RuntimeError(name+" normal acquisition failed; log retained")
            state = read(a.output/(name.replace(":", "-")+"-learn")/"state.json")
            learned = Theory(config, **state["flags"], state=state)
            states[name] = state
            result["conditions"][name]["learning_seconds"] = time.perf_counter()-start
            result["conditions"][name]["acquired_definitions"] = len(state["dsl"]["definitions"])
            result["conditions"][name]["acquisition_costs"] = state["costs"]
            if name != "B":
                result["conditions"][name]["reacquisition"] = macro_reconstruction(learned, baseline, name)
                if name.startswith("pull:"):
                    result["conditions"][name]["operator_reconstruction"] = action_reconstruction(baseline.domain, name, plan["action_reconstruction_states"])
                else:
                    result["conditions"][name]["operator_reconstruction"] = scalar_reconstruction(baseline, name, plan["action_reconstruction_states"])
                result["conditions"][name]["necessity_certificate"] = necessity_certificate(baseline.domain, name)
            future = [learned.vocabulary.solve_observation(dict(t, scope=learned.domain.scope), execution_mode="edited") for t in tasks]
            write(a.output/(name.replace(":", "-")+"-learned.json"), future)
            result["conditions"][name]["after_learning"] = summary(future, result["conditions"][name]["vocabulary_size"]+len(state["dsl"]["definitions"]))
            print(json.dumps({"basis": name, "initial": sum(r["solved"] for r in rows), "learned": sum(r["solved"] for r in future), "definitions": len(state["dsl"]["definitions"])}), flush=True)
        # Candidates selected by acquisition order BEFORE looking at their evaluation.
        # A fixed ordinary full-signature producer supplies already acquired
        # macros, not human-designed shortcuts. Its certificate dependencies count.
        macro_config = read(ROOT/plan["config"])
        macro_config["budget"].update(cycles=config["budget"]["cycles"], seconds=config["budget"]["seconds"])
        write(a.output/"macro-source-config.json", macro_config)
        command = [sys.executable, str(ROOT/"scripts/run_theory_formation.py"), "--config", str((a.output/"macro-source-config.json").resolve()),
            "--output", str((a.output/"macro-source").resolve()), "--refresh-corpus", "--eligible-sources", "--semantic-edits"]
        result["commands"].append(command)
        with (a.output/"macro-source.log").open("w", encoding="utf-8") as log:
            done = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, cwd=ROOT, timeout=plan["normal_timeout"])
        if done.returncode: raise RuntimeError("macro source failed")
        state = read(a.output/"macro-source"/"state.json")
        learned = Theory(macro_config, **state["flags"], state=state)
        result["macro_source"] = {"state_sha": state["sha256"], "costs": state["costs"], "seconds": state["seconds"],
                                  "selection": "first acquired definitions, never chosen from evaluation results"}
        for d in state["dsl"]["definitions"][:plan["macro_candidates"]]:
            name = "B+"+d["id"]
            rows = [learned.vocabulary.solve_observation(t, operation_keys=["definition:"+d["id"]], execution_mode="edited") for t in tasks]
            write(a.output/(name+".json"), rows)
            all_rows[name] = rows
            result["conditions"][name] = summary(rows, len(table)+1)
            result["conditions"][name]["definition"] = d
        # Same-input paired comparison, with no cheap-failure credit.
        base_rows = all_rows["B"]
        for name, rows in all_rows.items():
            common = [(b, r) for b, r in zip(base_rows, rows) if b["solved"] and r["solved"]]
            result["conditions"][name]["paired"] = {"common_solved": len(common),
                "nodes_delta": sum(r["states_explored"]-b["states_explored"] for b, r in common),
                "length_delta": sum(r["found_program_nodes"]-b["found_program_nodes"] for b, r in common),
                "lost": [b["task"] for b, r in zip(base_rows, rows) if b["solved"] and not r["solved"]],
                "gained": [r["task"] for b, r in zip(base_rows, rows) if r["solved"] and not b["solved"]]}
        axes = ("size", "coverage", "description", "search", "execution")
        vectors = {n: {"size": -r["vocabulary_size"], "coverage": r["solved"], "description": -r["mean_found_length"] if r["mean_found_length"] is not None else None,
                       "search": -r["nodes"], "execution": -r["normal_work"]} for n, r in result["conditions"].items()}
        result["empirical_pareto_frontier"] = [n for n, v in vectors.items() if not any(
            dominates(other, v, objectives=axes) for m, other in vectors.items() if m != n)]
        result["pareto_caveat"] = "bounded task coverage lower bound; mean found length is conditional on success; not global expressivity/minimality"
        maps = {g: tuple(a) for g, a in baseline.domain.actions.items()}
        result["action_pairs"] = [{"left": g, "right": h, "one_step_maps_equal": maps[g] == maps[h],
            "one_step_destination_overlap": len(set(maps[g]) & set(maps[h])),
            "commute_on_all_states": tuple(maps[g][i] for i in maps[h]) == tuple(maps[h][i] for i in maps[g]),
            "scope": "all arbitrary input functions on the declared 24 frames; overlap alone is not equivalence"} for g, h in combinations(maps, 2)]
        result["role_overlap"] = role_overlap(baseline.domain)
        for name in names:
            r = result["conditions"][name]
            if r["reacquisition"]["status"] == "replaceable by learned macro":
                classification = "replaceable by learned macro"
            elif r["necessity_certificate"]["passed"]:
                classification = "essential within the declared typed initial DSL"
            elif r["operator_reconstruction"]["found"]:
                q = r["paired"]
                classification = "theoretically redundant but search-useful" if q["lost"] or q["nodes_delta"] > 0 or q["length_delta"] > 0 else "redundant and removable within tested scope/budget"
            else:
                classification = "unresolved: bounded failure is not semantic necessity"
            r["classification"] = classification
        result["sources_unchanged"] = source_seal() == result["source_seal"]
        result["passed"] = result["sources_unchanged"]
    except Exception:
        result["errors"].append(traceback.format_exc())
    result["wall_seconds"] = time.perf_counter()-began
    lines = ["# Primitive basis quality", "", "Count schemas, parameter instances, and acquired wrappers separately. No universal-computation claim.",
        "Found lengths are bounded-search witnesses, not global minima. Representability is a certified LOWER BOUND unless an operator proof is provided.", "",
        "| Basis | Schemas | Correct | Mean found nodes | Mean depth | Search applications | Seconds | After learning | Classification |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |"]
    for name, r in result["conditions"].items():
        lines.append(f"| {name} | {r['vocabulary_size']} | {r['solved']}/{r['tasks']} | {r['mean_found_length']} | {r['mean_found_depth']} | {r['nodes']} | {r['seconds']:.3f} | {r.get('after_learning', {}).get('solved', 'n/a')} | {r.get('classification', '')} |")
    lines += ["", "Empirical Pareto frontier: "+str(result.get("empirical_pareto_frontier")), "",
        "Removing one pull parameter leaves the schema count unchanged. See parameter_instantiated_operators and per-condition executor branches.",
        "All per-task results, same-input deltas, universal action-map certificates, symbolic macro tests and negative outcomes remain in verification.json.",
        "Acquisition excludes certified representation/recurrence wrappers in every deletion condition, to avoid a disguised removed operator. Their general kernels still exist in MORTRA.",
        "Macro addition uses the first actual acquisitions of a separately frozen full normal producer. Their complete dependencies and costs are retained."]
    (a.output/"report.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    write(a.output/"verification.json", result)
    print(json.dumps({"passed": result["passed"], "errors": result["errors"], "seconds": result["wall_seconds"]}))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
