from pathlib import Path

from worker.backend.geometry_relation_channels import (
    RelationStalkSection,
    backward_relation_distances,
    canonical_relation,
    gclc_goal_channel,
    sections_compatible,
    yuclid_assertion_keys,
    yuclid_relation_metrics,
)


def test_relation_aliases_preserve_geometry_channels() -> None:
    assert canonical_relation("collinear") == "coll"
    assert canonical_relation("perpendicular") == "perp"
    assert canonical_relation("parallel") == "para"
    assert canonical_relation("same_length") == "cong"


def test_yuclid_metrics_reward_target_channel_and_goal_support() -> None:
    payload = {
        "all_deductions": [
            {"assertions": [{"name": "coll", "points": ["x", "o", "a"]}]},
            {"assertions": [{"name": "coll", "points": ["x", "o", "o1"]}]},
            {"assertions": [{"name": "perp", "points": ["x", "o", "o1"]}]},
        ]
    }
    metrics = yuclid_relation_metrics(
        payload, goal_channels={"coll"}, goal_support={"x", "o", "o1"}
    )
    assert metrics.target_assertion_count == 2
    assert metrics.target_support_weight == 13
    assert metrics.near_goal_assertion_count == 2
    assert dict(metrics.channel_counts) == {"coll": 2, "perp": 1}


def test_yuclid_metrics_count_only_novel_nonconstruction_progress() -> None:
    baseline = {
        "all_deductions": [
            {
                "newclid_rule": "Existing theorem",
                "assertions": [{"name": "coll", "points": ["a", "b", "c"]}],
            }
        ]
    }
    branch = {
        "all_deductions": [
            *baseline["all_deductions"],
            {
                "newclid_rule": "By construction",
                "assertions": [{"name": "coll", "points": ["x", "b", "c"]}],
            },
            {
                "newclid_rule": "Circle theorem",
                "assertions": [{"name": "coll", "points": ["x", "o", "c"]}],
            },
        ]
    }
    metrics = yuclid_relation_metrics(
        branch,
        goal_channels={"coll"},
        goal_support={"x", "o", "c"},
        excluded_assertion_keys=yuclid_assertion_keys(baseline),
        exclude_direct_construction=True,
    )
    assert metrics.target_assertion_count == 1
    assert metrics.target_support_weight == 9
    assert metrics.near_goal_assertion_count == 1


def test_backward_relation_distance_rewards_proof_reachable_channels() -> None:
    distances = backward_relation_distances(
        [
            (("eqangle", "ncoll"), ("cyclic",)),
            (("cyclic", "cong", "npara"), ("cong",)),
            (("perp", "eqangle"), ("para",)),
        ],
        goal_channels={"cong"},
    )
    assert distances["cong"] == 0
    assert distances["cyclic"] == 1
    assert distances["eqangle"] == 2
    assert "perp" not in distances

    metrics = yuclid_relation_metrics(
        {
            "all_deductions": [
                {
                    "newclid_rule": "r04",
                    "assertions": [{"name": "cyclic", "points": ["a", "b", "c", "d"]}],
                }
            ]
        },
        goal_channels={"cong"},
        goal_support={"a", "b"},
        transition_distances=distances,
    )
    assert metrics.transition_potential == 0.5
    assert metrics.transition_channel_coverage == 1


def test_gclc_goal_is_lowered_to_shared_channel() -> None:
    assert gclc_goal_channel("prove { collinear P Q S }") == "coll"
    assert gclc_goal_channel("prove { perpendicular A B C H }") == "perp"
    assert gclc_goal_channel("prove { parallel A B C D }") == "para"
    assert gclc_goal_channel("prove { equal { sratio A B C D } 1 }") == "eqratio"
    assert (
        gclc_goal_channel("prove\n{ equal\n { sum { a } { b } }\n { sum { b } { a } }\n}")
        == "algebraic_equal"
    )


def test_stalk_compatibility_requires_channel_and_support_overlap() -> None:
    newclid = RelationStalkSection("newclid", "coll", ("o", "x"), "n.json")
    gclc = RelationStalkSection("gclc", "coll", ("x", "y"), "g.tex")
    wrong_channel = RelationStalkSection("gclc", "perp", ("x", "y"), "p.tex")
    assert sections_compatible(newclid, gclc)
    assert not sections_compatible(newclid, wrong_channel)
