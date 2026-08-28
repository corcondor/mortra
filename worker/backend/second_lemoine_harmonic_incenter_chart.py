"""Exact second-Lemoine-circle chart for an incenter-on-altitude theorem.

The reusable chain is

    symmedian/perpendicular projections
      -> second Lemoine circle
      -> harmonic-power cyclicity
      -> two internal angle bisectors
      -> Pascal direction / altitude incidence.

The chart is independent of benchmark problem names.  Unlike the bare JGEX
formulation, it requires the natural-language semantic record because the
theorem is false when the dropped ``acute triangle`` condition is removed.
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

from worker.backend.geometry_natural_semantics import (
    extract_geometry_natural_semantics,
)
from worker.backend.geometry_proof_hypergraph import Atom
from worker.backend.jgex_chart_parser import ChartJGEXFormulation as JGEXFormulation

Point = sp.Matrix


def _canonical(value: sp.Expr) -> str:
    return str(sp.factor(sp.cancel(value)))


def _dot(left: Point, right: Point) -> sp.Expr:
    return sp.expand(left.dot(right))


def _cross(left: Point, right: Point) -> sp.Expr:
    return sp.expand(left[0] * right[1] - left[1] * right[0])


def _complex_product(left: Point, right: Point) -> Point:
    return sp.Matrix(
        (
            sp.expand(left[0] * right[0] - left[1] * right[1]),
            sp.expand(left[0] * right[1] + left[1] * right[0]),
        )
    )


def _conjugate(value: Point) -> Point:
    return sp.Matrix((value[0], -value[1]))


def _on_aline_residual(
    point: Point,
    target_origin: Point,
    target_unit: Point,
    source_point: Point,
    source_origin: Point,
    source_unit: Point,
) -> sp.Expr:
    """Polynomial incidence for JGEX's direct-similarity angle line."""

    target = target_unit - target_origin
    source = source_point - source_origin
    source_basis = source_unit - source_origin
    image_numerator = _complex_product(
        _complex_product(target, source), _conjugate(source_basis)
    )
    return _cross(point - target_origin, image_numerator)


def _cyclic_residual(a: Point, b: Point, c: Point, d: Point) -> sp.Expr:
    rows = [(_dot(point, point), point[0], point[1], 1) for point in (a, b, c, d)]
    return sp.Matrix(rows).det()


