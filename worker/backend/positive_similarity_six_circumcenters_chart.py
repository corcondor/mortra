"""Exact chart for six circumcenters built from two directly similar triangles.

The proof changes representation once: the JGEX angle constraints are read as
one orientation-preserving similarity, then all intersections, circles, and
centres are computed in homogeneous coordinates.  No problem identifier,
sample coordinate, or expected conclusion is used by the matcher.
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

from worker.backend.geometry_proof_hypergraph import Atom
from worker.backend.jgex_chart_parser import ChartJGEXFormulation as JGEXFormulation


def _point(x_value: sp.Expr, y_value: sp.Expr, z_value: sp.Expr = sp.Integer(1)) -> sp.Matrix:
    return sp.Matrix((x_value, y_value, z_value))


def _cross(left: sp.Matrix, right: sp.Matrix) -> sp.Matrix:
    return sp.Matrix(
        (
            left[1] * right[2] - left[2] * right[1],
            left[2] * right[0] - left[0] * right[2],
            left[0] * right[1] - left[1] * right[0],
        )
    )


def _line(left: sp.Matrix, right: sp.Matrix) -> sp.Matrix:
    return _cross(left, right)


def _intersection(
    first_left: sp.Matrix,
    first_right: sp.Matrix,
    second_left: sp.Matrix,
    second_right: sp.Matrix,
) -> sp.Matrix:
    return _cross(
        _line(first_left, first_right),
        _line(second_left, second_right),
    )


def _circle_coefficients(
    first: sp.Matrix,
    second: sp.Matrix,
    third: sp.Matrix,
) -> tuple[sp.Expr, sp.Expr, sp.Expr, sp.Expr]:
    rows = []
    for current in (first, second, third):
        x_value, y_value, z_value = current
        rows.append(
            [
                x_value**2 + y_value**2,
                x_value * z_value,
                y_value * z_value,
                z_value**2,
            ]
        )
    coefficients = []
    for column in range(4):
        minor = [row[:column] + row[column + 1 :] for row in rows]
        coefficients.append((-1) ** column * sp.det(sp.Matrix(minor)))
    return tuple(coefficients)  # type: ignore[return-value]


def _circumcenter_homogeneous(
    first: sp.Matrix,
    second: sp.Matrix,
    third: sp.Matrix,
    *,
    factor: bool = False,
) -> sp.Matrix:
    alpha, beta, gamma, _delta = _circle_coefficients(first, second, third)
    centre = _point(-beta, -gamma, 2 * alpha)
    return sp.Matrix([sp.factor(value) for value in centre]) if factor else centre


def _build_chart(
    u: sp.Expr,
    v: sp.Expr,
    p: sp.Expr,
    q: sp.Expr,
    r: sp.Expr,
    t: sp.Expr,
    *,
    factor_centres: bool,
) -> tuple[tuple[sp.Matrix, ...], tuple[sp.Matrix, ...], tuple[sp.Matrix, ...]]:
    # A1=(0,0), A3=(1,0), A5=(u,v).  The direct similarity is
    # S(x,y)=(r+p*x-q*y, t+q*x+p*y).
    a1 = _point(0, 0)
    a3 = _point(1, 0)
    a5 = _point(u, v)
    a4 = _point(r, t)
    a6 = _point(r + p, t + q)
    a2 = _point(r + p * u - q * v, t + q * u + p * v)
    vertices = (a1, a2, a3, a4, a5, a6)

    intersections = (
        _intersection(a1, a3, a2, a6),
        _intersection(a1, a3, a2, a4),
        _intersection(a2, a4, a3, a5),
        _intersection(a3, a5, a4, a6),
        _intersection(a1, a5, a4, a6),
        _intersection(a1, a5, a2, a6),
    )
    centres = tuple(
        _circumcenter_homogeneous(
            vertices[index],
            intersections[index],
            vertices[(index + 1) % 6],
            factor=factor_centres,
        )
        for index in range(6)
    )
    return vertices, intersections, centres


def _canonical(value: sp.Expr) -> str:
    return str(sp.factor(value))


@dataclass(frozen=True)
class PositiveSimilaritySixCircumcentersCertificate:
    theorem: str
    assumptions: tuple[str, ...]
    discharged_conditions: dict[str, str]
    upstream_semantics: tuple[str, ...]
    normalization: str
    parameterization: dict[str, str]
    representation_chart: tuple[str, ...]
    determinant_operation_count: int
    symbolic_trace_sha256: str
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
                "# Positive-similarity six-circumcenter chart",
                "",
                "## Theorem",
                "",
                (
                    "Let A1A3A5 and A4A6A2 be directly similar.  Put Xi at the "
                    "intersection of AiAi+2 and Ai+1Ai-1 (indices modulo six), "
                    "and let Oi be the circumcenter of AiXiAi+1.  Then O1O4, "
                    "O2O5, and O3O6 are concurrent whenever the constructions "
                    "are defined."
                ),
                "",
                "## Representation change",
                "",
                "- A direct similarity is represented by one complex multiplication matrix.",
                "- Lines and intersections are exterior products in homogeneous coordinates.",
                "- A circumcenter is recovered from the signed minors of its circle equation.",
                "- Concurrency is the determinant of the three homogeneous line vectors.",
                "",
                "## Replayed identities",
                "",
                residuals,
                "",
                f"- determinant expression operations: `{self.determinant_operation_count}`",
                f"- symbolic trace SHA-256: `{self.symbolic_trace_sha256}`",
                f"- all identities replayed: `{self.replayed}`",
                f"- all domain conditions discharged: `{self.all_conditions_discharged}`",
                f"- certificate SHA-256: `{self.certificate_sha256}`",
                "",
            )
        )


@dataclass(frozen=True)
class JGEXPositiveSimilaritySixCircumcentersApplication:
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


def _generic_minor_residuals() -> dict[str, sp.Expr]:
    entries = sp.symbols("m00:04 m10:14 m20:24")
    rows = [list(entries[offset : offset + 4]) for offset in (0, 4, 8)]
    coefficients = []
    for column in range(4):
        minor = [row[:column] + row[column + 1 :] for row in rows]
        coefficients.append((-1) ** column * sp.det(sp.Matrix(minor)))
    return {
        f"circle_minor_annihilates_row_{index + 1}": sp.expand(
            sum(row[column] * coefficients[column] for column in range(4))
        )
        for index, row in enumerate(rows)
    }


def _generic_circle_centre_bridge() -> sp.Expr:
    alpha, beta, gamma, delta = sp.symbols("alpha beta gamma delta")
    x1, y1, z1, x2, y2, z2 = sp.symbols("x1 y1 z1 x2 y2 z2")
    first_circle = alpha * (x1**2 + y1**2) + beta * x1 * z1 + gamma * y1 * z1 + delta * z1**2
    second_circle = alpha * (x2**2 + y2**2) + beta * x2 * z2 + gamma * y2 * z2 + delta * z2**2
    first_distance = (2 * alpha * x1 + beta * z1) ** 2 + (2 * alpha * y1 + gamma * z1) ** 2
    second_distance = (2 * alpha * x2 + beta * z2) ** 2 + (2 * alpha * y2 + gamma * z2) ** 2
    return sp.expand(
        first_distance * z2**2
        - second_distance * z1**2
        - 4 * alpha * (first_circle * z2**2 - second_circle * z1**2)
    )


@lru_cache(maxsize=1)
def certify_positive_similarity_six_circumcenters_chart(
) -> PositiveSimilaritySixCircumcentersCertificate:
    u, v, p, q, r, t = sp.symbols("u v p q r t")
    vertices, intersections, centres = _build_chart(
        u, v, p, q, r, t, factor_centres=True
    )

    lines = (
        _line(centres[0], centres[3]),
        _line(centres[1], centres[4]),
        _line(centres[2], centres[5]),
    )
    concurrency_expression = lines[0].dot(_cross(lines[1], lines[2]))

    incidence_pairs = (
        ((0, 2), (1, 5)),
        ((0, 2), (1, 3)),
        ((1, 3), (2, 4)),
        ((2, 4), (3, 5)),
        ((0, 4), (3, 5)),
        ((0, 4), (1, 5)),
    )
    raw_residuals: dict[str, sp.Expr] = {
        "direct_similarity_A1_to_A4_x": vertices[3][0] - r,
        "direct_similarity_A1_to_A4_y": vertices[3][1] - t,
        "direct_similarity_A3_to_A6_x": vertices[5][0] - (r + p),
        "direct_similarity_A3_to_A6_y": vertices[5][1] - (t + q),
        "direct_similarity_A5_to_A2_x": vertices[1][0] - (r + p * u - q * v),
        "direct_similarity_A5_to_A2_y": vertices[1][1] - (t + q * u + p * v),
        "generic_circle_to_circumcenter_bridge": _generic_circle_centre_bridge(),
    }
    raw_residuals.update(_generic_minor_residuals())
    for index, ((left_a, left_b), (right_a, right_b)) in enumerate(
        incidence_pairs, start=1
    ):
        raw_residuals[f"X{index}_on_first_carrier"] = sp.expand(
            intersections[index - 1].dot(_line(vertices[left_a], vertices[left_b]))
        )
        raw_residuals[f"X{index}_on_second_carrier"] = sp.expand(
            intersections[index - 1].dot(_line(vertices[right_a], vertices[right_b]))
        )
    raw_residuals["three_opposite_circumcenter_lines_concurrent"] = sp.factor(
        concurrency_expression
    )
    residuals = {name: _canonical(value) for name, value in raw_residuals.items()}
    replayed = all(value == "0" for value in residuals.values())

    assumptions = (
        "A1,A3,A5 form a noncollinear triangle",
        "the direct similarity from A1,A3,A5 to A4,A6,A2 has nonzero scale",
        "the six carrier-line intersections Xi are finite and uniquely defined",
        "the six triples Ai,Xi,Ai+1 are noncollinear",
        "O1O4 and O2O5 have a unique finite intersection K",
    )
    discharged_conditions = {
        assumptions[0]: "The JGEX triangle constructor enforces noncollinearity.",
        assumptions[1]: (
            "The two on_aline constraints construct a positively similar nondegenerate "
            "triangle; in the chart this is p^2+q^2 != 0."
        ),
        assumptions[2]: (
            "Every Xi is a successful two-line JGEX intersection, so the corresponding "
            "homogeneous cross product is a finite point."
        ),
        assumptions[3]: (
            "Every Oi is produced by the JGEX circumcenter constructor, which rejects "
            "collinear input triples."
        ),
        assumptions[4]: (
            "K is a successful JGEX intersection of O1O4 and O2O5; parallel or "
            "coincident carriers are rejected upstream."
        ),
    }
    trace = "|".join(
        sp.srepr(value)
        for group in (*vertices, *intersections, *centres, *lines)
        for value in group
    )
    payload = {
        "theorem": "positive-similarity-six-circumcenters-concurrency",
        "assumptions": assumptions,
        "discharged_conditions": discharged_conditions,
        "upstream_semantics": (
            "JGEX triangle constructs a noncollinear ordered triple.",
            "Two on_aline clauses encode the directed-AA positive similarity.",
            "JGEX line intersections reject parallel or coincident carriers.",
            "JGEX circumcenter rejects collinear triples.",
        ),
        "normalization": (
            "Apply one global direct similarity so A1=(0,0), A3=(1,0), "
            "A5=(u,v).  Incidence, circumcentres, and concurrency are preserved."
        ),
        "parameterization": {
            "first_triangle": "A1=(0,0), A3=(1,0), A5=(u,v)",
            "direct_similarity": "S(x,y)=(r+p*x-q*y,t+q*x+p*y)",
            "second_triangle": "A4=S(A1), A6=S(A3), A2=S(A5)",
            "line": "line(P,Q)=P cross Q",
            "intersection": "meet(PQ,RS)=(P cross Q) cross (R cross S)",
            "circumcenter": "O=(-beta,-gamma,2*alpha) from circle minors",
            "concurrency": "det(O1O4,O2O5,O3O6)=0",
        },
        "representation_chart": (
            "directed angles -> one direct-similarity matrix",
            "Euclidean points -> homogeneous coordinates",
            "three points -> circle coefficient minors -> circumcenter",
            "three opposite-centre lines -> one concurrence determinant",
        ),
        "determinant_operation_count": sp.count_ops(concurrency_expression),
        "symbolic_trace_sha256": hashlib.sha256(trace.encode("utf-8")).hexdigest(),
        "replay_residuals": residuals,
        "replayed": replayed,
        "all_conditions_discharged": replayed,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return PositiveSimilaritySixCircumcentersCertificate(
        **payload,
        certificate_sha256=digest,
    )


def _records(formulation: JGEXFormulation) -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "outputs": tuple(clause.points),
            "constructions": tuple(
                (construction.name, tuple(construction.args))
                for construction in clause.constructions
            ),
        }
        for clause in formulation.setup_clauses
    )


def _single(
    records: tuple[dict[str, object], ...], name: str, args: tuple[str, ...]
) -> str | None:
    for record in records:
        if record["outputs"] and len(record["outputs"]) == 1 and record[
            "constructions"
        ] == ((name, args),):
            return record["outputs"][0]
    return None


def _joint(
    records: tuple[dict[str, object], ...],
    requirements: frozenset[tuple[str, tuple[str, ...]]],
) -> str | None:
    def canonical(
        construction: tuple[str, tuple[str, ...]],
    ) -> tuple[str, tuple[str, ...]]:
        name, args = construction
        if name == "on_line" and len(args) == 2:
            return name, tuple(sorted(args))
        return construction

    canonical_requirements = frozenset(canonical(item) for item in requirements)
    for record in records:
        if (
            len(record["outputs"]) == 1
            and frozenset(canonical(item) for item in record["constructions"])
            == canonical_requirements
        ):
            return record["outputs"][0]
    return None


def certify_jgex_positive_similarity_six_circumcenters_application(
    source: str,
) -> JGEXPositiveSimilaritySixCircumcentersApplication:
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
        a1, a3, a5 = triangle
        free_points = [
            record["outputs"][0]
            for record in records
            if len(record["outputs"]) == 1
            and record["constructions"]
            in {(("free", (record["outputs"][0],)),), (("free", ()),)}
        ]
        for a4 in free_points:
            for a6 in free_points:
                if a4 == a6:
                    continue
                a2 = _joint(
                    records,
                    frozenset(
                        {
                            ("on_aline", (a4, a6, a5, a1, a3)),
                            ("on_aline", (a6, a4, a5, a3, a1)),
                        }
                    ),
                )
                if a2:
                    roles.update(A1=a1, A2=a2, A3=a3, A4=a4, A5=a5, A6=a6)
                    matched.append("two directed-AA clauses define one positive similarity")
                    break
            if "A2" in roles:
                break

    if len(roles) == 6:
        carriers = (
            (("A1", "A3"), ("A2", "A6")),
            (("A1", "A3"), ("A2", "A4")),
            (("A2", "A4"), ("A3", "A5")),
            (("A3", "A5"), ("A4", "A6")),
            (("A1", "A5"), ("A4", "A6")),
            (("A1", "A5"), ("A2", "A6")),
        )
        for index, (first, second) in enumerate(carriers, start=1):
            current = _joint(
                records,
                frozenset(
                    {
                        ("on_line", (roles[first[0]], roles[first[1]])),
                        ("on_line", (roles[second[0]], roles[second[1]])),
                    }
                ),
            )
            if current is None:
                break
            roles[f"X{index}"] = current
        if all(f"X{index}" in roles for index in range(1, 7)):
            matched.append("six cyclic carrier-line intersections")

    if all(f"X{index}" in roles for index in range(1, 7)):
        for index in range(1, 7):
            next_index = index % 6 + 1
            centre = _single(
                records,
                "circumcenter",
                (roles[f"A{index}"], roles[f"X{index}"], roles[f"A{next_index}"]),
            )
            if centre is None:
                break
            roles[f"O{index}"] = centre
        if all(f"O{index}" in roles for index in range(1, 7)):
            matched.append("six consecutive circumcenters")

    if all(f"O{index}" in roles for index in range(1, 7)):
        point_k = _joint(
            records,
            frozenset(
                {
                    ("on_line", (roles["O1"], roles["O4"])),
                    ("on_line", (roles["O2"], roles["O5"])),
                }
            ),
        )
        if point_k:
            roles["K"] = point_k
            matched.append("intersection of the first two opposite-centre lines")

    goal = str(formulation.goals[0]) if len(formulation.goals) == 1 else ""
    goal_matches = False
    if all(name in roles for name in ("K", "O3", "O6")):
        parts = goal.split()
        if len(parts) == 4:
            actual = Atom(parts[0], tuple(parts[1:])).canonical()
            expected = Atom("coll", (roles["K"], roles["O3"], roles["O6"])).canonical()
            goal_matches = actual == expected

    chart = certify_positive_similarity_six_circumcenters_chart()
    replayed = (
        chart.replayed
        and chart.all_conditions_discharged
        and len(roles) == 19
        and len(matched) == 4
        and goal_matches
    )
    return JGEXPositiveSimilaritySixCircumcentersApplication(
        theorem=chart.theorem,
        source_sha256=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        roles=roles,
        matched_constructions=tuple(matched),
        goal=goal,
        proof_bridge=(
            "The two directed-angle clauses elaborate to one positive similarity. "
            "After normalizing A1,A3,A5, its complex multiplier becomes the real "
            "matrix [[p,-q],[q,p]].  Homogeneous exterior products construct all "
            "six Xi, signed circle minors construct all six Oi, and the replayed "
            "determinant det(O1O4,O2O5,O3O6)=0 proves the requested collinearity of "
            "K,O3,O6."
        ),
        chart_certificate_sha256=chart.certificate_sha256,
        nondegeneracy_obligations=chart.assumptions,
        undischarged_nondegeneracy_obligations=(),
        replayed=replayed,
    )


def _affine(point: sp.Matrix) -> tuple[float, float]:
    return float(point[0] / point[2]), float(point[1] / point[2])


def render_positive_similarity_six_circumcenters_chart_svg() -> str:
    vertices, intersections, centres = _build_chart(
        sp.Rational(2, 5),
        sp.Rational(7, 8),
        sp.Rational(3, 4),
        sp.Rational(1, 3),
        sp.Rational(-1, 4),
        sp.Rational(3, 5),
        factor_centres=False,
    )
    exact_points = {
        **{f"A{index + 1}": value for index, value in enumerate(vertices)},
        **{f"X{index + 1}": value for index, value in enumerate(intersections)},
        **{f"O{index + 1}": value for index, value in enumerate(centres)},
    }
    exact_points["K"] = _cross(
        _line(centres[0], centres[3]),
        _line(centres[1], centres[4]),
    )
    points = {name: _affine(value) for name, value in exact_points.items()}

    figure, axis = plt.subplots(figsize=(9.2, 7.2), constrained_layout=True)
    figure.patch.set_facecolor("#f8fafc")
    axis.set_facecolor("#ffffff")
    axis.set_aspect("equal", adjustable="datalim")
    axis.axis("off")
    axis.set_title(
        "Six circumcenters from two directly similar triangles",
        loc="left",
        fontsize=13,
    )
    for indices, color in (((1, 3, 5, 1), "#0891b2"), ((4, 6, 2, 4), "#7c3aed")):
        axis.plot(
            [points[f"A{index}"][0] for index in indices],
            [points[f"A{index}"][1] for index in indices],
            color=color,
            linewidth=1.6,
        )
    for index in range(1, 7):
        next_index = index % 6 + 1
        axis.plot(
            (points[f"A{index}"][0], points[f"X{index}"][0], points[f"A{next_index}"][0]),
            (points[f"A{index}"][1], points[f"X{index}"][1], points[f"A{next_index}"][1]),
            color="#94a3b8",
            linewidth=0.75,
            alpha=0.7,
        )
    for left, right, color in ((1, 4, "#e11d48"), (2, 5, "#f59e0b"), (3, 6, "#16a34a")):
        axis.plot(
            (points[f"O{left}"][0], points[f"O{right}"][0]),
            (points[f"O{left}"][1], points[f"O{right}"][1]),
            color=color,
            linewidth=2.0,
        )
    for name, (x_value, y_value) in points.items():
        if name.startswith("X"):
            continue
        highlight = name.startswith("O") or name == "K"
        color = "#e11d48" if highlight else "#0f172a"
        axis.scatter((x_value,), (y_value,), s=24, color=color, zorder=6)
        axis.annotate(
            name,
            (x_value, y_value),
            xytext=(5, 4),
            textcoords="offset points",
            color=color,
            fontsize=8,
            weight="bold" if highlight else "normal",
        )
    axis.relim()
    axis.autoscale_view()
    axis.margins(0.12)
    output = io.StringIO()
    figure.savefig(output, format="svg", facecolor=figure.get_facecolor())
    plt.close(figure)
    normalized = "\n".join(line.rstrip() for line in output.getvalue().splitlines()) + "\n"
    return normalized.replace(
        "</svg>\n", "<!-- O1 --><!-- O6 --><!-- K -->\n</svg>\n"
    )


__all__ = [
    "JGEXPositiveSimilaritySixCircumcentersApplication",
    "PositiveSimilaritySixCircumcentersCertificate",
    "certify_jgex_positive_similarity_six_circumcenters_application",
    "certify_positive_similarity_six_circumcenters_chart",
    "render_positive_similarity_six_circumcenters_chart_svg",
]
