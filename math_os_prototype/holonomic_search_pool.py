"""Choose future compositions from raw or already-certified representatives.

The caller verifies rewrite traces and exact equality certificates before
admission. A finite coefficient signature is deliberately not an admission key.
"""
from copy import deepcopy
from itertools import combinations_with_replacement, product

from math_os_prototype.holonomic_route_discovery import key, validate


def primitive_seeds(parameters):
    seeds = [{"op": "hyper", "a": list(a), "b": [b]}
             for a, b in product(combinations_with_replacement(parameters, 2), parameters)]
    return seeds + [{"op": "hyper", "a": [a], "b": []} for a in parameters]


def draw_composition(pool, rng, *, with_add=False, pullback_degree=1, compound_operands=False):
    if type(pullback_degree) is not int or not 1 <= pullback_degree <= 3:
        raise ValueError("pullback degree must be between one and three")
    if type(compound_operands) is not bool:
        raise ValueError("compound operand policy must be boolean")
    parent = pool.choose(rng)
    child, parents = parent["program"], [parent["id"]]
    op = rng.choice(["diff", "mul", "pullback"]+(["add"] if with_add else []))
    if op == "diff":
        p = {"op": op, "child": child}
    elif op in ("mul", "add"):
        other = pool.choose(rng, seed_only=not compound_operands)
        parents.append(other["id"])
        p = {"op": op, "left": child, "right": other["program"]}
    elif pullback_degree == 1:
        p = {"op": op, "child": child, "numerator": [0, rng.choice([-1, 1, 2])],
             "denominator": [1, rng.choice([-1, 0, 1])]}
    else:
        p = {"op": op, "child": child,
             "numerator": [0]+[rng.choice([-2, -1, 0, 1, 2]) for _ in range(pullback_degree-1)]
                 +[rng.choice([-2, -1, 1, 2])],
             "denominator": [1]+[rng.choice([-1, 0, 1]) for _ in range(pullback_degree)]}
    return p, parents


class SeriesSearchPool:
    def __init__(self, policy="raw"):
        if policy not in ("raw", "certified"):
            raise ValueError("unknown pool policy")
        self.policy = policy
        self.entries, self.roots, self.aliases, self.canonical = [], [], {}, {}
        self._root_ids = set()

    def admit(self, row, reduced, *, is_seed=False, equal_to=None):
        validate(row["program"])
        validate(reduced)
        if row["id"] in self.aliases:
            raise ValueError("duplicate candidate id")
        representative, reason = None, "new_entry"
        if self.policy == "certified":
            if equal_to is not None:
                if row["comparison_status"] not in ("equality_via_learned_library", "exact_formal_series_equality", "definition_only_equality"):
                    raise ValueError("unproved equality cannot merge a proposal")
                representative = self.aliases[equal_to]
                reason = "proved_equal_to_previous"
            elif key(reduced) in self.canonical:
                representative = self.canonical[key(reduced)]
                reason = "same_certified_reduction"
        if representative is None:
            representative = {"id": row["id"], "program": deepcopy(reduced if self.policy == "certified" else row["program"])}
            self.entries.append(representative)
        self.aliases[row["id"]] = representative
        self.canonical.setdefault(key(reduced), representative)
        if is_seed and representative["id"] not in self._root_ids:
            self.roots.append(representative)
            self._root_ids.add(representative["id"])
        return {"representative": representative["id"], "admitted": representative["id"] == row["id"],
                "reason": reason, "active_entries": len(self.entries), "seed_entries": len(self.roots)}

    def choose(self, rng, *, seed_only=False):
        return rng.choice(self.roots if seed_only else self.entries)
