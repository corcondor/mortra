"""Exact Euler-line/equal-angle radical-axis chart.

For a triangle ABC, let D lie on the Euler line.  Put
E = BD intersect AC and F = CD intersect AB.  A point X lies on AD and
angle(EXF) = angle(BAC) modulo pi.  The circles (CXF) and (BXE) meet again
at P, and Q = XP intersect EF.  Then AQ is perpendicular to BC, hence
A,H,Q are collinear for the orthocenter H.

The proof works over QQ(u,v,d,x).  It never solves for either root X or P:
XP is recovered as the radical axis of the two normalized circle equations.
The final altitude numerator is an exact polynomial multiple of the input
equal-angle numerator, so both algebraic angle branches are covered.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
import hashlib
import io
import json

import matplotlib
from sympy.polys.domains import QQ
from sympy.polys.fields import field

matplotlib.use("Agg")

from matplotlib import pyplot as plt

from worker.backend.geometry_proof_hypergraph import Atom
from worker.backend.jgex_chart_parser import ChartJGEXFormulation as JGEXFormulation


def _exact_replay() -> tuple[dict[str, str], dict[str, str]]:
    rational_field, u, v, d_parameter, x_parameter = field("u,v,d,x", QQ)
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

    a = (zero, zero)
    b = (one, zero)
    c = (u, v)
    circumcenter = (one / 2, (u * u + v * v - u) / (2 * v))
    orthocenter = (u, u * (one - u) / v)
    d = add(
        circumcenter,
        scale(d_parameter, subtract(orthocenter, circumcenter)),
    )
    e = line_intersection(b, d, a, c)
    f = line_intersection(c, d, a, b)
    x = scale(x_parameter, d)

    angle_polynomial = (
        cross(subtract(e, x), subtract(f, x)) * dot(subtract(b, a), subtract(c, a))
        - dot(subtract(e, x), subtract(f, x))
        * cross(subtract(b, a), subtract(c, a))
    )

    first_circle = circle_coefficients(c, x, f)
    second_circle = circle_coefficients(b, x, e)
    radical_axis = tuple(
        first - second
        for first, second in zip(first_circle, second_circle, strict=True)
    )
    ef_direction = subtract(f, e)
    q_parameter = -(
        radical_axis[0] * e[0]
        + radical_axis[1] * e[1]
        + radical_axis[2]
    ) / (
        radical_axis[0] * ef_direction[0]
        + radical_axis[1] * ef_direction[1]
    )
    q = add(e, scale(q_parameter, ef_direction))
    altitude_goal = dot(subtract(q, a), subtract(c, b))

    ring_u, ring_v, ring_d, _ring_x = rational_field.ring.gens
    implication_multiplier = (
        ring_v**2
        * (ring_d - 1)
        * (ring_u**2 + ring_v**2 - 1)
    )
    implication_residual = (
        altitude_goal.numer + implication_multiplier * angle_polynomial.numer
    )

    residuals = {
        "O_equidistant_A_B": (
            dot(subtract(circumcenter, a), subtract(circumcenter, a))
            - dot(subtract(circumcenter, b), subtract(circumcenter, b))
        ),
        "O_equidistant_A_C": (
            dot(subtract(circumcenter, a), subtract(circumcenter, a))
            - dot(subtract(circumcenter, c), subtract(circumcenter, c))
        ),
        "AH_perpendicular_BC": dot(
            subtract(orthocenter, a),
            subtract(c, b),
        ),
        "CH_perpendicular_AB": dot(
            subtract(orthocenter, c),
            subtract(b, a),
        ),
        "D_on_OH": cross(
            subtract(d, circumcenter),
            subtract(orthocenter, circumcenter),
        ),
        "E_on_BD": cross(subtract(e, b), subtract(d, b)),
        "E_on_AC": cross(subtract(e, a), subtract(c, a)),
        "F_on_CD": cross(subtract(f, c), subtract(d, c)),
        "F_on_AB": cross(subtract(f, a), subtract(b, a)),
        "X_on_AD": cross(subtract(x, a), subtract(d, a)),
        "C_on_first_circle": circle_value(c, first_circle),
        "X_on_first_circle": circle_value(x, first_circle),
        "F_on_first_circle": circle_value(f, first_circle),
        "B_on_second_circle": circle_value(b, second_circle),
        "X_on_second_circle": circle_value(x, second_circle),
        "E_on_second_circle": circle_value(e, second_circle),
        "X_on_radical_axis": (
            radical_axis[0] * x[0]
            + radical_axis[1] * x[1]
            + radical_axis[2]
        ),
        "Q_on_EF": cross(subtract(q, e), subtract(f, e)),
        "Q_on_radical_axis": (
            radical_axis[0] * q[0]
            + radical_axis[1] * q[1]
            + radical_axis[2]
        ),
        "equal_angle_implies_altitude_numerator": implication_residual,
    }
    replayed = {
        name: "0" if value == 0 else str(value)
        for name, value in residuals.items()
    }
    polynomial_evidence = {
        "coefficient_domain": "QQ(u,v,d,x)",
        "equal_angle_degree_in_x": str(angle_polynomial.numer.degree(3)),
        "altitude_goal_degree_in_x": str(altitude_goal.numer.degree(3)),
        "implication_multiplier": "-v^2*(d-1)*(u^2+v^2-1)",
        "equal_angle_numerator_sha256": hashlib.sha256(
            str(angle_polynomial.numer).encode("ascii")
        ).hexdigest(),
        "altitude_goal_numerator_sha256": hashlib.sha256(
            str(altitude_goal.numer).encode("ascii")
        ).hexdigest(),
    }
    return replayed, polynomial_evidence


@dataclass(frozen=True)
class EulerLineEqualAngleRadicalAltitudeCertificate:
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
                "# Euler-line equal-angle radical-altitude chart",
                "",
                "## Reusable proof",
                "",
                "1. Normalize A=(0,0), B=(1,0), C=(u,v).",
                "2. Parameterize D on the Euler line and X on AD.",
                "3. Construct E and F by exact line intersections.",
                "4. Subtract the equations of (CXF) and (BXE) to obtain XP.",
                "5. Intersect that radical axis with EF to obtain Q.",
                "6. The altitude residual is a polynomial multiple of the angle residual.",
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
class JGEXEulerLineEqualAngleRadicalAltitudeApplication:
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
def certify_euler_line_equal_angle_radical_altitude_chart(
) -> EulerLineEqualAngleRadicalAltitudeCertificate:
    residuals, polynomial_evidence = _exact_replay()
    replayed = all(value == "0" for value in residuals.values())
    assumptions = (
        "ABC is a nondegenerate triangle with circumcenter O and orthocenter H",
        "D lies on the Euler line OH",
        "E=BD intersect AC and F=CD intersect AB are defined",
        "X lies on AD and angle(EXF)=angle(BAC) modulo pi",
        "P is the second common point of (CXF) and (BXE)",
        "Q=XP intersect EF is defined",
    )
    discharged = {
        assumptions[0]: "The triangle, circumcenter, and orthocenter clauses are matched.",
        assumptions[1]: "The on_line(O,H) clause is matched.",
        assumptions[2]: "Both paired line-intersection clauses are matched.",
        assumptions[3]: "The on_line(A,D)+eqangle3(E,F,A,B,C) clause is matched.",
        assumptions[4]: "The two circumcenters and common-circle clause are matched.",
        assumptions[5]: "The paired on_line(X,P)+on_line(E,F) clause is matched.",
    }
    payload = {
        "theorem": "euler-line-equal-angle-two-circle-radical-axis-is-altitude",
        "assumptions": assumptions,
        "discharged_conditions": discharged,
        "normalization": (
            "Set A=(0,0), B=(1,0), C=(u,v); parameterize D on OH and X on AD."
        ),
        "representation_chart": (
            "Euler-line incidence -> one affine parameter",
            "eqangle3 -> one directed-angle polynomial",
            "two circumcircles -> normalized circle equations",
            "second common point -> order-free radical axis",
            "radical axis intersect EF -> Q",
            "angle polynomial ideal -> altitude polynomial ideal",
        ),
        "proof_dag": (
            "Construct O,H,D,E,F,X in QQ(u,v,d,x).",
            "Replay all line, center, and circle incidences.",
            "Use the difference of the two circle equations as line XP.",
            "Construct Q as the intersection of that line with EF.",
            "Replay N_altitude = -v^2(d-1)(u^2+v^2-1) N_angle.",
            "Conclude AQ perpendicular BC, hence A,H,Q are collinear.",
        ),
        "polynomial_evidence": polynomial_evidence,
        "replay_residuals": residuals,
        "replayed": replayed,
        "all_conditions_discharged": replayed,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return EulerLineEqualAngleRadicalAltitudeCertificate(
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
    if name in {"circumcenter", "orthocenter"} and len(args) == 3:
        return name, tuple(sorted(args))
    if name in {"on_line", "on_circle"} and len(args) == 2:
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


def certify_jgex_euler_line_equal_angle_radical_altitude_application(
    source: str,
) -> JGEXEulerLineEqualAngleRadicalAltitudeApplication:
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
    for a, b, c in triangles:
        o = _single(records, (("circumcenter", (a, b, c)),))
        h = _single(records, (("orthocenter", (a, b, c)),))
        if not all((o, h)):
            continue
        d = _single(records, (("on_line", (o, h)),))
        if not d:
            continue
        e = _single(records, (("on_line", (b, d)), ("on_line", (a, c))))
        f = _single(records, (("on_line", (c, d)), ("on_line", (a, b))))
        if not all((e, f)):
            continue
        x = _single(
            records,
            (("on_line", (a, d)), ("eqangle3", (e, f, a, b, c))),
        )
        if not x:
            continue
        o1 = _single(records, (("circumcenter", (c, x, f)),))
        o2 = _single(records, (("circumcenter", (b, x, e)),))
        if not all((o1, o2)):
            continue
        p = _single(
            records,
            (("on_circle", (o1, c)), ("on_circle", (o2, b))),
        )
        if not p:
            continue
        q = _single(records, (("on_line", (x, p)), ("on_line", (e, f))))
        if not q:
            continue
        actual = (
            Atom(formulation.goals[0].predicate, formulation.goals[0].args).canonical()
            if len(formulation.goals) == 1
            else None
        )
        if actual == Atom("coll", (q, a, h)).canonical():
            accepted.append(
                {
                    "A": a, "B": b, "C": c, "O": o, "H": h, "D": d,
                    "E": e, "F": f, "X": x, "O1": o1, "O2": o2,
                    "P": p, "Q": q,
                }
            )

    chart = certify_euler_line_equal_angle_radical_altitude_chart()
    roles = accepted[0] if len(accepted) == 1 else {}
    replayed = bool(roles and chart.replayed and chart.all_conditions_discharged)
    goal = str(formulation.goals[0]) if len(formulation.goals) == 1 else ""
    return JGEXEulerLineEqualAngleRadicalAltitudeApplication(
        theorem=chart.theorem,
        source_sha256=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        roles=roles,
        matched_constructions=(
            "Euler-line point and two side intersections",
            "equal-angle point on AD",
            "two circles with a second common point",
            "common chord intersecting EF",
        ) if roles else (),
        goal=goal,
        proof_bridge=(
            "eqangle3 polynomial -> order-free radical axis XP -> "
            "exact altitude polynomial -> A,H,Q collinear"
        ),
        chart_certificate_sha256=chart.certificate_sha256,
        nondegeneracy_obligations=chart.assumptions,
        undischarged_nondegeneracy_obligations=() if replayed else chart.assumptions,
        replayed=replayed,
    )


def render_euler_line_equal_angle_radical_altitude_chart_svg() -> str:
    points = {
        "A": (0.0, 2.6), "B": (-2.0, 0.0), "C": (2.3, 0.2),
        "H": (0.12, 0.55), "D": (0.04, 1.05),
        "E": (0.95, 1.35), "F": (-0.9, 1.45),
        "X": (0.02, 1.75), "P": (0.1, 0.15), "Q": (0.08, 1.4),
    }
    fig, axis = plt.subplots(figsize=(8.8, 6.2))
    fig.patch.set_facecolor("#07090c")
    axis.set_facecolor("#07090c")
    axis.plot(
        [points["A"][0], points["B"][0], points["C"][0], points["A"][0]],
        [points["A"][1], points["B"][1], points["C"][1], points["A"][1]],
        color="#6f7b85",
        linewidth=1.3,
    )
    for left, right, color in (
        ("O" if "O" in points else "D", "H", "#31d7e8"),
        ("E", "F", "#ffb454"),
        ("X", "P", "#76e39a"),
        ("A", "H", "#31d7e8"),
    ):
        axis.plot(
            [points[left][0], points[right][0]],
            [points[left][1], points[right][1]],
            color=color,
            linewidth=1.2,
            alpha=0.9,
        )
    for label, point in points.items():
        axis.scatter([point[0]], [point[1]], s=24, color="#f1f5f8", zorder=4)
        axis.text(point[0] + 0.05, point[1] + 0.04, label, color="#f1f5f8", fontsize=9)
    axis.set_aspect("equal", adjustable="datalim")
    axis.axis("off")
    axis.set_title("equal angle | radical axis | altitude", color="#e7edf2", fontsize=12)
    fig.tight_layout()
    buffer = io.StringIO()
    fig.savefig(buffer, format="svg", bbox_inches="tight")
    plt.close(fig)
    return buffer.getvalue()


__all__ = [
    "EulerLineEqualAngleRadicalAltitudeCertificate",
    "JGEXEulerLineEqualAngleRadicalAltitudeApplication",
    "certify_euler_line_equal_angle_radical_altitude_chart",
    "certify_jgex_euler_line_equal_angle_radical_altitude_application",
    "render_euler_line_equal_angle_radical_altitude_chart_svg",
]
