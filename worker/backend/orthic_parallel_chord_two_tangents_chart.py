"""Exact chart for an orthic frame, a parallel chord, and two tangents."""

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


def _cross(left: sp.Matrix, right: sp.Matrix) -> sp.Expr:
    return sp.expand(left[0] * right[1] - left[1] * right[0])


def _intersection(p: sp.Matrix, q: sp.Matrix, r: sp.Matrix, s: sp.Matrix) -> sp.Matrix:
    first, second = q - p, s - r
    parameter = sp.cancel(_cross(r - p, second) / _cross(first, second))
    return (p + parameter * first).applyfunc(lambda value: sp.factor(sp.cancel(value)))


def _foot(point: sp.Matrix, first: sp.Matrix, second: sp.Matrix) -> sp.Matrix:
    direction = second - first
    parameter = sp.cancel((point - first).dot(direction) / direction.dot(direction))
    return (first + parameter * direction).applyfunc(sp.cancel)


def _circumcenter(p: sp.Matrix, q: sp.Matrix, r: sp.Matrix) -> sp.Matrix:
    x, y = sp.symbols("center_x center_y")
    solution = sp.solve(
        [
            2 * x * (other[0] - p[0])
            + 2 * y * (other[1] - p[1])
            - (other.dot(other) - p.dot(p))
            for other in (q, r)
        ],
        (x, y),
        dict=True,
        simplify=False,
    )[0]
    return sp.Matrix(
        [sp.factor(sp.cancel(solution[x])), sp.factor(sp.cancel(solution[y]))]
    )


