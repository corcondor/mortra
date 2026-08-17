from scripts.compare_open_goal_feedback_ablation import compare_reports


def test_compare_reports_uses_only_paired_cases_and_sums_all_stages() -> None:
    structural = {
        "results": {
            "a": {"status": "proved", "stages": [{"evaluated_paths": 2}]},
            "b": {
                "status": "proved",
                "stages": [{"evaluated_paths": 3}, {"evaluated_paths": 5}],
            },
            "structural_only": {"status": "proved", "stages": []},
        }
    }
    random = {
        "results": {
            "a": {"status": "unproved", "stages": [{"evaluated_paths": 7}]},
            "b": {"status": "proved", "stages": [{"evaluated_paths": 11}]},
        }
    }
    result = compare_reports(structural, random)
    assert result["paired_problem_count"] == 2
    assert result["structural_proved"] == 2
    assert result["random_proved"] == 1
    assert result["structural_total_paths"] == 10
    assert result["random_total_paths"] == 18
