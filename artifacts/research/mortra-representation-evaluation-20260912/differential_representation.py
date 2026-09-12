"""A finite-dimensional differential-action representation of a holonomic route.

A holonomic program is annihilated by an operator `sum_j c_j(x) D^j`. Reading
that operator on the Taylor coefficients turns differentiation into an index
shift, which is what makes the representation finite: the whole infinite jet
`(f, f', f'', ...)` at the expansion point is carried by a window of `order`
consecutive coefficients, and one step of the window is a matrix action

    J_{m}   = (a_{m-order}, ..., a_{m-1})
    J_{m+1} = B(m) J_m

with `B(m)` the companion matrix of the recurrence. `f^{(n)}(0) = n! a_n`, so
every derivative value at the expansion point is reachable by that action and
none of them needs the derivative primitive.

What is acquired, and what is stored: the recurrence polynomials, the index from
which they are solvable, and the seed coefficients before that index. What is
NOT stored is the answer: the record holds no derivative value, and the use-time
route reads only the record.

The derivation is checked, not asserted. `verify` unrolls the stored recurrence
and compares it against `holonomic_route_discovery.coefficients`, which reaches
the same series by an independent route (closure arithmetic on the program tree,
never the annihilating operator). A mismatch refuses the acquisition.
"""
from __future__ import annotations

import sympy as sp

from math_os_prototype.holonomic_route_discovery import (
    X, annihilator, coefficients, key, operator_coefficients)

N = sp.Symbol("n")
SCHEMA = "mortra.differential-representation.v1"


def falling(argument, power):
    """`t(t-1)...(t-power+1)`, the factor `D^power` puts on a coefficient."""
    product = sp.Integer(1)
    for offset in range(power):
        product *= (argument - offset)
    return sp.expand(product)


def _operator_terms(program):
    """The annihilating operator as `{shift: [(j, k, c_jk)]}`.

    `c_{j,k} x^k D^j` sends the coefficient `a_{i}` to index `i - j + k`, so the
    shift `j - k` is what decides which coefficient a term reaches.
    """
    grouped = {}
    cleared = operator_coefficients(annihilator(program))
    for order, entry in enumerate(cleared):
        polynomial = sp.Poly(sp.expand(entry), X)
        for (power,), value in polynomial.terms():
            if value == 0:
                continue
            grouped.setdefault(order - power, []).append(
                (order, power, sp.Rational(value)))
    if not grouped:
        raise ValueError("the annihilating operator is empty")
    return grouped


def recurrence_polynomials(program):
    """`sum_d P_d(n) a_{n-d} = 0`, valid from index `top` upward.

    Derived by reading `sum_{j,k} c_{j,k} x^k D^j f = 0` coefficientwise: the
    coefficient of `x^M` in the image is
    `sum_{j,k} c_{j,k} falling(M-k+j, j) a_{M-k+j}`, and writing `n = M + top`
    with `top` the largest shift puts the newest coefficient at index `n`.
    """
    grouped = _operator_terms(program)
    top, bottom = max(grouped), min(grouped)
    polynomials = []
    for offset in range(top - bottom + 1):
        shift = top - offset
        polynomials.append(sp.expand(sum(
            (weight * falling(N - offset, order)
             for order, _, weight in grouped.get(shift, [])), sp.S.Zero)))
    return {"polynomials": polynomials, "order": top - bottom,
            "valid_from": max(top, 0)}


def _first_solvable_index(leading, valid_from):
    """Where the recurrence can be solved for its newest coefficient.

    `leading` is a polynomial in `n`; below its largest integer root the step is
    singular and the coefficient there is not determined by the recurrence. Those
    coefficients are carried as seeds instead of being derived.
    """
    if leading == 0:
        raise ValueError("the leading recurrence coefficient vanishes identically")
    polynomial = sp.Poly(leading, N)
    if polynomial.degree() == 0:
        return valid_from
    roots = [int(root) for root in sp.solve(sp.Eq(leading, 0), N)
             if root.is_Integer]
    return max([valid_from] + [root + 1 for root in roots])