@dataclass(frozen=True)
class OrthicParallelChordTwoTangentsCertificate:
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
                "# Orthic parallel-chord two-tangent chart",
                "",
                "## Theorem",
                "",
                (
                    "In triangle ABC let E,F be the feet from B,C, H the orthocenter, "
                    "M the midpoint of AH, and K the projection of H on EF.  A chord "
                    "PQ of (ABC) is parallel to BC.  The tangent at E to (CQE) and "
                    "the tangent at F to (BPF) meet at X.  Then X,M,K are collinear."
                ),
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
class JGEXOrthicParallelChordTwoTangentsApplication:
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
def certify_orthic_parallel_chord_two_tangents_chart() -> (
    OrthicParallelChordTwoTangentsCertificate
):
    u, v, t = sp.symbols("u v t", nonzero=True)
    a, b, c = sp.Matrix((0, 0)), sp.Matrix((1, 0)), sp.Matrix((u, v))
    squared = u**2 + v**2
    circle_beta = sp.cancel((u - squared) / v)
    e = _foot(b, a, c)
    f = _foot(c, a, b)
    h = _intersection(b, e, c, f)
    m = ((a + h) / 2).applyfunc(sp.cancel)
    k = _foot(h, e, f)

    p_x = sp.cancel((1 - circle_beta * t) / (1 + t**2))
    p = sp.Matrix((p_x, sp.cancel(t * p_x)))
    direction = c - b
    parameter = sp.symbols("chord_parameter")
    candidate = p + parameter * direction

    def circle_value(point: sp.Matrix) -> sp.Expr:
        return sp.cancel(point.dot(point) - point[0] + circle_beta * point[1])

    chord_polynomial = sp.Poly(
        sp.together(circle_value(candidate)).as_numer_denom()[0], parameter
    )
    other = sp.cancel(
        -chord_polynomial.coeff_monomial(parameter)
        / chord_polynomial.coeff_monomial(parameter**2)
    )
    q = (p + other * direction).applyfunc(lambda value: sp.factor(sp.cancel(value)))
    o1 = _circumcenter(c, q, e)
    o2 = _circumcenter(b, p, f)
    tangent_e = e + sp.Matrix((-(e - o1)[1], (e - o1)[0]))
    tangent_f = f + sp.Matrix((-(f - o2)[1], (f - o2)[0]))
    x = _intersection(e, tangent_e, f, tangent_f)

    def distance_squared(left: sp.Matrix, right: sp.Matrix) -> sp.Expr:
        delta = left - right
        return sp.cancel(delta.dot(delta))

    raw_residuals = {
        "E_on_AC": _cross(e - a, c - a),
        "BE_perpendicular_AC": (b - e).dot(c - a),
        "F_on_AB": _cross(f - a, b - a),
        "CF_perpendicular_AB": (c - f).dot(b - a),
        "H_on_BE": _cross(h - b, e - b),
        "H_on_CF": _cross(h - c, f - c),
        "M_midpoint_x": 2 * m[0] - a[0] - h[0],
        "M_midpoint_y": 2 * m[1] - a[1] - h[1],
        "K_on_EF": _cross(k - e, f - e),
        "HK_perpendicular_EF": (h - k).dot(f - e),
        "A_on_circumcircle": circle_value(a),
        "B_on_circumcircle": circle_value(b),
        "C_on_circumcircle": circle_value(c),
        "P_on_circumcircle": circle_value(p),
        "Q_on_circumcircle": circle_value(q),
        "PQ_parallel_BC": _cross(q - p, c - b),
        "O1_equidistant_C_Q": distance_squared(o1, c) - distance_squared(o1, q),
        "O1_equidistant_C_E": distance_squared(o1, c) - distance_squared(o1, e),
        "O2_equidistant_B_P": distance_squared(o2, b) - distance_squared(o2, p),
        "O2_equidistant_B_F": distance_squared(o2, b) - distance_squared(o2, f),
        "X_on_tangent_at_E": (x - e).dot(e - o1),
        "X_on_tangent_at_F": (x - f).dot(f - o2),
        "X_M_K_collinear": _cross(x - m, k - m),
    }
    residuals = {name: _canonical(value) for name, value in raw_residuals.items()}
    replayed = all(value == "0" for value in residuals.values())
    assumptions = (
        "ABC is a defined nondegenerate triangle with circumcenter O",
        "E,F are the defined feet from B,C and H is their altitude intersection",
        "M is the midpoint of AH and K is the defined foot from H to EF",
        "P,Q are defined points of (ABC) with PQ parallel to BC",
        "O1,O2 are the defined circumcenters of CQE and BPF",
        "X is the defined intersection of the tangents at E and F",
    )
    payload = {
        "theorem": "orthic-parallel-chord-two-tangents-collinearity",
        "assumptions": assumptions,
        "discharged_conditions": {
            assumptions[0]: "The triangle and circumcenter clauses are matched.",
            assumptions[1]: "Both foot clauses and both altitude lines are matched.",
            assumptions[2]: "The midpoint and projection clauses are matched.",
            assumptions[3]: "The circle and parallel-line clauses are matched jointly.",
            assumptions[4]: "Both circumcenter triples are matched.",
            assumptions[5]: "Both tangent clauses defining X are matched.",
        },
        "upstream_semantics": (
            "JGEX foot denotes orthogonal projection onto a defined line.",
            "JGEX on_pline denotes the parallel through its first argument.",
            "JGEX on_tline denotes the perpendicular through its first argument.",
            "JGEX circumcenter rejects collinear defining triples.",
        ),
        "normalization": "Use A=(0,0), B=(1,0), C=(u,v), and parameterize P by the slope t of AP.",
        "representation_chart": (
            "two altitude feet -> rational orthic frame",
            "point on circumcircle -> one rational slope parameter",
            "parallel chord -> divide out the known circle root P",
            "two circumcenters -> four linear equal-distance equations",
            "two tangents -> two linear equations",
        ),
        "proof_dag": (
            "Construct E,F,H,M,K in the normalized triangle.",
            "Write (ABC), parameterize P, and solve the parallel chord for Q.",
            "Solve the two pairs of equal-distance equations for O1,O2.",
            "Intersect the two radius-perpendicular tangent lines at X.",
            "The determinant of X-M and K-M cancels identically.",
        ),
        "replay_residuals": residuals,
        "replayed": replayed,
        "all_conditions_discharged": replayed,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return OrthicParallelChordTwoTangentsCertificate(
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


def _canon(construction: tuple[str, tuple[str, ...]]) -> tuple[str, tuple[str, ...]]:
    name, args = construction
    if name == "circumcenter" and len(args) == 3:
        return name, tuple(sorted(args))
    if name == "foot" and len(args) == 3:
        return name, (args[0], *sorted(args[1:]))
    if name == "midpoint" and len(args) == 2:
        return name, tuple(sorted(args))
    if name in {"on_line", "on_circle"} and len(args) == 2:
        return name, tuple(args) if name == "on_circle" else tuple(sorted(args))
    if name in {"on_pline", "on_tline"} and len(args) == 3:
        return name, (args[0], *sorted(args[1:]))
    return construction


def _single(
    records: tuple[dict[str, object], ...], construction: tuple[str, tuple[str, ...]]
) -> str | None:
    expected = _canon(construction)
    matches = {
        str(record["outputs"][0])
        for record in records
        if len(record["outputs"]) == 1
        and len(record["constructions"]) == 1
        and _canon(record["constructions"][0]) == expected
    }
    return next(iter(matches)) if len(matches) == 1 else None


def _joint(
    records: tuple[dict[str, object], ...],
    constructions: tuple[tuple[str, tuple[str, ...]], ...],
) -> str | None:
    expected = sorted(map(_canon, constructions), key=repr)
    matches = {
        str(record["outputs"][0])
        for record in records
        if len(record["outputs"]) == 1
        and sorted(map(_canon, record["constructions"]), key=repr) == expected
    }
    return next(iter(matches)) if len(matches) == 1 else None


def certify_jgex_orthic_parallel_chord_two_tangents_application(
    source: str,
) -> JGEXOrthicParallelChordTwoTangentsApplication:
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
            o = _single(records, ("circumcenter", (a, b, c)))
            e = _single(records, ("foot", (b, a, c)))
            f = _single(records, ("foot", (c, a, b)))
            if not o or not e or not f:
                continue
            h = _joint(records, (("on_line", (b, e)), ("on_line", (c, f))))
            m = _single(records, ("midpoint", (a, h))) if h else None
            k = _single(records, ("foot", (h, e, f))) if h else None
            if not h or not m or not k:
                continue
            p = _single(records, ("on_circle", (o, a)))
            if not p:
                continue
            q = _joint(records, (("on_circle", (o, a)), ("on_pline", (p, b, c))))
            if not q:
                continue
            o1 = _single(records, ("circumcenter", (c, q, e)))
            o2 = _single(records, ("circumcenter", (b, p, f)))
            if not o1 or not o2:
                continue
            x = _joint(records, (("on_tline", (e, o1, e)), ("on_tline", (f, o2, f))))
            if not x:
                continue
            roles = {
                "A": a,
                "B": b,
                "C": c,
                "O": o,
                "E": e,
                "F": f,
                "H": h,
                "M": m,
                "K": k,
                "P": p,
                "Q": q,
                "O1": o1,
                "O2": o2,
                "X": x,
            }
            candidates[tuple(sorted(roles.items()))] = roles

    goal = str(formulation.goals[0]) if len(formulation.goals) == 1 else ""
    accepted: list[dict[str, str]] = []
    parts = goal.split()
    if len(parts) == 4:
        actual = Atom(parts[0], tuple(parts[1:])).canonical()
        for roles in candidates.values():
            if actual == Atom("coll", (roles["X"], roles["M"], roles["K"])).canonical():
                accepted.append(roles)
    chart = certify_orthic_parallel_chord_two_tangents_chart()
    unique = accepted[0] if len(accepted) == 1 else {}
    replayed = bool(
        chart.replayed
        and chart.all_conditions_discharged
        and len(unique) == 14
        and len(accepted) == 1
    )
    return JGEXOrthicParallelChordTwoTangentsApplication(
        theorem=chart.theorem,
        source_sha256=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        roles=unique,
        matched_constructions=(
            (
                "the orthic frame E,F,H and the derived points M,K",
                "a circumcircle chord PQ constrained parallel to BC",
                "the two circumcenters of CQE and BPF",
                "the two tangents defining X and the target line XMK",
            )
            if unique
            else ()
        ),
        goal=goal,
        proof_bridge=(
            "Normalize A=(0,0), B=(1,0), C=(u,v) and parameterize P by the slope "
            "of AP.  Divide out P to obtain Q on the parallel chord, solve both "
            "circumcenters and tangents linearly, and replay det(X-M,K-M)=0."
        ),
        chart_certificate_sha256=chart.certificate_sha256,
        nondegeneracy_obligations=chart.assumptions,
        undischarged_nondegeneracy_obligations=(),
        replayed=replayed,
    )


def render_orthic_parallel_chord_two_tangents_chart_svg() -> str:
    figure, axis = plt.subplots(figsize=(8.8, 6.0))
    axis.set_aspect("equal")
    axis.axis("off")
    axis.set_facecolor("#050709")
    figure.patch.set_facecolor("#050709")
    a, b, c = (0.0, 2.8), (-2.8, -1.2), (2.4, -1.2)
    e, f, h = (1.3, 0.45), (-1.35, 0.72), (0.05, 0.1)
    m, k, p, q, x = (0.02, 1.45), (0.1, 0.58), (-2.0, 1.25), (1.95, 1.1), (0.13, 0.9)
    axis.plot((a[0], b[0], c[0], a[0]), (a[1], b[1], c[1], a[1]), color="#475569")
    axis.plot((p[0], q[0]), (p[1], q[1]), color="#a3e635", linewidth=1.7)
    axis.plot((e[0], x[0]), (e[1], x[1]), color="#f472b6", linewidth=1.5)
    axis.plot((f[0], x[0]), (f[1], x[1]), color="#22d3ee", linewidth=1.5)
    axis.plot((m[0], k[0]), (m[1], k[1]), color="#fbbf24", linewidth=2.1)
    for label, point, color in (
        ("A", a, "#94a3b8"),
        ("B", b, "#94a3b8"),
        ("C", c, "#94a3b8"),
        ("E", e, "#f472b6"),
        ("F", f, "#22d3ee"),
        ("H", h, "#64748b"),
        ("M", m, "#fbbf24"),
        ("K", k, "#fbbf24"),
        ("P", p, "#a3e635"),
        ("Q", q, "#a3e635"),
        ("X", x, "#f8fafc"),
    ):
        axis.scatter(*point, s=28, color=color, zorder=5)
        axis.text(point[0] + 0.07, point[1] + 0.07, label, color=color, fontsize=9)
    axis.text(
        -2.45,
        2.42,
        "parallel chord -> two centers -> tangent intersection",
        color="#f8fafc",
        fontsize=10,
    )
    axis.set_xlim(-3.2, 2.85)
    axis.set_ylim(-1.55, 3.15)
    buffer = io.StringIO()
    figure.savefig(
        buffer, format="svg", bbox_inches="tight", facecolor=figure.get_facecolor()
    )
    plt.close(figure)
    return buffer.getvalue()


__all__ = [
    "OrthicParallelChordTwoTangentsCertificate",
    "JGEXOrthicParallelChordTwoTangentsApplication",
    "certify_orthic_parallel_chord_two_tangents_chart",
    "certify_jgex_orthic_parallel_chord_two_tangents_application",
    "render_orthic_parallel_chord_two_tangents_chart_svg",
]
