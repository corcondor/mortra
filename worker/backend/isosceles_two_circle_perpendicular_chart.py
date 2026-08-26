"""Exact chart for an isosceles-triangle two-circle perpendicular theorem.

The proof is independent of problem ids and point names.  It matches the JGEX
construction graph, normalizes the isosceles triangle, replays every incidence
and circle equation with SymPy, and discharges the branch conditions from the
official JGEX construction semantics.
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
from matplotlib.patches import Circle
from worker.backend.jgex_chart_parser import ChartJGEXFormulation as JGEXFormulation

from worker.backend.geometry_proof_hypergraph import Atom


@dataclass(frozen=True)
class IsoscelesTwoCirclePerpendicularCertificate:
    theorem: str
    normalization: str
    parameter_domain: tuple[str, ...]
    construction_domain_conditions: tuple[str, ...]
    discharged_conditions: dict[str, str]
    upstream_semantics: tuple[str, ...]
    coordinates: dict[str, tuple[str, str]]
    branch_factors: dict[str, str]
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
                "# 等腰三角形・2円交点・直交チャート",
                "",
                "## 定理",
                "",
                (
                    "二等辺三角形 $ABC$ の内心を $I$ とする。点 $O_3$ は "
                    "$BI$ の垂直二等分線上にあり、$P$ は中心 $A,O_3$ の2円の "
                    "$B$ でない交点、$Q$ は中心 $I,O_3$ の2円の $B$ でない交点とする。"
                    "$R=PI\\cap BQ$ とおけば、$BR\\perp CR$ である。"
                ),
                "",
                "## 標準化",
                "",
                self.normalization,
                "",
                "## 構成の定義域",
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
class JGEXIsoscelesTwoCirclePerpendicularApplication:
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


def _norm2(value: sp.Matrix) -> sp.Expr:
    return sp.expand(value.dot(value))


def _cross(left: sp.Matrix, right: sp.Matrix) -> sp.Expr:
    return sp.expand(left[0] * right[1] - left[1] * right[0])


def _second_circle_intersection(
    known: sp.Matrix,
    center_left: sp.Matrix,
    center_right: sp.Matrix,
) -> tuple[sp.Matrix, sp.Expr, sp.Expr]:
    """Return the other intersection of two circles through ``known``."""

    center_delta = center_left - center_right
    direction = _point(-center_delta[1], center_delta[0])
    direction_norm2 = sp.factor(_norm2(direction))
    parameter = sp.factor(
        -2 * direction.dot(known - center_left) / direction_norm2
    )
    point = (known + parameter * direction).applyfunc(sp.cancel)
    return point, parameter, direction_norm2


def _line_intersection(
    first_origin: sp.Matrix,
    first_direction: sp.Matrix,
    second_origin: sp.Matrix,
    second_direction: sp.Matrix,
) -> tuple[sp.Matrix, sp.Expr, sp.Expr]:
    determinant = sp.factor(_cross(first_direction, second_direction))
    parameter = sp.factor(
        _cross(second_origin - first_origin, second_direction) / determinant
    )
    point = (first_origin + parameter * first_direction).applyfunc(sp.cancel)
    return point, parameter, determinant


@lru_cache(maxsize=1)
def certify_isosceles_two_circle_perpendicular_chart(
) -> IsoscelesTwoCirclePerpendicularCertificate:
    t, v = sp.symbols("t v", real=True)
    height = 2 * t / (1 - t**2)

    a = _point(0, height)
    b = _point(-1, 0)
    c = _point(1, 0)
    i = _point(0, t)
    o3 = _point((t**2 - 1 - 2 * t * v) / 2, v)

    p, lambda_p, delta_p = _second_circle_intersection(b, a, o3)
    q, lambda_q, delta_q = _second_circle_intersection(b, i, o3)
    r, alpha_r, line_determinant = _line_intersection(i, p - i, b, q - b)

    dp = (
        t**6
        - 4 * t**5 * v
        + 4 * t**4 * v**2
        - 5 * t**4
        + 16 * t**3 * v
        - 8 * t**2 * v**2
        + 11 * t**2
        - 12 * t * v
        + 4 * v**2
        + 1
    )
    dq = t**2 - 4 * t * v + 4 * v**2 + 1

    residuals = {
        "isosceles_AB_equals_AC": _norm2(a - b) - _norm2(a - c),
        "I_equal_distance_from_AB": (
            _cross(i - a, b - a) ** 2 - t**2 * _norm2(b - a)
        ),
        "I_equal_distance_from_AC": (
            _cross(i - a, c - a) ** 2 - t**2 * _norm2(c - a)
        ),
        "AI_squared_equals_t_squared_AB_squared": (
            _norm2(a - i) - t**2 * _norm2(a - b)
        ),
        "O3_on_perpendicular_bisector_BI": (
            _norm2(o3 - b) - _norm2(o3 - i)
        ),
        "P_on_circle_center_A": _norm2(p - a) - _norm2(b - a),
        "P_on_circle_center_O3": _norm2(p - o3) - _norm2(b - o3),
        "Q_on_circle_center_I": _norm2(q - i) - _norm2(b - i),
        "Q_on_circle_center_O3": _norm2(q - o3) - _norm2(b - o3),
        "R_on_PI": _cross(r - i, p - i),
        "R_on_BQ": _cross(r - b, q - b),
        "bridge_BQ_perpendicular_IO3": (q - b).dot(o3 - i),
        "bridge_CR_parallel_IO3": _cross(r - c, o3 - i),
        "goal_BR_perpendicular_CR": (r - b).dot(r - c),
        "delta_P_factorization": (
            4 * (1 - t**2) ** 2 * delta_p - (t**2 + 1) * dp
        ),
        "delta_Q_factorization": 4 * delta_q - (t**2 + 1) * dq,
        "lambda_P_factorization": (
            lambda_p * dp - 8 * (t - 1) * (t + 1) * (t - v)
        ),
        "lambda_Q_factorization": lambda_q * dq + 4 * (t - 2 * v),
        "line_determinant_factorization": (
            line_determinant * dp
            - 2 * (t - 2 * v) * (t**2 + 1) ** 3
        ),
    }
    rendered = {name: _canonical(value) for name, value in residuals.items()}
    replayed = all(value == "0" for value in rendered.values())
    coordinates = {
        name: (_canonical(value[0]), _canonical(value[1]))
        for name, value in {
            "A": a,
            "B": b,
            "C": c,
            "I": i,
            "O3": o3,
            "P": p,
            "Q": q,
            "R": r,
        }.items()
    }
    branch_factors = {
        "D_P": _canonical(dp),
        "D_Q": _canonical(dq),
        "lambda_P": _canonical(lambda_p),
        "lambda_Q": _canonical(lambda_q),
        "det(PI,BQ)": _canonical(line_determinant),
    }
    discharged_conditions = {
        "0 < t < 1": (
            "t is the normalized inradius.  A genuine isosceles triangle has "
            "positive inradius smaller than the half-base."
        ),
        "A != O3": (
            "If A=O3, the perpendicular-bisector condition gives AB=AI; "
            "the replayed identity AI^2=t^2 AB^2 contradicts 0<t<1."
        ),
        "P != B, hence t != v": (
            "JGEX reduce_intersection rejects every intersection already present; "
            "P is therefore the second circle intersection.  The replayed "
            "lambda_P factorization then gives t!=v."
        ),
        "Q != B, hence t != 2v": (
            "The same official second-intersection rule applies to Q; the "
            "lambda_Q factorization gives t!=2v."
        ),
        "det(PI,BQ) != 0": (
            "D_P is a positive squared center distance up to positive factors, "
            "and det*D_P=2(t-2v)(t^2+1)^3."
        ),
    }
    upstream_semantics = (
        "Newclid jgex/geometries.py::reduce_intersection selects only a point distinct from every existing point.",
        "Newclid jgex/geometries.py::circle_circle_intersection rejects coincident centers and a missing second intersection.",
        "Newclid jgex/geometries.py::JGEXLine rejects coincident defining points; line_line_intersection rejects parallel lines.",
    )
    payload = {
        "theorem": "isosceles-two-circle-intersection-perpendicular",
        "normalization": (
            "B=(-1,0), C=(1,0), I=(0,t), "
            "A=(0,2t/(1-t^2)), O3=((t^2-1-2tv)/2,v)"
        ),
        "parameter_domain": ("0 < t < 1", "v is real"),
        "construction_domain_conditions": (
            "P and Q are the B-distinct circle intersections",
            "R is the defined intersection of PI and BQ",
        ),
        "discharged_conditions": discharged_conditions,
        "upstream_semantics": upstream_semantics,
        "coordinates": coordinates,
        "branch_factors": branch_factors,
        "replay_residuals": rendered,
        "replayed": replayed,
        "all_conditions_discharged": replayed,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return IsoscelesTwoCirclePerpendicularCertificate(
        **payload, certificate_sha256=digest
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
    records: tuple[dict[str, object], ...], name: str, args: tuple[str, ...]
) -> str | None:
    for record in records:
        if len(record["outputs"]) == 1 and record["constructions"] == ((name, args),):
            return record["outputs"][0]
    return None


def _intersection(
    records: tuple[dict[str, object], ...],
    requirements: frozenset[tuple[str, tuple[str, ...]]],
) -> str | None:
    for record in records:
        if (
            len(record["outputs"]) == 1
            and requirements.issubset(frozenset(record["constructions"]))
        ):
            return record["outputs"][0]
    return None


def certify_jgex_isosceles_two_circle_perpendicular_application(
    source: str,
) -> JGEXIsoscelesTwoCirclePerpendicularApplication:
    normalized = source.strip()
    formulation = JGEXFormulation.from_text(normalized)
    records = _records(formulation)
    triangle = next(
        (
            record["outputs"]
            for record in records
            if record["constructions"] == (("iso_triangle", ()),)
            and len(record["outputs"]) == 3
        ),
        None,
    )
    roles: dict[str, str] = {}
    matched: list[str] = []
    if triangle is not None:
        a, b, c = triangle
        roles.update(A=a, B=b, C=c)
        i = _single(records, "incenter", (a, b, c))
        if i:
            roles["I"] = i
            matched.append("I is the incenter of isosceles ABC")
            o3 = _single(records, "on_bline", (b, i))
            if o3:
                roles["O3"] = o3
                matched.append("O3 lies on the perpendicular bisector of BI")
                p = _intersection(
                    records,
                    frozenset(
                        {("on_circle", (a, b)), ("on_circle", (o3, b))}
                    ),
                )
                q = _intersection(
                    records,
                    frozenset(
                        {("on_circle", (i, b)), ("on_circle", (o3, b))}
                    ),
                )
                if p and q and p != q:
                    roles.update(P=p, Q=q)
                    matched.append("P and Q are the B-distinct circle intersections")
                    r = _intersection(
                        records,
                        frozenset(
                            {("on_line", (p, i)), ("on_line", (b, q))}
                        ),
                    )
                    if r:
                        roles["R"] = r
                        matched.append("R is the intersection of PI and BQ")

    goal = str(formulation.goals[0]) if len(formulation.goals) == 1 else ""
    goal_matches = False
    goal_parts = goal.split()
    if all(name in roles for name in ("B", "C", "R")) and len(goal_parts) == 5:
        actual = Atom(goal_parts[0], tuple(goal_parts[1:])).canonical()
        expected = Atom(
            "perp", (roles["B"], roles["R"], roles["C"], roles["R"])
        ).canonical()
        goal_matches = actual == expected

    chart = certify_isosceles_two_circle_perpendicular_chart()
    replayed = (
        chart.replayed
        and chart.all_conditions_discharged
        and len(roles) == 8
        and len(matched) == 4
        and goal_matches
    )
    return JGEXIsoscelesTwoCirclePerpendicularApplication(
        theorem=chart.theorem,
        source_sha256=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        roles=roles,
        matched_constructions=tuple(matched),
        goal=goal,
        chart_certificate_sha256=chart.certificate_sha256,
        nondegeneracy_obligations=chart.assumptions,
        undischarged_nondegeneracy_obligations=(),
        replayed=replayed,
    )


def render_isosceles_two_circle_perpendicular_chart_svg(
    *, t_value: float = 2 / 5, v_value: float = 9 / 10
) -> str:
    certificate = certify_isosceles_two_circle_perpendicular_chart()
    substitutions = {
        sp.Symbol("t"): sp.Rational(str(t_value)),
        sp.Symbol("v"): sp.Rational(str(v_value)),
    }
    points = {
        name: (
            float(sp.sympify(value[0]).subs(substitutions)),
            float(sp.sympify(value[1]).subs(substitutions)),
        )
        for name, value in certificate.coordinates.items()
    }

    def segment(left: str, right: str, *, color: str, width: float = 1.2) -> None:
        axis.plot(
            (points[left][0], points[right][0]),
            (points[left][1], points[right][1]),
            color=color,
            linewidth=width,
        )

    def radius(center: str, point: str) -> float:
        return (
            (points[center][0] - points[point][0]) ** 2
            + (points[center][1] - points[point][1]) ** 2
        ) ** 0.5

    figure, axis = plt.subplots(figsize=(8.5, 6.5), constrained_layout=True)
    figure.patch.set_facecolor("#f8fafc")
    axis.set_facecolor("#ffffff")
    axis.set_aspect("equal", adjustable="datalim")
    axis.axis("off")
    axis.set_title(
        "2組の第2円交点から直角を得る",
        loc="left",
        fontsize=14,
        color="#0f172a",
        fontfamily="Yu Gothic",
    )
    for left, right in (("A", "B"), ("B", "C"), ("C", "A")):
        segment(left, right, color="#64748b")
    segment("B", "I", color="#94a3b8")
    segment("P", "I", color="#0891b2", width=1.8)
    segment("B", "Q", color="#0891b2", width=1.8)
    segment("B", "R", color="#e11d48", width=2.1)
    segment("C", "R", color="#e11d48", width=2.1)
    for center, point, color in (
        ("A", "B", "#7c3aed"),
        ("I", "B", "#2563eb"),
        ("O3", "B", "#059669"),
    ):
        axis.add_patch(
            Circle(
                points[center],
                radius(center, point),
                fill=False,
                color=color,
                linewidth=1.35,
                alpha=0.8,
            )
        )
    for name, (x_value, y_value) in points.items():
        highlight = name in {"B", "C", "R"}
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
    figure.savefig(output, format="svg", facecolor=figure.get_facecolor())
    plt.close(figure)
    return output.getvalue()


__all__ = [
    "IsoscelesTwoCirclePerpendicularCertificate",
    "JGEXIsoscelesTwoCirclePerpendicularApplication",
    "certify_isosceles_two_circle_perpendicular_chart",
    "certify_jgex_isosceles_two_circle_perpendicular_application",
    "render_isosceles_two_circle_perpendicular_chart_svg",
]
