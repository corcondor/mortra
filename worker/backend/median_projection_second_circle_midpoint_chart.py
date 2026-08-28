"""Exact chart for a median projection and known-root circle intersection."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
import hashlib
import io
import json
import re

import matplotlib
import sympy as sp

matplotlib.use("Agg")

from matplotlib import pyplot as plt
from matplotlib.patches import Circle

from worker.backend.geometry_proof_hypergraph import Atom
from worker.backend.jgex_chart_parser import ChartJGEXFormulation as JGEXFormulation


@dataclass(frozen=True)
class MedianProjectionSecondCircleMidpointCertificate:
    theorem: str
    normalization: str
    parameter_domain: tuple[str, ...]
    construction_domain_conditions: tuple[str, ...]
    discharged_conditions: dict[str, str]
    coordinates: dict[str, tuple[str, str]]
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
        residuals = "\n".join(
            f"- `{name}`: `{value}`" for name, value in self.replay_residuals.items()
        )
        discharged = "\n".join(
            f"- `{condition}`: {reason}"
            for condition, reason in self.discharged_conditions.items()
        )
        return "\n".join(
            (
                "# 中線射影・円の第2交点・中点チャート",
                "",
                "## 定理",
                "",
                (
                    "三角形 $ABC$ で $M$ を $BC$ の中点、$P$ を $C$ から"
                    "$AM$ への垂足とする。円 $(ABP)$ が直線 $BC$ と $B$ 以外で"
                    "$Q$ に交わり、$N$ が $AQ$ の中点なら、$NB=NC$ である。"
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
class JGEXMedianProjectionSecondCircleMidpointApplication:
    theorem: str
    source_sha256: str
    natural_statement: str
    natural_statement_sha256: str
    natural_semantic_atoms: tuple[str, ...]
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


def _cyclic_determinant(points: tuple[sp.Matrix, ...]) -> sp.Expr:
    matrix = sp.Matrix(
        [[point.dot(point), point[0], point[1], 1] for point in points]
    )
    return sp.expand(matrix.det())


@lru_cache(maxsize=1)
def certify_median_projection_second_circle_midpoint_chart(
) -> MedianProjectionSecondCircleMidpointCertificate:
    u, v = sp.symbols("u v", real=True)
    point_a = _point(u, v)
    point_b = _point(-1, 0)
    point_c = _point(1, 0)
    point_m = _point(0, 0)
    point_p = (u / (u**2 + v**2) * point_a).applyfunc(sp.cancel)
    point_q = _point(-u, 0)
    point_n = ((point_a + point_q) / 2).applyfunc(sp.cancel)

    residuals = {
        "M_midpoint_BC_x": 2 * point_m[0] - point_b[0] - point_c[0],
        "M_midpoint_BC_y": 2 * point_m[1] - point_b[1] - point_c[1],
        "P_on_AM": _cross(point_p - point_a, point_m - point_a),
        "CP_perpendicular_AM": (point_c - point_p).dot(point_a - point_m),
        "A_B_P_Q_cyclic": _cyclic_determinant(
            (point_a, point_b, point_p, point_q)
        ),
        "Q_on_BC": _cross(point_q - point_b, point_c - point_b),
        "N_midpoint_AQ_x": 2 * point_n[0] - point_a[0] - point_q[0],
        "N_midpoint_AQ_y": 2 * point_n[1] - point_a[1] - point_q[1],
        "goal_NB_equals_NC": (
            (point_n - point_b).dot(point_n - point_b)
            - (point_n - point_c).dot(point_n - point_c)
        ),
    }
    rendered = {name: _canonical(value) for name, value in residuals.items()}
    replayed = all(value == "0" for value in rendered.values())
    coordinates = {
        name: (_canonical(value[0]), _canonical(value[1]))
        for name, value in {
            "A": point_a,
            "B": point_b,
            "C": point_c,
            "M": point_m,
            "P": point_p,
            "Q": point_q,
            "N": point_n,
        }.items()
    }
    discharged_conditions = {
        "v != 0": "The accepted triangle ABC is nondegenerate.",
        "u^2+v^2 != 0": "The median line AM has nonzero direction.",
        "Q != B": (
            "The natural-language domain explicitly selects the distinct second "
            "intersection of line BC with circle ABP."
        ),
    }
    payload = {
        "theorem": "median-projection-second-circle-intersection-midpoint-equidistant",
        "normalization": "B=(-1,0), C=(1,0), M=(0,0), A=(u,v) with v nonzero",
        "parameter_domain": ("u and v are real", "v != 0"),
        "construction_domain_conditions": (
            "P is the projection of C on AM",
            "Q is the circle-line intersection distinct from the known root B",
        ),
        "discharged_conditions": discharged_conditions,
        "coordinates": coordinates,
        "replay_residuals": rendered,
        "replayed": replayed,
        "all_conditions_discharged": replayed,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return MedianProjectionSecondCircleMidpointCertificate(
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
    records: tuple[dict[str, object], ...], name: str, args: frozenset[str]
) -> str | None:
    for record in records:
        if len(record["outputs"]) != 1 or len(record["constructions"]) != 1:
            continue
        construction_name, construction_args = record["constructions"][0]
        if construction_name == name and frozenset(construction_args) == args:
            return record["outputs"][0]
    return None


def _foot_role(
    records: tuple[dict[str, object], ...],
    point: str,
    line: tuple[str, str],
) -> str | None:
    for record in records:
        if len(record["outputs"]) != 1 or len(record["constructions"]) != 1:
            continue
        name, args = record["constructions"][0]
        if (
            name == "foot"
            and len(args) == 3
            and args[0] == point
            and frozenset(args[1:]) == frozenset(line)
        ):
            return record["outputs"][0]
    return None


def _circle_line_role(
    records: tuple[dict[str, object], ...],
    line: tuple[str, str],
    circle_points: frozenset[str],
) -> str | None:
    for record in records:
        if len(record["outputs"]) != 1:
            continue
        has_line = any(
            name == "on_line" and frozenset(args) == frozenset(line)
            for name, args in record["constructions"]
        )
        has_circle = any(
            name == "on_circum" and frozenset(args) == circle_points
            for name, args in record["constructions"]
        )
        if has_line and has_circle:
            return record["outputs"][0]
    return None


def _asserts_distinct_second_intersection(statement: str) -> bool:
    lowered = re.sub(r"\s+", " ", statement.strip().lower())
    return bool(
        re.search(r"\btwo distinct points\b", lowered)
        or re.search(r"\bsecond (?:point|intersection)\b", lowered)
        or re.search(r"\bintersects? again\b", lowered)
    )


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
    point_a, point_b, point_c = triangle
    point_m = _single_unordered(
        records, "midpoint", frozenset((point_b, point_c))
    )
    if not point_m:
        return {}, ()
    point_p = _foot_role(records, point_c, (point_a, point_m))
    if not point_p:
        return {}, ()
    point_q = _circle_line_role(
        records,
        (point_b, point_c),
        frozenset((point_a, point_b, point_p)),
    )
    if not point_q:
        return {}, ()
    point_n = _single_unordered(
        records, "midpoint", frozenset((point_a, point_q))
    )
    if not point_n:
        return {}, ()
    goal = str(formulation.goals[0]) if len(formulation.goals) == 1 else ""
    goal_parts = goal.split()
    if len(goal_parts) != 5:
        return {}, ()
    expected = Atom("cong", (point_n, point_b, point_n, point_c)).canonical()
    actual = Atom(goal_parts[0], tuple(goal_parts[1:])).canonical()
    if actual != expected:
        return {}, ()
    roles = {
        "A": point_a,
        "B": point_b,
        "C": point_c,
        "M": point_m,
        "P": point_p,
        "Q": point_q,
        "N": point_n,
    }
    matched = (
        "M is the midpoint of BC",
        "P is the projection of C on AM",
        "Q lies on BC and the circumcircle of ABP",
        "N is the midpoint of AQ",
        "the goal is NB=NC",
    )
    return roles, matched


def certify_jgex_median_projection_second_circle_midpoint_application(
    source: str,
    natural_statement: str,
) -> JGEXMedianProjectionSecondCircleMidpointApplication:
    normalized = source.strip()
    normalized_natural = natural_statement.strip()
    formulation = JGEXFormulation.from_text(normalized)
    roles, matched = _match_roles(formulation, _records(formulation))
    distinct = _asserts_distinct_second_intersection(normalized_natural)
    goal = str(formulation.goals[0]) if len(formulation.goals) == 1 else ""
    chart = certify_median_projection_second_circle_midpoint_chart()
    replayed = (
        chart.replayed
        and chart.all_conditions_discharged
        and distinct
        and len(roles) == 7
        and len(matched) == 5
    )
    return JGEXMedianProjectionSecondCircleMidpointApplication(
        theorem=chart.theorem,
        source_sha256=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        natural_statement=normalized_natural,
        natural_statement_sha256=hashlib.sha256(
            normalized_natural.encode("utf-8")
        ).hexdigest(),
        natural_semantic_atoms=(
            "distinct(Q,B)",
            "second_intersection(Q,line(B,C),circumcircle(A,B,P))",
        )
        if distinct
        else (),
        roles=roles,
        matched_constructions=matched,
        goal=goal,
        chart_certificate_sha256=chart.certificate_sha256,
        nondegeneracy_obligations=chart.assumptions,
        undischarged_nondegeneracy_obligations=() if distinct else ("Q != B",),
        replayed=replayed,
    )


def render_median_projection_second_circle_midpoint_chart_svg(
    *, u_value: float = 0.35, v_value: float = 1.35
) -> str:
    certificate = certify_median_projection_second_circle_midpoint_chart()
    symbols = {name: sp.Symbol(name, real=True) for name in ("u", "v")}
    substitutions = {
        symbols["u"]: sp.Rational(str(u_value)),
        symbols["v"]: sp.Rational(str(v_value)),
    }
    points = {
        name: (
            float(sp.sympify(value[0], locals=symbols).subs(substitutions)),
            float(sp.sympify(value[1], locals=symbols).subs(substitutions)),
        )
        for name, value in certificate.coordinates.items()
    }
    a, b, p = points["A"], points["B"], points["P"]
    matrix = sp.Matrix(
        [
            [2 * (b[0] - a[0]), 2 * (b[1] - a[1])],
            [2 * (p[0] - a[0]), 2 * (p[1] - a[1])],
        ]
    )
    rhs = sp.Matrix(
        [b[0] ** 2 + b[1] ** 2 - a[0] ** 2 - a[1] ** 2,
         p[0] ** 2 + p[1] ** 2 - a[0] ** 2 - a[1] ** 2]
    )
    center_values = matrix.inv() * rhs
    center = (float(center_values[0]), float(center_values[1]))
    radius = ((a[0] - center[0]) ** 2 + (a[1] - center[1]) ** 2) ** 0.5

    figure, axis = plt.subplots(figsize=(8.8, 5.8), constrained_layout=True)
    figure.patch.set_facecolor("#f8fafc")
    axis.set_facecolor("#ffffff")
    axis.set_aspect("equal", adjustable="datalim")
    axis.axis("off")
    axis.set_title(
        "射影から円の第2交点を復元する",
        loc="left",
        fontsize=14,
        color="#0f172a",
        fontfamily="Yu Gothic",
    )
    for left, right, color, width in (
        ("A", "B", "#64748b", 1.3),
        ("B", "C", "#64748b", 1.3),
        ("C", "A", "#64748b", 1.3),
        ("A", "M", "#2563eb", 1.5),
        ("C", "P", "#7c3aed", 1.5),
        ("A", "Q", "#e11d48", 1.8),
    ):
        axis.plot(
            (points[left][0], points[right][0]),
            (points[left][1], points[right][1]),
            color=color,
            linewidth=width,
        )
    axis.add_patch(Circle(center, radius, fill=False, color="#0ea5e9", linewidth=1.2))
    for name, (x_value, y_value) in points.items():
        highlight = name in {"Q", "N"}
        color = "#e11d48" if highlight else "#0f172a"
        axis.scatter((x_value,), (y_value,), color=color, s=30, zorder=5)
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
    axis.margins(0.18)
    output = io.StringIO()
    figure.savefig(output, format="svg", facecolor=figure.get_facecolor())
    plt.close(figure)
    return output.getvalue()


__all__ = [
    "MedianProjectionSecondCircleMidpointCertificate",
    "JGEXMedianProjectionSecondCircleMidpointApplication",
    "certify_median_projection_second_circle_midpoint_chart",
    "certify_jgex_median_projection_second_circle_midpoint_application",
    "render_median_projection_second_circle_midpoint_chart_svg",
]
