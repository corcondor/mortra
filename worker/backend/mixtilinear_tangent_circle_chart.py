"""Exact rational chart for a mixtilinear two-circle tangency construction."""

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


def _point(x: FracElement, y: FracElement) -> _Vector:
    return _Vector(x, y)


def _norm2(vector: _Vector) -> FracElement:
    return vector.dot(vector)


def _cross(left: _Vector, right: _Vector) -> FracElement:
    return left[0] * right[1] - left[1] * right[0]


def _perpendicular(vector: _Vector) -> _Vector:
    return _point(-vector[1], vector[0])


def _line_intersection(
    first: _Vector,
    first_direction: _Vector,
    second: _Vector,
    second_direction: _Vector,
) -> _Vector:
    parameter = _cross(second - first, second_direction) / _cross(
        first_direction, second_direction
    )
    return _point(*(first + parameter * first_direction))


def _second_line_circle(
    known: _Vector, direction: _Vector, center: _Vector
) -> _Vector:
    parameter = -2 * (known - center).dot(direction) / direction.dot(direction)
    return _point(*(known + parameter * direction))


def _circumcenter(first: _Vector, second: _Vector, third: _Vector) -> _Vector:
    row1 = second - first
    row2 = third - first
    rhs1 = (_norm2(second) - _norm2(first)) / 2
    rhs2 = (_norm2(third) - _norm2(first)) / 2
    determinant = _cross(row1, row2)
    return _point(
        (rhs1 * row2[1] - row1[1] * rhs2) / determinant,
        (row1[0] * rhs2 - rhs1 * row2[0]) / determinant,
    )


def _second_circle_circle(
    known: _Vector, first_center: _Vector, second_center: _Vector
) -> _Vector:
    return _second_line_circle(
        known, _perpendicular(second_center - first_center), first_center
    )


def _canonical(value: FracElement) -> str:
    return str(value)


