"""Exact coordinate chart for an orthocenter/circumcircle construction.

The chart is independent of benchmark identifiers.  It proves the following
construction family by a Euclidean-similarity normalization:

* ``H`` and ``O`` are the orthocenter and circumcenter of ``ABC``;
* ``M`` and ``N`` are the midpoints of ``AH`` and ``BC``;
* ``G`` is the second common point of the circle with centre ``M`` through
  ``A`` and the circumcircle of ``ABC``;
* ``Q`` is the second intersection of ``AN`` with the first circle;
* the tangent at ``G`` meets ``OM`` at ``P``;
* the circumcircles of ``GNQ`` and ``MBC`` have a common point on ``PN``.

Every coordinate and factorization displayed in the readable proof is
replayed symbolically.  The final statement is existential: it identifies the
intersection branch on ``PN`` rather than asserting that both intersections
of the two circles lie on that line.
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
from worker.backend.jgex_chart_parser import ChartJGEXFormulation as JGEXFormulation

from worker.backend.geometry_proof_hypergraph import Atom
from worker.backend.typed_existential_incidence import (
    audit_jgex_multivalued_intersections,
    certify_typed_existential_incidence,
)


@dataclass(frozen=True)
class OrthocenterCircleChartCertificate:
    theorem: str
    assumptions: tuple[str, ...]
    normalization: str
    coordinates: dict[str, tuple[str, str]]
    first_circle: str
    second_circle: str
    line_parameterization: str
    common_factor: str
    selected_root: str
    discharged_conditions: dict[str, str]
    all_conditions_discharged: bool
    existential_witness: dict[str, object]
    source_branch_counterexample: dict[str, object]
    replay_residuals: dict[str, str]
    replayed: bool
    certificate_sha256: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def to_markdown(self) -> str:
        coordinates = "\n".join(
            f"- `{name}=({value[0]}, {value[1]})`"
            for name, value in self.coordinates.items()
        )
        residuals = "\n".join(
            f"- `{name}`: `{value}`" for name, value in self.replay_residuals.items()
        )
        return "\n".join(
            (
                "# 垂心・中点・2円の共通点チャート",
                "",
                "## 定理",
                "",
                (
                    "上記の構成で、円 $(GNQ)$ と円 $(MBC)$ は直線 $PN$ 上に"
                    "共通点をもつ。すなわち、適切な交点 $T$ に対して "
                    "$P,N,T$ は一直線上にある。"
                ),
                "",
                "## 非退化条件",
                "",
                *(f"- `{item}`" for item in self.assumptions),
                "",
                "## 1. 相似変換による標準化",
                "",
                self.normalization,
                "",
                "## 2. 構成点の座標",
                "",
                coordinates,
                "",
                "## 3. 2円と直線 $PN$",
                "",
                f"- 円 $(GNQ)$: `{self.first_circle}`",
                f"- 円 $(MBC)$: `{self.second_circle}`",
                f"- 直線上の点: `{self.line_parameterization}`",
                "",
                "## 4. 共通因子",
                "",
                (
                    "直線上で2円の方程式を評価すると、両方が次の一次因子を"
                    "共有する。"
                ),
                "",
                f"`{self.common_factor}`",
                "",
                f"その零点は `{self.selected_root}` である。",
                "したがって、その点は2円と直線 $PN$ のすべてに属する。",
                "",
                "## 5. 非退化条件の消去",
                "",
                *(
                    f"- `{condition}`: {reason}"
                    for condition, reason in self.discharged_conditions.items()
                ),
                "",
                f"- 全条件消去: `{self.all_conditions_discharged}`",
                "",
                "## 6. 存在証人と量化",
                "",
                f"- `{self.existential_witness['quantified_formula']}`",
                (
                "- 元の一出力JGEX節は交点分岐を指定しないため、自然文の"
                "存在命題へ量化を修復した。"
                ),
                "- 目標を仮定せず、構成した座標を2円と直線へ代入して再生した。",
                (
                    "- 任意交点版への厳密反例: `"
                    f"{self.source_branch_counterexample['other_branch_collinearity']}`"
                ),
                "",
                "## 7. 恒等式の再生結果",
                "",
                residuals,
                "",
                f"- 全恒等式再生: `{self.replayed}`",
                f"- 証明書 SHA-256: `{self.certificate_sha256}`",
                "",
            )
        )


@dataclass(frozen=True)
class JGEXOrthocenterCircleChartApplication:
    theorem: str
    source_sha256: str
    roles: dict[str, str]
    matched_constructions: tuple[str, ...]
    goal: str
    branch_semantics: str
    source_formalization_status: str
    formalization_repair_required: bool
    repaired_quantified_goal: str
    natural_statement_proved: bool
    arbitrary_source_branch_proved: bool
    chart_certificate_sha256: str
    nondegeneracy_obligations: tuple[str, ...]
    undischarged_nondegeneracy_obligations: tuple[str, ...]
    replayed: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _canonical(expression: sp.Expr) -> str:
    return str(sp.factor(sp.cancel(expression)))


@lru_cache(maxsize=1)
def certify_orthocenter_circle_intersection_chart(
) -> OrthocenterCircleChartCertificate:
    """Replay the complete coordinate derivation as exact identities."""

    u, v, x, y, z = sp.symbols("u v x y z", nonzero=True)
    s = u**2 + v**2
    d = u**4 + u**2 * v**2 - 2 * u**2 + 1
    k = (
        u**6
        + 2 * u**4 * v**2
        - 2 * u**4
        + u**2 * v**4
        - 6 * u**2 * v**2
        + u**2
        + 4 * v**2
    )
    a2, b2 = sp.symbols("A B", positive=True)
    k_ab = (
        a2 * b2**2
        + 2 * (a2 - 1) * (a2 - 2) * b2
        + a2 * (a2 - 1) ** 2
    )
    k_completed_square = (
        a2 * (b2 + (a2 - 1) * (a2 - 2) / a2) ** 2
        + 4 * (a2 - 1) ** 3 / a2
    )

    def point(px: sp.Expr, py: sp.Expr) -> sp.Matrix:
        return sp.Matrix((px, py))

    def norm2(value: sp.Matrix) -> sp.Expr:
        return sp.expand(value.dot(value))

    a = point(u, v)
    b = point(-1, 0)
    c = point(1, 0)
    h = point(u, (1 - u**2) / v)
    o = point(0, (s - 1) / (2 * v))
    m = point(u, (-u**2 + v**2 + 1) / (2 * v))
    n = point(0, 0)
    g = point(u * v**2 / d, -v * (u**2 - 1) / d)
    q = point(u / s, v / s)
    p = point(u * (u**2 - v**2 - 1) / (2 * (u**2 - 1)), v)
    o1 = point(1 / (2 * u), 0)
    o2 = point(0, -(s - 1) ** 2 / (4 * v * (u**2 - v**2 - 1)))
    variable = point(x, y)

    circle1 = sp.cancel(
        norm2(variable - o1) - norm2(g - o1)
    )
    circle2 = sp.cancel(
        norm2(variable - o2) - norm2(m - o2)
    )
    line_point = sp.cancel(z * p)
    common_factor = sp.expand(
        k * z - 2 * (u**2 - 1) * (u**2 - v**2 - 1)
    )
    selected_root = sp.cancel(
        2 * (u**2 - 1) * (u**2 - v**2 - 1) / k
    )
    selected_point = sp.cancel(line_point.subs(z, selected_root))
    first_line_factor = sp.cancel(
        z * common_factor / (4 * (u**2 - 1) ** 2)
    )
    second_line_factor = sp.cancel(
        (
            ((u**2 - v**2 - 1) * z + 2 * (u**2 - 1))
            * common_factor
            / (4 * (u**2 - 1) ** 2 * (u**2 - v**2 - 1))
        )
    )

    residuals: dict[str, sp.Expr] = {
        "orthocenter_altitude_from_A": sp.cancel((h - a).dot(c - b)),
        "orthocenter_altitude_from_B": sp.cancel((h - b).dot(c - a)),
        "M_is_midpoint_AH_x": sp.cancel(2 * m[0] - a[0] - h[0]),
        "M_is_midpoint_AH_y": sp.cancel(2 * m[1] - a[1] - h[1]),
        "N_is_midpoint_BC_x": sp.cancel(2 * n[0] - b[0] - c[0]),
        "N_is_midpoint_BC_y": sp.cancel(2 * n[1] - b[1] - c[1]),
        "O_is_circumcenter_AB": sp.cancel(norm2(o - a) - norm2(o - b)),
        "O_is_circumcenter_AC": sp.cancel(norm2(o - a) - norm2(o - c)),
        "G_on_circle_center_M": sp.cancel(norm2(g - m) - norm2(a - m)),
        "G_on_circumcircle": sp.cancel(norm2(g - o) - norm2(a - o)),
        "Q_on_AN": sp.cancel(a[0] * q[1] - a[1] * q[0]),
        "Q_on_circle_center_M": sp.cancel(norm2(q - m) - norm2(a - m)),
        "P_on_OM": sp.cancel(
            (p[0] - o[0]) * (m[1] - o[1])
            - (p[1] - o[1]) * (m[0] - o[0])
        ),
        "PG_tangent_at_G": sp.cancel((p - g).dot(g - m)),
        "O1_contains_G_and_N": sp.cancel(norm2(g - o1) - norm2(n - o1)),
        "O1_contains_G_and_Q": sp.cancel(norm2(g - o1) - norm2(q - o1)),
        "O2_contains_M_and_B": sp.cancel(norm2(m - o2) - norm2(b - o2)),
        "O2_contains_M_and_C": sp.cancel(norm2(m - o2) - norm2(c - o2)),
        "first_circle_common_factor": sp.cancel(
            circle1.subs({x: line_point[0], y: line_point[1]})
            - first_line_factor
        ),
        "second_circle_common_factor": sp.cancel(
            circle2.subs({x: line_point[0], y: line_point[1]})
            - second_line_factor
        ),
        "selected_root_zeros_common_factor": sp.cancel(
            common_factor.subs(z, selected_root)
        ),
        "selected_point_on_first_circle": sp.cancel(
            circle1.subs(
                {
                    x: line_point[0].subs(z, selected_root),
                    y: line_point[1].subs(z, selected_root),
                }
            )
        ),
        "selected_point_on_second_circle": sp.cancel(
            circle2.subs(
                {
                    x: line_point[0].subs(z, selected_root),
                    y: line_point[1].subs(z, selected_root),
                }
            )
        ),
        "selected_point_collinear_NP": sp.cancel(
            p[0] * line_point[1].subs(z, selected_root)
            - p[1] * line_point[0].subs(z, selected_root)
        ),
        "K_as_positive_domain_quadratic": sp.cancel(
            k - k_ab.subs({a2: u**2, b2: v**2})
        ),
        "K_completed_square_for_A_gt_1": sp.cancel(
            k_ab - k_completed_square
        ),
    }
    rendered_residuals = {
        name: _canonical(value) for name, value in residuals.items()
    }
    sample_substitution = {u: sp.Rational(1, 3), v: sp.Rational(6, 5)}
    sample_good = point(sp.Rational(51483, 146761), sp.Rational(141480, 146761))
    sample_other = point(sp.Rational(6075, 19186), -sp.Rational(17685, 19186))
    sample_p = sp.cancel(p.subs(sample_substitution))
    sample_circle1 = sp.cancel(circle1.subs(sample_substitution))
    sample_circle2 = sp.cancel(circle2.subs(sample_substitution))
    counterexample_residuals = {
        "good_branch_on_first_circle": _canonical(
            sample_circle1.subs({x: sample_good[0], y: sample_good[1]})
        ),
        "good_branch_on_second_circle": _canonical(
            sample_circle2.subs({x: sample_good[0], y: sample_good[1]})
        ),
        "good_branch_on_PN": _canonical(
            sample_p[0] * sample_good[1] - sample_p[1] * sample_good[0]
        ),
        "other_branch_on_first_circle": _canonical(
            sample_circle1.subs({x: sample_other[0], y: sample_other[1]})
        ),
        "other_branch_on_second_circle": _canonical(
            sample_circle2.subs({x: sample_other[0], y: sample_other[1]})
        ),
    }
    other_branch_collinearity = _canonical(
        sample_p[0] * sample_other[1] - sample_p[1] * sample_other[0]
    )
    source_branch_counterexample = {
        "normalization": "u=1/3, v=6/5",
        "on_line_branch": (
            "T_good=(51483/146761,141480/146761)"
        ),
        "other_branch": "T_other=(6075/19186,-17685/19186)",
        "replay_residuals": counterexample_residuals,
        "other_branch_collinearity": (
            f"det(P,T_other)={other_branch_collinearity} != 0"
        ),
        "replayed": (
            all(value == "0" for value in counterexample_residuals.values())
            and other_branch_collinearity != "0"
        ),
    }
    existential_witness = certify_typed_existential_incidence(
        witness="T",
        witness_definition=(
            f"T=N+({_canonical(selected_root)})(P-N)"
        ),
        construction_atoms=(
            Atom("on_circle", ("T", "O1", "G")),
            Atom("on_circle", ("T", "O2", "M")),
        ),
        goal_atom=Atom("coll", ("N", "P", "T")),
        replay_residuals={
            "T_on_circle_GNQ": rendered_residuals[
                "selected_point_on_first_circle"
            ],
            "T_on_circle_MBC": rendered_residuals[
                "selected_point_on_second_circle"
            ],
            "T_on_line_PN": rendered_residuals[
                "selected_point_collinear_NP"
            ],
        },
        source_selects_unique_branch=False,
    )
    discharged_conditions = {
        "v != 0": (
            "B,Cを固定した三角形ABCの面積行列式であり、triangle構成が除外する。"
        ),
        "u != 0": (
            "u=0ではG,N,Qが一直線上となり、circumcenter(G,N,Q)が存在しない。"
        ),
        "u^2+v^2 != 1": (
            "等号時はQ=Aとなり、QをAと異なる第2交点として構成できない。"
        ),
        "u^2 != 1": (
            "等号時はGでの接線とOMが平行になり、有限な交点Pを構成できない。"
        ),
        "u^2-v^2-1 != 0": (
            "等号時はM,B,Cが一直線上となり、circumcenter(M,B,C)が存在しない。"
        ),
        "K(u,v) != 0": (
            "A=u^2>0, B=v^2>0とする。0<A<1ではKの3項の係数がすべて正、"
            "A=1ではK=B^2>0、A>1ではK=A(B+(A-1)(A-2)/A)^2+"
            "4(A-1)^3/A>0。"
        ),
    }
    all_conditions_discharged = (
        rendered_residuals["K_as_positive_domain_quadratic"] == "0"
        and rendered_residuals["K_completed_square_for_A_gt_1"] == "0"
    )
    replayed = (
        all(value == "0" for value in rendered_residuals.values())
        and existential_witness.replayed
        and all_conditions_discharged
        and bool(source_branch_counterexample["replayed"])
    )
    coordinates = {
        name: (_canonical(value[0]), _canonical(value[1]))
        for name, value in {
            "A": a,
            "B": b,
            "C": c,
            "H": h,
            "O": o,
            "M": m,
            "N": n,
            "G": g,
            "Q": q,
            "P": p,
            "O1": o1,
            "O2": o2,
            "T": selected_point,
        }.items()
    }
    payload = {
        "theorem": "orthocenter-midpoint-two-circle-common-point-on-line",
        "assumptions": (
            "v != 0",
            "u != 0",
            "u^2+v^2 != 1",
            "u^2 != 1",
            "u^2-v^2-1 != 0",
            "K(u,v) != 0",
        ),
        "normalization": "B=(-1,0), C=(1,0), A=(u,v)",
        "coordinates": coordinates,
        "first_circle": f"{_canonical(circle1)} = 0",
        "second_circle": f"{_canonical(circle2)} = 0",
        "line_parameterization": "X(z)=N+z(P-N)=zP",
        "common_factor": f"L(z)={_canonical(common_factor)}",
        "selected_root": f"z_T={_canonical(selected_root)}",
        "discharged_conditions": discharged_conditions,
        "all_conditions_discharged": all_conditions_discharged,
        "existential_witness": existential_witness.to_dict(),
        "source_branch_counterexample": source_branch_counterexample,
        "replay_residuals": rendered_residuals,
        "replayed": replayed,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return OrthocenterCircleChartCertificate(
        **payload,
        certificate_sha256=digest,
    )


def render_orthocenter_circle_chart_svg(
    *, u_value: float = 1 / 3, v_value: float = 6 / 5
) -> str:
    """Render construction and proof-focus panels for one nondegenerate model."""

    u = float(u_value)
    v = float(v_value)
    s = u * u + v * v
    d = u**4 + u * u * v * v - 2 * u * u + 1
    k = (
        u**6
        + 2 * u**4 * v**2
        - 2 * u**4
        + u**2 * v**4
        - 6 * u**2 * v**2
        + u**2
        + 4 * v**2
    )
    points = {
        "A": (u, v),
        "B": (-1.0, 0.0),
        "C": (1.0, 0.0),
        "H": (u, (1 - u * u) / v),
        "O": (0.0, (s - 1) / (2 * v)),
        "M": (u, (-u * u + v * v + 1) / (2 * v)),
        "N": (0.0, 0.0),
        "G": (u * v * v / d, -v * (u * u - 1) / d),
        "Q": (u / s, v / s),
        "P": (u * (u * u - v * v - 1) / (2 * (u * u - 1)), v),
        "O1": (1 / (2 * u), 0.0),
        "O2": (0.0, -(s - 1) ** 2 / (4 * v * (u * u - v * v - 1))),
    }
    z_t = 2 * (u * u - 1) * (u * u - v * v - 1) / k
    points["T"] = (z_t * points["P"][0], z_t * points["P"][1])

    def distance(left: str, right: str) -> float:
        return (
            (points[left][0] - points[right][0]) ** 2
            + (points[left][1] - points[right][1]) ** 2
        ) ** 0.5

    def segment(axes, left: str, right: str, **kwargs) -> None:
        axes.plot(
            (points[left][0], points[right][0]),
            (points[left][1], points[right][1]),
            **kwargs,
        )

    def label_points(
        axes,
        names: tuple[str, ...],
        highlight: set[str],
        offsets: dict[str, tuple[int, int]] | None = None,
    ) -> None:
        offsets = offsets or {}
        for name in names:
            px, py = points[name]
            color = "#e11d48" if name in highlight else "#0f172a"
            axes.scatter((px,), (py,), s=26, color=color, zorder=5)
            axes.annotate(
                name,
                (px, py),
                xytext=offsets.get(name, (5, 5)),
                textcoords="offset points",
                fontsize=9,
                color=color,
                weight="bold" if name in highlight else "normal",
            )

    figure, axes = plt.subplots(1, 2, figsize=(12, 5), constrained_layout=True)
    figure.patch.set_facecolor("#f8fafc")
    for axis in axes:
        axis.set_facecolor("#ffffff")
        axis.set_aspect("equal", adjustable="datalim")
        axis.axis("off")

    left, right = axes
    left.set_title(
        "構成", loc="left", fontsize=13, color="#0f172a", fontfamily="Yu Gothic"
    )
    for first, second in (("A", "B"), ("B", "C"), ("C", "A")):
        segment(left, first, second, color="#64748b", linewidth=1.2)
    for first, second in (
        ("A", "H"),
        ("A", "N"),
        ("O", "M"),
        ("P", "G"),
    ):
        segment(left, first, second, color="#94a3b8", linewidth=1.0)
    left.add_patch(
        Circle(
            points["M"],
            distance("M", "A"),
            fill=False,
            color="#0891b2",
            linewidth=1.8,
        )
    )
    left.add_patch(
        Circle(
            points["O"],
            distance("O", "A"),
            fill=False,
            color="#7c3aed",
            linewidth=1.4,
        )
    )
    label_points(
        left,
        ("A", "B", "C", "H", "O", "M", "N", "G", "Q", "P"),
        {"G", "Q", "P"},
        {
            "A": (-17, -15),
            "M": (-17, 2),
            "H": (6, 2),
            "N": (5, -14),
            "G": (7, -10),
            "P": (-15, 16),
            "Q": (-14, -11),
        },
    )

    right.set_title(
        "証明に使う2円と直線",
        loc="left",
        fontsize=13,
        color="#0f172a",
        fontfamily="Yu Gothic",
    )
    right.add_patch(
        Circle(
            points["O1"],
            distance("O1", "G"),
            fill=False,
            color="#0891b2",
            linewidth=2.0,
            label="(GNQ)",
        )
    )
    right.add_patch(
        Circle(
            points["O2"],
            distance("O2", "M"),
            fill=False,
            color="#7c3aed",
            linewidth=2.0,
            label="(MBC)",
        )
    )
    segment(right, "N", "P", color="#e11d48", linewidth=2.2)
    label_points(
        right,
        ("B", "C", "M", "N", "G", "Q", "P", "T", "O1", "O2"),
        {"N", "P", "T"},
        {
            "N": (-17, -14),
            "O2": (7, 5),
            "P": (7, 8),
            "G": (8, -10),
            "T": (-17, 8),
            "Q": (7, 6),
            "O1": (7, 5),
        },
    )
    right.legend(loc="upper right", frameon=False, fontsize=9)
    for axis in axes:
        axis.relim()
        axis.autoscale_view()
        axis.margins(0.14)

    output = io.StringIO()
    figure.savefig(output, format="svg", facecolor=figure.get_facecolor())
    plt.close(figure)
    return output.getvalue()


def _clause_records(formulation: JGEXFormulation) -> tuple[dict[str, object], ...]:
    records: list[dict[str, object]] = []
    for clause in formulation.setup_clauses:
        records.append(
            {
                "outputs": tuple(map(str, clause.points)),
                "constructions": tuple(
                    (construction.name, tuple(map(str, construction.args)))
                    for construction in clause.constructions
                ),
            }
        )
    return tuple(records)


def _single_output(
    records: tuple[dict[str, object], ...],
    construction_name: str,
    arguments: tuple[str, ...],
) -> str | None:
    for record in records:
        if (
            len(record["outputs"]) == 1
            and record["constructions"] == ((construction_name, arguments),)
        ):
            return record["outputs"][0]
    return None


def _intersection_output(
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


def certify_jgex_orthocenter_circle_chart_application(
    source: str,
) -> JGEXOrthocenterCircleChartApplication:
    """Match the construction dependency graph, never a problem identifier."""

    normalized = source.strip()
    formulation = JGEXFormulation.from_text(normalized)
    records = _clause_records(formulation)
    triangle = next(
        (
            tuple(record["outputs"])
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
        h = _single_output(records, "orthocenter", (a, b, c))
        o = _single_output(records, "circumcenter", (a, b, c))
        if h is not None and o is not None:
            roles.update(H=h, O=o)
            matched.append("orthocenter and circumcenter")
            m = _single_output(records, "midpoint", (a, h))
            n = _single_output(records, "midpoint", (b, c))
            if m is not None and n is not None:
                roles.update(M=m, N=n)
                matched.append("midpoints of AH and BC")
                g = _intersection_output(
                    records,
                    frozenset(
                        {
                            ("on_circle", (m, a)),
                            ("on_circle", (o, a)),
                        }
                    ),
                )
                q = _intersection_output(
                    records,
                    frozenset(
                        {
                            ("on_line", (a, n)),
                            ("on_circle", (m, a)),
                        }
                    ),
                )
                if g is not None and q is not None:
                    roles.update(G=g, Q=q)
                    matched.append("G and Q on the diameter circle")
                    p = _intersection_output(
                        records,
                        frozenset(
                            {
                                ("on_tline", (g, m, g)),
                                ("on_line", (o, m)),
                            }
                        ),
                    )
                    if p is not None:
                        roles["P"] = p
                        matched.append("tangent at G intersects OM")
                        o1 = _single_output(records, "circumcenter", (g, n, q))
                        o2 = _single_output(records, "circumcenter", (m, b, c))
                        if o1 is not None and o2 is not None:
                            roles.update(O1=o1, O2=o2)
                            matched.append("circumcircles GNQ and MBC")
                            t = _intersection_output(
                                records,
                                frozenset(
                                    {
                                        ("on_circle", (o1, g)),
                                        ("on_circle", (o2, m)),
                                    }
                                ),
                            )
                            if t is not None:
                                roles["T"] = t
                                matched.append("selected common point T")

    goal = str(formulation.goals[0]) if len(formulation.goals) == 1 else ""
    goal_matches = False
    if all(name in roles for name in ("N", "P", "T")):
        expected = Atom("coll", (roles["N"], roles["P"], roles["T"]))
        parts = goal.split()
        if len(parts) == 4:
            goal_matches = Atom(parts[0], tuple(parts[1:])).canonical() == expected.canonical()
    chart = certify_orthocenter_circle_intersection_chart()
    witness = chart.existential_witness
    branch_obligations = audit_jgex_multivalued_intersections(normalized)
    target_branch_obligation = next(
        (
            obligation
            for obligation in branch_obligations
            if obligation.output == roles.get("T")
        ),
        None,
    )
    formalization_repair_required = target_branch_obligation is not None
    replayed = (
        chart.replayed
        and len(roles) == 13
        and len(matched) == 6
        and goal_matches
        and bool(witness["replayed"])
        and chart.all_conditions_discharged
    )
    return JGEXOrthocenterCircleChartApplication(
        theorem=chart.theorem,
        source_sha256=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        roles=roles,
        matched_constructions=tuple(matched),
        goal=goal,
        branch_semantics=(
            "The natural theorem is existential: one common point lies on PN.  The "
            + (
                "one-output JGEX clause does not select that branch, so the exact "
                "witness T=N+z_T(P-N) repairs the quantifier before replay."
                if formalization_repair_required
                else "source construction supplies a unique branch."
            )
        ),
        source_formalization_status=(
            "branch_quantifier_mismatch"
            if formalization_repair_required
            else "source_branch_unique"
        ),
        formalization_repair_required=formalization_repair_required,
        repaired_quantified_goal=str(witness["quantified_formula"]),
        natural_statement_proved=replayed,
        arbitrary_source_branch_proved=(
            replayed and not formalization_repair_required
        ),
        chart_certificate_sha256=chart.certificate_sha256,
        nondegeneracy_obligations=chart.assumptions,
        undischarged_nondegeneracy_obligations=(),
        replayed=replayed,
    )


__all__ = [
    "JGEXOrthocenterCircleChartApplication",
    "OrthocenterCircleChartCertificate",
    "certify_jgex_orthocenter_circle_chart_application",
    "certify_orthocenter_circle_intersection_chart",
    "render_orthocenter_circle_chart_svg",
]
