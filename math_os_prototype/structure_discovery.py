"""Structures that change what a computation costs, discovered and certified exactly.

Three kinds are discovered here. None of them is a route to an answer, and none of
them is stored per instance: each is a statement about an operator or a bilinear
map, certified exactly, that turns a family of problems into cheaper computations.

    merging      which histories need not be told apart: the smallest linear
                 representation reproducing every word's value. Certified by
                 invariance of the reachable subspace and of the unobservable
                 subspace, not by agreeing on samples.

    relation     a polynomial p with p(A) = 0 (or p(A)s = 0): the iteration
                 x -> A x of length L becomes x^L mod p, so a computation of
                 length L costs O(r^2 log L) coefficient operations instead of
                 L applications of A.

    decomposition a bilinear map written with fewer multiplications than the
                 obvious one. Applied recursively, r multiplications for a k-way
                 split give exponent log_k r; Strassen's 7 for 2x2 is the case
                 the exponent 3 drops to log2 7.

Every cost is charged to one `OperationCounter`, and the counter separates the
work of discovering a structure from the work of using it, because a structure is
discovered once and used on every instance of its family.
"""
from __future__ import annotations

from fractions import Fraction
from itertools import product
import random

from math_os_prototype import algebraic_structures as alg
from math_os_prototype.algebraic_structures import OperationCounter, SparseMatrix


class NoStructure(ValueError):
    """The structure does not exist within the stated bounds; nothing is assumed."""


def _charge(counter, kind, amount=1):
    if counter is not None:
        counter.charge(kind, amount)


# ---------------------------------------------------------------------------
# Vectors
# ---------------------------------------------------------------------------

def unit(index):
    return {index: Fraction(1)}


def combine(vectors, coefficients, counter=None, kind="execute"):
    result = {}
    for vector, coefficient in zip(vectors, coefficients, strict=True):
        if not coefficient:
            continue
        for i, value in vector.items():
            result[i] = result.get(i, Fraction(0))+coefficient*value
            _charge(counter, kind)
    return {i: v for i, v in result.items() if v}


def pair(functional, vector, counter=None, kind="execute"):
    total = Fraction(0)
    for i, value in vector.items():
        if i in functional:
            total += functional[i]*value
            _charge(counter, kind)
    return total


# ---------------------------------------------------------------------------
# 1. Merging: the smallest linear representation of a word function
# ---------------------------------------------------------------------------

def _span_solve(basis, vector, counter=None):
    """Coordinates of `vector` in the span of the basis columns, or None."""
    if not basis.columns:
        return None if vector else {}
    return alg.solve(basis, vector, counter)


def transpose(matrix):
    columns = [dict() for _ in range(matrix.nrows)]
    for j, column in enumerate(matrix.columns):
        for i, value in column.items():
            columns[i][j] = value
    return SparseMatrix(matrix.ncols, columns)


def reachable_subspace(matrices, start, *, budget=None, counter=None):
    """A basis of the smallest subspace that contains `start` and is closed under every matrix."""
    dimension = matrices[0].nrows
    basis = SparseMatrix(dimension, [])
    frontier = []

    def add(vector):
        if not vector or _span_solve(basis, vector, counter) is not None:
            return
        basis.columns.append(dict(vector))
        frontier.append(dict(vector))

    add(start)
    while frontier:
        vector = frontier.pop()
        for matrix in matrices:
            add(matrix.apply(vector, counter))
        if budget is not None and counter is not None and counter["total"] > budget:
            raise NoStructure("the reachable subspace exceeded the budget")
    return basis


def invariant_row_space(matrices, functional, *, counter=None):
    """The smallest row space containing the functional and closed under every transpose.

    Its annihilator is the largest subspace inside ker(functional) that every
    operation maps into itself: exactly the directions no word can ever see.
    """
    dimension = matrices[0].nrows
    rows = SparseMatrix(dimension, [dict(functional)] if functional else [])
    transposed = [transpose(matrix) for matrix in matrices]
    while True:
        added = False
        for matrix in transposed:
            for index in range(rows.ncols):
                image = matrix.apply(dict(rows.columns[index]), counter)
                if image and _span_solve(rows, image, counter) is None:
                    rows.columns.append(image)
                    added = True
        if not added:
            return rows


