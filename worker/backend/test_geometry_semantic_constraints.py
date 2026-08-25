from worker.backend.geometry_semantic_constraints import (
    parse_geometry_semantic_context,
)
from worker.backend.jgex_exact_constraint_bridge import (
    inspect_jgex_semantic_branch_matches,
    inspect_jgex_exact_system,
    lower_jgex_to_exact_obligation,
)


PAIRED_TANGENT_SETUP = (
    "a b c = triangle; o = circumcenter a b c; "
    "d = on_tline b o b, on_circle b c; "
    "e = on_tline c o c, on_circle c b"
)
GOOD_SIDE_CONDITION = (
    "Let D,E be points such that A is on one side of line BC and "
    "D,E are on the other side."
)


def test_source_prose_derives_same_side_from_common_opposite_anchor() -> None:
    context = parse_geometry_semantic_context(GOOD_SIDE_CONDITION)

    derivation = context.derive_same_side("d", "e", "b", "c")

    assert derivation is not None
    assert derivation.rule == "opposite_to_common_anchor_implies_same_side"
    assert len(derivation.premises) == 2


def test_mixed_side_conditions_do_not_select_the_reflection_branch() -> None:
    context = parse_geometry_semantic_context(
        "A and D are on the same side of line BC. "
        "A and E are on opposite sides of line BC."
    )

    assert context.derive_same_side("d", "e", "b", "c") is None


def test_semantic_branch_is_goal_independent_and_uses_bc_as_gauge() -> None:
    match = inspect_jgex_semantic_branch_matches(
        PAIRED_TANGENT_SETUP + " ? para d e b c",
        natural_language=GOOD_SIDE_CONDITION,
    )
    analysis = inspect_jgex_exact_system(
        PAIRED_TANGENT_SETUP + " ? para d e b c",
        natural_language=GOOD_SIDE_CONDITION,
        representation="relational",
    )

    assert len(match) == 1
    assert match[0].same_side_derivation_rule == (
        "opposite_to_common_anchor_implies_same_side"
    )
    assert len(analysis.semialgebraic_branch_certificates) == 1
    certificate = analysis.semialgebraic_branch_certificates[0]
    assert certificate.replayed
    assert certificate.goal_independent
    assert certificate.coordinate_substitutions[0][1] == "_base_0 - _free_x_5"
    coordinates = dict(analysis.point_coordinates)
    assert coordinates["b"] == ("0", "0")
    assert coordinates["c"] == ("_base_0", "0")


def test_strict_side_condition_proves_only_the_selected_tangent_branch() -> None:
    problem = PAIRED_TANGENT_SETUP + " ? para d e b c"

    selected = lower_jgex_to_exact_obligation(
        problem,
        natural_language=GOOD_SIDE_CONDITION,
        representation="relational",
    )
    unselected = lower_jgex_to_exact_obligation(
        problem,
        representation="relational",
    )
    contradictory = lower_jgex_to_exact_obligation(
        problem,
        natural_language=(
            "A and D are on the same side of line BC. "
            "A and E are on opposite sides of line BC."
        ),
        representation="relational",
    )

    assert selected.exact_replay
    assert selected.remainder == "0"
    assert len(selected.semialgebraic_branch_certificates) == 1
    assert not unselected.exact_replay
    assert not contradictory.exact_replay
    assert not unselected.semialgebraic_branch_certificates
    assert not contradictory.semialgebraic_branch_certificates
