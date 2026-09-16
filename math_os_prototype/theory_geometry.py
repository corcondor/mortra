"""Geometry adapter: existing constructors/planner and internal exact bridge.

No question-specific rules, auxiliary points or learned routes are supplied.
Numeric construction filters are not certificates. Acceptance requires the
existing symbolic verifier and a scope-preserving extension check whenever
only the augmented statement is proved.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from itertools import combinations, islice
import json
import time

import numpy as np
from sympy.polys.polyerrors import CoercionFailed, PolynomialError

from math_os_prototype.representation_progress import digest
from math_os_prototype.runtime_typed_planner import PrimitiveResult
from worker.backend.typed_geometry_stalk import DEFAULT_POINT_FAMILIES, TypedConstructionCandidate, enumerate_typed_candidates


def relation_key(relation):
    tokens = relation.split()
    if tokens[0] == "coll":
        return "coll "+" ".join(sorted(tokens[1:]))
    if tokens[0] == "cong" and len(tokens) == 5:
        pairs = sorted([sorted(tokens[1:3]), sorted(tokens[3:5])])
        return "cong "+" ".join(p for pair in pairs for p in pair)
    return relation


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
        requested = config.get("construction_families", self.families)
        if not requested or not set(requested) <= set(self.registry):
            raise ValueError("nonempty existing construction family selection required")
        self.families = tuple(dict.fromkeys(requested))
        self.registry = {f: self.registry[f] for f in self.families}
        self.events = []
        self.costs = Counter()
        self.certificate_cache = {}
        self.extension_cache = {}
        self.native_candidate_cache = {}
        self.native_connected = config.get("deduction_backend", "exact") == "exact"
        if self.native_connected:
            from worker.backend.jgex_native_interfaces import native_rule_theorems, typed_construction_contracts, formulation_goal_atoms
            from worker.backend.symbolic_sheaf_coordination import RuleClosureAdapter
            self.native_theorems = native_rule_theorems()
            self.native_contracts = typed_construction_contracts(tuple(self.registry.values()))
            predicates = sorted({a.predicate for t in self.native_theorems for a in (*t.premises, t.conclusion)})
            self.native_rules = RuleClosureAdapter("mortra-native-rules", self.native_theorems,
                imports=predicates, exports=predicates,
                max_certificates_per_round=max(1, config.get("per_family_limit", 8)))
            self.native_goal = formulation_goal_atoms(self.formulation)[0]
            self.log(event="native_registry", constructors=list(self.families), predicates=predicates,
                rule_count=len(self.native_theorems), rules_sha256=digest([asdict(t) for t in self.native_theorems]),
                knowledge_origin="existing declarative rule bank; not run-acquired", external_deductor=False)
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

    def close(self, problem, statement, path, inherited=None):
        if self.config.get("deduction_backend", "exact") == "exact":
            return self.close_exact(problem, statement, path, inherited)
        if self.config.get("deduction_backend", "python") == "yuclid":
            return self.close_native(problem, statement, path)
        if self.config.get("deduction_backend", "python") != "python":
            raise ValueError("Unknown geometry deduction backend")
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
        return self.certify_solved(state)

    def close_exact(self, problem, statement, path, inherited=None):
        """Bounded consequence discovery, using the existing certificate engine.

        Newclid supplies parsing/construction only. Neither its deductive agent
        nor Yuclid participates. The original and augmented goal remain separate
        obligations, so an auxiliary cannot silently strengthen the theorem.
        """
        start = time.perf_counter()
        assumptions = sorted(str(a) for a in problem.assumptions)
        inherited = inherited or {}
        state = {"problem": problem.model_dump(mode="json"), "statement": statement,
            "relations": sorted(set(assumptions) | set(inherited.get("relations", []))),
            "relation_certificates": dict(inherited.get("relation_certificates", {})),
            "path": path, "deduction_proved": False, "certified": False,
            "closure_exhausted": False, "closure_steps": 0,
            "deduction_mode": "MORTRA exact polynomial certificates",
            "proof": None, "certificates": []}
        self.certify_solved(state, require_deduction=False)
        state["deduction_proved"] = state["certified"]
        before = list(state["relations"])
        if state["certified"]:
            goal = statement.split("?", 1)[1].strip()
            state["relations"] = sorted(set(state["relations"]) | {goal})
            state["relation_certificates"][goal] = state["certificates"][-1]
            state["proof"] = {"proof_length": sum(
                len(c["obligation"]["quotient_certificate"]) +
                len(c["obligation"]["local_lemma_certificates"]) + 1
                for c in state["certificates"] if c["accepted"]), "unit": "algebraic certificate components"}
        # Keep the first vocabulary conservative: no directed-angle/branch
        # recognition is invented here. Other existing goal semantics still work.
        limit = min(self.config.get("closure_steps", 1000), self.config["per_family_limit"])
        attempted = []
        from worker.backend.geometry_proof_hypergraph import Atom
        facts = frozenset(Atom(r.split()[0], tuple(r.split()[1:])).canonical() for r in state["relations"])
        proposal = self.native_rules.propose(facts, self.native_goal, round_index=len(path))
        native = {}
        for item in proposal.certificates:
            if self.native_rules.verify(item, facts):
                relation = relation_key(" ".join((item.conclusion.predicate, *item.conclusion.arguments)))
                native[relation] = item
        self.costs["native_rule_proposals"] += len(proposal.certificates)
        self.log(event="native_rule_proposals", path=path, proposals=[asdict(c) for c in proposal.certificates],
                 verified_instances=len(native))
        candidates = list(dict.fromkeys([*native, *self.relation_candidates(state, limit)]))[:limit]
        for relation in candidates:
            source = statement.split("?", 1)[0].strip()+" ? "+relation
            certificate = self.certify(source)
            # A relation must not add assumptions beyond the current chart.
            allowed = {condition for c in state["certificates"]
                for key in ("normalization_assumptions", "nondegeneracy_conditions")
                for condition in c.get("obligation", {}).get(key, [])}
            required = {condition for key in ("normalization_assumptions", "nondegeneracy_conditions")
                for condition in certificate.get("obligation", {}).get(key, [])}
            accepted = certificate["accepted"] and required <= allowed
            attempted.append(relation)
            self.log(event="exact_relation_check", path=path, relation=relation,
                accepted=accepted, additional_conditions=sorted(required-allowed),
                certificate=certificate, rule_instance=asdict(native[relation]) if relation in native else None)
            if accepted:
                state["relations"].append(relation)
                state["relation_certificates"][relation] = certificate
                self.costs["certified_new_relations"] += 1
                self.costs["native_rule_relations_certified"] += int(relation in native)
        state["relations"] = sorted(set(state["relations"]))
        state["relations_before_exact_closure"] = before
        state["closure_steps"] = len(attempted)
        state["closure_stop_reason"] = "bounded_relation_candidates_checked"
        self.costs["closure_calls"] += 1
        self.costs["closure_seconds"] += time.perf_counter()-start
        self.log(event="exact_closure", state_key=self.key(state), path=path,
            assumptions=assumptions, checked_relations=attempted,
            certified_relations=sorted(set(state["relations"])-set(before)),
            goal_certified=state["certified"], stop_reason=state["closure_stop_reason"])
        return state

    def relation_candidates(self, state, limit):
        """Local, lazy candidate enumeration, not all n^8 relation tuples."""
        names = {p["name"] for p in state["problem"]["points"]}
        goals = list(dict.fromkeys(p for g in self.formulation.goals
            for p in str(g).split()[1:] if p in names))
        recent = ([state["path"][-1]["output"], *state["path"][-1]["inputs"]]
                  if state["path"] else [])
        core = set(recent+goals)
        neighbors = set()
        for relation in state["relations"]:
            support = set(relation.split()[1:]) & names
            if support & core:
                neighbors.update(support)
        points = list(dict.fromkeys(recent+goals+sorted(neighbors)))[:8]
        # Collinearity and squared-distance equality have exact polynomial
        # semantics even with coinciding coordinates. Do not infer cyclicity
        # from its determinant without separately proving noncollinearity.
        streams = [iter("coll "+" ".join(p) for p in combinations(points, 3)),
            iter("cong "+" ".join(a+b) for a, b in combinations(list(combinations(points, 2)), 2))]
        seen = {relation_key(r) for r in state["relations"]}
        result = []
        while streams and len(result) < limit:
            remaining = []
            for stream in streams:
                # Bound rejected/duplicate scans too, not only proof calls.
                for relation in islice(stream, max(1, limit)):
                    relation = relation_key(relation)
                    if relation not in seen:
                        result.append(relation)
                        seen.add(relation)
                        remaining.append(stream)
                        break
                if len(result) >= limit:
                    break
            streams = remaining
        return result

    def close_native(self, problem, statement, path):
        import hashlib
        import os
        from pathlib import Path
        import sys
        from worker.backend.yuclid_native_verifier import verify_problem
        start = time.perf_counter()
        binary = Path(sys.executable).with_name("yuclid.exe" if os.name == "nt" else "yuclid")
        if not binary.is_file():
            raise FileNotFoundError("Install the declared py-yuclid dependency in this environment")
        # The existing upstream wrapper resolves its binary from PATH at import.
        os.environ["PATH"] = str(binary.parent)+os.pathsep+os.environ.get("PATH", "")
        result = verify_problem(problem, yuclid_exe=binary,
            ar_profile=self.config["ar_profile"],
            timeout_seconds=self.config["closure_timeout_seconds"])
        self.costs["closure_seconds"] += time.perf_counter()-start
        self.costs["closure_calls"] += 1
        self.costs["closure_deductions"] += result.all_deduction_count
        relations = {str(a) for a in problem.assumptions}
        for deduction in result.payload.get("all_deductions", []):
            for assertion in deduction.get("assertions", []):
                relations.add(" ".join([assertion["name"], *map(str, assertion["points"])]))
        state = {"problem": problem.model_dump(mode="json"), "statement": statement,
            "relations": sorted(relations), "path": path, "deduction_proved": result.solved,
            "closure_exhausted": result.status == "saturated", "closure_steps": None,
            "deduction_mode": "Yuclid DD/AR", "ar_profile": self.config["ar_profile"],
            "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
            "native_input_sha256": result.input_sha256,
            "certified": False, "certificates": [],
            "proof": {"proof_length": result.goal_deduction_count, "native": result.payload}}
        return self.certify_solved(state)

    def certify_solved(self, state, *, require_deduction=True):
        if not require_deduction or state["deduction_proved"]:
            start = time.perf_counter()
            try:
                # Auxiliary existence must not silently restrict the original
                # theorem. Certify the original statement independently too.
                for source in dict.fromkeys([str(self.formulation), state["statement"]]):
                    state["certificates"].append(self.certify(source))
                state["certified"] = all(c["accepted"] for c in state["certificates"])
                state["certification_route"] = "original_and_augmented_exact"
                if not state["certified"] and state["certificates"][-1]["accepted"]:
                    extension = self.certify_extension(str(self.formulation), state["statement"])
                    state["extension_certificate"] = extension
                    state["certified"] = extension["accepted"]
                    state["certification_route"] = "augmented_exact_with_conservative_extension"
            except (ValueError, NotImplementedError) as exc:
                state["certificate_failure"] = str(exc)
            self.costs["certification_seconds"] += time.perf_counter()-start
        return state

    def certify_extension(self, original, augmented):
        """Check a rational chart extension without re-proving the original goal.

        Reuse the bridge's elaborator and exact arithmetic. No new variables,
        constraints, old coordinates, or unproved regularity may be introduced.
        Other extension types are refused, not assumed conservative.
        """
        cache_key = digest([original, augmented])
        if cache_key in self.extension_cache:
            self.costs["extension_cache_hits"] += 1
            return self.extension_cache[cache_key]
        from newclid.jgex.formulation import JGEXFormulation
        from worker.backend.jgex_exact_constraint_bridge import _prepare_exact_system
        from math_os_prototype.geometry_contracts import exact_zero, factors
        import sympy as sp
        start = time.perf_counter()
        result = {"accepted": False, "kind": "rational_chart_conservative_extension",
                  "original_sha256": digest(original), "augmented_sha256": digest(augmented)}
        try:
            base_form, aug_form = map(JGEXFormulation.from_text, (original, augmented))
            prefix = len(base_form.setup_clauses)
            if (base_form.goals != aug_form.goals or base_form.auxiliary_clauses or aug_form.auxiliary_clauses
                    or tuple(base_form.setup_clauses) != tuple(aug_form.setup_clauses[:prefix])):
                raise ValueError("not an extension of the identical source and goal")
            base, *_, base_goal, base_eqs, base_vars = _prepare_exact_system(
                original, enable_structural_lemmas=False)
            extended, *_, aug_goal, aug_eqs, aug_vars = _prepare_exact_system(
                augmented, enable_structural_lemmas=False)
            if tuple(base_vars) != tuple(aug_vars):
                raise ValueError("extension introduces free or algebraic variables")
            if base.normalization_assumptions != extended.normalization_assumptions:
                raise ValueError("extension changes the normalization scope")
            checks = []
            def check(value):
                self.costs["extension_identity_checks"] += 1
                ok = exact_zero(value)
                checks.append(ok)
                return ok
            if not check(base_goal-aug_goal):
                raise ValueError("extension changes the original goal polynomial")
            for name, coordinates in base.coordinates.items():
                if name not in extended.coordinates or not all(check(a-b) for a, b in
                        zip(coordinates, extended.coordinates[name], strict=True)):
                    raise ValueError("extension changes an original point")
            if len(aug_eqs) < len(base_eqs) or not all(check(a-b) for a, b in zip(base_eqs, aug_eqs)):
                raise ValueError("extension changes original constraints")
            if not all(check(e) for e in aug_eqs[len(base_eqs):]):
                raise ValueError("extension adds nontrivial constraints")
            # Gauge regularity is part of the original theorem's scope too.
            # Ignoring it refused, for example, a foot on the nonzero base of
            # a normalized triangle. Read only explicit polynomial != 0 rows.
            symbols = {str(s): s for xy in base.coordinates.values() for e in xy for s in e.free_symbols}
            from math_os_prototype.geometry_contracts import parse
            scope_nonzero = [parse(c.removesuffix(" != 0"), symbols)
                             for c in base.normalization_assumptions if c.endswith(" != 0")]
            known_factors = {f for e in [*base.denominators, *scope_nonzero] for f in factors(e)}
            required_factors = {f for e in extended.denominators for f in factors(e)}
            if not required_factors <= known_factors:
                raise ValueError("extension requires unproved nonzero conditions")
            added = {n: p for n, p in extended.coordinates.items() if n not in base.coordinates}
            for coords in added.values():
                for value in coords:
                    if not value.free_symbols <= set(base_vars) or value.has(sp.Float):
                        raise ValueError("extension is outside the rational chart fragment")
                    for part in sp.cancel(value).as_numer_denom():
                        if base_vars:
                            try:
                                sp.Poly(part, *base_vars, domain=sp.QQ)
                            except (sp.PolynomialError, sp.polys.polyerrors.CoercionFailed) as exc:
                                raise ValueError("nonrational extension witness") from exc
                        elif part.is_Rational is not True:
                            raise ValueError("nonrational constant extension witness")
            result.update(accepted=True, identity_checks=len(checks), all_residuals_zero=all(checks),
                point_witnesses={n: list(map(str, p)) for n, p in added.items()},
                original_regularity=sorted(known_factors), required_regularity=sorted(required_factors),
                scope="original explicit chart under its declared regularity; no new constraints or free variables")
        except (ValueError, NotImplementedError, CoercionFailed, PolynomialError) as exc:
            result["refusal_reason"] = str(exc)
        result["certificate_sha256"] = digest(result)
        self.costs["extension_certification_seconds"] += time.perf_counter()-start
        self.extension_cache[cache_key] = result
        self.log(event="extension_certificate", certificate=result)
        return result

    def certify(self, statement):
        from worker.backend.jgex_exact_constraint_bridge import lower_jgex_to_exact_obligation
        if statement in self.certificate_cache:
            self.costs["exact_certificate_cache_hits"] += 1
            return self.certificate_cache[statement]
        if self.config.get("proof_dsl"):
            from math_os_prototype.geometry_proof_dsl import search_exact_proof
            result = search_exact_proof(statement,
                budget=self.config.get("proof_dsl_budget", 64),
                emit=lambda event: self.log(**event),
                backend_limits=self.config.get("proof_backend_limits"))
            self.costs.update(result["proof_dsl_costs"])
            self.certificate_cache[statement] = result
            return result
        self.costs["exact_prover_calls"] += 1
        self.log(event="exact_check_started", statement=statement)
        start = time.perf_counter()
        try:
            obligation = lower_jgex_to_exact_obligation(statement,
                enable_affine_local_lemmas=False, enable_structural_lemmas=False)
        except (ValueError, NotImplementedError, CoercionFailed, PolynomialError) as exc:
            result = {"statement": statement, "accepted": False,
                      "unsupported": type(exc).__name__+": "+str(exc)}
            self.costs["unsupported_exact_checks"] += 1
            self.certificate_cache[statement] = result
            self.log(event="exact_check_completed", accepted=False, statement=statement,
                     seconds=time.perf_counter()-start, unsupported=result["unsupported"])
            return result
        accepted = (obligation.exact_replay and obligation.remainder == "0"
                    and not obligation.vacuous_unit_ideal
                    and not obligation.untransported_nonzero_conditions)
        result = {"statement": statement, "accepted": accepted, "obligation": asdict(obligation)}
        self.certificate_cache[statement] = result
        self.log(event="exact_check_completed", accepted=accepted, statement=statement,
                 certificate_sha256=obligation.certificate_sha256,
                 seconds=time.perf_counter()-start)
        return result

    def objects(self, state):
        names = [p["name"] for p in state["problem"]["points"]]
        # Incidence objects refer to existing point arguments. They are not
        # extra geometric assumptions or automatically constructed centers.
        return {"Point": names, "Line": [list(p) for p in combinations(names, 2)],
                "Circle": [r.split()[1:] for r in state["relations"] if r.startswith("cyclic ")]}

    def candidate_rows(self, family, state, relations):
        names = [p["name"] for p in state["problem"]["points"]]
        graph = {name: set() for name in names}
        for relation in relations + state["problem"]["assumptions"]:
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
        return rows

    def candidates(self, family, state):
        start = time.perf_counter()
        rows = self.candidate_rows(family, state, state["relations"])
        without = self.candidate_rows(family, state, state.get("relations_before_exact_closure", state["relations"]))
        changed = [(c.key, c.structural_rank) for c in rows] != [(c.key, c.structural_rank) for c in without]
        self.costs["candidate_generation_and_counterfactual_seconds"] += time.perf_counter()-start
        self.costs["relation_influenced_enumerations"] += int(changed)
        contract_rows = self.native_candidates(state) if self.native_connected else ()
        prioritized = [TypedConstructionCandidate(c.family, c.inputs, c.rank)
                       for c in contract_rows if c.family == family and c.executable]
        by_key = {c.key: c for c in prioritized}
        for c in rows:
            by_key.setdefault(c.key, c)
        rows = list(by_key.values())[:self.config["per_family_limit"]]
        self.log(event="enumerate", state_key=self.key(state), family=family,
                 native_relations_changed_ranking=changed,
                 native_contract_candidates=[c.key for c in prioritized],
                 without_new_relations=[{"key": c.key, "rank": c.structural_rank} for c in without],
                 input_points=[p["name"] for p in state["problem"]["points"]], input_relations=state["relations"],
                 candidates=[{"family": c.family, "inputs": c.inputs, "key": c.key, "rank": c.structural_rank} for c in rows])
        return rows

    def native_candidates(self, state):
        """Reuse the existing backward-obligation and construction compilers."""
        from worker.backend.geometry_proof_hypergraph import Atom, synthesize_backward_obligations, stratify_backward_obligations
        from worker.backend.typed_construction_contracts import synthesize_contract_candidates
        key = self.key(state)
        if key in self.native_candidate_cache:
            self.costs["native_candidate_cache_hits"] += 1
            return self.native_candidate_cache[key]
        start = time.perf_counter()
        limit = self.config["per_family_limit"]
        facts = tuple(Atom(r.split()[0], tuple(r.split()[1:])).canonical() for r in state["relations"])
        # Preserve the existing experiment's witness/ground branch policy.
        expanded = synthesize_backward_obligations(facts, self.native_goal, self.native_theorems,
            max_states_per_rule=192, max_results=limit * 4)
        obligations = stratify_backward_obligations(expanded, limit=limit, witness_fraction=0.25)
        names = [p["name"] for p in state["problem"]["points"]]
        candidates, audit = synthesize_contract_candidates(
            (a for o in obligations for a in o.open_premises), self.native_contracts,
            visible_entities=names, output_entity=self.next_output(state),
            used_keys={s["key"] for s in state["path"]},
            max_candidates_per_contract=limit, max_candidates_per_obligation=limit,
            obligation_branches=[o.open_premises for o in obligations], known_facts=facts,
            use_representation_atlas=False)
        self.costs["native_backward_compilation_seconds"] += time.perf_counter()-start
        self.costs["native_backward_obligations"] += len(obligations)
        self.costs["native_contract_candidates"] += len(candidates)
        self.native_candidate_cache[key] = candidates
        self.log(event="native_backward_compilation", state_key=key,
            input_relations=state["relations"],
            certified_relations_used=sorted({
                relation for relation in state.get("relation_certificates", {})
                if Atom(relation.split()[0], tuple(relation.split()[1:])).canonical()
                in {a for o in obligations for a in o.matched_premises}}),
            obligations=[asdict(o) for o in obligations], audit=asdict(audit),
            candidates=[asdict(c) for c in candidates])
        return candidates

    @staticmethod
    def next_output(state):
        names = {p["name"] for p in state["problem"]["points"]}
        index = len(names)
        while f"aux{index}" in names:
            index += 1
        return f"aux{index}"

    def alternatives(self, family, state):
        for candidate in self.candidates(family, state):
            yield lambda candidate=candidate: self.apply(state, candidate)

    def apply(self, state, candidate):
        from newclid.problem import ProblemSetup
        from newclid.jgex.clause import JGEXClause
        from newclid.jgex.to_newclid import add_clause_to_problem
        start = time.perf_counter()
        output = self.next_output(state)
        step = {"family": candidate.family, "inputs": list(candidate.inputs),
                "output": output, "key": candidate.key}
        if self.native_connected:
            matched = [c for c in self.native_candidates(state) if c.key == candidate.key and c.executable]
            step["native_contract_selected"] = bool(matched)
            step["native_plan_certificates"] = [c.plan_certificate_sha256 for c in matched]
            self.costs["native_contract_applications"] += bool(matched)
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
        child = self.close(updated, statement, [*state["path"], step], state)
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
                  "initial_goal_certified": domain.initial()["certified"],
                  "initial_closure_exhausted": domain.initial()["closure_exhausted"],
                  "morphism_applications": domain.costs["morphism_applications"],
                  "explored_states": len(plan.facts), "charged_applications": plan.states_explored-1,
                  "auxiliary_count": len(state["path"]) if goal else 0,
                  "proof_length": state["proof"]["proof_length"] if goal else None,
                  "replay_passed": replay["passed"], "costs": dict(domain.costs),
                  "status": "proved" if goal else "budget_or_finite_candidate_exhaustion",
                  "false_proofs": 0, "llm_calls": 0,
                  "native_exact_checks": domain.costs["exact_prover_calls"],
                  "native_rule_proposals": domain.costs["native_rule_proposals"],
                  "native_rule_relations_certified": domain.costs["native_rule_relations_certified"],
                  "native_backward_obligations": domain.costs["native_backward_obligations"],
                  "native_contract_candidates": domain.costs["native_contract_candidates"],
                  "native_contract_applications": domain.costs["native_contract_applications"],
                  "certified_new_relations": domain.costs["certified_new_relations"],
                  "relation_influenced_enumerations": domain.costs["relation_influenced_enumerations"],
                  "proof_length_unit": state["proof"].get("unit", "deductions") if goal else None,
                  "external_deduction_used": config["search"].get("deduction_backend", "exact") != "exact",
                  "acquired_morphisms_used": 0,
                  "acquired_transfer": "not evaluated: no verified acquired geometry library connected"}
    except Exception as exc:
        write("failure.json", {"traceback": traceback.format_exc()})
        result = {"execution_completed": False, "proved": False, "false_proofs": 0,
                  "status": "formalization_failure" if domain is None or domain.stage == "formalization" else "solver_failure",
                  "error": type(exc).__name__+": "+str(exc)}
    result["wall_seconds"] = time.perf_counter()-start
    return result
