"""Certified minimal models of chain complexes, and learning which reduction procedure reaches them cheaply.

Over a field every finite chain complex is homotopy equivalent to its homology
with zero differential. A sequence of reduction moves (each a certified chain
homotopy equivalence) that eliminates every nonzero boundary coefficient reaches
that minimal model; every complete sequence ends at the same size, so the moves
needed are the same and what differs is the cost of the fill-in they create.

A task asks for the certified minimal model: zero differential, Betti numbers and
representative cycles lifted to the original complex. The cost is counted in two
declared parts: algebraic work (entry updates of eliminations, reindexing, move
records, lifting, copying the complex) and queue bookkeeping (priority-queue pushes
and pops). They are reported separately; the preregistered primary metric is the
algebraic work. Procedures are orderings of the admissible moves:

  * fixed orderings (min-fill is the standard default);
  * explore: successive halving over all orderings on the task itself, comparing
    cost at equal numbers of moves, every probe charged;
  * acquired: an ordering chosen from cheap complex features by a rule learned on
    training complexes that the system reduced itself.
"""
from __future__ import annotations

import heapq
import math

from math_os_prototype import algebraic_structures as alg
from math_os_prototype.algebraic_reduction_search import MutableComplex, _estimate


def _fill(c, s, t):
    return _estimate(c, s, t)


ORDERINGS = {
    "min-fill": lambda c, s, t: (_fill(c, s, t), c.degree[s]),
    "top-first": lambda c, s, t: (-c.degree[s], _fill(c, s, t)),
    "bottom-first": lambda c, s, t: (c.degree[s], _fill(c, s, t)),
    "short-boundary": lambda c, s, t: (len(c.boundary[s]), len(c.coboundary[t])),
    "few-cofaces": lambda c, s, t: (len(c.coboundary[t]), len(c.boundary[s])),
}
DEFAULT_ORDERING = "min-fill"


class Reducer:
    """Resumable reduction of one complex under one ordering, with its own operation counter."""

    def __init__(self, chain_complex, ordering):
        self.complex = MutableComplex.from_chain_complex(chain_complex)
        self.key = ORDERINGS[ordering]
        self.ordering = ordering
        self.counter = alg.OperationCounter()
        self.counter.charge("copy", chain_complex.size()+self.complex.nonzeros())
        self.heap = []
        self.moves = 0
        self.last_key = None
        for tau in sorted(self.complex.coboundary):
            self._push(tau)

    def _push(self, tau):
        cofaces = self.complex.coboundary.get(tau)
        if not cofaces:
            return
        for sigma in cofaces:
            heapq.heappush(self.heap, (self.key(self.complex, sigma, tau), sigma, tau))
            self.counter.charge("selection")

    def finished(self):
        return not self.heap

    def step(self, moves, budget=None):
        """Make up to `moves` moves; returns the number made."""
        made = 0
        c = self.complex
        while self.heap and made < moves:
            key, sigma, tau = heapq.heappop(self.heap)
            self.counter.charge("selection")
            if sigma not in c.boundary or tau not in c.boundary[sigma]:
                continue
            current = self.key(c, sigma, tau)
            if current != key:
                heapq.heappush(self.heap, (current, sigma, tau))
                self.counter.charge("selection")
                continue
            self.last_key = current
            faces = [f for f in c.boundary[sigma] if f != tau]
            cofaces = [y for y in c.coboundary[tau] if y != sigma]
            tau_faces = list(c.boundary[tau])
            sigma_cofaces = list(c.coboundary[sigma])
            c.reduce(sigma, tau, self.counter)
            made += 1
            self.moves += 1
            touched = set(faces) | set(tau_faces)
            for y in cofaces+sigma_cofaces:
                touched.update(c.boundary.get(y, ()))
            for face in sorted(touched):
                self._push(face)
            alg.check_budget(self.counter, budget)
        return made


def _answer(reducer, top):
    """Minimal model answer: Betti numbers and lifted representatives; the remaining differential is reported."""
    c = reducer.complex
    remaining = sum(len(c.boundary[cell]) for cell in c.boundary)
    betti = [len(c.cells[q]) if q < len(c.cells) else 0 for q in range(top+1)]
    representatives = {q: [c.lift({cell: 1}, q, reducer.counter) for cell in sorted(c.cells[q])]
                       for q in range(top+1) if q < len(c.cells)}
    return {"betti": betti, "representatives": representatives, "model_size": c.size(),
            "model_dims": [len(cells) for cells in c.cells], "remaining_differential_entries": remaining}