def acquire(program, *, check_terms=48):
    """Acquire the representation, and refuse it unless the check passes."""
    found = recurrence_polynomials(program)
    polynomials, order = found["polynomials"], found["order"]
    start = _first_solvable_index(polynomials[0], found["valid_from"])
    if start + order > check_terms:
        raise ValueError("not enough checked terms to seed this recurrence")
    seeds = list(coefficients(program, start))
    record = {
        "schema": SCHEMA, "program": key(program), "order": order,
        "recurrence_polynomials": [str(p) for p in polynomials],
        "first_solvable_index": start,
        "seed_coefficients": [str(s) for s in seeds],
        "seed_count": len(seeds),
        "expansion_point": 0,
        "relation": ("sum_{d=0}^{order} P_d(n) a_{n-d} = 0 for n >= "
                     "first_solvable_index, with a_i = 0 for i < 0"),
        "derivative_from_coefficient": "f^{(n)}(0) = n! * a_n",
        "scope": ("the Taylor coefficients of this program at 0; the "
                  "recurrence is exact for every index from "
                  "first_solvable_index upward")}
    check = verify(record, program, terms=check_terms)
    record["verification"] = check
    if not check["exact"]:
        raise AssertionError("the acquired recurrence disagrees with the series")
    return record


def _parsed(record):
    return ([sp.sympify(p) for p in record["recurrence_polynomials"]],
            [sp.sympify(s) for s in record["seed_coefficients"]])


def series_from_record(record, count):
    """Unroll the stored recurrence. Reads the record and nothing else.

    No derivative primitive is entered here, and neither is the series route the
    acquisition checked against: this is the representation being used.
    """
    polynomials, values = _parsed(record)
    order = record["order"]
    steps, operations = 0, 0
    while len(values) < count:
        index = len(values)
        leading = polynomials[0].subs(N, index)
        operations += 1
        total = sp.S.Zero
        for offset in range(1, order + 1):
            previous = index - offset
            if previous < 0:
                continue
            total += polynomials[offset].subs(N, index) * values[previous]
            operations += 3            # evaluate, multiply, add
        values.append(sp.cancel(-total / leading))
        operations += 1                # one exact division
        steps += 1
    return {"values": values[:count], "steps": steps, "operations": operations}


def companion_matrix(record, index):
    """`B(m)`: one step of the coefficient window, as a matrix.

    `J_{m+1} = B(m) J_m` with `J_m = (a_{m-order}, ..., a_{m-1})`. This is the
    differential action in its finite-dimensional form -- differentiation became
    an index shift, and the shift is a matrix.
    """
    polynomials, _ = _parsed(record)
    order = record["order"]
    matrix = sp.zeros(order, order)
    for row in range(order - 1):
        matrix[row, row + 1] = 1
    leading = polynomials[0].subs(N, index)
    for offset in range(1, order + 1):
        matrix[order - 1, order - offset] = sp.cancel(
            -polynomials[offset].subs(N, index) / leading)
    return matrix


def jet_by_matrix_action(record, count):
    """The coefficients again, as a product of companion matrices.

    Same numbers as `series_from_record`; this route makes the matrix action
    explicit rather than folding it into a scalar unrolling, and reports the
    multiplications it performed.
    """
    polynomials, seeds = _parsed(record)
    order = record["order"]
    start = record["first_solvable_index"]
    values = list(seeds)
    if len(values) != start:
        raise ValueError("the stored seeds do not reach the first solvable index")
    # indices below zero carry no coefficient; the convention a_i = 0 there is
    # the same one the recurrence was derived under
    window = sp.Matrix([values[index] if index >= 0 else sp.S.Zero
                        for index in range(start - order, start)])
    products = 0
    for index in range(start, count):
        window = companion_matrix(record, index) * window
        products += 1
        values.append(sp.cancel(window[order - 1]))
    return {"values": values[:count], "matrix_products": products,
            "window_dimension": order,
            # one order x order matrix against one column, per step
            "operations": products * (order * order + order * (order - 1))}


def derivative_values(record, upto):
    """`f(0), f'(0), ..., f^{(upto)}(0)`, from the representation alone."""
    unrolled = series_from_record(record, upto + 1)
    return {"values": [sp.factorial(index) * value
                       for index, value in enumerate(unrolled["values"])],
            "steps": unrolled["steps"],
            "operations": unrolled["operations"] + 2 * (upto + 1)}


def verify(record, program, *, terms=48):
    """Compare the unrolled recurrence with the independent series route."""
    unrolled = series_from_record(record, terms)["values"]
    reference = coefficients(program, terms)
    residuals = [sp.cancel(left - right)
                 for left, right in zip(unrolled, reference)]
    failures = [index for index, residual in enumerate(residuals) if residual != 0]
    return {"terms": terms, "exact": not failures, "failing_indices": failures,
            "checked_against": ("holonomic_route_discovery.coefficients, which "
                                "reaches the series through closure arithmetic "
                                "on the program tree and never through the "
                                "annihilating operator")}
