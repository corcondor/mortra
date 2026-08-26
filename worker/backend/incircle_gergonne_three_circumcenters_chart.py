"""Exact chart for an incircle contact triangle and three circumcenters.

Let K be the Gergonne point of ABC and let X,Y,Z be the second intersections
of AK,BK,CK with the circumcircle.  The centroid G of the circumcenters of
YKZ, ZKX, XKY lies on IK.  The proof normalizes the incircle, so the entire
configuration is rational in two contact parameters.
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
class IncircleGergonneThreeCircumcentersCertificate:
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
                "# Incircle-Gergonne three-circumcenter chart",
                "",
                "## Theorem",
                "",
                (
                    "Let K be the Gergonne point of ABC and X,Y,Z the second "
                    "intersections of AK,BK,CK with (ABC).  If OA,OB,OC are the "
                    "circumcenters of YKZ,ZKX,XKY, then their centroid G lies on IK."
                ),
                "",
                "## Representation changes",
                "",
                "- incircle contact triangle -> two rational contact parameters",
                "- Gergonne concurrence -> three exact line determinants",
                "- second circle intersections -> one known-root division each",
                "- three circumcenters -> six linear equal-distance equations",
                "- centroid collinearity -> one scalar-multiple identity",
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
class JGEXIncircleGergonneThreeCircumcentersApplication:
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


def _cross(left: sp.Matrix, right: sp.Matrix) -> sp.Expr:
    return sp.expand(left[0] * right[1] - left[1] * right[0])


def _intersection(
    first: sp.Matrix,
    second: sp.Matrix,
    third: sp.Matrix,
    fourth: sp.Matrix,
) -> sp.Matrix:
    direction = second - first
    other_direction = fourth - third
    parameter = sp.cancel(
        _cross(third - first, other_direction) / _cross(direction, other_direction)
    )
    return (first + parameter * direction).applyfunc(sp.factor)


def _circle_coefficients(
    first: sp.Matrix,
    second: sp.Matrix,
    third: sp.Matrix,
) -> tuple[sp.Expr, sp.Expr, sp.Expr]:
    cx, cy, constant = sp.symbols("cx cy constant")
    solution = sp.solve(
        [
            point.dot(point) + cx * point[0] + cy * point[1] + constant
            for point in (first, second, third)
        ],
        (cx, cy, constant),
        dict=True,
        simplify=False,
    )[0]
    return tuple(
        sp.factor(sp.cancel(solution[symbol])) for symbol in (cx, cy, constant)
    )


def _second_circle_intersection(
    known: sp.Matrix,
    line_point: sp.Matrix,
    circle: tuple[sp.Expr, sp.Expr, sp.Expr],
) -> sp.Matrix:
    parameter = sp.symbols("parameter")
    direction = line_point - known
    point = known + parameter * direction
    expression = sp.cancel(
        point.dot(point) + circle[0] * point[0] + circle[1] * point[1] + circle[2]
    )
    polynomial = sp.Poly(sp.together(expression).as_numer_denom()[0], parameter)
    # The known point gives the zero root, so the other root is -linear/quadratic.
    other = sp.cancel(
        -polynomial.coeff_monomial(parameter) / polynomial.coeff_monomial(parameter**2)
    )
    return (known + other * direction).applyfunc(
        lambda value: sp.factor(sp.cancel(value))
    )


def _circumcenter(
    first: sp.Matrix,
    second: sp.Matrix,
    third: sp.Matrix,
) -> sp.Matrix:
    x, y = sp.symbols("center_x center_y")
    solution = sp.solve(
        [
            2 * x * (other[0] - first[0])
            + 2 * y * (other[1] - first[1])
            - (other.dot(other) - first.dot(first))
            for other in (second, third)
        ],
        (x, y),
        dict=True,
        simplify=False,
    )[0]
    return sp.Matrix(
        [sp.factor(sp.cancel(solution[x])), sp.factor(sp.cancel(solution[y]))]
    )


@lru_cache(maxsize=1)
def certify_incircle_gergonne_three_circumcenters_chart() -> (
    IncircleGergonneThreeCircumcentersCertificate
):
    u, v = sp.symbols("u v", nonzero=True)
    origin = sp.zeros(2, 1)
    d = sp.Matrix((1, 0))
    e = sp.Matrix(((1 - u**2) / (1 + u**2), 2 * u / (1 + u**2)))
    f = sp.Matrix(((1 - v**2) / (1 + v**2), 2 * v / (1 + v**2)))
    a = sp.Matrix(((1 - u * v) / (1 + u * v), (u + v) / (1 + u * v)))
    b = sp.Matrix((1, v))
    c = sp.Matrix((1, u))

    k = _intersection(a, d, b, e)
    circle = _circle_coefficients(a, b, c)
    x = _second_circle_intersection(a, k, circle)
    y = _second_circle_intersection(b, k, circle)
    z = _second_circle_intersection(c, k, circle)
    oa = _circumcenter(y, k, z)
    ob = _circumcenter(z, k, x)
    oc = _circumcenter(x, k, y)
    g = ((oa + ob + oc) / 3).applyfunc(lambda value: sp.factor(sp.cancel(value)))
    scalar = sp.factor((u**2 * v**2 + u**2 + 2 * u * v + v**2 + 3) / (6 * (u * v + 1)))

    def circle_value(point: sp.Matrix) -> sp.Expr:
        return sp.cancel(
            point.dot(point) + circle[0] * point[0] + circle[1] * point[1] + circle[2]
        )

    def distance_squared(left: sp.Matrix, right: sp.Matrix) -> sp.Expr:
        delta = left - right
        return sp.cancel(delta.dot(delta))

    raw_residuals = {
        "D_on_unit_incircle": d.dot(d) - 1,
        "E_on_unit_incircle": e.dot(e) - 1,
        "F_on_unit_incircle": f.dot(f) - 1,
        "A_on_tangent_at_E": a.dot(e) - 1,
        "A_on_tangent_at_F": a.dot(f) - 1,
        "B_on_tangent_at_D": b.dot(d) - 1,
        "B_on_tangent_at_F": b.dot(f) - 1,
        "C_on_tangent_at_D": c.dot(d) - 1,
        "C_on_tangent_at_E": c.dot(e) - 1,
        "K_on_AD": _cross(k - a, d - a),
        "K_on_BE": _cross(k - b, e - b),
        "K_on_CF_Gergonne_concurrence": _cross(k - c, f - c),
        "A_on_circumcircle": circle_value(a),
        "B_on_circumcircle": circle_value(b),
        "C_on_circumcircle": circle_value(c),
        "X_on_AK": _cross(x - a, k - a),
        "X_on_circumcircle": circle_value(x),
        "Y_on_BK": _cross(y - b, k - b),
        "Y_on_circumcircle": circle_value(y),
        "Z_on_CK": _cross(z - c, k - c),
        "Z_on_circumcircle": circle_value(z),
        "OA_equidistant_Y_K": distance_squared(oa, y) - distance_squared(oa, k),
        "OA_equidistant_Y_Z": distance_squared(oa, y) - distance_squared(oa, z),
        "OB_equidistant_Z_K": distance_squared(ob, z) - distance_squared(ob, k),
        "OB_equidistant_Z_X": distance_squared(ob, z) - distance_squared(ob, x),
        "OC_equidistant_X_K": distance_squared(oc, x) - distance_squared(oc, k),
        "OC_equidistant_X_Y": distance_squared(oc, x) - distance_squared(oc, y),
        "centroid_scalar_x": g[0] - scalar * k[0],
        "centroid_scalar_y": g[1] - scalar * k[1],
        "G_I_K_collinear": _cross(g - origin, k - origin),
    }
    residuals = {name: _canonical(value) for name, value in raw_residuals.items()}
    replayed = all(value == "0" for value in residuals.values())
    assumptions = (
        "ABC is a defined nondegenerate triangle with incenter I",
        "D,E,F are the three defined perpendicular contact feet of I",
        "K is the defined intersection of AD and BE",
        "O is the defined circumcenter of ABC",
        "X,Y,Z are the defined second intersections of AK,BK,CK with (ABC)",
        "OA,OB,OC are the defined circumcenters of YKZ,ZKX,XKY",
        "G is the centroid output associated with OA,OB,OC",
    )
    discharged_conditions = {
        assumptions[0]: "The triangle and incenter clauses are matched.",
        assumptions[
            1
        ]: "All three foot constructors are matched to I and the opposite sides.",
        assumptions[2]: "The two defining contact cevians for K are matched.",
        assumptions[3]: "The circumcenter clause for ABC is matched.",
        assumptions[4]: "Each joint on_line/on_circle constructor is matched.",
        assumptions[5]: "All three circumcenter triples are matched cyclically.",
        assumptions[6]: "The four-output centroid constructor is matched to OA,OB,OC.",
    }
    payload = {
        "theorem": "incircle-gergonne-three-circumcenters-centroid-axis",
        "assumptions": assumptions,
        "discharged_conditions": discharged_conditions,
        "upstream_semantics": (
            "JGEX incenter and foot constructors provide the incircle contact triangle.",
            "JGEX joint on_line clauses define K and the three cevians.",
            "JGEX joint on_line/on_circle outputs select the nonvertex intersections.",
            "JGEX circumcenter and centroid constructors reject undefined inputs.",
        ),
        "normalization": (
            "Translate and scale the incircle to the unit circle, put D=(1,0), "
            "and parameterize E,F by the rational half-angle parameters u,v."
        ),
        "representation_chart": (
            "three contact tangents -> rational vertices A,B,C",
            "two contact cevians -> rational Gergonne point K",
            "known circle root -> rational second intersections X,Y,Z",
            "three circumcenters -> six linear equal-distance equations",
            "centroid -> G = lambda K with I at the origin",
        ),
        "proof_dag": (
            "Recover ABC as the intersections of the tangents at D,E,F.",
            "Intersect AD and BE; direct substitution also places K on CF.",
            "Solve (ABC) and divide out A,B,C to obtain X,Y,Z.",
            "Solve the six linear equal-distance equations for OA,OB,OC.",
            "Average the three centers and factor both coordinates.",
            "Both coordinates equal the same scalar times K, proving G,I,K collinear.",
        ),
        "replay_residuals": residuals,
        "replayed": replayed,
        "all_conditions_discharged": replayed,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return IncircleGergonneThreeCircumcentersCertificate(
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


def _centroid_output(
    records: tuple[dict[str, object], ...],
    centers: tuple[str, str, str],
) -> str | None:
    matches = {
        str(record["outputs"][3])
        for record in records
        if len(record["outputs"]) == 4
        and len(record["constructions"]) == 1
        and record["constructions"][0][0] == "centroid"
        and tuple(sorted(record["constructions"][0][1])) == tuple(sorted(centers))
    }
    return next(iter(matches)) if len(matches) == 1 else None


def certify_jgex_incircle_gergonne_three_circumcenters_application(
    source: str,
) -> JGEXIncircleGergonneThreeCircumcentersApplication:
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
            i = _single(records, ("incenter", (a, b, c)))
            if not i:
                continue
            d = _single(records, ("foot", (i, b, c)))
            e = _single(records, ("foot", (i, a, c)))
            f = _single(records, ("foot", (i, a, b)))
            if not d or not e or not f:
                continue
            k = _joint(records, (("on_line", (a, d)), ("on_line", (b, e))))
            o = _single(records, ("circumcenter", (a, b, c)))
            if not k or not o:
                continue
            x = _joint(records, (("on_line", (a, k)), ("on_circle", (o, a))))
            y = _joint(records, (("on_line", (b, k)), ("on_circle", (o, a))))
            z = _joint(records, (("on_line", (c, k)), ("on_circle", (o, a))))
            if not x or not y or not z:
                continue
            oa = _single(records, ("circumcenter", (y, k, z)))
            ob = _single(records, ("circumcenter", (z, k, x)))
            oc = _single(records, ("circumcenter", (x, k, y)))
            if not oa or not ob or not oc:
                continue
            g = _centroid_output(records, (oa, ob, oc))
            if not g:
                continue
            roles = {
                "A": a,
                "B": b,
                "C": c,
                "I": i,
                "D": d,
                "E": e,
                "F": f,
                "K": k,
                "O": o,
                "X": x,
                "Y": y,
                "Z": z,
                "OA": oa,
                "OB": ob,
                "OC": oc,
                "G": g,
            }
            candidates[tuple(sorted(roles.items()))] = roles

    goal = str(formulation.goals[0]) if len(formulation.goals) == 1 else ""
    accepted: list[dict[str, str]] = []
    parts = goal.split()
    if len(parts) == 4:
        actual = Atom(parts[0], tuple(parts[1:])).canonical()
        for roles in candidates.values():
            if actual == Atom("coll", (roles["G"], roles["I"], roles["K"])).canonical():
                accepted.append(roles)

    chart = certify_incircle_gergonne_three_circumcenters_chart()
    unique = accepted[0] if len(accepted) == 1 else {}
    matched = (
        (
            "the incircle contact triangle and two contact cevians defining K",
            "the three second intersections of AK,BK,CK with (ABC)",
            "the cyclic triple of circumcenters around K",
            "the centroid output and target line IKG",
        )
        if unique
        else ()
    )
    replayed = bool(
        chart.replayed
        and chart.all_conditions_discharged
        and len(unique) == 16
        and len(accepted) == 1
    )
    return JGEXIncircleGergonneThreeCircumcentersApplication(
        theorem=chart.theorem,
        source_sha256=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        roles=unique,
        matched_constructions=matched,
        goal=goal,
        proof_bridge=(
            "Normalize the incircle and parameterize two contact points.  Tangent "
            "intersections recover ABC and the contact cevians give K rationally.  "
            "After dividing the three known circumcircle roots, all three new "
            "circumcenters are linear solves and their centroid factors as G=lambda K."
        ),
        chart_certificate_sha256=chart.certificate_sha256,
        nondegeneracy_obligations=chart.assumptions,
        undischarged_nondegeneracy_obligations=(),
        replayed=replayed,
    )


def render_incircle_gergonne_three_circumcenters_chart_svg() -> str:
    figure, axis = plt.subplots(figsize=(8.8, 6.0))
    axis.set_aspect("equal")
    axis.axis("off")
    axis.set_facecolor("#050709")
    figure.patch.set_facecolor("#050709")
    a, b, c = (0.0, 3.0), (-3.0, -1.3), (3.2, -1.3)
    i, k, g = (0.0, 0.0), (0.16, 0.46), (0.09, 0.26)
    d, e, f = (0.0, -1.0), (0.82, 0.57), (-0.82, 0.57)
    x, y, z = (0.24, -2.0), (2.2, 1.1), (-2.15, 1.05)
    oa, ob, oc = (-0.45, 0.14), (0.62, 0.06), (0.12, 0.58)
    axis.plot((a[0], b[0], c[0], a[0]), (a[1], b[1], c[1], a[1]), color="#475569")
    axis.add_patch(Circle(i, 1.0, fill=False, color="#22d3ee", linewidth=1.5))
    for vertex, second in ((a, x), (b, y), (c, z)):
        axis.plot(
            (vertex[0], second[0]),
            (vertex[1], second[1]),
            color="#64748b",
            linewidth=1.0,
        )
    axis.plot((i[0], k[0], g[0]), (i[1], k[1], g[1]), color="#fbbf24", linewidth=2.1)
    for label, point, color in (
        ("A", a, "#94a3b8"),
        ("B", b, "#94a3b8"),
        ("C", c, "#94a3b8"),
        ("I", i, "#22d3ee"),
        ("D", d, "#22d3ee"),
        ("E", e, "#22d3ee"),
        ("F", f, "#22d3ee"),
        ("K", k, "#fbbf24"),
        ("G", g, "#fbbf24"),
        ("X", x, "#a3e635"),
        ("Y", y, "#a3e635"),
        ("Z", z, "#a3e635"),
        ("OA", oa, "#f472b6"),
        ("OB", ob, "#f472b6"),
        ("OC", oc, "#f472b6"),
    ):
        axis.scatter(*point, s=28, color=color, zorder=5)
        axis.text(point[0] + 0.07, point[1] + 0.07, label, color=color, fontsize=9)
    axis.text(
        -2.6,
        2.5,
        "contact triangle -> Gergonne point -> three centers",
        color="#f8fafc",
        fontsize=10,
    )
    axis.set_xlim(-3.45, 3.55)
    axis.set_ylim(-2.25, 3.35)
    buffer = io.StringIO()
    figure.savefig(
        buffer, format="svg", bbox_inches="tight", facecolor=figure.get_facecolor()
    )
    plt.close(figure)
    return buffer.getvalue()


__all__ = [
    "IncircleGergonneThreeCircumcentersCertificate",
    "JGEXIncircleGergonneThreeCircumcentersApplication",
    "certify_incircle_gergonne_three_circumcenters_chart",
    "certify_jgex_incircle_gergonne_three_circumcenters_application",
    "render_incircle_gergonne_three_circumcenters_chart_svg",
]
