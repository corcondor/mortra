"""Certificate-carrying Wu--Ritt characteristic-set construction.

This module follows the executable control structure formalized by
WuProver/lean_characteristic_set:

    BS := BasicSet(PS')
    RS := { prem(p, BS) | p in PS' \\ BS, prem(p, BS) != 0 }
    PS' := PS ++ RS ++ BS

The loop stops only when ``RS`` is empty.  Every pseudo-division identity is
recorded and replayed exactly.  No problem text, theorem name, or target value
is used to choose the characteristic set.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Iterable

import sympy as sp
from sympy.polys.domains import QQ
from sympy.polys.rings import PolyElement, ring

from worker.backend.certified_wu_characteristic import (
    CertifiedPseudoDivision,
    SparsePseudoDivisionBudgetExceeded,
    _ring_main_coefficient,
    _sparse_pseudo_division,
)


@dataclass(frozen=True)
class WuSetPseudoRemainder:
    dividend: str
    remainder: str
    steps: tuple[CertifiedPseudoDivision, ...]
    zero: bool
    all_identities_replayed: bool
    maximum_term_count: int


@dataclass(frozen=True)
class WuCharacteristicRound:
    round_index: int
    input_polynomial_count: int
    basic_set: tuple[str, ...]
    basic_set_rank: tuple[tuple[int, int], ...]
    nonzero_remainders: tuple[str, ...]
    reductions: tuple[WuSetPseudoRemainder, ...]
    all_identities_replayed: bool


@dataclass(frozen=True)
class CertifiedWuCharacteristicSet:
    initial_polynomials: tuple[str, ...]
    variables: tuple[str, ...]
    coefficient_parameters: tuple[str, ...]
    basic_set_mode: str
    characteristic_set: tuple[str, ...]
    characteristic_rank: tuple[tuple[int, int], ...]
    initials: tuple[str, ...]
    rounds: tuple[WuCharacteristicRound, ...]
    input_reductions: tuple[WuSetPseudoRemainder, ...]
    completion_reached: bool
    all_input_remainders_zero: bool
    vanishing_consequence_verified: bool
    characteristic_set_verified: bool
    all_identities_replayed: bool
    stopped_reason: str | None
    reduction_count: int
    maximum_term_count: int
    elapsed_seconds: float


@dataclass(frozen=True)
class CertifiedWuRittGoal:
    characteristic: CertifiedWuCharacteristicSet
    goal_polynomial: str
    goal_remainder: str
    goal_reduction: WuSetPseudoRemainder | None
    regularity_initials: tuple[str, ...]
    inconsistent_system: bool
    conditional_goal_proved: bool
    all_identities_replayed: bool
    stopped_reason: str | None
    elapsed_seconds: float


class WuCharacteristicTimeout(RuntimeError):
    """Raised only at a certified micro-step boundary when the deadline expires."""


def _deduplicate_ring(polynomials: Iterable[PolyElement]) -> tuple[PolyElement, ...]:
    unique: dict[str, PolyElement] = {}
    for polynomial in polynomials:
        if polynomial:
            unique.setdefault(str(polynomial), polynomial)
    return tuple(unique.values())


def _main_variable_index(polynomial: PolyElement) -> int | None:
    indices = [
        index
        for index in range(polynomial.ring.ngens)
        if polynomial.degree(index) > 0
    ]
    return max(indices, default=None)


def _polynomial_rank(polynomial: PolyElement) -> tuple[int, int]:
    main = _main_variable_index(polynomial)
    return (-1, 0) if main is None else (main, int(polynomial.degree(main)))


def _reduced_to_polynomial(dividend: PolyElement, divisor: PolyElement) -> bool:
    if not dividend:
        return True
    main = _main_variable_index(divisor)
    if main is None:
        return False
    return dividend.degree(main) < divisor.degree(main)


def _reduced_to_set(polynomial: PolyElement, ascending: tuple[PolyElement, ...]) -> bool:
    return all(_reduced_to_polynomial(polynomial, divisor) for divisor in ascending)


def _take_concat(
    ascending: tuple[PolyElement, ...],
    polynomial: PolyElement,
) -> tuple[PolyElement, ...]:
    """Ritt ``takeConcat``: truncate at the new main variable, then append."""

    main = _main_variable_index(polynomial)
    rank = -1 if main is None else main
    prefix = tuple(
        item
        for item in ascending
        if (_main_variable_index(item) if _main_variable_index(item) is not None else -1)
        < rank
    )
    return (*prefix, polynomial)


def standard_basic_set(polynomials: Iterable[PolyElement]) -> tuple[PolyElement, ...]:
    """Deterministic executable counterpart of StandardAscendingSet.basicSet."""

    candidates = sorted(
        _deduplicate_ring(polynomials),
        key=lambda item: (*_polynomial_rank(item), len(item), str(item)),
    )
    basic: tuple[PolyElement, ...] = ()
    while candidates:
        selected = candidates[0]
        basic = _take_concat(basic, selected)
        candidates = [
            item for item in candidates if _reduced_to_set(item, basic)
        ]
    return basic


def weak_basic_set(polynomials: Iterable[PolyElement]) -> tuple[PolyElement, ...]:
    """Executable counterpart of WeakAscendingSet.basicSet.

    The next polynomial must have a strictly larger main variable, while only
    its initial is required to be reduced with respect to the accumulated set.
    """

    candidates = sorted(
        _deduplicate_ring(polynomials),
        key=lambda item: (*_polynomial_rank(item), len(item), str(item)),
    )
    basic: tuple[PolyElement, ...] = ()
    while candidates:
        selected = candidates[0]
        selected_main = _main_variable_index(selected)
        selected_rank = -1 if selected_main is None else selected_main
        basic = (*basic, selected)
        next_candidates: list[PolyElement] = []
        for item in candidates:
            main = _main_variable_index(item)
            rank = -1 if main is None else main
            if rank <= selected_rank or main is None:
                continue
            initial = _ring_main_coefficient(item, main)
            if _reduced_to_set(initial, basic):
                next_candidates.append(item)
        candidates = next_candidates
    return basic


def _constant_division(
    dividend: PolyElement,
    divisor: PolyElement,
    *,
    phase: str,
) -> tuple[CertifiedPseudoDivision, PolyElement]:
    """Return an exact certificate for division by a nonzero field constant."""

    zero = dividend.ring.zero
    residual = divisor * dividend - dividend * divisor
    material = "|".join(
        (phase, "constant", str(dividend), str(divisor), str(divisor), str(dividend))
    )
    certificate = CertifiedPseudoDivision(
        phase=phase,
        variable="constant",
        dividend=str(dividend),
        divisor=str(divisor),
        multiplier=str(divisor),
        quotient=str(dividend),
        remainder_multiplier="1",
        remainder="0",
        dividend_degree=0,
        divisor_degree=0,
        replay_residual=str(residual),
        nonzero_obligation=None,
        normalization_nonzero_obligation=None,
        replayed=not residual,
        certificate_sha256=hashlib.sha256(material.encode()).hexdigest(),
    )
    return certificate, zero


def _set_pseudo_remainder_with_polynomial(
    dividend: PolyElement,
    ascending: tuple[PolyElement, ...],
    variable_names: tuple[str, ...],
    *,
    phase: str,
    max_terms: int,
    deadline: float | None = None,
) -> tuple[WuSetPseudoRemainder, PolyElement]:
    current = dividend
    steps: list[CertifiedPseudoDivision] = []
    maximum_terms = len(current)

    def check_deadline(_progress: dict[str, object]) -> None:
        if deadline is not None and time.perf_counter() >= deadline:
            raise WuCharacteristicTimeout("pseudo-division deadline exceeded")

    for divisor in reversed(ascending):
        if deadline is not None and time.perf_counter() >= deadline:
            raise WuCharacteristicTimeout("pseudo-remainder deadline exceeded")
        if not current:
            break
        main = _main_variable_index(divisor)
        if main is None:
            certificate, current = _constant_division(
                current,
                divisor,
                phase=phase,
            )
        else:
            certificate, current = _sparse_pseudo_division(
                current,
                divisor,
                main,
                variable_names[main],
                phase=phase,
                # Wu--Ritt set pseudo-remainders do not cancel polynomial
                # content.  Cancelling it would add an unrecorded open locus.
                normalize_remainder=False,
                max_intermediate_terms=max_terms,
                progress_callback=check_deadline,
            )
        steps.append(certificate)
        maximum_terms = max(maximum_terms, len(current))
        if maximum_terms > max_terms:
            raise SparsePseudoDivisionBudgetExceeded(maximum_terms, len(steps))
    return (
        WuSetPseudoRemainder(
            dividend=str(dividend),
            remainder=str(current),
            steps=tuple(steps),
            zero=not current,
            all_identities_replayed=all(item.replayed for item in steps),
            maximum_term_count=maximum_terms,
        ),
        current,
    )


def _set_pseudo_remainder(
    dividend: PolyElement,
    ascending: tuple[PolyElement, ...],
    variable_names: tuple[str, ...],
    *,
    phase: str,
    max_terms: int,
    deadline: float | None = None,
) -> WuSetPseudoRemainder:
    result, _ = _set_pseudo_remainder_with_polynomial(
        dividend,
        ascending,
        variable_names,
        phase=phase,
        max_terms=max_terms,
        deadline=deadline,
    )
    return result


def _list_difference(
    polynomials: tuple[PolyElement, ...],
    removed: tuple[PolyElement, ...],
) -> tuple[PolyElement, ...]:
    remaining = list(polynomials)
    for item in removed:
        key = str(item)
        for index, candidate in enumerate(remaining):
            if str(candidate) == key:
                remaining.pop(index)
                break
    return tuple(remaining)


def _certified_wu_ritt_characteristic_set_with_ring(
    polynomials: Iterable[sp.Expr],
    variables: Iterable[sp.Symbol],
    *,
    coefficient_variables: Iterable[sp.Symbol] = (),
    basic_set_mode: str = "standard",
    max_rounds: int = 32,
    max_reductions: int = 20_000,
    max_terms: int = 20_000,
    timeout_seconds: float = 300.0,
) -> tuple[CertifiedWuCharacteristicSet, tuple[PolyElement, ...], object]:
    """Compute and independently replay a bounded Wu--Ritt characteristic set."""

    started = time.perf_counter()
    deadline = started + timeout_seconds if timeout_seconds > 0 else None
    ordered_variables = tuple(variables)
    if not ordered_variables:
        raise ValueError("at least one variable is required")
    if basic_set_mode not in {"standard", "weak"}:
        raise ValueError("basic_set_mode must be 'standard' or 'weak'")
    coefficient_parameters = tuple(coefficient_variables)
    if len(coefficient_parameters) != len(set(coefficient_parameters)):
        raise ValueError("coefficient_variables must be unique")
    if not set(coefficient_parameters).issubset(ordered_variables):
        raise ValueError("coefficient_variables must be included in variables")
    dependent_variables = tuple(
        item for item in ordered_variables if item not in coefficient_parameters
    )
    if not dependent_variables:
        raise ValueError("at least one polynomial variable must remain")
    coefficient_domain = (
        QQ.frac_field(*coefficient_parameters)
        if coefficient_parameters
        else QQ
    )
    polynomial_ring, *_ = ring(
        ",".join(str(item) for item in dependent_variables),
        coefficient_domain,
    )
    initial = _deduplicate_ring(
        polynomial_ring.from_expr(sp.expand(item)) for item in polynomials
    )
    working = initial
    variable_names = tuple(str(item) for item in dependent_variables)
    rounds: list[WuCharacteristicRound] = []
    reduction_count = 0
    maximum_terms = max((len(item) for item in initial), default=0)
    stopped_reason: str | None = None
    characteristic: tuple[PolyElement, ...] = ()

    for round_index in range(max_rounds):
        if timeout_seconds > 0 and time.perf_counter() - started >= timeout_seconds:
            stopped_reason = "timeout"
            break
        basic = (
            standard_basic_set(working)
            if basic_set_mode == "standard"
            else weak_basic_set(working)
        )
        reductions: list[WuSetPseudoRemainder] = []
        remainders: list[PolyElement] = []
        try:
            for polynomial in _list_difference(working, basic):
                if reduction_count >= max_reductions:
                    stopped_reason = "reduction_budget"
                    break
                reduced, remainder = _set_pseudo_remainder_with_polynomial(
                    polynomial,
                    basic,
                    variable_names,
                    phase=f"characteristic_round_{round_index}",
                    max_terms=max_terms,
                    deadline=deadline,
                )
                reductions.append(reduced)
                reduction_count += len(reduced.steps)
                maximum_terms = max(maximum_terms, reduced.maximum_term_count)
                if not reduced.zero:
                    remainders.append(remainder)
        except SparsePseudoDivisionBudgetExceeded as error:
            maximum_terms = max(maximum_terms, error.observed_terms)
            stopped_reason = "term_budget"
        except WuCharacteristicTimeout:
            stopped_reason = "timeout"

        nonzero_remainders = _deduplicate_ring(remainders)
        rounds.append(
            WuCharacteristicRound(
                round_index=round_index,
                input_polynomial_count=len(working),
                basic_set=tuple(str(item) for item in basic),
                basic_set_rank=tuple(_polynomial_rank(item) for item in basic),
                nonzero_remainders=tuple(str(item) for item in nonzero_remainders),
                reductions=tuple(reductions),
                all_identities_replayed=all(
                    item.all_identities_replayed for item in reductions
                ),
            )
        )
        characteristic = basic
        if stopped_reason is not None:
            break
        if not nonzero_remainders:
            break
        working = _deduplicate_ring((*initial, *nonzero_remainders, *basic))
    else:
        stopped_reason = "round_budget"

    completion_reached = bool(rounds) and stopped_reason is None and not rounds[-1].nonzero_remainders
    input_reductions: list[WuSetPseudoRemainder] = []
    if completion_reached:
        try:
            for polynomial in initial:
                reduced = _set_pseudo_remainder(
                    polynomial,
                    characteristic,
                    variable_names,
                    phase="characteristic_input_replay",
                    max_terms=max_terms,
                    deadline=deadline,
                )
                input_reductions.append(reduced)
                reduction_count += len(reduced.steps)
                maximum_terms = max(maximum_terms, reduced.maximum_term_count)
        except SparsePseudoDivisionBudgetExceeded as error:
            maximum_terms = max(maximum_terms, error.observed_terms)
            stopped_reason = "input_replay_term_budget"
        except WuCharacteristicTimeout:
            stopped_reason = "timeout"

    all_replayed = all(item.all_identities_replayed for item in rounds) and all(
        item.all_identities_replayed for item in input_reductions
    )
    input_zero = (
        completion_reached
        and len(input_reductions) == len(initial)
        and all(item.zero for item in input_reductions)
    )
    consequence_verified = completion_reached and all(
        item.all_identities_replayed for item in rounds
    )
    verified = (
        completion_reached
        and input_zero
        and consequence_verified
        and all_replayed
        and stopped_reason is None
    )
    initials = tuple(
        str(_ring_main_coefficient(item, main))
        for item in characteristic
        if (main := _main_variable_index(item)) is not None
    )
    result = CertifiedWuCharacteristicSet(
        initial_polynomials=tuple(str(item) for item in initial),
        variables=tuple(str(item) for item in ordered_variables),
        coefficient_parameters=tuple(str(item) for item in coefficient_parameters),
        basic_set_mode=basic_set_mode,
        characteristic_set=tuple(str(item) for item in characteristic),
        characteristic_rank=tuple(_polynomial_rank(item) for item in characteristic),
        initials=initials,
        rounds=tuple(rounds),
        input_reductions=tuple(input_reductions),
        completion_reached=completion_reached,
        all_input_remainders_zero=input_zero,
        vanishing_consequence_verified=consequence_verified,
        characteristic_set_verified=verified,
        all_identities_replayed=all_replayed,
        stopped_reason=stopped_reason,
        reduction_count=reduction_count,
        maximum_term_count=maximum_terms,
        elapsed_seconds=time.perf_counter() - started,
    )
    return result, characteristic, polynomial_ring


def certified_wu_ritt_characteristic_set(
    polynomials: Iterable[sp.Expr],
    variables: Iterable[sp.Symbol],
    *,
    coefficient_variables: Iterable[sp.Symbol] = (),
    basic_set_mode: str = "standard",
    max_rounds: int = 32,
    max_reductions: int = 20_000,
    max_terms: int = 20_000,
    timeout_seconds: float = 300.0,
) -> CertifiedWuCharacteristicSet:
    """Compute and independently replay a bounded Wu--Ritt characteristic set."""

    result, _, _ = _certified_wu_ritt_characteristic_set_with_ring(
        polynomials,
        variables,
        coefficient_variables=coefficient_variables,
        basic_set_mode=basic_set_mode,
        max_rounds=max_rounds,
        max_reductions=max_reductions,
        max_terms=max_terms,
        timeout_seconds=timeout_seconds,
    )
    return result


def certified_wu_ritt_goal_proof(
    polynomials: Iterable[sp.Expr],
    variables: Iterable[sp.Symbol],
    goal_polynomial: sp.Expr,
    *,
    coefficient_variables: Iterable[sp.Symbol] = (),
    basic_set_mode: str = "standard",
    max_rounds: int = 32,
    max_reductions: int = 20_000,
    max_terms: int = 20_000,
    timeout_seconds: float = 300.0,
) -> CertifiedWuRittGoal:
    """Reduce a goal by a verified characteristic set on its regular locus."""

    started = time.perf_counter()
    deadline = started + timeout_seconds if timeout_seconds > 0 else None
    ordered_variables = tuple(variables)
    characteristic, characteristic_polynomials, polynomial_ring = (
        _certified_wu_ritt_characteristic_set_with_ring(
            polynomials,
            ordered_variables,
            coefficient_variables=coefficient_variables,
            basic_set_mode=basic_set_mode,
            max_rounds=max_rounds,
            max_reductions=max_reductions,
            max_terms=max_terms,
            timeout_seconds=timeout_seconds,
        )
    )
    goal = polynomial_ring.from_expr(sp.expand(goal_polynomial))
    inconsistent = any(
        item and _main_variable_index(item) is None
        for item in characteristic_polynomials
    )
    goal_reduction: WuSetPseudoRemainder | None = None
    stopped_reason = characteristic.stopped_reason
    if characteristic.characteristic_set_verified and not inconsistent:
        try:
            goal_reduction = _set_pseudo_remainder(
                goal,
                characteristic_polynomials,
                tuple(
                    str(item)
                    for item in ordered_variables
                    if item not in set(coefficient_variables)
                ),
                phase="characteristic_goal",
                max_terms=max_terms,
                deadline=deadline,
            )
        except SparsePseudoDivisionBudgetExceeded:
            stopped_reason = "goal_term_budget"
        except WuCharacteristicTimeout:
            stopped_reason = "timeout"
    proved = (
        characteristic.characteristic_set_verified
        and (inconsistent or (goal_reduction is not None and goal_reduction.zero))
        and stopped_reason is None
    )
    replayed = characteristic.all_identities_replayed and (
        goal_reduction is None or goal_reduction.all_identities_replayed
    )
    return CertifiedWuRittGoal(
        characteristic=characteristic,
        goal_polynomial=str(goal),
        goal_remainder=(
            "0" if inconsistent else goal_reduction.remainder if goal_reduction else str(goal)
        ),
        goal_reduction=goal_reduction,
        regularity_initials=characteristic.initials,
        inconsistent_system=inconsistent,
        conditional_goal_proved=proved,
        all_identities_replayed=replayed,
        stopped_reason=stopped_reason,
        elapsed_seconds=time.perf_counter() - started,
    )
