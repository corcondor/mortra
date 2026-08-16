import sympy as sp

from worker.backend.local_polynomial_elimination import (
    _resultant_term_upper_bound,
    eliminate_local_linear_variables,
)


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