def coordinate_representation(matrices, start, functional, *, budget=None, counter=None):
    """Rewrite the operations on a basis of what the start can reach."""
    reachable = reachable_subspace(matrices, start, budget=budget, counter=counter)
    if reachable.ncols == 0:
        raise NoStructure("the start vector is zero")
    reduced = []
    for matrix in matrices:
        columns = []
        for index in range(reachable.ncols):
            image = matrix.apply(dict(reachable.columns[index]), counter)
            coordinates = _span_solve(reachable, image, counter)
            if coordinates is None:
                raise NoStructure("the reachable subspace is not invariant")
            columns.append(coordinates)
        reduced.append(SparseMatrix(reachable.ncols, columns))
    start_coordinates = _span_solve(reachable, start, counter)
    reduced_functional = {}
    for index in range(reachable.ncols):
        value = pair(functional, dict(reachable.columns[index]), counter, "discover")
        if value:
            reduced_functional[index] = value
    return {"matrices": reduced, "start": start_coordinates, "functional": reduced_functional,
            "basis": reachable}


def quotient_by_unobservable(representation, *, counter=None):
    """Forget the directions the functional can never see, exactly."""
    matrices = representation["matrices"]
    dimension = matrices[0].nrows if matrices else 0
    rows = invariant_row_space(matrices, representation["functional"], counter=counter)
    hidden = alg.kernel(transpose(rows), counter)
    basis = SparseMatrix(dimension, [dict(c) for c in hidden.columns])
    complement = []
    for index in range(dimension):
        candidate = unit(index)
        if _span_solve(basis, candidate, counter) is None:
            basis.columns.append(dict(candidate))
            complement.append(dict(candidate))
    offset = hidden.ncols

    def coordinates_of(vector):
        solution = _span_solve(basis, vector, counter)
        if solution is None:
            raise NoStructure("a vector left the space")
        return {i-offset: v for i, v in solution.items() if i >= offset and v}

    reduced = []
    for matrix in matrices:
        columns = []
        for column in complement:
            columns.append(coordinates_of(matrix.apply(dict(column), counter)))
        reduced.append(SparseMatrix(len(complement), columns))
    reduced_start = coordinates_of(representation["start"])
    reduced_functional = {}
    for index, column in enumerate(complement):
        value = pair(representation["functional"], dict(column), counter, "discover")
        if value:
            reduced_functional[index] = value
    return {"matrices": reduced, "start": reduced_start, "functional": reduced_functional,
            "hidden_dimension": hidden.ncols}


def minimal_representation(matrices, start, functional, *, budget=None, counter=None):
    """The smallest linear representation of the word function, with its certificate.

    Reachability keeps only what the start can produce; observability forgets what
    the functional can never see. Both are exact constructions, and the certificate
    is the invariance that makes them value-preserving for every word, not an
    agreement on sampled words.
    """
    original = coordinate_representation(matrices, start, functional, budget=budget, counter=counter)
    reduced = quotient_by_unobservable(original, counter=counter)
    return {"dimension": len(reduced["matrices"][0].columns) if reduced["matrices"] else 0,
            "matrices": reduced["matrices"], "start": reduced["start"],
            "functional": reduced["functional"],
            "original_dimension": matrices[0].nrows,
            "reachable_dimension": original["basis"].ncols,
            "hidden_dimension": reduced["hidden_dimension"],
            "certificate": {
                "rule": "the reachable subspace contains the start and is closed under every operation; "
                        "the annihilator of the smallest row space containing the functional and closed "
                        "under every transpose is mapped into itself and is killed by the functional; "
                        "restricting to the first and quotienting by the second leaves every word value "
                        "unchanged"}}


def word_value(matrices, start, functional, word, counter=None, kind="execute"):
    """<g| M_{w_k} ... M_{w_1} |s>, one operation at a time."""
    vector = dict(start)
    for letter in word:
        vector = matrices[letter].apply(vector, counter)
    return pair(functional, vector, counter, kind)


# ---------------------------------------------------------------------------
# 2. Relation: a polynomial that collapses an iteration
# ---------------------------------------------------------------------------

