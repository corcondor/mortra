from worker.backend.wu_experiment_selection import eligible_conditional_names


def test_selection_uses_exact_eliminator_when_coordination_replay_abstains() -> None:
    baseline = {
        "results": {
            "p": {
                "status": "completed",
                "result": {"conditional_goal_proved": True},
                "coordination": {
                    "conditional_goal_solved": False,
                    "open_regularity_count": 3,
                },
            }
        }
    }

    assert eligible_conditional_names(baseline, ("p",)) == ("p",)


def test_selection_rejects_unproved_or_unconditional_results() -> None:
    baseline = {
        "results": {
            "unproved": {
                "status": "completed",
                "result": {"conditional_goal_proved": False},
                "coordination": {"open_regularity_count": 2},
            },
            "closed": {
                "status": "completed",
                "result": {"conditional_goal_proved": True},
                "coordination": {"open_regularity_count": 0},
            },
        }
    }

    assert eligible_conditional_names(baseline, ("unproved", "closed")) == ()
