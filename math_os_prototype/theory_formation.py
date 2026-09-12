"""Persistent, target-free exploration of a bounded exact mathematical fragment.

Acquisition is not a reward. A separate downstream record is needed to claim
benefit. Rewrites are learned reduction procedures, not new general algorithms.
The proof kernels, enumeration policy and recurrence evaluator are initial
developer-supplied knowledge. A stopped search has not exhausted mathematics.
"""
from __future__ import annotations

from copy import deepcopy
from collections import Counter
import time
import sympy as sp

from math_os_prototype.representation_progress import digest, description_bits
from math_os_prototype.theory_domain import Domain, size, linear_readout
from math_os_prototype.library_compression import grammar, match_term, instantiate_term

SCHEMA = "mortra.theory-state.v1"
DEFAULT_BUDGET = {"cycles": 180, "seconds": 180, "term_size": 7,
                  "concepts": 64, "active_concepts": 24, "candidates": 1800,
                  "batch": 12, "representations": 2, "dimension": 24}


def configure(config):
    if set(config) != {"domain", "seed", "budget"}:
        raise ValueError("only domain signature, random seed and resource budget accepted")
    if type(config["seed"]) is not int:
        raise ValueError("integer seed required")
    if set(config["budget"]) - set(DEFAULT_BUDGET):
        raise ValueError("unknown budget key")
    budget = dict(DEFAULT_BUDGET, **config["budget"])
    if any(type(v) is not int or v < 1 for v in budget.values()):
        raise ValueError("positive integer resource bounds required")
    return dict(deepcopy(config), budget=budget)


def pattern(t, names):
    if t["op"] == "var":
        return {"series_parameter": names[t["name"]]}
    return dict(t, args=[pattern(a, names) for a in t["args"]])


def rewrite(t, rules, scope, domain=None):
    """Certified functional equalities; strictly decreasing AST cost/order.

    No arbitrary substitution in finite-model theorems. Exact subtree congruence
    is valid for all typed operations here, including pullback on a closed model.
    Universal differential identities also license typed scalar substitution.
    """
    dependencies, checks = [], 0
    def visit(node):
        nonlocal checks
        node = dict(node, args=[visit(a) for a in node["args"]])
        while True:
            changed = False
            for rule in rules:
                checks += 1
                if rule["scope"] != scope:
                    raise ValueError("rewrite certificate scope mismatch")
                replacement = None
                if node == rule["left"]:
                    replacement = deepcopy(rule["right"])
                elif rule.get("universal_pattern") and domain is not None:
                    if scope["kind"] != "universal_differential_polynomial_identity":
                        raise ValueError("substitution is not licensed by a finite model")
                    def accepts_scalar(candidate):
                        if domain.type_of(candidate) != "scalar":
                            raise ValueError("scalar substitution required")
                    binding = {}
                    with grammar(accepts_scalar):
                        if match_term(rule["pattern_left"], node, binding):
                            replacement = instantiate_term(rule["pattern_right"], binding)
                    if replacement is not None and (size(replacement), digest(replacement)) >= (size(node), digest(node)):
                        replacement = None
                if replacement is not None:
                    if (size(replacement), digest(replacement)) >= (size(node), digest(node)):
                        raise ValueError("non-decreasing rewrite refused")
                    dependencies.append(rule["theorem"])
                    node = replacement
                    changed = True
                    break
            if not changed:
                return node
    result = visit(t)
    return result, sorted(set(dependencies)), checks


