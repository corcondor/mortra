"""Reusable exact interval charts for elementary transcendental functions.

The functions in this module are problem-independent proof primitives.  They
return rational enclosures, so a caller can replay every comparison without a
floating-point or expected-answer oracle.
"""

from __future__ import annotations

from typing import Any

import sympy as sp


def alternating_trig_bounds(
    x: sp.Rational,
) -> tuple[sp.Rational, sp.Rational, sp.Rational, sp.Rational]:
    """Enclose sin(x) and cos(x) by alternating Taylor partial sums."""

    x = sp.Rational(x)
    if not (0 <= x <= sp.Rational(3, 2)):
        raise ValueError("Taylor enclosure expects 0<=x<=3/2")
    sin_terms = [
        (-1) ** k * x ** (2 * k + 1) / sp.factorial(2 * k + 1)
        for k in range(7)
    ]
    cos_terms = [
        (-1) ** k * x ** (2 * k) / sp.factorial(2 * k)
        for k in range(7)
    ]
    sin_partial = [
        sum(sin_terms[: index + 1], sp.Integer(0))
        for index in range(len(sin_terms))
    ]
    cos_partial = [
        sum(cos_terms[: index + 1], sp.Integer(0))
        for index in range(len(cos_terms))
    ]
    return sin_partial[5], sin_partial[4], cos_partial[5], cos_partial[4]


def alternating_trig_interval_chart(points: list[sp.Rational]) -> dict[str, Any]:
    """Certify rational sin/cos enclosures at all requested points."""

    if not points:
        raise ValueError("trigonometric interval chart requires at least one point")
    evaluations: list[dict[str, str]] = []
    seen: set[sp.Rational] = set()
    for raw_point in points:
        point = sp.Rational(raw_point)
        if point in seen:
            continue
        seen.add(point)
        sin_lower, sin_upper, cos_lower, cos_upper = alternating_trig_bounds(point)
        if not (sin_lower <= sin_upper and cos_lower <= cos_upper):
            raise ValueError("alternating trigonometric enclosure order failed")
        evaluations.append(
            {
                "x": sp.sstr(point),
                "sin_lower": sp.sstr(sin_lower),
                "sin_upper": sp.sstr(sin_upper),
                "cos_lower": sp.sstr(cos_lower),
                "cos_upper": sp.sstr(cos_upper),
            }
        )
    return {
        "chart_id": "transcendental.sin_cos.alternating_interval.v1",
        "atomic_chart_ids": [
            "power_series.alternating_remainder.v1",
            "rational.interval.composition.v1",
        ],
        "domain": "0<=x<=3/2",
        "highest_retained_degrees": {"sin": 11, "cos": 10},
        "evaluations": evaluations,
    }


def log_one_plus_bounds(
    x: sp.Rational,
    terms: int = 14,
) -> tuple[sp.Rational, sp.Rational]:
    """Enclose log(1+x) for 0<x<1 by alternating rational sums."""

    x = sp.Rational(x)
    if not (0 < x < 1) or terms < 2 or terms % 2:
        raise ValueError("log enclosure expects 0<x<1 and an even term count")
    partials: list[sp.Rational] = []
    total = sp.Rational(0)
    for k in range(1, terms + 1):
        total += (-1) ** (k + 1) * x**k / k
        partials.append(total)
    return partials[-1], partials[-2]


def log_profile_bounds(
    lower: sp.Rational,
    upper: sp.Rational,
    *,
    terms: int = 14,
) -> tuple[sp.Rational, sp.Rational]:
    """Enclose (u+1/u)log(1+u) on a rational interval in (0,1)."""

    lower = sp.Rational(lower)
    upper = sp.Rational(upper)
    if not (0 < lower <= upper < 1):
        raise ValueError("profile enclosure expects 0<lower<=upper<1")
    log_lower = log_one_plus_bounds(lower, terms)[0]
    log_upper = log_one_plus_bounds(upper, terms)[1]
    # u+1/u decreases on (0,1), whereas log(1+u) increases.
    return (upper + 1 / upper) * log_lower, (lower + 1 / lower) * log_upper


def log_profile_derivative_bounds(
    u: sp.Rational,
    *,
    terms: int = 20,
) -> tuple[sp.Rational, sp.Rational]:
    """Enclose the derivative of (u+1/u)log(1+u) at rational u."""

    u = sp.Rational(u)
    if not (0 < u < 1):
        raise ValueError("profile derivative enclosure expects 0<u<1")
    log_lower, log_upper = log_one_plus_bounds(u, terms)
    coefficient = 1 - 1 / u**2
    rational_part = (u + 1 / u) / (1 + u)
    if coefficient >= 0:
        return (
            coefficient * log_lower + rational_part,
            coefficient * log_upper + rational_part,
        )
    return (
        coefficient * log_upper + rational_part,
        coefficient * log_lower + rational_part,
    )