def krylov_relation(matrix, start, *, max_degree=None, counter=None):
    """The smallest r with A^r s in the span of s, ..., A^{r-1} s, and that expansion.

    The coefficients are the expansion itself: A^r s = sum c_i A^i s, so the
    relation is p(x) = x^r - sum c_i x^i and p(A) s = 0. The same convention is
    used by `polynomial_remainder_power`, where x^r is replaced by sum c_i x^i.
    """
    dimension = matrix.nrows
    max_degree = dimension if max_degree is None else min(max_degree, dimension)
    basis = SparseMatrix(dimension, [])
    vectors, vector = [], dict(start)
    for _ in range(max_degree+1):
        coordinates = _span_solve(basis, vector, counter)
        if coordinates is not None:
            degree = len(vectors)
            coefficients = [coordinates.get(i, Fraction(0)) for i in range(degree)]
            return {"degree": degree, "coefficients": coefficients, "vectors": vectors}
        basis.columns.append(dict(vector))
        vectors.append(dict(vector))
        vector = matrix.apply(vector, counter)
    raise NoStructure("no relation within the degree bound")


def certify_relation(matrix, start, coefficients, *, counter=None):
    """p(A) s = 0, checked by exact application, not by sampling."""
    degree = len(coefficients)
    vector, total = dict(start), {}
    for index in range(degree+1):
        coefficient = Fraction(1) if index == degree else -coefficients[index]
        total = combine([total, vector], [Fraction(1), coefficient], counter, "verify")
        if index < degree:
            vector = matrix.apply(vector, counter)
    return not total


def certify_operator_relation(matrix, coefficients, *, counter=None):
    """p(A) = 0 as a matrix identity: then the relation holds for every start vector."""
    degree = len(coefficients)
    power = SparseMatrix.identity(matrix.nrows)
    total = SparseMatrix.zero(matrix.nrows, matrix.nrows)
    for index in range(degree+1):
        coefficient = Fraction(1) if index == degree else -coefficients[index]
        total = total.add(power, coefficient)
        _charge(counter, "verify", power.nonzeros())
        if index < degree:
            power = matrix.compose(power, counter)
    return total.is_zero()


def polynomial_remainder_power(coefficients, exponent, *, counter=None, kind="transform"):
    """x^L mod p by repeated squaring; p is monic of degree r = len(coefficients)."""
    degree = len(coefficients)
    if degree == 0:
        raise NoStructure("an empty relation")

    def reduce(terms):
        terms = list(terms)
        for index in range(len(terms)-1, degree-1, -1):
            factor = terms[index]
            if not factor:
                continue
            terms[index] = Fraction(0)
            for offset, coefficient in enumerate(coefficients):
                terms[index-degree+offset] += factor*coefficient
                _charge(counter, kind)
        return terms[:degree]

    def multiply(left, right):
        terms = [Fraction(0)]*(2*degree)
        for i, a in enumerate(left):
            if not a:
                continue
            for j, b in enumerate(right):
                if not b:
                    continue
                terms[i+j] += a*b
                _charge(counter, kind)
        return reduce(terms)

    result = [Fraction(0)]*degree
    result[0] = Fraction(1)
    base = [Fraction(0)]*degree
    if degree == 1:
        base = reduce([Fraction(0), Fraction(1)])
    else:
        base[1] = Fraction(1)
    power = exponent
    while power:
        if power & 1:
            result = multiply(result, base)
        power >>= 1
        if power:
            base = multiply(base, base)
    return result


def value_from_relation(initial_values, remainder, *, counter=None, kind="execute"):
    """y_L = sum q_i y_i, where q = x^L mod p and y_i are the first values."""
    total = Fraction(0)
    for coefficient, value in zip(remainder, initial_values, strict=True):
        if coefficient:
            total += coefficient*value
            _charge(counter, kind)
    return total


# ---------------------------------------------------------------------------
# 3. Decomposition: fewer multiplications, applied recursively
# ---------------------------------------------------------------------------

def matrix_multiplication_tensor(n, m, p):
    """T[(i,k), (k,j), (i,j)] = 1: the bilinear map of an n x m by m x p product."""
    entries = {}
    for i in range(n):
        for k in range(m):
            for j in range(p):
                entries[(i*m+k, k*p+j, i*p+j)] = Fraction(1)
    return {"shape": (n*m, m*p, n*p), "entries": entries}