class Theory:
    def __init__(self, config, *, theorem_reuse=True, representation_reuse=True, state=None):
        self.config = configure(config)
        self.domain = Domain(self.config["domain"])
        self.budget = self.config["budget"]
        self.flags = {"theorem_reuse": theorem_reuse, "representation_reuse": representation_reuse}
        if state is not None:
            state = deepcopy(state)
            seal = state.pop("sha256", None)
            if seal != digest(state):
                raise ValueError("TheoryState seal mismatch")
            if state["config"] != self.config or state["flags"] != self.flags:
                raise ValueError("resume cannot alter frozen inputs or experiment condition")
            if state["domain_key"] != self.domain.key:
                raise ValueError("model scope changed")
            self.state = state
            self.event("restored", actor="fixed infrastructure", previous_cycle=state["cycle"])
            return
        self.state = {
            "schema": SCHEMA, "config": self.config, "flags": self.flags,
            "domain_key": self.domain.key, "cycle": 0, "seconds": 0,
            "seed_primitives": self.domain.seeds(), "axioms": self.domain.scope,
            "exact_models": getattr(self.domain, "models", []), "premise": self.domain.premise,
            "concepts": {}, "conjectures": {}, "counterexamples": {},
            "theorems": {}, "representations": {}, "procedures": {},
            "rewrite_rules": [], "active_rules": [], "active_concepts": [],
            "proof_dependencies": {}, "representation_dependencies": {},
            "pending_terms": [], "expanded": [], "seen": [], "events": [],
            "decisions": [], "costs": {}, "kind_visits": {}, "downstream": [],
            "regressions": [], "open_questions": [], "human_inputs_after_start": 0,
            "task_origins": {"external": [], "self_generated": [], "replay_regression": []},
            "capability_growth_claim": False,
        }
        for t in self.domain.seeds():
            self.add_concept(t, [], seed=True)
        self.event("initial_knowledge", actor="development-time human",
                   kernels=["differential ring normalization", "complete model enumeration",
                            "action observable closure", "linear recurrence certification"],
                   policy="least-visited available computation kind, then estimated cost; no learned optimality")

    def event(self, kind, *, actor="MORTRA", **data):
        self.state["events"].append(dict(index=len(self.state["events"]),
                                         cycle=self.state["cycle"], actor=actor, kind=kind, **data))

    def charge(self, stage, **values):
        costs = self.state["costs"].setdefault(stage, {})
        for name, value in values.items():
            costs[name] = costs.get(name, 0) + value

    def add_concept(self, t, parents, seed=False):
        cid = "C-" + digest(t)[:16]
        if cid in self.state["concepts"]:
            return cid
        counter = {}
        value = self.domain.evaluate(t, counter)
        self.charge("concept_evaluation", **counter)
        self.state["concepts"][cid] = {
            "id": cid, "definition": t, "parents": parents,
            "scope": self.domain.scope, "type": self.domain.type_of(t), "seed": seed,
            "semantic_key": self.domain.semantic_key(value),
            "values_or_normal_form": [str(v) for v in value] if isinstance(value, tuple) else str(value),
            "probe": self.domain.probe(t), "description_bits": description_bits(t),
            "size": size(t), "born": self.state["cycle"], "reuse_count": 0,
            "theorems": [], "computation_saved": 0,
            "provenance": "development-time signature" if seed else "self_generated",
        }
        self.state["seen"].append(digest(t))
        self.refresh_active()
        if not seed:
            self.event("concept_invented", concept=cid, definition=t, parents=parents)
        return cid

    def refresh_active(self):
        concepts = list(self.state["concepts"].values())
        seeds = [c for c in concepts if c["seed"]]
        # Keep each type/top constructor represented; rotate the rest by age.
        groups = {}
        for c in concepts:
            if not c["seed"]:
                groups.setdefault((c["type"], c["definition"]["op"]), []).append(c)
        keep = list(seeds)
        for group in groups.values():
            group.sort(key=lambda c: (-c["reuse_count"], c["size"], c["id"]))
            keep.append(group[0])
        remaining = [c for c in concepts if c not in keep]
        remaining.sort(key=lambda c: (c["id"] in self.state["expanded"], c["born"], c["id"]))
        keep.extend(remaining[:max(0, self.budget["active_concepts"]-len(keep))])
        self.state["active_concepts"] = [c["id"] for c in keep]
        self.state["active_rules"] = [r["theorem"] for r in self.state["rewrite_rules"]]

    def conjecture(self, left, right, *, kind="equality", parents=()):
        if left == right:
            return
        key = "Q-" + digest([kind, left, right])[:16]
        if key in self.state["conjectures"]:
            return
        self.state["conjectures"][key] = {"id": key, "left": left, "right": right,
            "kind": kind, "parents": list(parents), "status": "open", "attempts": [],
            "born": self.state["cycle"], "last_theory_size": -1, "provenance": "self_generated"}
        self.state["task_origins"]["self_generated"].append(key)
        self.event("conjecture_generated", conjecture=key, left=left, right=right, schema=kind)

    def invent(self):
        s = self.state
        if not s["pending_terms"]:
            parent = next((s["concepts"][cid] for cid in s["active_concepts"] if cid not in s["expanded"]), None)
            if parent is None:
                return
            s["expanded"].append(parent["id"])
            self.event("concept_expanded", concept=parent["id"])
            others = [s["concepts"][cid]["definition"] for cid in s["active_concepts"]]
            for t in self.domain.compose(parent["definition"], others):
                if size(t) <= self.budget["term_size"] and digest(t) not in s["seen"]:
                    s["pending_terms"].append({"term": t, "parents": [parent["id"]]})
        for _ in range(min(self.budget["batch"], len(s["pending_terms"]))):
            row = s["pending_terms"].pop(0)
            original, parents = row["term"], row["parents"]
            if digest(original) in s["seen"]:
                continue
            s["seen"].append(digest(original))
            t, deps, checks = rewrite(original, self.rules(), self.domain.scope, self.domain)
            self.charge("rewrite", rule_matches_checked=checks)
            if deps:
                before_count, after_count = {}, {}
                before = self.domain.evaluate(original, before_count)
                after = self.domain.evaluate(t, after_count)
                if self.domain.semantic_key(before) != self.domain.semantic_key(after):
                    raise AssertionError("learned procedure changed exact semantics")
                saving = before_count["semantic_nodes"] - after_count["semantic_nodes"]
                evidence = {"cycle": s["cycle"], "kind": "rewrite_execution",
                            "theorems": deps, "original": original, "executed": t,
                            "before": before_count, "after": after_count,
                            "saved_semantic_nodes": saving, "distinct_later_term": True,
                            "origin": "self_generated", "independent_replay_equal": True}
                s["downstream"].append(evidence)
                self.charge("shadow_audit", semantic_nodes=before_count["semantic_nodes"]+after_count["semantic_nodes"])
                for tid in deps:
                    s["theorems"][tid]["reuse_count"] += 1
                    if tid in s["procedures"]:
                        s["procedures"][tid]["reuse_count"] += 1
                if digest(t) in s["seen"]:
                    self.charge("search", pruned_candidates=1, candidate_evaluations_avoided=1)
                    self.event("candidate_pruned", term=original, reduced=t, dependencies=deps)
                    continue
            peers = list(s["concepts"].values())
            probe = self.domain.probe(t)
            self.charge("probe", semantic_nodes=size(t))
            peers = [c for c in peers if c["type"] == self.domain.type_of(t) and c["probe"] == probe]
            # Small deterministic selection, not a target or a supplied theorem order.
            peers.sort(key=lambda c: (c["size"], digest([self.config["seed"], t, c["id"]])))
            for peer in peers[:2]:
                kind = "iff" if self.domain.type_of(t) == "predicate" else "equality"
                self.conjecture(t, peer["definition"], kind=kind, parents=parents+[peer["id"]])
            if len(s["concepts"]) < self.budget["concepts"]:
                value = self.domain.evaluate(t)
                key = self.domain.semantic_key(value)
                if not any(c["semantic_key"] == key and c["type"] == self.domain.type_of(t)
                           for c in s["concepts"].values()):
                    cid = self.add_concept(t, parents)
                    if self.domain.type_of(t) == "predicate":
                        other = next((c for c in s["concepts"].values() if c["type"] == "predicate" and c["id"] != cid), None)
                        if other:
                            self.conjecture(t, other["definition"], kind="implication", parents=[cid, other["id"]])
        self.charge("search", generation_batches=1)

    def rules(self):
        return self.state["rewrite_rules"] if self.flags["theorem_reuse"] else []

    def promote(self, qid, proof, dependencies):
        s, q = self.state, self.state["conjectures"][qid]
        tid = "T-" + qid[2:]
        s["theorems"][tid] = {"id": tid, "conjecture": qid, "certificate": proof,
            "dependencies": sorted(set(dependencies)), "concepts": q["parents"],
            "born": s["cycle"], "reuse_count": 0, "novelty": "unassessed"}
        s["proof_dependencies"][tid] = sorted(set(dependencies))
        for cid in q["parents"]:
            if cid in s["concepts"]:
                s["concepts"][cid]["theorems"].append(tid)
        if q["kind"] in {"equality", "iff"}:
            left, right = sorted([q["left"], q["right"]], key=lambda t: (size(t), digest(t)), reverse=True)
            rule = {"left": left, "right": right, "theorem": tid, "scope": self.domain.scope}
            if self.domain.kind == "differential_ring" and self.domain.type_of(left) == "scalar":
                names = {name: f"f{i}" for i, name in enumerate(self.domain.names)}
                rule.update(universal_pattern=True, pattern_left=pattern(left, names),
                            pattern_right=pattern(right, names))
            if left != right:
                s["rewrite_rules"].append(rule)
                s["procedures"][tid] = {"kind": "certified_reduction", "body": rule,
                    "born": s["cycle"], "reuse_count": 0,
                    "algorithm_claim": "specialized reduction, not a newly invented general algorithm"}
        self.event("theorem_promoted", theorem=tid, dependencies=dependencies)
        return tid

    def settle(self, qid):
        q = self.state["conjectures"][qid]
        left, ldeps, lc = rewrite(q["left"], self.rules(), self.domain.scope, self.domain)
        right, rdeps, rc = rewrite(q["right"], self.rules(), self.domain.scope, self.domain)
        self.charge("rewrite", rule_matches_checked=lc+rc)
        if left == right and ldeps+rdeps:
            q["status"] = "proved_redundant"
            q["certificate"] = {"method": "certified congruence", "dependencies": sorted(set(ldeps+rdeps))}
            self.charge("search", pruned_conjectures=1, proof_calls_avoided=1)
            self.event("conjecture_pruned", conjecture=qid, dependencies=sorted(set(ldeps+rdeps)))
            return
        started = time.perf_counter()
        proof = self.domain.settle(left, right, q["kind"])
        self.charge("certification", proof_calls=1, seconds=time.perf_counter()-started,
                    semantic_nodes=size(left)+size(right))
        q["attempts"].append({"cycle": self.state["cycle"], "result": proof["status"],
                               "reduced_left": left, "reduced_right": right,
                               "dependencies": sorted(set(ldeps+rdeps))})
        q["last_theory_size"] = len(self.state["theorems"])
        q["status"] = proof["status"]
        q["certificate"] = proof
        if proof["status"] == "proved":
            self.promote(qid, proof, ldeps+rdeps)
        elif proof["status"] == "disproved":
            self.state["counterexamples"][qid] = proof["counterexample"]
            self.event("counterexample", conjecture=qid, witness=proof["counterexample"])
        else:
            self.event("unknown", conjecture=qid, reason=proof.get("reason"))

    def acquire(self, cid):
        c = self.state["concepts"][cid]
        qid = self.structural_query("closure", concept=cid)
        started = time.perf_counter()
        try:
            record = self.domain.acquire(c["definition"], self.budget["dimension"])
        except (ValueError, AssertionError) as exc:
            self.finish_query(qid, "unknown", reason=str(exc))
            c["closure_refusal"] = str(exc)
            self.event("closure_unknown", concept=cid, reason=str(exc))
            return
        finally:
            self.charge("acquisition", closure_calls=1, seconds=time.perf_counter()-started)
        rid, tid = "R-"+cid[2:], "T-closure-"+cid[2:]
        self.finish_query(qid, "proved", theorem=tid)
        record.update(id=rid, concept=cid, theorem=tid, born=self.state["cycle"],
                      reuse_count=0, derived_labels=[], query_count=0)
        self.state["representations"][rid] = record
        self.state["representation_dependencies"][rid] = [cid, tid]
        self.state["theorems"][tid] = {"id": tid, "kind": "closure", "conjecture": qid, "concepts": [cid],
            "certificate": record["certificate"], "scope": record["scope"],
            "dependencies": [], "born": self.state["cycle"], "reuse_count": 0,
            "novelty": "unassessed"}
        self.state["proof_dependencies"][tid] = []
        c["theorems"].append(tid)
        self.event("representation_acquired", concept=cid, representation=rid,
                   dimension=record["dimension"], certificate=record["certificate"])

    def derive(self, rid, label):
        stored = self.state["representations"][rid]
        qid = self.structural_query("recurrence", representation=rid, label=label)
        started = time.perf_counter()
        representation = stored
        reuse = self.flags["representation_reuse"] and self.flags["theorem_reuse"]
        if not reuse:
            representation = self.domain.acquire(self.state["concepts"][stored["concept"]]["definition"], self.budget["dimension"])
            self.charge("reacquisition", closure_calls=1, seconds=time.perf_counter()-started)
        else:
            stored["reuse_count"] += 1
            self.state["concepts"][stored["concept"]]["reuse_count"] += 1
        started = time.perf_counter()
        try:
            found = self.domain.recurrence(representation, label)
        except ValueError as exc:
            self.finish_query(qid, "unknown", reason=str(exc))
            stored["derived_labels"].append(label)
            self.event("recurrence_unknown", representation=rid, label=label, reason=str(exc))
            self.charge("recurrence", proof_calls=1, failed=1, seconds=time.perf_counter()-started)
            return
        self.charge("recurrence", proof_calls=1, seconds=time.perf_counter()-started)
        stored["derived_labels"].append(label)
        tid = "T-recurrence-" + digest([rid, label])[:16]
        self.finish_query(qid, "proved", theorem=tid)
        self.state["theorems"][tid] = {"id": tid, "kind": "recurrence", "conjecture": qid, "concepts": [stored["concept"]],
            "certificate": found, "dependencies": [stored["theorem"]] if reuse else [],
            "born": self.state["cycle"], "reuse_count": 0, "novelty": "unassessed"}
        self.state["proof_dependencies"][tid] = [stored["theorem"]] if reuse else []
        if reuse:
            self.state["theorems"][stored["theorem"]]["reuse_count"] += 1
        self.state["procedures"][tid] = {"kind": "certified_scalar_recurrence", "body": found,
            "representation": rid, "born": self.state["cycle"], "reuse_count": 0,
            "algorithm_claim": "derived recurrence parameters; evaluator supplied in development"}
        self.event("recurrence_derived", theorem=tid, dependency=stored["theorem"],
                   closure_reused=reuse, certificate=found)
        if reuse:
            self.state["downstream"].append({"kind": "closure_used_for_new_recurrence",
                "cycle": self.state["cycle"], "representation": rid,
                "earlier_theorem": stored["theorem"], "new_theorem": tid,
                "acquisition_calls": 0, "origin": "self_generated",
                "cost_claim": "use no-representation-reuse run for measured avoided acquisition"})
        self.refresh_active()

    def structural_query(self, kind, **payload):
        qid = "Q-" + digest([kind, payload])[:16]
        self.state["conjectures"][qid] = {"id": qid, "kind": kind, **payload,
            "status": "open", "attempts": [], "born": self.state["cycle"],
            "last_theory_size": -1, "provenance": "self_generated",
            "question": "Does the applicable exact closure/recurrence kernel produce a certificate within budget?"}
        self.state["task_origins"]["self_generated"].append(qid)
        self.event("conjecture_generated", conjecture=qid, schema=kind, **payload)
        return qid

    def finish_query(self, qid, status, **result):
        q = self.state["conjectures"][qid]
        q.update(status=status, last_theory_size=len(self.state["theorems"]))
        q["attempts"].append({"cycle": self.state["cycle"], "result": status, **result})

    def use_procedure(self, pid):
        p = self.state["procedures"][pid]
        if p["kind"] != "certified_scalar_recurrence":
            return
        law = p["body"]
        r = self.state["representations"][p["representation"]]
        if law["scope"]["domain"] != self.domain.key or not law["certificate_passed"]:
            raise ValueError("uncertified recurrence refused")
        values = [sp.Rational(v) for v in law["initial_values"]]
        weights = [sp.Rational(v) for v in law["coefficients"]]
        order = law["order"]
        n = 3*r["dimension"] + 2 + p["reuse_count"]
        if order == 0:
            actual = sp.S.Zero
        else:
            while len(values) <= n:
                values.append(sum(w*v for w, v in zip(weights, values[-order:])))
            actual = values[n]
        index = 0
        for _ in range(n):
            index = self.domain.actions[law["label"]][index]
        c = self.state["concepts"][r["concept"]]
        expected = self.domain.evaluate(c["definition"])[index]
        if actual != expected:
            raise AssertionError("stored recurrence failed independent model execution")
        p["reuse_count"] += 1
        self.state["theorems"][pid]["reuse_count"] += 1
        self.state["downstream"].append({"kind": "new_length_from_stored_recurrence",
            "cycle": self.state["cycle"], "procedure": pid, "length": n,
            "value": str(actual), "model_value": str(expected), "agree": True,
            "origin": "self_generated", "acquisition_calls": 0, "proof_calls": 0,
            "cost_note": "no speedup asserted; independent model replay is charged separately"})
        self.charge("procedure_execution", scalar_multiply_adds=max(0, n+1-law["order"])*law["order"])
        self.charge("shadow_audit", model_action_steps=n)
        self.event("procedure_executed", procedure=pid, length=n, result=str(actual))

    def actions(self):
        s = self.state
        if not s["pending_terms"] and not any(cid not in s["expanded"] for cid in s["active_concepts"]):
            previous = list(s["active_concepts"])
            self.refresh_active()
            if previous != s["active_concepts"]:
                self.event("active_frontier_refreshed", previous=previous, active=list(s["active_concepts"]))
        options = []
        def offer(kind, payload, cost, novelty, uncertainty):
            options.append({"kind": kind, "payload": payload, "estimated_operations": cost,
                            "novelty": novelty, "unresolved_uncertainty": uncertainty,
                            "visits": s["kind_visits"].get(kind, 0),
                            "expected_compression": None, "downstream_reuse": len(s["downstream"]),
                            "proof_bottleneck": len([q for q in s["conjectures"].values() if q["status"] == "open"])})
        pending = sum(q["status"] == "open" for q in s["conjectures"].values())
        if pending <= 2*self.budget["batch"] and len(s["seen"]) < self.budget["candidates"] and (s["pending_terms"] or any(cid not in s["expanded"] for cid in s["active_concepts"])):
            offer("invent", None, self.budget["batch"], 1, 1)
        for q in s["conjectures"].values():
            if q["kind"] in {"closure", "recurrence"}:
                continue
            if q["status"] == "open" or (q["status"] == "unknown" and q["last_theory_size"] < len(s["theorems"]) and self.flags["theorem_reuse"]):
                offer("settle", q["id"], size(q["left"])+size(q["right"]), 0, 1)
                break
        acquired = {r["concept"] for r in s["representations"].values()}
        if self.domain.actions and len(acquired) < self.budget["representations"]:
            for c in s["concepts"].values():
                if not c["seed"] and c["type"] == "scalar" and c["id"] not in acquired and "closure_refusal" not in c:
                    if len(set(self.domain.evaluate(c["definition"]))) > 1:
                        offer("acquire", c["id"], len(self.domain.models), 1, 1)
                        break
        for rid, r in s["representations"].items():
            label = next((g for g in self.domain.actions if g not in r["derived_labels"]), None)
            if label is not None:
                offer("derive", [rid, label], r["dimension"]**2, 1, 1)
                break
        for pid, p in s["procedures"].items() if self.flags["theorem_reuse"] else []:
            if p["kind"] == "certified_scalar_recurrence" and p["reuse_count"] < 2:
                offer("use", pid, len(p["body"]["coefficients"]), 0, 0)
                break
        return options

    def step(self):
        options = self.actions()
        if not options:
            return False
        choice = min(options, key=lambda a: (a["visits"], a["estimated_operations"], a["kind"]))
        self.state["cycle"] += 1
        self.state["decisions"].append({"cycle": self.state["cycle"], "options": options,
                                        "chosen": choice, "policy": "least_visited_then_cost"})
        kind, payload = choice["kind"], choice["payload"]
        self.state["kind_visits"][kind] = self.state["kind_visits"].get(kind, 0) + 1
        started = time.perf_counter()
        if kind == "invent": self.invent()
        elif kind == "settle": self.settle(payload)
        elif kind == "acquire": self.acquire(payload)
        elif kind == "derive": self.derive(*payload)
        elif kind == "use": self.use_procedure(payload)
        self.state["seconds"] += time.perf_counter()-started
        return True

    def snapshot(self):
        result = deepcopy(self.state)
        result["open_questions"] = [q["id"] for q in result["conjectures"].values() if q["status"] in {"open", "unknown"}]
        result["capability_growth_claim"] = any(r.get("saved_semantic_nodes", 0) > 0 for r in result["downstream"])
        result["sha256"] = digest(result)
        return result

    def run(self, *, cycles=None):
        target = min(self.budget["cycles"], self.state["cycle"] + (cycles or self.budget["cycles"]))
        while self.state["cycle"] < target and self.state["seconds"] < self.budget["seconds"]:
            if not self.step():
                break
        self.state["stop_reason"] = ("wall_time_budget" if self.state["seconds"] >= self.budget["seconds"] else
                                     "cycle_budget" if self.state["cycle"] >= target else "bounded_frontier_exhausted")
        return self.snapshot()


