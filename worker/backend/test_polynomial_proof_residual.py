import sympy as sp

from worker.backend.polynomial_proof_residual import (
    bounded_normal_form_residual,
)


def test_bounded_normal_form_replays_a_transitive_ideal_membership() -> None:
    x, y, z = sp.symbols("x y z")

    result = bounded_normal_form_residual(
        (x - y, y - z),
        ((x - z,),),
    )

    atom = result.branches[0].atoms[0]
    assert atom.proved and atom.replayed
    assert atom.remainder == "0"
    assert result.selected_rank == (0, 0, 0, 0)
    assert result.basis_replayed


def test_and_or_residual_never_combines_incompatible_branches() -> None:
    x, y, z = sp.symbols("x y z")

    result = bounded_normal_form_residual(
        (x - y,),
        (
            (x - y, y - z),
            (x - y,),
        ),
        max_pairs=0,
    )

    assert result.branches[0].open_atom_count == 1
    assert result.branches[1].open_atom_count == 0
    assert result.selected_branch_index == 1
    assert result.selected_rank == (0, 0, 0, 0)


def test_nonzero_incomplete_residual_is_not_promoted_to_a_proof() -> None:
    x, y = sp.symbols("x y")

    result = bounded_normal_form_residual(
        (x * y - 1, x**2 - y),
        ((y - 1,),),
        max_pairs=0,
    )

    atom = result.branches[0].atoms[0]
    assert not atom.proved
    assert atom.replayed
    assert result.selected_rank[0] == 1


def test_direct_message_reduction_replays_without_claiming_complete_basis() -> None:
    x, y, z = sp.symbols("x y z")

    result = bounded_normal_form_residual(
        (x - y, y - z),
        ((x - z,),),
        direct_message_reduction=True,
    )

    assert result.selected_rank == (0, 0, 0, 0)
    assert result.basis_replayed
    assert not result.basis_complete
    assert result.stopped_reason == "direct_message_reduction"


def test_linear_span_chart_closes_combination_missed_by_ordered_division() -> None:
    x, y = sp.symbols("x y")
    generators = (x + y, x - y)
    ordered = bounded_normal_form_residual(
        generators,
        ((2 * x,),),
        direct_message_reduction=True,
    )
    chart = bounded_normal_form_residual(
        generators,
        ((2 * x,),),
        linear_span_reduction=True,
    )

    assert ordered.selected_rank[0] == 1
    assert chart.selected_rank == (0, 0, 0, 0)
    assert chart.branches[0].atoms[0].proved
    assert chart.branches[0].atoms[0].replayed
    assert not chart.basis_complete
    assert chart.stopped_reason == "linear_span_reduction"
