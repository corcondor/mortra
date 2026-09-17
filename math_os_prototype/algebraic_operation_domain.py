"""Sorts, predicates and given contracts for maps, bases, quotients, complexes and tangent data.

Everything computed here is computed by `algebraic_structures`; everything
searched over is searched by `runtime_typed_planner`. This module only says, in
the shared contract language, what each existing operation requires, what it
guarantees, how the guarantee is established, and what it costs.

The quotient is not a primitive: `ker(A)/im(B)` under `AB = 0` has to be
composed from the kernel, image and quotient contracts by the planner.
"""
from __future__ import annotations

from fractions import Fraction

import sympy as sp

from math_os_prototype import algebraic_structures as alg
from math_os_prototype.operation_contracts import (
    Condition,
    Contract,
    Definition,
    Predicate,
    Registry,
    Sort,
)
from math_os_prototype.representation_progress import digest


# ---------------------------------------------------------------------------
# Object identity
# ---------------------------------------------------------------------------

def matrix_key(matrix):
    return digest([matrix.nrows, [[[i, str(v)] for i, v in sorted(c.items())] for c in matrix.columns]])[:20]


def quotient_key(quotient):
    return digest([quotient["ambient"], matrix_key(quotient["super"]), matrix_key(quotient["sub"]),
                   quotient["dimension"],
                   [[[i, str(v)] for i, v in sorted(r.items())] for r in quotient["representatives"]]])[:20]


def complex_key(complex_):
    return digest([list(complex_.dims), {str(q): matrix_key(m) for q, m in sorted(complex_.boundary.items())}])[:20]


def system_key(system):
    return digest([list(system["variables"]), list(system["polynomials"])])[:20]


def point_key(point):
    return digest([str(Fraction(x)) for x in point])[:20]


def fact_key(fact):
    return digest(fact)[:20]


SORTS = (
    Sort("Map", matrix_key),
    Sort("Basis", matrix_key),
    Sort("Quotient", quotient_key),
    Sort("Complex", complex_key),
    Sort("Degree", lambda q: str(int(q))),
    Sort("System", system_key),
    Sort("Point", point_key),
    Sort("Fact", fact_key),
)


# ---------------------------------------------------------------------------
# Exact evaluation of a polynomial system (data, not callables)
# ---------------------------------------------------------------------------

def _expression(system, index):
    variables = sp.symbols(list(system["variables"]))
    return sp.sympify(system["polynomials"][index]), variables


def _evaluate(expression, variables, values):
    """Exact evaluation over QQ or over the dual numbers of `algebraic_structures`."""
    environment = dict(zip(variables, values, strict=True))

    def walk(node):
        if node.is_Number:
            return Fraction(int(sp.nsimplify(node).p), int(sp.nsimplify(node).q))
        if node.is_Symbol:
            return environment[node]
        if node.is_Add:
            total = Fraction(0)
            for argument in node.args:
                total = walk(argument)+total
            return total
        if node.is_Mul:
            product = Fraction(1)
            for argument in node.args:
                product = walk(argument)*product
            return product
        if node.is_Pow:
            exponent = node.args[1]
            if not exponent.is_Integer or int(exponent) < 0:
                raise ValueError("only nonnegative integer powers are supported")
            return walk(node.args[0])**int(exponent)
        raise ValueError(f"unsupported expression node: {node}")

    return walk(sp.expand(expression))


def system_callables(system):
    """Callables on a sequence of coordinates, exact over QQ and over dual numbers."""
    compiled = [_expression(system, i) for i in range(len(system["polynomials"]))]
    return [(lambda values, e=e, v=v: _evaluate(e, v, list(values))) for e, v in compiled]


def symbolic_jacobian(system, point):
    """Independent route: symbolic differentiation, then exact evaluation at the point."""
    columns = []
    for j, name in enumerate(system["variables"]):
        column = {}
        for i in range(len(system["polynomials"])):
            expression, variables = _expression(system, i)
            derivative = sp.diff(expression, sp.Symbol(name))
            value = _evaluate(derivative, variables, [Fraction(x) for x in point])
            if value:
                column[i] = Fraction(value)
        columns.append(column)
    return alg.SparseMatrix(len(system["polynomials"]), columns)


# ---------------------------------------------------------------------------
# Predicates: each one decides exactly and charges the shared counter
# ---------------------------------------------------------------------------

def _rank(matrix, counter):
    return alg.rank(matrix, counter)