@dataclass(frozen=True)
class MixtilinearTangentCircleCertificate:
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
                "# 混線内接円型構成と2円接触チャート",
                "",
                "## 定理",
                "",
                (
                    "内心・外心・接線から所定の点を構成すると、三角形 $DJK$ と"
                    "$GIH$ の外接円は接する。したがって両円の共通点と2中心は"
                    "一直線上にある。"
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
                    "すべての構成を $\\mathbf{Q}(p,q)$ 上で再生し、2円の半径平方"
                    "$R_3^2,R_4^2$ と中心間距離平方 $d^2$ に対する接触判別式"
                    "$(d^2-R_3^2-R_4^2)^2-4R_3^2R_4^2$ を既約化する。"
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
class JGEXMixtilinearTangentCircleApplication:
    theorem: str
    source_sha256: str
    roles: dict[str, str]
    matched_constructions: tuple[str, ...]
    goal: str
    proof_bridge: str
    chart_certificate_sha256: str
    nondegeneracy_obligations: tuple[str, ...]
    undischarged_nondegeneracy_obligations: tuple[str, ...]
    replayed: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@lru_cache(maxsize=1)
def certify_mixtilinear_tangent_circle_chart() -> MixtilinearTangentCircleCertificate:
    _rational_function_field, p, q = field("p,q", sp.QQ)
    a = _point(-(p * q - 1) / (p * q + 1), (p + q) / (p * q + 1))
    b = _point(-(p + 1) / (p - 1), -1)
    c = _point(-(q + 1) / (q - 1), -1)
    i = _point(0, 0)
    d = _point(0, -1)
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
    perpendicular_ai = _perpendicular(i - a)
    e = _line_intersection(a, b - a, i, perpendicular_ai)
    f = _line_intersection(a, c - a, i, perpendicular_ai)
    o1 = _circumcenter(a, e, f)
    g = _second_circle_circle(a, o1, o)
    h = _second_line_circle(a, i - a, o1)
    j = _line_intersection(g, _perpendicular(g - o), b, c - b)
    k = _second_line_circle(a, j - a, o)
    o3 = _circumcenter(d, j, k)
    o4 = _circumcenter(g, i, h)

    circumradius2 = _norm2(a - o)
    first_radius2 = _norm2(d - o3)
    second_radius2 = _norm2(i - o4)
    center_distance2 = _norm2(o3 - o4)
    tangency_discriminant = (
        center_distance2 - first_radius2 - second_radius2
    ) ** 2 - 4 * first_radius2 * second_radius2
    residuals = {
        "E_on_AB": _cross(e - a, b - a),
        "E_on_perpendicular_through_I": (e - i).dot(a - i),
        "F_on_AC": _cross(f - a, c - a),
        "F_on_perpendicular_through_I": (f - i).dot(a - i),
        "O1_center_AEF_1": _norm2(o1 - a) - _norm2(o1 - e),
        "O1_center_AEF_2": _norm2(o1 - a) - _norm2(o1 - f),
        "G_on_circle_AEF": _norm2(g - o1) - _norm2(a - o1),
        "G_on_circumcircle": _norm2(g - o) - circumradius2,
        "H_on_AI": _cross(h - a, i - a),
        "H_on_circle_AEF": _norm2(h - o1) - _norm2(a - o1),
        "J_on_BC": _cross(j - b, c - b),
        "JG_tangent_to_circumcircle": (j - g).dot(g - o),
        "K_on_AJ": _cross(k - a, j - a),
        "K_on_circumcircle": _norm2(k - o) - circumradius2,
        "O3_center_DJK_1": _norm2(o3 - d) - _norm2(o3 - j),
        "O3_center_DJK_2": _norm2(o3 - d) - _norm2(o3 - k),
        "O4_center_GIH_1": _norm2(o4 - g) - _norm2(o4 - i),
        "O4_center_GIH_2": _norm2(o4 - g) - _norm2(o4 - h),
        "two_circle_tangency_discriminant": tangency_discriminant,
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
            "O1": o1,
            "G": g,
            "H": h,
            "J": j,
            "K": k,
            "O3": o3,
            "O4": o4,
        }.items()
    }
    discharged_conditions = {
        "the tangent-coordinate triangle is finite and nondegenerate": (
            "The JGEX triangle and its incenter exist.  In the unit-incircle chart "
            "this excludes coincident/parallel side tangents and every base-chart denominator."
        ),
        "all named intersections and circumcenters are nondegenerate": (
            "Every denominator in the rational construction is the determinant of "
            "the corresponding line intersection, circumcenter, or second-intersection operator; "
            "successful JGEX construction excludes its vanishing."
        ),
        "the two final circles have a real common point T as specified": (
            "The input constructs T on both real circles.  Their exact tangency discriminant "
            "is zero, while Newclid rejects coincident centers, so T is their unique contact point."
        ),
    }
    upstream_semantics = (
        "Newclid rejects parallel line intersections and collinear circumcenter triples.",
        "Newclid reduce_intersection rejects existing branches and absent real intersections.",
        "Newclid circle_circle_intersection rejects coincident centers.",
    )
    payload = {
        "theorem": "mixtilinear-two-circumcircles-tangent",
        "assumptions": (
            "the tangent-coordinate triangle is finite and nondegenerate",
            "all named intersections and circumcenters are nondegenerate",
            "the two final circles have a real common point T as specified",
        ),
        "discharged_conditions": discharged_conditions,
        "upstream_semantics": upstream_semantics,
        "normalization": (
            "I=(0,0), incircle:x^2+y^2=1, BC:y=-1; "
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
    return MixtilinearTangentCircleCertificate(**payload, certificate_sha256=digest)


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


def certify_jgex_mixtilinear_tangent_circle_application(
    source: str,
) -> JGEXMixtilinearTangentCircleApplication:
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
        i = _single(records, "incenter", (a, b, c))
        o = _single(records, "circumcenter", (a, b, c))
        if i and o:
            roles.update(I=i, O=o)
            d = _single(records, "foot", (i, b, c))
            e = _intersection(
                records,
                frozenset({("on_line", (a, b)), ("on_tline", (i, a, i))}),
            )
            f = _intersection(
                records,
                frozenset({("on_line", (a, c)), ("on_tline", (i, a, i))}),
            )
            if d and e and f:
                roles.update(D=d, E=e, F=f)
                matched.append("contact foot and perpendicular chord through I")
                o1 = _single(records, "circumcenter", (a, e, f))
                if o1:
                    roles["O1"] = o1
                    g = _intersection(
                        records,
                        frozenset({("on_circle", (o1, a)), ("on_circle", (o, a))}),
                    )
                    h = _intersection(
                        records,
                        frozenset({("on_circle", (o1, a)), ("on_line", (a, i))}),
                    )
                    if g and h:
                        roles.update(G=g, H=h)
                        j = _intersection(
                            records,
                            frozenset({("on_tline", (g, o, g)), ("on_line", (b, c))}),
                        )
                        if j:
                            roles["J"] = j
                            k = _intersection(
                                records,
                                frozenset({("on_line", (a, j)), ("on_circle", (o, a))}),
                            )
                            if k:
                                roles["K"] = k
                                matched.append("mixtilinear point, tangent, and secant")
                                o3 = _single(records, "circumcenter", (d, j, k))
                                o4 = _single(records, "circumcenter", (g, i, h))
                                if o3 and o4:
                                    roles.update(O3=o3, O4=o4)
                                    t = _intersection(
                                        records,
                                        frozenset(
                                            {("on_circle", (o4, i)), ("on_circle", (o3, d))}
                                        ),
                                    )
                                    if t:
                                        roles["T"] = t
                                        matched.append("two final circumcircles and common point")

    goal = str(formulation.goals[0]) if len(formulation.goals) == 1 else ""
    goal_matches = False
    if all(name in roles for name in ("O3", "O4", "T")):
        parts = goal.split()
        if len(parts) == 4:
            actual = Atom(parts[0], tuple(parts[1:])).canonical()
            expected = Atom("coll", (roles["O3"], roles["O4"], roles["T"])).canonical()
            goal_matches = actual == expected
    chart = certify_mixtilinear_tangent_circle_chart()
    replayed = (
        chart.replayed
        and chart.all_conditions_discharged
        and len(roles) == 16
        and len(matched) == 3
        and goal_matches
    )
    return JGEXMixtilinearTangentCircleApplication(
        theorem=chart.theorem,
        source_sha256=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        roles=roles,
        matched_constructions=tuple(matched),
        goal=goal,
        proof_bridge=(
            "The exact tangency discriminant is zero. Because T is specified on both "
            "nondegenerate real circles, their unique contact point T lies on O3O4."
        ),
        chart_certificate_sha256=chart.certificate_sha256,
        nondegeneracy_obligations=chart.assumptions,
        undischarged_nondegeneracy_obligations=(),
        replayed=replayed,
    )


def render_mixtilinear_tangent_circle_chart_svg(
    *, p_value: float = 2.0, q_value: float = 0.4
) -> str:
    certificate = certify_mixtilinear_tangent_circle_chart()
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
            axis.scatter((px,), (py,), s=25, color=color, zorder=6)
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
    left.set_title("接線から2円を構成", loc="left", fontsize=13, fontfamily="Yu Gothic")
    for first, second in (("A", "B"), ("B", "C"), ("C", "A")):
        segment(left, first, second, color="#64748b", linewidth=1.1)
    left.add_patch(
        Circle(points["O"], distance("O", "A"), fill=False, color="#0891b2", linewidth=1.5)
    )
    left.add_patch(
        Circle(points["O1"], distance("O1", "A"), fill=False, color="#7c3aed", linewidth=1.5)
    )
    segment(left, "E", "F", color="#16a34a", linewidth=1.5)
    segment(left, "G", "J", color="#f59e0b", linewidth=1.7)
    labels(left, ("A", "B", "C", "I", "O", "D", "E", "F", "G", "H", "J", "K"), {"G", "H"})

    right.set_title("接触判別式から中心線へ", loc="left", fontsize=13, fontfamily="Yu Gothic")
    right.add_patch(
        Circle(points["O3"], distance("O3", "D"), fill=False, color="#0891b2", linewidth=2.0)
    )
    right.add_patch(
        Circle(points["O4"], distance("O4", "I"), fill=False, color="#7c3aed", linewidth=2.0)
    )
    segment(right, "O3", "O4", color="#e11d48", linewidth=2.2)
    labels(right, ("D", "J", "K", "G", "I", "H", "O3", "O4"), {"O3", "O4"})
    for axis in axes:
        axis.relim()
        axis.autoscale_view()
        axis.margins(0.14)
    output = io.StringIO()
    figure.savefig(output, format="svg", facecolor=figure.get_facecolor())
    plt.close(figure)
    return output.getvalue()


__all__ = [
    "JGEXMixtilinearTangentCircleApplication",
    "MixtilinearTangentCircleCertificate",
    "certify_jgex_mixtilinear_tangent_circle_application",
    "certify_mixtilinear_tangent_circle_chart",
    "render_mixtilinear_tangent_circle_chart_svg",
]
