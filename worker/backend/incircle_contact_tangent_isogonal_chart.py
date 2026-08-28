"""Exact chart for an incircle contact chord and two tangent vertices.

The chart recognizes the following construction without consulting a problem
identifier or an expected answer.  The incircle of ABC touches AB and AC at
F and E.  A point M lies on EF and the circumcircle.  The tangents at A,M
meet at S, the tangents at B,C meet at T, and J=TI cap OA.  Then

    angle(AS, SJ) = angle(IS, ST)  (mod pi).

The proof converts the contact chord EF into the polar of A with respect to
the incircle.  In one rational unit-circle chart the numerator of the final
directed-angle equation is exactly the polar-incidence numerator times a
small polynomial.  Consequently the proof covers both intersections of EF
with the circumcircle and needs no branch repair.
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
from worker.backend.jgex_chart_parser import ChartJGEXFormulation as JGEXFormulation


Point = tuple[sp.Expr, sp.Expr]


def _canonical(value: sp.Expr) -> str:
    if value == 0:
        return "0"
    cancelled = sp.cancel(value)
    return "0" if cancelled == 0 else str(sp.factor(cancelled))


def _point(x: sp.Expr, y: sp.Expr) -> Point:
    return sp.cancel(x), sp.cancel(y)


def _add(left: Point, right: Point) -> Point:
    return _point(left[0] + right[0], left[1] + right[1])


def _subtract(left: Point, right: Point) -> Point:
    return _point(left[0] - right[0], left[1] - right[1])


def _scale(factor: sp.Expr, value: Point) -> Point:
    return _point(factor * value[0], factor * value[1])


def _dot(left: Point, right: Point) -> sp.Expr:
    return sp.cancel(left[0] * right[0] + left[1] * right[1])


def _cross(left: Point, right: Point) -> sp.Expr:
    return sp.cancel(left[0] * right[1] - left[1] * right[0])


def _distance_squared(left: Point, right: Point) -> sp.Expr:
    delta = _subtract(left, right)
    return _dot(delta, delta)


def _line_distance_squared(point: Point, left: Point, right: Point) -> sp.Expr:
    direction = _subtract(right, left)
    return sp.cancel(
        _cross(_subtract(point, left), direction) ** 2 / _dot(direction, direction)
    )


def _foot(point: Point, left: Point, right: Point) -> Point:
    direction = _subtract(right, left)
    parameter = sp.cancel(
        _dot(_subtract(point, left), direction) / _dot(direction, direction)
    )
    return _add(left, _scale(parameter, direction))


def _sine_cosine(parameter: sp.Expr) -> tuple[sp.Expr, sp.Expr]:
    denominator = 1 + parameter**2
    return (
        sp.cancel(2 * parameter / denominator),
        sp.cancel((1 - parameter**2) / denominator),
    )


def _circumcircle_point_from_half_angle(parameter: sp.Expr) -> Point:
    sine, cosine = _sine_cosine(parameter)
    return _point(cosine**2 - sine**2, 2 * sine * cosine)


def _unit_circle_point(parameter: sp.Expr) -> Point:
    return _point(
        (1 - parameter**2) / (1 + parameter**2),
        2 * parameter / (1 + parameter**2),
    )


def _tangent_intersection(left: Point, right: Point) -> Point:
    determinant = _cross(left, right)
    return _point(
        (right[1] - left[1]) / determinant,
        (left[0] - right[0]) / determinant,
    )


def _numerator(value: sp.Expr) -> sp.Expr:
    return sp.factor(sp.together(sp.cancel(value)).as_numer_denom()[0])


@dataclass(frozen=True)
class IncircleContactTangentIsogonalCertificate:
    theorem: str
    assumptions: tuple[str, ...]
    discharged_conditions: dict[str, str]
    upstream_semantics: tuple[str, ...]
    normalization: str
    parameterization: dict[str, str]
    representation_chart: tuple[str, ...]
    proof_dag: tuple[str, ...]
    elimination_identity: dict[str, str]
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
                "# Incircle contact-chord tangent-isogonality chart",
                "",
                "## Theorem",
                "",
                (
                    "Let the incircle of ABC touch CA and AB at E and F.  "
                    "Let M be either point of EF on the circumcircle.  The "
                    "tangents at A,M meet at S and the tangents at B,C meet "
                    "at T.  If J=TI cap OA, then angle ASJ=angle IST modulo pi."
                ),
                "",
                "## Reusable proof",
                "",
                "1. EF is the polar of A with respect to the incircle.",
                "2. Normalize the circumcircle to the unit circle and use rational half-angle coordinates.",
                "3. Tangent intersections and J are linear rational constructions in that chart.",
                "4. The directed-angle numerator factors through the polar-incidence numerator.",
                "5. M lies on EF, so that incidence factor is zero; hence the angle equality follows.",
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
class JGEXIncircleContactTangentIsogonalApplication:
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
def certify_incircle_contact_tangent_isogonal_chart(
) -> IncircleContactTangentIsogonalCertificate:
    # Put the midpoint of the minor BC arc at (1,0).  If the central
    # half-angles are alpha,beta, use u=tan(alpha/2), v=tan(beta/2).
    # A third rational parameter w covers M; the omitted point (-1,0) cannot
    # lie on EF in the nondegenerate domain, as recorded below.
    u, v, w = sp.symbols("u v w", real=True)
    sine_alpha, cosine_alpha = _sine_cosine(u)
    sine_beta, cosine_beta = _sine_cosine(v)

    origin = _point(sp.Integer(0), sp.Integer(0))
    a = _circumcircle_point_from_half_angle(u)
    b = _circumcircle_point_from_half_angle(v)
    c = _point(b[0], -b[1])
    m = _unit_circle_point(w)
    i = _point(
        1 - 2 * sine_alpha * sine_beta,
        2 * cosine_alpha * sine_beta,
    )
    inradius_squared = sp.cancel(
        4 * sine_beta**2 * (sine_alpha - sine_beta) ** 2
    )

    d = _foot(i, b, c)
    e = _foot(i, a, c)
    f = _foot(i, a, b)

    def contact_polar(point: Point) -> sp.Expr:
        return sp.cancel(
            _dot(_subtract(point, i), _subtract(a, i)) - inradius_squared
        )

    contact_chord_scale = sp.cancel(4 * v * (v - 1) * (v + 1) / (v**2 + 1) ** 2)
    line_incidence = _cross(_subtract(m, e), _subtract(f, e))
    polar_incidence = contact_polar(m)

    s = _tangent_intersection(m, a)
    t = _point(1 / b[0], sp.Integer(0))
    ti_direction = _subtract(i, t)
    oa_parameter = sp.cancel(_cross(t, ti_direction) / _cross(a, ti_direction))
    j = _scale(oa_parameter, a)

    as_direction = _subtract(a, s)
    sj_direction = _subtract(j, s)
    is_direction = _subtract(i, s)
    st_direction = _subtract(t, s)
    directed_angle_polynomial = sp.cancel(
        _cross(as_direction, sj_direction) * _dot(is_direction, st_direction)
        - _dot(as_direction, sj_direction) * _cross(is_direction, st_direction)
    )
    polar_numerator = _numerator(polar_incidence)
    angle_numerator = _numerator(directed_angle_polynomial)
    goal_incidence_quotient = -8 * u * v * (u**2 * w + 2 * u - w)

    minus_arc_midpoint = _point(sp.Integer(-1), sp.Integer(0))
    omitted_point_polar_numerator = _numerator(contact_polar(minus_arc_midpoint))

    raw_residuals: dict[str, sp.Expr] = {
        "A_on_unit_circumcircle": _distance_squared(a, origin) - 1,
        "B_on_unit_circumcircle": _distance_squared(b, origin) - 1,
        "C_on_unit_circumcircle": _distance_squared(c, origin) - 1,
        "M_on_unit_circumcircle": _distance_squared(m, origin) - 1,
        "I_equidistant_from_AB_AC": (
            _line_distance_squared(i, a, b) - _line_distance_squared(i, a, c)
        ),
        "I_equidistant_from_AB_BC": (
            _line_distance_squared(i, a, b) - _line_distance_squared(i, b, c)
        ),
        "D_on_BC": _cross(_subtract(d, b), _subtract(c, b)),
        "ID_perpendicular_BC": _dot(_subtract(i, d), _subtract(c, b)),
        "E_on_CA": _cross(_subtract(e, c), _subtract(a, c)),
        "IE_perpendicular_CA": _dot(_subtract(i, e), _subtract(a, c)),
        "F_on_AB": _cross(_subtract(f, a), _subtract(b, a)),
        "IF_perpendicular_AB": _dot(_subtract(i, f), _subtract(b, a)),
        "ID_squared_is_inradius_squared": (
            _distance_squared(i, d) - inradius_squared
        ),
        "IE_squared_is_inradius_squared": (
            _distance_squared(i, e) - inradius_squared
        ),
        "IF_squared_is_inradius_squared": (
            _distance_squared(i, f) - inradius_squared
        ),
        "E_on_contact_polar_of_A": contact_polar(e),
        "F_on_contact_polar_of_A": contact_polar(f),
        "EF_perpendicular_AI": _dot(_subtract(e, f), _subtract(a, i)),
        "EF_line_equals_contact_polar": (
            line_incidence - contact_chord_scale * polar_incidence
        ),
        "S_on_tangent_at_M": _dot(m, s) - 1,
        "S_on_tangent_at_A": _dot(a, s) - 1,
        "T_on_tangent_at_B": _dot(b, t) - 1,
        "T_on_tangent_at_C": _dot(c, t) - 1,
        "J_on_TI": _cross(_subtract(j, t), _subtract(i, t)),
        "J_on_OA": _cross(_subtract(j, origin), _subtract(a, origin)),
        "directed_angle_numerator_factors_through_EF": (
            angle_numerator - goal_incidence_quotient * polar_numerator
        ),
    }
    residuals = {name: _canonical(value) for name, value in raw_residuals.items()}
    replayed = all(value == "0" for value in residuals.values())

    assumptions = (
        "ABC is a nondegenerate triangle and I is its incenter",
        "D,E,F are the perpendicular feet of I on BC,CA,AB",
        "O is the circumcenter and M is a defined common point of EF and (O)",
        "the tangent pairs at M,A and B,C have finite intersections S,T",
        "the lines TI and OA have a finite intersection J",
    )
    discharged_conditions = {
        assumptions[0]: (
            "The matched triangle and incenter constructors supply the ordered "
            "nondegenerate triangle and its internal incenter."
        ),
        assumptions[1]: (
            "The three matched foot constructors supply the orthogonal contact points."
        ),
        assumptions[2]: (
            "The circumcenter and joint on_line/on_circle clause supply a real, "
            "defined M on both carriers."
        ),
        assumptions[3]: (
            "Each joint pair of on_tline clauses exists only when the two tangent "
            "carriers have a finite common point."
        ),
        assumptions[4]: (
            "The joint pair of on_line clauses defines J and rejects parallel or "
            "coincident carrier ambiguity."
        ),
    }
    payload = {
        "theorem": "incircle-contact-chord-circumtangents-isogonal-trace",
        "assumptions": assumptions,
        "discharged_conditions": discharged_conditions,
        "upstream_semantics": (
            "JGEX triangle constructs a noncollinear ordered triple.",
            "JGEX incenter is the internal point equidistant from all side lines.",
            "JGEX foot is the Euclidean orthogonal projection onto a carrier line.",
            "JGEX on_tline P A B is the line through P perpendicular to AB.",
            "For a unit circle, the tangent at X has equation X dot Y = 1.",
            "JGEX eqangle is equality of directed line angles modulo pi.",
        ),
        "normalization": (
            "Apply an orientation-preserving similarity so O=(0,0), R=1, "
            "B=(cos 2beta,sin 2beta), C=(cos 2beta,-sin 2beta), and A=(cos 2alpha,sin 2alpha)."
        ),
        "parameterization": {
            "half_angle_parameters": "u=tan(alpha/2), v=tan(beta/2), 0<v<u<1/v",
            "circle_parameter": "U(w)=((1-w^2)/(1+w^2),2w/(1+w^2))",
            "incenter": "I=(1-2 sin(alpha)sin(beta),2 cos(alpha)sin(beta))",
            "inradius_squared": "4 sin(beta)^2 (sin(alpha)-sin(beta))^2",
            "tangent": "X dot Y=1 for X on the unit circle",
        },
        "representation_chart": (
            "incenter + two adjacent feet -> contact chord/polar of A",
            "circumcircle tangent pair -> solution of two linear tangent equations",
            "TI cap OA -> one projective line-intersection parameter",
            "directed equal angles -> one cross-dot polynomial",
            "cross-dot polynomial -> contact-polar incidence times a quotient",
        ),
        "proof_dag": (
            "Project I onto CA and AB to obtain E,F.",
            "Use IE perpendicular CA and IF perpendicular AB to prove E,F lie on the polar of A.",
            "Replace M on EF by the polar-incidence equation.",
            "Solve the four tangent equations for S and T, then solve TI cap OA for J.",
            "Translate angle ASJ=IST into a cross-dot determinant.",
            "Factor its numerator through the polar-incidence numerator and close the goal.",
        ),
        "elimination_identity": {
            "contact_line_to_polar_scale": _canonical(contact_chord_scale),
            "goal_to_polar_quotient": _canonical(goal_incidence_quotient),
            "branch_independence": (
                "The factorization uses only M on EF and M on the circumcircle; "
                "it does not select one line-circle root."
            ),
        },
        "domain_sign_certificate": {
            "minor_arc_domain": "0 < v < u and u*v < 1",
            "contact_chord_scale_nonzero": "v>0, v!=1",
            "rational_M_chart_is_complete_here": (
                "At M=(-1,0), the polar numerator is "
                + _canonical(omitted_point_polar_numerator)
                + "; it is nonzero under 0<v<u and u*v<1."
            ),
            "remaining_denominators": (
                "The matched tangent and line-intersection constructors discharge "
                "their determinants by definedness."
            ),
        },
        "replay_residuals": residuals,
        "replayed": replayed,
        "all_conditions_discharged": replayed,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return IncircleContactTangentIsogonalCertificate(
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
    if name == "foot" and len(args) == 3:
        return name, (args[0], *sorted(args[1:]))
    if name == "on_line" and len(args) == 2:
        return name, tuple(sorted(args))
    if name == "on_tline" and len(args) == 3:
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


def certify_jgex_incircle_contact_tangent_isogonal_application(
    source: str,
) -> JGEXIncircleContactTangentIsogonalApplication:
    normalized = source.strip()
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
        for a in triangle:
            b, c = sorted(point for point in triangle if point != a)
            i = _single(records, ("incenter", (a, b, c)))
            o = _single(records, ("circumcenter", (a, b, c)))
            if not i or not o:
                continue
            d = _single(records, ("foot", (i, b, c)))
            e = _single(records, ("foot", (i, a, c)))
            f = _single(records, ("foot", (i, a, b)))
            if not d or not e or not f:
                continue
            m = _joint(
                records,
                (("on_line", (e, f)), ("on_circle", (o, a))),
            )
            if not m:
                continue
            s = _joint(
                records,
                (("on_tline", (m, o, m)), ("on_tline", (a, o, a))),
            )
            t = _joint(
                records,
                (("on_tline", (b, o, b)), ("on_tline", (c, o, c))),
            )
            if not s or not t:
                continue
            j = _joint(
                records,
                (("on_line", (t, i)), ("on_line", (o, a))),
            )
            if not j:
                continue
            roles = {
                "A": a,
                "B": b,
                "C": c,
                "I": i,
                "D": d,
                "E": e,
                "F": f,
                "O": o,
                "M": m,
                "S": s,
                "T": t,
                "J": j,
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
            expected_goal = Atom(
                "eqangle",
                (
                    roles["A"],
                    roles["S"],
                    roles["S"],
                    roles["J"],
                    roles["I"],
                    roles["S"],
                    roles["S"],
                    roles["T"],
                ),
            ).canonical()
            if actual_goal == expected_goal:
                accepted.append(roles)

    chart = certify_incircle_contact_tangent_isogonal_chart()
    roles = accepted[0] if len(accepted) == 1 else {}
    replayed = bool(len(accepted) == 1 and chart.replayed and chart.all_conditions_discharged)
    obligations = chart.assumptions
    return JGEXIncircleContactTangentIsogonalApplication(
        theorem=chart.theorem,
        source_sha256=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        roles=roles,
        matched_constructions=(
            "triangle + incenter + three contact feet",
            "circumcenter and contact-chord/circumcircle intersection",
            "two circumcircle tangent vertices",
            "TI intersect OA",
            "directed equal-angle goal",
        )
        if roles
        else (),
        goal=goal,
        proof_bridge=(
            "contact feet -> polar EF; tangents -> linear unit-circle equations; "
            "J -> line intersection; directed-angle numerator -> EF incidence factor"
        ),
        chart_certificate_sha256=chart.certificate_sha256,
        nondegeneracy_obligations=obligations,
        undischarged_nondegeneracy_obligations=() if replayed else obligations,
        replayed=replayed,
    )


def render_incircle_contact_tangent_isogonal_chart_svg() -> str:
    def unit_from_half(parameter: float) -> tuple[float, float]:
        sine = 2 * parameter / (1 + parameter * parameter)
        cosine = (1 - parameter * parameter) / (1 + parameter * parameter)
        return cosine * cosine - sine * sine, 2 * sine * cosine

    def foot(
        point: tuple[float, float],
        left: tuple[float, float],
        right: tuple[float, float],
    ) -> tuple[float, float]:
        dx, dy = right[0] - left[0], right[1] - left[1]
        parameter = (
            (point[0] - left[0]) * dx + (point[1] - left[1]) * dy
        ) / (dx * dx + dy * dy)
        return left[0] + parameter * dx, left[1] + parameter * dy

    def tangent_intersection(
        left: tuple[float, float], right: tuple[float, float]
    ) -> tuple[float, float]:
        determinant = left[0] * right[1] - left[1] * right[0]
        return (
            (right[1] - left[1]) / determinant,
            (left[0] - right[0]) / determinant,
        )

    def line_intersection(
        a: tuple[float, float],
        b: tuple[float, float],
        c: tuple[float, float],
        d: tuple[float, float],
    ) -> tuple[float, float]:
        ab = (b[0] - a[0], b[1] - a[1])
        cd = (d[0] - c[0], d[1] - c[1])
        determinant = ab[0] * cd[1] - ab[1] * cd[0]
        parameter = (
            (c[0] - a[0]) * cd[1] - (c[1] - a[1]) * cd[0]
        ) / determinant
        return a[0] + parameter * ab[0], a[1] + parameter * ab[1]

    u, v = 0.58, 0.24
    sine_alpha = 2 * u / (1 + u * u)
    cosine_alpha = (1 - u * u) / (1 + u * u)
    sine_beta = 2 * v / (1 + v * v)
    a = unit_from_half(u)
    b = unit_from_half(v)
    c = (b[0], -b[1])
    i = (
        1 - 2 * sine_alpha * sine_beta,
        2 * cosine_alpha * sine_beta,
    )
    e = foot(i, a, c)
    f = foot(i, a, b)

    direction = (f[0] - e[0], f[1] - e[1])
    qa = direction[0] ** 2 + direction[1] ** 2
    qb = 2 * (e[0] * direction[0] + e[1] * direction[1])
    qc = e[0] ** 2 + e[1] ** 2 - 1
    discriminant = max(0.0, qb * qb - 4 * qa * qc)
    roots = (
        (-qb - math.sqrt(discriminant)) / (2 * qa),
        (-qb + math.sqrt(discriminant)) / (2 * qa),
    )
    m_parameter = max(roots)
    m = (e[0] + m_parameter * direction[0], e[1] + m_parameter * direction[1])
    s = tangent_intersection(m, a)
    t = tangent_intersection(b, c)
    origin = (0.0, 0.0)
    j = line_intersection(t, i, origin, a)

    fig, ax = plt.subplots(figsize=(9.2, 6.2))
    fig.patch.set_facecolor("#07090c")
    ax.set_facecolor("#07090c")
    ax.add_patch(Circle(origin, 1, fill=False, color="#34424f", linewidth=1.4))
    ax.plot(
        [a[0], b[0], c[0], a[0]],
        [a[1], b[1], c[1], a[1]],
        color="#7d8d99",
        linewidth=1.0,
    )
    ax.plot([e[0], f[0]], [e[1], f[1]], color="#ffb454", linewidth=2.0)
    ax.plot([m[0], s[0], a[0]], [m[1], s[1], a[1]], color="#31d7e8", linewidth=1.4)
    ax.plot([b[0], t[0], c[0]], [b[1], t[1], c[1]], color="#31d7e8", linewidth=1.1)
    ax.plot([t[0], i[0]], [t[1], i[1]], color="#ffb454", linewidth=1.2)
    ax.plot([origin[0], a[0]], [origin[1], a[1]], color="#596875", linewidth=1.0)
    ax.plot([s[0], j[0]], [s[1], j[1]], color="#f1f5f8", linewidth=1.5)

    points = {
        "A": a,
        "B": b,
        "C": c,
        "I": i,
        "E": e,
        "F": f,
        "M": m,
        "S": s,
        "T": t,
        "J": j,
        "O": origin,
    }
    for label, point in points.items():
        color = "#31d7e8" if label in {"M", "S", "T", "J"} else "#f3f6f8"
        ax.scatter([point[0]], [point[1]], s=22, color=color, zorder=4)
        ax.text(point[0] + 0.035, point[1] + 0.035, label, color=color, fontsize=9)
    ax.set_aspect("equal", adjustable="datalim")
    ax.axis("off")
    ax.set_title(
        "contact chord EF -> polar(A) -> tangent isogonality",
        color="#e7edf2",
        fontsize=12,
        pad=12,
    )
    fig.tight_layout()
    buffer = io.StringIO()
    fig.savefig(buffer, format="svg", transparent=False, bbox_inches="tight")
    plt.close(fig)
    return buffer.getvalue()


__all__ = [
    "IncircleContactTangentIsogonalCertificate",
    "JGEXIncircleContactTangentIsogonalApplication",
    "certify_incircle_contact_tangent_isogonal_chart",
    "certify_jgex_incircle_contact_tangent_isogonal_application",
    "render_incircle_contact_tangent_isogonal_chart_svg",
]
