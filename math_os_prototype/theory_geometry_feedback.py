"""Normal-entry recursive geometry acquisition using the existing fair planner."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import asdict
from itertools import combinations
from itertools import zip_longest
import json
import time

import sympy as sp

from math_os_prototype import geometry_contracts as gc
from math_os_prototype import geometry_semantic_dsl as dsl
from math_os_prototype import library_compression as library
from math_os_prototype.representation_progress import digest
from math_os_prototype.runtime_typed_planner import PrimitiveResult, RuntimeSearchProgress
from math_os_prototype.theory_action_domain import search_action_domain
from worker.backend.typed_geometry_stalk import (
    ConstructionFamily, DEFAULT_POINT_FAMILIES, enumerate_typed_candidates,
    iter_complete_typed_candidates,
)


def point_value(xy):
    if len(xy) != 2 or any(isinstance(v, float) for v in xy):
        raise ValueError("two exact rational coordinates required")
    return [str(sp.Rational(v)) for v in xy]


def reach_key(state):
    # The complete supported predicate interpretation is determined by these
    # exact coordinates. Proof paths, cache contents and macro names do not
    # create new reachability. This is NOT the planner's path-sensitive key.
    return digest(sorted({tuple(o["coordinates"]) for o in state.objects.values()}))


def syntax_size(term):
    """AST nodes, not serialized identifier bytes or measured execution cost."""
    if library.is_hole(term) or term.get("op") == "var":
        return 1
    children = term["arguments"].values() if library.is_call(term) else term["args"]
    return 1+sum(syntax_size(a) for a in children)


def refactor_corpus(corpus, bank):
    """Use certified definitions in the learning view; retain executed evidence."""
    started = time.perf_counter()
    rows, proofs = [], []
    checks = 0
    expansion_cost = Counter()
    for entry in corpus:
        original = entry["program"]
        current = deepcopy(original)
        # Each accepted replacement strictly reduces AST size. Old definitions
        # and old execution records are never edited, including their use nodes.
        while True:
            alternatives = []
            for h in bank.archive:
                sites = library.select_sites(library.match_sites(h["template"], current))
                checks += 1
                if not sites:
                    continue
                rewritten = library.rewrite(current, h["id"], h["template"], sites)
                if syntax_size(rewritten) < syntax_size(current):
                    alternatives.append((syntax_size(rewritten), h["id"], rewritten))
            if not alternatives:
                break
            _, name, rewritten = min(alternatives, key=lambda r: r[:2])
            if dsl.expand(current, bank.table, expansion_cost) != dsl.expand(rewritten, bank.table, expansion_cost):
                raise ValueError("learning refactoring changed primitive semantics")
            proofs.append({"history": entry["id"], "morphism": name,
                "before_sha256": digest(current), "after_sha256": digest(rewritten),
                "before_nodes": syntax_size(current), "after_nodes": syntax_size(rewritten),
                "proof": "identical full primitive expansion under certified definition table",
                "table_sha256": bank.table["sha256"]})
            current = rewritten
        rows.append(dict(entry, program=current, source_program=entry.get("source_program", original)))
    return rows, {"proofs": proofs, "matching_checks": checks,
                  "expansion_cost": dict(expansion_cost),
                  "seconds": time.perf_counter()-started}


class GeometryLibrary:
    def __init__(self):
        self.archive = []
        self.schemas = {}
        self.costs = Counter()
        for name, arity in dsl.FRAGMENT.arities.items():
            body = {"op": name, "args": [gc.point(f"f{i}") for i in range(arity)]}
            certificate, cost = gc.certify_body(body, fragment=dsl.FRAGMENT)
            self.schemas[name] = certificate
            self.costs.update(cost)
        self.table = library.definition_table({})

    def register(self, h):
        if any(x["id"] == h["id"] for x in self.archive):
            return False
        start = time.perf_counter()
        rebuilt = dsl.certify_definition(h["template"], self.archive)
        if any(digest(h.get(k)) != digest(v) for k, v in rebuilt.items() if k != "acquisition_cost"):
            raise ValueError("morphism registration certificate mismatch")
        self.costs["registration_seconds"] += time.perf_counter()-start
        self.costs["registration_prover_calls"] += rebuilt["acquisition_cost"]["prover_calls"]
        self.archive.append(deepcopy(h))
        self.table = library.definition_table({x["id"]: x["template"] for x in self.archive})
        return True


class SemanticGeometryDomain:
    sort = "GeometrySemanticState"

    def __init__(self, task, config, bank, *, policy="DISCOVER", active=(), emit=lambda e: None):
        if policy not in {"SOLVE", "DISCOVER"}:
            raise ValueError("unsupported search policy")
        self.task, self.config, self.bank, self.policy = deepcopy(task), config, bank, policy
        self.enumeration = config.get("candidate_enumeration", "complete")
        if self.enumeration not in {"complete", "legacy_prefix"}:
            raise ValueError("unknown candidate enumeration mode")
        self.fair_state_streams = self.enumeration == "complete"
        self.active = tuple(active)
        self.emit = emit
        self.costs = Counter()
        self.attempted = set()
        self.facts = None
        self.histories = []
        self.solution = None
        self.reached = set()
        self.goal_cache = {}
        self.started = time.perf_counter()
        self.search_seconds = 0.0
        self.window_started = None
        self.stop_reason = None
        self.sync()
        self.start_state = dsl.GeometrySemanticState(
            objects={n: {"type": "Point", "coordinates": point_value(xy)} for n, xy in task["points"].items()},
            terms={n: gc.point(n) for n in task["points"]}, registered_morphisms=self.families)
        for n in self.start_state.objects:
            gc.validate(gc.point(n))
        if len(self.start_state.objects) < 2:
            raise ValueError("at least two initial points required")
        for atom in task.get("predicates", []):
            proof = self.prove(self.start_state, atom["predicate"], tuple(atom["points"]), "input")
            if proof is None:
                raise ValueError("unproved initial predicate")
            self.start_state.predicates[dsl.atom_key(proof.predicate, proof.arguments)] = proof
        self.reached.add(reach_key(self.start_state))

    def sync(self):
        started = time.perf_counter()
        self.contracts = {h["id"]: h for h in self.bank.archive if h["id"] in self.active}
        available = {h["id"] for h in self.bank.archive}
        if set(self.active)-available:
            raise ValueError("active morphism not in certified archive")
        self.registry = {f.name: f for f in DEFAULT_POINT_FAMILIES}
        for h in self.contracts.values():
            self.registry[h["id"]] = ConstructionFamily(h["id"], len(h["parameters"]), "ordered", allow_repeated_inputs=True)
        self.families = tuple(self.registry)
        self.input_guards = {}
        for family in self.families:
            cert = (self.contracts[family]["exact_certificate"] if family in self.contracts
                    else self.bank.schemas[family])
            names = [p["name"] for p in cert["typed_parameters"]]
            symbols = {n+a: sp.Symbol(n+a, real=True) for n in names for a in ("x", "y")}
            symbols.update({s: sp.Symbol(s, real=True)
                for p in cert["local_auxiliary_variables"] for s in p["coordinates"]})
            expressions = list(cert["applicability"]["input_nonzero_polynomials"])
            expressions.extend(e for g in cert["applicability"].get("sequential_nonzero_polynomials", [])
                               for e in g["parent_factors"])
            inputs = {symbols[n+a] for n in names for a in ("x", "y")}
            guards = [gc.parse(e, symbols) for e in expressions]
            self.input_guards[family] = (names, symbols, [g for g in guards if g.free_symbols <= inputs])
        self.costs["registry_sync_seconds"] += time.perf_counter()-started

    def initial(self):
        return deepcopy(self.start_state)

    def key(self, state):
        # Histories are intentionally retained: enumeration ranks by relational
        # support and later acquisition reads the semantic terms.
        return digest({"objects": state.objects, "terms": state.terms,
                       "predicates": sorted(state.predicates), "depth": state.depth})

    def log_state(self, state):
        self.emit({"event": "semantic_state", "task_sha256": digest(self.task),
                   "state_hash": self.key(state), "reach_hash": reach_key(state),
                   **state.record()})

    def prove(self, state, predicate, args, source):
        proof = dsl.certify_atom(predicate, args, state.objects, provenance=source,
                                 known=state.predicates, stats=self.costs)
        if self.config.get("trace_predicates", False):
            self.emit({"event": "predicate_check", "predicate": predicate,
                "arguments": list(args), "source": source, "passed": proof is not None,
                "state_depth": state.depth})
        return proof

    def complete_candidates(self, family, state):
        names = list(state.objects)
        graph = {n: set() for n in names}
        for atom in state.predicates.values():
            for a, b in combinations(atom.arguments, 2):
                graph[a].add(b)
                graph[b].add(a)
        demands = Counter(n for g in self.task.get("goals", []) for n in g["points"] if n in names)
        stream = iter_complete_typed_candidates(points=names, graph=graph,
            goal_multiplicity=demands if self.policy == "SOLVE" else {},
            generated_points=set(names)-set(self.task["points"]), family=self.registry[family])
        state_key = self.key(state)
        for ordinal, row in enumerate(stream):
            if self.stop_reason or state.depth >= self.config["max_depth"]:
                return
            if (family, state_key, tuple(row.inputs)) in self.attempted:
                continue
            if (self.window_started is not None and
                    time.perf_counter()-self.window_started >= self.config["wall_seconds"]):
                self.stop_reason = "wall_time_budget"
                return
            limit = self.config.get("max_candidate_checks")
            if limit is not None and self.costs["complete_candidate_checks"] >= limit:
                self.stop_reason = "candidate_check_budget"
                return
            start = time.perf_counter()
            self.costs["complete_candidate_checks"] += 1
            self.costs["examined_input_tuples"] += 1
            admissible = self.binding_admissible(state, family, row.inputs)
            self.costs["candidate_generation_seconds"] += time.perf_counter()-start
            self.emit({"event": "candidate_scan", "state": state_key, "family": family,
                "ordinal": ordinal, "inputs": list(row.inputs),
                "disposition": "eligible" if admissible else "proved_false_input_guard"})
            if admissible:
                yield row
            else:
                self.costs["input_guard_filtered"] += 1
        self.emit({"event": "candidate_stream_exhausted", "state": state_key, "family": family})

    def candidate_rows(self, family, state):
        if self.stop_reason or state.depth >= self.config["max_depth"]:
            return []
        if self.enumeration == "complete":
            return self.complete_candidates(family, state)
        start = time.perf_counter()
        names = list(state.objects)
        graph = {n: set() for n in names}
        for atom in state.predicates.values():
            for a, b in combinations(atom.arguments, 2):
                graph[a].add(b)
                graph[b].add(a)
        demands = Counter(n for g in self.task.get("goals", []) for n in g["points"] if n in names)
        audit = {}
        rows = enumerate_typed_candidates(points=names, graph=graph,
            goal_multiplicity=demands if self.policy == "SOLVE" else {},
            generated_points=set(names)-set(self.task["points"]), families=[self.registry[family]],
            per_family_limit=self.config["per_family_limit"], seed=self.config["seed"],
            max_input_tuples_per_family=self.config["max_input_tuples"], audit=audit,
            binding_precondition=lambda f, args: self.binding_admissible(state, f.name, args))
        self.costs["candidate_generation_seconds"] += time.perf_counter()-start
        self.costs["examined_input_tuples"] += audit.get("examined_input_tuples", 0)
        self.costs["input_guard_filtered"] += audit.get("precondition_filtered", 0)
        return rows

    def alternatives(self, family, state):
        rows = self.candidate_rows(family, state)
        for row in rows:
            key = (family, self.key(state), tuple(row.inputs))
            if key not in self.attempted:
                yield lambda c=row, k=key: self.apply(state, c, k)

    def binding_admissible(self, state, family, args):
        """Only reject a proved-false guard; unresolved local guards remain live."""
        started = time.perf_counter()
        try:
            names, symbols, guards = self.input_guards[family]
            mapping = dict(zip(names, args, strict=True))
            replacement = {symbols[n+a]: sp.Rational(state.objects[v]["coordinates"][i])
                for n, v in mapping.items() for i, a in enumerate(("x", "y"))}
            for guard in guards:
                self.costs["candidate_guard_checks"] += 1
                if sp.cancel(guard.xreplace(replacement)) == 0:
                    return False
            return True
        finally:
            self.costs["candidate_guard_seconds"] += time.perf_counter()-started

    def apply(self, state, candidate, attempt):
        if self.stop_reason:
            return None
        elapsed = self.search_seconds
        if self.window_started is not None:
            elapsed += time.perf_counter()-self.window_started
        if elapsed > self.config["wall_seconds"]:
            self.stop_reason = "wall_budget_between_exact_operations"
            return None
        self.attempted.add(attempt)
        self.costs["candidate_expansions"] += 1
        acquired = candidate.family in self.contracts
        h = self.contracts.get(candidate.family)
        cert = h["exact_certificate"] if acquired else self.bank.schemas[candidate.family]
        count = len(cert["composition"])
        if self.costs["primitive_equivalent_operations"]+count > self.config["max_primitive_operations"]:
            self.stop_reason = "primitive_operation_budget"
            return None
        self.costs["primitive_equivalent_operations"] += count
        started = time.perf_counter()
        execution = None
        child = deepcopy(state)
        try:
            used_predicates = []
            for pred, args in dsl.requirements(candidate.family, candidate.inputs):
                known = dsl.atom_key(pred, args) in child.predicates
                proof = self.prove(child, pred, args, "applicability")
                if proof is None:
                    raise ValueError("unproved_applicability:"+pred)
                child.predicates[dsl.atom_key(pred, args)] = proof
                used_predicates.append({"atom": asdict(proof), "already_in_state": known})
            names = [p["name"] for p in cert["typed_parameters"]]
            mapping = dict(zip(names, candidate.inputs, strict=True))
            symbols = {n+a: sp.Symbol(n+a, real=True) for n in names for a in ("x", "y")}
            replacement = {symbols[n+a]: sp.Rational(state.objects[v]["coordinates"][i])
                           for n, v in mapping.items() for i, a in enumerate(("x", "y"))}
            local_coordinates = {p["name"]: p["coordinates"] for p in cert["local_auxiliary_variables"]}
            if cert.get("witness_mode") == "sequential_local":
                symbols.update({s: sp.Symbol(s, real=True) for xy in local_coordinates.values() for s in xy})
            step_guards = {g["before_output"]: g["parent_factors"]
                           for g in cert["applicability"].get("sequential_nonzero_polynomials", [])}
            def value(expression):
                return sp.cancel(gc.parse(expression, symbols).subs(replacement, simultaneous=True))
            def check_guards(expressions):
                check = time.perf_counter()
                try:
                    for e in expressions:
                        self.costs["applicability_prover_calls"] += 1
                        if value(e) == 0:
                            raise ValueError("unproved_applicability:contract_nonzero")
                finally:
                    self.costs["applicability_seconds"] += time.perf_counter()-check
            check_guards(cert["applicability"]["input_nonzero_polynomials"])
            local_terms = {n: state.terms[v] for n, v in mapping.items()}
            if acquired:
                binding = {n: state.terms[v] for n, v in mapping.items()}
                semantic = library.use_node(h["id"], h["template"], binding)
            else:
                semantic = {"op": candidate.family, "args": [state.terms[v] for v in candidate.inputs]}
            expansion_stats = {}
            expansion = dsl.expand(semantic, self.bank.table, expansion_stats)
            self.costs.update(expansion_stats)
            added = []
            for step in cert["composition"]:
                check_guards(step_guards.get(step["output"], []))
                execution = time.perf_counter()
                self.costs["witness_evaluation_attempts"] += 1
                xy = [str(value(e)) for e in cert["witness"][step["output"]]]
                if any(sp.Rational(e).is_finite is not True for e in xy):
                    raise ValueError("undefined exact witness")
                existing = next((n for n, o in child.objects.items() if o["coordinates"] == xy), None)
                if existing is None:
                    name = "v"+str(len(child.objects))
                    while name in child.objects:
                        name += "v"
                    child.objects[name] = {"type": "Point", "coordinates": xy}
                    added.append(name)
                else:
                    name = existing
                mapping[step["output"]] = name
                if cert.get("witness_mode") == "sequential_local":
                    replacement.update({symbols[s]: sp.Rational(v)
                        for s, v in zip(local_coordinates[step["output"]], xy, strict=True)})
                local_terms[step["output"]] = {"op": step["family"],
                                               "args": [local_terms[a] for a in step["inputs"]]}
                if existing is None:
                    child.terms[name] = local_terms[step["output"]]
                self.costs["witness_evaluations"] += 1
                self.costs["execution_seconds"] += time.perf_counter()-execution
                execution = None
            output = mapping[cert["output"]]
            if output in state.objects:
                raise ValueError("duplicate_output_point")
            child.terms[output] = semantic
            source = {"morphism": candidate.family, "contract": cert["id"], "parent": self.key(state)}
            for relation in cert["guaranteed_relation"]:
                args = tuple(mapping[a] for a in relation["points"])
                proof = self.prove(child, relation["predicate"], args, source)
                if proof is not None:
                    child.predicates[dsl.atom_key(proof.predicate, args)] = proof
                else:
                    self.costs["conditional_effects_not_published"] += 1
            # Newly established NDGs are live premises, not a log-only field.
            for n in added:
                for other in child.objects:
                    if n != other:
                        proof = self.prove(child, "diff", (n, other), source)
                        if proof:
                            child.predicates[dsl.atom_key("diff", (n, other))] = proof
            call = dsl.MorphismCall(candidate.family, dict(zip(names, candidate.inputs, strict=True)),
                tuple(added), cert["id"], semantic, expansion,
                {"origin": "acquired" if acquired else "primitive", "used_predicates": used_predicates,
                 "task_sha256": digest(self.task)})
            child.history.append(call)
            child.depth += 1
            child.primitive_cost += count
            child.registered_morphisms = self.families
            replay = self.replay(expansion, child.objects[output]["coordinates"])
            if not replay["passed"]:
                raise ValueError("independent replay rejected")
            self.costs["successful_acquired_calls" if acquired else "successful_primitive_calls"] += 1
            self.reached.add(reach_key(child))
            history = {"id": digest([digest(self.task), semantic]), "task_sha256": digest(self.task),
                "program": semantic, "primitive_expansion": expansion, "output": output,
                "predicates": [asdict(a) for a in child.predicates.values()], "state_hash": self.key(child),
                "replay": replay, "call": asdict(call)}
            self.histories.append(history)
            self.emit({"event": "certified_history", **history})
            self.log_state(child)
            return PrimitiveResult(child, {"morphism": candidate.family, "history": history["id"]})
        except (ValueError, TypeError, KeyError) as exc:
            self.costs["rejected_applications"] += 1
            self.emit({"event": "refusal", "family": candidate.family, "inputs": candidate.inputs,
                       "reason": str(exc), "task_sha256": digest(self.task)})
            return None
        finally:
            if execution is not None:
                self.costs["execution_seconds"] += time.perf_counter()-execution
            self.costs["application_seconds_inclusive"] += time.perf_counter()-started

    def replay(self, primitive, expected):
        started = time.perf_counter()
        elaborator = gc._JGEXElaborator()
        elaborator.coordinates.update({n: tuple(sp.Rational(v) for v in o["coordinates"])
                                       for n, o in self.start_state.objects.items()})
        steps, final = gc.dag(primitive, fragment=dsl.FRAGMENT)
        for step in steps:
            dsl.FRAGMENT.primitive(elaborator, step["family"], step["output"], step["inputs"])
            if any(sp.cancel(d) == 0 for d in elaborator.denominators):
                raise ValueError("primitive replay degeneracy")
        residuals = [str(sp.cancel(a-sp.Rational(b))) for a, b in zip(elaborator.coordinates[final], expected, strict=True)]
        elapsed = time.perf_counter()-started
        self.costs["independent_replay_seconds"] += elapsed
        self.costs["independent_replay_primitive_operations"] += len(steps)
        return {"passed": residuals == ["0", "0"], "residuals": residuals, "seconds": elapsed,
                "primitive_operations": len(steps), "method": "primitive reexecution, not contract witness"}

    def is_goal(self, state):
        if self.policy == "DISCOVER":
            return False
        key = self.key(state)
        if key in self.goal_cache:
            return self.goal_cache[key]
        started = time.perf_counter()
        for n in state.objects:
            proofs = [self.prove(state, g["predicate"], tuple(n if a == "u" else a for a in g["points"]), "goal")
                      for g in self.task.get("goals", [])]
            if proofs and all(p is not None for p in proofs):
                primitive = dsl.expand(state.terms[n], self.bank.table, self.costs)
                replay = self.replay(primitive, state.objects[n]["coordinates"])
                if not replay["passed"]:
                    self.costs["goal_replay_failures"] += 1
                    self.emit({"event": "goal_refusal", "reason": "independent_replay_rejected",
                               "task_sha256": digest(self.task), "point": n, "replay": replay})
                    continue
                self.solution = {"point": n, "term": state.terms[n], "primitive_expansion": primitive,
                    "goals": [asdict(p) for p in proofs], "replay": replay,
                    "acquired_calls": library.calls_in(state.terms[n])}
                self.goal_cache[key] = True
                self.costs["goal_seconds"] += time.perf_counter()-started
                return True
        self.costs["goal_seconds"] += time.perf_counter()-started
        self.goal_cache[key] = False
        return False

    def search(self, applications):
        progress = RuntimeSearchProgress()
        initial_count = len(self.facts) if self.facts is not None else 1
        self.window_started = time.perf_counter()
        try:
            self.sync()
            plan = search_action_domain(self, max_depth=self.config["max_depth"],
                max_states=initial_count+applications, progress=progress, initial_facts=self.facts)
        finally:
            self.search_seconds += time.perf_counter()-self.window_started
            self.window_started = None
        self.facts = plan.facts
        self.costs["planner_applications"] += progress.applications_completed
        self.emit({"event": "search_window", "task_sha256": digest(self.task),
                   "active": list(self.active), "retained": len(self.facts),
                   "applications": progress.applications_completed, "costs": dict(self.costs)})
        return {"task_sha256": digest(self.task), "solved": bool(self.solution), "solution": self.solution,
                "reach": sorted(self.reached), "costs": dict(self.costs),
                "stop_reason": "proved" if self.solution else self.stop_reason or "window_or_candidate_budget",
                "retained_states": len(self.facts), "wall_seconds": self.search_seconds,
                "candidate_enumeration": self.enumeration,
                "pending_streams": progress.pending_streams,
                "pending_note": "Live iterators are retained during search; a new search re-enumerates and skips completed calls. Pending is not impossibility."}


def acquire(histories, bank, config, *, flatten=False, emit=lambda e: None):
    start = time.perf_counter()
    corpus = []
    seen = set()
    for history in histories:
        if history["id"] in seen or not history["replay"]["passed"]:
            continue
        seen.add(history["id"])
        program = history["primitive_expansion"] if flatten else history["program"]
        program = dsl.rename_points(program, "t"+history["task_sha256"][:12]+"_")
        corpus.append({"id": history["id"], "program": program, "task_sha256": history["task_sha256"]})
    corpus = corpus[-config["corpus_capacity"]:]
    def size(node):
        if not isinstance(node, dict):
            return 0
        if library.is_call(node):
            return 1+sum(size(a) for a in node["arguments"].values())
        return int(node.get("op") in dsl.FRAGMENT.arities)+sum(size(a) for a in node.get("args", []))
    old = {h["id"] for h in bank.archive}
    accepted, rejected, refactorings, selection_rounds = [], [], [], []
    with library.grammar(dsl.validate_semantic):
        input_corpus = deepcopy(corpus)
        if not flatten:
            corpus, refactoring = refactor_corpus(corpus, bank)
            refactorings.append(refactoring)
        # Preserve both views for proposal generation, but never count two
        # variants of one history twice when measuring acquisition utility.
        proposal_corpus = list(corpus)
        proposal_corpus.extend(e for e, r in zip(input_corpus, corpus, strict=True)
                               if e["program"] != r["program"])
        proposals = library.candidates(proposal_corpus, pairs=config["pairs"], limit=config["max_parameters"],
                                       source_filter=lambda n: size(n) >= config["min_semantic_operations"],
                                       deduplicate_sources=True)
        admissible = []
        for p in proposals["candidates"]:
            try:
                body = dsl.definition_body(p["template"])
                if size(body) < config["min_semantic_operations"]:
                    continue
                expanded = dsl.expand(body, bank.table)
                if len(gc.dag(expanded, fragment=dsl.FRAGMENT)[0]) > config["max_primitive_steps"]:
                    continue
                identity = "geom.semantic."+digest({"template": p["template"], "scope": dsl.FRAGMENT.scope})[:20]
                if identity in old:
                    continue
                admissible.append((p, identity))
            except (ValueError, TypeError, KeyError) as exc:
                rejected.append({"candidate": p["id"], "reason": str(exc)})
        attempted = set()
        for _ in range(min(config["certification_budget"], config["per_cycle_capacity"])):
            eligible = []
            for p, identity in admissible:
                if p["id"] in attempted:
                    continue
                sources = [{"history": c["id"], "task_sha256": c["task_sha256"],
                            "learning_program_sha256": digest(c["program"]),
                            "source_program_sha256": digest(c.get("source_program", c["program"])),
                            "matches": library.match_sites(p["template"], c["program"])} for c in corpus]
                sources = [s for s in sources if s["matches"]]
                if len({s["task_sha256"] for s in sources}) < config["min_contexts"]:
                    continue
                utility = library.utility(corpus, p["template"], index=identity)
                if utility["failures"]:
                    raise ValueError("syntactic abstraction roundtrip failed")
                before = sum(syntax_size(c["program"]) for c in corpus)
                after = sum(syntax_size(c["program"]) for c in utility["rewritten"])
                definition = 1+len(library.holes(p["template"]))+syntax_size(p["template"])
                utility["syntax_nodes"] = {"before": before, "after": after,
                    "definition": definition, "net_saved": before-after-definition,
                    "model": "one per AST node; binder and each parameter once; IDs not bytes"}
                eligible.append((p, sources, utility))
            eligible.sort(key=lambda e: (-e[2]["syntax_nodes"]["net_saved"], -len(e[1]), e[0]["id"]))
            selection_rounds.append([{"candidate": p["id"], "history_support": len(s),
                "syntax_nodes": u["syntax_nodes"], "json_utility_bits": u["utility_bits"]}
                for p, s, u in eligible])
            if not eligible or eligible[0][2]["syntax_nodes"]["net_saved"] <= 0:
                break
            p, sources, utility = eligible[0]
            attempted.add(p["id"])
            certify_started = time.perf_counter()
            emit({"event": "certification_start", "cycle": config["cycle"],
                  "candidate": p["id"], "template": p["template"], "sources": sources})
            try:
                h = dsl.certify_definition(p["template"], bank.archive)
                h.update(source_histories=sources, acquisition_utility=utility,
                         acquisition_cycle=config["cycle"], source_corpus_sha256=digest(corpus))
                if len(accepted) < config["per_cycle_capacity"]:
                    bank.register(h)
                    accepted.append(h)
                emit({"event": "certification_complete", "candidate": p["id"],
                      "seconds": time.perf_counter()-certify_started, "morphism": h["id"]})
                corpus, refactoring = refactor_corpus(corpus, bank)
                refactorings.append(refactoring)
            except (ValueError, TypeError, KeyError) as exc:
                rejected.append({"candidate": p["id"], "reason": str(exc)})
                emit({"event": "certification_refused", "candidate": p["id"],
                      "seconds": time.perf_counter()-certify_started, "reason": str(exc)})
    return {"accepted": accepted, "rejected": rejected, "corpus": corpus,
            "input_corpus": input_corpus, "refactorings": refactorings,
            "selection_rounds": selection_rounds,
            "proposals": proposals, "eligible": len(admissible), "flattened_before_learning": flatten,
            "seconds": time.perf_counter()-start,
            "selection_rule": "positive marginal AST-node saving including definition, history support, content hash; no evaluation feedback"}


def run_semantic_feedback(config, output):
    """A/B/C/D/E with fixed tasks and no evaluation-to-acquisition channel."""
    started = time.perf_counter()
    def write(name, value):
        (output/name).write_text(json.dumps(value, indent=2)+"\n", encoding="utf-8")
    def emitter(label, stage):
        def emit(event):
            with (output/"events.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps({"condition": label, "stage": stage, **event})+"\n")
        return emit
    write("frozen-plan.json", config)
    write("support.json", dsl.support_manifest())
    training_hashes = {digest(t) for t in config["training"]}
    if training_hashes & {digest(t) for t in config["evaluation"]}:
        raise ValueError("training/evaluation overlap")
    all_results, banks = {}, {}
    initial_bank = GeometryLibrary()
    write("primitive-contracts.json", initial_bank.schemas)
    common_schema_cost = dict(initial_bank.costs)
    for label in ("A", "B", "C", "E"):
        bank = deepcopy(initial_bank)
        bank.costs.clear()
        banks[label] = bank
        emit = emitter(label, "training")
        domains = [SemanticGeometryDomain(t, config["search"], bank, emit=emit) for t in config["training"]]
        cycles, snapshots = [], []
        for cycle in range(config["cycles"]):
            active = [h["id"] for h in bank.archive]
            runs = []
            for domain in domains:
                domain.active = tuple(active)
                runs.append(domain.search(config["training_applications_per_cycle"]))
            # Contexts are interleaved, not selected by later evaluation scores.
            histories = [h for group in zip_longest(*(d.histories for d in domains)) for h in group if h is not None]
            learning = None
            if label != "A" and (label != "B" or cycle == 0):
                learning = acquire(histories, bank, dict(config["acquisition"], cycle=cycle),
                                   flatten=label == "E", emit=emit)
                for h in learning["accepted"]:
                    emit({"event": "registration", "cycle": cycle, "morphism": h})
            snapshots.append(deepcopy(bank.archive))
            row = {"cycle": cycle, "runs": runs, "acquisition": learning,
                   "active_size_after": len(bank.archive), "archive_sha256": digest(bank.archive)}
            cycles.append(row)
            write(label+"-training.json", cycles)
            write(label+"-archive.json", bank.archive)
            print(json.dumps({"condition": label, "cycle": cycle, "archive": len(bank.archive),
                              "generations": [h["generation"] for h in bank.archive]}), flush=True)
        all_results[label] = {"training": cycles, "snapshots": snapshots, "library_costs": dict(bank.costs)}
    # D is literally C's saved archive with the active root set empty. Transitive
    # bodies remain in the archive, and no dangling reference is manufactured.
    banks["D"] = banks["C"]
    all_results["D"] = {"training_source": "C", "archive_sha256": digest(banks["C"].archive)}
    frozen = {label: digest(bank.archive) for label, bank in banks.items()}
    for label in ("A", "B", "C", "D", "E"):
        bank = banks[label]
        active = [] if label == "D" else [h["id"] for h in bank.archive]
        evaluation = []
        for task in config["evaluation"]:
            domain = SemanticGeometryDomain(task, config["search"], bank, policy="SOLVE", active=active,
                                             emit=emitter(label, "evaluation"))
            evaluation.append(domain.search(config["evaluation_applications"]))
        all_results[label]["evaluation"] = evaluation
        write(label+"-evaluation.json", evaluation)
        print(json.dumps({"condition": label, "evaluation_solved": sum(r["solved"] for r in evaluation)}), flush=True)
    # Same initial state and same budgets at each frozen language size. This is
    # separate from training frontier continuation, whose cost has accumulated.
    reach = {}
    c_bank = banks["C"]
    for index, snapshot in enumerate([[], *all_results["C"]["snapshots"]]):
        rows = []
        active = [h["id"] for h in snapshot]
        for task in config["reachability"]:
            domain = SemanticGeometryDomain(task, config["search"], c_bank, active=active,
                emit=emitter("L"+str(index), "reachability"))
            rows.append(domain.search(config["reachability_applications"]))
        reach["L"+str(index)] = rows
        write("reachability.json", reach)
    differences = []
    for i in range(1, len(reach)):
        for prev, current in zip(reach["L"+str(i-1)], reach["L"+str(i)], strict=True):
            differences.append({"from": "L"+str(i-1), "to": "L"+str(i),
                "task_sha256": current["task_sha256"],
                "new_reachable_states": sorted(set(current["reach"])-set(prev["reach"])),
                "lost_reachable_states": sorted(set(prev["reach"])-set(current["reach"]))})
    # A same-budget DISCOVER comparison isolates C versus the flattening control.
    controls = {}
    for label in ("A", "B", "C", "D", "E"):
        bank = banks[label]
        active = [] if label == "D" else [h["id"] for h in bank.archive]
        controls[label] = [SemanticGeometryDomain(t, config["search"], bank, active=active,
            emit=emitter(label, "reach_control")).search(config["reachability_applications"])
            for t in config["reachability"]]
    write("reach-controls.json", controls)
    summary = {}
    for label, result in all_results.items():
        rows = result["evaluation"]
        summary[label] = {"solved": sum(r["solved"] for r in rows), "tasks": len(rows),
            "candidate_expansions": sum(r["costs"].get("candidate_expansions", 0) for r in rows),
            "evaluation_seconds": sum(r["wall_seconds"] for r in rows),
            "goal_acquired_calls": sum(len(r["solution"]["acquired_calls"]) for r in rows if r["solved"]),
            "archive_size": len(banks[label].archive),
            "active_size": 0 if label == "D" else len(banks[label].archive),
            "max_generation": max((h["generation"] for h in banks[label].archive), default=0),
            "reachable_states": [len(r["reach"]) for r in controls[label]]}
    delta = {label: [sorted(set(c["reach"])-set(other["reach"]))
                    for c, other in zip(controls["C"], controls[label], strict=True)] for label in ("A", "D", "E")}
    report = {"execution_completed": True, "summary": summary, "reach_differences": differences,
        "common_primitive_schema_certification_cost": common_schema_cost,
        "C_minus_control": delta, "archive_unchanged_during_evaluation": all(frozen[k] == digest(v.archive) for k, v in banks.items()),
        "recursive_acquisition_observed": any(h["parents"] for h in banks["C"].archive),
        "total_seconds": time.perf_counter()-started,
        "scope": "exact rational configurations and universally certified rational Point morphisms",
        "unbounded_expressivity_increase_claimed": False,
        "external_online_prover": False, "external_llm": False,
        "reach_definition": "sets of rational points; macro names, paths and redundant proof caches excluded",
        "reach_budget": {k: config[k] for k in ("reachability_applications",)},
        "conditional_cost_note": "witness execution, primitive replay, macro expansion and schema certification are separate counters"}
    write("comparisons.json", all_results)
    write("result.json", report)
    return report
