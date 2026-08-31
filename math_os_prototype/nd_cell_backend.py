"""Exact affine-polytopal backend for the dimension-independent geometry IR.

OpenCascade executes smooth boundary representations in three dimensions.  This
backend executes the same typed operations on rational cells in arbitrary finite
dimension.  It is deliberately small: affine transforms, linear sweeps, and
projections are exact; unsupported smooth or Boolean operations are not faked.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from html import escape
from pathlib import Path
from typing import Iterable, Sequence

from .engineering_geometry_ir import BasisOp, ConstructionProgram, EntityRef, GeometricType


Scalar = Fraction
Vector = tuple[Scalar, ...]
EdgeIndex = tuple[int, int]


def _fraction(value: int | float | str | Fraction) -> Fraction:
    if isinstance(value, Fraction):
        return value
    if isinstance(value, float):
        return Fraction(str(value))
    return Fraction(value)


def _vector(values: Iterable[int | float | str | Fraction]) -> Vector:
    return tuple(_fraction(value) for value in values)


def _matrix(
    rows: Sequence[Sequence[int | float | str | Fraction]],
) -> tuple[Vector, ...]:
    matrix = tuple(_vector(row) for row in rows)
    if not matrix or not matrix[0]:
        raise ValueError("matrix must not be empty")
    width = len(matrix[0])
    if any(len(row) != width for row in matrix):
        raise ValueError("matrix rows must have equal length")
    return matrix


def _matvec(matrix: tuple[Vector, ...], vector: Vector) -> Vector:
    if len(matrix[0]) != len(vector):
        raise ValueError("matrix and vector dimensions do not match")
    return tuple(sum(a * b for a, b in zip(row, vector)) for row in matrix)


def _add(left: Vector, right: Vector) -> Vector:
    if len(left) != len(right):
        raise ValueError("vector dimensions do not match")
    return tuple(a + b for a, b in zip(left, right))


@dataclass(frozen=True)
class ExactCell:
    ref: EntityRef
    vertices: tuple[Vector, ...]
    edges: tuple[EdgeIndex, ...]

    def __post_init__(self) -> None:
        ambient = self.ref.geometric_type.ambient_dimension
        if any(len(vertex) != ambient for vertex in self.vertices):
            raise ValueError("vertex ambient dimension does not match its type")
        if any(
            left < 0
            or right < 0
            or left >= len(self.vertices)
            or right >= len(self.vertices)
            or left == right
            for left, right in self.edges
        ):
            raise ValueError("invalid edge index")

    def to_dict(self) -> dict[str, object]:
        return {
            "entity": self.ref.name,
            "geometric_type": {
                "ambient_dimension": self.ref.geometric_type.ambient_dimension,
                "intrinsic_dimension": self.ref.geometric_type.intrinsic_dimension,
                "kind": self.ref.geometric_type.kind,
            },
            "vertices": [[str(value) for value in vertex] for vertex in self.vertices],
            "edges": [list(edge) for edge in self.edges],
        }


class ExactCellExecutor:
    """Execute the affine subset of MORTRA's basis over exact rational numbers."""

    def __init__(self, program_id: str):
        self.program = ConstructionProgram(program_id)

    def point(
        self,
        name: str,
        coordinates: Iterable[int | float | str | Fraction],
    ) -> ExactCell:
        point = _vector(coordinates)
        ref = self.program.declare(
            name, GeometricType(len(point), 0, "point"), role="input"
        )
        return ExactCell(ref, (point,), ())

    def affine_transform(
        self,
        cell: ExactCell,
        name: str,
        matrix: Sequence[Sequence[int | float | str | Fraction]],
        translation: Iterable[int | float | str | Fraction] | None = None,
    ) -> ExactCell:
        exact_matrix = _matrix(matrix)
        ambient = cell.ref.geometric_type.ambient_dimension
        if len(exact_matrix) != ambient or len(exact_matrix[0]) != ambient:
            raise ValueError("affine transform must be square in the ambient dimension")
        offset = (
            _vector(translation)
            if translation is not None
            else tuple(Fraction(0) for _ in range(ambient))
        )
        vertices = tuple(
            _add(_matvec(exact_matrix, vertex), offset) for vertex in cell.vertices
        )
        ref = self.program.apply(
            BasisOp.TRANSFORM,
            [cell.ref],
            name,
            cell.ref.geometric_type,
            matrix=[[str(value) for value in row] for row in exact_matrix],
            translation=[str(value) for value in offset],
            arithmetic="rational_exact",
        )
        return ExactCell(ref, vertices, cell.edges)

    def linear_sweep(
        self,
        cell: ExactCell,
        name: str,
        vector: Iterable[int | float | str | Fraction],
    ) -> ExactCell:
        direction = _vector(vector)
        ambient = cell.ref.geometric_type.ambient_dimension
        if len(direction) != ambient:
            raise ValueError("sweep vector has the wrong ambient dimension")
        if all(value == 0 for value in direction):
            raise ValueError("sweep vector must be nonzero")

        count = len(cell.vertices)
        translated = tuple(_add(vertex, direction) for vertex in cell.vertices)
        vertices = cell.vertices + translated
        edges = set(cell.edges)
        edges.update((left + count, right + count) for left, right in cell.edges)
        edges.update((index, index + count) for index in range(count))
        output_type = GeometricType(
            ambient,
            min(ambient, cell.ref.geometric_type.intrinsic_dimension + 1),
            "polytope",
        )
        ref = self.program.apply(
            BasisOp.SWEEP,
            [cell.ref],
            name,
            output_type,
            path_dimension=1,
            trajectory="line",
            vector=[str(value) for value in direction],
            arithmetic="rational_exact",
        )
        return ExactCell(ref, vertices, tuple(sorted(edges)))

    def project(
        self,
        cell: ExactCell,
        name: str,
        matrix: Sequence[Sequence[int | float | str | Fraction]],
    ) -> ExactCell:
        exact_matrix = _matrix(matrix)
        source_ambient = cell.ref.geometric_type.ambient_dimension
        target_ambient = len(exact_matrix)
        if len(exact_matrix[0]) != source_ambient:
            raise ValueError("projection matrix has the wrong source dimension")
        if target_ambient >= source_ambient:
            raise ValueError("projection must lower the ambient dimension")

        raw_vertices = tuple(_matvec(exact_matrix, vertex) for vertex in cell.vertices)
        vertices: list[Vector] = []
        lookup: dict[Vector, int] = {}
        source_to_target: list[int] = []
        for vertex in raw_vertices:
            if vertex not in lookup:
                lookup[vertex] = len(vertices)
                vertices.append(vertex)
            source_to_target.append(lookup[vertex])
        edges = {
            tuple(sorted((source_to_target[left], source_to_target[right])))
            for left, right in cell.edges
            if source_to_target[left] != source_to_target[right]
        }
        output_type = GeometricType(
            target_ambient,
            min(cell.ref.geometric_type.intrinsic_dimension, target_ambient),
            "polytope_projection",
        )
        ref = self.program.apply(
            BasisOp.PROJECT,
            [cell.ref],
            name,
            output_type,
            matrix=[[str(value) for value in row] for row in exact_matrix],
            arithmetic="rational_exact",
        )
        return ExactCell(ref, tuple(vertices), tuple(sorted(edges)))


