import sympy as sp

from worker.backend.constructible_groebner import (
    certify_constructible_groebner_branch,
)
from worker.backend.wu_zero_decomposition import decompose_wu_zero_set


def test_nonzero_saturation_proves_the_other_factor_is_zero() -> None:
    x, y = sp.symbols("x y")
    certificate = certify_constructible_groebner_branch(
        (x * y,),
        (x, y),
        y,
        nonzero_factors=(x,),
    )

    assert certificate.status == "goal_proved"
    assert certificate.all_identities_replayed
    assert certificate.goal_membership is not None
    assert certificate.goal_membership.proved


def test_contradictory_nonzero_branch_is_certified_empty() -> None:
    x = sp.Symbol("x")
    certificate = certify_constructible_groebner_branch(
        (x,),
        (x,),
        sp.Integer(0),
        nonzero_factors=(x,),
    )

    assert certificate.status == "empty"
    assert certificate.emptiness.proved
    assert certificate.all_identities_replayed


def test_nonconsequence_remains_unresolved() -> None:
    x, y = sp.symbols("x y")
    certificate = certify_constructible_groebner_branch(
        (x,),
        (x, y),
        y,
    )

    assert certificate.status == "unresolved"
    assert not certificate.proved


def test_wu_splits_conditional_root_before_groebner_fallback(monkeypatch) -> None:
    x, y = sp.symbols("x y")
    fallback_calls: list[tuple[sp.Expr, ...]] = []

    def fail_if_called_at_root(equations, *_args, **_kwargs):
        fallback_calls.append(tuple(equations))
        raise AssertionError("Groebner must not run before a Wu split")

    monkeypatch.setattr(
        "worker.backend.wu_zero_decomposition.certify_constructible_groebner_branch",
        fail_if_called_at_root,
    )
    result = decompose_wu_zero_set(
        (x * y,),
        (x, y),
        y,
        max_depth=1,
        max_solver_branches=1,
        timeout_seconds_per_branch=1.0,
        enable_groebner_fallback=True,
    )

    assert not fallback_calls
    assert result.branches[0].status in {"split", "proved"}
