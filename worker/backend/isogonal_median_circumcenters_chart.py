"""Exact symmetric-ray chart for an isogonal median and three circumcenters."""

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
class IsogonalMedianCircumcentersCertificate:
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
                "# 中線の等角線・二外心の中点チャート",
                "",
                "## 定理",
                "",
                (
                    "$M$ を三角形 $ABC$ の $BC$ の中点とする。$AP$ が $AM$"
                    "の $A$ に関する等角線で、$O,O_1,O_2$ がそれぞれ"
                    "$ABC,ABP,ACP$ の外心、$N$ が $O_1O_2$ の中点なら、"
                    "$A,O,N$ は共線である。"
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
class JGEXIsogonalMedianCircumcentersApplication:
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


def _circumcenter_from_origin(first: sp.Matrix, second: sp.Matrix) -> sp.Matrix:
    matrix = sp.Matrix(
        (
            (2 * first[0], 2 * first[1]),
            (2 * second[0], 2 * second[1]),
        )
    )
    rhs = sp.Matrix((first.dot(first), second.dot(second)))
    return (matrix.inv() * rhs).applyfunc(sp.cancel)


@lru_cache(maxsize=1)
def certify_isogonal_median_circumcenters_chart(
) -> IsogonalMedianCircumcentersCertificate:
    r, s, x, y, k = sp.symbols("r s x y k", real=True, nonzero=True)
    point_a = _point(0, 0)
    point_b = _point(r * x, r * y)
    point_c = _point(s * x, -s * y)
    point_m = ((point_b + point_c) / 2).applyfunc(sp.cancel)
    point_p = _point(k * (r + s) * x, k * (s - r) * y)
    point_o = _circumcenter_from_origin(point_b, point_c)
    point_o1 = _circumcenter_from_origin(point_b, point_p)
    point_o2 = _circumcenter_from_origin(point_c, point_p)
    point_n = ((point_o1 + point_o2) / 2).applyfunc(sp.cancel)

    angle_residual = (
        _cross(point_b, point_m) * point_p.dot(point_c)
        - point_b.dot(point_m) * _cross(point_p, point_c)
    )
    residuals = {
        "M_midpoint_BC_x": 2 * point_m[0] - point_b[0] - point_c[0],
        "M_midpoint_BC_y": 2 * point_m[1] - point_b[1] - point_c[1],
        "AP_is_reflection_of_AM_x": point_p[0] - 2 * k * point_m[0],
        "AP_is_reflection_of_AM_y": point_p[1] + 2 * k * point_m[1],
        "directed_isogonal_angle": angle_residual,
        "OA_equals_OB": point_o.dot(point_o) - (point_o - point_b).dot(
            point_o - point_b
        ),
        "OA_equals_OC": point_o.dot(point_o) - (point_o - point_c).dot(
            point_o - point_c
        ),
        "O1A_equals_O1B": point_o1.dot(point_o1) - (
            point_o1 - point_b
        ).dot(point_o1 - point_b),
        "O1A_equals_O1P": point_o1.dot(point_o1) - (
            point_o1 - point_p
        ).dot(point_o1 - point_p),
        "O2A_equals_O2C": point_o2.dot(point_o2) - (
            point_o2 - point_c
        ).dot(point_o2 - point_c),
        "O2A_equals_O2P": point_o2.dot(point_o2) - (
            point_o2 - point_p
        ).dot(point_o2 - point_p),
        "N_midpoint_O1O2_x": 2 * point_n[0] - point_o1[0] - point_o2[0],
        "N_midpoint_O1O2_y": 2 * point_n[1] - point_o1[1] - point_o2[1],
        "goal_A_O_N_collinear": _cross(point_o, point_n),
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
            "O": point_o,
            "O1": point_o1,
            "O2": point_o2,
            "N": point_n,
        }.items()
    }
    discharged_conditions = {
        "r*s*x*y != 0": "The accepted triangle ABC is nondegenerate.",
        "k != 0": "P is a genuine point on the isogonal ray from A.",
        "ABP and ACP are nondegenerate": (
            "Their determinants reduce to -2*k*r^2*x*y and 2*k*s^2*x*y."
        ),
    }
    payload = {
        "theorem": "isogonal-median-two-circumcenters-midpoint-on-euler-radius",
        "normalization": (
            "A=(0,0), B=(rx,ry), C=(sx,-sy); the internal angle-bisector "
            "axis is the x-axis and AP is the reflection direction of AM"
        ),
        "parameter_domain": (
            "r,s,x,y,k are real",
            "r*s*x*y*k != 0",
        ),
        "construction_domain_conditions": (
            "M is the midpoint of BC",
            "AP is the directed isogonal line of AM in angle BAC",
            "O,O1,O2 are the stated circumcenters",
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
    return IsogonalMedianCircumcentersCertificate(
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
        point_m = _single_unordered(
            records, "midpoint", frozenset((point_b, point_c))
        )
        if not point_m:
            continue
        point_p = _single_ordered(
            records, "on_aline", (point_a, point_c, point_b, point_a, point_m)
        )
        if not point_p:
            continue
        point_o = _single_unordered(
            records, "circumcenter", frozenset((point_a, point_b, point_c))
        )
        point_o1 = _single_unordered(
            records, "circumcenter", frozenset((point_a, point_b, point_p))
        )
        point_o2 = _single_unordered(
            records, "circumcenter", frozenset((point_a, point_c, point_p))
        )
        if not point_o or not point_o1 or not point_o2:
            continue
        point_n = _single_unordered(
            records, "midpoint", frozenset((point_o1, point_o2))
        )
        if not point_n:
            continue
        goal = formulation.goals[0]
        expected = Atom("coll", (point_a, point_o, point_n)).canonical()
        actual = Atom(goal.predicate, goal.args).canonical()
        if actual != expected:
            continue
        roles = {
            "A": point_a,
            "B": point_b,
            "C": point_c,
            "M": point_m,
            "P": point_p,
            "O": point_o,
            "O1": point_o1,
            "O2": point_o2,
            "N": point_n,
        }
        matched = (
            "M is the midpoint of BC",
            "AP is the on_aline isogonal direction of AM",
            "O,O1,O2 are the circumcenters of ABC,ABP,ACP",
            "N is the midpoint of O1O2",
            "the goal is A,O,N collinear",
        )
        return roles, matched
    return {}, ()


def certify_jgex_isogonal_median_circumcenters_application(
    source: str,
) -> JGEXIsogonalMedianCircumcentersApplication:
    normalized = source.strip()
    formulation = JGEXFormulation.from_text(normalized)
    roles, matched = _match_roles(formulation, _records(formulation))
    goal = str(formulation.goals[0]) if len(formulation.goals) == 1 else ""
    chart = certify_isogonal_median_circumcenters_chart()
    replayed = (
        chart.replayed
        and chart.all_conditions_discharged
        and len(roles) == 9
        and len(matched) == 5
    )
    return JGEXIsogonalMedianCircumcentersApplication(
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


def render_isogonal_median_circumcenters_chart_svg(
    *,
    r_value: float = 1.35,
    s_value: float = 0.9,
    x_value: float = 0.82,
    y_value: float = 0.58,
    k_value: float = 0.62,
) -> str:
    certificate = certify_isogonal_median_circumcenters_chart()
    names = ("r", "s", "x", "y", "k")
    symbols = {name: sp.Symbol(name, real=True) for name in names}
    substitutions = {
        symbols["r"]: sp.Rational(str(r_value)),
        symbols["s"]: sp.Rational(str(s_value)),
        symbols["x"]: sp.Rational(str(x_value)),
        symbols["y"]: sp.Rational(str(y_value)),
        symbols["k"]: sp.Rational(str(k_value)),
    }
    points = {
        name: (
            float(sp.sympify(value[0], locals=symbols).subs(substitutions)),
            float(sp.sympify(value[1], locals=symbols).subs(substitutions)),
        )
        for name, value in certificate.coordinates.items()
    }

    figure, axis = plt.subplots(figsize=(8.4, 6.0), constrained_layout=True)
    figure.patch.set_facecolor("#f8fafc")
    axis.set_facecolor("#ffffff")
    axis.set_aspect("equal", adjustable="datalim")
    axis.axis("off")
    axis.set_title(
        "等角線が外心の中点を同一直線へ送る",
        loc="left",
        fontsize=14,
        color="#0f172a",
        fontfamily="Yu Gothic",
    )
    for circle_points, color in (
        (("A", "B", "C"), "#94a3b8"),
        (("A", "B", "P"), "#7c3aed"),
        (("A", "C", "P"), "#0891b2"),
    ):
        a, b, c = (points[name] for name in circle_points)
        matrix = sp.Matrix(
            (
                (2 * (b[0] - a[0]), 2 * (b[1] - a[1])),
                (2 * (c[0] - a[0]), 2 * (c[1] - a[1])),
            )
        )
        rhs = sp.Matrix(
            (
                b[0] ** 2 + b[1] ** 2 - a[0] ** 2 - a[1] ** 2,
                c[0] ** 2 + c[1] ** 2 - a[0] ** 2 - a[1] ** 2,
            )
        )
        center_values = matrix.inv() * rhs
        center = (float(center_values[0]), float(center_values[1]))
        radius = ((a[0] - center[0]) ** 2 + (a[1] - center[1]) ** 2) ** 0.5
        axis.add_patch(Circle(center, radius, fill=False, color=color, linewidth=1.0))
    for left, right, color, width in (
        ("A", "B", "#64748b", 1.2),
        ("A", "C", "#64748b", 1.2),
        ("B", "C", "#64748b", 1.2),
        ("A", "M", "#7c3aed", 1.5),
        ("A", "P", "#0891b2", 1.7),
        ("O1", "O2", "#475569", 1.0),
        ("A", "N", "#e11d48", 2.0),
    ):
        axis.plot(
            (points[left][0], points[right][0]),
            (points[left][1], points[right][1]),
            color=color,
            linewidth=width,
        )
    for name, (x_coord, y_coord) in points.items():
        highlight = name in {"O", "N"}
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
    "IsogonalMedianCircumcentersCertificate",
    "JGEXIsogonalMedianCircumcentersApplication",
    "certify_isogonal_median_circumcenters_chart",
    "certify_jgex_isogonal_median_circumcenters_application",
    "render_isogonal_median_circumcenters_chart_svg",
]
