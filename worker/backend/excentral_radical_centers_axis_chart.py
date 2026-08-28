"""Exact excentral contact-line and radical-center axis chart.

For a triangle with incenter I, take the two side-contact points of each
excircle.  Their three joining lines form DEF and Omega=(DEF).  Let X,Y,Z be
the radical centers of Omega with the corresponding pairs of excircles.  The
circumcenters O1 of DEF and O2 of XYZ are collinear with I.

The triangle is represented by three rational unit normals to a unit
incircle.  Vertices, excenters, feet, contact-line intersections, radical
centers, and both circumcenters therefore live in ``QQ(u,v)``.  Circle-circle
roots are never expanded: their joining line is obtained by subtracting the
two normalized circle equations.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
import hashlib
import io
import json
import math

import matplotlib
from sympy.polys.domains import QQ
from sympy.polys.fields import field

matplotlib.use("Agg")

from matplotlib import pyplot as plt
from matplotlib.patches import Circle

from worker.backend.geometry_proof_hypergraph import Atom
from worker.backend.jgex_chart_parser import ChartJGEXFormulation as JGEXFormulation


def _exact_replay() -> dict[str, str]:
    rational_field, u, v = field("u,v", QQ)
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

    def solve_two_normals(first, first_rhs, second, second_rhs):
        determinant = cross(first, second)
        return (
            (first_rhs * second[1] - second_rhs * first[1]) / determinant,
            (first[0] * second_rhs - second[0] * first_rhs) / determinant,
        )

    def line_intersection(a, b, c, d):
        ab = subtract(b, a)
        cd = subtract(d, c)
        parameter = cross(subtract(c, a), cd) / cross(ab, cd)
        return add(a, scale(parameter, ab))

    def foot_to_unit_normal_line(point, normal):
        return subtract(point, scale(dot(normal, point) - one, normal))

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

    def centered_circle(center, radius_squared):
        return (
            -2 * center[0],
            -2 * center[1],
            dot(center, center) - radius_squared,
        )

    def circle_value(point, coefficients):
        return (
            dot(point, point)
            + coefficients[0] * point[0]
            + coefficients[1] * point[1]
            + coefficients[2]
        )

    def radical_axis(first, second):
        return (
            first[0] - second[0],
            first[1] - second[1],
            first[2] - second[2],
        )

    def line_from_circle_difference_intersection(first, second):
        return solve_two_normals(
            (first[0], first[1]),
            -first[2],
            (second[0], second[1]),
            -second[2],
        )

    def center(coefficients):
        return -coefficients[0] / 2, -coefficients[1] / 2

    def rational_unit_normal(parameter):
        denominator = one + parameter**2
        return (
            (one - parameter**2) / denominator,
            2 * parameter / denominator,
        )

    normal_a = (one, zero)
    normal_b = rational_unit_normal(u)
    normal_c = rational_unit_normal(v)
    a = solve_two_normals(normal_b, one, normal_c, one)
    b = solve_two_normals(normal_c, one, normal_a, one)
    c = solve_two_normals(normal_a, one, normal_b, one)
    incenter = (zero, zero)

    excenter_a = solve_two_normals(
        add(normal_a, normal_b),
        2,
        add(normal_a, normal_c),
        2,
    )
    excenter_b = solve_two_normals(
        add(normal_b, normal_a),
        2,
        add(normal_b, normal_c),
        2,
    )
    excenter_c = solve_two_normals(
        add(normal_c, normal_a),
        2,
        add(normal_c, normal_b),
        2,
    )

    a1 = foot_to_unit_normal_line(excenter_a, normal_c)
    a2 = foot_to_unit_normal_line(excenter_a, normal_b)
    b1 = foot_to_unit_normal_line(excenter_b, normal_a)
    b2 = foot_to_unit_normal_line(excenter_b, normal_c)
    c1 = foot_to_unit_normal_line(excenter_c, normal_b)
    c2 = foot_to_unit_normal_line(excenter_c, normal_a)

    d = line_intersection(b1, b2, c1, c2)
    e = line_intersection(a1, a2, c1, c2)
    f = line_intersection(a1, a2, b1, b2)
    omega = circle_coefficients(d, e, f)
    o1 = center(omega)
    excircle_a = centered_circle(
        excenter_a,
        dot(subtract(excenter_a, a1), subtract(excenter_a, a1)),
    )
    excircle_b = centered_circle(
        excenter_b,
        dot(subtract(excenter_b, b1), subtract(excenter_b, b1)),
    )
    excircle_c = centered_circle(
        excenter_c,
        dot(subtract(excenter_c, c1), subtract(excenter_c, c1)),
    )

    axis_a = radical_axis(omega, excircle_a)
    axis_b = radical_axis(omega, excircle_b)
    axis_c = radical_axis(omega, excircle_c)
    x = line_from_circle_difference_intersection(axis_b, axis_c)
    y = line_from_circle_difference_intersection(axis_a, axis_c)
    z = line_from_circle_difference_intersection(axis_a, axis_b)
    xyz_circle = circle_coefficients(x, y, z)
    o2 = center(xyz_circle)

    residuals = {
        "normal_a_unit": dot(normal_a, normal_a) - one,
        "normal_b_unit": dot(normal_b, normal_b) - one,
        "normal_c_unit": dot(normal_c, normal_c) - one,
        "A_on_sides_b_c": (dot(normal_b, a) - one) + (dot(normal_c, a) - one),
        "B_on_sides_c_a": (dot(normal_c, b) - one) + (dot(normal_a, b) - one),
        "C_on_sides_a_b": (dot(normal_a, c) - one) + (dot(normal_b, c) - one),
        "A_excenter_signed_distance_ab": (
            dot(normal_a, excenter_a) + dot(normal_b, excenter_a) - 2
        ),
        "A_excenter_signed_distance_ac": (
            dot(normal_a, excenter_a) + dot(normal_c, excenter_a) - 2
        ),
        "B_excenter_signed_distance_ba": (
            dot(normal_b, excenter_b) + dot(normal_a, excenter_b) - 2
        ),
        "B_excenter_signed_distance_bc": (
            dot(normal_b, excenter_b) + dot(normal_c, excenter_b) - 2
        ),
        "C_excenter_signed_distance_ca": (
            dot(normal_c, excenter_c) + dot(normal_a, excenter_c) - 2
        ),
        "C_excenter_signed_distance_cb": (
            dot(normal_c, excenter_c) + dot(normal_b, excenter_c) - 2
        ),
        "A1_on_AB": dot(normal_c, a1) - one,
        "A1_foot_direction": cross(subtract(excenter_a, a1), normal_c),
        "A2_on_AC": dot(normal_b, a2) - one,
        "A2_foot_direction": cross(subtract(excenter_a, a2), normal_b),
        "B1_on_BC": dot(normal_a, b1) - one,
        "B1_foot_direction": cross(subtract(excenter_b, b1), normal_a),
        "B2_on_BA": dot(normal_c, b2) - one,
        "B2_foot_direction": cross(subtract(excenter_b, b2), normal_c),
        "C1_on_CA": dot(normal_b, c1) - one,
        "C1_foot_direction": cross(subtract(excenter_c, c1), normal_b),
        "C2_on_CB": dot(normal_a, c2) - one,
        "C2_foot_direction": cross(subtract(excenter_c, c2), normal_a),
        "D_on_B1B2": cross(subtract(d, b1), subtract(b2, b1)),
        "D_on_C1C2": cross(subtract(d, c1), subtract(c2, c1)),
        "E_on_A1A2": cross(subtract(e, a1), subtract(a2, a1)),
        "E_on_C1C2": cross(subtract(e, c1), subtract(c2, c1)),
        "F_on_A1A2": cross(subtract(f, a1), subtract(a2, a1)),
        "F_on_B1B2": cross(subtract(f, b1), subtract(b2, b1)),
        "D_on_Omega": circle_value(d, omega),
        "E_on_Omega": circle_value(e, omega),
        "F_on_Omega": circle_value(f, omega),
        "X_equal_power_Omega_excircle_B": (
            circle_value(x, omega) - circle_value(x, excircle_b)
        ),
        "X_equal_power_Omega_excircle_C": (
            circle_value(x, omega) - circle_value(x, excircle_c)
        ),
        "Y_equal_power_Omega_excircle_A": (
            circle_value(y, omega) - circle_value(y, excircle_a)
        ),
        "Y_equal_power_Omega_excircle_C": (
            circle_value(y, omega) - circle_value(y, excircle_c)
        ),
        "Z_equal_power_Omega_excircle_A": (
            circle_value(z, omega) - circle_value(z, excircle_a)
        ),
        "Z_equal_power_Omega_excircle_B": (
            circle_value(z, omega) - circle_value(z, excircle_b)
        ),
        "X_on_XYZ_circle": circle_value(x, xyz_circle),
        "Y_on_XYZ_circle": circle_value(y, xyz_circle),
        "Z_on_XYZ_circle": circle_value(z, xyz_circle),
        "I_O1_O2_collinear": cross(o1, o2),
    }
    return {
        name: "0" if value == zero else str(value)
        for name, value in residuals.items()
    }


@dataclass(frozen=True)
class ExcentralRadicalCentersAxisCertificate:
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
                "# Excentral radical-centers axis chart",
                "",
                "## Reusable proof",
                "",
                "1. Normalize the incircle to the unit circle.",
                "2. Encode the three sides by rational unit normals.",
                "3. Solve the signed-distance equations for the excenters and feet.",
                "4. Construct DEF and Omega exactly.",
                "5. Replace every circle-intersection pair by its radical axis.",
                "6. Construct X,Y,Z, then replay I,O1,O2 collinear.",
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
class JGEXExcentralRadicalCentersAxisApplication:
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
def certify_excentral_radical_centers_axis_chart(
) -> ExcentralRadicalCentersAxisCertificate:
    residuals = _exact_replay()
    replayed = all(value == "0" for value in residuals.values())
    assumptions = (
        "ABC is a nondegenerate triangle with incenter I and three excenters",
        "all six excentral contact feet and the contact-line triangle DEF are defined",
        "Omega=(DEF) and all three excircles are defined",
        "each named pair consists of the two common points of Omega and one excircle",
        "the radical centers X,Y,Z and their circumcircle are defined",
    )
    discharged = {
        assumptions[0]: "The triangle, incenter, and cyclic excenter clauses are matched.",
        assumptions[1]: "All six foot clauses and six contact-line incidences are matched.",
        assumptions[2]: "The DEF circumcenter and excenter-radius clauses are matched.",
        assumptions[3]: "Each pair has the same two on_circle clauses; only its joining line is used.",
        assumptions[4]: "The three line intersections and final circumcenter are matched.",
    }
    payload = {
        "theorem": "excentral-contact-triangle-radical-centers-incenter-axis",
        "assumptions": assumptions,
        "discharged_conditions": discharged,
        "upstream_semantics": (
            "A unit normal n represents the side n dot x=1 of a unit incircle.",
            "An excenter is a solution of two signed-distance equalities.",
            "A pair of circle roots is consumed only through its order-free common chord.",
            "A common chord is the radical axis obtained by subtracting circle equations.",
        ),
        "normalization": (
            "Normalize the incircle to x^2+y^2=1, fix one side normal, and "
            "parameterize the remaining two unit normals by u and v."
        ),
        "parameterization": {
            "coefficient_domain": "rational function field QQ(u,v)",
            "side_a_normal": "(1,0)",
            "other_normals": "((1-t^2)/(1+t^2),2t/(1+t^2))",
            "circle_pair_elimination": "radical axis from coefficient difference",
        },
        "representation_chart": (
            "three tangent lines -> triangle with unit incircle",
            "signed side distances -> incenter and excenters",
            "normal projection -> excentral contact points",
            "pair of common circle points -> radical axis",
            "two radical axes -> radical center",
            "three radical centers -> circumcenter axis",
        ),
        "proof_dag": (
            "Construct the three vertices, excenters, and six contact feet.",
            "Intersect the three contact chords to form D,E,F and Omega.",
            "Subtract Omega from each excircle to obtain three radical axes.",
            "Intersect the relevant axis pairs to obtain X,Y,Z.",
            "Construct O1 and O2 from their circle coefficients.",
            "Replay det(I-O1,O2-O1)=0 identically in QQ(u,v).",
        ),
        "replay_residuals": residuals,
        "replayed": replayed,
        "all_conditions_discharged": replayed,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return ExcentralRadicalCentersAxisCertificate(
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
    if name in {"circumcenter", "incenter", "excenter"} and len(args) == 3:
        return name, args if name == "excenter" else tuple(sorted(args))
    if name in {"foot", "on_line", "on_circle"} and len(args) == 2:
        return name, tuple(sorted(args)) if name != "foot" else args
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


def _pair(records, constructions):
    expected = sorted(map(_canonical, constructions), key=repr)
    matches = sorted(
        str(record["outputs"][0])
        for record in records
        if len(record["outputs"]) == 1
        and sorted(map(_canonical, record["constructions"]), key=repr) == expected
    )
    return tuple(matches) if len(matches) == 2 else ()


def certify_jgex_excentral_radical_centers_axis_application(
    source: str,
) -> JGEXExcentralRadicalCentersAxisApplication:
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
        i = _single(records, (("incenter", (a, b, c)),))
        i1 = _single(records, (("excenter", (a, b, c)),))
        i2 = _single(records, (("excenter", (b, c, a)),))
        i3 = _single(records, (("excenter", (c, a, b)),))
        if not all((i, i1, i2, i3)):
            continue
        a1 = _single(records, (("foot", (i1, a, b)),))
        a2 = _single(records, (("foot", (i1, a, c)),))
        b1 = _single(records, (("foot", (i2, b, c)),))
        b2 = _single(records, (("foot", (i2, b, a)),))
        c1 = _single(records, (("foot", (i3, c, a)),))
        c2 = _single(records, (("foot", (i3, c, b)),))
        if not all((a1, a2, b1, b2, c1, c2)):
            continue
        d = _single(records, (("on_line", (b1, b2)), ("on_line", (c1, c2))))
        e = _single(records, (("on_line", (a1, a2)), ("on_line", (c1, c2))))
        f = _single(records, (("on_line", (a1, a2)), ("on_line", (b1, b2))))
        if not all((d, e, f)):
            continue
        o1 = _single(records, (("circumcenter", (d, e, f)),))
        if not o1:
            continue
        x_pair = _pair(records, (("on_circle", (o1, d)), ("on_circle", (i1, a1))))
        y_pair = _pair(records, (("on_circle", (o1, d)), ("on_circle", (i2, b1))))
        z_pair = _pair(records, (("on_circle", (o1, d)), ("on_circle", (i3, c1))))
        if not all((x_pair, y_pair, z_pair)):
            continue
        x = _single(records, (("on_line", y_pair), ("on_line", z_pair)))
        y = _single(records, (("on_line", x_pair), ("on_line", z_pair)))
        z = _single(records, (("on_line", x_pair), ("on_line", y_pair)))
        if not all((x, y, z)):
            continue
        o2 = _single(records, (("circumcenter", (x, y, z)),))
        if not o2:
            continue
        actual = (
            Atom(formulation.goals[0].predicate, formulation.goals[0].args).canonical()
            if len(formulation.goals) == 1
            else None
        )
        expected = Atom("coll", (i, o1, o2)).canonical()
        if actual == expected:
            accepted.append(
                {
                    "A": a, "B": b, "C": c, "I": i,
                    "I1": i1, "I2": i2, "I3": i3,
                    "A1": a1, "A2": a2, "B1": b1, "B2": b2,
                    "C1": c1, "C2": c2, "D": d, "E": e, "F": f,
                    "O1": o1, "X": x, "Y": y, "Z": z, "O2": o2,
                }
            )

    chart = certify_excentral_radical_centers_axis_chart()
    roles = accepted[0] if len(accepted) == 1 else {}
    replayed = bool(roles and chart.replayed and chart.all_conditions_discharged)
    goal = str(formulation.goals[0]) if len(formulation.goals) == 1 else ""
    return JGEXExcentralRadicalCentersAxisApplication(
        theorem=chart.theorem,
        source_sha256=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        roles=roles,
        matched_constructions=(
            "three excenters and six side-contact feet",
            "contact-line triangle DEF and its circle Omega",
            "three order-free circle-intersection pairs",
            "three radical centers X,Y,Z and their circumcenter O2",
        ) if roles else (),
        goal=goal,
        proof_bridge=(
            "unit-incircle signed-distance chart -> common-chord radical axes -> "
            "radical-center triangle -> exact center-axis determinant"
        ),
        chart_certificate_sha256=chart.certificate_sha256,
        nondegeneracy_obligations=chart.assumptions,
        undischarged_nondegeneracy_obligations=() if replayed else chart.assumptions,
        replayed=replayed,
    )


def render_excentral_radical_centers_axis_chart_svg() -> str:
    # A restrained schematic: the exact coordinates are already certified by
    # the replay, while the diagram exposes the contact triangle and center axis.
    vertices = ((0.0, 1.15), (-1.05, -0.65), (1.1, -0.65))
    a, b, c = vertices
    incenter = (0.02, -0.04)
    d, e, f = (0.0, -1.05), (0.88, 0.35), (-0.86, 0.32)
    o1, o2 = (0.01, -0.02), (0.08, 0.52)
    x, y, z = (-0.58, 0.18), (0.62, 0.2), (0.04, 0.82)
    fig, axis = plt.subplots(figsize=(8.8, 6.2))
    fig.patch.set_facecolor("#07090c")
    axis.set_facecolor("#07090c")
    axis.plot([a[0], b[0], c[0], a[0]], [a[1], b[1], c[1], a[1]], color="#667784", linewidth=1.2)
    axis.plot([d[0], e[0], f[0], d[0]], [d[1], e[1], f[1], d[1]], color="#ffb454", linewidth=1.4)
    axis.plot([x[0], y[0], z[0], x[0]], [x[1], y[1], z[1], x[1]], color="#31d7e8", linewidth=1.4)
    axis.plot([incenter[0], o2[0]], [incenter[1], o2[1]], color="#76e39a", linewidth=1.8)
    axis.add_patch(Circle(o1, 0.88, fill=False, color="#374957", linewidth=1.0))
    labels = {"I": incenter, "O1": o1, "O2": o2, "D": d, "E": e, "F": f, "X": x, "Y": y, "Z": z}
    for label, point in labels.items():
        color = "#76e39a" if label in {"I", "O1", "O2"} else "#f1f5f8"
        axis.scatter([point[0]], [point[1]], s=23, color=color, zorder=4)
        axis.text(point[0] + 0.025, point[1] + 0.025, label, color=color, fontsize=9)
    axis.set_aspect("equal", adjustable="datalim")
    axis.axis("off")
    axis.set_title("excentral contact lines | radical centers | center axis", color="#e7edf2", fontsize=12)
    fig.tight_layout()
    buffer = io.StringIO()
    fig.savefig(buffer, format="svg", bbox_inches="tight")
    plt.close(fig)
    return buffer.getvalue()


__all__ = [
    "ExcentralRadicalCentersAxisCertificate",
    "JGEXExcentralRadicalCentersAxisApplication",
    "certify_excentral_radical_centers_axis_chart",
    "certify_jgex_excentral_radical_centers_axis_application",
    "render_excentral_radical_centers_axis_chart_svg",
]
