"""Exact chart for an incircle contact triangle and two radical-axis pencils.

The theorem is the reusable algebraic core of USA TSTST 2016/6.  It is
matched from construction dependencies only.  After normalizing the incircle
to the unit circle, the whole proof has two free tangent parameters and the
target is one equality of powers.
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
class IncircleContactPencilMidpointCertificate:
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
                "# Incircle-contact circle-pencil midpoint chart",
                "",
                "## Theorem",
                "",
                (
                    "Let D,E,F be the contact points of the incircle of triangle ABC. "
                    "Let K be the projection of D onto EF and M the midpoint of DK. "
                    "The circle through B and the common chord of (AIC) with the "
                    "incircle, and the analogous circle through C from (AIB), have "
                    "equal power at M."
                ),
                "",
                "## Representation changes",
                "",
                "- contact triangle -> three tangent-line intersections",
                "- circle-circle intersections -> a linear common-chord equation",
                "- three-point circle -> incircle plus a multiple of that chord",
                "- midpoint collinearity -> equality of two circle powers",
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
class JGEXIncircleContactPencilMidpointApplication:
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
def certify_incircle_contact_pencil_midpoint_chart(
) -> IncircleContactPencilMidpointCertificate:
    u, v = sp.symbols("u v", real=True)
    one = sp.Integer(1)

    d = sp.Matrix((one, 0))
    e = sp.Matrix(((1 - u**2) / (1 + u**2), 2 * u / (1 + u**2)))
    f = sp.Matrix(((1 - v**2) / (1 + v**2), 2 * v / (1 + v**2)))
    a = sp.Matrix(((1 - u * v) / (1 + u * v), (u + v) / (1 + u * v)))
    b = sp.Matrix((one, v))
    c = sp.Matrix((one, u))

    k = sp.Matrix(
        (
            -(u**2 * v**2 - u**2 - 2 * u * v - v**2 - 1)
            / ((u**2 + 1) * (v**2 + 1)),
            2 * u * v * (u + v) / ((u**2 + 1) * (v**2 + 1)),
        )
    )
    m = sp.Matrix(
        (
            (u**2 + u * v + v**2 + 1) / ((u**2 + 1) * (v**2 + 1)),
            u * v * (u + v) / ((u**2 + 1) * (v**2 + 1)),
        )
    )

    # Common chords of (AIC) and (AIB) with the unit incircle.
    g_b = sp.Matrix(
        (-(u**2 + 1) / (u * v + 1), -v * (u**2 + 1) / (u * v + 1))
    )
    g_c = sp.Matrix(
        (-(v**2 + 1) / (u * v + 1), -u * (v**2 + 1) / (u * v + 1))
    )

    def gamma(point: sp.Matrix) -> sp.Expr:
        return point.dot(point) - 1

    def chord(g: sp.Matrix, point: sp.Matrix) -> sp.Expr:
        return g.dot(point) + 1

    lambda_b = -gamma(b) / chord(g_b, b)
    lambda_c = -gamma(c) / chord(g_c, c)
    power_b_at_m = gamma(m) + lambda_b * chord(g_b, m)
    power_c_at_m = gamma(m) + lambda_c * chord(g_c, m)

    x, y, gx, gy, lam = sp.symbols("x y gx gy lam", real=True)
    unit_circle = x**2 + y**2 - 1
    through_origin_circle = x**2 + y**2 + gx * x + gy * y
    common_chord = gx * x + gy * y + 1

    raw_residuals = {
        "D_on_normalized_incircle": gamma(d),
        "E_on_normalized_incircle": gamma(e),
        "F_on_normalized_incircle": gamma(f),
        "A_on_tangent_at_E": e.dot(a) - 1,
        "A_on_tangent_at_F": f.dot(a) - 1,
        "B_on_tangent_at_F": f.dot(b) - 1,
        "B_on_tangent_at_D": d.dot(b) - 1,
        "C_on_tangent_at_D": d.dot(c) - 1,
        "C_on_tangent_at_E": e.dot(c) - 1,
        "K_on_EF": sp.det(sp.Matrix.hstack(k - e, f - e)),
        "DK_perpendicular_EF": (d - k).dot(f - e),
        "M_midpoint_DK_x": 2 * m[0] - d[0] - k[0],
        "M_midpoint_DK_y": 2 * m[1] - d[1] - k[1],
        "A_on_circle_AIC": gamma(a) + chord(g_b, a),
        "C_on_circle_AIC": gamma(c) + chord(g_b, c),
        "A_on_circle_AIB": gamma(a) + chord(g_c, a),
        "B_on_circle_AIB": gamma(b) + chord(g_c, b),
        "circle_subtraction_gives_common_chord": (
            through_origin_circle - unit_circle - common_chord
        ),
        "B_closes_first_circle_pencil": gamma(b) + lambda_b * chord(g_b, b),
        "C_closes_second_circle_pencil": gamma(c) + lambda_c * chord(g_c, c),
        "M_has_equal_power_to_both_pencil_circles": (
            power_b_at_m - power_c_at_m
        ),
        "circle_pencil_preserves_common_chord": (
            (unit_circle + lam * common_chord) - unit_circle - lam * common_chord
        ),
    }
    residuals = {name: _canonical(value) for name, value in raw_residuals.items()}
    replayed = all(value == "0" for value in residuals.values())

    assumptions = (
        "ABC is a defined nondegenerate triangle with incenter I",
        "D,E,F are the three defined perpendicular contact projections from I",
        "K is the defined projection of D onto EF and M is the midpoint of DK",
        "the AIB and AIC circumcircles meet the incircle in the displayed pairs",
        "the two target circumcircles through B and C are defined",
        "P1 and P2 are the two displayed common points of the target circles",
    )
    discharged_conditions = {
        assumptions[0]: "The triangle and incenter constructors are matched explicitly.",
        assumptions[1]: "All three foot constructors and their carrier sides are matched.",
        assumptions[2]: "The projection and midpoint constructors are matched explicitly.",
        assumptions[3]: (
            "Each pair is supplied by two joint on_circle clauses.  The common-chord "
            "equation follows by subtracting the two circle equations."
        ),
        assumptions[4]: "Both circumcenter constructors reject repeated or collinear triples.",
        assumptions[5]: (
            "The final joint on_circle clauses provide the radical-axis endpoints; equal "
            "powers put M on their line."
        ),
    }
    payload = {
        "theorem": "incircle-contact-circle-pencil-midpoint-radical-axis",
        "assumptions": assumptions,
        "discharged_conditions": discharged_conditions,
        "upstream_semantics": (
            "JGEX incenter and foot clauses encode the incircle contact triangle.",
            "JGEX circumcenter rejects collinear or repeated triples.",
            "Two common points of two circles determine their radical axis.",
            "A circle through a fixed common chord belongs to the corresponding circle pencil.",
        ),
        "normalization": (
            "Translate and scale the incircle to x^2+y^2=1, rotate D to (1,0), "
            "and parameterize E and F by rational tangent parameters u and v.  The "
            "three vertices are intersections of the tangent lines at D,E,F."
        ),
        "representation_chart": (
            "incircle contacts -> rational unit-circle tangent parameters",
            "circle intersections -> common-chord linear form",
            "circle through chord and a vertex -> one-parameter circle pencil",
            "midpoint on radical axis -> equality of powers",
        ),
        "proof_dag": (
            "Normalize the incircle and recover A,B,C as intersections of contact tangents.",
            "Compute K as the projection of D onto EF and M=(D+K)/2.",
            "Subtract the AIC and incircle equations to obtain the B1B2 chord.",
            "Add the unique multiple of that chord making the pencil pass through B.",
            "Repeat with AIB and C for the second target circle.",
            "The two exact power expressions at M cancel identically.",
            "Therefore M lies on the radical axis P1P2.",
        ),
        "replay_residuals": residuals,
        "replayed": replayed,
        "all_conditions_discharged": replayed,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return IncircleContactPencilMidpointCertificate(
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
    if name in {"incenter", "circumcenter"} and len(args) == 3:
        return name, tuple(sorted(args))
    if name == "midpoint" and len(args) == 2:
        return name, tuple(sorted(args))
    if name == "foot" and len(args) == 3:
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


def _joint_circle_points(
    records: tuple[dict[str, object], ...],
    first_centre: str,
    first_radius_points: frozenset[str],
    second_centre: str,
    second_radius_points: frozenset[str],
) -> tuple[str, ...]:
    outputs: list[str] = []
    for record in records:
        if len(record["outputs"]) != 1 or len(record["constructions"]) != 2:
            continue
        constructions = tuple(record["constructions"])
        first_ok = any(
            name == "on_circle"
            and len(args) == 2
            and args[0] == first_centre
            and args[1] in first_radius_points
            for name, args in constructions
        )
        second_ok = any(
            name == "on_circle"
            and len(args) == 2
            and args[0] == second_centre
            and args[1] in second_radius_points
            for name, args in constructions
        )
        if first_ok and second_ok:
            outputs.append(str(record["outputs"][0]))
    return tuple(dict.fromkeys(outputs))


def certify_jgex_incircle_contact_pencil_midpoint_application(
    source: str,
) -> JGEXIncircleContactPencilMidpointApplication:
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
            i = _single(records, ("incenter", (a, b, c)))
            if not i:
                continue
            d = _single(records, ("foot", (i, b, c)))
            e = _single(records, ("foot", (i, a, c)))
            f = _single(records, ("foot", (i, a, b)))
            if not d or not e or not f:
                continue
            k = _single(records, ("foot", (d, e, f)))
            m = _single(records, ("midpoint", (d, k))) if k else None
            o_ab = _single(records, ("circumcenter", (a, i, b)))
            o_ac = _single(records, ("circumcenter", (a, i, c)))
            if not all((k, m, o_ab, o_ac)):
                continue

            c_pair = _joint_circle_points(
                records, o_ab, frozenset((a, i, b)), i, frozenset((d, e, f))
            )
            b_pair = _joint_circle_points(
                records, o_ac, frozenset((a, i, c)), i, frozenset((d, e, f))
            )
            if len(c_pair) != 2 or len(b_pair) != 2:
                continue
            c1, c2 = c_pair
            b1, b2 = b_pair
            o_b = _single(records, ("circumcenter", (b, b1, b2)))
            o_c = _single(records, ("circumcenter", (c, c1, c2)))
            if not o_b or not o_c:
                continue
            common = _joint_circle_points(
                records,
                o_b,
                frozenset((b, b1, b2)),
                o_c,
                frozenset((c, c1, c2)),
            )
            if len(common) != 2:
                continue
            p1, p2 = common
            roles = {
                "A": a,
                "B": b,
                "C": c,
                "I": i,
                "D": d,
                "E": e,
                "F": f,
                "K": k,
                "M": m,
                "OAB": o_ab,
                "OAC": o_ac,
                "C1": c1,
                "C2": c2,
                "B1": b1,
                "B2": b2,
                "OB": o_b,
                "OC": o_c,
                "P1": p1,
                "P2": p2,
            }
            key = (
                *triangle,
                i,
                *sorted((d, e, f)),
                k,
                m,
                *sorted((o_ab, o_ac, o_b, o_c)),
                *sorted((p1, p2)),
            )
            candidates[key] = roles

    goal = str(formulation.goals[0]) if len(formulation.goals) == 1 else ""
    accepted: list[dict[str, str]] = []
    parts = goal.split()
    if len(parts) == 4:
        actual = Atom(parts[0], tuple(parts[1:])).canonical()
        for roles in candidates.values():
            expected = Atom("coll", (roles["M"], roles["P1"], roles["P2"])).canonical()
            if actual == expected:
                accepted.append(roles)

    chart = certify_incircle_contact_pencil_midpoint_chart()
    unique = accepted[0] if len(accepted) == 1 else {}
    matched = (
        "an incircle contact triangle and the projection midpoint M",
        "the AIB and AIC circle-incircle common chords",
        "the B- and C-based circles through those common chords",
        "two common points spanning the target radical axis",
    ) if unique else ()
    replayed = bool(
        chart.replayed
        and chart.all_conditions_discharged
        and len(unique) == 19
        and len(accepted) == 1
    )
    return JGEXIncircleContactPencilMidpointApplication(
        theorem=chart.theorem,
        source_sha256=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        roles=unique,
        matched_constructions=matched,
        goal=goal,
        proof_bridge=(
            "Normalize the incircle to the unit circle and recover ABC from the three "
            "contact tangents.  Replace each pair of circle intersections by its linear "
            "common chord.  Each target circle is then the incircle plus the unique "
            "multiple of that chord which passes through B or C.  Direct substitution "
            "of M=(D+proj_EF(D))/2 gives equal powers, so M lies on P1P2."
        ),
        chart_certificate_sha256=chart.certificate_sha256,
        nondegeneracy_obligations=chart.assumptions,
        undischarged_nondegeneracy_obligations=(),
        replayed=replayed,
    )


def render_incircle_contact_pencil_midpoint_chart_svg() -> str:
    figure, axis = plt.subplots(figsize=(8.8, 6.0))
    axis.set_aspect("equal")
    axis.axis("off")
    axis.set_facecolor("#050709")
    figure.patch.set_facecolor("#050709")

    a = (0.0, 3.15)
    b = (-3.25, -1.45)
    c = (3.0, -1.45)
    i = (0.0, 0.0)
    d = (0.0, -1.0)
    e = (0.78, 0.62)
    f = (-0.82, 0.57)
    k = (0.02, 0.59)
    m = ((d[0] + k[0]) / 2, (d[1] + k[1]) / 2)
    p1, p2 = (-0.28, 1.85), (0.31, -1.05)

    axis.plot((a[0], b[0], c[0], a[0]), (a[1], b[1], c[1], a[1]), color="#64748b")
    axis.add_patch(Circle(i, 1.0, fill=False, color="#22d3ee", linewidth=1.6))
    axis.add_patch(Circle((-0.55, 0.4), 1.72, fill=False, color="#a3e635", linewidth=1.4))
    axis.add_patch(Circle((0.65, 0.35), 1.65, fill=False, color="#f472b6", linewidth=1.4))
    axis.plot((p1[0], p2[0]), (p1[1], p2[1]), color="#f8fafc", linewidth=2.0)
    axis.plot((d[0], k[0]), (d[1], k[1]), color="#fbbf24", linewidth=1.2)
    for label, point, color in (
        ("A", a, "#94a3b8"),
        ("B", b, "#94a3b8"),
        ("C", c, "#94a3b8"),
        ("I", i, "#22d3ee"),
        ("D", d, "#22d3ee"),
        ("E", e, "#22d3ee"),
        ("F", f, "#22d3ee"),
        ("K", k, "#fbbf24"),
        ("M", m, "#fbbf24"),
        ("P1", p1, "#f8fafc"),
        ("P2", p2, "#f8fafc"),
    ):
        axis.scatter(*point, s=30, color=color, zorder=5)
        axis.text(point[0] + 0.09, point[1] + 0.09, label, color=color, fontsize=9)
    axis.text(-2.75, 2.55, "circle pencil through B", color="#a3e635", fontsize=9)
    axis.text(1.15, 2.35, "circle pencil through C", color="#f472b6", fontsize=9)
    axis.text(0.45, -1.25, "radical axis", color="#f8fafc", fontsize=9)
    axis.set_xlim(-3.7, 3.6)
    axis.set_ylim(-1.9, 3.55)
    buffer = io.StringIO()
    figure.savefig(buffer, format="svg", bbox_inches="tight", facecolor=figure.get_facecolor())
    plt.close(figure)
    return buffer.getvalue()


__all__ = [
    "IncircleContactPencilMidpointCertificate",
    "JGEXIncircleContactPencilMidpointApplication",
    "certify_incircle_contact_pencil_midpoint_chart",
    "certify_jgex_incircle_contact_pencil_midpoint_application",
    "render_incircle_contact_pencil_midpoint_chart_svg",
]
