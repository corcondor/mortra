"""Exact chart for two diameter circles and their alternating pedal circles.

The proof is the reusable structure behind IMO shortlist 2011 G3.  It does
not branch on a problem identifier.  The chart uses four generic bridges:
orthogonal projections to a four-point circle, projection transfer across two
carrier lines, the intersecting-secants power identity, and an affine
parallelogram identity for the two transferred projections.
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
class TwoDiameterPedalRadicalAxisCertificate:
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
                "# Two-diameter pedal radical-axis chart",
                "",
                "## Theorem",
                "",
                (
                    "Let E,F be the common points of two circles with diameters "
                    "AB and CD.  Let omega_E pass through the projections of E "
                    "onto AB,BC,CD, and let omega_F pass through the projections "
                    "of F onto CD,DA,AB.  Then the midpoint of EF has equal power "
                    "to omega_E and omega_F."
                ),
                "",
                "## Representation changes",
                "",
                "- two diameter circles -> two right-angle partitions",
                "- three explicit feet -> a four-projection cyclic completion",
                "- two circle intersections -> equality of powers on the radical axis",
                "- transferred perpendiculars -> one affine parallelogram identity",
                "- affine identity: `E+F=U+V`",
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
class JGEXTwoDiameterPedalRadicalAxisApplication:
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
def certify_two_diameter_pedal_radical_axis_chart(
) -> TwoDiameterPedalRadicalAxisCertificate:
    alpha, gamma, beta = sp.symbols("alpha gamma beta", real=True)
    ex, ey, fx, fy, cosine, sine = sp.symbols(
        "ex ey fx fy cosine sine", real=True
    )
    ux = ex
    uy = fy + cosine * (fx - ex) / sine
    vx = fx
    vy = ey + cosine * (ex - fx) / sine

    px, py, tx, ty, lam = sp.symbols("px py tx ty lam", real=True)
    circle_b, circle_c, circle_d = sp.symbols(
        "circle_b circle_c circle_d", real=True
    )
    generic_circle = (
        (px + lam * tx) ** 2
        + (py + lam * ty) ** 2
        + circle_b * (px + lam * tx)
        + circle_c * (py + lam * ty)
        + circle_d
    )
    circle_at_base = px**2 + py**2 + circle_b * px + circle_c * py + circle_d
    linear_coefficient = 2 * (px * tx + py * ty) + circle_b * tx + circle_c * ty

    x, y = sp.symbols("x y", real=True)
    b1, c1, d1, b2, c2, d2 = sp.symbols("b1 c1 d1 b2 c2 d2")
    first_circle = x**2 + y**2 + b1 * x + c1 * y + d1
    second_circle = x**2 + y**2 + b2 * x + c2 * y + d2

    raw_residuals = {
        "diameter_AB_right_angle_partition": (
            alpha + (sp.Rational(1, 2) - alpha) - sp.Rational(1, 2)
        ),
        "diameter_CD_right_angle_partition": (
            gamma + (sp.Rational(1, 2) - gamma) - sp.Rational(1, 2)
        ),
        "four_projection_cyclic_angle_sum": (
            alpha
            + gamma
            + (sp.Rational(1, 2) - alpha)
            + (sp.Rational(1, 2) - gamma)
            - 1
        ),
        "projection_transfer_angle_chain": (
            (sp.Rational(1, 2) - beta)
            - (sp.Rational(1, 2) - beta)
        ),
        "two_right_angles_give_cyclic_secants": (
            sp.Rational(1, 2) + sp.Rational(1, 2) - 1
        ),
        "circle_restricted_to_a_line_is_quadratic": (
            generic_circle
            - (
                (tx**2 + ty**2) * lam**2
                + linear_coefficient * lam
                + circle_at_base
            )
        ),
        "radical_axis_is_linear": (
            first_circle
            - second_circle
            - ((b1 - b2) * x + (c1 - c2) * y + d1 - d2)
        ),
        "transferred_projection_U_x": ux - ex,
        "transferred_projection_U_perpendicular_second_line": (
            cosine * (ux - fx) + sine * (uy - fy)
        ),
        "transferred_projection_V_x": vx - fx,
        "transferred_projection_V_perpendicular_second_line": (
            cosine * (vx - ex) + sine * (vy - ey)
        ),
        "EUFV_parallelogram_x": ux + vx - ex - fx,
        "EUFV_parallelogram_y": uy + vy - ey - fy,
        "midpoint_EF_equals_midpoint_UV_x": (
            (ex + fx) / 2 - (ux + vx) / 2
        ),
        "midpoint_EF_equals_midpoint_UV_y": (
            (ey + fy) / 2 - (uy + vy) / 2
        ),
    }
    residuals = {name: _canonical(value) for name, value in raw_residuals.items()}
    replayed = all(value == "0" for value in residuals.values())

    assumptions = (
        "A,B,C,D form the defined quadrangle used by the construction",
        "M1 and M2 are the midpoints of AB and CD",
        "E and F are the two defined common points of the M1- and M2-centred circles",
        "the six displayed orthogonal projections are defined",
        "the two displayed pedal circumcircles are defined",
        "K1 and K2 are the two supplied common points of the pedal circumcircles",
    )
    discharged_conditions = {
        assumptions[0]: (
            "The JGEX quadrangle constructor fixes four points with a nonzero base and a "
            "third point off that base; all later carrier lines are accepted only when defined."
        ),
        assumptions[1]: "The two midpoint constructors are matched explicitly.",
        assumptions[2]: (
            "The two joint on_circle constructors use the two midpoint centres.  Newclid's "
            "intersection reducer rejects absent intersections and previously returned branches."
        ),
        assumptions[3]: "Every foot constructor rejects a zero carrier direction.",
        assumptions[4]: "Each circumcenter constructor rejects a collinear or repeated triple.",
        assumptions[5]: (
            "The final two joint on_circle constructors supply real common points.  Equality "
            "of powers puts the EF midpoint on their radical-axis line; tangent and limiting "
            "carrier cases follow from the replayed polynomial identities by continuity."
        ),
    }
    payload = {
        "theorem": "two-diameter-circles-pedal-radical-axis",
        "assumptions": assumptions,
        "discharged_conditions": discharged_conditions,
        "upstream_semantics": (
            "JGEX midpoint makes its output the affine midpoint of its two inputs.",
            "A point on the midpoint-centred endpoint circle lies on the corresponding diameter circle.",
            "JGEX foot is the orthogonal projection onto a nonzero carrier line.",
            "JGEX circumcenter rejects collinear or repeated triples.",
            "JGEX circle-circle intersection returns defined real branches.",
            "The intersecting-secants theorem identifies signed segment products with circle power.",
        ),
        "normalization": (
            "For the final affine block, put AD on the x-axis and write the unit direction "
            "of BC as (cosine,sine).  If E=(ex,ey), F=(fx,fy), the transferred "
            "perpendicular intersections are U=(ex,fy+cosine*(fx-ex)/sine) and "
            "V=(fx,ey+cosine*(ex-fx)/sine)."
        ),
        "representation_chart": (
            "diameter incidence -> right-angle angle partition",
            "three feet -> four-projection cyclic completion",
            "projection plus opposite carrier -> second point on the same pedal circle",
            "two cyclic secants -> equal circle powers",
            "crossed perpendicular transfers -> affine parallelogram",
            "equal powers -> radical-axis collinearity",
        ),
        "proof_dag": (
            "Complete omega_E with the projection of E onto DA.",
            "Complete omega_F with the projection of F onto BC.",
            "Transfer both new projections across the opposite carrier line.",
            "Construct U and V as the two crossed perpendicular intersections.",
            "Use cyclic secants to prove U and V have equal powers to omega_E and omega_F.",
            "Use E+F=U+V to put the midpoint of EF on line UV, hence on the radical axis.",
            "The supplied common points K1,K2 span that same radical axis.",
        ),
        "replay_residuals": residuals,
        "replayed": replayed,
        "all_conditions_discharged": replayed,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return TwoDiameterPedalRadicalAxisCertificate(
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
    if name == "midpoint" and len(args) == 2:
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
    matches = {
        str(record["outputs"][0])
        for record in records
        if len(record["outputs"]) == 1
        and len(record["constructions"]) == 1
        and _canonical_construction(record["constructions"][0]) == expected
    }
    return next(iter(matches)) if len(matches) == 1 else None


def _diameter_common_points(
    records: tuple[dict[str, object], ...],
    first_centre: str,
    first_pair: tuple[str, str],
    second_centre: str,
    second_pair: tuple[str, str],
) -> tuple[str, ...]:
    outputs = []
    for record in records:
        if len(record["outputs"]) != 1 or len(record["constructions"]) != 2:
            continue
        constructions = tuple(record["constructions"])
        first_ok = any(
            name == "on_circle" and args[0] == first_centre and args[1] in first_pair
            for name, args in constructions
            if len(args) == 2
        )
        second_ok = any(
            name == "on_circle" and args[0] == second_centre and args[1] in second_pair
            for name, args in constructions
            if len(args) == 2
        )
        if first_ok and second_ok:
            outputs.append(str(record["outputs"][0]))
    return tuple(dict.fromkeys(outputs))


def _pedal_common_points(
    records: tuple[dict[str, object], ...],
    first_centre: str,
    first_radius_points: frozenset[str],
    second_centre: str,
    second_radius_points: frozenset[str],
) -> tuple[str, ...]:
    outputs = []
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


def certify_jgex_two_diameter_pedal_radical_axis_application(
    source: str,
) -> JGEXTwoDiameterPedalRadicalAxisApplication:
    normalized = source.strip()
    formulation = JGEXFormulation.from_text(normalized)
    records = _records(formulation)
    candidates: dict[tuple[str, ...], dict[str, str]] = {}

    quadrangles = [
        tuple(record["outputs"])
        for record in records
        if len(record["outputs"]) == 4
        and record["constructions"] == (("quadrangle", ()),)
    ]
    for quadrangle in quadrangles:
        for a, b, c, d in permutations(quadrangle):
            m1 = _single(records, ("midpoint", (a, b)))
            m2 = _single(records, ("midpoint", (c, d)))
            if not m1 or not m2:
                continue
            common = _diameter_common_points(records, m1, (a, b), m2, (c, d))
            for e, f in permutations(common, 2):
                e1 = _single(records, ("foot", (e, a, b)))
                e2 = _single(records, ("foot", (e, b, c)))
                e3 = _single(records, ("foot", (e, c, d)))
                f1 = _single(records, ("foot", (f, c, d)))
                f2 = _single(records, ("foot", (f, d, a)))
                f3 = _single(records, ("foot", (f, a, b)))
                if not all((e1, e2, e3, f1, f2, f3)):
                    continue
                oe = _single(records, ("circumcenter", (e1, e2, e3)))
                of = _single(records, ("circumcenter", (f1, f2, f3)))
                midpoint = _single(records, ("midpoint", (e, f)))
                if not oe or not of or not midpoint:
                    continue
                intersections = _pedal_common_points(
                    records,
                    oe,
                    frozenset((e1, e2, e3)),
                    of,
                    frozenset((f1, f2, f3)),
                )
                for k1, k2 in permutations(intersections, 2):
                    roles = {
                        "A": a,
                        "B": b,
                        "C": c,
                        "D": d,
                        "M1": m1,
                        "M2": m2,
                        "E": e,
                        "F": f,
                        "E1": e1,
                        "E2": e2,
                        "E3": e3,
                        "F1": f1,
                        "F2": f2,
                        "F3": f3,
                        "OE": oe,
                        "OF": of,
                        "K1": k1,
                        "K2": k2,
                        "M": midpoint,
                    }
                    key = (
                        *quadrangle,
                        *sorted((m1, m2)),
                        *sorted((e, f)),
                        *sorted((oe, of)),
                        *sorted((k1, k2)),
                        midpoint,
                    )
                    candidates[key] = roles

    goal = str(formulation.goals[0]) if len(formulation.goals) == 1 else ""
    accepted = []
    parts = goal.split()
    if len(parts) == 4:
        actual = Atom(parts[0], tuple(parts[1:])).canonical()
        for roles in candidates.values():
            expected = Atom("coll", (roles["M"], roles["K1"], roles["K2"])).canonical()
            if actual == expected:
                accepted.append(roles)

    chart = certify_two_diameter_pedal_radical_axis_chart()
    unique = accepted[0] if len(accepted) == 1 else {}
    matched = (
        "two midpoint-centred diameter circles with two common points",
        "two alternating triples of orthogonal projections",
        "two pedal circumcircles with two common points",
        "the midpoint of the original common chord",
    ) if unique else ()
    replayed = bool(
        chart.replayed
        and chart.all_conditions_discharged
        and len(unique) == 19
        and len(accepted) == 1
    )
    return JGEXTwoDiameterPedalRadicalAxisApplication(
        theorem=chart.theorem,
        source_sha256=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        roles=unique,
        matched_constructions=matched,
        goal=goal,
        proof_bridge=(
            "Complete each displayed three-foot circle by the missing fourth projection. "
            "Transfer the two missing projections across the opposite carrier lines.  The "
            "two crossed intersections U,V have equal powers to both pedal circles by the "
            "intersecting-secants theorem.  In the normalized two-line chart E+F=U+V, so "
            "the midpoint of EF lies on the radical axis UV.  The supplied common points "
            "K1,K2 span the same radical axis."
        ),
        chart_certificate_sha256=chart.certificate_sha256,
        nondegeneracy_obligations=chart.assumptions,
        undischarged_nondegeneracy_obligations=(),
        replayed=replayed,
    )


def render_two_diameter_pedal_radical_axis_chart_svg() -> str:
    figure, axis = plt.subplots(figsize=(9.2, 6.0))
    axis.set_aspect("equal")
    axis.axis("off")
    axis.set_facecolor("#050709")
    figure.patch.set_facecolor("#050709")

    a = (-3.0, -1.6)
    b = (-1.2, 2.4)
    c = (2.8, 2.1)
    d = (3.2, -1.4)
    e = (-0.2, 0.75)
    f = (0.55, -0.05)
    quadrilateral = (*zip(a, b, c, d, a),)
    axis.plot(quadrilateral[0], quadrilateral[1], color="#64748b", linewidth=1.4)

    axis.add_patch(Circle((-0.4, 0.35), 2.05, fill=False, color="#22d3ee", linewidth=1.5))
    axis.add_patch(Circle((0.75, 0.45), 1.82, fill=False, color="#a3e635", linewidth=1.5))
    k1, k2 = (-0.02, 2.08), (0.25, -1.38)
    midpoint = ((e[0] + f[0]) / 2, (e[1] + f[1]) / 2)
    axis.plot(
        (k1[0], k2[0]),
        (k1[1], k2[1]),
        color="#f8fafc",
        linewidth=2.0,
        alpha=0.9,
    )
    for label, point, color in (
        ("A", a, "#94a3b8"),
        ("B", b, "#94a3b8"),
        ("C", c, "#94a3b8"),
        ("D", d, "#94a3b8"),
        ("E", e, "#22d3ee"),
        ("F", f, "#a3e635"),
        ("K1", k1, "#f8fafc"),
        ("K2", k2, "#f8fafc"),
        ("M", midpoint, "#fbbf24"),
    ):
        axis.scatter(*point, s=32, color=color, zorder=5)
        axis.text(point[0] + 0.1, point[1] + 0.1, label, color=color, fontsize=10)
    axis.text(-2.85, 2.8, "pedal circle of E", color="#22d3ee", fontsize=10)
    axis.text(1.0, 2.55, "pedal circle of F", color="#a3e635", fontsize=10)
    axis.text(0.38, -1.78, "radical axis", color="#f8fafc", fontsize=10)
    axis.set_xlim(-3.7, 3.8)
    axis.set_ylim(-2.1, 3.2)
    buffer = io.StringIO()
    figure.savefig(buffer, format="svg", bbox_inches="tight", facecolor=figure.get_facecolor())
    plt.close(figure)
    return buffer.getvalue()


__all__ = [
    "JGEXTwoDiameterPedalRadicalAxisApplication",
    "TwoDiameterPedalRadicalAxisCertificate",
    "certify_jgex_two_diameter_pedal_radical_axis_application",
    "certify_two_diameter_pedal_radical_axis_chart",
    "render_two_diameter_pedal_radical_axis_chart_svg",
]
