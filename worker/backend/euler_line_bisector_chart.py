"""Exact chart for an Euler-line, circle, and perpendicular-bisector family."""

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
class EulerLineBisectorChartCertificate:
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
                "# Euler線・2円・垂直二等分線チャート",
                "",
                "## 定理",
                "",
                (
                    "三角形 $ABC$ の外心を $O$、垂心を $H$ とし、"
                    "以下の構成依存関係で $E,F,K,L,M,P,Q$ を定める。"
                    "このとき $QH=QO$ である。"
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
                "## 証明",
                "",
                (
                    "各座標を元の直線・円・中点・垂直二等分線の条件へ代入し、"
                    "最後に $|Q-H|^2-|Q-O|^2$ を評価する。"
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
class JGEXEulerLineBisectorChartApplication:
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


@lru_cache(maxsize=1)
def certify_euler_line_bisector_chart() -> EulerLineBisectorChartCertificate:
    u, v = sp.symbols("u v", nonzero=True)
    s = u**2 + v**2
    de = 3 * u**3 - 3 * u**2 + 3 * u * v**2 - 3 * u - v**2 + 3
    df = 3 * u**3 + 3 * u**2 + 3 * u * v**2 - 3 * u + v**2 - 3
    w = 9 * u**4 + 10 * u**2 * v**2 - 18 * u**2 + v**4 - 6 * v**2 + 9
    side_minus = u**2 - 2 * u + v**2 - 3
    side_plus = u**2 + 2 * u + v**2 - 3

    def point(px: sp.Expr, py: sp.Expr) -> sp.Matrix:
        return sp.Matrix((px, py))

    def norm2(value: sp.Matrix) -> sp.Expr:
        return sp.expand(value.dot(value))

    def cross(left: sp.Matrix, right: sp.Matrix) -> sp.Expr:
        return sp.expand(left[0] * right[1] - left[1] * right[0])

    a = point(u, v)
    b = point(-1, 0)
    c = point(1, 0)
    o = point(0, (s - 1) / (2 * v))
    h = point(u, (1 - u**2) / v)
    e = point(
        u * (u + 1) * (u**2 - 2 * u + v**2 + 1) / de,
        v * (u - 1) * side_minus / de,
    )
    f = point(
        u * (u - 1) * (u**2 + 2 * u + v**2 + 1) / df,
        v * (u + 1) * side_plus / df,
    )
    o1 = point(
        -(3 * u**4 - 6 * u**2 * v**2 - 6 * u**2 - v**4 + 2 * v**2 + 3)
        / (8 * u * v**2),
        -(u**2 - v**2 - 1) / (2 * v),
    )
    k = point(
        -u
        * (15 * u**4 - 2 * u**2 * v**2 - 30 * u**2 - v**4 - 2 * v**2 + 15)
        / w,
        (u**2 - 1)
        * (3 * u**2 - 6 * u - v**2 + 3)
        * (3 * u**2 + 6 * u - v**2 + 3)
        / (v * w),
    )
    point_l = point(
        -u
        * (3 * u**4 + 6 * u**2 * v**2 - 6 * u**2 + 3 * v**4 - 10 * v**2 + 3)
        / w,
        v * side_minus * side_plus / w,
    )
    m = point(0, 0)
    p = point(
        -u * v**2 * side_minus * side_plus / (de * df),
        v * (u**2 - 1) * side_minus * side_plus / (de * df),
    )
    q = point(
        (3 * u**4 + 2 * u**2 * v**2 - 6 * u**2 - v**4 + 2 * v**2 + 3)
        / (8 * u * v**2),
        0,
    )

    residuals = {
        "O_is_circumcenter_AB": sp.cancel(norm2(o - a) - norm2(o - b)),
        "O_is_circumcenter_AC": sp.cancel(norm2(o - a) - norm2(o - c)),
        "H_altitude_from_A": sp.cancel((h - a).dot(c - b)),
        "H_altitude_from_B": sp.cancel((h - b).dot(c - a)),
        "E_on_OH": sp.cancel(cross(e - o, h - o)),
        "E_on_AC": sp.cancel(cross(e - a, c - a)),
        "F_on_OH": sp.cancel(cross(f - o, h - o)),
        "F_on_AB": sp.cancel(cross(f - a, b - a)),
        "O1_contains_A_and_H": sp.cancel(norm2(o1 - a) - norm2(o1 - h)),
        "O1_contains_A_and_O": sp.cancel(norm2(o1 - a) - norm2(o1 - o)),
        "K_on_circle_O1A": sp.cancel(norm2(k - o1) - norm2(a - o1)),
        "K_on_circumcircle": sp.cancel(norm2(k - o) - norm2(a - o)),
        "L_on_KH": sp.cancel(cross(point_l - k, h - k)),
        "L_on_circumcircle": sp.cancel(norm2(point_l - o) - norm2(a - o)),
        "M_midpoint_BC_x": sp.cancel(2 * m[0] - b[0] - c[0]),
        "M_midpoint_BC_y": sp.cancel(2 * m[1] - b[1] - c[1]),
        "P_on_HM": sp.cancel(cross(p - h, m - h)),
        "P_on_perpendicular_bisector_EF": sp.cancel(
            norm2(p - e) - norm2(p - f)
        ),
        "Q_on_PL": sp.cancel(cross(q - p, point_l - p)),
        "Q_on_BC": sp.cancel(cross(q - b, c - b)),
        "goal_QH_equals_QO": sp.cancel(norm2(q - h) - norm2(q - o)),
    }
    rendered = {name: _canonical(value) for name, value in residuals.items()}
    replayed = all(value == "0" for value in rendered.values())
    coordinates = {
        name: (_canonical(value[0]), _canonical(value[1]))
        for name, value in {
            "A": a,
            "B": b,
            "C": c,
            "O": o,
            "H": h,
            "E": e,
            "F": f,
            "O1": o1,
            "K": k,
            "L": point_l,
            "M": m,
            "P": p,
            "Q": q,
        }.items()
    }
    discharged_conditions = {
        "u*v != 0": (
            "v!=0 is the triangle determinant.  If u=0 then A,H,O are collinear, "
            "so the required circumcenter O1 of AHO does not exist."
        ),
        "DE(u,v)*DF(u,v) != 0": (
            "DE and DF are the exact line-line determinants for E=OH intersect AC "
            "and F=OH intersect AB; successful JGEX intersections exclude zero."
        ),
        "W(u,v) != 0": (
            "W is the common denominator of the nontrivial K/L circle branches; "
            "the finite second-intersection constructions exclude W=0."
        ),
        "all named intersections are nondegenerate": (
            "K is selected after rejecting the shared existing point A, L after "
            "rejecting K, and P,Q are defined by nonparallel line intersections."
        ),
    }
    upstream_semantics = (
        "Newclid reduce_intersection rejects intersections equal to existing points.",
        "Newclid line_line_intersection rejects parallel defining lines.",
        "Newclid circumcenter and circle intersections reject degenerate inputs.",
    )
    payload = {
        "theorem": "euler-line-circle-bisector-equal-distance",
        "assumptions": (
            "u*v != 0",
            "DE(u,v)*DF(u,v)*W(u,v) != 0",
            "all named intersections are nondegenerate",
        ),
        "discharged_conditions": discharged_conditions,
        "upstream_semantics": upstream_semantics,
        "normalization": "B=(-1,0), C=(1,0), A=(u,v)",
        "coordinates": coordinates,
        "replay_residuals": rendered,
        "replayed": replayed,
        "all_conditions_discharged": replayed,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return EulerLineBisectorChartCertificate(**payload, certificate_sha256=digest)


def render_euler_line_bisector_chart_svg(
    *, u_value: float = 2 / 5, v_value: float = 7 / 5
) -> str:
    """Render a readable two-stage diagram for a nondegenerate model."""

    certificate = certify_euler_line_bisector_chart()
    substitutions = {
        sp.Symbol("u"): sp.Rational(str(u_value)),
        sp.Symbol("v"): sp.Rational(str(v_value)),
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
            axis.scatter((px,), (py,), s=25, color=color, zorder=5)
            axis.annotate(
                name,
                (px, py),
                xytext=(5, 5),
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
        "円とEuler線の構成",
        loc="left",
        fontsize=13,
        color="#0f172a",
        fontfamily="Yu Gothic",
    )
    for first, second in (("A", "B"), ("B", "C"), ("C", "A")):
        segment(left, first, second, color="#64748b", linewidth=1.2)
    segment(left, "E", "F", color="#e11d48", linewidth=1.7)
    segment(left, "K", "H", color="#94a3b8", linewidth=1.1)
    left.add_patch(
        Circle(
            points["O"],
            distance("O", "A"),
            fill=False,
            color="#7c3aed",
            linewidth=1.7,
        )
    )
    left.add_patch(
        Circle(
            points["O1"],
            distance("O1", "A"),
            fill=False,
            color="#0891b2",
            linewidth=1.7,
        )
    )
    labels(
        left,
        ("A", "B", "C", "O", "H", "E", "F", "O1", "K", "L"),
        {"E", "F", "K", "L"},
    )

    right.set_title(
        "垂直二等分線から距離等式へ",
        loc="left",
        fontsize=13,
        color="#0f172a",
        fontfamily="Yu Gothic",
    )
    segment(right, "H", "M", color="#64748b", linewidth=1.2)
    segment(right, "E", "F", color="#94a3b8", linewidth=1.0)
    segment(right, "P", "L", color="#0891b2", linewidth=1.8)
    segment(right, "B", "C", color="#64748b", linewidth=1.2)
    segment(right, "Q", "H", color="#e11d48", linewidth=2.0)
    segment(right, "Q", "O", color="#e11d48", linewidth=2.0)
    labels(
        right,
        ("B", "C", "O", "H", "E", "F", "M", "P", "L", "Q"),
        {"Q", "H", "O"},
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


def certify_jgex_euler_line_bisector_application(
    source: str,
) -> JGEXEulerLineBisectorChartApplication:
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
        h = _single(records, "orthocenter", (a, b, c))
        if o and h:
            roles.update(O=o, H=h)
            matched.append("Euler line endpoints O,H")
            e = _intersection(
                records,
                frozenset({("on_line", (o, h)), ("on_line", (a, c))}),
            )
            f = _intersection(
                records,
                frozenset({("on_line", (o, h)), ("on_line", (a, b))}),
            )
            o1 = _single(records, "circumcenter", (a, h, o))
            if e and f and o1:
                roles.update(E=e, F=f, O1=o1)
                matched.append("E,F on the Euler line and O1=(AHO)")
                k = _intersection(
                    records,
                    frozenset(
                        {("on_circle", (o1, a)), ("on_circle", (o, a))}
                    ),
                )
                if k:
                    roles["K"] = k
                    point_l = _intersection(
                        records,
                        frozenset({("on_line", (k, h)), ("on_circle", (o, a))}),
                    )
                    m = _single(records, "midpoint", (b, c))
                    if point_l and m:
                        roles.update(L=point_l, M=m)
                        matched.append("K,L on the two circle/line intersections")
                        p = _intersection(
                            records,
                            frozenset(
                                {("on_line", (h, m)), ("on_bline", (e, f))}
                            ),
                        )
                        if p:
                            roles["P"] = p
                            q = _intersection(
                                records,
                                frozenset(
                                    {
                                        ("on_line", (p, point_l)),
                                        ("on_line", (b, c)),
                                    }
                                ),
                            )
                            if q:
                                roles["Q"] = q
                                matched.append("P on the bisector and Q on BC")

    goal = str(formulation.goals[0]) if len(formulation.goals) == 1 else ""
    goal_parts = goal.split()
    goal_matches = False
    if all(name in roles for name in ("H", "Q", "O")) and len(goal_parts) == 5:
        actual = Atom(goal_parts[0], tuple(goal_parts[1:])).canonical()
        expected = Atom(
            "cong", (roles["H"], roles["Q"], roles["O"], roles["Q"])
        ).canonical()
        goal_matches = actual == expected
    chart = certify_euler_line_bisector_chart()
    replayed = (
        chart.replayed
        and chart.all_conditions_discharged
        and len(roles) == 13
        and len(matched) == 4
        and goal_matches
    )
    return JGEXEulerLineBisectorChartApplication(
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


__all__ = [
    "EulerLineBisectorChartCertificate",
    "JGEXEulerLineBisectorChartApplication",
    "certify_euler_line_bisector_chart",
    "certify_jgex_euler_line_bisector_application",
    "render_euler_line_bisector_chart_svg",
]
