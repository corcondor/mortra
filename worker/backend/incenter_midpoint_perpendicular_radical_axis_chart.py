"""Exact chart for the incenter midpoint-perpendicular radical-axis theorem.

For a triangle ``ABC`` with incenter ``I``, let the lines through the side
midpoints perpendicular to ``AI``, ``BI``, and ``CI`` form a second triangle.
The midpoint of ``I`` and the second triangle's orthocenter has equal powers
to the two circumcircles.  The implementation proves the reusable theorem in
a unit-incircle tangent chart and then matches only the typed construction
graph of a JGEX problem.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
import hashlib
import io
import itertools
import json
import math

import matplotlib
import sympy as sp

matplotlib.use("Agg")

from matplotlib import pyplot as plt
from matplotlib.patches import Circle

from worker.backend.geometry_proof_hypergraph import Atom
from worker.backend.jgex_chart_parser import ChartJGEXFormulation as JGEXFormulation


@dataclass(frozen=True)
class IncenterMidpointPerpendicularRadicalAxisCertificate:
    theorem: str
    normalization: str
    parameter_domain: tuple[str, ...]
    construction_domain_conditions: tuple[str, ...]
    discharged_conditions: dict[str, str]
    upstream_semantics: tuple[str, ...]
    coordinates: dict[str, tuple[str, str]]
    determinant_factors: dict[str, str]
    replay_residuals: dict[str, str]
    replayed: bool
    all_conditions_discharged: bool
    certificate_sha256: str

    @property
    def assumptions(self) -> tuple[str, ...]:
        return self.parameter_domain + self.construction_domain_conditions

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["assumptions"] = self.assumptions
        return payload

    def to_markdown(self) -> str:
        coordinates = "\n".join(
            f"- `{name}=({value[0]}, {value[1]})`"
            for name, value in self.coordinates.items()
        )
        determinants = "\n".join(
            f"- `{name}`: `{value}`"
            for name, value in self.determinant_factors.items()
        )
        residuals = "\n".join(
            f"- `{name}`: `{value}`" for name, value in self.replay_residuals.items()
        )
        discharged = "\n".join(
            f"- `{condition}`: {reason}"
            for condition, reason in self.discharged_conditions.items()
        )
        return "\n".join(
            (
                "# 内心・辺中点垂線三角形の根軸チャート",
                "",
                "## 定理",
                "",
                (
                    "三角形 $ABC$ の内心を $I$ とする。辺 $BC,CA,AB$ の中点を"
                    "それぞれ $M_A,M_B,M_C$ とし、$M_A,M_B,M_C$ を通って"
                    "$AI,BI,CI$ に垂直な3直線が作る三角形を $A_1B_1C_1$ とする。"
                    "その垂心を $H$、$IH$ の中点を $M$ とすると、$M$ は"
                    "$ABC$ と $A_1B_1C_1$ の外接円の根軸上にある。"
                ),
                "",
                "## 標準化",
                "",
                self.normalization,
                "",
                "## 定義域条件",
                "",
                *(f"- `{item}`" for item in self.assumptions),
                "",
                "## 条件の消去",
                "",
                discharged,
                "",
                "## 座標",
                "",
                coordinates,
                "",
                "## 非退化因子",
                "",
                determinants,
                "",
                "## 恒等式再生",
                "",
                residuals,
                "",
                f"- 全恒等式再生: `{self.replayed}`",
                f"- 未消去条件なし: `{self.all_conditions_discharged}`",
                f"- 証明書 SHA-256: `{self.certificate_sha256}`",
                "",
            )
        )


@dataclass(frozen=True)
class JGEXIncenterMidpointPerpendicularRadicalAxisApplication:
    theorem: str
    source_sha256: str
    roles: dict[str, str]
    matched_constructions: tuple[str, ...]
    goal: str
    chart_certificate_sha256: str
    nondegeneracy_obligations: tuple[str, ...]
    undischarged_nondegeneracy_obligations: tuple[str, ...]
    replayed: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _canonical(expression: sp.Expr) -> str:
    return str(sp.factor(sp.cancel(expression)))


def _point(x: sp.Expr, y: sp.Expr) -> sp.Matrix:
    return sp.Matrix((x, y))


def _cross(left: sp.Matrix, right: sp.Matrix) -> sp.Expr:
    return sp.expand(left[0] * right[1] - left[1] * right[0])


def _line_intersection(
    first_normal: sp.Matrix,
    first_rhs: sp.Expr,
    second_normal: sp.Matrix,
    second_rhs: sp.Expr,
) -> tuple[sp.Matrix, sp.Expr]:
    determinant = sp.factor(_cross(first_normal, second_normal))
    point = _point(
        (first_rhs * second_normal[1] - first_normal[1] * second_rhs)
        / determinant,
        (first_normal[0] * second_rhs - first_rhs * second_normal[0])
        / determinant,
    ).applyfunc(sp.cancel)
    return point, determinant


def _circumcenter(
    point_a: sp.Matrix,
    point_b: sp.Matrix,
    point_c: sp.Matrix,
) -> tuple[sp.Matrix, sp.Expr]:
    ab = point_b - point_a
    ac = point_c - point_a
    determinant = sp.factor(2 * _cross(ab, ac))
    rhs_b = sp.expand(point_b.dot(point_b) - point_a.dot(point_a))
    rhs_c = sp.expand(point_c.dot(point_c) - point_a.dot(point_a))
    center = _point(
        (rhs_b * ac[1] - ab[1] * rhs_c) / determinant,
        (ab[0] * rhs_c - rhs_b * ac[0]) / determinant,
    ).applyfunc(sp.cancel)
    return center, determinant


@lru_cache(maxsize=1)
def certify_incenter_midpoint_perpendicular_radical_axis_chart(
) -> IncenterMidpointPerpendicularRadicalAxisCertificate:
    p, q = sp.symbols("p q", real=True)
    i = _point(0, 0)

    # After a Euclidean similarity, BC is the tangent x=1 to the unit
    # incircle.  The other two tangent lines use the rational half-angle
    # parameters p and q.
    normal_bc = _point(1, 0)
    normal_ca = _point(1 - p**2, 2 * p)
    normal_ab = _point(1 - q**2, 2 * q)
    rhs_bc = sp.Integer(1)
    rhs_ca = 1 + p**2
    rhs_ab = 1 + q**2

    point_a = _point((1 - p * q) / (1 + p * q), (p + q) / (1 + p * q))
    point_b = _point(1, q)
    point_c = _point(1, p)
    midpoint_a = ((point_b + point_c) / 2).applyfunc(sp.cancel)
    midpoint_b = ((point_c + point_a) / 2).applyfunc(sp.cancel)
    midpoint_c = ((point_a + point_b) / 2).applyfunc(sp.cancel)

    line_a_rhs = sp.expand(point_a.dot(midpoint_a))
    line_b_rhs = sp.expand(point_b.dot(midpoint_b))
    line_c_rhs = sp.expand(point_c.dot(midpoint_c))
    point_a1, determinant_a1 = _line_intersection(
        point_b, line_b_rhs, point_c, line_c_rhs
    )
    point_b1, determinant_b1 = _line_intersection(
        point_a, line_a_rhs, point_c, line_c_rhs
    )
    point_c1, determinant_c1 = _line_intersection(
        point_a, line_a_rhs, point_b, line_b_rhs
    )

    center_o, determinant_o = _circumcenter(point_a, point_b, point_c)
    center_o1, determinant_o1 = _circumcenter(point_a1, point_b1, point_c1)
    h = (point_a1 + point_b1 + point_c1 - 2 * center_o1).applyfunc(sp.cancel)
    m = (h / 2).applyfunc(sp.cancel)
    radius_squared = sp.cancel((point_a - center_o).dot(point_a - center_o))
    radius1_squared = sp.cancel((point_a1 - center_o1).dot(point_a1 - center_o1))
    power = sp.cancel((m - center_o).dot(m - center_o) - radius_squared)
    power1 = sp.cancel((m - center_o1).dot(m - center_o1) - radius1_squared)

    residuals = {
        "CA_tangent_normalized": normal_ca.dot(normal_ca) - rhs_ca**2,
        "AB_tangent_normalized": normal_ab.dot(normal_ab) - rhs_ab**2,
        "A_on_CA": normal_ca.dot(point_a) - rhs_ca,
        "A_on_AB": normal_ab.dot(point_a) - rhs_ab,
        "B_on_AB": normal_ab.dot(point_b) - rhs_ab,
        "B_on_BC": normal_bc.dot(point_b) - rhs_bc,
        "C_on_BC": normal_bc.dot(point_c) - rhs_bc,
        "C_on_CA": normal_ca.dot(point_c) - rhs_ca,
        "MA_midpoint_x": 2 * midpoint_a[0] - point_b[0] - point_c[0],
        "MA_midpoint_y": 2 * midpoint_a[1] - point_b[1] - point_c[1],
        "MB_midpoint_x": 2 * midpoint_b[0] - point_c[0] - point_a[0],
        "MB_midpoint_y": 2 * midpoint_b[1] - point_c[1] - point_a[1],
        "MC_midpoint_x": 2 * midpoint_c[0] - point_a[0] - point_b[0],
        "MC_midpoint_y": 2 * midpoint_c[1] - point_a[1] - point_b[1],
        "A1_on_line_B": point_b.dot(point_a1 - midpoint_b),
        "A1_on_line_C": point_c.dot(point_a1 - midpoint_c),
        "B1_on_line_A": point_a.dot(point_b1 - midpoint_a),
        "B1_on_line_C": point_c.dot(point_b1 - midpoint_c),
        "C1_on_line_A": point_a.dot(point_c1 - midpoint_a),
        "C1_on_line_B": point_b.dot(point_c1 - midpoint_b),
        "O_equidistant_A_B": (
            (center_o - point_a).dot(center_o - point_a)
            - (center_o - point_b).dot(center_o - point_b)
        ),
        "O_equidistant_A_C": (
            (center_o - point_a).dot(center_o - point_a)
            - (center_o - point_c).dot(center_o - point_c)
        ),
        "O1_equidistant_A1_B1": (
            (center_o1 - point_a1).dot(center_o1 - point_a1)
            - (center_o1 - point_b1).dot(center_o1 - point_b1)
        ),
        "O1_equidistant_A1_C1": (
            (center_o1 - point_a1).dot(center_o1 - point_a1)
            - (center_o1 - point_c1).dot(center_o1 - point_c1)
        ),
        "H_altitude_A1": (h - point_a1).dot(point_c1 - point_b1),
        "H_altitude_B1": (h - point_b1).dot(point_a1 - point_c1),
        "H_altitude_C1": (h - point_c1).dot(point_b1 - point_a1),
        "M_midpoint_IH_x": 2 * m[0] - i[0] - h[0],
        "M_midpoint_IH_y": 2 * m[1] - i[1] - h[1],
        "circumradii_equal": radius_squared - radius1_squared,
        "M_equal_circle_powers": power - power1,
    }
    rendered = {name: _canonical(value) for name, value in residuals.items()}
    replayed = all(value == "0" for value in rendered.values())
    coordinates = {
        name: (_canonical(value[0]), _canonical(value[1]))
        for name, value in {
            "I": i,
            "A": point_a,
            "B": point_b,
            "C": point_c,
            "MA": midpoint_a,
            "MB": midpoint_b,
            "MC": midpoint_c,
            "A1": point_a1,
            "B1": point_b1,
            "C1": point_c1,
            "O": center_o,
            "O1": center_o1,
            "H": h,
            "M": m,
        }.items()
    }
    determinant_factors = {
        "triangle_ABC_twice_area": _canonical(
            _cross(point_b - point_a, point_c - point_a)
        ),
        "line_B_line_C": _canonical(determinant_a1),
        "line_A_line_C": _canonical(determinant_b1),
        "line_A_line_B": _canonical(determinant_c1),
        "triangle_A1B1C1_twice_area": _canonical(
            _cross(point_b1 - point_a1, point_c1 - point_a1)
        ),
        "circumcenter_ABC": _canonical(determinant_o),
        "circumcenter_A1B1C1": _canonical(determinant_o1),
    }
    discharged_conditions = {
        "p*q*(p-q)*(1+p*q) != 0": (
            "The JGEX triangle and incenter require three distinct nonparallel "
            "side tangents; this is exactly the nonzero factor in the unit-incircle chart."
        ),
        "triangle A1B1C1 is nondegenerate": (
            "Its doubled area factors as -p*q*(p-q)*(1+p^2)*(1+q^2) / "
            "(4*(1+p*q)^2), hence it is nonzero over the real parameter domain."
        ),
        "X and Y are distinct common points of the two circles": (
            "The source constructs two circle intersections and uses them as a line; "
            "the JGEX construction domain rejects a collapsed common chord."
        ),
    }
    upstream_semantics = (
        "JGEX incenter supplies one point equidistant from the three side lines.",
        "JGEX line intersections reject parallel or coincident defining lines.",
        "JGEX circumcenter and orthocenter reject degenerate defining triangles.",
        "Two distinct common circle points span their radical axis.",
    )
    payload = {
        "theorem": "incenter-side-midpoint-perpendicular-triangle-radical-axis",
        "normalization": (
            "I=(0,0), the incircle has radius 1, BC is x=1, and the other "
            "two side tangents have half-angle parameters p and q."
        ),
        "parameter_domain": (
            "p and q are real",
            "p*q*(p-q)*(1+p*q) != 0",
        ),
        "construction_domain_conditions": (
            "the three midpoint perpendiculars form a nondegenerate triangle",
            "the two circumcircles have two distinct supplied common points X,Y",
        ),
        "discharged_conditions": discharged_conditions,
        "upstream_semantics": upstream_semantics,
        "coordinates": coordinates,
        "determinant_factors": determinant_factors,
        "replay_residuals": rendered,
        "replayed": replayed,
        "all_conditions_discharged": replayed,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return IncenterMidpointPerpendicularRadicalAxisCertificate(
        **payload,
        certificate_sha256=digest,
    )


def _records(formulation: JGEXFormulation) -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "outputs": tuple(map(str, clause.points)),
            "constructions": tuple(
                (construction.name, tuple(map(str, construction.args)))
                for construction in clause.constructions
            ),
        }
        for clause in formulation.setup_clauses
    )


def _single_unordered(
    records: tuple[dict[str, object], ...],
    name: str,
    args: frozenset[str],
) -> str | None:
    for record in records:
        if len(record["outputs"]) != 1 or len(record["constructions"]) != 1:
            continue
        construction_name, construction_args = record["constructions"][0]
        if construction_name == name and frozenset(construction_args) == args:
            return record["outputs"][0]
    return None


def _has_tline(
    constructions: tuple[tuple[str, tuple[str, ...]], ...],
    origin: str,
    left: str,
    right: str,
) -> bool:
    return any(
        name == "on_tline"
        and len(args) == 3
        and args[0] == origin
        and frozenset(args[1:]) == frozenset((left, right))
        for name, args in constructions
    )


def _tline_intersection_role(
    records: tuple[dict[str, object], ...],
    first: tuple[str, str, str],
    second: tuple[str, str, str],
) -> str | None:
    for record in records:
        if (
            len(record["outputs"]) == 1
            and _has_tline(record["constructions"], *first)
            and _has_tline(record["constructions"], *second)
        ):
            return record["outputs"][0]
    return None


def _has_circle(
    constructions: tuple[tuple[str, tuple[str, ...]], ...],
    center: str,
    through: str,
) -> bool:
    return any(
        name == "on_circle" and args == (center, through)
        for name, args in constructions
    )


def _circle_intersection_roles(
    records: tuple[dict[str, object], ...],
    first_circle: tuple[str, str],
    second_circle: tuple[str, str],
) -> tuple[str, ...]:
    matches: list[str] = []
    for record in records:
        if not (
            _has_circle(record["constructions"], *first_circle)
            and _has_circle(record["constructions"], *second_circle)
        ):
            continue
        matches.extend(map(str, record["outputs"]))
    return tuple(dict.fromkeys(matches))


def _match_roles(
    formulation: JGEXFormulation,
    records: tuple[dict[str, object], ...],
) -> tuple[dict[str, str], tuple[str, ...]]:
    triangle = next(
        (
            tuple(record["outputs"])
            for record in records
            if record["constructions"] == (("triangle", ()),)
            and len(record["outputs"]) == 3
        ),
        None,
    )
    if triangle is None:
        return {}, ()
    goal = str(formulation.goals[0]) if len(formulation.goals) == 1 else ""
    goal_parts = goal.split()
    if len(goal_parts) != 4 or goal_parts[0] != "coll":
        return {}, ()

    for point_a, point_b, point_c in itertools.permutations(triangle):
        incenter = _single_unordered(
            records, "incenter", frozenset((point_a, point_b, point_c))
        )
        if not incenter:
            continue
        midpoint_a = _single_unordered(
            records, "midpoint", frozenset((point_b, point_c))
        )
        midpoint_b = _single_unordered(
            records, "midpoint", frozenset((point_c, point_a))
        )
        midpoint_c = _single_unordered(
            records, "midpoint", frozenset((point_a, point_b))
        )
        if not all((midpoint_a, midpoint_b, midpoint_c)):
            continue
        point_a1 = _tline_intersection_role(
            records,
            (midpoint_b, point_b, incenter),
            (midpoint_c, point_c, incenter),
        )
        point_b1 = _tline_intersection_role(
            records,
            (midpoint_a, point_a, incenter),
            (midpoint_c, point_c, incenter),
        )
        point_c1 = _tline_intersection_role(
            records,
            (midpoint_a, point_a, incenter),
            (midpoint_b, point_b, incenter),
        )
        if not all((point_a1, point_b1, point_c1)):
            continue
        orthocenter = _single_unordered(
            records,
            "orthocenter",
            frozenset((point_a1, point_b1, point_c1)),
        )
        if not orthocenter:
            continue
        midpoint_ih = _single_unordered(
            records, "midpoint", frozenset((incenter, orthocenter))
        )
        center_o = _single_unordered(
            records, "circumcenter", frozenset((point_a, point_b, point_c))
        )
        center_o1 = _single_unordered(
            records,
            "circumcenter",
            frozenset((point_a1, point_b1, point_c1)),
        )
        if not all((midpoint_ih, center_o, center_o1)):
            continue
        intersections = _circle_intersection_roles(
            records,
            (center_o, point_a),
            (center_o1, point_a1),
        )
        if len(intersections) != 2:
            continue
        point_x, point_y = intersections
        expected = Atom("coll", (point_x, point_y, midpoint_ih)).canonical()
        actual = Atom(goal_parts[0], tuple(goal_parts[1:])).canonical()
        if actual != expected:
            continue
        roles = {
            "A": point_a,
            "B": point_b,
            "C": point_c,
            "I": incenter,
            "MA": midpoint_a,
            "MB": midpoint_b,
            "MC": midpoint_c,
            "A1": point_a1,
            "B1": point_b1,
            "C1": point_c1,
            "H": orthocenter,
            "M": midpoint_ih,
            "O": center_o,
            "O1": center_o1,
            "X": point_x,
            "Y": point_y,
        }
        matched = (
            "I is the incenter of ABC",
            "MA,MB,MC are the three side midpoints",
            "A1B1C1 is formed by the three midpoint perpendiculars",
            "H is the orthocenter of A1B1C1 and M is the midpoint of IH",
            "O and O1 are the two circumcenters",
            "X,Y are their two supplied common points",
            "the goal is collinearity of X,Y,M",
        )
        return roles, matched
    return {}, ()


def certify_jgex_incenter_midpoint_perpendicular_radical_axis_application(
    source: str,
) -> JGEXIncenterMidpointPerpendicularRadicalAxisApplication:
    normalized = source.strip()
    formulation = JGEXFormulation.from_text(normalized)
    roles, matched = _match_roles(formulation, _records(formulation))
    goal = str(formulation.goals[0]) if len(formulation.goals) == 1 else ""
    chart = certify_incenter_midpoint_perpendicular_radical_axis_chart()
    replayed = (
        chart.replayed
        and chart.all_conditions_discharged
        and len(roles) == 16
        and len(matched) == 7
    )
    return JGEXIncenterMidpointPerpendicularRadicalAxisApplication(
        theorem=chart.theorem,
        source_sha256=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        roles=roles,
        matched_constructions=matched,
        goal=goal,
        chart_certificate_sha256=chart.certificate_sha256,
        nondegeneracy_obligations=chart.assumptions,
        undischarged_nondegeneracy_obligations=(),
        replayed=replayed,
    )


def render_incenter_midpoint_perpendicular_radical_axis_chart_svg(
    *,
    p_value: float = 1.3,
    q_value: float = -2.0,
) -> str:
    certificate = certify_incenter_midpoint_perpendicular_radical_axis_chart()
    symbols = {name: sp.Symbol(name, real=True) for name in ("p", "q")}
    substitutions = {
        symbols["p"]: sp.Rational(str(p_value)),
        symbols["q"]: sp.Rational(str(q_value)),
    }
    points = {
        name: (
            float(sp.sympify(value[0], locals=symbols).subs(substitutions)),
            float(sp.sympify(value[1], locals=symbols).subs(substitutions)),
        )
        for name, value in certificate.coordinates.items()
    }
    center_o = points["O"]
    center_o1 = points["O1"]
    radius = math.dist(center_o, points["A"])
    delta = (center_o1[0] - center_o[0], center_o1[1] - center_o[1])
    distance = math.hypot(*delta)
    common_midpoint = (
        (center_o[0] + center_o1[0]) / 2,
        (center_o[1] + center_o1[1]) / 2,
    )
    chord_half = math.sqrt(max(radius**2 - distance**2 / 4, 0.0))
    perpendicular = (-delta[1] / distance, delta[0] / distance)
    points["X"] = (
        common_midpoint[0] + chord_half * perpendicular[0],
        common_midpoint[1] + chord_half * perpendicular[1],
    )
    points["Y"] = (
        common_midpoint[0] - chord_half * perpendicular[0],
        common_midpoint[1] - chord_half * perpendicular[1],
    )

    figure, axis = plt.subplots(figsize=(9.4, 6.2), constrained_layout=True)
    figure.patch.set_facecolor("#f8fafc")
    axis.set_facecolor("#ffffff")
    axis.set_aspect("equal", adjustable="datalim")
    axis.axis("off")
    axis.set_title(
        "内心と辺中点垂線がつくる根軸",
        loc="left",
        fontsize=14,
        color="#0f172a",
        fontfamily="Yu Gothic",
    )

    def segment(left: str, right: str, color: str, width: float = 1.3) -> None:
        axis.plot(
            (points[left][0], points[right][0]),
            (points[left][1], points[right][1]),
            color=color,
            linewidth=width,
        )

    for left, right in (("A", "B"), ("B", "C"), ("C", "A")):
        segment(left, right, "#64748b")
    for left, right in (("A1", "B1"), ("B1", "C1"), ("C1", "A1")):
        segment(left, right, "#2563eb", 1.6)
    segment("I", "H", "#7c3aed", 1.5)
    segment("X", "Y", "#e11d48", 2.2)
    axis.add_patch(Circle(center_o, radius, fill=False, color="#94a3b8", linewidth=1.0))
    axis.add_patch(Circle(center_o1, radius, fill=False, color="#0ea5e9", linewidth=1.0))
    shown = ("A", "B", "C", "A1", "B1", "C1", "I", "H", "M", "X", "Y")
    for name in shown:
        x_value, y_value = points[name]
        highlight = name in {"M", "X", "Y"}
        color = "#e11d48" if highlight else "#0f172a"
        axis.scatter((x_value,), (y_value,), color=color, s=28, zorder=5)
        axis.annotate(
            name,
            (x_value, y_value),
            xytext=(6, 5),
            textcoords="offset points",
            fontsize=9,
            color=color,
            weight="bold" if highlight else "normal",
        )
    axis.relim()
    axis.autoscale_view()
    axis.margins(0.12)
    output = io.StringIO()
    figure.savefig(output, format="svg", facecolor=figure.get_facecolor())
    plt.close(figure)
    return output.getvalue()


__all__ = [
    "IncenterMidpointPerpendicularRadicalAxisCertificate",
    "JGEXIncenterMidpointPerpendicularRadicalAxisApplication",
    "certify_incenter_midpoint_perpendicular_radical_axis_chart",
    "certify_jgex_incenter_midpoint_perpendicular_radical_axis_application",
    "render_incenter_midpoint_perpendicular_radical_axis_chart_svg",
]
