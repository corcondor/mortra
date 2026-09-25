"""Generic program edits. No mechanic-name templates or hash-based fitness."""
import copy
from dataclasses import dataclass

from .world import game_hash, validate

CONDITIONS = ("mortra", "random", "size_only")
FAMILIES = ("variable_add", "variable_delete", "domain", "action_add", "action_delete", "rule_add", "rule_delete",
            "guard", "assignment", "priority", "dependency", "topology", "board", "initial")
SIZE_FAMILIES = ("topology", "board", "initial")


def effect(g, rng, var=None):
    i = rng.randrange(len(g["domains"])) if var is None else var
    op = rng.choice(["set", "add", "add_mod", "copy_mod"])
    v = (rng.randrange(len(g["domains"])) if op == "copy_mod" else
         rng.randrange(g["domains"][i]) if op == "set" else rng.choice([-1, 1]))
    return {"var": i, "op": op, "value": v}


def guard(g, rng):
    i = rng.randrange(len(g["domains"]))
    return {"var": i, "op": rng.choice(["eq", "ne", "lt", "ge"]), "value": rng.randrange(g["domains"][i])}


def rule(g, rng):
    return {"action": rng.randrange(g["actions"]), "guard": [guard(g, rng)] if rng.randrange(2) else [],
            "assign": [effect(g, rng)]}


def generate(rng):
    n = 12
    # Unit displacement is an explicit spatial prior, not a named mechanic.
    domains = [n, n] + ([rng.choice([2, 3])] if rng.randrange(2) else [])
    actions = rng.randint(3, 8)
    density = rng.uniform(.05, .20)
    walls = [[x, y] for x in range(n) for y in range(n)
             if x in (0, n - 1) or y in (0, n - 1) or rng.random() < density]
    free = [(x, y) for x in range(1, n - 1) for y in range(1, n - 1) if [x, y] not in walls]
    x, y = rng.choice(free)
    g = {"version": "finite-program-v1.1", "domains": domains, "actions": actions, "walls": walls,
         "initial": [x, y] + [rng.randrange(d) for d in domains[2:]], "rules": [],
         "rendering": {"position_variables": [0, 1]}}
    displacements = [(0, -1), (0, 1), (1, -1), (1, 1)]
    rng.shuffle(displacements)
    action_ids = list(range(actions))
    rng.shuffle(action_ids)
    for a, (i, v) in zip(action_ids, displacements):
        g["rules"].append({"action": a, "guard": [], "assign": [{"var": i, "op": "add", "value": v}]})
    for a in action_ids[4:]:
        g["rules"].append({"action": a, "guard": [], "assign": [effect(g, rng)]})
    if len(domains) > 2:
        r = rng.choice(g["rules"])
        if not any(e["var"] == 2 for e in r["assign"]):
            r["assign"].append({"var": 2, "op": "add_mod", "value": 1})
    for _ in range(rng.randrange(4)):
        g["rules"].insert(rng.randrange(len(g["rules"]) + 1), rule(g, rng))
    return validate(g)


