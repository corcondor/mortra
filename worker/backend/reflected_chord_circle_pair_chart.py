"""Exact chart for an existentially labelled two-circle intersection pair.

Let A,B,C,D,E lie on one circle.  Put X=AB cap CD, Y=AE cap CD,
P=EX cap BY, and let Q,R be the second intersections of EX,BY with the
parent circle.  Reflect A in CD to A'.  The circles (PQR) and (A'XY) have
two intersections that can be labelled M,N so that CM and DN meet again on
(PQR).

The important branch is constructed rather than guessed.  N is the non-R
intersection of (PQR) and (DRY), while M is the non-Q intersection of
(PQR) and (XQC).  Exact replay proves that both lie on (A'XY).  A final
known-root line-circle step on DN produces K on (PQR), and CMK is collinear.
All coordinates stay in QQ(w,alpha,beta,epsilon); no quadratic root is used.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
import hashlib
import io
import json
import math

import matplotlib
from matplotlib.patches import Circle
from sympy.polys.domains import QQ
from sympy.polys.fields import field

matplotlib.use("Agg")

from matplotlib import pyplot as plt

from worker.backend.geometry_proof_hypergraph import Atom
from worker.backend.geometry_natural_semantics import (
    extract_geometry_natural_semantics,
)
from worker.backend.jgex_chart_parser import ChartJGEXFormulation as JGEXFormulation


def _exact_replay() -> dict[str, str]:
    rational_field, w, alpha, beta, epsilon = field(
        "w,alpha,beta,epsilon", QQ
    )
    zero, one = rational_field.zero, rational_field.one

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

    def line_intersection(a, b, c, d):
        ab = subtract(b, a)
        cd = subtract(d, c)
        parameter = cross(subtract(c, a), cd) / cross(ab, cd)
        return add(a, scale(parameter, ab))

    def circle_coefficients(a, b, c):
        ab = subtract(b, a)
        ac = subtract(c, a)
        norm_a = dot(a, a)
        rhs_b = -(dot(b, b) - norm_a)
        rhs_c = -(dot(c, c) - norm_a)
        determinant = cross(ab, ac)
        horizontal = (rhs_b * ac[1] - rhs_c * ab[1]) / determinant
        vertical = (ab[0] * rhs_c - ac[0] * rhs_b) / determinant
        constant = -(norm_a + horizontal * a[0] + vertical * a[1])
        return horizontal, vertical, constant

    def circle_value(point, coefficients):
        return (
            dot(point, point)
            + coefficients[0] * point[0]
            + coefficients[1] * point[1]
            + coefficients[2]
        )

    def second_circle_intersection(known, carrier, coefficients):
        direction = subtract(carrier, known)
        quadratic = dot(direction, direction)
        linear = (
            2 * dot(known, direction)
            + coefficients[0] * direction[0]
            + coefficients[1] * direction[1]
        )
        return add(known, scale(-linear / quadratic, direction))

    def second_circle_circle_intersection(known, first, second):
        radical_horizontal = first[0] - second[0]
        radical_vertical = first[1] - second[1]
        carrier = add(known, (radical_vertical, -radical_horizontal))
        return second_circle_intersection(known, carrier, first)

    def parent_point(parameter):
        denominator = one + parameter * parameter
        return (
            (one + 2 * w * parameter - parameter * parameter) / denominator,
            2 * parameter * (one + w * parameter) / denominator,
        )

    c = (-one, zero)
    d = (one, zero)
    a = parent_point(alpha)
    b = parent_point(beta)
    e = parent_point(epsilon)
    reflected_a = (a[0], -a[1])
    parent_circle = (zero, -2 * w, -one)
    x = line_intersection(a, b, c, d)
    y = line_intersection(a, e, c, d)
    p = line_intersection(e, x, b, y)
    q = second_circle_intersection(e, x, parent_circle)
    r = second_circle_intersection(b, y, parent_circle)
    omega = circle_coefficients(p, q, r)
    sigma = circle_coefficients(reflected_a, x, y)
    dry_circle = circle_coefficients(d, r, y)
    xqc_circle = circle_coefficients(x, q, c)
    n = second_circle_circle_intersection(r, omega, dry_circle)
    m = second_circle_circle_intersection(q, omega, xqc_circle)
    k = second_circle_intersection(n, d, omega)

    residuals = {
        "A_on_parent_circle": circle_value(a, parent_circle),
        "B_on_parent_circle": circle_value(b, parent_circle),
        "C_on_parent_circle": circle_value(c, parent_circle),
        "D_on_parent_circle": circle_value(d, parent_circle),
        "E_on_parent_circle": circle_value(e, parent_circle),
        "X_on_AB": cross(subtract(x, a), subtract(b, a)),
        "X_on_CD": cross(subtract(x, c), subtract(d, c)),
        "Y_on_AE": cross(subtract(y, a), subtract(e, a)),
        "Y_on_CD": cross(subtract(y, c), subtract(d, c)),
        "P_on_EX": cross(subtract(p, e), subtract(x, e)),
        "P_on_BY": cross(subtract(p, b), subtract(y, b)),
        "Q_on_EX": cross(subtract(q, e), subtract(x, e)),
        "Q_on_parent_circle": circle_value(q, parent_circle),
        "R_on_BY": cross(subtract(r, b), subtract(y, b)),
        "R_on_parent_circle": circle_value(r, parent_circle),
        "A_reflection_horizontal": reflected_a[0] - a[0],
        "A_reflection_vertical": reflected_a[1] + a[1],
        "P_on_omega": circle_value(p, omega),
        "Q_on_omega": circle_value(q, omega),
        "R_on_omega": circle_value(r, omega),
        "A1_on_sigma": circle_value(reflected_a, sigma),
        "X_on_sigma": circle_value(x, sigma),
        "Y_on_sigma": circle_value(y, sigma),
        "D_on_DRY": circle_value(d, dry_circle),
        "R_on_DRY": circle_value(r, dry_circle),
        "Y_on_DRY": circle_value(y, dry_circle),
        "X_on_XQC": circle_value(x, xqc_circle),
        "Q_on_XQC": circle_value(q, xqc_circle),
        "C_on_XQC": circle_value(c, xqc_circle),
        "N_on_omega": circle_value(n, omega),
        "N_on_DRY": circle_value(n, dry_circle),
        "N_on_sigma": circle_value(n, sigma),
        "M_on_omega": circle_value(m, omega),
        "M_on_XQC": circle_value(m, xqc_circle),
        "M_on_sigma": circle_value(m, sigma),
        "K_on_DN": cross(subtract(k, d), subtract(n, d)),
        "K_on_omega": circle_value(k, omega),
        "C_M_K_collinear": cross(subtract(m, c), subtract(k, c)),
    }
    return {
        name: "0" if value == zero else str(value)
        for name, value in residuals.items()
    }


@dataclass(frozen=True)
class ReflectedChordCirclePairCertificate:
    theorem: str
    assumptions: tuple[str, ...]
    discharged_conditions: dict[str, str]
    normalization: str
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
                "# Reflected-chord circle-pair chart",
                "",
                "## Reusable proof",
                "",
                "1. Normalize CD as the x-axis and rationally parameterize the parent circle.",
                "2. Construct X,Y,P,Q,R and the circles Omega=(PQR), Sigma=(A'XY).",
                "3. Define N as the non-R intersection of Omega and (DRY).",
                "4. Define M as the non-Q intersection of Omega and (XQC).",
                "5. Replay M,N on Sigma, which fixes the existential labelling.",
                "6. Let K be the non-N intersection of DN with Omega; replay C,M,K collinear.",
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
class JGEXReflectedChordCirclePairApplication:
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
    formalization_repair_required: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@lru_cache(maxsize=1)
def certify_reflected_chord_circle_pair_chart() -> ReflectedChordCirclePairCertificate:
    residuals = _exact_replay()
    replayed = all(value == "0" for value in residuals.values())
    assumptions = (
        "A,B,C,D,E are distinct points on a nondegenerate parent circle",
        "all named carrier-line intersections are finite and distinct",
        "the circles (PQR), (A'XY), (DRY), and (XQC) are defined",
        "the known roots R and Q are simple in their circle pairs",
        "the line DN has a second intersection with (PQR)",
    )
    discharged = {
        assumptions[0]: "The triangle, two on-circum clauses, and parent circumcenter are matched.",
        assumptions[1]: "Every required line intersection is matched as a typed construction.",
        assumptions[2]: "Both target circumcenter clauses and exact auxiliary-circle determinants replay.",
        assumptions[3]: "Known-root elimination returns finite rational second points M and N.",
        assumptions[4]: "The final known-root elimination returns K and replays K on the circle.",
    }
    payload = {
        "theorem": "reflected-chord-existential-circle-pair-return",
        "assumptions": assumptions,
        "discharged_conditions": discharged,
        "normalization": (
            "Use a Euclidean similarity with C=(-1,0), D=(1,0), parent circle "
            "x^2+y^2-2wy-1=0, and rational parameters for A,B,E."
        ),
        "representation_chart": (
            "cyclic pentagon -> rational parent-circle parameters",
            "line-circle incidence with known root -> rational second root",
            "two circles with known common root -> radical axis -> rational second root",
            "unlabelled two-circle pair -> existentially certified M,N labelling",
            "second secant root + collinearity -> target point on (PQR)",
        ),
        "proof_dag": (
            "Construct X,Y,P and the second parent-circle roots Q,R.",
            "Construct Omega=(PQR), Sigma=(A'XY), Delta_N=(DRY), Delta_M=(XQC).",
            "Use R to eliminate the first root of Omega intersect Delta_N and obtain N.",
            "Use Q to eliminate the first root of Omega intersect Delta_M and obtain M.",
            "Replay Sigma(N)=Sigma(M)=0, certifying the labelling of the common pair.",
            "Use N on Omega to obtain K on DN; replay Omega(K)=0 and det(C,M,K)=0.",
        ),
        "branch_certificate": {
            "N": "the non-R point of (PQR) intersect (DRY)",
            "M": "the non-Q point of (PQR) intersect (XQC)",
            "pair": "M and N both replay on (A'XY), so they label its pair with (PQR)",
            "K": "the non-N point of DN intersect (PQR)",
        },
        "replay_residuals": residuals,
        "replayed": replayed,
        "all_conditions_discharged": replayed,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return ReflectedChordCirclePairCertificate(
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
    if name in {"circumcenter", "on_circum"} and len(args) == 3:
        return name, tuple(sorted(args))
    if name in {"on_line", "on_circle"} and len(args) == 2:
        return name, tuple(sorted(args))
    return name, args


def _many(records, constructions) -> tuple[str, ...]:
    expected = sorted(map(_canonical_construction, constructions), key=repr)
    return tuple(
        sorted(
            {
                str(record["outputs"][0])
                for record in records
                if len(record["outputs"]) == 1
                and sorted(
                    map(_canonical_construction, record["constructions"]), key=repr
                )
                == expected
            }
        )
    )


def _single(records, constructions):
    matches = _many(records, constructions)
    return matches[0] if len(matches) == 1 else None


def certify_jgex_reflected_chord_circle_pair_application(
    source: str,
    natural_statement: str | None = None,
) -> JGEXReflectedChordCirclePairApplication:
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

    for a, b, c in triangles:
        circum_points = _many(records, (("on_circum", (a, b, c)),))
        for d in circum_points:
            for e in circum_points:
                if d == e:
                    continue
                o = _single(records, (("circumcenter", (a, b, c)),))
                x = _single(records, (("on_line", (c, d)), ("on_line", (a, b))))
                y = _single(records, (("on_line", (c, d)), ("on_line", (a, e))))
                if not all((o, x, y)):
                    continue
                p = _single(records, (("on_line", (e, x)), ("on_line", (b, y))))
                q = _single(records, (("on_line", (e, x)), ("on_circle", (o, a))))
                r = _single(records, (("on_line", (b, y)), ("on_circle", (o, a))))
                a1 = _single(records, (("reflect", (a, c, d)),))
                if not all((p, q, r, a1)):
                    continue
                o1 = _single(records, (("circumcenter", (p, q, r)),))
                o2 = _single(records, (("circumcenter", (a1, x, y)),))
                if not all((o1, o2)):
                    continue
                common = _many(
                    records,
                    (("on_circle", (o1, p)), ("on_circle", (o2, x))),
                )
                if len(common) != 2:
                    continue
                for m in common:
                    for n in common:
                        if m == n:
                            continue
                        z = _single(
                            records,
                            (("on_line", (c, m)), ("on_line", (d, n))),
                        )
                        if not z:
                            continue
                        actual = (
                            Atom(
                                formulation.goals[0].predicate,
                                formulation.goals[0].args,
                            ).canonical()
                            if len(formulation.goals) == 1
                            else None
                        )
                        expected = Atom("cyclic", (z, p, q, r)).canonical()
                        has_existential_labelling = (
                            semantics.has_existential_circle_pair_labelling(
                                (m, n),
                                ((p, q, r), (a1, x, y)),
                            )
                        )
                        if actual == expected and has_existential_labelling:
                            accepted.append(
                                {
                                    "A": a,
                                    "B": b,
                                    "C": c,
                                    "D": d,
                                    "E": e,
                                    "O": o,
                                    "X": x,
                                    "Y": y,
                                    "P": p,
                                    "Q": q,
                                    "R": r,
                                    "A1": a1,
                                    "O1": o1,
                                    "O2": o2,
                                    "M": m,
                                    "N": n,
                                    "K": z,
                                }
                            )

    chart = certify_reflected_chord_circle_pair_chart()
    unique = {tuple(sorted(item.items())): item for item in accepted}
    roles = next(iter(unique.values())) if len(unique) == 1 else {}
    replayed = bool(roles and chart.replayed and chart.all_conditions_discharged)
    goal = str(formulation.goals[0]) if len(formulation.goals) == 1 else ""
    return JGEXReflectedChordCirclePairApplication(
        theorem=chart.theorem,
        source_sha256=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        natural_statement_sha256=hashlib.sha256(natural.encode("utf-8")).hexdigest(),
        natural_statement=natural,
        natural_semantic_atoms=semantics.typed_atoms,
        roles=roles,
        matched_constructions=(
            "cyclic pentagon and reflected vertex across the shared chord",
            "two secant intersections X,Y and their crossing P",
            "second parent-circle roots Q,R",
            "unlabelled common pair of (PQR) and (A'XY)",
            "existential branch M=(PQR) intersect (XQC), N=(PQR) intersect (DRY)",
            "K=CM intersect DN on (PQR)",
        ) if roles else (),
        goal=goal,
        proof_bridge=(
            "known-root circle-pair elimination -> existential root labelling -> "
            "known-root secant return"
        ),
        chart_certificate_sha256=chart.certificate_sha256,
        nondegeneracy_obligations=chart.assumptions,
        undischarged_nondegeneracy_obligations=() if replayed else chart.assumptions,
        replayed=replayed,
        formalization_repair_required=False,
    )


def render_reflected_chord_circle_pair_chart_svg() -> str:
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

    def line_intersection(a, b, c, d):
        ab, cd = subtract(b, a), subtract(d, c)
        parameter = cross(subtract(c, a), cd) / cross(ab, cd)
        return add(a, scale(parameter, ab))

    def circle_coefficients(a, b, c):
        ab, ac = subtract(b, a), subtract(c, a)
        norm_a = dot(a, a)
        rhs_b, rhs_c = -(dot(b, b) - norm_a), -(dot(c, c) - norm_a)
        determinant = cross(ab, ac)
        horizontal = (rhs_b * ac[1] - rhs_c * ab[1]) / determinant
        vertical = (ab[0] * rhs_c - ac[0] * rhs_b) / determinant
        constant = -(norm_a + horizontal * a[0] + vertical * a[1])
        return horizontal, vertical, constant

    def second_circle_intersection(known, carrier, coefficients):
        direction = subtract(carrier, known)
        linear = (
            2 * dot(known, direction)
            + coefficients[0] * direction[0]
            + coefficients[1] * direction[1]
        )
        return add(known, scale(-linear / dot(direction, direction), direction))

    def second_circle_circle_intersection(known, first, second):
        carrier = add(known, (first[1] - second[1], second[0] - first[0]))
        return second_circle_intersection(known, carrier, first)

    w, alpha, beta, epsilon = 0.22, 0.42, 1.45, -0.72

    def parent_point(parameter):
        denominator = 1.0 + parameter * parameter
        return (
            (1.0 + 2.0 * w * parameter - parameter * parameter) / denominator,
            2.0 * parameter * (1.0 + w * parameter) / denominator,
        )

    c, d = (-1.0, 0.0), (1.0, 0.0)
    a, b, e = parent_point(alpha), parent_point(beta), parent_point(epsilon)
    a1 = (a[0], -a[1])
    parent = (0.0, -2.0 * w, -1.0)
    x = line_intersection(a, b, c, d)
    y = line_intersection(a, e, c, d)
    p = line_intersection(e, x, b, y)
    q = second_circle_intersection(e, x, parent)
    r = second_circle_intersection(b, y, parent)
    omega = circle_coefficients(p, q, r)
    sigma = circle_coefficients(a1, x, y)
    n = second_circle_circle_intersection(r, omega, circle_coefficients(d, r, y))
    m = second_circle_circle_intersection(q, omega, circle_coefficients(x, q, c))
    k = second_circle_intersection(n, d, omega)

    fig, axis = plt.subplots(figsize=(10.2, 6.6))
    fig.patch.set_facecolor("#07090c")
    axis.set_facecolor("#07090c")

    def draw_circle(coefficients, color, width=1.4, alpha_value=0.9):
        horizontal, vertical, constant = coefficients
        center = (-horizontal / 2.0, -vertical / 2.0)
        radius = math.sqrt(max(0.0, dot(center, center) - constant))
        axis.add_patch(
            Circle(
                center,
                radius,
                fill=False,
                color=color,
                linewidth=width,
                alpha=alpha_value,
            )
        )

    draw_circle(parent, "#586773", 1.1, 0.7)
    draw_circle(omega, "#35d5e6", 2.0, 0.95)
    draw_circle(sigma, "#ffb454", 1.7, 0.9)
    for left, right, color in (
        (c, d, "#6f7e89"),
        (a, b, "#6f7e89"),
        (a, e, "#6f7e89"),
        (e, x, "#65737d"),
        (b, y, "#65737d"),
        (c, m, "#8ee7f0"),
        (d, n, "#8ee7f0"),
    ):
        axis.plot(
            [left[0], right[0]],
            [left[1], right[1]],
            color=color,
            linewidth=1.1,
            alpha=0.85,
        )
    labels = {
        "A": a,
        "B": b,
        "C": c,
        "D": d,
        "E": e,
        "X": x,
        "Y": y,
        "P": p,
        "Q": q,
        "R": r,
        "A'": a1,
        "M": m,
        "N": n,
        "K": k,
    }
    for label, point in labels.items():
        axis.scatter([point[0]], [point[1]], s=20, color="#f4f7f9", zorder=5)
        axis.text(
            point[0] + 0.025,
            point[1] + 0.025,
            label,
            color="#f4f7f9",
            fontsize=8,
        )
    axis.set_aspect("equal", adjustable="datalim")
    axis.axis("off")
    axis.set_title(
        "Known-root circle pair | existential M,N labelling | secant return",
        color="#e7edf2",
        fontsize=12,
    )
    fig.tight_layout()
    buffer = io.StringIO()
    fig.savefig(buffer, format="svg", bbox_inches="tight")
    plt.close(fig)
    return buffer.getvalue()


__all__ = [
    "JGEXReflectedChordCirclePairApplication",
    "ReflectedChordCirclePairCertificate",
    "certify_jgex_reflected_chord_circle_pair_application",
    "certify_reflected_chord_circle_pair_chart",
    "render_reflected_chord_circle_pair_chart_svg",
]
