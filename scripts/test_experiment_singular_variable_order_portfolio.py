from __future__ import annotations

from scripts.experiment_singular_variable_order_portfolio import (
    structural_variable_orders,
)


def test_structural_orders_are_bounded_deterministic_permutations() -> None:
    variables = ("a", "b", "c", "d", "e", "f")
    polynomials = (
        "a*b-c",
        "b*d-e",
        "c*e-f",
        "a+d-f",
    )
    first = structural_variable_orders(
        variables,
        polynomials,
        "a*e-b*f",
        max_orders=9,
    )
    second = structural_variable_orders(
        variables,
        polynomials,
        "a*e-b*f",
        max_orders=9,
    )

    assert first == second
    assert 1 < len(first) <= 9
    assert len(set(first)) == len(first)
    assert all(set(order) == set(variables) for order in first)


def test_structural_orders_reject_nonpositive_bound() -> None:
    try:
        structural_variable_orders(("x",), ("x",), "x", max_orders=0)
    except ValueError as error:
        assert "positive" in str(error)
    else:
        raise AssertionError("expected ValueError")
