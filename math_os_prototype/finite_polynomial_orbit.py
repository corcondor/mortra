"""Exact recurrence certificates for eventually periodic polynomial updates.

A fitted recurrence is only a proposal.  Certification first closes monomials
under every periodic update.  The resulting finite linear lift implies, by
Cayley-Hamilton, that D zero residuals in each phase prove all later residuals
zero.  No assumption about a numerical fit or an asymptotic approximation is
used.  Closure may fail within the explicit resource bounds.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
from typing import Iterable, Sequence

import sympy as sp

Powers = tuple[int, ...]
Polynomial = dict[Powers, Fraction]


def _exact(value: object) -> Fraction:
    expression = sp.sympify(value)
    if expression.has(sp.Float) or expression.is_Rational is not True:
        raise ValueError("only exact rational coefficients and initial values are supported")
    return Fraction(int(expression.p), int(expression.q))


def _polynomial(expression: sp.Expr, variables: Sequence[sp.Symbol]) -> Polynomial:
    expression = sp.sympify(expression)
    if expression.has(sp.Float) or expression.free_symbols - set(variables):
        raise ValueError("polynomial must use declared variables and exact coefficients")
    return {
        powers: _exact(coefficient)
        for powers, coefficient in sp.Poly(expression, *variables, domain=sp.QQ).terms()
        if coefficient
    }


def _multiply(left: Polynomial, right: Polynomial, maximum_terms: int) -> Polynomial:
    result: Polynomial = {}
    for first, a in left.items():
        for second, b in right.items():
            powers = tuple(x + y for x, y in zip(first, second, strict=True))
            result[powers] = result.get(powers, Fraction(0)) + a * b
            if not result[powers]:
                del result[powers]
            if len(result) > maximum_terms:
                raise ValueError("polynomial term budget exceeded")
    return result


def _evaluate(polynomial: Polynomial, state: Sequence[Fraction]) -> Fraction:
    result = Fraction(0)
    for powers, coefficient in polynomial.items():
        term = coefficient
        for index, exponent in enumerate(powers):
            if exponent:
                term *= state[index] ** exponent
        result += term
    return result


def _serialized(polynomial: Polynomial) -> list[dict]:
    return [
        {"powers": list(powers), "coefficient": str(coefficient)}
        for powers, coefficient in sorted(polynomial.items())
    ]


@dataclass(eq=False)
class PolynomialOrbit:
    variables: tuple[sp.Symbol, ...]
    updates: tuple[tuple[sp.Expr, ...], ...]
    initial: tuple[Fraction, ...]
    cycle_start: int

    def __post_init__(self) -> None:
        if not self.variables or len(set(self.variables)) != len(self.variables):
            raise ValueError("variables must be nonempty and distinct")
        if not self.updates or not 0 <= self.cycle_start < len(self.updates):
            raise ValueError("cycle_start must select an update in the schedule")
        if len(self.initial) != len(self.variables):
            raise ValueError("initial state dimension differs from variables")
        if any(len(update) != len(self.variables) for update in self.updates):
            raise ValueError("update dimension differs from variables")
        self.initial = tuple(_exact(value) for value in self.initial)
        self.compiled = tuple(
            tuple(_polynomial(value, self.variables) for value in update)
            for update in self.updates
        )

    @property
    def period(self) -> int:
        return len(self.updates) - self.cycle_start

    def phase(self, generation: int) -> int:
        if generation < 0:
            raise ValueError("generation must be nonnegative")
        if generation < self.cycle_start:
            return generation
        return self.cycle_start + (generation - self.cycle_start) % self.period

    def states(self, maximum_generation: int) -> Iterable[tuple[Fraction, ...]]:
        if maximum_generation < 0:
            raise ValueError("maximum_generation must be nonnegative")
        state = self.initial
        yield state
        for generation in range(maximum_generation):
            state = tuple(_evaluate(poly, state) for poly in self.compiled[self.phase(generation)])
            yield state

    def observations(self, expression: sp.Expr, maximum_generation: int) -> tuple[Fraction, ...]:
        polynomial = _polynomial(expression, self.variables)
        return tuple(_evaluate(polynomial, state) for state in self.states(maximum_generation))

    @lru_cache(maxsize=16384)
    def monomial_pullback(self, powers: Powers, phase: int, maximum_terms: int) -> tuple:
        result = {(0,) * len(self.variables): Fraction(1)}
        for index, exponent in enumerate(powers):
            for _ in range(exponent):
                result = _multiply(result, self.compiled[phase][index], maximum_terms)
        return tuple(sorted(result.items()))

    def to_dict(self) -> dict:
        return {
            "variables": [str(variable) for variable in self.variables],
            "initial": [str(value) for value in self.initial],
            "cycle_start": self.cycle_start,
            "period": self.period,
            "updates": [[_serialized(poly) for poly in update] for update in self.compiled],
        }


def monomial_closure(
    model: PolynomialOrbit,
    expression: sp.Expr,
    *,
    maximum_dimension: int = 2048,
    maximum_degree: int = 8,
    maximum_terms: int = 20000,
) -> tuple[Powers, ...]:
    """Find an exact monomial span, not necessarily a minimal linear span."""
    if min(maximum_dimension, maximum_terms) < 1 or maximum_degree < 0:
        raise ValueError("closure budgets must be positive (degree may be zero)")
    basis = set(_polynomial(expression, model.variables))
    # The zero observation still has a one-dimensional constant lift.
    if not basis:
        basis.add((0,) * len(model.variables))
    pending = list(sorted(basis))
    cursor = 0
    while cursor < len(pending):
        if len(basis) > maximum_dimension:
            raise ValueError("monomial closure dimension budget exceeded")
        powers = pending[cursor]
        cursor += 1
        if sum(powers) > maximum_degree:
            raise ValueError("monomial closure degree budget exceeded")
        for phase in range(model.cycle_start, len(model.updates)):
            for target, _coefficient in model.monomial_pullback(powers, phase, maximum_terms):
                if target not in basis:
                    basis.add(target)
                    pending.append(target)
    return tuple(sorted(basis))


def certify_recurrence(
    model: PolynomialOrbit,
    expression: sp.Expr,
    coefficients: Sequence[object],
    *,
    start_index: int = 0,
    maximum_dimension: int = 2048,
    maximum_degree: int = 8,
    maximum_terms: int = 20000,
    maximum_checks: int = 20000,
) -> dict:
    """Certify the supplied proposal against the compiled polynomial program."""
    relation = tuple(_exact(coefficient) for coefficient in coefficients)
    if not relation or start_index < 0:
        raise ValueError("recurrence needs coefficients and a nonnegative start")
    basis = monomial_closure(
        model, expression, maximum_dimension=maximum_dimension,
        maximum_degree=maximum_degree, maximum_terms=maximum_terms,
    )
    dimension = len(basis)
    periodic_start = max(start_index, model.cycle_start)
    last_residual = periodic_start + model.period * dimension - 1
    checks = last_residual - start_index + 1
    if checks > maximum_checks:
        raise ValueError("exact recurrence certificate check budget exceeded")
    values = model.observations(expression, last_residual + len(relation))
    failures = []
    for index in range(start_index, last_residual + 1):
        residual = values[index + len(relation)] - sum(
            (coefficient * values[index + offset] for offset, coefficient in enumerate(relation)),
            Fraction(0),
        )
        if residual:
            failures.append({"generation": index, "residual": str(residual)})
            if len(failures) == 8:
                break
    index_by_powers = {powers: index for index, powers in enumerate(basis)}
    matrices = []
    for phase in range(model.cycle_start, len(model.updates)):
        entries = []
        for row, powers in enumerate(basis):
            for target, coefficient in model.monomial_pullback(powers, phase, maximum_terms):
                entries.append([row, index_by_powers[target], str(coefficient)])
        matrices.append({"phase": phase, "entries": entries})
    return {
        "schema": "mortra.polynomial-recurrence-certificate.v1",
        "passed": not failures,
        "scope": "all_generations_from_start" if not failures else "rejected",
        "start_index": start_index,
        "coefficients": [str(value) for value in relation],
        "observation": _serialized(_polynomial(expression, model.variables)),
        "lift_dimension": dimension,
        "basis": [list(powers) for powers in basis],
        "period": model.period,
        "periodic_start": periodic_start,
        "residual_count_required": checks,
        "residual_last_index": last_residual,
        "counterexamples": failures,
        "periodic_lift_matrices": matrices,
        "argument": "Exact polynomial closure; D residuals per phase; Cayley-Hamilton.",
        "not_claimed": ["minimal_recurrence", "physical_foldability", "problem_difficulty"],
    }


def discover_polynomial_observation_span(
    model: PolynomialOrbit,
    expression: sp.Expr,
    *,
    maximum_dimension: int = 128,
    maximum_degree: int = 8,
    maximum_terms: int = 20000,
) -> dict:
    """Close the polynomial linear span, retaining exact per-phase identities.

    Unlike monomial closure, row reduction retains combinations rather than
    every constituent monomial.  Each new row is a consequence of a pullback,
    so closure produces the least invariant linear span containing the input.
    This is not a globally minimal nonlinear representation or a hardness score.
    """
    if min(maximum_dimension, maximum_terms) < 1 or maximum_degree < 0:
        raise ValueError("invalid polynomial span budget")
    basis: list[Polynomial] = []
    pivots: list[Powers] = []

    def reduce(polynomial):
        remainder = polynomial.copy()
        coordinates = []
        for pivot, row in zip(pivots, basis, strict=True):
            coefficient = remainder.get(pivot, Fraction(0))
            coordinates.append(coefficient)
            for powers, value in row.items():
                if coefficient:
                    remainder[powers] = remainder.get(powers, Fraction(0)) - coefficient * value
                    if not remainder[powers]:
                        del remainder[powers]
        return remainder, coordinates

    def include(polynomial):
        remainder, _ = reduce(polynomial)
        if not remainder:
            return
        if len(basis) >= maximum_dimension:
            raise ValueError("polynomial observation span dimension budget exceeded")
        if len(remainder) > maximum_terms or max(map(sum, remainder)) > maximum_degree:
            raise ValueError("polynomial observation span degree or term budget exceeded")
        pivot = min(remainder)
        coefficient = remainder[pivot]
        basis.append({powers: value / coefficient for powers, value in remainder.items()})
        pivots.append(pivot)

    def pullback(polynomial, phase):
        result = {}
        for powers, coefficient in polynomial.items():
            for target, value in model.monomial_pullback(powers, phase, maximum_terms):
                result[target] = result.get(target, Fraction(0)) + coefficient * value
                if not result[target]:
                    del result[target]
                if len(result) > maximum_terms:
                    raise ValueError("polynomial pullback term budget exceeded")
        return result

    observation = _polynomial(expression, model.variables)
    include(observation or {(0,) * len(model.variables): Fraction(1)})
    cursor = 0
    while cursor < len(basis):
        polynomial = basis[cursor]
        cursor += 1
        for phase in range(model.cycle_start, len(model.updates)):
            include(pullback(polynomial, phase))
    matrices = []
    for phase in range(model.cycle_start, len(model.updates)):
        rows = []
        for polynomial in basis:
            residual, coordinates = reduce(pullback(polynomial, phase))
            if residual:
                raise AssertionError("polynomial span is not closed")
            rows.append(tuple(coordinates))
        matrices.append(tuple(rows))
    residual, functional = reduce(observation)
    if residual:
        raise AssertionError("observation cannot be recovered from span")
    initial_state = next(
        state for index, state in enumerate(model.states(model.cycle_start))
        if index == model.cycle_start
    )
    return {
        "schema": "mortra.polynomial-action-span.v1",
        "basis": [_serialized(polynomial) for polynomial in basis],
        "dimension": len(basis),
        "action_matrices": [
            [[str(value) for value in row] for row in matrix] for matrix in matrices
        ],
        "observation": [str(value) for value in functional],
        "initial_at_cycle_start": [str(_evaluate(polynomial, initial_state)) for polynomial in basis],
        "cycle_start": model.cycle_start,
        "period": model.period,
        "identity_count": model.period * len(basis),
        "all_identity_residuals_zero": True,
        "minimality_scope": (
            "linear polynomial span under listed periodic update maps" if observation
            else "one-dimensional constant convention for the zero observation"
        ),
    }


def derive_periodic_recurrence(
    model: PolynomialOrbit,
    expression: sp.Expr,
    *,
    maximum_dimension: int = 128,
) -> dict:
    """Derive a recurrence from a proven lift, without a fixed sample-fit window."""
    from math_os_prototype.finite_generator_problem_dna import _recurrence_from_linear_lift_samples

    span = discover_polynomial_observation_span(
        model, expression, maximum_dimension=maximum_dimension,
    )
    dimension = span["dimension"]
    matrices = [sp.Matrix([[sp.Rational(value) for value in row] for row in matrix])
                for matrix in span["action_matrices"]]
    observation = sp.Matrix([[sp.Rational(value) for value in span["observation"]]])
    initial = sp.Matrix([sp.Rational(value) for value in span["initial_at_cycle_start"]])
    product = sp.eye(dimension)
    phase_observations = []
    for matrix in matrices:
        phase_observations.append(observation * product)
        product = matrix * product
    # Reuse one matrix orbit for every phase, rather than recomputing it p times.
    phase_values = [[] for _ in matrices]
    current = initial
    for _ in range(3 * dimension + 1):
        for values, functional in zip(phase_values, phase_observations, strict=True):
            values.append((functional * current)[0])
        current = product * current
    r = sp.Symbol("r")
    common = sp.Poly(1, r, domain=sp.QQ)
    phase_certificates = []
    for phase, values in enumerate(phase_values):
        if all(value == 0 for value in values[:dimension]):
            phase_certificates.append({
                "phase": phase, "zero_sequence": True, "zero_residual_count": dimension,
            })
            continue
        recurrence = _recurrence_from_linear_lift_samples(values, dimension)
        common = sp.lcm(common, sp.Poly(recurrence.characteristic_polynomial, r, domain=sp.QQ))
        phase_certificates.append({
            "phase": phase, "coefficients": [str(value) for value in recurrence.coefficients],
            "initial_values": [str(value) for value in recurrence.initial_values],
            "zero_residual_count": len(recurrence.verification_residuals),
        })
    # The identically zero observation needs no nontrivial annihilator.
    if common.degree() == 0:
        coefficients = [Fraction(0)]
    else:
        degree = model.period * common.degree()
        coefficients = [Fraction(0)] * degree
        for (power,), coefficient in common.terms():
            if power != common.degree():
                coefficients[power * model.period] = -_exact(coefficient)
    return {
        "schema": "mortra.derived-periodic-recurrence.v1",
        "passed": True,
        "scope": "all_generations_from_start",
        "lift_dimension": dimension,
        "period": model.period,
        "start_index": model.cycle_start,
        "coefficients": [str(value) for value in coefficients],
        "order": len(coefficients),
        "span": span,
        "phase_certificates": phase_certificates,
        "common_phase_polynomial": str(common.as_expr()),
        "proof": "Exact polynomial action identities; phase monodromy; certified scalar recurrences; LCM.",
        "minimal_scalar_order_claimed": False,
        "physical_foldability_claimed": False,
    }
