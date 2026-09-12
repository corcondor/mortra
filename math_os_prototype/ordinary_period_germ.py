"""Transport certified initial data and screen ordinary differential operators."""

from collections import defaultdict
from math import prod

from flint import fmpq, nmod_mat
import sympy as sp


def coefficient_recurrence(operator):
    """Return exact lag polynomials from sum p_k(s) D^k, without fitting data."""
    s = sp.Symbol(operator["variable"])
    n = sp.Symbol("n")
    polys = [sp.Poly(sp.sympify(v), s, domain=sp.QQ)
             for v in operator["operator_coefficients_ascending"]]
    shift = min(i[0]-k for k, poly in enumerate(polys) for i in poly.as_dict())
    groups = defaultdict(lambda: sp.S.Zero)
    for k, poly in enumerate(polys):
        for (power,), coefficient in poly.as_dict().items():
            lag = power-k-shift
            groups[lag] += coefficient*sp.ff(n-lag, k)
    recurrence = {lag: sp.Poly(expression, n, domain=sp.QQ) for lag, expression in groups.items()}
    roots = sorted(int(root) for root in recurrence[0].ground_roots() if root.is_Integer and root >= 0)
    return {"lag_polynomials": recurrence, "shift": int(shift), "integer_roots": roots,
            "initial_count": max(roots, default=-1)+1}


def exact_germ_coefficients(recurrence, initial, count):
    if count < 0 or len(initial) < recurrence["initial_count"]:
        raise ValueError("insufficient certified initial data")
    def rational(v):
        v = sp.Rational(v)
        return fmpq(int(v.p), int(v.q))
    values = [rational(v) for v in initial[:count]]
    polynomials = {k: [rational(v) for v in poly.all_coeffs()]
                   for k, poly in recurrence["lag_polynomials"].items()}
    def evaluate(poly, n):
        result = fmpq(0)
        for coefficient in poly:
            result = result*n+coefficient
        return result
    for n in range(count):
        residual = sum((evaluate(polynomials[lag], n)*values[n-lag]
                        for lag in polynomials if 0 < lag <= n), fmpq(0))
        leading = evaluate(polynomials[0], n)
        if n < len(values):
            if leading*values[n]+residual:
                raise ArithmeticError("initial values do not satisfy the operator")
        elif not leading:
            raise ArithmeticError("a free initial coefficient is missing")
        else:
            values.append(-residual/leading)
    return values


def reduce_coefficients_mod_prime(values, prime):
    result = []
    for value in values:
        numerator, denominator = int(value.numerator), int(value.denominator)
        if denominator % prime == 0:
            raise ValueError("prime divides a coefficient denominator")
        result.append(numerator % prime * pow(denominator % prime, -1, prime) % prime)
    return result


def differential_operator_screen(values, *, prime, order, degree, holdout=24):
    """Exact rank over F_p for sum s^j D^k f; includes equations at the origin.

A full-column-rank result excludes rational operators within this rectangle
when values are reductions of exact rational coefficients with unit denominators.
A nonzero nullspace alone is a conjecture, even after unused terms agree.
"""
    if not sp.isprime(prime) or prime <= max(len(values), order) or min(order, degree) < 0:
        raise ValueError("invalid prime or operator rectangle")
    columns = (order+1)*(degree+1)
    training = len(values)-order-holdout
    if training < columns:
        raise ValueError("insufficient coefficients for the requested rectangle")
    def row(n):
        return [0 if n < j else prod(range(n-j+1, n-j+k+1))*values[n-j+k] % prime
                for k in range(order+1) for j in range(degree+1)]
    matrix = nmod_mat([row(n) for n in range(training)], prime)
    nullspace, nullity = matrix.nullspace()
    nullity = int(nullity)
    result = {"prime": prime, "maximum_derivative_order": order, "maximum_coefficient_degree": degree,
        "unknown_coefficients": columns, "training_equations": training,
        "rank_mod_prime": columns-nullity, "nullity": nullity,
        "status": "bounded_rational_operator_excluded" if not nullity else "finite_field_operator_candidates",
        "coefficient_convention": "rows k=0..order, columns s^j, ordinary D=d/ds",
        "scope": "homogeneous polynomial-coefficient differential operators in this rectangle"}
    if nullity:
        candidates = []
        for column in range(nullity):
            vector = [int(nullspace[i, column]) for i in range(columns)]
            checks = [sum(a*b for a, b in zip(row(n), vector)) % prime
                      for n in range(training, len(values)-order)]
            candidates.append({"vector": vector, "holdout_residuals": checks,
                               "holdout_passed": all(v == 0 for v in checks)})
        result["candidates"] = candidates
    return result
