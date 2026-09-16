"""Execute acquired Point morphisms in the existing symbolic geometry solver.

The bridge retains JGEX assumptions and goals. Numerical construction is only
a proposal filter. Every retained extension is checked by the existing exact
conservative-extension verifier; sampled coordinate equality is not accepted.
Learning reuses the existing semantic geometry library and abstraction code.
"""
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
from itertools import combinations, zip_longest
import json
import time

import numpy as np

from math_os_prototype import geometry_contracts as gc
from math_os_prototype import geometry_semantic_dsl as dsl
from math_os_prototype import library_compression as library
from math_os_prototype.representation_progress import digest
from math_os_prototype.runtime_typed_planner import PrimitiveResult
from math_os_prototype.theory_action_domain import search_action_domain
from math_os_prototype.theory_geometry import GeometryDomain
from math_os_prototype.theory_geometry_feedback import GeometryLibrary, acquire
from worker.backend.typed_geometry_stalk import (
    ConstructionFamily, EXTENDED_POINT_FAMILIES, iter_complete_typed_candidates,
)


def instantiate_call(h, inputs):
    if len(inputs) != len(h["parameters"]):
        raise ValueError("acquired morphism arity mismatch")
    return {"op": "use", "abstraction": h["id"],
            "arguments": {p["name"]: gc.point(n) for p, n in zip(h["parameters"], inputs, strict=True)}}


def compile_call(term, table, occupied):
    """Alpha-rename local binders; keep sharing, argument order and dependencies."""
    primitive = dsl.expand(term, table)
    steps, result = gc.dag(primitive, fragment=dsl.FRAGMENT)
    names = set(occupied)
    mapping, clauses, outputs = {}, [], []
    for step in steps:
        index = len(names)
        while f"aux{index}" in names:
            index += 1
        output = f"aux{index}"
        names.add(output)
        args = [mapping.get(n, n) for n in step["inputs"]]
        if not set(args) <= names:
            raise ValueError("unbound Point input")
        mapping[step["output"]] = output
        if step["family"] == "intersection_ll":
            # Same relational definition already used by FRAGMENT. The old
            # symbolic elaborator accepts the two loci, not this schema alias.
            clauses.append(f"{output} = on_line {output} {' '.join(args[:2])}, "
                           f"on_line {output} {' '.join(args[2:])}")
        else:
            clauses.append(f"{output} = {step['family']} {output} {' '.join(args)}")
        outputs.append((output, step["term"]))
    return clauses, mapping.get(result, result), primitive, outputs


def substitute_points(term, terms):
    if isinstance(term, dict) and term.get("op") == "var":
        return deepcopy(terms[term["name"]])
    if isinstance(term, dict):
        return {k: substitute_points(v, terms) for k, v in term.items()}
    if isinstance(term, list):
        return [substitute_points(v, terms) for v in term]
    return term


def alias_existing_points(original, primitive, outputs):
    """After proving full extension legality, reuse symbolically identical points.

    A Point-valued procedure may return an existing point. The numerical
    diagram builder only supports fresh, distinct constructed points.
    """
    from worker.backend.jgex_exact_constraint_bridge import _prepare_exact_system
    started = time.perf_counter()
    expected = _prepare_exact_system(original, enable_structural_lemmas=False)[0]
    steps, _ = gc.dag(primitive, fragment=dsl.FRAGMENT)
    bound, clauses, reduced_outputs, aliases = {}, [], [], []
    checks = 0
    for step, (output, term) in zip(steps, outputs, strict=True):
        inputs = [bound.get(n, n) for n in step["inputs"]]
        available = list(expected.coordinates)
        dsl.FRAGMENT.primitive(expected, step["family"], output, inputs)
        alias = None
        for name in available:
            checks += 2
            if all(gc.exact_zero(a-b) for a, b in zip(
                    expected.coordinates[output], expected.coordinates[name], strict=True)):
                alias = name
                break
        selected = alias or output
        bound[step["output"]] = selected
        reduced_outputs.append((selected, term))
        if alias:
            aliases.append({"output": output, "existing_point": alias,
                            "proof": "two exact coordinate identities in the source chart"})
            del expected.coordinates[output]
        elif step["family"] == "intersection_ll":
            clauses.append(f"{output} = on_line {output} {' '.join(inputs[:2])}, "
                           f"on_line {output} {' '.join(inputs[2:])}")
        else:
            clauses.append(f"{output} = {step['family']} {output} {' '.join(inputs)}")
    return clauses, reduced_outputs, {"aliases": aliases, "identity_checks": checks,
        "seconds": time.perf_counter()-started,
        "precondition": "the unabridged construction extension was certified first"}


