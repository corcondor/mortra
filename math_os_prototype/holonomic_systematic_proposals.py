"""Enumerate every declared one-step composition over the growing series pool.

Each new representative supplies unary streams and binary pairs whose latest
operand is that representative. Ordered pairs occur exactly once. The generic
agenda prevents later admissions from starving any finite stream position.
The pool, construction bounds, and downstream filters still limit reachability.
"""
from copy import deepcopy
from itertools import product

from math_os_prototype.holonomic_route_discovery import key
from math_os_prototype.research_indexed_agenda import ResearchIndexedAgenda


def pullback_maps(degree):
    if type(degree) is not int or not 1 <= degree <= 3:
        raise ValueError("pullback degree must be between one and three")
    if degree == 1:
        return [([0, a], [1, b]) for a, b in product((-1, 1, 2), (-1, 0, 1))]
    return [([0, *middle, last], [1, *denominator])
            for middle in product((-2, -1, 0, 1, 2), repeat=degree-1)
            for last in (-2, -1, 1, 2)
            for denominator in product((-1, 0, 1), repeat=degree)]


class SystematicSeriesProposals:
    def __init__(self, *, every=1, with_add=False, pullback_degree=1, compound_operands=False):
        if type(every) is not int or every < 1:
            raise ValueError("systematic proposal interval must be positive")
        self.every = every
        self.round = 0
        self.with_add = with_add
        self.compound = compound_operands
        self.maps = pullback_maps(pullback_degree)
        self.agenda = ResearchIndexedAgenda()
        self.entries = []
        self.roots = None
        self.descriptors = []

    def _pairs(self, index):
        right_indices = range(index+1) if self.compound else (i for i in self.roots if i <= index)
        pairs = [(index, i) for i in right_indices]
        if self.compound or index in self.roots:
            pairs.extend((i, index) for i in range(index))
        return pairs

    def _sync(self, pool):
        current = [(entry["id"], key(entry["program"])) for entry in pool.entries]
        if current[:len(self.entries)] != self.entries:
            raise ValueError("systematic enumeration requires an append-only representative pool")
        root_ids = {entry["id"] for entry in pool.roots}
        roots = tuple(i for i, entry in enumerate(pool.entries) if entry["id"] in root_ids)
        if self.roots is not None and roots != self.roots:
            raise ValueError("seed membership changed after systematic enumeration began")
        self.roots = roots
        for index in range(len(self.entries), len(current)):
            for op, length in [("diff", 1), ("mul", len(self._pairs(index))),
                               *([( "add", len(self._pairs(index)))] if self.with_add else []),
                               ("pullback", len(self.maps))]:
                if length:
                    self.agenda.admit(f"{index}:{op}", length)
                    self.descriptors.append((index, op))
        self.entries = current

    def offer(self, pool):
        self._sync(pool)
        round_index = self.round
        self.round += 1
        before = self.agenda.digest()
        item = self.agenda.pop() if round_index % self.every == 0 else None
        receipt = {"round": round_index, "before_sha256": before,
                   "after_sha256": self.agenda.digest(), "item": item,
                   "scheduled": round_index % self.every == 0}
        if item is None:
            return None, receipt
        index, op = self.descriptors[item["stream_id"]]
        entry = pool.entries[index]
        parents = [entry["id"]]
        if op in {"mul", "add"}:
            left, right = (pool.entries[i] for i in self._pairs(index)[item["offset"]])
            program = {"op": op, "left": left["program"], "right": right["program"]}
            parents = [left["id"], right["id"]]
        elif op == "diff":
            program = {"op": op, "child": entry["program"]}
        else:
            numerator, denominator = self.maps[item["offset"]]
            program = {"op": op, "child": entry["program"],
                       "numerator": numerator, "denominator": denominator}
        return deepcopy({"program": program, "parents": parents,
                         "proposal_origin": "systematic"}), receipt

    def snapshot(self):
        return {"schema": "mortra.systematic-series-proposals.v1", "every": self.every,
                "round": self.round, "agenda": self.agenda.snapshot(),
                "representatives": [entry[0] for entry in self.entries]}
