import sympy as sp

from worker.backend.chordal_buchberger_elimination import (
    eliminate_with_certified_chordal_buchberger,
)


def test_separator_messages_prove_a_goal_across_two_local_cliques() -> None:
    x, y, z, target = sp.symbols("x y z target")
    result = eliminate_with_certified_chordal_buchberger(
        (x - y, y - z, z - target),
        (x, y, z, target),
        protected_variables=(x, target),
        goal_polynomial=x - target,
    )
    assert result.exact_replay
    assert set(result.eliminated_variables) == {"y"}
    assert result.stopped_reason == "local_target_membership"
    assert len(result.steps) == 2
    assert result.goal_membership is not None
    assert result.goal_membership.proved and result.goal_membership.replayed
    assert result.local_complete_step_count == 1
    assert result.local_incomplete_step_count == 1


def test_clique_computation_keeps_separator_only_generators() -> None:
    x, y, z = sp.symbols("x y z")
    result = eliminate_with_certified_chordal_buchberger(
        (x**2 - y, x - z, y + z),
        (x, y, z),
        protected_variables=(y, z),
        goal_polynomial=z**2 - y,
    )
    assert result.goal_membership is not None
    assert result.goal_membership.proved
    assert any("y + z" in step.input_polynomials for step in result.steps)


def test_unrelated_goal_is_not_reported_as_proved() -> None:
    x, y = sp.symbols("x y")
    result = eliminate_with_certified_chordal_buchberger(
        (x - y,),
        (x, y),
        protected_variables=(y,),
        goal_polynomial=y + 1,
    )
    assert result.goal_membership is not None
    assert not result.goal_membership.proved
    assert result.goal_membership.replayed


def test_separator_budget_abstains_without_losing_certificate_soundness() -> None:
    x, a, b, c = sp.symbols("x a b c")
    result = eliminate_with_certified_chordal_buchberger(
        (x + a + b + c,),
        (x, a, b, c),
        protected_variables=(a, b, c),
        max_separator_variables=2,
    )
    assert result.eliminated_variables == ()
    assert result.stopped_reason == "separator_budget"
    assert result.exact_replay


def test_incomplete_local_basis_keeps_the_original_constraints() -> None:
    x, y, z = sp.symbols("x y z")
    result = eliminate_with_certified_chordal_buchberger(
        (x * y - 1, x**2 - z),
        (x, y, z),
        protected_variables=(y, z),
        goal_polynomial=y - z,
        max_pairs_per_clique=0,
        terminal_max_pairs=0,
    )
    assert "x" in result.remaining_variables
    assert set(result.initial_polynomials) <= set(result.remaining_polynomials)
    assert result.stopped_reason == "incomplete_local_basis"
    assert result.exact_replay


def test_incomplete_clique_transports_only_bounded_sound_messages() -> None:
    x, a, b = sp.symbols("x a b")
    result = eliminate_with_certified_chordal_buchberger(
        (x**2 + a, x*b + 1, x + a*b),
        (x, a, b),
        protected_variables=(a, b),
        goal_polynomial=a + b,
        max_pairs_per_clique=1,
        max_incomplete_messages=1,
        terminal_max_pairs=0,
    )
    step = result.steps[0]
    assert not step.buchberger_complete
    assert len(step.output_polynomials) <= 1
    assert set(step.output_polynomials) <= set(step.candidate_output_polynomials)
    assert set(step.input_polynomials) <= set(result.remaining_polynomials)
    assert step.unit_leading_coefficient_available


def test_nonunit_leading_coefficient_becomes_an_explicit_obligation() -> None:
    x, a, b = sp.symbols("x a b")
    result = eliminate_with_certified_chordal_buchberger(
        (a*x + b,),
        (x, a, b),
        protected_variables=(a, b),
        max_pairs_per_clique=0,
        terminal_max_pairs=0,
    )
    step = result.steps[0]
    assert step.leading_coefficient_polynomials == ("a",)
    assert step.coefficient_nonzero_obligations == ("a != 0",)
    assert not step.unit_leading_coefficient_available


def test_local_clique_membership_closes_root_without_global_completion() -> None:
    x, a, b = sp.symbols("x a b")
    result = eliminate_with_certified_chordal_buchberger(
        (x - a, x - b),
        (x, a, b),
        protected_variables=(a, b),
        goal_polynomial=a - b,
        max_pairs_per_clique=4,
        terminal_max_pairs=0,
    )

    assert result.stopped_reason == "local_target_membership"
    assert result.goal_membership is not None
    assert result.goal_membership.proved
    assert result.goal_membership.replayed
    assert result.steps[0].goal_membership is not None
    assert result.exact_replay


def test_obligation_conditioned_clique_order_prefers_a_target_separator() -> None:
    x, y, a, b = sp.symbols("x y a b")
    equations = (x - a, y - b)
    control = eliminate_with_certified_chordal_buchberger(
        equations,
        (x, y, a, b),
        protected_variables=(a, b),
        max_steps=1,
        ordering_strategy="min_fill",
        terminal_max_pairs=0,
    )
    treatment = eliminate_with_certified_chordal_buchberger(
        equations,
        (x, y, a, b),
        protected_variables=(a, b),
        max_steps=1,
        ordering_strategy="obligation_conditioned",
        guidance_polynomials=(b,),
        terminal_max_pairs=0,
    )

    assert control.steps[0].variable == "x"
    assert treatment.steps[0].variable == "y"
    assert treatment.exact_replay


def test_normal_form_residual_ranks_complete_and_branches() -> None:
    x, y, a, b, u, v = sp.symbols("x y a b u v")

    treatment = eliminate_with_certified_chordal_buchberger(
        (x - u, x - v, y - a, y - b),
        (x, y, a, b, u, v),
        protected_variables=(a, b, u, v),
        max_steps=1,
        ordering_strategy="residual_conditioned",
        guidance_polynomials=(a - b,),
        guidance_branches=((a - b,),),
        residual_max_pairs=0,
        terminal_max_pairs=0,
    )

    assert treatment.steps[0].variable == "y"
    assert "a - b" in treatment.remaining_polynomials
    assert treatment.exact_replay