def assess(state):
    """Report criteria, never replace a failed criterion by a large corpus count."""
    concepts, theorems = state["concepts"], state["theorems"]
    def depth(tid, path=()):
        if tid in path: raise ValueError("cyclic proof dependencies")
        return 1 + max([depth(p, path+(tid,)) for p in state["proof_dependencies"].get(tid, [])] or [0])
    statuses = dict(Counter(q["status"] for q in state["conjectures"].values()))
    criteria = {
        "invented_semantically_distinct_concept": any(not c["seed"] for c in concepts.values()),
        "target_free_conjecture": bool(state["conjectures"]),
        "exact_theorem": bool(theorems), "exact_counterexample": bool(state["counterexamples"]),
        "invented_concept_in_theorem": any(any(not concepts[c]["seed"] for c in t.get("concepts", []) if c in concepts) for t in theorems.values()),
        "later_reuse": bool(state["downstream"]),
        "proof_dependency_depth_at_least_two": any(depth(t) >= 2 for t in theorems),
        "future_search_reduced": sum(state["costs"].get("search", {}).get(k, 0) for k in ("proof_calls_avoided", "candidate_evaluations_avoided")) > 0,
    }
    return {"criteria": criteria, "all_minimum_criteria": all(criteria.values()),
            "concepts": len(concepts), "theorems": len(theorems), "statuses": statuses,
            "max_proof_depth": max([depth(t) for t in theorems] or [0]),
            "representations": len(state["representations"]), "procedures": len(state["procedures"]),
            "downstream_uses": len(state["downstream"]), "costs": state["costs"],
            "seconds": state["seconds"], "stop_reason": state["stop_reason"],
            "new_general_algorithm_demonstrated": False,
            "scope": state["axioms"], "external_unseen_tasks_evaluated": 0}
