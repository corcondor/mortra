"""Autonomous search over certified structure-preserving reductions of chain complexes.

A reduction move (algebraic_structures.reduction_move) is a chain homotopy
equivalence; a sequence of moves composes to one. This module applies moves on a
mutable complex (charging every entry update to one OperationCounter), lifts
homology representatives back through the recorded moves, and chooses which moves
to make with strategies of increasing autonomy:

  * direct       no reduction; homology by column reduction of the full complex;
  * collapse     only moves whose tau has a single coface (no fill-in);
  * markowitz    any invertible coefficient, smallest estimated fill-in first;
  * explore      probe every strategy for a bounded number of moves, measure the
                 size removed per operation, continue with the best (probes charged);
  * acquired     the strategy chosen by a rule learned from training complexes.

Answers are Betti numbers with representative cycles in the original complex. The
evaluator checks them independently; this module never reads the answer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

from math_os_prototype import algebraic_structures as alg

# A strategy is (name, fill limit): collapse = no fill-in allowed beyond free faces;
# markowitz-L = collapses, then any invertible pair whose estimated fill-in is <= L.
STRATEGIES = {"collapse": 0, "markowitz-2": 2, "markowitz-8": 8, "markowitz-32": 32, "markowitz-inf": None}


@dataclass
class MutableComplex:
    """Chain complex with named basis elements, boundary columns and coboundary rows."""
    cells: list                        # cells[q] = set of ids
    boundary: dict                     # id -> {face id: Fraction}
    coboundary: dict                   # id -> {coface id: Fraction}
    degree: dict                       # id -> q
    moves: list = field(default_factory=list)

    @staticmethod
    def from_chain_complex(complex_):
        cells, boundary, coboundary, degree = [], {}, {}, {}
        for q, count in enumerate(complex_.dims):
            ids = {(q, i) for i in range(count)}
            cells.append(ids)
            for cell in ids:
                degree[cell] = q
                boundary[cell] = {}
                coboundary[cell] = {}
        for q in range(1, len(complex_.dims)):
            for j, column in enumerate(complex_.d(q).columns):
                for i, value in column.items():
                    boundary[(q, j)][(q-1, i)] = value
                    coboundary[(q-1, i)][(q, j)] = value
        return MutableComplex(cells, boundary, coboundary, degree)

    def size(self):
        return sum(len(c) for c in self.cells)

    def nonzeros(self):
        return sum(len(b) for b in self.boundary.values())

    def reduce(self, sigma, tau, counter):
        """Eliminate the pair (sigma, tau) with a = <d sigma, tau> != 0 (reduction lemma)."""
        a = self.boundary[sigma][tau]
        d_sigma = dict(self.boundary[sigma])
        cofaces = {y: c for y, c in self.coboundary[tau].items() if y != sigma}
        for y, coefficient in cofaces.items():
            scale = coefficient/a
            column = self.boundary[y]
            for face, value in d_sigma.items():
                updated = column.get(face, Fraction(0))-scale*value
                if updated:
                    column[face] = updated
                    self.coboundary[face][y] = updated
                else:
                    column.pop(face, None)
                    self.coboundary[face].pop(y, None)
                counter.charge("reduction")
        self.moves.append({"sigma": sigma, "tau": tau, "a": a, "cofaces_of_tau": cofaces})
        counter.charge("record", len(cofaces)+1)
        for face in d_sigma:
            self.coboundary[face].pop(sigma, None)
            counter.charge("reindex")
        for coface in list(self.coboundary[sigma]):
            self.boundary[coface].pop(sigma, None)
            counter.charge("reindex")
        for face in list(self.boundary[tau]):
            self.coboundary[face].pop(tau, None)
            counter.charge("reindex")
        for cell in (sigma, tau):
            self.cells[self.degree[cell]].discard(cell)
            del self.boundary[cell]
            del self.coboundary[cell]

    def chain_complex(self):
        """Freeze into an algebraic_structures.ChainComplex with an index of the surviving cells."""
        order = [sorted(c) for c in self.cells]
        index = [{cell: i for i, cell in enumerate(cells)} for cells in order]
        boundary = {}
        for q in range(1, len(order)):
            boundary[q] = alg.SparseMatrix(len(order[q-1]), [
                {index[q-1][face]: v for face, v in self.boundary[cell].items()} for cell in order[q]])
        return alg.ChainComplex([len(c) for c in order], boundary, {q: order[q] for q in range(len(order))}), order

    def lift(self, vector, q, counter=None):
        """Apply G of every recorded move in reverse to a degree-q chain of the reduced complex.

        G is the inclusion in degree deg(tau) and adds -(<d y, tau>/a) sigma in degree
        deg(sigma), with <d y, tau> recorded before that move.
        """
        z = dict(vector)
        for move in reversed(self.moves):
            if self.degree[move["sigma"]] != q:
                continue
            coefficient = sum(z.get(y, Fraction(0))*c for y, c in move["cofaces_of_tau"].items())
            if counter is not None:
                counter.charge("lift", len(move["cofaces_of_tau"]))
            if coefficient:
                z[move["sigma"]] = z.get(move["sigma"], Fraction(0))-coefficient/move["a"]
        return {k: v for k, v in z.items() if v != 0}


def _estimate(complex_, sigma, tau):
    """Fill-in estimate of eliminating (sigma, tau): (cofaces(tau) - 1) * (faces(sigma) - 1)."""
    return (len(complex_.coboundary[tau])-1)*(len(complex_.boundary[sigma])-1)


def reduce_with(complex_, strategy, counter, budget=None, max_moves=None, fill_limit=None):
    """Greedy reduction driven by a priority queue with lazy invalidation.

    strategy "collapse" admits only pairs whose tau has a single coface (no fill-in);
    any other strategy admits every invertible coefficient in order of estimated
    fill-in, stopping when the smallest valid estimate exceeds fill_limit. Every
    queue push and pop is charged as one selection operation.
    """
    import heapq
    heap = []

    def push(tau):
        cofaces = complex_.coboundary.get(tau)
        if not cofaces or (strategy == "collapse" and len(cofaces) != 1):
            return
        for sigma in cofaces:
            heapq.heappush(heap, (_estimate(complex_, sigma, tau), -complex_.degree[sigma], sigma, tau))
            counter.charge("selection")

    for tau in sorted(complex_.coboundary):
        push(tau)
    alg.check_budget(counter, budget)
    made = 0
    while heap and (max_moves is None or made < max_moves):
        estimate, _, sigma, tau = heapq.heappop(heap)
        counter.charge("selection")
        if sigma not in complex_.boundary or tau not in complex_.boundary[sigma]:
            continue
        if strategy == "collapse" and len(complex_.coboundary[tau]) != 1:
            continue
        current = _estimate(complex_, sigma, tau)
        if current != estimate:
            heapq.heappush(heap, (current, -complex_.degree[sigma], sigma, tau))
            counter.charge("selection")
            continue
        if fill_limit is not None and current > fill_limit:
            break
        faces = [f for f in complex_.boundary[sigma] if f != tau]
        cofaces = [y for y in complex_.coboundary[tau] if y != sigma]
        tau_faces = list(complex_.boundary[tau])
        sigma_cofaces = list(complex_.coboundary[sigma])
        complex_.reduce(sigma, tau, counter)
        made += 1
        # Every pair whose key may have changed: faces of sigma and of tau, and the
        # faces of every column that was updated (cofaces of tau) or shortened (cofaces of sigma).
        touched = set(faces) | set(tau_faces)
        for y in cofaces+sigma_cofaces:
            touched.update(complex_.boundary.get(y, ()))
        for face in sorted(touched):
            push(face)
        alg.check_budget(counter, budget)
    return made


def run_strategy(chain_complex, name, counter, budget=None):
    """Collapse, then (for markowitz-L) eliminate with fill limit L, then collapse again."""
    complex_ = MutableComplex.from_chain_complex(chain_complex)
    reduce_with(complex_, "collapse", counter, budget)
    if name != "collapse":
        reduce_with(complex_, "markowitz", counter, budget, fill_limit=STRATEGIES[name])
        reduce_with(complex_, "collapse", counter, budget)
    return complex_


def solve_homology(chain_complex, strategy="direct", budget=None, acquired_rule=None, top=None):
    """Betti numbers b_0..b_top and representatives in the original complex within an operation budget.

    explore: every strategy is run to completion (or to its budget share) on its own
    copy, all operations charged; the smallest certified equivalent complex is kept.
    """
    top = len(chain_complex.dims)-2 if top is None else top
    counter = alg.OperationCounter()
    record = {"strategy": strategy, "original_size": chain_complex.size(), "chosen": None}
    try:
        if strategy == "direct":
            answer = _homology_of(chain_complex, None, counter, budget, top)
            record.update(reduced_size=chain_complex.size())
        else:
            if strategy in STRATEGIES:
                chosen, complex_ = strategy, run_strategy(chain_complex, strategy, counter, budget)
            elif strategy == "acquired":
                chosen = acquired_rule(features(chain_complex))
                complex_ = run_strategy(chain_complex, chosen, counter, budget)
            elif strategy == "explore":
                chosen, complex_ = _explore(chain_complex, counter, budget, record)
            else:
                raise ValueError("unknown strategy")
            record["chosen"] = chosen
            record["reduced_size"] = complex_.size()
            record["moves"] = len(complex_.moves)
            answer = _homology_of(None, complex_, counter, budget, top)
        record.update(solved=True, betti=answer["betti"], representatives=answer["representatives"])
    except alg.BudgetExceeded:
        record.update(solved=False, betti=None, representatives=None)
    record["operations"] = dict(counter)
    return record


def _explore(chain_complex, counter, budget, record):
    """Try every strategy with an equal share of the remaining budget; keep the smallest reduced complex."""
    outcomes, best = {}, None
    share = None if budget is None else budget//(len(STRATEGIES)+1)
    for name in STRATEGIES:
        local = alg.OperationCounter()
        try:
            complex_ = run_strategy(chain_complex, name, local, share)
        except alg.BudgetExceeded:
            complex_ = None
        counter.update(local)
        alg.check_budget(counter, budget)
        outcomes[name] = {"reduced_size": None if complex_ is None else complex_.size(),
                          "operations": local["total"]}
        if complex_ is not None and (best is None or (complex_.size(), local["total"]) < best[0]):
            best = ((complex_.size(), local["total"]), name, complex_)
    record["exploration"] = outcomes
    if best is None:
        raise alg.BudgetExceeded("no strategy finished within its share")
    return best[1], best[2]


def _homology_of(chain_complex, mutable, counter, budget, top):
    if mutable is not None:
        chain_complex, order = mutable.chain_complex()
    betti, representatives = [], {}
    for q in range(top+1):
        result = alg.homology(chain_complex, q, counter, budget)
        betti.append(result["betti"])
        if mutable is None:
            representatives[q] = [{(q, i): v for i, v in r.items()} for r in result["representatives"]]
        else:
            representatives[q] = [mutable.lift({order[q][i]: v for i, v in r.items()}, q)
                                  for r in result["representatives"]]
    return {"betti": betti, "representatives": representatives}


def features(chain_complex):
    dims = chain_complex.dims+[0, 0, 0]
    nonzeros = sum(chain_complex.d(q).nonzeros() for q in range(1, len(chain_complex.dims)))
    return {"size": chain_complex.size(), "edges_per_vertex": dims[1]/max(1, dims[0]),
            "triangles_per_edge": dims[2]/max(1, dims[1]), "density": nonzeros/max(1, chain_complex.size())}


def learn_rule(training):
    """Learn a strategy selector from training records {features, costs: {strategy: operations or None}}.

    For every feature and threshold, pick for each side the strategy with the lowest
    total training cost on that side (unsolved counts as the training budget); keep
    the split with the lowest total cost. Deterministic; reads only training records.
    """
    items = [t for t in training if any(c is not None for c in t["costs"].values())]
    penalty = max((c for t in items for c in t["costs"].values() if c is not None), default=1)*2
    def cost(item, name):
        value = item["costs"].get(name)
        return penalty if value is None else value
    def best_on(group):
        return min(STRATEGIES, key=lambda name: (sum(cost(t, name) for t in group), name))
    overall = best_on(items)
    best = (sum(cost(t, overall) for t in items), "size", float("inf"), overall, overall)
    for feature in ("size", "edges_per_vertex", "triangles_per_edge", "density"):
        for threshold in sorted({t["features"][feature] for t in items}):
            below = [t for t in items if t["features"][feature] <= threshold]
            above = [t for t in items if t["features"][feature] > threshold]
            left, right = best_on(below), (best_on(above) if above else overall)
            total = sum(cost(t, left) for t in below)+sum(cost(t, right) for t in above)
            if total < best[0]:
                best = (total, feature, threshold, left, right)
    total, feature, threshold, left, right = best
    def rule(f):
        return left if f[feature] <= threshold else right
    rule.description = {"feature": feature, "threshold": threshold, "at_or_below": left, "above": right,
                        "training_cost": total, "training_items": len(items)}
    return rule
