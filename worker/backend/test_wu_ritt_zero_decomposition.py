import sympy as sp

from worker.backend.wu_ritt_zero_decomposition import (
    decompose_wu_ritt_zero_set,
    verify_wu_ritt_zero_decomposition,
)


def test_paper_recursion_inherits_characteristic_set_and_closes() -> None:
    a, x = sp.symbols("a x")
    result = decompose_wu_ritt_zero_set(
        (a * x, (1 - a) * x),
        (a, x),
        x,
        max_depth=2,
        max_solver_branches=8,
        timeout_seconds_per_branch=10,
    )
    root = {item.branch_id: item for item in result.branches}["B0"]
    zero_child = {item.branch_id: item for item in result.branches}[root.child_ids[1]]

    assert root.status == "split"
    assert root.characteristic_verified
    assert root.characteristic_set == ("a*x",)
    assert set(root.characteristic_set).issubset(zero_child.system_polynomials)
    assert "a" in zero_child.system_polynomials
    assert zero_child.rank_decreased
    assert result.coverage_complete
    assert result.rank_decrease_violations == 0
    assert result.all_computed_identities_replayed
    assert verify_wu_ritt_zero_decomposition(result)


def test_unproved_zero_branch_prevents_promotion() -> None:
    a, x = sp.symbols("a x")
    result = decompose_wu_ritt_zero_set(
        (a * x,),
        (a, x),
        x,
        max_depth=2,
        max_solver_branches=8,
        timeout_seconds_per_branch=10,
    )

    assert not result.coverage_complete
    assert result.unresolved_leaf_count > 0
    assert verify_wu_ritt_zero_decomposition(result)


def test_depth_budget_keeps_regular_proof_but_not_global_promotion() -> None:
    a, x = sp.symbols("a x")
    result = decompose_wu_ritt_zero_set(
        (a * x, (1 - a) * x),
        (a, x),
        x,
        max_depth=0,
        max_solver_branches=8,
        timeout_seconds_per_branch=10,
    )

    assert not result.coverage_complete
    assert result.regular_leaf_count == 1
    assert any(item.status == "depth_budget" for item in result.branches)
    assert verify_wu_ritt_zero_decomposition(result)


def test_input_ndg_eliminates_contradictory_degenerate_branch() -> None:
    a, x = sp.symbols("a x")
    result = decompose_wu_ritt_zero_set(
        (a * x,),
        (a, x),
        x,
        known_nonzero_conditions=("a != 0",),
        max_depth=2,
        max_solver_branches=8,
        timeout_seconds_per_branch=10,
    )

    assert result.coverage_complete
    assert any(item.status == "empty_by_input_ndg" for item in result.branches)
    assert verify_wu_ritt_zero_decomposition(result)


def test_zero_decomposition_accepts_verified_weak_basic_set() -> None:
    x, y = sp.symbols("x y")
    result = decompose_wu_ritt_zero_set(
        (x - y, y - 1),
        (x, y),
        x - 1,
        basic_set_mode="weak",
    )

    assert result.coverage_complete
    assert result.all_characteristic_sets_verified
    assert verify_wu_ritt_zero_decomposition(result)


def test_initial_branch_mode_does_not_require_irreducible_factorization() -> None:
    a, b, x = sp.symbols("a b x")
    result = decompose_wu_ritt_zero_set(
        (a * b * x, (1 - a * b) * x),
        (a, b, x),
        x,
        max_depth=0,
        initial_branch_mode="initial",
    )
    root = {item.branch_id: item for item in result.branches}["B0"]

    assert root.status == "split"
    assert len(root.regularity_factors) == 1
    assert "a*b" in root.regularity_factors[0]
    assert verify_wu_ritt_zero_decomposition(result)
