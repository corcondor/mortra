"""Finite guarded assignments. Variable 0/1 are spatial, never player-visible."""
from collections import deque
import math

from experiments.game_frontier_v1.world import OpaqueMap, canonical, game_hash


def validate(g):
    def need(ok, msg):
        if not ok:
            raise ValueError(msg)
    domains = g["domains"]
    need(g["version"] == "finite-program-v1.1", "version")
    need(len(domains) >= 2 and domains[0] == domains[1] and domains[0] in (12, 16, 24, 32), "board")
    need(all(type(n) is int and n >= 2 for n in domains), "finite domains")
    need(type(g["actions"]) is int and 3 <= g["actions"] <= 8, "action count")
    need(len(g["initial"]) == len(domains) and all(type(v) is int and 0 <= v < n for v, n in zip(g["initial"], domains)), "initial state")
    walls = set(map(tuple, g["walls"]))
    need(len(walls) == len(g["walls"]) and all(len(p) == 2 and all(type(v) is int and 0 <= v < domains[i] for i, v in enumerate(p)) for p in walls), "walls")
    need(tuple(g["initial"][:2]) not in walls, "initial on wall")
    for r in g["rules"]:
        need(type(r["action"]) is int and 0 <= r["action"] < g["actions"], "rule action")
        for c in r["guard"]:
            need(type(c["var"]) is int and 0 <= c["var"] < len(domains), "guard var")
            need(c["op"] in ("eq", "ne", "lt", "ge"), "guard op")
            need(type(c["value"]) is int and 0 <= c["value"] < domains[c["var"]], "guard value")
        need(bool(r["assign"]) and len({e["var"] for e in r["assign"]}) == len(r["assign"]), "assignments")
        for e in r["assign"]:
            need(type(e["var"]) is int and 0 <= e["var"] < len(domains), "effect var")
            need(e["op"] in ("set", "add", "add_mod", "copy_mod"), "effect op")
            need(type(e["value"]) is int, "effect integer")
            if e["op"] == "set":
                need(0 <= e["value"] < domains[e["var"]], "set domain")
            if e["op"] == "copy_mod":
                need(0 <= e["value"] < len(domains), "copy variable")
    return g


class Engine:
    def __init__(self, g):
        validate(g)
        self.genome = g
        self.domains = tuple(g["domains"])
        self.initial = tuple(g["initial"])
        self.num_actions = g["actions"]
        self.walls = frozenset(map(tuple, g["walls"]))
        self.rules_by_action = {a: [r for r in g["rules"] if r["action"] == a] for a in range(self.num_actions)}

    def step(self, s, a):
        if type(a) is not int or not 0 <= a < self.num_actions:
            raise ValueError("action")
        for r in self.rules_by_action[a]:
            if not all({"eq": s[c["var"]] == c["value"], "ne": s[c["var"]] != c["value"],
                        "lt": s[c["var"]] < c["value"], "ge": s[c["var"]] >= c["value"]}[c["op"]] for c in r["guard"]):
                continue
            nxt = list(s)
            for e in r["assign"]:
                i, value = e["var"], e["value"]
                if e["op"] == "set":
                    nxt[i] = value
                elif e["op"] == "add":
                    nxt[i] = s[i] + value
                elif e["op"] == "add_mod":
                    nxt[i] = (s[i] + value) % self.domains[i]
                else:
                    nxt[i] = s[value] % self.domains[i]
            # First matching rule, simultaneous RHS reads, atomic boundary rejection.
            if any(not 0 <= v < n for v, n in zip(nxt, self.domains)) or tuple(nxt[:2]) in self.walls:
                return s
            return tuple(nxt)
        return s


def oracle(engine, cap, roots=None):
    ordered = list(dict.fromkeys(roots or [engine.initial]))
    ids = {s: i for i, s in enumerate(ordered)}
    edges = []
    i = 0
    while i < len(ordered):
        row = []
        for a in range(engine.num_actions):
            nxt = engine.step(ordered[i], a)
            if nxt not in ids:
                if len(ids) >= cap:
                    return {"status": "UNRESOLVED", "reason": "oracle state cap", "explored_states": len(ids)}, None
                ids[nxt] = len(ordered)
                ordered.append(nxt)
            row.append(ids[nxt])
        edges.append(row)
        i += 1
    return {"status": "COMPLETE", "reachable_states": len(ordered), "transition_edges": len(ordered) * engine.num_actions,
            "branching_factor": sum(len(set(row) - {i}) for i, row in enumerate(edges)) / len(edges),
            "branching_states": sum(len(set(row) - {i}) >= 2 for i, row in enumerate(edges))}, (ordered, edges, ids)


def distances(edges, start):
    d = {start: 0}
    q = deque([start])
    while q:
        u = q.popleft()
        for v in edges[u]:
            if v not in d:
                d[v] = d[u] + 1
                q.append(v)
    return d


def complexity(g, stats):
    from experiments.game_frontier_v1.designer import complexity as legacy_complexity
    surrogate = {"board": {"width": g["domains"][0], "height": g["domains"][1]}, "objects": [], "rules": []}
    for i, r in enumerate(g["rules"]):
        reads = {c["var"] for c in r["guard"]}
        reads.update(e["var"] for e in r["assign"] if e["op"] in ("add", "add_mod"))
        reads.update(e["value"] for e in r["assign"] if e["op"] == "copy_mod")
        surrogate["rules"].append({"id": i, "trigger": {}, "conditions": [{"flag": v} for v in sorted(reads)],
                                    "effects": [{"flag": e["var"], "kind": e["op"]} for e in r["assign"]]})
    deps = legacy_complexity(surrogate)
    return {**stats, "actions": g["actions"], "variables": len(g["domains"]), "domain_product": math.prod(g["domains"]),
            "rules": len(g["rules"]), "guard_terms": sum(len(r["guard"]) for r in g["rules"]),
            "assignments": sum(len(r["assign"]) for r in g["rules"]), "board_area": g["domains"][0] * g["domains"][1],
            "rule_dependency_depth": deps["rule_dependency_depth"], "rule_dependency_cycles": deps["rule_dependency_cycles"]}
