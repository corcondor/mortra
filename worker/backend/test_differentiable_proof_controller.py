from __future__ import annotations

import json
from copy import deepcopy

import pytest

from worker.backend.differentiable_proof_controller import (
    FEATURE_GROUPS,
    FEATURE_NAMES,
    DifferentiableProofController,
    extract_controller_features,
)


def sample_record() -> dict[str, object]:
    return {
        "steps": [
            {
                "family": "not_a_feature",
                "output": "e",
                "inputs": ["a", "b"],
                "structural_rank": [0, 1, 0, -2.5, -4, -2, 0, -1.5, 0, 0, -3, -2, -1, 0, 2, 3, 2],
            }
        ],
        "solved": False,
        "all_deduction_count": 120,
        "goal_deduction_count": 3,
        "relation_target_assertion_count": 2,
        "relation_support_weight": 9,
        "relation_near_goal_count": 4,
        "relation_transition_potential": 12.5,
        "relation_transition_channel_coverage": 3,
        "frontier_witnesses": [
            {"distance_to_goal": 1, "goal_support_overlap": 3, "points": ["a", "e"]}
        ],
        "backward_obligations": [{"theorem": "hidden_name"}],
        "open_relation_demands": [{"predicate": "perp", "arguments": ["a", "e"]}],
        "ar_supported_goal_count": 1,
        "ar_closed_goal_count": 0,
        "ar_residual_support_size": 2,
        "ar_residual_l1_weight": 2.0,
        "ar_known_rank": 11,
        "elapsed_seconds": 0.4,
        "error": None,
    }


def test_feature_schema_excludes_problem_solution_and_entity_identity() -> None:
    assert set(FEATURE_NAMES) == {
        feature for values in FEATURE_GROUPS.values() for feature in values
    }
    forbidden_fragments = ("problem", "answer", "point", "entity", "family", "theorem")
    assert not any(
        fragment in feature
        for fragment in forbidden_fragments
        for feature in FEATURE_NAMES
    )


def test_entity_and_rule_renaming_leave_features_and_score_unchanged() -> None:
    original = sample_record()
    renamed = deepcopy(original)
    renamed["problem_name"] = "unseen_problem"
    renamed["steps"][0]["family"] = "renamed_family"  # type: ignore[index]
    renamed["steps"][0]["output"] = "q99"  # type: ignore[index]
    renamed["steps"][0]["inputs"] = ["u17", "v23"]  # type: ignore[index]
    renamed["frontier_witnesses"][0]["points"] = ["u17", "q99"]  # type: ignore[index]
    renamed["backward_obligations"][0]["theorem"] = "renamed_rule"  # type: ignore[index]
    renamed["open_relation_demands"][0]["arguments"] = ["u17", "q99"]  # type: ignore[index]

    controller = DifferentiableProofController()
    assert extract_controller_features(original) == extract_controller_features(renamed)
    assert controller.score_record(original).score == pytest.approx(
        controller.score_record(renamed).score
    )


def test_consensus_trace_converges_and_does_not_change_truth() -> None:
    record = sample_record()
    controller = DifferentiableProofController()
    result = controller.score_record(record)
    assert len(result.trace) == controller.parameters.iterations
    assert result.trace[-1].primal_residual < result.trace[0].primal_residual
    assert 0.0 < result.consensus < 1.0
    assert record["solved"] is False


def test_every_progress_feature_is_locally_monotone() -> None:
    controller = DifferentiableProofController()
    baseline = {name: 0.25 for name in FEATURE_NAMES}
    baseline_scores = controller.local_scores(baseline)
    for stalk, names in FEATURE_GROUPS.items():
        for name in names:
            improved = dict(baseline)
            improved[name] = 0.75
            assert controller.local_scores(improved)[stalk] >= baseline_scores[stalk]


def test_missing_algebra_measurements_are_neutral_not_perfect() -> None:
    record = sample_record()
    for name in (
        "ar_supported_goal_count",
        "ar_closed_goal_count",
        "ar_residual_support_size",
        "ar_residual_l1_weight",
        "ar_known_rank",
    ):
        record.pop(name)
    features = extract_controller_features(record)
    assert all(features[name] == 0.5 for name in FEATURE_GROUPS["algebra"])


def test_serialized_controller_rejects_feature_schema_tampering(tmp_path) -> None:
    controller = DifferentiableProofController()
    payload = controller.to_dict()
    payload["feature_names"] = [*payload["feature_names"], "problem_id"]
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        DifferentiableProofController.load(path)
