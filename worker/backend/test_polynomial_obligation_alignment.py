import sympy as sp

from worker.backend.polynomial_obligation_alignment import (
    polynomial_obligation_alignment_rank,
)


def test_monomial_alignment_prefers_the_target_separator() -> None:
    x, y, a, b = sp.symbols("x y a b")

    unrelated = polynomial_obligation_alignment_rank((x - a,), (y - b,))
    aligned = polynomial_obligation_alignment_rank((y - b,), (y - b,))

    assert aligned < unrelated


def test_alignment_is_coefficient_independent_but_not_a_proof() -> None:
    x, y = sp.symbols("x y")

    exact_shape = polynomial_obligation_alignment_rank((2 * x - 3 * y,), (x + y,))
    different_shape = polynomial_obligation_alignment_rank((x * y,), (x + y,))

    assert exact_shape < different_shape
