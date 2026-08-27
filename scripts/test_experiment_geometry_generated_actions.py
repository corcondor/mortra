from __future__ import annotations

from copy import deepcopy
import json

import pytest

from scripts.experiment_geometry_generated_actions import (
    cohort_summary,
    resource_concurrency_profile,
    strict_replay_acceptance,
    summed_action_audit,
    unresolved_surface_inventory,
    validate_controlled_pair,
)


def replay_payload() -> dict[str, bool]:
    return {
        "accepted": True,
        "expected_hashes_present": True,
        "replay_solved": True,
        "input_hash_matches": True,
        "proof_hash_matches": True,
        "repeat_replay_solved": True,
        "repeat_input_hash_matches": True,
        "repeat_proof_hash_matches": True,
    }


def cohort(*, treatment: bool) -> dict[str, object]:
    return {
        "complete": True,
        "selectedProblemNames": ["a", "b"],
        "searchBudget": {
            "depth": 2,
            "paths": 112,
            "generated_action_quotient": treatment,
            "generated_action_oversample_factor": 4 if treatment else 1,
        },
        "perProblem": [
            {"name": "a", "status": "unsolved", "evaluatedPaths": 10},
            {"name": "b", "status": "unsolved", "evaluatedPaths": 10},
        ],
    }


def test_strict_replay_acceptance_recomputes_every_hash_condition() -> None:
    payload = replay_payload()
    assert strict_replay_acceptance(payload)
    for key in payload:
        mutated = deepcopy(payload)
        mutated[key] = False
        assert not strict_replay_acceptance(mutated), key


def test_controlled_pair_requires_complete_frozen_cohorts_and_one_intervention() -> None:
    control = cohort(treatment=False)
    treatment = cohort(treatment=True)
    validate_controlled_pair(control, treatment, {"a", "b"})

    incomplete = deepcopy(treatment)
    incomplete["complete"] = False
    with pytest.raises(ValueError, match="both be complete"):
        validate_controlled_pair(control, incomplete, {"a", "b"})

    wrong_cohort = deepcopy(treatment)
    wrong_cohort["selectedProblemNames"] = ["a"]
    with pytest.raises(ValueError, match="frozen unresolved cohort"):
        validate_controlled_pair(control, wrong_cohort, {"a", "b"})

    untreated = deepcopy(treatment)
    untreated["searchBudget"]["generated_action_quotient"] = False
    with pytest.raises(ValueError, match="treatment must enable"):
        validate_controlled_pair(control, untreated, {"a", "b"})


def test_problem_level_resource_concurrency_is_reported_but_not_a_math_budget() -> None:
    control = cohort(treatment=False)
    treatment = cohort(treatment=True)
    control["searchBudget"].update({
        "workers": 4,
        "effective_problem_workers": 4,
        "candidate_workers": 2,
        "effective_candidate_workers": 2,
        "max_total_native_workers": 8,
    })
    treatment["searchBudget"].update({
        "workers": 1,
        "effective_problem_workers": 1,
        "candidate_workers": 2,
        "effective_candidate_workers": 2,
        "max_total_native_workers": 2,
    })

    validate_controlled_pair(control, treatment, {"a", "b"})
    assert resource_concurrency_profile(control) != resource_concurrency_profile(treatment)

    treatment["searchBudget"]["candidate_workers"] = 1
    with pytest.raises(ValueError, match="differ outside generated-action options"):
        validate_controlled_pair(control, treatment, {"a", "b"})


def test_surface_inventory_counts_explicit_vocabulary_without_claiming_cause(tmp_path) -> None:
    dataset = tmp_path / "sample.jgex"
    dataset.write_text(
        "p1\n"
        "a b c = triangle; o = circumcenter a b c; x = on_circle o a ? cyclic a b c x\n"
        "p2\n"
        "a b c = triangle; d = foot a b c ? perp a d b c\n",
        encoding="utf-8",
    )

    inventory = unresolved_surface_inventory(dataset, ["p1", "p2"])

    assert inventory["problemCountByToken"] == {
        "circumcenter": 1,
        "foot": 1,
        "on_circle": 1,
    }
    assert "does not establish" in inventory["interpretationBoundary"]


def test_action_audit_can_be_restricted_to_the_paired_terminal_subset() -> None:
    summary = {
        "generatedActionAudits": [
            {
                "name": "paired",
                "normalized_candidate_paths": 12,
                "equivalent_paths_skipped": 2,
                "scheduled_unique_paths": 10,
            },
            {
                "name": "censored",
                "normalized_candidate_paths": 100,
                "equivalent_paths_skipped": 9,
                "scheduled_unique_paths": 91,
            },
        ]
    }

    paired = summed_action_audit(summary, {"paired"})

    assert paired["normalized_candidate_paths"] == 12
    assert paired["equivalent_paths_skipped"] == 2
    assert paired["scheduled_unique_paths"] == 10
    assert paired["invalid_paths"] == 0


def test_cohort_summary_rechecks_checkpoint_with_embedded_count(tmp_path) -> None:
    checkpoint = tmp_path / "p.progress.json"
    checkpoint.write_text('{"evaluated_path_count": 41}\n', encoding="utf-8")
    report = tmp_path / "report.json"
    report.write_text(
        json.dumps(
            {
                "run_state": {"complete": True},
                "selected_problem_names": ["p"],
                "protocol": {"search_budget": {}},
                "runs": [
                    {
                        "problem": "p",
                        "status": "right_censored_timeout",
                        "evaluated_paths": 41,
                        "checkpoint": str(checkpoint),
                        "checkpoint_sha256": "0" * 64,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="frozen artifact changed"):
        cohort_summary(report, None, None)


def test_cohort_summary_is_self_contained_after_checkpoint_enrichment(
    tmp_path,
) -> None:
    missing_checkpoint = tmp_path / "not-committed.progress.json"
    report = tmp_path / "report.json"
    checkpoint_hash = "1" * 64
    report.write_text(
        json.dumps(
            {
                "run_state": {"complete": True},
                "selected_problem_names": ["p"],
                "protocol": {"search_budget": {}},
                "runs": [
                    {
                        "problem": "p",
                        "status": "right_censored_timeout",
                        "evaluated_paths": 41,
                        "checkpoint": str(missing_checkpoint),
                        "checkpoint_sha256": checkpoint_hash,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    summary = cohort_summary(report, None, None)

    assert summary["evaluatedPaths"] == 41
    assert summary["checkpointSha256"] == {"p": checkpoint_hash}
