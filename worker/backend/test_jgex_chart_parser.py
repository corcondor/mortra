from __future__ import annotations

import pytest

from worker.backend.jgex_chart_parser import ChartJGEXFormulation


def test_parser_preserves_multi_output_and_intersection_constructions() -> None:
    source = (
        "a b c = triangle; p q = on_circle o a, on_line b c; "
        "x = on_line a p, on_line b q ? coll c p x"
    )

    formulation = ChartJGEXFormulation.from_text(source)

    assert formulation.setup_clauses[1].points == ("p", "q")
    assert tuple(
        (item.name, item.args)
        for item in formulation.setup_clauses[1].constructions
    ) == (("on_circle", ("o", "a")), ("on_line", ("b", "c")))
    assert str(formulation.goals[0]) == "coll c p x"


def test_parser_canonicalizes_equal_angles_like_newclid() -> None:
    formulation = ChartJGEXFormulation.from_text(
        "u v w = triangle ? eqangle u v u p u x u w"
    )

    assert str(formulation.goals[0]) == "eqangle p u u v u w u x"


def test_parser_erases_repeated_output_names_from_frozen_jgex_surface() -> None:
    formulation = ChartJGEXFormulation.from_text(
        "a b c = triangle a b c; x = on_line x a b, on_line x b c ? coll a x b"
    )

    assert formulation.setup_clauses[0].constructions[0].name == "triangle"
    assert formulation.setup_clauses[0].constructions[0].args == ()
    assert tuple(
        construction.args
        for construction in formulation.setup_clauses[1].constructions
    ) == (("a", "b"), ("b", "c"))


@pytest.mark.parametrize(
    "source",
    (
        "a b c = triangle",
        "a b c triangle ? coll a b c",
        "a b c = triangle ?",
        "? coll a b c",
    ),
)
def test_parser_rejects_incomplete_chart_sources(source: str) -> None:
    with pytest.raises(ValueError):
        ChartJGEXFormulation.from_text(source)