def trivial_decomposition(tensor):
    """One multiplication per nonzero entry: the obvious algorithm."""
    terms = []
    for (a, b, c), value in sorted(tensor["entries"].items()):
        terms.append(({a: Fraction(1)}, {b: Fraction(1)}, {c: value}))
    return terms


def decomposition_error(tensor, terms, *, counter=None, kind="verify"):
    """The exact difference between the tensor and the decomposition, as a dict."""
    residual = dict(tensor["entries"])
    for left, right, out in terms:
        for a, u in left.items():
            for b, v in right.items():
                if not u*v:
                    continue
                for c, w in out.items():
                    key = (a, b, c)
                    residual[key] = residual.get(key, Fraction(0))-u*v*w
                    _charge(counter, kind)
    return {key: value for key, value in residual.items() if value}


def flip(terms, index, other, position, rng):
    """One flip: two terms sharing a factor are rewritten, and the tensor is unchanged.

    With u (x) v (x) w + u (x) v' (x) w', adding v' to the first second factor and
    subtracting w from the second third factor leaves the sum equal:
        u (x) (v + v') (x) w  +  u (x) v' (x) (w' - w).
    A factor that cancels is the move that lowers the rank, not a failure.
    """
    left, right = list(terms[index]), list(terms[other])
    shared, first, second = position, (position+1) % 3, (position+2) % 3
    if left[shared] != right[shared]:
        return None
    if rng.random() < 0.5:
        first, second = second, first
    updated = list(terms)
    new_left, new_right = list(left), list(right)
    new_left[first] = _add_vectors(left[first], right[first])
    new_right[second] = _add_vectors(right[second], left[second], Fraction(-1))
    updated[index] = tuple(new_left)
    updated[other] = tuple(new_right)
    return updated


def _add_vectors(left, right, scale=Fraction(1)):
    result = dict(left)
    for index, value in right.items():
        result[index] = result.get(index, Fraction(0))+scale*value
    return {index: value for index, value in result.items() if value}


def _content(vector):
    """The scalar that makes a rational vector primitive: gcd of numerators over lcm of denominators."""
    from math import gcd
    numerator, denominator = 0, 1
    for value in vector.values():
        numerator = gcd(numerator, abs(value.numerator))
        denominator = denominator*value.denominator//gcd(denominator, value.denominator)
    if numerator == 0:
        return Fraction(1)
    return Fraction(numerator, denominator)


def normalise(term):
    """One representative per rank-one term: the first two factors primitive, scalars in the third."""
    left, right, out = ({k: v for k, v in factor.items() if v} for factor in term)
    if not (left and right and out):
        return None
    scale = Fraction(1)
    for factor in (left, right):
        content = _content(factor)
        if factor[min(factor)] < 0:
            content = -content
        if content != 1:
            for key in list(factor):
                factor[key] = factor[key]/content
            scale *= content
    if scale != 1:
        out = {key: value*scale for key, value in out.items()}
    return (left, right, {k: v for k, v in out.items() if v})


def reduce_decomposition(terms):
    """Drop terms that became zero and merge terms agreeing in two of three factors."""
    kept = [normalised for normalised in (normalise(term) for term in terms) if normalised]
    changed = True
    while changed:
        changed = False
        for i in range(len(kept)):
            for j in range(i+1, len(kept)):
                for shared in range(3):
                    a, b = (shared+1) % 3, (shared+2) % 3
                    if kept[i][shared] == kept[j][shared] and kept[i][a] == kept[j][a]:
                        merged = list(kept[i])
                        merged[b] = _add_vectors(kept[i][b], kept[j][b])
                        rest = [term for index, term in enumerate(kept) if index not in (i, j)]
                        normalised = normalise(tuple(merged))
                        kept = rest+([normalised] if normalised else [])
                        changed = True
                        break
                if changed:
                    break
            if changed:
                break
    return kept


# --- the same walk over GF(2), where coefficients cannot grow ---------------

def binary_terms(tensor):
    """The obvious decomposition, over GF(2): one term per nonzero entry."""
    return [(frozenset([a]), frozenset([b]), frozenset([c]))
            for (a, b, c), value in sorted(tensor["entries"].items()) if value.numerator % 2]


