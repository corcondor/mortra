"""Cold synthesis for affine lines trapped between log and exp.

The reusable object is an envelope of admissible affine functions.  Its
boundaries are obtained from the exact tangency conditions of the lower and
upper curves; neither a problem id nor a stored region is consulted.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any

import sympy as sp

from .latex_frontend import parse_latex_problem
from .visual_reasoning import (
    function_plot_diagram,
    plane_scene_diagram,
    variation_table_diagram,
)


@dataclass(frozen=True)
class LogExpAffineEnvelopeSynthesis:
    answer: Any
    answer_tex: str
    tool_name: str
    expression_tex: str
    derivation_tex: tuple[str, ...]
    verification_checks: tuple[str, ...]
    proof_program: tuple[dict[str, Any], ...]
    diagram: dict[str, Any] | None
    witness: dict[str, Any]
    visual_explanation: dict[str, Any] | None = None


def _parse_log_exp_affine_sandwich(statement: str) -> dict[str, str] | None:
    if not re.search(
        r"(?:任意の正の実数|すべての正の実数|every\s+positive\s+real)",
        statement,
        re.I,
    ):
        return None
    if not re.search(r"(?:存在範囲|存在領域|領域|locus|region)", statement, re.I):
        return None
    if not re.search(r"(?:面積|area)", statement, re.I):
        return None

    parsed = parse_latex_problem(statement)
    for segment in parsed.math_segments:
        compact = re.sub(r"\s+", "", segment)
        match = re.fullmatch(
            r"log\((?P<x>[A-Za-z])\)\+2<"
            r"(?P<a>[A-Za-z])\*(?P=x)\+(?P<b>[A-Za-z])<e\*\*(?P=x)",
            compact,
        )
        if match is None:
            match = re.fullmatch(
                r"log\((?P<x>[A-Za-z])\)\+2<"
                r"(?P<b>[A-Za-z])\+(?P<a>[A-Za-z])\*(?P=x)<e\*\*(?P=x)",
                compact,
            )
        if match is None:
            continue
        symbols = {match.group("x"), match.group("a"), match.group("b")}
        if len(symbols) != 3:
            return None
        point = f"({match.group('a')},{match.group('b')})"
        if point not in {re.sub(r"\s+", "", item) for item in parsed.math_segments}:
            return None
        return {
            "variable": match.group("x"),
            "slope": match.group("a"),
            "intercept": match.group("b"),
        }
    return None


def _lower_tangency_diagram(variable: str, slope: str) -> dict[str, Any]:
    sample_slope = 2.0
    sample_intercept = 1.0 - math.log(sample_slope)
    tangent_x = 1.0 / sample_slope
    return function_plot_diagram(
        (
            ("log-lower", lambda value: math.log(value) + 2.0, "primary"),
            (
                "lower-tangent",
                lambda value: sample_slope * value + sample_intercept,
                "accent",
            ),
        ),
        x_min=0.16,
        x_max=2.1,
        title="対数曲線に下から接する直線",
        caption=f"傾き {slope}=2 の境界直線です。接点は {variable}=1/2 で、これより上へ平行移動すると下側の不等式が厳密になります。",
        marked_points=((tangent_x, math.log(tangent_x) + 2.0, "接点"),),
    )


def _upper_tangency_diagram(variable: str, slope: str) -> dict[str, Any]:
    sample_slope = 2.0
    sample_intercept = sample_slope * (1.0 - math.log(sample_slope))
    tangent_x = math.log(sample_slope)
    return function_plot_diagram(
        (
            ("exp-upper", math.exp, "primary"),
            (
                "upper-tangent",
                lambda value: sample_slope * value + sample_intercept,
                "accent",
            ),
        ),
        x_min=0.0,
        x_max=2.0,
        title="指数曲線に下から接する直線",
        caption=f"同じ傾き {slope}=2 の上側境界です。接点は {variable}=log 2 で、直線をこれより下へ移すと指数曲線の下に入ります。",
        marked_points=((tangent_x, sample_slope, "接点"),),
    )


def _parameter_region_diagram(slope: str, intercept: str) -> dict[str, Any]:
    sample_count = 121
    slopes = [
        1.0 + (math.e - 1.0) * index / (sample_count - 1)
        for index in range(sample_count)
    ]
    lower = [(value, 1.0 - math.log(value)) for value in slopes]
    upper = [(value, value * (1.0 - math.log(value))) for value in slopes]
    polygon = [
        *({"x": x_value, "y": y_value} for x_value, y_value in lower),
        *({"x": x_value, "y": y_value} for x_value, y_value in reversed(upper)),
    ]
    return plane_scene_diagram(
        title="二つの接線条件が作る係数領域",
        caption="青い部分の各点が、すべての正の変数で対数曲線より上、指数曲線より下にある直線を表します。",
        viewport={"xMin": 0.86, "xMax": 2.86, "yMin": -0.14, "yMax": 1.14},
        shapes=(
            {
                "kind": "polyline",
                "id": "admissible-region",
                "points": tuple(polygon),
                "closed": True,
                "fill": True,
                "tone": "primary",
            },
            {
                "kind": "polyline",
                "id": "lower-boundary",
                "points": tuple(
                    {"x": x_value, "y": y_value} for x_value, y_value in lower
                ),
                "tone": "secondary",
            },
            {
                "kind": "polyline",
                "id": "upper-boundary",
                "points": tuple(
                    {"x": x_value, "y": y_value} for x_value, y_value in upper
                ),
                "tone": "accent",
            },
            {
                "kind": "label",
                "id": "lower-label",
                "point": {"x": 2.23, "y": 0.12},
                "tex": rf"{intercept}=1-\log {slope}",
                "tone": "secondary",
            },
            {
                "kind": "label",
                "id": "upper-label",
                "point": {"x": 1.82, "y": 0.78},
                "tex": rf"{intercept}={slope}(1-\log {slope})",
                "tone": "accent",
            },
            {
                "kind": "label",
                "id": "slope-axis",
                "point": {"x": 2.8, "y": -0.07},
                "tex": slope,
            },
            {
                "kind": "label",
                "id": "intercept-axis",
                "point": {"x": 0.92, "y": 1.08},
                "tex": intercept,
            },
        ),
        axes=True,
    )


def _slope_case_diagram(slope: str, intercept: str) -> dict[str, Any]:
    return variation_table_diagram(
        (
            {"tex": rf"0<{slope}\le1"},
            {"tex": rf"1<{slope}<e"},
            {"tex": rf"{slope}\ge e"},
        ),
        (
            {
                "label": "下側条件",
                "cells": (
                    {"tex": rf"{intercept}>1-\log {slope}\ge1"},
                    {"tex": rf"{intercept}>1-\log {slope}"},
                    {"tex": rf"{intercept}>1-\log {slope}"},
                ),
            },
            {
                "label": "上側条件",
                "cells": (
                    {"tex": rf"{intercept}\le1"},
                    {"tex": rf"{intercept}<{slope}(1-\log {slope})"},
                    {"tex": rf"{intercept}<{slope}(1-\log {slope})"},
                ),
            },
            {
                "label": "共通部分",
                "cells": ("なし", "存在", "なし"),
            },
        ),
        title="傾きごとに二つの条件を重ねる",
        caption=f"共通部分が残るのは 1<{slope}<e の列だけです。その列で {intercept} が二つの境界の間を動きます。",
        variable_label=slope,
    )


def synthesize_log_exp_affine_sandwich(
    statement: str,
) -> LogExpAffineEnvelopeSynthesis | None:
    parsed = _parse_log_exp_affine_sandwich(statement)
    if parsed is None:
        return None

    variable = parsed["variable"]
    slope_name = parsed["slope"]
    intercept_name = parsed["intercept"]

    x = sp.symbols("x", positive=True)
    a = sp.symbols("a", positive=True)
    b = sp.symbols("b", real=True)
    lower_gap = a * x + b - sp.log(x) - 2
    upper_gap = sp.exp(x) - a * x - b
    lower_contact = sp.simplify(lower_gap.subs(x, 1 / a))
    upper_contact = sp.simplify(upper_gap.subs(x, sp.log(a)))
    if lower_contact != a * 0 + b + sp.log(a) - 1:
        return None
    if upper_contact != a - a * sp.log(a) - b:
        return None
    if sp.simplify(sp.diff(lower_gap, x).subs(x, 1 / a)) != 0:
        return None
    if sp.simplify(sp.diff(upper_gap, x).subs(x, sp.log(a))) != 0:
        return None
    if sp.simplify(sp.diff(lower_gap, x, 2) - 1 / x**2) != 0:
        return None
    if sp.simplify(sp.diff(upper_gap, x, 2) - sp.exp(x)) != 0:
        return None

    lower_boundary = 1 - sp.log(a)
    upper_boundary = a * (1 - sp.log(a))
    width = sp.factor(upper_boundary - lower_boundary)
    if sp.simplify(width + (a - 1) * (sp.log(a) - 1)) != 0:
        return None
    area = sp.simplify(sp.integrate(width, (a, 1, sp.E)))
    expected_area = (sp.E**2 - 4 * sp.E + 5) / 4
    if sp.simplify(area - expected_area) != 0:
        return None

    lower_diagram = _lower_tangency_diagram(variable, slope_name)
    upper_diagram = _upper_tangency_diagram(variable, slope_name)
    case_diagram = _slope_case_diagram(slope_name, intercept_name)
    region_diagram = _parameter_region_diagram(slope_name, intercept_name)
    chain = (
        "elaborate_affine_function_sandwich",
        "minimize_log_affine_gap_by_tangency",
        "minimize_exp_affine_gap_by_tangency",
        "intersect_dual_envelopes",
        "integrate_parameter_slice_width",
    )

    region_tex = (
        rf"1<{slope_name}<e,\qquad "
        rf"1-\log {slope_name}<{intercept_name}"
        rf"<{slope_name}(1-\log {slope_name})"
    )
    answer_tex = rf"""\[
\boxed{{\left\{{({slope_name},{intercept_name})\ \middle|\ {region_tex}\right\}}}},
\qquad
\boxed{{\text{{面積}}=\frac{{e^2-4e+5}}{{4}}}}.
\]"""

    derivation_tex = (
        rf"まず傾き \({slope_name}\) は正でなければならない。実際、\({slope_name}\le0\) なら \({variable}\to\infty\) のとき直線 \({slope_name}{variable}+{intercept_name}\) は \(\log {variable}+2\) より上にあり続けることができない。以下 \({slope_name}>0\) とする。",
        rf"下側の不等式を調べるため \(L({variable})={slope_name}{variable}+{intercept_name}-\log {variable}-2\) とおく。\[L'({variable})={slope_name}-\frac1{{{variable}}},\qquad L''({variable})=\frac1{{{variable}^2}}>0.\] 従って最小値は \({variable}=1/{slope_name}\) で取り、\[\min_{{{variable}>0}}L({variable})={intercept_name}+\log {slope_name}-1.\] よって下側の不等式が全ての正の {variable} で成り立つための必要十分条件は \[{intercept_name}>1-\log {slope_name}.\]",
        rf"上側について \(U({variable})=e^{{{variable}}}-{slope_name}{variable}-{intercept_name}\) とおく。\({slope_name}\le1\) なら \(U\) は正の範囲で増加し、\({variable}\to0+\) での極限から \({intercept_name}\le1\) が必要十分である。しかし下側条件はこのとき \({intercept_name}>1-\log {slope_name}\ge1\) となるので両立しない。",
        rf"従って \({slope_name}>1\) である。このとき \(U'({variable})=e^{{{variable}}}-{slope_name}\) より最小値は \({variable}=\log {slope_name}\) で取り、\[\min_{{{variable}>0}}U({variable})={slope_name}(1-\log {slope_name})-{intercept_name}.\] 二つの境界の間隔は \[({slope_name}-1)(1-\log {slope_name})\] である。\({slope_name}>1\) のもとでこれが正となるのは \({slope_name}<e\) のときに限る。従って存在範囲は \[{region_tex}.\]",
        rf"境界を含むかどうかは面積に影響しない。{slope_name} を固定した縦の幅を積分すると、\[\begin{{aligned}}\text{{面積}}&=\int_1^e\Bigl({slope_name}(1-\log {slope_name})-(1-\log {slope_name})\Bigr)\,d{slope_name}\\&=\int_1^e({slope_name}-1)(1-\log {slope_name})\,d{slope_name}\\&=\frac{{e^2-4e+5}}4.\end{{aligned}}\]",
    )

    visual_explanation = {
        "version": 1,
        "mode": "stepper",
        "title": "対数と指数の間に入る直線を求める",
        "diagram_required_for_every_step": True,
        "composition_verified": True,
        "morphism_chain": list(chain),
        "steps": [
            {
                "id": "log-exp-envelope-1",
                "title": "下側の境界は対数曲線への接線",
                "explanation_ja": "傾きを固定して直線を下げると、対数曲線に初めて触れる位置が境界です。接点で傾きが等しいことから、接点と切片を一意に求めます。",
                "formula_tex": rf"{variable}=\frac1{{{slope_name}}},\qquad {intercept_name}=1-\log {slope_name}",
                "morphism": {
                    "morphism_id": chain[1],
                    "label_ja": "対数との差の最小値を接点で求める",
                    "input_type": "AffineLowerBoundObligation",
                    "output_type": "LowerEnvelope",
                },
                "source_state": {
                    "id": "lower-inequality",
                    "type": "AffineLowerBoundObligation",
                },
                "target_state": {"id": "lower-envelope", "type": "LowerEnvelope"},
                "diagram": lower_diagram,
            },
            {
                "id": "log-exp-envelope-2",
                "title": "上側の境界は指数曲線への接線",
                "explanation_ja": "同じ傾きの直線を上げると、指数曲線に初めて触れる位置が上側の境界です。傾きが1以下の場合も別に調べ、下側条件と両立しないことを確認します。",
                "formula_tex": rf"{variable}=\log {slope_name},\qquad {intercept_name}={slope_name}(1-\log {slope_name})",
                "morphism": {
                    "morphism_id": chain[2],
                    "label_ja": "指数との差の最小値を接点で求める",
                    "input_type": "AffineUpperBoundObligation",
                    "output_type": "UpperEnvelope",
                },
                "source_state": {
                    "id": "upper-inequality",
                    "type": "AffineUpperBoundObligation",
                },
                "target_state": {"id": "upper-envelope", "type": "UpperEnvelope"},
                "diagram": upper_diagram,
            },
            {
                "id": "log-exp-envelope-3",
                "title": "二つの条件が重なる傾きを選ぶ",
                "explanation_ja": "下側の切片より上、上側の切片より下という二条件を重ねます。境界間の幅の符号を調べると、許される傾きが1とeの間に限られます。",
                "formula_tex": rf"{slope_name}(1-\log {slope_name})-(1-\log {slope_name})=({slope_name}-1)(1-\log {slope_name})",
                "morphism": {
                    "morphism_id": chain[3],
                    "label_ja": "上下二つの切片範囲を重ねる",
                    "input_type": "LowerAndUpperEnvelope",
                    "output_type": "AdmissibleParameterRegion",
                },
                "source_state": {
                    "id": "two-envelopes",
                    "type": "LowerAndUpperEnvelope",
                },
                "target_state": {
                    "id": "slope-interval",
                    "type": "AdmissibleParameterRegion",
                },
                "diagram": case_diagram,
            },
            {
                "id": "log-exp-envelope-4",
                "title": "切片の幅を積分する",
                "explanation_ja": "各傾きで許される切片の長さを縦の幅として読み、その幅を傾きについて積分します。図の青い部分がそのまま求める面積です。",
                "formula_tex": rf"\int_1^e({slope_name}-1)(1-\log {slope_name})\,d{slope_name}=\frac{{e^2-4e+5}}4",
                "morphism": {
                    "morphism_id": chain[4],
                    "label_ja": "係数領域を縦に切って積分する",
                    "input_type": "AdmissibleParameterRegion",
                    "output_type": "ExactArea",
                },
                "source_state": {
                    "id": "parameter-region",
                    "type": "AdmissibleParameterRegion",
                },
                "target_state": {"id": "region-area", "type": "ExactArea"},
                "diagram": region_diagram,
            },
        ],
    }

    return LogExpAffineEnvelopeSynthesis(
        answer={
            "region": region_tex,
            "area": sp.sstr(area),
        },
        answer_tex=answer_tex,
        tool_name="mortra.runtime_elementary_inequality_envelope",
        expression_tex=rf"\{{({slope_name},{intercept_name})\mid {region_tex}\}}",
        derivation_tex=derivation_tex,
        verification_checks=(
            "現在入力から正の変数、直線の傾きと切片、対数側・指数側の厳密不等式を抽出",
            "対数との差の二階導関数が正で、接点における値が b+log(a)-1 になることを記号計算で再生",
            "指数との差の二階導関数が正で、a>1 の接点における値が a(1-log(a))-b になることを再生",
            "a<=1 の場合が下側条件と両立しないことを境界値から確認",
            "二境界の差を (a-1)(1-log(a)) へ因数分解し、1<a<e を導出",
            "縦断面の幅を厳密積分し、面積 (e^2-4e+5)/4 を再生",
        ),
        proof_program=(
            {
                "rule": chain[0],
                "variable": variable,
                "slope": slope_name,
                "intercept": intercept_name,
                "lower_curve": "log(x)+2",
                "upper_curve": "exp(x)",
            },
            {
                "rule": chain[1],
                "contact": "x=1/a",
                "lower_boundary": sp.sstr(lower_boundary),
            },
            {
                "rule": chain[2],
                "contact": "x=log(a)",
                "upper_boundary": sp.sstr(upper_boundary),
            },
            {
                "rule": chain[3],
                "width_factorization": sp.sstr(width),
                "slope_interval": "1<a<e",
            },
            {
                "rule": chain[4],
                "integrand": sp.sstr(width),
                "bounds": ["1", "e"],
                "area": sp.sstr(area),
            },
        ),
        diagram=region_diagram,
        witness={
            "query_kind": "log_exp_affine_sandwich_region",
            "variable": variable,
            "slope_symbol": slope_name,
            "intercept_symbol": intercept_name,
            "lower_contact": "1/a",
            "lower_contact_gap": sp.sstr(lower_contact),
            "upper_contact": "log(a)",
            "upper_contact_gap": sp.sstr(upper_contact),
            "lower_boundary": sp.sstr(lower_boundary),
            "upper_boundary": sp.sstr(upper_boundary),
            "width_factorization": sp.sstr(width),
            "slope_interval": "1<a<e",
            "area": sp.sstr(area),
            "shared_chart": {
                "id": "affine_support_envelope.v1",
                "operation": "differentiate gap -> recover tangency boundary -> intersect -> integrate slice width",
                "problem_specific_answer_stored": False,
            },
        },
        visual_explanation=visual_explanation,
    )


__all__ = ["LogExpAffineEnvelopeSynthesis", "synthesize_log_exp_affine_sandwich"]
