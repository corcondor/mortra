from __future__ import annotations

from fractions import Fraction

from math_os_prototype.nd_cell_backend import ExactCellExecutor, render_wireframe_svg


def _tesseract() -> tuple[ExactCellExecutor, object]:
    executor = ExactCellExecutor("exact-tesseract")
    cell = executor.point("origin", (0, 0, 0, 0))
    for index in range(4):
        direction = [0, 0, 0, 0]
        direction[index] = 1
        cell = executor.linear_sweep(cell, f"sweep_{index + 1}", direction)
    return executor, cell


def test_four_dimensional_cell_is_executed_not_only_typechecked() -> None:
    executor, cell = _tesseract()
    assert cell.ref.geometric_type.ambient_dimension == 4
    assert cell.ref.geometric_type.intrinsic_dimension == 4
    assert len(cell.vertices) == 16
    assert len(cell.edges) == 32
    assert all(value in {Fraction(0), Fraction(1)} for v in cell.vertices for value in v)
    assert executor.program.operator_histogram()["sweep"] == 4


def test_linear_sweep_scales_to_multiple_ambient_dimensions() -> None:
    for dimension in range(1, 13):
        executor = ExactCellExecutor(f"hypercube-{dimension}d")
        cell = executor.point("origin", (0,) * dimension)
        for index in range(dimension):
            direction = [0] * dimension
            direction[index] = 1
            cell = executor.linear_sweep(cell, f"axis_{index + 1}", direction)
        assert len(cell.vertices) == 2**dimension
        assert len(cell.edges) == dimension * 2 ** (dimension - 1)
        assert cell.ref.geometric_type.intrinsic_dimension == dimension


def test_exact_projection_preserves_rational_coordinates_and_renders(tmp_path) -> None:
    executor, cell = _tesseract()
    drawing = executor.project(
        cell,
        "drawing",
        ((1, 0, "1/2", "1/4"), (0, 1, "1/3", "1/7")),
    )
    assert drawing.ref.geometric_type.ambient_dimension == 2
    assert drawing.ref.geometric_type.intrinsic_dimension == 2
    assert len(drawing.vertices) == 16
    assert len(drawing.edges) == 32
    assert all(isinstance(value, Fraction) for v in drawing.vertices for value in v)
    output = tmp_path / "tesseract.svg"
    render_wireframe_svg(drawing, output, title="Cell(4, R^4) projected to R^2")
    assert output.stat().st_size > 1000


def test_affine_transform_is_exact() -> None:
    executor = ExactCellExecutor("exact-affine")
    point = executor.point("p", ("1/3", "2/5", "7/11"))
    moved = executor.affine_transform(
        point,
        "q",
        ((1, 0, 0), (0, 2, 0), (0, 0, -1)),
        ("1/6", 0, "3/11"),
    )
    assert moved.vertices == ((Fraction(1, 2), Fraction(4, 5), Fraction(-4, 11)),)
