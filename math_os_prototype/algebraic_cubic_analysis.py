"""Symbolic algebraic and calculus analysis of cubic curves.

Provides exact roots, derivatives, intersection/contact classification,
and definite integration for bounded areas without numerical heuristics.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Any

import sympy as sp


@dataclass(frozen=True)
class CubicRootAnalysis:
    root: Fraction
    multiplicity: int
    derivative_value: Fraction
    classification: str  # "intersection" (transversal cross) or "contact" (tangent)
    is_tangent: bool


@dataclass(frozen=True)
class CubicAnalysisResult:
    curve_equation: str
    roots: list[CubicRootAnalysis]
    bounded_interval: tuple[Fraction, Fraction] | None
    bounded_area: Fraction | None
    certificate_steps: list[str]


def analyze_cubic_curve(
    poly_expr_str: str = "x**3 - 3*x + 2",
    var_name: str = "x",
) -> CubicAnalysisResult:
    """Analyze a cubic curve y = P(x) against the x-axis y = 0.

    1. Finds all real roots of P(x) = 0.
    2. Computes the derivative P'(x) = dP/dx.
    3. Evaluates P'(r) at each root to determine if it is a transversal
       intersection (P'(r) != 0) or contact/tangent (P'(r) == 0).
    4. Determines the bounded interval between consecutive roots and computes
       the exact definite integral of |P(x)| dx over the bounded interval.
    """
    x = sp.Symbol(var_name)
    poly = sp.sympify(poly_expr_str)
    deriv = sp.diff(poly, x)

    steps = [
        f"Curve equation: y = {poly}",
        f"First derivative: y' = {deriv}",
    ]

    # Factor polynomial
    factored = sp.factor(poly)
    steps.append(f"Factored form: y = {factored}")

    # Solve roots
    raw_roots = sp.roots(poly, x)
    steps.append(f"Root multiplicities: {raw_roots}")

    root_analyses: list[CubicRootAnalysis] = []
    real_roots: list[Fraction] = []

    for r_sym, mult in sorted(raw_roots.items(), key=lambda item: float(item[0])):
        r_val = Fraction(int(sp.Rational(r_sym).p), int(sp.Rational(r_sym).q))
        real_roots.append(r_val)

        d_val_sym = deriv.subs(x, r_sym)
        d_val = Fraction(int(sp.Rational(d_val_sym).p), int(sp.Rational(d_val_sym).q))

        is_tangent = (d_val == 0)
        classification = "contact" if is_tangent else "intersection"

        steps.append(
            f"Root x = {r_val}: P'({r_val}) = {d_val} -> {classification} "
            f"(multiplicity {mult})"
        )

        root_analyses.append(
            CubicRootAnalysis(
                root=r_val,
                multiplicity=mult,
                derivative_value=d_val,
                classification=classification,
                is_tangent=is_tangent,
            )
        )

    # Bounded area between roots if at least 2 distinct roots
    bounded_interval = None
    bounded_area = None
    if len(real_roots) >= 2:
        x_min, x_max = min(real_roots), max(real_roots)
        bounded_interval = (x_min, x_max)

        # Definite integral
        int_expr = sp.integrate(poly, (x, sp.Rational(x_min.numerator, x_min.denominator),
                                       sp.Rational(x_max.numerator, x_max.denominator)))
        area_sym = sp.Abs(int_expr)
        bounded_area = Fraction(int(sp.Rational(area_sym).p), int(sp.Rational(area_sym).q))

        steps.append(
            f"Bounded interval between roots: [{x_min}, {x_max}]"
        )
        steps.append(
            f"Definite integral of P(x) over [{x_min}, {x_max}]: "
            f"integral = {int_expr}, area = {bounded_area}"
        )

    return CubicAnalysisResult(
        curve_equation=f"y = {poly}",
        roots=root_analyses,
        bounded_interval=bounded_interval,
        bounded_area=bounded_area,
        certificate_steps=steps,
    )
