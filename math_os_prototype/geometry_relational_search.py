"""Contract-directed synthesis over the relational geometry DSL.

Task format is the existing point-construction task: exact rational input
points and goal atoms over a distinguished point ``u``. The search never uses a
numeric heuristic, a target coordinate or a task-specific rule. Plans are
partial programs whose holes carry relation specs; a hole is filled by an
existing point that satisfies its spec at the instance, or by a primitive whose
kernel-certified post produces each spec atom directly or through a certified
MR-transfer instance, whose premises become the specs of the new input holes.

Only executions of primitives are charged as applications. Planning expansions,
predicate checks and certifications are counted and bounded separately.
Solutions are accepted only after primitive re-execution from the input points
and an exact goal check with prerequisites (same procedure as
SemanticGeometryDomain.replay / is_goal).
"""
from __future__ import annotations

from collections import Counter
import heapq
from itertools import product
import time

import sympy as sp

from math_os_prototype import geometry_contracts as gc
from math_os_prototype import geometry_relational_dsl as rdsl
from math_os_prototype import geometry_semantic_dsl as dsl
from math_os_prototype.representation_progress import digest


def independent_replay(term, inputs):
    """Primitive re-execution of a construction term from input coordinates only.

    Same procedure as SemanticGeometryDomain.replay: gc.dag + FRAGMENT.primitive.
    """
    started = time.perf_counter()
    elaborator = gc._JGEXElaborator()
    elaborator.coordinates.update({n: tuple(sp.Rational(v) for v in xy) for n, xy in inputs.items()})
    if term.get("op") == "var":
        final, steps = term["name"], []
    else:
        steps, final = gc.dag(term, fragment=dsl.FRAGMENT)
    for step in steps:
        dsl.FRAGMENT.primitive(elaborator, step["family"], step["output"], step["inputs"])
        if any(sp.cancel(d) == 0 for d in elaborator.denominators):
            raise ValueError("primitive replay degeneracy")
    return elaborator.coordinates[final], {"seconds": time.perf_counter()-started,
                                           "primitive_operations": len(steps),
                                           "method": "primitive reexecution, not contract witness"}


