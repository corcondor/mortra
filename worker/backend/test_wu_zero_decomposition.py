import sympy as sp

from worker.backend.wu_zero_decomposition import (
    decompose_wu_zero_set,
    verify_zero_decomposition_cover,
)


def test_zero_decomposition_closes_regular_and_degenerate_loci() -> None:
    a, x = sp.symbols("a x")
    result = decompose_wu_zero_set(
        (a * x, (1 - a) * x),
        (a, x),
        x,
        max_depth=1,
        max_solver_branches=4,
        timeout_seconds_per_branch=10,
    )
    branches = {item.branch_id: item for item in result.branches}

    assert branches["B0"].status == "split"
    assert branches["B0.R"].status == "proved_regular_locus"
    zero_child = branches[branches["B0"].child_ids[1]]
    assert zero_child.zero_factors == ("a",)
    assert zero_child.status == "proved"
    assert result.coverage_complete
    assert result.all_branches_proved
    assert result.all_computed_identities_replayed
    assert verify_zero_decomposition_cover(result)


def test_zero_first_order_is_a_real_ablation_not_a_hidden_answer() -> None:
    a, x = sp.symbols("a x")
    result = decompose_wu_zero_set(
        (a * x, (1 - a) * x),
        (a, x),
        x,
        max_depth=2,
        max_solver_branches=4,
        timeout_seconds_per_branch=10,
        zero_first_elimination=False,
    )

    assert not result.coverage_complete
    assert any(item.status == "regularity_cycle" for item in result.branches)
    assert verify_zero_decomposition_cover(result)


def test_unproved_degenerate_locus_prevents_parent_promotion() -> None:
    a, x = sp.symbols("a x")
    result = decompose_wu_zero_set(
        (a * x,),
        (a, x),
        x,
        max_depth=1,
        max_solver_branches=4,
        timeout_seconds_per_branch=10,
    )

    assert not result.coverage_complete
    assert result.unresolved_leaf_count > 0
    assert verify_zero_decomposition_cover(result)


def test_input_nonzero_condition_closes_the_regular_proof_without_branching() -> None:
    a, x = sp.symbols("a x")
    result = decompose_wu_zero_set(
        (a * x,),
        (a, x),
        x,
        known_nonzero_conditions=("a != 0",),
        max_depth=1,
        max_solver_branches=2,
        timeout_seconds_per_branch=10,
    )

    assert result.coverage_complete
    assert len(result.branches) == 1
    assert result.branches[0].status == "proved"
    assert verify_zero_decomposition_cover(result)


def test_branch_budget_never_promotes_an_incomplete_cover() -> None:
    a, b, x = sp.symbols("a b x")
    result = decompose_wu_zero_set(
        (a * b * x,),
        (a, b, x),
        x,
        max_depth=2,
        max_solver_branches=1,
        timeout_seconds_per_branch=10,
    )

    assert not result.coverage_complete
    assert any(item.status == "branch_budget" for item in result.branches)
    assert verify_zero_decomposition_cover(result)
