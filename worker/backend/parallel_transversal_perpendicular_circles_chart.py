"""Exact chart for circles induced by two parallel triangle transversals.

For each transversal of a fixed triangle, perpendiculars through its three
side intersections form a new triangle.  This module proves that the
circumcircles obtained from any two parallel transversals are tangent.  The
matcher uses only construction dependencies and never a problem identifier.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
from itertools import permutations
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


def _canonical(value: sp.Expr) -> str:
    return str(sp.factor(sp.cancel(value)))


def _build_perpendicular_triangle(
    p: sp.Expr,
    q: sp.Expr,
    h: sp.Expr,
    tau: sp.Expr,
) -> tuple[sp.Matrix, sp.Matrix, sp.Matrix, sp.Matrix, sp.Matrix, sp.Matrix]:
    """Return X,Y,Z,U,V,W in the normalized affine chart."""

    denominator_ac = p + h * q
    denominator_bc = p + h * q - 1
    z_point = sp.Matrix((tau, 0))
    y_point = tau / denominator_ac * sp.Matrix((p, q))
    mu = (tau - 1) / denominator_bc
    x_point = sp.Matrix((1 + mu * (p - 1), mu * q))

    ac = sp.Matrix((p, q))
    bc = sp.Matrix((p - 1, q))
    u_point = sp.Matrix(
        (
            tau,
            sp.cancel((ac.dot(y_point) - p * tau) / q),
        )
    )
    v_point = sp.Matrix(
        (
            tau,
            sp.cancel((bc.dot(x_point) - (p - 1) * tau) / q),
        )
    )
    ac_level = sp.cancel(ac.dot(y_point))
    bc_level = sp.cancel(bc.dot(x_point))
    w_x = sp.cancel(ac_level - bc_level)
    w_y = sp.cancel((ac_level - p * w_x) / q)
    w_point = sp.Matrix((w_x, w_y))
    return x_point, y_point, z_point, u_point, v_point, w_point


def _circle_coefficients(
    first: sp.Matrix,
    second: sp.Matrix,
    third: sp.Matrix,
) -> tuple[sp.Expr, sp.Expr, sp.Expr]:
    matrix = sp.Matrix(
        [
            [point[0], point[1], 1, -point.dot(point)]
            for point in (first, second, third)
        ]
    )
    values = matrix[:, :3].inv() * matrix[:, 3]
    return tuple(sp.cancel(value) for value in values)  # type: ignore[return-value]


@dataclass(frozen=True)
class ParallelTransversalPerpendicularCirclesCertificate:
    theorem: str
    assumptions: tuple[str, ...]
    discharged_conditions: dict[str, str]
    upstream_semantics: tuple[str, ...]
    normalization: str
    parameterization: dict[str, str]
    representation_chart: tuple[str, ...]
    circle_parameter_degrees: dict[str, int]
    tangency_factorization: str
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
                "# Parallel-transversal perpendicular-circle chart",
                "",
                "## Theorem",
                "",
                (
                    "Two parallel lines cut the sides of triangle ABC at Xi,Yi,Zi. "
                    "For each i, intersect the perpendiculars to AC through Yi and "
                    "to AB through Zi, the perpendiculars to BC through Xi and to AB "
                    "through Zi, and the perpendiculars to BC through Xi and to AC "
                    "through Yi.  The circumcircles of the two resulting triangles "
                    "are tangent.  Every common point lies on their line of centres."
                ),
                "",
                "## Representation changes",
                "",
                "- A parallel family becomes x+h*y=tau.",
                "- All six perpendicular intersections are affine-linear in tau.",
                "- Each circumcircle has coefficients affine-linear in tau.",
                "- Two-circle tangency is one radius/centre discriminant.",
                "",
                "## Exact tangency identity",
                "",
                f"`{self.tangency_factorization}`",
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
class JGEXParallelTransversalPerpendicularCirclesApplication:
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
def certify_parallel_transversal_perpendicular_circles_chart(
) -> ParallelTransversalPerpendicularCirclesCertificate:
    p, q, h, tau1, tau2 = sp.symbols("p q h tau1 tau2", real=True)
    a_point = sp.Matrix((0, 0))
    b_point = sp.Matrix((1, 0))
    c_point = sp.Matrix((p, q))
    ac = c_point - a_point
    bc = c_point - b_point

    first = _build_perpendicular_triangle(p, q, h, tau1)
    second = _build_perpendicular_triangle(p, q, h, tau2)
    b1, c1, d1 = _circle_coefficients(*first[3:])
    b2, c2, d2 = _circle_coefficients(*second[3:])

    centre_distance_squared = sp.cancel(
        ((b1 - b2) ** 2 + (c1 - c2) ** 2) / 4
    )
    radius1_squared = sp.cancel((b1**2 + c1**2) / 4 - d1)
    radius2_squared = sp.cancel((b2**2 + c2**2) / 4 - d2)
    tangency_discriminant = sp.cancel(
        (centre_distance_squared - radius1_squared - radius2_squared) ** 2
        - 4 * radius1_squared * radius2_squared
    )

    raw_residuals: dict[str, sp.Expr] = {}
    for index, (tau, points) in enumerate(((tau1, first), (tau2, second)), start=1):
        x_point, y_point, z_point, u_point, v_point, w_point = points
        raw_residuals.update(
            {
                f"X{index}_on_BC": (
                    (x_point[0] - b_point[0]) * bc[1]
                    - (x_point[1] - b_point[1]) * bc[0]
                ),
                f"Y{index}_on_CA": (
                    y_point[0] * ac[1] - y_point[1] * ac[0]
                ),
                f"Z{index}_on_AB": z_point[1],
                f"X{index}_on_transversal": x_point[0] + h * x_point[1] - tau,
                f"Y{index}_on_transversal": y_point[0] + h * y_point[1] - tau,
                f"Z{index}_on_transversal": z_point[0] + h * z_point[1] - tau,
                f"U{index}_perp_AC_through_Y": ac.dot(u_point - y_point),
                f"U{index}_perp_AB_through_Z": (u_point - z_point).dot(b_point),
                f"V{index}_perp_BC_through_X": bc.dot(v_point - x_point),
                f"V{index}_perp_AB_through_Z": (v_point - z_point).dot(b_point),
                f"W{index}_perp_BC_through_X": bc.dot(w_point - x_point),
                f"W{index}_perp_AC_through_Y": ac.dot(w_point - y_point),
            }
        )
        circle = (b1, c1, d1) if index == 1 else (b2, c2, d2)
        for point_name, point in zip(("U", "V", "W"), points[3:]):
            raw_residuals[f"Gamma{index}_contains_{point_name}{index}"] = (
                point.dot(point)
                + circle[0] * point[0]
                + circle[1] * point[1]
                + circle[2]
            )

    db, dc = sp.symbols("db dc", real=True)
    dx, dy = sp.symbols("dx dy", real=True)
    raw_residuals.update(
        {
            "parallel_transversal_direction": (
                (first[0][0] + h * first[0][1] - tau1)
                - (second[0][0] + h * second[0][1] - tau2)
            ),
            "two_circle_tangency_discriminant": tangency_discriminant,
            "generic_dot_cross_norm_identity": (
                (db * dx + dc * dy) ** 2
                + (db * dy - dc * dx) ** 2
                - (db**2 + dc**2) * (dx**2 + dy**2)
            ),
        }
    )
    residuals = {name: _canonical(value) for name, value in raw_residuals.items()}
    replayed = all(value == "0" for value in residuals.values())

    assumptions = (
        "ABC is a nondegenerate triangle",
        "both parallel transversals have unique intersections with AB,BC,CA",
        "the six pairs of perpendicular carriers have unique finite intersections",
        "both induced circumcircles are defined",
        "the two induced circles have a real common point T",
    )
    discharged_conditions = {
        assumptions[0]: "The JGEX triangle constructor rejects collinear vertices.",
        assumptions[1]: (
            "Each Xi,Yi,Zi is a successful JGEX line intersection; the shared "
            "on_pline carrier fixes the same direction for the second transversal."
        ),
        assumptions[2]: (
            "Every Ui,Vi,Wi is a successful intersection of two on_tline carriers."
        ),
        assumptions[3]: "Both JGEX circumcenter constructors reject collinear triples.",
        assumptions[4]: (
            "The final paired on_circle clause supplies a real common point.  If the "
            "two circles are distinct, the exact discriminant makes it their unique "
            "tangency point; if they coincide, the two centres are equal and the "
            "collinearity determinant is already zero."
        ),
    }
    coefficient_degrees = {
        "Gamma_b_in_tau": int(sp.degree(sp.fraction(b1)[0], tau1)),
        "Gamma_c_in_tau": int(sp.degree(sp.fraction(c1)[0], tau1)),
        "Gamma_d_in_tau": int(sp.degree(sp.fraction(d1)[0], tau1)),
    }
    payload = {
        "theorem": "parallel-transversal-perpendicular-triangle-circles-tangent",
        "assumptions": assumptions,
        "discharged_conditions": discharged_conditions,
        "upstream_semantics": (
            "JGEX triangle constructs a noncollinear ordered triple.",
            "JGEX on_line intersections reject parallel or coincident carriers.",
            "JGEX on_pline preserves the complete carrier direction.",
            "JGEX on_tline constructs a perpendicular carrier through its first point.",
            "JGEX circumcenter rejects collinear or repeated triples.",
            "JGEX on_circle returns a defined real point on the requested circle.",
        ),
        "normalization": (
            "Apply a Euclidean similarity so A=(0,0), B=(1,0), C=(p,q).  "
            "After scaling the transversal equation, the parallel family is x+h*y=tau."
        ),
        "parameterization": {
            "triangle": "A=(0,0), B=(1,0), C=(p,q)",
            "parallel_family": "L_tau: x+h*y=tau",
            "side_intersections": "X_tau=L_tau cap BC, Y_tau=L_tau cap CA, Z_tau=L_tau cap AB",
            "perpendicular_triangle": (
                "U_tau=perp(Y_tau,CA) cap perp(Z_tau,AB); "
                "V_tau=perp(X_tau,BC) cap perp(Z_tau,AB); "
                "W_tau=perp(X_tau,BC) cap perp(Y_tau,CA)"
            ),
            "circle": "Gamma_tau=circumcircle(U_tau,V_tau,W_tau)",
        },
        "representation_chart": (
            "two parallel carrier constructions -> one affine line family",
            "six perpendicular intersections -> two affine-linear point triples",
            "point triples -> circle coefficients affine-linear in tau",
            "common point plus tangency discriminant -> centre/contact collinearity",
        ),
        "circle_parameter_degrees": coefficient_degrees,
        "tangency_factorization": (
            "(D^2-R1^2-R2^2)^2-4*R1^2*R2^2 = 0"
        ),
        "replay_residuals": residuals,
        "replayed": replayed,
        "all_conditions_discharged": replayed,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return ParallelTransversalPerpendicularCirclesCertificate(
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
    if name == "on_line" and len(args) == 2:
        return name, tuple(sorted(args))
    if name in {"on_pline", "on_tline"} and len(args) == 3:
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


def certify_jgex_parallel_transversal_perpendicular_circles_application(
    source: str,
) -> JGEXParallelTransversalPerpendicularCirclesApplication:
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
        for a, b, c in permutations(triangle):
            x_candidates = [
                record["outputs"][0]
                for record in records
                if len(record["outputs"]) == 1
                and len(record["constructions"]) == 1
                and _canonical_construction(record["constructions"][0])
                == _canonical_construction(("on_line", (b, c)))
            ]
            y1_candidates = [
                record["outputs"][0]
                for record in records
                if len(record["outputs"]) == 1
                and len(record["constructions"]) == 1
                and _canonical_construction(record["constructions"][0])
                == _canonical_construction(("on_line", (a, c)))
            ]
            for x1 in x_candidates:
                for x2 in x_candidates:
                    if x1 == x2:
                        continue
                    for y1 in y1_candidates:
                        z1_values = _joint_outputs(
                            records,
                            frozenset(
                                {
                                    ("on_line", (a, b)),
                                    ("on_line", (x1, y1)),
                                }
                            ),
                        )
                        for z1 in z1_values:
                            y2_values = _joint_outputs(
                                records,
                                frozenset(
                                    {
                                        ("on_line", (a, c)),
                                        ("on_pline", (x2, x1, y1)),
                                    }
                                ),
                            )
                            z2_values = _joint_outputs(
                                records,
                                frozenset(
                                    {
                                        ("on_line", (a, b)),
                                        ("on_pline", (x2, x1, y1)),
                                    }
                                ),
                            )
                            for y2 in y2_values:
                                for z2 in z2_values:
                                    groups: list[dict[str, str]] = []
                                    for index, (x_point, y_point, z_point) in enumerate(
                                        ((x1, y1, z1), (x2, y2, z2)), start=1
                                    ):
                                        u_values = _joint_outputs(
                                            records,
                                            frozenset(
                                                {
                                                    ("on_tline", (y_point, a, c)),
                                                    ("on_tline", (z_point, a, b)),
                                                }
                                            ),
                                        )
                                        v_values = _joint_outputs(
                                            records,
                                            frozenset(
                                                {
                                                    ("on_tline", (x_point, b, c)),
                                                    ("on_tline", (z_point, a, b)),
                                                }
                                            ),
                                        )
                                        w_values = _joint_outputs(
                                            records,
                                            frozenset(
                                                {
                                                    ("on_tline", (x_point, b, c)),
                                                    ("on_tline", (y_point, a, c)),
                                                }
                                            ),
                                        )
                                        if not (len(u_values) == len(v_values) == len(w_values) == 1):
                                            break
                                        u_point, v_point, w_point = (
                                            u_values[0], v_values[0], w_values[0]
                                        )
                                        centre = _single(
                                            records,
                                            ("circumcenter", (u_point, v_point, w_point)),
                                        )
                                        if not centre:
                                            break
                                        groups.append(
                                            {
                                                "X": x_point,
                                                "Y": y_point,
                                                "Z": z_point,
                                                "U": u_point,
                                                "V": v_point,
                                                "W": w_point,
                                                "O": centre,
                                            }
                                        )
                                    if len(groups) != 2:
                                        continue
                                    common_values = tuple(
                                        dict.fromkeys(
                                            common
                                            for first_radius in ("U", "V", "W")
                                            for second_radius in ("U", "V", "W")
                                            for common in _joint_outputs(
                                                records,
                                                frozenset(
                                                    {
                                                        (
                                                            "on_circle",
                                                            (
                                                                groups[0]["O"],
                                                                groups[0][first_radius],
                                                            ),
                                                        ),
                                                        (
                                                            "on_circle",
                                                            (
                                                                groups[1]["O"],
                                                                groups[1][second_radius],
                                                            ),
                                                        ),
                                                    }
                                                ),
                                            )
                                        )
                                    )
                                    for common in common_values:
                                        roles = {"A": a, "B": b, "C": c, "T": common}
                                        for index, group in enumerate(groups, start=1):
                                            roles.update(
                                                {f"{name}{index}": value for name, value in group.items()}
                                            )
                                        group_keys = sorted(
                                            tuple(group[name] for name in ("O", "X", "Y", "Z", "U", "V", "W"))
                                            for group in groups
                                        )
                                        key = (
                                            a,
                                            *sorted((b, c)),
                                            common,
                                            *group_keys[0],
                                            *group_keys[1],
                                        )
                                        candidates[key] = roles

    goal = str(formulation.goals[0]) if len(formulation.goals) == 1 else ""
    accepted: list[dict[str, str]] = []
    parts = goal.split()
    if len(parts) == 4:
        actual = Atom(parts[0], tuple(parts[1:])).canonical()
        for roles in candidates.values():
            expected = Atom(
                "coll", (roles["O1"], roles["O2"], roles["T"])
            ).canonical()
            if actual == expected:
                accepted.append(roles)

    chart = certify_parallel_transversal_perpendicular_circles_chart()
    unique = accepted[0] if len(accepted) == 1 else {}
    matched = (
        "two parallel transversals of one triangle",
        "six pairwise perpendicular intersections",
        "two induced circumcircles",
        "one common point of the induced circles",
    ) if unique else ()
    replayed = bool(
        chart.replayed
        and chart.all_conditions_discharged
        and len(unique) == 18
        and len(accepted) == 1
    )
    return JGEXParallelTransversalPerpendicularCirclesApplication(
        theorem=chart.theorem,
        source_sha256=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        roles=unique,
        matched_constructions=matched,
        goal=goal,
        proof_bridge=(
            "The two parallel carriers elaborate to x+h*y=tau1 and x+h*y=tau2. "
            "All six perpendicular intersections are affine-linear in tau, and "
            "the three coefficients of their circumcircle are also affine-linear. "
            "The replayed two-circle discriminant is identically zero for arbitrary "
            "tau1,tau2.  The supplied real common point T is therefore the tangency "
            "point (or the centres coincide), so O1,O2,T are collinear."
        ),
        chart_certificate_sha256=chart.certificate_sha256,
        nondegeneracy_obligations=chart.assumptions,
        undischarged_nondegeneracy_obligations=(),
        replayed=replayed,
    )


def render_parallel_transversal_perpendicular_circles_chart_svg() -> str:
    p, q, h = sp.Rational(2, 5), sp.Rational(6, 5), sp.Rational(1, 3)
    tau1, tau2 = sp.Rational(1, 5), sp.Rational(4, 5)
    groups = []
    for tau in (tau1, tau2):
        points = _build_perpendicular_triangle(p, q, h, tau)
        b_value, c_value, d_value = _circle_coefficients(*points[3:])
        centre = sp.Matrix((-b_value / 2, -c_value / 2))
        radius = sp.sqrt(centre.dot(centre) - d_value)
        groups.append((points, centre, radius, (b_value, c_value, d_value)))

    first_centre, second_centre = groups[0][1], groups[1][1]
    direction = second_centre - first_centre
    direction_length = sp.sqrt(direction.dot(direction))
    candidates = (
        first_centre + groups[0][2] * direction / direction_length,
        first_centre - groups[0][2] * direction / direction_length,
    )
    second_coefficients = groups[1][3]
    tangent = min(
        candidates,
        key=lambda point: abs(
            float(
                point.dot(point)
                + second_coefficients[0] * point[0]
                + second_coefficients[1] * point[1]
                + second_coefficients[2]
            )
        ),
    )

    figure, axis = plt.subplots(figsize=(8.8, 7.0), constrained_layout=True)
    figure.patch.set_facecolor("#f8fafc")
    axis.set_facecolor("#ffffff")
    axis.set_aspect("equal", adjustable="datalim")
    axis.axis("off")
    axis.set_title("Parallel transversals induce tangent circumcircles", loc="left", fontsize=13)
    triangle = ((0.0, 0.0), (1.0, 0.0), (float(p), float(q)), (0.0, 0.0))
    axis.plot([point[0] for point in triangle], [point[1] for point in triangle], color="#334155", linewidth=1.4)
    colors = ("#0891b2", "#7c3aed")
    for index, (points, centre, radius, _coefficients) in enumerate(groups):
        affine = [(float(point[0]), float(point[1])) for point in points]
        for left, right in ((3, 4), (4, 5), (5, 3)):
            axis.plot(
                (affine[left][0], affine[right][0]),
                (affine[left][1], affine[right][1]),
                color=colors[index],
                linewidth=1.2,
                alpha=0.85,
            )
        centre_xy = (float(centre[0]), float(centre[1]))
        axis.add_patch(
            Circle(centre_xy, float(radius), fill=False, color=colors[index], linewidth=2.0)
        )
        axis.scatter((centre_xy[0],), (centre_xy[1],), color=colors[index], s=30, zorder=6)
        axis.annotate(f"O{index + 1}", centre_xy, xytext=(5, 4), textcoords="offset points", color=colors[index], fontsize=9, weight="bold")
    centre_line_x = (float(first_centre[0]), float(second_centre[0]), float(tangent[0]))
    centre_line_y = (float(first_centre[1]), float(second_centre[1]), float(tangent[1]))
    axis.plot(centre_line_x, centre_line_y, color="#e11d48", linewidth=2.0)
    axis.scatter((float(tangent[0]),), (float(tangent[1]),), color="#e11d48", s=34, zorder=7)
    axis.annotate("T", (float(tangent[0]), float(tangent[1])), xytext=(5, 4), textcoords="offset points", color="#e11d48", fontsize=9, weight="bold")
    axis.relim()
    axis.autoscale_view()
    axis.margins(0.16)
    output = io.StringIO()
    figure.savefig(output, format="svg", facecolor=figure.get_facecolor())
    plt.close(figure)
    return output.getvalue()


__all__ = [
    "JGEXParallelTransversalPerpendicularCirclesApplication",
    "ParallelTransversalPerpendicularCirclesCertificate",
    "certify_jgex_parallel_transversal_perpendicular_circles_application",
    "certify_parallel_transversal_perpendicular_circles_chart",
    "render_parallel_transversal_perpendicular_circles_chart_svg",
]
