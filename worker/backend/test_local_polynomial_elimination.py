import sympy as sp

from worker.backend.local_polynomial_elimination import (
    _expanded_polynomial_degree,
    _polynomial_degree_capped,
    _polynomial_degree_upper_bound,
    _resultant_term_upper_bound,
    _select_resultant_pivot,
    eliminate_local_linear_variables,
)


def test_pre_normalized_degree_falls_back_for_factored_separator_message() -> None:
    x, y = sp.symbols("x y")

    assert _expanded_polynomial_degree((x + 1) * (y + 1), x) == 1
    assert _expanded_polynomial_degree((x + 1) ** 2 * (y + 1), x) == 2


def test_linear_separator_elimination_replays_an_ideal_identity() -> None:
    x, y, z = sp.symbols("x y z")
    result = eliminate_local_linear_variables(
        (2 * x + y, 3 * x - z),
        (x, y, z),
        protected_variables=(y, z),
    )
    assert result.exact_replay
    assert result.eliminated_variables == ("x",)
    assert result.remaining_polynomials == ("-3*y - 2*z",)
    assert result.steps[0].replay_residuals == ("0",)
    assert result.steps[0].separator_variables == ("y", "z")
    assert result.steps[0].ideal_membership_witnesses[0].replay_residual == "0"


def test_all_protected_variables_take_the_identity_fast_path() -> None:
    x, y = sp.symbols("x y")
    result = eliminate_local_linear_variables(
        ((x + y) ** 4 - x**4, x - y),
        (x, y),
        protected_variables=(x, y),
    )

    assert result.exact_replay
    assert result.steps == ()
    assert result.eliminated_variables == ()
    assert result.stopped_reason == "no_unprotected_variables"
    assert result.remaining_polynomials == ("-x**4 + (x + y)**4", "x - y")


def test_pre_normalized_input_preserves_the_same_exact_elimination() -> None:
    x, y, z = sp.symbols("x y z")
    equations = (x - y, x - z)

    control = eliminate_local_linear_variables(
        equations,
        (x, y, z),
        protected_variables=(y, z),
    )
    treatment = eliminate_local_linear_variables(
        equations,
        (x, y, z),
        protected_variables=(y, z),
        pre_normalized=True,
    )

    assert treatment.exact_replay
    assert treatment.eliminated_variables == control.eliminated_variables
    assert treatment.remaining_polynomials == control.remaining_polynomials


def test_linear_chain_is_compressed_to_its_boundary() -> None:
    x, y, z, target = sp.symbols("x y z target")
    result = eliminate_local_linear_variables(
        (x - y, y - z, z - target),
        (x, y, z, target),
        protected_variables=(x, target),
    )
    assert result.exact_replay
    assert set(result.eliminated_variables) == {"y", "z"}
    assert result.remaining_polynomials == ("-target + x",)


def test_nonlinear_variable_is_not_silently_eliminated() -> None:
    x, y = sp.symbols("x y")
    result = eliminate_local_linear_variables(
        (x**2 - y,),
        (x, y),
        protected_variables=(y,),
        max_resultant_degree=1,
    )
    assert result.eliminated_variables == ()
    assert result.stopped_reason == "no_locally_linear_variable"
    assert result.remaining_polynomials == ("x**2 - y",)


def test_quadratic_resultant_is_recomputed_exactly() -> None:
    x, y, z = sp.symbols("x y z")
    result = eliminate_local_linear_variables(
        (x**2 - y, x - z),
        (x, y, z),
        protected_variables=(y, z),
    )
    assert result.exact_replay
    assert result.eliminated_variables == ("x",)
    assert result.remaining_polynomials == ("-y + z**2",)
    assert result.steps[0].method == "resultant_projection"
    witness = result.steps[0].ideal_membership_witnesses[0]
    assert witness.replay_residual == "0"
    assert sp.denom(sp.sympify(witness.left_multiplier)) == 1
    assert sp.denom(sp.sympify(witness.right_multiplier)) == 1


def test_resultant_term_bound_is_computed_without_expansion() -> None:
    x, a, b, c, d = sp.symbols("x a b c d")
    bound = _resultant_term_upper_bound(x**2 + a * x + b, x**2 + c * x + d, x)
    assert bound >= 1
    result = eliminate_local_linear_variables(
        (x**2 + a * x + b, x**2 + c * x + d),
        (x, a, b, c, d),
        protected_variables=(a, b, c, d),
        max_output_terms=bound - 1,
    )
    assert result.eliminated_variables == ()
    assert result.stopped_reason == "term_budget"


def test_separator_width_is_an_independent_budget() -> None:
    x, a, b, c = sp.symbols("x a b c")
    result = eliminate_local_linear_variables(
        (x + a + b + c,),
        (x, a, b, c),
        protected_variables=(a, b, c),
        max_separator_variables=2,
    )
    assert result.eliminated_variables == ()
    assert result.stopped_reason == "separator_budget"