def check_zero_composition(A, B, *, counter):
    if A.ncols != B.nrows:
        return False
    return A.compose(B, counter).is_zero()


def check_kernel_of(A, K, *, counter):
    """A K = 0, K of full column rank, rank A + cols K = cols A: the certificate of `certify_kernel`."""
    if K.nrows != A.ncols:
        return False
    return (A.compose(K, counter).is_zero() and _rank(K, counter) == K.ncols
            and _rank(A, counter)+K.ncols == A.ncols)


def check_image_of(B, I, *, counter):
    """Every column of I lies in im B, I is independent, and the counts agree with rank B."""
    if I.nrows != B.nrows:
        return False
    if _rank(I, counter) != I.ncols or I.ncols != _rank(B, counter):
        return False
    return all(alg.solve(B, column, counter) is not None for column in I.columns)


def check_contained(I, K, *, counter):
    if I.nrows != K.nrows:
        return False
    return all(alg.solve(K, column, counter) is not None for column in I.columns)


def check_quotient_of(K, I, Q, *, counter):
    if not (Q["super"].equals(K) and Q["sub"].equals(I)):
        return False
    if Q["ambient"] != K.nrows or len(Q["representatives"]) != Q["dimension"]:
        return False
    if _rank(K, counter)-_rank(I, counter) != Q["dimension"]:
        return False
    if any(alg.solve(K, r, counter) is None for r in Q["representatives"]):
        return False
    combined = alg.SparseMatrix(K.nrows, list(I.columns)+list(Q["representatives"]))
    return _rank(combined, counter) == _rank(I, counter)+len(Q["representatives"])


def check_differential_of(C, q, A, *, counter):
    return C.d(int(q)).equals(A)


def check_successor(q, r, *, counter):
    return int(r) == int(q)+1


def check_same_columns(K, M, *, counter):
    return K.equals(M)


def check_vanishes_at(S, p, *, counter):
    functions = system_callables(S)
    counter.charge("evaluate", len(functions))
    return all(Fraction(f([Fraction(x) for x in p])) == 0 for f in functions)


def check_jacobian_at(S, p, J, *, counter):
    counter.charge("differentiate", len(S["polynomials"])*len(S["variables"]))
    return symbolic_jacobian(S, p).equals(J)


def check_homology_of(A, B, Q, *, counter):
    """Q presents ker(A)/im(B): decided from Q alone, whatever route produced it."""
    return (check_kernel_of(A, Q["super"], counter=counter)
            and check_image_of(B, Q["sub"], counter=counter)
            and check_quotient_of(Q["super"], Q["sub"], Q, counter=counter))


def check_complex_differentials_vanish(C, *, counter):
    """d d = 0 in every degree: the chain complex certificate of `algebraic_structures`."""
    return C.certify_differential(counter)


def check_subsystem(S, T, *, counter):
    """Every polynomial of S is one of T, in the same variables: V(T) is contained in V(S)."""
    counter.charge("compare_systems", len(S["polynomials"])+len(T["polynomials"]))
    return (list(S["variables"]) == list(T["variables"])
            and set(S["polynomials"]) <= set(T["polynomials"]))


def check_composition_of(A, B, C, *, counter):
    if A.ncols != B.nrows:
        return False
    return A.compose(B, counter).equals(C)


PREDICATES = (
    Predicate("zero_composition", ("Map", "Map"), check_zero_composition, "A B = 0"),
    Predicate("kernel_of", ("Map", "Basis"), check_kernel_of, "columns of K are a basis of ker A"),
    Predicate("image_of", ("Map", "Basis"), check_image_of, "columns of I are a basis of im B"),
    Predicate("contained", ("Basis", "Basis"), check_contained, "span I is contained in span K"),
    Predicate("quotient_of", ("Basis", "Basis", "Quotient"), check_quotient_of,
              "Q presents span K / span I with representatives"),
    Predicate("differential_of", ("Complex", "Degree", "Map"), check_differential_of, "A = d_q of C"),
    Predicate("successor", ("Degree", "Degree"), check_successor, "r = q + 1"),
    Predicate("same_columns", ("Basis", "Map"), check_same_columns, "the map with the columns of K"),
    Predicate("vanishes_at", ("System", "Point"), check_vanishes_at, "every polynomial of S vanishes at p"),
    Predicate("jacobian_at", ("System", "Point", "Map"), check_jacobian_at, "J is the Jacobian of S at p"),
    Predicate("composition_of", ("Map", "Map", "Map"), check_composition_of, "C = A B"),
    Predicate("homology_of", ("Map", "Map", "Quotient"), check_homology_of, "Q presents ker(A) / im(B)"),
    Predicate("complex_differentials_vanish", ("Complex",), check_complex_differentials_vanish, "d d = 0"),
    Predicate("subsystem", ("System", "System"), check_subsystem, "S is a subsystem of T"),
)