def render_wireframe_svg(
    cell: ExactCell,
    path: Path,
    *,
    width: int = 900,
    height: int = 700,
    padding: int = 64,
    title: str = "Exact projected cell",
) -> None:
    if cell.ref.geometric_type.ambient_dimension != 2:
        raise ValueError("SVG rendering requires a two-dimensional projection")
    xs = [float(vertex[0]) for vertex in cell.vertices]
    ys = [float(vertex[1]) for vertex in cell.vertices]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max(max_x - min_x, 1e-12)
    span_y = max(max_y - min_y, 1e-12)
    scale = min((width - 2 * padding) / span_x, (height - 2 * padding) / span_y)

    def point(vertex: Vector) -> tuple[float, float]:
        x = padding + (float(vertex[0]) - min_x) * scale
        y = height - padding - (float(vertex[1]) - min_y) * scale
        return x, y

    lines = []
    for left, right in cell.edges:
        x1, y1 = point(cell.vertices[left])
        x2, y2 = point(cell.vertices[right])
        lines.append(
            f'<line x1="{x1:.3f}" y1="{y1:.3f}" x2="{x2:.3f}" '
            'y2="{y2:.3f}" />'.format(y2=y2)
        )
    circles = []
    for vertex in cell.vertices:
        x, y = point(vertex)
        circles.append(f'<circle cx="{x:.3f}" cy="{y:.3f}" r="3.2" />')
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="#f7f8f6"/>
  <text x="{padding}" y="36" font-family="Arial, sans-serif" font-size="18" fill="#172229">{escape(title)}</text>
  <g stroke="#183845" stroke-width="1.4" fill="none">{''.join(lines)}</g>
  <g fill="#19a7b8">{''.join(circles)}</g>
</svg>
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(svg, encoding="utf-8")
