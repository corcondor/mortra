"""Persistent executable definitions learned from Theory's own computations.

Uses the existing anti-unifier, MDL learner, call generator and full expander.
Definitions have stable references; later bodies may call earlier definitions.
The fixed interpreter is initial knowledge, not a learned algorithm.
"""
from copy import copy, deepcopy
from itertools import product, islice, chain
import time
import sympy as sp

from math_os_prototype import library_compression as lib
from math_os_prototype.theory_domain import term, size, recurrence_value
from math_os_prototype.theory_spaces import materialize
from math_os_prototype.representation_progress import digest


def references(node):
    found = set()
    if lib.is_call(node):
        found.add(str(node["abstraction"]))
    if isinstance(node, dict):
        for value in node.values():
            found.update(references(value))
    elif isinstance(node, list):
        for value in node:
            found.update(references(value))
    return found


def program_size(node):
    """Charge a call and every supplied argument; no hidden free ASTs."""
    if lib.is_call(node):
        return 1 + sum(program_size(v) if isinstance(v, dict) else 1
                       for v in node["arguments"].values())
    return 1 + sum(program_size(a) for a in node.get("args", []))


def context_operations(node):
    """Exclude literal payloads and holes from compositional novelty."""
    if lib.is_hole(node):
        return 0
    if lib.is_call(node):
        return 1 + sum(context_operations(v) for v in node["arguments"].values())
    if not isinstance(node, dict):
        return 0
    return bool(node.get("args")) + sum(context_operations(v) for v in node.get("args", []))


