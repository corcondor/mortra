"""Bounded, certificate-carrying Wu--Ritt zero decomposition.

Unlike the earlier generic case splitter, every recursive child receives

    parent system + parent characteristic set + one vanished initial factor.

This is the recursion used by the formalized Wu--Ritt algorithm.  Budgets only
produce abstention; a parent is proved only when its regular component and all
degenerate children are proved or certified empty.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import asdict, dataclass
from typing import Iterable

import sympy as sp

from worker.backend.wu_polynomial_stalk import (
    canonical_irreducible_factors,
    condition_factor_keys,
)
from worker.backend.wu_ritt_characteristic import certified_wu_ritt_goal_proof


@dataclass(frozen=True)
class WuRittZeroBranch:
    branch_id: str
    parent_id: str | None
    depth: int
    locus: str
    status: str
    system_polynomials: tuple[str, ...]
    inherited_characteristic_set: tuple[str, ...]
    zero_factors: tuple[str, ...]
    nonzero_factors: tuple[str, ...]
    characteristic_set: tuple[str, ...]
    characteristic_rank: tuple[tuple[int, int], ...]
    characteristic_verified: bool
    rank_decreased: bool | None
    regularity_factors: tuple[str, ...]
    child_ids: tuple[str, ...]
    conditional_goal_proved: bool
    inconsistent_system: bool
    completion_rounds: int
    pseudo_division_steps: int
    maximum_term_count: int
    all_identities_replayed: bool
    certificate_sha256: str | None
    stopped_reason: str | None
    elapsed_seconds: float


@dataclass(frozen=True)
class CertifiedWuRittZeroDecomposition:
    theorem: str
    root_branch_id: str
    branches: tuple[WuRittZeroBranch, ...]
    solver_branch_count: int
    regular_leaf_count: int
    empty_leaf_count: int
    proved_leaf_count: int
    unresolved_leaf_count: int
    distinct_initial_factor_count: int
    rank_decrease_violations: int
    coverage_complete: bool
    all_branches_proved: bool
    all_characteristic_sets_verified: bool
    all_computed_identities_replayed: bool
    elapsed_seconds: float


@dataclass(frozen=True)
class _BranchState:
    branch_id: str
    parent_id: str | None
    depth: int
    system_polynomials: tuple[str, ...]
    inherited_characteristic_set: tuple[str, ...]
    zero_factors: tuple[str, ...]
    nonzero_factors: tuple[str, ...]
    parent_characteristic_rank: tuple[tuple[int, int], ...] | None


def _canonical_expression(expression: sp.Expr) -> str:
    expanded = sp.expand(expression)
    symbols = tuple(sorted(expanded.free_symbols, key=str))
    if not symbols:
        return sp.sstr(expanded)
    return sp.sstr(sp.Poly(expanded, *symbols, domain=sp.QQ).monic().as_expr())


def _deduplicate_text(expressions: Iterable[sp.Expr]) -> tuple[str, ...]:
    unique: dict[str, str] = {}
    for expression in expressions:
        expanded = sp.expand(expression)
        if expanded != 0:
            unique.setdefault(sp.sstr(expanded), sp.sstr(expanded))
    return tuple(unique.values())


def _deduplicate_polynomial_text(expressions: Iterable[str]) -> tuple[str, ...]:
    """Preserve already certified ring text without reparsing large polynomials."""

    return tuple(dict.fromkeys(item for item in expressions if item not in {"", "0"}))


def _factor_texts(initials: tuple[str, ...], symbols: dict[str, sp.Symbol]) -> tuple[str, ...]:
    factors: dict[str, str] = {}
    for initial in initials:
        expression = sp.sympify(initial, locals=symbols)
        for factor in canonical_irreducible_factors(expression):
            text = _canonical_expression(factor)
            factors.setdefault(text, text)
    return tuple(factors[key] for key in sorted(factors))


def _initial_texts(initials: tuple[str, ...], symbols: dict[str, sp.Symbol]) -> tuple[str, ...]:
    """Keep Wu--Ritt's original init(p) branches without eager factorization."""

    variable_names = tuple(symbols)
    unique: dict[str, str] = {}
    for initial in initials:
        if not any(name in initial for name in variable_names):
            continue
        unique.setdefault(initial, initial)
    return tuple(unique[key] for key in sorted(unique))


