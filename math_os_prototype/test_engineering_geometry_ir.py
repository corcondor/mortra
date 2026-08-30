from __future__ import annotations

import pytest

from math_os_prototype.engineering_geometry_ir import (
    BasisOp,
    ConstructionProgram,
    GeometricType,
    basis_summary,
)


def test_basis_is_dimension_independent_and_small() -> None:
    summary = basis_summary()
    assert summary["basis_size"] == 8
    assert set(summary["legacy_aliases"]) == {
        "Rotate3",
        "Extrude",
        "Revolve",
        "Loft",
        "Boundary",
        "CrossSection",
    }


def test_same_sweep_rule_typechecks_in_three_and_four_dimensions() -> None:
    program = ConstructionProgram("dimension-independent-sweep")
    face3 = program.declare("face3", GeometricType(3, 2, "region"))
    volume3 = program.apply(
        BasisOp.SWEEP,
        [face3],
        "volume3",
        GeometricType(3, 3, "region"),
        path_dimension=1,
    )
    volume4 = program.declare("volume4", GeometricType(4, 3, "region"))
    hypervolume4 = program.apply(
        BasisOp.SWEEP,
        [volume4],
        "hypervolume4",
        GeometricType(4, 4, "region"),
        path_dimension=1,
    )
    assert volume3.geometric_type.intrinsic_dimension == 3
    assert hypervolume4.geometric_type.intrinsic_dimension == 4


def test_invalid_boolean_across_dimensions_is_rejected() -> None:
    program = ConstructionProgram("bad-boolean")
    a = program.declare("a", GeometricType(3, 3, "region"))
    b = program.declare("b", GeometricType(4, 4, "region"))
    with pytest.raises(ValueError, match="identical"):
        program.apply(
            BasisOp.COMBINE,
            [a, b],
            "bad",
            GeometricType(3, 3, "region"),
            operation="union",
        )


def test_projection_and_slice_signatures() -> None:
    program = ConstructionProgram("drawing")
    solid = program.declare("solid", GeometricType(3, 3, "region"))
    section = program.apply(
        BasisOp.SLICE,
        [solid],
        "section",
        GeometricType(3, 2, "section"),
        codimension=1,
    )
    drawing = program.apply(
        BasisOp.PROJECT,
        [solid],
        "drawing",
        GeometricType(2, 2, "drawing"),
    )
    assert section.geometric_type == GeometricType(3, 2, "section")
    assert drawing.geometric_type == GeometricType(2, 2, "drawing")
