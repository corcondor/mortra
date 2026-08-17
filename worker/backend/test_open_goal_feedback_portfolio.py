from scripts.experiment_open_goal_feedback_imo_ag_30 import (
    SearchStage,
    original_benchmark_names,
    portfolio_summary,
    stage_artifact_matches,
)


def test_portfolio_union_does_not_double_count_agent_successes() -> None:
    summary = portfolio_summary(
        baseline_names=("a", "b"),
        strict_exchange_names=("b", "c"),
        construction_names=("c", "d"),
        total=5,
    )
    assert summary["portfolio_solved"] == 4
    assert summary["new_strict_exchange_names"] == ["c"]
    assert summary["new_construction_feedback_names"] == ["d"]
    assert summary["portfolio_score"] == 0.8


def test_original_benchmark_names_excludes_reformulated_result() -> None:
    baseline = {
        "scores": {
            "original_imo_ag_30": {"solved_names": ["original_a", "original_b"]},
            "readme_reformulated_imo_ag_30": {
                "solved_names": ["original_a", "original_b", "easy_variant"]
            },
        },
        "results": {"easy_variant": {"status": "solved"}},
    }
    assert original_benchmark_names(baseline) == {"original_a", "original_b"}


def test_stage_artifact_resume_requires_the_same_fixed_budget() -> None:
    stage = SearchStage(
        "test",
        (
            "--per-family-limit",
            "4",
            "--branch-limit",
            "42",
            "--beam-width",
            "8",
            "--max-depth",
            "1",
            "--beam-ranking",
            "frontier-pareto",
        ),
    )
    artifact = {
        "experiment": "newclid_dynamic_typed_construction_stalk_no_llm",
        "protocol": {
            "ranking": "structural",
            "beam_ranking": "frontier-pareto",
            "per_family_limit": 4,
            "branch_limit": 42,
            "beam_width": 8,
            "max_depth": 1,
        },
    }
    assert stage_artifact_matches(
        artifact,
        stage=stage,
        candidate_ranking="structural",
        beam_ranking_override=None,
    )
    assert not stage_artifact_matches(
        artifact,
        stage=stage,
        candidate_ranking="random",
        beam_ranking_override=None,
    )
