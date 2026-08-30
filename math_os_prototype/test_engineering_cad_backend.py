from __future__ import annotations

import importlib.util
import math

import pytest


pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("build123d") is None,
    reason="build123d/OpenCascade research environment is not active",
)


from math_os_prototype.engineering_cad_backend import (  # noqa: E402
    build_angle_bracket,
    build_clevis_bracket,
    build_cross_drilled_manifold,
    build_flange,
    build_lattice_panel,
    build_spoked_wheel,
    build_stepped_shaft,
    build_transition_duct,
    export_part_artifacts,
)


@pytest.mark.parametrize(
    "builder",
    [
        build_flange,
        build_stepped_shaft,
        build_angle_bracket,
        build_transition_duct,
        build_lattice_panel,
        build_spoked_wheel,
        build_clevis_bracket,
        build_cross_drilled_manifold,
    ],
)
def test_part_is_valid_and_every_executable_check_passes(builder) -> None:
    part = builder()
    assert part.entity.shape.is_valid
    assert len(part.entity.shape.solids()) == 1
    assert part.entity.shape.volume > 0
    assert part.passed, [check for check in part.checks if not check.passed]


def test_flange_volume_changes_parametrically_without_new_operator_types() -> None:
    a = build_flange(outer_radius=34, thickness=8)
    b = build_flange(outer_radius=41, thickness=11)
    assert b.entity.shape.volume > a.entity.shape.volume
    assert set(a.program.operator_histogram()) == set(b.program.operator_histogram())
    assert {
        name for name, count in a.program.operator_histogram().items() if count
    } == {
        name for name, count in b.program.operator_histogram().items() if count
    }


def test_stepped_shaft_matches_closed_form_volume() -> None:
    lengths = (17.0, 29.0, 13.0)
    radii = (8.0, 14.0, 7.0)
    bore = 2.5
    part = build_stepped_shaft(lengths=lengths, radii=radii, bore_radius=bore)
    expected = math.pi * sum(
        length * (radius**2 - bore**2)
        for length, radius in zip(lengths, radii)
    )
    assert part.entity.shape.volume == pytest.approx(expected, abs=1e-5)


def test_lattice_holds_volume_under_parameter_change() -> None:
    part = build_lattice_panel(size=90, bar_width=4, thickness=3, count=7)
    expected_area = 2 * 7 * 90 * 4 - 7**2 * 4**2
    assert part.entity.shape.volume == pytest.approx(expected_area * 3, abs=1e-5)


def test_drawing_is_brep_derived_fitted_and_hatched(tmp_path) -> None:
    manifest = export_part_artifacts(build_flange(), tmp_path)

    views = manifest["views"]
    assert [view["name"] for view in views] == ["TOP", "FRONT", "RIGHT", "ISOMETRIC"]
    assert len({round(view["drawing_scale"], 9) for view in views[:3]}) == 1
    for view in views:
        min_x, min_y, max_x, max_y = view["page_box"]
        assert view["bbox"]["width"] <= max_x - min_x
        assert view["bbox"]["height"] <= max_y - min_y

    assert manifest["section"]["face_count"] > 0
    assert manifest["section"]["hatch_segment_count"] > 0
    assert (tmp_path / "flange.step").stat().st_size > 0
    assert (tmp_path / "flange-drawing.svg").stat().st_size > 0
    assert (tmp_path / "flange-drawing.dxf").stat().st_size > 0
