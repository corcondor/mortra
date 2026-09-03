"""Deterministic spatial drawing from MORTRA's existing geometry vocabulary.

The families in this module are programs over points, lines, rotations,
midpoints, surfaces, and projections.  Family names are not mathematical
primitives: they only select parameters and composition graphs.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Sequence

import numpy as np

from math_os_prototype.generative_geometry_basis import (
    ConstructionStep,
    LEXICON_CONSTRUCTORS,
    PROOF_CONSTRUCTIONS,
)


Vec3 = tuple[float, float, float]


EXISTING_SPATIAL_OPERATIONS = frozenset(
    {
        "Point3",
        "Line3",
        "Plane3",
        "Surface",
        "Boundary",
        "Rotate3",
        "Projection",
        "midpoint",
        "reflect",
    }
)


def _assert_existing_vocabulary() -> None:
    known = LEXICON_CONSTRUCTORS | PROOF_CONSTRUCTIONS
    missing = EXISTING_SPATIAL_OPERATIONS - known
    if missing:
        raise RuntimeError(f"spatial renderer introduced unknown operations: {sorted(missing)}")


_assert_existing_vocabulary()


@dataclass(frozen=True)
class SpatialEdge:
    edge_id: str
    start_id: str
    end_id: str
    role: str = "result"


@dataclass(frozen=True)
class SpatialFace:
    face_id: str
    vertex_ids: tuple[str, ...]
    pigment_index: int = 0
    role: str = "surface"


@dataclass(frozen=True)
class SpatialFigure:
    figure_id: str
    family: str
    points: dict[str, Vec3]
    edges: tuple[SpatialEdge, ...]
    faces: tuple[SpatialFace, ...]
    construction_trace: tuple[ConstructionStep, ...]
    parameters: dict[str, Any]
    node_ids: tuple[str, ...] = ()

    @property
    def composition_depth(self) -> int:
        return max((step.depth for step in self.construction_trace), default=0)

    @property
    def operations_used(self) -> frozenset[str]:
        return frozenset(step.operation for step in self.construction_trace)

    def semantic_payload(self) -> dict[str, Any]:
        return {
            "figure_id": self.figure_id,
            "family": self.family,
            "points": {
                key: [round(value, 12) for value in point]
                for key, point in sorted(self.points.items())
            },
            "edges": [asdict(edge) for edge in self.edges],
            "faces": [asdict(face) for face in self.faces],
            "trace": [step.to_dict() for step in self.construction_trace],
            "parameters": self.parameters,
            "node_ids": list(self.node_ids),
        }


@dataclass(frozen=True)
class Camera:
    azimuth_degrees: float
    elevation_degrees: float
    roll_degrees: float = 0.0
    distance: float = 9.0
    focal_length: float = 1.8
    projection: str = "perspective"


@dataclass(frozen=True)
class ProjectedPoint:
    x: float
    y: float
    depth: float


@dataclass(frozen=True)
class SpatialPalette:
    paper: str
    pigments: tuple[str, ...]
    ink: str
    guide: str
    accent: str


PALETTES: dict[str, SpatialPalette] = {
    "blush-cobalt": SpatialPalette(
        "#F6F0EF", ("#EDB8C7", "#AFC7E6", "#F2D9A7", "#B8D5C8"), "#253445", "#9EA5B2", "#D65E7B"
    ),
    "graphite-rose": SpatialPalette(
        "#F2EFEB", ("#7C8792", "#B8C1C6", "#E4B3C3", "#D8D0C3"), "#20252B", "#A5A09A", "#B65170"
    ),
    "cobalt-paper": SpatialPalette(
        "#F7F5F0", ("#2E68B2", "#70A4D8", "#C9DDF0", "#E7B4C4"), "#1E3555", "#AAB3BF", "#2F6EB7"
    ),
    "saffron-ink": SpatialPalette(
        "#F4F0E5", ("#E4AB32", "#F1D27A", "#91B6AC", "#D9938B"), "#272922", "#ABA692", "#CA7B22"
    ),
    "mineral-night": SpatialPalette(
        "#091319", ("#285968", "#477F8E", "#B0607E", "#DCA56A"), "#E7E2D8", "#49616C", "#F18D79"
    ),
    "mint-rose": SpatialPalette(
        "#F6F1EB", ("#B9D6CB", "#EAB7C7", "#F0D7A7", "#AFC6D9"), "#31474B", "#A7AAA3", "#CF6178"
    ),
    "spectrum-glass": SpatialPalette(
        "#F7F4EF",
        ("#2E6FAF", "#73C7C4", "#F08EAA", "#F4C65D", "#826CB4", "#DCEAF5"),
        "#18344D",
        "#91A5B2",
        "#F05F91",
    ),
    "prism-coral": SpatialPalette(
        "#F8F2ED",
        ("#E85D75", "#F3A55D", "#F5D36B", "#65B9AF", "#5D8FC7", "#B579BA"),
        "#27384A",
        "#A6A0A2",
        "#E54872",
    ),
    "sapphire-amber": SpatialPalette(
        "#F4F3EF",
        ("#174F8A", "#3C86C6", "#8AC8D4", "#F2B749", "#E67563", "#B9D8EA"),
        "#132D43",
        "#9AA8B2",
        "#F2A43D",
    ),
}


class SpatialBuilder:
    def __init__(self, figure_id: str, family: str, parameters: dict[str, Any]) -> None:
        self.figure_id = figure_id
        self.family = family
        self.parameters = parameters
        self.points: dict[str, Vec3] = {}
        self.edges: list[SpatialEdge] = []
        self.faces: list[SpatialFace] = []
        self.trace: list[ConstructionStep] = []
        self.depths: dict[str, int] = {}
        self.node_ids: list[str] = []
        self._edge_keys: set[tuple[str, str]] = set()

    def _record(
        self,
        operation: str,
        inputs: Sequence[str],
        outputs: Sequence[str],
        parameters: dict[str, Any] | None = None,
    ) -> None:
        if operation not in EXISTING_SPATIAL_OPERATIONS:
            raise ValueError(f"operation is outside the existing spatial basis: {operation}")
        depth = max((self.depths.get(item, -1) for item in inputs), default=-1) + 1
        self.trace.append(
            ConstructionStep(
                operation=operation,
                inputs=tuple(inputs),
                outputs=tuple(outputs),
                depth=depth,
                parameters=parameters or {},
            )
        )
        for output in outputs:
            self.depths[output] = depth

    def point(
        self,
        point_id: str,
        value: Vec3,
        *,
        operation: str = "Point3",
        inputs: Sequence[str] = (),
        parameters: dict[str, Any] | None = None,
        node: bool = False,
    ) -> None:
        if point_id in self.points:
            raise ValueError(f"duplicate point: {point_id}")
        if not all(math.isfinite(coordinate) for coordinate in value):
            raise ValueError("spatial points must be finite")
        self.points[point_id] = value
        self._record(operation, inputs, (point_id,), parameters)
        if node:
            self.node_ids.append(point_id)

    def rotated_point(
        self,
        point_id: str,
        source_id: str,
        *,
        axis: Vec3,
        angle: float,
        center: Vec3 = (0.0, 0.0, 0.0),
        translation: Vec3 = (0.0, 0.0, 0.0),
        scale: float = 1.0,
        node: bool = False,
    ) -> None:
        source = self.points[source_id]
        relative = tuple((source[index] - center[index]) * scale for index in range(3))
        rotated = rotate_axis_angle(relative, axis, angle)
        value = tuple(rotated[index] + center[index] + translation[index] for index in range(3))
        self.point(
            point_id,
            value,
            operation="Rotate3",
            inputs=(source_id,),
            parameters={
                "axis": list(axis),
                "angle": angle,
                "center": list(center),
                "translation": list(translation),
                "scale": scale,
            },
            node=node,
        )

    def midpoint(self, point_id: str, first_id: str, second_id: str, *, node: bool = False) -> None:
        first = np.asarray(self.points[first_id], dtype=np.float64)
        second = np.asarray(self.points[second_id], dtype=np.float64)
        value = tuple(((first + second) / 2.0).tolist())
        self.point(point_id, value, operation="midpoint", inputs=(first_id, second_id), node=node)

    def reflected_point(
        self,
        point_id: str,
        source_id: str,
        *,
        plane_point: Vec3 = (0.0, 0.0, 0.0),
        plane_normal: Vec3 = (0.0, 1.0, 0.0),
        node: bool = False,
    ) -> None:
        """Reflect a point in a plane using MORTRA's existing ``reflect`` construction."""

        source = np.asarray(self.points[source_id], dtype=np.float64)
        origin = np.asarray(plane_point, dtype=np.float64)
        normal = normalize(plane_normal)
        reflected = source - 2.0 * float(np.dot(source - origin, normal)) * normal
        self.point(
            point_id,
            tuple(reflected.tolist()),
            operation="reflect",
            inputs=(source_id,),
            parameters={"plane_point": list(plane_point), "plane_normal": list(plane_normal)},
            node=node,
        )

    def edge(self, edge_id: str, start_id: str, end_id: str, role: str = "result") -> None:
        if start_id == end_id:
            return
        key = tuple(sorted((start_id, end_id)))
        if key in self._edge_keys:
            return
        self._edge_keys.add(key)
        self.edges.append(SpatialEdge(edge_id, start_id, end_id, role))
        self._record("Line3", (start_id, end_id), (edge_id,))

    def face(
        self,
        face_id: str,
        vertex_ids: Sequence[str],
        pigment_index: int,
        role: str = "surface",
    ) -> None:
        if len(vertex_ids) < 3:
            raise ValueError("a face needs at least three vertices")
        plane_id = f"{face_id}.plane"
        self._record("Plane3", tuple(vertex_ids[:3]), (plane_id,))
        self._record("Boundary", (plane_id, *vertex_ids), (face_id,))
        self.faces.append(SpatialFace(face_id, tuple(vertex_ids), pigment_index, role))

    def build(self) -> SpatialFigure:
        return SpatialFigure(
            figure_id=self.figure_id,
            family=self.family,
            points=dict(self.points),
            edges=tuple(self.edges),
            faces=tuple(self.faces),
            construction_trace=tuple(self.trace),
            parameters=dict(self.parameters),
            node_ids=tuple(self.node_ids),
        )