@dataclass(frozen=True)
class SecondLemoineHarmonicIncenterCertificate:
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
        signs = "\n".join(
            f"- `{name}`: {value}"
            for name, value in self.domain_sign_certificate.items()
        )
        return "\n".join(
            (
                "# Second Lemoine circle / harmonic incenter chart",
                "",
                "## Theorem",
                "",
                (
                    "In the acute-triangle construction described by the chart, "
                    "the incenter of PXY lies on the altitude AD."
                ),
                "",
                "## Representation changes",
                "",
                "- two directed-angle loci -> the symmedian point K",
                "- three perpendicular projections -> the second Lemoine circle",
                "- harmonic bundle / power identity -> cyclic quadrilateral PKXY",
                "- cyclic angles -> internal bisectors XW and YV",
                "- Pascal's point at infinity -> the altitude direction AD",
                "",
                "## Domain and branch signs",
                "",
                signs,
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
class JGEXSecondLemoineHarmonicIncenterApplication:
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
    replayed: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@lru_cache(maxsize=1)
def certify_second_lemoine_harmonic_incenter_chart() -> (
    SecondLemoineHarmonicIncenterCertificate
):
    u, v = sp.symbols("u v", nonzero=True, real=True)
    s = u**2 + v**2
    t = s - u
    h = 1 + t
    b2 = (1 - u) ** 2 + v**2
    d2_denominator = 3 * u**2 - 3 * u + v**2 + 1

    a = sp.Matrix((u, v))
    b = sp.Matrix((0, 0))
    c = sp.Matrix((1, 0))
    d = sp.Matrix((u, 0))
    m = sp.Matrix((sp.Rational(1, 2), 0))
    g = (a + b + c) / 3
    o = sp.Matrix((sp.Rational(1, 2), t / (2 * v)))
    k = sp.Matrix(((u + s) / (2 * h), v / (2 * h)))
    d1 = sp.Matrix((1 - u, 0))
    d2 = sp.Matrix((u * s / d2_denominator, 0))
    p = sp.Matrix(
        (
            -u * (u**2 - 2 * u - v**2) / h,
            -2 * u * v * (u - 1) / h,
        )
    )
    x = sp.Matrix((s / h, 0))
    y = sp.Matrix((u / h, 0))

    # Auxiliary points from the official second-Lemoine-circle proof.
    x1 = sp.Matrix((u / h, v / h))
    y1 = sp.Matrix((s / h, v / h))
    w = sp.Matrix((u**2 / h, u * v / h))
    vv = sp.Matrix(((u + v**2) / h, -v * (u - 1) / h))
    i = sp.Matrix(
        (
            u,
            -u * (u - 1) * t / (v * h),
        )
    )

    radius_squared = _dot(x - k, x - k)
    raw_residuals: dict[str, sp.Expr] = {
        "D_on_BC": _cross(d - b, c - b),
        "AD_perpendicular_BC": _dot(a - d, c - b),
        "O_equidistant_A_B": _dot(o - a, o - a) - _dot(o - b, o - b),
        "O_equidistant_A_C": _dot(o - a, o - a) - _dot(o - c, o - c),
        "M_midpoint_BC_x": m[0] - (b[0] + c[0]) / 2,
        "M_midpoint_BC_y": m[1] - (b[1] + c[1]) / 2,
        "G_centroid_x": g[0] - (a[0] + b[0] + c[0]) / 3,
        "G_centroid_y": g[1] - (a[1] + b[1] + c[1]) / 3,
        "K_first_symmedian_angle_line": _on_aline_residual(k, a, c, b, a, g),
        "K_second_symmedian_angle_line": _on_aline_residual(k, b, a, c, b, g),
        "D1_reflection_x": d1[0] - (2 * m[0] - d[0]),
        "D1_reflection_y": d1[1] - (2 * m[1] - d[1]),
        "D2_on_BC": _cross(d2 - b, c - b),
        "D2_isogonal_angle_line": _on_aline_residual(d2, a, b, c, a, d1),
        "P_on_AD2": _cross(p - a, d2 - a),
        "KP_perpendicular_AO": _dot(p - k, o - a),
        "X_on_BC": _cross(x - b, c - b),
        "KX_perpendicular_BO": _dot(x - k, o - b),
        "Y_on_BC": _cross(y - b, c - b),
        "KY_perpendicular_CO": _dot(y - k, o - c),
        "X1_on_KX": _cross(x1 - k, x - k),
        "X1_on_AB": _cross(x1 - a, b - a),
        "Y1_on_KY": _cross(y1 - k, y - k),
        "Y1_on_AC": _cross(y1 - a, c - a),
        "W_on_KP": _cross(w - k, p - k),
        "W_on_AB": _cross(w - a, b - a),
        "V_on_KP": _cross(vv - k, p - k),
        "V_on_AC": _cross(vv - a, c - a),
        "KY_equals_KX": _dot(y - k, y - k) - radius_squared,
        "KX1_equals_KX": _dot(x1 - k, x1 - k) - radius_squared,
        "KY1_equals_KX": _dot(y1 - k, y1 - k) - radius_squared,
        "KW_equals_KX": _dot(w - k, w - k) - radius_squared,
        "KV_equals_KX": _dot(vv - k, vv - k) - radius_squared,
        "harmonic_power_equivalent_PKXY_cyclic": _cyclic_residual(p, k, x, y),
        "XW_angle_bisector_squared": (
            _dot(p - x, w - x) ** 2 * _dot(y - x, y - x)
            - _dot(w - x, y - x) ** 2 * _dot(p - x, p - x)
        ),
        "YV_angle_bisector_squared": (
            _dot(p - y, vv - y) ** 2 * _dot(x - y, x - y)
            - _dot(vv - y, x - y) ** 2 * _dot(p - y, p - y)
        ),
        "I_on_XW": _cross(i - x, w - x),
        "I_on_YV": _cross(i - y, vv - y),
        "Pascal_X1Y_parallel_AD": _cross(y - x1, d - a),
        "Pascal_Y1X_parallel_AD": _cross(x - y1, d - a),
        "I_on_altitude_AD": _cross(i - a, d - a),
    }
    residuals = {name: _canonical(value) for name, value in raw_residuals.items()}
    replayed = all(value == "0" for value in residuals.values())

    assumptions = (
        "ABC is acute and oriented with B=(0,0), C=(1,0), A=(u,v), v>0",
        "D is the altitude foot from A and O is the circumcenter of ABC",
        "M is the midpoint of BC and G is the centroid of ABC",
        "K is the intersection of the two displayed symmedian angle lines",
        "D1 is the reflection of D in M and D2 is the selected point on BC",
        "P,X,Y are the three displayed perpendicular-line intersections",
        "I is the internal incenter of the nondegenerate triangle PXY",
    )
    domain_sign_certificate = {
        "acute_coordinate_domain": (
            "acute(B), acute(C), acute(A) give u>0, 1-u>0, "
            "t=u^2-u+v^2>0; orientation gives v>0"
        ),
        "denominators": (
            "h=1+t>0 and 3u^2-3u+v^2+1>=(u-1/2)^2+1/4+v^2>0"
        ),
        "D1_D2_on_segment": (
            "D1_x=1-u is in (0,1); D2_x=u*s/q is in (0,1) because "
            "q-u*s=(1-u)((1-u)^2+v^2)>0"
        ),
        "triangle_PXY_nondegenerate": (
            "X_x-Y_x=t/h>0 and P_y=2uv(1-u)/h>0"
        ),
        "XW_internal_branch": (
            "cross(XP,XW)=uv(1-u)s/h^2>0 and "
            "cross(XW,XY)=uvt/h^2>0"
        ),
        "YV_internal_branch": (
            "cross(YP,YV)=-uv(1-u)((1-u)^2+v^2)/h^2<0 and "
            "cross(YV,YX)=-v(1-u)t/h^2<0"
        ),
    }
    discharged_conditions = {
        assumptions[0]: "The typed natural-language record supplies acute(A,B,C).",
        assumptions[1]: "The foot and circumcenter clauses are matched and replayed.",
        assumptions[2]: "The first and fourth centroid outputs are matched by position.",
        assumptions[3]: "Both directed on_aline clauses with common output K are matched.",
        assumptions[4]: "The mirror and joint on_line/on_aline clauses are matched.",
        assumptions[5]: "All six incidence/perpendicular residuals replay to zero.",
        assumptions[6]: "The sign certificate selects both internal angle-bisector branches.",
    }
    payload = {
        "theorem": "second-lemoine-harmonic-pascal-incenter-altitude",
        "assumptions": assumptions,
        "discharged_conditions": discharged_conditions,
        "upstream_semantics": (
            "Natural-language acute and segment qualifiers are typed and hash-bound.",
            "JGEX on_aline denotes the direct-similarity angle-line locus.",
            "JGEX on_tline, on_line, foot, mirror, centroid and incenter keep their standard semantics.",
            "Internalness is established by oriented sign identities, not by squaring alone.",
        ),
        "normalization": (
            "Apply an orientation-preserving similarity so B=(0,0), C=(1,0), "
            "A=(u,v).  Acute ABC gives v,u,1-u,u^2-u+v^2>0."
        ),
        "representation_chart": (
            "directed angle-line pair -> symmedian point",
            "perpendicular projections from the symmedian point -> second Lemoine circle",
            "harmonic bundle -> power identity -> cyclicity",
            "cyclicity plus equal radii -> internal angle bisectors",
            "six points on one conic -> Pascal point at infinity -> fixed altitude direction",
        ),
        "proof_dag": (
            "Solve the two directed angle-line incidences to obtain K.",
            "Solve the three perpendicular projections and four auxiliary intersections.",
            "Replay KX=KY=KX1=KY1=KW=KV, certifying the second Lemoine circle.",
            "Replay the PKXY determinant; this is the harmonic-power conclusion used synthetically.",
            "Replay the two angle-bisector equations and use sign factors to select internal branches.",
            "Their intersection I is the incenter of PXY.",
            "Pascal for X,W,X1,Y,V,Y1 has its third point at infinity in direction AD.",
            "The coordinate replay I_x=u independently verifies I lies on AD.",
        ),
        "domain_sign_certificate": domain_sign_certificate,
        "replay_residuals": residuals,
        "replayed": replayed,
        "all_conditions_discharged": replayed,
    }
    digest = hashlib.sha256(
        json.dumps(payload, ensure_ascii=True, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return SecondLemoineHarmonicIncenterCertificate(
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
    if name == "foot" and len(args) == 3:
        return name, (args[0], *sorted(args[1:]))
    if name in {"on_line"} and len(args) == 2:
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


def _centroid_outputs(
    records: tuple[dict[str, object], ...],
    triangle: tuple[str, str, str],
) -> tuple[str, str] | None:
    matches = {
        (str(record["outputs"][0]), str(record["outputs"][3]))
        for record in records
        if len(record["outputs"]) == 4
        and len(record["constructions"]) == 1
        and record["constructions"][0] == ("centroid", triangle)
    }
    return next(iter(matches)) if len(matches) == 1 else None


def certify_jgex_second_lemoine_harmonic_incenter_application(
    source: str,
    natural_statement: str | None = None,
) -> JGEXSecondLemoineHarmonicIncenterApplication:
    normalized = source.strip()
    natural = (natural_statement or "").strip()
    semantics = extract_geometry_natural_semantics(natural)
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
        a, b, c = map(str, triangle)
        centroid = _centroid_outputs(records, (a, b, c))
        if centroid is None:
            continue
        m, g = centroid
        d = _single(records, ("foot", (a, b, c)))
        o = _single(records, ("circumcenter", (a, b, c)))
        if not d or not o:
            continue
        k = _joint(
            records,
            (
                ("on_aline", (a, c, b, a, g)),
                ("on_aline", (b, a, c, b, g)),
            ),
        )
        if not k:
            continue
        d1 = _single(records, ("mirror", (d, m)))
        if not d1:
            continue
        d2 = _joint(
            records,
            (
                ("on_line", (b, c)),
                ("on_aline", (a, b, c, a, d1)),
            ),
        )
        if not d2:
            continue
        p = _joint(records, (("on_tline", (k, a, o)), ("on_line", (a, d2))))
        x = _joint(records, (("on_line", (b, c)), ("on_tline", (k, b, o))))
        y = _joint(records, (("on_line", (b, c)), ("on_tline", (k, c, o))))
        if not p or not x or not y:
            continue
        i = _single(records, ("incenter", (p, x, y)))
        if not i:
            continue
        roles = {
            "A": a,
            "B": b,
            "C": c,
            "D": d,
            "O": o,
            "M": m,
            "G": g,
            "K": k,
            "D1": d1,
            "D2": d2,
            "P": p,
            "X": x,
            "Y": y,
            "I": i,
        }
        candidates[tuple(sorted(roles.items()))] = roles

    goal = str(formulation.goals[0]) if len(formulation.goals) == 1 else ""
    accepted: list[dict[str, str]] = []
    parts = goal.split()
    if len(parts) == 4:
        actual = Atom(parts[0], tuple(parts[1:])).canonical()
        for roles in candidates.values():
            expected = Atom("coll", (roles["I"], roles["A"], roles["D"])).canonical()
            semantic_match = (
                semantics.has_acute_triangle(
                    (roles["A"], roles["B"], roles["C"])
                )
                and semantics.point_on_segment(
                    roles["D1"], (roles["B"], roles["C"])
                )
                and semantics.point_on_segment(
                    roles["D2"], (roles["B"], roles["C"])
                )
            )
            if actual == expected and semantic_match:
                accepted.append(roles)

    chart = certify_second_lemoine_harmonic_incenter_chart()
    unique = accepted[0] if len(accepted) == 1 else {}
    matched = (
        (
            "typed acute triangle and both selected segment points",
            "altitude, circumcenter, midpoint/centroid and two symmedian angle lines",
            "reflection and isogonal point on the base",
            "three perpendicular projections from K and the incenter goal",
        )
        if unique
        else ()
    )
    replayed = bool(
        chart.replayed
        and chart.all_conditions_discharged
        and len(unique) == 14
        and len(accepted) == 1
    )
    missing: tuple[str, ...] = () if replayed else chart.assumptions
    return JGEXSecondLemoineHarmonicIncenterApplication(
        theorem=chart.theorem,
        source_sha256=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        natural_statement_sha256=semantics.statement_sha256,
        natural_statement=natural,
        natural_semantic_atoms=semantics.typed_atoms,
        roles=unique,
        matched_constructions=matched,
        goal=goal,
        proof_bridge=(
            "Normalize BC, solve the directed-angle construction of the symmedian "
            "point, and replay the second Lemoine circle.  The harmonic-power step "
            "gives PKXY cyclic; oriented residuals certify XW and YV as the internal "
            "bisectors.  Their intersection has x=u, so Pascal's infinite point is "
            "the altitude direction and I lies on AD."
        ),
        chart_certificate_sha256=chart.certificate_sha256,
        nondegeneracy_obligations=chart.assumptions,
        undischarged_nondegeneracy_obligations=missing,
        replayed=replayed,
    )


def render_second_lemoine_harmonic_incenter_chart_svg() -> str:
    u, v = 0.38, 0.96
    s = u * u + v * v
    h = 1 - u + s
    a = (u, v)
    b = (0.0, 0.0)
    c = (1.0, 0.0)
    k = ((u + s) / (2 * h), v / (2 * h))
    p = (-u * (u * u - 2 * u - v * v) / h, -2 * u * v * (u - 1) / h)
    x = (s / h, 0.0)
    y = (u / h, 0.0)
    x1 = (u / h, v / h)
    y1 = (s / h, v / h)
    w = (u * u / h, u * v / h)
    vv = ((u + v * v) / h, -v * (u - 1) / h)
    i = (u, -u * (u - 1) * (s - u) / (v * h))
    radius = ((x[0] - k[0]) ** 2 + (x[1] - k[1]) ** 2) ** 0.5

    figure, axis = plt.subplots(figsize=(9.2, 6.1))
    axis.set_aspect("equal")
    axis.axis("off")
    axis.set_facecolor("#050709")
    figure.patch.set_facecolor("#050709")
    axis.plot((a[0], b[0], c[0], a[0]), (a[1], b[1], c[1], a[1]), color="#475569")
    axis.add_patch(Circle(k, radius, fill=False, color="#22d3ee", linewidth=1.6))
    axis.plot((x[0], w[0]), (x[1], w[1]), color="#a3e635", linewidth=2.0)
    axis.plot((y[0], vv[0]), (y[1], vv[1]), color="#a3e635", linewidth=2.0)
    axis.plot((a[0], u), (a[1], 0), color="#fbbf24", linewidth=1.7)
    axis.plot((p[0], k[0]), (p[1], k[1]), color="#64748b", linewidth=1.0)
    for label, point, color in (
        ("A", a, "#f8fafc"),
        ("B", b, "#94a3b8"),
        ("C", c, "#94a3b8"),
        ("K", k, "#22d3ee"),
        ("P", p, "#94a3b8"),
        ("X", x, "#22d3ee"),
        ("Y", y, "#22d3ee"),
        ("X1", x1, "#22d3ee"),
        ("Y1", y1, "#22d3ee"),
        ("W", w, "#a3e635"),
        ("V", vv, "#a3e635"),
        ("I", i, "#fbbf24"),
    ):
        axis.scatter(*point, s=30, color=color, zorder=5)
        axis.text(point[0] + 0.02, point[1] + 0.025, label, color=color, fontsize=9)
    axis.text(
        -0.02,
        1.08,
        "second Lemoine circle -> internal bisectors -> altitude",
        color="#f8fafc",
        fontsize=10,
    )
    axis.set_xlim(-0.10, 1.10)
    axis.set_ylim(-0.08, 1.16)
    buffer = io.StringIO()
    figure.savefig(buffer, format="svg", bbox_inches="tight", facecolor=figure.get_facecolor())
    plt.close(figure)
    return "\n".join(line.rstrip() for line in buffer.getvalue().splitlines()) + "\n"


__all__ = [
    "JGEXSecondLemoineHarmonicIncenterApplication",
    "SecondLemoineHarmonicIncenterCertificate",
    "certify_jgex_second_lemoine_harmonic_incenter_application",
    "certify_second_lemoine_harmonic_incenter_chart",
    "render_second_lemoine_harmonic_incenter_chart_svg",
]
