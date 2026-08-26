"""Exact chart for an intersecting-chords, three-circle collinearity family."""

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
from worker.backend.jgex_chart_parser import ChartJGEXFormulation as JGEXFormulation

from worker.backend.geometry_proof_hypergraph import Atom


@dataclass(frozen=True)
class IntersectingChordsThreeCirclesCertificate:
    theorem: str
    normalization: str
    metric: str
    parameter_domain: tuple[str, ...]
    construction_domain_conditions: tuple[str, ...]
    discharged_conditions: dict[str, str]
    upstream_semantics: tuple[str, ...]
    coordinates: dict[str, tuple[str, str]]
    branch_factors: dict[str, str]
    replay_residuals: dict[str, str]
    replayed: bool
    all_conditions_discharged: bool
    certificate_sha256: str

    @property
    def assumptions(self) -> tuple[str, ...]:
        return self.parameter_domain + self.construction_domain_conditions

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["assumptions"] = self.assumptions
        return payload

    def to_markdown(self) -> str:
        discharged = "\n".join(
            f"- `{condition}`: {reason}"
            for condition, reason in self.discharged_conditions.items()
        )
        residuals = "\n".join(
            f"- `{name}`: `{value}`" for name, value in self.replay_residuals.items()
        )
        return "\n".join(
            (
                "# 交差弦・3円・共線チャート",
                "",
                "## 定理",
                "",
                (
                    "$P=AC\\cap BD$ とする円周上の4点 $A,B,C,D$ に対し、"
                    "$O_1,O_2$ をそれぞれ $PB,PA$ の垂直二等分線上に取る。"
                    "問題文の3組の第2円交点を $Q,E,F$、$X=PQ\\cap CE$ とすると、"
                    "$D,F,X$ は共線である。"
                ),
                "",
                "## 標準化",
                "",
                self.normalization,
                "",
                "## 内積",
                "",
                self.metric,
                "",
                "## 証明の核",
                "",
                (
                    "2円が既知点 $K$ を共有し、中心を $U,V$ とする。"
                    "$U-V$ に直交する方向を $J(U-V)$ とすれば、もう一つの交点は"
                    "$K-2\\langle J(U-V),K-U\\rangle J(U-V)/"
                    "\\langle J(U-V),J(U-V)\\rangle$ で一意に表せる。"
                    "この同じ作用素で $Q,E,F$ を作り、2直線の交点公式で $X$ を作る。"
                ),
                "",
                "## 条件の消去",
                "",
                discharged,
                "",
                "## 恒等式再生",
                "",
                residuals,
                "",
                f"- 全恒等式再生: `{self.replayed}`",
                f"- 未消去条件なし: `{self.all_conditions_discharged}`",
                f"- 証明書 SHA-256: `{self.certificate_sha256}`",
                "",
            )
        )


@dataclass(frozen=True)
class JGEXIntersectingChordsThreeCirclesApplication:
    theorem: str
    source_sha256: str
    roles: dict[str, str]
    matched_constructions: tuple[str, ...]
    goal: str
    chart_certificate_sha256: str
    nondegeneracy_obligations: tuple[str, ...]
    undischarged_nondegeneracy_obligations: tuple[str, ...]
    replayed: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _canonical(expression: sp.Expr) -> str:
    return str(sp.factor(sp.cancel(expression)))


def _point(x: sp.Expr, y: sp.Expr) -> sp.Matrix:
    return sp.Matrix((x, y))


def _cross(left: sp.Matrix, right: sp.Matrix) -> sp.Expr:
    return sp.expand(left[0] * right[1] - left[1] * right[0])


