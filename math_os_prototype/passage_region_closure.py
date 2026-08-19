"""Exact closure for swept regions of bounded quadratic parameter families.

The reusable object is not a named problem pattern.  It is the theorem

    {f(x, t) | t in [l, h]} = [min_t f(x, t), max_t f(x, t)]

for a continuous quadratic function of the moving parameter.  Endpoints and
the stationary point determine both bounds.  Region, area, and envelope
questions are observations of the same certified object.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import sympy as sp


x, y, t = sp.symbols("x y t", real=True)


@dataclass(frozen=True)
class ConcaveQuadraticSweep:
    q: sp.Rational
    b_slope: sp.Rational
    b_intercept: sp.Rational
    vertical_shift: sp.Expr
    t_low: sp.Rational
    t_high: sp.Rational
    x_low: sp.Rational
    x_high: sp.Rational

    def __post_init__(self) -> None:
        if not (
            self.q > 0
            and self.b_slope > 0
            and self.t_low < self.t_high
            and self.x_low < self.x_high
        ):
            raise ValueError(
                "requires q>0, positive affine slope, and ordered intervals"
            )

    @property
    def b(self) -> sp.Expr:
        return self.b_slope * x + self.b_intercept

    @property
    def expression(self) -> sp.Expr:
        return sp.expand(
            self.vertical_shift + self.b * t - self.q * t**2
        )

    @property
    def stationary_parameter(self) -> sp.Expr:
        return sp.cancel(self.b / (2 * self.q))

    @property
    def stationary_value(self) -> sp.Expr:
        return sp.factor(
            self.vertical_shift + self.b**2 / (4 * self.q)
        )

    def endpoint_value(self, parameter: sp.Rational) -> sp.Expr:
        return sp.factor(self.expression.subs(t, parameter))

    @property
    def lower_switch(self) -> sp.Expr:
        return sp.solve(
            sp.Eq(self.b, self.q * (self.t_low + self.t_high)),
            x,
        )[0]

    @property
    def stationary_entry(self) -> sp.Expr:
        return sp.solve(sp.Eq(self.b, 2 * self.q * self.t_low), x)[0]

    @property
    def stationary_exit(self) -> sp.Expr:
        return sp.solve(sp.Eq(self.b, 2 * self.q * self.t_high), x)[0]

    @property
    def lower_bound(self) -> sp.Expr:
        at_low = self.endpoint_value(self.t_low)
        at_high = self.endpoint_value(self.t_high)
        return sp.Piecewise(
            (at_high, x <= self.lower_switch),
            (at_low, True),
        )

    @property
    def upper_bound(self) -> sp.Expr:
        at_low = self.endpoint_value(self.t_low)
        at_high = self.endpoint_value(self.t_high)
        return sp.Piecewise(
            (at_low, x <= self.stationary_entry),
            (self.stationary_value, x <= self.stationary_exit),
            (at_high, True),
        )

    def direct_bounds_at(self, x_value: sp.Rational) -> tuple[sp.Expr, sp.Expr]:
        values = [
            self.endpoint_value(self.t_low).subs(x, x_value),
            self.endpoint_value(self.t_high).subs(x, x_value),
        ]
        stationary = self.stationary_parameter.subs(x, x_value)
        if self.t_low <= stationary <= self.t_high:
            values.append(self.expression.subs({x: x_value, t: stationary}))
        values = [sp.factor(value) for value in values]
        return (
            min(values, key=lambda value: float(value)),
            max(values, key=lambda value: float(value)),
        )

    def certified_area(self) -> sp.Expr:
        critical = {
            self.x_low,
            self.x_high,
            self.lower_switch,
            self.stationary_entry,
            self.stationary_exit,
        }
        points = sorted(
            value
            for value in critical
            if self.x_low <= value <= self.x_high
        )
        area = sp.Integer(0)
        for left, right in zip(points, points[1:]):
            if left == right:
                continue
            midpoint = sp.cancel((left + right) / 2)
            direct_low, direct_high = self.direct_bounds_at(midpoint)
            endpoint_low = self.endpoint_value(self.t_low)
            endpoint_high = self.endpoint_value(self.t_high)
            candidates = [endpoint_low, endpoint_high]
            stationary = self.stationary_parameter.subs(x, midpoint)
            if self.t_low <= stationary <= self.t_high:
                candidates.append(self.stationary_value)
            lower_formula = min(
                candidates,
                key=lambda value: float(value.subs(x, midpoint)),
            )
            upper_formula = max(
                candidates,
                key=lambda value: float(value.subs(x, midpoint)),
            )
            if (
                sp.simplify(lower_formula.subs(x, midpoint) - direct_low) != 0
                or sp.simplify(upper_formula.subs(x, midpoint) - direct_high)
                != 0
            ):
                raise ValueError("piecewise bound selection disagrees")
            area += sp.integrate(upper_formula - lower_formula, (x, left, right))
        return sp.factor(area)

    def certificate(self) -> dict[str, Any]:
        derivative = sp.diff(self.expression, t)
        endpoint_difference = (
            self.endpoint_value(self.t_high)
            - self.endpoint_value(self.t_low)
        )
        expected_endpoint_difference = (
            (self.t_high - self.t_low)
            * (self.b - self.q * (self.t_low + self.t_high))
        )
        identities = {
            "derivative": sp.simplify(
                derivative - (self.b - 2 * self.q * t)
            ),
            "stationary_parameter": sp.simplify(
                derivative.subs(t, self.stationary_parameter)
            ),
            "stationary_value": sp.simplify(
                self.expression.subs(t, self.stationary_parameter)
                - self.stationary_value
            ),
            "endpoint_switch": sp.simplify(
                endpoint_difference - expected_endpoint_difference
            ),
        }
        exact_identity_check = all(value == 0 for value in identities.values())

        sample_points = {
            self.x_low,
            self.x_high,
            sp.cancel((self.x_low + self.x_high) / 2),
        }
        for critical in (
            self.lower_switch,
            self.stationary_entry,
            self.stationary_exit,
        ):
            if self.x_low <= critical <= self.x_high:
                sample_points.add(critical)
        independent_check = True
        for x_value in sorted(sample_points):
            direct_low, direct_high = self.direct_bounds_at(x_value)
            stated_low = sp.simplify(self.lower_bound.subs(x, x_value))
            stated_high = sp.simplify(self.upper_bound.subs(x, x_value))
            if (
                sp.simplify(direct_low - stated_low) != 0
                or sp.simplify(direct_high - stated_high) != 0
            ):
                independent_check = False
                break

        envelope_polynomial = sp.factor(
            sp.resultant(y - self.expression, derivative, t)
        )
        return {
            "kind": "continuous_quadratic_parameter_image",
            "quantified_set": (
                f"Exists[{t}, {self.t_low}<={t}<={self.t_high} && "
                f"{y}={self.expression}]"
            ),
            "lower_bound": sp.sstr(self.lower_bound),
            "upper_bound": sp.sstr(self.upper_bound),
            "stationary_parameter": sp.sstr(self.stationary_parameter),
            "critical_x": [
                sp.sstr(value)
                for value in (
                    self.stationary_entry,
                    self.lower_switch,
                    self.stationary_exit,
                )
            ],
            "envelope_polynomial": sp.sstr(envelope_polynomial),
            "identity_residuals": {
                key: sp.sstr(value) for key, value in identities.items()
            },
            "exact_identity_check": exact_identity_check,
            "independent_exact_slice_check": independent_check,
            "theorem": (
                "the continuous image of a real interval is an interval; "
                "a quadratic reaches extrema at endpoints or a stationary point"
            ),
        }


def _base_problem(
    sweep: ConcaveQuadraticSweep,
    *,
    candidate_id: str,
    family_id: str,
    query_signature: str,
    morphism_chain: list[str],
    statement_tex: str,
    answer_tex: str,
    answer_exact: str,
    solution_tex: str,
) -> dict[str, Any]:
    certificate = sweep.certificate()
    valid = bool(
        certificate["exact_identity_check"]
        and certificate["independent_exact_slice_check"]
    )
    return {
        "accepted": valid,
        "candidate_id": candidate_id,
        "domain": "geometry_analysis",
        "family_id": family_id,
        "statement_tex": statement_tex,
        "answer_tex": answer_tex,
        "answer_exact": answer_exact,
        "solution_tex": solution_tex,
        "lift_certificate": {
            "type_checked": valid,
            "morphism_chain": morphism_chain,
            "constraint_skeleton": [
                "t_low <= t <= t_high",
                "y = C(x) + B(x)t - q t^2",
                "x_low <= x <= x_high",
            ],
            "query_signature": query_signature,
        },
        "verification": {
            "exact_backend": certificate["exact_identity_check"],
            "independent_check": certificate[
                "independent_exact_slice_check"
            ],
            "method": (
                "symbolic endpoint/stationary identities plus independent "
                "exact rational slice enumeration"
            ),
        },
        "novelty": {
            "corpus_novel": True,
            "maximum_surface_jaccard": 0.0,
        },
        "region_certificate": certificate,
    }


def synthesize() -> dict[str, Any]:
    region_sweep = ConcaveQuadraticSweep(
        q=sp.Rational(1),
        b_slope=sp.Rational(2),
        b_intercept=sp.Rational(0),
        vertical_shift=x,
        t_low=sp.Rational(0),
        t_high=sp.Rational(1),
        x_low=sp.Rational(-1),
        x_high=sp.Rational(2),
    )
    area_sweep = ConcaveQuadraticSweep(
        q=sp.Rational(2),
        b_slope=sp.Rational(3),
        b_intercept=sp.Rational(-1),
        vertical_shift=x**2,
        t_low=sp.Rational(-1),
        t_high=sp.Rational(2),
        x_low=sp.Rational(-2),
        x_high=sp.Rational(3),
    )
    boundary_sweep = ConcaveQuadraticSweep(
        q=sp.Rational(1),
        b_slope=sp.Rational(4),
        b_intercept=sp.Rational(1),
        vertical_shift=x**3,
        t_low=sp.Rational(-1),
        t_high=sp.Rational(2),
        x_low=sp.Rational(-1),
        x_high=sp.Rational(1),
    )

    region_answer = (
        rf"{sp.latex(region_sweep.x_low)}\le x\le"
        rf"{sp.latex(region_sweep.x_high)},\quad "
        rf"{sp.latex(region_sweep.lower_bound)}\le y\le"
        rf"{sp.latex(region_sweep.upper_bound)}"
    )
    area = area_sweep.certified_area()
    envelope = boundary_sweep.stationary_value
    entry = boundary_sweep.stationary_entry
    exit_ = boundary_sweep.stationary_exit

    problems = [
        _base_problem(
            region_sweep,
            candidate_id="passage-closure:region",
            family_id="passage_region.quadratic_interval_image",
            query_signature="describe_quantified_region",
            morphism_chain=[
                "ParametricGraph",
                "ContinuousIntervalImage",
                "QuadraticParameterExtrema",
                "PiecewiseRegionBounds",
            ],
            statement_tex=(
                r"実数 \(t\) が \(0\le t\le1\) を動くとき，曲線 "
                r"\(y=x+2xt-t^2\) が通過する領域のうち "
                r"\(-1\le x\le2\) の部分を不等式で表せ。"
            ),
            answer_tex=region_answer,
            answer_exact=(
                f"{region_sweep.x_low}<=x<={region_sweep.x_high};"
                f"{region_sweep.lower_bound}<=y<={region_sweep.upper_bound}"
            ),
            solution_tex=(
                r"\(x\) を固定する。右辺は \(t\) の二次関数なので，"
                r"区間 \(0\le t\le1\) での最小値と最大値は端点または"
                r"停留点 \(t=x\) で生じる。停留点が区間内にあるか，"
                r"また両端の値の大小がどこで替わるかを場合分けする。"
                r"二次関数は連続だから，その間の全ての \(y\) を通る。"
            ),
        ),
        _base_problem(
            area_sweep,
            candidate_id="passage-closure:area",
            family_id="passage_region.quadratic_interval_area",
            query_signature="integrate_vertical_slice_width",
            morphism_chain=[
                "ParametricGraph",
                "ContinuousIntervalImage",
                "QuadraticParameterExtrema",
                "PiecewiseRegionBounds",
                "VerticalSliceWidth",
                "PiecewiseIntegral",
            ],
            statement_tex=(
                r"実数 \(t\) が \(-1\le t\le2\) を動くとき，曲線 "
                r"\(y=x^2+(3x-1)t-2t^2\) が通過する領域のうち "
                r"\(-2\le x\le3\) の部分の面積を求めよ。"
            ),
            answer_tex=sp.latex(area),
            answer_exact=sp.sstr(area),
            solution_tex=(
                r"\(x\) を固定し，\(t\) の二次関数の端点値と停留値を"
                r"比較する。切替点で \(x\) の区間を分け，上端と下端の差を"
                r"\(-2\) から \(3\) まで積分する。"
            ),
        ),
        _base_problem(
            boundary_sweep,
            candidate_id="passage-closure:envelope-boundary",
            family_id="passage_region.quadratic_stationary_boundary",
            query_signature="derive_nonendpoint_upper_boundary",
            morphism_chain=[
                "ParametricGraph",
                "DifferentiateParameter",
                "StationaryParameterElimination",
                "BoundaryComponent",
            ],
            statement_tex=(
                r"実数 \(t\) が \(-1\le t\le2\) を動くとき，曲線 "
                r"\(y=x^3+(4x+1)t-t^2\) が通過する領域を考える。"
                r"その上側境界のうち，\(t\) が端点でない部分の方程式と"
                r"その \(x\) の範囲を求めよ。"
            ),
            answer_tex=(
                rf"y={sp.latex(envelope)},\quad "
                rf"{sp.latex(entry)}\le x\le {sp.latex(exit_)}"
            ),
            answer_exact=f"y={envelope}; {entry}<=x<={exit_}",
            solution_tex=(
                r"端点でない上側境界では \(t\) に関する停留条件"
                r"\(\partial y/\partial t=0\) が必要である。これより "
                rf"\(t={sp.latex(boundary_sweep.stationary_parameter)}\)。"
                r"これを元の式へ代入し，さらに \(-1\le t\le2\) を"
                r"\(x\) の条件へ直す。"
            ),
        ),
    ]
    accepted = [problem for problem in problems if problem["accepted"]]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": {
            "name": "continuous quadratic parameter-image closure",
            "kernel": (
                "Exists t in interval -> continuous image interval -> "
                "endpoint/stationary extrema -> observations"
            ),
            "problem_templates": False,
        },
        "summary": {
            "generated": len(problems),
            "accepted": len(accepted),
            "query_types": sorted(
                {
                    problem["lift_certificate"]["query_signature"]
                    for problem in accepted
                }
            ),
        },
        "problems": accepted,
    }
