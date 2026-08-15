from newclid.jgex.constructions import ALL_JGEX_CONSTRUCTIONS
from newclid.jgex.definition import JGEXDefinition
from newclid.jgex.formulation import JGEXFormulation

from worker.backend.jgex_legacy_normalizer import normalize_legacy_formulation


DEFINITIONS = JGEXDefinition.to_dict(ALL_JGEX_CONSTRUCTIONS)


def normalized_setup(problem: str) -> str:
    formulation = JGEXFormulation.from_text(problem)
    normalized, report = normalize_legacy_formulation(formulation, DEFINITIONS)
    assert report.unresolved_constructions == 0
    return str(normalized).split(" ? ", maxsplit=1)[0]


def test_restores_omitted_free_triangle_outputs() -> None:
    assert normalized_setup("a b c = triangle") == "a b c = triangle a b c"


def test_restores_omitted_free_segment_outputs() -> None:
    assert normalized_setup("b c = segment") == "b c = segment b c"


def test_restores_omitted_relative_construction_output() -> None:
    assert normalized_setup("x = angle_bisector p b a") == (
        "x = angle_bisector x p b a"
    )


def test_moves_legacy_trailing_output_to_definition_position() -> None:
    assert normalized_setup("x = parallelogram e a m x") == (
        "x = parallelogram x e a m"
    )


def test_preserves_current_jgex_syntax() -> None:
    problem = "a b c = triangle a b c; x = angle_bisector x b a c"
    assert normalized_setup(problem) == problem


def test_normalizes_each_intersection_constraint_from_same_lhs() -> None:
    assert normalized_setup("p = on_line a b, on_circle o a") == (
        "p = on_line p a b, on_circle p o a"
    )


def test_coordinate_annotations_are_sketch_metadata_not_output_names() -> None:
    assert normalized_setup(
        "a@0_0 b@1_0 c@0_1 = triangle a b c; "
        "x@0.5_0.5 = on_circle x a b"
    ) == (
        "a@0_0 b@1_0 c@0_1 = triangle a b c; "
        "x@0.5_0.5 = on_circle x a b"
    )