def test_unknown_localization_condition_can_be_rejected_by_caller() -> None:
    x, a, b = sp.symbols("x a b")
    result = eliminate_local_linear_variables(
        (a * x + b,),
        (x, a, b),
        protected_variables=(a, b),
        nonzero_condition_acceptor=lambda condition: condition == "1 != 0",
    )

    assert result.eliminated_variables == ()
    assert result.stopped_reason == "term_budget"


def test_rejected_linear_division_falls_back_to_exact_resultant() -> None:
    x, a, b, c, d = sp.symbols("x a b c d")
    result = eliminate_local_linear_variables(
        (a * x + b, c * x + d),
        (x, a, b, c, d),
        protected_variables=(a, b, c, d),
        nonzero_condition_acceptor=lambda _condition: False,
    )

    assert result.eliminated_variables == ("x",)
    assert result.steps[0].method == "resultant_projection"
    assert result.steps[0].nonzero_conditions == ()
    assert sp.expand(sp.sympify(result.remaining_polynomials[0])) in {
        sp.expand(a * d - b * c),
        sp.expand(b * c - a * d),
    }


def test_resultant_pivot_minimizes_predicted_expansion_not_degree_only() -> None:
    x, a, b, c, d, e = sp.symbols("x a b c d e")
    sparse_quadratic = x**2 - a
    dense_linear = x * (a + b + c + d + e) + a * b * c * d * e
    second_quadratic = x**2 - b

    pivot = _select_resultant_pivot(
        (dense_linear, sparse_quadratic, second_quadratic),
        x,
    )

    assert pivot in {sparse_quadratic, second_quadratic}


def test_min_fill_order_uses_the_existing_primal_graph() -> None:
    v, w, a, b, c, d = sp.symbols("v w a b c d")
    equations = (v + a, v + b, w + c, w + d, c + d)
    local_degree = eliminate_local_linear_variables(
        equations,
        (v, w, a, b, c, d),
        protected_variables=(a, b, c, d),
        max_steps=1,
        ordering_strategy="local_degree",
    )
    min_fill = eliminate_local_linear_variables(
        equations,
        (v, w, a, b, c, d),
        protected_variables=(a, b, c, d),
        max_steps=1,
        ordering_strategy="min_fill",
    )
    assert local_degree.eliminated_variables == ("v",)
    assert min_fill.eliminated_variables == ("w",)


def test_obligation_conditioned_order_prefers_a_target_aligned_separator() -> None:
    x, y, a, b = sp.symbols("x y a b")
    equations = (x - a, y - b)
    control = eliminate_local_linear_variables(
        equations,
        (x, y),
        max_steps=1,
        ordering_strategy="min_fill",
    )
    treatment = eliminate_local_linear_variables(
        equations,
        (x, y),
        max_steps=1,
        ordering_strategy="obligation_conditioned",
        guidance_polynomials=(b,),
    )

    assert control.eliminated_variables == ("x",)
    assert treatment.eliminated_variables == ("y",)
    assert treatment.exact_replay


def test_obligation_conditioning_closes_a_separator_under_the_same_step_budget() -> None:
    x, z, a, d, b, y = sp.symbols("x z a d b y")
    equations = (x - a, x - d, y - z, z - b)
    control = eliminate_local_linear_variables(
        equations,
        (x, z, a, d, b, y),
        protected_variables=(a, d, b, y),
        max_steps=1,
        ordering_strategy="min_fill",
    )
    treatment = eliminate_local_linear_variables(
        equations,
        (x, z, a, d, b, y),
        protected_variables=(a, d, b, y),
        max_steps=1,
        ordering_strategy="obligation_conditioned",
        guidance_polynomials=(y - b,),
    )

    assert "-b + y" not in control.remaining_polynomials
    assert "-b + y" in treatment.remaining_polynomials
    assert treatment.steps[0].replayed


def test_normal_form_residual_preserves_one_coherent_and_branch() -> None:
    x, y, a, b, u, v = sp.symbols("x y a b u v")
    equations = (x - u, x - v, y - a, y - b)

    treatment = eliminate_local_linear_variables(
        equations,
        (x, y, a, b, u, v),
        protected_variables=(a, b, u, v),
        max_steps=1,
        ordering_strategy="residual_conditioned",
        guidance_polynomials=(a - b,),
        guidance_branches=((a - b,),),
        residual_max_pairs=0,
    )

    assert treatment.eliminated_variables == ("y",)
    assert "a - b" in treatment.remaining_polynomials
def test_structural_degree_bound_does_not_expand_parameter_charts() -> None:
    x, parameter = sp.symbols("x parameter")
    expression = (parameter + 1) ** 30 * x**4 + parameter * x

    assert _polynomial_degree_upper_bound(expression, x) == 4
    assert _polynomial_degree_capped(expression, x, 2) == 3
    expanded = sp.expand(expression, x)
    assert _expanded_polynomial_degree(expanded, x) == 4
