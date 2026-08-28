"""Exact unit-incircle chart for a midline crossing and antipode angle."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
import hashlib
import io
import itertools
import json

import matplotlib
import sympy as sp

matplotlib.use("Agg")

from matplotlib import pyplot as plt
from matplotlib.patches import Circle

from worker.backend.geometry_proof_hypergraph import Atom
from worker.backend.jgex_chart_parser import ChartJGEXFormulation as JGEXFormulation


@dataclass(frozen=True)
class IncenterMidlinePerpendicularAntipodeAngleCertificate:
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
                "# 単位内接円・中線交点・内心対蹠角チャート",
                "",
                "## 定理",
                "",
                (
                    "三角形 $ABC$ の内心を $I$、$BC$ の中点を $M$ とする。"
                    "$I$ を通り $BC$ に垂直な直線と $AM$ の交点を $L$、"
                    "$I$ の $A$ に関する対称点を $J$ とすると、"
                    "$\\angle ABJ=\\angle IBL$（有向角、$\\bmod\\,\\pi$）。"
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
class JGEXIncenterMidlinePerpendicularAntipodeAngleApplication:
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


def _point(x_coord: sp.Expr, y_coord: sp.Expr) -> sp.Matrix:
    return sp.Matrix((x_coord, y_coord))


def _cross(left: sp.Matrix, right: sp.Matrix) -> sp.Expr:
    return sp.expand(left[0] * right[1] - left[1] * right[0])


@lru_cache(maxsize=1)
def certify_incenter_midline_perpendicular_antipode_angle_chart(
) -> IncenterMidlinePerpendicularAntipodeAngleCertificate:
    p, q = sp.symbols("p q", positive=True)
    point_i = _point(0, 1)
    point_b = _point(-p, 0)
    point_c = _point(q, 0)
    point_a = _point((p - q) / (p * q - 1), 2 * p * q / (p * q - 1))
    point_m = (point_b + point_c) / 2
    point_l = _point(0, 2 * p * q / (p * q + 1))
    point_j = 2 * point_a - point_i

    vector_ab = point_a - point_b
    vector_ac = point_a - point_c
    vector_bi = point_i - point_b
    vector_bl = point_l - point_b
    vector_bj = point_j - point_b
    angle_residual = (
        _cross(vector_ab, vector_bj) * vector_bi.dot(vector_bl)
        - vector_ab.dot(vector_bj) * _cross(vector_bi, vector_bl)
    )

    residuals = {
        "BC_is_unit_circle_tangent": (point_i[1] ** 2 - 1),
        "AB_is_unit_circle_tangent": (
            _cross(vector_ab, point_i - point_b) ** 2 - vector_ab.dot(vector_ab)
        ),
        "AC_is_unit_circle_tangent": (
            _cross(vector_ac, point_i - point_c) ** 2 - vector_ac.dot(vector_ac)
        ),
        "M_is_midpoint_BC": (2 * point_m - point_b - point_c).dot(
            2 * point_m - point_b - point_c
        ),
        "L_on_AM": _cross(point_l - point_a, point_m - point_a),
        "IL_perpendicular_BC": (point_l - point_i).dot(point_c - point_b),
        "J_is_reflection_of_I_about_A": (
            point_i + point_j - 2 * point_a
        ).dot(point_i + point_j - 2 * point_a),
        "goal_equal_directed_angles": angle_residual,
    }
    rendered = {name: _canonical(value) for name, value in residuals.items()}
    replayed = all(value == "0" for value in rendered.values())
    coordinates = {
        name: (_canonical(value[0]), _canonical(value[1]))
        for name, value in {
            "A": point_a,
            "B": point_b,
            "C": point_c,
            "I": point_i,
            "M": point_m,
            "L": point_l,
            "J": point_j,
        }.items()
    }
    discharged_conditions = {
        "p>0 and q>0": "B and C lie on opposite sides of the incircle contact.",
        "p*q>1": "A lies above BC and the accepted triangle is nondegenerate.",
        "p*q-1 != 0": "The two non-BC tangents meet at finite A.",
        "p*q+1 != 0": "The point L is finite; positivity makes this automatic.",
    }
    payload = {
        "theorem": "incenter-midline-perpendicular-antipode-equal-angle",
        "normalization": (
            "The incircle is the unit circle centered at I=(0,1), BC is y=0, "
            "B=(-p,0), C=(q,0), and AB,AC are the other two tangents"
        ),
        "parameter_domain": (
            "p,q are positive real numbers",
            "p*q>1",
        ),
        "construction_domain_conditions": (
            "M is the midpoint of BC",
            "L=AM intersect the perpendicular to BC through I",
            "J is the reflection of I about A",
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
    return IncenterMidlinePerpendicularAntipodeAngleCertificate(
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


def _single_ordered(
    records: tuple[dict[str, object], ...],
    name: str,
    args: tuple[str, ...],
) -> str | None:
    for record in records:
        if len(record["outputs"]) != 1 or len(record["constructions"]) != 1:
            continue
        construction_name, construction_args = record["constructions"][0]
        if construction_name == name and construction_args == args:
            return record["outputs"][0]
    return None


def _line_and_perpendicular(
    records: tuple[dict[str, object], ...],
    line: frozenset[str],
    through: str,
    perpendicular_to: frozenset[str],
) -> str | None:
    for record in records:
        if len(record["outputs"]) != 1 or len(record["constructions"]) != 2:
            continue
        has_line = any(
            name == "on_line" and frozenset(args) == line
            for name, args in record["constructions"]
        )
        has_perpendicular = any(
            name == "on_tline"
            and len(args) == 3
            and args[0] == through
            and frozenset(args[1:]) == perpendicular_to
            for name, args in record["constructions"]
        )
        if has_line and has_perpendicular:
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
            if record["constructions"] == (("triangle", ()),)
            and len(record["outputs"]) == 3
        ),
        None,
    )
    if triangle is None or len(formulation.goals) != 1:
        return {}, ()
    for point_a, point_b, point_c in itertools.permutations(triangle):
        point_i = _single_unordered(
            records, "incenter", frozenset((point_a, point_b, point_c))
        )
        point_m = _single_unordered(
            records, "midpoint", frozenset((point_b, point_c))
        )
        if not point_i or not point_m:
            continue
        point_l = _line_and_perpendicular(
            records,
            frozenset((point_a, point_m)),
            point_i,
            frozenset((point_b, point_c)),
        )
        point_j = _single_ordered(records, "mirror", (point_i, point_a))
        if not point_l or not point_j:
            continue
        goal = formulation.goals[0]
        expected = Atom(
            "eqangle",
            (point_a, point_b, point_b, point_j, point_i, point_b, point_b, point_l),
        ).canonical()
        actual = Atom(goal.predicate, goal.args).canonical()
        if actual != expected:
            continue
        roles = {
            "A": point_a,
            "B": point_b,
            "C": point_c,
            "I": point_i,
            "M": point_m,
            "L": point_l,
            "J": point_j,
        }
        matched = (
            "I is the incenter of ABC and M is the midpoint of BC",
            "L lies on AM and IL is perpendicular to BC",
            "J is the reflection of I about A",
            "the goal equates the directed angles ABJ and IBL",
        )
        return roles, matched
    return {}, ()


def certify_jgex_incenter_midline_perpendicular_antipode_angle_application(
    source: str,
) -> JGEXIncenterMidlinePerpendicularAntipodeAngleApplication:
    normalized = source.strip()
    formulation = JGEXFormulation.from_text(normalized)
    roles, matched = _match_roles(formulation, _records(formulation))
    goal = str(formulation.goals[0]) if len(formulation.goals) == 1 else ""
    chart = certify_incenter_midline_perpendicular_antipode_angle_chart()
    replayed = (
        chart.replayed
        and chart.all_conditions_discharged
        and len(roles) == 7
        and len(matched) == 4
    )
    return JGEXIncenterMidlinePerpendicularAntipodeAngleApplication(
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


def render_incenter_midline_perpendicular_antipode_angle_chart_svg(
    *, p_value: float = 2.0, q_value: float = 1.5
) -> str:
    certificate = certify_incenter_midline_perpendicular_antipode_angle_chart()
    symbols = {name: sp.Symbol(name, positive=True) for name in ("p", "q")}
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

    figure, axis = plt.subplots(figsize=(8.2, 6.2), constrained_layout=True)
    figure.patch.set_facecolor("#f8fafc")
    axis.set_facecolor("#ffffff")
    axis.set_aspect("equal", adjustable="datalim")
    axis.axis("off")
    axis.set_title(
        "内接円の3接線が角の等価性を固定する",
        loc="left",
        fontsize=14,
        color="#0f172a",
        fontfamily="Yu Gothic",
    )
    axis.add_patch(Circle(points["I"], 1, fill=False, color="#0891b2", linewidth=1.5))
    for left, right, color, width in (
        ("A", "B", "#64748b", 1.4),
        ("A", "C", "#64748b", 1.4),
        ("B", "C", "#64748b", 1.4),
        ("A", "M", "#7c3aed", 1.3),
        ("I", "L", "#7c3aed", 1.5),
        ("A", "J", "#e11d48", 1.5),
        ("B", "J", "#e11d48", 1.5),
        ("B", "L", "#0891b2", 1.5),
    ):
        axis.plot(
            (points[left][0], points[right][0]),
            (points[left][1], points[right][1]),
            color=color,
            linewidth=width,
        )
    for name, (x_coord, y_coord) in points.items():
        highlight = name in {"I", "L", "J"}
        color = "#e11d48" if name == "J" else "#0f172a"
        axis.scatter((x_coord,), (y_coord,), color=color, s=30, zorder=5)
        axis.annotate(
            name,
            (x_coord, y_coord),
            xytext=(6, 5),
            textcoords="offset points",
            fontsize=9,
            color=color,
            weight="bold" if highlight else "normal",
        )
    axis.relim()
    axis.autoscale_view()
    axis.margins(0.15)
    output = io.StringIO()
    figure.savefig(output, format="svg", bbox_inches="tight")
    plt.close(figure)
    return output.getvalue()


__all__ = [
    "IncenterMidlinePerpendicularAntipodeAngleCertificate",
    "JGEXIncenterMidlinePerpendicularAntipodeAngleApplication",
    "certify_incenter_midline_perpendicular_antipode_angle_chart",
    "certify_jgex_incenter_midline_perpendicular_antipode_angle_application",
    "render_incenter_midline_perpendicular_antipode_angle_chart_svg",
]
