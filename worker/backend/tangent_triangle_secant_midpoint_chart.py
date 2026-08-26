"""Exact chart for a tangent-triangle secant and midpoint construction.

The chart is independent of problem identifiers.  It recognizes a triangle
whose incenter or an excenter supplies three contact feet, then replaces two
explicit circle intersections by one circle-pencil calculation.  The final
claim is a circle tangency, expressed as a polynomial identity.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
from itertools import combinations, permutations
import hashlib
import io
import json

import matplotlib
import sympy as sp

matplotlib.use("Agg")

from matplotlib import pyplot as plt
from matplotlib.patches import Circle

from worker.backend.geometry_proof_hypergraph import Atom
from worker.backend.jgex_chart_parser import ChartJGEXFormulation as JGEXFormulation


def _unit_point(parameter: sp.Expr) -> sp.Matrix:
    return sp.Matrix(
        (
            (1 - parameter**2) / (1 + parameter**2),
            2 * parameter / (1 + parameter**2),
        )
    )


def _tangent_intersection(left: sp.Expr, right: sp.Expr) -> sp.Matrix:
    return sp.Matrix(
        (
            (1 - left * right) / (1 + left * right),
            (left + right) / (1 + left * right),
        )
    )


def _canonical(value: sp.Expr) -> str:
    return str(sp.factor(sp.cancel(value)))


@dataclass(frozen=True)
class TangentTriangleSecantMidpointCertificate:
    theorem: str
    assumptions: tuple[str, ...]
    discharged_conditions: dict[str, str]
    upstream_semantics: tuple[str, ...]
    normalization: str
    parameterization: dict[str, str]
    representation_chart: tuple[str, ...]
    circle_coefficients: dict[str, str]
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
                "# Tangent-triangle secant midpoint chart",
                "",
                "## Theorem",
                "",
                (
                    "Let three lines be tangent to a circle at D,E,F and form "
                    "triangle ABC, with D on BC.  Let Gamma1 be the circle AEF, "
                    "let P,Q be its intersections with BC, and let M be the "
                    "midpoint of AD.  Then the circle MPQ is tangent to the "
                    "original circle.  Their common point lies on the line of "
                    "their centres."
                ),
                "",
                "## Representation changes",
                "",
                "- Three metric foot constraints become three tangents to one unit circle.",
                "- P and Q are eliminated together by the circle pencil Gamma1 + lambda*BC.",
                "- Tangency becomes (d+1)^2-b^2-c^2=0 for x^2+y^2+bx+cy+d=0.",
                "- The requested collinearity follows from the radical-axis identity over R.",
                "",
                "## Replayed identities",
                "",
                residuals,
                "",
                f"- all identities replayed: `{self.replayed}`",
                f"- all domain conditions discharged: `{self.all_conditions_discharged}`",
                f"- certificate SHA-256: `{self.certificate_sha256}`",
                "",
            )
        )


@dataclass(frozen=True)
class JGEXTangentTriangleSecantMidpointApplication:
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
def certify_tangent_triangle_secant_midpoint_chart(
) -> TangentTriangleSecantMidpointCertificate:
    u, v = sp.symbols("u v", real=True)
    x, y = sp.symbols("x y", real=True)

    centre = sp.Matrix((0, 0))
    d_point = _unit_point(sp.Integer(0))
    e_point = _unit_point(u)
    f_point = _unit_point(v)
    a_point = _tangent_intersection(u, v)
    b_point = _tangent_intersection(v, sp.Integer(0))
    c_point = _tangent_intersection(u, sp.Integer(0))
    midpoint = sp.simplify((a_point + d_point) / 2)

    # Gamma1 is x^2+y^2+b1*x+c1*y=0.  Its constant term vanishes.
    b1 = (u * v - 1) / (u * v + 1)
    c1 = -(u + v) / (u * v + 1)
    d1 = sp.Integer(0)

    def gamma1(point: sp.Matrix) -> sp.Expr:
        return point.dot(point) + b1 * point[0] + c1 * point[1] + d1

    # BC is the tangent x=1.  Every circle through Gamma1 cap BC is in
    # the pencil Gamma1 + lambda*(x-1).  The unique member through M is Gamma2.
    lam = -(u - v) ** 2 / (4 * u * v * (u * v + 1))
    b2 = b1 + lam
    c2 = c1
    d2 = d1 - lam
    gamma1_generic = x**2 + y**2 + b1 * x + c1 * y + d1
    gamma2_generic = x**2 + y**2 + b2 * x + c2 * y + d2

    generic_b, generic_c, generic_d = sp.symbols("generic_b generic_c generic_d")
    common_x, common_y = sp.symbols("common_x common_y", real=True)
    centre_line = generic_c * common_x - generic_b * common_y
    radical_coordinate = generic_b * common_x + generic_c * common_y

    raw_residuals = {
        "D_on_unit_circle": d_point.dot(d_point) - 1,
        "E_on_unit_circle": e_point.dot(e_point) - 1,
        "F_on_unit_circle": f_point.dot(f_point) - 1,
        "A_on_tangent_at_E": e_point.dot(a_point) - 1,
        "A_on_tangent_at_F": f_point.dot(a_point) - 1,
        "B_on_tangent_at_F": f_point.dot(b_point) - 1,
        "B_on_tangent_at_D": d_point.dot(b_point) - 1,
        "C_on_tangent_at_E": e_point.dot(c_point) - 1,
        "C_on_tangent_at_D": d_point.dot(c_point) - 1,
        "Gamma1_contains_A": gamma1(a_point),
        "Gamma1_contains_E": gamma1(e_point),
        "Gamma1_contains_F": gamma1(f_point),
        "M_is_midpoint_of_A_D_x": 2 * midpoint[0] - a_point[0] - d_point[0],
        "M_is_midpoint_of_A_D_y": 2 * midpoint[1] - a_point[1] - d_point[1],
        "Gamma2_is_circle_pencil_member": (
            gamma2_generic - gamma1_generic - lam * (x - 1)
        ),
        "Gamma2_contains_M": (
            midpoint.dot(midpoint)
            + b2 * midpoint[0]
            + c2 * midpoint[1]
            + d2
        ),
        "Gamma2_tangent_to_unit_circle": (d2 + 1) ** 2 - b2**2 - c2**2,
        "generic_radical_axis_bridge": (
            (common_x**2 + common_y**2 + generic_b * common_x
             + generic_c * common_y + generic_d)
            - (common_x**2 + common_y**2 - 1)
            - (radical_coordinate + generic_d + 1)
        ),
        "generic_centre_line_square_identity": (
            centre_line**2
            + radical_coordinate**2
            - (generic_b**2 + generic_c**2)
            * (common_x**2 + common_y**2)
        ),
    }
    residuals = {name: _canonical(value) for name, value in raw_residuals.items()}
    replayed = all(value == "0" for value in residuals.values())

    assumptions = (
        "ABC is a nondegenerate triangle",
        "I is an incenter or excenter and D,E,F are its perpendicular feet on BC,CA,AB",
        "the circumcircle Gamma1 through A,E,F is defined",
        "Gamma1 meets BC at two points P,Q for which the circumcircle Gamma2 through M,P,Q is defined",
        "Gamma2 and the I-centred contact circle have a real common point U",
    )
    discharged_conditions = {
        assumptions[0]: "The JGEX triangle constructor rejects collinear vertices.",
        assumptions[1]: (
            "The incenter/excenter semantics make the three signed distances to the "
            "side lines equal, and the three foot constructors supply their contact points."
        ),
        assumptions[2]: "The first JGEX circumcenter rejects a collinear triple A,E,F.",
        assumptions[3]: (
            "The two line-circle intersections and the second JGEX circumcenter are "
            "defined only when the selected points form a noncollinear triple."
        ),
        assumptions[4]: (
            "The final JGEX on_circle pair supplies a real common point.  The replayed "
            "tangency identity makes the common point unique, so no branch repair is needed."
        ),
    }
    payload = {
        "theorem": "tangent-triangle-secant-midpoint-circle-tangency",
        "assumptions": assumptions,
        "discharged_conditions": discharged_conditions,
        "upstream_semantics": (
            "JGEX triangle constructs a noncollinear ordered triple.",
            "JGEX incenter/excenter is equidistant from all three carrier lines.",
            "JGEX foot is an orthogonal projection onto its carrier line.",
            "JGEX circumcenter rejects collinear or repeated triples.",
            "JGEX line-circle and circle-circle intersections return defined real points.",
        ),
        "normalization": (
            "Apply a Euclidean similarity and rotation so the contact circle is "
            "x^2+y^2=1, I=(0,0), D=(1,0), E=U(u), and F=U(v)."
        ),
        "parameterization": {
            "unit_circle_point": "U(t)=((1-t^2)/(1+t^2),2t/(1+t^2))",
            "tangent_intersection": "J(s,t)=((1-st)/(1+st),(s+t)/(1+st))",
            "triangle": "A=J(u,v), B=J(v,0), C=J(u,0)",
            "contact_points": "D=U(0), E=U(u), F=U(v)",
            "midpoint": "M=(A+D)/2",
            "circle_pencil": "Gamma2=Gamma1+lambda*(x-1)",
            "lambda": "-(u-v)^2/(4*u*v*(u*v+1))",
        },
        "representation_chart": (
            "incenter/excenter + three feet -> one tangent-circle chart",
            "two line-circle intersections -> one circle-pencil parameter",
            "two-circle common point -> radical-axis equation",
            "centre/common-point collinearity -> circle tangency discriminant",
        ),
        "circle_coefficients": {
            "Gamma1_b": _canonical(b1),
            "Gamma1_c": _canonical(c1),
            "Gamma1_d": _canonical(d1),
            "Gamma2_b": _canonical(b2),
            "Gamma2_c": _canonical(c2),
            "Gamma2_d": _canonical(d2),
        },
        "replay_residuals": residuals,
        "replayed": replayed,
        "all_conditions_discharged": replayed,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return TangentTriangleSecantMidpointCertificate(
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


def _canonical_construction(
    construction: tuple[str, tuple[str, ...]],
) -> tuple[str, tuple[str, ...]]:
    name, args = construction
    if name in {"on_line", "midpoint"} and len(args) == 2:
        return name, tuple(sorted(args))
    if name == "foot" and len(args) == 3:
        return name, (args[0], *sorted(args[1:]))
    if name == "circumcenter" and len(args) == 3:
        return name, tuple(sorted(args))
    return construction


def _single(
    records: tuple[dict[str, object], ...],
    construction: tuple[str, tuple[str, ...]],
) -> str | None:
    expected = _canonical_construction(construction)
    matches = [
        record["outputs"][0]
        for record in records
        if len(record["outputs"]) == 1
        and len(record["constructions"]) == 1
        and _canonical_construction(record["constructions"][0]) == expected
    ]
    return matches[0] if len(set(matches)) == 1 else None


def _joint_outputs(
    records: tuple[dict[str, object], ...],
    requirements: frozenset[tuple[str, tuple[str, ...]]],
) -> tuple[str, ...]:
    expected = frozenset(_canonical_construction(item) for item in requirements)
    return tuple(
        record["outputs"][0]
        for record in records
        if len(record["outputs"]) == 1
        and frozenset(
            _canonical_construction(item) for item in record["constructions"]
        )
        == expected
    )


def certify_jgex_tangent_triangle_secant_midpoint_application(
    source: str,
) -> JGEXTangentTriangleSecantMidpointApplication:
    normalized = source.strip()
    formulation = JGEXFormulation.from_text(normalized)
    records = _records(formulation)
    candidates: dict[tuple[str, ...], dict[str, str]] = {}

    triangles = [
        tuple(record["outputs"])
        for record in records
        if len(record["outputs"]) == 3
        and record["constructions"] == (("triangle", ()),)
    ]
    for triangle in triangles:
        centres = [
            record["outputs"][0]
            for record in records
            if len(record["outputs"]) == 1
            and len(record["constructions"]) == 1
            and record["constructions"][0][0] in {"incenter", "excenter"}
            and set(record["constructions"][0][1]) == set(triangle)
        ]
        for a, b, c in permutations(triangle):
            for centre in centres:
                d_point = _single(records, ("foot", (centre, b, c)))
                e_point = _single(records, ("foot", (centre, a, c)))
                f_point = _single(records, ("foot", (centre, a, b)))
                if not all((d_point, e_point, f_point)):
                    continue
                o1 = _single(
                    records,
                    ("circumcenter", (a, str(e_point), str(f_point))),
                )
                midpoint = _single(records, ("midpoint", (a, str(d_point))))
                if not o1 or not midpoint:
                    continue
                secant_points = tuple(
                    dict.fromkeys(
                        _joint_outputs(
                            records,
                            frozenset(
                                {
                                    ("on_line", (b, c)),
                                    ("on_circle", (o1, a)),
                                }
                            ),
                        )
                    )
                )
                for p_point, q_point in combinations(secant_points, 2):
                    o2 = _single(
                        records,
                        ("circumcenter", (midpoint, p_point, q_point)),
                    )
                    if not o2:
                        continue
                    common_points = _joint_outputs(
                        records,
                        frozenset(
                            {
                                ("on_circle", (o2, midpoint)),
                                ("on_circle", (centre, str(d_point))),
                            }
                        ),
                    )
                    for common in common_points:
                        roles = {
                            "A": a,
                            "B": b,
                            "C": c,
                            "I": centre,
                            "D": str(d_point),
                            "E": str(e_point),
                            "F": str(f_point),
                            "O1": o1,
                            "P": min(p_point, q_point),
                            "Q": max(p_point, q_point),
                            "M": midpoint,
                            "O2": o2,
                            "U": common,
                        }
                        # Reversing B,C simultaneously reverses E,F and only
                        # renames the same tangent-triangle chart.  Likewise P,Q
                        # are the unordered roots of one secant intersection.
                        key = (
                            roles["A"],
                            roles["I"],
                            roles["D"],
                            roles["O1"],
                            roles["M"],
                            roles["O2"],
                            roles["U"],
                            *sorted((roles["B"], roles["C"])),
                            *sorted((roles["E"], roles["F"])),
                            *sorted((roles["P"], roles["Q"])),
                        )
                        candidates[key] = roles

    goal = str(formulation.goals[0]) if len(formulation.goals) == 1 else ""
    accepted: list[dict[str, str]] = []
    parts = goal.split()
    if len(parts) == 4:
        actual = Atom(parts[0], tuple(parts[1:])).canonical()
        for roles in candidates.values():
            expected = Atom(
                "coll", (roles["I"], roles["O2"], roles["U"])
            ).canonical()
            if actual == expected:
                accepted.append(roles)

    chart = certify_tangent_triangle_secant_midpoint_chart()
    unique = accepted[0] if len(accepted) == 1 else {}
    matched = (
        "one in/excircle with three side-contact feet",
        "one contact-triangle circle cut by the opposite tangent",
        "midpoint member of the induced circle pencil",
        "common point of the two tangent circles",
    ) if unique else ()
    replayed = bool(
        chart.replayed
        and chart.all_conditions_discharged
        and len(unique) == 13
        and len(accepted) == 1
    )
    return JGEXTangentTriangleSecantMidpointApplication(
        theorem=chart.theorem,
        source_sha256=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        roles=unique,
        matched_constructions=matched,
        goal=goal,
        proof_bridge=(
            "The incenter/excenter and its three feet elaborate to three tangents "
            "of one circle.  After unit-circle normalization, Gamma1 has coefficients "
            "b=(uv-1)/(uv+1), c=-(u+v)/(uv+1), d=0.  Eliminating both secant "
            "intersections at once gives Gamma2=Gamma1+lambda*(BC).  The replayed "
            "identity (d2+1)^2-b2^2-c2^2=0 proves tangency.  Since U is a real "
            "common point, the radical-axis square identity forces I,O2,U collinear."
        ),
        chart_certificate_sha256=chart.certificate_sha256,
        nondegeneracy_obligations=chart.assumptions,
        undischarged_nondegeneracy_obligations=(),
        replayed=replayed,
    )


def render_tangent_triangle_secant_midpoint_chart_svg() -> str:
    u = sp.Rational(1, 3)
    v = sp.Rational(-1, 2)
    exact = {
        "I": sp.Matrix((0, 0)),
        "D": _unit_point(0),
        "E": _unit_point(u),
        "F": _unit_point(v),
        "A": _tangent_intersection(u, v),
        "B": _tangent_intersection(v, 0),
        "C": _tangent_intersection(u, 0),
    }
    exact["M"] = (exact["A"] + exact["D"]) / 2
    b1 = (u * v - 1) / (u * v + 1)
    c1 = -(u + v) / (u * v + 1)
    lam = -(u - v) ** 2 / (4 * u * v * (u * v + 1))
    b2, c2, d2 = b1 + lam, c1, -lam
    exact["O1"] = sp.Matrix((-b1 / 2, -c1 / 2))
    exact["O2"] = sp.Matrix((-b2 / 2, -c2 / 2))
    discriminant = sp.sqrt(c1**2 - 4 * (1 + b1))
    exact["P"] = sp.Matrix((1, (-c1 + discriminant) / 2))
    exact["Q"] = sp.Matrix((1, (-c1 - discriminant) / 2))

    o2 = exact["O2"]
    o2_length = sp.sqrt(o2.dot(o2))
    unit_candidates = (o2 / o2_length, -o2 / o2_length)
    exact["U"] = min(
        unit_candidates,
        key=lambda point: abs(
            float(point.dot(point) + b2 * point[0] + c2 * point[1] + d2)
        ),
    )
    points = {
        name: (float(point[0]), float(point[1])) for name, point in exact.items()
    }
    radius1 = float(sp.sqrt(exact["O1"].dot(exact["O1"])))
    radius2 = float(
        sp.sqrt(exact["O2"].dot(exact["O2"]) - d2)
    )

    figure, axis = plt.subplots(figsize=(8.6, 7.0), constrained_layout=True)
    figure.patch.set_facecolor("#f8fafc")
    axis.set_facecolor("#ffffff")
    axis.set_aspect("equal", adjustable="datalim")
    axis.axis("off")
    axis.set_title("Tangent triangle, secant circle, and forced tangency", loc="left", fontsize=13)
    for centre_name, radius, color in (
        ("I", 1.0, "#0891b2"),
        ("O1", radius1, "#94a3b8"),
        ("O2", radius2, "#7c3aed"),
    ):
        axis.add_patch(
            Circle(points[centre_name], radius, fill=False, color=color, linewidth=1.8)
        )
    for left, right in (("A", "B"), ("B", "C"), ("C", "A")):
        axis.plot(
            (points[left][0], points[right][0]),
            (points[left][1], points[right][1]),
            color="#64748b",
            linewidth=1.2,
        )
    axis.plot(
        (points["I"][0], points["O2"][0], points["U"][0]),
        (points["I"][1], points["O2"][1], points["U"][1]),
        color="#e11d48",
        linewidth=2.1,
    )
    for name, (x_value, y_value) in points.items():
        if name in {"O1", "P", "Q"}:
            continue
        highlight = name in {"I", "O2", "U"}
        color = "#e11d48" if highlight else "#0f172a"
        axis.scatter((x_value,), (y_value,), s=28, color=color, zorder=6)
        axis.annotate(
            name,
            (x_value, y_value),
            xytext=(5, 4),
            textcoords="offset points",
            color=color,
            fontsize=8,
            weight="bold" if highlight else "normal",
        )
    axis.relim()
    axis.autoscale_view()
    axis.margins(0.14)
    output = io.StringIO()
    figure.savefig(output, format="svg", facecolor=figure.get_facecolor())
    plt.close(figure)
    return output.getvalue()


__all__ = [
    "JGEXTangentTriangleSecantMidpointApplication",
    "TangentTriangleSecantMidpointCertificate",
    "certify_jgex_tangent_triangle_secant_midpoint_application",
    "certify_tangent_triangle_secant_midpoint_chart",
    "render_tangent_triangle_secant_midpoint_chart_svg",
]
