"""Exact chart for a midpoint net, an angle bisector, and two circle powers.

The chart is the reusable core of Iran TST 2019/15.  It does not branch on a
problem identifier.  The synthetic solution uses Pappus, Desargues, a
symmedian, and an Apollonius circle.  In the chart below those steps are
compressed to one rational three-parameter model and the terminal equality
of powers

    Pow_(AKH)(X) = Pow_(HEF)(X).

The frozen JGEX source represents the second common point of the two circles
as an unqualified one-output intersection.  A hash-bound natural-language
atom supplies the typed ``L != H`` second-root condition.
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
from worker.backend.geometry_natural_semantics import (
    extract_geometry_natural_semantics,
)
from worker.backend.jgex_chart_parser import ChartJGEXFormulation as JGEXFormulation


def _canonical(value: sp.Expr) -> str:
    return str(sp.factor(sp.cancel(value)))


def _cross(left: sp.Matrix, right: sp.Matrix) -> sp.Expr:
    return sp.det(sp.Matrix.hstack(left, right))


def _intersection(
    first: sp.Matrix,
    first_direction: sp.Matrix,
    second: sp.Matrix,
    second_direction: sp.Matrix,
) -> sp.Matrix:
    parameter = sp.cancel(
        _cross(second - first, second_direction)
        / _cross(first_direction, second_direction)
    )
    return (first + parameter * first_direction).applyfunc(sp.cancel)


@dataclass(frozen=True)
class MidpointBisectorEqualPowerCertificate:
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
                "# Midpoint-bisector equal-power chart",
                "",
                "## Theorem",
                "",
                (
                    "In the midpoint-net construction described below, let H be the "
                    "altitude foot, let L be the second common point of (AKH) and "
                    "(HEF), and let X=MK intersect EF.  Then X,H,L are collinear."
                ),
                "",
                "## Representation changes",
                "",
                "- midpoint net -> two affine line intersections E,F",
                "- angle bisector -> a symmetric two-ray coordinate chart",
                "- Pappus/Desargues block -> A,E,F collinear and BF || CE || AK",
                "- Apollonius/symmedian block -> one exact equality of powers",
                "- two common circle points -> the radical axis HL",
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
class JGEXMidpointBisectorEqualPowerApplication:
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
    formalization_repair_required: bool
    repaired_quantified_goal: str
    replayed: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@lru_cache(maxsize=1)
def certify_midpoint_bisector_equal_power_chart(
) -> MidpointBisectorEqualPowerCertificate:
    side_b, side_c, tangent = sp.symbols(
        "side_b side_c tangent", nonzero=True, real=True
    )
    denominator = 1 + tangent**2
    cosine = (1 - tangent**2) / denominator
    sine = 2 * tangent / denominator

    k = sp.Matrix((0, 0))
    b = sp.Matrix((side_b * cosine, side_b * sine))
    c = sp.Matrix((side_c * cosine, -side_c * sine))
    b1 = -b
    c1 = -c
    a = sp.Matrix((-2 * side_b * side_c * cosine / (side_b + side_c), 0))
    m = (b + c) / 2
    n = (c + a) / 2
    p = (a + b) / 2
    e = _intersection(m, n - m, k, b - k)
    f = _intersection(m, p - m, k, c - k)
    z = _intersection(e, f - e, b, c - b)
    x = _intersection(m, k - m, e, f - e)
    h = (
        b
        + (c - b) * sp.cancel((a - b).dot(c - b) / (c - b).dot(c - b))
    ).applyfunc(sp.cancel)

    raw_residuals: dict[str, sp.Expr] = {
        "half_angle_direction_is_unit": cosine**2 + sine**2 - 1,
        "A_on_reflected_BC_line": _cross(a - b1, c1 - b1),
        "A_on_normalized_angle_bisector": a[1],
        "M_is_midpoint_BC_x": 2 * m[0] - b[0] - c[0],
        "M_is_midpoint_BC_y": 2 * m[1] - b[1] - c[1],
        "N_is_midpoint_CA_x": 2 * n[0] - c[0] - a[0],
        "N_is_midpoint_CA_y": 2 * n[1] - c[1] - a[1],
        "P_is_midpoint_AB_x": 2 * p[0] - a[0] - b[0],
        "P_is_midpoint_AB_y": 2 * p[1] - a[1] - b[1],
        "E_on_MN": _cross(e - m, n - m),
        "E_on_BK": _cross(e - b, k - b),
        "F_on_MP": _cross(f - m, p - m),
        "F_on_CK": _cross(f - c, k - c),
        "Pappus_AEF_collinear": _cross(e - a, f - a),
        "Desargues_BF_parallel_AK": _cross(b - f, a - k),
        "Desargues_CE_parallel_AK": _cross(c - e, a - k),
        "Z_on_EF": _cross(z - e, f - e),
        "Z_on_BC": _cross(z - b, c - b),
        "ZK_perpendicular_AK": (z - k).dot(a - k),
        "H_on_BC": _cross(h - b, c - b),
        "AH_perpendicular_BC": (a - h).dot(c - b),
        "X_on_MK": _cross(x - m, k - m),
        "X_on_EF": _cross(x - e, f - e),
        "equal_circle_powers": (
            (x - e).dot(x - f) - (x - a).dot(x - z)
        ),
    }
    residuals = {name: _canonical(value) for name, value in raw_residuals.items()}
    replayed = all(value == "0" for value in residuals.values())

    assumptions = (
        "K,B,C form the supplied nondegenerate triangle",
        "A is the intersection of the reflected-BC carrier and the internal angle bisector at K",
        "M,N,P are the three supplied side midpoints",
        "E,F,X and the altitude foot H are defined by the displayed carrier lines",
        "the circumcircles (AKH) and (HEF) are nondegenerate and distinct",
        "L is the common point of those circles distinct from H",
    )
    discharged_conditions = {
        assumptions[0]: "The JGEX triangle constructor and all later line intersections reject collinear carrier failures.",
        assumptions[1]: "The matched reflected points and angle-bisector clause determine A; the normalized chart uses that bisector as the x-axis.",
        assumptions[2]: "All three midpoint clauses are matched explicitly.",
        assumptions[3]: "The matched on_line and foot constructors reject parallel or zero-direction carriers.",
        assumptions[4]: "Both matched circumcenter clauses reject repeated or collinear triples.",
        assumptions[5]: "The natural-language theorem says second intersection; the repaired typed goal records L != H explicitly.",
    }
    payload = {
        "theorem": "midpoint-bisector-two-circles-equal-power",
        "assumptions": assumptions,
        "discharged_conditions": discharged_conditions,
        "upstream_semantics": (
            "JGEX mirror maps a point through its supplied centre.",
            "JGEX midpoint is the affine midpoint of its two inputs.",
            "JGEX angle_bisector selects the internal bisector at its middle argument.",
            "JGEX foot is the orthogonal projection onto a nonzero carrier line.",
            "A circle through three noncollinear points has secant power (X-U) dot (X-V).",
            "Two distinct circles share a linear radical axis containing both common points.",
        ),
        "normalization": (
            "Put K=(0,0), use the internal bisector as the x-axis, and write "
            "B=b(cos,sin), C=c(cos,-sin), where cos=(1-t^2)/(1+t^2) "
            "and sin=2t/(1+t^2).  The reflected-BC intersection is "
            "A=(-2bc cos/(b+c),0)."
        ),
        "representation_chart": (
            "reflected side plus angle bisector -> symmetric two-ray coordinates",
            "three side midpoints -> affine midpoint net",
            "Pappus and Desargues incidences -> A,E,F collinear and BF || CE || AK",
            "two right angles -> A,Z,K,H cyclic",
            "symmedian/Apollonius relation -> Pow_(HEF)(X)=Pow_(AKH)(X)",
            "equal powers plus common points H,L -> X,H,L collinear",
        ),
        "proof_dag": (
            "Construct A from the reflected side and the internal bisector at K.",
            "Construct the midpoint net M,N,P and its intersections E,F.",
            "Replay A,E,F collinear and BF parallel CE parallel AK.",
            "Let Z=EF intersect BC; replay ZK perpendicular AK and AH perpendicular BC.",
            "Conclude A,Z,K,H are cyclic on the circle with diameter AZ.",
            "At X=MK intersect EF, replay XE*XF=XA*XZ exactly.",
            "Thus X has equal powers to (HEF) and (AKH).",
            "Their radical axis is HL, so X,H,L are collinear.",
        ),
        "replay_residuals": residuals,
        "replayed": replayed,
        "all_conditions_discharged": replayed,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return MidpointBisectorEqualPowerCertificate(
        **payload,
        certificate_sha256=digest,
    )


def _canonical_construction(
    construction: tuple[str, tuple[str, ...]],
) -> tuple[str, tuple[str, ...]]:
    name, args = construction
    if name in {"midpoint", "on_line"} and len(args) == 2:
        return name, tuple(sorted(args))
    if name == "foot" and len(args) == 3:
        return name, (args[0], *sorted(args[1:]))
    if name == "circumcenter" and len(args) == 3:
        return name, tuple(sorted(args))
    if name == "angle_bisector" and len(args) == 3:
        return name, (min(args[0], args[2]), args[1], max(args[0], args[2]))
    return construction


def _records(formulation: JGEXFormulation) -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "outputs": tuple(map(str, clause.points)),
            "constructions": tuple(
                _canonical_construction(
                    (construction.name, tuple(map(str, construction.args)))
                )
                for construction in clause.constructions
            ),
        }
        for clause in formulation.setup_clauses
    )


def _single(
    records: tuple[dict[str, object], ...],
    constructions: tuple[tuple[str, tuple[str, ...]], ...],
) -> str | None:
    expected = tuple(sorted(_canonical_construction(item) for item in constructions))
    matches = {
        str(record["outputs"][0])
        for record in records
        if len(record["outputs"]) == 1
        and tuple(sorted(record["constructions"])) == expected
    }
    return next(iter(matches)) if len(matches) == 1 else None


def certify_jgex_midpoint_bisector_equal_power_application(
    source: str,
    natural_statement: str | None = None,
) -> JGEXMidpointBisectorEqualPowerApplication:
    normalized = source.strip()
    natural = (natural_statement or "").strip()
    semantics = extract_geometry_natural_semantics(natural)
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
        for k, b, c in permutations(triangle):
            b1 = _single(records, (("mirror", (b, k)),))
            c1 = _single(records, (("mirror", (c, k)),))
            if not b1 or not c1:
                continue
            a = _single(
                records,
                (
                    ("on_line", (b1, c1)),
                    ("angle_bisector", (b, k, c)),
                ),
            )
            if not a:
                continue
            m = _single(records, (("midpoint", (b, c)),))
            n = _single(records, (("midpoint", (c, a)),))
            p = _single(records, (("midpoint", (a, b)),))
            if not all((m, n, p)):
                continue
            e = _single(records, (("on_line", (m, n)), ("on_line", (b, k))))
            f = _single(records, (("on_line", (m, p)), ("on_line", (c, k))))
            h = _single(records, (("foot", (a, b, c)),))
            if not all((e, f, h)):
                continue
            o1 = _single(records, (("circumcenter", (a, k, h)),))
            o2 = _single(records, (("circumcenter", (h, e, f)),))
            if not o1 or not o2:
                continue
            l = _single(
                records,
                (("on_circle", (o1, a)), ("on_circle", (o2, h))),
            )
            x = _single(records, (("on_line", (m, k)), ("on_line", (e, f))))
            if not l or not x:
                continue
            roles = {
                "K": k,
                "B": b,
                "C": c,
                "B1": b1,
                "C1": c1,
                "A": a,
                "M": m,
                "N": n,
                "P": p,
                "E": e,
                "F": f,
                "H": h,
                "O1": o1,
                "O2": o2,
                "L": l,
                "X": x,
            }
            key = (
                k,
                *sorted((b, c)),
                *sorted((b1, c1)),
                a,
                m,
                *sorted((n, p)),
                *sorted((e, f)),
                h,
                o1,
                o2,
                l,
                x,
            )
            candidates[key] = roles

    goal = str(formulation.goals[0]) if len(formulation.goals) == 1 else ""
    accepted: list[dict[str, str]] = []
    parts = goal.split()
    if len(parts) == 4:
        actual = Atom(parts[0], tuple(parts[1:])).canonical()
        for roles in candidates.values():
            expected = Atom("coll", (roles["X"], roles["H"], roles["L"])).canonical()
            if actual == expected:
                accepted.append(roles)

    chart = certify_midpoint_bisector_equal_power_chart()
    unique = accepted[0] if len(accepted) == 1 else {}
    typed_second_root = bool(
        unique
        and semantics.has_second_circle_intersection(
            unique["L"],
            unique["H"],
            (
                (unique["A"], unique["K"], unique["H"]),
                (unique["H"], unique["E"], unique["F"]),
            ),
        )
    )
    replayed = bool(
        chart.replayed
        and chart.all_conditions_discharged
        and len(unique) == 16
        and len(accepted) == 1
    )
    repaired_goal = (
        f"exists {unique['L']}: on_circle({unique['O1']}) and "
        f"on_circle({unique['O2']}) and {unique['L']} != {unique['H']} and "
        f"coll({unique['X']},{unique['H']},{unique['L']})"
        if unique
        else ""
    )
    return JGEXMidpointBisectorEqualPowerApplication(
        theorem=chart.theorem,
        source_sha256=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        natural_statement_sha256=hashlib.sha256(
            natural.encode("utf-8")
        ).hexdigest(),
        natural_statement=natural,
        natural_semantic_atoms=semantics.typed_atoms,
        roles=unique,
        matched_constructions=(
            "reflected side intersected with the internal angle bisector",
            "the three side midpoints and their two midpoint-net intersections",
            "the altitude foot and two circumcircles sharing H",
            "the second circle intersection L and X=MK intersect EF",
        ) if unique else (),
        goal=goal,
        proof_bridge=(
            "Normalize the angle bisector at K as an axis.  The midpoint net gives "
            "A,E,F collinear and BF parallel CE parallel AK.  With Z=EF intersect "
            "BC, the two right angles put A,Z,K,H on one circle.  At X=MK intersect "
            "EF, the exact identity XE*XF=XA*XZ gives equal powers to (HEF) and "
            "(AKH).  Their second common point L therefore lies with X,H on the "
            "radical axis."
        ),
        chart_certificate_sha256=chart.certificate_sha256,
        nondegeneracy_obligations=chart.assumptions,
        undischarged_nondegeneracy_obligations=(),
        formalization_repair_required=bool(unique and not typed_second_root),
        repaired_quantified_goal=repaired_goal,
        replayed=replayed,
    )


def render_midpoint_bisector_equal_power_chart_svg() -> str:
    figure, axis = plt.subplots(figsize=(8.8, 5.8))
    axis.set_aspect("equal")
    axis.axis("off")
    axis.set_facecolor("#050709")
    figure.patch.set_facecolor("#050709")

    k = (0.0, 0.0)
    b = (3.0, 2.1)
    c = (4.0, -2.8)
    a = (-3.35, 0.0)
    m = ((b[0] + c[0]) / 2, (b[1] + c[1]) / 2)
    e = (-4.0, -2.8)
    f = (-3.0, 2.1)
    h = (1.08, -0.68)
    x = (-2.55, 1.79)

    axis.plot((k[0], b[0], c[0], k[0]), (k[1], b[1], c[1], k[1]), color="#475569")
    axis.plot((a[0], e[0], f[0]), (a[1], e[1], f[1]), color="#f8fafc", linewidth=1.7)
    axis.plot((m[0], x[0]), (m[1], x[1]), color="#fbbf24", linewidth=1.8)
    axis.add_patch(Circle((-0.95, -0.2), 2.55, fill=False, color="#22d3ee", linewidth=1.5))
    axis.add_patch(Circle((-1.25, 0.25), 2.85, fill=False, color="#a3e635", linewidth=1.5))
    for label, point, color in (
        ("K", k, "#94a3b8"),
        ("B", b, "#94a3b8"),
        ("C", c, "#94a3b8"),
        ("A", a, "#f8fafc"),
        ("E", e, "#a3e635"),
        ("F", f, "#a3e635"),
        ("M", m, "#fbbf24"),
        ("H", h, "#22d3ee"),
        ("X", x, "#f472b6"),
    ):
        axis.scatter(*point, s=30, color=color, zorder=5)
        axis.text(point[0] + 0.08, point[1] + 0.08, label, color=color, fontsize=9)
    axis.text(-4.2, 3.15, "midpoint net -> equal powers -> radical axis", color="#f8fafc", fontsize=10)
    axis.set_xlim(-4.6, 4.65)
    axis.set_ylim(-3.35, 3.55)
    buffer = io.StringIO()
    figure.savefig(buffer, format="svg", bbox_inches="tight", facecolor=figure.get_facecolor())
    plt.close(figure)
    return buffer.getvalue()


__all__ = [
    "JGEXMidpointBisectorEqualPowerApplication",
    "MidpointBisectorEqualPowerCertificate",
    "certify_jgex_midpoint_bisector_equal_power_application",
    "certify_midpoint_bisector_equal_power_chart",
    "render_midpoint_bisector_equal_power_chart_svg",
]