def semantic_hash(figure: SpatialFigure) -> str:
    payload = json.dumps(figure.semantic_payload(), ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def normalize(vector: Iterable[float]) -> np.ndarray:
    array = np.asarray(tuple(vector), dtype=np.float64)
    norm = float(np.linalg.norm(array))
    if norm <= 1e-12:
        raise ValueError("a direction vector must be nonzero")
    return array / norm


def rotate_axis_angle(point: Vec3, axis: Vec3, angle: float) -> Vec3:
    """Rodrigues rotation, the executable realization of Rotate3."""

    vector = np.asarray(point, dtype=np.float64)
    unit_axis = normalize(axis)
    rotated = (
        vector * math.cos(angle)
        + np.cross(unit_axis, vector) * math.sin(angle)
        + unit_axis * float(np.dot(unit_axis, vector)) * (1.0 - math.cos(angle))
    )
    return tuple(rotated.tolist())


def camera_basis(camera: Camera) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    azimuth = math.radians(camera.azimuth_degrees)
    elevation = math.radians(camera.elevation_degrees)
    eye = camera.distance * np.asarray(
        [
            math.cos(elevation) * math.cos(azimuth),
            math.cos(elevation) * math.sin(azimuth),
            math.sin(elevation),
        ],
        dtype=np.float64,
    )
    forward = normalize(-eye)
    world_up = np.asarray([0.0, 0.0, 1.0], dtype=np.float64)
    if abs(float(np.dot(forward, world_up))) > 0.98:
        world_up = np.asarray([0.0, 1.0, 0.0], dtype=np.float64)
    right = normalize(np.cross(forward, world_up))
    up = normalize(np.cross(right, forward))
    roll = math.radians(camera.roll_degrees)
    rolled_right = math.cos(roll) * right + math.sin(roll) * up
    rolled_up = -math.sin(roll) * right + math.cos(roll) * up
    return eye, rolled_right, rolled_up, forward


def project_points(figure: SpatialFigure, camera: Camera) -> dict[str, ProjectedPoint]:
    eye, right, up, forward = camera_basis(camera)
    result: dict[str, ProjectedPoint] = {}
    for point_id, value in figure.points.items():
        vector = np.asarray(value, dtype=np.float64)
        relative = vector - eye
        depth = float(np.dot(relative, forward))
        if camera.projection == "orthographic":
            x = float(np.dot(vector, right))
            y = float(np.dot(vector, up))
        else:
            if depth <= 1e-6:
                raise ValueError("a point lies behind the perspective camera")
            x = camera.focal_length * float(np.dot(relative, right)) / depth
            y = camera.focal_length * float(np.dot(relative, up)) / depth
        result[point_id] = ProjectedPoint(x, y, depth)
    return result


def face_normal(figure: SpatialFigure, face: SpatialFace) -> np.ndarray:
    first, second, third = (np.asarray(figure.points[item], dtype=np.float64) for item in face.vertex_ids[:3])
    cross = np.cross(second - first, third - first)
    norm = float(np.linalg.norm(cross))
    if norm <= 1e-12:
        return np.asarray([0.0, 0.0, 1.0], dtype=np.float64)
    return cross / norm


def edge_length_signature(figure: SpatialFigure) -> tuple[float, ...]:
    values = []
    for edge in figure.edges:
        first = np.asarray(figure.points[edge.start_id], dtype=np.float64)
        second = np.asarray(figure.points[edge.end_id], dtype=np.float64)
        values.append(round(float(np.linalg.norm(first - second)), 10))
    return tuple(sorted(values))


def rotate_figure(figure: SpatialFigure, axis: Vec3, angle: float, suffix: str) -> SpatialFigure:
    points = {key: rotate_axis_angle(value, axis, angle) for key, value in figure.points.items()}
    trace = list(figure.construction_trace)
    base_depth = figure.composition_depth + 1
    for point_id in sorted(points):
        trace.append(
            ConstructionStep(
                operation="Rotate3",
                inputs=(point_id,),
                outputs=(f"{point_id}.rotated",),
                depth=base_depth,
                parameters={"axis": list(axis), "angle": angle},
            )
        )
    return SpatialFigure(
        figure_id=f"{figure.figure_id}-{suffix}",
        family=figure.family,
        points=points,
        edges=figure.edges,
        faces=figure.faces,
        construction_trace=tuple(trace),
        parameters={**figure.parameters, "global_rotation": {"axis": list(axis), "angle": angle}},
        node_ids=figure.node_ids,
    )


def new_morphism_count(figure: SpatialFigure) -> int:
    return len(figure.operations_used - EXISTING_SPATIAL_OPERATIONS)
