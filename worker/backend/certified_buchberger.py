"""元の生成元まで遡れる、有界なBuchberger計算。"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from itertools import combinations
from typing import Iterable

import sympy as sp


@dataclass(frozen=True)
class PolynomialIdealWitness:
    """多項式が初期生成元の線形結合であることの厳密な証明書。"""

    polynomial: str
    multipliers: tuple[str, ...]
    replay_residual: str
    replayed: bool
    certificate_sha256: str


@dataclass(frozen=True)
class CertifiedBuchbergerStep:
    left_basis_index: int
    right_basis_index: int
    input_basis_size: int
    s_polynomial: str
    remainder: str
    reduction_quotients: tuple[str, ...]
    output_basis_index: int | None
    deferred_reason: str | None
    witness: PolynomialIdealWitness | None
    replayed: bool


@dataclass(frozen=True)
class CertifiedBuchbergerResult:
    initial_polynomials: tuple[str, ...]
    variables: tuple[str, ...]
    basis: tuple[PolynomialIdealWitness, ...]
    steps: tuple[CertifiedBuchbergerStep, ...]
    processed_pair_count: int
    product_criterion_pair_count: int
    zero_remainder_pair_count: int
    deferred_pair_count: int
    stopped_reason: str | None
    groebner_complete: bool
    all_witnesses_replayed: bool


@dataclass(frozen=True)
class CertifiedIdealMembership:
    goal_polynomial: str
    remainder: str
    initial_multipliers: tuple[str, ...]
    replay_residual: str
    proved: bool
    replayed: bool
    certificate_sha256: str


@dataclass(frozen=True)
class PolynomialDAGIdentity:
    """直前の基底要素だけを参照し、平坦化を避けた証明辺。"""

    kind: str
    polynomial: str
    premises: tuple[str, ...]
    multipliers: tuple[str, ...]
    replay_residual: str
    replayed: bool
    certificate_sha256: str


@dataclass(frozen=True)
class CertifiedBuchbergerDAGStep:
    left_basis_index: int
    right_basis_index: int
    input_basis_size: int
    remainder: str
    output_basis_index: int | None
    deferred_reason: str | None
    identity: PolynomialDAGIdentity | None
    replayed: bool


@dataclass(frozen=True)
class CertifiedBuchbergerDAGResult:
    initial_polynomials: tuple[str, ...]
    variables: tuple[str, ...]
    basis_polynomials: tuple[str, ...]
    identities: tuple[PolynomialDAGIdentity, ...]
    steps: tuple[CertifiedBuchbergerDAGStep, ...]
    processed_pair_count: int
    product_criterion_pair_count: int
    zero_remainder_pair_count: int
    deferred_pair_count: int
    stopped_reason: str | None
    groebner_complete: bool
    all_identities_replayed: bool


@dataclass(frozen=True)
class CertifiedDAGIdealMembership:
    goal_polynomial: str
    remainder: str
    premises: tuple[str, ...]
    multipliers: tuple[str, ...]
    replay_residual: str
    proved: bool
    replayed: bool
    certificate_sha256: str


@dataclass(frozen=True)
class _BasisItem:
    polynomial: sp.Poly
    multipliers: tuple[sp.Poly, ...]


def _zero(variables: tuple[sp.Symbol, ...]) -> sp.Poly:
    return sp.Poly(0, *variables, domain=sp.QQ)


def _as_poly(expression: sp.Expr, variables: tuple[sp.Symbol, ...]) -> sp.Poly:
    return sp.Poly(expression, *variables, domain=sp.QQ)


def _monomial(
    coefficient: sp.Expr,
    variables: tuple[sp.Symbol, ...],
    powers: tuple[int, ...],
) -> sp.Poly:
    expression = coefficient * sp.prod(
        variable**power for variable, power in zip(variables, powers)
    )
    return _as_poly(expression, variables)


def _leading_term(polynomial: sp.Poly) -> tuple[tuple[int, ...], sp.Expr]:
    terms = polynomial.terms(order="lex")
    if not terms:
        raise ValueError("zero polynomial has no leading term")
    return terms[0]


def _divides(left: tuple[int, ...], right: tuple[int, ...]) -> bool:
    return all(a <= b for a, b in zip(left, right))


def _normalize(item: _BasisItem) -> _BasisItem:
    if item.polynomial.is_zero:
        return item
    _, leading_coefficient = _leading_term(item.polynomial)
    scale = sp.cancel(1 / leading_coefficient)
    return _BasisItem(
        item.polynomial.mul_ground(scale),
        tuple(value.mul_ground(scale) for value in item.multipliers),
    )


def _replay_residual(
    item: _BasisItem,
    initial: tuple[sp.Poly, ...],
) -> sp.Poly:
    residual = item.polynomial
    for multiplier, polynomial in zip(item.multipliers, initial):
        residual -= multiplier * polynomial
    return residual


def _expression(polynomial: sp.Poly) -> sp.Expr:
    return polynomial.as_expr()


def _expressions(polynomials: Iterable[sp.Poly]) -> tuple[str, ...]:
    return tuple(sp.sstr(_expression(item)) for item in polynomials)


def _witness(
    item: _BasisItem,
    initial: tuple[sp.Poly, ...],
) -> PolynomialIdealWitness:
    residual = _replay_residual(item, initial)
    polynomial = sp.sstr(_expression(item.polynomial))
    multipliers = _expressions(item.multipliers)
    residual_text = sp.sstr(_expression(residual))
    material = "|".join((polynomial, *multipliers, residual_text))
    return PolynomialIdealWitness(
        polynomial=polynomial,
        multipliers=multipliers,
        replay_residual=residual_text,
        replayed=residual.is_zero,
        certificate_sha256=hashlib.sha256(material.encode()).hexdigest(),
    )


def _divide(
    dividend: sp.Poly,
    divisors: tuple[_BasisItem, ...],
    variables: tuple[sp.Symbol, ...],
) -> tuple[tuple[sp.Poly, ...], sp.Poly]:
    """固定されたlex順序で多変数除算を行う。"""

    quotients = [_zero(variables) for _ in divisors]
    remainder = _zero(variables)
    current = dividend
    while not current.is_zero:
        current_powers, current_coefficient = _leading_term(current)
        reduced = False
        for index, divisor in enumerate(divisors):
            divisor_powers, divisor_coefficient = _leading_term(divisor.polynomial)
            if not _divides(divisor_powers, current_powers):
                continue
            powers = tuple(
                current - divisor
                for current, divisor in zip(current_powers, divisor_powers)
            )
            factor = _monomial(
                sp.cancel(current_coefficient / divisor_coefficient),
                variables,
                powers,
            )
            quotients[index] += factor
            current -= factor * divisor.polynomial
            reduced = True
            break
        if reduced:
            continue
        leading = _monomial(current_coefficient, variables, current_powers)
        remainder += leading
        current -= leading
    return tuple(quotients), remainder


def _s_polynomial(
    left: _BasisItem,
    right: _BasisItem,
    variables: tuple[sp.Symbol, ...],
) -> tuple[sp.Poly, tuple[sp.Poly, ...]]:
    left_powers, left_coefficient = _leading_term(left.polynomial)
    right_powers, right_coefficient = _leading_term(right.polynomial)
    lcm = tuple(max(a, b) for a, b in zip(left_powers, right_powers))
    left_factor = _monomial(
        sp.cancel(1 / left_coefficient),
        variables,
        tuple(a - b for a, b in zip(lcm, left_powers)),
    )
    right_factor = _monomial(
        sp.cancel(1 / right_coefficient),
        variables,
        tuple(a - b for a, b in zip(lcm, right_powers)),
    )
    return (
        left_factor * left.polynomial - right_factor * right.polynomial,
        tuple(
            left_factor * a - right_factor * b
            for a, b in zip(left.multipliers, right.multipliers)
        ),
    )


def _pair_rank(
    pair: tuple[int, int],
    basis: list[_BasisItem],
    variables: tuple[sp.Symbol, ...],
) -> tuple[int, tuple[int, ...], int, int]:
    left, right = pair
    left_powers, _ = _leading_term(basis[left].polynomial)
    right_powers, _ = _leading_term(basis[right].polynomial)
    lcm = tuple(max(a, b) for a, b in zip(left_powers, right_powers))
    return sum(lcm), lcm, left, right


def _relatively_prime_leading_monomials(
    left: _BasisItem,
    right: _BasisItem,
    variables: tuple[sp.Symbol, ...],
) -> bool:
    left_powers, _ = _leading_term(left.polynomial)
    right_powers, _ = _leading_term(right.polynomial)
    return all(min(a, b) == 0 for a, b in zip(left_powers, right_powers))


def certified_buchberger(
    polynomials: Iterable[sp.Expr],
    variables: Iterable[sp.Symbol],
    *,
    max_pairs: int = 2_000,
    max_basis_size: int = 128,
    max_polynomial_terms: int = 2_000,
    max_witness_terms: int = 20_000,
) -> CertifiedBuchbergerResult:
    """lex Gröbner基底候補を作り、全生成元への係数を同時に追跡する。"""

    initial_expressions = tuple(sp.expand(item) for item in polynomials)
    ordered_variables = tuple(variables)
    if not ordered_variables:
        raise ValueError("at least one polynomial variable is required")
    unknown = set().union(*(item.free_symbols for item in initial_expressions)) - set(
        ordered_variables
    )
    if unknown:
        raise ValueError(f"variables omitted from polynomial ring: {sorted(map(str, unknown))}")

    initial = tuple(_as_poly(item, ordered_variables) for item in initial_expressions)
    basis: list[_BasisItem] = []
    seen: set[str] = set()
    for index, polynomial in enumerate(initial):
        if polynomial.is_zero:
            continue
        multipliers = tuple(
            _as_poly(sp.Integer(1 if index == source else 0), ordered_variables)
            for source in range(len(initial))
        )
        item = _normalize(_BasisItem(polynomial, multipliers))
        key = sp.sstr(_expression(item.polynomial))
        if key in seen:
            continue
        seen.add(key)
        basis.append(item)

    pairs = set(combinations(range(len(basis)), 2))
    steps: list[CertifiedBuchbergerStep] = []
    processed = 0
    product_criterion = 0
    zero_remainders = 0
    deferred = 0
    stopped_reason: str | None = None

    while pairs:
        if processed >= max_pairs:
            stopped_reason = "pair_budget"
            break
        left_index, right_index = min(
            pairs,
            key=lambda pair: _pair_rank(pair, basis, ordered_variables),
        )
        pairs.remove((left_index, right_index))
        left = basis[left_index]
        right = basis[right_index]
        if _relatively_prime_leading_monomials(left, right, ordered_variables):
            product_criterion += 1
            continue

        processed += 1
        input_basis = tuple(basis)
        s_polynomial, s_multipliers = _s_polynomial(
            left,
            right,
            ordered_variables,
        )
        quotients, remainder = _divide(
            s_polynomial,
            input_basis,
            ordered_variables,
        )
        remainder_multipliers: list[sp.Poly] = []
        for index, source in enumerate(s_multipliers):
            value = source
            for quotient, divisor in zip(quotients, input_basis):
                value -= quotient * divisor.multipliers[index]
            remainder_multipliers.append(value)
        replay = s_polynomial - remainder
        for quotient, divisor in zip(quotients, input_basis):
            replay -= quotient * divisor.polynomial
        if not replay.is_zero:
            raise AssertionError("Buchberger division did not replay")
        if remainder.is_zero:
            zero_remainders += 1
            steps.append(
                CertifiedBuchbergerStep(
                    left_basis_index=left_index,
                    right_basis_index=right_index,
                    input_basis_size=len(input_basis),
                    s_polynomial=sp.sstr(_expression(s_polynomial)),
                    remainder="0",
                    reduction_quotients=_expressions(quotients),
                    output_basis_index=None,
                    deferred_reason=None,
                    witness=None,
                    replayed=True,
                )
            )
            continue

        candidate = _normalize(
            _BasisItem(remainder, tuple(remainder_multipliers)),
        )
        candidate_witness = _witness(candidate, initial)
        reason = None
        if len(basis) >= max_basis_size:
            reason = "basis_budget"
        elif candidate.polynomial.length() > max_polynomial_terms:
            reason = "polynomial_term_budget"
        elif sum(item.length() for item in candidate.multipliers) > max_witness_terms:
            reason = "witness_term_budget"
        if reason is not None:
            deferred += 1
            stopped_reason = stopped_reason or reason
            steps.append(
                CertifiedBuchbergerStep(
                    left_basis_index=left_index,
                    right_basis_index=right_index,
                    input_basis_size=len(input_basis),
                    s_polynomial=sp.sstr(_expression(s_polynomial)),
                    remainder=sp.sstr(_expression(candidate.polynomial)),
                    reduction_quotients=_expressions(quotients),
                    output_basis_index=None,
                    deferred_reason=reason,
                    witness=candidate_witness,
                    replayed=candidate_witness.replayed,
                )
            )
            continue

        key = sp.sstr(_expression(candidate.polynomial))
        output_index = None
        if key not in seen:
            output_index = len(basis)
            for index in range(len(basis)):
                pairs.add((index, output_index))
            basis.append(candidate)
            seen.add(key)
        steps.append(
            CertifiedBuchbergerStep(
                left_basis_index=left_index,
                right_basis_index=right_index,
                input_basis_size=len(input_basis),
                s_polynomial=sp.sstr(_expression(s_polynomial)),
                remainder=sp.sstr(_expression(candidate.polynomial)),
                reduction_quotients=_expressions(quotients),
                output_basis_index=output_index,
                deferred_reason=None,
                witness=candidate_witness,
                replayed=candidate_witness.replayed,
            )
        )

    witnesses = tuple(_witness(item, initial) for item in basis)
    return CertifiedBuchbergerResult(
        initial_polynomials=tuple(sp.sstr(item) for item in initial_expressions),
        variables=tuple(str(item) for item in ordered_variables),
        basis=witnesses,
        steps=tuple(steps),
        processed_pair_count=processed,
        product_criterion_pair_count=product_criterion,
        zero_remainder_pair_count=zero_remainders,
        deferred_pair_count=deferred,
        stopped_reason=stopped_reason,
        groebner_complete=not pairs and deferred == 0,
        all_witnesses_replayed=all(item.replayed for item in witnesses)
        and all(item.replayed for item in steps),
    )


def certify_ideal_membership(
    goal: sp.Expr,
    result: CertifiedBuchbergerResult,
) -> CertifiedIdealMembership:
    """計算済み基底で目標を還元し、初期生成元まで証明書を合成する。"""

    variables = tuple(sp.Symbol(item) for item in result.variables)
    initial = tuple(
        _as_poly(sp.sympify(item), variables) for item in result.initial_polynomials
    )
    basis = tuple(
        _BasisItem(
            _as_poly(sp.sympify(item.polynomial), variables),
            tuple(_as_poly(sp.sympify(value), variables) for value in item.multipliers),
        )
        for item in result.basis
    )
    goal_poly = _as_poly(sp.expand(goal), variables)
    quotients, remainder = _divide(goal_poly, basis, variables)
    multipliers: list[sp.Poly] = []
    for index in range(len(initial)):
        value = _zero(variables)
        for quotient, basis_item in zip(quotients, basis):
            value += quotient * basis_item.multipliers[index]
        multipliers.append(value)
    residual = goal_poly - remainder
    for multiplier, polynomial in zip(multipliers, initial):
        residual -= multiplier * polynomial
    remainder_text = sp.sstr(_expression(remainder))
    multiplier_text = _expressions(multipliers)
    residual_text = sp.sstr(_expression(residual))
    material = "|".join(
        (
            sp.sstr(goal),
            remainder_text,
            *multiplier_text,
            residual_text,
        )
    )
    return CertifiedIdealMembership(
        goal_polynomial=sp.sstr(sp.expand(goal)),
        remainder=remainder_text,
        initial_multipliers=multiplier_text,
        replay_residual=residual_text,
        proved=remainder.is_zero,
        replayed=residual.is_zero,
        certificate_sha256=hashlib.sha256(material.encode()).hexdigest(),
    )


def _dag_identity(
    kind: str,
    polynomial: sp.Poly,
    premises: tuple[sp.Poly, ...],
    multipliers: tuple[sp.Poly, ...],
) -> PolynomialDAGIdentity:
    active = tuple(
        (premise, multiplier)
        for premise, multiplier in zip(premises, multipliers)
        if not multiplier.is_zero
    )
    residual = polynomial
    for premise, multiplier in active:
        residual -= multiplier * premise
    polynomial_text = sp.sstr(_expression(polynomial))
    premise_text = _expressions(item[0] for item in active)
    multiplier_text = _expressions(item[1] for item in active)
    residual_text = sp.sstr(_expression(residual))
    material = "|".join(
        (kind, polynomial_text, *premise_text, *multiplier_text, residual_text)
    )
    return PolynomialDAGIdentity(
        kind=kind,
        polynomial=polynomial_text,
        premises=premise_text,
        multipliers=multiplier_text,
        replay_residual=residual_text,
        replayed=residual.is_zero,
        certificate_sha256=hashlib.sha256(material.encode()).hexdigest(),
    )


def _dag_pair_rank(
    pair: tuple[int, int],
    basis: list[sp.Poly],
) -> tuple[int, tuple[int, ...], int, int]:
    left, right = pair
    left_powers, _ = _leading_term(basis[left])
    right_powers, _ = _leading_term(basis[right])
    lcm = tuple(max(a, b) for a, b in zip(left_powers, right_powers))
    return sum(lcm), lcm, left, right


def _dag_s_polynomial(
    left: sp.Poly,
    right: sp.Poly,
    variables: tuple[sp.Symbol, ...],
) -> tuple[sp.Poly, sp.Poly, sp.Poly]:
    left_powers, left_coefficient = _leading_term(left)
    right_powers, right_coefficient = _leading_term(right)
    lcm = tuple(max(a, b) for a, b in zip(left_powers, right_powers))
    left_factor = _monomial(
        sp.cancel(1 / left_coefficient),
        variables,
        tuple(a - b for a, b in zip(lcm, left_powers)),
    )
    right_factor = _monomial(
        sp.cancel(1 / right_coefficient),
        variables,
        tuple(a - b for a, b in zip(lcm, right_powers)),
    )
    return left_factor * left - right_factor * right, left_factor, right_factor


def certified_buchberger_dag(
    polynomials: Iterable[sp.Expr],
    variables: Iterable[sp.Symbol],
    *,
    max_pairs: int = 2_000,
    max_basis_size: int = 128,
    max_polynomial_terms: int = 2_000,
    max_certificate_terms: int = 20_000,
    membership_target: sp.Expr | None = None,
    membership_check_interval: int = 1,
) -> CertifiedBuchbergerDAGResult:
    """中間基底への局所辺だけを持つ、証明DAG版Buchberger計算。

    ``membership_target`` が与えられた場合は、完全基底の構成前でも現在の
    基底で目標が0へ還元できた時点で停止する。これは完全性を主張しないが、
    得られたイデアル所属証明は厳密である。
    """

    initial_expressions = tuple(sp.expand(item) for item in polynomials)
    ordered_variables = tuple(variables)
    if not ordered_variables:
        raise ValueError("at least one polynomial variable is required")
    unknown = set().union(*(item.free_symbols for item in initial_expressions)) - set(
        ordered_variables
    )
    if unknown:
        raise ValueError(
            f"variables omitted from polynomial ring: {sorted(map(str, unknown))}"
        )
    if membership_check_interval < 1:
        raise ValueError("membership_check_interval must be positive")
    target_poly = (
        _as_poly(sp.expand(membership_target), ordered_variables)
        if membership_target is not None
        else None
    )
    initial = tuple(_as_poly(item, ordered_variables) for item in initial_expressions)
    basis: list[sp.Poly] = []
    identities: list[PolynomialDAGIdentity] = []
    seen: dict[str, int] = {}
    for polynomial in initial:
        if polynomial.is_zero:
            continue
        _, leading_coefficient = _leading_term(polynomial)
        scale = sp.cancel(1 / leading_coefficient)
        normalized = polynomial.mul_ground(scale)
        key = sp.sstr(_expression(normalized))
        if key in seen:
            continue
        identity = _dag_identity(
            "initial_normalization",
            normalized,
            (polynomial,),
            (_as_poly(scale, ordered_variables),),
        )
        seen[key] = len(basis)
        basis.append(normalized)
        identities.append(identity)

    # SymPyの改善Buchberger実装と同様に、更新規則へ入る前に初期生成元を
    # 自己簡約する。これを省くと、先頭項だけによるactive集合の縮約が
    # イデアルを弱める場合がある。
    current_indices = list(range(len(basis)))
    while current_indices:
        reduced_indices: list[int] = []
        for source_index in current_indices:
            divisor_polynomials = tuple(basis[index] for index in reduced_indices)
            quotients, remainder = _divide(
                basis[source_index],
                tuple(_BasisItem(item, ()) for item in divisor_polynomials),
                ordered_variables,
            )
            if remainder.is_zero:
                continue
            _, leading_coefficient = _leading_term(remainder)
            scale = sp.cancel(1 / leading_coefficient)
            candidate = remainder.mul_ground(scale)
            key = sp.sstr(_expression(candidate))
            candidate_index = seen.get(key)
            if candidate_index is None:
                premises = (basis[source_index], *divisor_polynomials)
                multipliers = (
                    _as_poly(scale, ordered_variables),
                    *tuple((-item).mul_ground(scale) for item in quotients),
                )
                identity = _dag_identity(
                    "initial_autoreduction",
                    candidate,
                    premises,
                    multipliers,
                )
                candidate_index = len(basis)
                seen[key] = candidate_index
                basis.append(candidate)
                identities.append(identity)
            reduced_indices.append(candidate_index)
        if [basis[index] for index in reduced_indices] == [
            basis[index] for index in current_indices
        ]:
            current_indices = reduced_indices
            break
        current_indices = reduced_indices

    active: set[int] = set()
    pairs: set[tuple[int, int]] = set()
    product_criterion = 0

    def leading(index: int) -> tuple[int, ...]:
        return _leading_term(basis[index])[0]

    def lcm(left: tuple[int, ...], right: tuple[int, ...]) -> tuple[int, ...]:
        return tuple(max(a, b) for a, b in zip(left, right))

    def multiply(left: tuple[int, ...], right: tuple[int, ...]) -> tuple[int, ...]:
        return tuple(a + b for a, b in zip(left, right))

    def update(new_index: int) -> None:
        nonlocal active, pairs, product_criterion
        new_leading = leading(new_index)
        candidates = set(active)
        possible: set[tuple[int, int]] = set()
        while candidates:
            old_index = candidates.pop()
            old_leading = leading(old_index)
            pair_lcm = lcm(new_leading, old_leading)

            def competing_lcm_divides(index: int) -> bool:
                return _divides(lcm(new_leading, leading(index)), pair_lcm)

            if multiply(new_leading, old_leading) == pair_lcm:
                product_criterion += 1
            elif not any(competing_lcm_divides(index) for index in candidates) and not any(
                competing_lcm_divides(pair[1]) for pair in possible
            ):
                possible.add((new_index, old_index))

        retained_pairs: set[tuple[int, int]] = set()
        for left_index, right_index in pairs:
            old_lcm = lcm(leading(left_index), leading(right_index))
            if (
                not _divides(new_leading, old_lcm)
                or lcm(leading(left_index), new_leading) == old_lcm
                or lcm(leading(right_index), new_leading) == old_lcm
            ):
                retained_pairs.add((left_index, right_index))
        pairs = retained_pairs | possible
        active = {
            index for index in active if not _divides(new_leading, leading(index))
        }
        active.add(new_index)

    for index in sorted(current_indices, key=lambda item: leading(item)):
        update(index)

    steps: list[CertifiedBuchbergerDAGStep] = []
    processed = 0
    zero_remainders = 0
    deferred = 0
    stopped_reason: str | None = None

    def target_reduces_to_zero() -> bool:
        if target_poly is None:
            return False
        active_basis = tuple(
            _BasisItem(basis[index], ())
            for index in sorted(active, key=lambda item: leading(item))
        )
        return _divide(target_poly, active_basis, ordered_variables)[1].is_zero

    if target_reduces_to_zero():
        stopped_reason = "target_membership"
        pairs.clear()
    while pairs:
        if processed >= max_pairs:
            stopped_reason = "pair_budget"
            break
        left_index, right_index = min(
            pairs,
            key=lambda pair: lcm(leading(pair[0]), leading(pair[1])),
        )
        pairs.remove((left_index, right_index))
        processed += 1
        input_indices = tuple(sorted(active, key=lambda item: leading(item)))
        input_basis = tuple(basis[index] for index in input_indices)
        s_polynomial, left_factor, right_factor = _dag_s_polynomial(
            basis[left_index],
            basis[right_index],
            ordered_variables,
        )
        quotients, remainder = _divide(
            s_polynomial,
            tuple(_BasisItem(item, ()) for item in input_basis),
            ordered_variables,
        )
        if remainder.is_zero:
            zero_remainders += 1
            steps.append(
                CertifiedBuchbergerDAGStep(
                    left_basis_index=left_index,
                    right_basis_index=right_index,
                    input_basis_size=len(input_basis),
                    remainder="0",
                    output_basis_index=None,
                    deferred_reason=None,
                    identity=None,
                    replayed=True,
                )
            )
            continue

        _, leading_coefficient = _leading_term(remainder)
        scale = sp.cancel(1 / leading_coefficient)
        candidate = remainder.mul_ground(scale)
        multipliers = [(-item).mul_ground(scale) for item in quotients]
        premises = list(input_basis)

        def add_source(source_index: int, multiplier: sp.Poly) -> None:
            if source_index in input_indices:
                position = input_indices.index(source_index)
                multipliers[position] += multiplier.mul_ground(scale)
            else:
                premises.append(basis[source_index])
                multipliers.append(multiplier.mul_ground(scale))

        add_source(left_index, left_factor)
        add_source(right_index, -right_factor)
        identity = _dag_identity(
            "s_polynomial_reduction",
            candidate,
            tuple(premises),
            tuple(multipliers),
        )
        reason = None
        if len(basis) >= max_basis_size:
            reason = "basis_budget"
        elif candidate.length() > max_polynomial_terms:
            reason = "polynomial_term_budget"
        elif sum(item.length() for item in multipliers) > max_certificate_terms:
            reason = "certificate_term_budget"
        if reason is not None:
            deferred += 1
            stopped_reason = stopped_reason or reason
            steps.append(
                CertifiedBuchbergerDAGStep(
                    left_basis_index=left_index,
                    right_basis_index=right_index,
                    input_basis_size=len(input_basis),
                    remainder=sp.sstr(_expression(candidate)),
                    output_basis_index=None,
                    deferred_reason=reason,
                    identity=identity,
                    replayed=identity.replayed,
                )
            )
            continue

        key = sp.sstr(_expression(candidate))
        output_index = seen.get(key)
        if output_index is None:
            output_index = len(basis)
            seen[key] = output_index
            basis.append(candidate)
            identities.append(identity)
            update(output_index)
        steps.append(
            CertifiedBuchbergerDAGStep(
                left_basis_index=left_index,
                right_basis_index=right_index,
                input_basis_size=len(input_basis),
                remainder=sp.sstr(_expression(candidate)),
                output_basis_index=output_index,
                deferred_reason=None,
                identity=identity,
                replayed=identity.replayed,
            )
        )
        if processed % membership_check_interval == 0 and target_reduces_to_zero():
            stopped_reason = "target_membership"
            pairs.clear()
            break

    active_basis = tuple(basis[index] for index in sorted(active, key=lambda item: leading(item)))
    return CertifiedBuchbergerDAGResult(
        initial_polynomials=tuple(sp.sstr(item) for item in initial_expressions),
        variables=tuple(str(item) for item in ordered_variables),
        basis_polynomials=_expressions(active_basis),
        identities=tuple(identities),
        steps=tuple(steps),
        processed_pair_count=processed,
        product_criterion_pair_count=product_criterion,
        zero_remainder_pair_count=zero_remainders,
        deferred_pair_count=deferred,
        stopped_reason=stopped_reason,
        groebner_complete=not pairs
        and deferred == 0
        and stopped_reason != "target_membership",
        all_identities_replayed=all(item.replayed for item in identities)
        and all(item.replayed for item in steps),
    )


def certify_dag_ideal_membership(
    goal: sp.Expr,
    result: CertifiedBuchbergerDAGResult,
) -> CertifiedDAGIdealMembership:
    """DAG基底を用いて目標を還元し、最後の一辺だけを記録する。"""

    variables = tuple(sp.Symbol(item) for item in result.variables)
    basis = tuple(
        _as_poly(sp.sympify(item), variables) for item in result.basis_polynomials
    )
    goal_poly = _as_poly(sp.expand(goal), variables)
    quotients, remainder = _divide(
        goal_poly,
        tuple(_BasisItem(item, ()) for item in basis),
        variables,
    )
    residual = goal_poly - remainder
    for quotient, polynomial in zip(quotients, basis):
        residual -= quotient * polynomial
    active = tuple(
        (polynomial, quotient)
        for polynomial, quotient in zip(basis, quotients)
        if not quotient.is_zero
    )
    premise_text = _expressions(item[0] for item in active)
    multiplier_text = _expressions(item[1] for item in active)
    remainder_text = sp.sstr(_expression(remainder))
    residual_text = sp.sstr(_expression(residual))
    goal_text = sp.sstr(_expression(goal_poly))
    material = "|".join(
        (goal_text, remainder_text, *premise_text, *multiplier_text, residual_text)
    )
    return CertifiedDAGIdealMembership(
        goal_polynomial=goal_text,
        remainder=remainder_text,
        premises=premise_text,
        multipliers=multiplier_text,
        replay_residual=residual_text,
        proved=remainder.is_zero,
        replayed=residual.is_zero,
        certificate_sha256=hashlib.sha256(material.encode()).hexdigest(),
    )
