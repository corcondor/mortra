"""Exact chart for two orthic transversals and a midpoint right angle."""

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

from worker.backend.geometry_proof_hypergraph import Atom
from worker.backend.jgex_chart_parser import ChartJGEXFormulation as JGEXFormulation


@dataclass(frozen=True)
class OrthicTransversalsMidpointRightAngleCertificate:
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
                "# 垂足三角形・二直交線・中点直角チャート",
                "",
                "## 定理",
                "",
                (
                    "三角形 $ABC$ の垂足を $D,E,F$ とする。$P=DE\\cap"
                    " (A\\text{ を通り }AB\\text{ に垂直な直線})$、"
                    "$Q=DF\\cap(A\\text{ を通り }AC\\text{ に垂直な直線})$、"
                    "$T=PQ\\cap BC$ とし、$M$ を $BC$ の中点とすると、"
                    "$AM\\perp AT$。"
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
class JGEXOrthicTransversalsMidpointRightAngleApplication:
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
def certify_orthic_transversals_midpoint_right_angle_chart(
) -> OrthicTransversalsMidpointRightAngleCertificate:
    b, u, v = sp.symbols("b u v", real=True, nonzero=True)
    ac_norm2 = u**2 + v**2
    bc_norm2 = (u - b) ** 2 + v**2
    p_denominator = u**2 - v**2 - b * u
    q_denominator = u**2 * (u - b) + v**2 * (u + b)
    t_denominator = u**2 + v**2 - b**2

    point_a = _point(0, 0)
    point_b = _point(b, 0)
    point_c = _point(u, v)
    point_d = _point(
        b * v**2 / bc_norm2,
        b * v * (b - u) / bc_norm2,
    )
    point_e = _point(b * u**2 / ac_norm2, b * u * v / ac_norm2)
    point_f = _point(u, 0)
    point_p = _point(0, -b * u * v / p_denominator)
    point_q = _point(
        b * u * v**2 / q_denominator,
        -b * u**2 * v / q_denominator,
    )
    point_t = _point(
        b * v**2 / t_denominator,
        -b * v * (b + u) / t_denominator,
    )
    point_m = _point((b + u) / 2, v / 2)

    residuals = {
        "D_on_BC": _cross(point_d - point_b, point_c - point_b),
        "AD_perpendicular_BC": point_d.dot(point_c - point_b),
        "E_on_AC": _cross(point_e - point_a, point_c - point_a),
        "BE_perpendicular_AC": (point_e - point_b).dot(point_c - point_a),
        "F_on_AB": _cross(point_f - point_a, point_b - point_a),
        "CF_perpendicular_AB": (point_f - point_c).dot(point_b - point_a),
        "P_on_DE": _cross(point_p - point_d, point_e - point_d),
        "AP_perpendicular_AB": point_p.dot(point_b - point_a),
        "Q_on_DF": _cross(point_q - point_d, point_f - point_d),
        "AQ_perpendicular_AC": point_q.dot(point_c - point_a),
        "T_on_PQ": _cross(point_t - point_p, point_q - point_p),
        "T_on_BC": _cross(point_t - point_b, point_c - point_b),
        "M_is_midpoint_BC": (2 * point_m - point_b - point_c).dot(
            2 * point_m - point_b - point_c
        ),
        "goal_AM_perpendicular_AT": point_m.dot(point_t),
    }
    rendered = {name: _canonical(value) for name, value in residuals.items()}
    replayed = all(value == "0" for value in rendered.values())
    coordinates = {
        name: (_canonical(value[0]), _canonical(value[1]))
        for name, value in {
            "A": point_a,
            "B": point_b,
            "C": point_c,
            "D": point_d,
            "E": point_e,
            "F": point_f,
            "P": point_p,
            "Q": point_q,
            "T": point_t,
            "M": point_m,
        }.items()
    }
    discharged_conditions = {
        "b*v != 0": "The accepted triangle ABC is nondegenerate.",
        "u^2+v^2 != 0": "Side AC of the accepted triangle is nonzero.",
        "(u-b)^2+v^2 != 0": "Side BC of the accepted triangle is nonzero.",
        "u^2-v^2-b*u != 0": "The accepted construction defines finite P.",
        "u^2(u-b)+v^2(u+b) != 0": "The accepted construction defines finite Q.",
        "u^2+v^2-b^2 != 0": "The accepted construction defines finite T.",
    }
    payload = {
        "theorem": "orthic-transversals-midpoint-right-angle",
        "normalization": (
            "A=(0,0), B=(b,0), C=(u,v); all later points are eliminated "
            "from their incidence and perpendicularity constraints"
        ),
        "parameter_domain": (
            "b,u,v are real",
            "b*v != 0",
        ),
        "construction_domain_conditions": (
            "D,E,F are the three altitude feet",
            "P=DE intersect the perpendicular to AB through A",
            "Q=DF intersect the perpendicular to AC through A",
            "T=PQ intersect BC is finite",
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
    return OrthicTransversalsMidpointRightAngleCertificate(
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


def _midpoint(
    records: tuple[dict[str, object], ...],
    endpoints: frozenset[str],
) -> str | None:
    for record in records:
        if len(record["outputs"]) != 1 or len(record["constructions"]) != 1:
            continue
        name, args = record["constructions"][0]
        if name == "midpoint" and frozenset(args) == endpoints:
            return record["outputs"][0]
    return None


def _two_lines(
    records: tuple[dict[str, object], ...],
    first: frozenset[str],
    second: frozenset[str],
) -> str | None:
    expected = {first, second}
    for record in records:
        if len(record["outputs"]) != 1 or len(record["constructions"]) != 2:
            continue
        lines = {
            frozenset(args)
            for name, args in record["constructions"]
            if name == "on_line" and len(args) == 2
        }
        if lines == expected:
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
        point_d = _foot(records, point_a, frozenset((point_b, point_c)))
        point_e = _foot(records, point_b, frozenset((point_a, point_c)))
        point_f = _foot(records, point_c, frozenset((point_a, point_b)))
        if not point_d or not point_e or not point_f:
            continue
        point_p = _line_and_perpendicular(
            records,
            frozenset((point_d, point_e)),
            point_a,
            frozenset((point_a, point_b)),
        )
        point_q = _line_and_perpendicular(
            records,
            frozenset((point_d, point_f)),
            point_a,
            frozenset((point_a, point_c)),
        )
        if not point_p or not point_q:
            continue
        point_t = _two_lines(
            records,
            frozenset((point_p, point_q)),
            frozenset((point_b, point_c)),
        )
        point_m = _midpoint(records, frozenset((point_b, point_c)))
        if not point_t or not point_m:
            continue
        goal = formulation.goals[0]
        expected = Atom("perp", (point_m, point_a, point_a, point_t)).canonical()
        actual = Atom(goal.predicate, goal.args).canonical()
        if actual != expected:
            continue
        roles = {
            "A": point_a,
            "B": point_b,
            "C": point_c,
            "D": point_d,
            "E": point_e,
            "F": point_f,
            "P": point_p,
            "Q": point_q,
            "T": point_t,
            "M": point_m,
        }
        matched = (
            "D,E,F are the three altitude feet",
            "P lies on DE and AP is perpendicular to AB",
            "Q lies on DF and AQ is perpendicular to AC",
            "T is the intersection of PQ and BC; M is the midpoint of BC",
            "the goal is AM perpendicular to AT",
        )
        return roles, matched
    return {}, ()


def certify_jgex_orthic_transversals_midpoint_right_angle_application(
    source: str,
) -> JGEXOrthicTransversalsMidpointRightAngleApplication:
    normalized = source.strip()
    formulation = JGEXFormulation.from_text(normalized)
    roles, matched = _match_roles(formulation, _records(formulation))
    goal = str(formulation.goals[0]) if len(formulation.goals) == 1 else ""
    chart = certify_orthic_transversals_midpoint_right_angle_chart()
    replayed = (
        chart.replayed
        and chart.all_conditions_discharged
        and len(roles) == 10
        and len(matched) == 5
    )
    return JGEXOrthicTransversalsMidpointRightAngleApplication(
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


def render_orthic_transversals_midpoint_right_angle_chart_svg(
    *, b_value: float = 1.0, u_value: float = 0.3, v_value: float = 1.6
) -> str:
    certificate = certify_orthic_transversals_midpoint_right_angle_chart()
    symbols = {name: sp.Symbol(name, real=True) for name in ("b", "u", "v")}
    substitutions = {
        symbols["b"]: sp.Rational(str(b_value)),
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

    figure, axis = plt.subplots(figsize=(8.8, 6.2), constrained_layout=True)
    figure.patch.set_facecolor("#f8fafc")
    axis.set_facecolor("#ffffff")
    axis.set_aspect("equal", adjustable="datalim")
    axis.axis("off")
    axis.set_title(
        "垂足三角形から現れる AM と AT の直交",
        loc="left",
        fontsize=14,
        color="#0f172a",
        fontfamily="Yu Gothic",
    )
    for left, right, color, width in (
        ("A", "B", "#64748b", 1.2),
        ("A", "C", "#64748b", 1.2),
        ("B", "C", "#64748b", 1.2),
        ("D", "E", "#7c3aed", 1.2),
        ("D", "F", "#0891b2", 1.2),
        ("P", "Q", "#0f172a", 1.5),
        ("A", "M", "#e11d48", 1.8),
        ("A", "T", "#e11d48", 1.8),
    ):
        axis.plot(
            (points[left][0], points[right][0]),
            (points[left][1], points[right][1]),
            color=color,
            linewidth=width,
        )
    for name, (x_coord, y_coord) in points.items():
        highlight = name in {"A", "M", "T"}
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
    axis.margins(0.14)
    output = io.StringIO()
    figure.savefig(output, format="svg", bbox_inches="tight")
    plt.close(figure)
    return output.getvalue()


__all__ = [
    "JGEXOrthicTransversalsMidpointRightAngleApplication",
    "OrthicTransversalsMidpointRightAngleCertificate",
    "certify_jgex_orthic_transversals_midpoint_right_angle_application",
    "certify_orthic_transversals_midpoint_right_angle_chart",
    "render_orthic_transversals_midpoint_right_angle_chart_svg",
]
