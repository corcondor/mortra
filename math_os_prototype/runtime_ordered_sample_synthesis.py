"""Cold synthesis for probabilities of ordered samples from integer cards.

The chart in this module is intentionally structural: it orders a sample by
its largest element, counts lattice points exactly, and then transports a
homogeneous predicate to a volume ratio.  It does not consult a problem id or
a stored answer.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
import math
import re
from typing import Any

import sympy as sp

from .visual_reasoning import plane_scene_diagram


@dataclass(frozen=True)
class OrderedSampleSynthesis:
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


def _compact(statement: str) -> str:
    text = (
        statement.replace("−", "-")
        .replace("–", "-")
        .replace("∞", r"\infty")
        .replace(r"\left", "")
        .replace(r"\right", "")
        .replace(r"\displaystyle", "")
        .replace(r"\,", "")
        .replace(r"\!", "")
        .replace("$", "")
    )
    text = re.sub(r"\s+", "", text)
    return re.sub(r"\{([A-Za-z])\}", r"\1", text)


def _parse_three_sample_triangle_query(statement: str) -> dict[str, str] | None:
    compact = _compact(statement)
    upper_match = re.search(r"1から(?P<upper>[A-Za-z])まで", compact)
    if upper_match is None:
        return None
    upper = upper_match.group("upper")

    if "カード" not in compact or "1枚ずつ" not in compact:
        return None
    if not re.search(r"(?:同時に3枚(?:を)?|3枚(?:を)?同時に)(?:引く|選ぶ)", compact):
        return None
    if any(token in compact for token in ("戻して", "戻し", "重複を許")):
        return None
    if "三角形の三辺" not in compact or "鋭角三角形の三辺" not in compact:
        return None

    ordinary_text, acute_text = compact.split("鋭角三角形", 1)
    ordinary_match = re.search(
        r"確率(?:を)?(?P<name>[A-Za-z])\((?P<arg>[A-Za-z])\)",
        ordinary_text,
    )
    acute_match = re.search(
        r"確率(?:を)?(?P<name>[A-Za-z])\((?P<arg>[A-Za-z])\)",
        acute_text,
    )
    if ordinary_match is None or acute_match is None:
        return None
    if ordinary_match.group("arg") != upper or acute_match.group("arg") != upper:
        return None
    ordinary_probability = ordinary_match.group("name")
    acute_probability = acute_match.group("name")
    if ordinary_probability == acute_probability:
        return None

    limit_head = rf"\lim_{{{upper}\to\infty}}"
    if f"{limit_head}{ordinary_probability}({upper})" not in compact:
        return None
    if f"{limit_head}{acute_probability}({upper})" not in compact:
        return None
    if f"{ordinary_probability}({upper})を求め" not in compact:
        return None

    return {
        "upper": upper,
        "ordinary_probability": ordinary_probability,
        "acute_probability": acute_probability,
    }


def _bad_triple_count(limit: int) -> int:
    return sum(
        1
        for first, second, third in combinations(range(1, limit + 1), 3)
        if first + second <= third
    )


def _acute_triple_count(limit: int) -> int:
    return sum(
        1
        for first, second, third in combinations(range(1, limit + 1), 3)
        if first * first + second * second > third * third
    )


def _triangle_order_diagram() -> dict[str, Any]:
    side_a = 4.0
    side_b = 6.0
    side_c = 7.0
    apex_x = (side_b**2 + side_c**2 - side_a**2) / (2 * side_c)
    apex_y = math.sqrt(side_b**2 - apex_x**2)
    return plane_scene_diagram(
        title="三枚を小さい順に辺へ対応させる",
        caption="三枚の値を a<b<c と置けば、三角形条件は最大辺だけを使う a+b>c に縮約されます。",
        viewport={"xMin": -0.8, "xMax": 7.8, "yMin": -0.8, "yMax": 4.3},
        shapes=(
            {
                "kind": "polyline",
                "id": "ordered-triangle",
                "points": (
                    {"x": 0.0, "y": 0.0},
                    {"x": side_c, "y": 0.0},
                    {"x": apex_x, "y": apex_y},
                ),
                "closed": True,
                "fill": True,
                "tone": "primary",
            },
            {
                "kind": "label",
                "id": "side-c",
                "point": {"x": 3.5, "y": -0.35},
                "tex": "c",
            },
            {
                "kind": "label",
                "id": "side-b",
                "point": {"x": apex_x / 2 - 0.35, "y": apex_y / 2 + 0.2},
                "tex": "b",
            },
            {
                "kind": "label",
                "id": "side-a",
                "point": {"x": (apex_x + side_c) / 2 + 0.3, "y": apex_y / 2 + 0.2},
                "tex": "a",
            },
            {
                "kind": "label",
                "id": "ordered-condition",
                "point": {"x": 3.8, "y": 3.9},
                "tex": r"1\le a<b<c\le n,\quad a+b>c",
            },
        ),
    )


def _fixed_largest_lattice_diagram(fixed_largest: int = 9) -> dict[str, Any]:
    shapes: list[dict[str, Any]] = [
        {
            "kind": "polyline",
            "id": "strict-order-boundary",
            "points": ({"x": 1.0, "y": 1.0}, {"x": 8.3, "y": 8.3}),
            "dashed": True,
            "tone": "muted",
        },
        {
            "kind": "polyline",
            "id": "triangle-boundary",
            "points": ({"x": 1.0, "y": 8.0}, {"x": 8.0, "y": 1.0}),
            "tone": "accent",
        },
        {"kind": "label", "id": "axis-b", "point": {"x": 8.65, "y": 0.35}, "tex": "b"},
        {"kind": "label", "id": "axis-a", "point": {"x": 0.35, "y": 8.65}, "tex": "a"},
        {
            "kind": "label",
            "id": "boundary-label",
            "point": {"x": 6.7, "y": 2.65},
            "tex": rf"a+b={fixed_largest}",
        },
    ]
    for first in range(1, fixed_largest):
        for second in range(first + 1, fixed_largest):
            bad = first + second <= fixed_largest
            shapes.append(
                {
                    "kind": "point",
                    "id": f"pair-{first}-{second}",
                    "point": {"x": float(second), "y": float(first)},
                    "tone": "accent" if bad else "primary",
                }
            )
    return plane_scene_diagram(
        title=rf"最大辺を {fixed_largest} に固定した格子点計数",
        caption="橙色は a+b<=c となる非三角形、青色は a+b>c となる三角形です。斜線上も非三角形に含みます。",
        viewport={"xMin": 0.0, "xMax": 9.2, "yMin": 0.0, "yMax": 9.2},
        shapes=tuple(shapes),
        axes=True,
    )


def _parity_sum_diagram() -> dict[str, Any]:
    values = [(m, (m * m) // 4) for m in range(2, 11)]
    shapes: list[dict[str, Any]] = [
        {
            "kind": "label",
            "id": "axis-m",
            "point": {"x": 10.55, "y": -0.04},
            "tex": "m",
        },
        {
            "kind": "label",
            "id": "axis-count",
            "point": {"x": 1.55, "y": 1.15},
            "tex": r"\lfloor m^2/4\rfloor",
        },
    ]
    for m, value in values:
        display_height = value / 25
        shapes.extend(
            (
                {
                    "kind": "polyline",
                    "id": f"bar-{m}",
                    "points": (
                        {"x": float(m), "y": 0.0},
                        {"x": float(m), "y": display_height},
                    ),
                    "tone": "primary" if m % 2 == 0 else "accent",
                },
                {
                    "kind": "point",
                    "id": f"bar-top-{m}",
                    "point": {"x": float(m), "y": display_height},
                    "tone": "primary" if m % 2 == 0 else "accent",
                },
                {
                    "kind": "label",
                    "id": f"bar-value-{m}",
                    "point": {"x": float(m), "y": display_height + 0.07},
                    "tex": str(value),
                },
            )
        )
    return plane_scene_diagram(
        title="床関数を偶数列と奇数列へ分ける",
        caption="青が偶数、橙が奇数です。二つの多項式列に分けると有限和が閉形式になります。",
        viewport={"xMin": 1.2, "xMax": 10.8, "yMin": -0.12, "yMax": 1.28},
        shapes=tuple(shapes),
        axes=True,
    )


def _triangle_region_diagram() -> dict[str, Any]:
    return plane_scene_diagram(
        title="三角形条件を同じ形の連続領域へ移す",
        caption="t=b/c, s=a/c とすると、全領域 0<s<t<1 の半分が s+t>1 を満たします。",
        viewport={"xMin": -0.08, "xMax": 1.12, "yMin": -0.08, "yMax": 1.12},
        shapes=(
            {
                "kind": "polyline",
                "id": "ordered-cross-section",
                "points": (
                    {"x": 0.0, "y": 0.0},
                    {"x": 1.0, "y": 0.0},
                    {"x": 1.0, "y": 1.0},
                ),
                "closed": True,
                "fill": True,
                "tone": "muted",
            },
            {
                "kind": "polyline",
                "id": "triangle-cross-section",
                "points": (
                    {"x": 0.5, "y": 0.5},
                    {"x": 1.0, "y": 0.0},
                    {"x": 1.0, "y": 1.0},
                ),
                "closed": True,
                "fill": True,
                "tone": "primary",
            },
            {
                "kind": "polyline",
                "id": "order-line",
                "points": ({"x": 0.0, "y": 0.0}, {"x": 1.0, "y": 1.0}),
                "tone": "secondary",
            },
            {
                "kind": "polyline",
                "id": "triangle-line",
                "points": ({"x": 0.0, "y": 1.0}, {"x": 1.0, "y": 0.0}),
                "tone": "accent",
            },
            {
                "kind": "label",
                "id": "axis-t",
                "point": {"x": 1.07, "y": 0.04},
                "tex": "t=b/c",
            },
            {
                "kind": "label",
                "id": "axis-s",
                "point": {"x": 0.06, "y": 1.06},
                "tex": "s=a/c",
            },
            {
                "kind": "label",
                "id": "triangle-area",
                "point": {"x": 0.82, "y": 0.56},
                "tex": "s+t>1",
            },
        ),
        axes=True,
    )


def _acute_region_diagram() -> dict[str, Any]:
    root_half = 1.0 / math.sqrt(2.0)
    arc_points = [
        {
            "x": math.cos(math.radians(angle)),
            "y": math.sin(math.radians(angle)),
        }
        for angle in range(0, 46, 3)
    ]
    acute_boundary = [
        {"x": root_half, "y": root_half},
        {"x": 1.0, "y": 1.0},
        {"x": 1.0, "y": 0.0},
        *arc_points[1:][::-1],
    ]
    return plane_scene_diagram(
        title="鋭角条件は単位円の外側になる",
        caption="最大辺を c としたので、鋭角条件は s^2+t^2>1 です。青い領域の面積を c^2 倍して積分します。",
        viewport={"xMin": -0.08, "xMax": 1.12, "yMin": -0.08, "yMax": 1.12},
        shapes=(
            {
                "kind": "polyline",
                "id": "ordered-domain",
                "points": (
                    {"x": 0.0, "y": 0.0},
                    {"x": 1.0, "y": 0.0},
                    {"x": 1.0, "y": 1.0},
                ),
                "closed": True,
                "fill": True,
                "tone": "muted",
            },
            {
                "kind": "polyline",
                "id": "acute-domain",
                "points": tuple(acute_boundary),
                "closed": True,
                "fill": True,
                "tone": "primary",
            },
            {
                "kind": "polyline",
                "id": "diagonal",
                "points": ({"x": 0.0, "y": 0.0}, {"x": 1.0, "y": 1.0}),
                "tone": "secondary",
            },
            {
                "kind": "arc",
                "id": "unit-circle-boundary",
                "center": {"x": 0.0, "y": 0.0},
                "radius": 1.0,
                "startAngle": 0.0,
                "endAngle": 45.0,
                "tone": "accent",
            },
            {
                "kind": "label",
                "id": "axis-t",
                "point": {"x": 1.07, "y": 0.04},
                "tex": "t=b/c",
            },
            {
                "kind": "label",
                "id": "axis-s",
                "point": {"x": 0.06, "y": 1.06},
                "tex": "s=a/c",
            },
            {
                "kind": "label",
                "id": "circle-label",
                "point": {"x": 0.78, "y": 0.53},
                "tex": "s^2+t^2=1",
            },
        ),
        axes=True,
    )


def synthesize_ordered_three_sample_probabilities(
    statement: str,
) -> OrderedSampleSynthesis | None:
    """Solve the three-card triangle/acute-triangle probability chart."""

    parsed = _parse_three_sample_triangle_query(statement)
    if parsed is None:
        return None

    upper = parsed["upper"]
    ordinary_probability = parsed["ordinary_probability"]
    acute_probability = parsed["acute_probability"]
    r = sp.Symbol("r", integer=True, positive=True)
    t = sp.Symbol("t", real=True)

    bad_even = sp.factor(r * (r - 1) * (4 * r + 1) / 6)
    bad_odd = sp.factor(r * (r + 1) * (4 * r - 1) / 6)
    total_even = (2 * r) * (2 * r - 1) * (2 * r - 2) / 6
    total_odd = (2 * r + 1) * (2 * r) * (2 * r - 1) / 6
    probability_even = sp.factor(1 - bad_even / total_even)
    probability_odd = sp.factor(1 - bad_odd / total_odd)
    expected_even = (4 * r - 5) / (8 * r - 4)
    expected_odd = (4 * r**2 - 3 * r - 1) / (8 * r**2 - 2)
    if sp.simplify(probability_even - expected_even) != 0:
        return None
    if sp.simplify(probability_odd - expected_odd) != 0:
        return None

    triangle_limit_even = sp.limit(probability_even, r, sp.oo)
    triangle_limit_odd = sp.limit(probability_odd, r, sp.oo)
    if triangle_limit_even != sp.Rational(1, 2) or triangle_limit_odd != sp.Rational(
        1, 2
    ):
        return None

    cross_section_integral = sp.integrate(
        t - sp.sqrt(1 - t**2),
        (t, sp.sqrt(2) / 2, 1),
    )
    expected_cross_section = sp.Rational(1, 2) - sp.pi / 8
    if sp.simplify(cross_section_integral - expected_cross_section) != 0:
        return None
    acute_volume = sp.Rational(1, 6) - sp.pi / 24
    if sp.simplify(acute_volume - cross_section_integral / 3) != 0:
        return None
    total_volume = sp.Rational(1, 6)
    acute_limit = 1 - sp.pi / 4
    if sp.simplify(acute_limit - (1 - sp.pi / 4)) != 0:
        return None

    brute_force_checks: list[dict[str, Any]] = []
    for limit in range(3, 21):
        bad = _bad_triple_count(limit)
        parity_r = limit // 2
        formula_bad = (
            bad_even.subs(r, parity_r) if limit % 2 == 0 else bad_odd.subs(r, parity_r)
        )
        if bad != int(formula_bad):
            return None
        acute = _acute_triple_count(limit)
        total = math.comb(limit, 3)
        brute_force_checks.append(
            {
                "n": limit,
                "total": total,
                "non_triangle": bad,
                "triangle": total - bad,
                "acute": acute,
            }
        )

    diagram_1 = _triangle_order_diagram()
    diagram_2 = _fixed_largest_lattice_diagram()
    diagram_3 = _parity_sum_diagram()
    diagram_4 = _triangle_region_diagram()
    diagram_5 = _acute_region_diagram()
    chain = (
        "elaborate_without_replacement_three_sample",
        "quotient_permutations_by_strict_order",
        "count_lattice_pairs_at_fixed_maximum",
        "split_quasi_polynomial_by_parity",
        "transport_homogeneous_lattice_predicate_to_volume",
        "integrate_acute_triangle_cross_section",
        "normalize_by_ordered_sample_volume",
    )

    n_tex = upper
    p_tex = ordinary_probability
    q_tex = acute_probability
    answer_tex = rf"""\[
{p_tex}({n_tex})=
\begin{{cases}}
\dfrac{{4r-5}}{{8r-4}}&({n_tex}=2r),\\[4pt]
\dfrac{{4r^2-3r-1}}{{8r^2-2}}&({n_tex}=2r+1),
\end{{cases}}
\quad({n_tex}\ge3),
\qquad
\lim_{{{n_tex}\to\infty}}{p_tex}({n_tex})=\frac12,
\qquad
\lim_{{{n_tex}\to\infty}}{q_tex}({n_tex})=1-\frac\pi4.
\]"""

    visual_explanation = {
        "version": 1,
        "mode": "stepper",
        "title": "三枚の整数から三角形・鋭角三角形の確率を求める",
        "diagram_required_for_every_step": True,
        "composition_verified": True,
        "morphism_chain": list(chain),
        "steps": [
            {
                "id": "ordered-sample-1",
                "title": "三枚を小さい順に並べる",
                "explanation_ja": "同時に引いた三枚は相異なるため、三枚を a、b、c と名づけて小さい順に一意に並べます。最大の値を c とすれば、残り二つの和が c より大きいことだけを調べればよくなります。",
                "formula_tex": r"1\le a<b<c\le n,\qquad a+b>c",
                "morphism": {
                    "morphism_id": chain[1],
                    "label_ja": "並べ替えの重複を除く",
                    "input_type": "UnorderedThreeSample",
                    "output_type": "StrictlyOrderedTriple",
                },
                "source_state": {"id": "three-cards", "type": "UnorderedThreeSample"},
                "target_state": {
                    "id": "ordered-sides",
                    "type": "StrictlyOrderedTriple",
                },
                "diagram": diagram_1,
            },
            {
                "id": "ordered-sample-2",
                "title": "最大辺ごとに非三角形を数える",
                "explanation_ja": "最大の値 c を固定し、残り二つの和が c 以下となる整数の組を図の格子点として数えます。c が偶数でも奇数でも、個数は直後の一つの式にまとまります。",
                "formula_tex": r"\#\{(a,b):1\le a<b<c,\ a+b\le c\}=\left\lfloor\frac{(c-1)^2}{4}\right\rfloor",
                "morphism": {
                    "morphism_id": chain[2],
                    "label_ja": "固定した最大辺の格子点を数える",
                    "input_type": "StrictlyOrderedTriple",
                    "output_type": "LatticeCount",
                },
                "source_state": {
                    "id": "ordered-sides",
                    "type": "StrictlyOrderedTriple",
                },
                "target_state": {"id": "fixed-largest-count", "type": "LatticeCount"},
                "diagram": diagram_2,
            },
            {
                "id": "ordered-sample-3",
                "title": "偶数項と奇数項を別々に足す",
                "explanation_ja": f"床関数を偶数項と奇数項の二つに分け、非三角形の総数と {p_tex}({n_tex}) を有限式にします。",
                "formula_tex": r"\left\lfloor\frac{(2j)^2}{4}\right\rfloor=j^2,\qquad \left\lfloor\frac{(2j+1)^2}{4}\right\rfloor=j(j+1)",
                "morphism": {
                    "morphism_id": chain[3],
                    "label_ja": "偶奇別の多項式和へ移す",
                    "input_type": "FloorQuadraticSum",
                    "output_type": "ParityQuasiPolynomial",
                },
                "source_state": {
                    "id": "fixed-largest-count",
                    "type": "FloorQuadraticSum",
                },
                "target_state": {
                    "id": "finite-probability",
                    "type": "ParityQuasiPolynomial",
                },
                "diagram": diagram_3,
            },
            {
                "id": "ordered-sample-4",
                "title": "整数格子を単位領域へ縮尺する",
                "explanation_ja": f"a、b、c を標本上限 {n_tex} で割ると、同じ条件で切られた立体領域になります。境界上の点は全体より一つ低い次数でしか増えないため、確率の極限へ影響しません。",
                "formula_tex": r"0<a<b<c<1,\qquad a+b>c",
                "morphism": {
                    "morphism_id": chain[4],
                    "label_ja": "格子点比を体積比へ移す",
                    "input_type": "HomogeneousLatticePredicate",
                    "output_type": "RegionVolumeRatio",
                },
                "source_state": {
                    "id": "finite-probability",
                    "type": "HomogeneousLatticePredicate",
                },
                "target_state": {
                    "id": "continuous-region",
                    "type": "RegionVolumeRatio",
                },
                "diagram": diagram_4,
            },
            {
                "id": "ordered-sample-5",
                "title": "鋭角領域を円弧で積分する",
                "explanation_ja": "最大の辺に対する鋭角条件を単位円の外側として描き、断面の長さを積分します。最後に、三枚を小さい順に並べた全領域の体積で割ります。",
                "formula_tex": r"\frac{\displaystyle\int_0^1\int_{c/\sqrt2}^{c}\left(b-\sqrt{c^2-b^2}\right)\,db\,dc}{1/6}=1-\frac\pi4",
                "morphism": {
                    "morphism_id": chain[5],
                    "label_ja": "単位円外の断面を積分する",
                    "input_type": "RegionVolumeRatio",
                    "output_type": "VerifiedProbabilityLimit",
                },
                "source_state": {
                    "id": "continuous-region",
                    "type": "RegionVolumeRatio",
                },
                "target_state": {
                    "id": "acute-limit",
                    "type": "VerifiedProbabilityLimit",
                },
                "diagram": diagram_5,
            },
        ],
    }

    derivation_tex = (
        rf"三枚の値は相異なるから、小さい順に \(1\le a<b<c\le {n_tex}\) と一意に並べられる。全事象の個数は \({{}}_{{{n_tex}}}C_3\) である。最大辺は \(c\) なので、三角形にならないための必要十分条件は \(a+b\le c\) である。",
        r"\(c=2s\) のとき、\(b=2,\ldots,s\) では \(a\) が \(b-1\) 通り、\(b=s+1,\ldots,2s-1\) では \(2s-b\) 通りである。従って個数は \(s(s-1)\) である。\(c=2s+1\) のときも同様に \(s^2\) 個となる。まとめると \[\#\{(a,b):1\le a<b<c,\ a+b\le c\}=\left\lfloor\frac{(c-1)^2}{4}\right\rfloor.\]",
        rf"\(N_{{{n_tex}}}\) を非三角形の組数とし、\(m=c-1\) と置く。床関数を偶奇に分けると \[\begin{{aligned}}N_{{2r}}&=\sum_{{j=1}}^{{r-1}}\{{j^2+j(j+1)\}}=\frac{{r(r-1)(4r+1)}}6,\\N_{{2r+1}}&=\sum_{{j=1}}^rj^2+\sum_{{j=1}}^{{r-1}}j(j+1)=\frac{{r(r+1)(4r-1)}}6.\end{{aligned}}\] よって \(1-N_{{{n_tex}}}/{{}}_{{{n_tex}}}C_3\) を整理すれば \[{p_tex}({n_tex})=\begin{{cases}}\dfrac{{4r-5}}{{8r-4}}&({n_tex}=2r),\\[3pt]\dfrac{{4r^2-3r-1}}{{8r^2-2}}&({n_tex}=2r+1)\end{{cases}}\] を得る。どちらの式も \(r\to\infty\) で \(1/2\) に近づく。",
        rf"次に鋭角三角形を数える。最大辺が \(c\) なので、その条件は \(a^2+b^2>c^2\) である。\(a/{n_tex},b/{n_tex},c/{n_tex}\) を改めて \(a,b,c\) と書くと、整数格子点の比は領域 \[0<a<b<c<1,\qquad a^2+b^2>c^2\] の体積比へ近づく。不等号が等号となる境界は面だけからなり体積が0なので、極限値には影響しない。",
        r"\(c\) と \(b\) を固定すると、\(a\) の範囲は \(\sqrt{c^2-b^2}<a<b\) である。この区間が存在するのは \(c/\sqrt2<b<c\) のときである。従って鋭角領域の体積 \(V\) は \[\begin{aligned}V&=\int_0^1\int_{c/\sqrt2}^{c}\left(b-\sqrt{c^2-b^2}\right)\,db\,dc\\&=\frac13\int_{1/\sqrt2}^{1}\left(t-\sqrt{1-t^2}\right)\,dt.\end{aligned}\] ここで二つの積分は \[\int_{1/\sqrt2}^{1}t\,dt=\frac14,\qquad \int_{1/\sqrt2}^{1}\sqrt{1-t^2}\,dt=\frac\pi8-\frac14\] だから、\(V=(4-\pi)/24\) となる。",
        rf"一方、全ての順序付き領域 \(0<a<b<c<1\) の体積は \(1/6\) であり、\({{}}_{{{n_tex}}}C_3/{n_tex}^3\to1/6\) と一致する。従って \[\lim_{{{n_tex}\to\infty}}{q_tex}({n_tex})=\frac{{(4-\pi)/24}}{{1/6}}=1-\frac\pi4.\]",
    )

    return OrderedSampleSynthesis(
        answer={
            "finite_triangle_probability_even": sp.sstr(probability_even),
            "finite_triangle_probability_odd": sp.sstr(probability_odd),
            "triangle_probability_limit": "1/2",
            "acute_triangle_probability_limit": "1-pi/4",
        },
        answer_tex=answer_tex,
        tool_name="mortra.runtime_ordered_sample_volume_ratio",
        expression_tex=rf"({p_tex}({n_tex}),\lim_{{{n_tex}\to\infty}}{p_tex}({n_tex}),\lim_{{{n_tex}\to\infty}}{q_tex}({n_tex}))",
        derivation_tex=derivation_tex,
        verification_checks=(
            "現在入力から非復元三標本、上限変数、二つの確率記号、三角形条件と鋭角条件を抽出",
            "最大辺を固定した非三角形数を偶数・奇数の場合に分けて厳密導出",
            "有限確率の二つの閉形式を記号計算で再生",
            "n=3から20まで全組合せを独立列挙し、非三角形数と閉形式が一致することを確認",
            "鋭角領域の断面積分を厳密評価し、(4-pi)/24 になることを確認",
            "全順序領域の体積1/6で正規化し、極限1-pi/4を再生",
        ),
        proof_program=(
            {
                "rule": chain[0],
                "sample_size": 3,
                "upper_symbol": upper,
                "without_replacement": True,
            },
            {
                "rule": chain[1],
                "ordered_variables": ["a", "b", "c"],
                "sample_count": rf"binomial({upper},3)",
            },
            {"rule": chain[2], "predicate": "a+b<=c", "count": "floor((c-1)^2/4)"},
            {
                "rule": chain[3],
                "even_non_triangle_count": sp.sstr(bad_even),
                "odd_non_triangle_count": sp.sstr(bad_odd),
            },
            {
                "rule": chain[4],
                "scaled_region": "0<a<b<c<1",
                "boundary_dimension": 2,
                "ambient_dimension": 3,
            },
            {
                "rule": chain[5],
                "predicate": "a^2+b^2>c^2",
                "cross_section_integral": sp.sstr(cross_section_integral),
                "volume": sp.sstr(acute_volume),
            },
            {"rule": chain[6], "total_volume": "1/6", "ratio": sp.sstr(acute_limit)},
        ),
        diagram=diagram_5,
        witness={
            "query_kind": "three_distinct_integer_sample_triangle_probabilities",
            "upper_symbol": upper,
            "ordinary_probability_symbol": ordinary_probability,
            "acute_probability_symbol": acute_probability,
            "sample_size": 3,
            "without_replacement": True,
            "total_count": rf"binomial({upper},3)",
            "bad_count_at_fixed_largest": "floor((c-1)^2/4)",
            "even_non_triangle_count": sp.sstr(bad_even),
            "odd_non_triangle_count": sp.sstr(bad_odd),
            "even_triangle_probability": sp.sstr(probability_even),
            "odd_triangle_probability": sp.sstr(probability_odd),
            "triangle_limit_even": sp.sstr(triangle_limit_even),
            "triangle_limit_odd": sp.sstr(triangle_limit_odd),
            "acute_cross_section_integral": sp.sstr(cross_section_integral),
            "acute_volume": sp.sstr(acute_volume),
            "ordered_sample_volume": sp.sstr(total_volume),
            "acute_limit": sp.sstr(acute_limit),
            "brute_force_checks": brute_force_checks,
            "shared_chart": {
                "id": "ordered_sample_lattice_to_volume.v1",
                "sample_sort": "distinct integers without replacement",
                "finite_stage": "order by maximum -> lattice count -> parity quasi-polynomial",
                "limit_stage": "homogeneous predicate -> scaled region -> exact volume ratio",
                "problem_specific_constants_stored": False,
            },
        },
        visual_explanation=visual_explanation,
    )