def minimal_model(chain_complex, procedure, *, budget=None, rule=None, top=1, first_quota=16):
    """Run a procedure to the certified minimal model; every operation, including exploration, is counted."""
    record = {"procedure": procedure, "original_size": chain_complex.size()}
    total = alg.OperationCounter()
    try:
        if procedure in ORDERINGS:
            chosen = procedure
            reducer = Reducer(chain_complex, chosen)
            try:
                reducer.step(math.inf, budget)
            finally:
                _add(total, reducer.counter)
        elif procedure == "acquired":
            features = complex_features(chain_complex)
            total.charge("features", len(features))
            chosen = rule(features)
            reducer = Reducer(chain_complex, chosen)
            try:
                reducer.step(math.inf, budget)
            finally:
                _add(total, reducer.counter)
        elif procedure == "explore":
            chosen, reducer = _successive_halving(chain_complex, total, budget, first_quota, record)
        else:
            raise ValueError("unknown procedure")
        record["chosen"] = chosen
        before = reducer.counter["total"]
        answer = _answer(reducer, top)
        lift_operations = reducer.counter["total"]-before
        total.charge("lift", lift_operations)
        record.update(answer, solved=answer["remaining_differential_entries"] == 0, moves=reducer.moves)
        if not record["solved"]:
            record["failure"] = "nonzero differential remained"
    except alg.BudgetExceeded:
        record.update(solved=False, failure="operation cap")
    breakdown = dict(total)
    queue = breakdown.get("selection", 0)
    record["operations"] = total["total"] if record["solved"] else None
    record["algebraic_operations"] = (total["total"]-queue) if record["solved"] else None
    record["queue_operations"] = queue if record["solved"] else None
    return record


def _add(total, counter):
    for kind, value in counter.items():
        total[kind] += value


def _successive_halving(chain_complex, total, budget, quota, record):
    """Race all orderings at equal numbers of moves; halve the field each round by cost so far."""
    racers = {name: Reducer(chain_complex, name) for name in ORDERINGS}
    rounds, discarded = [], alg.OperationCounter()
    def refresh():
        total.clear()
        _add(total, discarded)
        for r in racers.values():
            _add(total, r.counter)
    while True:
        for reducer in racers.values():
            reducer.step(quota, None)
            refresh()
            alg.check_budget(total, budget)
        finished = [r for r in racers.values() if r.finished()]
        rounds.append({"quota": quota, "costs": {n: r.counter["total"] for n, r in racers.items()}})
        if finished:
            best = min(finished, key=lambda r: (r.counter["total"], r.ordering))
            record["exploration"] = {"rounds": rounds, "discarded_operations": discarded["total"]}
            return best.ordering, best
        if len(racers) > 1:
            ranked = sorted(racers.values(), key=lambda r: (r.counter["total"], r.ordering))
            keep = ranked[:max(1, len(ranked)//2)]
            for r in ranked[len(keep):]:
                _add(discarded, r.counter)
            racers = {r.ordering: r for r in keep}
            refresh()
        quota *= 2


def complex_features(chain_complex):
    """Features from the cell counts only (a constant amount of work, charged by the caller)."""
    dims = list(chain_complex.dims)+[0, 0, 0]
    return {"size": chain_complex.size(), "edges_per_vertex": dims[1]/max(1, dims[0]),
            "triangles_per_edge": dims[2]/max(1, dims[1])}


def learn_ordering_rule(training):
    """Learn a one-split rule from training records {features, costs: {ordering: operations}}.

    For every feature and threshold, each side takes the ordering with the lowest total
    training cost; the split with the lowest total cost is kept. Ties prefer the default.
    """
    items = [t for t in training if all(t["costs"].get(o) is not None for o in ORDERINGS)]
    if not items:
        def default(_):
            return DEFAULT_ORDERING
        default.description = {"feature": None, "reason": "no complete training items"}
        return default
    def best_on(group):
        return min(ORDERINGS, key=lambda o: (sum(t["costs"][o] for t in group), o != DEFAULT_ORDERING, o))
    overall = best_on(items)
    best = (sum(t["costs"][overall] for t in items), None, None, overall, overall)
    for feature in sorted(items[0]["features"]):
        for threshold in sorted({t["features"][feature] for t in items}):
            below = [t for t in items if t["features"][feature] <= threshold]
            above = [t for t in items if t["features"][feature] > threshold]
            if not above:
                continue
            left, right = best_on(below), best_on(above)
            cost = sum(t["costs"][left] for t in below)+sum(t["costs"][right] for t in above)
            if cost < best[0]:
                best = (cost, feature, threshold, left, right)
    cost, feature, threshold, left, right = best
    def rule(features):
        if feature is None:
            return left
        return left if features[feature] <= threshold else right
    rule.description = {"feature": feature, "threshold": threshold, "at_or_below": left, "above": right,
                        "training_cost": cost, "training_items": len(items),
                        "default_training_cost": sum(t["costs"][DEFAULT_ORDERING] for t in items)}
    return rule
