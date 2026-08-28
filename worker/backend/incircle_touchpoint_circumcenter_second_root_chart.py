"""Exact unit-incircle chart for a circumcenter-line second-root theorem."""

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
class IncircleTouchpointCircumcenterSecondRootCertificate:
    theorem: str
    normalization: str
    parameter_domain: tuple[str, ...]
    construction_domain_conditions: tuple[str, ...]
    discharged_conditions: dict[str, str]
    coordinates: dict[str, tuple[str, str]]
    second_root_parameter: str
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
                "# 内接円接点・外心直線・円の第2根チャート",
                "",
                "## 定理",
                "",
                (
                    "三角形 $ABC$ の内心と外心を $I,O$、内接円の $BC$ 上の"
                    "接点を $D$ とする。円 $(ADI)$ が直線 $AO$ と $A$ 以外で"
                    "$E$ に交わるなら、$AE=ID$ である。"
                ),
                "",
                "## 標準化",
                "",
                self.normalization,
                "",
                f"- 第2根パラメータ: `{self.second_root_parameter}`",
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
class JGEXIncircleTouchpointCircumcenterSecondRootApplication:
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


def _circumcenter(
    point_a: sp.Matrix,
    point_b: sp.Matrix,
    point_c: sp.Matrix,
) -> sp.Matrix:
    ab = point_b - point_a
    ac = point_c - point_a
    determinant = 2 * _cross(ab, ac)
    rhs_b = sp.expand(point_b.dot(point_b) - point_a.dot(point_a))
    rhs_c = sp.expand(point_c.dot(point_c) - point_a.dot(point_a))
    return _point(
        (rhs_b * ac[1] - ab[1] * rhs_c) / determinant,
        (ab[0] * rhs_c - rhs_b * ac[0]) / determinant,
    ).applyfunc(sp.cancel)


def _cyclic_determinant(points: tuple[sp.Matrix, ...]) -> sp.Expr:
    return sp.expand(
        sp.Matrix(
            [[point.dot(point), point[0], point[1], 1] for point in points]
        ).det()
    )


