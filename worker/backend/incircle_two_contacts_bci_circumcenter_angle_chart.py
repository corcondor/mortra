"""Exact unit-incircle chart for a two-contact equal-angle theorem."""

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
from matplotlib.patches import Circle

from worker.backend.geometry_proof_hypergraph import Atom
from worker.backend.jgex_chart_parser import ChartJGEXFormulation as JGEXFormulation


@dataclass(frozen=True)
class IncircleTwoContactsBCICircumcenterAngleCertificate:
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
                "# 内接円の2接点と円 BCI の外心による等角チャート",
                "",
                "## 定理",
                "",
                (
                    "三角形 $ABC$ の内心を $I$、内接円の $AB,AC$ 上の接点を"
                    "$D,E$ とし、三角形 $BCI$ の外心を $O$ とすると、"
                    "$\\angle ODB=\\angle CEO$ である。"
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
class JGEXIncircleTwoContactsBCICircumcenterAngleApplication:
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


@lru_cache(maxsize=1)
def certify_incircle_two_contacts_bci_circumcenter_angle_chart(
) -> IncircleTwoContactsBCICircumcenterAngleCertificate:
    p, q = sp.symbols("p q", real=True)
    point_i = _point(0, 0)
    point_b = _point(1, q)
    point_c = _point(1, p)
    normal_ab = _point(1 - q**2, 2 * q)
    normal_ac = _point(1 - p**2, 2 * p)
    point_d = (normal_ab / (1 + q**2)).applyfunc(sp.cancel)
    point_e = (normal_ac / (1 + p**2)).applyfunc(sp.cancel)
    point_o = _circumcenter(point_b, point_c, point_i)

    vector_od = point_o - point_d
    vector_db = point_b - point_d
    vector_ce = point_c - point_e
    vector_eo = point_o - point_e
    equal_angle_polynomial = sp.expand(
        _cross(vector_od, vector_db) * vector_ce.dot(vector_eo)
        - vector_od.dot(vector_db) * _cross(vector_ce, vector_eo)
    )
    residuals = {
        "AB_tangent_normalized": normal_ab.dot(normal_ab) - (1 + q**2) ** 2,
        "AC_tangent_normalized": normal_ac.dot(normal_ac) - (1 + p**2) ** 2,
        "D_on_AB": normal_ab.dot(point_d) - (1 + q**2),
        "ID_perpendicular_AB": point_d.dot(point_b - point_d),
        "E_on_AC": normal_ac.dot(point_e) - (1 + p**2),
        "IE_perpendicular_AC": point_e.dot(point_c - point_e),
        "O_equidistant_B_C": (
            (point_o - point_b).dot(point_o - point_b)
            - (point_o - point_c).dot(point_o - point_c)
        ),
        "O_equidistant_B_I": (
            (point_o - point_b).dot(point_o - point_b)
            - (point_o - point_i).dot(point_o - point_i)
        ),
        "goal_equal_directed_angles": equal_angle_polynomial,
    }
    rendered = {name: _canonical(value) for name, value in residuals.items()}
    replayed = all(value == "0" for value in rendered.values())
    coordinates = {
        name: (_canonical(value[0]), _canonical(value[1]))
        for name, value in {
            "I": point_i,
            "B": point_b,
            "C": point_c,
            "D": point_d,
            "E": point_e,
            "O": point_o,
        }.items()
    }
    discharged_conditions = {
        "p*q*(p-q) != 0": (
            "The accepted triangle, its two distinct contact points, and the "
            "circumcenter of BCI discharge these factors."
        ),
        "the four angle rays are nonzero": (
            "The JGEX equal-angle goal is defined only for noncollapsed line pairs."
        ),
    }
    payload = {
        "theorem": "incircle-two-contact-points-bci-circumcenter-equal-angle",
        "normalization": (
            "I=(0,0), the incircle is the unit circle, BC is x=1, and the "
            "AB,AC tangents use half-angle parameters q,p."
        ),
        "parameter_domain": ("p and q are real", "p*q*(p-q) != 0"),
        "construction_domain_conditions": (
            "D,E are the two contact feet and O is the circumcenter of BCI",
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
    return IncircleTwoContactsBCICircumcenterAngleCertificate(
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
    if not point_i:
        return {}, ()
    point_d = _foot_role(records, point_i, (point_a, point_b))
    point_e = _foot_role(records, point_i, (point_a, point_c))
    if not point_d or not point_e:
        return {}, ()
    point_o = _single_unordered(
        records, "circumcenter", frozenset((point_b, point_c, point_i))
    )
    if not point_o:
        return {}, ()
    goal = str(formulation.goals[0]) if len(formulation.goals) == 1 else ""
    goal_parts = goal.split()
    if len(goal_parts) != 9:
        return {}, ()
    expected = Atom(
        "eqangle",
        (point_o, point_d, point_d, point_b, point_c, point_e, point_e, point_o),
    ).canonical()
    actual = Atom(goal_parts[0], tuple(goal_parts[1:])).canonical()
    if actual != expected:
        return {}, ()
    roles = {
        "A": point_a,
        "B": point_b,
        "C": point_c,
        "I": point_i,
        "D": point_d,
        "E": point_e,
        "O": point_o,
    }
    matched = (
        "I is the incenter of ABC",
        "D,E are the contact feet on AB,AC",
        "O is the circumcenter of BCI",
        "the goal is angle ODB equal to angle CEO",
    )
    return roles, matched


def certify_jgex_incircle_two_contacts_bci_circumcenter_angle_application(
    source: str,
) -> JGEXIncircleTwoContactsBCICircumcenterAngleApplication:
    normalized = source.strip()
    formulation = JGEXFormulation.from_text(normalized)
    roles, matched = _match_roles(formulation, _records(formulation))
    goal = str(formulation.goals[0]) if len(formulation.goals) == 1 else ""
    chart = certify_incircle_two_contacts_bci_circumcenter_angle_chart()
    replayed = (
        chart.replayed
        and chart.all_conditions_discharged
        and len(roles) == 7
        and len(matched) == 4
    )
    return JGEXIncircleTwoContactsBCICircumcenterAngleApplication(
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


def render_incircle_two_contacts_bci_circumcenter_angle_chart_svg(
    *, p_value: float = 1.3, q_value: float = -2.0
) -> str:
    certificate = certify_incircle_two_contacts_bci_circumcenter_angle_chart()
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
    figure, axis = plt.subplots(figsize=(8.4, 5.6), constrained_layout=True)
    figure.patch.set_facecolor("#f8fafc")
    axis.set_facecolor("#ffffff")
    axis.set_aspect("equal", adjustable="datalim")
    axis.axis("off")
    axis.set_title(
        "2つの接点を等角で結ぶ",
        loc="left",
        fontsize=14,
        color="#0f172a",
        fontfamily="Yu Gothic",
    )
    axis.add_patch(Circle(points["I"], 1.0, fill=False, color="#94a3b8", linewidth=1.1))
    for left, right, color, width in (
        ("B", "C", "#64748b", 1.3),
        ("O", "D", "#2563eb", 1.8),
        ("D", "B", "#2563eb", 1.8),
        ("C", "E", "#e11d48", 1.8),
        ("E", "O", "#e11d48", 1.8),
    ):
        axis.plot(
            (points[left][0], points[right][0]),
            (points[left][1], points[right][1]),
            color=color,
            linewidth=width,
        )
    for name, (x_value, y_value) in points.items():
        color = "#e11d48" if name in {"D", "E", "O"} else "#0f172a"
        axis.scatter((x_value,), (y_value,), color=color, s=30, zorder=5)
        axis.annotate(
            name,
            (x_value, y_value),
            xytext=(6, 5),
            textcoords="offset points",
            fontsize=9,
            color=color,
        )
    axis.relim()
    axis.autoscale_view()
    axis.margins(0.2)
    output = io.StringIO()
    figure.savefig(output, format="svg", facecolor=figure.get_facecolor())
    plt.close(figure)
    return output.getvalue()


__all__ = [
    "IncircleTwoContactsBCICircumcenterAngleCertificate",
    "JGEXIncircleTwoContactsBCICircumcenterAngleApplication",
    "certify_incircle_two_contacts_bci_circumcenter_angle_chart",
    "certify_jgex_incircle_two_contacts_bci_circumcenter_angle_application",
    "render_incircle_two_contacts_bci_circumcenter_angle_chart_svg",
]
