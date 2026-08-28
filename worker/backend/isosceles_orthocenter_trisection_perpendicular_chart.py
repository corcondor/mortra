"""Exact affine-metric chart for an isosceles trisection theorem."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
import hashlib
import io
import json

import matplotlib
import sympy as sp

matplotlib.use("Agg")

from matplotlib import pyplot as plt

from worker.backend.geometry_proof_hypergraph import Atom
from worker.backend.jgex_chart_parser import ChartJGEXFormulation as JGEXFormulation


@dataclass(frozen=True)
class IsoscelesOrthocenterTrisectionPerpendicularCertificate:
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
                "# 二等辺三角形・垂心・三等分点の直交チャート",
                "",
                "## 定理",
                "",
                (
                    "$AB=AC$ の三角形 $ABC$ で、$H$ を垂心、$E$ を $AC$ の"
                    "中点とする。$D,F$ が $CB$ をこの順に三等分するとき、"
                    "$BE\\perp HD$ である。"
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
class JGEXIsoscelesOrthocenterTrisectionPerpendicularApplication:
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


@lru_cache(maxsize=1)
def certify_isosceles_orthocenter_trisection_perpendicular_chart(
) -> IsoscelesOrthocenterTrisectionPerpendicularCertificate:
    t = sp.symbols("t", real=True)
    point_a = _point(0, t)
    point_b = _point(-1, 0)
    point_c = _point(1, 0)
    point_h = _point(0, 1 / t)
    point_e = (point_a + point_c) / 2
    point_d = (2 * point_c + point_b) / 3
    point_f = (point_c + 2 * point_b) / 3

    residuals = {
        "isosceles_AB_AC": (
            (point_a - point_b).dot(point_a - point_b)
            - (point_a - point_c).dot(point_a - point_c)
        ),
        "H_altitude_A": (point_h - point_a).dot(point_c - point_b),
        "H_altitude_B": (point_h - point_b).dot(point_c - point_a),
        "H_altitude_C": (point_h - point_c).dot(point_b - point_a),
        "E_midpoint_AC_x": 2 * point_e[0] - point_a[0] - point_c[0],
        "E_midpoint_AC_y": 2 * point_e[1] - point_a[1] - point_c[1],
        "D_first_trisection_x": 3 * point_d[0] - 2 * point_c[0] - point_b[0],
        "D_first_trisection_y": 3 * point_d[1] - 2 * point_c[1] - point_b[1],
        "F_second_trisection_x": 3 * point_f[0] - point_c[0] - 2 * point_b[0],
        "F_second_trisection_y": 3 * point_f[1] - point_c[1] - 2 * point_b[1],
        "goal_BE_perpendicular_HD": (point_e - point_b).dot(point_d - point_h),
    }
    rendered = {name: _canonical(value) for name, value in residuals.items()}
    replayed = all(value == "0" for value in rendered.values())
    coordinates = {
        name: (_canonical(value[0]), _canonical(value[1]))
        for name, value in {
            "A": point_a,
            "B": point_b,
            "C": point_c,
            "H": point_h,
            "E": point_e,
            "D": point_d,
            "F": point_f,
        }.items()
    }
    discharged_conditions = {
        "t != 0": (
            "The accepted isosceles triangle is nondegenerate; its normalized height "
            "therefore does not vanish."
        ),
        "D and F are ordered trisection points of CB": (
            "JGEX trisegment returns the first and second internal trisection points "
            "in the declared endpoint order."
        ),
    }
    payload = {
        "theorem": "isosceles-orthocenter-midpoint-trisection-perpendicular",
        "normalization": "B=(-1,0), C=(1,0), A=(0,t) with t nonzero",
        "parameter_domain": ("t is real and t != 0",),
        "construction_domain_conditions": (
            "H is the orthocenter and D,F are the ordered trisection points of CB",
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
    return IsoscelesOrthocenterTrisectionPerpendicularCertificate(
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


def _match_roles(
    formulation: JGEXFormulation,
    records: tuple[dict[str, object], ...],
) -> tuple[dict[str, str], tuple[str, ...]]:
    triangle = next(
        (
            tuple(record["outputs"])
            for record in records
            if record["constructions"] == (("iso_triangle", ()),)
            and len(record["outputs"]) == 3
        ),
        None,
    )
    if triangle is None:
        return {}, ()
    point_a, point_b, point_c = triangle
    point_h = _single_unordered(
        records, "orthocenter", frozenset((point_a, point_b, point_c))
    )
    point_e = _single_unordered(
        records, "midpoint", frozenset((point_a, point_c))
    )
    if not point_h or not point_e:
        return {}, ()
    trisegment = next(
        (
            record
            for record in records
            if len(record["outputs"]) == 2
            and record["constructions"] == (("trisegment", (point_c, point_b)),)
        ),
        None,
    )
    if trisegment is None:
        return {}, ()
    point_d, point_f = trisegment["outputs"]
    goal = str(formulation.goals[0]) if len(formulation.goals) == 1 else ""
    goal_parts = goal.split()
    if len(goal_parts) != 5:
        return {}, ()
    expected = Atom("perp", (point_b, point_e, point_h, point_d)).canonical()
    actual = Atom(goal_parts[0], tuple(goal_parts[1:])).canonical()
    if actual != expected:
        return {}, ()
    roles = {
        "A": point_a,
        "B": point_b,
        "C": point_c,
        "H": point_h,
        "E": point_e,
        "D": point_d,
        "F": point_f,
    }
    matched = (
        "ABC is isosceles with apex A",
        "H is the orthocenter of ABC",
        "E is the midpoint of AC",
        "D,F are the ordered trisection points of CB",
        "the goal is BE perpendicular to HD",
    )
    return roles, matched


def certify_jgex_isosceles_orthocenter_trisection_perpendicular_application(
    source: str,
) -> JGEXIsoscelesOrthocenterTrisectionPerpendicularApplication:
    normalized = source.strip()
    formulation = JGEXFormulation.from_text(normalized)
    roles, matched = _match_roles(formulation, _records(formulation))
    goal = str(formulation.goals[0]) if len(formulation.goals) == 1 else ""
    chart = certify_isosceles_orthocenter_trisection_perpendicular_chart()
    replayed = (
        chart.replayed
        and chart.all_conditions_discharged
        and len(roles) == 7
        and len(matched) == 5
    )
    return JGEXIsoscelesOrthocenterTrisectionPerpendicularApplication(
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


def render_isosceles_orthocenter_trisection_perpendicular_chart_svg(
    *, t_value: float = 1.7
) -> str:
    certificate = certify_isosceles_orthocenter_trisection_perpendicular_chart()
    symbol = sp.Symbol("t", real=True)
    points = {
        name: (
            float(sp.sympify(value[0], locals={"t": symbol}).subs(symbol, t_value)),
            float(sp.sympify(value[1], locals={"t": symbol}).subs(symbol, t_value)),
        )
        for name, value in certificate.coordinates.items()
    }
    figure, axis = plt.subplots(figsize=(8.8, 5.8), constrained_layout=True)
    figure.patch.set_facecolor("#f8fafc")
    axis.set_facecolor("#ffffff")
    axis.set_aspect("equal", adjustable="datalim")
    axis.axis("off")
    axis.set_title(
        "二等辺三角形の中点と三等分点",
        loc="left",
        fontsize=14,
        color="#0f172a",
        fontfamily="Yu Gothic",
    )

    def segment(left: str, right: str, color: str, width: float = 1.4) -> None:
        axis.plot(
            (points[left][0], points[right][0]),
            (points[left][1], points[right][1]),
            color=color,
            linewidth=width,
        )

    for left, right in (("A", "B"), ("B", "C"), ("C", "A")):
        segment(left, right, "#64748b")
    segment("B", "E", "#2563eb", 2.0)
    segment("H", "D", "#e11d48", 2.0)
    for name, (x_value, y_value) in points.items():
        highlight = name in {"B", "E", "H", "D"}
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
    axis.margins(0.2)
    output = io.StringIO()
    figure.savefig(output, format="svg", facecolor=figure.get_facecolor())
    plt.close(figure)
    return output.getvalue()


__all__ = [
    "IsoscelesOrthocenterTrisectionPerpendicularCertificate",
    "JGEXIsoscelesOrthocenterTrisectionPerpendicularApplication",
    "certify_isosceles_orthocenter_trisection_perpendicular_chart",
    "certify_jgex_isosceles_orthocenter_trisection_perpendicular_application",
    "render_isosceles_orthocenter_trisection_perpendicular_chart_svg",
]