def certify_compilation(original, augmented, primitive, outputs):
    """Compare DSL evaluation with the actual JGEX coordinates symbolically."""
    from worker.backend.jgex_exact_constraint_bridge import _prepare_exact_system
    before = _prepare_exact_system(original, enable_structural_lemmas=False)[0]
    after = _prepare_exact_system(augmented, enable_structural_lemmas=False)[0]
    expected = gc._JGEXElaborator()
    expected.coordinates.update(before.coordinates)
    steps, _ = gc.dag(primitive, fragment=dsl.FRAGMENT)
    # Local variables cannot shadow parameters or previously constructed points.
    bound = {}
    checks = []
    for step, (output, _) in zip(steps, outputs, strict=True):
        inputs = [bound.get(n, n) for n in step["inputs"]]
        dsl.FRAGMENT.primitive(expected, step["family"], output, inputs)
        bound[step["output"]] = output
        checks.extend(gc.exact_zero(a-b) for a, b in zip(
            expected.coordinates[output], after.coordinates[output], strict=True))
    certificate = {"method": "symbolic DSL/JGEX coordinate identities under extension scope",
                   "identity_checks": len(checks), "all_residuals_zero": all(checks),
                   "primitive_sha256": digest(primitive), "statement_sha256": digest(augmented)}
    certificate["sha256"] = digest(certificate)
    return certificate


