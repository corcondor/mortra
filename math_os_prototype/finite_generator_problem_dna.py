"""Exact problem discovery from a finite alphabet of linear maps.

The geometric or algebraic actions are the genes.  A word over the finite
alphabet composes those actions, while an observable supplies the quantity in
the problem.  The transfer operator acts on observables and can compress an
exponential word tree into an exact finite recurrence.

Nothing in this module contains a completed contest problem or a stored
recurrence.  All recurrences are reconstructed from the supplied matrices and
observable by exact symbolic linear algebra.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations, permutations, product
from math import comb
from typing import Callable, Hashable, Iterable, Sequence, TypeVar

import sympy as sp


Exact = sp.Expr | int
StateT = TypeVar("StateT", bound=Hashable)
GeneratorT = TypeVar("GeneratorT")


@dataclass(frozen=True)
class LinearGenerator:
    """A named exact linear action on a column state vector."""

    name: str
    rows: tuple[tuple[Exact, ...], ...]

    @classmethod
    def from_rows(
        cls, name: str, rows: Sequence[Sequence[Exact]]
    ) -> "LinearGenerator":
        return cls(name=name, rows=tuple(tuple(sp.sympify(v) for v in row) for row in rows))

    @property
    def matrix(self) -> sp.ImmutableMatrix:
        return sp.ImmutableMatrix(self.rows)


@dataclass(frozen=True)
class FiniteGeneratorSystem:
    """A typed finite alphabet acting on one exact state space."""

    name: str
    variable_names: tuple[str, ...]
    generators: tuple[LinearGenerator, ...]
    seed: tuple[Exact, ...]

    def __post_init__(self) -> None:
        dimension = len(self.variable_names)
        if dimension == 0:
            raise ValueError("a generator system needs at least one variable")
        if not self.generators:
            raise ValueError("a generator system needs at least one generator")
        if len(self.seed) != dimension:
            raise ValueError("the seed dimension does not match the state space")
        for generator in self.generators:
            if generator.matrix.shape != (dimension, dimension):
                raise ValueError(
                    f"generator {generator.name!r} has shape {generator.matrix.shape}, "
                    f"expected {(dimension, dimension)}"
                )

    @property
    def variables(self) -> tuple[sp.Symbol, ...]:
        symbols = sp.symbols(" ".join(self.variable_names))
        if isinstance(symbols, sp.Symbol):
            return (symbols,)
        return tuple(symbols)

    @property
    def seed_vector(self) -> sp.ImmutableMatrix:
        return sp.ImmutableMatrix([sp.sympify(value) for value in self.seed])


@dataclass(frozen=True)
class TransferRecurrence:
    """An exact Krylov relation for a word-aggregated observable."""

    order: int
    coefficients: tuple[sp.Expr, ...]
    characteristic_polynomial: sp.Expr
    characteristic_factorization: sp.Expr
    initial_values: tuple[sp.Expr, ...]
    observable_degree: int
    ambient_observable_dimension: int
    krylov_dimension: int
    monomial_support: tuple[tuple[int, ...], ...]
    certificate_identity: sp.Expr

    def to_dict(self) -> dict[str, object]:
        return {
            "order": self.order,
            "coefficients": [str(value) for value in self.coefficients],
            "characteristic_polynomial": str(self.characteristic_polynomial),
            "characteristic_factorization": str(self.characteristic_factorization),
            "initial_values": [str(value) for value in self.initial_values],
            "observable_degree": self.observable_degree,
            "ambient_observable_dimension": self.ambient_observable_dimension,
            "krylov_dimension": self.krylov_dimension,
            "monomial_support": [list(monomial) for monomial in self.monomial_support],
            "certificate_identity": str(self.certificate_identity),
            "certificate_passed": self.certificate_identity == 0,
        }


@dataclass(frozen=True)
class ScalarRecurrence:
    """The exact minimal recurrence after evaluating at a specific seed."""

    order: int
    coefficients: tuple[sp.Expr, ...]
    characteristic_polynomial: sp.Expr
    characteristic_factorization: sp.Expr
    initial_values: tuple[sp.Expr, ...]
    parent_transfer_order: int
    verification_residuals: tuple[sp.Expr, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "order": self.order,
            "coefficients": [str(value) for value in self.coefficients],
            "characteristic_polynomial": str(self.characteristic_polynomial),
            "characteristic_factorization": str(self.characteristic_factorization),
            "initial_values": [str(value) for value in self.initial_values],
            "parent_transfer_order": self.parent_transfer_order,
            "verification_residuals": [
                str(value) for value in self.verification_residuals
            ],
            "certificate_passed": all(value == 0 for value in self.verification_residuals),
        }


@dataclass(frozen=True)
class ExactFiniteQuotient:
    """An exact observable-preserving quotient of a finite generated action."""

    states: tuple[Hashable, ...]
    classes: tuple[tuple[Hashable, ...], ...]
    transition: tuple[tuple[int, ...], ...]
    initial_class: int
    observable_values: tuple[Hashable, ...]
    semantics: str = "aggregate"
    action_targets: tuple[tuple[int, ...], ...] | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "state_count": len(self.states),
            "class_count": len(self.classes),
            "states": list(self.states),
            "classes": [list(block) for block in self.classes],
            "transition": [list(row) for row in self.transition],
            "initial_class": self.initial_class,
            "observable_values": list(self.observable_values),
            "semantics": self.semantics,
            "action_targets": (
                [list(row) for row in self.action_targets]
                if self.action_targets is not None else None
            ),
        }


def discover_exact_finite_quotient(
    generators: Sequence[GeneratorT],
    seed: StateT,
    action: Callable[[GeneratorT, StateT], StateT],
    observable: Callable[[StateT], Hashable],
    *,
    maximum_state_count: int = 10_000,
    state_key: Callable[[StateT], object] = repr,
    semantics: str = "aggregate",
) -> ExactFiniteQuotient:
    """Close a finite action and find its coarsest exact observable quotient.

    Two states remain in one class exactly when they have the same observable
    value and the same number of generator edges into every current class.
    Refinement continues to a fixed point.  The resulting quotient preserves
    aggregate word counts for every depth, not merely for sampled depths.
    With semantics="action", refinement instead preserves each labelled
    generator separately. Only that mode certifies arbitrary chosen words.
    """

    if not generators:
        raise ValueError("at least one generator is required")
    if semantics not in {"aggregate", "action"}:
        raise ValueError("semantics must be aggregate or action")
    if maximum_state_count < 1:
        raise ValueError("maximum_state_count must be positive")
    seen = {seed}
    frontier = [seed]
    while frontier:
        state = frontier.pop()
        for generator in generators:
            image = action(generator, state)
            if image in seen:
                continue
            seen.add(image)
            if len(seen) > maximum_state_count:
                raise ValueError("generated action exceeded maximum_state_count")
            frontier.append(image)
    states = tuple(sorted(seen, key=state_key))

    observable_by_state = {state: observable(state) for state in states}
    observable_order = tuple(
        sorted(set(observable_by_state.values()), key=lambda value: repr(value))
    )
    observable_label = {value: index for index, value in enumerate(observable_order)}
    labels = {state: observable_label[observable_by_state[state]] for state in states}
    while True:
        class_count = len(set(labels.values()))
        signatures: dict[StateT, tuple[object, ...]] = {}
        for state in states:
            outgoing = [0 for _ in range(class_count)]
            for generator in generators:
                outgoing[labels[action(generator, state)]] += 1
            targets = tuple(labels[action(generator, state)] for generator in generators)
            signatures[state] = (labels[state], *(targets if semantics == "action" else outgoing))
        signature_order = {
            signature: index
            for index, signature in enumerate(sorted(set(signatures.values()), key=repr))
        }
        updated = {state: signature_order[signatures[state]] for state in states}
        old_blocks = {
            frozenset(state for state in states if labels[state] == label)
            for label in set(labels.values())
        }
        new_blocks = {
            frozenset(state for state in states if updated[state] == label)
            for label in set(updated.values())
        }
        labels = updated
        if old_blocks == new_blocks:
            break

    blocks = [
        tuple(sorted((state for state in states if labels[state] == label), key=state_key))
        for label in sorted(set(labels.values()))
    ]
    blocks.sort(
        key=lambda block: (
            repr(observable_by_state[block[0]]),
            tuple(state_key(state) for state in block),
        )
    )
    class_of = {state: index for index, block in enumerate(blocks) for state in block}
    transition = [[0 for _ in blocks] for _ in blocks]
    action_targets = [[] for _ in generators] if semantics == "action" else None
    for source_index, block in enumerate(blocks):
        signatures = []
        for state in block:
            outgoing = [0 for _ in blocks]
            for generator in generators:
                outgoing[class_of[action(generator, state)]] += 1
            signatures.append(tuple(outgoing))
        if len(set(signatures)) != 1:
            raise AssertionError("fixed-point partition is not equitable")
        for target_index, count in enumerate(signatures[0]):
            transition[target_index][source_index] = count
        if action_targets is not None:
            for generator_index, generator in enumerate(generators):
                targets = {class_of[action(generator, state)] for state in block}
                if len(targets) != 1:
                    raise AssertionError("a labelled action does not descend to the quotient")
                action_targets[generator_index].append(targets.pop())
    return ExactFiniteQuotient(
        states=states,
        classes=tuple(blocks),
        transition=tuple(tuple(row) for row in transition),
        initial_class=class_of[seed],
        observable_values=tuple(observable_by_state[block[0]] for block in blocks),
        semantics=semantics,
        action_targets=(
            tuple(tuple(row) for row in action_targets)
            if action_targets is not None else None
        ),
    )


def pullback(
    polynomial: sp.Expr,
    generator: LinearGenerator,
    variables: Sequence[sp.Symbol],
) -> sp.Expr:
    """Return ``polynomial(generator(state))`` with simultaneous substitution."""

    state = sp.ImmutableMatrix(variables)
    image = generator.matrix * state
    substitution = dict(zip(variables, image))
    return sp.expand(polynomial.subs(substitution, simultaneous=True))


def transfer(
    polynomial: sp.Expr,
    system: FiniteGeneratorSystem,
) -> sp.Expr:
    """Apply the unnormalised transfer operator to an observable."""

    variables = system.variables
    return sp.expand(
        sum(pullback(polynomial, generator, variables) for generator in system.generators)
    )


def _coefficient_column(
    polynomial: sp.Expr,
    variables: Sequence[sp.Symbol],
    monomials: Sequence[tuple[int, ...]],
) -> sp.ImmutableMatrix:
    poly = sp.Poly(polynomial, *variables)
    return sp.ImmutableMatrix([poly.coeff_monomial(monomial) for monomial in monomials])


def homogeneous_exponents(variable_count: int, degree: int) -> tuple[tuple[int, ...], ...]:
    """Enumerate exponent vectors of one homogeneous polynomial degree."""

    if variable_count < 1 or degree < 0:
        raise ValueError("variable_count must be positive and degree non-negative")
    return tuple(
        exponents
        for exponents in product(range(degree + 1), repeat=variable_count)
        if sum(exponents) == degree
    )


def full_permutation_group(variable_count: int) -> tuple[tuple[int, ...], ...]:
    return tuple(permutations(range(variable_count)))


def invariant_orbit_basis(
    variables: Sequence[sp.Symbol],
    degree: int,
    permutations_: Sequence[Sequence[int]],
) -> tuple[sp.Expr, ...]:
    """Build monomial-orbit sums for a finite coordinate permutation group."""

    variable_count = len(variables)
    identity = tuple(range(variable_count))
    normalised = {tuple(permutation) for permutation in permutations_}
    if identity not in normalised:
        raise ValueError("the supplied permutation group must contain the identity")
    if any(sorted(permutation) != list(range(variable_count)) for permutation in normalised):
        raise ValueError("each action must be a coordinate permutation")
    for left in normalised:
        for right in normalised:
            composition = tuple(left[right[index]] for index in range(variable_count))
            if composition not in normalised:
                raise ValueError("the supplied coordinate permutations are not a group")

    all_exponents = set(homogeneous_exponents(variable_count, degree))
    remaining = set(all_exponents)
    assigned: set[tuple[int, ...]] = set()
    orbits: list[tuple[tuple[int, ...], ...]] = []
    while remaining:
        representative = max(remaining)
        orbit = {
            tuple(representative[permutation[index]] for index in range(variable_count))
            for permutation in normalised
        }
        if not orbit <= all_exponents or orbit & assigned:
            raise ValueError("the supplied actions do not form disjoint monomial orbits")
        remaining -= orbit
        assigned.update(orbit)
        orbits.append(tuple(sorted(orbit, reverse=True)))

    basis: list[sp.Expr] = []
    for orbit in sorted(orbits, key=lambda values: values[0], reverse=True):
        polynomial = sum(
            sp.prod(variable**exponent for variable, exponent in zip(variables, exponents))
            for exponents in orbit
        )
        basis.append(sp.expand(polynomial))
    return tuple(basis)


def transfer_matrix_in_basis(
    system: FiniteGeneratorSystem,
    basis: Sequence[sp.Expr],
) -> sp.ImmutableMatrix:
    """Return the row-action matrix ``T(b_i) = sum_j M[i,j] b_j``."""

    if not basis:
        raise ValueError("the observable basis must be non-empty")
    variables = system.variables
    images = [transfer(item, system) for item in basis]
    monomials = _support(tuple(basis) + tuple(images), variables)
    basis_matrix = sp.Matrix.hstack(
        *(
            sp.Matrix(_coefficient_column(item, variables, monomials))
            for item in basis
        )
    )
    rows: list[list[sp.Expr]] = []
    for image in images:
        target = sp.Matrix(_coefficient_column(image, variables, monomials))
        if basis_matrix.rank() != basis_matrix.row_join(target).rank():
            raise ValueError("the supplied basis is not invariant under the transfer operator")
        solution, parameters = basis_matrix.gauss_jordan_solve(target)
        if parameters.rows:
            raise ValueError("the supplied basis is linearly dependent")
        rows.append([sp.factor(value) for value in solution])
    return sp.ImmutableMatrix(rows)


def _support(
    polynomials: Iterable[sp.Expr], variables: Sequence[sp.Symbol]
) -> tuple[tuple[int, ...], ...]:
    monomials: set[tuple[int, ...]] = set()
    for polynomial in polynomials:
        monomials.update(sp.Poly(polynomial, *variables).monoms())
    return tuple(sorted(monomials, reverse=True))


def discover_transfer_recurrence(
    system: FiniteGeneratorSystem,
    observable: sp.Expr,
    *,
    max_order: int | None = None,
) -> TransferRecurrence:
    """Discover and certify the first exact transfer recurrence.

    If ``q_0`` is the observable and ``q_(n+1) = T(q_n)``, the returned
    coefficients satisfy ``q_m = sum(c_i q_i)``.  Evaluating at the seed gives
    the same recurrence for the sum of the observable over every word of a
    given length.
    """

    variables = system.variables
    observable = sp.expand(sp.sympify(observable))
    poly = sp.Poly(observable, *variables)
    if poly.is_zero:
        raise ValueError("the observable must be nonzero")
    degree = poly.total_degree()
    ambient_dimension = comb(degree + len(variables), len(variables))
    if poly.is_homogeneous:
        ambient_dimension = comb(degree + len(variables) - 1, len(variables) - 1)
    limit = max_order if max_order is not None else ambient_dimension
    if limit < 1:
        raise ValueError("max_order must be positive")

    krylov: list[sp.Expr] = [observable]
    relation: tuple[sp.Expr, ...] | None = None
    order = 0

    for candidate_order in range(1, limit + 1):
        krylov.append(transfer(krylov[-1], system))
        monomials = _support(krylov, variables)
        previous = sp.Matrix.hstack(
            *(
                sp.Matrix(_coefficient_column(item, variables, monomials))
                for item in krylov[:-1]
            )
        )
        target = sp.Matrix(_coefficient_column(krylov[-1], variables, monomials))
        if previous.rank() != previous.row_join(target).rank():
            continue
        solution, parameters = previous.gauss_jordan_solve(target)
        if parameters.rows:
            continue
        relation = tuple(sp.factor(value) for value in solution)
        order = candidate_order
        break

    if relation is None:
        raise ValueError(
            f"no recurrence was found through order {limit}; increase max_order"
        )

    r = sp.Symbol("r")
    characteristic = sp.expand(
        r**order - sum(relation[index] * r**index for index in range(order))
    )
    identity = sp.expand(
        krylov[order]
        - sum(relation[index] * krylov[index] for index in range(order))
    )
    seed_substitution = dict(zip(variables, system.seed_vector))
    initial_values = tuple(
        sp.simplify(krylov[index].subs(seed_substitution)) for index in range(order)
    )
    monomial_support = _support(krylov[: order + 1], variables)

    return TransferRecurrence(
        order=order,
        coefficients=relation,
        characteristic_polynomial=characteristic,
        characteristic_factorization=sp.factor(characteristic),
        initial_values=initial_values,
        observable_degree=degree,
        ambient_observable_dimension=ambient_dimension,
        krylov_dimension=order,
        monomial_support=monomial_support,
        certificate_identity=identity,
    )


def recurrence_terms(
    recurrence: TransferRecurrence,
    count: int,
) -> tuple[sp.Expr, ...]:
    """Replay a certified recurrence without expanding the word tree."""

    if count < 0:
        raise ValueError("count must be non-negative")
    terms = list(recurrence.initial_values[:count])
    while len(terms) < count:
        next_value = sum(
            recurrence.coefficients[index] * terms[-recurrence.order + index]
            for index in range(recurrence.order)
        )
        terms.append(sp.simplify(next_value))
    return tuple(terms)


def minimize_seed_recurrence(
    recurrence: TransferRecurrence,
) -> ScalarRecurrence:
    """Remove transfer eigenmodes annihilated by the chosen initial state.

    The parent recurrence has order ``D``.  A proposed smaller recurrence is
    checked on ``D`` consecutive residuals.  Every residual itself satisfies
    the parent recurrence, so those exact zero initial values certify that the
    smaller relation holds for the complete infinite sequence.
    """

    parent_order = recurrence.order
    terms = recurrence_terms(recurrence, 3 * parent_order + 1)
    relation: tuple[sp.Expr, ...] | None = None
    residuals: tuple[sp.Expr, ...] = ()
    order = 0
    for candidate_order in range(1, parent_order + 1):
        equations = sp.Matrix(
            [
                [terms[offset + index] for index in range(candidate_order)]
                for offset in range(parent_order)
            ]
        )
        targets = sp.Matrix(
            [terms[offset + candidate_order] for offset in range(parent_order)]
        )
        if equations.rank() != equations.row_join(targets).rank():
            continue
        solution, parameters = equations.gauss_jordan_solve(targets)
        if parameters.rows:
            continue
        candidate = tuple(sp.factor(value) for value in solution)
        candidate_residuals = tuple(
            sp.simplify(
                terms[offset + candidate_order]
                - sum(
                    candidate[index] * terms[offset + index]
                    for index in range(candidate_order)
                )
            )
            for offset in range(parent_order)
        )
        if any(value != 0 for value in candidate_residuals):
            continue
        relation = candidate
        residuals = candidate_residuals
        order = candidate_order
        break

    if relation is None:
        raise AssertionError("the parent recurrence must remain a valid scalar recurrence")
    r = sp.Symbol("r")
    characteristic = sp.expand(
        r**order - sum(relation[index] * r**index for index in range(order))
    )
    return ScalarRecurrence(
        order=order,
        coefficients=relation,
        characteristic_polynomial=characteristic,
        characteristic_factorization=sp.factor(characteristic),
        initial_values=tuple(terms[:order]),
        parent_transfer_order=parent_order,
        verification_residuals=residuals,
    )


def discover_linear_observation_recurrence(
    transition: sp.MatrixBase,
    initial_state: Sequence[Exact] | sp.MatrixBase,
    observation: Sequence[Exact] | sp.MatrixBase,
) -> ScalarRecurrence:
    """Find the exact scalar recurrence of ``q M^n v``.

    ``transition`` is an exact square matrix, ``initial_state`` is a column
    state, and ``observation`` is a row functional.  The algorithm generates
    only ``O(d)`` exact terms for a ``d``-dimensional system, finds the first
    valid relation, and certifies it on ``d`` consecutive residuals.  Every
    residual then obeys the characteristic recurrence of ``transition``, so
    these zero values prove the scalar relation for all subsequent indices.
    """

    matrix = sp.Matrix(transition)
    if matrix.rows != matrix.cols or matrix.rows == 0:
        raise ValueError("transition must be a non-empty square matrix")
    dimension = matrix.rows
    state = sp.Matrix(initial_state)
    if state.shape == (1, dimension):
        state = state.T
    if state.shape != (dimension, 1):
        raise ValueError("initial_state must have one entry per transition row")
    functional = sp.Matrix(observation)
    if functional.shape == (dimension, 1):
        functional = functional.T
    if functional.shape != (1, dimension):
        raise ValueError("observation must have one entry per transition row")

    values: list[sp.Expr] = []
    current = state
    for _ in range(3 * dimension + 1):
        values.append(sp.simplify((functional * current)[0]))
        current = matrix * current

    return _recurrence_from_linear_lift_samples(values, dimension)


def _recurrence_from_linear_lift_samples(values: Sequence[sp.Expr], dimension: int) -> ScalarRecurrence:
    """Internal: the caller must already establish a dimension-D linear lift."""
    if dimension < 1 or len(values) < 3 * dimension + 1:
        raise ValueError("insufficient terms for the supplied exact linear lift dimension")
    rational_values: list[Fraction] = []
    for value in values:
        rational = sp.cancel(value)
        if rational.is_Rational is not True:
            raise ValueError("linear observation recurrence currently requires rational data")
        rational_values.append(Fraction(int(rational.p), int(rational.q)))

    connection = [Fraction(1)]
    previous = [Fraction(1)]
    order = 0
    shift = 1
    previous_discrepancy = Fraction(1)
    for index, value in enumerate(rational_values):
        discrepancy = value
        for lag in range(1, order + 1):
            discrepancy += connection[lag] * rational_values[index - lag]
        if discrepancy == 0:
            shift += 1
            continue
        old_connection = connection[:]
        multiplier = -discrepancy / previous_discrepancy
        required = len(previous) + shift
        if len(connection) < required:
            connection.extend(Fraction(0) for _ in range(required - len(connection)))
        for previous_index, previous_value in enumerate(previous):
            connection[previous_index + shift] += multiplier * previous_value
        if 2 * order <= index:
            order = index + 1 - order
            previous = old_connection
            previous_discrepancy = discrepancy
            shift = 1
        else:
            shift += 1
    if order < 1 or order > dimension:
        raise ValueError("the observed sequence is zero or exceeds the state dimension")
    connection.extend(Fraction(0) for _ in range(order + 1 - len(connection)))
    relation = tuple(
        sp.Rational(
            -connection[order - index].numerator,
            connection[order - index].denominator,
        )
        for index in range(order)
    )
    residuals = tuple(
        sp.simplify(
            values[offset + order]
            - sum(
                relation[index] * values[offset + index]
                for index in range(order)
            )
        )
        for offset in range(dimension)
    )
    if any(residuals):
        raise AssertionError("Berlekamp-Massey relation failed exact residual checks")

    r = sp.Symbol("r")
    characteristic = sp.expand(
        r**order - sum(relation[index] * r**index for index in range(order))
    )
    return ScalarRecurrence(
        order=order,
        coefficients=relation,
        characteristic_polynomial=characteristic,
        characteristic_factorization=sp.factor(characteristic),
        initial_values=tuple(values[:order]),
        parent_transfer_order=dimension,
        verification_residuals=residuals,
    )


def certify_scalar_recurrence_from_linear_lift_samples(
    values: Sequence[sp.Expr],
    dimension: int,
) -> ScalarRecurrence:
    """Certify a scalar recurrence from samples of a known linear lift.

    The caller must have independently established that the samples are an
    observation of a fixed exact linear system of dimension ``dimension``.
    The certificate checks enough consecutive residuals for the relation to
    hold for every later index by Cayley-Hamilton.
    """

    return _recurrence_from_linear_lift_samples(values, dimension)


def discover_exact_linear_observation_recurrence(
    transition: sp.MatrixBase,
    initial_state: Sequence[Exact] | sp.MatrixBase,
    observation: Sequence[Exact] | sp.MatrixBase,
) -> ScalarRecurrence:
    """Find the first scalar recurrence over an exact algebraic field.

    This is the algebraic-number counterpart of
    :func:`discover_linear_observation_recurrence`.  It deliberately uses
    exact linear systems instead of numerical eigenvalue fitting, so rows
    containing radicals or roots of unity remain certifiable.
    """

    matrix = sp.Matrix(transition)
    if matrix.rows != matrix.cols or matrix.rows == 0:
        raise ValueError("transition must be a non-empty square matrix")
    dimension = matrix.rows
    state = sp.Matrix(initial_state)
    if state.shape == (1, dimension):
        state = state.T
    if state.shape != (dimension, 1):
        raise ValueError("initial_state must have one entry per transition row")
    functional = sp.Matrix(observation)
    if functional.shape == (dimension, 1):
        functional = functional.T
    if functional.shape != (1, dimension):
        raise ValueError("observation must have one entry per transition row")
    if matrix.free_symbols or state.free_symbols or functional.free_symbols:
        raise ValueError("transition, state, and observation must contain exact constants")

    values: list[sp.Expr] = []
    current = state
    for _ in range(3 * dimension + 1):
        values.append(sp.expand_func(sp.trigsimp((functional * current)[0])))
        current = matrix * current

    relation: tuple[sp.Expr, ...] | None = None
    residuals: tuple[sp.Expr, ...] = ()
    order = 0
    for candidate_order in range(1, dimension + 1):
        coefficient_matrix = sp.Matrix(
            [
                [values[offset + index] for index in range(candidate_order)]
                for offset in range(dimension)
            ]
        )
        right_hand_side = sp.Matrix(
            [values[offset + candidate_order] for offset in range(dimension)]
        )
        solution_set = sp.linsolve((coefficient_matrix, right_hand_side))
        if solution_set == sp.EmptySet:
            continue
        solution = tuple(next(iter(solution_set)))
        if any(value.free_symbols for value in solution):
            continue
        candidate = tuple(sp.simplify(value) for value in solution)
        candidate_residuals = tuple(
            sp.simplify(
                values[offset + candidate_order]
                - sum(
                    candidate[index] * values[offset + index]
                    for index in range(candidate_order)
                )
            )
            for offset in range(dimension)
        )
        if any(value != 0 for value in candidate_residuals):
            continue
        relation = candidate
        residuals = candidate_residuals
        order = candidate_order
        break

    if relation is None:
        raise ValueError("the observed exact sequence has no certified recurrence")
    r = sp.Symbol("r")
    characteristic = sp.expand(
        r**order - sum(relation[index] * r**index for index in range(order))
    )
    return ScalarRecurrence(
        order=order,
        coefficients=relation,
        characteristic_polynomial=characteristic,
        characteristic_factorization=sp.factor(characteristic),
        initial_values=tuple(values[:order]),
        parent_transfer_order=dimension,
        verification_residuals=residuals,
    )


def direct_word_sum(
    system: FiniteGeneratorSystem,
    observable: sp.Expr,
    depth: int,
) -> sp.Expr:
    """Expand all words at a small depth for an independent exact replay."""

    if depth < 0:
        raise ValueError("depth must be non-negative")
    states = [system.seed_vector]
    for _ in range(depth):
        states = [
            generator.matrix * state
            for state in states
            for generator in system.generators
        ]
    variables = system.variables
    return sp.simplify(
        sum(observable.subs(dict(zip(variables, state))) for state in states)
    )


def distinct_orbit_counts(
    system: FiniteGeneratorSystem,
    max_depth: int,
) -> tuple[int, ...]:
    """Count exact endpoint states at every word length."""

    if max_depth < 0:
        raise ValueError("max_depth must be non-negative")
    states = {tuple(system.seed_vector)}
    counts = [1]
    for _ in range(max_depth):
        states = {
            tuple(sp.simplify(value) for value in generator.matrix * sp.Matrix(state))
            for state in states
            for generator in system.generators
        }
        counts.append(len(states))
    return tuple(counts)


def pairwise_noncommuting_count(system: FiniteGeneratorSystem) -> int:
    return sum(
        left.matrix * right.matrix != right.matrix * left.matrix
        for left, right in combinations(system.generators, 2)
    )


def unipotent_log(generator: LinearGenerator) -> sp.ImmutableMatrix:
    """Return the exact finite logarithm when ``M-I`` is nilpotent."""

    matrix = generator.matrix
    identity = sp.eye(matrix.rows)
    nilpotent = matrix - identity
    power = nilpotent
    result = sp.zeros(matrix.rows)
    for degree in range(1, matrix.rows + 1):
        result += (-1) ** (degree + 1) * power / degree
        power = power * nilpotent
        if power.is_zero_matrix:
            return sp.ImmutableMatrix(result)
    raise ValueError(f"generator {generator.name!r} is not unipotent")


def lie_bracket(left: sp.MatrixBase, right: sp.MatrixBase) -> sp.ImmutableMatrix:
    return sp.ImmutableMatrix(left * right - right * left)


def matrix_span_rank(matrices: Sequence[sp.MatrixBase]) -> int:
    if not matrices:
        return 0
    columns = [sp.Matrix(matrix).reshape(matrix.rows * matrix.cols, 1) for matrix in matrices]
    return sp.Matrix.hstack(*columns).rank()


def structural_metrics(
    system: FiniteGeneratorSystem,
    observable: sp.Expr,
    *,
    word_depth: int = 10,
) -> dict[str, object]:
    """Measure structural diversity and exact compression without fake steps."""

    recurrence = discover_transfer_recurrence(system, observable)
    orbit_counts = distinct_orbit_counts(system, word_depth)
    raw_word_count = len(system.generators) ** word_depth
    return {
        "generator_count": len(system.generators),
        "pairwise_noncommuting_count": pairwise_noncommuting_count(system),
        "word_depth": word_depth,
        "raw_word_count": raw_word_count,
        "distinct_endpoint_count": orbit_counts[-1],
        "endpoint_collision_count": raw_word_count - orbit_counts[-1],
        "orbit_counts": list(orbit_counts),
        "recurrence": recurrence.to_dict(),
        "word_to_recurrence_compression": sp.Rational(raw_word_count, recurrence.order),
    }


def discover_action_observable_basis(
    system: FiniteGeneratorSystem,
    observables: Sequence[sp.Expr],
    *,
    maximum_dimension: int = 64,
) -> dict[str, object]:
    """Find the smallest linear observable space closed under every generator.

    Closure is a polynomial identity, not a sequence fit. The result is minimal
    among linear spaces containing the supplied observations; it need not be a
    globally minimal nonlinear state representation.
    """
    if maximum_dimension < 1 or not observables:
        raise ValueError("positive dimension and nonempty observations required")
    variables = system.variables
    basis: list[sp.Expr] = []

    def add_if_independent(expression: sp.Expr) -> None:
        expression = sp.expand(sp.sympify(expression))
        if expression.has(sp.Float):
            raise ValueError("exact observations are required")
        polynomial = sp.Poly(expression, *variables)
        if any(c.is_algebraic is not True for c in polynomial.coeffs()):
            raise ValueError("fixed algebraic observation coefficients are required")
        if expression == 0:
            return
        monomials = _support([*basis, expression], variables)
        columns = [sp.Matrix(_coefficient_column(p, variables, monomials)) for p in basis]
        candidate = sp.Matrix(_coefficient_column(expression, variables, monomials))
        if columns and sp.Matrix.hstack(*columns, candidate).rank() == len(basis):
            return
        if len(basis) >= maximum_dimension:
            raise ValueError("action closure exceeded maximum_dimension")
        basis.append(expression)

    for generator in system.generators:
        if generator.matrix.has(sp.Float) or any(c.is_algebraic is not True for c in generator.matrix):
            raise ValueError("fixed exact algebraic generator coefficients are required")
    for observation in observables:
        add_if_independent(observation)
    if not basis:
        raise ValueError("at least one nonzero observation is required")
    cursor = 0
    while cursor < len(basis):
        expression = basis[cursor]
        for generator in system.generators:
            add_if_independent(pullback(expression, generator, variables))
        cursor += 1
    matrices, residuals = [], []
    for generator in system.generators:
        single = FiniteGeneratorSystem(
            system.name, system.variable_names, (generator,), system.seed
        )
        matrix = transfer_matrix_in_basis(single, basis)
        residual = sp.Matrix([pullback(p, generator, variables) for p in basis]) - matrix * sp.Matrix(basis)
        checked = tuple(sp.simplify(r) for r in residual)
        if any(r != 0 for r in checked):
            raise AssertionError("per-generator polynomial identity failed")
        matrices.append(matrix)
        residuals.append(checked)
    return {
        "basis": tuple(basis),
        "action_matrices": tuple(matrices),
        "generator_names": tuple(g.name for g in system.generators),
        "identity_residuals": tuple(residuals),
        "certificate_passed": True,
        "scope": "all finite words; linear closure of supplied polynomial observations",
    }


def binary_shear_system() -> FiniteGeneratorSystem:
    """The two positive elementary shears discussed in the research notes."""

    return FiniteGeneratorSystem(
        name="binary_positive_shears",
        variable_names=("a", "b"),
        generators=(
            LinearGenerator.from_rows("R", ((1, 1), (0, 1))),
            LinearGenerator.from_rows("L", ((1, 0), (1, 1))),
        ),
        seed=(1, 1),
    )


def signed_four_shear_system() -> FiniteGeneratorSystem:
    """Four distinct time-one flows generated by ``+/-E`` and ``+/-F``."""

    return FiniteGeneratorSystem(
        name="signed_four_shears",
        variable_names=("a", "b"),
        generators=(
            LinearGenerator.from_rows("A", ((1, 1), (0, 1))),
            LinearGenerator.from_rows("C", ((1, -1), (0, 1))),
            LinearGenerator.from_rows("G", ((1, 0), (1, 1))),
            LinearGenerator.from_rows("T", ((1, 0), (-1, 1))),
        ),
        seed=(1, 1),
    )
