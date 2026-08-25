import sympy as sp

from worker.backend.source_preserving_polynomial_reduction import (
    lift_reduced_multipliers,
    reduce_by_monic_univariate_relations,
    retarget_source_preserving_reduction,
)


def test_monic_reduction_and_multiplier_lift_replay() -> None:
    x, a, b = sp.symbols("x a b")
    source = (x - a, x**3 + b)
    goal = x**3 + b

    reduction = reduce_by_monic_univariate_relations(source, (x,), goal)

    assert reduction.reducer_input_indices == (0,)
    assert reduction.eliminated_reducer_input_indices == (0,)
    assert reduction.reduced_variables == ()
    assert len(reduction.reduced_polynomials) == 1
    assert reduction.reduced_polynomials[0].input_index == 1
    assert reduction.reduced_polynomials[0].expression == a**3 + b
    assert reduction.reduced_goal == a**3 + b
    lifted = lift_reduced_multipliers(reduction, (1,))
    assert lifted == (0, 1)


def test_quadratic_reducer_remains_in_the_quotient_proof_ring() -> None:
    x, a, b = sp.symbols("x a b")
    source = (x**2 - a, x**3 + b)

    reduction = reduce_by_monic_univariate_relations(source, (x,), x**3 + b)

    assert reduction.reducer_input_indices == (0,)
    assert reduction.eliminated_reducer_input_indices == ()
    assert reduction.reduced_variables == (x,)
    assert len(reduction.reduced_polynomials) == 2
    assert reduction.reduced_polynomials[1].expression == a * x + b
    assert lift_reduced_multipliers(reduction, (0, 1)) == (0, 1)


def test_retarget_reuses_source_reduction_and_replays_new_goal() -> None:
    x, a, b = sp.symbols("x a b")
    source = (x**2 - a, x**3 + b)
    initial = reduce_by_monic_univariate_relations(source, (x,), x**3 + b)

    retargeted = retarget_source_preserving_reduction(initial, x**4 - a**2)
    fresh = reduce_by_monic_univariate_relations(source, (x,), x**4 - a**2)

    assert retargeted.reduced_polynomials == initial.reduced_polynomials
    assert retargeted.reduced_goal == fresh.reduced_goal == 0
    assert retargeted.goal_reducer_quotients == fresh.goal_reducer_quotients
    lifted = lift_reduced_multipliers(retargeted, (0, 0))
    assert sp.expand(
        retargeted.goal
        - sum(
            multiplier * polynomial
            for multiplier, polynomial in zip(lifted, source, strict=True)
        )
    ) == 0


def test_only_monic_univariate_relations_are_selected() -> None:
    x, y, a = sp.symbols("x y a")
    reduction = reduce_by_monic_univariate_relations(
        (a * x**2 - 1, x + y),
        (x, y),
        x,
    )

    assert reduction.reducer_input_indices == ()


def test_no_reducer_preserves_factored_expression_dag() -> None:
    x, y, a = sp.symbols("x y a")
    factored = (x + y) ** 6 * (a + x)

    reduction = reduce_by_monic_univariate_relations(
        (factored, x + y),
        (x, y),
        factored,
        max_degree=0,
    )

    assert reduction.reducer_input_indices == ()
    assert reduction.reduced_polynomials[0].expression == factored
    assert reduction.reduced_goal == factored
    assert reduction.reduced_goal != sp.expand(factored)
