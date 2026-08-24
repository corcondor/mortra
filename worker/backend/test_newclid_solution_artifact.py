import pytest

pytest.importorskip("newclid")

from worker.backend.newclid_solution_artifact import (
    build_newclid_solution_artifact,
    construction_graph,
)

from newclid.jgex.formulation import JGEXFormulation


ORTHOCENTER = (
    "a b c = triangle a b c; "
    "h = on_tline h b a c, on_tline h c a b ? perp a h b c"
)

UNPROVED_CONGRUENCE = (
    "a b c = triangle; i = incenter a b c; d = foot i b c; "
    "o = circumcenter a b c; m1 = midpoint a i; "
    "s = on_circle o a, on_circle m1 a; h = orthocenter b i c; "
    "q = on_line h s, on_circle m1 a; m2 = midpoint d q; "
    "x = mirror i m2 ? cong i x d i"
)


def test_construction_graph_records_dependencies_without_problem_templates() -> None:
    formulation = JGEXFormulation.from_text(ORTHOCENTER)
    nodes, edges = construction_graph(formulation)

    assert [node.operation for node in nodes] == ["triangle", "on_tline", "on_tline"]
    assert {edge.point for edge in edges} == {"a", "b", "c"}
    assert all(edge.consumer.startswith("c1.") for edge in edges)


def test_native_run_returns_synchronized_proof_and_svg() -> None:
    artifact = build_newclid_solution_artifact(ORTHOCENTER, seed=1234)

    assert artifact.status == "proved", artifact.error
    assert artifact.solved
    assert artifact.proof_length > 0
    assert "⟂" in artifact.proof_text
    assert "<svg" in artifact.diagram_svg
    assert set(artifact.coordinates) == {"a", "b", "c", "h"}
    assert any("⟂" in predicate for predicate in artifact.proof_predicates)


def test_point_renaming_preserves_construction_program_shape() -> None:
    renamed = (
        "p q r = triangle p q r; "
        "s = on_tline s q p r, on_tline s r p q ? perp p s q r"
    )
    first = build_newclid_solution_artifact(ORTHOCENTER, seed=7)
    second = build_newclid_solution_artifact(renamed, seed=7)

    assert first.solved and second.solved
    assert [node.operation for node in first.construction_nodes] == [
        node.operation for node in second.construction_nodes
    ]
    assert first.formulation_sha256 != second.formulation_sha256


def test_native_run_normalizes_legacy_omitted_output_arguments() -> None:
    legacy = (
        "a b c = iso_triangle; "
        "i = incenter a b c ? cong a b a c"
    )

    artifact = build_newclid_solution_artifact(legacy, seed=11)

    assert artifact.status == "proved", artifact.error
    assert artifact.solved
    assert artifact.run["legacy_normalization"]["rewritten_constructions"] == 2
    assert artifact.run["legacy_normalization"]["unresolved_constructions"] == 0


def test_unproved_run_is_not_misclassified_as_rendering_error() -> None:
    artifact = build_newclid_solution_artifact(UNPROVED_CONGRUENCE, seed=0)

    assert artifact.status == "unproved", artifact.error
    assert not artifact.solved
    assert artifact.error is None
    assert artifact.proof_text == ""
    assert "<svg" in artifact.diagram_svg