def _triangular_rank_less(
    child: tuple[tuple[int, int], ...],
    parent: tuple[tuple[int, int], ...],
) -> bool:
    """Lean's triangular-set lex order pads shorter chains with top."""

    for child_item, parent_item in zip(child, parent):
        if child_item != parent_item:
            return child_item < parent_item
    return len(child) > len(parent)


def _certificate_sha256(value: object) -> str:
    material = repr(value).encode()
    return hashlib.sha256(material).hexdigest()


def _closed(branch_id: str, records: dict[str, WuRittZeroBranch]) -> bool:
    branch = records[branch_id]
    if branch.status in {"proved", "proved_regular_locus", "empty_characteristic", "empty_by_input_ndg"}:
        return True
    if branch.status != "split" or not branch.child_ids:
        return False
    return all(_closed(child_id, records) for child_id in branch.child_ids)


def decompose_wu_ritt_zero_set(
    polynomials: Iterable[sp.Expr],
    variables: Iterable[sp.Symbol],
    goal_polynomial: sp.Expr,
    *,
    known_nonzero_conditions: tuple[str, ...] = (),
    max_depth: int = 2,
    max_solver_branches: int = 32,
    max_rounds: int = 32,
    max_reductions: int = 20_000,
    max_terms: int = 20_000,
    timeout_seconds_per_branch: float = 60.0,
    basic_set_mode: str = "standard",
    initial_branch_mode: str = "initial",
) -> CertifiedWuRittZeroDecomposition:
    """Run bounded Wu--Ritt recursion and retain a replayable branch cover."""

    if initial_branch_mode not in {"initial", "irreducible"}:
        raise ValueError("initial_branch_mode must be 'initial' or 'irreducible'")

    started = time.perf_counter()
    ordered_variables = tuple(variables)
    symbols = {str(item): item for item in ordered_variables}
    initial_system = _deduplicate_text(polynomials)
    known_nonzero = condition_factor_keys(known_nonzero_conditions)
    queue = [
        _BranchState(
            branch_id="B0",
            parent_id=None,
            depth=0,
            system_polynomials=initial_system,
            inherited_characteristic_set=(),
            zero_factors=(),
            nonzero_factors=(),
            parent_characteristic_rank=None,
        )
    ]
    records: dict[str, WuRittZeroBranch] = {}
    solver_branch_count = 0
    distinct_factors: set[str] = set()

    def budget_record(state: _BranchState, reason: str) -> WuRittZeroBranch:
        return WuRittZeroBranch(
            branch_id=state.branch_id,
            parent_id=state.parent_id,
            depth=state.depth,
            locus="root" if state.parent_id is None else "degenerate",
            status=reason,
            system_polynomials=state.system_polynomials,
            inherited_characteristic_set=state.inherited_characteristic_set,
            zero_factors=state.zero_factors,
            nonzero_factors=state.nonzero_factors,
            characteristic_set=(),
            characteristic_rank=(),
            characteristic_verified=False,
            rank_decreased=None,
            regularity_factors=(),
            child_ids=(),
            conditional_goal_proved=False,
            inconsistent_system=False,
            completion_rounds=0,
            pseudo_division_steps=0,
            maximum_term_count=0,
            all_identities_replayed=True,
            certificate_sha256=None,
            stopped_reason=reason,
            elapsed_seconds=0.0,
        )

    while queue:
        state = queue.pop(0)
        if any(factor in known_nonzero for factor in state.zero_factors):
            item = budget_record(state, "empty_by_input_ndg")
            records[state.branch_id] = WuRittZeroBranch(
                **{**asdict(item), "status": "empty_by_input_ndg", "stopped_reason": None}
            )
            continue
        if solver_branch_count >= max_solver_branches:
            records[state.branch_id] = budget_record(state, "branch_budget")
            continue

        branch_started = time.perf_counter()
        equations = tuple(
            sp.sympify(item, locals=symbols) for item in state.system_polynomials
        )
        proof = certified_wu_ritt_goal_proof(
            equations,
            ordered_variables,
            goal_polynomial,
            basic_set_mode=basic_set_mode,
            max_rounds=max_rounds,
            max_reductions=max_reductions,
            max_terms=max_terms,
            timeout_seconds=timeout_seconds_per_branch,
        )
        solver_branch_count += 1
        characteristic = proof.characteristic
        rank_decreased = (
            None
            if state.parent_characteristic_rank is None
            else _triangular_rank_less(
                characteristic.characteristic_rank,
                state.parent_characteristic_rank,
            )
        )
        regularity_factors = (
            _initial_texts(characteristic.initials, symbols)
            if initial_branch_mode == "initial"
            else _factor_texts(characteristic.initials, symbols)
        )
        distinct_factors.update(regularity_factors)
        status = "unresolved"
        child_ids: tuple[str, ...] = ()

        if not characteristic.characteristic_set_verified:
            status = "characteristic_incomplete"
        elif rank_decreased is False:
            status = "rank_not_decreased"
        elif proof.inconsistent_system:
            status = "empty_characteristic"
        elif not regularity_factors:
            status = "proved" if proof.conditional_goal_proved else "unresolved_regular_locus"
        else:
            regular_id = f"{state.branch_id}.R"
            zero_ids = tuple(
                f"{state.branch_id}.Z{index:02d}-{hashlib.sha256(factor.encode()).hexdigest()[:8]}"
                for index, factor in enumerate(regularity_factors, start=1)
            )
            child_ids = (regular_id, *zero_ids)
            records[regular_id] = WuRittZeroBranch(
                branch_id=regular_id,
                parent_id=state.branch_id,
                depth=state.depth + 1,
                locus="regular",
                status=(
                    "proved_regular_locus"
                    if proof.conditional_goal_proved
                    else "unresolved_regular_locus"
                ),
                system_polynomials=state.system_polynomials,
                inherited_characteristic_set=characteristic.characteristic_set,
                zero_factors=state.zero_factors,
                nonzero_factors=tuple(
                    dict.fromkeys((*state.nonzero_factors, *regularity_factors))
                ),
                characteristic_set=characteristic.characteristic_set,
                characteristic_rank=characteristic.characteristic_rank,
                characteristic_verified=True,
                rank_decreased=rank_decreased,
                regularity_factors=regularity_factors,
                child_ids=(),
                conditional_goal_proved=proof.conditional_goal_proved,
                inconsistent_system=False,
                completion_rounds=len(characteristic.rounds),
                pseudo_division_steps=characteristic.reduction_count + (
                    len(proof.goal_reduction.steps) if proof.goal_reduction else 0
                ),
                maximum_term_count=max(
                    characteristic.maximum_term_count,
                    proof.goal_reduction.maximum_term_count if proof.goal_reduction else 0,
                ),
                all_identities_replayed=proof.all_identities_replayed,
                certificate_sha256=_certificate_sha256(proof),
                stopped_reason=proof.stopped_reason,
                elapsed_seconds=0.0,
            )
            for child_id, factor in zip(zero_ids, regularity_factors, strict=True):
                child_system = _deduplicate_polynomial_text(
                    (
                        *state.system_polynomials,
                        *characteristic.characteristic_set,
                        factor,
                    )
                )
                child_state = _BranchState(
                    branch_id=child_id,
                    parent_id=state.branch_id,
                    depth=state.depth + 1,
                    system_polynomials=child_system,
                    inherited_characteristic_set=characteristic.characteristic_set,
                    zero_factors=tuple(dict.fromkeys((*state.zero_factors, factor))),
                    nonzero_factors=state.nonzero_factors,
                    parent_characteristic_rank=characteristic.characteristic_rank,
                )
                if state.depth >= max_depth:
                    records[child_id] = budget_record(child_state, "depth_budget")
                else:
                    queue.append(child_state)
            status = "split"

        records[state.branch_id] = WuRittZeroBranch(
            branch_id=state.branch_id,
            parent_id=state.parent_id,
            depth=state.depth,
            locus="root" if state.parent_id is None else "degenerate",
            status=status,
            system_polynomials=state.system_polynomials,
            inherited_characteristic_set=state.inherited_characteristic_set,
            zero_factors=state.zero_factors,
            nonzero_factors=state.nonzero_factors,
            characteristic_set=characteristic.characteristic_set,
            characteristic_rank=characteristic.characteristic_rank,
            characteristic_verified=characteristic.characteristic_set_verified,
            rank_decreased=rank_decreased,
            regularity_factors=regularity_factors,
            child_ids=child_ids,
            conditional_goal_proved=proof.conditional_goal_proved,
            inconsistent_system=proof.inconsistent_system,
            completion_rounds=len(characteristic.rounds),
            pseudo_division_steps=characteristic.reduction_count + (
                len(proof.goal_reduction.steps) if proof.goal_reduction else 0
            ),
            maximum_term_count=max(
                characteristic.maximum_term_count,
                proof.goal_reduction.maximum_term_count if proof.goal_reduction else 0,
            ),
            all_identities_replayed=proof.all_identities_replayed,
            certificate_sha256=_certificate_sha256(proof),
            stopped_reason=proof.stopped_reason,
            elapsed_seconds=time.perf_counter() - branch_started,
        )

    ordered_records = tuple(
        records[key]
        for key in sorted(records, key=lambda item: (item.count("."), item))
    )
    leaves = tuple(item for item in ordered_records if not item.child_ids)
    complete = _closed("B0", records)
    return CertifiedWuRittZeroDecomposition(
        theorem=(
            "For verified CS(P): V(P)=V(CS)\\V(IP) union "
            "union_{p in CS} V(P union CS union {init(p)}); irreducible "
            "factor branches refine each init(p)=0 component"
        ),
        root_branch_id="B0",
        branches=ordered_records,
        solver_branch_count=solver_branch_count,
        regular_leaf_count=sum(item.locus == "regular" for item in leaves),
        empty_leaf_count=sum(
            item.status in {"empty_characteristic", "empty_by_input_ndg"}
            for item in leaves
        ),
        proved_leaf_count=sum(
            item.status in {"proved", "proved_regular_locus"} for item in leaves
        ),
        unresolved_leaf_count=sum(
            item.status
            not in {"proved", "proved_regular_locus", "empty_characteristic", "empty_by_input_ndg"}
            for item in leaves
        ),
        distinct_initial_factor_count=len(distinct_factors),
        rank_decrease_violations=sum(item.rank_decreased is False for item in ordered_records),
        coverage_complete=complete,
        all_branches_proved=complete,
        all_characteristic_sets_verified=all(
            item.characteristic_verified
            for item in ordered_records
            if item.locus != "regular" and item.status not in {"branch_budget", "depth_budget", "empty_by_input_ndg"}
        ),
        all_computed_identities_replayed=all(
            item.all_identities_replayed for item in ordered_records
        ),
        elapsed_seconds=time.perf_counter() - started,
    )