class RelationalSynthesis:
    """Best-first contract-directed synthesis for one point-construction task."""

    def __init__(self, task, config, *, transfer=True, library=None, fallback=None, emit=None):
        self.task = task
        self.config = config
        self.transfer = transfer
        # library: {(predicate, args over v,p0,p1,p2): entry} from geometry_relational_library.acquire,
        # acquired without reading any task. fallback: callable(task, remaining_applications) -> row.
        self.library = library or {}
        self.fallback = fallback
        self.emit = emit or (lambda event: None)
        self.costs = Counter()
        self.contracts = rdsl.primitive_contracts()
        # A learned policy is data: it may reorder the families that are offered,
        # and nothing else. An unknown or missing order leaves the kernel order.
        order = (config or {}).get("family_order")
        if order:
            ranked = sorted(self.contracts, key=lambda f: (order.index(f) if f in order else len(order), f))
            self.contracts = {f: self.contracts[f] for f in ranked}
        self.shapes = rdsl.transfer_shapes() if transfer else {}
        self.inputs = {n: tuple(sp.Rational(v) for v in xy) for n, xy in task["points"].items()}
        self.coordinates = dict(self.inputs)
        self.names = list(self.inputs)
        self.terms = {n: gc.point(n) for n in self.inputs}
        self.executed = {}
        self.goal_atoms = [(g["predicate"], tuple(g["points"])) for g in task["goals"]]
        self.solution = None
        self.stop_reason = None
        self.serial = 0

    # -- instance checks -------------------------------------------------
    def _spec_holds(self, spec, name):
        for predicate, args in spec:
            self.costs["polynomial_checks"] += 1
            if not rdsl.polynomial_holds(predicate, tuple(name if a == "v" else a for a in args), self.coordinates):
                return False
        return True

    def _goal_holds(self, name):
        if name in self.inputs:
            return False
        for predicate, args in self.goal_atoms:
            if not rdsl.atom_holds(predicate, tuple(name if a == "u" else a for a in args), self.coordinates, self.costs):
                return False
        return True

    # -- plans -----------------------------------------------------------
    # A plan is (nodes, distinct, penalty). penalty counts root goal atoms left
    # unguaranteed by contracts; they are decided only by the exact goal check.
    # nodes: tuple indexed by id of
    #   ("hole", spec)            spec: tuple of canonical atoms with "v"
    #   ("name", point_name)
    #   ("step", family, arg_ids)
    def _root_plan(self):
        spec = tuple(sorted({rdsl.canonical_atom(p, tuple("v" if a == "u" else a for a in args))
                             for p, args in self.goal_atoms}))
        return ((("hole", spec),), (), 0)

    @staticmethod
    def _holes(nodes):
        return [i for i, node in enumerate(nodes) if node[0] == "hole"]

    def _priority(self, plan):
        nodes, _, penalty = plan
        steps = sum(1 for n in nodes if n[0] == "step")
        specified = sum(1 for n in nodes if n[0] == "hole" and n[1])
        empty = sum(1 for n in nodes if n[0] == "hole" and not n[1])
        return (steps+specified+penalty, empty)

    def _key(self, plan):
        nodes, distinct, penalty = plan
        order, seen = [], {}
        def visit(i):
            if i in seen:
                return
            seen[i] = len(seen)
            node = nodes[i]
            if node[0] == "step":
                for a in node[2]:
                    visit(a)
            order.append(i)
        visit(0)
        def render(i):
            node = nodes[i]
            if node[0] == "step":
                return ["step", node[1], [seen[a] for a in node[2]]]
            return [node[0], list(node[1]) if node[0] == "hole" else node[1]]
        return digest([[render(i) for i in order], sorted(sorted((seen[a], seen[b])) for a, b in distinct), penalty])

    def _matchings(self, family, spec):
        """Each spec atom produced directly by a post atom, or transferred through a certified shape."""
        contract = self.contracts[family]
        options_per_atom = []
        for predicate, args in spec:
            options = []
            group = rdsl.certified_symmetry_group(predicate)
            for relation in contract["post"]:
                post_args = tuple(relation["args"])
                if relation["atom"] == predicate:
                    for perm in group:
                        permuted = tuple(args[perm[k]] for k in range(len(args)))
                        binding, ok = {}, True
                        for alpha, beta in zip(permuted, post_args, strict=True):
                            if (alpha == "v") != (beta == "y"):
                                ok = False
                                break
                            if alpha == "v":
                                continue
                            if binding.setdefault(beta, alpha) != alpha:
                                ok = False
                                break
                        if ok:
                            options.append(("direct", tuple(sorted(binding.items()))))
                if self.transfer and "y" in post_args and len(set(post_args)) == 3:
                    others = [a for a in dict.fromkeys(post_args) if a != "y"]
                    roles = tuple("y" if a == "y" else ("x1" if a == others[0] else "x2") for a in post_args)
                    shape = rdsl.canonical_atom(relation["atom"], roles)
                    if shape in self.shapes and rdsl.certify_transfer(predicate, args, "v", shape, self.costs):
                        options.append(("transfer", tuple(others), (predicate, args)))
            if not options:
                return []
            options_per_atom.append(sorted(set(options), key=repr))
        return list(product(*options_per_atom))

    def _expand(self, plan, allow_partial=False):
        nodes, distinct, _ = plan
        hole = self._holes(nodes)[0]
        spec = nodes[hole][1]
        is_root = hole == 0
        children = []
        partners = [b if a == hole else a for a, b in distinct if hole in (a, b)]
        taken = {nodes[p][1] for p in partners if nodes[p][0] == "name"}
        candidates = list(self.names) if spec else list(self.inputs)
        for name in candidates:
            if name in taken or (is_root and name in self.inputs):
                continue
            if any(self.coordinates[name] == self.coordinates[t] for t in taken):
                continue
            if is_root and not self._goal_holds(name):
                continue
            if not is_root and not self._spec_holds(spec, name):
                continue
            children.append(self._replace(plan, hole, ("name", name), [], []))
        if not spec:
            return children
        subsets = [(spec, 0)]
        if allow_partial and is_root and len(spec) > 1:
            subsets += [(tuple(a for a in spec if a != skipped), 1) for skipped in spec]
        for subset, extra in subsets:
            children.extend(self._step_children(plan, hole, subset, extra))
            if self.library:
                children.extend(self._library_children(plan, hole, subset, extra))
        return [c for c in children if c is not None]

    def _step_children(self, plan, hole, spec, extra):
        children = []
        for family, contract in self.contracts.items():
            for matching in self._matchings(family, spec):
                bound, specs, pairs, ok = {}, {p: set() for p in contract["params"]}, [], True
                for option in matching:
                    if option[0] == "direct":
                        for param, name in option[1]:
                            if bound.setdefault(param, name) != name:
                                ok = False
                    else:
                        left, right = option[1]
                        specs[left].add(option[2])
                        specs[right].add(option[2])
                        pairs.append((left, right))
                if not ok:
                    continue
                for param, name in bound.items():
                    if specs[param] and not self._spec_holds(tuple(specs[param]), name):
                        ok = False
                        break
                if not ok or not self._requirements_possible(contract, bound):
                    continue
                placeholders = [bound.get(p, "_hole_"+p) for p in contract["params"]]
                if rdsl.binding_returns_input(family, placeholders):
                    self.costs["identity_bindings_excluded"] += 1
                    continue
                args, new_nodes = [], []
                for param in contract["params"]:
                    if param in bound:
                        new_nodes.append(("name", bound[param]))
                    else:
                        new_nodes.append(("hole", tuple(sorted(rdsl.canonical_atom(p, a) for p, a in specs[param]))))
                    args.append(param)
                children.append(self._replace(plan, hole, ("step", family, contract["params"]), new_nodes, pairs, extra))
        return children

    def _library_children(self, plan, hole, spec, extra=0):
        """Acquired programs whose exactly certified contract produces every spec atom."""
        from itertools import permutations
        fixed = list(dict.fromkeys(a for _, args in spec for a in args if a != "v"))
        # How many named points a retrieved program may be bound to. The enumerated
        # index is written over three, so three is the default; a library holding
        # operations over more says so in the configuration.
        slots = tuple(self.config.get("library_slots", ("p0", "p1", "p2")))
        if len(fixed) > len(slots):
            return []
        limit = self.config.get("library_programs_per_binding", 2)
        children, used = [], set()
        for image in permutations(slots, len(fixed)):
            renaming = dict(zip(fixed, image, strict=True))
            patterns = [rdsl.canonical_atom(p, tuple(renaming.get(a, a) for a in args)) for p, args in spec]
            self.costs["library_queries"] += 1
            accepted = 0
            for index in self.library.candidates(patterns):
                if accepted >= limit:
                    break
                started = time.perf_counter()
                before = self.library.costs["exact_certifications"]
                certified = all(self.library.certified(index, pattern) is not None for pattern in patterns)
                self.costs["library_exact_certifications"] += self.library.costs["exact_certifications"]-before
                self.costs["library_certification_seconds"] += time.perf_counter()-started
                if not certified:
                    continue
                program = self.library.programs[index]
                binding = {slot: name for name, slot in renaming.items()}
                signature = (index, tuple(sorted((k, v) for k, v in binding.items() if k in program["params"])))
                accepted += 1
                if signature in used:
                    continue
                used.add(signature)
                children.append(self._insert_program(plan, hole, program, binding, extra))
        return children

    def _insert_program(self, plan, hole, program, binding, extra=0):
        nodes, distinct, penalty = plan
        nodes = list(nodes)
        ids = {}
        used = {a for step in program["steps"] for a in step["args"]}
        for param in program["params"]:
            if param not in used:
                continue          # an unused input would be an unreachable hole
            ids[param] = len(nodes)
            nodes.append(("name", binding[param]) if param in binding else ("hole", ()))
        for step in program["steps"]:
            node = ("step", step["prim"], tuple(ids[a] for a in step["args"]))
            if step["out"] == program["result"]:
                nodes[hole] = node
                ids[step["out"]] = hole
            else:
                ids[step["out"]] = len(nodes)
                nodes.append(node)
        return (tuple(nodes), tuple(distinct), penalty+extra)

    def _requirements_possible(self, contract, bound):
        """Refute a binding before charging: a requirement whose polynomial vanishes at the bound names."""
        for requirement in contract["pre"]:
            if all(a in bound for a in requirement["args"]):
                args = tuple(bound[a] for a in requirement["args"])
                self.costs["polynomial_checks"] += 1
                if not rdsl.polynomial_holds(requirement["atom"], args, self.coordinates):
                    self.costs["refuted_before_charge"] += 1
                    return False
            elif len(set(bound.get(a, a) for a in requirement["args"])) < len(requirement["args"]) and \
                    rdsl._generic_polynomial(requirement["atom"], tuple(bound.get(a, a) for a in requirement["args"])) == 0:
                self.costs["refuted_before_charge"] += 1
                return False
        return True

    def _replace(self, plan, hole, node, new_nodes, pairs, extra=0):
        nodes, distinct, penalty = plan
        nodes = list(nodes)
        if node[0] == "step":
            family, params = node[1], node[2]
            ids = []
            for new in new_nodes:
                ids.append(len(nodes))
                nodes.append(new)
            index = dict(zip(params, ids, strict=True))
            nodes[hole] = ("step", family, tuple(ids))
            distinct = tuple(distinct)+tuple((index[a], index[b]) for a, b in pairs)
        else:
            nodes[hole] = node
        return (tuple(nodes), tuple(distinct), penalty+extra)

    # -- execution -------------------------------------------------------
    def _execute(self, plan, applications):
        nodes, distinct, _ = plan
        resolved = {}
        def resolve(i):
            if i in resolved:
                return resolved[i]
            node = nodes[i]
            if node[0] == "name":
                resolved[i] = node[1]
                return node[1]
            args = [resolve(a) for a in node[2]]
            if any(a is None for a in args):
                resolved[i] = None
                return None
            # Transfer premises include diff(xi, xj): refuse before charging when they coincide.
            members = set(node[2])
            for a, b in distinct:
                if a in members and b in members and self.coordinates[resolved[a]] == self.coordinates[resolved[b]]:
                    self.costs["distinctness_failures"] += 1
                    resolved[i] = None
                    return None
            key = rdsl.canonical_step(node[1], args)
            if key in self.executed:
                resolved[i] = self.executed[key]
                return resolved[i]
            if rdsl.binding_returns_input(node[1], args):
                self.costs["identity_bindings_excluded"] += 1
                self.executed[key] = None
                resolved[i] = None
                return None
            if self.costs["applications"] >= applications:
                self.stop_reason = "application_budget"
                resolved[i] = None
                return None
            self.costs["applications"] += 1
            started = time.perf_counter()
            xy, reason = rdsl.execute_primitive(key[0], list(key[1]), self.coordinates, self.costs)
            self.costs["execution_seconds"] += time.perf_counter()-started
            if xy is None:
                self.costs["refused_applications"] += 1
                self.executed[key] = None
                self.emit({"event": "relational_refusal", "family": key[0], "inputs": list(key[1]), "reason": reason})
                resolved[i] = None
                return None
            existing = next((n for n in self.names if self.coordinates[n] == xy), None)
            if existing is not None:
                self.costs["duplicate_outputs"] += 1
                name = existing
            else:
                name = f"n{len(self.names)}"
                self.coordinates[name] = xy
                self.names.append(name)
                self.terms[name] = {"op": key[0], "args": [self.terms[a] for a in key[1]]}
                self.emit({"event": "relational_execution", "family": key[0], "inputs": list(key[1]), "output": name})
                if self.solution is None and self._goal_holds(name):
                    self._accept(name)
            self.executed[key] = name
            resolved[i] = name
            return name
        root = resolve(0)
        for a, b in distinct:
            if resolved.get(a) is None or resolved.get(b) is None:
                continue
            if self.coordinates[resolved[a]] == self.coordinates[resolved[b]]:
                self.costs["distinctness_failures"] += 1
        if root is not None and self.solution is None and self._goal_holds(root):
            self._accept(root)

    def _fallback_solution_passes(self, solution):
        """Same acceptance as directed solutions: primitive replay, exact goal atoms, not an input point."""
        try:
            xy, _ = independent_replay(solution["term"], self.inputs)
        except (ValueError, KeyError):
            return False
        xy = tuple(sp.cancel(v) for v in xy)
        if xy in set(self.inputs.values()):
            return False
        local = dict(self.inputs, u=xy)
        return all(rdsl.atom_holds(p, tuple(args), local) for p, args in self.goal_atoms)

    def _accept(self, name):
        term = self.terms[name]
        xy, replay = independent_replay(term, self.inputs)
        passed = tuple(sp.cancel(v) for v in xy) == self.coordinates[name]
        goals = [rdsl.atom_holds(p, tuple(name if a == "u" else a for a in args), self.coordinates)
                 for p, args in self.goal_atoms]
        if not passed or not all(goals):
            self.costs["goal_replay_failures"] += 1
            return
        primitive = term
        self.solution = {"point": name, "term": term, "primitive_expansion": primitive,
                         "goals": [{"predicate": p, "arguments": [name if a == "u" else a for a in args]}
                                   for p, args in self.goal_atoms],
                         "replay": dict(replay, passed=True,
                                        residuals=[str(sp.cancel(a-b)) for a, b in zip(xy, self.coordinates[name])]),
                         "applications_at_solution": self.costs["applications"]}

    # -- search ----------------------------------------------------------
    def search(self, applications):
        """Phases with declared allowances: certified plans, then partially certified root plans.

        Each phase has its own application and plan-expansion allowance from the
        configuration; the remainder of the application budget goes to the fallback.
        """
        started = time.perf_counter()
        wall = self.config.get("wall_seconds", 600)
        max_steps = self.config.get("max_plan_steps", 8)
        phases = [("guaranteed", False, self.config.get("guaranteed_applications", 40),
                   self.config.get("guaranteed_expansions", 2000))]
        if self.config.get("partial_root_coverage", True):
            phases.append(("partial", True, self.config.get("partial_applications", 16),
                           self.config.get("partial_expansions", 1000)))
        try:
            for phase, allow_partial, allowance, expansions in phases:
                if self.solution is not None or self.stop_reason == "wall_time_budget":
                    break
                if self.costs["applications"] >= applications:
                    self.stop_reason = "application_budget"
                    break
                self.stop_reason = None
                cap = min(applications, self.costs["applications"]+allowance)
                expansion_cap = self.costs["plan_expansions"]+expansions
                root = self._root_plan()
                queue = [(self._priority(root), 0, root)]
                seen = {self._key(root)}
                while queue and self.solution is None:
                    if time.perf_counter()-started > wall:
                        self.stop_reason = "wall_time_budget"
                        break
                    if self.costs["plan_expansions"] >= expansion_cap:
                        self.stop_reason = "plan_expansion_budget"
                        break
                    _, _, plan = heapq.heappop(queue)
                    if not self._holes(plan[0]):
                        self.costs[phase+"_plans_executed"] += 1
                        self._execute(plan, cap)
                        if self.stop_reason == "application_budget":
                            break
                        continue
                    self.costs["plan_expansions"] += 1
                    for child in self._expand(plan, allow_partial):
                        if sum(1 for n in child[0] if n[0] == "step") > max_steps:
                            self.costs["plans_over_step_budget"] += 1
                            continue
                        key = self._key(child)
                        if key in seen:
                            continue
                        seen.add(key)
                        self.serial += 1
                        heapq.heappush(queue, (self._priority(child), self.serial, child))
                    self.costs["max_queue"] = max(self.costs["max_queue"], len(queue))
                if not queue and self.solution is None and self.stop_reason is None:
                    self.stop_reason = "plans_exhausted"
                self.costs[phase+"_stop_"+str(self.stop_reason)] += 1
                self.costs[phase+"_applications_used"] = self.costs["applications"]
        finally:
            self.costs["search_seconds"] += time.perf_counter()-started
        if self.solution is None and self.stop_reason != "wall_time_budget" and self.costs["applications"] < applications:
            self.stop_reason = "directed_phases_complete"
        remaining = applications-self.costs["applications"]
        elapsed = time.perf_counter()-started
        wall = self.config.get("wall_seconds", 600)
        if (self.solution is None and self.fallback is not None and remaining > 0 and elapsed < wall
                and self.stop_reason == "directed_phases_complete"):
            row = self.fallback(self.task, remaining, wall-elapsed)
            self.costs["fallback_applications"] = row["applications"]
            self.costs["applications"] += row["applications"]
            for key, value in row.get("costs", {}).items():
                if isinstance(value, (int, float)):
                    self.costs["fallback_"+key] += value
            if row["solved"] and self._fallback_solution_passes(row["solution"]):
                self.solution = dict(row["solution"], via="fallback", applications_at_solution=self.costs["applications"])
                self.stop_reason = "fallback"
            else:
                if row["solved"]:
                    self.costs["fallback_solutions_refused"] += 1
                self.stop_reason = "fallback_"+str(row["stop_reason"])
        return {"task_sha256": digest(self.task), "solved": self.solution is not None,
                "solution": self.solution, "costs": dict(self.costs),
                "stop_reason": "proved" if self.solution else self.stop_reason,
                "wall_seconds": time.perf_counter()-started,
                "candidate_enumeration": "contract_directed_synthesis",
                "transfer_metarule": self.transfer}
