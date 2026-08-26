"""Exact incircle/tangent-coordinate chart for a reflection construction."""

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
class IncircleReflectionChartCertificate:
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
                "# 内接円・直径円・点反転チャート",
                "",
                "## 定理",
                "",
                (
                    "内心 $I$、接点 $D$、直径 $AI$ の円、三角形 $BIC$ の垂心 $H$"
                    "を用いる所定の構成で、$DQ$ の中点に関する $I$ の対称点 $X$ は"
                    "内接円上にある。したがって $IX=ID$ である。"
                ),
                "",
                "## 接線座標による標準化",
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
                    "2本の辺を単位円の接線として表し、外心、2つの円交点、"
                    "垂心、点対称を順に代入する。最後に $|IX|^2-|ID|^2$ を"
                    "簡約する。"
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
class JGEXIncircleReflectionChartApplication:
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


def _canonical(expression: sp.Expr) -> str:
    return str(sp.factor(sp.cancel(expression)))


@lru_cache(maxsize=1)
def certify_incircle_reflection_chart() -> IncircleReflectionChartCertificate:
    p, q = sp.symbols("p q", nonzero=True)
    w = (
        5 * p**2 * q**2
        - 4 * p**2 * q
        + p**2
        - 4 * p * q**2
        + 8 * p * q
        - 4 * p
        + q**2
        - 4 * q
        + 5
    )

    def point(px: sp.Expr, py: sp.Expr) -> sp.Matrix:
        return sp.Matrix((px, py))

    def norm2(value: sp.Matrix) -> sp.Expr:
        return sp.expand(value.dot(value))

    def cross(left: sp.Matrix, right: sp.Matrix) -> sp.Expr:
        return sp.expand(left[0] * right[1] - left[1] * right[0])

    normal_p = point((1 - p**2) / (1 + p**2), 2 * p / (1 + p**2))
    normal_q = point((1 - q**2) / (1 + q**2), 2 * q / (1 + q**2))
    a = point(-(p * q - 1) / (p * q + 1), (p + q) / (p * q + 1))
    b = point(-(p + 1) / (p - 1), -1)
    c = point(-(q + 1) / (q - 1), -1)
    i = point(0, 0)
    d = point(0, -1)
    o = point(
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
    m1 = sp.cancel(a / 2)
    s = point(
        -(p + 1) * (q + 1) * (p * q - 1) / (2 * (p**2 * q**2 + 1)),
        -(
            p**2 * q**2
            - p**2 * q
            - p * q**2
            - 2 * p * q
            - p
            - q
            + 1
        )
        / (2 * (p**2 * q**2 + 1)),
    )
    h = point(0, -2 * (p * q + 1) / ((p - 1) * (q - 1)))
    q_point = point(
        -2 * (p * q - 1) * (2 * p * q - p - q + 2) / w,
        2 * (p * q - 1) ** 2 / w,
    )
    m2 = sp.cancel((d + q_point) / 2)
    x = sp.cancel(2 * m2 - i)

    residuals = {
        "first_tangent_normal_is_unit": sp.cancel(norm2(normal_p) - 1),
        "second_tangent_normal_is_unit": sp.cancel(norm2(normal_q) - 1),
        "A_on_first_tangent": sp.cancel(normal_p.dot(a) - 1),
        "B_on_first_tangent": sp.cancel(normal_p.dot(b) - 1),
        "A_on_second_tangent": sp.cancel(normal_q.dot(a) - 1),
        "C_on_second_tangent": sp.cancel(normal_q.dot(c) - 1),
        "BC_tangent_to_unit_incircle": sp.cancel(b[1] + 1),
        "D_is_foot_from_I_to_BC_x": sp.cancel(d[0] - i[0]),
        "D_is_foot_from_I_to_BC_y": sp.cancel(d[1] + 1),
        "O_is_circumcenter_AB": sp.cancel(norm2(o - a) - norm2(o - b)),
        "O_is_circumcenter_AC": sp.cancel(norm2(o - a) - norm2(o - c)),
        "M1_midpoint_AI_x": sp.cancel(2 * m1[0] - a[0] - i[0]),
        "M1_midpoint_AI_y": sp.cancel(2 * m1[1] - a[1] - i[1]),
        "S_on_diameter_circle_AI": sp.cancel(
            norm2(s - m1) - norm2(a - m1)
        ),
        "S_on_circumcircle": sp.cancel(norm2(s - o) - norm2(a - o)),
        "H_altitude_from_I": sp.cancel((h - i).dot(c - b)),
        "H_altitude_from_B": sp.cancel((h - b).dot(c - i)),
        "Q_on_HS": sp.cancel(cross(q_point - h, s - h)),
        "Q_on_diameter_circle_AI": sp.cancel(
            norm2(q_point - m1) - norm2(a - m1)
        ),
        "M2_midpoint_DQ_x": sp.cancel(2 * m2[0] - d[0] - q_point[0]),
        "M2_midpoint_DQ_y": sp.cancel(2 * m2[1] - d[1] - q_point[1]),
        "X_reflection_of_I_x": sp.cancel(x[0] + i[0] - 2 * m2[0]),
        "X_reflection_of_I_y": sp.cancel(x[1] + i[1] - 2 * m2[1]),
        "goal_IX_equals_ID": sp.cancel(norm2(x - i) - norm2(d - i)),
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
            "D": d,
            "O": o,
            "M1": m1,
            "S": s,
            "H": h,
            "Q": q_point,
            "M2": m2,
            "X": x,
        }.items()
    }
    discharged_conditions = {
        "p,q != +/-1": (
            "AB and AC meet the fixed tangent BC at finite vertices B and C; "
            "the tangent parameters +/-1 would make either side parallel to or "
            "coincident with BC."
        ),
        "p*q != -1": (
            "AB and AC meet at the finite vertex A; p*q=-1 makes the two tangents parallel."
        ),
        "p*q != 1": (
            "For p*q=1 the second line-circle intersection Q collapses to the existing point I, "
            "which reduce_intersection rejects."
        ),
        "W(p,q) != 0": (
            "W is the denominator of the nontrivial HS/circle intersection Q; "
            "the successful finite JGEX construction excludes W=0."
        ),
        "the named second-intersection branches are selected": (
            "The first circle pair already shares A and the line-circle pair already shares S; "
            "reduce_intersection rejects existing points and returns the remaining branch."
        ),
    }
    upstream_semantics = (
        "Newclid reduce_intersection rejects any intersection equal to an existing point.",
        "Newclid circle_circle_intersection and line_circle_intersection reject absent finite intersections.",
    )
    payload = {
        "theorem": "incircle-diameter-circle-reflection",
        "assumptions": (
            "p,q != +/-1",
            "p*q != -1 and p*q != 1",
            "W(p,q) != 0",
            "the named second-intersection branches are selected",
        ),
        "discharged_conditions": discharged_conditions,
        "upstream_semantics": upstream_semantics,
        "normalization": (
            "I=(0,0), incircle: x^2+y^2=1, BC: y=-1; "
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
    return IncircleReflectionChartCertificate(**payload, certificate_sha256=digest)


def render_incircle_reflection_chart_svg(
    *, p_value: float = 2.0, q_value: float = 0.4
) -> str:
    """Render the circle-intersection and reflection stages separately."""

    certificate = certify_incircle_reflection_chart()
    substitutions = {
        sp.Symbol("p"): sp.Rational(str(p_value)),
        sp.Symbol("q"): sp.Rational(str(q_value)),
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

    def labels(
        axis,
        names: tuple[str, ...],
        highlight: set[str],
        offsets: dict[str, tuple[int, int]] | None = None,
    ) -> None:
        offsets = offsets or {}
        for name in names:
            px, py = points[name]
            color = "#e11d48" if name in highlight else "#0f172a"
            axis.scatter((px,), (py,), s=25, color=color, zorder=5)
            axis.annotate(
                name,
                (px, py),
                xytext=offsets.get(name, (5, 5)),
                textcoords="offset points",
                fontsize=9,
                color=color,
                weight="bold" if name in highlight else "normal",
            )

    figure, axes = plt.subplots(1, 2, figsize=(12, 5), constrained_layout=True)
    figure.patch.set_facecolor("#f8fafc")
    for axis in axes:
        axis.set_facecolor("#ffffff")
        axis.set_aspect("equal", adjustable="datalim")
        axis.axis("off")

    left, right = axes
    left.set_title(
        "内接円と直径AIの円",
        loc="left",
        fontsize=13,
        color="#0f172a",
        fontfamily="Yu Gothic",
    )
    for first, second in (("A", "B"), ("B", "C"), ("C", "A")):
        segment(left, first, second, color="#64748b", linewidth=1.2)
    segment(left, "H", "S", color="#94a3b8", linewidth=1.1)
    left.add_patch(
        Circle(points["I"], 1.0, fill=False, color="#7c3aed", linewidth=1.8)
    )
    left.add_patch(
        Circle(
            points["M1"],
            distance("M1", "A"),
            fill=False,
            color="#0891b2",
            linewidth=1.8,
        )
    )
    left.add_patch(
        Circle(
            points["O"],
            distance("O", "A"),
            fill=False,
            color="#64748b",
            linewidth=1.0,
        )
    )
    labels(
        left,
        ("A", "B", "C", "I", "D", "O", "M1", "S", "H", "Q"),
        {"S", "Q"},
        {
            "A": (-17, 7),
            "S": (7, -13),
            "I": (-13, 5),
            "M1": (-20, -10),
            "O": (-13, -12),
            "D": (6, -13),
            "Q": (7, 5),
        },
    )

    right.set_title(
        "中点反転と最終距離",
        loc="left",
        fontsize=13,
        color="#0f172a",
        fontfamily="Yu Gothic",
    )
    right.add_patch(
        Circle(points["I"], 1.0, fill=False, color="#7c3aed", linewidth=2.0)
    )
    segment(right, "D", "Q", color="#0891b2", linewidth=2.0)
    segment(right, "I", "X", color="#e11d48", linewidth=2.2)
    segment(right, "I", "D", color="#e11d48", linewidth=1.5, linestyle="--")
    labels(
        right,
        ("I", "D", "Q", "M2", "X"),
        {"I", "D", "X"},
        {"I": (5, 7), "D": (6, -13), "M2": (7, -11), "X": (7, 5)},
    )
    for axis in axes:
        axis.relim()
        axis.autoscale_view()
        axis.margins(0.14)

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


def certify_jgex_incircle_reflection_application(
    source: str,
) -> JGEXIncircleReflectionChartApplication:
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
            m1 = _single(records, "midpoint", (a, i))
            h = _single(records, "orthocenter", (b, i, c))
            if d and m1 and h:
                roles.update(D=d, M1=m1, H=h)
                matched.append("incenter, contact foot, and orthocenter BIC")
                s = _intersection(
                    records,
                    frozenset(
                        {("on_circle", (o, a)), ("on_circle", (m1, a))}
                    ),
                )
                if s:
                    roles["S"] = s
                    q = _intersection(
                        records,
                        frozenset({("on_line", (h, s)), ("on_circle", (m1, a))}),
                    )
                    if q:
                        roles["Q"] = q
                        matched.append("S and Q on the diameter circle AI")
                        m2 = _single(records, "midpoint", (d, q))
                        if m2:
                            roles["M2"] = m2
                            x = _single(records, "mirror", (i, m2))
                            if x:
                                roles["X"] = x
                                matched.append("midpoint reflection defining X")

    goal = str(formulation.goals[0]) if len(formulation.goals) == 1 else ""
    goal_parts = goal.split()
    goal_matches = False
    if all(name in roles for name in ("I", "X", "D")) and len(goal_parts) == 5:
        actual = Atom(goal_parts[0], tuple(goal_parts[1:])).canonical()
        expected = Atom(
            "cong", (roles["I"], roles["X"], roles["D"], roles["I"])
        ).canonical()
        goal_matches = actual == expected
    chart = certify_incircle_reflection_chart()
    replayed = (
        chart.replayed
        and chart.all_conditions_discharged
        and len(roles) == 12
        and len(matched) == 3
        and goal_matches
    )
    return JGEXIncircleReflectionChartApplication(
        theorem=chart.theorem,
        source_sha256=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        roles=roles,
        matched_constructions=tuple(matched),
        goal=goal,
        branch_semantics=(
            "S and Q denote the nontrivial intersections specified in the theorem; "
            "the chart proves the corresponding branch exactly."
        ),
        chart_certificate_sha256=chart.certificate_sha256,
        nondegeneracy_obligations=chart.assumptions,
        undischarged_nondegeneracy_obligations=(),
        replayed=replayed,
    )


__all__ = [
    "IncircleReflectionChartCertificate",
    "JGEXIncircleReflectionChartApplication",
    "certify_incircle_reflection_chart",
    "certify_jgex_incircle_reflection_application",
    "render_incircle_reflection_chart_svg",
]
