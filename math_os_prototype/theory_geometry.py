"""Geometry adapter: existing MORTRA constructors, Newclid DDARN and exact bridge.

No question-specific rules, auxiliary points or learned routes are supplied.
Numeric construction filters are not certificates. Acceptance requires the
existing symbolic verifier on both the original and augmented statements.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from itertools import combinations
import json
import time

import numpy as np

from math_os_prototype.representation_progress import digest
from math_os_prototype.runtime_typed_planner import PrimitiveResult
from worker.backend.typed_geometry_stalk import DEFAULT_POINT_FAMILIES, enumerate_typed_candidates


class GeometryDomain:
    sort = "GeometryState"

    def __init__(self, task, config, emit=lambda event: None):
        from newclid.jgex.formulation import JGEXFormulation
        from newclid.jgex.constructions import ALL_JGEX_CONSTRUCTIONS
        from newclid.jgex.definition import JGEXDefinition
        from worker.backend.newclid_sympy_ar_compat import install_variadic_diff_compat
        install_variadic_diff_compat()
        self.config, self.task, self.emit = config, task, emit
        self.formulation = JGEXFormulation.from_text(task["statement"])
        if self.formulation.auxiliary_clauses:
            raise ValueError("Input contains supplied auxiliary clauses")
        if len(self.formulation.goals) != 1:
            raise ValueError("This adapter certifies exactly one nonempty goal")
        declared = list(dict.fromkeys(str(p) for c in self.formulation.setup_clauses for p in c.points))
        self.name_mapping = {name: f"p{i}" for i, name in enumerate(declared)}
        self.formulation = self.formulation.renamed(self.name_mapping)
        self.definitions = JGEXDefinition.to_dict(ALL_JGEX_CONSTRUCTIONS)
        self.families = tuple(f.name for f in DEFAULT_POINT_FAMILIES)
        self.registry = {f.name: f for f in DEFAULT_POINT_FAMILIES}
        self.events = []
        self.costs = Counter()
        self.root = None
        self.stage = "formalization"

    def log(self, **event):
        self.events.append(event)
        self.emit(event)

    def contract(self, family):
        definition = self.definitions[family]
        return {"name": family, "source_types": ["Point"] * self.registry[family].input_arity,
                "target_types": ["Point"], "preconditions": str(definition.requirements),
                "produced_relations": [str(c) for c in definition.clauses],
                "proof_obligations": "construction equations and nondegeneracy; original goal",
                "certificate": "exact polynomial quotient replay on the declared regular locus",
                "definition": definition.model_dump(mode="json")}

    def key(self, state):
        # Include the entire path/diagram, not only goal truth or point count.
        return digest({k: state[k] for k in ("statement", "problem", "relations")})

    def initial(self):
        if self.root is None:
            from newclid.jgex.problem_builder import JGEXProblemBuilder
            start = time.perf_counter()
            problem = JGEXProblemBuilder(rng=self.config["seed"], problem=self.formulation).build(
                max_attempts_to_satisfy_goals_numerically=3)
            if "diagram_similarity" in self.config:
                from newclid.symbols.points_registry import Point
                from newclid.numerical.geometries import PointNum
                scale, dx, dy = self.config["diagram_similarity"]
                if scale <= 0:
                    raise ValueError("Similarity requires positive scale")
                problem = problem.model_copy(update={"points": tuple(Point(name=p.name,
                    num=PointNum(x=scale*p.num.x+dx, y=scale*p.num.y+dy)) for p in problem.points)})
            self.costs["formalization_seconds"] += time.perf_counter()-start
            self.stage = "deduction"
            self.root = self.close(problem, str(self.formulation), [])
            self.log(event="initial", state_key=self.key(self.root), state=self.root)
        return self.root

    def close(self, problem, statement, path):
        from newclid.api import GeometricSolverBuilder, PythonDefault
        from newclid.problem import predicate_to_construction
        from newclid.proof_data import proof_data_from_state
        from worker.backend.newclid_mapping_compat import ValidatedMappingMatcher
        start = time.perf_counter()
        solver = GeometricSolverBuilder(rng=self.config["seed"], api_default=PythonDefault(False))
        matcher = ValidatedMappingMatcher()
        solver = solver.with_rule_matcher(matcher)
        # The pinned optional SymPy AR emits deductions whose premises cannot
        # always be recovered. Use its existing pure symbolic closure, retaining
        # independent exact algebraic verification as the acceptance gate.
        solver = solver.with_deductors([]).build(problem)
        proof = solver.proof_state
        if len(proof.goals) != len(problem.goals):
            raise ValueError("Deductor dropped an input goal")
        exhausted = False
        steps = 0
        for steps in range(1, self.config["closure_steps"] + 1):
            if not solver.deductive_agent.step(proof, solver.rules):
                exhausted = not proof.check_goals()
                break
        solved = proof.check_goals()
        self.costs["closure_seconds"] += time.perf_counter()-start
        self.costs["closure_rule_steps"] += steps
        self.costs["closure_calls"] += 1
        relations = sorted(str(predicate_to_construction(p)) for p in proof.graph.hyper_graph)
        state = {"problem": problem.model_dump(mode="json"), "statement": statement,
                 "relations": relations, "path": path, "deduction_proved": solved,
                 "closure_exhausted": exhausted, "closure_steps": steps,
                 "unsupported_rules": sorted(matcher.unsupported),
                 "deduction_mode": "Newclid symbolic DD; optional SymPy AR disabled",
                 "certified": False, "proof": None, "certificates": []}
        if solved:
            data = proof_data_from_state(list(problem.goals), proof)
            state["proof"] = data.model_dump(mode="json")
            start = time.perf_counter()
            try:
                # Auxiliary existence must not silently restrict the original
                # theorem. Certify the original statement independently too.
                for source in dict.fromkeys([str(self.formulation), statement]):
                    state["certificates"].append(self.certify(source))
                state["certified"] = all(c["accepted"] for c in state["certificates"])
            except (ValueError, NotImplementedError) as exc:
                state["certificate_failure"] = str(exc)
            self.costs["certification_seconds"] += time.perf_counter()-start
        return state

    def certify(self, statement):
        from worker.backend.jgex_exact_constraint_bridge import lower_jgex_to_exact_obligation
        obligation = lower_jgex_to_exact_obligation(statement,
            enable_affine_local_lemmas=False, enable_structural_lemmas=False)
        self.costs["exact_prover_calls"] += 1
        accepted = (obligation.exact_replay and obligation.remainder == "0"
                    and not obligation.vacuous_unit_ideal
                    and not obligation.untransported_nonzero_conditions)
        return {"statement": statement, "accepted": accepted, "obligation": asdict(obligation)}

    def objects(self, state):
        names = [p["name"] for p in state["problem"]["points"]]
        # Incidence objects refer to existing point arguments. They are not
        # extra geometric assumptions or automatically constructed centers.
        return {"Point": names, "Line": [list(p) for p in combinations(names, 2)],
                "Circle": [r.split()[1:] for r in state["relations"] if r.startswith("cyclic ")]}

    def candidates(self, family, state):
        names = [p["name"] for p in state["problem"]["points"]]
        graph = {name: set() for name in names}
        for relation in state["relations"] + state["problem"]["assumptions"]:
            tokens = relation.split() if isinstance(relation, str) else relation["string"].split()
            points = set(tokens[1:]) & set(names)
            for left, right in combinations(points, 2):
                graph[left].add(right)
                graph[right].add(left)
        goals = Counter(p for g in self.formulation.goals for p in str(g).split()[1:])
        generated = {step["output"] for step in state["path"]}
        rows = enumerate_typed_candidates(points=names, graph=graph, goal_multiplicity=goals,
            generated_points=generated, families=[self.registry[family]],
            used_keys={step["key"] for step in state["path"]},
            per_family_limit=self.config["per_family_limit"], ranking="structural",
            seed=self.config["seed"])
        self.log(event="enumerate", state_key=self.key(state), family=family,
                 input_points=names, input_relations=state["relations"],
                 candidates=[{"family": c.family, "inputs": c.inputs, "key": c.key} for c in rows])
        return rows

    def alternatives(self, family, state):
        for candidate in self.candidates(family, state):
            yield lambda candidate=candidate: self.apply(state, candidate)

    def apply(self, state, candidate):
        from newclid.problem import ProblemSetup
        from newclid.jgex.clause import JGEXClause
        from newclid.jgex.to_newclid import add_clause_to_problem
        start = time.perf_counter()
        names = {p["name"] for p in state["problem"]["points"]}
        index = len(names)
        while f"aux{index}" in names:
            index += 1
        output = f"aux{index}"
        step = {"family": candidate.family, "inputs": list(candidate.inputs),
                "output": output, "key": candidate.key}
        clause = f"{output} = {step['family']} {output} {' '.join(step['inputs'])}"
        self.costs["morphism_applications"] += 1
        seed = int(digest([self.config["seed"], state["path"], step])[:8], 16)
        try:
            problem = ProblemSetup.model_validate(state["problem"])
            updated, _ = add_clause_to_problem(problem, JGEXClause.from_str(clause)[0],
                                               self.definitions, np.random.default_rng(seed), 5)
        except Exception as exc:
            self.costs["construction_seconds"] += time.perf_counter()-start
            self.log(event="rejected_construction", parent=self.key(state), action=step,
                     reason=type(exc).__name__+": "+str(exc))
            return None
        self.costs["construction_seconds"] += time.perf_counter()-start
        setup, goal = state["statement"].split("?", 1)
        statement = setup.strip()+"; "+clause+" ? "+goal.strip()
        child = self.close(updated, statement, [*state["path"], step])
        event = {"event": "apply", "parent": self.key(state), "child": self.key(child),
                 "action": step, "contract": self.contract(step["family"]),
                 "produced_assumptions": [a for a in child["problem"]["assumptions"]
                    if a not in state["problem"]["assumptions"]],
                 "new_relations": sorted(set(child["relations"])-set(state["relations"])),
                 "state": child}
        self.log(**event)
        return PrimitiveResult(child, {k: v for k, v in event.items() if k != "state"})

    def is_goal(self, state):
        return state["certified"]

    def replay(self, state):
        other = GeometryDomain(self.task, self.config)
        current = other.initial()
        for expected in state["path"]:
            candidates = other.candidates(expected["family"], current)
            candidate = next((c for c in candidates if c.key == expected["key"]), None)
            if candidate is None:
                return {"passed": False, "reason": "recorded action not generatable"}
            result = other.apply(current, candidate)
            if result is None:
                return {"passed": False, "reason": "recorded action not applicable"}
            current = result.value
        passed = (other.key(current) == self.key(state) and current["certified"]
                  and current["certificates"] == state["certificates"])
        return {"passed": passed, "costs": dict(other.costs), "state_key": other.key(current)}


def run_geometry_theory(config, output):
    """Normal-entry adapter orchestration; action selection stays in the planner."""
    import traceback
    from importlib.metadata import distributions
    from math_os_prototype.theory_action_domain import search_action_domain

    def write(name, value):
        (output/name).write_text(json.dumps(value, indent=2)+"\n", encoding="utf-8")

    def emit(event):
        with (output/"events.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(event)+"\n")

    write("dependencies.json", {d.metadata["Name"]: d.version for d in distributions()})
    start = time.perf_counter()
    domain = None
    try:
        domain = GeometryDomain(config["task"], config["search"], emit)
        write("morphisms.json", [domain.contract(f) for f in domain.families])
        write("name-mapping.json", domain.name_mapping)
        plan = search_action_domain(domain, max_depth=config["search"]["max_depth"],
                                    max_states=config["search"]["max_states"])
        goal = plan.goals.get(domain.sort)
        state = goal.value if goal else domain.initial()
        write("state.json", state)
        write("proof-program.json", plan.proof_program)
        write("objects.json", domain.objects(state))
        replay = domain.replay(state) if goal else {"passed": False, "reason": "no certified goal"}
        write("replay.json", replay)
        result = {"execution_completed": True, "proved": bool(goal) and replay["passed"],
                  "initial_deduction_proved": domain.initial()["deduction_proved"],
                  "initial_closure_exhausted": domain.initial()["closure_exhausted"],
                  "morphism_applications": domain.costs["morphism_applications"],
                  "explored_states": len(plan.facts), "charged_applications": plan.states_explored-1,
                  "auxiliary_count": len(state["path"]) if goal else 0,
                  "proof_length": state["proof"]["proof_length"] if goal else None,
                  "replay_passed": replay["passed"], "costs": dict(domain.costs),
                  "status": "proved" if goal else "budget_or_finite_candidate_exhaustion",
                  "false_proofs": 0, "llm_calls": 0,
                  "acquired_morphisms_used": 0,
                  "acquired_transfer": "not evaluated: no verified acquired geometry library connected"}
    except Exception as exc:
        write("failure.json", {"traceback": traceback.format_exc()})
        result = {"execution_completed": False, "proved": False, "false_proofs": 0,
                  "status": "formalization_failure" if domain is None or domain.stage == "formalization" else "solver_failure",
                  "error": type(exc).__name__+": "+str(exc)}
    result["wall_seconds"] = time.perf_counter()-start
    return result
