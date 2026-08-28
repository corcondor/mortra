"""Runtime registry for replayable exact geometry charts.

The chart modules prove reusable construction theorems.  This registry is the
single runtime boundary that matches a JGEX source against every theorem,
replays the matching certificate, and returns the readable proof and diagram.

Chart discovery in this repository happened after the frozen benchmark was
inspected.  A successful runtime match is therefore a mathematical proof, but
is not automatically an unseen-benchmark success.  Cohort admission remains a
separate responsibility of the benchmark auditor.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import re
from typing import Any, Callable

from worker.backend.barycentric_circle_chart import (
    certify_incenter_excenter_radical_axis_chart,
    certify_jgex_incenter_excenter_radical_axis_application,
    render_incenter_excenter_radical_axis_chart_svg,
)
from worker.backend.arc_midpoint_reflection_center_axis_chart import (
    certify_arc_midpoint_reflection_center_axis_chart,
    certify_jgex_arc_midpoint_reflection_center_axis_application,
    render_arc_midpoint_reflection_center_axis_chart_svg,
)
from worker.backend.cyclic_bisector_transversal_midpoints_chart import (
    certify_cyclic_bisector_transversal_midpoints_chart,
    certify_jgex_cyclic_bisector_transversal_midpoints_application,
    render_cyclic_bisector_transversal_midpoints_chart_svg,
)
from worker.backend.euler_line_bisector_chart import (
    certify_euler_line_bisector_chart,
    certify_jgex_euler_line_bisector_application,
    render_euler_line_bisector_chart_svg,
)
from worker.backend.incircle_reflection_chart import (
    certify_incircle_reflection_chart,
    certify_jgex_incircle_reflection_application,
    render_incircle_reflection_chart_svg,
)
from worker.backend.incircle_three_circle_axis_chart import (
    certify_incircle_three_circle_axis_chart,
    certify_jgex_incircle_three_circle_axis_application,
    render_incircle_three_circle_axis_chart_svg,
)
from worker.backend.incircle_contact_pencil_midpoint_chart import (
    certify_incircle_contact_pencil_midpoint_chart,
    certify_jgex_incircle_contact_pencil_midpoint_application,
    render_incircle_contact_pencil_midpoint_chart_svg,
)
from worker.backend.incircle_gergonne_three_circumcenters_chart import (
    certify_incircle_gergonne_three_circumcenters_chart,
    certify_jgex_incircle_gergonne_three_circumcenters_application,
    render_incircle_gergonne_three_circumcenters_chart_svg,
)
from worker.backend.isosceles_two_circle_perpendicular_chart import (
    certify_isosceles_two_circle_perpendicular_chart,
    certify_jgex_isosceles_two_circle_perpendicular_application,
    render_isosceles_two_circle_perpendicular_chart_svg,
)
from worker.backend.intersecting_chords_three_circles_chart import (
    certify_intersecting_chords_three_circles_chart,
    certify_jgex_intersecting_chords_three_circles_application,
    render_intersecting_chords_three_circles_chart_svg,
)
from worker.backend.mixtilinear_tangent_circle_chart import (
    certify_jgex_mixtilinear_tangent_circle_application,
    certify_mixtilinear_tangent_circle_chart,
    render_mixtilinear_tangent_circle_chart_svg,
)
from worker.backend.midpoint_bisector_equal_power_chart import (
    certify_jgex_midpoint_bisector_equal_power_application,
    certify_midpoint_bisector_equal_power_chart,
    render_midpoint_bisector_equal_power_chart_svg,
)
from worker.backend.orthocenter_circle_intersection_chart import (
    certify_jgex_orthocenter_circle_chart_application,
    certify_orthocenter_circle_intersection_chart,
    render_orthocenter_circle_chart_svg,
)
from worker.backend.orthic_parallel_chord_two_tangents_chart import (
    certify_jgex_orthic_parallel_chord_two_tangents_application,
    certify_orthic_parallel_chord_two_tangents_chart,
    render_orthic_parallel_chord_two_tangents_chart_svg,
)
from worker.backend.parallel_transversal_perpendicular_circles_chart import (
    certify_jgex_parallel_transversal_perpendicular_circles_application,
    certify_parallel_transversal_perpendicular_circles_chart,
    render_parallel_transversal_perpendicular_circles_chart_svg,
)
from worker.backend.positive_similarity_six_circumcenters_chart import (
    certify_jgex_positive_similarity_six_circumcenters_application,
    certify_positive_similarity_six_circumcenters_chart,
    render_positive_similarity_six_circumcenters_chart_svg,
)
from worker.backend.second_lemoine_harmonic_incenter_chart import (
    certify_jgex_second_lemoine_harmonic_incenter_application,
    certify_second_lemoine_harmonic_incenter_chart,
    render_second_lemoine_harmonic_incenter_chart_svg,
)
from worker.backend.tangential_quadrilateral_second_tangent_chart import (
    certify_jgex_tangential_quadrilateral_second_tangent_application,
    certify_tangential_quadrilateral_second_tangent_chart,
    render_tangential_quadrilateral_second_tangent_chart_svg,
)
from worker.backend.tangent_triangle_secant_midpoint_chart import (
    certify_jgex_tangent_triangle_secant_midpoint_application,
    certify_tangent_triangle_secant_midpoint_chart,
    render_tangent_triangle_secant_midpoint_chart_svg,
)
from worker.backend.three_circumcenters_radical_reflection_chart import (
    certify_jgex_three_circumcenters_radical_reflection_application,
    certify_three_circumcenters_radical_reflection_chart,
    render_three_circumcenters_radical_reflection_chart_svg,
)
from worker.backend.two_diameter_pedal_radical_axis_chart import (
    certify_jgex_two_diameter_pedal_radical_axis_application,
    certify_two_diameter_pedal_radical_axis_chart,
    render_two_diameter_pedal_radical_axis_chart_svg,
)


@dataclass(frozen=True)
class ExactGeometryChartAttempt:
    chart_id: str
    proof_class: str
    replayed: bool
    theorem: str | None
    matched_constructions: tuple[str, ...]
    role_count: int
    goal: str | None
    error: str | None
    proof_status: str = "not_matched"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ExactGeometryChartSolution:
    chart_id: str
    proof_class: str
    source_sha256: str
    theorem: str
    roles: dict[str, str]
    matched_constructions: tuple[str, ...]
    goal: str
    nondegeneracy_obligations: tuple[str, ...]
    identity_count: int
    chart_certificate_sha256: str
    application: dict[str, object]
    certificate: dict[str, object]
    proof_markdown: str
    diagram_svg: str | None
    proof_status: str
    undischarged_obligations: tuple[str, ...]
    strict_frozen_score_eligible: bool = False
    natural_statement_sha256: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ExactGeometryChartPortfolioResult:
    source_sha256: str
    solved: bool
    conditional: bool
    ambiguous: bool
    selected: ExactGeometryChartSolution | None
    attempts: tuple[ExactGeometryChartAttempt, ...]
    strict_frozen_score_eligible: bool
    benchmark_admission: str
    natural_statement_sha256: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "source_sha256": self.source_sha256,
            "solved": self.solved,
            "conditional": self.conditional,
            "ambiguous": self.ambiguous,
            "selected": self.selected.to_dict() if self.selected else None,
            "attempts": [item.to_dict() for item in self.attempts],
            "strict_frozen_score_eligible": self.strict_frozen_score_eligible,
            "benchmark_admission": self.benchmark_admission,
            "natural_statement_sha256": self.natural_statement_sha256,
        }


@dataclass(frozen=True)
class _ChartSpec:
    chart_id: str
    proof_class: str
    apply: Callable[..., Any]
    certify: Callable[[], Any]
    render: Callable[[], str]
    required_operation_counts: tuple[tuple[str, int], ...]
    goal_predicate: str
    uses_natural_statement: bool = False


_CHARTS = (
    _ChartSpec(
        "second-lemoine-harmonic-pascal-incenter-altitude",
        "posthoc_exact_chart_with_hash_bound_natural_domain",
        certify_jgex_second_lemoine_harmonic_incenter_application,
        certify_second_lemoine_harmonic_incenter_chart,
        render_second_lemoine_harmonic_incenter_chart_svg,
        (
            ("triangle", 1),
            ("foot", 1),
            ("circumcenter", 1),
            ("centroid", 1),
            ("on_aline", 3),
            ("mirror", 1),
            ("on_line", 4),
            ("on_tline", 3),
            ("incenter", 1),
        ),
        "coll",
        uses_natural_statement=True,
    ),
    _ChartSpec(
        "midpoint-bisector-two-circles-equal-power",
        "posthoc_exact_existential_chart_with_quantifier_repair",
        certify_jgex_midpoint_bisector_equal_power_application,
        certify_midpoint_bisector_equal_power_chart,
        render_midpoint_bisector_equal_power_chart_svg,
        (
            ("triangle", 1),
            ("mirror", 2),
            ("angle_bisector", 1),
            ("midpoint", 3),
            ("on_line", 7),
            ("foot", 1),
            ("circumcenter", 2),
            ("on_circle", 2),
        ),
        "coll",
    ),
    _ChartSpec(
        "orthic-parallel-chord-two-tangents-collinearity",
        "posthoc_exact_chart_replayed",
        certify_jgex_orthic_parallel_chord_two_tangents_application,
        certify_orthic_parallel_chord_two_tangents_chart,
        render_orthic_parallel_chord_two_tangents_chart_svg,
        (
            ("triangle", 1),
            ("circumcenter", 3),
            ("foot", 3),
            ("on_line", 2),
            ("midpoint", 1),
            ("on_circle", 2),
            ("on_pline", 1),
            ("on_tline", 2),
        ),
        "coll",
    ),
    _ChartSpec(
        "incircle-gergonne-three-circumcenters-centroid-axis",
        "posthoc_exact_chart_replayed",
        certify_jgex_incircle_gergonne_three_circumcenters_application,
        certify_incircle_gergonne_three_circumcenters_chart,
        render_incircle_gergonne_three_circumcenters_chart_svg,
        (
            ("triangle", 1),
            ("incenter", 1),
            ("foot", 3),
            ("on_line", 5),
            ("circumcenter", 4),
            ("on_circle", 3),
            ("centroid", 1),
        ),
        "coll",
    ),
    _ChartSpec(
        "three-circumcenters-radical-axis-reflection-isogonal",
        "posthoc_exact_chart_replayed",
        certify_jgex_three_circumcenters_radical_reflection_application,
        certify_three_circumcenters_radical_reflection_chart,
        render_three_circumcenters_radical_reflection_chart_svg,
        (
            ("triangle", 1),
            ("free", 1),
            ("circumcenter", 5),
            ("on_circle", 4),
            ("reflect", 1),
        ),
        "eqangle",
    ),
    _ChartSpec(
        "cyclic-opposite-bisectors-transversal-midpoints-perpendicular",
        "posthoc_exact_chart_replayed",
        certify_jgex_cyclic_bisector_transversal_midpoints_application,
        certify_cyclic_bisector_transversal_midpoints_chart,
        render_cyclic_bisector_transversal_midpoints_chart_svg,
        (
            ("triangle", 1),
            ("on_circum", 1),
            ("circumcenter", 1),
            ("angle_bisector", 4),
            ("on_line", 8),
            ("midpoint", 2),
        ),
        "perp",
    ),
    _ChartSpec(
        "intersecting-chords-three-circles-collinearity",
        "exact_chart_with_construction_domain_discharged",
        certify_jgex_intersecting_chords_three_circles_application,
        certify_intersecting_chords_three_circles_chart,
        render_intersecting_chords_three_circles_chart_svg,
        (("triangle", 1), ("on_circum", 1), ("on_bline", 2)),
        "coll",
    ),
    _ChartSpec(
        "isosceles-two-circle-intersection-perpendicular",
        "exact_chart_with_construction_domain_discharged",
        certify_jgex_isosceles_two_circle_perpendicular_application,
        certify_isosceles_two_circle_perpendicular_chart,
        render_isosceles_two_circle_perpendicular_chart_svg,
        (("iso_triangle", 1), ("incenter", 1), ("on_bline", 1)),
        "perp",
    ),
    _ChartSpec(
        "orthocenter-midpoint-two-circle-common-point-on-line",
        "posthoc_exact_existential_chart_with_quantifier_repair",
        certify_jgex_orthocenter_circle_chart_application,
        certify_orthocenter_circle_intersection_chart,
        render_orthocenter_circle_chart_svg,
        (("orthocenter", 1), ("on_tline", 1), ("midpoint", 2)),
        "coll",
    ),
    _ChartSpec(
        "incircle-diameter-circle-reflection",
        "posthoc_exact_chart_replayed",
        certify_jgex_incircle_reflection_application,
        certify_incircle_reflection_chart,
        render_incircle_reflection_chart_svg,
        (("incenter", 1), ("orthocenter", 1), ("mirror", 1), ("midpoint", 2)),
        "cong",
    ),
    _ChartSpec(
        "euler-line-circle-bisector-equal-distance",
        "posthoc_exact_chart_replayed",
        certify_jgex_euler_line_bisector_application,
        certify_euler_line_bisector_chart,
        render_euler_line_bisector_chart_svg,
        (("orthocenter", 1), ("on_bline", 1), ("midpoint", 1)),
        "cong",
    ),
    _ChartSpec(
        "mixtilinear-two-circumcircles-tangent",
        "posthoc_exact_chart_replayed",
        certify_jgex_mixtilinear_tangent_circle_application,
        certify_mixtilinear_tangent_circle_chart,
        render_mixtilinear_tangent_circle_chart_svg,
        (("incenter", 1), ("on_tline", 2), ("foot", 1)),
        "coll",
    ),
    _ChartSpec(
        "incenter-excenter-radical-axis-isogonal-trace",
        "external_theorem_reimplemented_and_replayed",
        certify_jgex_incenter_excenter_radical_axis_application,
        certify_incenter_excenter_radical_axis_chart,
        render_incenter_excenter_radical_axis_chart_svg,
        (("incenter", 1), ("excenter", 3)),
        "eqangle",
    ),
    _ChartSpec(
        "incircle-antipodes-three-circle-axis",
        "posthoc_exact_chart_replayed",
        certify_jgex_incircle_three_circle_axis_application,
        certify_incircle_three_circle_axis_chart,
        render_incircle_three_circle_axis_chart_svg,
        (("incenter", 1), ("mirror", 3), ("foot", 3)),
        "coll",
    ),
    _ChartSpec(
        "positive-similarity-six-circumcenters-concurrency",
        "posthoc_exact_chart_replayed",
        certify_jgex_positive_similarity_six_circumcenters_application,
        certify_positive_similarity_six_circumcenters_chart,
        render_positive_similarity_six_circumcenters_chart_svg,
        (("triangle", 1), ("on_aline", 2), ("circumcenter", 6)),
        "coll",
    ),
    _ChartSpec(
        "tangential-quadrilateral-second-tangent-circle-tangency",
        "posthoc_exact_chart_replayed",
        certify_jgex_tangential_quadrilateral_second_tangent_application,
        certify_tangential_quadrilateral_second_tangent_chart,
        render_tangential_quadrilateral_second_tangent_chart_svg,
        (("circumcenter", 2), ("on_tline", 10), ("reflect", 1)),
        "coll",
    ),
    _ChartSpec(
        "tangent-triangle-secant-midpoint-circle-tangency",
        "posthoc_exact_chart_replayed",
        certify_jgex_tangent_triangle_secant_midpoint_application,
        certify_tangent_triangle_secant_midpoint_chart,
        render_tangent_triangle_secant_midpoint_chart_svg,
        (
            ("foot", 3),
            ("circumcenter", 2),
            ("on_circle", 3),
            ("on_line", 2),
            ("midpoint", 1),
        ),
        "coll",
    ),
    _ChartSpec(
        "parallel-transversal-perpendicular-triangle-circles-tangent",
        "posthoc_exact_chart_replayed",
        certify_jgex_parallel_transversal_perpendicular_circles_application,
        certify_parallel_transversal_perpendicular_circles_chart,
        render_parallel_transversal_perpendicular_circles_chart_svg,
        (
            ("triangle", 1),
            ("on_pline", 2),
            ("on_tline", 12),
            ("circumcenter", 2),
            ("on_circle", 2),
        ),
        "coll",
    ),
    _ChartSpec(
        "two-diameter-circles-pedal-radical-axis",
        "posthoc_exact_chart_replayed",
        certify_jgex_two_diameter_pedal_radical_axis_application,
        certify_two_diameter_pedal_radical_axis_chart,
        render_two_diameter_pedal_radical_axis_chart_svg,
        (
            ("quadrangle", 1),
            ("midpoint", 3),
            ("on_circle", 8),
            ("foot", 6),
            ("circumcenter", 2),
        ),
        "coll",
    ),
    _ChartSpec(
        "incircle-contact-circle-pencil-midpoint-radical-axis",
        "posthoc_exact_chart_replayed",
        certify_jgex_incircle_contact_pencil_midpoint_application,
        certify_incircle_contact_pencil_midpoint_chart,
        render_incircle_contact_pencil_midpoint_chart_svg,
        (
            ("triangle", 1),
            ("incenter", 1),
            ("foot", 4),
            ("circumcenter", 4),
            ("on_circle", 12),
            ("midpoint", 1),
        ),
        "coll",
    ),
    _ChartSpec(
        "arc-midpoint-antipode-reflection-center-axis",
        "posthoc_exact_chart_replayed",
        certify_jgex_arc_midpoint_reflection_center_axis_application,
        certify_arc_midpoint_reflection_center_axis_chart,
        render_arc_midpoint_reflection_center_axis_chart_svg,
        (
            ("triangle", 1),
            ("circumcenter", 2),
            ("on_bline", 3),
            ("on_circle", 3),
            ("mirror", 3),
            ("reflect", 6),
            ("orthocenter", 2),
        ),
        "para",
    ),
)


def _operation_count(source: str, operation: str) -> int:
    setup = source.rsplit("?", maxsplit=1)[0]
    return len(re.findall(rf"\b{re.escape(operation)}\b", setup))


def _passes_structural_prefilter(source: str, spec: _ChartSpec) -> bool:
    if "?" not in source:
        return False
    goal = source.rsplit("?", maxsplit=1)[1].strip().split()
    if not goal or goal[0] != spec.goal_predicate:
        return False
    return all(
        _operation_count(source, operation) >= count
        for operation, count in spec.required_operation_counts
    )


def _proof_markdown(source: str, application: Any, certificate: Any) -> str:
    unresolved = tuple(
        getattr(
            application,
            "undischarged_nondegeneracy_obligations",
            application.nondegeneracy_obligations,
        )
    )
    role_lines = "\n".join(
        f"- `{role}` -> `{point}`" for role, point in sorted(application.roles.items())
    )
    obligation_lines = "\n".join(
        f"- `{item}`" for item in application.nondegeneracy_obligations
    )
    repair_required = bool(getattr(application, "formalization_repair_required", False))
    natural_statement = str(getattr(application, "natural_statement", "")).strip()
    natural_lines = (
        (
            "## Natural-language domain",
            "",
            "```text",
            natural_statement,
            "```",
            "",
            "- typed atoms: "
            + ", ".join(getattr(application, "natural_semantic_atoms", ())),
            "- statement SHA-256: `"
            + str(getattr(application, "natural_statement_sha256", ""))
            + "`",
            "",
        )
        if natural_statement
        else ()
    )
    quantification_lines = (
        (
            "## 量化監査",
            "",
            (
                "- 元の一出力交点節は2つの交点から分岐を選ばないため、"
                "そのままでは自然文の存在命題と同値ではない。"
            ),
            ("- 修復後: `" f"{getattr(application, 'repaired_quantified_goal', '')}`"),
            "- 自然文の存在命題: `proved`",
            "- 元入力の任意交点版: `not proved`",
            "- この量化修復は凍結ベンチマーク得点へ加算しない。",
            "",
        )
        if repair_required
        else ()
    )
    return "\n".join(
        (
            f"# {application.theorem} 適用証明",
            "",
            "## 判定",
            "",
            "- 構成依存関係と目標を照合した。",
            "- 座標チャート上の全恒等式を厳密再生した。",
            (
                "- 判定: `proved`（構成の定義域条件まで消去済み）。"
                if not unresolved
                else "- 判定: `conditional`（下記の未消去条件が残る）。"
            ),
            "- 問題確認後に実装したチャートなので、凍結未見得点には遡及加算しない。",
            "",
            "## 入力問題",
            "",
            "```text",
            source.strip(),
            "```",
            "",
            *natural_lines,
            "## 点の役割対応",
            "",
            role_lines or "- なし",
            "",
            "## 非退化条件",
            "",
            obligation_lines or "- なし",
            "",
            "## 未消去条件",
            "",
            *(f"- `{item}`" for item in unresolved),
            *(("- なし",) if not unresolved else ()),
            "",
            *quantification_lines,
            "## 証明書",
            "",
            f"- SHA-256: `{certificate.certificate_sha256}`",
            f"- 再生恒等式: `{len(certificate.replay_residuals)}`",
            "",
            certificate.to_markdown(),
        )
    )


def certify_jgex_with_exact_chart_portfolio(
    source: str,
    *,
    include_diagram: bool = True,
    natural_statement: str | None = None,
) -> ExactGeometryChartPortfolioResult:
    """Match and replay every registered chart without problem-name branches."""

    normalized = source.strip()
    normalized_natural = (natural_statement or "").strip()
    source_sha256 = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    natural_statement_sha256 = (
        hashlib.sha256(normalized_natural.encode("utf-8")).hexdigest()
        if normalized_natural
        else None
    )
    attempts: list[ExactGeometryChartAttempt] = []
    matches: list[ExactGeometryChartSolution] = []

    for spec in _CHARTS:
        if not _passes_structural_prefilter(normalized, spec):
            attempts.append(
                ExactGeometryChartAttempt(
                    chart_id=spec.chart_id,
                    proof_class=spec.proof_class,
                    replayed=False,
                    theorem=None,
                    matched_constructions=(),
                    role_count=0,
                    goal=None,
                    error="structural_prefilter_miss",
                    proof_status="not_matched",
                )
            )
            continue
        try:
            application = (
                spec.apply(normalized, normalized_natural)
                if spec.uses_natural_statement
                else spec.apply(normalized)
            )
            error: str | None = None
            if application.replayed:
                certificate = spec.certify()
                if not certificate.replayed:
                    error = "chart_certificate_did_not_replay"
                elif (
                    application.chart_certificate_sha256
                    != certificate.certificate_sha256
                ):
                    error = "chart_certificate_hash_mismatch"
                elif any(
                    str(residual) != "0"
                    for residual in certificate.replay_residuals.values()
                ):
                    error = "chart_has_nonzero_replay_residual"
                else:
                    unresolved = tuple(
                        getattr(
                            application,
                            "undischarged_nondegeneracy_obligations",
                            application.nondegeneracy_obligations,
                        )
                    )
                    proof_status = "proved" if not unresolved else "conditional"
                    matches.append(
                        ExactGeometryChartSolution(
                            chart_id=spec.chart_id,
                            proof_class=spec.proof_class,
                            source_sha256=source_sha256,
                            theorem=application.theorem,
                            roles=dict(application.roles),
                            matched_constructions=tuple(
                                application.matched_constructions
                            ),
                            goal=application.goal,
                            nondegeneracy_obligations=tuple(
                                application.nondegeneracy_obligations
                            ),
                            identity_count=len(certificate.replay_residuals),
                            chart_certificate_sha256=(certificate.certificate_sha256),
                            application=application.to_dict(),
                            certificate=certificate.to_dict(),
                            proof_markdown=_proof_markdown(
                                normalized, application, certificate
                            ),
                            diagram_svg=spec.render() if include_diagram else None,
                            proof_status=proof_status,
                            undischarged_obligations=unresolved,
                            natural_statement_sha256=(
                                str(application.natural_statement_sha256)
                                if getattr(
                                    application, "natural_statement_sha256", ""
                                )
                                else None
                            ),
                        )
                    )
            attempts.append(
                ExactGeometryChartAttempt(
                    chart_id=spec.chart_id,
                    proof_class=spec.proof_class,
                    replayed=application.replayed and error is None,
                    theorem=application.theorem,
                    matched_constructions=tuple(application.matched_constructions),
                    role_count=len(application.roles),
                    goal=application.goal,
                    error=error,
                    proof_status=(
                        "proved"
                        if application.replayed
                        and error is None
                        and not tuple(
                            getattr(
                                application,
                                "undischarged_nondegeneracy_obligations",
                                application.nondegeneracy_obligations,
                            )
                        )
                        else (
                            "conditional"
                            if application.replayed and error is None
                            else "not_matched"
                        )
                    ),
                )
            )
        except Exception as exc:  # Preserve one specialist failure, try the rest.
            attempts.append(
                ExactGeometryChartAttempt(
                    chart_id=spec.chart_id,
                    proof_class=spec.proof_class,
                    replayed=False,
                    theorem=None,
                    matched_constructions=(),
                    role_count=0,
                    goal=None,
                    error=f"{type(exc).__name__}: {exc}",
                    proof_status="not_matched",
                )
            )

    selected = matches[0] if len(matches) == 1 else None
    proved = selected is not None and selected.proof_status == "proved"
    conditional = selected is not None and selected.proof_status == "conditional"
    repair_required = bool(
        selected and selected.application.get("formalization_repair_required", False)
    )
    return ExactGeometryChartPortfolioResult(
        source_sha256=source_sha256,
        solved=proved,
        conditional=conditional,
        ambiguous=len(matches) > 1,
        selected=selected,
        attempts=tuple(attempts),
        strict_frozen_score_eligible=False,
        benchmark_admission=(
            (
                "The natural existential statement is proved after quantifier repair, "
                "but the malformed one-output source is not a raw benchmark solve."
            )
            if repair_required
            else "A fresh held-out cohort must establish transfer before score admission."
        ),
        natural_statement_sha256=natural_statement_sha256,
    )


__all__ = [
    "ExactGeometryChartAttempt",
    "ExactGeometryChartPortfolioResult",
    "ExactGeometryChartSolution",
    "certify_jgex_with_exact_chart_portfolio",
]
