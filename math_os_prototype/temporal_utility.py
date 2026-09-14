"""Causal, bounded measurement of acquired operations on later experience.

The archive is immutable mathematics; this module learns only which archived
operations to offer. Counterfactuals are charged, not treated as free rewards.
The paired observer uses a policy-independent normal producer, not benchmarks.
"""
from copy import deepcopy
from fractions import Fraction
import time

from math_os_prototype import library_compression as lib
from math_os_prototype.representation_policy import dominates
from math_os_prototype.representation_progress import digest
from math_os_prototype.theory_domain import term


POLICIES = ("all", "acquisition", "temporal", "initial")
ARITHMETIC = ("semantic_nodes", "model_node_evaluations", "model_action_steps",
              "matrix_multiply_adds", "recurrence_multiply_adds")
OBJECTIVES = ("description_gain", "search_gain", "proof_gain", "solution_gain",
              "reuse", "matching_gain", "validation_gain", *[k+"_gain" for k in ARITHMETIC])
DEFAULTS = {"active_capacity": 6, "window": 1000, "experiences": 10000,
            "acquisition_sample": 32, "shadow_interval": 128, "shadow_pairs": 96,
            "search_interval": 1000, "search_pairs": 10, "work_per_execution": 100000,
            "search_states": 128, "search_work": 100000, "future_history": 16,
            "producer_policy": "all"}


def configure(options):
    if set(options)-set(DEFAULTS):
        raise ValueError("unknown temporal policy option")
    result = dict(DEFAULTS, **options)
    if result["producer_policy"] not in {"all", "temporal"}:
        raise ValueError("producer policy must be frozen before running")
    if any(type(v) is not int or v < 1 for k, v in result.items() if k != "producer_policy"):
        raise ValueError("positive integer temporal budgets required")
    return result


def operation_key(node, definitions):
    if lib.is_call(node):
        d = next((d for d in definitions if str(d["index"]) == str(node["abstraction"])), None)
        if d is None:
            raise ValueError("undefined archived call")
        return "definition:"+d["id"]
    if node.get("op") == "represented":
        return "representation:"+node["binding"]
    if node.get("op") == "recurrence":
        return "recurrence:"+node["procedure"]
    return None


def references(node, definitions):
    if not isinstance(node, dict):
        return set()
    out = {operation_key(node, definitions)}-{None}
    children = node["arguments"].values() if lib.is_call(node) else node.get("args", [])
    for child in children:
        out.update(references(child, definitions))
    return out


class MeasurementLimit(Exception):
    pass