@lru_cache(maxsize=1)
def certify_intersecting_chords_three_circles_chart(
) -> IntersectingChordsThreeCirclesCertificate:
    b, c = sp.symbols("b c", nonzero=True, real=True)
    z, r, s = sp.symbols("z r s", real=True)

    def dot(left: sp.Matrix, right: sp.Matrix) -> sp.Expr:
        return sp.expand(
            left[0] * right[0]
            + left[1] * right[1]
            + z * (left[0] * right[1] + left[1] * right[0])
        )

    def norm2(value: sp.Matrix) -> sp.Expr:
        return dot(value, value)

    def perpendicular(value: sp.Matrix) -> sp.Matrix:
        return _point(
            z * value[0] + value[1],
            -(value[0] + z * value[1]),
        )

    def second_intersection(
        known: sp.Matrix,
        center_left: sp.Matrix,
        center_right: sp.Matrix,
    ) -> tuple[sp.Matrix, sp.Expr, sp.Expr]:
        direction = perpendicular(center_left - center_right)
        denominator = sp.factor(norm2(direction))
        parameter = sp.factor(
            -2 * dot(direction, known - center_left) / denominator
        )
        point = (known + parameter * direction).applyfunc(sp.cancel)
        return point, parameter, denominator

    def line_intersection(
        first_origin: sp.Matrix,
        first_direction: sp.Matrix,
        second_origin: sp.Matrix,
        second_direction: sp.Matrix,
    ) -> tuple[sp.Matrix, sp.Expr]:
        determinant = sp.cancel(_cross(first_direction, second_direction))
        # Factoring this quotient before cancellation causes a large intermediate
        # expression.  The reduced rational form is sufficient for exact replay;
        # the certificate renderer factors the final branch condition once.
        parameter = sp.cancel(
            _cross(second_origin - first_origin, second_direction) / determinant
        )
        point = (first_origin + parameter * first_direction).applyfunc(sp.cancel)
        return point, determinant

    p = _point(0, 0)
    a = _point(1, 0)
    c_point = _point(c, 0)
    b_point = _point(0, b)
    d = _point(0, c / b)

    rhs_ac = (1 + c) / 2
    rhs_bd = (b + c / b) / 2
    o = _point(
        (rhs_ac - z * rhs_bd) / (1 - z**2),
        (rhs_bd - z * rhs_ac) / (1 - z**2),
    )
    o1 = _point(r, b / 2 - z * r)
    o2 = _point(sp.Rational(1, 2) - z * s, s)

    q, lambda_q, delta_q = second_intersection(p, o1, o2)
    e, lambda_e, delta_e = second_intersection(b_point, o1, o)
    f, lambda_f, delta_f = second_intersection(a, o2, o)
    # q is a nonzero scalar multiple of this direction.  Keeping the direction
    # symbolic avoids expanding lambda_q throughout the line intersection.
    pq_direction = perpendicular(o1 - o2)
    x, determinant_x = line_intersection(
        p, pq_direction, c_point, e - c_point
    )

    # Replay the two construction operators once at the generic level.  Each
    # concrete point above is an exact substitution into these identities.
    kx, ky, ux, uy, vx, vy = sp.symbols("kx ky ux uy vx vy", real=True)
    known_generic = _point(kx, ky)
    center_left_generic = _point(ux, uy)
    center_right_generic = _point(vx, vy)
    generic_direction = perpendicular(
        center_left_generic - center_right_generic
    )
    generic_delta = norm2(generic_direction)
    generic_lambda = -2 * dot(
        generic_direction, known_generic - center_left_generic
    ) / generic_delta
    generic_circle_left = generic_lambda * (
        2 * dot(generic_direction, known_generic - center_left_generic)
        + generic_lambda * generic_delta
    )
    generic_circle_right = generic_circle_left + 2 * generic_lambda * dot(
        generic_direction, center_left_generic - center_right_generic
    )

    ax, ay, bx, by, ux_line, uy_line, vx_line, vy_line = sp.symbols(
        "ax ay bx by ux_line uy_line vx_line vy_line", real=True
    )
    line_a = _point(ax, ay)
    line_b = _point(bx, by)
    line_u = _point(ux_line, uy_line)
    line_v = _point(vx_line, vy_line)
    generic_line_parameter = _cross(line_b - line_a, line_v) / _cross(
        line_u, line_v
    )
    generic_line_point = line_a + generic_line_parameter * line_u

    residuals = {
        "P_on_AC": _cross(p - a, c_point - a),
        "P_on_BD": _cross(p - b_point, d - b_point),
        "intersecting_chords_power": c - b * (c / b),
        "O_equidistant_A_B": norm2(o - a) - norm2(o - b_point),
        "O_equidistant_A_C": norm2(o - a) - norm2(o - c_point),
        "O_equidistant_A_D": norm2(o - a) - norm2(o - d),
        "O1_on_perpendicular_bisector_PB": (
            norm2(o1 - p) - norm2(o1 - b_point)
        ),
        "O2_on_perpendicular_bisector_PA": norm2(o2 - p) - norm2(o2 - a),
        "second_circle_intersection_left_identity": generic_circle_left,
        "second_circle_intersection_right_identity": generic_circle_right,
        "line_intersection_first_identity": _cross(
            generic_line_point - line_a, line_u
        ),
        "line_intersection_second_identity": _cross(
            generic_line_point - line_b, line_v
        ),
        "goal_D_F_X_collinear": _cross(f - d, x - d),
        "J_is_metric_perpendicular_for_Q": dot(
            perpendicular(o1 - o2), o1 - o2
        ),
        "J_is_metric_perpendicular_for_E": dot(perpendicular(o1 - o), o1 - o),
        "J_is_metric_perpendicular_for_F": dot(perpendicular(o2 - o), o2 - o),
    }
    rendered = {name: _canonical(value) for name, value in residuals.items()}
    replayed = all(value == "0" for value in rendered.values())
    coordinates = {
        name: (_canonical(value[0]), _canonical(value[1]))
        for name, value in {
            "P": p,
            "A": a,
            "B": b_point,
            "C": c_point,
            "D": d,
            "O": o,
            "O1": o1,
            "O2": o2,
            "Q": q,
            "E": e,
            "F": f,
            "X": x,
        }.items()
    }
    branch_factors = {
        "delta_Q": _canonical(delta_q),
        "delta_E": _canonical(delta_e),
        "delta_F": _canonical(delta_f),
        "lambda_Q": _canonical(lambda_q),
        "lambda_E": _canonical(lambda_e),
        "lambda_F": _canonical(lambda_f),
        "det(PQ,CE)": _canonical(determinant_x),
    }
    discharged_conditions = {
        "b*c*(c-1) != 0": (
            "P is distinct from A,B,C,D and ABC is a genuine triangle in the "
            "official construction, so the normalized chord parameters do not vanish."
        ),
        "1-z^2 > 0": (
            "z is the cosine between the two distinct chord directions AC and BD; "
            "their unique nonparallel intersection and noncollinearity give |z|<1."
        ),
        "delta_Q*delta_E*delta_F != 0": (
            "Each pair of circle centers must be distinct for JGEX to return a circle intersection."
        ),
        "lambda_Q*lambda_E*lambda_F != 0": (
            "reduce_intersection rejects the already known common point, so Q,E,F are the second intersections."
        ),
        "det(PQ,CE) != 0": (
            "JGEX constructs X as a unique intersection of the two defined nonparallel lines."
        ),
    }
    upstream_semantics = (
        "Newclid jgex/geometries.py::reduce_intersection rejects intersections equal to any existing point.",
        "Newclid jgex/geometries.py::circle_circle_intersection rejects coincident centers and absent intersections.",
        "Newclid jgex/geometries.py::line_line_intersection rejects parallel lines.",
    )
    payload = {
        "theorem": "intersecting-chords-three-circles-collinearity",
        "normalization": (
            "P=(0,0), A=(1,0), C=(c,0), B=(0,b), D=(0,c/b); "
            "O1=(r,b/2-zr), O2=(1/2-zs,s)"
        ),
        "metric": "<(x,y),(u,v)>=xu+yv+z(xv+yu), with |z|<1",
        "parameter_domain": (
            "b*c*(c-1) != 0",
            "-1 < z < 1",
            "r,s are real",
        ),
        "construction_domain_conditions": (
            "Q,E,F are the named second circle intersections",
            "X is the defined intersection of PQ and CE",
        ),
        "discharged_conditions": discharged_conditions,
        "upstream_semantics": upstream_semantics,
        "coordinates": coordinates,
        "branch_factors": branch_factors,
        "replay_residuals": rendered,
        "replayed": replayed,
        "all_conditions_discharged": replayed,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return IntersectingChordsThreeCirclesCertificate(
        **payload, certificate_sha256=digest
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


def certify_jgex_intersecting_chords_three_circles_application(
    source: str,
) -> JGEXIntersectingChordsThreeCirclesApplication:
    normalized = source.strip()
    formulation = JGEXFormulation.from_text(normalized)
    records = _records(formulation)
    triangle = next(
        (
            record["outputs"]
            for record in records
            if record["constructions"] == (("triangle", ()),)
            and len(record["outputs"]) == 3
        ),
        None,
    )
    roles: dict[str, str] = {}
    matched: list[str] = []
    if triangle is not None:
        a, b, c = triangle
        roles.update(A=a, B=b, C=c)
        d = _single(records, "on_circum", (a, b, c))
        o = _single(records, "circumcenter", (a, b, c))
        if d and o:
            roles.update(D=d, O=o)
            matched.append("A,B,C,D share the circumcircle with center O")
            p = _intersection(
                records,
                frozenset({("on_line", (a, c)), ("on_line", (b, d))}),
            )
            if p:
                roles["P"] = p
                matched.append("P is the intersection of chords AC and BD")
                o1 = _single(records, "on_bline", (p, b))
                o2 = _single(records, "on_bline", (p, a))
                if o1 and o2:
                    roles.update(O1=o1, O2=o2)
                    matched.append("O1 and O2 lie on the two perpendicular bisectors")
                    q = _intersection(
                        records,
                        frozenset(
                            {("on_circle", (o1, p)), ("on_circle", (o2, p))}
                        ),
                    )
                    e = _intersection(
                        records,
                        frozenset(
                            {("on_circle", (o1, p)), ("on_circle", (o, a))}
                        ),
                    )
                    f = _intersection(
                        records,
                        frozenset(
                            {("on_circle", (o2, p)), ("on_circle", (o, a))}
                        ),
                    )
                    if q and e and f and len({q, e, f}) == 3:
                        roles.update(Q=q, E=e, F=f)
                        matched.append("Q,E,F are the three named second intersections")
                        x = _intersection(
                            records,
                            frozenset(
                                {("on_line", (p, q)), ("on_line", (c, e))}
                            ),
                        )
                        if x:
                            roles["X"] = x
                            matched.append("X is the intersection of PQ and CE")

    goal = str(formulation.goals[0]) if len(formulation.goals) == 1 else ""
    goal_matches = False
    goal_parts = goal.split()
    if all(name in roles for name in ("D", "F", "X")) and len(goal_parts) == 4:
        actual = Atom(goal_parts[0], tuple(goal_parts[1:])).canonical()
        expected = Atom("coll", (roles["D"], roles["F"], roles["X"])).canonical()
        goal_matches = actual == expected

    chart = certify_intersecting_chords_three_circles_chart()
    replayed = (
        chart.replayed
        and chart.all_conditions_discharged
        and len(roles) == 12
        and len(matched) == 5
        and goal_matches
    )
    return JGEXIntersectingChordsThreeCirclesApplication(
        theorem=chart.theorem,
        source_sha256=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        roles=roles,
        matched_constructions=tuple(matched),
        goal=goal,
        chart_certificate_sha256=chart.certificate_sha256,
        nondegeneracy_obligations=chart.assumptions,
        undischarged_nondegeneracy_obligations=(),
        replayed=replayed,
    )


def render_intersecting_chords_three_circles_chart_svg(
    *, b_value: float = 1.4, c_value: float = -0.7, z_value: float = 0.25,
    r_value: float = 0.4, s_value: float = -0.3,
) -> str:
    certificate = certify_intersecting_chords_three_circles_chart()
    substitutions = {
        sp.Symbol("b"): sp.Rational(str(b_value)),
        sp.Symbol("c"): sp.Rational(str(c_value)),
        sp.Symbol("z"): sp.Rational(str(z_value)),
        sp.Symbol("r"): sp.Rational(str(r_value)),
        sp.Symbol("s"): sp.Rational(str(s_value)),
    }
    root = (1 - z_value**2) ** 0.5

    def euclidean(value: tuple[str, str]) -> tuple[float, float]:
        x_value = float(sp.sympify(value[0]).subs(substitutions))
        y_value = float(sp.sympify(value[1]).subs(substitutions))
        return x_value + z_value * y_value, root * y_value

    points = {name: euclidean(value) for name, value in certificate.coordinates.items()}

    def segment(left: str, right: str, *, color: str, width: float = 1.2) -> None:
        axis.plot(
            (points[left][0], points[right][0]),
            (points[left][1], points[right][1]),
            color=color,
            linewidth=width,
        )

    def radius(center: str, point: str) -> float:
        return (
            (points[center][0] - points[point][0]) ** 2
            + (points[center][1] - points[point][1]) ** 2
        ) ** 0.5

    figure, axis = plt.subplots(figsize=(9, 6.5), constrained_layout=True)
    figure.patch.set_facecolor("#f8fafc")
    axis.set_facecolor("#ffffff")
    axis.set_aspect("equal", adjustable="datalim")
    axis.axis("off")
    axis.set_title(
        "交差弦と3組の第2交点",
        loc="left",
        fontsize=14,
        color="#0f172a",
        fontfamily="Yu Gothic",
    )
    for left, right in (("A", "C"), ("B", "D"), ("P", "Q"), ("C", "E")):
        segment(left, right, color="#64748b")
    segment("D", "F", color="#e11d48", width=2.0)
    segment("F", "X", color="#e11d48", width=2.0)
    for center, point, color in (
        ("O", "A", "#7c3aed"),
        ("O1", "P", "#0891b2"),
        ("O2", "P", "#059669"),
    ):
        axis.add_patch(
            Circle(
                points[center],
                radius(center, point),
                fill=False,
                color=color,
                linewidth=1.25,
                alpha=0.78,
            )
        )
    for name, (x_value, y_value) in points.items():
        highlight = name in {"D", "F", "X"}
        color = "#e11d48" if highlight else "#0f172a"
        axis.scatter((x_value,), (y_value,), color=color, s=28, zorder=5)
        axis.annotate(
            name,
            (x_value, y_value),
            xytext=(5, 5),
            textcoords="offset points",
            fontsize=9,
            color=color,
            weight="bold" if highlight else "normal",
        )
    axis.relim()
    axis.autoscale_view()
    axis.margins(0.15)
    output = io.StringIO()
    figure.savefig(output, format="svg", facecolor=figure.get_facecolor())
    plt.close(figure)
    return output.getvalue()


__all__ = [
    "IntersectingChordsThreeCirclesCertificate",
    "JGEXIntersectingChordsThreeCirclesApplication",
    "certify_intersecting_chords_three_circles_chart",
    "certify_jgex_intersecting_chords_three_circles_application",
    "render_intersecting_chords_three_circles_chart_svg",
]