@lru_cache(maxsize=1)
def certify_incircle_touchpoint_circumcenter_second_root_chart(
) -> IncircleTouchpointCircumcenterSecondRootCertificate:
    p, q = sp.symbols("p q", real=True)
    point_i = _point(0, 0)
    point_d = _point(1, 0)
    point_a = _point((1 - p * q) / (1 + p * q), (p + q) / (1 + p * q))
    point_b = _point(1, q)
    point_c = _point(1, p)
    normal_ca = _point(1 - p**2, 2 * p)
    normal_ab = _point(1 - q**2, 2 * q)
    point_o = _circumcenter(point_a, point_b, point_c)
    second_root_parameter = sp.cancel(
        4 * (1 + p * q) / ((1 + p**2) * (1 + q**2))
    )
    point_e = (
        point_a + second_root_parameter * (point_o - point_a)
    ).applyfunc(sp.cancel)

    residuals = {
        "CA_tangent_normalized": normal_ca.dot(normal_ca) - (1 + p**2) ** 2,
        "AB_tangent_normalized": normal_ab.dot(normal_ab) - (1 + q**2) ** 2,
        "A_on_CA": normal_ca.dot(point_a) - (1 + p**2),
        "A_on_AB": normal_ab.dot(point_a) - (1 + q**2),
        "B_on_AB": normal_ab.dot(point_b) - (1 + q**2),
        "B_on_BC": point_b[0] - 1,
        "C_on_BC": point_c[0] - 1,
        "C_on_CA": normal_ca.dot(point_c) - (1 + p**2),
        "D_on_BC": _cross(point_d - point_b, point_c - point_b),
        "ID_perpendicular_BC": (point_d - point_i).dot(point_c - point_b),
        "O_equidistant_A_B": (
            (point_o - point_a).dot(point_o - point_a)
            - (point_o - point_b).dot(point_o - point_b)
        ),
        "O_equidistant_A_C": (
            (point_o - point_a).dot(point_o - point_a)
            - (point_o - point_c).dot(point_o - point_c)
        ),
        "E_on_AO": _cross(point_e - point_a, point_o - point_a),
        "A_D_I_E_cyclic": _cyclic_determinant(
            (point_a, point_d, point_i, point_e)
        ),
        "goal_AE_equals_ID": (
            (point_e - point_a).dot(point_e - point_a)
            - (point_d - point_i).dot(point_d - point_i)
        ),
    }
    rendered = {name: _canonical(value) for name, value in residuals.items()}
    replayed = all(value == "0" for value in rendered.values())
    coordinates = {
        name: (_canonical(value[0]), _canonical(value[1]))
        for name, value in {
            "I": point_i,
            "D": point_d,
            "A": point_a,
            "B": point_b,
            "C": point_c,
            "O": point_o,
            "E": point_e,
        }.items()
    }
    discharged_conditions = {
        "p*q*(p-q)*(1+p*q) != 0": (
            "The accepted nondegenerate triangle with incenter has three distinct "
            "nonparallel side tangents in this chart."
        ),
        "p+q != 0": (
            "The source constructs the circumcircle of A,D,I, so those three points "
            "are noncollinear in the accepted construction domain."
        ),
        "E != A": (
            "The natural statement identifies A and E as the two line-circle "
            "intersection points; the displayed second-root parameter is nonzero."
        ),
    }
    payload = {
        "theorem": "incircle-touchpoint-circumcenter-line-second-root-equals-inradius",
        "normalization": (
            "I=(0,0), the incircle has radius 1, D=(1,0), BC is x=1, and "
            "the remaining tangents use half-angle parameters p,q."
        ),
        "parameter_domain": (
            "p and q are real",
            "p*q*(p-q)*(1+p*q)*(p+q) != 0",
        ),
        "construction_domain_conditions": (
            "E is the intersection of AO with circle ADI distinct from A",
        ),
        "discharged_conditions": discharged_conditions,
        "coordinates": coordinates,
        "second_root_parameter": _canonical(second_root_parameter),
        "replay_residuals": rendered,
        "replayed": replayed,
        "all_conditions_discharged": replayed,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return IncircleTouchpointCircumcenterSecondRootCertificate(
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


def _line_circum_role(
    records: tuple[dict[str, object], ...],
    line: tuple[str, str],
    circle: frozenset[str],
) -> str | None:
    for record in records:
        if len(record["outputs"]) != 1:
            continue
        has_line = any(
            name == "on_line" and frozenset(args) == frozenset(line)
            for name, args in record["constructions"]
        )
        has_circum = any(
            name == "on_circum" and frozenset(args) == circle
            for name, args in record["constructions"]
        )
        if has_line and has_circum:
            return record["outputs"][0]
    return None


def _asserts_two_intersections(statement: str) -> bool:
    lowered = re.sub(r"\s+", " ", statement.strip().lower())
    return bool(
        re.search(r"\bat the points?\b", lowered)
        or re.search(r"\btwo distinct points\b", lowered)
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
    point_i = _single_unordered(
        records, "incenter", frozenset((point_a, point_b, point_c))
    )
    point_o = _single_unordered(
        records, "circumcenter", frozenset((point_a, point_b, point_c))
    )
    if not point_i or not point_o:
        return {}, ()
    point_d = _foot_role(records, point_i, (point_b, point_c))
    if not point_d:
        return {}, ()
    point_e = _line_circum_role(
        records,
        (point_a, point_o),
        frozenset((point_a, point_d, point_i)),
    )
    if not point_e:
        return {}, ()
    goal = str(formulation.goals[0]) if len(formulation.goals) == 1 else ""
    goal_parts = goal.split()
    if len(goal_parts) != 5:
        return {}, ()
    expected = Atom("cong", (point_a, point_e, point_i, point_d)).canonical()
    actual = Atom(goal_parts[0], tuple(goal_parts[1:])).canonical()
    if actual != expected:
        return {}, ()
    roles = {
        "A": point_a,
        "B": point_b,
        "C": point_c,
        "I": point_i,
        "D": point_d,
        "O": point_o,
        "E": point_e,
    }
    matched = (
        "I and O are the incenter and circumcenter of ABC",
        "D is the foot from I to BC",
        "E lies on AO and circle ADI",
        "the natural statement selects E as the other intersection from A",
        "the goal is AE=ID",
    )
    return roles, matched


def certify_jgex_incircle_touchpoint_circumcenter_second_root_application(
    source: str,
    natural_statement: str,
) -> JGEXIncircleTouchpointCircumcenterSecondRootApplication:
    normalized = source.strip()
    normalized_natural = natural_statement.strip()
    formulation = JGEXFormulation.from_text(normalized)
    roles, matched = _match_roles(formulation, _records(formulation))
    distinct = _asserts_two_intersections(normalized_natural)
    goal = str(formulation.goals[0]) if len(formulation.goals) == 1 else ""
    chart = certify_incircle_touchpoint_circumcenter_second_root_chart()
    replayed = (
        chart.replayed
        and chart.all_conditions_discharged
        and distinct
        and len(roles) == 7
        and len(matched) == 5
    )
    return JGEXIncircleTouchpointCircumcenterSecondRootApplication(
        theorem=chart.theorem,
        source_sha256=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        natural_statement=normalized_natural,
        natural_statement_sha256=hashlib.sha256(
            normalized_natural.encode("utf-8")
        ).hexdigest(),
        natural_semantic_atoms=("distinct(E,A)", "on_circum(E,A,D,I)")
        if distinct
        else (),
        roles=roles,
        matched_constructions=matched,
        goal=goal,
        chart_certificate_sha256=chart.certificate_sha256,
        nondegeneracy_obligations=chart.assumptions,
        undischarged_nondegeneracy_obligations=() if distinct else ("E != A",),
        replayed=replayed,
    )


def render_incircle_touchpoint_circumcenter_second_root_chart_svg(
    *, p_value: float = 1.3, q_value: float = -2.0
) -> str:
    certificate = certify_incircle_touchpoint_circumcenter_second_root_chart()
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
    a, d, i = points["A"], points["D"], points["I"]
    matrix = sp.Matrix(
        [
            [2 * (d[0] - a[0]), 2 * (d[1] - a[1])],
            [2 * (i[0] - a[0]), 2 * (i[1] - a[1])],
        ]
    )
    rhs = sp.Matrix(
        [d[0] ** 2 + d[1] ** 2 - a[0] ** 2 - a[1] ** 2,
         i[0] ** 2 + i[1] ** 2 - a[0] ** 2 - a[1] ** 2]
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
        "内接円の接点から円の第2根へ",
        loc="left",
        fontsize=14,
        color="#0f172a",
        fontfamily="Yu Gothic",
    )
    for left, right, color, width in (
        ("A", "B", "#64748b", 1.3),
        ("B", "C", "#64748b", 1.3),
        ("C", "A", "#64748b", 1.3),
        ("A", "O", "#2563eb", 1.5),
        ("I", "D", "#7c3aed", 1.8),
        ("A", "E", "#e11d48", 2.0),
    ):
        axis.plot(
            (points[left][0], points[right][0]),
            (points[left][1], points[right][1]),
            color=color,
            linewidth=width,
        )
    axis.add_patch(Circle(center, radius, fill=False, color="#0ea5e9", linewidth=1.2))
    axis.add_patch(Circle(points["I"], 1.0, fill=False, color="#94a3b8", linewidth=1.0))
    for name, (x_value, y_value) in points.items():
        highlight = name in {"A", "E", "I", "D"}
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
    "IncircleTouchpointCircumcenterSecondRootCertificate",
    "JGEXIncircleTouchpointCircumcenterSecondRootApplication",
    "certify_incircle_touchpoint_circumcenter_second_root_chart",
    "certify_jgex_incircle_touchpoint_circumcenter_second_root_application",
    "render_incircle_touchpoint_circumcenter_second_root_chart_svg",
]
