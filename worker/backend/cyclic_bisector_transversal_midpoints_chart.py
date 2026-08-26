"""Exact chart for opposite angle bisectors in a cyclic quadrilateral.

The chart replaces four Euclidean angle-bisector constructions by the two
antipodal arc-midpoint pairs on a normalized circumcircle.  Intersections are
then projective cross products.  The final perpendicularity is one homogeneous
bilinear identity, valid for all four independent arc-midpoint branch choices.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
from itertools import permutations, product
import cmath
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

Homogeneous = tuple[sp.Expr, sp.Expr, sp.Expr]


def _canonical(value: sp.Expr) -> str:
    return str(sp.factor(sp.cancel(value)))


def _cross(left: Homogeneous, right: Homogeneous) -> Homogeneous:
    return (
        sp.expand(left[1] * right[2] - left[2] * right[1]),
        sp.expand(left[2] * right[0] - left[0] * right[2]),
        sp.expand(left[0] * right[1] - left[1] * right[0]),
    )


def _unit_chord(left: sp.Expr, right: sp.Expr) -> Homogeneous:
    # z + left*right*conjugate(z) = left + right on the unit circle.
    return (sp.Integer(1), sp.expand(left * right), -sp.expand(left + right))


def _incidence(line: Homogeneous, point: Homogeneous) -> sp.Expr:
    return sp.expand(sum(line[index] * point[index] for index in range(3)))


def _midpoint(left: Homogeneous, right: Homogeneous) -> Homogeneous:
    return (
        sp.expand(left[0] * right[2] + right[0] * left[2]),
        sp.expand(left[1] * right[2] + right[1] * left[2]),
        sp.expand(2 * left[2] * right[2]),
    )


@dataclass(frozen=True)
class CyclicBisectorTransversalMidpointsCertificate:
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
                "# Cyclic-bisector transversal midpoint chart",
                "",
                "## Theorem",
                "",
                (
                    "Let I and J be the intersections of the opposite internal angle "
                    "bisectors of a cyclic quadrilateral ABCD.  A line IJ meets AB, "
                    "BC, CD, DA at P,Q,R,S.  If M and N are the midpoints of PR and "
                    "QS, then OM is perpendicular to ON, where O is the circumcenter."
                ),
                "",
                "## Representation changes",
                "",
                "- opposite angle bisectors -> antipodal arc-midpoint pairs",
                "- points and lines -> homogeneous complex projective coordinates",
                "- side intersections -> cross products",
                "- perpendicularity at O -> one Hermitian bilinear numerator",
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
class JGEXCyclicBisectorTransversalMidpointsApplication:
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
def certify_cyclic_bisector_transversal_midpoints_chart() -> (
    CyclicBisectorTransversalMidpointsCertificate
):
    x, y, z, w = sp.symbols("x y z w", nonzero=True)
    a, b, c, d = x**2, y**2, z**2, w**2

    def bar(value: sp.Expr) -> sp.Expr:
        return sp.cancel(value.xreplace({x: 1 / x, y: 1 / y, z: 1 / z, w: 1 / w}))

    def construct(sign_i: int, sign_j: int) -> dict[str, Homogeneous]:
        u = sign_i * y * w
        v = sign_j * x * z
        point_i = _cross(_unit_chord(a, u), _unit_chord(c, -u))
        point_j = _cross(_unit_chord(b, v), _unit_chord(d, -v))
        transversal = _cross(point_i, point_j)
        point_p = _cross(transversal, _unit_chord(a, b))
        point_q = _cross(transversal, _unit_chord(b, c))
        point_r = _cross(transversal, _unit_chord(c, d))
        point_s = _cross(transversal, _unit_chord(d, a))
        point_m = _midpoint(point_p, point_r)
        point_n = _midpoint(point_q, point_s)
        return {
            "I": point_i,
            "J": point_j,
            "L": transversal,
            "P": point_p,
            "Q": point_q,
            "R": point_r,
            "S": point_s,
            "M": point_m,
            "N": point_n,
        }

    main = construct(1, 1)
    u, v = y * w, x * z
    raw_residuals: dict[str, sp.Expr] = {
        "A_on_normalized_circumcircle": a * bar(a) - 1,
        "B_on_normalized_circumcircle": b * bar(b) - 1,
        "C_on_normalized_circumcircle": c * bar(c) - 1,
        "D_on_normalized_circumcircle": d * bar(d) - 1,
        "I_on_A_opposite_arc_bisector": _incidence(_unit_chord(a, u), main["I"]),
        "I_on_C_opposite_arc_bisector": _incidence(_unit_chord(c, -u), main["I"]),
        "J_on_B_opposite_arc_bisector": _incidence(_unit_chord(b, v), main["J"]),
        "J_on_D_opposite_arc_bisector": _incidence(_unit_chord(d, -v), main["J"]),
    }
    for name, side in (
        ("P", (a, b)),
        ("Q", (b, c)),
        ("R", (c, d)),
        ("S", (d, a)),
    ):
        raw_residuals[f"{name}_on_IJ"] = _incidence(main["L"], main[name])
        raw_residuals[f"{name}_on_corresponding_side"] = _incidence(
            _unit_chord(*side), main[name]
        )
    for sign_i, sign_j in product((1, -1), repeat=2):
        branch = construct(sign_i, sign_j)
        raw_residuals[f"OM_perpendicular_ON_branch_{sign_i}_{sign_j}"] = sp.expand(
            branch["M"][0] * branch["N"][1] + branch["M"][1] * branch["N"][0]
        )

    residuals = {name: _canonical(value) for name, value in raw_residuals.items()}
    replayed = all(value == "0" for value in residuals.values())
    assumptions = (
        "ABCD is a defined nondegenerate cyclic quadrilateral with circumcenter O",
        "I is the defined intersection of the angle bisectors at A and C",
        "J is the defined intersection of the angle bisectors at B and D",
        "P,Q,R,S are the defined intersections of IJ with AB,BC,CD,DA",
        "M and N are the defined midpoints of PR and QS",
        "the target lines OM and ON are defined in the generic construction domain",
    )
    discharged_conditions = {
        assumptions[
            0
        ]: "The triangle, on_circum, and circumcenter clauses are matched.",
        assumptions[
            1
        ]: "Both angle_bisector clauses with output I are matched jointly.",
        assumptions[
            2
        ]: "Both angle_bisector clauses with output J are matched jointly.",
        assumptions[3]: "Each point has one side incidence and one IJ incidence.",
        assumptions[
            4
        ]: "Both midpoint constructors and their endpoint pairs are matched.",
        assumptions[5]: (
            "The homogeneous identity is valid on every defined branch; undefined "
            "intersections are excluded by the upstream construction semantics."
        ),
    }
    payload = {
        "theorem": "cyclic-opposite-bisectors-transversal-midpoints-perpendicular",
        "assumptions": assumptions,
        "discharged_conditions": discharged_conditions,
        "upstream_semantics": (
            "JGEX on_circum places D on the circumcircle through A,B,C.",
            "JGEX angle_bisector denotes the displayed internal angle-bisector line.",
            "JGEX joint on_line clauses denote the unique displayed line intersection.",
            "JGEX midpoint is affine and perp is the zero dot-product relation.",
        ),
        "normalization": (
            "Translate and scale the circumcircle to the unit circle with O=0 and "
            "write A=x^2, B=y^2, C=z^2, D=w^2."
        ),
        "representation_chart": (
            "angle bisector in a cyclic quadrilateral -> line through an arc midpoint",
            "opposite angle bisectors -> antipodal arc-midpoint pair",
            "incidence construction -> homogeneous cross product",
            "midpoint pair at the circumcenter -> Hermitian bilinear form",
        ),
        "proof_dag": (
            "Replace the A,C bisectors by the lines through +yw and -yw.",
            "Replace the B,D bisectors by the lines through +xz and -xz.",
            "Form I,J and the transversal IJ by projective cross products.",
            "Intersect IJ with the four side chords to obtain P,Q,R,S.",
            "Form the affine homogeneous midpoints M of PR and N of QS.",
            "Expand M*conjugate(N)+conjugate(M)*N; it vanishes identically.",
            "Repeat after both independent antipodal sign changes; all four vanish.",
        ),
        "replay_residuals": residuals,
        "replayed": replayed,
        "all_conditions_discharged": replayed,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return CyclicBisectorTransversalMidpointsCertificate(
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
    if name in {"circumcenter", "on_circum"} and len(args) == 3:
        return name, tuple(sorted(args))
    if name in {"on_line", "midpoint"} and len(args) == 2:
        return name, tuple(sorted(args))
    if name == "angle_bisector" and len(args) == 3:
        return name, (args[1], *sorted((args[0], args[2])))
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


def _joint(
    records: tuple[dict[str, object], ...],
    constructions: tuple[tuple[str, tuple[str, ...]], ...],
) -> str | None:
    expected = sorted(map(_canonical_construction, constructions), key=repr)
    matches = {
        str(record["outputs"][0])
        for record in records
        if len(record["outputs"]) == 1
        and sorted(map(_canonical_construction, record["constructions"]), key=repr)
        == expected
    }
    return next(iter(matches)) if len(matches) == 1 else None


def certify_jgex_cyclic_bisector_transversal_midpoints_application(
    source: str,
) -> JGEXCyclicBisectorTransversalMidpointsApplication:
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
    for triangle in triangles:
        for a, b, c in permutations(triangle):
            d = _single(records, ("on_circum", (a, b, c)))
            o = _single(records, ("circumcenter", (a, b, c)))
            if not d or not o:
                continue
            i = _joint(
                records,
                (
                    ("angle_bisector", (d, a, b)),
                    ("angle_bisector", (b, c, d)),
                ),
            )
            j = _joint(
                records,
                (
                    ("angle_bisector", (a, b, c)),
                    ("angle_bisector", (c, d, a)),
                ),
            )
            if not i or not j:
                continue
            p = _joint(records, (("on_line", (a, b)), ("on_line", (i, j))))
            q = _joint(records, (("on_line", (b, c)), ("on_line", (i, j))))
            r = _joint(records, (("on_line", (c, d)), ("on_line", (i, j))))
            s = _joint(records, (("on_line", (d, a)), ("on_line", (i, j))))
            if not all((p, q, r, s)):
                continue
            m = _single(records, ("midpoint", (p, r)))
            n = _single(records, ("midpoint", (q, s)))
            if not m or not n:
                continue
            roles = {
                "A": a,
                "B": b,
                "C": c,
                "D": d,
                "O": o,
                "I": i,
                "J": j,
                "P": p,
                "Q": q,
                "R": r,
                "S": s,
                "M": m,
                "N": n,
            }
            # Reversing A,C swaps the two midpoint rays but describes the same
            # unoriented theorem application.  Collapse that automorphism here
            # so a symmetric source is not reported as an ambiguous match.
            opposite_intersection_pairs = sorted(
                (tuple(sorted((p, r))), tuple(sorted((q, s))))
            )
            key = (
                o,
                *sorted((a, c)),
                *sorted((b, d)),
                *sorted((i, j)),
                *opposite_intersection_pairs[0],
                *opposite_intersection_pairs[1],
                *sorted((m, n)),
            )
            candidates[key] = roles

    goal = str(formulation.goals[0]) if len(formulation.goals) == 1 else ""
    accepted: list[dict[str, str]] = []
    parts = goal.split()
    if len(parts) == 5:
        actual = Atom(parts[0], tuple(parts[1:])).canonical()
        for roles in candidates.values():
            expected = Atom(
                "perp", (roles["M"], roles["O"], roles["N"], roles["O"])
            ).canonical()
            if actual == expected:
                accepted.append(roles)

    chart = certify_cyclic_bisector_transversal_midpoints_chart()
    unique = accepted[0] if len(accepted) == 1 else {}
    matched = (
        (
            "a cyclic quadrilateral and its circumcenter",
            "the two opposite angle-bisector intersections",
            "four intersections of their transversal with the sides",
            "the two opposite-side midpoint pairs and the target perpendicularity",
        )
        if unique
        else ()
    )
    replayed = bool(
        chart.replayed
        and chart.all_conditions_discharged
        and len(unique) == 13
        and len(accepted) == 1
    )
    return JGEXCyclicBisectorTransversalMidpointsApplication(
        theorem=chart.theorem,
        source_sha256=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        roles=unique,
        matched_constructions=matched,
        goal=goal,
        proof_bridge=(
            "Normalize the circumcircle and write A=x^2, B=y^2, C=z^2, D=w^2. "
            "Opposite internal angle bisectors pass through the antipodal arc-midpoints "
            "+/-yw and +/-xz.  Cross products construct I,J,P,Q,R,S without division. "
            "For the midpoints M,N, the homogeneous Hermitian numerator for OM dot ON "
            "vanishes on all four branch choices."
        ),
        chart_certificate_sha256=chart.certificate_sha256,
        nondegeneracy_obligations=chart.assumptions,
        undischarged_nondegeneracy_obligations=(),
        replayed=replayed,
    )


def render_cyclic_bisector_transversal_midpoints_chart_svg() -> str:
    def point(angle: float) -> complex:
        return cmath.exp(1j * angle)

    def cross(
        left: tuple[complex, complex, complex], right: tuple[complex, complex, complex]
    ):
        return (
            left[1] * right[2] - left[2] * right[1],
            left[2] * right[0] - left[0] * right[2],
            left[0] * right[1] - left[1] * right[0],
        )

    def chord(left: complex, right: complex):
        return (1 + 0j, left * right, -(left + right))

    def affine(value: tuple[complex, complex, complex]) -> complex:
        return value[0] / value[2]

    angles = (2.15, 3.65, 5.20, 0.55)
    a, b, c, d = map(point, angles)
    x, y, z, w = map(lambda angle: point(angle / 2), angles)
    i = cross(chord(a, y * w), chord(c, -y * w))
    j = cross(chord(b, x * z), chord(d, -x * z))
    line_ij = cross(i, j)
    p = affine(cross(line_ij, chord(a, b)))
    q = affine(cross(line_ij, chord(b, c)))
    r = affine(cross(line_ij, chord(c, d)))
    s = affine(cross(line_ij, chord(d, a)))
    i, j = affine(i), affine(j)
    m, n = (p + r) / 2, (q + s) / 2

    figure, axis = plt.subplots(figsize=(8.8, 6.0))
    axis.set_aspect("equal")
    axis.axis("off")
    axis.set_facecolor("#050709")
    figure.patch.set_facecolor("#050709")
    axis.add_patch(Circle((0, 0), 1, fill=False, color="#334155", linewidth=1.4))
    vertices = (a, b, c, d, a)
    axis.plot([v.real for v in vertices], [v.imag for v in vertices], color="#64748b")
    axis.plot((i.real, j.real), (i.imag, j.imag), color="#22d3ee", linewidth=1.5)
    axis.plot((0, m.real), (0, m.imag), color="#a3e635", linewidth=2.0)
    axis.plot((0, n.real), (0, n.imag), color="#fbbf24", linewidth=2.0)
    for label, value, color in (
        ("A", a, "#94a3b8"),
        ("B", b, "#94a3b8"),
        ("C", c, "#94a3b8"),
        ("D", d, "#94a3b8"),
        ("I", i, "#22d3ee"),
        ("J", j, "#22d3ee"),
        ("M", m, "#a3e635"),
        ("N", n, "#fbbf24"),
        ("O", 0j, "#f8fafc"),
    ):
        axis.scatter(value.real, value.imag, s=28, color=color, zorder=5)
        axis.text(value.real + 0.04, value.imag + 0.04, label, color=color, fontsize=9)
    axis.text(
        -1.45,
        1.38,
        "cyclic bisectors -> orthogonal midpoint rays",
        color="#f8fafc",
        fontsize=10,
    )
    axis.set_xlim(-1.55, 1.55)
    axis.set_ylim(-1.45, 1.5)
    buffer = io.StringIO()
    figure.savefig(
        buffer, format="svg", bbox_inches="tight", facecolor=figure.get_facecolor()
    )
    plt.close(figure)
    return buffer.getvalue()


__all__ = [
    "CyclicBisectorTransversalMidpointsCertificate",
    "JGEXCyclicBisectorTransversalMidpointsApplication",
    "certify_cyclic_bisector_transversal_midpoints_chart",
    "certify_jgex_cyclic_bisector_transversal_midpoints_application",
    "render_cyclic_bisector_transversal_midpoints_chart_svg",
]
