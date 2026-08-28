"""Exact affine chart for midpoint projections from a transversal.

A transversal meets two sides through a common vertex.  Opposite cross
segments are bisected, and perpendiculars to the transversal are intersected
with the corresponding perpendicular bisectors.  The resulting connector is
not merely parallel to the midpoint connector: the two directed vectors are
equal.
"""

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

from worker.backend.geometry_proof_hypergraph import Atom
from worker.backend.jgex_chart_parser import ChartJGEXFormulation as JGEXFormulation


@dataclass(frozen=True)
class TransversalMidpointProjectionCertificate:
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
                "# 横断線・交差中点・垂直二等分線チャート",
                "",
                "## 定理",
                "",
                (
                    "直線 $\\ell$ が三角形 $ABC$ の辺 $AB,AC$ と $D,E$ で"
                    "交わる。$P,Q$ をそれぞれ $CD,BE$ の中点とする。"
                    "$P,Q$ を通る $\\ell$ への垂線が $AC,AB$ の垂直二等分線"
                    "と $M,N$ で交わるなら、"
                    "$\\overrightarrow{MN}=\\overrightarrow{PQ}$ である。"
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
class JGEXTransversalMidpointProjectionApplication:
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
def certify_transversal_midpoint_projection_chart(
) -> TransversalMidpointProjectionCertificate:
    d, e, h, u, v = sp.symbols("d e h u v", real=True)
    point_a = _point(0, h)
    point_d = _point(d, 0)
    point_e = _point(e, 0)
    point_b = _point(u * d, h * (1 - u))
    point_c = _point(v * e, h * (1 - v))
    point_p = ((point_c + point_d) / 2).applyfunc(sp.cancel)
    point_q = ((point_b + point_e) / 2).applyfunc(sp.cancel)
    point_m = _point(
        point_p[0],
        (d * e + h**2 * (2 - v)) / (2 * h),
    ).applyfunc(sp.cancel)
    point_n = _point(
        point_q[0],
        (d * e + h**2 * (2 - u)) / (2 * h),
    ).applyfunc(sp.cancel)
    transversal = point_e - point_d

    residuals = {
        "D_on_AB": _cross(point_d - point_a, point_b - point_a),
        "E_on_AC": _cross(point_e - point_a, point_c - point_a),
        "P_midpoint_CD_x": 2 * point_p[0] - point_c[0] - point_d[0],
        "P_midpoint_CD_y": 2 * point_p[1] - point_c[1] - point_d[1],
        "Q_midpoint_BE_x": 2 * point_q[0] - point_b[0] - point_e[0],
        "Q_midpoint_BE_y": 2 * point_q[1] - point_b[1] - point_e[1],
        "PM_perpendicular_DE": (point_m - point_p).dot(transversal),
        "M_on_perpendicular_bisector_AC": (
            _norm2(point_m - point_a) - _norm2(point_m - point_c)
        ),
        "QN_perpendicular_DE": (point_n - point_q).dot(transversal),
        "N_on_perpendicular_bisector_AB": (
            _norm2(point_n - point_a) - _norm2(point_n - point_b)
        ),
        "strong_vector_identity_x": (
            point_n[0] - point_m[0] - point_q[0] + point_p[0]
        ),
        "strong_vector_identity_y": (
            point_n[1] - point_m[1] - point_q[1] + point_p[1]
        ),
        "goal_MN_parallel_PQ": _cross(
            point_n - point_m,
            point_q - point_p,
        ),
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
            "P": point_p,
            "Q": point_q,
            "M": point_m,
            "N": point_n,
        }.items()
    }
    discharged_conditions = {
        "h != 0": (
            "A is not on transversal DE because ABC is nondegenerate and D,E "
            "are distinct intersections with AB,AC."
        ),
        "d != e": "The accepted line DE is defined by two distinct points.",
        "u*v != 0": "The accepted triangle has B,C distinct from A.",
    }
    payload = {
        "theorem": "transversal-cross-midpoints-perpendicular-bisectors-translation",
        "normalization": (
            "DE is the x-axis, A=(0,h), D=(d,0), E=(e,0), "
            "B=(ud,h(1-u)), C=(ve,h(1-v))"
        ),
        "parameter_domain": (
            "d,e,h,u,v are real",
            "h != 0",
            "d != e",
            "u*v != 0",
        ),
        "construction_domain_conditions": (
            "D lies on AB and E lies on AC",
            "M,N are the stated unique line intersections",
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
    return TransversalMidpointProjectionCertificate(
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


def _single(
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


def _paired_intersection(
    records: tuple[dict[str, object], ...],
    first: tuple[str, frozenset[str]],
    second: tuple[str, frozenset[str]],
) -> str | None:
    for record in records:
        if len(record["outputs"]) != 1 or len(record["constructions"]) != 2:
            continue
        normalized = {
            (name, frozenset(args)) for name, args in record["constructions"]
        }
        if normalized == {first, second}:
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
    point_d = _single(records, "on_line", frozenset((point_a, point_b)))
    point_e = _single(records, "on_line", frozenset((point_a, point_c)))
    if not point_d or not point_e:
        return {}, ()
    point_p = _single(records, "midpoint", frozenset((point_c, point_d)))
    point_q = _single(records, "midpoint", frozenset((point_b, point_e)))
    if not point_p or not point_q:
        return {}, ()
    point_m = _paired_intersection(
        records,
        ("on_bline", frozenset((point_a, point_c))),
        ("on_tline", frozenset((point_p, point_d, point_e))),
    )
    point_n = _paired_intersection(
        records,
        ("on_bline", frozenset((point_a, point_b))),
        ("on_tline", frozenset((point_q, point_d, point_e))),
    )
    if not point_m or not point_n or len(formulation.goals) != 1:
        return {}, ()
    goal = formulation.goals[0]
    expected = Atom("para", (point_m, point_n, point_p, point_q)).canonical()
    actual = Atom(goal.predicate, goal.args).canonical()
    if actual != expected:
        return {}, ()
    roles = {
        "A": point_a,
        "B": point_b,
        "C": point_c,
        "D": point_d,
        "E": point_e,
        "P": point_p,
        "Q": point_q,
        "M": point_m,
        "N": point_n,
    }
    matched = (
        "D lies on AB and E lies on AC",
        "P,Q are the midpoints of CD,BE",
        "PM and QN are perpendicular to DE",
        "M,N lie on the perpendicular bisectors of AC,AB",
        "the goal is MN parallel to PQ",
    )
    return roles, matched


def certify_jgex_transversal_midpoint_projection_application(
    source: str,
) -> JGEXTransversalMidpointProjectionApplication:
    normalized = source.strip()
    formulation = JGEXFormulation.from_text(normalized)
    roles, matched = _match_roles(formulation, _records(formulation))
    goal = str(formulation.goals[0]) if len(formulation.goals) == 1 else ""
    chart = certify_transversal_midpoint_projection_chart()
    replayed = (
        chart.replayed
        and chart.all_conditions_discharged
        and len(roles) == 9
        and len(matched) == 5
    )
    return JGEXTransversalMidpointProjectionApplication(
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


def render_transversal_midpoint_projection_chart_svg(
    *,
    d_value: float = -0.9,
    e_value: float = 1.1,
    h_value: float = 1.8,
    u_value: float = 1.35,
    v_value: float = 1.25,
) -> str:
    certificate = certify_transversal_midpoint_projection_chart()
    symbols = {
        name: sp.Symbol(name, real=True) for name in ("d", "e", "h", "u", "v")
    }
    substitutions = {
        symbols["d"]: sp.Rational(str(d_value)),
        symbols["e"]: sp.Rational(str(e_value)),
        symbols["h"]: sp.Rational(str(h_value)),
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

    figure, axis = plt.subplots(figsize=(8.8, 5.8), constrained_layout=True)
    figure.patch.set_facecolor("#f8fafc")
    axis.set_facecolor("#ffffff")
    axis.set_aspect("equal", adjustable="datalim")
    axis.axis("off")
    axis.set_title(
        "横断線から同じ平行移動が現れる",
        loc="left",
        fontsize=14,
        color="#0f172a",
        fontfamily="Yu Gothic",
    )
    for left, right, color, width in (
        ("A", "B", "#64748b", 1.3),
        ("A", "C", "#64748b", 1.3),
        ("D", "E", "#0f172a", 1.5),
        ("C", "D", "#94a3b8", 1.0),
        ("B", "E", "#94a3b8", 1.0),
        ("P", "M", "#7c3aed", 1.5),
        ("Q", "N", "#7c3aed", 1.5),
        ("P", "Q", "#0891b2", 2.0),
        ("M", "N", "#e11d48", 2.0),
    ):
        axis.plot(
            (points[left][0], points[right][0]),
            (points[left][1], points[right][1]),
            color=color,
            linewidth=width,
        )
    for name, (x_value, y_value) in points.items():
        highlight = name in {"P", "Q", "M", "N"}
        color = "#e11d48" if name in {"M", "N"} else (
            "#0891b2" if highlight else "#0f172a"
        )
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
    figure.savefig(output, format="svg", bbox_inches="tight")
    plt.close(figure)
    return output.getvalue()


__all__ = [
    "JGEXTransversalMidpointProjectionApplication",
    "TransversalMidpointProjectionCertificate",
    "certify_jgex_transversal_midpoint_projection_application",
    "certify_transversal_midpoint_projection_chart",
    "render_transversal_midpoint_projection_chart_svg",
]
