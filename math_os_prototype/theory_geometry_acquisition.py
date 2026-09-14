"""Rational construction tasks on MORTRA's existing typed geometry planner.

The input is a point-construction specification, not a supplied program.
Training proofs feed the existing library learner; certified definitions become
ordinary ConstructionFamily entries. This is not a general geometry solver.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from itertools import combinations
import json
import time

import sympy as sp

from math_os_prototype import geometry_contracts as gc
from math_os_prototype import library_compression as library
from math_os_prototype.representation_progress import digest
from math_os_prototype.runtime_typed_planner import PrimitiveResult, RuntimeSearchProgress
from math_os_prototype.theory_action_domain import search_action_domain
from worker.backend.typed_geometry_stalk import (
    ConstructionFamily, DEFAULT_POINT_FAMILIES, enumerate_typed_candidates,
)


class ConstructionBudgetExceeded(RuntimeError):
    pass


def task_identity(task):
    return digest({k: v for k, v in task.items() if k not in {"id", "description"}})


class RationalGeometryDomain:
    sort = "GeometryState"

    def __init__(self, task, config, contracts=(), *, mode="certified", emit=lambda e: None):
        self.task, self.config, self.mode, self.emit = deepcopy(task), config, mode, emit
        names = task["points"]
        if len(set(names)) != len(names) or "u" in names or len(names) < 2:
            raise ValueError("distinct declared input names required; u is the output")
        for name in names:
            gc.validate(gc.point(name))
        self.symbols = {n+axis: sp.Symbol(n+axis, real=True) for n in [*names, "u"] for axis in ("x", "y")}
        self.goals = [gc.parse(e, self.symbols) for e in task["goal_polynomials"]]
        if not self.goals or any(not e.is_polynomial(*self.symbols.values()) for e in self.goals):
            raise ValueError("nonempty polynomial construction specification required")
        self.guards = set()
        for e in task.get("nonzero", []):
            value = gc.parse(e, self.symbols)
            if not value.is_polynomial(*self.symbols.values()):
                raise ValueError("task guards must be input polynomials")
            if value.free_symbols & {self.symbols["ux"], self.symbols["uy"]}:
                raise ValueError("task precondition cannot constrain the unknown output")
            self.guards.update(gc.factors(value))
        self.registry = {f.name: f for f in DEFAULT_POINT_FAMILIES if f.name in gc.ARITIES}
        self.contracts = {}
        self.costs = Counter()
        self.events = []
        self.started = time.perf_counter()
        self.goal_cache = {}
        for h in contracts:
            if mode == "certified":
                valid, cost = gc.replay_contract(h)
                self.costs["archive_replay_seconds"] += cost["certification_seconds"]
                self.costs["archive_replay_prover_calls"] += cost["prover_calls"]
                if not valid:
                    raise ValueError("stored geometry contract replay rejected")
            else:
                gc.validate(h["body"])
                if h["typed_parameters"] != [{"name": n, "type": "Point"} for n in gc.parameters(h["body"])]:
                    raise ValueError("plain macro parameter mismatch")
            self.contracts[h["id"]] = h
            self.registry[h["id"]] = ConstructionFamily(h["id"], len(h["typed_parameters"]), "ordered", allow_repeated_inputs=True)
        self.families = tuple(self.registry)
        self.log(event="registry", primitives=list(gc.ARITIES), acquired=list(self.contracts),
                 scope=gc.SCOPE, mode=mode)

    def log(self, **event):
        self.events.append(event)
        self.emit(event)

    def initial(self):
        return {"points": {n: [n+"x", n+"y"] for n in self.task["points"]},
                "terms": {n: gc.point(n) for n in self.task["points"]},
                "path": [], "certificates": [], "primitive_equivalent_depth": 0}

    def key(self, state):
        return digest({"points": state["points"], "terms": state["terms"],
                       "graph_history": [{k: s[k] for k in ("inputs", "outputs")} for s in state["path"]]})

    def coordinates(self, state):
        return {n: tuple(gc.parse(e, self.symbols) for e in xy) for n, xy in state["points"].items()}

    def budget(self, operations=0):
        if self.costs["primitive_equivalent_operations"]+operations > self.config["max_primitive_operations"]:
            raise ConstructionBudgetExceeded("primitive_operation_budget")
        if time.perf_counter()-self.started > self.config["wall_seconds"]:
            raise ConstructionBudgetExceeded("wall_budget_checked_between_exact_operations")

    def candidates(self, family, state):
        started = time.perf_counter()
        names = list(state["points"])
        # Goal support is symbolic input data, never a known answer or trace ID.
        multiplicity = Counter(n for e in self.goals for n in names
                               if self.symbols.get(n+"x") in e.free_symbols or self.symbols.get(n+"y") in e.free_symbols)
        graph = {n: set() for n in names}
        for step in state["path"]:
            for a, b in combinations([*step["inputs"], *step["outputs"]], 2):
                graph[a].add(b)
                graph[b].add(a)
        options = self.candidate_options(family, state)
        audit = options.setdefault("audit", {})
        rows = enumerate_typed_candidates(points=names, graph=graph,
            goal_multiplicity=multiplicity, generated_points=set(names)-set(self.task["points"]),
            families=[self.registry[family]], used_keys=set(),
            per_family_limit=self.config["per_family_limit"], ranking="structural", seed=self.config["seed"],
            **options)
        self.costs["offered_candidates"] += len(rows)
        self.costs["examined_input_tuples"] += audit["examined_input_tuples"]
        self.costs["precondition_filtered"] += audit["precondition_filtered"]
        self.log(event="candidate_audit", family=family, parent=self.key(state), **audit)
        self.costs["candidate_generation_seconds"] += time.perf_counter()-started
        self.log(event="enumerate", family=family, parent=self.key(state),
                 active_points=names, active_point_count=len(names),
                 candidates=[{"key": c.key, "inputs": c.inputs} for c in rows])
        return rows

    def candidate_options(self, family, state):
        return {"max_input_tuples_per_family": self.config.get("max_input_tuples_per_family")}

    def public_outputs(self, contract, steps):
        return [s["output"] for s in steps]

    def alternatives(self, family, state):
        for candidate in self.candidates(family, state):
            yield lambda c=candidate: self.apply(state, c)

    def require_guards(self, expressions):
        for expression in expressions:
            numerator, denominator = sp.cancel(expression).as_numer_denom()
            required = set(gc.factors(numerator)) | set(gc.factors(denominator))
            if not required <= self.guards:
                raise ValueError("unproved_applicability: "+str(sorted(required-self.guards)))

    def apply(self, state, candidate):
        self.budget()
        self.costs["candidate_expansions"] += 1
        acquired = candidate.family in self.contracts
        h = self.contracts.get(candidate.family)
        if acquired:
            self.costs["acquired_morphism_calls"] += 1
            body = h["body"]
            binding = {p["name"]: state["terms"][v] for p, v in zip(h["typed_parameters"], candidate.inputs, strict=True)}
        else:
            body = {"op": candidate.family, "args": [gc.point(f"f{i}") for i in range(len(candidate.inputs))]}
            binding = {f"f{i}": state["terms"][v] for i, v in enumerate(candidate.inputs)}
        def substitute(node):
            return deepcopy(binding[node["name"]]) if node["op"] == "var" else {
                "op": node["op"], "args": [substitute(a) for a in node["args"]]}
        term = substitute(body)
        child = deepcopy(state)
        coords = self.coordinates(state)
        source_names = gc.parameters(body)
        env = {n: coords[v] for n, v in zip(source_names, candidate.inputs, strict=True)}
        steps, final = gc.dag(body)
        count = len(steps)
        public_outputs = self.public_outputs(h, steps)
        self.budget(count)
        self.costs["primitive_equivalent_operations"] += count
        start = time.perf_counter()
        try:
            if acquired and self.mode in {"certified", "summarized", "hiding_only"}:
                symbol_map = {n+axis: sp.Symbol(n+axis, real=True) for n in source_names for axis in ("x", "y")}
                replacement = {symbol_map[n+axis]: env[n][i] for n in source_names for i, axis in enumerate(("x", "y"))}
                guards = [gc.parse(e, symbol_map).subs(replacement, simultaneous=True)
                          for e in h["applicability"]["input_nonzero_polynomials"]]
                self.require_guards(guards)
                self.costs["contract_checks"] += 1
                self.costs["contract_check_seconds"] += time.perf_counter()-start
                execution = time.perf_counter()
                for s in steps:
                    if s["output"] not in public_outputs:
                        continue
                    env[s["output"]] = tuple(sp.cancel(gc.parse(e, symbol_map).subs(replacement, simultaneous=True))
                                              for e in h["witness"][s["output"]])
                self.costs["certified_witness_evaluations"] += len(public_outputs)
                self.costs["execution_seconds"] += time.perf_counter()-execution
                certificate = h["id"]
            else:
                # Plain macros retain per-primitive legality checks. They are
                # not deliberately made unsafe to manufacture a comparison win.
                for s in steps:
                    execution = time.perf_counter()
                    explicit = gc._JGEXElaborator()
                    explicit.coordinates.update(env)
                    gc.primitive(explicit, s["family"], s["output"], s["inputs"])
                    self.costs["execution_seconds"] += time.perf_counter()-execution
                    check_start = time.perf_counter()
                    self.require_guards(explicit.denominators)
                    self.costs["contract_checks"] += 1
                    self.costs["contract_check_seconds"] += time.perf_counter()-check_start
                    env[s["output"]] = explicit.coordinates[s["output"]]
                    self.costs["primitive_executions"] += 1
                certificate = "primitive_contract_composition"
            output_coords = tuple(sp.cancel(v) for v in env[final])
            if any(all(gc.exact_zero(a-b) for a, b in zip(output_coords, other)) for other in coords.values()):
                raise ValueError("duplicate_point")
            mapping = dict(zip(source_names, candidate.inputs, strict=True))
            local_terms = {n: state["terms"][v] for n, v in mapping.items()}
            added = []
            for s in steps:
                local_term = {"op": s["family"], "args": [local_terms[a] for a in s["inputs"]]}
                local_terms[s["output"]] = local_term
                if s["output"] not in public_outputs:
                    continue
                index = len(child["points"])
                name = f"v{index}"
                while name in child["points"]:
                    index += 1
                    name = f"v{index}"
                mapping[s["output"]] = name
                child["points"][name] = list(map(str, env[s["output"]]))
                child["terms"][name] = local_term
                added.append(name)
            action = {"family": candidate.family, "inputs": list(candidate.inputs), "outputs": added,
                      "output": mapping[final], "body": body, "term": term,
                      "primitive_equivalent_operations": count, "certificate": certificate}
            if len(public_outputs) < count:
                action["contraction"] = {"summary_id": h["summary"]["id"],
                    "local_mapping": {n: mapping[n] for n in public_outputs},
                    "private_locals": [s["output"] for s in steps if s["output"] not in public_outputs],
                    "refined": False}
            child["path"].append(action)
            child["certificates"].append(certificate)
            child["primitive_equivalent_depth"] += count
            self.costs["successful_applications"] += 1
            self.costs["successful_acquired_applications"] += int(acquired)
            self.costs["exposed_objects"] += len(added)
            self.costs["hidden_objects"] += count-len(added)
            self.log(event="apply", action=action, parent=self.key(state), child=self.key(child))
            return PrimitiveResult(child, action)
        except ValueError as exc:
            self.costs["rejected_applications"] += 1
            self.costs["rejected_acquired_applications"] += int(acquired)
            self.log(event="reject", family=candidate.family, inputs=candidate.inputs, reason=str(exc))
            return None
        finally:
            self.costs["application_seconds_inclusive"] += time.perf_counter()-start

    def is_goal(self, state):
        self.budget()
        key = self.key(state)
        if key in self.goal_cache:
            return self.goal_cache[key] is not None
        started = time.perf_counter()
        self.costs["goal_checked_states"] += 1
        self.costs["state_object_count_sum"] += len(state["points"])
        self.costs["max_state_object_count"] = max(self.costs["max_state_object_count"], len(state["points"]))
        for name, coords in self.coordinates(state).items():
            replacement = {self.symbols["ux"]: coords[0], self.symbols["uy"]: coords[1]}
            residuals = [sp.cancel(e.subs(replacement, simultaneous=True)) for e in self.goals]
            self.costs["goal_prover_calls"] += len(residuals)
            if all(gc.exact_zero(e) for e in residuals):
                witness = {"point": name, "term": state["terms"][name], "residuals": list(map(str, residuals)),
                           "precondition": sorted(self.guards), "scope": gc.SCOPE}
                self.goal_cache[key] = witness
                self.log(event="goal_certificate", witness=witness, state=key)
                self.costs["goal_proof_seconds"] += time.perf_counter()-started
                return True
        self.goal_cache[key] = None
        self.costs["goal_proof_seconds"] += time.perf_counter()-started
        return False


def proof_depths(proof, actions):
    """Lengths count operations; depths count the longest dependency chain."""
    if not proof:
        return {"expanded_primitive_proof_nodes": None,
                "expanded_primitive_proof_depth": None, "macro_proof_depth": None}
    steps, output = gc.dag(proof["term"])
    depths = {}
    for step in steps:
        depths[step["output"]] = 1+max((depths.get(n, 0) for n in step["inputs"]), default=0)
    macro_depths = {}
    for action in actions:
        depth = 1+max((macro_depths.get(n, 0) for n in action["inputs"]), default=0)
        if action["family"] == "refine":
            original = actions[action["refines_action"]]
            depth = max(depth, 1+max(macro_depths[n] for n in original["outputs"]))
        for name in action["outputs"]:
            macro_depths[name] = depth
    return {"expanded_primitive_proof_nodes": len(steps),
            "expanded_primitive_proof_depth": depths.get(output, 0),
            "macro_proof_depth": macro_depths.get(proof["point"], 0)}


def solve(task, config, contracts=(), *, mode="certified", emit=lambda e: None, domain_class=RationalGeometryDomain):
    start = time.perf_counter()
    domain = domain_class(task, config, contracts, mode=mode, emit=emit)
    progress = RuntimeSearchProgress()
    try:
        plan = search_action_domain(domain, max_depth=config["max_primitive_operations"],
                                    max_states=config["max_states"], progress=progress)
        goal = plan.goals.get(domain.sort)
        state = goal.value if goal else None
        stop = "proved" if goal else "candidate_or_state_budget"
    except ConstructionBudgetExceeded as exc:
        state, stop = None, str(exc)
    proof = domain.goal_cache.get(domain.key(state)) if state else None
    needed, used = {proof["point"]} if proof else set(), []
    for step in reversed(state["path"] if state else []):
        if needed & set(step["outputs"]):
            used.append(step)
            needed.update(step["inputs"])
            if step["family"] == "refine":
                needed.update(state["path"][step["refines_action"]]["outputs"])
    used.reverse()
    return {"task": deepcopy(task), "task_sha256": task_identity(task), "solved": bool(state), "stop_reason": stop,
            "state": state, "proof": proof, "costs": dict(domain.costs), "events": domain.events,
            "wall_seconds": time.perf_counter()-start,
            "states_explored": progress.states_explored, "states_retained": progress.states_retained,
            "planner_applications_started": progress.applications_started,
            "planner_applications_completed": progress.applications_completed,
            "planner_applications_interrupted": progress.applications_started-progress.applications_completed,
            "measurement_version": 2,
            "wall_budget_is_soft": True,
            "proof_length": sum(s["primitive_equivalent_operations"] for s in used) if state else None,
            "macro_proof_length": len(used) if state else None,
            **proof_depths(proof, state["path"] if state else []),
            "proof_actions": used,
            "goal_acquired_calls": [s["family"] for s in used if s["family"] in domain.contracts],
            "false_proofs": None, "false_proof_scope": "requires independent replay"}


def independent_replay(result):
    """Replay the found term with primitive formulas, not saved H witnesses."""
    if not result["solved"]:
        return {"checked": False, "passed": None, "reason": "no proof submitted"}
    started = time.perf_counter()
    task, term = result["task"], result["proof"]["term"]
    domain = RationalGeometryDomain(task, {"seed": 0, "wall_seconds": 3600})
    explicit = gc._JGEXElaborator()
    explicit.coordinates.update(domain.coordinates(domain.initial()))
    steps, output = gc.dag(term)
    for step in steps:
        gc.primitive(explicit, step["family"], step["output"], step["inputs"])
        domain.require_guards(explicit.denominators)
    x, y = explicit.coordinates[output]
    replacement = {domain.symbols["ux"]: x, domain.symbols["uy"]: y}
    residuals = [str(sp.cancel(e.subs(replacement, simultaneous=True))) for e in domain.goals]
    contract, _ = gc.certify_body(term) if steps else (None, {})
    if contract:
        domain.require_guards([gc.parse(e, domain.symbols) for e in contract["nondegeneracy_conditions"]])
    return {"checked": True, "passed": all(e == "0" for e in residuals), "residuals": residuals,
            "primitive_operations": len(steps), "contract_id": contract["id"] if contract else None,
            "seconds": time.perf_counter()-started, "method": "primitive_reexecution_and_relational_witness_certificate"}


def acquisition(training, config):
    started = time.perf_counter()
    corpus = []
    for i, result in enumerate(training):
        if not result["solved"] or not result["independent_replay"]["passed"]:
            continue
        def qualify(term):
            return gc.point(f"trace{i}_"+term["name"]) if term["op"] == "var" else {
                "op": term["op"], "args": [qualify(a) for a in term["args"]]}
        corpus.append({"id": digest(result["proof"]), "program": qualify(result["proof"]["term"]),
                       "source_proof": digest(result["proof"]), "task_sha256": result["task_sha256"]})
    def admissible(template):
        try:
            body = gc.body_from_template(template)
            return config["min_steps"] <= len(gc.dag(body)[0]) <= config["max_steps"]
        except ValueError:
            return False
    with library.grammar(gc.validate):
        proposals = library.candidates(corpus, pairs=config["pairs"], limit=config["max_parameters"])
        compression = library.learn(corpus, pairs=config["pairs"], limit=config["max_parameters"],
            keep=config["capacity"], admissible=admissible)
        accepted, rejected = [], []
        for entry in proposals["candidates"]:
            if not admissible(entry["template"]):
                continue
            sources = []
            for c in corpus:
                matches = library.match_sites(entry["template"], c["program"])
                if matches:
                    sources.append({**{k: c[k] for k in ("source_proof", "task_sha256")},
                                    "matches": matches})
            if len({s["task_sha256"] for s in sources}) < 2:
                continue
            body = gc.body_from_template(entry["template"])
            try:
                h, cost = gc.certify_body(body)
                utility = library.utility(corpus, entry["template"], index=-1)
                h.update(source_proof_traces=sources, acquisition_cost=cost,
                         template=entry["template"], acquisition_utility_bits=utility["utility_bits"])
                accepted.append(h)
            except ValueError as exc:
                rejected.append({"template": entry["template"], "reason": str(exc)})
    accepted.sort(key=lambda h: (-len(h["source_proof_traces"]), -h["acquisition_utility_bits"], h["id"]))
    active = accepted[:config["capacity"]]
    compressed_bodies = {digest(gc.body_from_template(r["template"])) for r in compression["ranked"]
                         if r["verdict"]["utility_bits"] > 0}
    return {"corpus": corpus, "archive": accepted, "active": active, "rejected": rejected,
            "proposals": proposals, "existing_library_compression": compression,
            "compression_active": [h for h in accepted if digest(h["body"]) in compressed_bodies],
            "wall_seconds": time.perf_counter()-started,
            "selection_rule": "training source count, acquisition compression, content hash; fixed capacity",
            "novelty": "existing anti-unification; new adapter is not claimed as a new learning algorithm"}


def run_contract_geometry(config, output):
    """Normal-entry fixed train/acquire/freeze/evaluate protocol."""
    def write(name, value):
        (output/name).write_text(json.dumps(value, indent=2)+"\n", encoding="utf-8")
    def run(task, label, contracts=(), mode="certified"):
        def emit(event):
            with (output/"events.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps({"phase": label, "task": task["id"], **event})+"\n")
        result = solve(task, config["search"], contracts, mode=mode, emit=emit)
        result["independent_replay"] = independent_replay(result)
        result["false_proofs"] = int(result["solved"] and not result["independent_replay"]["passed"])
        print(json.dumps({"phase": label, "task": task["id"], "solved": result["solved"],
                          "expansions": result["costs"].get("candidate_expansions", 0)}), flush=True)
        return result
    write("frozen-plan.json", config)
    if set(task_identity(t) for t in config["training"]) & set(task_identity(t) for t in config["evaluation"]):
        raise ValueError("training and evaluation overlap")
    training = []
    for task in config["training"]:
        training.append(run(task, "training"))
        write("training.json", training)
    learned = acquisition(training, config["acquisition"])
    write("acquisition.json", learned)
    write("archive.json", learned["archive"])
    write("frozen-library.json", learned["active"])
    frozen_hash = digest(learned["active"])
    comparisons = {}
    for label, contracts, mode in [
        ("primitive_only", [], "primitive"),
        ("syntactic_macro", learned["active"], "primitive"),
        ("library_compression", learned["compression_active"], "primitive"),
        ("certified_morphism", learned["active"], "certified"),
    ]:
        comparisons[label] = [run(t, label, contracts, mode) for t in config["evaluation"]]
        write("comparisons.json", comparisons)
    uses = Counter(h for r in comparisons["certified_morphism"] for h in r["goal_acquired_calls"])
    excluded = sorted(uses, key=lambda h: (-uses[h], h))[:1]
    comparisons["ablation"] = [run(t, "ablation", [h for h in learned["active"] if h["id"] not in excluded])
                                for t in config["evaluation"]]
    write("comparisons.json", comparisons)
    causal = []
    for base, ablated in zip(comparisons["certified_morphism"], comparisons["ablation"], strict=True):
        causal.append({"task": base["task"]["id"], "lost_solve": base["solved"] and not ablated["solved"],
            "additional_expansions": ablated["costs"].get("candidate_expansions", 0)-base["costs"].get("candidate_expansions", 0),
            "longer_proof": bool(base["solved"] and ablated["solved"] and ablated["proof_length"] > base["proof_length"])})
    summary = {label: {"solved": sum(r["solved"] for r in rows), "tasks": len(rows),
        "false_proofs": sum(r["false_proofs"] for r in rows),
        "candidate_expansions": sum(r["costs"].get("candidate_expansions", 0) for r in rows),
        "primitive_equivalent_operations": sum(r["costs"].get("primitive_equivalent_operations", 0) for r in rows),
        "wall_seconds": sum(r["wall_seconds"] for r in rows),
        "contract_check_seconds": sum(r["costs"].get("contract_check_seconds", 0) for r in rows),
        "independent_replay_seconds": sum(r["independent_replay"].get("seconds", 0) for r in rows),
        "registration_certification_seconds": sum(r["costs"].get("archive_replay_seconds", 0) for r in rows),
        "registration_prover_calls": sum(r["costs"].get("archive_replay_prover_calls", 0) for r in rows),
        "goal_prover_calls": sum(r["costs"].get("goal_prover_calls", 0) for r in rows),
        "acquired_morphism_calls": sum(r["costs"].get("acquired_morphism_calls", 0) for r in rows),
        "successful_acquired_applications": sum(r["costs"].get("successful_acquired_applications", 0) for r in rows),
        "rejected_acquired_applications": sum(r["costs"].get("rejected_acquired_applications", 0) for r in rows),
        "goal_acquired_calls": sum(len(r["goal_acquired_calls"]) for r in rows)} for label, rows in comparisons.items()}
    result = {"execution_completed": True, "scope": gc.SCOPE, "plan_sha256": digest(config),
        "archive_sha256": digest(learned["archive"]), "frozen_library_sha256": frozen_hash,
        "library_unchanged": frozen_hash == digest(learned["active"]), "summary": summary,
        "acquired_count": len(learned["archive"]), "active_count": len(learned["active"]),
        "ablation_excluded": excluded, "causal_comparison": causal,
        "acquisition_seconds": learned["wall_seconds"],
        "acquisition_certification_seconds": sum(h["acquisition_cost"]["certification_seconds"] for h in learned["archive"]),
        "minimal_chain_passed": bool(uses and any(c["lost_solve"] or c["additional_expansions"] > 0 or c["longer_proof"] for c in causal)
            and not any(r["false_proofs"] for rows in comparisons.values() for r in rows)),
        "new_algorithm_claimed": False, "external_prover_used": False,
        "scope_note": "unseen construction specifications, not an olympiad theorem-solving benchmark"}
    write("result.json", result)
    return result
