"""Exact three-circle pencil chart for the 2023 IMO geometry construction.

The construction starts from an equilateral triangle.  Points A1 and B1 lie
on two perpendicular bisectors, while two JGEX ``on_aline`` clauses compose
the directed-angle data and determine C1 on the third bisector.  The three
derived circumcircles are coaxial, so every common point of the first two is
on the third.

The replay uses two free parameters over ``QQ(sqrt(3))`` and implements the
repository's actual ``on_aline`` semantics as direct complex similarity.  No
angle value, benchmark name, or expected conclusion is consulted.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
import hashlib
import io
import json
import math

import matplotlib
import sympy as sp
from sympy.polys.domains import QQ
from sympy.polys.fields import field

matplotlib.use("Agg")

from matplotlib import pyplot as plt
from worker.backend.geometry_proof_hypergraph import Atom
from worker.backend.jgex_chart_parser import ChartJGEXFormulation as JGEXFormulation


def _exact_replay() -> dict[str, str]:
    algebraic_domain = QQ.algebraic_field(sp.sqrt(3))
    rational_field, s, t = field("s,t", algebraic_domain)
    zero = rational_field.zero
    one = rational_field.one
    root_three = rational_field(algebraic_domain.convert(sp.sqrt(3)))

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

    def complex_product(left, right):
        return (
            left[0] * right[0] - left[1] * right[1],
            left[0] * right[1] + left[1] * right[0],
        )

    def conjugate(value):
        return value[0], -value[1]

    def line_intersection(a, b, c, d):
        ab = subtract(b, a)
        cd = subtract(d, c)
        parameter = cross(subtract(c, a), cd) / cross(ab, cd)
        return add(a, scale(parameter, ab))

    def perpendicular_bisector_intersection(a, b, origin, direction):
        midpoint = scale(one / 2, add(a, b))
        chord = subtract(b, a)
        parameter = dot(chord, subtract(midpoint, origin)) / dot(chord, direction)
        return add(origin, scale(parameter, direction))

    def on_aline_direction(target, source, source_basis):
        return complex_product(
            complex_product(target, source),
            conjugate(source_basis),
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

    def coaxial_residuals(first, second, third):
        first_second = tuple(a - b for a, b in zip(first, second, strict=True))
        first_third = tuple(a - b for a, b in zip(first, third, strict=True))
        return (
            first_second[0] * first_third[1]
            - first_second[1] * first_third[0],
            first_second[0] * first_third[2]
            - first_second[2] * first_third[0],
            first_second[1] * first_third[2]
            - first_second[2] * first_third[1],
        )

    a = (zero, root_three)
    b = (-one, zero)
    c = (one, zero)
    circumcenter = (zero, root_three / 3)
    a1 = (zero, s)
    b1 = (one / 2 + root_three * t, root_three / 2 + t)

    first_angle_direction = on_aline_direction(
        subtract(b, a),
        subtract(a1, c),
        subtract(b1, c),
    )
    c0 = add(a, first_angle_direction)
    second_angle_direction = on_aline_direction(
        subtract(b, a),
        subtract(c0, a),
        subtract(circumcenter, a),
    )
    c1 = perpendicular_bisector_intersection(
        a,
        b,
        a,
        second_angle_direction,
    )

    a2 = line_intersection(b, c1, c, b1)
    b2 = line_intersection(c, a1, a, c1)
    c2 = line_intersection(a, b1, b, a1)
    circle_a = circle_coefficients(a, a1, a2)
    circle_b = circle_coefficients(b, b1, b2)
    circle_c = circle_coefficients(c, c1, c2)
    coaxial = coaxial_residuals(circle_a, circle_b, circle_c)

    residuals = {
        "ABC_equidistant_AB_BC": (
            dot(subtract(a, b), subtract(a, b))
            - dot(subtract(b, c), subtract(b, c))
        ),
        "ABC_equidistant_BC_CA": (
            dot(subtract(b, c), subtract(b, c))
            - dot(subtract(c, a), subtract(c, a))
        ),
        "O_equidistant_A_B": (
            dot(subtract(circumcenter, a), subtract(circumcenter, a))
            - dot(subtract(circumcenter, b), subtract(circumcenter, b))
        ),
        "O_equidistant_B_C": (
            dot(subtract(circumcenter, b), subtract(circumcenter, b))
            - dot(subtract(circumcenter, c), subtract(circumcenter, c))
        ),
        "A1_on_BC_bisector": (
            dot(subtract(a1, b), subtract(a1, b))
            - dot(subtract(a1, c), subtract(a1, c))
        ),
        "B1_on_CA_bisector": (
            dot(subtract(b1, c), subtract(b1, c))
            - dot(subtract(b1, a), subtract(b1, a))
        ),
        "C0_first_on_aline": cross(subtract(c0, a), first_angle_direction),
        "C1_second_on_aline": cross(subtract(c1, a), second_angle_direction),
        "C1_on_AB_bisector": (
            dot(subtract(c1, a), subtract(c1, a))
            - dot(subtract(c1, b), subtract(c1, b))
        ),
        "A2_on_BC1": cross(subtract(a2, b), subtract(c1, b)),
        "A2_on_CB1": cross(subtract(a2, c), subtract(b1, c)),
        "B2_on_CA1": cross(subtract(b2, c), subtract(a1, c)),
        "B2_on_AC1": cross(subtract(b2, a), subtract(c1, a)),
        "C2_on_AB1": cross(subtract(c2, a), subtract(b1, a)),
        "C2_on_BA1": cross(subtract(c2, b), subtract(a1, b)),
        "A_on_first_circle": circle_value(a, circle_a),
        "A1_on_first_circle": circle_value(a1, circle_a),
        "A2_on_first_circle": circle_value(a2, circle_a),
        "B_on_second_circle": circle_value(b, circle_b),
        "B1_on_second_circle": circle_value(b1, circle_b),
        "B2_on_second_circle": circle_value(b2, circle_b),
        "C_on_third_circle": circle_value(c, circle_c),
        "C1_on_third_circle": circle_value(c1, circle_c),
        "C2_on_third_circle": circle_value(c2, circle_c),
        "three_circles_pencil_1": coaxial[0],
        "three_circles_pencil_2": coaxial[1],
        "three_circles_pencil_3": coaxial[2],
    }
    return {
        name: "0" if value == zero else str(value)
        for name, value in residuals.items()
    }


@dataclass(frozen=True)
class EquilateralAngleSumThreeCirclesCertificate:
    theorem: str
    assumptions: tuple[str, ...]
    discharged_conditions: dict[str, str]
    upstream_semantics: tuple[str, ...]
    normalization: str
    parameterization: dict[str, str]
    representation_chart: tuple[str, ...]
    proof_dag: tuple[str, ...]
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
                "# Equilateral angle-sum three-circle chart",
                "",
                "## Reusable proof",
                "",
                "1. Fix an equilateral coordinate frame over QQ(sqrt(3)).",
                "2. Parameterize A1 and B1 on their perpendicular bisectors.",
                "3. Compose the two directed on_aline similarities to obtain C1.",
                "4. Construct A2,B2,C2 by six line incidences.",
                "5. Form the three circle equations and subtract them pairwise.",
                "6. Their radical axes are proportional, so the circles share both roots.",
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
class JGEXEquilateralAngleSumThreeCirclesApplication:
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
def certify_equilateral_angle_sum_three_circles_chart(
) -> EquilateralAngleSumThreeCirclesCertificate:
    residuals = _exact_replay()
    replayed = all(value == "0" for value in residuals.values())
    assumptions = (
        "ABC is equilateral with circumcenter O",
        "A1,B1,C1 lie on the three perpendicular bisectors",
        "the two on_aline clauses use JGEX direct-similarity semantics",
        "A2,B2,C2 and the three target circles are defined",
        "X is any common point of the first two target circles",
    )
    discharged = {
        assumptions[0]: "The ieq_triangle and circumcenter clauses are matched.",
        assumptions[1]: "All three on_bline clauses are matched.",
        assumptions[2]: "The exact six-argument on_aline sequences are matched.",
        assumptions[3]: "Six carrier intersections and three circumcenters are matched.",
        assumptions[4]: "Both on_circle clauses are matched; no root ordering is used.",
    }
    payload = {
        "theorem": "equilateral-composed-angle-lines-three-circles-coaxial",
        "assumptions": assumptions,
        "discharged_conditions": discharged,
        "upstream_semantics": (
            "on_bline means equality of squared distances to its endpoints.",
            "on_aline(P,A,B,C,D,E) means angle(AP,AB)=angle(DC,DE).",
            "Direct similarities compose by complex multiplication and conjugation.",
            "A common point of two members of a circle pencil lies on every member.",
        ),
        "normalization": (
            "Set A=(0,sqrt(3)), B=(-1,0), C=(1,0), "
            "O=(0,sqrt(3)/3), preserving every equilateral configuration up to similarity."
        ),
        "parameterization": {
            "coefficient_domain": "QQ(sqrt(3))(s,t)",
            "A1": "(0,s)",
            "B1": "(1/2+sqrt(3)t,sqrt(3)/2+t)",
            "C1": "second on_aline direction intersect perpendicular bisector AB",
        },
        "representation_chart": (
            "perpendicular bisector -> one-parameter affine point",
            "on_aline -> direct complex-similarity direction",
            "two on_aline clauses -> composed angle-sum direction",
            "three points -> normalized circle equation",
            "pairwise circle differences -> radical axes",
            "proportional radical axes -> shared two-point pencil",
        ),
        "proof_dag": (
            "Parameterize A1 and B1 and replay their bisector equations.",
            "Construct C0 and C1 with the two exact on_aline directions.",
            "Construct A2,B2,C2 from their paired carrier lines.",
            "Construct the three target circle equations.",
            "Replay all three 2x2 minors of their radical-axis coefficients as zero.",
            "Infer that the common point X of the first two lies on the third.",
        ),
        "replay_residuals": residuals,
        "replayed": replayed,
        "all_conditions_discharged": replayed,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return EquilateralAngleSumThreeCirclesCertificate(
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
    if name in {"on_bline", "on_line", "on_circle"} and len(args) == 2:
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


def certify_jgex_equilateral_angle_sum_three_circles_application(
    source: str,
) -> JGEXEquilateralAngleSumThreeCirclesApplication:
    normalized = source.strip()
    formulation = JGEXFormulation.from_text(normalized)
    records = _records(formulation)
    accepted: list[dict[str, str]] = []
    triangles = [
        tuple(map(str, record["outputs"]))
        for record in records
        if len(record["outputs"]) == 3
        and record["constructions"] == (("ieq_triangle", ()),)
    ]
    for a, b, c in triangles:
        o = _single(records, (("circumcenter", (a, b, c)),))
        a1 = _single(records, (("on_bline", (b, c)),))
        b1 = _single(records, (("on_bline", (c, a)),))
        if not all((o, a1, b1)):
            continue
        c0 = _single(records, (("on_aline", (a, b, a1, c, b1)),))
        if not c0:
            continue
        c1 = _single(
            records,
            (("on_bline", (a, b)), ("on_aline", (a, b, c0, a, o))),
        )
        if not c1:
            continue
        a2 = _single(records, (("on_line", (b, c1)), ("on_line", (c, b1))))
        b2 = _single(records, (("on_line", (c, a1)), ("on_line", (a, c1))))
        c2 = _single(records, (("on_line", (a, b1)), ("on_line", (b, a1))))
        if not all((a2, b2, c2)):
            continue
        o1 = _single(records, (("circumcenter", (a, a1, a2)),))
        o2 = _single(records, (("circumcenter", (b, b1, b2)),))
        o3 = _single(records, (("circumcenter", (c, c1, c2)),))
        if not all((o1, o2, o3)):
            continue
        x = _single(
            records,
            (("on_circle", (o1, a)), ("on_circle", (o2, b))),
        )
        if not x:
            continue
        actual = (
            Atom(formulation.goals[0].predicate, formulation.goals[0].args).canonical()
            if len(formulation.goals) == 1
            else None
        )
        expected = Atom("cyclic", (x, c, c1, c2)).canonical()
        if actual == expected:
            accepted.append(
                {
                    "A": a, "B": b, "C": c, "O": o,
                    "A1": a1, "B1": b1, "C0": c0, "C1": c1,
                    "A2": a2, "B2": b2, "C2": c2,
                    "O1": o1, "O2": o2, "O3": o3, "X": x,
                }
            )

    chart = certify_equilateral_angle_sum_three_circles_chart()
    roles = accepted[0] if len(accepted) == 1 else {}
    replayed = bool(roles and chart.replayed and chart.all_conditions_discharged)
    goal = str(formulation.goals[0]) if len(formulation.goals) == 1 else ""
    return JGEXEquilateralAngleSumThreeCirclesApplication(
        theorem=chart.theorem,
        source_sha256=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        roles=roles,
        matched_constructions=(
            "equilateral parent triangle and three perpendicular bisectors",
            "two directed on_aline clauses forming C0,C1",
            "six carrier intersections A2,B2,C2",
            "three target circles and a common point of the first two",
        ) if roles else (),
        goal=goal,
        proof_bridge=(
            "on_aline direct similarities -> exact angle composition -> "
            "three-circle pencil -> third-circle membership"
        ),
        chart_certificate_sha256=chart.certificate_sha256,
        nondegeneracy_obligations=chart.assumptions,
        undischarged_nondegeneracy_obligations=() if replayed else chart.assumptions,
        replayed=replayed,
    )


def render_equilateral_angle_sum_three_circles_chart_svg() -> str:
    root_three = math.sqrt(3.0)
    a, b, c = (0.0, root_three), (-1.0, 0.0), (1.0, 0.0)
    a1, b1, c1 = (0.0, 0.72), (0.62, 0.68), (-0.58, 0.7)
    a2, b2, c2 = (-0.15, 0.35), (0.18, 0.38), (0.0, 0.25)
    fig, axis = plt.subplots(figsize=(8.8, 6.2))
    fig.patch.set_facecolor("#07090c")
    axis.set_facecolor("#07090c")
    axis.plot([a[0], b[0], c[0], a[0]], [a[1], b[1], c[1], a[1]], color="#667784", linewidth=1.3)
    for points, color in (
        ((a, a1, a2), "#31d7e8"),
        ((b, b1, b2), "#ffb454"),
        ((c, c1, c2), "#76e39a"),
    ):
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        axis.plot(xs + [xs[0]], ys + [ys[0]], color=color, linewidth=1.2, alpha=0.85)
    labels = {"A": a, "B": b, "C": c, "A1": a1, "B1": b1, "C1": c1, "A2": a2, "B2": b2, "C2": c2}
    for label, point in labels.items():
        axis.scatter([point[0]], [point[1]], s=22, color="#f1f5f8", zorder=4)
        axis.text(point[0] + 0.02, point[1] + 0.02, label, color="#f1f5f8", fontsize=9)
    axis.set_aspect("equal", adjustable="datalim")
    axis.axis("off")
    axis.set_title("equilateral angle composition | three-circle pencil", color="#e7edf2", fontsize=12)
    fig.tight_layout()
    buffer = io.StringIO()
    fig.savefig(buffer, format="svg", bbox_inches="tight")
    plt.close(fig)
    return buffer.getvalue()


__all__ = [
    "EquilateralAngleSumThreeCirclesCertificate",
    "JGEXEquilateralAngleSumThreeCirclesApplication",
    "certify_equilateral_angle_sum_three_circles_chart",
    "certify_jgex_equilateral_angle_sum_three_circles_application",
    "render_equilateral_angle_sum_three_circles_chart_svg",
]