class SymbolicDSLDomain(GeometryDomain):
    def __init__(self, task, config, bank, *, active=(), discover=False, emit=lambda e: None):
        # The old entry remains available for regression. This adapter adds
        # learned operations and complete binding streams, not a second solver.
        base = {k: v for k, v in config.items() if k != "construction_families"}
        super().__init__(task, base, emit)
        self.config = config
        self.bank, self.discover = bank, discover
        self.active = tuple(active)
        self.histories = []
        self.attempted = set()
        self.facts = None
        self.fair_state_streams = True
        self.sync()

    def sync(self):
        self.learned = {h["id"]: h for h in self.bank.archive if h["id"] in self.active}
        if set(self.active)-set(self.learned):
            raise ValueError("unregistered acquired morphism")
        available = {f.name: f for f in EXTENDED_POINT_FAMILIES if f.name in self.definitions}
        requested = self.config.get("construction_families", tuple(available))
        if not requested or set(requested)-set(available):
            raise ValueError("unknown or empty construction grammar")
        self.registry = {n: available[n] for n in requested}
        from worker.backend.jgex_native_interfaces import typed_construction_contracts
        self.native_contracts = typed_construction_contracts(tuple(self.registry.values()))
        from worker.backend.typed_construction_contracts import TypedConstructionContract
        from worker.backend.geometry_proof_hypergraph import Atom
        for h in self.learned.values():
            self.registry[h["id"]] = ConstructionFamily(h["id"], len(h["parameters"]),
                "ordered", allow_repeated_inputs=True)
            cert = h["exact_certificate"]
            names = {p["name"]: "?INPUT"+str(i) for i, p in enumerate(h["parameters"])}
            names[cert["output"]] = "?OUT"
            # Publish only effects whose entities cross the call boundary.
            # Other effects remain in the expanded construction and certificate.
            atoms = tuple(Atom(e["predicate"], tuple(names[p] for p in e["points"]))
                for e in h["effects"] if set(e["points"]) <= set(names)
                and not e["conditions"])
            guarded = bool(h["applicability"].get("input_nonzero_polynomials")) or any(
                g["parent_factors"] for g in h["applicability"].get("sequential_nonzero_polynomials", []))
            if atoms and not guarded:
                self.native_contracts += (TypedConstructionContract(self.registry[h["id"]],
                    "?OUT", tuple(names[p["name"]] for p in h["parameters"]), atoms),)
        self.families = tuple(self.registry)
        self.native_candidate_cache.clear()
        self.log(event="symbolic_dsl_registry", active=list(self.active),
                 constructors=list(self.registry), archive_sha256=digest(self.bank.archive),
                 solver="existing GeometryDomain and exact bridge", binding_enumeration="complete")

    def contract(self, family):
        if family in getattr(self, "learned", {}):
            h = self.learned[family]
            return {"name": family, "source_types": ["Point"]*len(h["parameters"]),
                    "target_types": ["Point"], "certificate": h["exact_certificate"],
                    "body": h["body"], "parents": h["parents"]}
        return super().contract(family)

    def initial(self):
        state = super().initial()
        if "terms" not in state:
            terms = {p["name"]: gc.point(p["name"]) for p in state["problem"]["points"]}
            for clause in self.formulation.setup_clauses:
                if len(clause.points) != 1 or len(clause.constructions) != 1:
                    continue
                construction = clause.constructions[0]
                family = dsl.FRAGMENT.canonical_family(str(construction.name))
                args = tuple(map(str, construction.args))
                output = str(clause.points[0])
                if (family in dsl.FRAGMENT.arities and args and args[0] == output
                        and len(args)-1 == dsl.FRAGMENT.arities[family]
                        and output not in args[1:]):
                    terms[output] = {"op": family, "args": [deepcopy(terms[n]) for n in args[1:]]}
            state["terms"] = terms
            self.log(event="initial_dsl_terms", terms=terms,
                     origin="constructions explicitly present in the input task, not acquired knowledge")
        return state

    def key(self, state):
        return digest([super().key(state), state.get("terms", {}), state.get("path", [])])

    def candidates(self, family, state):
        names = [p["name"] for p in state["problem"]["points"]]
        graph = {n: set() for n in names}
        for relation in state["relations"]:
            points = set(relation.split()[1:]) & set(names)
            for a, b in combinations(points, 2):
                graph[a].add(b)
                graph[b].add(a)
        # The backward compiler supplies an ordering prefix, never membership.
        from worker.backend.typed_geometry_stalk import TypedConstructionCandidate
        seen = set()
        for c in self.native_candidates(state):
            if c.family == family and c.executable and c.key not in seen:
                seen.add(c.key)
                yield TypedConstructionCandidate(c.family, c.inputs, c.rank)
        for c in iter_complete_typed_candidates(points=names, graph=graph,
                goal_multiplicity=Counter(self.native_goal.arguments),
                generated_points={s["output"] for s in state["path"]}, family=self.registry[family]):
            if c.key not in seen:
                yield c

    def is_goal(self, state):
        return not self.discover and super().is_goal(state)

    def alternatives(self, family, state):
        state_key = self.key(state)
        for candidate in self.candidates(family, state):
            key = (state_key, candidate.key)
            if key in self.attempted:
                continue
            def invoke(candidate=candidate, key=key):
                self.attempted.add(key)
                return self.apply(state, candidate)
            yield invoke

    def search(self, applications):
        self.sync()
        initial_count = len(self.facts) if self.facts is not None else 1
        plan = search_action_domain(self, max_depth=self.config["max_depth"],
            max_states=initial_count+applications, initial_facts=self.facts)
        self.facts = plan.facts
        return plan, plan.states_explored-initial_count

    def apply(self, state, candidate):
        from newclid.problem import ProblemSetup
        from newclid.jgex.clause import JGEXClause
        from newclid.jgex.to_newclid import add_clause_to_problem
        from newclid.jgex.errors import JGEXConstructionError
        start = time.perf_counter()
        names = {p["name"] for p in state["problem"]["points"]}
        if not set(candidate.inputs) <= names:
            raise ValueError("candidate refers to an unavailable Point")
        h = self.learned.get(candidate.family)
        semantic_family = dsl.FRAGMENT.canonical_family(candidate.family)
        if h:
            call = instantiate_call(h, candidate.inputs)
        else:
            call = {"op": semantic_family or candidate.family, "args": [gc.point(n) for n in candidate.inputs]}
        if h or semantic_family is not None:
            clauses, output, primitive, outputs = compile_call(call, self.bank.table, names)
        else:
            output = self.next_output(state)
            clauses = [f"{output} = {candidate.family} {output} {' '.join(candidate.inputs)}"]
            primitive, outputs = call, [(output, call)]
        self.costs["dsl_compile_seconds"] += time.perf_counter()-start
        operations = len(clauses)
        self.costs["morphism_applications"] += 1
        if self.costs["primitive_equivalent_operations"]+operations > self.config.get("max_primitive_operations", 6000):
            self.costs["primitive_budget_refusals"] += 1
            self.log(event="symbolic_dsl_resource_refusal", family=candidate.family,
                     reason="primitive_equivalent_operation_budget")
            return None
        self.costs["primitive_equivalent_operations"] += operations
        self.costs["acquired_applications"] += int(h is not None)
        step = {"family": candidate.family, "inputs": list(candidate.inputs), "key": candidate.key,
                "output": output, "outputs": [n for n, _ in outputs], "call": call,
                "clauses": clauses, "primitive_operations": operations}
        setup, goal = state["statement"].split("?", 1)
        statement = setup.strip()+"; "+"; ".join(clauses)+" ? "+goal.strip()
        # A numeric filter must never justify a guard. Check the symbolic
        # extension before giving its assumptions to deduction or learning.
        extension = self.certify_extension(state["statement"], statement)
        if not extension["accepted"]:
            self.costs["extension_refusals"] += 1
            self.log(event="symbolic_dsl_refusal", action=step, certificate=extension)
            return None
        unabridged_statement, unabridged_extension = statement, extension
        compilation = None
        aliasing = None
        if h or semantic_family is not None:
            clauses, outputs, aliasing = alias_existing_points(state["statement"], primitive, outputs)
            output = outputs[-1][0]
            statement = (setup.strip()+("; "+"; ".join(clauses) if clauses else "")+" ? "+goal.strip())
            extension = self.certify_extension(state["statement"], statement)
            if not extension["accepted"]:
                raise ValueError("exact point aliasing lost extension legality")
            step.update(output=output, outputs=[n for n, _ in outputs], clauses=clauses)
            self.costs["point_alias_identity_checks"] += aliasing["identity_checks"]
            self.costs["point_alias_seconds"] += aliasing["seconds"]
            self.costs["existing_point_reuses"] += len(aliasing["aliases"])
            self.costs["emitted_construction_clauses"] += len(clauses)
            replay_start = time.perf_counter()
            compilation = certify_compilation(state["statement"], statement, primitive, outputs)
            self.costs["compilation_identity_checks"] += compilation["identity_checks"]
            self.costs["compilation_verification_seconds"] += time.perf_counter()-replay_start
            if not compilation["all_residuals_zero"]:
                raise ValueError("DSL/JGEX semantic correspondence failed")
        problem = ProblemSetup.model_validate(state["problem"])
        rng = np.random.default_rng(int(digest([self.config["seed"], state["path"], step])[:8], 16))
        numeric_start = time.perf_counter()
        try:
            for clause in clauses:
                self.costs["numeric_construction_calls"] += 1
                problem, _ = add_clause_to_problem(problem, JGEXClause.from_str(clause)[0],
                                                   self.definitions, rng, 5)
        except (JGEXConstructionError, ValueError, KeyError, ArithmeticError) as exc:
            self.costs["numeric_construction_seconds"] += time.perf_counter()-numeric_start
            self.log(event="symbolic_dsl_numeric_filter_refusal", action=step, reason=str(exc))
            return None
        self.costs["numeric_construction_seconds"] += time.perf_counter()-numeric_start
        child = self.close(problem, statement, [*state["path"], step], state)
        child["terms"] = deepcopy(state["terms"])
        for n, term in outputs:
            child["terms"][n] = substitute_points(term, state["terms"])
        program = substitute_points(call, state["terms"])
        child["terms"][output] = program
        history = None
        try:
            expanded = dsl.expand(program, self.bank.table)
            history = {"id": digest([digest(self.task), program, extension["certificate_sha256"]]),
                "task_sha256": digest(self.task), "program": program, "primitive_expansion": expanded,
                "replay": {"passed": True, "method": "symbolic conservative extension and full primitive expansion",
                           "certificate": extension}, "acquired_calls": library.calls_in(program),
                "compilation_certificate": compilation,
                "execution": {"call": call, "primitive": primitive, "outputs": outputs},
                "point_aliasing": aliasing, "unabridged_statement": unabridged_statement,
                "unabridged_extension": unabridged_extension,
                "source_statement": state["statement"], "result_statement": statement}
            self.histories.append(history)
        except ValueError as exc:
            self.log(event="learning_fragment_refusal", family=candidate.family, reason=str(exc))
        self.log(event="symbolic_dsl_apply", action=step, extension=extension,
                 history=history, child_key=self.key(child), goal_certified=child["certified"])
        self.costs["acquired_successful_executions"] += int(h is not None)
        return PrimitiveResult(child, {"action": step, "extension_sha256": extension["certificate_sha256"]})


