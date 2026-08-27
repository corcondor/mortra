"""Audit and compare a symbolic quotient of typed geometry construction paths."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from worker.backend.generated_construction_action import (  # noqa: E402
    certificate_to_dict,
    normalize_construction_actions,
    verify_construction_action_certificate,
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked_path(value: str, expected: str) -> Path:
    path = (ROOT / value).resolve() if not Path(value).is_absolute() else Path(value)
    observed = sha256(path)
    if observed != expected:
        raise ValueError(f"frozen artifact changed: {path} ({observed} != {expected})")
    return path


SURFACE_CONSTRUCTION_TOKENS = (
    "angle_bisector",
    "foot",
    "on_bline",
    "on_tline",
    "on_circle",
    "on_circum",
    "circumcenter",
    "incenter",
    "excenter",
    "on_aline",
    "eqangle3",
    "reflect",
    "mirror",
    "midpoint",
    "centroid",
    "on_pline",
)


def unresolved_surface_inventory(
    dataset_path: Path,
    names: list[str],
) -> dict[str, Any]:
    """Inventory explicit JGEX vocabulary without inferring a proof bottleneck."""

    lines = dataset_path.read_text(encoding="utf-8").splitlines()
    positions = {line: index for index, line in enumerate(lines) if line in names}
    missing = sorted(set(names) - set(positions))
    if missing:
        raise ValueError("frozen problems missing from JGEX dataset: " + ", ".join(missing))
    rows: list[dict[str, Any]] = []
    problem_counts: Counter[str] = Counter()
    occurrence_counts: Counter[str] = Counter()
    for name in names:
        index = positions[name]
        if index + 1 >= len(lines):
            raise ValueError(f"missing JGEX statement after {name}")
        statement = lines[index + 1]
        before, separator, goal = statement.partition("?")
        if not separator:
            raise ValueError(f"JGEX statement has no goal separator: {name}")
        token_counts = {
            token: len(re.findall(rf"\b{re.escape(token)}\b", before))
            for token in SURFACE_CONSTRUCTION_TOKENS
        }
        present = {token: count for token, count in token_counts.items() if count}
        problem_counts.update(present.keys())
        for token, count in present.items():
            occurrence_counts[token] += count
        rows.append({
            "name": name,
            "goal": goal.strip(),
            "explicitConstructionCounts": present,
        })
    return {
        "interpretationBoundary": (
            "surface vocabulary only; occurrence does not establish the causal "
            "reason a proof search stopped"
        ),
        "problems": rows,
        "problemCountByToken": dict(sorted(problem_counts.items())),
        "occurrenceCountByToken": dict(sorted(occurrence_counts.items())),
        "notRepresentedByThisFormalCohort": [
            "general-natural-language-elaboration",
            "three-dimensional-geometry",
            "explicit-polar-harmonic-inversion-complex-coordinate-charts",
        ],
    }


def strict_replay_acceptance(payload: dict[str, Any] | None) -> bool:
    """Recompute strict acceptance instead of trusting one summary boolean."""

    return bool(
        payload
        and payload.get("accepted") is True
        and payload.get("expected_hashes_present") is True
        and payload.get("replay_solved") is True
        and payload.get("input_hash_matches") is True
        and payload.get("proof_hash_matches") is True
        and payload.get("repeat_replay_solved") is True
        and payload.get("repeat_input_hash_matches") is True
        and payload.get("repeat_proof_hash_matches") is True
    )


def analyse_artifact(entry: dict[str, Any]) -> dict[str, Any]:
    path = checked_path(entry["artifact"], entry["sha256"])
    artifact = json.loads(path.read_text(encoding="utf-8"))
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    errors: list[str] = []
    replay_failures: list[str] = []
    reordered = 0
    certificates: list[dict[str, Any]] = []
    depths: Counter[int] = Counter()
    for record_index, record in enumerate(artifact.get("records", ())):
        steps = record.get("steps", ())
        depths[len(steps)] += 1
        normalized = normalize_construction_actions(steps)
        if normalized.certificate is None:
            errors.extend(f"record {record_index}: {error}" for error in normalized.errors)
            continue
        certificate_errors = verify_construction_action_certificate(normalized.certificate)
        replay_failures.extend(
            f"record {record_index}: {error}" for error in certificate_errors
        )
        order = [action.source_index for action in normalized.certificate.canonical_actions]
        reordered += order != list(range(len(steps)))
        groups[normalized.certificate.semantic_state_key].append(record)
        if len(certificates) < 3:
            certificates.append(certificate_to_dict(normalized.certificate))
    inconsistent = [
        key for key, records in groups.items()
        if len({bool(record.get("solved")) for record in records}) > 1
    ]
    raw_paths = len(artifact.get("records", ()))
    unique_states = len(groups)
    return {
        "name": entry["name"],
        "artifact": entry["artifact"],
        "artifactSha256": entry["sha256"],
        "solved": bool(artifact.get("solved")),
        "rawVerifiedPaths": raw_paths,
        "certifiedPaths": sum(len(records) for records in groups.values()),
        "uniqueGeneratedActionStates": unique_states,
        "equivalentPathsRemoved": raw_paths - unique_states,
        "quotientReductionRate": ((raw_paths - unique_states) / raw_paths if raw_paths else 0.0),
        "canonicalOrderChanged": reordered,
        "depthHistogram": dict(sorted(depths.items())),
        "normalizationErrors": errors,
        "certificateReplayFailures": replay_failures,
        "outcomeInconsistentClasses": inconsistent,
        "certificateSamples": certificates,
    }


def fresh_replay(entry: dict[str, Any], replay_dir: Path | None) -> dict[str, Any]:
    checked_path(entry["artifact"], entry["sha256"])
    source_replay = checked_path(entry["replay"], entry["replaySha256"])
    replay_path = replay_dir / f"{entry['name']}.replay.json" if replay_dir else source_replay
    if not replay_path.is_file():
        return {"name": entry["name"], "available": False, "accepted": False}
    payload = json.loads(replay_path.read_text(encoding="utf-8"))
    return {
        "name": entry["name"],
        "available": True,
        "path": replay_path.resolve().relative_to(ROOT).as_posix(),
        "sha256": sha256(replay_path),
        "accepted": strict_replay_acceptance(payload),
        "declaredAccepted": bool(payload.get("accepted")),
        "expectedHashesPresent": bool(payload.get("expected_hashes_present")),
        "replaySolved": bool(payload.get("replay_solved")),
        "inputHashMatches": bool(payload.get("input_hash_matches")),
        "proofHashMatches": bool(payload.get("proof_hash_matches")),
        "repeatReplaySolved": bool(payload.get("repeat_replay_solved")),
        "repeatInputHashMatches": bool(payload.get("repeat_input_hash_matches")),
        "repeatProofHashMatches": bool(payload.get("repeat_proof_hash_matches")),
    }


def cohort_summary(
    report_path: Path | None,
    run_dir: Path | None,
    replay_dir: Path | None,
) -> dict[str, Any] | None:
    if report_path is None or not report_path.is_file():
        return None
    report = json.loads(report_path.read_text(encoding="utf-8"))
    runs = report.get("runs", ())
    native_confirmed = [
        item["problem"] for item in runs
        if item.get("solved") and item.get("native_confirmed")
    ]
    proof_replays: list[dict[str, Any]] = []
    for name in native_confirmed:
        path = replay_dir / f"{name}.replay.json" if replay_dir is not None else None
        payload = (
            json.loads(path.read_text(encoding="utf-8"))
            if path is not None and path.is_file()
            else None
        )
        proof_replays.append({
            "name": name,
            "available": payload is not None,
            "path": (
                path.resolve().relative_to(ROOT).as_posix()
                if path is not None and path.is_file()
                else None
            ),
            "sha256": sha256(path) if path is not None and path.is_file() else None,
            "accepted": strict_replay_acceptance(payload),
            "declaredAccepted": bool(payload and payload.get("accepted")),
        })
    strict = sorted(item["name"] for item in proof_replays if item["accepted"])
    status_counts = Counter(str(item.get("status", "unknown")) for item in runs)
    per_problem: list[dict[str, Any]] = []
    checkpoint_hashes: dict[str, str] = {}
    for item in runs:
        evaluated_paths = int(item.get("evaluated_paths", 0))
        checkpoint = item.get("checkpoint")
        checkpoint_hash = item.get("checkpoint_sha256")
        if isinstance(checkpoint, str) and isinstance(checkpoint_hash, str):
            checkpoint_hashes[str(item["problem"])] = checkpoint_hash
            raw_checkpoint = Path(checkpoint)
            checkpoint_path = (
                raw_checkpoint
                if raw_checkpoint.is_absolute()
                else (ROOT / raw_checkpoint).resolve()
            )
            if checkpoint_path.is_file():
                checkpoint_path = checked_path(checkpoint, checkpoint_hash)
            elif not evaluated_paths:
                raise FileNotFoundError(
                    "checkpoint is absent and no evaluated path count was embedded: "
                    f"{checkpoint_path}"
                )
            if not evaluated_paths:
                checkpoint_payload = json.loads(
                    checkpoint_path.read_text(encoding="utf-8")
                )
                evaluated_paths = int(
                    checkpoint_payload.get("evaluated_path_count", 0)
                )
        per_problem.append({
            "name": str(item["problem"]),
            "status": str(item.get("status", "unknown")),
            "evaluatedPaths": evaluated_paths,
            "nativeConfirmed": bool(item.get("native_confirmed")),
        })
    action_audits: list[dict[str, Any]] = []
    artifact_hashes: dict[str, str] = {}
    for item in runs:
        embedded_audit = item.get("generated_action_quotient")
        if isinstance(embedded_audit, dict):
            action_audits.append({"name": item["problem"], **embedded_audit})
        embedded_hash = item.get("artifact_sha256")
        if isinstance(embedded_hash, str):
            artifact_hashes[item["problem"]] = embedded_hash
        if run_dir is not None:
            path = run_dir / f"{item['problem']}.json"
            if not path.is_file():
                continue
            observed_hash = sha256(path)
            if isinstance(embedded_hash, str) and embedded_hash != observed_hash:
                raise ValueError(f"cohort artifact hash mismatch: {path}")
            artifact_hashes[item["problem"]] = observed_hash
            if isinstance(embedded_audit, dict):
                continue
            artifact = json.loads(path.read_text(encoding="utf-8"))
            audit = artifact.get("protocol", {}).get("generated_action_quotient")
            if isinstance(audit, dict):
                action_audits.append({"name": item["problem"], **audit})
    resolved_report = report_path.resolve()
    return {
        "report": (
            resolved_report.relative_to(ROOT).as_posix()
            if resolved_report.is_relative_to(ROOT)
            else resolved_report.as_posix()
        ),
        "reportSha256": sha256(report_path),
        "complete": bool(report.get("run_state", {}).get("complete")),
        "selectedProblemNames": list(map(str, report.get("selected_problem_names", ()))),
        "searchBudget": report.get("protocol", {}).get("search_budget", {}),
        "statusCounts": dict(sorted(status_counts.items())),
        "perProblem": per_problem,
        "evaluatedPaths": sum(item["evaluatedPaths"] for item in per_problem),
        "incidenceChecked": sum(int(item.get("incidence_checked", 0)) for item in runs),
        "elapsedProblemSeconds": sum(float(item.get("elapsed_seconds", 0.0)) for item in runs),
        "nativeConfirmedBeforeIndependentReplay": sorted(native_confirmed),
        "strictNewSolves": strict,
        "unreplayedNativeConfirmations": sorted(set(native_confirmed) - set(strict)),
        "proofReplays": proof_replays,
        "rightCensored": sum(
            item.get("status") == "right_censored_timeout" for item in runs
        ),
        "executionErrors": sum(item.get("status") == "execution_error" for item in runs),
        "artifactSha256": artifact_hashes,
        "checkpointSha256": checkpoint_hashes,
        "generatedActionAudits": action_audits,
        "normalizedCandidatePaths": sum(
            int(item.get("normalized_candidate_paths", 0)) for item in action_audits
        ),
        "invalidCandidatePaths": sum(
            int(item.get("invalid_paths", 0)) for item in action_audits
        ),
        "scheduledUniquePaths": sum(
            int(item.get("scheduled_unique_paths", 0)) for item in action_audits
        ),
        "equivalentCandidatesSkipped": sum(
            int(item.get("equivalent_paths_skipped", 0)) for item in action_audits
        ),
        "certificateReplayFailures": sum(
            int(item.get("certificate_replay_failures", 0)) for item in action_audits
        ),
    }


def validate_controlled_pair(
    control: dict[str, Any],
    treatment: dict[str, Any],
    expected_problem_names: set[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not control["complete"] or not treatment["complete"]:
        raise ValueError("control and treatment reports must both be complete")
    control_names = set(control["selectedProblemNames"])
    treatment_names = set(treatment["selectedProblemNames"])
    if control_names != expected_problem_names or treatment_names != expected_problem_names:
        raise ValueError("control or treatment differs from the frozen unresolved cohort")

    control_search = control["searchBudget"]
    treatment_search = treatment["searchBudget"]
    if control_search.get("generated_action_quotient") is not False:
        raise ValueError("control must disable the generated-action quotient")
    if treatment_search.get("generated_action_quotient") is not True:
        raise ValueError("treatment must enable the generated-action quotient")
    if int(treatment_search.get("generated_action_oversample_factor", 0)) < 1:
        raise ValueError("treatment must declare a positive oversample factor")

    intervention = {"generated_action_quotient", "generated_action_oversample_factor"}
    resource_concurrency = {
        "workers",
        "effective_problem_workers",
        "max_total_native_workers",
    }
    ignored = intervention | resource_concurrency
    control_budget = {
        key: value for key, value in control_search.items() if key not in ignored
    }
    treatment_budget = {
        key: value for key, value in treatment_search.items() if key not in ignored
    }
    if control_budget != treatment_budget:
        raise ValueError("control and treatment differ outside generated-action options")
    return control_budget, treatment_budget


def resource_concurrency_profile(summary: dict[str, Any]) -> dict[str, Any]:
    search = summary["searchBudget"]
    return {
        key: search.get(key)
        for key in (
            "workers",
            "effective_problem_workers",
            "candidate_workers",
            "effective_candidate_workers",
            "max_total_native_workers",
        )
    }


ACTION_AUDIT_FIELDS = (
    "normalized_candidate_paths",
    "invalid_paths",
    "scheduled_unique_paths",
    "equivalent_paths_skipped",
    "certificate_replay_failures",
)


def summed_action_audit(
    summary: dict[str, Any], names: set[str] | None = None
) -> dict[str, int]:
    """Sum intervention counters, optionally on a paired terminal subset."""

    rows = summary.get("generatedActionAudits", ())
    selected = [
        row for row in rows
        if names is None or str(row.get("name")) in names
    ]
    return {
        field: sum(int(row.get(field, 0)) for row in selected)
        for field in ACTION_AUDIT_FIELDS
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fresh-replay-dir", type=Path)
    parser.add_argument("--control-report", type=Path)
    parser.add_argument("--control-run-dir", type=Path)
    parser.add_argument("--control-replay-dir", type=Path)
    parser.add_argument("--treatment-report", type=Path)
    parser.add_argument("--treatment-run-dir", type=Path)
    parser.add_argument("--treatment-replay-dir", type=Path)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    dataset_path = checked_path(
        manifest["dataset"]["path"], manifest["dataset"]["sha256"]
    )
    union_path = checked_path(
        manifest["baselineUnion"]["path"], manifest["baselineUnion"]["sha256"]
    )
    unresolved = [analyse_artifact(entry) for entry in manifest["unresolved"]]
    controls = [analyse_artifact(entry) for entry in manifest["proofReplayControls"]]
    replay_dir = args.fresh_replay_dir.resolve() if args.fresh_replay_dir else None
    replays = [fresh_replay(entry, replay_dir) for entry in manifest["proofReplayControls"]]
    control = cohort_summary(
        args.control_report.resolve() if args.control_report else None,
        args.control_run_dir.resolve() if args.control_run_dir else None,
        args.control_replay_dir.resolve() if args.control_replay_dir else None,
    )
    treatment = cohort_summary(
        args.treatment_report.resolve() if args.treatment_report else None,
        args.treatment_run_dir.resolve() if args.treatment_run_dir else None,
        args.treatment_replay_dir.resolve() if args.treatment_replay_dir else None,
    )

    controlled_effect: dict[str, Any] | None = None
    if control is not None and treatment is not None:
        expected_problem_names = {
            str(entry["name"]) for entry in manifest["unresolved"]
        }
        validate_controlled_pair(control, treatment, expected_problem_names)
        control_strict = set(control["strictNewSolves"])
        treatment_strict = set(treatment["strictNewSolves"])
        control_by_name = {item["name"]: item for item in control["perProblem"]}
        treatment_by_name = {item["name"]: item for item in treatment["perProblem"]}
        terminal_statuses = {"solved", "unsolved"}
        paired_terminal = sorted(
            name
            for name in expected_problem_names
            if control_by_name[name]["status"] in terminal_statuses
            and treatment_by_name[name]["status"] in terminal_statuses
        )
        unpaired = sorted(expected_problem_names - set(paired_terminal))
        paired_control_paths = sum(
            int(control_by_name[name]["evaluatedPaths"])
            for name in paired_terminal
        )
        paired_treatment_paths = sum(
            int(treatment_by_name[name]["evaluatedPaths"])
            for name in paired_terminal
        )
        paired_control_strict = control_strict & set(paired_terminal)
        paired_treatment_strict = treatment_strict & set(paired_terminal)
        paired_names = set(paired_terminal)
        paired_control_audit = summed_action_audit(control, paired_names)
        paired_treatment_audit = summed_action_audit(treatment, paired_names)
        all_control_audit = summed_action_audit(control)
        all_treatment_audit = summed_action_audit(treatment)
        control_resources = resource_concurrency_profile(control)
        treatment_resources = resource_concurrency_profile(treatment)
        same_resources = control_resources == treatment_resources
        controlled_effect = {
            "sameFrozenCohort": True,
            "sameMathematicalSearchBudgetOutsideIntervention": True,
            "sameResourceConcurrency": same_resources,
            "resourceConcurrency": {
                "control": control_resources,
                "treatment": treatment_resources,
            },
            "wallClockCausalClaimAllowed": same_resources,
            "pairedTerminalProblems": paired_terminal,
            "unpairedOrRightCensoredProblems": unpaired,
            "pairedEvaluatedPaths": {
                "control": paired_control_paths,
                "treatment": paired_treatment_paths,
                "delta": paired_treatment_paths - paired_control_paths,
            },
            "allRunEvaluatedPathDeltaDescriptiveOnly": (
                treatment["evaluatedPaths"] - control["evaluatedPaths"]
            ),
            "elapsedProblemSecondsDeltaDescriptiveOnly": (
                treatment["elapsedProblemSeconds"] - control["elapsedProblemSeconds"]
            ),
            "rightCensoredDelta": treatment["rightCensored"] - control["rightCensored"],
            "executionErrorDelta": treatment["executionErrors"] - control["executionErrors"],
            "pairedGeneratedActionAudit": {
                "control": paired_control_audit,
                "treatment": paired_treatment_audit,
                "delta": {
                    field: paired_treatment_audit[field] - paired_control_audit[field]
                    for field in ACTION_AUDIT_FIELDS
                },
            },
            "allRunGeneratedActionAuditDescriptiveOnly": {
                "control": all_control_audit,
                "treatment": all_treatment_audit,
                "delta": {
                    field: all_treatment_audit[field] - all_control_audit[field]
                    for field in ACTION_AUDIT_FIELDS
                },
            },
            "pairedStrictTreatmentOnlySolves": sorted(
                paired_treatment_strict - paired_control_strict
            ),
            "pairedStrictControlOnlySolves": sorted(
                paired_control_strict - paired_treatment_strict
            ),
            "pairedStrictSharedSolves": sorted(
                paired_control_strict & paired_treatment_strict
            ),
            "unpairedStrictSolvesNotAttributedToIntervention": sorted(
                (control_strict | treatment_strict) - set(paired_terminal)
            ),
        }

    path_rows = [*unresolved, *controls]
    frozen_names = [str(entry["name"]) for entry in manifest["unresolved"]]
    raw_paths = sum(item["rawVerifiedPaths"] for item in path_rows)
    unique_states = sum(item["uniqueGeneratedActionStates"] for item in path_rows)
    control_strict = set(control["strictNewSolves"] if control else ())
    treatment_strict = set(treatment["strictNewSolves"] if treatment else ())
    strict_new = sorted(control_strict | treatment_strict)
    baseline_solved = int(manifest["baselineUnion"]["solved"])
    total = int(manifest["baselineUnion"]["total"])
    result = {
        "experiment": "geometry_construction_generated_action_controlled_audit",
        "benchmarkId": manifest["benchmarkId"],
        "principle": {
            "quotient": "alpha-renaming + declared input symmetry + order of independent actions",
            "preserved": "typed construction dependency DAG and semantic construction terms",
            "notInferred": (
                "numeric branch, point coordinates, numerical-search completeness, "
                "or native proof outcome"
            ),
            "acceptance": "only native certificate hashes count as strict solves",
        },
        "provenance": {
            "manifest": args.manifest.resolve().relative_to(ROOT).as_posix(),
            "manifestSha256": sha256(args.manifest),
            "dataset": manifest["dataset"],
            "baselineUnion": manifest["baselineUnion"],
            "baselineUnionObservedSha256": sha256(union_path),
            "implementation": {
                "generatedAction": {
                    "path": "worker/backend/generated_construction_action.py",
                    "sha256": sha256(ROOT / "worker/backend/generated_construction_action.py"),
                },
                "search": {
                    "path": "scripts/experiment_newclid_construction_stalk.py",
                    "sha256": sha256(ROOT / "scripts/experiment_newclid_construction_stalk.py"),
                },
                "cohortDriver": {
                    "path": "scripts/benchmark_hageo409_auxiliary.py",
                    "sha256": sha256(ROOT / "scripts/benchmark_hageo409_auxiliary.py"),
                },
            },
            "usesExternalLlm": False,
        },
        "retrospectiveControl": {
            "rawVerifiedPaths": raw_paths,
            "uniqueGeneratedActionStates": unique_states,
            "equivalentPathsRemoved": raw_paths - unique_states,
            "quotientReductionRate": ((raw_paths - unique_states) / raw_paths if raw_paths else 0.0),
            "certificateReplayRate": (
                sum(not item["certificateReplayFailures"] for item in path_rows)
                / len(path_rows)
            ),
            "normalizationErrorCount": sum(len(item["normalizationErrors"]) for item in path_rows),
            "outcomeInconsistentClassCount": sum(len(item["outcomeInconsistentClasses"]) for item in path_rows),
        },
        "unresolvedSurfaceInventory": unresolved_surface_inventory(
            dataset_path, frozen_names
        ),
        "nativeProofReplay": {
            "total": len(replays),
            "accepted": sum(item["accepted"] for item in replays),
            "rate": sum(item["accepted"] for item in replays) / len(replays),
            "runs": replays,
        },
        "control": control,
        "treatment": treatment,
        "controlledEffect": controlled_effect,
        "score": {
            "before": {"solved": baseline_solved, "total": total, "rate": baseline_solved / total},
            "strictAdditionalSolves": strict_new,
            "after": {
                "solved": baseline_solved + len(strict_new),
                "total": total,
                "rate": (baseline_solved + len(strict_new)) / total,
            },
        },
        "unresolvedProblems": unresolved,
        "proofReplayControls": controls,
        "conclusion": (
            "The symbolic generated-action certificates replay; the frozen A/B result counts only independently replayed native proofs and does not infer numerical-search completeness or unmeasured score gains."
            if controlled_effect is not None
            else "Retrospective quotient and proof replay are complete; a paired prospective A/B result has not been supplied."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "retrospectiveControl": result["retrospectiveControl"],
        "nativeProofReplay": {key: result["nativeProofReplay"][key] for key in ("total", "accepted", "rate")},
        "score": result["score"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
