"""Certified constructible-set branching for Wu characteristic proofs.

The core invariant is the Wu--Ritt cover

    V(P) = (V(P) intersect D(H)) union union_f V(P union {f}),

where ``H`` is the product of the irreducible regularity factors used by a
conditional pseudo-remainder proof.  A parent is closed only when its regular
locus and every factor-zero child are closed.  Search budgets therefore cause
abstention, never proof promotion.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from typing import Iterable

import sympy as sp

from worker.backend.certified_wu_characteristic import (
    CertifiedWuResult,
    certified_sparse_wu_characteristic_proof,
    structural_variable_matching,
)
from worker.backend.wu_polynomial_stalk import (
    canonical_irreducible_factors,
    condition_factor_keys,
    coordinate_wu_polynomial_stalk,
    regularity_factor_expressions,
)
from worker.backend.constructible_groebner import (
    certify_constructible_groebner_branch,
)


@dataclass(frozen=True)
class WuZeroBranch:
    branch_id: str
    parent_id: str | None
    depth: int
    locus: str
    zero_factors: tuple[str, ...]
    nonzero_factors: tuple[str, ...]
    status: str
    cover_factors: tuple[str, ...]
    child_ids: tuple[str, ...]
    matching_complete: bool | None
    triangularization_complete: bool | None
    stopped_reason: str | None
    conditional_goal_proved: bool
    input_conditioned_goal_solved: bool
    open_regularity_count: int
    open_regularity_factors: tuple[str, ...]
    pseudo_division_steps: int
    maximum_term_count: int
    all_identities_replayed: bool
    exact_result_sha256: str | None
    elapsed_seconds: float


@dataclass(frozen=True)
class WuZeroDecompositionResult:
    theorem: str
    root_branch_id: str
    branches: tuple[WuZeroBranch, ...]
    solver_branch_count: int
    regular_leaf_count: int
    empty_leaf_count: int
    proved_leaf_count: int
    unresolved_leaf_count: int
    factorized_obligation_count: int
    distinct_branch_factor_count: int
    coverage_complete: bool
    all_branches_proved: bool
    all_computed_identities_replayed: bool
    elapsed_seconds: float


@dataclass(frozen=True)
class _BranchState:
    branch_id: str
    parent_id: str | None
    depth: int
    zero_factors: tuple[str, ...]
    nonzero_factors: tuple[str, ...]


def _canonical_expression(expression: sp.Expr) -> str:
    expanded = sp.expand(expression)
    symbols = tuple(sorted(expanded.free_symbols, key=str))
    if not symbols:
        return sp.sstr(expanded)
    return sp.sstr(sp.Poly(expanded, *symbols, domain=sp.QQ).monic().as_expr())


def _deduplicate_expressions(expressions: Iterable[sp.Expr]) -> tuple[sp.Expr, ...]:
    unique: dict[str, sp.Expr] = {}
    for expression in expressions:
        expanded = sp.expand(expression)
        if expanded == 0:
            continue
        unique.setdefault(sp.sstr(expanded), expanded)
    return tuple(unique.values())


def _result_sha256(result: CertifiedWuResult) -> str:
    material = json.dumps(asdict(result), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(material.encode()).hexdigest()


def _factor_key(expression: sp.Expr) -> str:
    factors = canonical_irreducible_factors(expression)
    if len(factors) != 1:
        raise ValueError("zero-decomposition branch guards must be irreducible")
    return sp.sstr(factors[0])


def _branch_elimination_order(
    equations: tuple[sp.Expr, ...],
    variables: tuple[sp.Symbol, ...],
    zero_factors: tuple[sp.Expr, ...],
    *,
    zero_first: bool,
) -> tuple[sp.Symbol, ...] | None:
    if not zero_factors or not zero_first:
        return None
    matching = structural_variable_matching(equations, variables)
    dependent = set(matching.dependent_variables)
    default = [name for name in reversed(matching.dependent_variables)]
    zero_symbols = {str(item) for factor in zero_factors for item in factor.free_symbols}
    zero_prefix = [
        str(variable)
        for variable in variables
        if str(variable) in dependent and str(variable) in zero_symbols
    ]
    names = tuple(dict.fromkeys((*zero_prefix, *default)))
    if set(names) != dependent:
        raise ValueError("branch elimination order lost a dependent variable")
    by_name = {str(item): item for item in variables}
    return tuple(by_name[name] for name in names)


def _closed_branch(branch_id: str, records: dict[str, WuZeroBranch]) -> bool:
    branch = records[branch_id]
    if branch.status in {
        "proved",
        "proved_regular_locus",
        "proved_by_groebner",
        "empty_by_input_ndg",
        "empty_by_groebner",
    }:
        return True
    if branch.status != "split" or not branch.child_ids:
        return False
    return all(_closed_branch(child_id, records) for child_id in branch.child_ids)


def decompose_wu_zero_set(
    polynomials: Iterable[sp.Expr],
    variables: Iterable[sp.Symbol],
    goal_polynomial: sp.Expr,
    *,
    known_nonzero_conditions: tuple[str, ...] = (),
    max_depth: int = 1,
    max_solver_branches: int = 16,
    max_reductions: int = 10_000,
    max_terms: int = 20_000,
    timeout_seconds_per_branch: float = 60.0,
    root_timeout_seconds: float | None = None,
    normalize_remainders: bool = True,
    max_content_terms: int = 5_000,
    zero_first_elimination: bool = True,
    enable_groebner_fallback: bool = False,
    groebner_max_pairs: int = 2_000,
    groebner_max_basis_size: int = 128,
    groebner_max_polynomial_terms: int = 2_000,
    groebner_max_certificate_terms: int = 20_000,
) -> WuZeroDecompositionResult:
    """Recursively cover a polynomial zero set by regular and degenerate loci."""

    started = time.perf_counter()
    base_polynomials = _deduplicate_expressions(polynomials)
    ordered_variables = tuple(variables)
    symbols = {str(item): item for item in ordered_variables}
    known_keys = condition_factor_keys(known_nonzero_conditions)
    queue = [_BranchState("B0", None, 0, (), ())]
    records: dict[str, WuZeroBranch] = {}
    solver_branch_count = 0
    factorized_obligation_count = 0
    distinct_factors: set[str] = set()

    while queue:
        state = queue.pop(0)
        zero_expressions = tuple(
            sp.sympify(item, locals=symbols) for item in state.zero_factors
        )
        zero_keys = {_factor_key(item) for item in zero_expressions}
        if zero_keys & known_keys:
            records[state.branch_id] = WuZeroBranch(
                branch_id=state.branch_id,
                parent_id=state.parent_id,
                depth=state.depth,
                locus="degenerate",
                zero_factors=state.zero_factors,
                nonzero_factors=state.nonzero_factors,
                status="empty_by_input_ndg",
                cover_factors=(),
                child_ids=(),
                matching_complete=None,
                triangularization_complete=None,
                stopped_reason=None,
                conditional_goal_proved=False,
                input_conditioned_goal_solved=False,
                open_regularity_count=0,
                open_regularity_factors=(),
                pseudo_division_steps=0,
                maximum_term_count=0,
                all_identities_replayed=True,
                exact_result_sha256=None,
                elapsed_seconds=0.0,
            )
            continue
        if solver_branch_count >= max_solver_branches:
            records[state.branch_id] = WuZeroBranch(
                branch_id=state.branch_id,
                parent_id=state.parent_id,
                depth=state.depth,
                locus="root" if state.parent_id is None else "degenerate",
                zero_factors=state.zero_factors,
                nonzero_factors=state.nonzero_factors,
                status="branch_budget",
                cover_factors=(),
                child_ids=(),
                matching_complete=None,
                triangularization_complete=None,
                stopped_reason="branch_budget",
                conditional_goal_proved=False,
                input_conditioned_goal_solved=False,
                open_regularity_count=0,
                open_regularity_factors=(),
                pseudo_division_steps=0,
                maximum_term_count=0,
                all_identities_replayed=True,
                exact_result_sha256=None,
                elapsed_seconds=0.0,
            )
            continue

        branch_started = time.perf_counter()
        equations = _deduplicate_expressions((*base_polynomials, *zero_expressions))
        elimination_order = _branch_elimination_order(
            equations,
            ordered_variables,
            zero_expressions,
            zero_first=zero_first_elimination,
        )
        result = certified_sparse_wu_characteristic_proof(
            equations,
            ordered_variables,
            goal_polynomial,
            max_reductions=max_reductions,
            max_terms=max_terms,
            timeout_seconds=(
                root_timeout_seconds
                if state.depth == 0 and root_timeout_seconds is not None
                else timeout_seconds_per_branch
            ),
            normalize_remainders=normalize_remainders,
            max_content_terms=max_content_terms,
            elimination_order=elimination_order,
            require_complete_matching=not zero_expressions,
        )
        solver_branch_count += 1
        branch_nonzero_conditions = (
            *known_nonzero_conditions,
            *(f"{item} != 0" for item in state.nonzero_factors),
        )
        coordination = coordinate_wu_polynomial_stalk(
            result,
            known_nonzero_conditions=tuple(branch_nonzero_conditions),
        )
        open_factors = regularity_factor_expressions(
            coordination.open_regularity_obligations
        )
        open_factor_text = tuple(_canonical_expression(item) for item in open_factors)
        factorized_obligation_count += coordination.open_regularity_count
        distinct_factors.update(open_factor_text)
        status = "unresolved"
        cover_factors: tuple[str, ...] = ()
        child_ids: tuple[str, ...] = ()
        groebner_fallback = None
        repeated_zero = zero_keys & set(open_factor_text)
        can_split_before_groebner = bool(
            coordination.conditional_goal_solved
            and open_factor_text
            and not repeated_zero
            and state.depth < max_depth
        )

        if coordination.input_conditioned_goal_solved:
            status = "proved"
        elif enable_groebner_fallback and not can_split_before_groebner:
            condition_expressions: list[sp.Expr] = []
            for condition in branch_nonzero_conditions:
                expression = condition.strip()
                if expression.endswith("!= 0"):
                    expression = expression[:-4].strip()
                elif expression.endswith("!=0"):
                    expression = expression[:-3].strip()
                condition_expressions.append(sp.sympify(expression, locals=symbols))
            groebner_fallback = certify_constructible_groebner_branch(
                equations,
                ordered_variables,
                goal_polynomial,
                nonzero_factors=condition_expressions,
                max_pairs=groebner_max_pairs,
                max_basis_size=groebner_max_basis_size,
                max_polynomial_terms=groebner_max_polynomial_terms,
                max_certificate_terms=groebner_max_certificate_terms,
            )
            if groebner_fallback.status == "empty":
                status = "empty_by_groebner"
            elif groebner_fallback.status == "goal_proved":
                status = "proved_by_groebner"
        if status == "unresolved" and coordination.conditional_goal_solved:
            if repeated_zero:
                status = "regularity_cycle"
            elif state.depth >= max_depth:
                status = "depth_budget"
            else:
                regular_id = f"{state.branch_id}.R"
                zero_ids = tuple(
                    f"{state.branch_id}.Z{index:02d}-{hashlib.sha256(factor.encode()).hexdigest()[:8]}"
                    for index, factor in enumerate(open_factor_text, start=1)
                )
                child_ids = (regular_id, *zero_ids)
                cover_factors = open_factor_text
                records[regular_id] = WuZeroBranch(
                    branch_id=regular_id,
                    parent_id=state.branch_id,
                    depth=state.depth + 1,
                    locus="regular",
                    zero_factors=state.zero_factors,
                    nonzero_factors=tuple(
                        dict.fromkeys((*state.nonzero_factors, *open_factor_text))
                    ),
                    status="proved_regular_locus",
                    cover_factors=(),
                    child_ids=(),
                    matching_complete=result.matching.complete,
                    triangularization_complete=result.triangularization_complete,
                    stopped_reason=None,
                    conditional_goal_proved=True,
                    input_conditioned_goal_solved=True,
                    open_regularity_count=0,
                    open_regularity_factors=(),
                    pseudo_division_steps=(
                        len(result.triangulation_steps) + len(result.goal_steps)
                    ),
                    maximum_term_count=result.maximum_term_count,
                    all_identities_replayed=(
                        result.all_identities_replayed
                        and coordination.conditional_goal_replayed
                    ),
                    exact_result_sha256=_result_sha256(result),
                    elapsed_seconds=0.0,
                )
                queue.extend(
                    _BranchState(
                        branch_id=child_id,
                        parent_id=state.branch_id,
                        depth=state.depth + 1,
                        zero_factors=tuple(
                            dict.fromkeys((*state.zero_factors, factor))
                        ),
                        nonzero_factors=state.nonzero_factors,
                    )
                    for child_id, factor in zip(zero_ids, open_factor_text, strict=True)
                )
                status = "split"

        records[state.branch_id] = WuZeroBranch(
            branch_id=state.branch_id,
            parent_id=state.parent_id,
            depth=state.depth,
            locus="root" if state.parent_id is None else "degenerate",
            zero_factors=state.zero_factors,
            nonzero_factors=state.nonzero_factors,
            status=status,
            cover_factors=cover_factors,
            child_ids=child_ids,
            matching_complete=result.matching.complete,
            triangularization_complete=result.triangularization_complete,
            stopped_reason=result.stopped_reason,
            conditional_goal_proved=result.conditional_goal_proved,
            input_conditioned_goal_solved=coordination.input_conditioned_goal_solved,
            open_regularity_count=coordination.open_regularity_count,
            open_regularity_factors=open_factor_text,
            pseudo_division_steps=(
                len(result.triangulation_steps) + len(result.goal_steps)
            ),
            maximum_term_count=result.maximum_term_count,
            all_identities_replayed=(
                groebner_fallback.all_identities_replayed
                if groebner_fallback is not None
                and status in {"empty_by_groebner", "proved_by_groebner"}
                else result.all_identities_replayed
                and (
                    not result.conditional_goal_proved
                    or coordination.conditional_goal_replayed
                )
            ),
            exact_result_sha256=(
                groebner_fallback.certificate_sha256
                if groebner_fallback is not None
                and status in {"empty_by_groebner", "proved_by_groebner"}
                else _result_sha256(result)
            ),
            elapsed_seconds=time.perf_counter() - branch_started,
        )

    ordered_records = tuple(
        records[key]
        for key in sorted(records, key=lambda item: (item.count("."), item))
    )
    leaves = tuple(item for item in ordered_records if not item.child_ids)
    coverage_complete = _closed_branch("B0", records)
    return WuZeroDecompositionResult(
        theorem=(
            "V(P)=V(P)∩D(H)∪⋃_{f|H}V(P∪{f}); a split closes only when "
            "the regular locus and every irreducible factor-zero child close"
        ),
        root_branch_id="B0",
        branches=ordered_records,
        solver_branch_count=solver_branch_count,
        regular_leaf_count=sum(item.locus == "regular" for item in leaves),
        empty_leaf_count=sum(
            item.status in {"empty_by_input_ndg", "empty_by_groebner"}
            for item in leaves
        ),
        proved_leaf_count=sum(
            item.status
            in {"proved", "proved_regular_locus", "proved_by_groebner"}
            for item in leaves
        ),
        unresolved_leaf_count=sum(
            item.status
            not in {
                "proved",
                "proved_regular_locus",
                "proved_by_groebner",
                "empty_by_input_ndg",
                "empty_by_groebner",
            }
            for item in leaves
        ),
        factorized_obligation_count=factorized_obligation_count,
        distinct_branch_factor_count=len(distinct_factors),
        coverage_complete=coverage_complete,
        all_branches_proved=coverage_complete,
        all_computed_identities_replayed=all(
            item.all_identities_replayed for item in ordered_records
        ),
        elapsed_seconds=time.perf_counter() - started,
    )


def verify_zero_decomposition_cover(result: WuZeroDecompositionResult) -> bool:
    """Replay the finite branch topology independently of the search loop."""

    records = {item.branch_id: item for item in result.branches}
    if result.root_branch_id not in records:
        return False
    for branch in result.branches:
        if branch.status != "split":
            continue
        if len(branch.child_ids) != len(branch.cover_factors) + 1:
            return False
        regular = records.get(branch.child_ids[0])
        if regular is None or regular.status != "proved_regular_locus":
            return False
        if set(branch.cover_factors) - set(regular.nonzero_factors):
            return False
        for factor, child_id in zip(
            branch.cover_factors,
            branch.child_ids[1:],
            strict=True,
        ):
            child = records.get(child_id)
            if child is None or factor not in child.zero_factors:
                return False
            if child.parent_id != branch.branch_id:
                return False
    return (
        result.coverage_complete == _closed_branch(result.root_branch_id, records)
        and result.all_branches_proved == result.coverage_complete
    )
