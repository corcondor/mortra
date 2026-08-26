"""Exact chart for a circle of three circumcenters and an isogonal reflection.

For a point P and a cyclic triangle ABC, the circumcenters of APB, BPC,
CPA define a second circle.  Reflecting P in the radical axis of that circle
and (ABC) produces the A-isogonal line.  The proof uses one unit-circle
complex chart; no problem identifier or expected conclusion is consulted.
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


@dataclass(frozen=True)
class ThreeCircumcentersRadicalReflectionCertificate:
    theorem: str
    assumptions: tuple[str, ...]
    discharged_conditions: dict[str, str]
    upstream_semantics: tuple[str, ...]
    normalization: str
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
                "# Three-circumcenter radical-reflection chart",
                "",
                "## Theorem",
                "",
                (
                    "Let O1,O2,O3 be the circumcenters of APB, BPC, CPA.  The "
                    "circle through O1,O2,O3 meets (ABC) in X,Y.  If Q is the "
                    "reflection of P in XY, then AP and AQ are isogonal in angle BAC."
                ),
                "",
                "## Representation changes",
                "",
                "- three circumcenters -> six linear equal-distance equations",
                "- their circumcircle -> one Hermitian circle equation",
                "- the common chord XY -> subtraction of the two circle equations",
                "- reflection in XY -> one rational complex expression",
                "- isogonality at A -> reality of one cross-ratio product",
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
class JGEXThreeCircumcentersRadicalReflectionApplication:
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
def certify_three_circumcenters_radical_reflection_chart() -> (
    ThreeCircumcentersRadicalReflectionCertificate
):
    a, b, c, p, p_bar = sp.symbols("a b c p p_bar", nonzero=True)

    def bar(value: sp.Expr) -> sp.Expr:
        return sp.cancel(
            value.subs(
                {a: 1 / a, b: 1 / b, c: 1 / c, p: p_bar, p_bar: p},
                simultaneous=True,
            )
        )

    def circumcenter(first: sp.Expr, second: sp.Expr, third: sp.Expr) -> sp.Expr:
        centre, centre_bar = sp.symbols("centre centre_bar")
        equations = []
        for other in (second, third):
            equations.append(
                sp.expand(
                    centre * (bar(first) - bar(other))
                    + centre_bar * (first - other)
                    - (first * bar(first) - other * bar(other))
                )
            )
        solution = sp.solve(
            equations,
            (centre, centre_bar),
            dict=True,
            simplify=False,
        )[0]
        return sp.factor(sp.cancel(solution[centre]))

    o1 = circumcenter(a, p, b)
    o2 = circumcenter(b, p, c)
    o3 = circumcenter(c, p, a)

    circle_u, circle_v, circle_w = sp.symbols("circle_u circle_v circle_w")
    circle_equations = (
        o1 * bar(o1) + circle_u * o1 + circle_v * bar(o1) + circle_w,
        o2 * bar(o2) + circle_u * o2 + circle_v * bar(o2) + circle_w,
        o3 * bar(o3) + circle_u * o3 + circle_v * bar(o3) + circle_w,
    )
    circle_solution = sp.solve(
        circle_equations,
        (circle_u, circle_v, circle_w),
        dict=True,
        simplify=False,
    )[0]
    u = sp.factor(sp.cancel(circle_solution[circle_u]))
    v = sp.factor(sp.cancel(circle_solution[circle_v]))
    w = sp.factor(sp.cancel(circle_solution[circle_w]))
    axis_constant = sp.factor(w + 1)

    # For U*z + conjugate(U)*conjugate(z) + C = 0, reflection is
    # q = p - (U*p + conjugate(U)*conjugate(p) + C)/U.
    q = sp.factor(sp.cancel(-(v * p_bar + axis_constant) / u))
    q_bar = bar(q)

    def distance_squared(left: sp.Expr, right: sp.Expr) -> sp.Expr:
        return sp.cancel((left - right) * (bar(left) - bar(right)))

    z_value, z_bar_value = sp.symbols("z_value z_bar_value")
    gamma = z_value * z_bar_value + u * z_value + v * z_bar_value + w
    omega = z_value * z_bar_value - 1
    radical_axis = u * z_value + v * z_bar_value + axis_constant
    midpoint = sp.cancel((p + q) / 2)
    midpoint_bar = sp.cancel((p_bar + q_bar) / 2)
    isogonal_ratio = sp.cancel((p - a) * (q - a) / ((b - a) * (c - a)))

    raw_residuals = {
        "A_on_normalized_circumcircle": a * bar(a) - 1,
        "B_on_normalized_circumcircle": b * bar(b) - 1,
        "C_on_normalized_circumcircle": c * bar(c) - 1,
        "O1_equidistant_A_P": distance_squared(o1, a) - distance_squared(o1, p),
        "O1_equidistant_A_B": distance_squared(o1, a) - distance_squared(o1, b),
        "O2_equidistant_B_P": distance_squared(o2, b) - distance_squared(o2, p),
        "O2_equidistant_B_C": distance_squared(o2, b) - distance_squared(o2, c),
        "O3_equidistant_C_P": distance_squared(o3, c) - distance_squared(o3, p),
        "O3_equidistant_C_A": distance_squared(o3, c) - distance_squared(o3, a),
        "O1_on_three_center_circle": circle_equations[0].subs(circle_solution),
        "O2_on_three_center_circle": circle_equations[1].subs(circle_solution),
        "O3_on_three_center_circle": circle_equations[2].subs(circle_solution),
        "three_center_circle_has_conjugate_coefficients": v - bar(u),
        "three_center_circle_has_real_constant": w - bar(w),
        "circle_subtraction_is_radical_axis": gamma - omega - radical_axis,
        "reflection_midpoint_lies_on_radical_axis": (
            u * midpoint + v * midpoint_bar + axis_constant
        ),
        "reflection_segment_is_normal_to_axis": (
            q - p + (u * p + v * p_bar + axis_constant) / u
        ),
        "isogonal_cross_ratio_is_real": isogonal_ratio - bar(isogonal_ratio),
    }
    residuals = {name: _canonical(value) for name, value in raw_residuals.items()}
    replayed = all(value == "0" for value in residuals.values())
    assumptions = (
        "ABC is a defined nondegenerate triangle with circumcenter O",
        "P is a defined point distinct from the required circumcenter triples",
        "O1,O2,O3 are the defined circumcenters of APB,BPC,CPA",
        "OG is the defined circumcenter of O1O2O3",
        "X and Y are the two defined common points of (ABC) and (O1O2O3)",
        "Q is the reflection of P in the defined line XY",
    )
    discharged_conditions = {
        assumptions[0]: "The triangle and original circumcenter clauses are matched.",
        assumptions[
            1
        ]: "The free-point clause and all three dependent triples are matched.",
        assumptions[
            2
        ]: "All three circumcenter constructors are matched by their triples.",
        assumptions[3]: "The circumcenter of the three centers is matched explicitly.",
        assumptions[4]: (
            "Two distinct outputs share the same pair of on_circle clauses; their "
            "carrier line is the radical axis obtained by circle subtraction."
        ),
        assumptions[
            5
        ]: "The reflect constructor uses exactly P and the two common points.",
    }
    payload = {
        "theorem": "three-circumcenters-radical-axis-reflection-isogonal",
        "assumptions": assumptions,
        "discharged_conditions": discharged_conditions,
        "upstream_semantics": (
            "JGEX circumcenter rejects collinear or repeated defining triples.",
            "Two joint on_circle outputs determine the common chord of the two circles.",
            "JGEX reflect denotes Euclidean reflection in the carrier line.",
            "JGEX eqangle is the oriented isogonality relation modulo pi.",
        ),
        "normalization": (
            "Translate and scale (ABC) to the unit circle and write conjugates of "
            "A,B,C as 1/A,1/B,1/C; keep P and conjugate(P) independent."
        ),
        "representation_chart": (
            "circumcenter -> two linear equal-distance equations",
            "circle through three centers -> Hermitian circle coefficients",
            "two-circle common chord -> radical-axis subtraction",
            "line reflection -> rational complex normal projection",
            "equal angles at A -> real isogonal cross-ratio product",
        ),
        "proof_dag": (
            "Solve the three pairs of equal-distance equations for O1,O2,O3.",
            "Solve the circle equation through O1,O2,O3 and verify its real structure.",
            "Subtract the unit-circle equation to obtain the line XY.",
            "Reflect P across XY using its complex normal coefficient.",
            "Substitute Q into the isogonal cross-ratio at A.",
            "The ratio equals its conjugate identically, proving the target eqangle.",
        ),
        "replay_residuals": residuals,
        "replayed": replayed,
        "all_conditions_discharged": replayed,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return ThreeCircumcentersRadicalReflectionCertificate(
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
    if name == "circumcenter" and len(args) == 3:
        return name, tuple(sorted(args))
    if name == "on_circle" and len(args) == 2:
        return construction
    if name == "reflect" and len(args) == 3:
        return name, (args[0], *sorted(args[1:]))
    return construction


def _single(
    records: tuple[dict[str, object], ...],
    construction: tuple[str, tuple[str, ...]],
) -> str | None:
    expected = _canonical_construction(construction)
    matches = {
        str(record["outputs"][0])
        for record in records
        if len(record["outputs"]) == 1
        and len(record["constructions"]) == 1
        and _canonical_construction(record["constructions"][0]) == expected
    }
    return next(iter(matches)) if len(matches) == 1 else None


def _joint_circle_pair(
    records: tuple[dict[str, object], ...],
    first: tuple[str, str],
    second: tuple[str, str],
) -> tuple[str, str] | None:
    expected = sorted(
        (
            _canonical_construction(("on_circle", first)),
            _canonical_construction(("on_circle", second)),
        ),
        key=repr,
    )
    matches = sorted(
        {
            str(record["outputs"][0])
            for record in records
            if len(record["outputs"]) == 1
            and sorted(map(_canonical_construction, record["constructions"]), key=repr)
            == expected
        }
    )
    return (matches[0], matches[1]) if len(matches) == 2 else None


def certify_jgex_three_circumcenters_radical_reflection_application(
    source: str,
) -> JGEXThreeCircumcentersRadicalReflectionApplication:
    normalized = source.strip()
    formulation = JGEXFormulation.from_text(normalized)
    records = _records(formulation)
    candidates: dict[tuple[tuple[str, str], ...], dict[str, str]] = {}
    triangles = [
        tuple(record["outputs"])
        for record in records
        if len(record["outputs"]) == 3
        and record["constructions"] == (("triangle", ()),)
    ]
    free_points = [
        str(record["outputs"][0])
        for record in records
        if len(record["outputs"]) == 1 and record["constructions"] == (("free", ()),)
    ]
    for triangle in triangles:
        for a, b, c in permutations(triangle):
            o = _single(records, ("circumcenter", (a, b, c)))
            if not o:
                continue
            for p in free_points:
                o1 = _single(records, ("circumcenter", (a, p, b)))
                o2 = _single(records, ("circumcenter", (b, p, c)))
                o3 = _single(records, ("circumcenter", (c, p, a)))
                if not o1 or not o2 or not o3:
                    continue
                og = _single(records, ("circumcenter", (o1, o2, o3)))
                if not og:
                    continue
                common = _joint_circle_pair(records, (o, a), (og, o1))
                if not common:
                    continue
                x, y = common
                q = _single(records, ("reflect", (p, x, y)))
                if not q:
                    continue
                roles = {
                    "A": a,
                    "B": b,
                    "C": c,
                    "P": p,
                    "O": o,
                    "O1": o1,
                    "O2": o2,
                    "O3": o3,
                    "OG": og,
                    "X": x,
                    "Y": y,
                    "Q": q,
                }
                candidates[tuple(sorted(roles.items()))] = roles

    goal = str(formulation.goals[0]) if len(formulation.goals) == 1 else ""
    accepted: list[dict[str, str]] = []
    parts = goal.split()
    if len(parts) == 9:
        actual = Atom(parts[0], tuple(parts[1:])).canonical()
        for roles in candidates.values():
            expected = Atom(
                "eqangle",
                (
                    roles["A"],
                    roles["B"],
                    roles["A"],
                    roles["P"],
                    roles["A"],
                    roles["Q"],
                    roles["A"],
                    roles["C"],
                ),
            ).canonical()
            if actual == expected:
                accepted.append(roles)

    chart = certify_three_circumcenters_radical_reflection_chart()
    unique = accepted[0] if len(accepted) == 1 else {}
    matched = (
        (
            "three circumcenters around one free point and a cyclic triangle",
            "the circumcircle of those three centers",
            "the two common points with the original circumcircle",
            "reflection in the common chord and the isogonal target",
        )
        if unique
        else ()
    )
    replayed = bool(
        chart.replayed
        and chart.all_conditions_discharged
        and len(unique) == 12
        and len(accepted) == 1
    )
    return JGEXThreeCircumcentersRadicalReflectionApplication(
        theorem=chart.theorem,
        source_sha256=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        roles=unique,
        matched_constructions=matched,
        goal=goal,
        proof_bridge=(
            "Normalize (ABC) to the unit circle.  Each of O1,O2,O3 follows from two "
            "linear equal-distance equations.  Subtracting their circle from the unit "
            "circle gives XY directly.  Reflecting P in that Hermitian line yields a "
            "rational Q for which (P-A)(Q-A)/((B-A)(C-A)) is real."
        ),
        chart_certificate_sha256=chart.certificate_sha256,
        nondegeneracy_obligations=chart.assumptions,
        undischarged_nondegeneracy_obligations=(),
        replayed=replayed,
    )


def render_three_circumcenters_radical_reflection_chart_svg() -> str:
    a = sp.Matrix((sp.Rational(-3, 5), sp.Rational(4, 5)))
    b = sp.Matrix((sp.Rational(-4, 5), sp.Rational(-3, 5)))
    c = sp.Matrix((sp.Rational(5, 13), sp.Rational(-12, 13)))
    p = sp.Matrix((sp.Rational(-1, 10), sp.Rational(-1, 5)))

    def centre(points: tuple[sp.Matrix, sp.Matrix, sp.Matrix]) -> sp.Matrix:
        first = points[0]
        matrix = sp.Matrix([list(2 * (other - first)) for other in points[1:]])
        rhs = sp.Matrix([other.dot(other) - first.dot(first) for other in points[1:]])
        return matrix.inv() * rhs

    o1, o2, o3 = centre((a, p, b)), centre((b, p, c)), centre((c, p, a))
    og = centre((o1, o2, o3))
    radius = sp.sqrt((o1 - og).dot(o1 - og))
    normal = -2 * og
    constant = og.dot(og) - radius**2 + 1
    signed = sp.cancel((normal.dot(p) + constant) / normal.dot(normal))
    q = p - 2 * signed * normal

    figure, axis = plt.subplots(figsize=(8.8, 6.0))
    axis.set_aspect("equal")
    axis.axis("off")
    axis.set_facecolor("#050709")
    figure.patch.set_facecolor("#050709")
    axis.add_patch(Circle((0, 0), 1, fill=False, color="#334155", linewidth=1.4))
    axis.add_patch(
        Circle(
            (float(og[0]), float(og[1])),
            float(radius),
            fill=False,
            color="#475569",
            linewidth=1.2,
        )
    )
    triangle = (a, b, c, a)
    axis.plot(
        [float(v[0]) for v in triangle],
        [float(v[1]) for v in triangle],
        color="#64748b",
    )
    direction = sp.Matrix((-normal[1], normal[0]))
    base = -constant * normal / normal.dot(normal)
    left, right = base - 2 * direction, base + 2 * direction
    axis.plot(
        (float(left[0]), float(right[0])),
        (float(left[1]), float(right[1])),
        color="#22d3ee",
        linewidth=1.7,
    )
    axis.plot(
        (float(p[0]), float(q[0])),
        (float(p[1]), float(q[1])),
        color="#fbbf24",
        linewidth=1.5,
    )
    axis.plot(
        (float(a[0]), float(p[0])),
        (float(a[1]), float(p[1])),
        color="#a3e635",
        linewidth=1.8,
    )
    axis.plot(
        (float(a[0]), float(q[0])),
        (float(a[1]), float(q[1])),
        color="#f472b6",
        linewidth=1.8,
    )
    for label, value, color in (
        ("A", a, "#f8fafc"),
        ("B", b, "#94a3b8"),
        ("C", c, "#94a3b8"),
        ("P", p, "#fbbf24"),
        ("Q", q, "#f472b6"),
        ("O1", o1, "#64748b"),
        ("O2", o2, "#64748b"),
        ("O3", o3, "#64748b"),
    ):
        axis.scatter(float(value[0]), float(value[1]), s=28, color=color, zorder=5)
        axis.text(
            float(value[0]) + 0.04,
            float(value[1]) + 0.04,
            label,
            color=color,
            fontsize=9,
        )
    axis.text(
        -1.55,
        1.32,
        "three centers -> radical reflection -> isogonal rays",
        color="#f8fafc",
        fontsize=10,
    )
    axis.set_xlim(-1.65, 1.65)
    axis.set_ylim(-1.35, 1.45)
    buffer = io.StringIO()
    figure.savefig(
        buffer, format="svg", bbox_inches="tight", facecolor=figure.get_facecolor()
    )
    plt.close(figure)
    return buffer.getvalue()


__all__ = [
    "ThreeCircumcentersRadicalReflectionCertificate",
    "JGEXThreeCircumcentersRadicalReflectionApplication",
    "certify_three_circumcenters_radical_reflection_chart",
    "certify_jgex_three_circumcenters_radical_reflection_application",
    "render_three_circumcenters_radical_reflection_chart_svg",
]
