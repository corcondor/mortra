import sympy as sp

from worker.backend.source_guarded_linear_elimination import (
    _fraction_free_structural,
    _linear_coefficients_structural,
    eliminate_source_guarded_linear_variables,
    lift_guarded_linear_certificate,
    source_preserving_goal_factor_candidates,
    source_proved_nondegeneracy_factors,
)


def test_structural_linear_coefficients_preserve_factored_context() -> None:
    x, y, a, b, c = sp.symbols("x y a b c")
    expression = (a * x + b) * (y + 1) + c

    coefficients = _linear_coefficients_structural(expression, x)

    assert coefficients is not None
    constant, coefficient = coefficients
    assert sp.expand(constant - (b * (y + 1) + c)) == 0
    assert sp.expand(coefficient - a * (y + 1)) == 0
    assert _linear_coefficients_structural(expression * (x + 1), x) is None


def test_structural_fraction_free_substitution_replays_without_expanding() -> None:
    x, y, z, a, b = sp.symbols("x y z a b")
    pivot = a * x + b
    expression = (x + y) ** 4 * (x - z) + (x + 1) ** 2

    degree, transformed, quotient = _fraction_free_structural(
        expression,
        x,
        a,
        b,
        pivot,
    )

    assert degree == 5
    assert sp.expand(a**degree * expression - transformed - quotient * pivot) == 0
    assert transformed != sp.expand(transformed)


def test_guarded_linear_elimination_and_source_lift_replay() -> None:
    x, a, b, c = sp.symbols("x a b c")
    source = (a * x + b, x - c)
    goal = a * c + b

    reduced = eliminate_source_guarded_linear_variables(
        source,
        (x,),
        goal,
        (a,),
        max_steps=1,
    )

    assert reduced.reduced_variables == ()
    assert reduced.reduced_source_indices == (1,)
    assert sp.expand(reduced.reduced_polynomials[0] + goal) == 0
    lifted = lift_guarded_linear_certificate(reduced, (-1,))
    assert lifted.goal_multiplier == 1
    assert lifted.source_multipliers == (1, -a)
    assert lifted.replay_residual == 0
    assert lifted.replayed
    assert lifted.multiplier_source_proved_nonzero


def test_guarded_linear_elimination_rejects_unproved_coefficient() -> None:
    x, a, b = sp.symbols("x a b")
    reduced = eliminate_source_guarded_linear_variables(
        (a * x + b,),
        (x,),
        b,
        (),
    )

    assert reduced.steps == ()
    assert reduced.reduced_variables == (x,)


def test_two_guarded_eliminations_lift_one_reduced_certificate() -> None:
    x, y, a, b, c, d, e = sp.symbols("x y a b c d e")
    source = (a * x + b, d * y + e, x + y - c)
    goal = a * d * c + b * d + a * e
    reduced = eliminate_source_guarded_linear_variables(
        source,
        (x, y),
        goal,
        (a, d),
        max_steps=2,
    )

    assert reduced.reduced_variables == ()
    assert reduced.reduced_source_indices == (2,)
    multiplier = sp.cancel(reduced.reduced_goal / reduced.reduced_polynomials[0])
    lifted = lift_guarded_linear_certificate(reduced, (multiplier,))
    assert lifted.replayed
    assert lifted.multiplier_source_proved_nonzero
    assert lifted.replay_residual == 0


def test_external_saturation_multiplier_must_be_source_proved_nonzero() -> None:
    x, a, b = sp.symbols("x a b")
    reduced = eliminate_source_guarded_linear_variables(
        (x,),
        (x,),
        x,
        (a,),
        max_steps=0,
    )

    accepted = lift_guarded_linear_certificate(
        reduced,
        (a,),
        reduced_goal_multiplier=a,
    )
    rejected = lift_guarded_linear_certificate(
        reduced,
        (b,),
        reduced_goal_multiplier=b,
    )

    assert accepted.replayed
    assert accepted.reduced_goal_multiplier_source_proved_nonzero
    assert accepted.multiplier_source_proved_nonzero
    assert rejected.replayed
    assert not rejected.reduced_goal_multiplier_source_proved_nonzero
    assert not rejected.multiplier_source_proved_nonzero


def test_nondegeneracy_candidates_stay_in_ring_and_depend_on_proof_variables() -> None:
    x, y, a, b, omitted = sp.symbols("x y a b omitted")
    reduced = eliminate_source_guarded_linear_variables(
        (x + y,),
        (x, y),
        x + y,
        (a * b, x + y, omitted + x),
        max_steps=0,
    )

    factors = source_proved_nondegeneracy_factors(
        reduced,
        allowed_symbols=(x, y, a, b),
        proof_variables=(x, y),
    )

    assert factors == (x + y,)


def test_guarded_elimination_stops_before_expanding_an_oversized_stage() -> None:
    x, y, a = sp.symbols("x y a")
    oversized = sp.expand((x + y + 1) ** 6)

    reduced = eliminate_source_guarded_linear_variables(
        (a * x + y, oversized),
        (x, y),
        x + y,
        (a,),
        max_steps=2,
        max_expression_operation_count=10,
    )

    assert reduced.steps == ()
    assert reduced.stopped_reason == "max_expression_operation_count"
    assert max(reduced.operation_counts_by_stage[0]) > 10


def test_guarded_elimination_records_each_completed_stage_size() -> None:
    x, y, a = sp.symbols("x y a")

    reduced = eliminate_source_guarded_linear_variables(
        (a * x + y, y - 1),
        (x, y),
        x + y,
        (a,),
        max_steps=1,
        max_total_operation_count=1_000,
    )

    assert len(reduced.steps) == 1
    assert len(reduced.operation_counts_by_stage) == 2
    assert reduced.stopped_reason is None


def test_goal_factor_candidate_reconstructs_original_target() -> None:
    x, y = sp.symbols("x y")
    goal = 12 * x * (y + 1) ** 3

    candidates = source_preserving_goal_factor_candidates(
        goal,
        proof_variables=(x, y),
    )

    assert tuple(item.factor for item in candidates) == (x, y + 1)
    assert all(item.replayed and item.replay_residual == 0 for item in candidates)
    assert all(
        sp.expand(item.factor * item.complementary_multiplier - goal) == 0
        for item in candidates
    )
