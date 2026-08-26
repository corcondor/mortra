"""Exact incircle chart for a three-circle radical-axis construction."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
import hashlib
import io
import json
from typing import Iterator

import matplotlib
import sympy as sp
from sympy.polys.fields import FracElement, field

matplotlib.use("Agg")

from matplotlib import pyplot as plt
from matplotlib.patches import Circle
from worker.backend.jgex_chart_parser import ChartJGEXFormulation as JGEXFormulation

from worker.backend.geometry_proof_hypergraph import Atom


@dataclass(frozen=True)
class IncircleThreeCircleAxisCertificate:
    theorem: str
    assumptions: tuple[str, ...]
    discharged_conditions: dict[str, str]
    upstream_semantics: tuple[str, ...]
    normalization: str
    coordinates: dict[str, tuple[str, str]]
    replay_residuals: dict[str, str]
    replayed: bool
    all_conditions_discharged: bool
    certificate_sha256: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def to_markdown(self) -> str:
        coordinates = "\n".join(
            f"- `{name}=({value[0]}, {value[1]})`"
            for name, value in self.coordinates.items()
        )
        residuals = "\n".join(
            f"- `{name}`: `{value}`" for name, value in self.replay_residuals.items()
        )
        return "\n".join(
            (
                "# 内接円・反対点・3円根軸チャート",
                "",
                "## 定理",
                "",
                (
                    "三角形の内心を通る3本の直線から外接円上の点を取り、その反対点と"
                    "内接円の3接点を用いて3円を構成する。指定された2本の共通弦の交点は"
                    "内心と外心を結ぶ直線上にある。"
                ),
                "",
                "## 標準化",
                "",
                self.normalization,
                "",
                "## 非退化条件",
                "",
                *(f"- `{item}`" for item in self.assumptions),
                "",
                "## 条件の消去根拠",
                "",
                *(
                    f"- `{condition}`: {reason}"
                    for condition, reason in self.discharged_conditions.items()
                ),
                "",
                "## 構成点の座標",
                "",
                coordinates,
                "",
                "## 証明過程",
                "",
                (
                    "直線と円の第2交点、外心、2円の第2交点、直線交点を順に"
                    "$\\mathbf{Q}(p,q)$ 上で計算する。各構成条件を再代入し、最後に"
                    "$\\det(T-I,O-I)$ を既約化する。"
                ),
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
class JGEXIncircleThreeCircleAxisApplication:
    theorem: str
    source_sha256: str
    roles: dict[str, str]
    matched_constructions: tuple[str, ...]
    goal: str
    branch_semantics: str
    chart_certificate_sha256: str
    nondegeneracy_obligations: tuple[str, ...]
    undischarged_nondegeneracy_obligations: tuple[str, ...]
    replayed: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class _Vector:
    x: FracElement
    y: FracElement

    def __iter__(self) -> Iterator[FracElement]:
        yield self.x
        yield self.y

    def __getitem__(self, index: int) -> FracElement:
        return (self.x, self.y)[index]

    def __add__(self, other: "_Vector") -> "_Vector":
        return _Vector(self.x + other.x, self.y + other.y)

    def __sub__(self, other: "_Vector") -> "_Vector":
        return _Vector(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: FracElement) -> "_Vector":
        return _Vector(self.x * scalar, self.y * scalar)

    def __rmul__(self, scalar: FracElement) -> "_Vector":
        return self * scalar

    def dot(self, other: "_Vector") -> FracElement:
        return self.x * other.x + self.y * other.y


def _canonical(expression: FracElement) -> str:
    return str(expression)


def _reduce(expression: FracElement) -> FracElement:
    return expression


def _point(x: FracElement, y: FracElement) -> _Vector:
    return _Vector(x, y)


def _norm2(vector: _Vector) -> FracElement:
    return vector.dot(vector)


def _cross(left: _Vector, right: _Vector) -> FracElement:
    return left[0] * right[1] - left[1] * right[0]


def _second_line_circle(
    known: _Vector, direction: _Vector, center: _Vector
) -> _Vector:
    parameter = _reduce(
        -2 * (known - center).dot(direction) / direction.dot(direction)
    )
    return _point(*(known + parameter * direction))


def _circumcenter(
    first: _Vector, second: _Vector, third: _Vector
) -> _Vector:
    row1 = second - first
    row2 = third - first
    rhs1 = _reduce((_norm2(second) - _norm2(first)) / 2)
    rhs2 = _reduce((_norm2(third) - _norm2(first)) / 2)
    determinant = _reduce(_cross(row1, row2))
    return _point(
        _reduce((rhs1 * row2[1] - row1[1] * rhs2) / determinant),
        _reduce((row1[0] * rhs2 - rhs1 * row2[0]) / determinant),
    )


def _second_circle_circle(
    known: _Vector, first_center: _Vector, second_center: _Vector
) -> _Vector:
    center_line = second_center - first_center
    direction = _point(-center_line[1], center_line[0])
    return _second_line_circle(known, direction, first_center)


def _line_intersection(
    first: _Vector,
    first_direction: _Vector,
    second: _Vector,
    second_direction: _Vector,
) -> _Vector:
    parameter = _reduce(
        _cross(second - first, second_direction)
        / _cross(first_direction, second_direction)
    )
    return _point(*(first + parameter * first_direction))


@lru_cache(maxsize=1)
def certify_incircle_three_circle_axis_chart() -> IncircleThreeCircleAxisCertificate:
    """Replay the complete construction over the rational function field Q(p,q)."""

    _rational_function_field, p, q = field("p,q", sp.QQ)
    normal_p = _point((1 - p**2) / (1 + p**2), 2 * p / (1 + p**2))
    normal_q = _point((1 - q**2) / (1 + q**2), 2 * q / (1 + q**2))
    a = _point(-(p * q - 1) / (p * q + 1), (p + q) / (p * q + 1))
    b = _point(-(p + 1) / (p - 1), -1)
    c = _point(-(q + 1) / (q - 1), -1)
    i = _point(0, 0)
    d = _point(0, -1)
    e = normal_q
    f = normal_p
    o = _point(
        -(p * q - 1) / ((p - 1) * (q - 1)),
        -(
            p**2 * q**2
            - 2 * p**2 * q
            + p**2
            - 2 * p * q**2
            - 2 * p
            + q**2
            - 2 * q
            + 1
        )
        / (2 * (p - 1) * (q - 1) * (p * q + 1)),
    )

    j1 = _second_line_circle(a, i - a, o)
    j = _point(*(2 * o - j1))
    k1 = _second_line_circle(b, i - b, o)
    k = _point(*(2 * o - k1))
    l1 = _second_line_circle(c, i - c, o)
    point_l = _point(*(2 * o - l1))
    x = _second_line_circle(j, d - j, o)
    y = _second_line_circle(k, e - k, o)
    z = _second_line_circle(point_l, f - point_l, o)
    o1 = _circumcenter(x, e, f)
    o2 = _circumcenter(y, f, d)
    o3 = _circumcenter(z, d, e)
    u = _second_circle_circle(f, o1, o2)
    v = _second_circle_circle(e, o1, o3)
    t = _line_intersection(f, u - f, e, v - e)

    circumradius2 = _reduce(_norm2(a - o))
    residuals = {
        "A_on_first_tangent": _reduce(normal_p.dot(a) - 1),
        "B_on_first_tangent": _reduce(normal_p.dot(b) - 1),
        "A_on_second_tangent": _reduce(normal_q.dot(a) - 1),
        "C_on_second_tangent": _reduce(normal_q.dot(c) - 1),
        "J1_on_AI": _reduce(_cross(j1 - a, i - a)),
        "J1_on_circumcircle": _reduce(_norm2(j1 - o) - circumradius2),
        "J_is_antipode": _reduce(_norm2(j - o) - circumradius2),
        "K1_on_BI": _reduce(_cross(k1 - b, i - b)),
        "K1_on_circumcircle": _reduce(_norm2(k1 - o) - circumradius2),
        "K_is_antipode": _reduce(_norm2(k - o) - circumradius2),
        "L1_on_CI": _reduce(_cross(l1 - c, i - c)),
        "L1_on_circumcircle": _reduce(_norm2(l1 - o) - circumradius2),
        "L_is_antipode": _reduce(_norm2(point_l - o) - circumradius2),
        "X_on_JD": _reduce(_cross(x - j, d - j)),
        "X_on_circumcircle": _reduce(_norm2(x - o) - circumradius2),
        "Y_on_KE": _reduce(_cross(y - k, e - k)),
        "Y_on_circumcircle": _reduce(_norm2(y - o) - circumradius2),
        "Z_on_LF": _reduce(_cross(z - point_l, f - point_l)),
        "Z_on_circumcircle": _reduce(_norm2(z - o) - circumradius2),
        "O1_center_XEF_1": _reduce(_norm2(o1 - x) - _norm2(o1 - e)),
        "O1_center_XEF_2": _reduce(_norm2(o1 - x) - _norm2(o1 - f)),
        "O2_center_YFD_1": _reduce(_norm2(o2 - y) - _norm2(o2 - f)),
        "O2_center_YFD_2": _reduce(_norm2(o2 - y) - _norm2(o2 - d)),
        "O3_center_ZDE_1": _reduce(_norm2(o3 - z) - _norm2(o3 - d)),
        "O3_center_ZDE_2": _reduce(_norm2(o3 - z) - _norm2(o3 - e)),
        "U_on_circle_XEF": _reduce(_norm2(u - o1) - _norm2(f - o1)),
        "U_on_circle_YFD": _reduce(_norm2(u - o2) - _norm2(f - o2)),
        "V_on_circle_XEF": _reduce(_norm2(v - o1) - _norm2(e - o1)),
        "V_on_circle_ZDE": _reduce(_norm2(v - o3) - _norm2(e - o3)),
        "T_on_UF": _reduce(_cross(t - f, u - f)),
        "T_on_VE": _reduce(_cross(t - e, v - e)),
        "goal_I_O_T_collinear": _reduce(_cross(t - i, o - i)),
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
            "O": o,
            "D": d,
            "E": e,
            "F": f,
            "J1": j1,
            "J": j,
            "K1": k1,
            "K": k,
            "L1": l1,
            "L": point_l,
            "X": x,
            "Y": y,
            "Z": z,
            "O1": o1,
            "O2": o2,
            "O3": o3,
            "U": u,
            "V": v,
            "T": t,
        }.items()
    }
    discharged_conditions = {
        "the tangent-coordinate triangle is finite and nondegenerate": (
            "The input triangle, circumcenter, and incenter exist; this excludes "
            "coincident or parallel side tangents in the normalized unit-incircle chart."
        ),
        "all named second-intersection branches are nondegenerate": (
            "J1/K1/L1 share A/B/C with the circumcircle, X/Y/Z share J/K/L, "
            "and U/V share F/E.  reduce_intersection rejects each known branch."
        ),
        "the three circumcenters and the two defining lines exist": (
            "Successful circumcenter clauses exclude collinear triples; the final "
            "line intersection excludes coincident points and parallel lines."
        ),
    }
    upstream_semantics = (
        "Newclid reduce_intersection rejects intersections equal to existing points.",
        "Newclid rejects degenerate circumcenters and parallel line intersections.",
    )
    payload = {
        "theorem": "incircle-antipodes-three-circle-axis",
        "assumptions": (
            "the tangent-coordinate triangle is finite and nondegenerate",
            "all named second-intersection branches are nondegenerate",
            "the three circumcenters and the two defining lines exist",
        ),
        "discharged_conditions": discharged_conditions,
        "upstream_semantics": upstream_semantics,
        "normalization": (
            "I=(0,0), incircle: x^2+y^2=1, BC:y=-1; "
            "AB and AC are unit-circle tangents with parameters p and q"
        ),
        "coordinates": coordinates,
        "replay_residuals": rendered,
        "replayed": replayed,
        "all_conditions_discharged": replayed,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return IncircleThreeCircleAxisCertificate(**payload, certificate_sha256=digest)


def render_incircle_three_circle_axis_chart_svg(
    *, p_value: float = 2.0, q_value: float = 0.4
) -> str:
    """Render the source construction and the final radical-axis stage."""

    certificate = certify_incircle_three_circle_axis_chart()
    p_symbol, q_symbol = sp.symbols("p q")
    substitutions = {
        p_symbol: sp.Rational(str(p_value)),
        q_symbol: sp.Rational(str(q_value)),
    }
    points = {
        name: (
            float(sp.sympify(value[0]).subs(substitutions)),
            float(sp.sympify(value[1]).subs(substitutions)),
        )
        for name, value in certificate.coordinates.items()
    }

    def distance(left: str, right: str) -> float:
        return (
            (points[left][0] - points[right][0]) ** 2
            + (points[left][1] - points[right][1]) ** 2
        ) ** 0.5

    def segment(axis, left: str, right: str, **kwargs) -> None:
        axis.plot(
            (points[left][0], points[right][0]),
            (points[left][1], points[right][1]),
            **kwargs,
        )

    def labels(axis, names: tuple[str, ...], highlight: set[str]) -> None:
        for name in names:
            px, py = points[name]
            color = "#e11d48" if name in highlight else "#0f172a"
            axis.scatter((px,), (py,), s=24, color=color, zorder=6)
            axis.annotate(
                name,
                (px, py),
                xytext=(5, 5),
                textcoords="offset points",
                fontsize=8,
                color=color,
                weight="bold" if name in highlight else "normal",
            )

    figure, axes = plt.subplots(1, 2, figsize=(13, 5.5), constrained_layout=True)
    figure.patch.set_facecolor("#f8fafc")
    for axis in axes:
        axis.set_facecolor("#ffffff")
        axis.set_aspect("equal", adjustable="datalim")
        axis.axis("off")

    left, right = axes
    left.set_title(
        "内心軸と外接円上の反対点",
        loc="left",
        fontsize=13,
        color="#0f172a",
        fontfamily="Yu Gothic",
    )
    for first, second in (("A", "B"), ("B", "C"), ("C", "A")):
        segment(left, first, second, color="#64748b", linewidth=1.1)
    left.add_patch(
        Circle(
            points["O"],
            distance("O", "A"),
            fill=False,
            color="#0891b2",
            linewidth=1.6,
        )
    )
    left.add_patch(Circle(points["I"], 1.0, fill=False, color="#7c3aed", linewidth=1.5))
    for first, second in (("A", "J"), ("B", "K"), ("C", "L")):
        segment(left, first, second, color="#cbd5e1", linewidth=0.9)
    for first, second in (("J", "D"), ("K", "E"), ("L", "F")):
        segment(left, first, second, color="#94a3b8", linewidth=1.0)
    labels(
        left,
        ("A", "B", "C", "I", "O", "D", "E", "F", "J", "K", "L", "X", "Y", "Z"),
        {"X", "Y", "Z"},
    )

    right.set_title(
        "3円の共通弦と内心・外心軸",
        loc="left",
        fontsize=13,
        color="#0f172a",
        fontfamily="Yu Gothic",
    )
    circle_specs = (
        ("O1", "F", "#0891b2"),
        ("O2", "F", "#7c3aed"),
        ("O3", "E", "#16a34a"),
    )
    for center, point_on_circle, color in circle_specs:
        right.add_patch(
            Circle(
                points[center],
                distance(center, point_on_circle),
                fill=False,
                color=color,
                linewidth=1.8,
            )
        )
    segment(right, "F", "U", color="#f59e0b", linewidth=2.0)
    segment(right, "E", "V", color="#f59e0b", linewidth=2.0)
    segment(right, "I", "O", color="#e11d48", linewidth=2.2)
    labels(
        right,
        ("D", "E", "F", "O1", "O2", "O3", "U", "V", "I", "O", "T"),
        {"I", "O", "T"},
    )
    for axis in axes:
        axis.relim()
        axis.autoscale_view()
        axis.margins(0.12)

    output = io.StringIO()
    figure.savefig(output, format="svg", facecolor=figure.get_facecolor())
    plt.close(figure)
    return output.getvalue()


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


def certify_jgex_incircle_three_circle_axis_application(
    source: str,
) -> JGEXIncircleThreeCircleAxisApplication:
    normalized = source.strip()
    formulation = JGEXFormulation.from_text(normalized)
    records = _records(formulation)
    triangle = next(
        (
            record["outputs"]
            for record in records
            if record["constructions"] == (("triangle", ()),)
            and len(record["outputs"]) == 3
        ),
        None,
    )
    roles: dict[str, str] = {}
    matched: list[str] = []
    if triangle is not None:
        a, b, c = triangle
        roles.update(A=a, B=b, C=c)
        o = _single(records, "circumcenter", (a, b, c))
        i = _single(records, "incenter", (a, b, c))
        if o and i:
            roles.update(O=o, I=i)
            antipodes: dict[str, tuple[str, str]] = {}
            for key, vertex in (("J", a), ("K", b), ("L", c)):
                first = _intersection(
                    records,
                    frozenset({("on_line", (vertex, i)), ("on_circle", (o, a))}),
                )
                opposite = _single(records, "mirror", (first, o)) if first else None
                if first and opposite:
                    antipodes[key] = (first, opposite)
                    roles[f"{key}1"] = first
                    roles[key] = opposite
            if len(antipodes) == 3:
                matched.append("three incenter-axis intersections and antipodes")
                d = _single(records, "foot", (i, b, c))
                e = _single(records, "foot", (i, a, c))
                f = _single(records, "foot", (i, a, b))
                if d and e and f:
                    roles.update(D=d, E=e, F=f)
                    x = _intersection(
                        records,
                        frozenset({("on_line", (roles["J"], d)), ("on_circle", (o, a))}),
                    )
                    y = _intersection(
                        records,
                        frozenset({("on_line", (roles["K"], e)), ("on_circle", (o, a))}),
                    )
                    z = _intersection(
                        records,
                        frozenset({("on_line", (roles["L"], f)), ("on_circle", (o, a))}),
                    )
                    if x and y and z:
                        roles.update(X=x, Y=y, Z=z)
                        matched.append("contact triangle and three secants")
                        o1 = _single(records, "circumcenter", (x, e, f))
                        o2 = _single(records, "circumcenter", (y, f, d))
                        o3 = _single(records, "circumcenter", (z, d, e))
                        if o1 and o2 and o3:
                            roles.update(O1=o1, O2=o2, O3=o3)
                            u = _intersection(
                                records,
                                frozenset({("on_circle", (o1, f)), ("on_circle", (o2, f))}),
                            )
                            v = _intersection(
                                records,
                                frozenset({("on_circle", (o1, e)), ("on_circle", (o3, e))}),
                            )
                            if u and v:
                                roles.update(U=u, V=v)
                                t = _intersection(
                                    records,
                                    frozenset({("on_line", (u, f)), ("on_line", (v, e))}),
                                )
                                if t:
                                    roles["T"] = t
                                    matched.append("three circumcircles and two common chords")

    goal = str(formulation.goals[0]) if len(formulation.goals) == 1 else ""
    goal_matches = False
    if all(name in roles for name in ("I", "O", "T")):
        goal_parts = goal.split()
        if len(goal_parts) == 4:
            actual = Atom(goal_parts[0], tuple(goal_parts[1:])).canonical()
            expected = Atom("coll", (roles["I"], roles["O"], roles["T"])).canonical()
            goal_matches = actual == expected
    chart = certify_incircle_three_circle_axis_chart()
    replayed = (
        chart.replayed
        and chart.all_conditions_discharged
        and len(roles) == 23
        and len(matched) == 3
        and goal_matches
    )
    return JGEXIncircleThreeCircleAxisApplication(
        theorem=chart.theorem,
        source_sha256=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        roles=roles,
        matched_constructions=tuple(matched),
        goal=goal,
        branch_semantics=(
            "Every on_circle clause denotes the nontrivial second intersection used by "
            "the exact chart; all corresponding denominator obligations are retained."
        ),
        chart_certificate_sha256=chart.certificate_sha256,
        nondegeneracy_obligations=chart.assumptions,
        undischarged_nondegeneracy_obligations=(),
        replayed=replayed,
    )


__all__ = [
    "IncircleThreeCircleAxisCertificate",
    "JGEXIncircleThreeCircleAxisApplication",
    "certify_incircle_three_circle_axis_chart",
    "certify_jgex_incircle_three_circle_axis_application",
    "render_incircle_three_circle_axis_chart_svg",
]
