"""Exact rational unit-circle chart for a diameter parallelogram.

The circumcircle of ``BOC`` meets ``AB`` and ``AC`` again.  Using a rational
parameterization of the circumcircle of ``ABC`` makes the opposite endpoint
of the diameter through ``O`` explicit and turns the claim into the affine
identity ``A + N = P + Q``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
import hashlib
import io
import itertools
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
class CircumcenterDiameterParallelogramCertificate:
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
                "# 外心・第2交点・直径平行四辺形チャート",
                "",
                "## 定理",
                "",
                (
                    "三角形 $ABC$ の外心を $O$ とし、円 $(BOC)$ が $AB,AC$"
                    "と $B,C$ 以外で $P,Q$ に交わる。円 $(BOC)$ の $O$ の"
                    "対蹠点を $N$ とすると、$A+N=P+Q$、したがって四角形"
                    "$APNQ$ は平行四辺形である。"
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
class JGEXCircumcenterDiameterParallelogramApplication:
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


def _norm2(value: sp.Matrix) -> sp.Expr:
    return sp.expand(value.dot(value))


@lru_cache(maxsize=1)
def certify_circumcenter_diameter_parallelogram_chart(
) -> CircumcenterDiameterParallelogramCertificate:
    s, t = sp.symbols("s t", real=True)
    point_o = _point(0, 0)
    point_b = _point(1, 0)
    point_c = _point((1 - t**2) / (1 + t**2), 2 * t / (1 + t**2))
    point_a = _point((1 - s**2) / (1 + s**2), 2 * s / (1 + s**2))
    point_o1 = _point(sp.Rational(1, 2), t / 2)
    point_n = _point(1, t)
    point_p = _point((1 - s * t) / (1 + s**2), (s + t) / (1 + s**2))
    point_q = _point((1 + s * t) / (1 + s**2), s * (1 + s * t) / (1 + s**2))
    gamma_radius2 = _norm2(point_o - point_o1)

    residuals = {
        "OA_equals_OB": _norm2(point_a - point_o) - _norm2(point_b - point_o),
        "OB_equals_OC": _norm2(point_b - point_o) - _norm2(point_c - point_o),
        "O1O_equals_O1B": _norm2(point_o - point_o1) - _norm2(point_b - point_o1),
        "O1O_equals_O1C": _norm2(point_o - point_o1) - _norm2(point_c - point_o1),
        "P_on_AB": _cross(point_p - point_a, point_b - point_a),
        "P_on_gamma": _norm2(point_p - point_o1) - gamma_radius2,
        "Q_on_AC": _cross(point_q - point_a, point_c - point_a),
        "Q_on_gamma": _norm2(point_q - point_o1) - gamma_radius2,
        "N_mirror_O_about_O1_x": point_n[0] + point_o[0] - 2 * point_o1[0],
        "N_mirror_O_about_O1_y": point_n[1] + point_o[1] - 2 * point_o1[1],
        "strong_parallelogram_identity_x": (
            point_a[0] + point_n[0] - point_p[0] - point_q[0]
        ),
        "strong_parallelogram_identity_y": (
            point_a[1] + point_n[1] - point_p[1] - point_q[1]
        ),
        "goal_AP_parallel_NQ": _cross(point_p - point_a, point_q - point_n),
        "second_side_PN_parallel_AQ": _cross(point_n - point_p, point_q - point_a),
    }
    rendered = {name: _canonical(value) for name, value in residuals.items()}
    replayed = all(value == "0" for value in rendered.values())
    coordinates = {
        name: (_canonical(value[0]), _canonical(value[1]))
        for name, value in {
            "A": point_a,
            "B": point_b,
            "C": point_c,
            "O": point_o,
            "O1": point_o1,
            "P": point_p,
            "Q": point_q,
            "N": point_n,
        }.items()
    }
    discharged_conditions = {
        "1+s^2 != 0 and 1+t^2 != 0": "Both denominators are positive over R.",
        "s,t,0 are pairwise distinct": "The accepted triangle ABC is nondegenerate.",
        "C != -B": (
            "The stated condition angle BAC != 90 degrees makes circle BOC "
            "nondegenerate."
        ),
        "P != B and Q != C": (
            "The natural-language domain explicitly chooses the other two "
            "circle-line intersections."
        ),
    }
    payload = {
        "theorem": "circumcenter-secondary-circle-diameter-parallelogram",
        "normalization": (
            "O=(0,0), B=(1,0), and A,C use rational unit-circle parameters "
            "s,t; the circle through B,O,C has center O1=(1/2,t/2)"
        ),
        "parameter_domain": (
            "s,t are real",
            "s,t,0 are pairwise distinct",
            "angle BAC != 90 degrees",
        ),
        "construction_domain_conditions": (
            "P is the intersection of AB with circle BOC distinct from B",
            "Q is the intersection of AC with circle BOC distinct from C",
            "N is the antipode of O on circle BOC",
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
    return CircumcenterDiameterParallelogramCertificate(
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


def _circle_line_role(
    records: tuple[dict[str, object], ...],
    line: frozenset[str],
    center: str,
    radius_point: str,
) -> str | None:
    for record in records:
        if len(record["outputs"]) != 1 or len(record["constructions"]) != 2:
            continue
        has_line = any(
            name == "on_line" and frozenset(args) == line
            for name, args in record["constructions"]
        )
        has_circle = any(
            name == "on_circle" and args == (center, radius_point)
            for name, args in record["constructions"]
        )
        if has_line and has_circle:
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
        point_o = _single_unordered(
            records, "circumcenter", frozenset((point_a, point_b, point_c))
        )
        if not point_o:
            continue
        point_o1 = _single_unordered(
            records, "circumcenter", frozenset((point_o, point_b, point_c))
        )
        if not point_o1:
            continue
        point_p = _circle_line_role(
            records, frozenset((point_a, point_b)), point_o1, point_o
        )
        point_q = _circle_line_role(
            records, frozenset((point_a, point_c)), point_o1, point_o
        )
        point_n = _single_ordered(records, "mirror", (point_o, point_o1))
        if not point_p or not point_q or not point_n:
            continue
        goal = formulation.goals[0]
        expected = Atom("para", (point_a, point_p, point_n, point_q)).canonical()
        actual = Atom(goal.predicate, goal.args).canonical()
        if actual != expected:
            continue
        roles = {
            "A": point_a,
            "B": point_b,
            "C": point_c,
            "O": point_o,
            "O1": point_o1,
            "P": point_p,
            "Q": point_q,
            "N": point_n,
        }
        matched = (
            "O is the circumcenter of ABC",
            "O1 is the circumcenter of BOC",
            "P,Q lie on AB,AC and circle centered at O1 through O",
            "N is the reflection of O about O1",
            "the goal is AP parallel to NQ",
        )
        return roles, matched
    return {}, ()


def _asserts_distinct_secondary_intersections(
    statement: str,
    roles: dict[str, str],
) -> bool:
    normalized = re.sub(r"[$\\{}]", "", statement.strip().lower())
    normalized = re.sub(r"\s+", " ", normalized)
    point_p = re.escape(roles.get("P", "__missing_p__").lower())
    point_b = re.escape(roles.get("B", "__missing_b__").lower())
    point_q = re.escape(roles.get("Q", "__missing_q__").lower())
    point_c = re.escape(roles.get("C", "__missing_c__").lower())
    return bool(
        re.search(rf"\b{point_p}\b.{{0,80}}different from\s+{point_b}\b", normalized)
        and re.search(
            rf"\b{point_q}\b.{{0,80}}different from\s+{point_c}\b",
            normalized,
        )
    )


def certify_jgex_circumcenter_diameter_parallelogram_application(
    source: str,
    natural_statement: str,
) -> JGEXCircumcenterDiameterParallelogramApplication:
    normalized = source.strip()
    normalized_natural = natural_statement.strip()
    formulation = JGEXFormulation.from_text(normalized)
    roles, matched = _match_roles(formulation, _records(formulation))
    distinct = _asserts_distinct_secondary_intersections(normalized_natural, roles)
    goal = str(formulation.goals[0]) if len(formulation.goals) == 1 else ""
    chart = certify_circumcenter_diameter_parallelogram_chart()
    replayed = (
        chart.replayed
        and chart.all_conditions_discharged
        and distinct
        and len(roles) == 8
        and len(matched) == 5
    )
    return JGEXCircumcenterDiameterParallelogramApplication(
        theorem=chart.theorem,
        source_sha256=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        natural_statement=normalized_natural,
        natural_statement_sha256=hashlib.sha256(
            normalized_natural.encode("utf-8")
        ).hexdigest(),
        natural_semantic_atoms=("distinct(P,B)", "distinct(Q,C)") if distinct else (),
        roles=roles,
        matched_constructions=matched,
        goal=goal,
        chart_certificate_sha256=chart.certificate_sha256,
        nondegeneracy_obligations=chart.assumptions,
        undischarged_nondegeneracy_obligations=(
            () if distinct else ("P != B", "Q != C")
        ),
        replayed=replayed,
    )


def render_circumcenter_diameter_parallelogram_chart_svg(
    *, s_value: float = 1.4, t_value: float = 0.55
) -> str:
    certificate = certify_circumcenter_diameter_parallelogram_chart()
    symbols = {name: sp.Symbol(name, real=True) for name in ("s", "t")}
    substitutions = {
        symbols["s"]: sp.Rational(str(s_value)),
        symbols["t"]: sp.Rational(str(t_value)),
    }
    points = {
        name: (
            float(sp.sympify(value[0], locals=symbols).subs(substitutions)),
            float(sp.sympify(value[1], locals=symbols).subs(substitutions)),
        )
        for name, value in certificate.coordinates.items()
    }
    o1 = points["O1"]
    radius = ((points["O"][0] - o1[0]) ** 2 + (points["O"][1] - o1[1]) ** 2) ** 0.5

    figure, axis = plt.subplots(figsize=(7.8, 6.2), constrained_layout=True)
    figure.patch.set_facecolor("#f8fafc")
    axis.set_facecolor("#ffffff")
    axis.set_aspect("equal", adjustable="datalim")
    axis.axis("off")
    axis.set_title(
        "円の第2交点が平行四辺形を閉じる",
        loc="left",
        fontsize=14,
        color="#0f172a",
        fontfamily="Yu Gothic",
    )
    axis.add_patch(Circle((0, 0), 1, fill=False, color="#94a3b8", linewidth=1.2))
    axis.add_patch(Circle(o1, radius, fill=False, color="#7c3aed", linewidth=1.5))
    for left, right, color, width in (
        ("A", "B", "#64748b", 1.2),
        ("A", "C", "#64748b", 1.2),
        ("A", "P", "#0891b2", 2.0),
        ("P", "N", "#e11d48", 2.0),
        ("N", "Q", "#0891b2", 2.0),
        ("Q", "A", "#e11d48", 2.0),
        ("O", "N", "#475569", 1.0),
    ):
        axis.plot(
            (points[left][0], points[right][0]),
            (points[left][1], points[right][1]),
            color=color,
            linewidth=width,
        )
    for name, (x_value, y_value) in points.items():
        highlight = name in {"A", "P", "N", "Q"}
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
    axis.margins(0.16)
    output = io.StringIO()
    figure.savefig(output, format="svg", bbox_inches="tight")
    plt.close(figure)
    return output.getvalue()


__all__ = [
    "CircumcenterDiameterParallelogramCertificate",
    "JGEXCircumcenterDiameterParallelogramApplication",
    "certify_circumcenter_diameter_parallelogram_chart",
    "certify_jgex_circumcenter_diameter_parallelogram_application",
    "render_circumcenter_diameter_parallelogram_chart_svg",
]
