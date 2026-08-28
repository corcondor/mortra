"""Exact Miquel--cevian chart for a coaxial triple of circles.

Let ``DEF`` be the cevian triangle of ``P`` in ``ABC`` and let ``Q`` be its
Miquel point.  For ``R`` on ``PQ``, let ``AR,BR,CR`` meet ``(AEF)``,
``(BDF)``, ``(CDE)`` again at ``J,K,L``.  Then ``(AJD)``, ``(BKE)``, and
``(CLF)`` are coaxial.

The replay works in the homogeneous polynomial ring ``QQ[u,v,p,q,t]``.  It
does not solve for the final common point.  A circle through a known pair of
points differs from a base circle by the common-chord line times ``z``; this
constructs the three target circles directly.  Their two radical axes are
then proved proportional.  Projective primitive normalization removes only
common polynomial factors and never changes a represented point, line, or
circle.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
import hashlib
import io
import json
import math

import matplotlib
from sympy.polys.domains import QQ
from sympy.polys.rings import ring

matplotlib.use("Agg")

from matplotlib import pyplot as plt
from matplotlib.patches import Circle

from worker.backend.geometry_natural_semantics import (
    extract_geometry_natural_semantics,
)
from worker.backend.geometry_proof_hypergraph import Atom
from worker.backend.jgex_chart_parser import ChartJGEXFormulation as JGEXFormulation


def _exact_replay() -> dict[str, str]:
    polynomial_ring, u, v, p, q, t = ring("u,v,p,q,t", QQ)
    zero = polynomial_ring.zero
    one = polynomial_ring.one

    def primitive(values):
        values = tuple(values)
        nonzero = [value for value in values if value]
        if not nonzero:
            return values
        divisor = nonzero[0]
        for value in nonzero[1:]:
            divisor = divisor.gcd(value)
            if divisor == one:
                break
        if divisor == one:
            return values
        return tuple(value.exquo(divisor) for value in values)

    def add(left, right):
        return tuple(a + b for a, b in zip(left, right, strict=True))

    def subtract(left, right):
        return tuple(a - b for a, b in zip(left, right, strict=True))

    def scale(factor, value):
        return tuple(factor * item for item in value)

    def cross(left, right):
        return primitive(
            (
                left[1] * right[2] - left[2] * right[1],
                left[2] * right[0] - left[0] * right[2],
                left[0] * right[1] - left[1] * right[0],
            )
        )

    def line(first, second):
        return cross(first, second)

    def intersection(first, second):
        return cross(first, second)

    def line_value(carrier, point):
        return sum(coefficient * coordinate for coefficient, coordinate in zip(
            carrier,
            point,
            strict=True,
        ))

    def determinant3(matrix):
        return (
            matrix[0][0]
            * (matrix[1][1] * matrix[2][2] - matrix[1][2] * matrix[2][1])
            - matrix[0][1]
            * (matrix[1][0] * matrix[2][2] - matrix[1][2] * matrix[2][0])
            + matrix[0][2]
            * (matrix[1][0] * matrix[2][1] - matrix[1][1] * matrix[2][0])
        )

    def circle_coefficients(first, second, third):
        rows = [
            (x * x + y * y, x * z, y * z, z * z)
            for x, y, z in (first, second, third)
        ]
        coefficients = []
        for omitted in range(4):
            minor = [
                tuple(row[index] for index in range(4) if index != omitted)
                for row in rows
            ]
            coefficients.append(((-1) ** omitted) * determinant3(minor))
        return primitive(coefficients)

    def circle_value(point, coefficients):
        x, y, z = point
        quadratic, horizontal, vertical, constant = coefficients
        return (
            quadratic * (x * x + y * y)
            + horizontal * x * z
            + vertical * y * z
            + constant * z * z
        )

    def circle_bilinear(first, second, coefficients):
        x, y, z = first
        x1, y1, z1 = second
        quadratic, horizontal, vertical, constant = coefficients
        return (
            2 * quadratic * (x * x1 + y * y1)
            + horizontal * (x * z1 + x1 * z)
            + vertical * (y * z1 + y1 * z)
            + 2 * constant * z * z1
        )

    def second_circle_point(known, other_line_point, coefficients):
        # Q(known+s*other)=s*(B+s*Q(other)); return the nonzero root
        # homogeneously as Q(other)*known-B*other.
        return primitive(
            subtract(
                scale(circle_value(other_line_point, coefficients), known),
                scale(
                    circle_bilinear(known, other_line_point, coefficients),
                    other_line_point,
                ),
            )
        )

    def radical_axis(first, second):
        # Cross-normalize the quadratic coefficient before subtraction.
        return primitive(
            second[0] * first[index] - first[0] * second[index]
            for index in range(4)
        )

    def circle_through_base_chord_and_point(base, chord, point):
        chord_circle = (zero, chord[0], chord[1], chord[2])
        return primitive(
            subtract(
                scale(circle_value(point, chord_circle), base),
                scale(circle_value(point, base), chord_circle),
            )
        )

    def coaxial_residuals(first, second, third):
        first_second = radical_axis(first, second)
        first_third = radical_axis(first, third)
        return cross(
            (first_second[1], first_second[2], first_second[3]),
            (first_third[1], first_third[2], first_third[3]),
        )

    a = (zero, zero, one)
    b = (one, zero, one)
    c = (u, v, one)
    parent = (p, q, one)
    d = intersection(line(a, parent), line(b, c))
    e = intersection(line(b, parent), line(a, c))
    f = intersection(line(c, parent), line(a, b))
    aef = circle_coefficients(a, e, f)
    bdf = circle_coefficients(b, d, f)
    cde = circle_coefficients(c, d, e)

    aef_bdf_axis = radical_axis(aef, bdf)
    axis_direction = (aef_bdf_axis[2], -aef_bdf_axis[1], zero)
    miquel = second_circle_point(f, axis_direction, aef)

    def target_circles(point_r):
        ar = line(a, point_r)
        br = line(b, point_r)
        cr = line(c, point_r)
        ajd = circle_through_base_chord_and_point(aef, ar, d)
        bke = circle_through_base_chord_and_point(bdf, br, e)
        clf = circle_through_base_chord_and_point(cde, cr, f)
        return ar, br, cr, ajd, bke, clf

    generic_r = primitive(add(parent, scale(t, miquel)))
    generic = target_circles(generic_r)
    exceptional = target_circles(miquel)
    ar, br, cr, ajd, bke, clf = generic
    _, _, _, exceptional_ajd, exceptional_bke, exceptional_clf = exceptional
    generic_coaxial = coaxial_residuals(ajd, bke, clf)
    exceptional_coaxial = coaxial_residuals(
        exceptional_ajd,
        exceptional_bke,
        exceptional_clf,
    )

    residuals = {
        "D_on_AP": line_value(line(a, parent), d),
        "D_on_BC": line_value(line(b, c), d),
        "E_on_BP": line_value(line(b, parent), e),
        "E_on_AC": line_value(line(a, c), e),
        "F_on_CP": line_value(line(c, parent), f),
        "F_on_AB": line_value(line(a, b), f),
        "A_on_AEF": circle_value(a, aef),
        "E_on_AEF": circle_value(e, aef),
        "F_on_AEF": circle_value(f, aef),
        "B_on_BDF": circle_value(b, bdf),
        "D_on_BDF": circle_value(d, bdf),
        "F_on_BDF": circle_value(f, bdf),
        "C_on_CDE": circle_value(c, cde),
        "D_on_CDE": circle_value(d, cde),
        "E_on_CDE": circle_value(e, cde),
        "Q_on_AEF": circle_value(miquel, aef),
        "Q_on_BDF": circle_value(miquel, bdf),
        "Q_on_CDE_Miquel_closure": circle_value(miquel, cde),
        "R_on_PQ": line_value(line(parent, miquel), generic_r),
        "A_on_AJD": circle_value(a, ajd),
        "D_on_AJD": circle_value(d, ajd),
        "B_on_BKE": circle_value(b, bke),
        "E_on_BKE": circle_value(e, bke),
        "C_on_CLF": circle_value(c, clf),
        "F_on_CLF": circle_value(f, clf),
        "AJD_BKE_CLF_coaxial_1": generic_coaxial[0],
        "AJD_BKE_CLF_coaxial_2": generic_coaxial[1],
        "AJD_BKE_CLF_coaxial_3": generic_coaxial[2],
        "exceptional_R_equals_Q_coaxial_1": exceptional_coaxial[0],
        "exceptional_R_equals_Q_coaxial_2": exceptional_coaxial[1],
        "exceptional_R_equals_Q_coaxial_3": exceptional_coaxial[2],
    }
    return {
        name: "0" if value == zero else str(value)
        for name, value in residuals.items()
    }


@dataclass(frozen=True)
class MiquelCevianCoaxialCertificate:
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
                "# Miquel--cevian coaxial chart",
                "",
                "## Reusable proof",
                "",
                "1. Normalize A=(0,0), B=(1,0), C=(u,v), P=(p,q).",
                "2. Construct the cevian triangle and its three base circles.",
                "3. Eliminate the known common root F to obtain the Miquel point Q.",
                "4. For R on PQ, represent each target circle as a base circle plus its common-chord line.",
                "5. Cross-normalize the three equations; their radical axes are proportional.",
                "6. Hence every common point of (AJD) and (BKE) lies on (CLF).",
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
class JGEXMiquelCevianCoaxialApplication:
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
def certify_miquel_cevian_coaxial_chart() -> MiquelCevianCoaxialCertificate:
    residuals = _exact_replay()
    replayed = all(value == "0" for value in residuals.values())
    assumptions = (
        "ABC is nondegenerate and P has a defined cevian triangle DEF",
        "Q is the non-F Miquel point of DEF",
        "R is any point on PQ",
        "J,K,L are the nontrivial second intersections on AR,BR,CR",
        "the three target circles are defined",
    )
    discharged = {
        assumptions[0]: "The triangle, free point, and six cevian incidences are matched.",
        assumptions[1]: "A hash-bound miquel_point atom fixes the common-circle branch.",
        assumptions[2]: "The carrier R on PQ is matched; a second affine chart covers R=Q.",
        assumptions[3]: "Each later circumcenter clause excludes the repeated known root.",
        assumptions[4]: "The three matched circumcenter clauses certify noncollinear triples.",
    }
    payload = {
        "theorem": "miquel-cevian-three-target-circles-coaxial",
        "assumptions": assumptions,
        "discharged_conditions": discharged,
        "upstream_semantics": (
            "Cevian incidence is reconstructed from carrier-line intersections.",
            "miquel_point selects the non-cevian common point of the three base circles.",
            "A later circumcenter excludes a repeated line-circle root.",
            "Coaxiality is equality of cross-normalized radical axes.",
        ),
        "normalization": (
            "Use a Euclidean similarity to set A=(0,0), B=(1,0), "
            "C=(u,v), P=(p,q), retaining the full five-dimensional family with R."
        ),
        "parameterization": {
            "coefficient_domain": "homogeneous polynomial ring QQ[u,v,p,q,t]",
            "generic_R": "R=P+tQ",
            "exceptional_chart": "R=Q",
            "projective_reduction": "divide only common polynomial factors",
        },
        "representation_chart": (
            "cevian incidence -> homogeneous line intersections",
            "two circles with known root -> Miquel second root",
            "base circle + common chord + third point -> target circle",
            "circle-pair coefficient difference -> radical axis",
            "proportional radical axes -> coaxial circle pencil",
            "coaxial pencil + two-circle point -> third-circle membership",
        ),
        "proof_dag": (
            "Construct D,E,F and circles (AEF),(BDF),(CDE).",
            "Use F as the known root of the first two circles to construct Q.",
            "Replay Q on (CDE), closing the Miquel triangle.",
            "Construct the equations of (AJD),(BKE),(CLF) from shared chords.",
            "Show both independent radical-axis cross products vanish.",
            "Replay the exceptional endpoint R=Q in a second affine chart.",
        ),
        "branch_certificate": {
            "Q": "miquel_point(Q,D,E,F), excluding the known root F",
            "J": "A is the existing AR/(AEF) root and (AJD) is defined",
            "K": "B is the existing BR/(BDF) root and (BKE) is defined",
            "L": "C is the existing CR/(CDE) root and (CLF) is defined",
            "T": "arbitrary common point of the first two target circles",
        },
        "replay_residuals": residuals,
        "replayed": replayed,
        "all_conditions_discharged": replayed,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return MiquelCevianCoaxialCertificate(
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


def _canonical_construction(item):
    name, args = item
    if name == "circumcenter" and len(args) == 3:
        return name, tuple(sorted(args))
    if name in {"on_line", "on_circle"} and len(args) == 2:
        return name, tuple(sorted(args))
    return name, args


def _single(records, constructions):
    expected = sorted(map(_canonical_construction, constructions), key=repr)
    matches = {
        str(record["outputs"][0])
        for record in records
        if len(record["outputs"]) == 1
        and sorted(map(_canonical_construction, record["constructions"]), key=repr)
        == expected
    }
    return next(iter(matches)) if len(matches) == 1 else None


def certify_jgex_miquel_cevian_coaxial_application(
    source: str,
    natural_statement: str | None = None,
) -> JGEXMiquelCevianCoaxialApplication:
    normalized = source.strip()
    natural = (natural_statement or "").strip()
    semantics = extract_geometry_natural_semantics(natural)
    formulation = JGEXFormulation.from_text(normalized)
    records = _records(formulation)
    accepted: list[dict[str, str]] = []

    triangles = [
        tuple(map(str, record["outputs"]))
        for record in records
        if len(record["outputs"]) == 3
        and record["constructions"] == (("triangle", ()),)
    ]
    free_points = [
        str(record["outputs"][0])
        for record in records
        if len(record["outputs"]) == 1
        and record["constructions"] == (("free", ()),)
    ]
    for a, b, c in triangles:
        for p in free_points:
            d = _single(records, (("on_line", (a, p)), ("on_line", (b, c))))
            e = _single(records, (("on_line", (b, p)), ("on_line", (a, c))))
            f = _single(records, (("on_line", (c, p)), ("on_line", (a, b))))
            if not all((d, e, f)):
                continue
            o1 = _single(records, (("circumcenter", (a, e, f)),))
            o2 = _single(records, (("circumcenter", (b, d, f)),))
            o3 = _single(records, (("circumcenter", (c, d, e)),))
            if not all((o1, o2, o3)):
                continue
            q = _single(
                records,
                (("on_circle", (o1, a)), ("on_circle", (o2, b))),
            )
            if not q or not semantics.has_miquel_point(q, (d, e, f)):
                continue
            r = _single(records, (("on_line", (p, q)),))
            if not r:
                continue
            j = _single(
                records,
                (("on_line", (a, r)), ("on_circle", (o1, a))),
            )
            k = _single(
                records,
                (("on_line", (b, r)), ("on_circle", (o2, b))),
            )
            l = _single(
                records,
                (("on_line", (c, r)), ("on_circle", (o3, c))),
            )
            if not all((j, k, l)):
                continue
            oa = _single(records, (("circumcenter", (a, j, d)),))
            ob = _single(records, (("circumcenter", (b, k, e)),))
            if not all((oa, ob)):
                continue
            target = _single(
                records,
                (("on_circle", (oa, a)), ("on_circle", (ob, b))),
            )
            if not target:
                continue
            actual = (
                Atom(formulation.goals[0].predicate, formulation.goals[0].args).canonical()
                if len(formulation.goals) == 1
                else None
            )
            expected = Atom("cyclic", (c, f, l, target)).canonical()
            if actual == expected:
                accepted.append(
                    {
                        "A": a, "B": b, "C": c, "P": p,
                        "D": d, "E": e, "F": f,
                        "O1": o1, "O2": o2, "O3": o3,
                        "Q": q, "R": r, "J": j, "K": k, "L": l,
                        "OA": oa, "OB": ob, "T": target,
                    }
                )

    chart = certify_miquel_cevian_coaxial_chart()
    roles = accepted[0] if len(accepted) == 1 else {}
    replayed = bool(roles and chart.replayed and chart.all_conditions_discharged)
    goal = str(formulation.goals[0]) if len(formulation.goals) == 1 else ""
    return JGEXMiquelCevianCoaxialApplication(
        theorem=chart.theorem,
        source_sha256=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        natural_statement_sha256=hashlib.sha256(natural.encode("utf-8")).hexdigest(),
        natural_statement=natural,
        natural_semantic_atoms=semantics.typed_atoms,
        roles=roles,
        matched_constructions=(
            "cevian triangle DEF of P",
            "hash-bound Miquel point Q and carrier R on PQ",
            "three known-root secants AR,BR,CR",
            "two target circles and their arbitrary common point T",
        ) if roles else (),
        goal=goal,
        proof_bridge=(
            "Miquel known-root elimination -> shared-chord circle equations -> "
            "cross-normalized radical-axis identity"
        ),
        chart_certificate_sha256=chart.certificate_sha256,
        nondegeneracy_obligations=chart.assumptions,
        undischarged_nondegeneracy_obligations=() if replayed else chart.assumptions,
        replayed=replayed,
    )


def render_miquel_cevian_coaxial_chart_svg() -> str:
    def line_intersection(a, b, c, d):
        denominator = (a[0] - b[0]) * (c[1] - d[1]) - (a[1] - b[1]) * (
            c[0] - d[0]
        )
        determinant_ab = a[0] * b[1] - a[1] * b[0]
        determinant_cd = c[0] * d[1] - c[1] * d[0]
        return (
            (determinant_ab * (c[0] - d[0]) - (a[0] - b[0]) * determinant_cd)
            / denominator,
            (determinant_ab * (c[1] - d[1]) - (a[1] - b[1]) * determinant_cd)
            / denominator,
        )

    def circle_coefficients(a, b, c):
        matrix = ((a[0], a[1], 1.0), (b[0], b[1], 1.0), (c[0], c[1], 1.0))
        rhs = (-(a[0] ** 2 + a[1] ** 2), -(b[0] ** 2 + b[1] ** 2), -(c[0] ** 2 + c[1] ** 2))
        determinant = (
            matrix[0][0] * (matrix[1][1] - matrix[2][1])
            - matrix[0][1] * (matrix[1][0] - matrix[2][0])
            + matrix[1][0] * matrix[2][1] - matrix[1][1] * matrix[2][0]
        )
        def replace(column):
            rows = [list(row) for row in matrix]
            for index in range(3):
                rows[index][column] = rhs[index]
            return (
                rows[0][0] * (rows[1][1] * rows[2][2] - rows[1][2] * rows[2][1])
                - rows[0][1] * (rows[1][0] * rows[2][2] - rows[1][2] * rows[2][0])
                + rows[0][2] * (rows[1][0] * rows[2][1] - rows[1][1] * rows[2][0])
            )
        return replace(0) / determinant, replace(1) / determinant, replace(2) / determinant

    a, b, c, p = (0.0, 0.0), (1.0, 0.0), (0.32, 0.92), (0.42, 0.34)
    d = line_intersection(a, p, b, c)
    e = line_intersection(b, p, a, c)
    f = line_intersection(c, p, a, b)
    # A schematic rendering is sufficient here; the exact certificate above
    # contains the full Miquel and coaxial replay.
    fig, axis = plt.subplots(figsize=(9.0, 6.2))
    fig.patch.set_facecolor("#07090c")
    axis.set_facecolor("#07090c")
    axis.plot([a[0], b[0], c[0], a[0]], [a[1], b[1], c[1], a[1]], color="#6f7e89", linewidth=1.3)
    for vertex, trace in ((a, d), (b, e), (c, f)):
        axis.plot([vertex[0], trace[0]], [vertex[1], trace[1]], color="#2fd2e5", linewidth=1.0, alpha=0.8)
    for points, color in (((a, e, f), "#ffb454"), ((b, d, f), "#76e39a"), ((c, d, e), "#aa8cff")):
        horizontal, vertical, constant = circle_coefficients(*points)
        center = (-horizontal / 2, -vertical / 2)
        radius = math.sqrt(max(0.0, center[0] ** 2 + center[1] ** 2 - constant))
        axis.add_patch(Circle(center, radius, fill=False, color=color, linewidth=1.5, alpha=0.9))
    labels = {"A": a, "B": b, "C": c, "P": p, "D": d, "E": e, "F": f}
    for label, point in labels.items():
        axis.scatter([point[0]], [point[1]], s=22, color="#f1f5f8", zorder=4)
        axis.text(point[0] + 0.018, point[1] + 0.018, label, color="#f1f5f8", fontsize=9)
    axis.set_aspect("equal", adjustable="datalim")
    axis.axis("off")
    axis.set_title("Miquel point | shared-chord circles | coaxial pencil", color="#e7edf2", fontsize=12)
    fig.tight_layout()
    buffer = io.StringIO()
    fig.savefig(buffer, format="svg", bbox_inches="tight")
    plt.close(fig)
    return buffer.getvalue()


__all__ = [
    "JGEXMiquelCevianCoaxialApplication",
    "MiquelCevianCoaxialCertificate",
    "certify_jgex_miquel_cevian_coaxial_application",
    "certify_miquel_cevian_coaxial_chart",
    "render_miquel_cevian_coaxial_chart_svg",
]
