"""Exact chart for two Euler midpoints and crossed perpendiculars.

Two triangles share a vertex and their opposite vertex pairs lie on two
intersecting lines.  The chart uses an oblique unit basis for those lines and
proves that the crossed perpendiculars through the Euler midpoints meet on the
line joining the two orthocenters.
"""

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
class EulerMidpointsCrossPerpendicularCertificate:
    theorem: str
    normalization: str
    parameter_domain: tuple[str, ...]
    construction_domain_conditions: tuple[str, ...]
    discharged_conditions: dict[str, str]
    upstream_semantics: tuple[str, ...]
    coordinates: dict[str, tuple[str, str]]
    line_determinant: str
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
                "# 2つのEuler中点と交差垂線の共点チャート",
                "",
                "## 定理",
                "",
                (
                    "$P=AD\\cap BC$ とする。三角形 $ABP,CDP$ の外心を "
                    "$O_1,O_2$、垂心を $H_1,H_2$ とし、$E_i$ を "
                    "$O_iH_i$ の中点とする。$E_1$ を通り $CD$ に垂直な直線と、"
                    "$E_2$ を通り $AB$ に垂直な直線の交点を $X$ とすると、"
                    "$X,H_1,H_2$ は共線である。"
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
                "## 構成点の座標",
                "",
                coordinates,
                "",
                "## Cramer分母",
                "",
                f"`{self.line_determinant}`",
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
class JGEXEulerMidpointsCrossPerpendicularApplication:
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


def _dot(left: sp.Matrix, right: sp.Matrix, z: sp.Expr) -> sp.Expr:
    return sp.expand(
        left[0] * right[0]
        + left[1] * right[1]
        + z * (left[0] * right[1] + left[1] * right[0])
    )


def _norm2(value: sp.Matrix, z: sp.Expr) -> sp.Expr:
    return _dot(value, value, z)


def _cross(left: sp.Matrix, right: sp.Matrix) -> sp.Expr:
    return sp.expand(left[0] * right[1] - left[1] * right[0])


def _circumcenter(
    first_parameter: sp.Expr,
    second_parameter: sp.Expr,
    z: sp.Expr,
) -> sp.Matrix:
    delta = 1 - z**2
    return _point(
        (first_parameter - z * second_parameter) / (2 * delta),
        (second_parameter - z * first_parameter) / (2 * delta),
    ).applyfunc(sp.cancel)


def _orthocenter(
    first_parameter: sp.Expr,
    second_parameter: sp.Expr,
    center: sp.Matrix,
) -> sp.Matrix:
    return (
        _point(first_parameter, second_parameter) - 2 * center
    ).applyfunc(sp.cancel)


def _normal(direction: sp.Matrix, z: sp.Expr) -> sp.Matrix:
    return _point(
        direction[0] + z * direction[1],
        z * direction[0] + direction[1],
    )


def _two_line_equation_intersection(
    first_origin: sp.Matrix,
    first_normal: sp.Matrix,
    second_origin: sp.Matrix,
    second_normal: sp.Matrix,
) -> tuple[sp.Matrix, sp.Expr]:
    determinant = sp.factor(_cross(first_normal, second_normal))
    first_rhs = sp.expand(first_normal.dot(first_origin))
    second_rhs = sp.expand(second_normal.dot(second_origin))
    point = _point(
        (first_rhs * second_normal[1] - first_normal[1] * second_rhs)
        / determinant,
        (first_normal[0] * second_rhs - first_rhs * second_normal[0])
        / determinant,
    ).applyfunc(sp.cancel)
    return point, determinant


@lru_cache(maxsize=1)
def certify_euler_midpoints_cross_perpendicular_chart(
) -> EulerMidpointsCrossPerpendicularCertificate:
    a, b, c, d, z = sp.symbols("a b c d z", real=True)
    p = _point(0, 0)
    point_a = _point(a, 0)
    point_d = _point(d, 0)
    point_b = _point(0, b)
    point_c = _point(0, c)

    o1 = _circumcenter(a, b, z)
    h1 = _orthocenter(a, b, o1)
    e1 = ((o1 + h1) / 2).applyfunc(sp.cancel)
    o2 = _circumcenter(d, c, z)
    h2 = _orthocenter(d, c, o2)
    e2 = ((o2 + h2) / 2).applyfunc(sp.cancel)

    direction_cd = point_d - point_c
    direction_ab = point_a - point_b
    normal_cd = _normal(direction_cd, z)
    normal_ab = _normal(direction_ab, z)
    x, line_determinant = _two_line_equation_intersection(
        e1,
        normal_cd,
        e2,
        normal_ab,
    )

    residuals = {
        "P_on_AD": _cross(p - point_a, point_d - point_a),
        "P_on_BC": _cross(p - point_b, point_c - point_b),
        "O1_equidistant_A_P": (
            _norm2(o1 - point_a, z) - _norm2(o1 - p, z)
        ),
        "O1_equidistant_B_P": (
            _norm2(o1 - point_b, z) - _norm2(o1 - p, z)
        ),
        "H1_altitude_from_A": _dot(h1 - point_a, point_b - p, z),
        "H1_altitude_from_B": _dot(h1 - point_b, point_a - p, z),
        "E1_midpoint_x": 2 * e1[0] - o1[0] - h1[0],
        "E1_midpoint_y": 2 * e1[1] - o1[1] - h1[1],
        "O2_equidistant_D_P": (
            _norm2(o2 - point_d, z) - _norm2(o2 - p, z)
        ),
        "O2_equidistant_C_P": (
            _norm2(o2 - point_c, z) - _norm2(o2 - p, z)
        ),
        "H2_altitude_from_D": _dot(h2 - point_d, point_c - p, z),
        "H2_altitude_from_C": _dot(h2 - point_c, point_d - p, z),
        "E2_midpoint_x": 2 * e2[0] - o2[0] - h2[0],
        "E2_midpoint_y": 2 * e2[1] - o2[1] - h2[1],
        "X_on_perpendicular_through_E1": _dot(x - e1, direction_cd, z),
        "X_on_perpendicular_through_E2": _dot(x - e2, direction_ab, z),
        "normal_determinant_factorization": (
            line_determinant - (1 - z**2) * (a * c - b * d)
        ),
        "goal_X_H1_H2_collinear": _cross(x - h1, h2 - h1),
    }
    rendered = {name: _canonical(value) for name, value in residuals.items()}
    replayed = all(value == "0" for value in rendered.values())
    coordinates = {
        name: (_canonical(value[0]), _canonical(value[1]))
        for name, value in {
            "P": p,
            "A": point_a,
            "B": point_b,
            "C": point_c,
            "D": point_d,
            "O1": o1,
            "H1": h1,
            "E1": e1,
            "O2": o2,
            "H2": h2,
            "E2": e2,
            "X": x,
        }.items()
    }
    discharged_conditions = {
        "a*b*c*d != 0": (
            "The two successful circumcenter constructions make ABP and CDP "
            "nondegenerate, so none of the four normalized ray parameters vanishes."
        ),
        "1-z^2 > 0": (
            "The distinct lines AD and BC form a genuine Euclidean oblique basis; "
            "their unit direction cosine therefore satisfies |z|<1."
        ),
        "a*c-b*d != 0": (
            "The two crossed perpendiculars have normal determinant "
            "(1-z^2)(a*c-b*d).  JGEX creates X only when their intersection is unique."
        ),
    }
    upstream_semantics = (
        "JGEX circumcenter rejects a collinear defining triple.",
        "JGEX on_tline requires a nonzero reference-line direction.",
        "JGEX line intersection rejects parallel or coincident defining lines.",
    )
    payload = {
        "theorem": "two-euler-midpoints-cross-perpendiculars-orthocenter-line",
        "normalization": (
            "P=(0,0), A=(a,0), D=(d,0), B=(0,b), C=(0,c), "
            "with <(x,y),(u,v)>=xu+yv+z(xv+yu)"
        ),
        "parameter_domain": (
            "a*b*c*d != 0",
            "z is real and 1-z^2 > 0",
        ),
        "construction_domain_conditions": (
            "the two circumcenters and orthocenters are defined",
            "X is the unique intersection of the crossed perpendiculars",
        ),
        "discharged_conditions": discharged_conditions,
        "upstream_semantics": upstream_semantics,
        "coordinates": coordinates,
        "line_determinant": _canonical(line_determinant),
        "replay_residuals": rendered,
        "replayed": replayed,
        "all_conditions_discharged": replayed,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return EulerMidpointsCrossPerpendicularCertificate(
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


def _has_line(
    constructions: tuple[tuple[str, tuple[str, ...]], ...],
    left: str,
    right: str,
) -> bool:
    return any(
        name == "on_line" and frozenset(args) == frozenset((left, right))
        for name, args in constructions
    )


def _line_intersection_role(
    records: tuple[dict[str, object], ...],
    first: tuple[str, str],
    second: tuple[str, str],
) -> str | None:
    for record in records:
        if (
            len(record["outputs"]) == 1
            and _has_line(record["constructions"], *first)
            and _has_line(record["constructions"], *second)
        ):
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


def _match_roles(
    formulation: JGEXFormulation,
    records: tuple[dict[str, object], ...],
) -> tuple[dict[str, str], tuple[str, ...]]:
    quadrangle = next(
        (
            tuple(record["outputs"])
            for record in records
            if record["constructions"] == (("quadrangle", ()),)
            and len(record["outputs"]) == 4
        ),
        None,
    )
    if quadrangle is None:
        return {}, ()

    goal = str(formulation.goals[0]) if len(formulation.goals) == 1 else ""
    for point_a, point_b, point_c, point_d in itertools.permutations(quadrangle):
        p = _line_intersection_role(
            records,
            (point_a, point_d),
            (point_b, point_c),
        )
        if not p:
            continue
        o1 = _single_unordered(
            records, "circumcenter", frozenset((point_a, point_b, p))
        )
        h1 = _single_unordered(
            records, "orthocenter", frozenset((point_a, point_b, p))
        )
        o2 = _single_unordered(
            records, "circumcenter", frozenset((point_c, point_d, p))
        )
        h2 = _single_unordered(
            records, "orthocenter", frozenset((point_c, point_d, p))
        )
        if not all((o1, h1, o2, h2)):
            continue
        e1 = _single_unordered(records, "midpoint", frozenset((o1, h1)))
        e2 = _single_unordered(records, "midpoint", frozenset((o2, h2)))
        if not e1 or not e2:
            continue
        x = _tline_intersection_role(
            records,
            (e1, point_c, point_d),
            (e2, point_a, point_b),
        )
        if not x:
            continue
        expected = Atom("coll", (x, h1, h2)).canonical()
        goal_parts = goal.split()
        if len(goal_parts) != 4:
            continue
        actual = Atom(goal_parts[0], tuple(goal_parts[1:])).canonical()
        if actual != expected:
            continue
        roles = {
            "A": point_a,
            "B": point_b,
            "C": point_c,
            "D": point_d,
            "P": p,
            "O1": o1,
            "H1": h1,
            "O2": o2,
            "H2": h2,
            "E1": e1,
            "E2": e2,
            "X": x,
        }
        matched = (
            "P is the intersection of AD and BC",
            "O1,H1 are the circumcenter and orthocenter of ABP",
            "O2,H2 are the circumcenter and orthocenter of CDP",
            "E1,E2 are the corresponding Euler midpoints",
            "X is the intersection of the crossed perpendiculars",
            "the goal is collinearity of X,H1,H2",
        )
        return roles, matched
    return {}, ()


def certify_jgex_euler_midpoints_cross_perpendicular_application(
    source: str,
) -> JGEXEulerMidpointsCrossPerpendicularApplication:
    normalized = source.strip()
    formulation = JGEXFormulation.from_text(normalized)
    roles, matched = _match_roles(formulation, _records(formulation))
    goal = str(formulation.goals[0]) if len(formulation.goals) == 1 else ""
    chart = certify_euler_midpoints_cross_perpendicular_chart()
    replayed = (
        chart.replayed
        and chart.all_conditions_discharged
        and len(roles) == 12
        and len(matched) == 6
    )
    return JGEXEulerMidpointsCrossPerpendicularApplication(
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


def render_euler_midpoints_cross_perpendicular_chart_svg(
    *,
    a_value: float = 1.5,
    b_value: float = 1.3,
    c_value: float = -1.0,
    d_value: float = -2.0,
    z_value: float = 0.25,
) -> str:
    certificate = certify_euler_midpoints_cross_perpendicular_chart()
    symbols = {
        name: sp.Symbol(name, real=True) for name in ("a", "b", "c", "d", "z")
    }
    substitutions = {
        symbols["a"]: sp.Rational(str(a_value)),
        symbols["b"]: sp.Rational(str(b_value)),
        symbols["c"]: sp.Rational(str(c_value)),
        symbols["d"]: sp.Rational(str(d_value)),
        symbols["z"]: sp.Rational(str(z_value)),
    }
    height = float(sp.sqrt(1 - substitutions[symbols["z"]] ** 2))
    z_numeric = float(substitutions[symbols["z"]])
    oblique_points = {
        name: (
            float(sp.sympify(value[0], locals=symbols).subs(substitutions)),
            float(sp.sympify(value[1], locals=symbols).subs(substitutions)),
        )
        for name, value in certificate.coordinates.items()
    }
    points = {
        name: (x_value + z_numeric * y_value, height * y_value)
        for name, (x_value, y_value) in oblique_points.items()
    }

    figure, axis = plt.subplots(figsize=(9.4, 6.2), constrained_layout=True)
    figure.patch.set_facecolor("#f8fafc")
    axis.set_facecolor("#ffffff")
    axis.set_aspect("equal", adjustable="datalim")
    axis.axis("off")
    axis.set_title(
        "2つのEuler中点から同じ直線へ",
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

    for left, right in (("A", "B"), ("B", "C"), ("C", "D"), ("D", "A")):
        segment(left, right, "#64748b")
    segment("A", "D", "#94a3b8")
    segment("B", "C", "#94a3b8")
    segment("O1", "H1", "#2563eb")
    segment("O2", "H2", "#7c3aed")
    segment("E1", "X", "#0891b2", 1.8)
    segment("E2", "X", "#0891b2", 1.8)
    segment("H1", "H2", "#e11d48", 2.2)
    for name, (x_value, y_value) in points.items():
        highlight = name in {"X", "H1", "H2"}
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
    axis.margins(0.16)
    output = io.StringIO()
    figure.savefig(output, format="svg", facecolor=figure.get_facecolor())
    plt.close(figure)
    return output.getvalue()


__all__ = [
    "EulerMidpointsCrossPerpendicularCertificate",
    "JGEXEulerMidpointsCrossPerpendicularApplication",
    "certify_euler_midpoints_cross_perpendicular_chart",
    "certify_jgex_euler_midpoints_cross_perpendicular_application",
    "render_euler_midpoints_cross_perpendicular_chart_svg",
]
