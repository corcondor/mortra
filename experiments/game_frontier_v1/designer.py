"""Fixed mutation grammar and metric-only designer selection, registered before runs."""
from dataclasses import dataclass
import json
import random

from .world import ACTIONS, canonical, game_hash, validate

FAMILIES = ("board_expansion", "wall_add_remove", "route_relocation", "object_add_remove",
            "object_property", "rule_add_remove", "condition_add", "effect_change",
            "dependency_chain", "portal", "hazard", "consumable", "movable_object",
            "temporary_retreat", "irreversible")
SIZE_FAMILIES = ("board_expansion", "wall_add_remove", "route_relocation")
CONDITIONS = ("mortra", "random", "size_only")


def initial_game(seed):
    rng = random.Random(seed)
    goal = rng.choice([[2, 1], [2, 3], [1, 2], [3, 2]])
    return validate({"version": 1, "board": {"width": 12, "height": 12,
        "walls": [[x, y] for x in range(12) for y in range(12)
                  if not (1 <= x <= 3 and 1 <= y <= 3)]},
        "objects": [], "rules": [], "flags": [], "action_set": list(ACTIONS),
        "start": [2, 2], "goal": goal})


def _floors(g):
    walls = set(map(tuple, g["board"]["walls"]))
    return [(x, y) for x in range(1, g["board"]["width"] - 1)
            for y in range(1, g["board"]["height"] - 1) if (x, y) not in walls]


def _add_object(g, rng, **props):
    occupied = {tuple(o["position"]) for o in g["objects"]} | {tuple(g["start"]), tuple(g["goal"])}
    cells = [p for p in _floors(g) if p not in occupied]
    if not cells:
        raise ValueError("no object placement")
    obj = {"id": len(g["objects"]), "position": list(rng.choice(cells)), "portable": False,
           "solid": False, "active": True, "hazard": False, "counter": 0, "counter_max": 3, "mode": 0}
    obj.update(props)
    g["objects"].append(obj)
    return obj["id"]


def _rule(g, trigger, effects, conditions=None):
    g["rules"].append({"id": max((r["id"] for r in g["rules"]), default=-1) + 1,
                       "trigger": trigger, "conditions": conditions or [], "effects": effects})


def _flag(g):
    g["flags"].append(False)
    return len(g["flags"]) - 1


def _condition(g, rng):
    choices = ["region"]
    if g["objects"]:
        choices += ["carrying", "not_carrying", "active", "counter"]
    if g["flags"]:
        choices += ["flag"]
    kind = rng.choice(choices)
    if kind == "region":
        return {"kind": kind, "cells": [list(rng.choice(_floors(g)))]}
    if kind == "flag":
        return {"kind": kind, "flag": rng.randrange(len(g["flags"])), "value": rng.choice([True, False])}
    result = {"kind": kind, "object": rng.randrange(len(g["objects"]))}
    if kind == "active":
        result["value"] = rng.choice([True, False])
    if kind == "counter":
        result.update(op=rng.choice(["eq", "lt", "ge"]), value=rng.randrange(4))
    return result


def _effect(g, rng):
    options = ["teleport"]
    if g["objects"]:
        options += ["set_active", "set_passability", "toggle_passability", "consume", "move", "increment", "set_hazard"]
        if any(o["portable"] for o in g["objects"]):
            options += ["give", "take"]
    if g["flags"]:
        options += ["set_flag", "toggle_flag"]
    kind = rng.choice(options)
    eff = {"kind": kind}
    if kind in ("set_flag", "toggle_flag"):
        eff["flag"] = rng.randrange(len(g["flags"]))
    elif kind != "teleport":
        candidates = [o["id"] for o in g["objects"] if kind not in ("give", "take") or o["portable"]]
        eff["object"] = rng.choice(candidates)
    if kind in ("set_flag", "set_active", "set_passability", "set_hazard"):
        eff["value"] = rng.choice([True, False])
    if kind in ("teleport", "move"):
        eff["position"] = list(rng.choice(_floors(g)))
    if kind == "increment":
        eff["value"] = rng.choice([-1, 1])
    return eff