class Vocabulary:
    def __init__(self, theory):
        self.theory, self.domain = theory, theory.domain
        self.state = theory.state.setdefault("dsl", {
            "definitions": [], "corpus": [], "attempts": [], "executions": [],
            "seen_calls": [], "last_learn_size": 0, "last_synthesis_size": -1,
            "word_cursor": 0, "grammar_versions": [], "seen_programs": []})
        self.state.setdefault("observation_operations", {})
        self.state.setdefault("recurrence_operations", {})
        self.state.setdefault("natural_cursor", 0)
        self.state.setdefault("composition_cursor", 0)
        # Interpreter caches, not learned knowledge; rebuilding them is charged.
        self._compiled_spaces = {}
        self._observation_values = {}

    def register_recurrence(self, pid):
        p = self.theory.state["procedures"][pid]
        self.state["recurrence_operations"][pid] = {
            "signature": {"parameters": {"n": "natural"}, "result": "scalar"},
            "body": {"kernel": "certified_recurrence_value", "procedure": pid},
            "scope": p["body"]["scope"], "meaning": "q(T_label**n(initial_state))",
            "born": self.theory.state["cycle"]}

    def law(self, pid):
        p = self.theory.state["procedures"][pid]
        law = p["body"]
        if p["kind"] != "certified_scalar_recurrence" or not law["certificate_passed"]:
            raise ValueError("uncertified recurrence")
        scope = law["scope"]
        if scope["domain"] != self.domain.key or scope["parent"] != self.domain.scope or scope["kind"] != "all_repeats":
            raise ValueError("recurrence scope mismatch")
        return p, law

    def register_observation(self, rid):
        r = materialize(self.theory.state, rid)
        self.state["observation_operations"][rid] = {
            "signature": {"parameters": {"word": "action_word"}, "result": "scalar"},
            "body": {"kernel": "certified_matrix_word_readout", "binding": rid,
                     "space": r.get("space"), "readout": r["readout"]},
            "scope": r["scope"], "requirements": "unrestricted observation; no legality/goal inference",
            "meaning": "q after an action word, on every state in the declared finite model",
            "born": self.theory.state["cycle"]}

    def table(self):
        return lib.definition_table({d["index"]: d["template"] for d in self.state["definitions"]})

    def accepts(self, node, *, counter=None):
        if counter is not None:
            counter["type_scope_checks"] = counter.get("type_scope_checks", 0)+1
        if not isinstance(node, dict) or "op" not in node:
            raise ValueError("not a typed program")
        if lib.is_call(node):
            definition = None
            for d in self.state["definitions"]:
                if counter is not None:
                    counter["definition_lookup_checks"] = counter.get("definition_lookup_checks", 0)+1
                if str(d["index"]) == str(node["abstraction"]):
                    definition = d
                    break
            if definition is None or definition["scope"] != self.domain.scope:
                raise ValueError("missing definition or incompatible scope")
            if set(node["arguments"]) != set(definition["signature"]["parameters"]):
                raise ValueError("call arity mismatch")
            for name, value in node["arguments"].items():
                expected = definition["signature"]["parameters"][name]
                actual = "rational" if not isinstance(value, dict) and sp.sympify(value).is_Rational else self.accepts(value, counter=counter)
                if actual != expected:
                    raise ValueError("call argument type mismatch")
            return definition["signature"]["result"]
        if node.get("op") == "word":
            if node.get("args") != [] or any(g not in self.domain.actions for g in node["letters"]):
                raise ValueError("invalid action word")
            return "action_word"
        if node.get("op") == "natural":
            number = sp.sympify(node["value"])
            if node.get("args") != [] or number.is_Integer is not True or number < 0:
                raise ValueError("natural argument required")
            return "natural"
        if node.get("op") == "recurrence":
            self.law(node["procedure"])
            if len(node["args"]) != 1 or self.accepts(node["args"][0], counter=counter) != "natural":
                raise ValueError("recurrence takes one natural argument")
            return "scalar"
        if node.get("op") == "represented":
            r = materialize(self.theory.state, node["binding"])
            if r["scope"] != self.domain.scope or r["system_key"] != self.domain.key:
                raise ValueError("representation outside scope")
            if len(node["args"]) != 1 or self.accepts(node["args"][0], counter=counter) != "action_word":
                raise ValueError("represented observation takes one action word")
            return "scalar"
        # Delegate primitive typing after substituting typed representative leaves.
        children = []
        for child in node.get("args", []):
            sort = self.accepts(child, counter=counter)
            if sort == "scalar":
                children.append(self.domain.seeds()[0])
            elif sort == "predicate":
                children.append(term("eq", self.domain.seeds()[0], self.domain.seeds()[0]))
            else:
                raise ValueError("action word used as scalar")
        return self.domain.type_of(dict(node, args=children))

    def expand(self, node, *, counter=None, charge=None):
        self.accepts(node, counter=counter)
        with lib.grammar(lambda p: self.accepts(p, counter=counter)):
            return lib.expand_for_execution(node, self.table(), stats=counter, charge=charge)

    def primitive(self, node, *, counter=None, charge=None):
        node = self.expand(node, counter=counter, charge=charge)
        def walk(t):
            if t["op"] == "recurrence":
                p, law = self.law(t["procedure"])
                index = law["scope"]["initial_state_index"]
                for _ in range(int(t["args"][0]["value"])):
                    if charge is not None:
                        charge("model_action_steps", 1)
                    index = self.domain.actions[law["label"]][index]
                c = self.theory.state["concepts"][self.theory.state["representations"][p["representation"]]["concept"]]
                value = self.domain.evaluate(c["definition"], charge=charge)[index]
                return term("const", value=str(value))
            if t["op"] == "represented":
                q = deepcopy(self.theory.state["concepts"][
                    self.theory.state["representations"][t["binding"]]["concept"]]["definition"])
                # For states acted on in word order, pullbacks nest in reverse.
                for g in reversed(t["args"][0]["letters"]):
                    q = term("pull", q, label=g)
                return q
            return dict(t, args=[walk(a) for a in t.get("args", [])])
        return walk(node)

    def evaluate(self, program, *, requirements=None, charge=None, counter=None):
        if requirements and any(v not in (None, False, "unrestricted") for v in requirements.values()):
            raise ValueError("observation language does not certify additional legality or goal requirements")
        counter = counter if counter is not None else {}
        counter.setdefault("matrix_multiply_adds", 0)
        counter.setdefault("representation_calls", 0)
        began = time.perf_counter()
        node = self.expand(program, counter=counter, charge=charge)
        counter["expansion_validation_seconds"] = counter.get("expansion_validation_seconds", 0)+time.perf_counter()-began
        domain = copy(self.domain)
        domain.sensors, domain.names = dict(domain.sensors), list(domain.names)
        def walk(t):
            if t["op"] == "recurrence":
                if requirements:
                    raise ValueError("recurrence permits only its certified initial state and repeats")
                _, law = self.law(t["procedure"])
                n = int(t["args"][0]["value"])
                if charge is not None:
                    charge("recurrence_multiply_adds", max(0, n+1-law["order"])*law["order"])
                value = recurrence_value(law, n)
                counter["recurrence_calls"] = counter.get("recurrence_calls", 0)+1
                counter["recurrence_multiply_adds"] = counter.get("recurrence_multiply_adds", 0)+max(0, n+1-law["order"])*law["order"]
                return term("const", value=str(value))
            if t["op"] == "represented":
                if requirements and any(v not in (None, False, "unrestricted") for v in requirements.values()):
                    raise ValueError("representation does not preserve requested legality/goal")
                r = materialize(self.theory.state, t["binding"])
                identity = digest({k: r[k] for k in ("basis", "action_matrices", "readout", "scope", "system_key")})
                value_key = digest([identity, t["args"][0]["letters"]])
                if identity not in self._compiled_spaces:
                    system = self.domain.linear_system()
                    basis = [sp.sympify(b) for b in r["basis"]]
                    rows = tuple(tuple(b.coeff(x) for x in system.variables) for b in basis)
                    matrices = {g: tuple(tuple(sp.Rational(x) for x in row) for row in m)
                                for g, m in r["action_matrices"].items()}
                    self._compiled_spaces[identity] = (rows, matrices, tuple(map(sp.Rational, r["readout"])))
                    counter["representation_compiles"] = counter.get("representation_compiles", 0)+1
                if value_key in self._observation_values:
                    values = self._observation_values[value_key]
                    counter["representation_cache_hits"] = counter.get("representation_cache_hits", 0)+1
                else:
                    rows, matrices, weights = self._compiled_spaces[identity]
                    for g in reversed(t["args"][0]["letters"]):
                        if charge is not None:
                            charge("matrix_multiply_adds", r["dimension"]**2)
                        weights = tuple(sum(w*row[j] for w, row in zip(weights, matrices[g]))
                                        for j in range(len(weights)))
                        counter["matrix_multiply_adds"] += r["dimension"]**2
                    if charge is not None:
                        charge("matrix_multiply_adds", r["dimension"]*r["ambient_dimension"])
                    values = tuple(sum(w*row[j] for w, row in zip(weights, rows))
                                   for j in range(r["ambient_dimension"]))
                    counter["matrix_multiply_adds"] += r["dimension"]*len(values)
                    if len(self._observation_values) >= self.theory.budget["library_corpus"]:
                        self._observation_values.pop(next(iter(self._observation_values)))
                    self._observation_values[value_key] = values
                counter["representation_calls"] += 1
                name = "__certified_"+digest(t)[:16]
                domain.sensors[name] = values
                domain.names.append(name)
                return term("var", name=name)
            return dict(t, args=[walk(a) for a in t.get("args", [])])
        result = domain.evaluate(walk(node), counter, charge=charge)
        return result, counter

    def record(self, program, primitive, parents=()):
        if not self.theory.budget["definitions"]:
            return
        key = digest(program)
        if key in self.state["seen_programs"]:
            return
        if len(self.state["corpus"]) >= self.theory.budget["library_corpus"]:
            return
        self.state["seen_programs"].append(key)
        self.state["corpus"].append({"id": key, "program": deepcopy(program),
             "primitive": deepcopy(primitive), "parents": list(parents),
             "cycle": self.theory.state["cycle"], "source": "self_generated_execution"})

    def signature(self, template, samples):
        parameters = {}
        for name, pair in samples.items():
            sorts = [("rational" if not isinstance(v, dict) else self.accepts(v)) for v in pair]
            if len(set(sorts)) != 1:
                raise ValueError("anti-unification crosses types")
            parameters[name] = sorts[0]
        instance = lib.instantiate_term(template, {n: pair[0] for n, pair in samples.items()})
        return {"parameters": parameters, "result": self.accepts(instance)}

    def learn(self):
        s, e = self.state, self.theory
        s["last_learn_size"] = len(s["corpus"])
        began = time.perf_counter()
        with lib.grammar(self.accepts):
            found = lib.learn(s["corpus"], pairs=e.budget["library_pairs"], keep=8,
                              admissible=lambda t: context_operations(t) >= 2)
            accepted = None
            for candidate in found["ranked"]:
                template = candidate["template"]
                if any(d["template"] == template for d in s["definitions"]):
                    continue
                try:
                    signature = self.signature(template, candidate["samples"])
                except ValueError:
                    continue
                index = len(s["definitions"])
                verdict = lib.utility(s["corpus"], template, index=index)
                if verdict["utility_bits"] <= 0 or verdict["failures"]:
                    continue
                dependencies = sorted(references(template))
                depth = 1 + max([s["definitions"][int(i)]["depth"] for i in dependencies] or [0])
                definition = {"index": index, "id": lib.definition_id(template),
                    "template": template, "signature": signature, "scope": deepcopy(self.domain.scope),
                    "dependencies": dependencies, "depth": depth, "born": e.state["cycle"],
                    "definition_bits": verdict["definition_bits"], "utility_bits": verdict["utility_bits"],
                    "reuse_count": 0, "acquisition_sources": [r["id"] for r in verdict["rewritten"] if r["sites"]],
                    "certificate": "capture-free definitional expansion with typed shared arguments"}
                s["definitions"].append(definition)
                # Check every changed program against its original primitive meaning.
                for row, rewritten in zip(s["corpus"], verdict["rewritten"]):
                    if self.primitive(rewritten["program"]) != row["primitive"]:
                        raise AssertionError("library abstraction changed primitive computation")
                    row["program"] = rewritten["program"]
                accepted = definition
                s["grammar_versions"].append({"cycle": e.state["cycle"], "table": self.table(),
                                               "new_definition": definition["id"]})
                e.event("dsl_definition_acquired", definition=definition)
                break
        s["attempts"].append({"cycle": e.state["cycle"], "corpus": len(s["corpus"]),
            "pairs": found["pairs_tried"], "offered": found["offered"], "evaluated": found["evaluated"],
            "operation_aliases_excluded": found["excluded_by_contract"],
            "accepted": accepted["id"] if accepted else None,
            "seconds": time.perf_counter()-began})
        e.charge("library_acquisition", pairs=found["pairs_tried"],
                 candidates=found["evaluated"], seconds=time.perf_counter()-began)

    def synthesize(self):
        e, s = self.theory, self.state
        s["last_synthesis_size"] = len(s["corpus"])+len(s["definitions"])+len(e.state["representations"])
        pool = [e.state["concepts"][cid]["definition"] for cid in e.state["active_concepts"]]
        pool += [row["program"] for row in s["executions"][-e.budget["batch"]:]]
        words = list(islice(chain.from_iterable(product(self.domain.actions, repeat=n)
                     for n in range(1, e.budget["word_length"]+1)),
                     s["word_cursor"], s["word_cursor"]+e.budget["batch"])) if self.domain.actions else []
        naturals = list(range(s["natural_cursor"], s["natural_cursor"]+e.budget["batch"]))
        s["word_cursor"] += len(words)
        s["natural_cursor"] += len(naturals)
        pool += [term("word", letters=list(w)) for w in words]
        pool += [term("natural", value=n) for n in naturals]
        by_sort = {}
        for p in pool:
            by_sort.setdefault(self.accepts(p), []).append(p)
        ranked = sorted(s["definitions"], key=lambda d: (
            -d.get("downstream_saved_bits", 0)/max(1, d["reuse_count"]), -d["utility_bits"], d["index"]))
        search_cost = {}
        arguments = {d["index"]: {name: by_sort.get(sort, [])
                      for name, sort in d["signature"]["parameters"].items()} for d in ranked}
        # Keep computation syntax here: evaluating a recurrence to a constant
        # before deduplication erases the new argument and its procedure route.
        with lib.grammar(self.accepts):
            calls = lib.call_candidates(ranked, pool, limit=e.budget["batch"],
                exclude=[lib.key(self.expand(row["program"])) for row in s["corpus"]],
                table=self.table(), scan=e.budget["library_pairs"], normalise=self.expand,
                stats=search_cost, argument_pools=arguments)
        e.charge("dsl_search", **search_cost)
        programs = [c["call"] for c in calls]
        # Certified spaces become callable operations from action words to scalar
        # observations. Word construction uses only the declared action alphabet.
        if e.flags["representation_reuse"]:
            from math_os_prototype.runtime_typed_planner import (
                initial_fact, RuntimePrimitive, PrimitiveResult, synthesize_typed_plan)
            facts = [initial_fact("action_word", term("word", letters=list(w))) for w in words[:e.budget["batch"]]]
            primitives = []
            for rid in e.state["representations"]:
                def execute(args, rid=rid):
                    program = term("represented", args[0].value, binding=rid)
                    if digest(program) in s["seen_calls"]:
                        return None
                    return PrimitiveResult(program, {"binding": rid, "scope": self.domain.scope})
                primitives.append(RuntimePrimitive(rid, ("action_word",), "scalar_observation", execute))
            if facts and primitives:
                plan = synthesize_typed_plan(facts, primitives, ["scalar_observation"],
                    max_depth=1, max_states=e.budget["library_pairs"])
                programs.extend(f.value for f in plan.facts if f.sort == "scalar_observation")
                e.charge("dsl_search", typed_states=plan.states_explored)
            if e.flags["theorem_reuse"] and s["recurrence_operations"]:
                facts = [initial_fact("natural", term("natural", value=n))
                         for n in naturals]
                primitives = []
                for pid in s["recurrence_operations"]:
                    def execute(args, pid=pid):
                        return PrimitiveResult(term("recurrence", args[0].value, procedure=pid),
                                               {"procedure": pid})
                    primitives.append(RuntimePrimitive(pid, ("natural",), "scalar_observation", execute))
                plan = synthesize_typed_plan(facts, primitives, ["scalar_observation"],
                    max_depth=1, max_states=e.budget["library_pairs"])
                programs.extend(f.value for f in plan.facts if f.sort == "scalar_observation")
                e.charge("dsl_search", typed_states=plan.states_explored)
        # Re-enter the same domain constructors with acquired executable terms.
        # Rotate parents; selecting only the last outputs would starve earlier
        # definitions whenever a batch contains many represented observations.
        parents = [r["program"] for r in s["executions"]]
        if parents:
            parent = parents[s["composition_cursor"] % len(parents)]
            s["composition_cursor"] += 1
            composed = self.domain.compose(parent, pool, type_of=self.accepts)
            programs.extend(islice(composed, e.budget["batch"]))
        for program in programs:
            if digest(program) in s["seen_calls"]:
                continue
            s["seen_calls"].append(digest(program))
            primitive = self.primitive(program)
            if size(primitive) > e.budget["expanded_size"] or program_size(program) > e.budget["term_size"]:
                e.charge("dsl_search", size_refusals=1)
                continue
            actual, counter = self.evaluate(program)
            expected = self.domain.evaluate(primitive)
            if self.domain.semantic_key(actual) != self.domain.semantic_key(expected):
                raise AssertionError("DSL execution differs from independent primitive execution")
            row = {"cycle": e.state["cycle"], "program": program, "primitive": primitive,
                "definitions": sorted(references(program)), "agree": True,
                "result": [str(v) for v in actual] if isinstance(actual, tuple) else str(actual),
                "execution_cost": counter, "call_bits": lib.cost(program),
                "expanded_bits": lib.cost(primitive), "origin": "self_generated"}
            s["executions"].append(row)
            for ref in row["definitions"]:
                s["definitions"][int(ref)]["reuse_count"] += 1
                definition = s["definitions"][int(ref)]
                definition["downstream_saved_bits"] = definition.get("downstream_saved_bits", 0) + row["expanded_bits"]-row["call_bits"]
            e.charge("dsl_execution", **counter)
            e.charge("dsl_shadow_audit", semantic_nodes=size(primitive))
            self.record(program, primitive)
            e.state["pending_terms"].append({"term": primitive, "program": program, "parents": []})
            e.event("dsl_program_executed", **{k: v for k, v in row.items() if k != "cycle"})

    def options(self):
        e, s = self.theory, self.state
        if not e.budget["definitions"]:
            return []
        out = []
        if len(s["definitions"]) < e.budget["definitions"] and len(s["corpus"])-s["last_learn_size"] >= e.budget["library_interval"]:
            out.append(("abstract", e.budget["library_pairs"]))
        generation = len(s["corpus"])+len(s["definitions"])+len(e.state["representations"])
        if e.flags["dsl_reuse"] and generation != s["last_synthesis_size"] and (s["definitions"] or e.state["representations"]):
            out.append(("synthesize", e.budget["batch"]))
        return out

    def solve_observation(self, task, *, acquired=True, definitions_enabled=True):
        """Synthesize a program from its exact finite-model specification.

        This is a goal adapter for the existing typed planner. No witness or
        acquired body is supplied by the caller. Equality on the complete model
        is a congruence for the declared pure operations, not for legality.
        """
        start = time.perf_counter()
        from math_os_prototype.runtime_typed_planner import (
            initial_fact, RuntimePrimitive, PrimitiveResult, synthesize_typed_plan)
        if self.domain.scope["kind"] != "complete_finite_model":
            raise ValueError("observation synthesis requires a complete finite model")
        if task["scope"] != self.domain.scope or task.get("requirements"):
            raise ValueError("query scope or additional requirements are unsupported")
        allowed = {"id", "scope", "values", "budget", "requirements"}
        if set(task) - allowed or len(task["values"]) != len(self.domain.models):
            raise ValueError("query takes values, not a witness or a route")
        target = [str(sp.Rational(v)) for v in task["values"]]
        budget = task["budget"]
        required = {"states", "depth", "program_size", "expanded_size"}
        if not required <= set(budget) <= required | {"work"} or any(
                type(v) is not int or v < 1 for v in budget.values()):
            raise ValueError("positive frozen query bounds required")
        before = digest(self.theory.state)
        # Each external task starts cold in every condition; no answer cache
        # from an earlier evaluation task is counted as acquired capability.
        self._compiled_spaces.clear()
        self._observation_values.clear()
        counter = {"candidate_evaluations": 0, "size_refusals": 0, "type_refusals": 0,
                   "semantic_nodes": 0, "representation_calls": 0,
                   "matrix_multiply_adds": 0, "prover_calls": 0, "acquisition_calls": 0,
                   "attempted_applications": 0, "verification_checks": 0,
                   "primitive_expansion_seconds": 0, "evaluation_seconds": 0,
                   "candidate_build_seconds": 0, "verification_seconds": 0,
                   "rewrite_matching_checks": 0}
        work = {"used": 0, "limit": budget.get("work"), "categories": {}}
        class WorkLimit(RuntimeError):
            pass
        def charge(kind, count):
            if work["limit"] is not None and work["used"]+count > work["limit"]:
                raise WorkLimit("shared interpreter work budget exhausted")
            work["used"] += count
            work["categories"][kind] = work["categories"].get(kind, 0)+count
        def payload(program):
            if program_size(program) > budget["program_size"]:
                counter["size_refusals"] += 1
                return None
            began = time.perf_counter()
            try:
                expanded = self.primitive(program, counter=counter, charge=charge)
            finally:
                counter["primitive_expansion_seconds"] += time.perf_counter()-began
            if size(expanded) > budget["expanded_size"]:
                counter["size_refusals"] += 1
                return None
            sort = self.accepts(program, counter=counter)
            if sort in {"action_word", "natural"}:
                return {"program": program, "values": program}
            began = time.perf_counter()
            try:
                result, _ = self.evaluate(program, counter=counter, charge=charge)
                counter["candidate_evaluations"] += 1
            finally:
                counter["evaluation_seconds"] += time.perf_counter()-began
            return {"program": program, "values": [str(v) for v in result]}
        def primitive(name, inputs, output, build):
            def execute(args):
                counter["attempted_applications"] += 1
                try:
                    began = time.perf_counter()
                    p = build([a.value["program"] for a in args])
                    counter["candidate_build_seconds"] += time.perf_counter()-began
                    value = payload(p)
                except (ValueError, TypeError):
                    counter["type_refusals"] += 1
                    return None
                return PrimitiveResult(value, {"scope": self.domain.scope, "program": p}) if value else None
            return RuntimePrimitive(name, tuple(inputs), output, execute)
        seeds = self.domain.seeds()
        # Common inputs in every condition; acquired computations, not a larger
        # external input set, distinguish B from A and C.
        seeds += [term("word", letters=[g]) for g in self.domain.actions]
        seeds += [term("natural", value=n) for n in (0, 1)]
        if len(seeds) > budget["states"]:
            raise ValueError("state budget cannot hold the common initial inputs")
        facts = []
        operations = []
        if acquired:
            definitions = sorted(self.state["definitions"] if definitions_enabled else [], key=lambda d: (
                -d.get("downstream_saved_bits", 0)/max(1, d["reuse_count"]), d["index"]))
            for d in definitions:
                names = list(d["signature"]["parameters"])
                def build(args, d=d, names=names):
                    return {"op": lib.USE, "abstraction": d["index"], "arguments": dict(zip(names, args))}
                operations.append(primitive("definition:"+d["id"],
                    list(d["signature"]["parameters"].values()), d["signature"]["result"], build))
            for rid in self.state["observation_operations"]:
                operations.append(primitive("representation:"+rid, ["action_word"], "scalar",
                    lambda a, rid=rid: term("represented", a[0], binding=rid)))
            for pid in self.state["recurrence_operations"]:
                operations.append(primitive("recurrence:"+pid, ["natural"], "scalar",
                    lambda a, pid=pid: term("recurrence", a[0], procedure=pid)))
        representatives = [self.domain.seeds()[0]]
        if "eq" in self.domain.operations:
            representatives.append(term("eq", representatives[0], representatives[0]))
        known = set()
        for parent in representatives:
            for prototype in self.domain.compose(parent, representatives):
                key = digest({k: v for k, v in prototype.items() if k != "args"})
                if key in known:
                    continue
                known.add(key)
                operations.append(primitive("primitive:"+key,
                    [self.domain.type_of(a) for a in prototype["args"]], self.domain.type_of(prototype),
                    lambda a, p=prototype: dict(p, args=a)))
        program, stopped, plan = None, "bounded_search_exhausted", None
        try:
            facts = [initial_fact(self.accepts(p), payload(p)) for p in seeds]
            if any(f.value is None for f in facts):
                raise ValueError("size bounds exclude common initial inputs")
            plan = synthesize_typed_plan(facts, operations, ["scalar"],
                max_depth=budget["depth"], max_states=budget["states"], fair=True,
                goal_predicates={"scalar": lambda f: f.value["values"] == target},
                value_key=lambda sort, v: digest(v["values"]))
            solution = plan.goals.get("scalar")
            if solution is not None:
                began = time.perf_counter()
                try:
                    expanded = self.primitive(solution.value["program"], counter=counter, charge=charge)
                    independent = [str(v) for v in self.domain.evaluate(expanded, charge=charge)]
                    counter["verification_checks"] += len(target)
                    if independent != target:
                        raise AssertionError("synthesized solution fails independent finite-model replay")
                    program, stopped = solution.value["program"], "solved"
                finally:
                    counter["verification_seconds"] += time.perf_counter()-began
        except WorkLimit:
            stopped = "work_budget_exhausted"
        if digest(self.theory.state) != before:
            raise AssertionError("query changed the acquired archive")
        bodies = [{k: d[k] for k in ("id", "index", "signature", "template", "scope", "dependencies")}
                  for d in self.state["definitions"]]
        structural_bits = sum(lib.cost(d) for d in bodies)
        certified_bits = sum(lib.cost(self.theory.state.get(k, {})) for k in
                             ("observable_spaces", "representations", "procedures"))
        active_bits = (structural_bits if acquired and definitions_enabled else 0)+(certified_bits if acquired else 0)
        return {"task": task["id"], "solved": program is not None, "program": program,
            "definitions_used": sorted(references(program)),
            "states_explored": len(seeds)+counter["attempted_applications"], "costs": counter,
            "work": work, "archive_digest": before,
            "enabled_operations": [o.name for o in operations],
            "library_cost": {"structural_definition_bits": structural_bits,
                "certified_operation_bits": certified_bits, "active_bits": active_bits,
                "stored_bits": structural_bits+certified_bits},
            "seconds": time.perf_counter()-start, "archive_unchanged": True,
            "proof": {"kind": "complete_finite_model_replay", "scope": self.domain.scope,
                      "checks": len(target)} if program else None,
            "stop": stopped, "program_bits": lib.cost(program) if program else None,
            "program_and_library_bits": lib.cost(program)+active_bits if program else None}
