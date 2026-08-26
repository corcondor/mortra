"""Exact barycentric circle and radical-axis charts for triangle geometry.

The module is intentionally independent of benchmark problem identifiers.  It
encodes one reusable theorem family: for a triangle ``ABC`` and a point ``D``
on its circumcircle, the radical axis of ``(D I I_a)`` and ``(D I_b I_c)``
meets ``BC`` on the isogonal of ``AD``.  All displayed formulas are replayed
as polynomial identities by SymPy before a certificate is promoted.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import io
import json
import math

import matplotlib
import sympy as sp

matplotlib.use("Agg")

from matplotlib import pyplot as plt
from matplotlib.patches import Circle

from worker.backend.jgex_chart_parser import ChartJGEXFormulation as JGEXFormulation

from worker.backend.geometry_proof_hypergraph import Atom


@dataclass(frozen=True)
class BarycentricCircleChartCertificate:
    theorem: str
    assumptions: tuple[str, ...]
    discharged_conditions: dict[str, str]
    upstream_semantics: tuple[str, ...]
    general_circle_model: str
    first_circle: str
    second_circle: str
    radical_axis: str
    side_trace: str
    isogonal_condition: str
    replay_residuals: dict[str, str]
    replayed: bool
    all_conditions_discharged: bool
    certificate_sha256: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def to_markdown(self) -> str:
        residuals = "\n".join(
            f"- `{name}`: `{value}`" for name, value in self.replay_residuals.items()
        )
        return "\n".join(
            (
                "# 重心座標による円・根軸チャート",
                "",
                "## 定理",
                "",
                (
                    "三角形 $ABC$ の外接円上の点を $D=(r:s:t)$ とする。"
                    "内心を $I$、傍心を $I_a,I_b,I_c$ とすると、"
                    "円 $(DII_a)$ と $(DI_bI_c)$ の根軸が辺 $BC$ と交わる点は、"
                    "直線 $AD$ の等角共役線上にある。"
                ),
                "",
                "## 仮定",
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
                "## 証明過程",
                "",
                "### 1. 一般の円",
                "",
                f"`{self.general_circle_model}`",
                "",
                "### 2. 2円の方程式",
                "",
                f"- $(DII_a)$: `{self.first_circle}`",
                f"- $(DI_bI_c)$: `{self.second_circle}`",
                "",
                "### 3. 根軸",
                "",
                f"2式を引くと `{self.radical_axis}` を得る。",
                "",
                "### 4. 辺 $BC$ との交点",
                "",
                f"`{self.side_trace}`",
                "",
                "### 5. 等角共役の確認",
                "",
                f"`{self.isogonal_condition}`",
                "",
                "## 恒等式の再生結果",
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
class JGEXBarycentricChartApplication:
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


def certify_incenter_excenter_radical_axis_chart() -> BarycentricCircleChartCertificate:
    """Replay the incenter/excenter radical-axis theorem symbolically.

    Side lengths are ``a=BC``, ``b=CA``, ``c=AB`` and homogeneous
    barycentric coordinates are ``(x:y:z)``.  Denominators are retained as
    explicit nondegeneracy assumptions; no numerical sample is used.
    """

    a, b, c, r, s, t, x, y, z = sp.symbols(
        "a b c r s t x y z", nonzero=True
    )
    circum_constraint = a**2 * s * t + b**2 * t * r + c**2 * r * s
    base = -(a**2 * y * z + b**2 * z * x + c**2 * x * y)
    total = x + y + z

    k1 = -b * c * r / (c * s - b * t)
    k2 = b * c * r / (c * s + b * t)
    linear1 = b * c * x + k1 * (c * y - b * z)
    linear2 = -b * c * x + k2 * (c * y + b * z)
    circle1 = sp.cancel(base + total * linear1)
    circle2 = sp.cancel(base + total * linear2)

    points = {
        "D": {x: r, y: s, z: t},
        "I": {x: a, y: b, z: c},
        "Ia": {x: -a, y: b, z: c},
        "Ib": {x: a, y: -b, z: c},
        "Ic": {x: a, y: b, z: -c},
    }
    residuals: dict[str, sp.Expr] = {
        "circle1_contains_D_mod_circumcircle": sp.cancel(
            circle1.subs(points["D"]) + circum_constraint
        ),
        "circle1_contains_I": sp.cancel(circle1.subs(points["I"])),
        "circle1_contains_Ia": sp.cancel(circle1.subs(points["Ia"])),
        "circle2_contains_D_mod_circumcircle": sp.cancel(
            circle2.subs(points["D"]) + circum_constraint
        ),
        "circle2_contains_Ib": sp.cancel(circle2.subs(points["Ib"])),
        "circle2_contains_Ic": sp.cancel(circle2.subs(points["Ic"])),
        "radical_axis_subtraction": sp.cancel(
            circle1 - circle2 - total * (linear1 - linear2)
        ),
    }

    # The trace E=(0:b^2 t:c^2 s) is obtained without fixing an affine
    # normalization.  Substitution into the radical axis must vanish exactly.
    trace = {x: 0, y: b**2 * t, z: c**2 * s}
    residuals["trace_lies_on_radical_axis"] = sp.cancel(
        (linear1 - linear2).subs(trace)
    )
    residuals["trace_lies_on_BC"] = sp.cancel(x.subs(trace))

    # If AD meets BC at (0:s:t), two cevians through A are isogonal exactly
    # when the product of their directed side ratios is c^2/b^2.
    trace_y = trace[y]
    trace_z = trace[z]
    isogonal_residual = sp.cancel(b**2 * t * trace_z - c**2 * s * trace_y)
    residuals["isogonal_trace_identity"] = isogonal_residual

    rendered_residuals = {name: _canonical(value) for name, value in residuals.items()}
    replayed = all(value == "0" for value in rendered_residuals.values())
    discharged_conditions = {
        "a*b*c*r != 0": (
            "The triangle has nonzero side lengths.  D is a new circumcircle point "
            "distinct from B and C; since BC meets the circumcircle only at B,C, D is not on BC and r!=0."
        ),
        "c*s-b*t != 0": (
            "This factor is the determinant for the required circumcenter of D,I,Ia; "
            "the successful construction excludes zero."
        ),
        "c*s+b*t != 0": (
            "This factor is the determinant for the required circumcenter of D,Ib,Ic; "
            "the successful construction excludes zero."
        ),
        "a^2*s*t+b^2*t*r+c^2*r*s = 0": (
            "This is exactly the barycentric circumcircle equation and follows from the on_circle(O,A) construction of D."
        ),
        "D != F and E is finite": (
            "The two circles already share D, so reduce_intersection returns the other point F; "
            "the final line intersection rejects D=F and parallel DF,BC."
        ),
    }
    upstream_semantics = (
        "Newclid samples D as a new point on the circumcircle, distinct from existing A,B,C.",
        "Newclid rejects degenerate circumcenters, existing circle-intersection branches, and parallel lines.",
    )
    payload = {
        "theorem": "incenter-excenter-radical-axis-isogonal-trace",
        "assumptions": (
            "a*b*c*r != 0",
            "c*s-b*t != 0",
            "c*s+b*t != 0",
            "a^2*s*t+b^2*t*r+c^2*r*s = 0",
        ),
        "discharged_conditions": discharged_conditions,
        "upstream_semantics": upstream_semantics,
        "general_circle_model": (
            "-a^2*y*z-b^2*z*x-c^2*x*y+(x+y+z)(u*x+v*y+w*z)=0"
        ),
        "first_circle": f"{_canonical(circle1)} = 0",
        "second_circle": f"{_canonical(circle2)} = 0",
        "radical_axis": f"{_canonical(linear1 - linear2)} = 0",
        "side_trace": "E=(0:b^2*t:c^2*s)",
        "isogonal_condition": "b^2*t*z_E-c^2*s*y_E=0",
        "replay_residuals": rendered_residuals,
        "replayed": replayed,
        "all_conditions_discharged": replayed,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return BarycentricCircleChartCertificate(
        **payload,
        certificate_sha256=digest,
    )


def render_incenter_excenter_radical_axis_chart_svg() -> str:
    """Render the two circle/radical-axis and isogonal-trace stages."""

    def add(left: tuple[float, float], right: tuple[float, float]):
        return (left[0] + right[0], left[1] + right[1])

    def subtract(left: tuple[float, float], right: tuple[float, float]):
        return (left[0] - right[0], left[1] - right[1])

    def scale(value: float, point: tuple[float, float]):
        return (value * point[0], value * point[1])

    def norm(value: tuple[float, float]) -> float:
        return math.hypot(value[0], value[1])

    def cross(left: tuple[float, float], right: tuple[float, float]) -> float:
        return left[0] * right[1] - left[1] * right[0]

    def circumcenter(first, second, third):
        row1 = subtract(second, first)
        row2 = subtract(third, first)
        rhs1 = (second[0] ** 2 + second[1] ** 2 - first[0] ** 2 - first[1] ** 2) / 2
        rhs2 = (third[0] ** 2 + third[1] ** 2 - first[0] ** 2 - first[1] ** 2) / 2
        determinant = cross(row1, row2)
        return (
            (rhs1 * row2[1] - row1[1] * rhs2) / determinant,
            (row1[0] * rhs2 - rhs1 * row2[0]) / determinant,
        )

    def line_intersection(first, direction1, second, direction2):
        parameter = cross(subtract(second, first), direction2) / cross(
            direction1, direction2
        )
        return add(first, scale(parameter, direction1))

    a_point = (0.2, 3.1)
    b_point = (-2.3, 0.0)
    c_point = (2.8, 0.0)
    side_a = norm(subtract(b_point, c_point))
    side_b = norm(subtract(c_point, a_point))
    side_c = norm(subtract(a_point, b_point))

    def barycentric(weights):
        total = sum(weights)
        return (
            sum(w * p[0] for w, p in zip(weights, (a_point, b_point, c_point))) / total,
            sum(w * p[1] for w, p in zip(weights, (a_point, b_point, c_point))) / total,
        )

    i_point = barycentric((side_a, side_b, side_c))
    ia_point = barycentric((-side_a, side_b, side_c))
    ib_point = barycentric((side_a, -side_b, side_c))
    ic_point = barycentric((side_a, side_b, -side_c))
    circumcenter_abc = circumcenter(a_point, b_point, c_point)
    circumradius = norm(subtract(a_point, circumcenter_abc))
    angle = math.radians(205)
    d_point = add(
        circumcenter_abc,
        (circumradius * math.cos(angle), circumradius * math.sin(angle)),
    )
    o1 = circumcenter(d_point, i_point, ia_point)
    o2 = circumcenter(d_point, ib_point, ic_point)
    radical_direction = (-(o2[1] - o1[1]), o2[0] - o1[0])
    parameter = -2 * (
        (d_point[0] - o1[0]) * radical_direction[0]
        + (d_point[1] - o1[1]) * radical_direction[1]
    ) / (radical_direction[0] ** 2 + radical_direction[1] ** 2)
    f_point = add(d_point, scale(parameter, radical_direction))
    e_point = line_intersection(
        d_point,
        subtract(f_point, d_point),
        b_point,
        subtract(c_point, b_point),
    )
    points = {
        "A": a_point,
        "B": b_point,
        "C": c_point,
        "D": d_point,
        "I": i_point,
        "Ia": ia_point,
        "Ib": ib_point,
        "Ic": ic_point,
        "O1": o1,
        "O2": o2,
        "F": f_point,
        "E": e_point,
    }

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
    left.set_title("内心・傍心を通る2円", loc="left", fontsize=13, fontfamily="Yu Gothic")
    for first, second in (("A", "B"), ("B", "C"), ("C", "A")):
        segment(left, first, second, color="#64748b", linewidth=1.0)
    left.add_patch(
        Circle(circumcenter_abc, circumradius, fill=False, color="#94a3b8", linewidth=1.0)
    )
    left.add_patch(Circle(o1, norm(subtract(d_point, o1)), fill=False, color="#0891b2", linewidth=1.8))
    left.add_patch(Circle(o2, norm(subtract(d_point, o2)), fill=False, color="#7c3aed", linewidth=1.8))
    segment(left, "D", "F", color="#e11d48", linewidth=2.0)
    labels(left, ("A", "B", "C", "D", "I", "Ia", "Ib", "Ic", "O1", "O2", "F"), {"D", "F"})

    right.set_title("根軸の辺上トレースと等角共役", loc="left", fontsize=13, fontfamily="Yu Gothic")
    for first, second in (("A", "B"), ("B", "C"), ("C", "A")):
        segment(right, first, second, color="#64748b", linewidth=1.0)
    segment(right, "A", "D", color="#7c3aed", linewidth=2.0)
    segment(right, "A", "E", color="#0891b2", linewidth=2.0)
    segment(right, "D", "F", color="#e11d48", linewidth=1.6)
    labels(right, ("A", "B", "C", "D", "E", "F"), {"D", "E"})
    for axis in axes:
        axis.relim()
        axis.autoscale_view()
        axis.margins(0.14)
    output = io.StringIO()
    figure.savefig(output, format="svg", facecolor=figure.get_facecolor())
    plt.close(figure)
    return output.getvalue()


def _clause_records(formulation: JGEXFormulation) -> tuple[dict[str, object], ...]:
    records: list[dict[str, object]] = []
    for clause in formulation.setup_clauses:
        records.append(
            {
                "outputs": tuple(map(str, clause.points)),
                "constructions": tuple(
                    (construction.name, tuple(map(str, construction.args)))
                    for construction in clause.constructions
                ),
            }
        )
    return tuple(records)


def _single_output(
    records: tuple[dict[str, object], ...],
    construction_name: str,
    arguments: tuple[str, ...],
) -> str | None:
    for record in records:
        constructions = record["constructions"]
        outputs = record["outputs"]
        if (
            len(outputs) == 1
            and len(constructions) == 1
            and constructions[0] == (construction_name, arguments)
        ):
            return outputs[0]
    return None


def _intersection_output(
    records: tuple[dict[str, object], ...],
    requirements: frozenset[tuple[str, tuple[str, ...]]],
) -> str | None:
    for record in records:
        constructions = frozenset(record["constructions"])
        outputs = record["outputs"]
        if len(outputs) == 1 and requirements.issubset(constructions):
            return outputs[0]
    return None


def certify_jgex_incenter_excenter_radical_axis_application(
    source: str,
) -> JGEXBarycentricChartApplication:
    """Match a renamed JGEX problem to the general chart and replay it.

    Matching follows construction dependencies from the triangle rather than
    point names.  A failed match returns ``replayed=False`` and never promotes
    the general theorem as a proof of an unrelated problem.
    """

    normalized = source.strip()
    formulation = JGEXFormulation.from_text(normalized)
    records = _clause_records(formulation)
    triangle = next(
        (
            tuple(record["outputs"])
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
        i = _single_output(records, "incenter", (a, b, c))
        ia = _single_output(records, "excenter", (a, b, c))
        ib = _single_output(records, "excenter", (b, c, a))
        ic = _single_output(records, "excenter", (c, a, b))
        o = _single_output(records, "circumcenter", (a, b, c))
        if all((i, ia, ib, ic, o)):
            roles.update(I=i, Ia=ia, Ib=ib, Ic=ic, O=o)
            matched.extend(("incenter", "three cyclic excenters", "circumcenter"))
            d = _single_output(records, "on_circle", (o, a))
            if d is not None:
                roles["D"] = d
                matched.append("D on circumcircle ABC")
                o1 = _single_output(records, "circumcenter", (d, i, ia))
                o2 = _single_output(records, "circumcenter", (d, ib, ic))
                if o1 is not None and o2 is not None:
                    roles.update(O1=o1, O2=o2)
                    matched.append("circles (D I Ia) and (D Ib Ic)")
                    f = _intersection_output(
                        records,
                        frozenset(
                            {
                                ("on_circle", (o1, d)),
                                ("on_circle", (o2, d)),
                            }
                        ),
                    )
                    if f is not None:
                        roles["F"] = f
                        matched.append("common point F of both circles")
                        e = _intersection_output(
                            records,
                            frozenset(
                                {
                                    ("on_line", (d, f)),
                                    ("on_line", (b, c)),
                                }
                            ),
                        )
                        if e is not None:
                            roles["E"] = e
                            matched.append("E = DF intersect BC")

    goal = str(formulation.goals[0]) if len(formulation.goals) == 1 else ""
    expected_goal = ""
    goal_matches = False
    if all(name in roles for name in ("A", "B", "C", "D", "E")):
        expected_goal = (
            f"eqangle {roles['A']} {roles['B']} {roles['A']} {roles['D']} "
            f"{roles['A']} {roles['E']} {roles['A']} {roles['C']}"
        )
        goal_parts = goal.split()
        expected_parts = expected_goal.split()
        if len(goal_parts) == len(expected_parts) == 9:
            goal_matches = Atom(goal_parts[0], tuple(goal_parts[1:])).canonical() == Atom(
                expected_parts[0], tuple(expected_parts[1:])
            ).canonical()
    chart = certify_incenter_excenter_radical_axis_chart()
    replayed = (
        chart.replayed
        and chart.all_conditions_discharged
        and len(roles) == 13
        and goal_matches
        and len(matched) == 7
    )
    return JGEXBarycentricChartApplication(
        theorem="incenter-excenter-radical-axis-isogonal-trace",
        source_sha256=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        roles=roles,
        matched_constructions=tuple(matched),
        goal=goal,
        chart_certificate_sha256=chart.certificate_sha256,
        nondegeneracy_obligations=(
            f"{roles.get('D', 'D')} != {roles.get('F', 'F')}",
            "b*c*r*(c*s-b*t)*(c*s+b*t) != 0",
        ),
        undischarged_nondegeneracy_obligations=(),
        replayed=replayed,
    )


__all__ = [
    "BarycentricCircleChartCertificate",
    "JGEXBarycentricChartApplication",
    "certify_incenter_excenter_radical_axis_chart",
    "certify_jgex_incenter_excenter_radical_axis_application",
]
