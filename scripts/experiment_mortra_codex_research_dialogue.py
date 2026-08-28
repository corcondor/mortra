"""Run a resumable MORTRA/Codex control-treatment research cycle.

The internal exchange is a typed, hash-chained JSON ledger.  Natural language
is retained only as a hash-bound input to the geometry semantic parser; it is
not the communication format between the research components.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from worker.backend.exact_geometry_chart_portfolio import (  # noqa: E402
    ExactGeometryChartPortfolioResult,
    certify_jgex_with_exact_chart_portfolio,
    registered_exact_chart_contracts,
)
from worker.backend.geometry_natural_semantics import (  # noqa: E402
    extract_geometry_natural_semantics,
)
from worker.backend.jgex_chart_parser import (  # noqa: E402
    ChartJGEXFormulation,
)
from worker.backend.major_arc_homothety_tangent_chart import (  # noqa: E402
    certify_major_arc_homothety_tangent_chart,
)
from worker.backend.mortra_research_dialogue import (  # noqa: E402
    ResearchDialogueLedger,
    payload_sha256,
)


CHART_ID = "major-arc-homothety-right-circle-tangent"
OBJECTIVE_CODE = "close_frozen_unproved_with_minimal_reusable_typed_chart"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _dataset(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) % 2:
        raise ValueError("HAGeo dataset must contain name/source line pairs")
    return {lines[index]: lines[index + 1] for index in range(0, len(lines), 2)}


def _operation_multiset(source: str) -> dict[str, int]:
    formulation = ChartJGEXFormulation.from_text(source)
    counts = Counter(
        construction.name
        for clause in formulation.setup_clauses
        for construction in clause.constructions
    )
    return dict(sorted(counts.items()))


def _goal(source: str) -> dict[str, object]:
    formulation = ChartJGEXFormulation.from_text(source)
    return {
        "alternatives": [
            {"predicate": goal.predicate, "args": list(goal.args)}
            for goal in formulation.goals
        ]
    }


def _nearest_chart_contracts(source: str, limit: int = 5) -> list[dict[str, object]]:
    operations = _operation_multiset(source)
    formulation = ChartJGEXFormulation.from_text(source)
    goal_predicates = {goal.predicate for goal in formulation.goals}
    distances: list[dict[str, object]] = []
    for contract in registered_exact_chart_contracts():
        required = dict(contract["required_operation_counts"])
        missing = {
            operation: int(count) - int(operations.get(operation, 0))
            for operation, count in required.items()
            if int(operations.get(operation, 0)) < int(count)
        }
        goal_mismatch = contract["goal_predicate"] not in goal_predicates
        distances.append(
            {
                "chart_id": contract["chart_id"],
                "goal_mismatch": goal_mismatch,
                "missing_operation_counts": missing,
                "structural_distance": sum(missing.values()) + int(goal_mismatch),
                "uses_natural_statement": contract["uses_natural_statement"],
            }
        )
    return sorted(
        distances,
        key=lambda item: (int(item["structural_distance"]), str(item["chart_id"])),
    )[:limit]


def _attempt_summary(result: ExactGeometryChartPortfolioResult) -> dict[str, object]:
    active_attempts = [
        {
            "chart_id": attempt.chart_id,
            "proof_status": attempt.proof_status,
            "replayed": attempt.replayed,
            "error": attempt.error,
            "role_count": attempt.role_count,
        }
        for attempt in result.attempts
        if attempt.error != "structural_prefilter_miss"
    ]
    errors = Counter(
        attempt.error or "none"
        for attempt in result.attempts
        if attempt.error != "structural_prefilter_miss"
    )
    selected = result.selected
    repair_required = bool(
        selected
        and selected.application.get("formalization_repair_required", False)
    )
    certified_solved = result.solved and not repair_required
    return {
        "solved": certified_solved,
        "raw_chart_solved": result.solved,
        "proved_after_quantifier_repair_only": repair_required,
        "conditional": result.conditional,
        "ambiguous": result.ambiguous,
        "selected_chart_id": selected.chart_id if selected else None,
        "proof_status": selected.proof_status if selected else "not_proved",
        "certificate_sha256": (
            selected.chart_certificate_sha256 if selected else None
        ),
        "undischarged_obligations": (
            list(selected.undischarged_obligations) if selected else []
        ),
        "active_attempts": active_attempts,
        "active_error_histogram": dict(sorted(errors.items())),
    }


def _cohort_observation(
    names: tuple[str, ...],
    sources: dict[str, str],
    natural_sources: dict[str, str],
) -> dict[str, Any]:
    observations: dict[str, object] = {}
    for name in names:
        source = sources[name]
        natural = natural_sources.get(name, "")
        control = certify_jgex_with_exact_chart_portfolio(
            source,
            include_diagram=False,
            natural_statement=natural,
            disabled_chart_ids={CHART_ID},
        )
        semantics = extract_geometry_natural_semantics(natural)
        observations[name] = {
            "source_sha256": control.source_sha256,
            "natural_statement_sha256": control.natural_statement_sha256,
            "operation_multiset": _operation_multiset(source),
            "goal": _goal(source),
            "natural_semantic_atoms": list(semantics.typed_atoms),
            "control": _attempt_summary(control),
            "stop_obligation": {
                "kind": "no_replayed_exact_certificate",
                "goal": _goal(source),
                "construction_types": sorted(_operation_multiset(source)),
                "nearest_chart_contracts": _nearest_chart_contracts(source),
            },
        }
    return {
        "cohort_size": len(names),
        "uses_external_llm": False,
        "uses_expected_answer": False,
        "control_intervention": {
            "disabled_chart_ids": [CHART_ID],
        },
        "problems": observations,
    }


def _typed_hypothesis(certificate_sha256: str) -> dict[str, Any]:
    return {
        "intervention_class": "reusable_typed_representation_chart",
        "chart_id": CHART_ID,
        "trigger_contract": {
            "goal_predicate": "cong",
            "minimum_operation_counts": {
                "triangle": 1,
                "incenter": 1,
                "circumcenter": 2,
                "on_bline": 1,
                "on_circle": 1,
                "midpoint": 1,
                "mirror": 2,
                "foot": 2,
            },
            "required_natural_atom_schemas": [
                "acute(A,B,C)",
                "arc_midpoint_through(N,B,A,C)",
            ],
        },
        "morphism_sequence": [
            "arc_through_midpoint_to_antipode",
            "construction_to_homothety_A_half",
            "right_triangle_similarity_to_power",
            "arc_midpoint_to_power",
            "two_tangent_circles_to_unique_circle",
            "inverse_homothety_to_goal",
        ],
        "chart_certificate_sha256": certificate_sha256,
        "forbidden_conditioning": [
            "problem_identifier",
            "expected_answer",
            "benchmark_membership",
            "surface_number_constants",
        ],
        "acceptance_rule": {
            "minimum_new_exact_solves": 1,
            "maximum_regressions": 0,
            "maximum_ambiguous_matches": 0,
            "require_certificate_hash_match": True,
        },
    }


def _controlled_experiment(
    names: tuple[str, ...],
    sources: dict[str, str],
    natural_sources: dict[str, str],
    control_payload: dict[str, Any],
    certificate_sha256: str,
) -> dict[str, Any]:
    results: dict[str, object] = {}
    new_solves: list[str] = []
    regressions: list[str] = []
    ambiguous: list[str] = []
    certificate_failures: list[str] = []
    remaining: list[str] = []
    for name in names:
        treatment = certify_jgex_with_exact_chart_portfolio(
            sources[name],
            include_diagram=False,
            natural_statement=natural_sources.get(name, ""),
        )
        control = dict(control_payload["problems"][name]["control"])
        treatment_summary = _attempt_summary(treatment)
        treatment_solved = bool(treatment_summary["solved"])
        if treatment_solved and not bool(control["solved"]):
            new_solves.append(name)
        if bool(control["solved"]) and not treatment_solved:
            regressions.append(name)
        if treatment.ambiguous:
            ambiguous.append(name)
        selected = treatment.selected
        if (
            selected is not None
            and selected.chart_id == CHART_ID
            and selected.chart_certificate_sha256 != certificate_sha256
        ):
            certificate_failures.append(name)
        if not treatment_solved:
            remaining.append(name)
        results[name] = {
            "source_sha256": treatment.source_sha256,
            "control": control,
            "treatment": treatment_summary,
            "delta": {
                "new_exact_solve": treatment_solved and not bool(control["solved"]),
                "regression": bool(control["solved"]) and not treatment_solved,
            },
        }
    return {
        "design": "paired_frozen_control_treatment_ablation",
        "uses_external_llm": False,
        "uses_expected_answer": False,
        "control": {"disabled_chart_ids": [CHART_ID]},
        "treatment": {"enabled_chart_ids": [CHART_ID]},
        "summary": {
            "evaluated": len(names),
            "new_exact_solves": len(new_solves),
            "regressions": len(regressions),
            "ambiguous": len(ambiguous),
            "certificate_hash_failures": len(certificate_failures),
            "remaining_unproved": len(remaining),
        },
        "sets": {
            "new_exact_solves": new_solves,
            "regressions": regressions,
            "ambiguous": ambiguous,
            "certificate_hash_failures": certificate_failures,
            "remaining_unproved": remaining,
        },
        "results": results,
    }


def _decision(experiment: dict[str, Any]) -> dict[str, Any]:
    summary = dict(experiment["summary"])
    accepted = (
        int(summary["new_exact_solves"]) >= 1
        and int(summary["regressions"]) == 0
        and int(summary["ambiguous"]) == 0
        and int(summary["certificate_hash_failures"]) == 0
    )
    return {
        "accepted": accepted,
        "status": (
            "accepted_as_post_inspection_capability"
            if accepted
            else "rejected_or_retained_as_unconfirmed_research"
        ),
        "score_admission": "not_unseen_frozen_score",
        "capability_union_delta": (
            int(summary["new_exact_solves"]) if accepted else 0
        ),
        "frozen_unseen_score_delta": 0,
        "evidence": summary,
        "next_stop_obligations": experiment["sets"]["remaining_unproved"],
    }


def run_research_dialogue(
    *,
    union_path: Path,
    dataset_path: Path,
    natural_dataset_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    union = json.loads(union_path.read_text(encoding="utf-8"))
    sources = _dataset(dataset_path)
    natural_sources = json.loads(natural_dataset_path.read_text(encoding="utf-8"))
    names = tuple(map(str, union["sets"]["unresolved_frozen_problems"]))
    missing = sorted(set(names) - set(sources))
    if missing:
        raise ValueError(f"unresolved problems missing from dataset: {missing}")

    frozen_cohort = {
        "union_sha256": _sha256(union_path),
        "dataset_sha256": _sha256(dataset_path),
        "natural_dataset_sha256": _sha256(natural_dataset_path),
        "problem_sources": {
            name: hashlib.sha256(sources[name].encode("utf-8")).hexdigest()
            for name in names
        },
    }
    frozen_cohort_sha256 = payload_sha256(frozen_cohort)
    chart = certify_major_arc_homothety_tangent_chart()
    intervention_files = (
        ROOT / "worker/backend/major_arc_homothety_tangent_chart.py",
        ROOT / "worker/backend/geometry_natural_semantics.py",
        ROOT / "worker/backend/exact_geometry_chart_portfolio.py",
        ROOT / "worker/backend/mortra_research_dialogue.py",
        ROOT / "scripts/experiment_mortra_codex_research_dialogue.py",
    )
    cycle_payload = {
        "frozen_cohort_sha256": frozen_cohort_sha256,
        "chart_id": CHART_ID,
        "chart_certificate_sha256": chart.certificate_sha256,
        "intervention_source_sha256": {
            str(path.relative_to(ROOT).as_posix()): _sha256(path)
            for path in intervention_files
        },
    }
    cycle_fingerprint = payload_sha256(cycle_payload)

    if output_path.exists():
        ledger = ResearchDialogueLedger.load(output_path)
        if ledger.frozen_cohort_sha256 != frozen_cohort_sha256:
            raise ValueError("existing ledger belongs to a different frozen cohort")
    else:
        ledger = ResearchDialogueLedger.create(
            objective_code=OBJECTIVE_CODE,
            frozen_cohort_sha256=frozen_cohort_sha256,
        )

    existing = {
        entry.kind: entry
        for entry in ledger.cycle_entries(cycle_fingerprint)
    }
    if "decision" in existing:
        return {
            "cycle_fingerprint": cycle_fingerprint,
            "resumed": True,
            "decision": existing["decision"].payload,
            "head_sha256": ledger.to_dict()["head_sha256"],
        }

    if "cohort_observation" in existing:
        observation = existing["cohort_observation"].payload
    else:
        observation = _cohort_observation(names, sources, natural_sources)
        ledger.append(
            role="mortra",
            kind="cohort_observation",
            cycle_fingerprint=cycle_fingerprint,
            payload=observation,
        )
        ledger.save(output_path)

    if "typed_hypothesis" not in existing:
        ledger.append(
            role="codex",
            kind="typed_hypothesis",
            cycle_fingerprint=cycle_fingerprint,
            payload=_typed_hypothesis(chart.certificate_sha256),
        )
        ledger.save(output_path)

    if "controlled_experiment" in existing:
        experiment = existing["controlled_experiment"].payload
    else:
        experiment = _controlled_experiment(
            names,
            sources,
            natural_sources,
            observation,
            chart.certificate_sha256,
        )
        ledger.append(
            role="mortra",
            kind="controlled_experiment",
            cycle_fingerprint=cycle_fingerprint,
            payload=experiment,
        )
        ledger.save(output_path)

    decision = _decision(experiment)
    ledger.append(
        role="governor",
        kind="decision",
        cycle_fingerprint=cycle_fingerprint,
        payload=decision,
    )
    ledger.save(output_path)
    return {
        "cycle_fingerprint": cycle_fingerprint,
        "resumed": False,
        "decision": decision,
        "head_sha256": ledger.to_dict()["head_sha256"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--union", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--natural-dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run_research_dialogue(
        union_path=args.union,
        dataset_path=args.dataset,
        natural_dataset_path=args.natural_dataset,
        output_path=args.output,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if bool(report["decision"]["accepted"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
