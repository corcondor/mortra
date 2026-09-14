"""State-hiding adapter on the existing fair typed planner (no new solver)."""
from collections import Counter
from copy import deepcopy
import json
import time
import sympy as sp
from math_os_prototype import geometry_contracts as gc
from math_os_prototype import geometry_contraction as contraction
from math_os_prototype.representation_progress import digest
from math_os_prototype.runtime_typed_planner import PrimitiveResult
from math_os_prototype.theory_geometry_acquisition import (
    RationalGeometryDomain, solve, independent_replay, acquisition, task_identity,
)


class ContractionGeometryDomain(RationalGeometryDomain):
    def __init__(self, task, config, contracts=(), *, mode="summarized", emit=lambda e: None):
        super().__init__(task, config, contracts, mode="certified", emit=emit)
        self.mode = mode
        self.guard_cache = {}
        self.effect_signatures = {}
        self.contract_symbols = {}
        for h in self.contracts.values():
            valid, cost = contraction.replay_summary(h, h["summary"])
            if not valid:
                raise ValueError("stored contraction summary rejected")
            self.costs["summary_registration_seconds"] += cost["seconds"]
            self.costs["summary_registration_prover_calls"] += cost["summary_identity_calls"]+cost["contract_replay"]["prover_calls"]
            self.effect_signatures[h["id"]] = h["summary"]["effect_signature"]
        self.preconditions = dict(self.contracts)
        for family, arity in gc.ARITIES.items():
            h, cost = gc.certify_body({"op": family, "args": [gc.point(f"f{i}") for i in range(arity)]})
            summary, summary_cost = contraction.compile_summary(h)
            self.costs["primitive_registration_seconds"] += cost["certification_seconds"]+summary_cost["seconds"]
            self.costs["primitive_registration_prover_calls"] += cost["prover_calls"]+summary_cost["summary_identity_calls"]+summary_cost["contract_replay"]["prover_calls"]
            self.preconditions[family] = h
            self.effect_signatures[family] = summary["effect_signature"]
        self.parsed_guards = {}
        for family, h in self.preconditions.items():
            syms = {p["name"]+a: sp.Symbol(p["name"]+a, real=True) for p in h["typed_parameters"] for a in ("x", "y")}
            self.contract_symbols[family] = syms
            self.parsed_guards[family] = [gc.parse(e, syms) for e in h["applicability"]["input_nonzero_polynomials"]]
        target = contraction.effect_signature(self.goals, self.symbols, [self.symbols["ux"], self.symbols["uy"]])
        self.effect_priority_by_family = {f: (int(s["output_type"] != target["output_type"]),
            int(s["affine_all_coordinates"] != target["affine_all_coordinates"])) for f, s in self.effect_signatures.items()}
        if mode == "summarized":
            self.families = tuple(sorted(self.families, key=lambda f: self.effect_priority_by_family[f]))
        self.families = (*self.families, "refine")
        self.log(event="summary_registry", mode=mode, effects=self.effect_signatures,
                 target_signature=target, family_order=self.families,
                 effect_use="ordering only, no reachability exclusion", refinement="explicit paid alternative")

    def key(self, state):
        # Availability of a refinement is part of action semantics.
        return digest({"base": super().key(state), "refinements": [s.get("contraction") for s in state["path"]]})

    def public_outputs(self, contract, steps):
        return contract["summary"]["interface"]["public_outputs"] if contract else super().public_outputs(contract, steps)

    def candidate_options(self, family, state):
        audit = {}
        options = {**super().candidate_options(family, state), "audit": audit}
        self.current_audit = audit
        if self.mode != "summarized":
            return options
        coords = self.coordinates(state)
        def precondition(schema, inputs):
            self.budget()
            start = time.perf_counter()
            self.costs["precondition_bindings"] += 1
            key = (schema.name, tuple(tuple(state["points"][n]) for n in inputs))
            if key in self.guard_cache:
                ok, reason = self.guard_cache[key]
                self.costs["precondition_cache_hits"] += 1
            else:
                h = self.preconditions[schema.name]
                syms = self.contract_symbols[schema.name]
                replacements = {syms[p["name"]+a]: coords[n][i]
                    for p, n in zip(h["typed_parameters"], inputs, strict=True) for i, a in enumerate(("x", "y"))}
                self.costs["precondition_prover_calls"] += len(self.parsed_guards[schema.name])
                try:
                    self.require_guards([e.xreplace(replacements) for e in self.parsed_guards[schema.name]])
                    ok, reason = True, None
                except ValueError as exc:
                    ok, reason = False, str(exc)
                self.guard_cache[key] = (ok, reason)
            self.costs["precondition_seconds"] += time.perf_counter()-start
            if not ok:
                self.log(event="precondition_filter", family=schema.name, inputs=inputs,
                         parent=self.key(state), reason=reason,
                         meaning="not admitted by existing sufficient-guard checker, not necessarily impossible")
            return ok
        options.update(binding_precondition=precondition,
                       effect_priority=lambda c: self.effect_priority_by_family[c.family])
        return options

    def alternatives(self, family, state):
        if family != "refine":
            yield from super().alternatives(family, state)
            return
        for index, action in enumerate(state["path"]):
            hidden = action.get("contraction")
            if hidden and not hidden["refined"]:
                self.costs["offered_refinements"] += 1
                yield lambda index=index: self.refine(state, index)

    def refine(self, state, index):
        action = state["path"][index]
        detail = action["contraction"]
        if detail["refined"]:
            return None
        self.budget(action["primitive_equivalent_operations"])
        self.costs["candidate_expansions"] += 1
        self.costs["refinement_calls"] += 1
        self.costs["primitive_equivalent_operations"] += action["primitive_equivalent_operations"]
        start = time.perf_counter()
        h = self.contracts[action["family"]]
        coords = self.coordinates(state)
        explicit = gc._JGEXElaborator()
        terms = {}
        for p, actual in zip(h["typed_parameters"], action["inputs"], strict=True):
            explicit.coordinates[p["name"]] = coords[actual]
            terms[p["name"]] = state["terms"][actual]
        child, added = deepcopy(state), []
        for step in h["composition"]:
            gc.primitive(explicit, step["family"], step["output"], step["inputs"])
            self.require_guards(explicit.denominators)
            self.costs["refinement_primitive_executions"] += 1
            self.costs["refinement_contract_checks"] += len(explicit.denominators)
            terms[step["output"]] = {"op": step["family"], "args": [terms[n] for n in step["inputs"]]}
            if step["output"] not in detail["private_locals"]:
                continue
            name = f"v{len(child['points'])}"
            while name in child["points"]:
                name = "r"+name
            child["points"][name] = list(map(str, explicit.coordinates[step["output"]]))
            child["terms"][name] = terms[step["output"]]
            added.append(name)
        child["path"][index]["contraction"]["refined"] = True
        refinement = {"family": "refine", "inputs": action["inputs"], "outputs": added,
            "output": added[-1], "refines_action": index, "certificate": h["summary"]["id"],
            "primitive_equivalent_operations": len(h["composition"])}
        child["path"].append(refinement)
        child["primitive_equivalent_depth"] += len(h["composition"])
        self.costs["refinement_seconds"] += time.perf_counter()-start
        self.costs["successful_applications"] += 1
        self.costs["exposed_objects"] += len(added)
        self.log(event="refine", action=refinement, parent=self.key(state), child=self.key(child))
        return PrimitiveResult(child, refinement)


