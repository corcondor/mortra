"""Exact chart for an arc midpoint and two known-root circle steps.

Let the internal bisectors from B,C meet AC,AB at E,F, put
K=AI cap EF, and let T be the midpoint of the BC arc containing A.  If X is
the second intersection of the A-median with (ABC), S is the non-A common
point of (AEF) and (ABC), S' is the reflection of S in AI, and J is the
non-A point of AX on (AS'K), then T,J,I,X are concyclic.

The proof is replayed in the rational function field QQ(u,v).  Both circle
steps use a typed existing root A, while the otherwise ambiguous arc midpoint
is supplied by a hash-bound natural-language atom.
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
from matplotlib.patches import Circle

from worker.backend.geometry_natural_semantics import (
    extract_geometry_natural_semantics,
)
from worker.backend.geometry_proof_hypergraph import Atom
from worker.backend.jgex_chart_parser import ChartJGEXFormulation as JGEXFormulation


def _exact_replay() -> dict[str, str]:
    rational_field, u, v = field("u,v", QQ)
    zero = rational_field.zero
    one = rational_field.one
    half = one / 2

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

    def distance_squared(left, right):
        delta = subtract(left, right)
        return dot(delta, delta)

    def line_intersection(first, first_direction, second, second_direction):
        parameter = (
            cross(subtract(second, first), second_direction)
            / cross(first_direction, second_direction)
        )
        return add(first, scale(parameter, first_direction))

    def foot(value, left, right):
        direction = subtract(right, left)
        parameter = dot(subtract(value, left), direction) / dot(direction, direction)
        return add(left, scale(parameter, direction))

    def reflection(value, left, right):
        projection = foot(value, left, right)
        return subtract(scale(2, projection), value)

    def sine_cosine(parameter):
        denominator = one + parameter**2
        return 2 * parameter / denominator, (one - parameter**2) / denominator

    def circumcircle_point(parameter):
        sine, cosine = sine_cosine(parameter)
        return cosine**2 - sine**2, 2 * sine * cosine

    def second_unit_circle_intersection(known, carrier):
        direction = subtract(carrier, known)
        parameter = -2 * dot(known, direction) / dot(direction, direction)
        return add(known, scale(parameter, direction))

    def circle_coefficients(first, second, third):
        second_delta = subtract(second, first)
        third_delta = subtract(third, first)
        first_norm = dot(first, first)
        second_rhs = -(dot(second, second) - first_norm)
        third_rhs = -(dot(third, third) - first_norm)
        determinant = cross(second_delta, third_delta)
        linear = (
            second_rhs * third_delta[1] - third_rhs * second_delta[1]
        ) / determinant
        vertical = (
            second_delta[0] * third_rhs - third_delta[0] * second_rhs
        ) / determinant
        constant = -(first_norm + linear * first[0] + vertical * first[1])
        return linear, vertical, constant

    def circle_value(value, coefficients):
        linear, vertical, constant = coefficients
        return (
            dot(value, value)
            + linear * value[0]
            + vertical * value[1]
            + constant
        )

    def second_circle_intersection(known, carrier, coefficients):
        linear, vertical, _ = coefficients
        direction = subtract(carrier, known)
        parameter = -(
            2 * dot(known, direction)
            + linear * direction[0]
            + vertical * direction[1]
        ) / dot(direction, direction)
        return add(known, scale(parameter, direction))

    sine_alpha, cosine_alpha = sine_cosine(u)
    sine_beta, _ = sine_cosine(v)
    origin = (zero, zero)
    a = circumcircle_point(u)
    b = circumcircle_point(v)
    c = (b[0], -b[1])
    i = (
        one - 2 * sine_alpha * sine_beta,
        2 * cosine_alpha * sine_beta,
    )
    e = line_intersection(b, subtract(i, b), a, subtract(c, a))
    f = line_intersection(c, subtract(i, c), a, subtract(b, a))
    k = line_intersection(a, subtract(i, a), e, subtract(f, e))
    t = (-one, zero)
    m = scale(half, add(b, c))
    x = second_unit_circle_intersection(a, m)

    aef_circle = circle_coefficients(a, e, f)
    aef_linear, aef_vertical, aef_constant = aef_circle
    radical_direction = (aef_vertical, -aef_linear)
    s = second_unit_circle_intersection(a, add(a, radical_direction))
    s1 = reflection(s, a, i)
    ask_circle = circle_coefficients(a, s1, k)
    j = second_circle_intersection(a, x, ask_circle)
    tjix_circle = circle_coefficients(t, j, i)

    midpoint_ss1 = scale(half, add(s, s1))
    residuals = {
        "A_on_parent_circle": distance_squared(a, origin) - one,
        "B_on_parent_circle": distance_squared(b, origin) - one,
        "C_on_parent_circle": distance_squared(c, origin) - one,
        "I_equidistant_AB_AC": (
            distance_squared(i, foot(i, a, b))
            - distance_squared(i, foot(i, a, c))
        ),
        "I_equidistant_AB_BC": (
            distance_squared(i, foot(i, a, b))
            - distance_squared(i, foot(i, b, c))
        ),
        "E_on_AC": cross(subtract(e, a), subtract(c, a)),
        "B_I_E_collinear": cross(subtract(e, b), subtract(i, b)),
        "F_on_AB": cross(subtract(f, a), subtract(b, a)),
        "C_I_F_collinear": cross(subtract(f, c), subtract(i, c)),
        "K_on_AI": cross(subtract(k, a), subtract(i, a)),
        "K_on_EF": cross(subtract(k, e), subtract(f, e)),
        "T_on_parent_circle": distance_squared(t, origin) - one,
        "T_on_BC_perpendicular_bisector": (
            distance_squared(t, b) - distance_squared(t, c)
        ),
        "M_midpoint_BC_x": m[0] - (b[0] + c[0]) / 2,
        "M_midpoint_BC_y": m[1] - (b[1] + c[1]) / 2,
        "X_on_AM": cross(subtract(x, a), subtract(m, a)),
        "X_on_parent_circle": distance_squared(x, origin) - one,
        "A_on_AEF_circle": circle_value(a, aef_circle),
        "E_on_AEF_circle": circle_value(e, aef_circle),
        "F_on_AEF_circle": circle_value(f, aef_circle),
        "A_on_radical_axis": (
            aef_linear * a[0] + aef_vertical * a[1] + aef_constant + one
        ),
        "S_on_parent_circle": distance_squared(s, origin) - one,
        "S_on_AEF_circle": circle_value(s, aef_circle),
        "SS1_midpoint_on_AI": cross(subtract(midpoint_ss1, a), subtract(i, a)),
        "SS1_perpendicular_AI": dot(subtract(s1, s), subtract(i, a)),
        "A_on_AS1K_circle": circle_value(a, ask_circle),
        "S1_on_AS1K_circle": circle_value(s1, ask_circle),
        "K_on_AS1K_circle": circle_value(k, ask_circle),
        "J_on_AX": cross(subtract(j, a), subtract(x, a)),
        "J_on_AS1K_circle": circle_value(j, ask_circle),
        "T_on_TJIX_circle": circle_value(t, tjix_circle),
        "J_on_TJIX_circle": circle_value(j, tjix_circle),
        "I_on_TJIX_circle": circle_value(i, tjix_circle),
        "X_on_TJIX_circle": circle_value(x, tjix_circle),
    }
    return {
        name: "0" if value == zero else str(value)
        for name, value in residuals.items()
    }


@dataclass(frozen=True)
class ArcMidpointReflectedBisectorCyclicCertificate:
    theorem: str
    assumptions: tuple[str, ...]
    discharged_conditions: dict[str, str]
    upstream_semantics: tuple[str, ...]
    normalization: str
    parameterization: dict[str, str]
    representation_chart: tuple[str, ...]
    proof_dag: tuple[str, ...]
    branch_certificate: dict[str, str]
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
                "# Arc-midpoint reflected-bisector cyclic chart",
                "",
                "## Reusable proof",
                "",
                "1. Normalize the parent circumcircle and its incenter rationally.",
                "2. Build E,F,K by exact carrier-line intersections.",
                "3. Use the natural arc atom to select T and the known root A to obtain X.",
                "4. Subtract the equations of (AEF) and (ABC); use A to obtain S.",
                "5. Reflect S in AI and solve the circle (AS'K).",
                "6. Use A again to obtain J; the TJIX circle residual is zero.",
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
class JGEXArcMidpointReflectedBisectorCyclicApplication:
    theorem: str
    source_sha256: str
    natural_statement_sha256: str
    natural_statement: str
    natural_semantic_atoms: tuple[str, ...]
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
def certify_arc_midpoint_reflected_bisector_cyclic_chart(
) -> ArcMidpointReflectedBisectorCyclicCertificate:
    residuals = _exact_replay()
    replayed = all(value == "0" for value in residuals.values())
    assumptions = (
        "ABC is a nondegenerate triangle with circumcenter O and incenter I",
        "E=BI cap AC, F=CI cap AB, and K=AI cap EF are finite",
        "T is the midpoint of the BC arc containing A",
        "X is the non-A point of AM on (ABC)",
        "S is the non-A common point of (AEF) and (ABC)",
        "S' is the reflection of S in AI and (AS'K) is defined",
        "J is the non-A point of AX on (AS'K)",
    )
    discharged = {
        assumptions[0]: "The triangle, circumcenter, and incenter clauses are matched.",
        assumptions[1]: "The two bisector feet and both carrier intersections are matched.",
        assumptions[2]: "A hash-bound arc_midpoint_through atom fixes the branch.",
        assumptions[3]: "A is the existing line-circle root, so X is the other root.",
        assumptions[4]: "A is common to both circles, so S is the other root.",
        assumptions[5]: "The reflection and circumcenter clauses are matched.",
        assumptions[6]: "A is the existing root on AX and (AS'K).",
    }
    payload = {
        "theorem": "arc-midpoint-reflected-bisector-two-circle-cyclicity",
        "assumptions": assumptions,
        "discharged_conditions": discharged,
        "upstream_semantics": (
            "Internal angle-bisector feet are intersections with BI and CI.",
            "arc_midpoint_through distinguishes the two perpendicular-bisector roots.",
            "A supplied common circle point is excluded by second-root semantics.",
            "JGEX reflect is Euclidean reflection in the carrier line.",
        ),
        "normalization": (
            "Normalize (ABC) to the unit circle with B,C symmetric about the x-axis; "
            "u=tan(alpha/2), v=tan(beta/2), and the arc midpoint through A is (-1,0)."
        ),
        "parameterization": {
            "triangle_domain": "0<v<u and u*v<1, excluding vanishing chart denominators",
            "parent_circle": "x^2+y^2=1",
            "known_root_elimination": "lambda=-2<P,D>/|D|^2 or its general-circle analogue",
        },
        "representation_chart": (
            "angle bisectors -> incenter carrier lines",
            "arc midpoint phrase -> typed circumcircle branch",
            "two circles with known common point -> radical-axis second root",
            "axis reflection -> affine point",
            "known-root secant -> second circle point",
            "circle residual -> cyclic relation",
        ),
        "proof_dag": (
            "Construct E,F,K and the typed arc midpoint T.",
            "Eliminate A from AM cap (ABC) to obtain X.",
            "Subtract (AEF) and (ABC), then eliminate A to obtain S.",
            "Reflect S across AI and construct (AS'K).",
            "Eliminate A from AX cap (AS'K) to obtain J.",
            "Replay the circle through T,J,I at X; its residual is zero.",
        ),
        "branch_certificate": {
            "T": "arc_midpoint_through(T,B,A,C)",
            "X": "A is the typed existing root",
            "S": "A is the typed existing common point of both circles",
            "J": "A is the typed existing root",
        },
        "replay_residuals": residuals,
        "replayed": replayed,
        "all_conditions_discharged": replayed,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return ArcMidpointReflectedBisectorCyclicCertificate(
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


def _canonical_construction(item):
    name, args = item
    if name in {"circumcenter", "incenter"} and len(args) == 3:
        return name, tuple(sorted(args))
    if name in {"on_line", "on_bline", "midpoint"} and len(args) == 2:
        return name, tuple(sorted(args))
    if name == "angle_bisector" and len(args) == 3:
        return name, (min(args[0], args[2]), args[1], max(args[0], args[2]))
    if name == "reflect" and len(args) == 3:
        return name, (args[0], *sorted(args[1:]))
    return name, args


def _single(records, constructions):
    expected = sorted(map(_canonical_construction, constructions), key=repr)
    matches = {
        str(record["outputs"][0])
        for record in records
        if len(record["outputs"]) == 1
        and sorted(map(_canonical_construction, record["constructions"]), key=repr)
        == expected
    }
    return next(iter(matches)) if len(matches) == 1 else None


def certify_jgex_arc_midpoint_reflected_bisector_cyclic_application(
    source: str,
    natural_statement: str | None = None,
) -> JGEXArcMidpointReflectedBisectorCyclicApplication:
    normalized = source.strip()
    natural = (natural_statement or "").strip()
    semantics = extract_geometry_natural_semantics(natural)
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
        i = _single(records, (("incenter", (a, b, c)),))
        e = _single(
            records,
            (("on_line", (a, c)), ("angle_bisector", (c, b, a))),
        )
        f = _single(
            records,
            (("on_line", (a, b)), ("angle_bisector", (b, c, a))),
        )
        if not all((o, i, e, f)):
            continue
        k = _single(records, (("on_line", (a, i)), ("on_line", (e, f))))
        t = _single(records, (("on_circle", (o, a)), ("on_bline", (b, c))))
        m = _single(records, (("midpoint", (b, c)),))
        if not all((k, t, m)):
            continue
        x = _single(records, (("on_line", (a, m)), ("on_circle", (o, a))))
        o1 = _single(records, (("circumcenter", (a, e, f)),))
        if not x or not o1:
            continue
        s = _single(records, (("on_circle", (o1, a)), ("on_circle", (o, a))))
        if not s:
            continue
        s1 = _single(records, (("reflect", (s, a, i)),))
        if not s1:
            continue
        o2 = _single(records, (("circumcenter", (a, s1, k)),))
        if not o2:
            continue
        j = _single(records, (("on_line", (a, x)), ("on_circle", (o2, a))))
        if not j or not semantics.has_arc_midpoint_through(t, (b, c), a):
            continue
        roles = {
            "A": a, "B": b, "C": c, "O": o, "I": i, "E": e, "F": f,
            "K": k, "T": t, "M": m, "X": x, "O1": o1, "S": s,
            "S1": s1, "O2": o2, "J": j,
        }
        actual = Atom(
            formulation.goals[0].predicate,
            formulation.goals[0].args,
        ).canonical() if len(formulation.goals) == 1 else None
        expected = Atom("cyclic", (t, j, i, x)).canonical()
        if actual == expected:
            accepted.append(roles)

    chart = certify_arc_midpoint_reflected_bisector_cyclic_chart()
    roles = accepted[0] if len(accepted) == 1 else {}
    replayed = bool(roles and chart.replayed and chart.all_conditions_discharged)
    goal = str(formulation.goals[0]) if len(formulation.goals) == 1 else ""
    return JGEXArcMidpointReflectedBisectorCyclicApplication(
        theorem=chart.theorem,
        source_sha256=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        natural_statement_sha256=hashlib.sha256(natural.encode("utf-8")).hexdigest(),
        natural_statement=natural,
        natural_semantic_atoms=semantics.typed_atoms,
        roles=roles,
        matched_constructions=(
            "two internal-bisector feet and K=AI intersect EF",
            "hash-bound BC arc midpoint through A",
            "A-median second circumcircle point X",
            "second common point S of (AEF) and (ABC)",
            "reflection S' in AI and second point J on (AS'K)",
        ) if roles else (),
        goal=goal,
        proof_bridge=(
            "arc branch -> two known-root circle eliminations -> axis reflection -> "
            "exact four-point circle residual"
        ),
        chart_certificate_sha256=chart.certificate_sha256,
        nondegeneracy_obligations=chart.assumptions,
        undischarged_nondegeneracy_obligations=() if replayed else chart.assumptions,
        replayed=replayed,
    )


def render_arc_midpoint_reflected_bisector_cyclic_chart_svg() -> str:
    def unit_half(parameter: float) -> tuple[float, float]:
        sine = 2 * parameter / (1 + parameter * parameter)
        cosine = (1 - parameter * parameter) / (1 + parameter * parameter)
        return cosine * cosine - sine * sine, 2 * sine * cosine

    def cross(left, right):
        return left[0] * right[1] - left[1] * right[0]

    def sub(left, right):
        return left[0] - right[0], left[1] - right[1]

    def line(first, direction, second, second_direction):
        parameter = cross(sub(second, first), second_direction) / cross(
            direction, second_direction
        )
        return first[0] + parameter * direction[0], first[1] + parameter * direction[1]

    def second_unit(known, carrier):
        direction = sub(carrier, known)
        parameter = -2 * (known[0] * direction[0] + known[1] * direction[1]) / (
            direction[0] ** 2 + direction[1] ** 2
        )
        return (
            known[0] + parameter * direction[0],
            known[1] + parameter * direction[1],
        )

    u, v = 0.58, 0.24
    sine_alpha = 2 * u / (1 + u * u)
    cosine_alpha = (1 - u * u) / (1 + u * u)
    sine_beta = 2 * v / (1 + v * v)
    a, b = unit_half(u), unit_half(v)
    c = (b[0], -b[1])
    i = (1 - 2 * sine_alpha * sine_beta, 2 * cosine_alpha * sine_beta)
    e = line(b, sub(i, b), a, sub(c, a))
    f = line(c, sub(i, c), a, sub(b, a))
    k = line(a, sub(i, a), e, sub(f, e))
    t = (-1.0, 0.0)
    m = ((b[0] + c[0]) / 2, (b[1] + c[1]) / 2)
    x = second_unit(a, m)

    # The exact certificate contains S,S',J; the diagram emphasizes the final
    # parent-circle and TJIX relation without duplicating the algebra engine.
    fig, axis = plt.subplots(figsize=(8.8, 6.0))
    fig.patch.set_facecolor("#07090c")
    axis.set_facecolor("#07090c")
    axis.add_patch(Circle((0, 0), 1, fill=False, color="#34424f", linewidth=1.4))
    axis.plot([a[0], b[0], c[0], a[0]], [a[1], b[1], c[1], a[1]], color="#74838f")
    axis.plot([b[0], i[0], e[0]], [b[1], i[1], e[1]], color="#31d7e8")
    axis.plot([c[0], i[0], f[0]], [c[1], i[1], f[1]], color="#31d7e8")
    axis.plot([e[0], k[0], f[0]], [e[1], k[1], f[1]], color="#ffb454")
    axis.plot([a[0], m[0], x[0]], [a[1], m[1], x[1]], color="#b8c3cb")
    points = {"A": a, "B": b, "C": c, "I": i, "E": e, "F": f, "K": k, "T": t, "X": x}
    for label, value in points.items():
        color = "#31d7e8" if label in {"T", "X"} else "#f1f5f8"
        axis.scatter([value[0]], [value[1]], s=22, color=color, zorder=4)
        axis.text(value[0] + 0.025, value[1] + 0.025, label, color=color, fontsize=9)
    axis.set_aspect("equal", adjustable="datalim")
    axis.axis("off")
    axis.set_title("arc midpoint | reflected bisector circle chain", color="#e7edf2", fontsize=12)
    fig.tight_layout()
    buffer = io.StringIO()
    fig.savefig(buffer, format="svg", bbox_inches="tight")
    plt.close(fig)
    return buffer.getvalue()


__all__ = [
    "ArcMidpointReflectedBisectorCyclicCertificate",
    "JGEXArcMidpointReflectedBisectorCyclicApplication",
    "certify_arc_midpoint_reflected_bisector_cyclic_chart",
    "certify_jgex_arc_midpoint_reflected_bisector_cyclic_application",
    "render_arc_midpoint_reflected_bisector_cyclic_chart_svg",
]
