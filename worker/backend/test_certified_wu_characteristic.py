import sympy as sp
from sympy.polys.domains import QQ
from sympy.polys.rings import ring

from worker.backend.certified_wu_characteristic import (
    _sparse_pseudo_division,
    SparsePseudoDivisionBudgetExceeded,
    certified_pseudo_division,
    certified_sparse_wu_characteristic_proof,
    certified_wu_characteristic_proof,
    structural_min_fill_elimination_order,
    structural_variable_matching,
)


def test_pseudo_division_replays_the_exact_identity() -> None:
    x, y = sp.symbols("x y")
    certificate = certified_pseudo_division(
        x**2 + x * y,
        2 * x + 2,
        x,
        phase="test",
    )
    assert certificate.replayed
    assert certificate.multiplier == "4"
    assert sp.expand(sp.sympify(certificate.remainder) - (4 - 4 * y)) == 0


def test_structural_matching_leaves_an_early_parameter_free() -> None:
    x, y, z = sp.symbols("x y z")
    result = structural_variable_matching((y - x, z - y**2), (x, y, z))
    assert result.complete
    assert result.dependent_variables == ("y", "z")
    assert result.parameter_variables == ("x",)


def test_wu_chain_proves_a_composed_polynomial_identity() -> None:
    x, y, z = sp.symbols("x y z")
    result = certified_wu_characteristic_proof(
        (y - x, z - y**2),
        (x, y, z),
        z - x**2,
        timeout_seconds=10,
    )
    assert result.triangularization_complete
    assert result.all_identities_replayed
    assert result.final_remainder == "0"
    assert result.conditional_goal_proved
    assert result.unconditional_goal_proved


def test_wu_chain_keeps_a_nonzero_initial_as_an_open_obligation() -> None:
    a, x = sp.symbols("a x")
    result = certified_wu_characteristic_proof(
        (a * x,),
        (a, x),
        x,
        timeout_seconds=10,
    )
    assert result.triangularization_complete
    assert result.conditional_goal_proved
    assert not result.unconditional_goal_proved
    assert result.nonzero_obligations == ("Ne(a, 0)",)


def test_unmatched_equation_abstains() -> None:
    x = sp.symbols("x")
    result = certified_wu_characteristic_proof(
        (x, x + 1),
        (x,),
        x,
        timeout_seconds=10,
    )
    assert not result.matching.complete
    assert result.stopped_reason == "structural_matching_incomplete"
    assert not result.conditional_goal_proved


def test_sparse_wu_replays_the_same_composed_identity() -> None:
    x, y, z = sp.symbols("x y z")
    result = certified_sparse_wu_characteristic_proof(
        (y - x, z - y**2),
        (x, y, z),
        z - x**2,
        timeout_seconds=10,
    )
    assert result.triangularization_complete
    assert result.all_identities_replayed
    assert result.conditional_goal_proved
    assert result.unconditional_goal_proved


def test_sparse_pseudo_division_replays_for_a_nonfirst_variable() -> None:
    x, y, z = sp.symbols("x y z")
    result = certified_sparse_wu_characteristic_proof(
        (z - y**2,),
        (x, y, z),
        z - x**2,
        timeout_seconds=10,
    )
    assert result.goal_steps[0].quotient == "1"
    assert result.goal_steps[0].replayed


def test_sparse_wu_preserves_nonzero_obligations() -> None:
    a, x = sp.symbols("a x")
    result = certified_sparse_wu_characteristic_proof(
        (a * x,),
        (a, x),
        x,
        timeout_seconds=10,
    )
    assert result.conditional_goal_proved
    assert not result.unconditional_goal_proved
    assert result.nonzero_obligations == ("Ne(a, 0)",)


def test_sparse_content_reduction_keeps_factor_in_replayed_identity() -> None:
    polynomial_ring, a, x, y, z = ring("a,x,y,z", QQ)
    certificate, remainder = _sparse_pseudo_division(
        a * x + a * z,
        x + y,
        1,
        "x",
        phase="test",
    )
    assert certificate.replayed
    assert certificate.remainder_multiplier == "a"
    assert remainder == z - y
    assert certificate.normalization_nonzero_obligation == "Ne(a, 0)"


def test_sparse_content_reduction_can_be_ablated() -> None:
    polynomial_ring, a, x, y, z = ring("a,x,y,z", QQ)
    certificate, remainder = _sparse_pseudo_division(
        a * x + a * z,
        x + y,
        1,
        "x",
        phase="test",
        normalize_remainder=False,
    )
    assert certificate.replayed
    assert certificate.remainder_multiplier == "1"
    assert remainder == a * z - a * y
    assert certificate.normalization_nonzero_obligation is None


def test_sparse_pseudo_division_aborts_inside_an_oversized_local_step() -> None:
    polynomial_ring, x, y = ring("x,y", QQ)
    with __import__("pytest").raises(SparsePseudoDivisionBudgetExceeded):
        _sparse_pseudo_division(
            (x + y) ** 8,
            x + y**2,
            0,
            "x",
            phase="test",
            max_intermediate_terms=5,
        )


def test_min_fill_order_is_structural_and_keeps_goal_variable_late() -> None:
    center, left, right, goal = sp.symbols("center left right goal")
    polynomials = (
        center - left,
        center - right,
        goal - center,
    )
    order = structural_min_fill_elimination_order(
        polynomials,
        (center, left, right, goal),
        protected_variables=(goal,),
    )
    assert order[-1] == goal
    assert set(order) == {center, left, right, goal}


def test_redundant_dependent_variable_may_vanish_without_aborting_chain() -> None:
    x, y, z = sp.symbols("x y z")
    result = certified_sparse_wu_characteristic_proof(
        (y - x, z - x, z - y),
        (x, y, z),
        z - x,
        timeout_seconds=10,
    )
    assert result.triangularization_complete
    assert result.stopped_reason is None
    assert result.conditional_goal_proved