def mutate(parent, family, rng, max_board):
    g = json.loads(canonical(parent))
    before = game_hash(g)
    walls = set(map(tuple, g["board"]["walls"]))
    protected = {tuple(g["start"]), tuple(g["goal"])} | {tuple(o["position"]) for o in g["objects"]}
    if family == "board_expansion":
        sizes = [n for n in (12, 16, 24, 32) if g["board"]["width"] < n <= max_board]
        if not sizes:
            raise ValueError("already at maximum board")
        old = g["board"]["width"]
        new = sizes[0]
        walls.update((x, y) for x in range(new) for y in range(new) if x >= old or y >= old)
        # One bounded corridor extension, without changing goal/rules/objects.
        x, y = rng.choice(_floors(g))
        if rng.randrange(2):
            walls.difference_update((xx, y) for xx in range(x, new - 1))
        else:
            walls.difference_update((x, yy) for yy in range(y, new - 1))
        g["board"].update(width=new, height=new)
    elif family == "wall_add_remove":
        floors = _floors(g)
        adjacent = sorted({(x + dx, y + dy) for x, y in floors for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0))
                           if 0 < x + dx < g["board"]["width"] - 1 and 0 < y + dy < g["board"]["height"] - 1
                           and (x + dx, y + dy) in walls})
        removable_floor = [p for p in floors if p not in protected]
        if adjacent and (rng.randrange(2) or not removable_floor):
            walls.remove(rng.choice(adjacent))
        elif removable_floor:
            walls.add(rng.choice(removable_floor))
        else:
            raise ValueError("no wall edit")
    elif family == "route_relocation":
        choices = [p for p in _floors(g) if p not in protected]
        if not choices:
            raise ValueError("no goal relocation")
        g["goal"] = list(rng.choice(choices))
    elif family == "object_add_remove":
        referenced = {d["object"] for r in g["rules"] for d in [r["trigger"], *r["conditions"], *r["effects"]] if "object" in d}
        if g["objects"] and g["objects"][-1]["id"] not in referenced and rng.randrange(2):
            g["objects"].pop()
        else:
            _add_object(g, rng, portable=bool(rng.randrange(2)), solid=bool(rng.randrange(2)))
    elif family == "object_property":
        if not g["objects"]:
            _add_object(g, rng)
        o = rng.choice(g["objects"])
        key = rng.choice(["portable", "solid", "active", "mode", "counter"])
        o[key] = (o[key] + 1) % 4 if key in ("mode", "counter") else not o[key]
    elif family == "rule_add_remove":
        if g["rules"] and rng.randrange(2):
            g["rules"].remove(rng.choice(g["rules"]))
        else:
            if not g["objects"]:
                _add_object(g, rng, portable=True)
            _rule(g, {"event": rng.choice(["ENTER", "INTERACT", "PICK", "DROP", "PUSH"]),
                      "object": rng.randrange(len(g["objects"]))}, [_effect(g, rng)])
    elif family in ("condition_add", "effect_change"):
        if not g["rules"]:
            i = _add_object(g, rng)
            _rule(g, {"event": "INTERACT", "object": i}, [{"kind": "increment", "object": i, "value": 1}])
        if family == "condition_add":
            candidates = [r for r in g["rules"] if len(r["conditions"]) < 4]
            if not candidates:
                raise ValueError("condition bound")
            rng.choice(candidates)["conditions"].append(_condition(g, rng))
        else:
            r = rng.choice(g["rules"])
            r["effects"][rng.randrange(len(r["effects"]))] = _effect(g, rng)
    elif family == "dependency_chain":
        i, j = _add_object(g, rng), _add_object(g, rng, solid=True)
        f = _flag(g)
        prev = {"kind": "flag", "flag": rng.randrange(f), "value": True} if f else None
        _rule(g, {"event": "INTERACT", "object": i}, [{"kind": "set_flag", "flag": f, "value": True}], [prev] if prev else [])
        _rule(g, {"event": "INTERACT", "object": j}, [{"kind": "set_passability", "object": j, "value": True}],
              [{"kind": "flag", "flag": f, "value": True}])
    elif family == "portal":
        i = _add_object(g, rng)
        _rule(g, {"event": "ENTER", "object": i}, [{"kind": "teleport", "position": list(rng.choice(_floors(g)))}])
    elif family == "hazard":
        i = _add_object(g, rng, hazard=True)
        _rule(g, {"event": "INTERACT", "object": i}, [{"kind": "set_hazard", "object": i, "value": False}])
    elif family == "consumable":
        i = _add_object(g, rng, portable=True)
        f = _flag(g)
        _rule(g, {"event": "PICK", "object": i}, [{"kind": "set_flag", "flag": f, "value": True}, {"kind": "consume", "object": i}])
    elif family == "movable_object":
        _add_object(g, rng, portable=True, solid=True)
    elif family == "temporary_retreat":
        i, j = _add_object(g, rng), _add_object(g, rng, solid=True)
        _rule(g, {"event": "INTERACT", "object": i}, [{"kind": "toggle_passability", "object": j}])
    elif family == "irreversible":
        i = _add_object(g, rng)
        f = _flag(g)
        _rule(g, {"event": "ENTER", "object": i}, [{"kind": "set_flag", "flag": f, "value": True},
              {"kind": "consume", "object": i}])
    else:
        raise ValueError("unknown mutation family")
    g["board"]["walls"] = [list(p) for p in sorted(walls)]
    validate(g)
    if game_hash(g) == before:
        raise ValueError("no-op mutation")
    return g