def mutate(parent, family, rng, max_board):
    g = copy.deepcopy(parent)
    if family == "variable_add":
        i = len(g["domains"])
        g["domains"].append(rng.choice([2, 3, 4]))
        g["initial"].append(0)
        if not g["rules"]:
            g["rules"].append(rule(g, rng))
        r = rng.choice(g["rules"])
        r["assign"] = [e for e in r["assign"] if e["var"] != i] + [effect(g, rng, i)]
    elif family == "variable_delete":
        if len(g["domains"]) == 2:
            raise ValueError("only spatial variables remain")
        i = len(g["domains"]) - 1
        g["domains"].pop()
        g["initial"].pop()
        for r in g["rules"]:
            r["guard"] = [c for c in r["guard"] if c["var"] != i]
            r["assign"] = [e for e in r["assign"] if e["var"] != i and not (e["op"] == "copy_mod" and e["value"] == i)]
        g["rules"] = [r for r in g["rules"] if r["assign"]]
    elif family == "domain":
        if len(g["domains"]) == 2:
            raise ValueError("no nonspatial domain")
        i = rng.randrange(2, len(g["domains"]))
        g["domains"][i] += rng.choice([-1, 1])
    elif family == "action_add":
        if g["actions"] == 8:
            raise ValueError("action upper bound")
        g["actions"] += 1
        r = rule(g, rng)
        r["action"] = g["actions"] - 1
        g["rules"].append(r)
    elif family == "action_delete":
        if g["actions"] == 3:
            raise ValueError("action lower bound")
        g["actions"] -= 1
        g["rules"] = [r for r in g["rules"] if r["action"] < g["actions"]]
    elif family == "rule_add":
        g["rules"].insert(rng.randrange(len(g["rules"]) + 1), rule(g, rng))
    elif family == "rule_delete":
        if not g["rules"]:
            raise ValueError("no rule")
        g["rules"].pop(rng.randrange(len(g["rules"])))
    elif family in ("guard", "assignment", "dependency", "priority"):
        if not g["rules"]:
            raise ValueError("no rule")
        r = rng.choice(g["rules"])
        if family == "guard":
            if r["guard"] and rng.randrange(2):
                r["guard"].pop(rng.randrange(len(r["guard"])))
            else:
                r["guard"].append(guard(g, rng))
        elif family == "priority":
            g["rules"].remove(r)
            g["rules"].insert(rng.randrange(len(g["rules"]) + 1), r)
        else:
            i = rng.randrange(len(g["domains"]))
            e = {"var": i, "op": "copy_mod", "value": rng.randrange(len(g["domains"]))} if family == "dependency" else effect(g, rng, i)
            r["assign"] = [a for a in r["assign"] if a["var"] != i] + [e]
    elif family == "topology":
        n = g["domains"][0]
        p = [rng.randrange(1, n - 1), rng.randrange(1, n - 1)]
        if p == g["initial"][:2]:
            raise ValueError("protected reset state")
        if p in g["walls"]:
            g["walls"].remove(p)
        else:
            g["walls"].append(p)
            g["walls"].sort()
    elif family == "board":
        old = g["domains"][0]
        options = [n for n in (12, 16, 24, 32) if old < n <= max_board]
        if not options:
            raise ValueError("board upper bound")
        n = options[0]
        g["domains"][:2] = [n, n]
        g["walls"] = [p for p in g["walls"] if 0 < p[0] < old - 1 and 0 < p[1] < old - 1]
        g["walls"] += [[x, y] for x in range(n) for y in range(n) if x in (0, n - 1) or y in (0, n - 1)]
    elif family == "initial":
        n = g["domains"][0]
        floors = [(x, y) for x in range(n) for y in range(n) if [x, y] not in g["walls"]]
        g["initial"][:2] = rng.choice(floors)
    else:
        raise ValueError("unknown mutation")
    validate(g)
    if game_hash(parent) == game_hash(g):
        raise ValueError("no-op edit")
    return g


@dataclass(frozen=True)
class Feedback:
    identifier: str
    valid: bool
    full_success: float
    learned_success: float
    D: float
    B80: int | None
    B90: int | None
    median_success_steps: float


def choose(condition, parent, candidates, rng, budget):
    valid = [c for c in candidates if c.valid]
    if condition == "random":
        return rng.choice(valid) if valid else parent
    eligible = [c for c in [parent, *valid] if c.valid and c.full_success >= .8 and c.learned_success >= .8]
    if not eligible:
        return parent
    def score(c):
        return (c.D, c.B80 if c.B80 is not None else budget + 1,
                c.B90 if c.B90 is not None else budget + 1, c.median_success_steps)
    best = max(map(score, eligible))
    return rng.choice([c for c in eligible if score(c) == best])
