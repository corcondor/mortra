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
from math_os_prototype.theory_domain import term, size, recurrence_value, _parsed_literal
from math_os_prototype.theory_spaces import materialize
from math_os_prototype.representation_progress import digest, encoding


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
        self.state.setdefault("semantic_relations", [])
        self.state.setdefault("semantic_discoveries", [])
        self.state.setdefault("semantic_uses", [])
        # Bodies live in the bounded sample or existing execution records.
        # Only sources of accepted definitions get additional immutable copies.
        self.state.setdefault("acquisition_evidence", {})
        self.state.setdefault("experience_count", len(self.state["seen_programs"]))
        self.state.setdefault("corpus_arrivals", len(self.state["corpus"]))
        self.state.setdefault("corpus_version", len(self.state["corpus"]))
        self.state.setdefault("last_learn_version", self.state["last_learn_size"])
        self.state.setdefault("last_learn_arrivals", self.state["last_learn_size"])
        self.state.setdefault("last_learn_knowledge", None)
        self.state.setdefault("last_synthesis_generation", self.state["last_synthesis_size"])
        self.state.setdefault("corpus_events", [])
        self._seen_programs = set(self.state["seen_programs"])
        # Interpreter caches, not learned knowledge; rebuilding them is charged.
        self._compiled_spaces = {}
        self._observation_values = {}
        self._definition_table_cache = None

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

    def _execution_table(self, counter):
        """Reuse a detached table only while every definition body is unchanged.

        Public table() still returns a fresh copy. Macro resolution continues
        checking the seal, while accepts() checks current signatures and scope.
        """
        began = time.perf_counter()
        templates = {d["index"]: d["template"] for d in self.state["definitions"]}
        if not getattr(self.domain, "syntax_cache_enabled", True):
            result = lib.definition_table(templates)
            if counter is not None:
                counter["definition_table_builds"] = counter.get("definition_table_builds", 0)+1
                counter["definition_table_seconds"] = counter.get("definition_table_seconds", 0)+time.perf_counter()-began
            return result
        key = encoding(templates)
        hit = self._definition_table_cache is not None and self._definition_table_cache[0] == key
        if not hit:
            self._definition_table_cache = (key, lib.definition_table(templates))
        if counter is not None:
            event = "definition_table_cache_hits" if hit else "definition_table_builds"
            counter[event] = counter.get(event, 0)+1
            counter["definition_table_key_bytes"] = counter.get("definition_table_key_bytes", 0)+len(key)
            counter["definition_table_seconds"] = counter.get("definition_table_seconds", 0)+time.perf_counter()-began
        return self._definition_table_cache[1]

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
                actual = "rational" if not isinstance(value, dict) and self.domain.parse_literal(value).is_Rational else self.accepts(value, counter=counter)
                if actual != expected:
                    raise ValueError("call argument type mismatch")
            return definition["signature"]["result"]
        if node.get("op") == "word":
            if node.get("args") != [] or any(g not in self.domain.actions for g in node["letters"]):
                raise ValueError("invalid action word")
            return "action_word"
        if node.get("op") == "natural":
            number = self.domain.parse_literal(node["value"])
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
            return lib.expand_for_execution(node, self._execution_table(counter), stats=counter, charge=charge)

    def primitive(self, node, *, counter=None, charge=None):
        """Independent replay lowering. Never required just to size a candidate."""
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

    def execution_shape(self, program, *, counter=None, charge=None):
        """Exact old lowered AST size, without evaluating an observation.

        Recurrence lowering produces one constant regardless of n. Keep that
        same size policy, but estimate/charge its interpreter work separately.
        """
        node = self.expand(program, counter=counter, charge=charge)
        def walk(t):
            if charge:
                charge("shape_visits", 1)
            if counter is not None:
                counter["shape_visits"] = counter.get("shape_visits", 0)+1
            if t["op"] == "recurrence":
                return 1
            if t["op"] == "represented":
                c = self.theory.state["concepts"][self.theory.state["representations"][t["binding"]]["concept"]]
                return len(t["args"][0]["letters"])+size(c["definition"])
            return 1+sum(walk(a) for a in t.get("args", []))
        return walk(node)

    def execution_estimate(self, program, *, counter=None, charge=None):
        """Cold arithmetic work estimate, not a claim about wall-clock time."""
        node = self.expand(program, counter=counter, charge=charge)
        states = len(self.domain.models)
        def walk(t):
            if charge:
                charge("cost_model_visits", 1)
            if counter is not None:
                counter["cost_model_visits"] = counter.get("cost_model_visits", 0)+1
            if t["op"] == "recurrence":
                _, law = self.law(t["procedure"])
                return states+max(0, int(t["args"][0]["value"])+1-law["order"])*law["order"]
            if t["op"] == "represented":
                r = materialize(self.theory.state, t["binding"])
                return states+len(t["args"][0]["letters"])*r["dimension"]**2+r["dimension"]*r["ambient_dimension"]
            return states+sum(walk(a) for a in t.get("args", []))
        return walk(node), lib.cost(program)

    def edit(self, program, *, counter=None, charge=None):
        from math_os_prototype.theory_semantic_edit import rewrite
        return rewrite(self, program, counter=counter, charge=charge)

    def active_definitions(self, editing):
        if not editing:
            return self.state["definitions"]
        from math_os_prototype.theory_semantic_edit import validate
        projections = set()
        equivalent = set()
        for r in self.state["semantic_relations"]:
            validate(self, r)
            if r["kind"] == "projection":
                projections.add(r["definition_index"])
            # One syntactic branch per proved operator alias. Both implementations
            # remain archived, and concrete-call editing still compares costs.
            if any(d["index"] < r["definition_index"] and d["template"] == r["right"]
                   and d["signature"] == r["signature"] for d in self.state["definitions"]):
                equivalent.add(r["definition_index"])
        return [d for d in self.state["definitions"] if d["index"] not in projections | equivalent]

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

    def record(self, program, primitive, parents=(), *, evaluated=None, execution=None):
        if not self.theory.budget["definitions"]:
            return
        began = time.perf_counter()
        e, s = self.theory, self.state
        e.charge("corpus_feedback", record_calls=1)
        try:
            key = digest(program)
            if key in self._seen_programs:
                e.charge("corpus_feedback", duplicate_experiences=1)
                s["corpus_events"].append({"cycle": e.state["cycle"], "experience": key,
                    "status": "duplicate", "execution": execution, "version": s["corpus_version"]})
                return
            self._seen_programs.add(key)
            s["seen_programs"].append(key)
            s["experience_count"] += 1
            row = {"id": key, "program": deepcopy(program), "primitive": deepcopy(primitive),
                "parents": list(parents), "cycle": e.state["cycle"],
                "source": "self_generated_execution", "sequence": s["experience_count"],
                "execution": execution}
            if evaluated is not None:
                row["evaluation"] = {"semantic_key": self.domain.semantic_key(evaluated),
                    "scope": deepcopy(self.domain.scope), "kind": "exact_domain_evaluation"}
            full = len(s["corpus"]) >= e.budget["library_corpus"]
            admitted = not full or e.flags.get("corpus_refresh", False)
            retired = s["corpus"].pop(0)["id"] if admitted and full else None
            if admitted:
                s["corpus"].append(row)
                s["corpus_version"] += 1
                s["corpus_arrivals"] += 1
                e.charge("corpus_feedback", sample_bytes_written=len(encoding(row)))
            e.charge("corpus_feedback", admitted=int(admitted), retired=int(retired is not None),
                     refused_capacity=int(not admitted))
            s["corpus_events"].append({"cycle": e.state["cycle"], "experience": key,
                "sequence": row["sequence"], "admitted": admitted, "retired": retired,
                "status": "admitted" if admitted else "refused_capacity", "execution": execution,
                "active_size": len(s["corpus"]), "version": s["corpus_version"]})
        finally:
            e.charge("corpus_feedback", seconds=time.perf_counter()-began)

    def knowledge_input(self):
        s = self.state
        return digest({"definitions": [{k: d[k] for k in ("template", "signature", "scope")}
                                       for d in s["definitions"]],
            "observations": s["observation_operations"], "recurrences": s["recurrence_operations"],
            "relations": s["semantic_relations"]})

    def generation(self):
        e, s = self.theory, self.state
        if not e.flags.get("corpus_refresh"):
            return len(s["corpus"])+len(s["definitions"])+len(e.state["representations"])
        began = time.perf_counter()
        result = digest({"corpus": s["corpus_version"], "knowledge": self.knowledge_input(),
            "active": [e.state["concepts"][cid]["definition"] for cid in e.state["active_concepts"]],
            "executions": len(s["executions"])})
        e.charge("corpus_input_matching", seconds=time.perf_counter()-began, checks=1)
        return result

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
        input_version = s["corpus_version"]
        input_arrivals = s["corpus_arrivals"]
        began = time.perf_counter()
        certification_seconds = 0
        view_cost = {}
        views = [(s["corpus"], [])]
        if e.flags.get("semantic_edits") and s["semantic_relations"]:
            alternative, uses = [], []
            for row in s["corpus"]:
                program, proofs = self.edit(row["program"], counter=view_cost)
                alternative.append(dict(row, program=program,
                    primitive=self.primitive(program,
                        charge=lambda k, n: view_cost.__setitem__(k, view_cost.get(k, 0)+n)) if proofs else row["primitive"]))
                uses.append({"source": row["id"], "before": row["program"], "after": program,
                             "proofs": proofs})
            if any(u["proofs"] for u in uses):
                views.append((alternative, uses))
        with lib.grammar(self.accepts):
            offers = []
            searches = []
            for corpus, edits in views:
                found = lib.learn(corpus, pairs=e.budget["library_pairs"]//len(views), keep=8,
                                  admissible=lambda t: context_operations(t) >= 2)
                offers.extend((candidate, corpus, edits) for candidate in found["ranked"])
                searches.append(found)
            accepted = None
            # Each alternative is scored on one copy of each original program;
            # equivalent views are never counted as extra training examples.
            for candidate, corpus, edits in sorted(offers, key=lambda row: -row[0]["verdict"]["utility_bits"]):
                template = candidate["template"]
                if any(d["template"] == template for d in s["definitions"]):
                    continue
                try:
                    signature = self.signature(template, candidate["samples"])
                except ValueError:
                    continue
                index = len(s["definitions"])
                verdict = lib.utility(corpus, template, index=index)
                if verdict["utility_bits"] <= 0 or verdict["failures"]:
                    continue
                dependencies = sorted(references(template))
                depth = 1 + max([s["definitions"][int(i)]["depth"] for i in dependencies] or [0])
                definition = {"index": index, "id": lib.definition_id(template),
                    "template": template, "signature": signature, "scope": deepcopy(self.domain.scope),
                    "dependencies": dependencies, "depth": depth, "born": e.state["cycle"],
                    "definition_bits": verdict["definition_bits"], "utility_bits": verdict["utility_bits"],
                    "reuse_count": 0, "acquisition_sources": [r["id"] for r in verdict["rewritten"] if r["sites"]],
                    "corpus_version": s["corpus_version"],
                    "corpus_arrivals": input_arrivals,
                    "certificate": "capture-free definitional expansion with typed shared arguments"}
                if edits:
                    definition["semantic_sources"] = [u for u in edits if u["proofs"]]
                # Retain exactly the source rows needed by this acquisition,
                # keyed by full snapshot, not by a mutable corpus row's ID.
                evidence_start = time.perf_counter()
                used = set(definition["acquisition_sources"]) | {u["source"] for u in definition.get("semantic_sources", [])}
                definition["source_evidence"] = {}
                for row in s["corpus"]:
                    if row["id"] in used:
                        evidence_id = digest(row)
                        if evidence_id not in s["acquisition_evidence"]:
                            s["acquisition_evidence"][evidence_id] = deepcopy(row)
                            e.charge("corpus_proof_storage", rows=1, bytes=len(encoding(row)))
                        definition["source_evidence"][row["id"]] = evidence_id
                e.charge("corpus_proof_storage", seconds=time.perf_counter()-evidence_start)
                s["definitions"].append(definition)
                changed = False
                # Check every changed program against its original primitive meaning.
                for row, source, rewritten in zip(s["corpus"], corpus, verdict["rewritten"]):
                    changed |= row["program"] != rewritten["program"] or row["primitive"] != source["primitive"]
                    if self.primitive(rewritten["program"]) != source["primitive"]:
                        raise AssertionError("library abstraction changed primitive computation")
                    if row["primitive"] != source["primitive"]:
                        row.setdefault("semantic_history", []).append({"program": row["program"],
                            "primitive": row["primitive"], "edits": [u for u in edits if u["source"] == row["id"]]})
                        row["primitive"] = source["primitive"]
                    row["program"] = rewritten["program"]
                if changed:
                    s["corpus_version"] += 1
                accepted = definition
                s["grammar_versions"].append({"cycle": e.state["cycle"], "table": self.table(),
                                               "new_definition": definition["id"]})
                e.event("dsl_definition_acquired", definition=definition)
                if e.flags.get("semantic_edits"):
                    from math_os_prototype.theory_semantic_edit import discover
                    discovery = discover(self, definition)
                    s["semantic_discoveries"].append(discovery)
                    s["semantic_relations"].extend(discovery["relations"])
                    certification_seconds += discovery["seconds"]
                    e.charge("dsl_semantic_certification", seconds=discovery["certification_seconds"], **discovery["costs"])
                    e.charge("dsl_semantic_discovery", seconds=discovery["discovery_seconds"])
                    s["grammar_versions"].append({"cycle": e.state["cycle"],
                        "active_definition_indices": [d["index"] for d in self.active_definitions(True)],
                        "new_equations": [r["id"] for r in discovery["relations"]]})
                    e.event("dsl_semantic_relation_search", discovery=discovery)
                break
        s["attempts"].append({"cycle": e.state["cycle"], "corpus": len(s["corpus"]),
            "input_version": input_version, "corpus_version": s["corpus_version"],
            "corpus_arrivals": input_arrivals, "corpus_ids": [r["id"] for r in s["corpus"]],
            "pairs": sum(f["pairs_tried"] for f in searches), "offered": sum(f["offered"] for f in searches),
            "evaluated": sum(f["evaluated"] for f in searches), "equivalent_views": len(views), "view_cost": view_cost,
            "operation_aliases_excluded": [x for f in searches for x in f["excluded_by_contract"]],
            "accepted": accepted["id"] if accepted else None,
            "seconds": time.perf_counter()-began})
        # Consume the learner's own equivalent edits too, but never count them
        # as incoming experience or as a reason to immediately learn again.
        s["last_learn_version"] = s["corpus_version"]
        s["last_learn_arrivals"] = s["corpus_arrivals"]
        s["last_learn_knowledge"] = self.knowledge_input()
        e.charge("library_acquisition", pairs=sum(f["pairs_tried"] for f in searches),
                 candidates=sum(f["evaluated"] for f in searches), seconds=time.perf_counter()-began-certification_seconds,
                 **view_cost)

    def synthesize(self):
        e, s = self.theory, self.state
        s["last_synthesis_size"] = len(s["corpus"])+len(s["definitions"])+len(e.state["representations"])
        s["last_synthesis_generation"] = self.generation()
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
        ranked = sorted(self.active_definitions(e.flags.get("semantic_edits", False)), key=lambda d: (
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
            shape_counter = {}
            shape_size = self.execution_shape(program, counter=shape_counter)
            e.charge("dsl_candidate_validation", **shape_counter)
            if shape_size > e.budget["expanded_size"] or program_size(program) > e.budget["term_size"]:
                e.charge("dsl_search", size_refusals=1)
                continue
            original = deepcopy(program)
            edit_counter, proofs = {}, []
            edit_started = time.perf_counter()
            if e.flags.get("semantic_edits"):
                program, proofs = self.edit(program, counter=edit_counter)
            e.charge("dsl_semantic_optimization", seconds=time.perf_counter()-edit_started, **edit_counter)
            evaluation_started = time.perf_counter()
            actual, counter = self.evaluate(program)
            counter["seconds"] = time.perf_counter()-evaluation_started
            replay_started = time.perf_counter()
            replay_counter = {}
            def replay_charge(k, n):
                replay_counter[k] = replay_counter.get(k, 0)+n
            original_primitive = self.primitive(original, charge=replay_charge)
            expected = self.domain.evaluate(original_primitive, charge=replay_charge)
            primitive = self.primitive(program, charge=replay_charge) if proofs else original_primitive
            e.charge("dsl_independent_replay", seconds=time.perf_counter()-replay_started, **replay_counter)
            if self.domain.semantic_key(actual) != self.domain.semantic_key(expected):
                raise AssertionError("DSL execution differs from independent primitive execution")
            row = {"cycle": e.state["cycle"], "program": program, "primitive": primitive,
                "original_program": original, "semantic_proofs": proofs,
                "independent_replay_cost": replay_counter,
                "definitions": sorted(references(program)), "agree": True,
                "result": [str(v) for v in actual] if isinstance(actual, tuple) else str(actual),
                "execution_cost": counter, "call_bits": lib.cost(program),
                "expanded_bits": lib.cost(primitive), "origin": "self_generated"}
            s["executions"].append(row)
            if proofs:
                s["semantic_uses"].append({"cycle": e.state["cycle"], "before": original,
                    "after": program, "proofs": proofs, "result": row["result"],
                    "execution_cost": counter, "replay_cost": replay_counter})
            for ref in row["definitions"]:
                s["definitions"][int(ref)]["reuse_count"] += 1
                definition = s["definitions"][int(ref)]
                definition["downstream_saved_bits"] = definition.get("downstream_saved_bits", 0) + row["expanded_bits"]-row["call_bits"]
            e.charge("dsl_execution", **counter)
            e.charge("dsl_shadow_audit", semantic_nodes=size(primitive))
            self.record(program, primitive, evaluated=actual, execution=len(s["executions"])-1)
            e.state["pending_terms"].append({"term": primitive, "program": program, "parents": []})
            e.event("dsl_program_executed", **{k: v for k, v in row.items() if k != "cycle"})

    def options(self):
        e, s = self.theory, self.state
        if not e.budget["definitions"]:
            return []
        out = []
        began = time.perf_counter()
        new_experience = (s["corpus_arrivals"]-s["last_learn_arrivals"] if e.flags.get("corpus_refresh")
                          else len(s["corpus"])-s["last_learn_size"])
        knowledge_changed = (e.flags.get("corpus_refresh") and s["last_learn_knowledge"] is not None
                             and self.knowledge_input() != s["last_learn_knowledge"])
        if len(s["definitions"]) < e.budget["definitions"] and (new_experience >= e.budget["library_interval"] or knowledge_changed):
            out.append(("abstract", e.budget["library_pairs"]))
        if e.flags["dsl_reuse"] and self.generation() != s["last_synthesis_generation"] and (s["definitions"] or e.state["representations"]):
            out.append(("synthesize", e.budget["batch"]))
        e.charge("corpus_eligibility", seconds=time.perf_counter()-began, checks=1)
        return out

    def solve_observation(self, task, *, acquired=True, definitions_enabled=True, execution_mode="certified"):
        """Synthesize a program from its exact finite-model specification.

        This is a goal adapter for the existing typed planner. No witness or
        acquired body is supplied by the caller. Equality on the complete model
        is a congruence for the declared pure operations, not for legality.
        """
        start = time.perf_counter()
        if execution_mode not in {"legacy", "certified", "edited"}:
            raise ValueError("unknown execution mode")
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
        self._definition_table_cache = None
        _parsed_literal.cache_clear()
        counter = {"candidate_evaluations": 0, "size_refusals": 0, "type_refusals": 0,
                   "semantic_nodes": 0, "representation_calls": 0,
                   "matrix_multiply_adds": 0, "prover_calls": 0, "acquisition_calls": 0,
                   "attempted_applications": 0, "verification_checks": 0,
                   "primitive_expansion_seconds": 0, "evaluation_seconds": 0,
                   "candidate_build_seconds": 0, "verification_seconds": 0,
                   "rewrite_matching_checks": 0}
        work = {"used": 0, "limit": budget.get("work"), "categories": {}}
        replay_work = {"used": 0, "categories": {}}
        rewrite_trace = []
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
                expanded_size = size(self.primitive(program, counter=counter, charge=charge)) if execution_mode == "legacy" else self.execution_shape(program, counter=counter, charge=charge)
            finally:
                counter["primitive_expansion_seconds"] += time.perf_counter()-began
            if expanded_size > budget["expanded_size"]:
                counter["size_refusals"] += 1
                return None
            sort = self.accepts(program, counter=counter)
            if sort in {"action_word", "natural"}:
                return {"program": program, "values": program}
            original = program
            if execution_mode == "edited":
                began = time.perf_counter()
                program, proofs = self.edit(program, counter=counter, charge=charge)
                counter["semantic_edit_seconds"] = counter.get("semantic_edit_seconds", 0)+time.perf_counter()-began
                if proofs:
                    rewrite_trace.append({"before": original, "after": program, "proofs": proofs})
            began = time.perf_counter()
            try:
                result, _ = self.evaluate(program, counter=counter, charge=charge)
                counter["candidate_evaluations"] += 1
            finally:
                counter["evaluation_seconds"] += time.perf_counter()-began
            return {"program": program, "original_program": original, "values": [str(v) for v in result]}
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
            definitions = sorted(self.active_definitions(execution_mode == "edited") if definitions_enabled else [], key=lambda d: (
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
                    def replay_charge(kind, count):
                        charge(kind, count)
                        replay_work["used"] += count
                        replay_work["categories"][kind] = replay_work["categories"].get(kind, 0)+count
                    expanded = self.primitive(solution.value.get("original_program", solution.value["program"]), counter=counter, charge=replay_charge)
                    independent = [str(v) for v in self.domain.evaluate(expanded, charge=replay_charge)]
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
        equation_bits = lib.cost(self.state["semantic_relations"])
        active_bits = (structural_bits if acquired and definitions_enabled else 0)+(certified_bits if acquired else 0)+(equation_bits if execution_mode == "edited" else 0)
        literal_cache = _parsed_literal.cache_info()
        counter.update(literal_parse_cache_hits=literal_cache.hits, literal_parse_cache_misses=literal_cache.misses,
                       literal_parse_cache_entries=literal_cache.currsize)
        return {"task": task["id"], "solved": program is not None, "program": program,
            "definitions_used": sorted(references(program)),
            "states_explored": len(seeds)+counter["attempted_applications"], "costs": counter,
            "work": work, "independent_replay_work": replay_work,
            "normal_work_used": work["used"]-replay_work["used"],
            "semantic_rewrite_trace": rewrite_trace, "execution_mode": execution_mode, "archive_digest": before,
            "syntax_cache_enabled": getattr(self.domain, "syntax_cache_enabled", True),
            "enabled_operations": [o.name for o in operations],
            "library_cost": {"structural_definition_bits": structural_bits,
                "certified_operation_bits": certified_bits, "active_bits": active_bits,
                "semantic_equation_bits": equation_bits, "stored_bits": structural_bits+certified_bits+equation_bits},
            "seconds": time.perf_counter()-start, "archive_unchanged": True,
            "proof": {"kind": "complete_finite_model_replay", "scope": self.domain.scope,
                      "checks": len(target)} if program else None,
            "stop": stopped, "program_bits": lib.cost(program) if program else None,
            "program_and_library_bits": lib.cost(program)+active_bits if program else None}