def run_contraction_geometry(config, output):
    def write(name, value):
        (output/name).write_text(json.dumps(value, indent=2)+"\n", encoding="utf-8")
    def run(task, label, contracts=(), mode="certified"):
        def emit(event):
            with (output/"events.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps({"phase": label, "task": task["id"], **event})+"\n")
        cls = ContractionGeometryDomain if mode in {"summarized", "hiding_only"} else RationalGeometryDomain
        result = solve(task, config["search"], contracts, mode=mode, emit=emit, domain_class=cls)
        result["independent_replay"] = independent_replay(result)
        result["false_proofs"] = int(result["solved"] and not result["independent_replay"]["passed"])
        write(f"{label}-{task['id']}.json", result)
        print(json.dumps({"phase": label, "task": task["id"], "solved": result["solved"],
                          "expansions": result["costs"].get("candidate_expansions", 0)}), flush=True)
        return result
    write("frozen-plan.json", config)
    train_ids = {task_identity(t) for t in config["training"]}
    if train_ids & {task_identity(t) for t in config["evaluation"]}:
        raise ValueError("training/evaluation overlap")
    training = [run(t, "training") for t in config["training"]]
    write("training.json", training)
    learned = acquisition(training, config["acquisition"])
    write("acquisition.json", learned)
    archive = deepcopy(learned["active"])
    for h in archive:
        boundary, evidence = contraction.source_interfaces(h, learned["corpus"])
        h["summary"], h["summary_cost"] = contraction.compile_summary(h, boundary)
        h["interface_sources"] = evidence
    write("archive.json", learned["archive"])
    write("frozen-library.json", archive)
    frozen = digest(archive)
    comparisons = {}
    for label, contracts, mode in [("primitive_only", [], "primitive"),
        ("syntactic_macro", archive, "primitive"), ("certified_morphism", archive, "certified"),
        ("summarized", archive, "summarized"), ("hiding_only", archive, "hiding_only")]:
        comparisons[label] = [run(t, label, contracts, mode) for t in config["evaluation"]]
        write("comparisons.json", comparisons)
    uses = Counter(h for r in comparisons["summarized"] for h in r["goal_acquired_calls"])
    excluded = sorted(uses, key=lambda h: (-uses[h], h))[:1]
    comparisons["ablation"] = [run(t, "ablation", [h for h in archive if h["id"] not in excluded], "summarized")
                                for t in config["evaluation"]]
    write("comparisons.json", comparisons)
    # Historical tasks are replayed separately, never included in scientific totals.
    write("regression.json", [run(t, "regression", archive, "summarized") for t in config["regression"]])
    summary = {}
    for label, rows in comparisons.items():
        costs = Counter()
        for r in rows:
            costs.update(r["costs"])
        costs["max_state_object_count"] = max(r["costs"].get("max_state_object_count", 0) for r in rows)
        costs["mean_state_object_count"] = costs["state_object_count_sum"]/max(1, costs["goal_checked_states"])
        summary[label] = {"solved": sum(r["solved"] for r in rows), "total": len(rows),
            "false_proofs": sum(r["false_proofs"] for r in rows), "costs": dict(costs),
            "wall_seconds": sum(r["wall_seconds"] for r in rows),
            "states_explored": sum(r["states_explored"] or 0 for r in rows),
            "states_retained": sum(r["states_retained"] or 0 for r in rows),
            "incomplete_state_counts": sum(r["states_explored"] is None for r in rows),
            "replay_seconds": sum(r["independent_replay"].get("seconds", 0) for r in rows)}
    causal = []
    for d, b, e, a in zip(comparisons["summarized"], comparisons["syntactic_macro"],
                          comparisons["hiding_only"], comparisons["ablation"], strict=True):
        def cheaper(left, right):
            return left["solved"] and (not right["solved"] or any(
                left["costs"].get(k, 0) < right["costs"].get(k, 0)
                for k in ("candidate_expansions", "goal_prover_calls", "max_state_object_count")))
        causal.append({"task": d["task"]["id"], "vs_exposed": cheaper(d, b),
            "hiding_only_vs_exposed": cheaper(e, b), "used_H_ablation": cheaper(d, a),
            "lost_exposed_solve": b["solved"] and not d["solved"],
            "used": d["goal_acquired_calls"]})
    lost = any(base["solved"] and not d["solved"] for label in ("primitive_only", "syntactic_macro", "certified_morphism", "hiding_only")
               for base, d in zip(comparisons[label], comparisons["summarized"], strict=True))
    false = any(s["false_proofs"] for s in summary.values())
    hiding_lost = any(b["solved"] and not e["solved"] for b, e in
                      zip(comparisons["syntactic_macro"], comparisons["hiding_only"], strict=True))
    lower_search = lambda label: any(summary[label]["costs"].get(k, 0) < summary["syntactic_macro"]["costs"].get(k, 0)
                                     for k in ("candidate_expansions", "goal_prover_calls"))
    passed = bool(uses and not lost and not false and summary["summarized"]["costs"].get("hidden_objects", 0)
                  and not hiding_lost and lower_search("summarized") and lower_search("hiding_only")
                  and any(c["vs_exposed"] and c["used"] for c in causal)
                  and any(c["hiding_only_vs_exposed"] for c in causal)
                  and any(c["used_H_ablation"] for c in causal))
    result = {"execution_completed": True, "scope": gc.SCOPE, "plan_sha256": digest(config),
        "frozen_library_sha256": frozen, "library_unchanged": frozen == digest(archive),
        "archive_sha256": digest(learned["archive"]),
        "summary": summary, "causal_comparison": causal, "ablation_excluded": excluded,
        "acquisition_seconds": learned["wall_seconds"], "acquired_count": len(learned["archive"]),
        "summary_compilation_costs": [h["summary_cost"] for h in archive],
        "scientific_gate_passed": passed, "minimal_chain_passed": passed,
        "lost_baseline_solve": lost, "hiding_lost_solve": hiding_lost,
        "new_algorithm_claimed": False, "external_prover_used": False,
        "scope_note": "finite construction search; not a completeness or asymptotic speedup claim"}
    write("result.json", result)
    return result
