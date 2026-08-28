"""Exact chart for crossed altitude lines and a right-angle pedal point."""

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
class CrossAltitudesRightAnglePedalCertificate:
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
                "# 交差高度線・直角・垂足円チャート",
                "",
                "## 定理",
                "",
                (
                    "$P,Q$ が三角形 $ABC$ の $B,C$ からの高度線上にあり、"
                    "$AP\\perp AQ$ とする。$F$ を $A$ から $PQ$ への垂足と"
                    "すると、$F$ は直径 $BC$ の円上にあり、$BF\\perp CF$。"
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
class JGEXCrossAltitudesRightAnglePedalApplication:
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


@lru_cache(maxsize=1)
def certify_cross_altitudes_right_angle_pedal_chart(
) -> CrossAltitudesRightAnglePedalCertificate:
    b, u, v, t = sp.symbols("b u v t", real=True, nonzero=True)
    ac_norm2 = u**2 + v**2
    point_a = _point(0, 0)
    point_b = _point(b, 0)
    point_c = _point(u, v)
    point_b1 = _point(b * u**2 / ac_norm2, b * u * v / ac_norm2)
    point_c1 = _point(u, 0)
    point_p = _point(b - t * v, t * u)
    point_q = _point(u, v - b / t)
    point_f = _point(
        (b + t**2 * u - t * v) / (t**2 + 1),
        t * (-b + t * v + u) / (t**2 + 1),
    ).applyfunc(sp.cancel)

    residuals = {
        "B1_on_AC": _cross(point_b1 - point_a, point_c - point_a),
        "BB1_perpendicular_AC": (point_b1 - point_b).dot(point_c - point_a),
        "C1_on_AB": _cross(point_c1 - point_a, point_b - point_a),
        "CC1_perpendicular_AB": (point_c1 - point_c).dot(point_b - point_a),
        "P_on_BB1": _cross(point_p - point_b, point_b1 - point_b),
        "Q_on_CC1": _cross(point_q - point_c, point_c1 - point_c),
        "AP_perpendicular_AQ": point_p.dot(point_q),
        "F_on_PQ": _cross(point_f - point_p, point_q - point_p),
        "AF_perpendicular_PQ": point_f.dot(point_q - point_p),
        "goal_BF_perpendicular_CF": (point_f - point_b).dot(point_f - point_c),
    }
    rendered = {name: _canonical(value) for name, value in residuals.items()}
    replayed = all(value == "0" for value in rendered.values())
    coordinates = {
        name: (_canonical(value[0]), _canonical(value[1]))
        for name, value in {
            "A": point_a,
            "B": point_b,
            "C": point_c,
            "B1": point_b1,
            "C1": point_c1,
            "P": point_p,
            "Q": point_q,
            "F": point_f,
        }.items()
    }
    discharged_conditions = {
        "b*v != 0": "The accepted triangle ABC is nondegenerate.",
        "t != 0": "The constructed finite point Q exists.",
        "t^2+1 != 0": "The denominator is positive over R.",
        "P != Q": "The accepted foot construction F=foot(A,PQ) defines line PQ.",
    }
    payload = {
        "theorem": "cross-altitudes-right-angle-pedal-on-diameter-circle",
        "normalization": (
            "A=(0,0), B=(b,0), C=(u,v); P=B+t(-v,u), and AP dot AQ=0 "
            "determines Q=(u,v-b/t)"
        ),
        "parameter_domain": (
            "b,u,v,t are real",
            "b*v*t != 0",
        ),
        "construction_domain_conditions": (
            "P lies on the altitude line through B",
            "Q lies on the altitude line through C and AP is perpendicular to AQ",
            "F is the projection of A on PQ",
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
    return CrossAltitudesRightAnglePedalCertificate(
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


def _foot(
    records: tuple[dict[str, object], ...],
    point: str,
    line: frozenset[str],
) -> str | None:
    for record in records:
        if len(record["outputs"]) != 1 or len(record["constructions"]) != 1:
            continue
        name, args = record["constructions"][0]
        if name == "foot" and len(args) == 3 and args[0] == point:
            if frozenset(args[1:]) == line:
                return record["outputs"][0]
    return None


def _line_and_perpendicular_role(
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
        point_b1 = _foot(records, point_b, frozenset((point_a, point_c)))
        point_c1 = _foot(records, point_c, frozenset((point_a, point_b)))
        if not point_b1 or not point_c1:
            continue
        point_p = _single_unordered(
            records, "on_line", frozenset((point_b, point_b1))
        )
        if not point_p:
            continue
        point_q = _line_and_perpendicular_role(
            records,
            frozenset((point_c, point_c1)),
            point_a,
            frozenset((point_a, point_p)),
        )
        if not point_q:
            continue
        point_f = _foot(records, point_a, frozenset((point_p, point_q)))
        if not point_f:
            continue
        goal = formulation.goals[0]
        expected = Atom("perp", (point_b, point_f, point_f, point_c)).canonical()
        actual = Atom(goal.predicate, goal.args).canonical()
        if actual != expected:
            continue
        roles = {
            "A": point_a,
            "B": point_b,
            "C": point_c,
            "B1": point_b1,
            "C1": point_c1,
            "P": point_p,
            "Q": point_q,
            "F": point_f,
        }
        matched = (
            "BB1 and CC1 are the two altitude lines",
            "P lies on BB1",
            "Q lies on CC1 and AQ is perpendicular to AP",
            "F is the projection of A on PQ",
            "the goal is BF perpendicular to CF",
        )
        return roles, matched
    return {}, ()


def certify_jgex_cross_altitudes_right_angle_pedal_application(
    source: str,
) -> JGEXCrossAltitudesRightAnglePedalApplication:
    normalized = source.strip()
    formulation = JGEXFormulation.from_text(normalized)
    roles, matched = _match_roles(formulation, _records(formulation))
    goal = str(formulation.goals[0]) if len(formulation.goals) == 1 else ""
    chart = certify_cross_altitudes_right_angle_pedal_chart()
    replayed = (
        chart.replayed
        and chart.all_conditions_discharged
        and len(roles) == 8
        and len(matched) == 5
    )
    return JGEXCrossAltitudesRightAnglePedalApplication(
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


def render_cross_altitudes_right_angle_pedal_chart_svg(
    *, b_value: float = 1.4, u_value: float = 0.55, v_value: float = 1.35, t_value: float = 0.8
) -> str:
    certificate = certify_cross_altitudes_right_angle_pedal_chart()
    symbols = {name: sp.Symbol(name, real=True) for name in ("b", "u", "v", "t")}
    substitutions = {
        symbols["b"]: sp.Rational(str(b_value)),
        symbols["u"]: sp.Rational(str(u_value)),
        symbols["v"]: sp.Rational(str(v_value)),
        symbols["t"]: sp.Rational(str(t_value)),
    }
    points = {
        name: (
            float(sp.sympify(value[0], locals=symbols).subs(substitutions)),
            float(sp.sympify(value[1], locals=symbols).subs(substitutions)),
        )
        for name, value in certificate.coordinates.items()
    }
    midpoint = (
        (points["B"][0] + points["C"][0]) / 2,
        (points["B"][1] + points["C"][1]) / 2,
    )
    radius = (
        (points["B"][0] - points["C"][0]) ** 2
        + (points["B"][1] - points["C"][1]) ** 2
    ) ** 0.5 / 2

    figure, axis = plt.subplots(figsize=(8.4, 6.0), constrained_layout=True)
    figure.patch.set_facecolor("#f8fafc")
    axis.set_facecolor("#ffffff")
    axis.set_aspect("equal", adjustable="datalim")
    axis.axis("off")
    axis.set_title(
        "直角条件が垂足を直径円へ送る",
        loc="left",
        fontsize=14,
        color="#0f172a",
        fontfamily="Yu Gothic",
    )
    axis.add_patch(Circle(midpoint, radius, fill=False, color="#e11d48", linewidth=1.5))
    for left, right, color, width in (
        ("A", "B", "#64748b", 1.2),
        ("A", "C", "#64748b", 1.2),
        ("B", "C", "#64748b", 1.2),
        ("B", "P", "#7c3aed", 1.2),
        ("C", "Q", "#0891b2", 1.2),
        ("P", "Q", "#0f172a", 1.5),
        ("A", "F", "#e11d48", 1.8),
        ("B", "F", "#e11d48", 1.5),
        ("C", "F", "#e11d48", 1.5),
    ):
        axis.plot(
            (points[left][0], points[right][0]),
            (points[left][1], points[right][1]),
            color=color,
            linewidth=width,
        )
    for name, (x_coord, y_coord) in points.items():
        highlight = name == "F"
        color = "#e11d48" if highlight else "#0f172a"
        axis.scatter((x_coord,), (y_coord,), color=color, s=28, zorder=5)
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
    axis.margins(0.16)
    output = io.StringIO()
    figure.savefig(output, format="svg", bbox_inches="tight")
    plt.close(figure)
    return output.getvalue()


__all__ = [
    "CrossAltitudesRightAnglePedalCertificate",
    "JGEXCrossAltitudesRightAnglePedalApplication",
    "certify_cross_altitudes_right_angle_pedal_chart",
    "certify_jgex_cross_altitudes_right_angle_pedal_application",
    "render_cross_altitudes_right_angle_pedal_chart_svg",
]
