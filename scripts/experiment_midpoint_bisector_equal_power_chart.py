from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys

import sympy as sp

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from worker.backend.exact_geometry_chart_portfolio import (
    certify_jgex_with_exact_chart_portfolio,
)
from worker.backend.midpoint_bisector_equal_power_chart import (
    certify_jgex_midpoint_bisector_equal_power_application,
    certify_midpoint_bisector_equal_power_chart,
    render_midpoint_bisector_equal_power_chart_svg,
)


DATASET = ROOT / "data" / "hageo-409-jgex-2026-08-18.txt"
BASE_UNION = (
    ROOT
    / "data"
    / "hageo-certified-capability-union-plus-orthic-parallel-chord-two-tangents-chart-2026-08-27.json"
)
FIXTURE = ROOT / "data" / "fixtures" / "2019IranTSTp15.jgex.txt"
OUTPUT = (
    ROOT
    / "data"
    / "midpoint-bisector-equal-power-chart-experiment-2026-08-27.json"
)
RUN_DIR = (
    ROOT
    / "data"
    / "hageo-exact-chart-midpoint-bisector-equal-power-runs-2026-08-27"
)
CHART_ID = "midpoint-bisector-two-circles-equal-power"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_formulations() -> dict[str, str]:
    lines = [line.strip() for line in DATASET.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(lines) % 2:
        raise ValueError("HAGeo JGEX dataset must contain alternating name/source lines")
    return dict(zip(lines[0::2], lines[1::2], strict=True))


def _renamed(source: str, salt: int) -> str:
    reserved = {
        "triangle",
        "mirror",
        "on_line",
        "angle_bisector",
        "midpoint",
        "foot",
        "circumcenter",
        "on_circle",
        "coll",
    }
    names = tuple(dict.fromkeys(re.findall(r"\b[a-z][a-z0-9_]*\b", source)))
    mapping = {
        name: f"v{salt}_{index}"
        for index, name in enumerate(name for name in names if name not in reserved)
    }
    return re.sub(
        r"\b[a-z][a-z0-9_]*\b",
        lambda match: mapping.get(match.group(0), match.group(0)),
        source,
    )


def _cross(left: sp.Matrix, right: sp.Matrix) -> sp.Expr:
    return sp.det(sp.Matrix.hstack(left, right))


def _intersection(
    first: sp.Matrix,
    first_direction: sp.Matrix,
    second: sp.Matrix,
    second_direction: sp.Matrix,
) -> sp.Matrix:
    parameter = sp.cancel(
        _cross(second - first, second_direction)
        / _cross(first_direction, second_direction)
    )
    return (first + parameter * first_direction).applyfunc(sp.cancel)


def _circle_coefficients(
    first: sp.Matrix,
    second: sp.Matrix,
    third: sp.Matrix,
) -> sp.Matrix:
    matrix = sp.Matrix(
        (
            (first[0], first[1], 1),
            (second[0], second[1], 1),
            (third[0], third[1], 1),
        )
    )
    right = -sp.Matrix((first.dot(first), second.dot(second), third.dot(third)))
    return matrix.inv() * right


def _power(point: sp.Matrix, coefficients: sp.Matrix) -> sp.Expr:
    return sp.cancel(
        point.dot(point)
        + coefficients[0] * point[0]
        + coefficients[1] * point[1]
        + coefficients[2]
    )


def _independent_rational_models() -> int:
    checked = 0
    for side_b in map(sp.Rational, (2, 3, 5, 7)):
        for side_c in map(sp.Rational, (4, 6, 8, 9)):
            for numerator, tangent_denominator in ((1, 3), (2, 5), (3, 7), (4, 9)):
                tangent = sp.Rational(numerator, tangent_denominator)
                denominator = 1 + tangent**2
                cosine = (1 - tangent**2) / denominator
                sine = 2 * tangent / denominator
                k = sp.Matrix((0, 0))
                b = sp.Matrix((side_b * cosine, side_b * sine))
                c = sp.Matrix((side_c * cosine, -side_c * sine))
                a = sp.Matrix((-2 * side_b * side_c * cosine / (side_b + side_c), 0))
                m = (b + c) / 2
                n = (c + a) / 2
                p = (a + b) / 2
                e = _intersection(m, n - m, k, b - k)
                f = _intersection(m, p - m, k, c - k)
                x = _intersection(m, k - m, e, f - e)
                h = (
                    b
                    + (c - b)
                    * sp.cancel((a - b).dot(c - b) / (c - b).dot(c - b))
                ).applyfunc(sp.cancel)
                circle_akh = _circle_coefficients(a, k, h)
                circle_hef = _circle_coefficients(h, e, f)
                if sp.cancel(_power(x, circle_akh) - _power(x, circle_hef)) != 0:
                    raise AssertionError("independent equal-power replay failed")
                checked += 1
    return checked


def main() -> None:
    formulations = _load_formulations()
    union = json.loads(BASE_UNION.read_text(encoding="utf-8"))
    frozen_names = set(union["sets"]["primary_union"]) | set(
        union["sets"]["unresolved_frozen_problems"]
    )
    if len(formulations) != 409 or len(frozen_names) != 89:
        raise AssertionError("frozen dataset or benchmark split changed")

    source = FIXTURE.read_text(encoding="utf-8").strip()
    if formulations["2019IranTSTp15"] != source:
        raise AssertionError("fixture does not match the frozen source")

    certificate = certify_midpoint_bisector_equal_power_chart()
    portfolio = certify_jgex_with_exact_chart_portfolio(source)
    if not portfolio.solved or portfolio.selected is None:
        raise AssertionError("natural theorem did not replay")
    if portfolio.selected.chart_id != CHART_ID:
        raise AssertionError("unexpected chart selected")
    if portfolio.strict_frozen_score_eligible:
        raise AssertionError("ambiguous raw branch must not enter the frozen score")

    scan: list[dict[str, object]] = []
    chart_matches: list[str] = []
    for name in sorted(frozen_names):
        result = certify_jgex_with_exact_chart_portfolio(
            formulations[name], include_diagram=False
        )
        selected_chart = result.selected.chart_id if result.selected else None
        if selected_chart == CHART_ID:
            chart_matches.append(name)
        scan.append(
            {
                "problem": name,
                "solved_by_portfolio": result.solved,
                "selected_chart": selected_chart,
                "ambiguous": result.ambiguous,
                "strict_frozen_score_eligible": result.strict_frozen_score_eligible,
            }
        )
    if chart_matches != ["2019IranTSTp15"]:
        raise AssertionError(f"unexpected new-chart matches: {chart_matches}")

    renamed_accepts = 0
    for salt in range(64):
        application = certify_jgex_midpoint_bisector_equal_power_application(
            _renamed(source, salt)
        )
        renamed_accepts += int(application.replayed)

    mutations = (
        source.replace("n = midpoint c a", "n = midpoint c b"),
        source.replace("e = on_line m n, on_line b k", "e = on_line m p, on_line b k"),
        source.replace("h = foot a b c", "h = foot k b c"),
        source.replace("o2 = circumcenter h e f", "o2 = circumcenter k e f"),
        source.replace("x = on_line m k, on_line e f", "x = on_line m a, on_line e f"),
        source.replace("? coll x h l", "? coll x a l"),
    )
    mutation_trials = 0
    mutation_false_accepts = 0
    for mutation in mutations:
        for salt in range(16):
            mutation_trials += 1
            mutation_false_accepts += int(
                certify_jgex_midpoint_bisector_equal_power_application(
                    _renamed(mutation, salt)
                ).replayed
            )

    independent_models = _independent_rational_models()
    if renamed_accepts != 64 or mutation_false_accepts != 0 or independent_models != 64:
        raise AssertionError("generalization or mutation audit failed")

    RUN_DIR.mkdir(parents=True, exist_ok=True)
    proof_path = RUN_DIR / "2019IranTSTp15.proof.md"
    diagram_path = RUN_DIR / "2019IranTSTp15.diagram.svg"
    portfolio_path = RUN_DIR / "2019IranTSTp15.chart-portfolio.json"
    artifact_path = RUN_DIR / "2019IranTSTp15.artifact.json"
    proof_path.write_text(portfolio.selected.proof_markdown, encoding="utf-8")
    diagram_svg = "\n".join(
        line.rstrip() for line in render_midpoint_bisector_equal_power_chart_svg().splitlines()
    ) + "\n"
    diagram_path.write_text(diagram_svg, encoding="utf-8")
    portfolio_path.write_text(
        json.dumps(portfolio.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    artifact = {
        "problem": "2019IranTSTp15",
        "theorem": certificate.theorem,
        "proof_status": "natural_theorem_proved_after_quantifier_repair",
        "strict_frozen_score_eligible": False,
        "formalization_repair": portfolio.selected.application[
            "repaired_quantified_goal"
        ],
        "certificate_sha256": certificate.certificate_sha256,
        "proof_path": str(proof_path.relative_to(ROOT)).replace("\\", "/"),
        "proof_sha256": _sha256(proof_path),
        "diagram_path": str(diagram_path.relative_to(ROOT)).replace("\\", "/"),
        "diagram_sha256": _sha256(diagram_path),
        "portfolio_path": str(portfolio_path.relative_to(ROOT)).replace("\\", "/"),
        "portfolio_sha256": _sha256(portfolio_path),
    }
    artifact_path.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    report = {
        "experiment": "midpoint_bisector_equal_power_minimal_chart",
        "protocol": {
            "uses_external_llm_at_runtime": False,
            "uses_expected_answer": False,
            "problem_id_branch": False,
            "frozen_dataset": str(DATASET.relative_to(ROOT)).replace("\\", "/"),
            "frozen_dataset_sha256": _sha256(DATASET),
            "base_union": str(BASE_UNION.relative_to(ROOT)).replace("\\", "/"),
            "base_union_sha256": _sha256(BASE_UNION),
        },
        "summary": {
            "frozen_problem_count": 89,
            "natural_theorems_added": 1,
            "strict_frozen_score_additions": 0,
            "primary_certified_solved_before": 76,
            "primary_certified_solved_after": 76,
            "primary_certified_score_after": 76 / 89,
            "reason_not_admitted": "the raw one-output circle intersection omits L != H",
            "new_chart_matches": chart_matches,
            "symbolic_identities_replayed": len(certificate.replay_residuals),
            "independent_rational_models": independent_models,
            "point_renaming_trials": 64,
            "point_renaming_accepts": renamed_accepts,
            "broken_mutation_trials": mutation_trials,
            "broken_mutation_false_accepts": mutation_false_accepts,
        },
        "artifact": artifact,
        "frozen_scan": scan,
    }
    OUTPUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
