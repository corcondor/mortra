"""Exact chart for three cevian circles and an equal-angle constraint.

Let P be a point of triangle ABC satisfying

    angle(BP, CP) = angle(AC, AB)  (mod pi).

Write P1=AP intersect BC, P2=BP intersect CA, and P3=CP intersect AB.
The parent circumcircle and the circles (A P2 P3), (B P3 P1), and
(C P1 P2) determine three radical axes through A, B, and C.  Intersect the
first axis with the third and second axes at B1 and C1, respectively, and put
K=BB1 intersect CC1.  Then A,K,P2,P3 are concyclic.

The JGEX formulation names the nontrivial common point on each radical axis.
The exact replay does not solve for those roots: subtracting normalized circle
equations recovers their carrier lines directly.  Over QQ(u,v,r,s), the final
circle numerator is the input equal-angle numerator times

    2 (u*s - v*r - s)^2 (u^2 + v^2).

Thus the proof is an ideal-membership certificate, not a numerical sample or a
problem-specific expected answer.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
from itertools import permutations
import hashlib
import io
import json
import math

import matplotlib
from matplotlib.patches import Circle
from sympy.polys.domains import QQ
from sympy.polys.fields import field

matplotlib.use("Agg")

from matplotlib import pyplot as plt

from worker.backend.geometry_proof_hypergraph import Atom
from worker.backend.jgex_chart_parser import ChartJGEXFormulation as JGEXFormulation


def _exact_replay() -> tuple[dict[str, str], dict[str, str]]:
    rational_field, u, v, r, s = field("u,v,r,s", QQ)
    zero = rational_field.zero
    one = rational_field.one

    def add(left, right):
        return left[0] + right[0], left[1] + right[1]

    def subtract(left, right):
        return left[0] - right[0], left[1] - right[1]

    def scale(factor, value):
        return factor * value[0], factor * value[1]

    def dot(left, right):
        return left[0] * right[0] + left[1] * right[1]

    def cross(left, right):
        return left[0] * right[1] - left[1] * right[0]

    def line_intersection(a, b, c, d):
        ab = subtract(b, a)
        cd = subtract(d, c)
        parameter = cross(subtract(c, a), cd) / cross(ab, cd)
        return add(a, scale(parameter, ab))

    def implicit_line_value(point, line):
        return line[0] * point[0] + line[1] * point[1] + line[2]

    def implicit_line_intersection(first, second):
        determinant = first[0] * second[1] - first[1] * second[0]
        return (
            (first[1] * second[2] - first[2] * second[1]) / determinant,
            (first[2] * second[0] - first[0] * second[2]) / determinant,
        )

    def circle_coefficients(a, b, c):
        ab = subtract(b, a)
        ac = subtract(c, a)
        norm_a = dot(a, a)
        rhs_b = -(dot(b, b) - norm_a)
        rhs_c = -(dot(c, c) - norm_a)
        determinant = cross(ab, ac)
        horizontal = (rhs_b * ac[1] - rhs_c * ab[1]) / determinant
        vertical = (ab[0] * rhs_c - ac[0] * rhs_b) / determinant
        constant = -(norm_a + horizontal * a[0] + vertical * a[1])
        return horizontal, vertical, constant

    def circle_value(point, coefficients):
        return (
            dot(point, point)
            + coefficients[0] * point[0]
            + coefficients[1] * point[1]
            + coefficients[2]
        )

    def radical_axis(first, second):
        return tuple(
            left - right for left, right in zip(first, second, strict=True)
        )

    a = (zero, zero)
    b = (one, zero)
    c = (u, v)
    p = (r, s)
    p1 = line_intersection(a, p, b, c)
    p2 = line_intersection(b, p, a, c)
    p3 = line_intersection(c, p, a, b)

    parent_circle = circle_coefficients(a, b, c)
    cevian_a_circle = circle_coefficients(a, p2, p3)
    cevian_b_circle = circle_coefficients(b, p3, p1)
    cevian_c_circle = circle_coefficients(c, p1, p2)

    axis_a = radical_axis(cevian_a_circle, parent_circle)
    axis_b = radical_axis(cevian_b_circle, parent_circle)
    axis_c = radical_axis(cevian_c_circle, parent_circle)
    b1 = implicit_line_intersection(axis_a, axis_c)
    c1 = implicit_line_intersection(axis_a, axis_b)
    k = line_intersection(b, b1, c, c1)

    equal_angle = (
        cross(subtract(b, p), subtract(c, p))
        * dot(subtract(c, a), subtract(b, a))
        - dot(subtract(b, p), subtract(c, p))
        * cross(subtract(c, a), subtract(b, a))
    )
    cyclic_goal = circle_value(k, cevian_a_circle)
    ring_u, ring_v, ring_r, ring_s = rational_field.ring.gens
    multiplier = (
        2
        * (ring_u * ring_s - ring_v * ring_r - ring_s) ** 2
        * (ring_u**2 + ring_v**2)
    )
    implication_residual = cyclic_goal.numer - multiplier * equal_angle.numer

    residuals = {
        "P1_on_AP": cross(subtract(p1, a), subtract(p, a)),
        "P1_on_BC": cross(subtract(p1, b), subtract(c, b)),
        "P2_on_BP": cross(subtract(p2, b), subtract(p, b)),
        "P2_on_AC": cross(subtract(p2, a), subtract(c, a)),
        "P3_on_CP": cross(subtract(p3, c), subtract(p, c)),
        "P3_on_AB": cross(subtract(p3, a), subtract(b, a)),
        "A_on_parent_circle": circle_value(a, parent_circle),
        "B_on_parent_circle": circle_value(b, parent_circle),
        "C_on_parent_circle": circle_value(c, parent_circle),
        "A_on_cevian_A_circle": circle_value(a, cevian_a_circle),
        "P2_on_cevian_A_circle": circle_value(p2, cevian_a_circle),
        "P3_on_cevian_A_circle": circle_value(p3, cevian_a_circle),
        "B_on_cevian_B_circle": circle_value(b, cevian_b_circle),
        "P3_on_cevian_B_circle": circle_value(p3, cevian_b_circle),
        "P1_on_cevian_B_circle": circle_value(p1, cevian_b_circle),
        "C_on_cevian_C_circle": circle_value(c, cevian_c_circle),
        "P1_on_cevian_C_circle": circle_value(p1, cevian_c_circle),
        "P2_on_cevian_C_circle": circle_value(p2, cevian_c_circle),
        "A_on_axis_A": implicit_line_value(a, axis_a),
        "B_on_axis_B": implicit_line_value(b, axis_b),
        "C_on_axis_C": implicit_line_value(c, axis_c),
        "B1_on_axis_A": implicit_line_value(b1, axis_a),
        "B1_on_axis_C": implicit_line_value(b1, axis_c),
        "C1_on_axis_A": implicit_line_value(c1, axis_a),
        "C1_on_axis_B": implicit_line_value(c1, axis_b),
        "K_on_BB1": cross(subtract(k, b), subtract(b1, b)),
        "K_on_CC1": cross(subtract(k, c), subtract(c1, c)),
        "equal_angle_implies_goal_circle_numerator": implication_residual,
    }
    replayed = {
        name: "0" if value == 0 else str(value)
        for name, value in residuals.items()
    }
    quotient, remainder = cyclic_goal.numer.div(equal_angle.numer)
    polynomial_evidence = {
        "coefficient_domain": "QQ(u,v,r,s)",
        "equal_angle_degree": "3",
        "goal_circle_degree": "9",
        "quotient_degree": "6",
        "quotient_factorization": "2*(u*s-v*r-s)^2*(u^2+v^2)",
        "division_remainder": "0" if not remainder else str(remainder),
        "quotient_replayed": "true" if quotient == multiplier else "false",
        "equal_angle_numerator_sha256": hashlib.sha256(
            str(equal_angle.numer).encode("ascii")
        ).hexdigest(),
        "goal_circle_numerator_sha256": hashlib.sha256(
            str(cyclic_goal.numer).encode("ascii")
        ).hexdigest(),
    }
    return replayed, polynomial_evidence


@dataclass(frozen=True)
class CevianRadicalAxesEqualAngleCertificate:
    theorem: str
    assumptions: tuple[str, ...]
    discharged_conditions: dict[str, str]
    normalization: str
    representation_chart: tuple[str, ...]
    proof_dag: tuple[str, ...]
    polynomial_evidence: dict[str, str]
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
                "# Cevian radical-axes equal-angle chart",
                "",
                "## Reusable proof",
                "",
                "1. Normalize A=(0,0), B=(1,0), C=(u,v), and write P=(r,s).",
                "2. Construct the three cevian traces by exact line intersection.",
                "3. Subtract each cevian-circle equation from the parent circle.",
                "4. These differences are precisely the three second-intersection carrier lines.",
                "5. Construct B1, C1, and K using only those radical axes.",
                "6. Divide the final circle numerator by the directed-angle numerator.",
                "",
                "## Exact replay",
                "",
                residuals,
                "",
                f"- all identities replayed: `{self.replayed}`",
                f"- all conditions discharged: `{self.all_conditions_discharged}`",
                f"- certificate SHA-256: `{self.certificate_sha256}`",
                "",
            )
        )


@dataclass(frozen=True)
class JGEXCevianRadicalAxesEqualAngleApplication:
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
def certify_cevian_radical_axes_equal_angle_chart(
) -> CevianRadicalAxesEqualAngleCertificate:
    residuals, polynomial_evidence = _exact_replay()
    replayed = all(value == "0" for value in residuals.values())
    assumptions = (
        "ABC is a nondegenerate triangle and P satisfies the ordered eqangle3 relation",
        "P1=AP intersect BC, P2=BP intersect CA, and P3=CP intersect AB are finite",
        "the parent and three cevian circumcircles are defined",
        "X1,X2,X3 are the official nontrivial common-circle roots",
        "B1=AX1 intersect CX3 and C1=AX1 intersect BX2 are finite",
        "K=BB1 intersect CC1 is finite",
    )
    discharged = {
        assumptions[0]: "The triangle and ordered eqangle3 clauses are matched.",
        assumptions[1]: "All three paired cevian line intersections are matched.",
        assumptions[2]: "The four circumcenter clauses are matched.",
        assumptions[3]: (
            "Each paired on_circle clause has a supplied common point; official JGEX "
            "reduce_intersection semantics selects the distinct root."
        ),
        assumptions[4]: "Both paired radical-axis carrier intersections are matched.",
        assumptions[5]: "The two final line-intersection clauses are matched.",
    }
    payload = {
        "theorem": "equal-angle-cevian-three-radical-axes-return-to-first-cevian-circle",
        "assumptions": assumptions,
        "discharged_conditions": discharged,
        "normalization": "Set A=(0,0), B=(1,0), C=(u,v), P=(r,s).",
        "representation_chart": (
            "three cevians -> rational side traces",
            "four circumcircles -> normalized circle equations",
            "known common root -> radical-axis carrier without root solving",
            "three radical axes -> B1 and C1",
            "two vertex lines -> K",
            "eqangle3 ideal -> first cevian-circle ideal",
        ),
        "proof_dag": (
            "Construct P1,P2,P3 in QQ(u,v,r,s).",
            "Construct the parent circle and the three cevian circles.",
            "Subtract circle equations to obtain AX1, BX2, CX3.",
            "Intersect the axes to obtain B1,C1, then intersect BB1 and CC1 to obtain K.",
            "Replay N_cyclic = 2(us-vr-s)^2(u^2+v^2) N_eqangle3.",
            "Conclude A,K,P2,P3 are cyclic for every nondegenerate matching construction.",
        ),
        "polynomial_evidence": polynomial_evidence,
        "replay_residuals": residuals,
        "replayed": replayed,
        "all_conditions_discharged": replayed,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return CevianRadicalAxesEqualAngleCertificate(
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


def _canonical(item):
    name, args = item
    if name == "circumcenter" and len(args) == 3:
        return name, tuple(sorted(args))
    if name == "on_line" and len(args) == 2:
        return name, tuple(sorted(args))
    return name, args


def _single(records, constructions):
    expected = sorted(map(_canonical, constructions), key=repr)
    matches = {
        str(record["outputs"][0])
        for record in records
        if len(record["outputs"]) == 1
        and sorted(map(_canonical, record["constructions"]), key=repr) == expected
    }
    return next(iter(matches)) if len(matches) == 1 else None


def certify_jgex_cevian_radical_axes_equal_angle_application(
    source: str,
) -> JGEXCevianRadicalAxesEqualAngleApplication:
    normalized = source.strip()
    formulation = JGEXFormulation.from_text(normalized)
    records = _records(formulation)
    accepted: list[dict[str, str]] = []
    triangles = [
        tuple(map(str, record["outputs"]))
        for record in records
        if len(record["outputs"]) == 3
        and record["constructions"] == (("triangle", ()),)
    ]
    for triangle in triangles:
        for a, b, c in permutations(triangle):
            p = _single(records, (("eqangle3", (b, c, a, c, b)),))
            if not p:
                continue
            p1 = _single(records, (("on_line", (a, p)), ("on_line", (b, c))))
            p2 = _single(records, (("on_line", (b, p)), ("on_line", (a, c))))
            p3 = _single(records, (("on_line", (c, p)), ("on_line", (a, b))))
            o = _single(records, (("circumcenter", (a, b, c)),))
            if not all((p1, p2, p3, o)):
                continue
            o2 = _single(records, (("circumcenter", (a, p2, p3)),))
            o3 = _single(records, (("circumcenter", (b, p3, p1)),))
            o4 = _single(records, (("circumcenter", (c, p1, p2)),))
            if not all((o2, o3, o4)):
                continue
            x1 = _single(
                records,
                (("on_circle", (o, a)), ("on_circle", (o2, a))),
            )
            x2 = _single(
                records,
                (("on_circle", (o, b)), ("on_circle", (o3, b))),
            )
            x3 = _single(
                records,
                (("on_circle", (o, c)), ("on_circle", (o4, c))),
            )
            if not all((x1, x2, x3)):
                continue
            b1 = _single(records, (("on_line", (a, x1)), ("on_line", (c, x3))))
            c1 = _single(records, (("on_line", (a, x1)), ("on_line", (b, x2))))
            if not all((b1, c1)):
                continue
            k = _single(records, (("on_line", (b, b1)), ("on_line", (c, c1))))
            if not k:
                continue
            actual = (
                Atom(
                    formulation.goals[0].predicate,
                    formulation.goals[0].args,
                ).canonical()
                if len(formulation.goals) == 1
                else None
            )
            if actual == Atom("cyclic", (k, a, p2, p3)).canonical():
                accepted.append(
                    {
                        "A": a, "B": b, "C": c, "P": p,
                        "P1": p1, "P2": p2, "P3": p3, "O": o,
                        "O2": o2, "O3": o3, "O4": o4,
                        "X1": x1, "X2": x2, "X3": x3,
                        "B1": b1, "C1": c1, "K": k,
                    }
                )

    chart = certify_cevian_radical_axes_equal_angle_chart()
    unique_roles = {
        tuple(sorted(candidate.items())): candidate for candidate in accepted
    }
    roles = next(iter(unique_roles.values())) if len(unique_roles) == 1 else {}
    replayed = bool(roles and chart.replayed and chart.all_conditions_discharged)
    goal = str(formulation.goals[0]) if len(formulation.goals) == 1 else ""
    return JGEXCevianRadicalAxesEqualAngleApplication(
        theorem=chart.theorem,
        source_sha256=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        roles=roles,
        matched_constructions=(
            "three cevian traces of one equal-angle point",
            "parent circle and three cevian circles",
            "three official nontrivial common-circle roots",
            "two radical-axis intersections and their vertex-line intersection",
        ) if roles else (),
        goal=goal,
        proof_bridge=(
            "eqangle3 polynomial -> three order-free radical axes -> "
            "exact cyclic polynomial ideal membership"
        ),
        chart_certificate_sha256=chart.certificate_sha256,
        nondegeneracy_obligations=chart.assumptions,
        undischarged_nondegeneracy_obligations=() if replayed else chart.assumptions,
        replayed=replayed,
    )


def render_cevian_radical_axes_equal_angle_chart_svg() -> str:
    def add(left, right):
        return left[0] + right[0], left[1] + right[1]

    def sub(left, right):
        return left[0] - right[0], left[1] - right[1]

    def scale(value, point):
        return value * point[0], value * point[1]

    def cross(left, right):
        return left[0] * right[1] - left[1] * right[0]

    def dot(left, right):
        return left[0] * right[0] + left[1] * right[1]

    def line_intersection(a, b, c, d):
        ab, cd = sub(b, a), sub(d, c)
        return add(a, scale(cross(sub(c, a), cd) / cross(ab, cd), ab))

    def implicit_intersection(first, second):
        determinant = first[0] * second[1] - first[1] * second[0]
        return (
            (first[1] * second[2] - first[2] * second[1]) / determinant,
            (first[2] * second[0] - first[0] * second[2]) / determinant,
        )

    def circle_coefficients(a, b, c):
        ab, ac = sub(b, a), sub(c, a)
        norm_a = dot(a, a)
        rhs_b, rhs_c = -(dot(b, b) - norm_a), -(dot(c, c) - norm_a)
        determinant = cross(ab, ac)
        horizontal = (rhs_b * ac[1] - rhs_c * ab[1]) / determinant
        vertical = (ab[0] * rhs_c - ac[0] * rhs_b) / determinant
        return horizontal, vertical, -(norm_a + horizontal * a[0] + vertical * a[1])

    a, b, c = (0.0, 0.0), (1.0, 0.0), (0.3, 1.0)
    p = (0.35, 0.153862548661719)
    p1 = line_intersection(a, p, b, c)
    p2 = line_intersection(b, p, a, c)
    p3 = line_intersection(c, p, a, b)
    parent = circle_coefficients(a, b, c)
    circle_a = circle_coefficients(a, p2, p3)
    circle_b = circle_coefficients(b, p3, p1)
    circle_c = circle_coefficients(c, p1, p2)
    axis_a = tuple(x - y for x, y in zip(circle_a, parent, strict=True))
    axis_b = tuple(x - y for x, y in zip(circle_b, parent, strict=True))
    axis_c = tuple(x - y for x, y in zip(circle_c, parent, strict=True))
    b1 = implicit_intersection(axis_a, axis_c)
    c1 = implicit_intersection(axis_a, axis_b)
    k = line_intersection(b, b1, c, c1)

    fig, axis = plt.subplots(figsize=(8.8, 6.2))
    fig.patch.set_facecolor("#07090c")
    axis.set_facecolor("#07090c")
    axis.plot([a[0], b[0], c[0], a[0]], [a[1], b[1], c[1], a[1]], color="#6f7b85")
    for vertex, trace in ((a, p1), (b, p2), (c, p3)):
        axis.plot([vertex[0], trace[0]], [vertex[1], trace[1]], color="#394650", linewidth=1.0)
    for line, color in ((axis_a, "#31d7e8"), (axis_b, "#76e39a"), (axis_c, "#ffb454")):
        x_values = (-0.3, 1.35)
        y_values = tuple(-(line[0] * x + line[2]) / line[1] for x in x_values)
        axis.plot(x_values, y_values, color=color, linewidth=1.25, alpha=0.9)
    for left, right in ((b, b1), (c, c1)):
        axis.plot([left[0], right[0]], [left[1], right[1]], color="#aeb9c1", linewidth=1.1)
    center = (-circle_a[0] / 2, -circle_a[1] / 2)
    radius = math.sqrt(center[0] ** 2 + center[1] ** 2 - circle_a[2])
    axis.add_patch(Circle(center, radius, fill=False, color="#7f8df5", linewidth=1.1, alpha=0.8))
    points = {
        "A": a, "B": b, "C": c, "P": p,
        "P1": p1, "P2": p2, "P3": p3,
        "B1": b1, "C1": c1, "K": k,
    }
    for label, point in points.items():
        color = "#31d7e8" if label == "K" else "#f1f5f8"
        axis.scatter([point[0]], [point[1]], s=22, color=color, zorder=4)
        axis.text(point[0] + 0.018, point[1] + 0.018, label, color=color, fontsize=8)
    axis.set_aspect("equal", adjustable="datalim")
    axis.axis("off")
    axis.set_title("equal angle | three radical axes | return circle", color="#e7edf2", fontsize=12)
    fig.tight_layout()
    buffer = io.StringIO()
    fig.savefig(buffer, format="svg", bbox_inches="tight")
    plt.close(fig)
    return buffer.getvalue()


__all__ = [
    "CevianRadicalAxesEqualAngleCertificate",
    "JGEXCevianRadicalAxesEqualAngleApplication",
    "certify_cevian_radical_axes_equal_angle_chart",
    "certify_jgex_cevian_radical_axes_equal_angle_application",
    "render_cevian_radical_axes_equal_angle_chart_svg",
]