@dataclass(frozen=True)
class Feedback:
    game_hash: str
    solvable: bool
    b80: int | None
    difficulty_area: float
    final_success: float


def choose(condition, parent, candidates, rng):
    """No genome, learned model, oracle counts, paths or coverage are accepted."""
    valid = [c for c in candidates if c.solvable]
    if condition == "random":
        return rng.choice(valid) if valid else parent
    eligible = [c for c in valid if c.final_success >= 0.8 and c.b80 is not None]
    if parent.final_success >= 0.8 and parent.b80 is not None:
        eligible.append(parent)
    if not eligible:
        return parent
    return min(eligible, key=lambda c: (-c.b80, -c.difficulty_area, c.game_hash))


def complexity(genome):
    """Syntactic rule-dependency depth of SCC condensation, not proven task depth."""
    rules = genome["rules"]
    def keys(d):
        if "flag" in d:
            return {("flag", d["flag"])}
        if "object" in d:
            return {("object", d["object"])}
        return set()
    reads = [set().union(*(keys(c) for c in [r["trigger"], *r["conditions"]])) for r in rules]
    writes = [set().union(*(keys(e) for e in r["effects"])) for r in rules]
    adj = [{j for j in range(len(rules)) if writes[i] & reads[j]} for i in range(len(rules))]
    reach = []
    for i in range(len(rules)):
        seen, todo = {i}, [i]
        while todo:
            for j in adj[todo.pop()]:
                if j not in seen:
                    seen.add(j)
                    todo.append(j)
        reach.append(seen)
    blocks, owner = [], {}
    for i in range(len(rules)):
        if i not in owner:
            block = {j for j in reach[i] if i in reach[j]}
            for j in block:
                owner[j] = len(blocks)
            blocks.append(block)
    dag = [{owner[j] for i in b for j in adj[i] if owner[j] != owner[i]} for b in blocks]
    memo = {}
    def depth(i):
        if i not in memo:
            memo[i] = 1 + max((depth(j) for j in dag[i]), default=0)
        return memo[i]
    return {"board_width": genome["board"]["width"], "board_height": genome["board"]["height"],
            "objects": len(genome["objects"]), "rules": len(rules),
            "rule_dependency_depth": max((depth(i) for i in range(len(blocks))), default=0),
            "rule_dependency_cycles": sum(len(b) > 1 or any(i in adj[i] for i in b) for b in blocks),
            "mechanic_effect_kinds": len({e["kind"] for r in rules for e in r["effects"]})}