def run_symbolic_feedback(config, output):
    """Frozen JGEX tasks -> existing planner -> certified histories -> library."""
    def write(name, data):
        (output/name).write_text(json.dumps(data, indent=2)+"\n", encoding="utf-8")
    def emitter(stage, task):
        def emit(event):
            with (output/"events.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps({"stage": stage, "task": task, **event})+"\n")
        return emit
    bank = GeometryLibrary()
    histories, rows = [], []
    write("frozen-plan.json", config)
    from math_os_prototype.geometry_proof_dsl import proof_operations
    write("proof-dsl.json", proof_operations())
    training_keys = {digest(t) for t in config["training"]}
    if training_keys & {digest(t) for t in config["evaluation"]}:
        raise ValueError("training/evaluation task overlap")
    domains = [SymbolicDSLDomain(task, config["search"], bank, discover=True,
               emit=emitter("training", digest(task))) for task in config["training"]]
    for cycle in range(config["cycles"]):
        streams = []
        for domain in domains:
            domain.active = tuple(h["id"] for h in bank.archive)
            before = domain.costs.copy()
            plan, applications = domain.search(config["training_applications_per_cycle"])
            streams.append(domain.histories)
            rows.append({"cycle": cycle, "task": digest(domain.task), "costs": dict(domain.costs-before),
                         "applications": applications, "histories": len(domain.histories)})
        histories = [h for group in zip_longest(*streams) for h in group if h is not None]
        learned = acquire(histories, bank, dict(config["acquisition"], cycle=cycle),
                          emit=emitter("acquisition", None))
        write(f"acquisition-{cycle}.json", learned)
        write("archive.json", bank.archive)
        write("training.json", rows)
        print(json.dumps({"cycle": cycle, "archive": len(bank.archive), "histories": len(histories)}), flush=True)
    saved_archive = digest(bank.archive)
    evaluation = []
    for label in ("initial", "acquired", "inactive"):
        for task in config["evaluation"]:
            domain = SymbolicDSLDomain(task, config["search"], bank,
                active=[h["id"] for h in bank.archive] if label == "acquired" else (),
                emit=emitter(label, digest(task)))
            plan = search_action_domain(domain, max_depth=config["search"]["max_depth"],
                                       max_states=config["evaluation_applications"]+1)
            goal = plan.goals.get(domain.sort)
            evaluation.append({"condition": label, "task": digest(task), "proved": bool(goal),
                "proof_program": plan.proof_program, "costs": dict(domain.costs),
                "state": goal.value if goal else None,
                "acquired_calls_in_construction_path": sum(s["action"]["family"] in domain.learned
                    for s in plan.proof_program)})
            write("evaluation.json", evaluation)
    result = {"execution_completed": True, "archive_size": len(bank.archive),
              "training": rows, "evaluation_solved": {label: sum(e["proved"] for e in evaluation
                   if e["condition"] == label) for label in ("initial", "acquired", "inactive")},
              "archive_unchanged_during_evaluation": saved_archive == digest(bank.archive),
              "acquired_later_applications": sum(r["costs"].get("acquired_applications", 0) for r in rows),
              "acquired_successful_executions": sum(r["costs"].get("acquired_successful_executions", 0) for r in rows),
              "scope": "symbolic JGEX goals and conservative rational construction extensions",
              "new_mathematical_capability_claimed": False, "external_deductor": False}
    write("histories.json", histories)
    write("result.json", result)
    return result
