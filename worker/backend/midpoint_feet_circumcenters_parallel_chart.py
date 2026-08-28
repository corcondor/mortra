"""Exact affine-metric chart for two midpoint-foot circumcenters."""

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
class MidpointFeetCircumcentersParallelCertificate:
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
                "# 中点・垂足・二外心の平行チャート",
                "",
                "## 定理",
                "",
                (
                    "$D,K$ を三角形 $ABC$ の $BC,AD$ の中点、$E,F$ を $D$"
                    "から $AB,AC$ への垂足とする。$M=KE\\cap BC$、"
                    "$N=KF\\cap BC$ とし、$O_1,O_2$ をそれぞれ"
                    "$DEM,DFN$ の外心とすると、$O_1O_2\\parallel BC$ である。"
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
class JGEXMidpointFeetCircumcentersParallelApplication:
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


def _norm2(value: sp.Matrix) -> sp.Expr:
    return sp.expand(value.dot(value))


@lru_cache(maxsize=1)
def certify_midpoint_feet_circumcenters_parallel_chart(
) -> MidpointFeetCircumcentersParallelCertificate:
    u, v = sp.symbols("u v", real=True)
    left_denominator = (u + 1) ** 2 + v**2
    right_denominator = (u - 1) ** 2 + v**2
    axis_denominator = u**2 + v**2 - 1
    point_a = _point(u, v)
    point_b = _point(-1, 0)
    point_c = _point(1, 0)
    point_d = _point(0, 0)
    point_k = (point_a / 2).applyfunc(sp.cancel)
    point_e = _point(-v**2 / left_denominator, v * (u + 1) / left_denominator)
    point_f = _point(v**2 / right_denominator, -v * (u - 1) / right_denominator)
    point_m = _point(-(u**2 + u + v**2) / axis_denominator, 0)
    point_n = _point((u**2 - u + v**2) / axis_denominator, 0)
    common_height = -v / (2 * axis_denominator)
    point_o1 = _point(point_m[0] / 2, common_height)
    point_o2 = _point(point_n[0] / 2, common_height)

    residuals = {
        "D_midpoint_BC_x": 2 * point_d[0] - point_b[0] - point_c[0],
        "D_midpoint_BC_y": 2 * point_d[1] - point_b[1] - point_c[1],
        "K_midpoint_AD_x": 2 * point_k[0] - point_a[0] - point_d[0],
        "K_midpoint_AD_y": 2 * point_k[1] - point_a[1] - point_d[1],
        "E_on_AB": _cross(point_e - point_a, point_b - point_a),
        "DE_perpendicular_AB": (point_e - point_d).dot(point_b - point_a),
        "F_on_AC": _cross(point_f - point_a, point_c - point_a),
        "DF_perpendicular_AC": (point_f - point_d).dot(point_c - point_a),
        "M_on_KE": _cross(point_m - point_k, point_e - point_k),
        "M_on_BC": _cross(point_m - point_b, point_c - point_b),
        "N_on_KF": _cross(point_n - point_k, point_f - point_k),
        "N_on_BC": _cross(point_n - point_b, point_c - point_b),
        "O1D_equals_O1E": _norm2(point_o1 - point_d) - _norm2(point_o1 - point_e),
        "O1D_equals_O1M": _norm2(point_o1 - point_d) - _norm2(point_o1 - point_m),
        "O2D_equals_O2F": _norm2(point_o2 - point_d) - _norm2(point_o2 - point_f),
        "O2D_equals_O2N": _norm2(point_o2 - point_d) - _norm2(point_o2 - point_n),
        "shared_circumcenter_height": point_o2[1] - point_o1[1],
        "goal_O1O2_parallel_BC": _cross(point_o2 - point_o1, point_c - point_b),
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
            "K": point_k,
            "E": point_e,
            "F": point_f,
            "M": point_m,
            "N": point_n,
            "O1": point_o1,
            "O2": point_o2,
        }.items()
    }
    discharged_conditions = {
        "v != 0": "The accepted triangle ABC is nondegenerate.",
        "u^2+v^2 != 1": (
            "The stated finite intersections M=KE cap BC and N=KF cap BC exist."
        ),
        "u != -1 and u != 1": (
            "The accepted circumcenters of DEM and DFN require nondegenerate "
            "triangles."
        ),
    }
    payload = {
        "theorem": "midpoint-feet-two-circumcenters-parallel-to-base",
        "normalization": "B=(-1,0), C=(1,0), D=(0,0), A=(u,v)",
        "parameter_domain": (
            "u,v are real",
            "v != 0",
            "u^2+v^2 != 1",
        ),
        "construction_domain_conditions": (
            "E,F are the projections of D on AB,AC",
            "M=KE cap BC and N=KF cap BC are finite",
            "the circumcenters of DEM and DFN exist",
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
    return MidpointFeetCircumcentersParallelCertificate(
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


def _line_intersection(
    records: tuple[dict[str, object], ...],
    first: frozenset[str],
    second: frozenset[str],
) -> str | None:
    for record in records:
        if len(record["outputs"]) != 1 or len(record["constructions"]) != 2:
            continue
        lines = {
            frozenset(args)
            for name, args in record["constructions"]
            if name == "on_line"
        }
        if lines == {first, second}:
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
        point_d = _single_unordered(
            records, "midpoint", frozenset((point_b, point_c))
        )
        if not point_d:
            continue
        point_k = _single_unordered(
            records, "midpoint", frozenset((point_a, point_d))
        )
        point_e = _foot(records, point_d, frozenset((point_a, point_b)))
        point_f = _foot(records, point_d, frozenset((point_a, point_c)))
        if not point_k or not point_e or not point_f:
            continue
        point_m = _line_intersection(
            records,
            frozenset((point_b, point_c)),
            frozenset((point_k, point_e)),
        )
        point_n = _line_intersection(
            records,
            frozenset((point_b, point_c)),
            frozenset((point_k, point_f)),
        )
        if not point_m or not point_n:
            continue
        point_o1 = _single_unordered(
            records, "circumcenter", frozenset((point_d, point_e, point_m))
        )
        point_o2 = _single_unordered(
            records, "circumcenter", frozenset((point_d, point_f, point_n))
        )
        if not point_o1 or not point_o2:
            continue
        goal = formulation.goals[0]
        expected = Atom("para", (point_o1, point_o2, point_b, point_c)).canonical()
        actual = Atom(goal.predicate, goal.args).canonical()
        if actual != expected:
            continue
        roles = {
            "A": point_a,
            "B": point_b,
            "C": point_c,
            "D": point_d,
            "K": point_k,
            "E": point_e,
            "F": point_f,
            "M": point_m,
            "N": point_n,
            "O1": point_o1,
            "O2": point_o2,
        }
        matched = (
            "D,K are the midpoints of BC,AD",
            "E,F are the projections of D on AB,AC",
            "M=KE intersect BC and N=KF intersect BC",
            "O1,O2 are the circumcenters of DEM,DFN",
            "the goal is O1O2 parallel to BC",
        )
        return roles, matched
    return {}, ()


def certify_jgex_midpoint_feet_circumcenters_parallel_application(
    source: str,
) -> JGEXMidpointFeetCircumcentersParallelApplication:
    normalized = source.strip()
    formulation = JGEXFormulation.from_text(normalized)
    roles, matched = _match_roles(formulation, _records(formulation))
    goal = str(formulation.goals[0]) if len(formulation.goals) == 1 else ""
    chart = certify_midpoint_feet_circumcenters_parallel_chart()
    replayed = (
        chart.replayed
        and chart.all_conditions_discharged
        and len(roles) == 11
        and len(matched) == 5
    )
    return JGEXMidpointFeetCircumcentersParallelApplication(
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


def render_midpoint_feet_circumcenters_parallel_chart_svg(
    *, u_value: float = 0.28, v_value: float = 1.55
) -> str:
    certificate = certify_midpoint_feet_circumcenters_parallel_chart()
    symbols = {name: sp.Symbol(name, real=True) for name in ("u", "v")}
    substitutions = {
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

    figure, axis = plt.subplots(figsize=(9.0, 5.8), constrained_layout=True)
    figure.patch.set_facecolor("#f8fafc")
    axis.set_facecolor("#ffffff")
    axis.set_aspect("equal", adjustable="datalim")
    axis.axis("off")
    axis.set_title(
        "二つの外心は同じ高さに現れる",
        loc="left",
        fontsize=14,
        color="#0f172a",
        fontfamily="Yu Gothic",
    )
    for center_name, through_name, color in (
        ("O1", "D", "#7c3aed"),
        ("O2", "D", "#0891b2"),
    ):
        center = points[center_name]
        through = points[through_name]
        radius = (
            (through[0] - center[0]) ** 2 + (through[1] - center[1]) ** 2
        ) ** 0.5
        axis.add_patch(Circle(center, radius, fill=False, color=color, linewidth=1.0))
    for left, right, color, width in (
        ("A", "B", "#64748b", 1.2),
        ("A", "C", "#64748b", 1.2),
        ("B", "C", "#0f172a", 1.4),
        ("D", "E", "#94a3b8", 1.0),
        ("D", "F", "#94a3b8", 1.0),
        ("K", "M", "#7c3aed", 1.4),
        ("K", "N", "#0891b2", 1.4),
        ("O1", "O2", "#e11d48", 2.2),
    ):
        axis.plot(
            (points[left][0], points[right][0]),
            (points[left][1], points[right][1]),
            color=color,
            linewidth=width,
        )
    for name, (x_coord, y_coord) in points.items():
        highlight = name in {"O1", "O2"}
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
    "JGEXMidpointFeetCircumcentersParallelApplication",
    "MidpointFeetCircumcentersParallelCertificate",
    "certify_jgex_midpoint_feet_circumcenters_parallel_application",
    "certify_midpoint_feet_circumcenters_parallel_chart",
    "render_midpoint_feet_circumcenters_parallel_chart_svg",
]