class TemporalUtility:
    def __init__(self, vocabulary, options, state=None):
        self.v = vocabulary
        if vocabulary.domain.scope.get("kind") != "complete_finite_model":
            raise ValueError("temporal measurements currently require a complete finite model")
        self.options = configure(options)
        self.state = state if state is not None else {
            "schema": "mortra.temporal-utility.v1", "options": self.options,
            "sequence": 0, "entries": {}, "active": [], "version": 0,
            "shadow_cursor": 0, "search_cursor": 0, "shadow_pairs": 0, "search_pairs": 0,
            "future_evidence": [], "selections": [], "windows": {}, "searches": [],
            "costs": {}, "exhausted": [], "stream_digest": digest([])}
        if self.state["options"] != self.options:
            raise ValueError("temporal resume options changed")
        self._patterns = {}
        self._frozen_window = None

    def charge(self, kind, value):
        self.state["costs"][kind] = self.state["costs"].get(kind, 0)+value

    def lower(self, node, active, charge, *, symbolic=False):
        """Remove inactive calls by their existing certified meaning, not name deletion."""
        charge("lowering_visits", 1)
        if lib.is_hole(node) or not isinstance(node, dict):
            return deepcopy(node)
        definitions = self.v.state["definitions"]
        key = operation_key(node, definitions)
        if lib.is_call(node):
            args = {k: self.lower(a, active, charge, symbolic=symbolic) for k, a in node["arguments"].items()}
            if key in active:
                return dict(node, arguments=args)
            d = next(d for d in definitions if str(d["index"]) == str(node["abstraction"]))
            return self.lower(lib.instantiate_term(d["template"], args), active, charge, symbolic=symbolic)
        if node["op"] == "represented" and key not in active:
            from math_os_prototype.theory_spaces import materialize
            r = materialize(self.v.theory.state, node["binding"])
            if r["scope"] != self.v.domain.scope:
                raise ValueError("counterfactual representation scope mismatch")
            q = deepcopy(self.v.theory.state["concepts"][r["concept"]]["definition"])
            word = node["args"][0]
            if word.get("op") != "word":
                raise ValueError("symbolic action-word pattern not supported")
            for g in reversed(word["letters"]):
                q = term("pull", q, label=g)
            return q
        if node["op"] == "recurrence" and key not in active:
            if symbolic and lib.is_hole(node["args"][0]):
                raise ValueError("symbolic natural lowering is not a scalar template")
            return self.v.primitive(node, charge=charge)
        return dict(node, args=[self.lower(a, active, charge, symbolic=symbolic) for a in node.get("args", [])])

    def sync(self):
        """Called at acquisition, before any later experience can be observed."""
        began = time.perf_counter()
        s, vs, engine = self.state, self.v.state, self.v.theory.state
        candidates = []
        for d in vs["definitions"]:
            candidates.append(("definition:"+d["id"], d["template"], d["signature"], d["scope"],
                               {"definition": d["id"], "source_evidence": d.get("source_evidence", {})}))
        for rid, op in vs["observation_operations"].items():
            candidates.append(("representation:"+rid, op["body"], op["signature"], op["scope"],
                               {"binding": rid, "space": op["body"].get("space")}))
        for pid, op in vs["recurrence_operations"].items():
            candidates.append(("recurrence:"+pid, op["body"], op["signature"], op["scope"],
                               {"procedure": pid, "representation": engine["procedures"][pid]["representation"]}))
        changed = False
        for key, body, signature, scope, evidence in candidates:
            identity = digest([body, signature, scope, evidence])
            if key in s["entries"]:
                if s["entries"][key]["identity"] != identity:
                    raise ValueError("archived operation changed after temporal registration")
                continue
            birth = vs["experience_count"]
            rows = vs["corpus"][-self.options["acquisition_sample"]:]
            cost_objects = [[body, signature, scope, evidence]]
            if key.startswith("representation:"):
                from math_os_prototype.theory_spaces import materialize
                r = materialize(engine, key.split(":", 1)[1])
                cost_objects.append({k: r[k] for k in ("basis", "action_matrices", "certificate", "scope") if k in r})
            elif key.startswith("recurrence:"):
                cost_objects.append(engine["procedures"][key.split(":", 1)[1]]["body"])
            objects = {digest(obj): lib.cost(obj) for obj in cost_objects}
            source_rows = rows + [vs["acquisition_evidence"][sid] for sid in evidence.get("source_evidence", {}).values()
                                  if sid in vs["acquisition_evidence"]]
            entry = {"key": key, "identity": identity, "signature": deepcopy(signature),
                     "scope": deepcopy(scope), "body": deepcopy(body), "acquired_after": birth,
                     "acquisition_evidence": deepcopy(evidence), "acquisition_sample": sorted(set([r["id"] for r in rows]) | set(evidence.get("source_evidence", {}))),
                     "acquisition_contexts": sorted({self.context(r["program"], r["primitive"]) for r in source_rows}),
                     "implementation_bits": sum(objects.values()), "cost_objects": objects,
                     "acquisition_utility_bits": 0, "future": [], "future_contexts": [],
                     "future_samples": 0, "last_measurement": birth}
            s["entries"][key] = entry
            savings = 0
            for row in rows:
                counts = {}
                def charge(k, n):
                    counts[k] = counts.get(k, 0)+n
                    if sum(counts.values()) > self.options["work_per_execution"]:
                        raise MeasurementLimit()
                try:
                    baseline = self.lower(row["program"], set(), charge)
                    fitted, _ = self.prepare(row["program"], {key}, charge)
                    savings += lib.cost(baseline)-lib.cost(fitted)
                except MeasurementLimit:
                    self.charge("acquisition_sample_refused", 1)
                self.charge("acquisition_measurement_operations", sum(counts.values()))
            entry["acquisition_utility_bits"] = savings-lib.cost([body, signature, scope])
            entry["acquisition_measurement"] = "bounded prefix sample, implementation description charged"
            if key.startswith("definition:"):
                d = next(d for d in vs["definitions"] if "definition:"+d["id"] == key)
                entry["prefix_sample_utility_bits"] = entry["acquisition_utility_bits"]
                entry["acquisition_utility_bits"] = d["utility_bits"]
                entry["acquisition_measurement"] = "original library acquisition utility, including definition cost"
            entry["acquisition_sample_cutoff"] = birth
            changed = True
        if changed:
            self.reconsider()
        self.charge("registration_seconds", time.perf_counter()-began)

    def pattern(self, key, charge):
        if key not in self._patterns:
            entry = self.state["entries"][key]
            if key.startswith("definition:"):
                try:
                    self._patterns[key] = self.lower(entry["body"], set(), charge, symbolic=True)
                except ValueError:
                    self._patterns[key] = None
            else:
                self._patterns[key] = None
        return self._patterns[key]

    def prepare(self, original, active, charge):
        """Typed definitional matching, with decreasing description length.

        Matching source patterns is not a newly discovered theorem. Their
        equalities follow from archived expansion/transition certificates.
        """
        active = set(active)
        node = self.lower(original, active, charge)
        used = set()
        def visit(t):
            if lib.is_call(t):
                return dict(t, arguments={k: visit(a) if isinstance(a, dict) else a for k, a in t["arguments"].items()})
            t = dict(t, args=[visit(a) for a in t.get("args", [])])
            for key in sorted(active):
                entry = self.state["entries"][key]
                charge("matching_checks", 1)
                replacement = None
                if key.startswith("definition:"):
                    pattern = self.pattern(key, charge)
                    binding = {}
                    with lib.grammar(self.v.accepts):
                        matched = pattern is not None and lib.match_term(pattern, t, binding)
                    if matched:
                        d = next(d for d in self.v.state["definitions"] if "definition:"+d["id"] == key)
                        if set(binding) == set(d["signature"]["parameters"]):
                            replacement = lib.use_node(d["index"], d["template"], binding)
                elif key.startswith("representation:"):
                    rid = key.split(":", 1)[1]
                    r = self.v.theory.state["representations"][rid]
                    q = self.v.theory.state["concepts"][r["concept"]]["definition"]
                    inner, labels = t, []
                    while inner != q and inner.get("op") == "pull":
                        labels.append(inner["label"])
                        inner = inner["args"][0]
                        charge("matching_checks", 1)
                    if inner == q:
                        replacement = term("represented", term("word", letters=list(reversed(labels))), binding=rid)
                if replacement is not None and lib.cost(replacement) < lib.cost(t):
                    self.v.accepts(replacement)
                    charge("replacement_type_checks", 1)
                    t = replacement
                    used.add(key)
            return t
        result = visit(node)
        used.update(references(result, self.v.state["definitions"]))
        return result, sorted(used)

    def execute(self, program, active, expected, *, relation_ids=None):
        began = time.perf_counter()
        counts, work = {}, [0]
        def charge(k, n):
            counts[k] = counts.get(k, 0)+n
            work[0] += n
            if work[0] > self.options["work_per_execution"]:
                raise MeasurementLimit()
        self.v._compiled_spaces.clear()
        self.v._observation_values.clear()
        self.v._definition_table_cache = None
        self._patterns.clear()
        prepared, used, solved = None, [], False
        interpreter = {}
        edits = []
        try:
            prepared, used = self.prepare(program, active, charge)
            type_cost = {}
            self.v.accepts(prepared, counter=type_cost)
            for k, n in type_cost.items():
                if type(n) is int:
                    charge(k, n)
            if self.v.theory.flags.get("semantic_edits"):
                prepared, edits = self.v.edit(prepared, counter=interpreter, charge=charge, relation_ids=relation_ids)
                prepared = self.lower(prepared, set(active), charge)
            values, _ = self.v.evaluate(prepared, counter=interpreter, charge=charge)
            if self.v.domain.semantic_key(values) != self.v.domain.semantic_key(expected):
                raise AssertionError("temporal counterfactual changed mathematical value")
            solved = True
        except MeasurementLimit:
            pass
        return {"solved": solved, "program": prepared, "used": used, "costs": counts,
                "bits": lib.cost(prepared) if solved else None, "proof_calls": 0,
                "seconds": time.perf_counter()-began, "work": work[0],
                "interpreter": interpreter, "semantic_edits": edits,
                "stop": "certified_execution" if solved else "measurement_work_budget"}

    def vector(self, entry):
        rows = entry["future"]
        result = {}
        for key in OBJECTIVES:
            values = [r[key] for r in rows if r.get(key) is not None]
            result[key] = Fraction(sum(values), len(values)) if values else None
        return result

    def choose(self, policy):
        entries = list(self.state["entries"].values())
        if policy == "initial":
            return []
        if policy == "all":
            return [e["key"] for e in entries]
        tie = lambda e: (-e["acquisition_utility_bits"], e["acquired_after"], e["key"])
        if policy == "acquisition":
            return [e["key"] for e in sorted(entries, key=tie)[:self.options["active_capacity"]]]
        remaining, ordered = entries, []
        vectors = {e["key"]: self.vector(e) for e in entries}
        # The no-operation baseline dominates a measured entry only on its
        # observed coverage; unknowns are not zero. Archive probes can revive it.
        remaining = [e for e in entries if not dominates(
            {k: 0 if v is not None else None for k, v in vectors[e["key"]].items()},
            vectors[e["key"]], objectives=OBJECTIVES)]
        while remaining:
            # Different measurement coverage is incomparable, not implicitly zero.
            def beats(a, b):
                av, bv = vectors[a["key"]], vectors[b["key"]]
                if any((av[k] is None) != (bv[k] is None) for k in OBJECTIVES):
                    return False
                return dominates(av, bv, objectives=OBJECTIVES)
            front = [e for e in remaining if not any(beats(other, e) for other in remaining if other is not e)]
            if not front:
                raise AssertionError("cyclic temporal Pareto relation")
            # Fixed deterministic tie: measured before unmeasured, then smaller
            # archived body, older acquisition, content key. No scalar reward.
            front.sort(key=lambda e: (not bool(e["future"]), lib.cost(e["body"]), e["acquired_after"], e["key"]))
            ordered.extend(front)
            remaining = [e for e in remaining if e not in front]
        return [e["key"] for e in ordered[:self.options["active_capacity"]]]

    def reconsider(self):
        began = time.perf_counter()
        chosen = self.choose("temporal")
        if chosen != self.state["active"]:
            self.state["selections"].append({"after_sequence": self.state["sequence"],
                "acquired_through": self.v.state["experience_count"], "before": self.state["active"],
                "after": chosen, "evidence_through": max([e["last_measurement"] for e in self.state["entries"].values()] or [0]),
                "vectors": {k: {n: str(v) if v is not None else None for n, v in self.vector(e).items()}
                            for k, e in self.state["entries"].items()},
                "rule": "Pareto; measured, body bits, acquisition sequence, content key"})
            self.state["active"] = chosen
            self.state["version"] += 1
        self.charge("selection_seconds", time.perf_counter()-began)

    def disabled_closure(self, keys, disabled):
        disabled = set(disabled)
        changed = True
        while changed:
            changed = False
            for key, entry in self.state["entries"].items():
                deps = references(entry["body"], self.v.state["definitions"]) if key.startswith("definition:") else set()
                if key.startswith("recurrence:"):
                    deps.add("representation:"+entry["acquisition_evidence"]["representation"])
                if deps & disabled and key not in disabled:
                    disabled.add(key)
                    changed = True
        return sorted(set(keys)-disabled)

    def add_future(self, key, sequence, source, context, with_r, without_r, *, search=False):
        e = self.state["entries"][key]
        if sequence <= e["acquired_after"] or source in e["acquisition_sample"]:
            raise ValueError("acquisition data cannot become future evidence")
        metrics = {k: None for k in OBJECTIVES}
        both = with_r["solved"] and without_r["solved"]
        metrics["solution_gain"] = int(with_r["solved"])-int(without_r["solved"])
        if search:
            metrics["search_gain"] = without_r["states_explored"]-with_r["states_explored"] if both else None
            metrics["proof_gain"] = without_r["costs"]["prover_calls"]-with_r["costs"]["prover_calls"] if both else None
        else:
            if both:
                metrics["description_gain"] = without_r["bits"]-with_r["bits"]
                metrics["proof_gain"] = 0
                for kind in ARITHMETIC:
                    metrics[kind+"_gain"] = without_r["costs"].get(kind, 0)-with_r["costs"].get(kind, 0)
                metrics["matching_gain"] = without_r["costs"].get("matching_checks", 0)-with_r["costs"].get("matching_checks", 0)
                metrics["validation_gain"] = without_r["costs"].get("lowering_visits", 0)-with_r["costs"].get("lowering_visits", 0)
            reused = key in with_r["used"] and with_r["solved"]
            metrics["reuse"] = int(reused and context not in e["future_contexts"] and context not in e["acquisition_contexts"])
            if reused and context not in e["future_contexts"]:
                e["future_contexts"].append(context)
        row = {"sequence": sequence, "source": source, "context": context, "operation": key,
               "acquired_after": e["acquired_after"], "search": search, "metrics": metrics,
               "with": with_r, "without": without_r}
        self.state["future_evidence"].append(row)
        e["future"].append(dict(metrics, sequence=sequence))
        e["future"] = e["future"][-self.options["future_history"]:]
        e["future_samples"] += 1
        e["last_measurement"] = sequence

    def observe(self, program, primitive, sequence, expected=None):
        s = self.state
        if sequence <= s["sequence"]:
            raise ValueError("experience sequence must advance")
        if sequence > self.options["experiences"]:
            if "experience_budget" not in s["exhausted"]:
                s["exhausted"].append("experience_budget")
            return
        began = time.perf_counter()
        source = digest(program)
        if expected is None:
            expected = self.v.domain.evaluate(primitive, charge=lambda k, n: self.charge("independent_"+k, n))
            self.charge("expected_value_evaluations", 1)
        # Select from the prefix only. No current observation has updated utility.
        chosen = {p: (list(s["active"]) if p == "temporal" else self.choose(p)) for p in POLICIES}
        window = (sequence-1)//self.options["window"]
        w = s["windows"].setdefault(str(window), {"start": window*self.options["window"],
            "end": sequence, "conditions": {}, "source_ids_digest": digest([]),
            "active_at_start": deepcopy(chosen), "archive_at_start": len(s["entries"])})
        w.setdefault("relations_at_start", [r["id"] for r in self.v.state["semantic_relations"]])
        if self._frozen_window is None or self._frozen_window[0] != window:
            self._frozen_window = (window, w["active_at_start"]["temporal"])
        outcomes = {}
        for policy, active in dict(chosen, temporal_window_frozen=self._frozen_window[1]).items():
            result = self.execute(program, active, expected,
                relation_ids=w["relations_at_start"] if policy == "temporal_window_frozen" else None)
            outcomes[policy] = result
            totals = w["conditions"].setdefault(policy, {"experiences": 0, "solved": 0, "bits": 0,
                "seconds": 0, "costs": {}, "reuse": 0})
            totals["experiences"] += 1
            totals["solved"] += int(result["solved"])
            totals["bits"] += result["bits"] or 0
            totals["seconds"] += result["seconds"]
            totals["reuse"] += len(result["used"])
            for k, n in result["costs"].items():
                totals["costs"][k] = totals["costs"].get(k, 0)+n
        if all(r["solved"] for r in outcomes.values()):
            w["common_solved_count"] = w.get("common_solved_count", 0)+1
            common = w.setdefault("common_solved_costs", {})
            for policy, r in outcomes.items():
                c = common.setdefault(policy, {"bits": 0, "seconds": 0, "work": 0})
                c["bits"] += r["bits"]
                c["seconds"] += r["seconds"]
                c["work"] += r["work"]
        s["sequence"] = sequence
        s["stream_digest"] = digest([s["stream_digest"], source, sequence])
        w["source_ids_digest"] = digest([w["source_ids_digest"], source, sequence])
        w["end"] = sequence
        eligible = [e for e in s["entries"].values() if e["acquired_after"] < sequence and source not in e["acquisition_sample"]]
        context = self.context(program, primitive)
        measurements_before = len(s["future_evidence"])
        if eligible and sequence % self.options["shadow_interval"] == 0:
            if s["shadow_pairs"] < self.options["shadow_pairs"]:
                # All archive entries, including inactive entries, receive turns.
                eligible.sort(key=lambda e: (e["future_samples"], e["last_measurement"], e["key"]))
                key = eligible[0]["key"]
                before_shadow = time.perf_counter()
                yes = self.execute(program, [key], expected)
                no = self.execute(program, [], expected)
                self.add_future(key, sequence, source, context, yes, no)
                s["shadow_pairs"] += 1
                self.charge("shadow_seconds", time.perf_counter()-before_shadow)
                self.charge("shadow_work", yes["work"]+no["work"])
            elif "shadow_pair_budget" not in s["exhausted"]:
                s["exhausted"].append("shadow_pair_budget")
        if eligible and sequence % self.options["search_interval"] == 0:
            if s["search_pairs"] < self.options["search_pairs"]:
                self.search_observation(program, sequence, source, context, expected, chosen)
            elif "search_pair_budget" not in s["exhausted"]:
                s["exhausted"].append("search_pair_budget")
        if len(s["future_evidence"]) != measurements_before:
            self.reconsider()
        w["archive_at_end"] = len(s["entries"])
        w["active_at_end"] = len(s["active"])
        w["definition_call_depth"] = max([d["depth"] for d in self.v.state["definitions"]] or [0])
        w["semantic_abstraction_depth"] = None
        w["semantic_depth_note"] = "call nesting is not mathematical semantic depth"
        w["library_bits"] = {p: self.library_bits(keys) for p, keys in chosen.items()}
        w["frozen_library_bits"] = self.library_bits(self._frozen_window[1], relation_ids=w["relations_at_start"])
        self.charge("observer_seconds", time.perf_counter()-began)

    def library_bits(self, keys, *, relation_ids=None):
        needed = set(keys)
        pending = list(keys)
        while pending:
            key = pending.pop()
            entry = self.state["entries"][key]
            deps = references(entry["body"], self.v.state["definitions"]) if key.startswith("definition:") else set()
            if key.startswith("recurrence:"):
                deps.add("representation:"+entry["acquisition_evidence"]["representation"])
            for dep in deps-needed:
                needed.add(dep)
                pending.append(dep)
        objects = {}
        for key in needed:
            objects.update(self.state["entries"][key]["cost_objects"])
        for r in self.v.state["semantic_relations"]:
            if "definition:"+r["definition"] in needed and (relation_ids is None or r["id"] in relation_ids):
                objects[digest(r)] = lib.cost(r)
        return sum(objects.values())

    def context(self, program, primitive):
        return digest({"type": self.v.accepts(program), "root": primitive["op"],
                       "children": [a["op"] for a in primitive.get("args", [])], "scope": self.v.domain.scope})

    def search_observation(self, program, sequence, source, context, expected, chosen):
        if self.v.accepts(program) != "scalar":
            return
        task = {"id": "internal-experience-"+str(sequence), "scope": self.v.domain.scope,
                "values": [str(v) for v in expected], "budget": {"states": self.options["search_states"],
                "depth": 64, "program_size": 4096, "expanded_size": 4096, "work": self.options["search_work"]}}
        started = time.perf_counter()
        rows = {p: self.v.solve_observation(task, operation_keys=keys, execution_mode="edited") for p, keys in chosen.items()}
        active = chosen["temporal"]
        ablation = None
        if active:
            # Fixed rotating member of the selected set, not a benchmark winner.
            key = active[self.state["search_cursor"] % len(active)]
            self.state["search_cursor"] += 1
            keys = self.disabled_closure(active, [key])
            no = self.v.solve_observation(task, operation_keys=keys, execution_mode="edited")
            self.add_future(key, sequence, source, context, rows["temporal"], no, search=True)
            ablation = {"disabled": key, "allowed": keys, "result": no}
        self.state["searches"].append({"sequence": sequence, "source": source,
            "task": task, "conditions": rows, "ablation": ablation, "external": False})
        self.state["search_pairs"] += 1
        self.charge("search_measurement_seconds", time.perf_counter()-started)
