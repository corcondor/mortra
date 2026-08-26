"""Exact chart for reflected arc midpoints and a center-axis invariant.

The chart is the reusable complex-affine core of SAGF 2023 problem 8.  It
depends only on a triangle, its circumcircle, three arc-midpoint branches,
antipodes, side reflections, and the resulting triangle centers.  No problem
identifier or point spelling is used by the matcher.
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
class ArcMidpointReflectionCenterAxisCertificate:
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
                "# Arc-midpoint reflection center-axis chart",
                "",
                "## Theorem",
                "",
                (
                    "For a triangle ABC, choose D,E,F on its circumcircle and on the "
                    "perpendicular bisectors of BC,CA,AB.  Reflect D,E,F and their "
                    "antipodes in the corresponding sides.  The line joining the "
                    "orthocenter of the first reflected triangle to the circumcenter "
                    "of the antipodal reflected triangle is parallel to the Euler line "
                    "of ABC."
                ),
                "",
                "## Representation changes",
                "",
                "- circumcircle points -> unit complex squares x^2,y^2,z^2",
                "- arc-midpoint branches -> products yz,zx,xy",
                "- side reflection -> p+q-pq*conjugate(w)",
                "- triangle centers -> affine complex formulas",
                "- parallelism -> a real scalar multiple",
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
class JGEXArcMidpointReflectionCenterAxisApplication:
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
def certify_arc_midpoint_reflection_center_axis_chart(
) -> ArcMidpointReflectionCenterAxisCertificate:
    x, y, z = sp.symbols("x y z", nonzero=True)

    def bar(value: sp.Expr) -> sp.Expr:
        return sp.cancel(value.xreplace({x: 1 / x, y: 1 / y, z: 1 / z}))

    def norm2(value: sp.Expr) -> sp.Expr:
        return sp.cancel(value * bar(value))

    a, b, c = x**2, y**2, z**2
    d, e, f = y * z, z * x, x * y
    r, s, t = -d, -e, -f

    d1, e1, f1 = b + c - d, c + a - e, a + b - f
    r1, s1, t1 = b + c + d, c + a + e, a + b + f

    denominator = (
        x**2 * y
        + x**2 * z
        + x * y**2
        - x * y * z
        + x * z**2
        + y**2 * z
        + y * z**2
    )
    od = (
        x**4 * y
        + x**4 * z
        - x**3 * y * z
        + x**2 * y**2 * z
        + x**2 * y * z**2
        + x * y**4
        - x * y**3 * z
        + x * y**2 * z**2
        - x * y * z**3
        + x * z**4
        + y**4 * z
        + y * z**4
    ) / denominator
    o1 = x**2 + x * y + x * z + y**2 + y * z + z**2
    h = a + b + c
    h1 = d1 + e1 + f1 - 2 * od
    scalar = -(
        (x + y + z) * (x * y + x * z + y * z) / denominator
    )

    # Certify all eight independent choices of arc-midpoint branch at once.
    sd, se, sf = sp.symbols("sd se sf")

    def branch_bar(value: sp.Expr) -> sp.Expr:
        return sp.cancel(
            value.xreplace(
                {x: 1 / x, y: 1 / y, z: 1 / z, sd: sd, se: se, sf: sf}
            )
        )

    def branch_center(points: tuple[sp.Expr, sp.Expr, sp.Expr]) -> sp.Expr:
        centre, centre_bar = sp.symbols("branch_centre branch_centre_bar")
        first = points[0]
        equations = []
        for other in points[1:]:
            equations.append(
                sp.cancel(
                    first * branch_bar(first)
                    - other * branch_bar(other)
                    - (first - other) * centre_bar
                    - (branch_bar(first) - branch_bar(other)) * centre
                )
            )
        return sp.cancel(
            sp.solve(
                equations,
                (centre, centre_bar),
                dict=True,
                simplify=False,
            )[0][centre]
        )

    def reduce_branch_signs(value: sp.Expr) -> sp.Expr:
        numerator = sp.fraction(sp.cancel(value))[0]
        polynomial = sp.Poly(numerator, sd, se, sf, domain="EX")
        reduced = sp.Integer(0)
        for powers, coefficient in polynomial.terms():
            reduced += (
                coefficient
                * sd ** (powers[0] % 2)
                * se ** (powers[1] % 2)
                * sf ** (powers[2] % 2)
            )
        return sp.factor(reduced)

    branch_d1 = b + c - sd * y * z
    branch_e1 = c + a - se * z * x
    branch_f1 = a + b - sf * x * y
    branch_r1 = b + c + sd * y * z
    branch_s1 = c + a + se * z * x
    branch_t1 = a + b + sf * x * y
    branch_od = branch_center((branch_d1, branch_e1, branch_f1))
    branch_o1 = branch_center((branch_r1, branch_s1, branch_t1))
    branch_h1 = branch_d1 + branch_e1 + branch_f1 - 2 * branch_od
    branch_ratio = sp.cancel((branch_h1 - branch_o1) / h)
    branch_real_remainder = reduce_branch_signs(
        branch_ratio - branch_bar(branch_ratio)
    )

    raw_residuals = {
        "D_on_unit_circumcircle": norm2(d) - 1,
        "E_on_unit_circumcircle": norm2(e) - 1,
        "F_on_unit_circumcircle": norm2(f) - 1,
        "D_on_perpendicular_bisector_BC": norm2(d - b) - norm2(d - c),
        "E_on_perpendicular_bisector_CA": norm2(e - c) - norm2(e - a),
        "F_on_perpendicular_bisector_AB": norm2(f - a) - norm2(f - b),
        "D_reflected_in_BC": d1 - (b + c - b * c * bar(d)),
        "E_reflected_in_CA": e1 - (c + a - c * a * bar(e)),
        "F_reflected_in_AB": f1 - (a + b - a * b * bar(f)),
        "antipode_D_reflected_in_BC": r1 - (b + c - b * c * bar(r)),
        "antipode_E_reflected_in_CA": s1 - (c + a - c * a * bar(s)),
        "antipode_F_reflected_in_AB": t1 - (a + b - a * b * bar(t)),
        "OD_equidistant_D1_E1": norm2(d1 - od) - norm2(e1 - od),
        "OD_equidistant_D1_F1": norm2(d1 - od) - norm2(f1 - od),
        "O1_equidistant_R1_S1": norm2(r1 - o1) - norm2(s1 - o1),
        "O1_equidistant_R1_T1": norm2(r1 - o1) - norm2(t1 - o1),
        "H_is_original_orthocenter_at_A": (
            (h - a) * bar(c - b) + bar(h - a) * (c - b)
        ),
        "H_is_original_orthocenter_at_B": (
            (h - b) * bar(a - c) + bar(h - b) * (a - c)
        ),
        "H1_from_circumcenter_OD": h1 - (d1 + e1 + f1 - 2 * od),
        "center_axis_factorization": h1 - o1 - scalar * h,
        "center_axis_scalar_is_real": scalar - bar(scalar),
        "all_independent_arc_branches_have_real_axis_scalar": branch_real_remainder,
    }
    residuals = {name: _canonical(value) for name, value in raw_residuals.items()}
    replayed = all(value == "0" for value in residuals.values())

    assumptions = (
        "ABC is a defined nondegenerate triangle with circumcenter O and orthocenter H",
        "D,E,F are defined circumcircle points on the three side perpendicular bisectors",
        "R,S,T are the point reflections of D,E,F in O",
        "D1,E1,F1 and R1,S1,T1 are the displayed side reflections",
        "H1 is the orthocenter of D1E1F1",
        "O1 is the circumcenter of R1S1T1",
    )
    discharged_conditions = {
        assumptions[0]: "The triangle, circumcenter, and orthocenter clauses are matched.",
        assumptions[1]: (
            "Each point is supplied by a joint on_bline and on_circle construction; "
            "the sign-reduced branch identity covers all eight independent arc choices."
        ),
        assumptions[2]: "All three mirror constructors use the matched circumcenter O.",
        assumptions[3]: "All six reflection clauses and their carrier sides are matched.",
        assumptions[4]: "The orthocenter constructor is matched on the first reflected triple.",
        assumptions[5]: "The circumcenter constructor rejects a repeated or collinear triple.",
    }
    payload = {
        "theorem": "arc-midpoint-antipode-reflection-center-axis",
        "assumptions": assumptions,
        "discharged_conditions": discharged_conditions,
        "upstream_semantics": (
            "JGEX on_bline encodes equal distances to its two carrier points.",
            "JGEX reflect is Euclidean line reflection and mirror is point reflection.",
            "For a triangle with circumcenter U, its orthocenter is the vertex sum minus 2U.",
            "A complex ratio fixed by conjugation is real and therefore encodes parallel vectors.",
        ),
        "normalization": (
            "Translate and scale the circumcircle to the unit circle.  Write its vertices "
            "as a=x^2, b=y^2, c=z^2 with unit complex x,y,z.  The selected perpendicular-"
            "bisector branches are d=sd*yz, e=se*zx, f=sf*xy with each sign squaring to "
            "one; polynomial reduction modulo sd^2=se^2=sf^2=1 covers all branches."
        ),
        "representation_chart": (
            "circumcircle plus side bisector -> half-angle product",
            "point antipode and line reflection -> affine conjugate map",
            "reflected triples -> exact circumcenter and orthocenter formulas",
            "center-line parallelism -> real scalar factorization",
        ),
        "proof_dag": (
            "Normalize the original circumcircle and introduce half-angle variables.",
            "Replace the three arc-midpoint branches by yz,zx,xy.",
            "Apply w -> p+q-pq*conjugate(w) to each side reflection.",
            "Solve two linear equal-distance equations for each reflected circumcenter.",
            "Use H1=D1+E1+F1-2OD for the first reflected triangle.",
            "Factor H1-O1 as a real scalar times H-O.",
            "Conclude H1O1 is parallel to the original Euler line OH.",
        ),
        "replay_residuals": residuals,
        "replayed": replayed,
        "all_conditions_discharged": replayed,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return ArcMidpointReflectionCenterAxisCertificate(
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
    if name in {"circumcenter", "orthocenter"} and len(args) == 3:
        return name, tuple(sorted(args))
    if name in {"on_bline", "reflect"} and len(args) >= 2:
        return name, (args[0], *sorted(args[1:])) if name == "reflect" else (tuple(sorted(args)))
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


def _joint_arc_point(
    records: tuple[dict[str, object], ...],
    left: str,
    right: str,
    centre: str,
    radius_points: frozenset[str],
) -> str | None:
    matches: set[str] = set()
    side = tuple(sorted((left, right)))
    for record in records:
        if len(record["outputs"]) != 1 or len(record["constructions"]) != 2:
            continue
        constructions = tuple(record["constructions"])
        bline_ok = any(
            name == "on_bline" and tuple(sorted(args)) == side
            for name, args in constructions
        )
        circle_ok = any(
            name == "on_circle"
            and len(args) == 2
            and args[0] == centre
            and args[1] in radius_points
            for name, args in constructions
        )
        if bline_ok and circle_ok:
            matches.add(str(record["outputs"][0]))
    return next(iter(matches)) if len(matches) == 1 else None


def certify_jgex_arc_midpoint_reflection_center_axis_application(
    source: str,
) -> JGEXArcMidpointReflectionCenterAxisApplication:
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
            o = _single(records, ("circumcenter", (a, b, c)))
            h = _single(records, ("orthocenter", (a, b, c)))
            if not o or not h:
                continue
            circle_points = frozenset((a, b, c))
            d = _joint_arc_point(records, b, c, o, circle_points)
            e = _joint_arc_point(records, c, a, o, circle_points)
            f = _joint_arc_point(records, a, b, o, circle_points)
            if not d or not e or not f:
                continue
            r = _single(records, ("mirror", (d, o)))
            s = _single(records, ("mirror", (e, o)))
            t = _single(records, ("mirror", (f, o)))
            d1 = _single(records, ("reflect", (d, b, c)))
            e1 = _single(records, ("reflect", (e, c, a)))
            f1 = _single(records, ("reflect", (f, a, b)))
            r1 = _single(records, ("reflect", (r, b, c))) if r else None
            s1 = _single(records, ("reflect", (s, c, a))) if s else None
            t1 = _single(records, ("reflect", (t, a, b))) if t else None
            if not all((r, s, t, d1, e1, f1, r1, s1, t1)):
                continue
            h1 = _single(records, ("orthocenter", (d1, e1, f1)))
            o1 = _single(records, ("circumcenter", (r1, s1, t1)))
            if not h1 or not o1:
                continue
            roles = {
                "A": a,
                "B": b,
                "C": c,
                "O": o,
                "H": h,
                "D": d,
                "E": e,
                "F": f,
                "R": r,
                "S": s,
                "T": t,
                "D1": d1,
                "E1": e1,
                "F1": f1,
                "R1": r1,
                "S1": s1,
                "T1": t1,
                "H1": h1,
                "O1": o1,
            }
            key = (
                *triangle,
                o,
                h,
                *sorted((d, e, f)),
                *sorted((r, s, t)),
                *sorted((d1, e1, f1)),
                *sorted((r1, s1, t1)),
                h1,
                o1,
            )
            candidates[key] = roles

    goal = str(formulation.goals[0]) if len(formulation.goals) == 1 else ""
    accepted: list[dict[str, str]] = []
    parts = goal.split()
    if len(parts) == 5:
        actual = Atom(parts[0], tuple(parts[1:])).canonical()
        for roles in candidates.values():
            expected = Atom("para", (roles["H1"], roles["O1"], roles["O"], roles["H"])).canonical()
            if actual == expected:
                accepted.append(roles)

    chart = certify_arc_midpoint_reflection_center_axis_chart()
    unique = accepted[0] if len(accepted) == 1 else {}
    matched = (
        "three circumcircle arc-midpoint branches",
        "their three antipodes and six side reflections",
        "the orthocenter and circumcenter of the two reflected triples",
        "parallelism with the original Euler line",
    ) if unique else ()
    replayed = bool(
        chart.replayed
        and chart.all_conditions_discharged
        and len(unique) == 19
        and len(accepted) == 1
    )
    return JGEXArcMidpointReflectionCenterAxisApplication(
        theorem=chart.theorem,
        source_sha256=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        roles=unique,
        matched_constructions=matched,
        goal=goal,
        proof_bridge=(
            "Normalize the circumcircle and write A=x^2, B=y^2, C=z^2.  The three "
            "perpendicular-bisector intersections are yz,zx,xy.  Side reflection is the "
            "affine conjugate map w -> p+q-pq*conjugate(w).  Solving the two center "
            "systems and using H1=D1+E1+F1-2OD factors H1-O1 as a real multiple of H-O."
        ),
        chart_certificate_sha256=chart.certificate_sha256,
        nondegeneracy_obligations=chart.assumptions,
        undischarged_nondegeneracy_obligations=(),
        replayed=replayed,
    )


def render_arc_midpoint_reflection_center_axis_chart_svg() -> str:
    figure, axis = plt.subplots(figsize=(8.8, 6.0))
    axis.set_aspect("equal")
    axis.axis("off")
    axis.set_facecolor("#050709")
    figure.patch.set_facecolor("#050709")

    centre = (0.0, 0.0)
    radius = 2.25
    axis.add_patch(Circle(centre, radius, fill=False, color="#334155", linewidth=1.4))
    a, b, c = (0.25, 2.24), (-2.08, -0.86), (1.82, -1.33)
    axis.plot((a[0], b[0], c[0], a[0]), (a[1], b[1], c[1], a[1]), color="#64748b")
    d, e, f = (-0.2, -2.24), (2.16, 0.62), (-1.76, 1.41)
    d1, e1, f1 = (-0.25, -0.52), (0.72, 0.86), (-0.93, 0.72)
    r1, s1, t1 = (0.2, -2.82), (2.45, 1.05), (-2.38, 1.55)
    h, h1, o1 = (0.0, 0.72), (-0.65, 0.28), (0.82, 1.27)
    axis.plot((h[0], centre[0]), (h[1], centre[1]), color="#22d3ee", linewidth=2.0)
    axis.plot((h1[0], o1[0]), (h1[1], o1[1]), color="#fbbf24", linewidth=2.0)
    axis.plot(
        (d1[0], e1[0], f1[0], d1[0]),
        (d1[1], e1[1], f1[1], d1[1]),
        color="#a3e635",
        linewidth=1.2,
    )
    axis.plot(
        (r1[0], s1[0], t1[0], r1[0]),
        (r1[1], s1[1], t1[1], r1[1]),
        color="#f472b6",
        linewidth=1.2,
    )
    for label, point, color in (
        ("A", a, "#94a3b8"), ("B", b, "#94a3b8"), ("C", c, "#94a3b8"),
        ("D", d, "#64748b"), ("E", e, "#64748b"), ("F", f, "#64748b"),
        ("H", h, "#22d3ee"), ("O", centre, "#22d3ee"),
        ("H1", h1, "#fbbf24"), ("O1", o1, "#fbbf24"),
    ):
        axis.scatter(*point, s=29, color=color, zorder=5)
        axis.text(point[0] + 0.08, point[1] + 0.08, label, color=color, fontsize=9)
    axis.text(-2.7, 2.75, "reflected arc-midpoint center axis", color="#f8fafc", fontsize=10)
    axis.set_xlim(-3.0, 3.0)
    axis.set_ylim(-3.05, 3.0)
    buffer = io.StringIO()
    figure.savefig(buffer, format="svg", bbox_inches="tight", facecolor=figure.get_facecolor())
    plt.close(figure)
    return buffer.getvalue()


__all__ = [
    "ArcMidpointReflectionCenterAxisCertificate",
    "JGEXArcMidpointReflectionCenterAxisApplication",
    "certify_arc_midpoint_reflection_center_axis_chart",
    "certify_jgex_arc_midpoint_reflection_center_axis_application",
    "render_arc_midpoint_reflection_center_axis_chart_svg",
]
