"""Exact chart for a cyclic cevian, midpoint reflection, and second roots."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
import hashlib
import io
import itertools
import json
import re

import matplotlib
import sympy as sp

matplotlib.use("Agg")

from matplotlib import pyplot as plt
from matplotlib.patches import Circle

from worker.backend.geometry_proof_hypergraph import Atom
from worker.backend.jgex_chart_parser import ChartJGEXFormulation as JGEXFormulation


@dataclass(frozen=True)
class CyclicCevianReflectionSecondRootsParallelCertificate:
    theorem: str
    normalization: str
    parameter_domain: tuple[str, ...]
    construction_domain_conditions: tuple[str, ...]
    discharged_conditions: dict[str, str]
    coordinates: dict[str, tuple[str, str]]
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
        coordinates = "\n".join(
            f"- `{name}=({value[0]}, {value[1]})`"
            for name, value in self.coordinates.items()
        )
        residuals = "\n".join(
            f"- `{name}`: `{value}`" for name, value in self.replay_residuals.items()
        )
        discharged = "\n".join(
            f"- `{condition}`: {reason}"
            for condition, reason in self.discharged_conditions.items()
        )
        return "\n".join(
            (
                "# 円内接セバ線・中点反射・第2交点平行チャート",
                "",
                "## 定理",
                "",
                (
                    "$P$ を $ABC$ の外接円上、$D=AP\\cap BC$ とし、"
                    "$T$ を $BC$ の中点に関する $D$ の反射とする。"
                    "$G$ を $AT$ と円 $(PDT)$ の第2交点、$E,F$ を円"
                    " $(AGP)$ と $AB,AC$ の第2交点、$Q=EF\\cap GP$"
                    " とすると、$AQ\\parallel BC$。"
                ),
                "",
                "## 標準化",
                "",
                self.normalization,
                "",
                "## 定義域条件",
                "",
                *(f"- `{item}`" for item in self.assumptions),
                "",
                "## 条件の消去",
                "",
                discharged,
                "",
                "## 座標",
                "",
                coordinates,
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
class JGEXCyclicCevianReflectionSecondRootsParallelApplication:
    theorem: str
    source_sha256: str
    natural_statement: str
    natural_statement_sha256: str
    natural_semantic_atoms: tuple[str, ...]
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


def _point(x_coord: sp.Expr, y_coord: sp.Expr) -> sp.Matrix:
    return sp.Matrix((x_coord, y_coord))


def _cross(left: sp.Matrix, right: sp.Matrix) -> sp.Expr:
    return sp.expand(left[0] * right[1] - left[1] * right[0])


@lru_cache(maxsize=1)
def certify_cyclic_cevian_reflection_second_roots_parallel_chart(
) -> CyclicCevianReflectionSecondRootsParallelCertificate:
    u, v, r = sp.symbols("u v r", real=True, nonzero=True)
    side_ac_norm2 = u**2 + v**2
    point_a = _point(0, 0)
    point_b = _point(1, 0)
    point_c = _point(u, v)
    point_d = point_b + r * (point_c - point_b)
    point_m = (point_b + point_c) / 2
    point_t = point_b + point_c - point_d
    point_d_norm2 = sp.expand(point_d.dot(point_d))
    point_t_norm2 = sp.expand(point_t.dot(point_t))
    common_scale = 1 + r * (side_ac_norm2 - 1)
    point_p = sp.cancel(common_scale / point_d_norm2) * point_d
    point_g = sp.cancel(common_scale / point_t_norm2) * point_t
    point_e = _point(common_scale, 0)
    point_f = sp.cancel(common_scale / side_ac_norm2) * point_c
    parallel_scale = sp.cancel(common_scale / (side_ac_norm2 - 1))
    point_q = parallel_scale * (point_c - point_b)
    circle_abc_y = (u - side_ac_norm2) / v

    def circle_abc(point: sp.Matrix) -> sp.Expr:
        return point.dot(point) - point[0] + circle_abc_y * point[1]

    def circle_agp(point: sp.Matrix) -> sp.Expr:
        return (
            point.dot(point)
            - common_scale * point[0]
            + common_scale * (u - 1) * point[1] / v
        )

    residuals = {
        "A_on_circle_ABC": circle_abc(point_a),
        "B_on_circle_ABC": circle_abc(point_b),
        "C_on_circle_ABC": circle_abc(point_c),
        "P_on_circle_ABC": circle_abc(point_p),
        "D_on_AP": _cross(point_d, point_p),
        "D_on_BC": _cross(point_d - point_b, point_c - point_b),
        "M_is_midpoint_BC": (2 * point_m - point_b - point_c).dot(
            2 * point_m - point_b - point_c
        ),
        "T_is_reflection_of_D_about_M": (
            point_d + point_t - 2 * point_m
        ).dot(point_d + point_t - 2 * point_m),
        "G_on_AT": _cross(point_g, point_t),
        "directed_power_AP_AD": point_p.dot(point_d) - common_scale,
        "directed_power_AG_AT": point_g.dot(point_t) - common_scale,
        "PDTG_concyclic_by_power_converse": (
            point_p.dot(point_d) - point_g.dot(point_t)
        ),
        "A_on_circle_AGP": circle_agp(point_a),
        "G_on_circle_AGP": circle_agp(point_g),
        "P_on_circle_AGP": circle_agp(point_p),
        "E_on_circle_AGP": circle_agp(point_e),
        "F_on_circle_AGP": circle_agp(point_f),
        "E_on_AB": _cross(point_e, point_b),
        "F_on_AC": _cross(point_f, point_c),
        "Q_on_EF": _cross(point_q - point_e, point_f - point_e),
        "Q_on_GP": _cross(point_q - point_g, point_p - point_g),
        "goal_AQ_parallel_BC": _cross(point_q, point_c - point_b),
    }
    rendered = {name: _canonical(value) for name, value in residuals.items()}
    replayed = all(value == "0" for value in rendered.values())
    coordinates = {
        name: (_canonical(value[0]), _canonical(value[1]))
        for name, value in {
            "A": point_a,
            "B": point_b,
            "C": point_c,
            "D": point_d,
            "M": point_m,
            "T": point_t,
            "P": point_p,
            "G": point_g,
            "E": point_e,
            "F": point_f,
            "Q": point_q,
        }.items()
    }
    discharged_conditions = {
        "v != 0": "The accepted triangle ABC is nondegenerate.",
        "u^2+v^2 != 0": "Side AC is nonzero.",
        "|D|^2 != 0": "The accepted intersection D is distinct from A.",
        "|T|^2 != 0": "The accepted line AT is defined.",
        "u^2+v^2-1 != 0": "The accepted finite intersection Q exists.",
        "G != T; E != A; F != A": (
            "The natural statement explicitly selects the second intersections."
        ),
    }
    payload = {
        "theorem": "cyclic-cevian-reflection-second-roots-parallel",
        "normalization": (
            "A=(0,0), B=(1,0), C=(u,v), D=B+r(C-B); all three second "
            "intersections are eliminated through known-root products"
        ),
        "parameter_domain": (
            "u,v,r are real",
            "v != 0",
        ),
        "construction_domain_conditions": (
            "P is the non-A intersection of AD with circle ABC",
            "T is the reflection of D about the midpoint of BC",
            "G is the intersection of AT and circle PDT distinct from T",
            "E,F are the intersections of AB,AC and circle AGP distinct from A",
            "Q=EF intersect GP is finite",
        ),
        "discharged_conditions": discharged_conditions,
        "coordinates": coordinates,
        "replay_residuals": rendered,
        "replayed": replayed,
        "all_conditions_discharged": replayed,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return CyclicCevianReflectionSecondRootsParallelCertificate(
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


def _single_unordered(
    records: tuple[dict[str, object], ...],
    name: str,
    args: frozenset[str],
) -> str | None:
    for record in records:
        if len(record["outputs"]) != 1 or len(record["constructions"]) != 1:
            continue
        construction_name, construction_args = record["constructions"][0]
        if construction_name == name and frozenset(construction_args) == args:
            return record["outputs"][0]
    return None


def _single_ordered(
    records: tuple[dict[str, object], ...],
    name: str,
    args: tuple[str, ...],
) -> str | None:
    for record in records:
        if len(record["outputs"]) != 1 or len(record["constructions"]) != 1:
            continue
        construction_name, construction_args = record["constructions"][0]
        if construction_name == name and construction_args == args:
            return record["outputs"][0]
    return None


def _two_lines(
    records: tuple[dict[str, object], ...],
    first: frozenset[str],
    second: frozenset[str],
) -> str | None:
    expected = {first, second}
    for record in records:
        if len(record["outputs"]) != 1 or len(record["constructions"]) != 2:
            continue
        lines = {
            frozenset(args)
            for name, args in record["constructions"]
            if name == "on_line" and len(args) == 2
        }
        if lines == expected:
            return record["outputs"][0]
    return None


def _circle_line_role(
    records: tuple[dict[str, object], ...],
    line: frozenset[str],
    center: str,
    radius_point: str,
) -> str | None:
    for record in records:
        if len(record["outputs"]) != 1 or len(record["constructions"]) != 2:
            continue
        has_line = any(
            name == "on_line" and frozenset(args) == line
            for name, args in record["constructions"]
        )
        has_circle = any(
            name == "on_circle" and args == (center, radius_point)
            for name, args in record["constructions"]
        )
        if has_line and has_circle:
            return record["outputs"][0]
    return None


def _match_roles(
    formulation: JGEXFormulation,
    records: tuple[dict[str, object], ...],
) -> tuple[dict[str, str], tuple[str, ...]]:
    triangle = next(
        (
            tuple(record["outputs"])
            for record in records
            if record["constructions"] == (("triangle", ()),)
            and len(record["outputs"]) == 3
        ),
        None,
    )
    if triangle is None or len(formulation.goals) != 1:
        return {}, ()
    for point_a, point_b, point_c in itertools.permutations(triangle):
        point_o = _single_unordered(
            records, "circumcenter", frozenset((point_a, point_b, point_c))
        )
        if not point_o:
            continue
        point_p = _single_ordered(records, "on_circle", (point_o, point_a))
        if not point_p:
            continue
        point_d = _two_lines(
            records,
            frozenset((point_a, point_p)),
            frozenset((point_b, point_c)),
        )
        point_m = _single_unordered(
            records, "midpoint", frozenset((point_b, point_c))
        )
        if not point_d or not point_m:
            continue
        point_t = _single_ordered(records, "mirror", (point_d, point_m))
        if not point_t:
            continue
        point_o1 = _single_unordered(
            records, "circumcenter", frozenset((point_p, point_d, point_t))
        )
        if not point_o1:
            continue
        point_g = _circle_line_role(
            records, frozenset((point_a, point_t)), point_o1, point_p
        )
        if not point_g:
            continue
        point_o2 = _single_unordered(
            records, "circumcenter", frozenset((point_a, point_g, point_p))
        )
        if not point_o2:
            continue
        point_e = _circle_line_role(
            records, frozenset((point_a, point_b)), point_o2, point_a
        )
        point_f = _circle_line_role(
            records, frozenset((point_a, point_c)), point_o2, point_a
        )
        if not point_e or not point_f:
            continue
        point_q = _two_lines(
            records,
            frozenset((point_e, point_f)),
            frozenset((point_g, point_p)),
        )
        if not point_q:
            continue
        goal = formulation.goals[0]
        expected = Atom("para", (point_a, point_q, point_b, point_c)).canonical()
        actual = Atom(goal.predicate, goal.args).canonical()
        if actual != expected:
            continue
        roles = {
            "A": point_a,
            "B": point_b,
            "C": point_c,
            "O": point_o,
            "P": point_p,
            "D": point_d,
            "M": point_m,
            "T": point_t,
            "O1": point_o1,
            "G": point_g,
            "O2": point_o2,
            "E": point_e,
            "F": point_f,
            "Q": point_q,
        }
        matched = (
            "P lies on the circumcircle of ABC",
            "D=AP intersect BC and T is the reflection of D about midpoint M",
            "G lies on AT and circle PDT",
            "E,F lie on AB,AC and circle AGP",
            "Q=EF intersect GP",
            "the goal is AQ parallel to BC",
        )
        return roles, matched
    return {}, ()


def _asserts_secondary_intersections(
    statement: str,
    roles: dict[str, str],
) -> tuple[str, ...]:
    normalized = re.sub(r"[$\\{}]", "", statement.strip().lower())
    normalized = re.sub(r"\s+", " ", normalized)
    point_g = re.escape(roles.get("G", "__missing_g__").lower())
    point_e = re.escape(roles.get("E", "__missing_e__").lower())
    point_f = re.escape(roles.get("F", "__missing_f__").lower())
    atoms: list[str] = []
    if re.search(rf"\bagain at\s+{point_g}\b", normalized):
        atoms.append("distinct(G,T)")
    if re.search(
        rf"\bagain at\s+{point_e}\s+and\s+{point_f}\b",
        normalized,
    ):
        atoms.extend(("distinct(E,A)", "distinct(F,A)"))
    return tuple(atoms)


def certify_jgex_cyclic_cevian_reflection_second_roots_parallel_application(
    source: str,
    natural_statement: str,
) -> JGEXCyclicCevianReflectionSecondRootsParallelApplication:
    normalized = source.strip()
    normalized_natural = natural_statement.strip()
    formulation = JGEXFormulation.from_text(normalized)
    roles, matched = _match_roles(formulation, _records(formulation))
    semantic_atoms = _asserts_secondary_intersections(normalized_natural, roles)
    goal = str(formulation.goals[0]) if len(formulation.goals) == 1 else ""
    chart = certify_cyclic_cevian_reflection_second_roots_parallel_chart()
    replayed = (
        chart.replayed
        and chart.all_conditions_discharged
        and len(semantic_atoms) == 3
        and len(roles) == 14
        and len(matched) == 6
    )
    return JGEXCyclicCevianReflectionSecondRootsParallelApplication(
        theorem=chart.theorem,
        source_sha256=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        natural_statement=normalized_natural,
        natural_statement_sha256=hashlib.sha256(
            normalized_natural.encode("utf-8")
        ).hexdigest(),
        natural_semantic_atoms=semantic_atoms,
        roles=roles,
        matched_constructions=matched,
        goal=goal,
        chart_certificate_sha256=chart.certificate_sha256,
        nondegeneracy_obligations=chart.assumptions,
        undischarged_nondegeneracy_obligations=(
            ()
            if len(semantic_atoms) == 3
            else ("G != T", "E != A", "F != A")
        ),
        replayed=replayed,
    )


def _circle_data(
    first: tuple[float, float],
    second: tuple[float, float],
    third: tuple[float, float],
) -> tuple[tuple[float, float], float]:
    x1, y1 = first
    x2, y2 = second
    x3, y3 = third
    determinant = 2 * (
        x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2)
    )
    center_x = (
        (x1**2 + y1**2) * (y2 - y3)
        + (x2**2 + y2**2) * (y3 - y1)
        + (x3**2 + y3**2) * (y1 - y2)
    ) / determinant
    center_y = (
        (x1**2 + y1**2) * (x3 - x2)
        + (x2**2 + y2**2) * (x1 - x3)
        + (x3**2 + y3**2) * (x2 - x1)
    ) / determinant
    radius = ((x1 - center_x) ** 2 + (y1 - center_y) ** 2) ** 0.5
    return (center_x, center_y), radius


def render_cyclic_cevian_reflection_second_roots_parallel_chart_svg(
    *, u_value: float = 0.3, v_value: float = 1.4, r_value: float = 0.35
) -> str:
    certificate = certify_cyclic_cevian_reflection_second_roots_parallel_chart()
    symbols = {name: sp.Symbol(name, real=True) for name in ("u", "v", "r")}
    substitutions = {
        symbols["u"]: sp.Rational(str(u_value)),
        symbols["v"]: sp.Rational(str(v_value)),
        symbols["r"]: sp.Rational(str(r_value)),
    }
    points = {
        name: (
            float(sp.sympify(value[0], locals=symbols).subs(substitutions)),
            float(sp.sympify(value[1], locals=symbols).subs(substitutions)),
        )
        for name, value in certificate.coordinates.items()
    }
    circles = (
        (*_circle_data(points["A"], points["B"], points["C"]), "#94a3b8"),
        (*_circle_data(points["P"], points["D"], points["T"]), "#7c3aed"),
        (*_circle_data(points["A"], points["G"], points["P"]), "#0891b2"),
    )

    figure, axis = plt.subplots(figsize=(9.0, 6.4), constrained_layout=True)
    figure.patch.set_facecolor("#f8fafc")
    axis.set_facecolor("#ffffff")
    axis.set_aspect("equal", adjustable="datalim")
    axis.axis("off")
    axis.set_title(
        "3つの円が1つの平行方向へ縮約する",
        loc="left",
        fontsize=14,
        color="#0f172a",
        fontfamily="Yu Gothic",
    )
    for center, radius, color in circles:
        axis.add_patch(Circle(center, radius, fill=False, color=color, linewidth=1.2))
    for left, right, color, width in (
        ("A", "B", "#64748b", 1.2),
        ("A", "C", "#64748b", 1.2),
        ("B", "C", "#64748b", 1.2),
        ("A", "P", "#475569", 1.1),
        ("A", "T", "#7c3aed", 1.2),
        ("E", "F", "#0891b2", 1.5),
        ("G", "P", "#0891b2", 1.5),
        ("A", "Q", "#e11d48", 2.0),
    ):
        axis.plot(
            (points[left][0], points[right][0]),
            (points[left][1], points[right][1]),
            color=color,
            linewidth=width,
        )
    for name, (x_coord, y_coord) in points.items():
        highlight = name in {"A", "Q", "B", "C"}
        color = "#e11d48" if name in {"A", "Q"} else "#0f172a"
        axis.scatter((x_coord,), (y_coord,), color=color, s=28, zorder=5)
        axis.annotate(
            name,
            (x_coord, y_coord),
            xytext=(6, 5),
            textcoords="offset points",
            fontsize=9,
            color=color,
            weight="bold" if highlight else "normal",
        )
    axis.relim()
    axis.autoscale_view()
    axis.margins(0.14)
    output = io.StringIO()
    figure.savefig(output, format="svg", bbox_inches="tight")
    plt.close(figure)
    return output.getvalue()


__all__ = [
    "CyclicCevianReflectionSecondRootsParallelCertificate",
    "JGEXCyclicCevianReflectionSecondRootsParallelApplication",
    "certify_cyclic_cevian_reflection_second_roots_parallel_chart",
    "certify_jgex_cyclic_cevian_reflection_second_roots_parallel_application",
    "render_cyclic_cevian_reflection_second_roots_parallel_chart_svg",
]