# ---------------------------------------------------------------------------
# Specifications: what is wanted, never how to reach it
# ---------------------------------------------------------------------------

DEFINITIONS = (
    # ker(A) / im(B): the first integration task. The contracts for kernel, image
    # and quotient are given; which sequence of them meets this specification is not.
    Definition(predicate="homology_of", params=("A", "B", "v"), sorts=("Map", "Map", "Quotient"),
               exists=("K", "I"),
               body=(Condition.of("kernel_of", "A", "K"), Condition.of("image_of", "B", "I"),
                     Condition.of("quotient_of", "K", "I", "v"))),
    # H_q of a chain complex, stated over the complex and the degree.
    Definition(predicate="homology_at", params=("C", "q", "v"), sorts=("Complex", "Degree", "Quotient"),
               exists=("A", "B", "r"),
               body=(Condition.of("differential_of", "C", "q", "A"), Condition.of("successor", "q", "r"),
                     Condition.of("differential_of", "C", "r", "B"),
                     Condition.of("homology_of", "A", "B", "v"))),
    # The tangent directions of V(S) at p that the extra equations of T remove.
    Definition(predicate="tangent_quotient", params=("S", "T", "p", "v"),
               sorts=("System", "System", "Point", "Quotient"), exists=("J", "G", "K", "M"),
               body=(Condition.of("jacobian_at", "S", "p", "J"), Condition.of("jacobian_at", "T", "p", "G"),
                     Condition.of("kernel_of", "G", "K"), Condition.of("same_columns", "K", "M"),
                     Condition.of("homology_of", "J", "M", "v"))),
)


# ---------------------------------------------------------------------------
# Given contracts
# ---------------------------------------------------------------------------

def run_kernel_basis(binding, counter):
    return alg.kernel(binding["A"], counter)


def run_image_basis(binding, counter):
    return alg.image(binding["B"], counter)


def run_quotient_basis(binding, counter):
    K, I = binding["K"], binding["I"]
    if I.nrows != K.nrows:
        return None
    combined = alg.SparseMatrix(K.nrows, [dict(c) for c in I.columns]+[dict(c) for c in K.columns])
    reduced, pivots, _ = alg.column_reduce(combined, counter, record=False)
    offset = I.ncols
    representatives = [dict(K.columns[j-offset]) for j in sorted(pivots.values()) if j >= offset]
    return {"ambient": K.nrows, "super": K.copy(), "sub": I.copy(),
            "representatives": representatives, "dimension": len(representatives)}


def run_return_A(binding, counter):
    """A lemma returns its subject unchanged; what it adds is the guarantee, not a new object."""
    counter.charge("lemma")
    return binding["A"]


def run_return_J(binding, counter):
    counter.charge("lemma")
    return binding["J"]


def run_compose_maps(binding, counter):
    A, B = binding["A"], binding["B"]
    if A.ncols != B.nrows:
        return None
    return A.compose(B, counter)


def run_differential(binding, counter):
    """d_q of the complex; above the top degree it is the map out of the zero space."""
    C, q = binding["C"], int(binding["q"])
    if not 0 <= q <= len(C.dims):
        return None
    counter.charge("read_differential")
    return C.d(q)


def run_next_degree(binding, counter):
    counter.charge("successor")
    return int(binding["q"])+1


def run_basis_as_map(binding, counter):
    counter.charge("coerce")
    return binding["K"].copy()


def run_jacobian(binding, counter):
    S, p = binding["S"], binding["p"]
    if len(p) != len(S["variables"]):
        return None
    functions = system_callables(S)
    counter.charge("dual_evaluate", len(functions)*len(p))
    return alg.jacobian_by_dual_numbers(functions, [Fraction(x) for x in p])


def run_inclusion_lemma(binding, counter):
    """A B = 0, K a kernel basis of A and I an image basis of B give span I subseteq span K.

    The conclusion is derived, not recomputed: every column of I is B x, so
    A (B x) = (A B) x = 0, hence the column lies in ker A, which span K exhausts
    because rank A + cols K = cols A. The value returned is K itself, now carrying
    the stronger guarantee.
    """
    counter.charge("lemma")
    return binding["K"]