def binary_reduce(terms):
    kept = [term for term in terms if all(term)]
    changed = True
    while changed:
        changed = False
        for i in range(len(kept)):
            for j in range(i+1, len(kept)):
                for shared in range(3):
                    a, b = (shared+1) % 3, (shared+2) % 3
                    if kept[i][shared] == kept[j][shared] and kept[i][a] == kept[j][a]:
                        merged = list(kept[i])
                        merged[b] = kept[i][b] ^ kept[j][b]
                        rest = [term for index, term in enumerate(kept) if index not in (i, j)]
                        kept = rest+([tuple(merged)] if all(merged) else [])
                        changed = True
                        break
                if changed:
                    break
            if changed:
                break
    return kept


def binary_flip(terms, index, other, position, rng):
    left, right = list(terms[index]), list(terms[other])
    shared, first, second = position, (position+1) % 3, (position+2) % 3
    if left[shared] != right[shared]:
        return None
    if rng.random() < 0.5:
        first, second = second, first
    updated = list(terms)
    new_left, new_right = list(left), list(right)
    new_left[first] = left[first] ^ right[first]
    new_right[second] = right[second] ^ left[second]
    updated[index] = tuple(new_left)
    updated[other] = tuple(new_right)
    return updated


def binary_error(tensor, terms):
    """The residual of a decomposition over GF(2), as the set of entries that differ."""
    residual = {}
    for (a, b, c), value in tensor["entries"].items():
        residual[(a, b, c)] = value.numerator % 2
    for left, right, out in terms:
        for a in left:
            for b in right:
                for c in out:
                    residual[(a, b, c)] = (residual.get((a, b, c), 0)+1) % 2
    return {key for key, value in residual.items() if value}


