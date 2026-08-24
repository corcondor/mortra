from __future__ import annotations

import pytest
import sympy as sp
import worker.backend.wolfram_polynomial_certificate as wolfram_certificate

from worker.backend.wolfram_polynomial_certificate import (
    _clear_rational_certificate_denominators,
    _extract_json,
    _saturation_factors,
    _wolfram_expression,
    replay_polynomial_reduction,
)


def test_replay_accepts_exact_polynomial_combination() -> None:
    x, y = sp.symbols("x y")
    equations = (x - y, y - 1)
    quotients = (x + y, 2 * y)
    goal = sp.expand(quotients[0] * equations[0] + quotients[1] * equations[1])

    assert replay_polynomial_reduction(goal, equations, quotients, sp.Integer(0)) == 0


def test_replay_rejects_incorrect_quotient() -> None:
    x, y = sp.symbols("x y")

    residual = replay_polynomial_reduction(
        x + y,
        (x - y,),
        (sp.Integer(1),),
        sp.Integer(0),
    )

    assert residual == 2 * y


def test_replay_accepts_conditional_saturation_multiplier() -> None:
    x, d = sp.symbols("x d")

    residual = replay_polynomial_reduction(
        x,
        (d * x,),
        (sp.Integer(1),),
        sp.Integer(0),
        d,
    )

    assert residual == 0


def test_extract_json_accepts_multiline_wolframscript_output() -> None:
    payload = _extract_json('license banner\n{\n  "status": "complete"\n}\n')

    assert payload == {"status": "complete"}


def test_disabled_saturation_does_not_parse_unused_regularity_factors() -> None:
    factors = _saturation_factors(
        ("this is intentionally not a polynomial != 0",),
        enabled=False,
        limit=0,
    )

    assert factors == ()


def test_wolfram_serialization_preserves_factored_coefficient_charts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    x = sp.Symbol("x")

    def fail_expand(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("serialization must not expand the coefficient chart")

    monkeypatch.setattr(wolfram_certificate.sp, "expand", fail_expand)

    assert _wolfram_expression((x + 1) ** 12)


def test_replay_cancels_rational_parameter_coefficients() -> None:
    x, a = sp.symbols("x a")
    equation = x - a
    quotient = (x + a) / (a + 1)
    goal = (x**2 - a**2) / (a + 1)

    residual = replay_polynomial_reduction(
        goal,
        (equation,),
        (quotient,),
        sp.Integer(0),
    )

    assert residual == 0


def test_rational_denominator_must_be_known_nonzero() -> None:
    x, a = sp.symbols("x a")

    quotients, remainder, multiplier, required, unsupported = (
        _clear_rational_certificate_denominators(
            ((x + a) / (a + 1),),
            sp.Integer(0),
            frozenset({"a + 1"}),
        )
    )

    assert sp.expand(quotients[0] - x - a) == 0
    assert remainder == 0
    assert multiplier == a + 1
    assert required == ("a + 1",)
    assert unsupported == ()


def test_rational_denominator_reports_missing_regularity() -> None:
    x, a = sp.symbols("x a")

    *_, unsupported = _clear_rational_certificate_denominators(
        ((x + a) / (a + 1),),
        sp.Integer(0),
        frozenset(),
    )

    assert unsupported == ("a + 1",)
