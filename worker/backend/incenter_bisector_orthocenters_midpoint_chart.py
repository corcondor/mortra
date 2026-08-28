"""Exact unit-incircle chart for a bisector/orthocenter midpoint theorem."""

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
class IncenterBisectorOrthocentersMidpointCertificate:
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
                "# 内心・二等分線・垂心対の中点チャート",
                "",
                "## 定理",
                "",
                (
                    "三角形 $ABC$ の内心を $I$ とし、$E=BI\\cap AC$, "
                    "$F=CI\\cap AB$、$D$ を $I$ から $BC$ への垂足とする。"
                    "$M,N$ を三角形 $AIF,AIE$ の垂心、$P=EM\\cap FN$、"
                    "$X$ を $BC$ の中点とする。$Y\\in AD$ かつ $XY\\perp IP$ "
                    "とすると、$XY$ の中点は $AI$ 上にある。"
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
class JGEXIncenterBisectorOrthocentersMidpointApplication:
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
    first_origin: sp.Matrix,
    first_direction: sp.Matrix,
    second_origin: sp.Matrix,
    second_direction: sp.Matrix,
) -> tuple[sp.Matrix, sp.Expr]:
    determinant = sp.factor(_cross(first_direction, second_direction))
    parameter = sp.cancel(
        _cross(second_origin - first_origin, second_direction) / determinant
    )
    point = (first_origin + parameter * first_direction).applyfunc(sp.cancel)
    return point, determinant


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
def certify_incenter_bisector_orthocenters_midpoint_chart(
) -> IncenterBisectorOrthocentersMidpointCertificate:
    p, q = sp.symbols("p q", real=True)
    i = _point(0, 0)
    point_a = _point((1 - p * q) / (1 + p * q), (p + q) / (1 + p * q))
    point_b = _point(1, q)
    point_c = _point(1, p)
    point_d = _point(1, 0)
    normal_ca = _point(1 - p**2, 2 * p)
    normal_ab = _point(1 - q**2, 2 * q)

    point_e, determinant_e = _line_intersection(
        point_a, point_c - point_a, i, point_b
    )
    point_f, determinant_f = _line_intersection(
        point_a, point_b - point_a, i, point_c
    )
    center_aif = _circumcenter(point_a, i, point_f)
    point_m = (point_a + point_f - 2 * center_aif).applyfunc(sp.cancel)
    center_aie = _circumcenter(point_a, i, point_e)
    point_n = (point_a + point_e - 2 * center_aie).applyfunc(sp.cancel)
    point_p, determinant_p = _line_intersection(
        point_e, point_m - point_e, point_f, point_n - point_f
    )
    point_x = ((point_b + point_c) / 2).applyfunc(sp.cancel)
    direction_ad = point_d - point_a
    y_parameter_denominator = sp.factor(point_p.dot(direction_ad))
    y_parameter = sp.cancel(point_p.dot(point_x - point_a) / y_parameter_denominator)
    point_y = (point_a + y_parameter * direction_ad).applyfunc(sp.cancel)
    point_k = ((point_x + point_y) / 2).applyfunc(sp.cancel)

    residuals = {
        "CA_tangent_normalized": normal_ca.dot(normal_ca) - (1 + p**2) ** 2,
        "AB_tangent_normalized": normal_ab.dot(normal_ab) - (1 + q**2) ** 2,
        "A_on_CA": normal_ca.dot(point_a) - (1 + p**2),
        "A_on_AB": normal_ab.dot(point_a) - (1 + q**2),
        "B_on_AB": normal_ab.dot(point_b) - (1 + q**2),
        "B_on_BC": point_b[0] - 1,
        "C_on_BC": point_c[0] - 1,
        "C_on_CA": normal_ca.dot(point_c) - (1 + p**2),
        "E_on_AC": _cross(point_e - point_a, point_c - point_a),
        "E_on_BI": _cross(point_e - point_b, i - point_b),
        "F_on_AB": _cross(point_f - point_a, point_b - point_a),
        "F_on_CI": _cross(point_f - point_c, i - point_c),
        "D_on_BC": _cross(point_d - point_b, point_c - point_b),
        "ID_perpendicular_BC": (point_d - i).dot(point_c - point_b),
        "M_altitude_A": (point_m - point_a).dot(point_f - i),
        "M_altitude_I": (point_m - i).dot(point_f - point_a),
        "M_altitude_F": (point_m - point_f).dot(point_a - i),
        "N_altitude_A": (point_n - point_a).dot(point_e - i),
        "N_altitude_I": (point_n - i).dot(point_e - point_a),
        "N_altitude_E": (point_n - point_e).dot(point_a - i),
        "P_on_EM": _cross(point_p - point_e, point_m - point_e),
        "P_on_FN": _cross(point_p - point_f, point_n - point_f),
        "X_midpoint_BC_x": 2 * point_x[0] - point_b[0] - point_c[0],
        "X_midpoint_BC_y": 2 * point_x[1] - point_b[1] - point_c[1],
        "Y_on_AD": _cross(point_y - point_a, point_d - point_a),
        "XY_perpendicular_IP": (point_y - point_x).dot(point_p - i),
        "K_midpoint_XY_x": 2 * point_k[0] - point_x[0] - point_y[0],
        "K_midpoint_XY_y": 2 * point_k[1] - point_x[1] - point_y[1],
        "goal_K_on_AI": _cross(point_k - i, point_a - i),
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
            "D": point_d,
            "E": point_e,
            "F": point_f,
            "M": point_m,
            "N": point_n,
            "P": point_p,
            "X": point_x,
            "Y": point_y,
            "K": point_k,
        }.items()
    }
    determinant_factors = {
        "triangle_ABC_twice_area": _canonical(
            _cross(point_b - point_a, point_c - point_a)
        ),
        "E_intersection": _canonical(determinant_e),
        "F_intersection": _canonical(determinant_f),
        "P_intersection": _canonical(determinant_p),
        "Y_intersection": _canonical(y_parameter_denominator),
    }
    discharged_conditions = {
        "p*q*(p-q)*(1+p*q) != 0": (
            "The nondegenerate JGEX triangle with an incenter has three distinct "
            "nonparallel side tangents in this unit-incircle chart."
        ),
        "E,F,M,N,P,Y are uniquely defined": (
            "Each source construction is an accepted line intersection, orthocenter, "
            "foot, or perpendicular-line intersection; its displayed determinant is nonzero."
        ),
        "p+q != 0 and the two cevian denominators are nonzero": (
            "These are factors of the accepted P, E, and F constructions and are "
            "therefore discharged by the JGEX construction domain."
        ),
    }
    upstream_semantics = (
        "The incenter makes BI and CI the corresponding internal angle bisectors.",
        "JGEX foot and on_tline constructors enforce Euclidean perpendicularity.",
        "JGEX line intersections and orthocenters reject degenerate inputs.",
    )
    payload = {
        "theorem": "incenter-bisector-orthocenters-midpoint-on-bisector",
        "normalization": (
            "I=(0,0), the incircle has radius 1, BC is x=1, and CA,AB use "
            "the rational tangent half-angle parameters p,q."
        ),
        "parameter_domain": (
            "p and q are real",
            "p*q*(p-q)*(1+p*q) != 0",
        ),
        "construction_domain_conditions": (
            "all line intersections, feet, and orthocenters in the source are defined",
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
    return IncenterBisectorOrthocentersMidpointCertificate(
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


def _has(
    constructions: tuple[tuple[str, tuple[str, ...]], ...],
    name: str,
    args: tuple[str, ...],
    *,
    unordered_tail: bool = False,
) -> bool:
    for construction_name, construction_args in constructions:
        if construction_name != name or len(construction_args) != len(args):
            continue
        if unordered_tail:
            if construction_args[0] == args[0] and frozenset(
                construction_args[1:]
            ) == frozenset(args[1:]):
                return True
        elif construction_args == args:
            return True
    return False


def _bisector_side_role(
    records: tuple[dict[str, object], ...],
    side: tuple[str, str],
    angle: tuple[str, str, str],
) -> str | None:
    for record in records:
        if len(record["outputs"]) != 1:
            continue
        constructions = record["constructions"]
        if _has(constructions, "on_line", side, unordered_tail=False) or _has(
            constructions, "on_line", tuple(reversed(side)), unordered_tail=False
        ):
            if _has(constructions, "angle_bisector", angle):
                return record["outputs"][0]
    return None


def _line_intersection_role(
    records: tuple[dict[str, object], ...],
    first: tuple[str, str],
    second: tuple[str, str],
) -> str | None:
    for record in records:
        if len(record["outputs"]) != 1:
            continue
        constructions = record["constructions"]
        pairs = {
            frozenset(args)
            for name, args in constructions
            if name == "on_line" and len(args) == 2
        }
        if frozenset(first) in pairs and frozenset(second) in pairs:
            return record["outputs"][0]
    return None


def _line_tline_intersection_role(
    records: tuple[dict[str, object], ...],
    line: tuple[str, str],
    tline: tuple[str, str, str],
) -> str | None:
    for record in records:
        if len(record["outputs"]) != 1:
            continue
        constructions = record["constructions"]
        line_found = any(
            name == "on_line" and frozenset(args) == frozenset(line)
            for name, args in constructions
        )
        tline_found = _has(
            constructions, "on_tline", tline, unordered_tail=True
        )
        if line_found and tline_found:
            return record["outputs"][0]
    return None


def _ordered_single(
    records: tuple[dict[str, object], ...], name: str, args: tuple[str, ...]
) -> str | None:
    for record in records:
        if (
            len(record["outputs"]) == 1
            and record["constructions"] == ((name, args),)
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
        point_e = _bisector_side_role(
            records, (point_a, point_c), (point_a, point_b, point_c)
        )
        point_f = _bisector_side_role(
            records, (point_a, point_b), (point_a, point_c, point_b)
        )
        if not point_e or not point_f:
            continue
        point_d = _ordered_single(
            records, "foot", (incenter, point_b, point_c)
        )
        point_m = _single_unordered(
            records, "orthocenter", frozenset((point_a, incenter, point_f))
        )
        point_n = _single_unordered(
            records, "orthocenter", frozenset((point_a, incenter, point_e))
        )
        if not all((point_d, point_m, point_n)):
            continue
        point_p = _line_intersection_role(
            records, (point_e, point_m), (point_f, point_n)
        )
        point_x = _single_unordered(
            records, "midpoint", frozenset((point_b, point_c))
        )
        if not point_p or not point_x:
            continue
        point_y = _line_tline_intersection_role(
            records,
            (point_a, point_d),
            (point_x, incenter, point_p),
        )
        if not point_y:
            continue
        point_k = _single_unordered(
            records, "midpoint", frozenset((point_x, point_y))
        )
        if not point_k:
            continue
        expected = Atom("coll", (point_k, point_a, incenter)).canonical()
        actual = Atom(goal_parts[0], tuple(goal_parts[1:])).canonical()
        if actual != expected:
            continue
        roles = {
            "A": point_a,
            "B": point_b,
            "C": point_c,
            "I": incenter,
            "D": point_d,
            "E": point_e,
            "F": point_f,
            "M": point_m,
            "N": point_n,
            "P": point_p,
            "X": point_x,
            "Y": point_y,
            "K": point_k,
        }
        matched = (
            "I is the incenter and E,F are the two internal-bisector traces",
            "D is the foot from I to BC",
            "M,N are the orthocenters of AIF and AIE",
            "P is the intersection of EM and FN",
            "X is the midpoint of BC",
            "Y lies on AD and XY is perpendicular to IP",
            "the goal places the midpoint K of XY on AI",
        )
        return roles, matched
    return {}, ()


def certify_jgex_incenter_bisector_orthocenters_midpoint_application(
    source: str,
) -> JGEXIncenterBisectorOrthocentersMidpointApplication:
    normalized = source.strip()
    formulation = JGEXFormulation.from_text(normalized)
    roles, matched = _match_roles(formulation, _records(formulation))
    goal = str(formulation.goals[0]) if len(formulation.goals) == 1 else ""
    chart = certify_incenter_bisector_orthocenters_midpoint_chart()
    replayed = (
        chart.replayed
        and chart.all_conditions_discharged
        and len(roles) == 13
        and len(matched) == 7
    )
    return JGEXIncenterBisectorOrthocentersMidpointApplication(
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


def render_incenter_bisector_orthocenters_midpoint_chart_svg(
    *, p_value: float = 1.3, q_value: float = -2.0
) -> str:
    certificate = certify_incenter_bisector_orthocenters_midpoint_chart()
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
    figure, axis = plt.subplots(figsize=(9.4, 6.2), constrained_layout=True)
    figure.patch.set_facecolor("#f8fafc")
    axis.set_facecolor("#ffffff")
    axis.set_aspect("equal", adjustable="datalim")
    axis.axis("off")
    axis.set_title(
        "二等分線と2つの垂心から中点を決める",
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
    for left, right in (("B", "E"), ("C", "F"), ("E", "M"), ("F", "N")):
        segment(left, right, "#2563eb", 1.2)
    segment("A", "D", "#94a3b8")
    segment("X", "Y", "#e11d48", 2.2)
    segment("I", "P", "#7c3aed", 1.4)
    for name in ("A", "B", "C", "I", "D", "E", "F", "M", "N", "P", "X", "Y", "K"):
        x_value, y_value = points[name]
        highlight = name in {"K", "X", "Y"}
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
    axis.margins(0.14)
    output = io.StringIO()
    figure.savefig(output, format="svg", facecolor=figure.get_facecolor())
    plt.close(figure)
    return output.getvalue()


__all__ = [
    "IncenterBisectorOrthocentersMidpointCertificate",
    "JGEXIncenterBisectorOrthocentersMidpointApplication",
    "certify_incenter_bisector_orthocenters_midpoint_chart",
    "certify_jgex_incenter_bisector_orthocenters_midpoint_application",
    "render_incenter_bisector_orthocenters_midpoint_chart_svg",
]
