from dataclasses import replace

from worker.backend.generated_construction_action import (
    ConstructionAction,
    normalize_construction_actions,
    verify_construction_action_certificate,
)


def _certificate(actions: list[ConstructionAction]):
    result = normalize_construction_actions(actions)
    assert not result.errors
    assert result.certificate is not None
    return result.certificate


def test_independent_actions_and_alpha_renaming_share_one_normal_form() -> None:
    left = _certificate(
        [
            ConstructionAction("midpoint", "x", ("a", "b")),
            ConstructionAction("circumcenter", "y", ("c", "d", "e")),
        ]
    )
    right = _certificate(
        [
            ConstructionAction("circumcenter", "u", ("e", "c", "d")),
            ConstructionAction("midpoint", "v", ("b", "a")),
        ]
    )
    assert left.semantic_state_key == right.semantic_state_key
    assert [item.family for item in left.canonical_actions] == [
        item.family for item in right.canonical_actions
    ]
    assert not verify_construction_action_certificate(left)


def test_dependency_is_preserved_when_generated_names_change() -> None:
    left = _certificate(
        [
            ConstructionAction("midpoint", "x", ("a", "b")),
            ConstructionAction("foot", "y", ("c", "x", "d")),
        ]
    )
    right = _certificate(
        [
            ConstructionAction("midpoint", "q", ("b", "a")),
            ConstructionAction("foot", "r", ("c", "d", "q")),
        ]
    )
    assert left.semantic_state_key == right.semantic_state_key
    assert left.canonical_actions[1].inputs == ("c", "d", "g0")


def test_independent_prefix_order_does_not_change_a_dependent_dag_state() -> None:
    left = _certificate(
        [
            ConstructionAction("midpoint", "x", ("a", "b")),
            ConstructionAction("circumcenter", "y", ("c", "d", "e")),
            ConstructionAction("foot", "z", ("x", "f", "g")),
        ]
    )
    right = _certificate(
        [
            ConstructionAction("circumcenter", "u", ("e", "d", "c")),
            ConstructionAction("midpoint", "v", ("b", "a")),
            ConstructionAction("foot", "w", ("v", "g", "f")),
        ]
    )

    assert left.semantic_state_key == right.semantic_state_key
    assert [item.family for item in left.canonical_actions] == [
        "circumcenter",
        "midpoint",
        "foot",
    ]
    assert [item.family for item in right.canonical_actions] == [
        "circumcenter",
        "midpoint",
        "foot",
    ]


def test_forward_reference_and_duplicate_semantic_branch_are_rejected() -> None:
    forward = normalize_construction_actions(
        [
            ConstructionAction("foot", "y", ("c", "x", "d")),
            ConstructionAction("midpoint", "x", ("a", "b")),
        ]
    )
    assert any("forward reference" in error for error in forward.errors)

    duplicate = normalize_construction_actions(
        [
            ConstructionAction("midpoint", "x", ("a", "b")),
            ConstructionAction("midpoint", "y", ("b", "a")),
        ]
    )
    assert any("branch-ambiguous" in error for error in duplicate.errors)


def test_mutated_certificate_is_not_accepted() -> None:
    certificate = _certificate([ConstructionAction("midpoint", "x", ("a", "b"))])
    mutated = replace(certificate, semantic_state_key="stale")
    assert "construction-action certificate replay mismatch" in verify_construction_action_certificate(mutated)


def test_distinct_base_incidence_is_not_merged() -> None:
    left = _certificate([ConstructionAction("midpoint", "x", ("a", "b"))])
    right = _certificate([ConstructionAction("midpoint", "x", ("a", "c"))])
    assert left.semantic_state_key != right.semantic_state_key


def test_certificate_explicitly_excludes_numerical_search_completeness() -> None:
    certificate = _certificate([ConstructionAction("on_line", "x", ("a", "b"))])
    assert "numeric-branch-equivalence" in certificate.not_claimed
    assert "generated-point-coordinate-equality" in certificate.not_claimed
    assert "numeric-branch-search-completeness" in certificate.not_claimed
    assert "native-proof-outcome-equivalence" in certificate.not_claimed
