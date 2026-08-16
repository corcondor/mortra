"""Chordal eliminationを係数証明書付き局所Buchberger計算で実行する。"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from itertools import combinations
from typing import Callable, Iterable

import sympy as sp

from worker.backend.certified_buchberger import (
    CertifiedBuchbergerDAGResult,
    CertifiedDAGIdealMembership,
    PolynomialDAGIdentity,
    certified_buchberger_dag,
    certify_dag_ideal_membership,
)


@dataclass(frozen=True)
class CertifiedCliqueEliminationStep:
    variable: str
    clique_variables: tuple[str, ...]
    separator_variables: tuple[str, ...]
    input_polynomials: tuple[str, ...]
    leading_coefficient_polynomials: tuple[str, ...]
    coefficient_nonzero_obligations: tuple[str, ...]
    unit_leading_coefficient_available: bool
    candidate_output_polynomials: tuple[str, ...]
    output_polynomials: tuple[str, ...]
    internal_identities: tuple[PolynomialDAGIdentity, ...]
    buchberger_complete: bool
    processed_pair_count: int
    deferred_pair_count: int
    stopped_reason: str | None
    replayed: bool
    elimination_committed: bool
    elapsed_seconds: float
    certificate_sha256: str


@dataclass(frozen=True)
class ChordalBuchbergerEliminationResult:
    initial_polynomials: tuple[str, ...]
    remaining_polynomials: tuple[str, ...]
    remaining_variables: tuple[str, ...]
    eliminated_variables: tuple[str, ...]
    steps: tuple[CertifiedCliqueEliminationStep, ...]
    stopped_reason: str | None
    local_complete_step_count: int
    local_incomplete_step_count: int
    exact_replay: bool
    terminal_buchberger: CertifiedBuchbergerDAGResult | None
    goal_membership: CertifiedDAGIdealMembership | None


def _deduplicate(polynomials: Iterable[sp.Expr]) -> tuple[sp.Expr, ...]:
    unique: dict[str, sp.Expr] = {}
    for polynomial in polynomials:
        expanded = sp.expand(polynomial)
        if expanded == 0:
            continue
        unique.setdefault(sp.sstr(expanded), expanded)
    return tuple(unique[key] for key in sorted(unique))


def _primal_adjacency(
    polynomials: Iterable[sp.Expr],
) -> dict[sp.Symbol, set[sp.Symbol]]:
    adjacency: dict[sp.Symbol, set[sp.Symbol]] = {}
    for polynomial in polynomials:
        scope = set(polynomial.free_symbols)
        for variable in scope:
            adjacency.setdefault(variable, set()).update(scope - {variable})
    return adjacency


def _fill_edge_count(
    variable: sp.Symbol,
    adjacency: dict[sp.Symbol, set[sp.Symbol]],
) -> int:
    neighbors = adjacency.get(variable, set())
    return sum(
        right not in adjacency.get(left, set())
        for left, right in combinations(neighbors, 2)
    )


def _term_count(polynomial: sp.Expr) -> int:
    return len(sp.Add.make_args(sp.expand(polynomial)))


def _monomial_divides(left: tuple[int, ...], right: tuple[int, ...]) -> bool:
    return all(a <= b for a, b in zip(left, right))


def _scope_distance_to_goal(
    scope: frozenset[sp.Symbol],
    goal_variables: frozenset[sp.Symbol],
    adjacency: dict[sp.Symbol, set[sp.Symbol]],
) -> int:
    """Return factor-graph distance from a separator message to the goal."""

    if not goal_variables:
        return 0
    if scope & goal_variables:
        return 0
    frontier = set(scope)
    visited = set(scope)
    distance = 0
    while frontier:
        distance += 1
        frontier = {
            neighbor
            for variable in frontier
            for neighbor in adjacency.get(variable, set())
            if neighbor not in visited
        }
        if frontier & goal_variables:
            return distance
        visited.update(frontier)
    return len(adjacency) + 1


def _select_incomplete_messages(
    candidates: tuple[sp.Expr, ...],
    *,
    goal_variables: frozenset[sp.Symbol],
    adjacency: dict[sp.Symbol, set[sp.Symbol]],
    maximum: int,
) -> tuple[sp.Expr, ...]:
    """Keep a small, goal-relevant antichain of sound separator consequences."""

    if maximum <= 0:
        return ()
    ranked = sorted(
        candidates,
        key=lambda polynomial: (
            _scope_distance_to_goal(
                frozenset(polynomial.free_symbols), goal_variables, adjacency
            ),
            len(polynomial.free_symbols),
            _term_count(polynomial),
            int(sp.count_ops(polynomial)),
            sp.sstr(polynomial),
        ),
    )
    selected: list[sp.Expr] = []
    selected_leads: list[tuple[tuple[str, ...], tuple[int, ...]]] = []
    for polynomial in ranked:
        variables = tuple(sorted(polynomial.free_symbols, key=str))
        if not variables:
            selected.append(polynomial)
        else:
            powers, _ = sp.Poly(polynomial, *variables, domain=sp.QQ).terms(
                order="lex"
            )[0]
            signature = (tuple(str(item) for item in variables), powers)
            if any(
                signature[0] == old_variables
                and _monomial_divides(old_powers, signature[1])
                for old_variables, old_powers in selected_leads
            ):
                continue
            selected.append(polynomial)
            selected_leads.append(signature)
        if len(selected) >= maximum:
            break
    return tuple(selected)


def _identity_replays(identity: PolynomialDAGIdentity) -> bool:
    if len(identity.multipliers) != len(identity.premises):
        return False
    residual = sp.expand(
        sp.sympify(identity.polynomial)
        - sum(
            (
                sp.sympify(multiplier) * polynomial
                for multiplier, polynomial in zip(
                    identity.multipliers,
                    map(sp.sympify, identity.premises),
                )
            ),
            sp.Integer(0),
        )
    )
    return residual == 0 and identity.replayed and identity.replay_residual == "0"


def _leading_coefficient_obligations(
    variable: sp.Symbol,
    inputs: tuple[sp.Expr, ...],
) -> tuple[tuple[sp.Expr, ...], tuple[str, ...], bool]:
    """Expose the coefficient-ideal boundary used by chordal elimination."""

    coefficients: dict[str, sp.Expr] = {}
    unit_available = False
    for expression in inputs:
        polynomial = sp.Poly(expression, variable)
        if polynomial.degree() <= 0:
            continue
        coefficient = sp.factor(polynomial.LC())
        coefficients.setdefault(sp.sstr(coefficient), coefficient)
        if not coefficient.free_symbols and coefficient != 0:
            unit_available = True
    ordered = tuple(coefficients[key] for key in sorted(coefficients))
    obligations = tuple(
        f"{sp.sstr(item)} != 0" for item in ordered if item.free_symbols
    )
    return ordered, obligations, unit_available


def _clique_step(
    variable: sp.Symbol,
    clique: frozenset[sp.Symbol],
    inputs: tuple[sp.Expr, ...],
    *,
    max_pairs: int,
    max_basis_size: int,
    max_polynomial_terms: int,
    max_witness_terms: int,
    goal_variables: frozenset[sp.Symbol],
    global_adjacency: dict[sp.Symbol, set[sp.Symbol]],
    max_incomplete_messages: int,
) -> tuple[tuple[sp.Expr, ...], CertifiedCliqueEliminationStep]:
    started = time.perf_counter()
    leading_coefficients, coefficient_obligations, unit_available = (
        _leading_coefficient_obligations(variable, inputs)
    )
    local_variables = (variable,) + tuple(
        sorted(clique - {variable}, key=str)
    )
    result = certified_buchberger_dag(
        inputs,
        local_variables,
        max_pairs=max_pairs,
        max_basis_size=max_basis_size,
        max_polynomial_terms=max_polynomial_terms,
        max_certificate_terms=max_witness_terms,
    )
    output_by_polynomial: dict[str, sp.Expr] = {}
    for polynomial in result.basis_polynomials:
        expression = sp.sympify(polynomial)
        if variable in expression.free_symbols:
            continue
        output_by_polynomial.setdefault(polynomial, expression)
    candidate_outputs = tuple(
        output_by_polynomial[key] for key in sorted(output_by_polynomial)
    )
    outputs = (
        candidate_outputs
        if result.groebner_complete
        else _select_incomplete_messages(
            candidate_outputs,
            goal_variables=goal_variables,
            adjacency=global_adjacency,
            maximum=max_incomplete_messages,
        )
    )
    replayed = result.all_identities_replayed and all(
        _identity_replays(item) for item in result.identities
    )
    material = "|".join(
        (
            str(variable),
            *(str(item) for item in sorted(clique, key=str)),
            *(sp.sstr(item) for item in inputs),
            *(sp.sstr(item) for item in leading_coefficients),
            *coefficient_obligations,
            str(unit_available),
            *(sp.sstr(item) for item in candidate_outputs),
            *(item.certificate_sha256 for item in result.identities),
            str(result.groebner_complete),
            str(result.processed_pair_count),
            str(result.deferred_pair_count),
            str(result.stopped_reason),
        )
    )
    return outputs, CertifiedCliqueEliminationStep(
        variable=str(variable),
        clique_variables=tuple(str(item) for item in local_variables),
        separator_variables=tuple(str(item) for item in local_variables[1:]),
        input_polynomials=tuple(sp.sstr(item) for item in inputs),
        leading_coefficient_polynomials=tuple(
            sp.sstr(item) for item in leading_coefficients
        ),
        coefficient_nonzero_obligations=coefficient_obligations,
        unit_leading_coefficient_available=unit_available,
        candidate_output_polynomials=tuple(
            sp.sstr(item) for item in candidate_outputs
        ),
        output_polynomials=tuple(sp.sstr(item) for item in outputs),
        internal_identities=result.identities,
        buchberger_complete=result.groebner_complete,
        processed_pair_count=result.processed_pair_count,
        deferred_pair_count=result.deferred_pair_count,
        stopped_reason=result.stopped_reason,
        replayed=replayed,
        elimination_committed=result.groebner_complete,
        elapsed_seconds=time.perf_counter() - started,
        certificate_sha256=hashlib.sha256(material.encode()).hexdigest(),
    )


def eliminate_with_certified_chordal_buchberger(
    polynomials: Iterable[sp.Expr],
    variables: Iterable[sp.Symbol],
    *,
    protected_variables: Iterable[sp.Symbol] = (),
    goal_polynomial: sp.Expr | None = None,
    max_steps: int | None = None,
    max_separator_variables: int | None = 12,
    max_clique_polynomials: int = 32,
    max_pairs_per_clique: int = 256,
    max_basis_size_per_clique: int = 64,
    max_polynomial_terms: int = 2_000,
    max_witness_terms: int = 20_000,
    terminal_max_pairs: int = 1_000,
    terminal_max_basis_size: int = 128,
    max_incomplete_messages: int = 4,
    progress_callback: Callable[[dict[str, object]], None] | None = None,
) -> ChordalBuchbergerEliminationResult:
    """クリーク内で消去し、境界多項式だけを消去木の親へ渡す。"""

    initial = _deduplicate(polynomials)
    factors = initial
    remaining = set(variables)
    protected = set(protected_variables)
    goal_variables = frozenset(
        goal_polynomial.free_symbols if goal_polynomial is not None else protected
    )
    steps: list[CertifiedCliqueEliminationStep] = []
    eliminated: list[str] = []
    blocked: set[sp.Symbol] = set()
    stopped_reason: str | None = None

    while remaining - protected - blocked:
        if max_steps is not None and len(steps) >= max_steps:
            stopped_reason = "max_steps"
            break
        adjacency = _primal_adjacency(factors)
        candidates: list[
            tuple[tuple[int, int, int, int, str], sp.Symbol, frozenset[sp.Symbol], tuple[sp.Expr, ...]]
        ] = []
        blocked_separator = False
        blocked_polynomials = False
        for variable in remaining - protected - blocked:
            neighbors = adjacency.get(variable, set()) & remaining
            if max_separator_variables is not None and len(neighbors) > max_separator_variables:
                blocked_separator = True
                continue
            clique = frozenset({variable, *neighbors})
            local = tuple(
                item for item in factors if item.free_symbols <= set(clique)
            )
            if len(local) > max_clique_polynomials:
                blocked_polynomials = True
                continue
            rank = (
                _fill_edge_count(variable, adjacency),
                len(neighbors),
                len(local),
                sum(_term_count(item) for item in local),
                str(variable),
            )
            candidates.append((rank, variable, clique, local))
        if not candidates:
            stopped_reason = (
                "separator_budget"
                if blocked_separator
                else "clique_polynomial_budget"
                if blocked_polynomials
                else "no_candidate"
            )
            break

        _, variable, clique, local = min(candidates, key=lambda item: item[0])
        if progress_callback is not None:
            progress_callback(
                {
                    "stage": "clique_started",
                    "variable": str(variable),
                    "separator_width": len(clique) - 1,
                    "input_polynomial_count": len(local),
                    "eliminated_variable_count": len(eliminated),
                }
            )
        if not any(variable in item.free_symbols for item in local):
            remaining.remove(variable)
            eliminated.append(str(variable))
            continue
        outputs, step = _clique_step(
            variable,
            clique,
            local,
            max_pairs=max_pairs_per_clique,
            max_basis_size=max_basis_size_per_clique,
            max_polynomial_terms=max_polynomial_terms,
            max_witness_terms=max_witness_terms,
            goal_variables=goal_variables,
            global_adjacency=adjacency,
            max_incomplete_messages=max_incomplete_messages,
        )
        if not step.replayed:
            stopped_reason = "certificate_replay_failed"
            break
        steps.append(step)
        if step.buchberger_complete:
            local_set = set(local)
            factors = _deduplicate(
                (*(item for item in factors if item not in local_set), *outputs)
            )
            remaining.remove(variable)
            eliminated.append(str(variable))
        else:
            # 部分基底は安全な帰結だが、消去イデアルと同値とは限らない。
            # 元の局所生成元を残し、得られた帰結だけを追加する。
            factors = _deduplicate((*factors, *outputs))
            blocked.add(variable)
        if progress_callback is not None:
            progress_callback(
                {
                    "stage": "clique_completed",
                    "variable": step.variable,
                    "separator_width": len(step.separator_variables),
                    "input_polynomial_count": len(step.input_polynomials),
                    "output_polynomial_count": len(step.output_polynomials),
                    "candidate_output_polynomial_count": len(
                        step.candidate_output_polynomials
                    ),
                    "coefficient_nonzero_obligation_count": len(
                        step.coefficient_nonzero_obligations
                    ),
                    "unit_leading_coefficient_available": (
                        step.unit_leading_coefficient_available
                    ),
                    "processed_pair_count": step.processed_pair_count,
                    "deferred_pair_count": step.deferred_pair_count,
                    "buchberger_complete": step.buchberger_complete,
                    "stopped_reason": step.stopped_reason,
                    "elimination_committed": step.elimination_committed,
                    "elapsed_seconds": step.elapsed_seconds,
                    "eliminated_variable_count": len(eliminated),
                }
            )

    if stopped_reason is None and remaining - protected:
        stopped_reason = "incomplete_local_basis"

    terminal_result = None
    goal_membership = None
    if goal_polynomial is not None:
        terminal_variables = tuple(
            sorted(
                set().union(
                    goal_polynomial.free_symbols,
                    *(item.free_symbols for item in factors),
                ),
                key=str,
            )
        )
        if terminal_variables:
            terminal_started = time.perf_counter()
            if progress_callback is not None:
                progress_callback(
                    {
                        "stage": "terminal_started",
                        "variable_count": len(terminal_variables),
                        "polynomial_count": len(factors),
                    }
                )
            terminal_result = certified_buchberger_dag(
                factors,
                terminal_variables,
                max_pairs=terminal_max_pairs,
                max_basis_size=terminal_max_basis_size,
                max_polynomial_terms=max_polynomial_terms,
                max_certificate_terms=max_witness_terms,
                membership_target=goal_polynomial,
                membership_check_interval=1,
            )
            goal_membership = certify_dag_ideal_membership(
                goal_polynomial,
                terminal_result,
            )
            if progress_callback is not None:
                progress_callback(
                    {
                        "stage": "terminal_completed",
                        "processed_pair_count": terminal_result.processed_pair_count,
                        "deferred_pair_count": terminal_result.deferred_pair_count,
                        "buchberger_complete": terminal_result.groebner_complete,
                        "stopped_reason": terminal_result.stopped_reason,
                        "goal_proved": goal_membership.proved,
                        "elapsed_seconds": time.perf_counter() - terminal_started,
                    }
                )
        elif sp.expand(goal_polynomial) == 0:
            terminal_result = certified_buchberger_dag(
                (),
                tuple(sorted(goal_polynomial.free_symbols, key=str)) or (sp.Symbol("_unit"),),
            )
            goal_membership = certify_dag_ideal_membership(
                goal_polynomial,
                terminal_result,
            )

    return ChordalBuchbergerEliminationResult(
        initial_polynomials=tuple(sp.sstr(item) for item in initial),
        remaining_polynomials=tuple(sp.sstr(item) for item in factors),
        remaining_variables=tuple(sorted(str(item) for item in remaining)),
        eliminated_variables=tuple(eliminated),
        steps=tuple(steps),
        stopped_reason=stopped_reason,
        local_complete_step_count=sum(item.buchberger_complete for item in steps),
        local_incomplete_step_count=sum(not item.buchberger_complete for item in steps),
        exact_replay=all(item.replayed for item in steps)
        and bool(terminal_result is None or terminal_result.all_identities_replayed)
        and bool(goal_membership is None or goal_membership.replayed),
        terminal_buchberger=terminal_result,
        goal_membership=goal_membership,
    )
