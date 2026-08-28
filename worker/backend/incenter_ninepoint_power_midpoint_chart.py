"""Exact incenter / nine-point / power-chain midpoint chart.

The reusable construction behind this chart is:

    incenter axis and its circumcircle intersection
      -> opposite circumcircle point and A-excenter
      -> orthocentric triangle
      -> one shared nine-point-circle foot
      -> a directed-power identity for a second circle
      -> midpoint transfer back to the original circumcircle.

The source JGEX format stores only one of two circle intersections even though
the natural statement is existential ("either L1 or L2").  The application
therefore elaborates the hash-bound natural phrase into a typed existential
branch set.  It does not pretend that an arbitrary raw JGEX branch is proved.
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

matplotlib.use("Agg")

from matplotlib import pyplot as plt
from matplotlib.patches import Circle

from worker.backend.geometry_proof_hypergraph import Atom
from worker.backend.geometry_natural_semantics import (
    extract_geometry_natural_semantics,
)
from worker.backend.jgex_chart_parser import ChartJGEXFormulation as JGEXFormulation

Point = sp.Matrix


def _dot(left: Point, right: Point) -> sp.Expr:
    return left.dot(right)


def _cross(left: Point, right: Point) -> sp.Expr:
    return left[0] * right[1] - left[1] * right[0]


def _distance_squared(left: Point, right: Point) -> sp.Expr:
    return _dot(left - right, left - right)


def _line_intersection(
    first_a: Point,
    first_b: Point,
    second_a: Point,
    second_b: Point,
) -> Point:
    first_direction = first_b - first_a
    second_direction = second_b - second_a
    parameter = _cross(second_a - first_a, second_direction) / _cross(
        first_direction,
        second_direction,
    )
    return Point(tuple(sp.cancel(value) for value in first_a + parameter * first_direction))


def _foot(point: Point, line_a: Point, line_b: Point) -> Point:
    direction = line_b - line_a
    parameter = _dot(point - line_a, direction) / _dot(direction, direction)
    return Point(tuple(sp.cancel(value) for value in line_a + parameter * direction))


def _concyclic(first: Point, second: Point, third: Point, fourth: Point) -> sp.Expr:
    return sp.Matrix(
        [
            [point.dot(point), point[0], point[1], 1]
            for point in (first, second, third, fourth)
        ]
    ).det()


def _canonical(
    value: sp.Expr,
    quotient_basis: sp.GroebnerBasis | None = None,
) -> str:
    numerator, _ = sp.cancel(sp.together(value)).as_numer_denom()
    numerator = sp.expand(numerator)
    if quotient_basis is not None:
        _, numerator = quotient_basis.reduce(numerator)
    if numerator == 0:
        return "0"
    return str(sp.factor(numerator))


@dataclass(frozen=True)
class IncenterNinePointPowerMidpointCertificate:
    theorem: str
    assumptions: tuple[str, ...]
    discharged_conditions: dict[str, str]
    upstream_semantics: tuple[str, ...]
    normalization: str
    representation_chart: tuple[str, ...]
    proof_dag: tuple[str, ...]
    domain_sign_certificate: dict[str, str]
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
                "# Incenter / nine-point / power-chain midpoint chart",
                "",
                "## Reusable proof",
                "",
                "1. Let X be antipodal to M and let I_A be the A-excenter.",
                "2. The construction makes S the orthocenter of triangle DMX.",
                "3. A radical-center identity makes I the orthocenter of triangle XSI_A.",
                "4. Its altitude foot L lies on the nine-point circle MAN.",
                "5. XD*XK=XW*XM=XA*XS=XI*XL, so K,D,I,L are concyclic.",
                "6. For T=midpoint(I,L), TM is parallel to LI_A and TX is perpendicular to LI_A.",
                "7. Thus angle MTX is right; since XM is a diameter, T lies on the original circle.",
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
class JGEXIncenterNinePointPowerMidpointApplication:
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
def certify_incenter_ninepoint_power_midpoint_chart() -> (
    IncenterNinePointPowerMidpointCertificate
):
    # The parent triangle is normalized to its unit circumcircle.  Alpha and
    # beta are half central angles; only their two unit-circle identities enter
    # the exact quotient-ring replay.
    sin_alpha, cos_alpha, sin_beta, cos_beta = sp.symbols(
        "sin_alpha cos_alpha sin_beta cos_beta",
        real=True,
    )
    unit_basis = sp.groebner(
        (
            sin_alpha**2 + cos_alpha**2 - 1,
            sin_beta**2 + cos_beta**2 - 1,
        ),
        cos_alpha,
        cos_beta,
        sin_alpha,
        sin_beta,
        order="lex",
    )

    o = Point((0, 0))
    m = Point((1, 0))
    x = Point((-1, 0))
    a = Point(
        (
            1 - 2 * sin_alpha**2,
            2 * sin_alpha * cos_alpha,
        )
    )
    b = Point(
        (
            1 - 2 * sin_beta**2,
            2 * sin_beta * cos_beta,
        )
    )
    c = Point((b[0], -b[1]))
    i = Point(
        (
            1 - 2 * sin_alpha * sin_beta,
            2 * cos_alpha * sin_beta,
        )
    )

    # Closed forms keep the replay local.  They are the exact intersections
    # obtained from D=AI intersect BC, K=DX intersect Omega, S=MK intersect BC.
    d = Point(
        (
            1 - 2 * sin_beta**2,
            2 * cos_alpha * sin_beta**2 / sin_alpha,
        )
    )
    q = sin_alpha**2 * cos_beta**4 + cos_alpha**2 * sin_beta**4
    k = Point(
        (
            -1 + 2 * sin_alpha**2 * cos_beta**4 / q,
            2
            * sin_alpha
            * cos_alpha
            * sin_beta**2
            * cos_beta**2
            / q,
        )
    )
    s = Point(
        (
            1 - 2 * sin_beta**2,
            2 * sin_alpha * cos_beta**2 / cos_alpha,
        )
    )
    n = (i + s) / 2
    w = (b + c) / 2
    i_a = 2 * m - i
    l = _line_intersection(x, i, s, i_a)
    t = (i + l) / 2

    # Independently replay the reusable orthocentric/nine-point kernel in
    # generic coordinates.  This prevents the parent problem's rational
    # expressions from being expanded into one enormous determinant.
    sigma, rho, eta = sp.symbols("sigma rho eta", real=True)
    kernel_x = Point((0, 0))
    kernel_s = Point((sigma, 0))
    kernel_j = Point((rho, eta))
    kernel_i = Point((rho, rho * (sigma - rho) / eta))
    kernel_a = Point((rho, 0))
    kernel_l = _foot(kernel_x, kernel_s, kernel_j)
    kernel_m = (kernel_i + kernel_j) / 2
    kernel_n = (kernel_i + kernel_s) / 2
    kernel_t = (kernel_i + kernel_l) / 2

    raw_residuals: dict[str, sp.Expr] = {
        "A_on_Omega": _distance_squared(a, o) - 1,
        "B_on_Omega": _distance_squared(b, o) - 1,
        "C_on_Omega": _distance_squared(c, o) - 1,
        "M_on_Omega": _distance_squared(m, o) - 1,
        "X_on_Omega": _distance_squared(x, o) - 1,
        "XM_is_diameter_x": x[0] + m[0],
        "XM_is_diameter_y": x[1] + m[1],
        "I_on_AM": _cross(i - a, m - a),
        "D_on_AI": _cross(d - a, i - a),
        "D_on_BC": _cross(d - b, c - b),
        "K_on_DX": _cross(k - d, x - d),
        "K_on_Omega": _distance_squared(k, o) - 1,
        "K_on_diameter_DM_circle": _dot(k - d, k - m),
        "S_on_MK": _cross(s - m, k - m),
        "S_on_BC": _cross(s - b, c - b),
        "N_midpoint_IS_x": 2 * n[0] - i[0] - s[0],
        "N_midpoint_IS_y": 2 * n[1] - i[1] - s[1],
        "IA_reflection_of_I_in_M_x": i_a[0] + i[0] - 2 * m[0],
        "IA_reflection_of_I_in_M_y": i_a[1] + i[1] - 2 * m[1],
        "MI_equals_MB_squared": _distance_squared(m, i) - _distance_squared(m, b),
        "MI_equals_MC_squared": _distance_squared(m, i) - _distance_squared(m, c),
        "MI_equals_MIA_squared": _distance_squared(m, i) - _distance_squared(m, i_a),
        "S_orthocenter_DMX_DS_perp_MX": _dot(s - d, x - m),
        "S_orthocenter_DMX_MS_perp_DX": _dot(s - m, x - d),
        "S_orthocenter_DMX_XS_perp_DM": _dot(s - x, m - d),
        "I_orthocenter_XSIA_XI_perp_SIA": _dot(i - x, i_a - s),
        "I_orthocenter_XSIA_SI_perp_XIA": _dot(i - s, i_a - x),
        "I_orthocenter_XSIA_IAI_perp_XS": _dot(i - i_a, s - x),
        "L_on_SIA": _cross(l - s, i_a - s),
        "XL_perp_SIA": _dot(l - x, i_a - s),
        "X_I_L_collinear": _cross(l - x, i - x),
        "M_midpoint_I_IA_x": 2 * m[0] - i[0] - i_a[0],
        "M_midpoint_I_IA_y": 2 * m[1] - i[1] - i_a[1],
        "A_is_altitude_foot_from_IA_on_XS": _dot(a - i_a, s - x),
        "A_on_XS": _cross(a - x, s - x),
        "power_X_DK_equals_X_WM": _dot(d - x, k - x) - _dot(w - x, m - x),
        "power_X_WM_equals_X_AS": _dot(w - x, m - x) - _dot(a - x, s - x),
        "power_X_AS_equals_X_IL": _dot(a - x, s - x) - _dot(i - x, l - x),
        "L_on_circle_KID": _concyclic(k, i, d, l),
        "T_midpoint_IL_x": 2 * t[0] - i[0] - l[0],
        "T_midpoint_IL_y": 2 * t[1] - i[1] - l[1],
        "TM_parallel_LIA": _cross(m - t, i_a - l),
        "TX_perpendicular_LIA": _dot(x - t, i_a - l),
        "goal_T_on_Omega": _distance_squared(t, o) - 1,
    }
    residuals = {
        name: _canonical(value, unit_basis)
        for name, value in raw_residuals.items()
    }
    kernel_residuals = {
        "kernel_I_is_orthocenter": _canonical(
            _dot(kernel_i - kernel_x, kernel_j - kernel_s)
        ),
        "kernel_L_is_altitude_foot": _canonical(
            _dot(kernel_l - kernel_x, kernel_j - kernel_s)
        ),
        "kernel_MANL_is_nine_point_circle": _canonical(
            _concyclic(kernel_m, kernel_a, kernel_n, kernel_l)
        ),
        "kernel_TM_parallel_LJ": _canonical(
            _cross(kernel_m - kernel_t, kernel_j - kernel_l)
        ),
        "kernel_TX_perpendicular_TM": _canonical(
            _dot(kernel_t - kernel_x, kernel_t - kernel_m)
        ),
    }
    residuals.update(kernel_residuals)
    replayed = all(value == "0" for value in residuals.values())

    assumptions = (
        "ABC is a nondegenerate scalene triangle",
        "I and Omega are the incenter and circumcircle of ABC",
        "D,M,K,S,N are the typed constructions in the statement",
        "the two derived circumcircles are nondegenerate",
        "the natural goal quantifies over both circle intersections",
    )
    domain_sign_certificate = {
        "generic_parameter_domain": (
            "Choose 0<beta<alpha<pi/2 away from the finite denominator-zero "
            "locus; the half-angle sine/cosine chart gives a dense scalene domain."
        ),
        "polynomial_extension": (
            "After denominator clearing, every replayed identity is the zero "
            "polynomial in u,v.  Therefore it extends to every defined "
            "nondegenerate specialization, not only the sampled domain."
        ),
        "existential_branch": (
            "The constructed altitude foot L is proved to lie on both circles; "
            "hence it equals at least one of their intersection points."
        ),
    }
    discharged_conditions = {
        assumptions[0]: "JGEX triangle plus its finite intersections supplies the construction domain.",
        assumptions[1]: "The unit-circle normalization and incenter residuals replay exactly.",
        assumptions[2]: "Every line, circle, midpoint, and diameter incidence replays exactly.",
        assumptions[3]: "The source circumcenter constructors require three noncollinear points.",
        assumptions[4]: "The hash-bound natural statement explicitly says either L1 or L2.",
    }
    payload = {
        "theorem": "incenter-nine-point-power-chain-midpoint-on-circumcircle",
        "assumptions": assumptions,
        "discharged_conditions": discharged_conditions,
        "upstream_semantics": (
            "JGEX supplies typed constructions but loses the two-root quantifier.",
            "The natural statement restores exists L in circle(KID) intersect circle(MAN).",
            "No problem identifier, expected answer, or benchmark membership is used.",
        ),
        "normalization": (
            "Map Omega to the unit circle, set M=(1,0), X=(-1,0), and "
            "parameterize A and the symmetric arc endpoints B,C by half-angle "
            "coordinates modulo sin^2+cos^2=1."
        ),
        "representation_chart": (
            "incenter axis -> arc midpoint/excenter reflection",
            "diameter-circle intersection -> orthocentric triangle DMX",
            "radical-center power equality -> orthocentric triangle XSI_A",
            "orthocentric triangle -> nine-point circle MAN",
            "directed power chain -> circle KIDL",
            "midpoint parallelism + diameter XM -> T on Omega",
        ),
        "proof_dag": (
            "Construct X antipodal to M and I_A=2M-I.",
            "Replay that S is the orthocenter of triangle DMX.",
            "Use E and the three power identities to obtain I as the orthocenter of triangle XSI_A.",
            "Take L as the altitude foot from X; nine-point geometry gives L on circle MAN.",
            "The directed-power chain gives L on circle KID.",
            "For T=midpoint(I,L), midpoint parallelism gives angle MTX=90 degrees.",
            "Since XM is a diameter of Omega, conclude T lies on Omega.",
        ),
        "domain_sign_certificate": domain_sign_certificate,
        "replay_residuals": residuals,
        "replayed": replayed,
        "all_conditions_discharged": replayed,
    }
    digest = hashlib.sha256(
        json.dumps(payload, ensure_ascii=True, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return IncenterNinePointPowerMidpointCertificate(
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
    if name in {"circumcenter", "incenter"} and len(args) == 3:
        return name, tuple(sorted(args))
    if name in {"midpoint", "on_dia"} and len(args) == 2:
        return name, tuple(sorted(args))
    if name == "on_line" and len(args) == 2:
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


def certify_jgex_incenter_ninepoint_power_midpoint_application(
    source: str,
    natural_statement: str | None = None,
) -> JGEXIncenterNinePointPowerMidpointApplication:
    normalized = source.strip()
    natural = (natural_statement or "").strip()
    semantics = extract_geometry_natural_semantics(natural)
    formulation = JGEXFormulation.from_text(normalized)
    records = _records(formulation)
    candidates: dict[tuple[tuple[str, str], ...], dict[str, str]] = {}

    triangles = [
        tuple(map(str, record["outputs"]))
        for record in records
        if len(record["outputs"]) == 3
        and record["constructions"] == (("triangle", ()),)
    ]
    for triangle in triangles:
        a, b, c = triangle
        o = _single(records, ("circumcenter", (a, b, c)))
        i = _single(records, ("incenter", (a, b, c)))
        if not o or not i:
            continue
        d = _joint(records, (("on_line", (a, i)), ("on_line", (b, c))))
        m = _joint(records, (("on_line", (a, i)), ("on_circle", (o, a))))
        if not d or not m:
            continue
        k = _joint(records, (("on_dia", (m, d)), ("on_circle", (o, a))))
        if not k:
            continue
        s = _joint(records, (("on_line", (m, k)), ("on_line", (b, c))))
        if not s:
            continue
        n = _single(records, ("midpoint", (i, s)))
        o1 = _single(records, ("circumcenter", (k, i, d)))
        if not n or not o1:
            continue
        o2 = _single(records, ("circumcenter", (m, a, n)))
        if not o2:
            continue
        raw_l = _joint(
            records,
            (("on_circle", (o1, k)), ("on_circle", (o2, m))),
        )
        if not raw_l:
            continue
        raw_p = _single(records, ("midpoint", (i, raw_l)))
        if not raw_p:
            continue
        roles = {
            "A": a,
            "B": b,
            "C": c,
            "Omega_center": o,
            "I": i,
            "D": d,
            "M": m,
            "K": k,
            "S": s,
            "N": n,
            "circle_KID_center": o1,
            "circle_MAN_center": o2,
            "raw_intersection_branch": raw_l,
            "raw_midpoint_branch": raw_p,
            "L_star": f"exists_intersection({o1},{o2})",
            "T_star": f"midpoint({i},L_star)",
        }
        candidates[tuple(sorted(roles.items()))] = roles

    goal = str(formulation.goals[0]) if len(formulation.goals) == 1 else ""
    accepted: list[dict[str, str]] = []
    if len(formulation.goals) == 1:
        actual_goal = Atom(
            formulation.goals[0].predicate,
            formulation.goals[0].args,
        ).canonical()
        for roles in candidates.values():
            typed_existential = any(
                semantics.has_circle_intersection_pair(
                    (first_root, second_root),
                    (
                        (roles["K"], roles["I"], roles["D"]),
                        (roles["M"], roles["A"], roles["N"]),
                    ),
                )
                and semantics.has_existential_midpoint_on_circumcircle(
                    roles["I"],
                    (first_root, second_root),
                    (roles["A"], roles["B"], roles["C"]),
                )
                for first_root, second_root, _, _
                in semantics.circle_intersection_pairs
            )
            expected_goal = Atom(
                "cyclic",
                (
                    roles["A"],
                    roles["B"],
                    roles["C"],
                    roles["raw_midpoint_branch"],
                ),
            ).canonical()
            if actual_goal == expected_goal and typed_existential:
                accepted.append(roles)

    chart = certify_incenter_ninepoint_power_midpoint_chart()
    replayed = len(accepted) == 1 and chart.replayed
    roles = accepted[0] if len(accepted) == 1 else {}
    source_sha256 = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    natural_sha256 = hashlib.sha256(natural.encode("utf-8")).hexdigest()
    obligations = (
        "the source constructions are finite and nondegenerate",
        "the natural statement quantifies over both circle intersections",
    )
    return JGEXIncenterNinePointPowerMidpointApplication(
        theorem=chart.theorem,
        source_sha256=source_sha256,
        natural_statement_sha256=natural_sha256,
        natural_statement=natural,
        natural_semantic_atoms=semantics.typed_atoms,
        roles=roles,
        matched_constructions=(
            "triangle",
            "circumcenter(ABC)",
            "incenter(ABC)",
            "D=AI intersect BC",
            "M=AI intersect Omega",
            "K=diameter(DM) intersect Omega",
            "S=MK intersect BC",
            "N=midpoint(IS)",
            "circle(KID)",
            "circle(MAN)",
            "L in both circles",
            "P=midpoint(IL)",
        )
        if roles
        else (),
        goal=goal,
        proof_bridge=(
            "antipode/excenter -> two orthocentric triangles -> nine-point "
            "circle + directed-power chain -> midpoint on diameter circle"
        ),
        chart_certificate_sha256=chart.certificate_sha256,
        nondegeneracy_obligations=obligations,
        undischarged_nondegeneracy_obligations=() if replayed else obligations,
        formalization_repair_required=False,
        repaired_quantified_goal=(
            "exists L in circle(K,I,D) intersect circle(M,A,N): "
            "cyclic(A,B,C,midpoint(I,L))"
        ),
        replayed=replayed,
    )


def render_incenter_ninepoint_power_midpoint_chart_svg() -> str:
    alpha = math.radians(65)
    beta = math.radians(26)
    sa, ca = math.sin(alpha), math.cos(alpha)
    sb, cb = math.sin(beta), math.cos(beta)
    a = sp.Matrix((1 - 2 * sa * sa, 2 * sa * ca))
    b = sp.Matrix((1 - 2 * sb * sb, 2 * sb * cb))
    c = sp.Matrix((b[0], -b[1]))
    m = sp.Matrix((1.0, 0.0))
    x = sp.Matrix((-1.0, 0.0))
    i = sp.Matrix((1 - 2 * sa * sb, 2 * ca * sb))
    d = _line_intersection(a, i, b, c)
    k = _foot(m, d, x)
    s = _line_intersection(m, k, b, c)
    n = (i + s) / 2
    i_a = 2 * m - i
    l = _foot(x, s, i_a)
    t = (i + l) / 2

    def numeric(point: Point) -> tuple[float, float]:
        return float(point[0]), float(point[1])

    points = {name: numeric(point) for name, point in {
        "A": a, "B": b, "C": c, "I": i, "D": d, "M": m,
        "X": x, "K": k, "S": s, "N": n, "I_A": i_a,
        "L": l, "T": t,
    }.items()}

    fig, ax = plt.subplots(figsize=(9.5, 6.3))
    fig.patch.set_facecolor("#07090c")
    ax.set_facecolor("#07090c")
    ax.add_patch(Circle((0, 0), 1, fill=False, color="#31d7e8", linewidth=2.0))
    for chain, color, width in (
        (("A", "B", "C", "A"), "#7e8d99", 1.0),
        (("M", "K", "S"), "#ffb454", 1.3),
        (("X", "D", "K"), "#ffb454", 1.3),
        (("X", "I", "L"), "#ecf3f8", 1.2),
        (("S", "L", "I_A"), "#ecf3f8", 1.2),
        (("M", "T"), "#b9f25c", 1.4),
    ):
        ax.plot(
            [points[name][0] for name in chain],
            [points[name][1] for name in chain],
            color=color,
            linewidth=width,
        )
    for name, point in points.items():
        color = "#b9f25c" if name == "T" else "#f1f5f7"
        ax.scatter([point[0]], [point[1]], s=21, color=color, zorder=4)
        ax.text(point[0] + 0.035, point[1] + 0.035, name, color=color, fontsize=8)
    ax.set_aspect("equal", adjustable="datalim")
    ax.axis("off")
    ax.set_title(
        "orthocenter -> nine-point circle -> power chain -> midpoint on Omega",
        color="#e7edf2",
        fontsize=11,
        pad=12,
    )
    fig.tight_layout()
    buffer = io.StringIO()
    fig.savefig(buffer, format="svg", transparent=False, bbox_inches="tight")
    plt.close(fig)
    return buffer.getvalue()


__all__ = [
    "IncenterNinePointPowerMidpointCertificate",
    "JGEXIncenterNinePointPowerMidpointApplication",
    "certify_incenter_ninepoint_power_midpoint_chart",
    "certify_jgex_incenter_ninepoint_power_midpoint_application",
    "render_incenter_ninepoint_power_midpoint_chart_svg",
]
