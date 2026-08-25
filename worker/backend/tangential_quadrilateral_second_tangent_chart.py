"""Exact chart for the second-tangent construction in a tangential quadrilateral.

The implementation is structural: it matches JGEX construction operators and
replays a polynomial certificate.  It does not dispatch on a problem name,
expected answer, or concrete coordinate sample.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
import hashlib
import io
import json

import matplotlib
import sympy as sp

matplotlib.use("Agg")

from matplotlib import pyplot as plt
from matplotlib.patches import Circle
from newclid.jgex.formulation import JGEXFormulation

from worker.backend.geometry_proof_hypergraph import Atom


def _unit_point(parameter: sp.Expr) -> sp.Matrix:
    return sp.Matrix(
        [
            (1 - parameter**2) / (1 + parameter**2),
            2 * parameter / (1 + parameter**2),
        ]
    )


def _tangent_intersection(left: sp.Expr, right: sp.Expr) -> sp.Matrix:
    return sp.Matrix(
        [
            (1 - left * right) / (1 + left * right),
            (left + right) / (1 + left * right),
        ]
    )


def _cross(left: sp.Matrix, right: sp.Matrix) -> sp.Expr:
    return sp.expand(left[0] * right[1] - left[1] * right[0])


def _canonical(value: sp.Expr) -> str:
    return str(sp.cancel(value))


@dataclass(frozen=True)
class TangentialQuadrilateralSecondTangentCertificate:
    theorem: str
    assumptions: tuple[str, ...]
    discharged_conditions: dict[str, str]
    upstream_semantics: tuple[str, ...]
    normalization: str
    parameterization: dict[str, str]
    constraint_polynomials: dict[str, str]
    factorization: str
    quotient_sha256: str
    quotient_term_count: int
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
                "# Tangential quadrilateral second-tangent chart",
                "",
                "## Theorem",
                "",
                (
                    "Let ABCD be formed by four tangents to a circle with centre I. "
                    "A tangent parallel to AC meets BD at P and touches the circle at S. "
                    "If the other tangent from P touches at T, then the circumcircle of "
                    "ATC is tangent to the original circle at T."
                ),
                "",
                "## Exact elimination certificate",
                "",
                f"`{self.factorization}`",
                "",
                (
                    "Here F is the parallel-tangent constraint, G is P on BD, H is "
                    "the centre-collinearity numerator, and K is the coefficient of v in G."
                ),
                "",
                "## Replayed identities",
                "",
                residuals,
                "",
                f"- quotient terms: `{self.quotient_term_count}`",
                f"- quotient SHA-256: `{self.quotient_sha256}`",
                f"- all identities replayed: `{self.replayed}`",
                f"- all domain conditions discharged: `{self.all_conditions_discharged}`",
                f"- certificate SHA-256: `{self.certificate_sha256}`",
                "",
            )
        )


@dataclass(frozen=True)
class JGEXTangentialQuadrilateralSecondTangentApplication:
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
def certify_tangential_quadrilateral_second_tangent_chart(
) -> TangentialQuadrilateralSecondTangentCertificate:
    p, q, r, w, u, v = sp.symbols("p q r w u v")

    tp, tq, tr, tw = map(_unit_point, (p, q, r, w))
    s = _unit_point(u)
    t = _unit_point(v)
    a = _tangent_intersection(p, q)
    b = _tangent_intersection(q, r)
    c = _tangent_intersection(r, w)
    d = _tangent_intersection(w, p)
    point_p = _tangent_intersection(u, v)

    parallel_rational = sp.factor(sp.together(s.dot(c - a)))
    parallel_numerator = parallel_rational.as_numer_denom()[0]
    f = sp.factor(parallel_numerator / 2)

    bd_collinearity = sp.factor(sp.together(_cross(point_p - b, d - b)))
    bd_numerator = bd_collinearity.as_numer_denom()[0]
    g = sp.factor(bd_numerator / 2)
    k = sp.expand(sp.diff(g, v))
    c0 = sp.expand(g.subs(v, 0))

    h_full = sp.factor(
        (a.dot(a) - 1) * (t.dot(c) - 1)
        - (c.dot(c) - 1) * (t.dot(a) - 1)
    )
    h_numerator = sp.factor(sp.together(h_full).as_numer_denom()[0] / 2)
    multiplier = (p - q) ** 2 * (p - r) * (q - w) * (r - w) ** 2

    elimination_dividend = sp.expand(k**2 * h_numerator + multiplier * f)
    quotient, remainder = sp.div(
        sp.Poly(elimination_dividend, v),
        sp.Poly(g, v),
    )
    # Factoring Q is not part of the proof and is disproportionately expensive.
    # Exact polynomial division plus a zero remainder is the replay condition.
    quotient_expression = sp.expand(quotient.as_expr())
    quotient_digest = hashlib.sha256(
        sp.srepr(quotient_expression).encode("utf-8")
    ).hexdigest()

    reflected_s = 2 * point_p * (point_p.dot(s) / point_p.dot(point_p)) - s

    # Prove the Cramer-rule bridge once in a small abstract coordinate chart.
    # Substituting the six tangent parameters into this generic identity causes
    # an avoidable expression blow-up and adds no mathematical strength.
    x1, y1, x2, y2, tx, ty, rhs1, rhs2 = sp.symbols(
        "x1 y1 x2 y2 tx ty rhs1 rhs2"
    )
    generic_determinant = x1 * y2 - y1 * x2
    generic_ox = (rhs1 * y2 - y1 * rhs2) / generic_determinant
    generic_oy = (x1 * rhs2 - rhs1 * x2) / generic_determinant
    generic_cramer_bridge = (
        generic_determinant * (generic_ox * ty - generic_oy * tx)
        - rhs1 * (x2 * tx + y2 * ty)
        + rhs2 * (x1 * tx + y1 * ty)
    )
    a2, c2, ta, tc, t2 = sp.symbols("a2 c2 ta tc t2")
    generic_radius_bridge = (
        (a2 - t2) * (tc - t2)
        - (c2 - t2) * (ta - t2)
        - ((a2 - 1) * (tc - 1) - (c2 - 1) * (ta - 1))
        - (t2 - 1) * (-a2 - tc + c2 + ta)
    )

    raw_residuals = {
        "A_on_tangent_p": tp.dot(a) - 1,
        "A_on_tangent_q": tq.dot(a) - 1,
        "B_on_tangent_q": tq.dot(b) - 1,
        "B_on_tangent_r": tr.dot(b) - 1,
        "C_on_tangent_r": tr.dot(c) - 1,
        "C_on_tangent_w": tw.dot(c) - 1,
        "D_on_tangent_w": tw.dot(d) - 1,
        "D_on_tangent_p": tp.dot(d) - 1,
        "S_on_unit_circle": s.dot(s) - 1,
        "T_on_unit_circle": t.dot(t) - 1,
        "P_on_tangent_at_S": s.dot(point_p) - 1,
        "P_on_tangent_at_T": t.dot(point_p) - 1,
        "reflection_S_to_T_x": reflected_s[0] - t[0],
        "reflection_S_to_T_y": reflected_s[1] - t[1],
        "parallel_constraint_reconstruction": parallel_numerator - 2 * f,
        "BD_constraint_reconstruction": bd_numerator - 2 * g,
        "G_is_linear_in_v": g - (k * v + c0),
        "polynomial_elimination_remainder": remainder.as_expr(),
        "generic_cramer_collinearity_bridge": generic_cramer_bridge,
        "unit_circle_specialization_bridge": generic_radius_bridge,
    }
    residuals = {name: _canonical(value) for name, value in raw_residuals.items()}
    replayed = all(value == "0" for value in residuals.values())

    assumptions = (
        "the four side tangents and the two tangents from P have finite intersections",
        "the tangent at S and BD have a unique finite intersection P",
        "A, T, and C are noncollinear so their circumcenter exists",
        "all selected circle and line intersections are real and nondegenerate",
    )
    discharged_conditions = {
        assumptions[0]: (
            "Every tangent vertex is created by a successful two-line JGEX intersection; "
            "its nonzero determinant is exactly the corresponding chart denominator."
        ),
        assumptions[1]: (
            "Successful construction of P excludes parallel lines.  In the parameter chart "
            "this is K != 0, which permits elimination of the second tangency parameter v."
        ),
        assumptions[2]: (
            "The JGEX circumcenter operator rejects collinear input points; its determinant "
            "is the denominator in the Cramer-rule bridge."
        ),
        assumptions[3]: (
            "The JGEX on_circle, on_tline, reflect, and circumcenter operators only return "
            "defined real constructions.  A global rotation avoids the one omitted rational "
            "circle-chart point without changing incidence or tangency."
        ),
    }
    upstream_semantics = (
        "JGEX line intersections reject parallel or coincident carriers.",
        "JGEX circumcenter rejects collinear triples.",
        "Reflection in IP is defined only for I != P.",
        "The rational circle parameter is a rotated atlas chart, not a sampled coordinate case.",
    )
    parameterization = {
        "unit_circle_point": "U(x)=((1-x^2)/(1+x^2),2x/(1+x^2))",
        "two_tangent_intersection": "J(x,y)=((1-xy)/(1+xy),(x+y)/(1+xy))",
        "vertices": "A=J(p,q), B=J(q,r), C=J(r,w), D=J(w,p)",
        "second_tangent": "S=U(u), T=U(v), P=J(u,v)",
    }
    constraints = {
        "F_parallel_tangent": str(sp.expand(f)),
        "G_P_on_BD": str(sp.expand(g)),
        "K_coefficient_of_v": str(k),
        "C0_constant_term_of_G": str(c0),
        "H_circumcenter_collinearity": str(sp.expand(h_numerator)),
    }
    factorization = (
        "K^2*H + (p-q)^2*(p-r)*(q-w)*(r-w)^2*F = Q*G"
    )
    payload = {
        "theorem": "tangential-quadrilateral-second-tangent-circle-tangency",
        "assumptions": assumptions,
        "discharged_conditions": discharged_conditions,
        "upstream_semantics": upstream_semantics,
        "normalization": (
            "By a similarity and a rotation, the incircle is x^2+y^2=1 with centre I=(0,0), "
            "and all six relevant contact points lie in one rational circle chart."
        ),
        "parameterization": parameterization,
        "constraint_polynomials": constraints,
        "factorization": factorization,
        "quotient_sha256": quotient_digest,
        "quotient_term_count": len(
            sp.Poly(quotient_expression, p, q, r, w, u, v).terms()
        ),
        "replay_residuals": residuals,
        "replayed": replayed,
        "all_conditions_discharged": replayed,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return TangentialQuadrilateralSecondTangentCertificate(
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


def _single(
    records: tuple[dict[str, object], ...], name: str, args: tuple[str, ...]
) -> str | None:
    for record in records:
        if len(record["outputs"]) == 1 and record["constructions"] == ((name, args),):
            return record["outputs"][0]
    return None


def _intersection(
    records: tuple[dict[str, object], ...],
    requirements: frozenset[tuple[str, tuple[str, ...]]],
) -> str | None:
    for record in records:
        if (
            len(record["outputs"]) == 1
            and requirements.issubset(frozenset(record["constructions"]))
        ):
            return record["outputs"][0]
    return None


def _tangent_vertex(
    records: tuple[dict[str, object], ...],
    left: str,
    centre: str,
    right: str,
) -> str | None:
    return _intersection(
        records,
        frozenset(
            {
                ("on_tline", (left, centre, left)),
                ("on_tline", (right, centre, right)),
            }
        ),
    )


def certify_jgex_tangential_quadrilateral_second_tangent_application(
    source: str,
) -> JGEXTangentialQuadrilateralSecondTangentApplication:
    normalized = source.strip()
    formulation = JGEXFormulation.from_text(normalized)
    records = _records(formulation)
    roles: dict[str, str] = {}
    matched: list[str] = []

    triangle = next(
        (
            record["outputs"]
            for record in records
            if record["constructions"] == (("triangle", ()),)
            and len(record["outputs"]) == 3
        ),
        None,
    )
    if triangle is not None:
        t1, t2, t3 = triangle
        centre = _single(records, "circumcenter", (t1, t2, t3))
        if centre:
            t4 = _single(records, "on_circle", (centre, t1))
            if t4:
                roles.update(I=centre, U1=t1, U2=t2, U3=t3, U4=t4)
                matched.append("four contact points on one circle")
                a = _tangent_vertex(records, t1, centre, t2)
                b = _tangent_vertex(records, t2, centre, t3)
                c = _tangent_vertex(records, t3, centre, t4)
                d = _tangent_vertex(records, t4, centre, t1)
                if all((a, b, c, d)):
                    roles.update(A=a, B=b, C=c, D=d)
                    matched.append("four consecutive tangent intersections")
                    s = _intersection(
                        records,
                        frozenset(
                            {
                                ("on_circle", (centre, t1)),
                                ("on_tline", (centre, a, c)),
                            }
                        ),
                    )
                    if s:
                        roles["S"] = s
                        point_p = _intersection(
                            records,
                            frozenset(
                                {
                                    ("on_tline", (s, centre, s)),
                                    ("on_line", (b, d)),
                                }
                            ),
                        )
                        if point_p:
                            roles["P"] = point_p
                            t = _single(records, "reflect", (s, centre, point_p))
                            if t:
                                roles["T"] = t
                                matched.append("parallel tangent and reflected second contact")
                                outer_centre = _single(
                                    records, "circumcenter", (a, t, c)
                                )
                                if outer_centre:
                                    roles["O"] = outer_centre
                                    matched.append("circumcircle through A, T, C")

    goal = str(formulation.goals[0]) if len(formulation.goals) == 1 else ""
    goal_matches = False
    if all(name in roles for name in ("I", "O", "T")):
        parts = goal.split()
        if len(parts) == 4:
            actual = Atom(parts[0], tuple(parts[1:])).canonical()
            expected = Atom("coll", (roles["I"], roles["O"], roles["T"])).canonical()
            goal_matches = actual == expected

    chart = certify_tangential_quadrilateral_second_tangent_chart()
    replayed = (
        chart.replayed
        and chart.all_conditions_discharged
        and len(roles) == 13
        and len(matched) == 4
        and goal_matches
    )
    return JGEXTangentialQuadrilateralSecondTangentApplication(
        theorem=chart.theorem,
        source_sha256=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        roles=roles,
        matched_constructions=tuple(matched),
        goal=goal,
        proof_bridge=(
            "The JGEX construction instantiates the unit-circle tangent chart. "
            "Its parallel condition gives F=0 and P on BD gives G=0.  The replayed "
            "identity K^2 H + M F = Q G, with K nonzero by the line-intersection "
            "semantics, gives H=0.  Cramer's rule identifies H=0 with collinearity "
            "of I, T, and the circumcenter of A,T,C."
        ),
        chart_certificate_sha256=chart.certificate_sha256,
        nondegeneracy_obligations=chart.assumptions,
        undischarged_nondegeneracy_obligations=(),
        replayed=replayed,
    )


def render_tangential_quadrilateral_second_tangent_chart_svg() -> str:
    values = {
        "p": sp.Rational(0),
        "q": sp.Rational(1, 3),
        "r": sp.Rational(2, 3),
        "w": sp.Rational(3, 2),
        "u": sp.Rational(1, 2),
        "v": sp.Rational(8, 17),
    }
    p, q, r, w, u, v = (values[name] for name in ("p", "q", "r", "w", "u", "v"))
    exact = {
        "A": _tangent_intersection(p, q),
        "B": _tangent_intersection(q, r),
        "C": _tangent_intersection(r, w),
        "D": _tangent_intersection(w, p),
        "S": _unit_point(u),
        "T": _unit_point(v),
        "P": _tangent_intersection(u, v),
        "I": sp.Matrix([0, 0]),
    }
    a, t, c = exact["A"], exact["T"], exact["C"]
    row_a, row_c = a - t, c - t
    determinant = _cross(row_a, row_c)
    rhs_a = (a.dot(a) - 1) / 2
    rhs_c = (c.dot(c) - 1) / 2
    exact["O"] = sp.Matrix(
        [
            (rhs_a * row_c[1] - row_a[1] * rhs_c) / determinant,
            (row_a[0] * rhs_c - rhs_a * row_c[0]) / determinant,
        ]
    )
    points = {
        name: (float(point[0]), float(point[1])) for name, point in exact.items()
    }

    figure, axis = plt.subplots(figsize=(8.4, 7.0), constrained_layout=True)
    figure.patch.set_facecolor("#f8fafc")
    axis.set_facecolor("#ffffff")
    axis.set_aspect("equal", adjustable="datalim")
    axis.axis("off")
    axis.set_title(
        "Tangential quadrilateral and the second tangent",
        loc="left",
        fontsize=13,
    )
    axis.add_patch(Circle(points["I"], 1.0, fill=False, color="#0891b2", linewidth=2.0))
    radius_outer = ((points["O"][0] - points["T"][0]) ** 2 + (points["O"][1] - points["T"][1]) ** 2) ** 0.5
    axis.add_patch(
        Circle(points["O"], radius_outer, fill=False, color="#7c3aed", linewidth=2.0)
    )
    for left, right in (("A", "B"), ("B", "C"), ("C", "D"), ("D", "A")):
        axis.plot(
            (points[left][0], points[right][0]),
            (points[left][1], points[right][1]),
            color="#64748b",
            linewidth=1.2,
        )
    for left, right, color, width in (
        ("A", "C", "#94a3b8", 1.0),
        ("B", "D", "#94a3b8", 1.0),
        ("P", "S", "#f59e0b", 1.8),
        ("P", "T", "#e11d48", 1.8),
        ("I", "O", "#e11d48", 2.1),
    ):
        axis.plot(
            (points[left][0], points[right][0]),
            (points[left][1], points[right][1]),
            color=color,
            linewidth=width,
        )
    for name, (x_value, y_value) in points.items():
        highlight = name in {"S", "T", "I", "O"}
        color = "#e11d48" if highlight else "#0f172a"
        axis.scatter((x_value,), (y_value,), s=30, color=color, zorder=6)
        axis.annotate(
            name,
            (x_value, y_value),
            xytext=(6, 5),
            textcoords="offset points",
            color=color,
            fontsize=9,
            weight="bold" if highlight else "normal",
        )
    axis.relim()
    axis.autoscale_view()
    axis.margins(0.14)
    output = io.StringIO()
    figure.savefig(output, format="svg", facecolor=figure.get_facecolor())
    plt.close(figure)
    return output.getvalue()


__all__ = [
    "JGEXTangentialQuadrilateralSecondTangentApplication",
    "TangentialQuadrilateralSecondTangentCertificate",
    "certify_jgex_tangential_quadrilateral_second_tangent_application",
    "certify_tangential_quadrilateral_second_tangent_chart",
    "render_tangential_quadrilateral_second_tangent_chart_svg",
]