def verify_wu_ritt_zero_decomposition(
    result: CertifiedWuRittZeroDecomposition,
) -> bool:
    """Independently check branch inheritance, topology, and promotion rules."""

    records = {item.branch_id: item for item in result.branches}
    if result.root_branch_id not in records:
        return False
    for branch in result.branches:
        if branch.status != "split":
            continue
        if len(branch.child_ids) != len(branch.regularity_factors) + 1:
            return False
        regular = records.get(branch.child_ids[0])
        if regular is None or regular.locus != "regular":
            return False
        if set(branch.regularity_factors) - set(regular.nonzero_factors):
            return False
        required = set(branch.system_polynomials) | set(branch.characteristic_set)
        for factor, child_id in zip(
            branch.regularity_factors,
            branch.child_ids[1:],
            strict=True,
        ):
            child = records.get(child_id)
            if child is None or child.parent_id != branch.branch_id:
                return False
            if factor not in child.zero_factors:
                return False
            if required - set(child.system_polynomials):
                return False
            if factor not in child.system_polynomials:
                return False
            if child.inherited_characteristic_set != branch.characteristic_set:
                return False
    complete = _closed(result.root_branch_id, records)
    return (
        result.coverage_complete == complete
        and result.all_branches_proved == complete
        and not (result.coverage_complete and result.rank_decrease_violations)
    )