def search_decomposition(tensor, *, target_rank, steps=400000, seed=0, counter=None, restarts=10):
    """Search for a decomposition of rank at most `target_rank` by flips over GF(2).

    Every state of the walk is an exact decomposition of the same tensor over
    GF(2): a flip rewrites two terms by an identity and a reduction merges or
    drops terms. The walk is told the target rank and nothing else, and what it
    reaches is checked against the tensor.
    """
    best = binary_reduce(binary_terms(tensor))
    history = [len(best)]
    for restart in range(restarts):
        rng = random.Random(seed*1000+restart)
        terms = list(best)
        for _ in range(max(1, steps//restarts)):
            if len(best) <= target_rank:
                break
            index, other = rng.randrange(len(terms)), rng.randrange(len(terms))
            if index == other:
                continue
            flipped = binary_flip(terms, index, other, rng.randrange(3), rng)
            _charge(counter, "discover")
            if flipped is None:
                continue
            reduced = binary_reduce(flipped)
            if len(reduced) <= len(terms):
                terms = reduced
                if len(terms) < len(best):
                    best = list(terms)
                    history.append(len(best))
    return {"terms": best, "rank": len(best), "history": history,
            "reached_target": len(best) <= target_rank,
            "exact_over_gf2": not binary_error(tensor, best)}


def lift_to_rationals(tensor, binary_decomposition, *, counter=None, sign_budget=1 << 16):
    """Turn a decomposition over GF(2) into an exact one over the rationals, or report that it did not.

    The supports of the first two factors are kept; their signs are searched, and
    for each choice the third factors are solved for exactly. Nothing is accepted
    without `decomposition_error` returning empty.
    """
    supports = [(sorted(left), sorted(right)) for left, right, _ in binary_decomposition]
    free = []
    for index, (left, right) in enumerate(supports):
        free.extend([(index, 0, position) for position in range(1, len(left))])
        free.extend([(index, 1, position) for position in range(1, len(right))])
    if 1 << len(free) > sign_budget:
        free = free[:max(0, sign_budget.bit_length()-1)]
    rows, columns = tensor["shape"][0], tensor["shape"][1]
    for pattern in range(1 << len(free)):
        signs = {key: (1 if not (pattern >> position) & 1 else -1)
                 for position, key in enumerate(free)}
        factors = []
        for index, (left, right) in enumerate(supports):
            u = {key: Fraction(signs.get((index, 0, position), 1))
                 for position, key in enumerate(left)}
            v = {key: Fraction(signs.get((index, 1, position), 1))
                 for position, key in enumerate(right)}
            factors.append((u, v))
        products = SparseMatrix(rows*columns, [])
        for u, v in factors:
            column = {}
            for a, x in u.items():
                for b, y in v.items():
                    column[a*columns+b] = column.get(a*columns+b, Fraction(0))+x*y
            products.columns.append(column)
        outputs, solved = [], True
        for output in range(tensor["shape"][2]):
            target = {}
            for (a, b, c), value in tensor["entries"].items():
                if c == output:
                    target[a*columns+b] = target.get(a*columns+b, Fraction(0))+value
            solution = alg.solve(products, target, counter)
            if solution is None:
                solved = False
                break
            outputs.append(solution)
        _charge(counter, "discover")
        if not solved:
            continue
        terms = []
        for index, (u, v) in enumerate(factors):
            w = {output: coefficients[index] for output, coefficients in enumerate(outputs)
                 if coefficients.get(index)}
            if w:
                terms.append((u, v, w))
        if not decomposition_error(tensor, terms, counter=counter):
            return {"terms": terms, "rank": len(terms), "sign_pattern": pattern}
    return None


def apply_decomposition(terms, left_entries, right_entries, shape, *, counter=None, kind="execute"):
    """Run the bilinear map through the decomposition: one multiplication per term."""
    products = []
    for left, right, _ in terms:
        a = sum(coefficient*left_entries[index] for index, coefficient in left.items())
        b = sum(coefficient*right_entries[index] for index, coefficient in right.items())
        _charge(counter, kind+":add", len(left)+len(right))
        _charge(counter, kind+":multiply")
        products.append(a*b)
    result = [0]*shape[2]
    for product, (_, _, out) in zip(products, terms, strict=True):
        for index, coefficient in out.items():
            result[index] += coefficient*product
            _charge(counter, kind+":add")
    return result


def recursive_multiply(terms, block, A, B, size, *, counter=None, kind="execute"):
    """Multiply two size x size matrices by applying the decomposition recursively.

    A and B are lists of rows. At size 1 the product is one scalar multiplication;
    above it, the matrices are split into block x block pieces, the decomposition
    says which combinations to multiply, and each of those is multiplied the same
    way. Nothing about the decomposition is assumed here: it is read from the terms.
    """
    if size == 1:
        _charge(counter, kind+":multiply")
        return [[A[0][0]*B[0][0]]]
    half = size//block

    def piece(matrix, index):
        row, column = divmod(index, block)
        return [r[column*half:(column+1)*half] for r in matrix[row*half:(row+1)*half]]

    def add(left, right, scale):
        _charge(counter, kind+":add", half*half)
        return [[a+scale*b for a, b in zip(x, y, strict=True)] for x, y in zip(left, right, strict=True)]

    def zero():
        return [[0]*half for _ in range(half)]

    products = []
    for left, right, _ in terms:
        first, second = zero(), zero()
        for index, coefficient in left.items():
            first = add(first, piece(A, index), coefficient)
        for index, coefficient in right.items():
            second = add(second, piece(B, index), coefficient)
        products.append(recursive_multiply(terms, block, first, second, half, counter=counter, kind=kind))
    result = [[0]*size for _ in range(size)]
    for product, (_, _, out) in zip(products, terms, strict=True):
        for index, coefficient in out.items():
            row, column = divmod(index, block)
            for i in range(half):
                for j in range(half):
                    result[row*half+i][column*half+j] += coefficient*product[i][j]
                    _charge(counter, kind+":add")
    return result


def naive_multiply(A, B, size, *, counter=None, kind="baseline"):
    result = [[0]*size for _ in range(size)]
    for i in range(size):
        for j in range(size):
            total = 0
            for k in range(size):
                total += A[i][k]*B[k][j]
                _charge(counter, kind+":multiply")
                _charge(counter, kind+":add")
            result[i][j] = total
    return result


def recursive_multiplication_cost(rank, block, depth):
    """Scalar multiplications of this recursion, against the obvious algorithm."""
    return rank**depth, (block**3)**depth


def exponent(rank, block):
    """The exponent of a recursion using this many multiplications for a block-way split."""
    import math
    return math.log(rank)/math.log(block)