GIVEN_CONTRACTS = (
    Contract(name="kernel_basis", params=(("A", "Map"),), result="Basis",
             post=(Condition.of("kernel_of", "A", "v"),), run=run_kernel_basis,
             note="column reduction with the recorded transform; the certificate is checked exactly"),
    Contract(name="image_basis", params=(("B", "Map"),), result="Basis",
             post=(Condition.of("image_of", "B", "v"),), run=run_image_basis,
             note="pivot columns of the reduced form"),
    Contract(name="kernel_contains_image",
             params=(("A", "Map"), ("B", "Map"), ("K", "Basis"), ("I", "Basis")), result="Basis",
             pre=(Condition.of("zero_composition", "A", "B"), Condition.of("kernel_of", "A", "K"),
                  Condition.of("image_of", "B", "I")),
             post=(Condition.of("contained", "I", "K"),), run=run_inclusion_lemma, returns="K",
             derivation={"kind": "lemma", "rule": "A B = 0 and a complete kernel basis give im B subseteq span K"},
             note="a supplied inference rule: it returns K, now carrying the stronger guarantee, and the "
                  "conclusion is derived from the premises instead of recomputed"),
    Contract(name="quotient_basis", params=(("K", "Basis"), ("I", "Basis")), result="Quotient",
             pre=(Condition.of("contained", "I", "K"),),
             post=(Condition.of("quotient_of", "K", "I", "v"),), run=run_quotient_basis,
             note="representatives of span K independent modulo span I"),
    Contract(name="differentials_compose_to_zero",
             params=(("C", "Complex"), ("q", "Degree"), ("r", "Degree"), ("A", "Map"), ("B", "Map")),
             result="Map",
             pre=(Condition.of("complex_differentials_vanish", "C"), Condition.of("differential_of", "C", "q", "A"),
                  Condition.of("successor", "q", "r"), Condition.of("differential_of", "C", "r", "B")),
             post=(Condition.of("zero_composition", "A", "B"),), run=run_return_A, returns="A",
             derivation={"kind": "lemma", "rule": "consecutive differentials of a chain complex compose to zero"},
             note="a supplied inference rule: d d = 0 is decided once for the complex and then reused "
                  "in every degree instead of multiplying the two matrices again"),
    Contract(name="subsystem_jacobian_kills_tangent",
             params=(("S", "System"), ("T", "System"), ("p", "Point"), ("J", "Map"), ("G", "Map"),
                     ("K", "Basis"), ("M", "Map")),
             result="Map",
             pre=(Condition.of("subsystem", "S", "T"), Condition.of("jacobian_at", "S", "p", "J"),
                  Condition.of("jacobian_at", "T", "p", "G"), Condition.of("kernel_of", "G", "K"),
                  Condition.of("same_columns", "K", "M")),
             post=(Condition.of("zero_composition", "J", "M"),), run=run_return_J, returns="J",
             derivation={"kind": "lemma",
                         "rule": "every row of the Jacobian of a subsystem is a row of the larger one, "
                                 "so it annihilates the larger tangent space"},
             note="a supplied inference rule: it lets the tangent problem reuse the acquired quotient "
                  "operation without multiplying the Jacobian by the tangent basis"),
    Contract(name="compose_maps", params=(("A", "Map"), ("B", "Map")), result="Map",
             post=(Condition.of("composition_of", "A", "B", "v"),), run=run_compose_maps),
    Contract(name="differential", params=(("C", "Complex"), ("q", "Degree")), result="Map",
             post=(Condition.of("differential_of", "C", "q", "v"),), run=run_differential),
    Contract(name="next_degree", params=(("q", "Degree"),), result="Degree",
             post=(Condition.of("successor", "q", "v"),), run=run_next_degree),
    Contract(name="basis_as_map", params=(("K", "Basis"),), result="Map",
             post=(Condition.of("same_columns", "K", "v"),), run=run_basis_as_map),
    Contract(name="jacobian", params=(("S", "System"), ("p", "Point")), result="Map",
             pre=(Condition.of("vanishes_at", "S", "p"),),
             post=(Condition.of("jacobian_at", "S", "p", "v"),), run=run_jacobian,
             note="dual numbers compute it; symbolic differentiation checks it"),
)


def base_registry(contracts=GIVEN_CONTRACTS):
    """The human-given layer: sorts, predicates, specifications and primitive contracts, nothing acquired."""
    return Registry(SORTS, PREDICATES, contracts, DEFINITIONS)
