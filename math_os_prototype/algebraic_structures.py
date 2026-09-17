"""Exact algebraic structures with certificates: from polynomials to modules, complexes and homology.

Design: docs/research/ALGEBRAIC-STRUCTURES-20260917.md. Every object is exact
(rational coefficients, python Fractions), every derived object carries the
identities that justify it, and every arithmetic update on a matrix entry is
counted by an OperationCounter so that search strategies can be compared at an
equal, deterministic cost.

Contents
  * sparse matrices over QQ; column reduction with the column-operation record;
    kernel, image and cokernel with certificates;
  * module maps between finitely presented vector spaces / modules coker(A) ->
    coker(B) with the well-definedness certificate F A = B S;
  * chain complexes (d d = 0), homology with representative cycles, chain maps,
    induced maps on homology, chain homotopy equivalences and their composition;
  * simplicial complexes and their boundary complexes;
  * the elementary reduction of a complex along an invertible boundary coefficient
    (a chain homotopy equivalence, proposed by formula and verified exactly);
  * persistence of a filtered complex over QQ[t] (column reduction) and the rank
    invariant that certifies a barcode;
  * dual numbers k[e]/(e^2), Jacobians by first-order evaluation, tangent spaces
    T_pX = ker J(p);
  * Plucker coordinates of 2-planes in 4-space.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from fractions import Fraction
from itertools import combinations


# ---------------------------------------------------------------------------
# Counting
# ---------------------------------------------------------------------------

class OperationCounter(Counter):
    """Deterministic cost: every entry update of an elimination is one operation."""

    def charge(self, kind, amount=1):
        self[kind] += amount
        self["total"] += amount


class BudgetExceeded(RuntimeError):
    pass


def check_budget(counter, budget):
    if budget is not None and counter["total"] > budget:
        raise BudgetExceeded(f"operation budget {budget} exceeded")


# ---------------------------------------------------------------------------
# Sparse matrices over QQ (columns as dicts row -> Fraction)
# ---------------------------------------------------------------------------

@dataclass
class SparseMatrix:
    nrows: int
    columns: list = field(default_factory=list)

    @property
    def ncols(self):
        return len(self.columns)

    @staticmethod
    def zero(nrows, ncols):
        return SparseMatrix(nrows, [dict() for _ in range(ncols)])

    @staticmethod
    def identity(n):
        return SparseMatrix(n, [{i: Fraction(1)} for i in range(n)])

    @staticmethod
    def from_rows(rows, ncols=None):
        ncols = ncols if ncols is not None else (len(rows[0]) if rows else 0)
        matrix = SparseMatrix.zero(len(rows), ncols)
        for i, row in enumerate(rows):
            for j, value in enumerate(row):
                if value:
                    matrix.columns[j][i] = Fraction(value)
        return matrix

    def to_rows(self):
        rows = [[Fraction(0)]*self.ncols for _ in range(self.nrows)]
        for j, column in enumerate(self.columns):
            for i, value in column.items():
                rows[i][j] = value
        return rows

    def copy(self):
        return SparseMatrix(self.nrows, [dict(c) for c in self.columns])

    def nonzeros(self):
        return sum(len(c) for c in self.columns)

    def apply(self, vector, counter=None):
        """Matrix times a sparse vector {column index: value}."""
        result = {}
        for j, coefficient in vector.items():
            for i, value in self.columns[j].items():
                result[i] = result.get(i, Fraction(0))+coefficient*value
                if counter is not None:
                    counter.charge("multiply")
        return {i: v for i, v in result.items() if v != 0}

    def compose(self, other, counter=None):
        """self @ other."""
        if self.ncols != other.nrows:
            raise ValueError("dimension mismatch in composition")
        return SparseMatrix(self.nrows, [self.apply(c, counter) for c in other.columns])

    def add(self, other, scale=Fraction(1)):
        if (self.nrows, self.ncols) != (other.nrows, other.ncols):
            raise ValueError("dimension mismatch in addition")
        columns = []
        for a, b in zip(self.columns, other.columns, strict=True):
            column = dict(a)
            for i, value in b.items():
                column[i] = column.get(i, Fraction(0))+scale*value
            columns.append({i: v for i, v in column.items() if v != 0})
        return SparseMatrix(self.nrows, columns)

    def is_zero(self):
        return all(not c for c in self.columns)

    def equals(self, other):
        return (self.nrows, self.ncols) == (other.nrows, other.ncols) and self.add(other, Fraction(-1)).is_zero()


def _low(column):
    return max(column) if column else -1


def column_reduce(matrix, counter=None, budget=None, record=True):
    """Standard column reduction (left-to-right, lowest-row pivots).

    Returns (reduced columns, pivot map low -> column, V) where matrix @ V = reduced
    when record is True. Each entry update is one counted operation.
    """
    counter = counter if counter is not None else OperationCounter()
    reduced = [dict(c) for c in matrix.columns]
    transform = [{j: Fraction(1)} for j in range(matrix.ncols)] if record else None
    pivots = {}
    for j in range(matrix.ncols):
        column = reduced[j]
        low = _low(column)
        while low >= 0 and low in pivots:
            k = pivots[low]
            factor = column[low]/reduced[k][low]
            for i, value in reduced[k].items():
                updated = column.get(i, Fraction(0))-factor*value
                if updated:
                    column[i] = updated
                else:
                    column.pop(i, None)
                counter.charge("elimination")
            if record:
                for i, value in transform[k].items():
                    updated = transform[j].get(i, Fraction(0))-factor*value
                    if updated:
                        transform[j][i] = updated
                    else:
                        transform[j].pop(i, None)
                    counter.charge("record")
            check_budget(counter, budget)
            low = _low(column)
        if low >= 0:
            pivots[low] = j
    return reduced, pivots, (SparseMatrix(matrix.ncols, transform) if record else None)


def rank(matrix, counter=None, budget=None):
    _, pivots, _ = column_reduce(matrix, counter, budget, record=False)
    return len(pivots)


def kernel(matrix, counter=None, budget=None):
    """Basis of ker(matrix) as columns of a SparseMatrix, with its certificate."""
    reduced, pivots, transform = column_reduce(matrix, counter, budget)
    basis = SparseMatrix(matrix.ncols, [transform.columns[j] for j in range(matrix.ncols) if not reduced[j]])
    return basis


def image(matrix, counter=None, budget=None):
    reduced, pivots, _ = column_reduce(matrix, counter, budget, record=False)
    return SparseMatrix(matrix.nrows, [reduced[j] for j in sorted(pivots.values())])


def certify_kernel(matrix, basis):
    """A @ K = 0, K has full column rank and rank(A) + cols(K) = ncols(A)."""
    return (matrix.compose(basis).is_zero() and rank(basis) == basis.ncols
            and rank(matrix)+basis.ncols == matrix.ncols)


def cokernel_presentation(matrix):
    """coker(A: QQ^a -> QQ^m): a complement basis of im A given by non-pivot rows (unit vectors)."""
    reduced, pivots, _ = column_reduce(matrix, record=False)
    free_rows = [i for i in range(matrix.nrows) if i not in pivots]
    return {"dimension": len(free_rows), "complement_rows": free_rows,
            "certificate": "rows not occupied by a lowest-row pivot of the reduced image form a complement"}


# ---------------------------------------------------------------------------
# Module maps between presentations: coker(A) -> coker(B) given by F, with F A = B S
# ---------------------------------------------------------------------------

def certify_presentation_map(F, A, B, S):
    """F descends to coker(A) -> coker(B) when F A = B S (then F(im A) lies in im B)."""
    return F.compose(A).equals(B.compose(S))


def solve_presentation_map(F, A, B, counter=None):
    """Find S with F A = B S column by column (exact linear algebra over QQ), or None."""
    target = F.compose(A, counter)
    columns = []
    for column in target.columns:
        solution = solve(B, column, counter)
        if solution is None:
            return None
        columns.append(solution)
    return SparseMatrix(B.ncols, columns)


def solve(matrix, vector, counter=None):
    """A x = b over QQ, a particular solution or None."""
    augmented = matrix.copy()
    augmented.columns.append(dict(vector))
    reduced, pivots, transform = column_reduce(augmented, counter)
    last = matrix.ncols
    if reduced[last]:
        return None
    # transform.columns[last] expresses 0 = A (V_last) with V_last[last] = 1: x = -V_last restricted.
    v = transform.columns[last]
    return {i: -value for i, value in v.items() if i != last}


# ---------------------------------------------------------------------------
# Chain complexes over QQ
# ---------------------------------------------------------------------------

@dataclass
class ChainComplex:
    """dims[q] = dim C_q; boundary[q]: C_q -> C_{q-1} for q >= 1 (boundary[0] is zero)."""
    dims: list
    boundary: dict
    labels: dict = field(default_factory=dict)

    def d(self, q):
        if q <= 0 or q >= len(self.dims):
            rows = self.dims[q-1] if 0 <= q-1 < len(self.dims) else 0
            cols = self.dims[q] if 0 <= q < len(self.dims) else 0
            return SparseMatrix.zero(rows, cols)
        return self.boundary[q]

    def size(self):
        return sum(self.dims)

    def certify_differential(self, counter=None):
        return all(self.d(q).compose(self.d(q+1), counter).is_zero() for q in range(1, len(self.dims)-1))


def homology(complex_, q, counter=None, budget=None):
    """H_q = ker d_q / im d_{q+1}: Betti number and representative cycles.

    Representatives are kernel vectors that raise the rank when appended to the
    reduced image of d_{q+1}; their classes form a basis of H_q.
    """
    counter = counter if counter is not None else OperationCounter()
    cycles = kernel(complex_.d(q), counter, budget)
    boundaries = image(complex_.d(q+1), counter, budget)
    combined = SparseMatrix(complex_.dims[q], boundaries.columns+cycles.columns)
    reduced, pivots, _ = column_reduce(combined, counter, budget, record=False)
    offset = boundaries.ncols
    representatives = [cycles.columns[j-offset] for j in sorted(pivots.values()) if j >= offset]
    return {"betti": len(representatives), "representatives": representatives,
            "cycles": cycles.ncols, "boundary_rank": boundaries.ncols}


def betti_numbers(complex_, counter=None, budget=None):
    counter = counter if counter is not None else OperationCounter()
    ranks = [0]+[rank(complex_.d(q), counter, budget) for q in range(1, len(complex_.dims))]+[0]
    return [complex_.dims[q]-ranks[q]-ranks[q+1] for q in range(len(complex_.dims))]


@dataclass
class ChainMap:
    source: ChainComplex
    target: ChainComplex
    maps: dict                       # q -> SparseMatrix C_q -> D_q

    def at(self, q):
        if q in self.maps:
            return self.maps[q]
        return SparseMatrix.zero(self.target.dims[q] if q < len(self.target.dims) else 0,
                                 self.source.dims[q] if q < len(self.source.dims) else 0)

    def certify(self, counter=None):
        """d^D F = F d^C in every degree."""
        top = max(len(self.source.dims), len(self.target.dims))
        return all(self.target.d(q).compose(self.at(q), counter).equals(self.at(q-1).compose(self.source.d(q), counter))
                   for q in range(1, top))

    def compose(self, first):
        """self o first."""
        return ChainMap(first.source, self.target,
                        {q: self.at(q).compose(first.at(q)) for q in set(self.maps) | set(first.maps)})


def induced_map_on_homology(chain_map, q):
    """Matrix of H_q(F) in the representative bases of source and target."""
    source = homology(chain_map.source, q)
    target = homology(chain_map.target, q)
    boundaries = image(chain_map.target.d(q+1))
    reps = target["representatives"]
    columns = []
    for z in source["representatives"]:
        image_vector = chain_map.at(q).apply(z)
        system = SparseMatrix(chain_map.target.dims[q], reps+boundaries.columns)
        solution = solve(system, image_vector)
        if solution is None:
            raise ValueError("image of a cycle is not a combination of cycles and boundaries")
        columns.append({i: v for i, v in solution.items() if i < len(reps)})
    return SparseMatrix(len(reps), columns)


def certify_homotopy_equivalence(C, D, F, G, h_C, h_D):
    """F: C->D, G: D->C chain maps with G F - id = d h + h d on C and F G - id = d h' + h' d on D.

    h_C[q]: C_q -> C_{q+1}, h_D[q]: D_q -> D_{q+1} (missing entries are zero).
    """
    def same(X, Y):
        return X is Y or (X.dims == Y.dims and all(X.d(q).equals(Y.d(q)) for q in range(1, len(X.dims))))
    try:
        if not (same(F.source, C) and same(F.target, D) and same(G.source, D) and same(G.target, C)):
            return False
        if not (C.certify_differential() and D.certify_differential() and F.certify() and G.certify()):
            return False
    except ValueError:
        return False
    def zero(rows, cols):
        return SparseMatrix.zero(rows, cols)
    for X, first, second, h in ((C, F, G, h_C), (D, G, F, h_D)):
        for q in range(len(X.dims)):
            composite = second.at(q).compose(first.at(q))
            identity = SparseMatrix.identity(X.dims[q])
            left = composite.add(identity, Fraction(-1))
            up = h.get(q, zero(X.dims[q+1] if q+1 < len(X.dims) else 0, X.dims[q]))
            down = h.get(q-1, zero(X.dims[q], X.dims[q-1] if q >= 1 else 0))
            right = zero(X.dims[q], X.dims[q])
            if q+1 < len(X.dims):
                right = right.add(X.d(q+1).compose(up))
            if q >= 1:
                right = right.add(down.compose(X.d(q)))
            if not left.equals(right):
                return False
    return True


# ---------------------------------------------------------------------------
# Simplicial complexes
# ---------------------------------------------------------------------------

def closure(facets):
    simplices = set()
    for facet in facets:
        facet = tuple(sorted(facet))
        for k in range(1, len(facet)+1):
            simplices.update(combinations(facet, k))
    return simplices


def simplicial_chain_complex(simplices, max_dimension=None):
    """Oriented simplicial chain complex over QQ with simplices sorted within each dimension."""
    by_dimension = {}
    for s in {tuple(sorted(s)) for s in simplices}:
        by_dimension.setdefault(len(s)-1, []).append(s)
    top = max(by_dimension) if by_dimension else 0
    if max_dimension is not None:
        top = min(top, max_dimension)
    bases = [sorted(by_dimension.get(q, [])) for q in range(top+1)]
    index = [{s: i for i, s in enumerate(basis)} for basis in bases]
    boundary = {}
    for q in range(1, top+1):
        matrix = SparseMatrix.zero(len(bases[q-1]), len(bases[q]))
        for j, s in enumerate(bases[q]):
            for i in range(len(s)):
                face = s[:i]+s[i+1:]
                matrix.columns[j][index[q-1][face]] = Fraction(-1 if i % 2 else 1)
        boundary[q] = matrix
    return ChainComplex([len(b) for b in bases], boundary, {q: bases[q] for q in range(top+1)})


# ---------------------------------------------------------------------------
# Elementary reduction along an invertible coefficient (a certified local move)
# ---------------------------------------------------------------------------

def reduction_move(complex_, q, sigma, tau, counter=None):
    """Remove sigma in C_{q+1} and tau in C_q where a = <d sigma, tau> != 0.

    Returns (D, F, G, h) with D the reduced complex, F: C->D, G: D->C chain maps and
    h: C_q -> C_{q+1} the homotopy h(x) = -(x_tau/a) sigma, so that G F - id = d h + h d
    and F G = id. The formulas are the
    standard reduction lemma; certify_homotopy_equivalence checks them exactly.
    """
    counter = counter if counter is not None else OperationCounter()
    d_up = complex_.d(q+1)
    d_sigma = d_up.columns[sigma]
    a = d_sigma.get(tau)
    if not a:
        raise ValueError("coefficient is zero")
    keep_up = [j for j in range(complex_.dims[q+1]) if j != sigma]
    keep_down = [i for i in range(complex_.dims[q]) if i != tau]
    row_down = {old: new for new, old in enumerate(keep_down)}
    row_up = {old: new for new, old in enumerate(keep_up)}

    def project(vector):
        """pi(x) = x - x_tau/a d sigma, re-indexed to D_q."""
        scale = vector.get(tau, Fraction(0))/a
        result = dict(vector)
        if scale:
            for i, value in d_sigma.items():
                result[i] = result.get(i, Fraction(0))-scale*value
                counter.charge("reduction")
        return {row_down[i]: v for i, v in result.items() if v != 0 and i != tau}

    dims = list(complex_.dims)
    dims[q] -= 1
    dims[q+1] -= 1
    boundary = {}
    for k, matrix in complex_.boundary.items():
        if k == q+1:
            boundary[k] = SparseMatrix(dims[q], [project(matrix.columns[j]) for j in keep_up])
        elif k == q:
            boundary[k] = SparseMatrix(matrix.nrows, [dict(matrix.columns[i]) for i in keep_down])
        elif k == q+2:
            columns = []
            for column in matrix.columns:
                columns.append({row_up[i]: v for i, v in column.items() if i != sigma})
                counter.charge("reindex", len(column))
            boundary[k] = SparseMatrix(dims[q+1], columns)
        else:
            boundary[k] = matrix
    reduced = ChainComplex(dims, boundary)

    F, G, h = {}, {}, {}
    F[q] = SparseMatrix(dims[q], [project({i: Fraction(1)}) for i in range(complex_.dims[q])])
    F[q+1] = SparseMatrix(dims[q+1], [({} if j == sigma else {row_up[j]: Fraction(1)}) for j in range(complex_.dims[q+1])])
    G[q] = SparseMatrix(complex_.dims[q], [{old: Fraction(1)} for old in keep_down])
    G_up = []
    for j in keep_up:
        column = {j: Fraction(1)}
        coefficient = d_up.columns[j].get(tau, Fraction(0))
        if coefficient:
            column[sigma] = -coefficient/a
        G_up.append(column)
    G[q+1] = SparseMatrix(complex_.dims[q+1], G_up)
    for k in range(len(complex_.dims)):
        if k not in (q, q+1):
            F[k] = SparseMatrix.identity(complex_.dims[k])
            G[k] = SparseMatrix.identity(complex_.dims[k])
    h[q] = SparseMatrix(complex_.dims[q+1], [({sigma: -Fraction(1)/a} if i == tau else {}) for i in range(complex_.dims[q])])
    return reduced, ChainMap(complex_, reduced, F), ChainMap(reduced, complex_, G), h


# ---------------------------------------------------------------------------
# Persistence over QQ[t]
# ---------------------------------------------------------------------------

def filtered_boundary(filtration):
    """filtration: list of (simplex, birth) sorted by (birth, dimension, simplex). Returns the total boundary matrix."""
    order = sorted(((tuple(sorted(s)), b) for s, b in filtration), key=lambda item: (item[1], len(item[0]), item[0]))
    if len({s for s, _ in order}) != len(order):
        raise ValueError("a simplex appears more than once in the filtration")
    index = {s: i for i, (s, _) in enumerate(order)}
    matrix = SparseMatrix.zero(len(order), len(order))
    for j, (s, _) in enumerate(order):
        if len(s) > 1:
            for i in range(len(s)):
                face = s[:i]+s[i+1:]
                if face not in index or index[face] >= j:
                    raise ValueError("filtration is not a filtered simplicial complex")
                matrix.columns[j][index[face]] = Fraction(-1 if i % 2 else 1)
    return order, matrix


def persistence_barcode(filtration, counter=None, budget=None):
    """Bars (dimension, birth, death or None) from the standard reduction of the filtered boundary."""
    order, matrix = filtered_boundary(filtration)
    reduced, pivots, _ = column_reduce(matrix, counter, budget, record=False)
    paired = set()
    bars = []
    for low, j in pivots.items():
        paired.update((low, j))
        birth, death = order[low][1], order[j][1]
        if death > birth:
            bars.append((len(order[low][0])-1, birth, death))
    for i, (s, b) in enumerate(order):
        if i not in paired:
            bars.append((len(s)-1, b, None))
    return sorted(bars, key=lambda bar: (bar[0], bar[1], float("inf") if bar[2] is None else bar[2]))


def rank_invariant(filtration, q, i, j):
    """rank of H_q(K_i) -> H_q(K_j), computed directly: dim of (Z_q(K_i) + B_q(K_j)) / B_q(K_j)."""
    order, _ = filtered_boundary(filtration)
    K_i = {s for s, b in order if b <= i}
    K_j = {s for s, b in order if b <= j}
    complex_j = simplicial_chain_complex(K_j)
    if q >= len(complex_j.dims):
        return 0
    basis_j = complex_j.labels[q]
    index = {s: n for n, s in enumerate(basis_j)}
    complex_i = simplicial_chain_complex(K_i)
    if q >= len(complex_i.dims):
        return 0
    cycles_i = kernel(complex_i.d(q))
    embedded = [{index[complex_i.labels[q][r]]: v for r, v in column.items()} for column in cycles_i.columns]
    boundaries_j = image(complex_j.d(q+1))
    with_cycles = rank(SparseMatrix(len(basis_j), boundaries_j.columns+embedded))
    return with_cycles-boundaries_j.ncols


def barcode_rank(bars, q, i, j):
    """Number of bars in dimension q alive on the whole interval [i, j] (birth <= i and death > j)."""
    return sum(1 for d, b, e in bars if d == q and b <= i and (e is None or e > j))


def persistence_module_presentation(bars, q):
    """Direct sum of graded k[t]-modules: t^b k[t] / (t^e) for a bar [b, e), free t^b k[t] when e is None."""
    return [{"generator_degree": b, "relation": None if e is None else f"t^{e-b} * g = 0"}
            for d, b, e in bars if d == q]


# ---------------------------------------------------------------------------
# Dual numbers, Jacobians and tangent spaces
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Dual:
    """a + b e with e^2 = 0 over QQ."""
    a: Fraction
    b: Fraction = Fraction(0)

    @staticmethod
    def lift(value):
        return value if isinstance(value, Dual) else Dual(Fraction(value), Fraction(0))

    def __add__(self, other):
        other = Dual.lift(other)
        return Dual(self.a+other.a, self.b+other.b)

    __radd__ = __add__

    def __neg__(self):
        return Dual(-self.a, -self.b)

    def __sub__(self, other):
        return self+(-Dual.lift(other))

    def __rsub__(self, other):
        return Dual.lift(other)-self

    def __mul__(self, other):
        other = Dual.lift(other)
        return Dual(self.a*other.a, self.a*other.b+self.b*other.a)

    __rmul__ = __mul__

    def __pow__(self, exponent):
        if not isinstance(exponent, int) or exponent < 0:
            raise ValueError("dual numbers support nonnegative integer powers only")
        result = Dual(Fraction(1))
        for _ in range(exponent):
            result = result*self
        return result


def jacobian_by_dual_numbers(polynomials, point):
    """J_ij = e-coefficient of f_i(p + e * unit_j); polynomials are callables on sequences."""
    n = len(point)
    columns = []
    for j in range(n):
        shifted = [Dual(Fraction(p), Fraction(1 if k == j else 0)) for k, p in enumerate(point)]
        values = [Dual.lift(f(shifted)) for f in polynomials]
        columns.append({i: v.b for i, v in enumerate(values) if v.b != 0})
    return SparseMatrix(len(polynomials), columns)


def tangent_space(polynomials, point):
    """Zariski tangent space of V(f_1, ..., f_k) at p: ker J(p), with the check that p lies on V(f).

    It equals the tangent space of the reduced variety only when the given polynomials
    generate its ideal near p.
    """
    if any(Fraction(f([Fraction(x) for x in point])) != 0 for f in polynomials):
        raise ValueError("point is not on the variety")
    J = jacobian_by_dual_numbers(polynomials, point)
    basis = kernel(J)
    return {"dimension": basis.ncols, "basis": basis, "jacobian": J, "certified": certify_kernel(J, basis)}


# ---------------------------------------------------------------------------
# Plucker coordinates of 2-planes in 4-space
# ---------------------------------------------------------------------------

PAIRS = ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3))


def plucker(u, v):
    return tuple(Fraction(u[i])*Fraction(v[j])-Fraction(u[j])*Fraction(v[i]) for i, j in PAIRS)


def plucker_relation(p):
    p12, p13, p14, p23, p24, p34 = p
    return p12*p34-p13*p24+p14*p23


def plucker_pairing(p, r):
    """Coefficient of e1^e2^e3^e4 in the wedge of two decomposable bivectors: zero iff the planes meet nontrivially."""
    p12, p13, p14, p23, p24, p34 = p
    r12, r13, r14, r23, r24, r34 = r
    return p12*r34-p13*r24+p14*r23+p23*r14-p24*r13+p34*r12


def compose_equivalences(first, second):
    """Compose (C -> D) and (D -> E) homotopy equivalences.

    Each argument is (F, G, h_source, h_target). The composite is
    F = F2 F1, G = G1 G2, h_C = h1 + G1 h2 F1, h_E = h2' + F2 h1' G2,
    which satisfies G F - id = d h_C + h_C d on C and F G - id = d h_E + h_E d on E
    whenever the parts do. certify_homotopy_equivalence checks the result.
    """
    F1, G1, h1, h1t = first
    F2, G2, h2, h2t = second
    C, E = F1.source, F2.target
    F = F2.compose(F1)
    G = G1.compose(G2)
    h_C, h_E = {}, {}
    for q in range(len(C.dims)):
        rows = C.dims[q+1] if q+1 < len(C.dims) else 0
        total = h1.get(q, SparseMatrix.zero(rows, C.dims[q]))
        middle = h2.get(q)
        if middle is not None:
            total = total.add(G1.at(q+1).compose(middle).compose(F1.at(q)))
        h_C[q] = total
    for q in range(len(E.dims)):
        rows = E.dims[q+1] if q+1 < len(E.dims) else 0
        total = h2t.get(q, SparseMatrix.zero(rows, E.dims[q]))
        middle = h1t.get(q)
        if middle is not None:
            total = total.add(F2.at(q+1).compose(middle).compose(G2.at(q)))
        h_E[q] = total
    return F, G, h_C, h_E
