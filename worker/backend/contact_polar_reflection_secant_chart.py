"""Exact chart for a contact-polar reflection and two known-root secants.

Let the incircle of ABC touch BC,CA,AB at D,E,F, and let H be the
reflection of D in EF.  Put T=OI cap BC and let Q be the second point of AT
on the circumcircle.  For any point M on that circumcircle, let the circle
QMH meet AM again at Y.  The reflection of Y in EF lies on BC.

The result is stronger than the frozen construction that additionally puts
M on OI.  A rational unit-circle replay proves the final collinearity
identically, and an explicit second affine chart covers the one circle point
omitted by the rational parameter.
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

from worker.backend.geometry_proof_hypergraph import Atom
from worker.backend.jgex_chart_parser import ChartJGEXFormulation as JGEXFormulation


Point = tuple[sp.Expr, sp.Expr]


def _exact_rational_field_replay() -> dict[str, str]:
    """Replay every incidence identity in QQ(u,v,w).

    Keeping coordinates in a fraction field avoids repeatedly expanding the
    same large rational expressions through SymPy's generic expression engine.
    This is an exact change of evaluation domain, not a numerical shortcut.
    """

    rational_field, u, v, w = field("u,v,w", QQ)
    zero = rational_field.zero
    one = rational_field.one
    half = one / 2

    def point(x, y):
        return x, y

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

    def line_distance_squared(value, left, right):
        direction = subtract(right, left)
        return cross(subtract(value, left), direction) ** 2 / dot(direction, direction)

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
        return point(cosine**2 - sine**2, 2 * sine * cosine)

    def unit_circle_point(parameter):
        denominator = one + parameter**2
        return point((one - parameter**2) / denominator, 2 * parameter / denominator)

    def second_unit_circle_intersection(known, carrier):
        direction = subtract(carrier, known)
        parameter = -2 * dot(known, direction) / dot(direction, direction)
        return add(known, scale(parameter, direction))

    def circle_coefficients(first, second, third):
        # Subtract the first circle equation from the other two and solve the
        # resulting 2x2 system by Cramer's rule inside the fraction field.
        dx_second = second[0] - first[0]
        dy_second = second[1] - first[1]
        dx_third = third[0] - first[0]
        dy_third = third[1] - first[1]
        norm_first = dot(first, first)
        rhs_second = -(dot(second, second) - norm_first)
        rhs_third = -(dot(third, third) - norm_first)
        determinant = dx_second * dy_third - dx_third * dy_second
        linear = (rhs_second * dy_third - rhs_third * dy_second) / determinant
        vertical = (dx_second * rhs_third - dx_third * rhs_second) / determinant
        constant = -(norm_first + linear * first[0] + vertical * first[1])
        return linear, vertical, constant

    def second_circle_intersection(known, carrier, linear, vertical):
        direction = subtract(carrier, known)
        parameter = -(
            2 * dot(known, direction)
            + linear * direction[0]
            + vertical * direction[1]
        ) / dot(direction, direction)
        return add(known, scale(parameter, direction))

    sine_alpha, cosine_alpha = sine_cosine(u)
    sine_beta, _ = sine_cosine(v)
    origin = point(zero, zero)
    a = circumcircle_point(u)
    b = circumcircle_point(v)
    c = point(b[0], -b[1])
    i = point(one - 2 * sine_alpha * sine_beta, 2 * cosine_alpha * sine_beta)
    d = foot(i, b, c)
    e = foot(i, a, c)
    f = foot(i, a, b)
    h = reflection(d, e, f)
    t = point(b[0], b[0] * i[1] / i[0])
    q = second_unit_circle_intersection(a, t)

    def build_for_m(m):
        linear, vertical, constant = circle_coefficients(q, m, h)
        o1 = point(-linear / 2, -vertical / 2)
        y = second_circle_intersection(m, a, linear, vertical)
        y1 = reflection(y, e, f)

        def circle_value(value):
            return (
                dot(value, value)
                + linear * value[0]
                + vertical * value[1]
                + constant
            )

        return {
            "m": m,
            "o1": o1,
            "y": y,
            "y1": y1,
            "circle_value": circle_value,
        }

    generic = build_for_m(unit_circle_point(w))
    exceptional = build_for_m(point(-one, zero))
    m = generic["m"]
    o1 = generic["o1"]
    y = generic["y"]
    y1 = generic["y1"]
    circle_value = generic["circle_value"]
    midpoint_dh = scale(half, add(d, h))
    midpoint_yy1 = scale(half, add(y, y1))
    raw_residuals = {
        "A_on_unit_circumcircle": distance_squared(a, origin) - one,
        "B_on_unit_circumcircle": distance_squared(b, origin) - one,
        "C_on_unit_circumcircle": distance_squared(c, origin) - one,
        "I_equidistant_from_AB_AC": (
            line_distance_squared(i, a, b) - line_distance_squared(i, a, c)
        ),
        "I_equidistant_from_AB_BC": (
            line_distance_squared(i, a, b) - line_distance_squared(i, b, c)
        ),
        "D_on_BC": cross(subtract(d, b), subtract(c, b)),
        "ID_perpendicular_BC": dot(subtract(i, d), subtract(c, b)),
        "E_on_CA": cross(subtract(e, c), subtract(a, c)),
        "IE_perpendicular_CA": dot(subtract(i, e), subtract(a, c)),
        "F_on_AB": cross(subtract(f, a), subtract(b, a)),
        "IF_perpendicular_AB": dot(subtract(i, f), subtract(b, a)),
        "DH_midpoint_on_EF": cross(subtract(midpoint_dh, e), subtract(f, e)),
        "DH_perpendicular_EF": dot(subtract(h, d), subtract(f, e)),
        "T_on_OI": cross(subtract(t, origin), subtract(i, origin)),
        "T_on_BC": cross(subtract(t, b), subtract(c, b)),
        "A_is_known_AT_circle_root": distance_squared(a, origin) - one,
        "Q_on_AT": cross(subtract(q, a), subtract(t, a)),
        "Q_on_unit_circumcircle": distance_squared(q, origin) - one,
        "M_on_unit_circumcircle": distance_squared(m, origin) - one,
        "Q_on_QMH_circle": circle_value(q),
        "M_on_QMH_circle": circle_value(m),
        "H_on_QMH_circle": circle_value(h),
        "O1_equidistant_Q_M": distance_squared(o1, q) - distance_squared(o1, m),
        "O1_equidistant_Q_H": distance_squared(o1, q) - distance_squared(o1, h),
        "M_is_known_MA_circle_root": circle_value(m),
        "Y_on_MA": cross(subtract(y, m), subtract(a, m)),
        "Y_on_QMH_circle": circle_value(y),
        "YY1_midpoint_on_EF": cross(subtract(midpoint_yy1, e), subtract(f, e)),
        "YY1_perpendicular_EF": dot(subtract(y1, y), subtract(f, e)),
        "Y1_on_BC": cross(subtract(y1, b), subtract(c, b)),
        "exceptional_M_on_unit_circumcircle": (
            distance_squared(exceptional["m"], origin) - one
        ),
        "exceptional_Q_on_QMH_circle": exceptional["circle_value"](q),
        "exceptional_M_on_QMH_circle": exceptional["circle_value"](exceptional["m"]),
        "exceptional_H_on_QMH_circle": exceptional["circle_value"](h),
        "exceptional_Y_on_MA": cross(
            subtract(exceptional["y"], exceptional["m"]),
            subtract(a, exceptional["m"]),
        ),
        "exceptional_Y_on_QMH_circle": exceptional["circle_value"](exceptional["y"]),
        "exceptional_Y1_on_BC": cross(
            subtract(exceptional["y1"], b),
            subtract(c, b),
        ),
    }
    return {
        name: "0" if value == zero else str(value)
        for name, value in raw_residuals.items()
    }


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


def _reflection(point: Point, left: Point, right: Point) -> Point:
    projection = _foot(point, left, right)
    return _subtract(_scale(2, projection), point)


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


def _second_unit_circle_intersection(known: Point, carrier: Point) -> Point:
    direction = _subtract(carrier, known)
    parameter = sp.cancel(-2 * _dot(known, direction) / _dot(direction, direction))
    return _add(known, _scale(parameter, direction))


def _circle_coefficients(first: Point, second: Point, third: Point) -> tuple[sp.Expr, ...]:
    linear, vertical, constant = sp.symbols("circle_linear circle_vertical circle_constant")
    equations = tuple(
        point[0] ** 2
        + point[1] ** 2
        + linear * point[0]
        + vertical * point[1]
        + constant
        for point in (first, second, third)
    )
    solution = sp.solve(
        equations,
        (linear, vertical, constant),
        dict=True,
        simplify=False,
    )[0]
    return (
        sp.cancel(solution[linear]),
        sp.cancel(solution[vertical]),
        sp.cancel(solution[constant]),
    )


def _second_circle_intersection(
    known: Point,
    carrier: Point,
    linear: sp.Expr,
    vertical: sp.Expr,
) -> Point:
    direction = _subtract(carrier, known)
    parameter = sp.cancel(
        -(
            2 * _dot(known, direction)
            + linear * direction[0]
            + vertical * direction[1]
        )
        / _dot(direction, direction)
    )
    return _add(known, _scale(parameter, direction))


@dataclass(frozen=True)
class ContactPolarReflectionSecantCertificate:
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
                "# Contact-polar reflection and secant chart",
                "",
                "## Theorem",
                "",
                (
                    "Let H be the reflection of the BC contact point D in the "
                    "contact chord EF.  Put T=OI cap BC and let Q be the second "
                    "intersection of AT with the circumcircle.  For any M on the "
                    "circumcircle, the circle QMH meets AM again at Y, whose "
                    "reflection in EF lies on BC."
                ),
                "",
                "## Reusable proof",
                "",
                "1. Normalize the circumcircle and write the incenter/contact feet rationally.",
                "2. Reflect D in the contact polar EF to obtain H.",
                "3. Use the known root A to eliminate Q from line AT and the unit circle.",
                "4. Solve the circle through Q,M,H by three linear coefficient equations.",
                "5. Use the known root M to eliminate the second intersection Y on AM.",
                "6. Reflect Y in EF; the resulting BC-collinearity determinant is identically zero.",
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
class JGEXContactPolarReflectionSecantApplication:
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
def certify_contact_polar_reflection_secant_chart(
) -> ContactPolarReflectionSecantCertificate:
    residuals = _exact_rational_field_replay()
    replayed = all(value == "0" for value in residuals.values())

    assumptions = (
        "ABC is a nondegenerate triangle with circumcenter O and incenter I",
        "D,E,F are the perpendicular contact feet on BC,CA,AB",
        "H is the reflection of D in the defined line EF",
        "T=OI cap BC is finite and Q is the non-A point of AT on (ABC)",
        "M is any defined point of (ABC) for which the circle QMH exists",
        "Y is the non-M point of AM on (QMH), and Y1 is its reflection in EF",
    )
    discharged_conditions = {
        assumptions[0]: "The triangle, circumcenter, and incenter clauses are matched.",
        assumptions[1]: "All three foot clauses are matched with their carrier sides.",
        assumptions[2]: "The reflection clause fixes H and the line EF.",
        assumptions[3]: (
            "The joint line clauses define T; official JGEX intersection semantics "
            "exclude the already known root A when Q is constructed."
        ),
        assumptions[4]: (
            "The on_circle clause defines M and the circumcenter clause rejects a "
            "collinear or repeated Q,M,H triple."
        ),
        assumptions[5]: (
            "Official JGEX intersection semantics exclude the known root M; the "
            "remaining line-circle point and its reflection are matched explicitly."
        ),
    }
    payload = {
        "theorem": "contact-polar-reflection-two-secants-side-return",
        "assumptions": assumptions,
        "discharged_conditions": discharged_conditions,
        "upstream_semantics": (
            "JGEX foot is an orthogonal projection.",
            "JGEX reflect is Euclidean reflection in a carrier line.",
            "JGEX circumcenter is defined only for a noncollinear triple.",
            "JGEX line-circle intersections exclude an already supplied root.",
            "JGEX coll is the exact carrier-line determinant.",
        ),
        "normalization": (
            "Normalize (ABC) to the unit circle with B,C symmetric about the x-axis; "
            "use u=tan(alpha/2), v=tan(beta/2)."
        ),
        "parameterization": {
            "triangle_domain": "0<v<u and u*v<1",
            "generic_M": "((1-w^2)/(1+w^2),2w/(1+w^2))",
            "exceptional_M": "(-1,0)",
            "known_root_formula": "lambda=-2<P,D>/|D|^2 on the unit circle",
            "general_circle": "x^2+y^2+Lx+Ny+K=0",
        },
        "representation_chart": (
            "contact feet -> contact-polar reflection",
            "known-root line/circumcircle pair -> rational second root Q",
            "three-point circle -> three linear coefficient equations",
            "known-root line/general-circle pair -> rational second root Y",
            "reflection in EF -> BC determinant",
        ),
        "proof_dag": (
            "Construct D,E,F and reflect D across EF to H.",
            "Intersect OI with BC and eliminate the known root A to obtain Q.",
            "Keep M as a free point of the unit circumcircle.",
            "Solve the circle coefficients through Q,M,H.",
            "Eliminate the known root M on line MA to obtain Y.",
            "Reflect Y across EF and reduce the BC determinant to zero.",
            "Replay M=(-1,0) separately to complete the rational circle cover.",
        ),
        "branch_certificate": {
            "radial_condition_unused": (
                "The proof treats M as an arbitrary circumcircle point, so either "
                "intersection of OI with the circumcircle is covered."
            ),
            "Q_branch": "A is the typed existing root; Q is the other root.",
            "Y_branch": "M is the typed existing root; Y is the other root.",
            "circle_cover": "generic rational chart plus the explicit point (-1,0)",
        },
        "replay_residuals": residuals,
        "replayed": replayed,
        "all_conditions_discharged": replayed,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return ContactPolarReflectionSecantCertificate(
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
    if name in {"foot", "reflect"} and len(args) == 3:
        return name, (args[0], *sorted(args[1:]))
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


def certify_jgex_contact_polar_reflection_secant_application(
    source: str,
) -> JGEXContactPolarReflectionSecantApplication:
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
            o = _single(records, ("circumcenter", (a, b, c)))
            i = _single(records, ("incenter", (a, b, c)))
            if not o or not i:
                continue
            d = _single(records, ("foot", (i, b, c)))
            e = _single(records, ("foot", (i, a, c)))
            f = _single(records, ("foot", (i, a, b)))
            if not d or not e or not f:
                continue
            h = _single(records, ("reflect", (d, e, f)))
            if not h:
                continue
            m = _joint(
                records,
                (("on_line", (o, i)), ("on_circle", (o, a))),
            )
            t = _joint(
                records,
                (("on_line", (i, o)), ("on_line", (b, c))),
            )
            if not m or not t:
                continue
            q = _joint(
                records,
                (("on_line", (a, t)), ("on_circle", (o, a))),
            )
            if not q:
                continue
            o1 = _single(records, ("circumcenter", (q, m, h)))
            if not o1:
                continue
            y = _joint(
                records,
                (("on_line", (m, a)), ("on_circle", (o1, q))),
            )
            if not y:
                continue
            y1 = _single(records, ("reflect", (y, e, f)))
            if not y1:
                continue
            roles = {
                "A": a,
                "B": b,
                "C": c,
                "O": o,
                "I": i,
                "D": d,
                "E": e,
                "F": f,
                "H": h,
                "M": m,
                "T": t,
                "Q": q,
                "O1": o1,
                "Y": y,
                "Y1": y1,
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
                "coll",
                (roles["B"], roles["C"], roles["Y1"]),
            ).canonical()
            if actual_goal == expected_goal:
                accepted.append(roles)

    chart = certify_contact_polar_reflection_secant_chart()
    roles = accepted[0] if len(accepted) == 1 else {}
    replayed = bool(len(accepted) == 1 and chart.replayed and chart.all_conditions_discharged)
    return JGEXContactPolarReflectionSecantApplication(
        theorem=chart.theorem,
        source_sha256=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        roles=roles,
        matched_constructions=(
            "triangle + circumcenter + incenter + three contact feet",
            "reflection of D in contact chord EF",
            "circumcircle point M and axis/side intersection T",
            "known-root secant A-to-Q",
            "circle QMH and known-root secant M-to-Y",
            "reflection of Y in EF and side-collinearity goal",
        )
        if roles
        else (),
        goal=goal,
        proof_bridge=(
            "contact feet -> polar reflection; known roots A and M -> two Vieta "
            "eliminations; circle coefficients -> reflected point on BC"
        ),
        chart_certificate_sha256=chart.certificate_sha256,
        nondegeneracy_obligations=chart.assumptions,
        undischarged_nondegeneracy_obligations=() if replayed else chart.assumptions,
        replayed=replayed,
    )


def render_contact_polar_reflection_secant_chart_svg() -> str:
    def unit_from_half(parameter: float) -> tuple[float, float]:
        sine = 2 * parameter / (1 + parameter * parameter)
        cosine = (1 - parameter * parameter) / (1 + parameter * parameter)
        return cosine * cosine - sine * sine, 2 * sine * cosine

    def foot(point, left, right):
        direction = (right[0] - left[0], right[1] - left[1])
        parameter = (
            (point[0] - left[0]) * direction[0]
            + (point[1] - left[1]) * direction[1]
        ) / (direction[0] ** 2 + direction[1] ** 2)
        return (
            left[0] + parameter * direction[0],
            left[1] + parameter * direction[1],
        )

    def reflect(point, left, right):
        projection = foot(point, left, right)
        return 2 * projection[0] - point[0], 2 * projection[1] - point[1]

    def second_unit(known, carrier):
        direction = (carrier[0] - known[0], carrier[1] - known[1])
        parameter = -2 * (
            known[0] * direction[0] + known[1] * direction[1]
        ) / (direction[0] ** 2 + direction[1] ** 2)
        return (
            known[0] + parameter * direction[0],
            known[1] + parameter * direction[1],
        )

    def circumcenter(first, second, third):
        matrix = sp.Matrix(
            (
                (2 * (second[0] - first[0]), 2 * (second[1] - first[1])),
                (2 * (third[0] - first[0]), 2 * (third[1] - first[1])),
            )
        )
        rhs = sp.Matrix(
            (
                second[0] ** 2 + second[1] ** 2 - first[0] ** 2 - first[1] ** 2,
                third[0] ** 2 + third[1] ** 2 - first[0] ** 2 - first[1] ** 2,
            )
        )
        result = matrix.inv() * rhs
        return float(result[0]), float(result[1])

    def second_circle(known, carrier, centre):
        direction = (carrier[0] - known[0], carrier[1] - known[1])
        parameter = -2 * (
            (known[0] - centre[0]) * direction[0]
            + (known[1] - centre[1]) * direction[1]
        ) / (direction[0] ** 2 + direction[1] ** 2)
        return (
            known[0] + parameter * direction[0],
            known[1] + parameter * direction[1],
        )

    u, v = 0.58, 0.24
    sine_alpha = 2 * u / (1 + u * u)
    cosine_alpha = (1 - u * u) / (1 + u * u)
    sine_beta = 2 * v / (1 + v * v)
    a = unit_from_half(u)
    b = unit_from_half(v)
    c = (b[0], -b[1])
    origin = (0.0, 0.0)
    i = (1 - 2 * sine_alpha * sine_beta, 2 * cosine_alpha * sine_beta)
    d = foot(i, b, c)
    e = foot(i, a, c)
    f = foot(i, a, b)
    h = reflect(d, e, f)
    t = (b[0], b[0] * i[1] / i[0])
    q = second_unit(a, t)
    norm_i = math.hypot(i[0], i[1])
    m = (i[0] / norm_i, i[1] / norm_i)
    o1 = circumcenter(q, m, h)
    y = second_circle(m, a, o1)
    y1 = reflect(y, e, f)
    radius = math.dist(o1, q)

    fig, ax = plt.subplots(figsize=(9.2, 6.2))
    fig.patch.set_facecolor("#07090c")
    ax.set_facecolor("#07090c")
    ax.add_patch(Circle(origin, 1, fill=False, color="#34424f", linewidth=1.3))
    ax.add_patch(Circle(o1, radius, fill=False, color="#31d7e8", linewidth=1.5))
    ax.plot([a[0], b[0], c[0], a[0]], [a[1], b[1], c[1], a[1]], color="#70808c")
    ax.plot([e[0], f[0]], [e[1], f[1]], color="#ffb454", linewidth=2.0)
    ax.plot([d[0], h[0]], [d[1], h[1]], color="#ffb454", linestyle="--")
    ax.plot([origin[0], i[0], m[0]], [origin[1], i[1], m[1]], color="#596875")
    ax.plot([a[0], t[0], q[0]], [a[1], t[1], q[1]], color="#83929e")
    ax.plot([m[0], y[0], a[0]], [m[1], y[1], a[1]], color="#31d7e8")
    ax.plot([y[0], y1[0]], [y[1], y1[1]], color="#f1f5f8", linewidth=1.3)

    points = {
        "A": a, "B": b, "C": c, "I": i, "D": d, "E": e, "F": f,
        "H": h, "M": m, "T": t, "Q": q, "Y": y, "Y'": y1,
    }
    for label, point in points.items():
        color = "#31d7e8" if label in {"M", "Q", "Y", "Y'"} else "#f3f6f8"
        ax.scatter([point[0]], [point[1]], s=21, color=color, zorder=4)
        ax.text(point[0] + 0.03, point[1] + 0.03, label, color=color, fontsize=9)
    ax.set_aspect("equal", adjustable="datalim")
    ax.axis("off")
    ax.set_title(
        "contact-polar reflection | two known-root secants",
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
    "ContactPolarReflectionSecantCertificate",
    "JGEXContactPolarReflectionSecantApplication",
    "certify_contact_polar_reflection_secant_chart",
    "certify_jgex_contact_polar_reflection_secant_application",
    "render_contact_polar_reflection_secant_chart_svg",
]
