"""Compile short origami fold sequences into MORTRA's existing rotations.

This first executable model deliberately uses a panel tree.  Every fold is
therefore a rotation of one connected subtree about an existing hinge, so the
kinematics are exact without a numerical solver.  Cyclic crease meshes can be
added later by imposing rotation-product closure on the same representation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Iterable

import numpy as np

from math_os_prototype.generative_geometry_basis import ConstructionStep
from math_os_prototype.spatial_visual_basis import (
    SpatialBuilder,
    SpatialFigure,
    normalize,
    rotate_axis_angle,
)


Vec3 = tuple[float, float, float]


@dataclass(frozen=True)
class Panel:
    panel_id: str
    vertex_ids: tuple[str, ...]
    pigment_index: int


@dataclass(frozen=True)
class Hinge:
    hinge_id: str
    parent_panel_id: str
    child_panel_id: str
    parent_edge: tuple[str, str]
    child_edge: tuple[str, str]


@dataclass(frozen=True)
class FoldGene:
    hinge_id: str
    direction: str
    angle_degrees: float

    @property
    def signed_angle_radians(self) -> float:
        sign = 1.0 if self.direction == "V" else -1.0
        return sign * math.radians(self.angle_degrees)

    @property
    def token(self) -> str:
        return f"{self.direction}{round(self.angle_degrees):02d}@{self.hinge_id}"


@dataclass(frozen=True)
class AppliedFold:
    gene: FoldGene
    axis_start: Vec3
    axis_end: Vec3
    moved_panel_ids: tuple[str, ...]
    moved_point_ids: tuple[str, ...]


@dataclass(frozen=True)
class FoldState:
    state_id: str
    points: dict[str, Vec3]
    panels: dict[str, Panel]
    hinges: dict[str, Hinge]
    children: dict[str, tuple[str, ...]]
    applied: tuple[AppliedFold, ...] = ()


@dataclass(frozen=True)
class FoldProgram:
    program_id: str
    title: str
    genes: tuple[FoldGene, ...]

    @property
    def dna(self) -> str:
        return " ".join(gene.token for gene in self.genes)


def _rotate_xy(vector: np.ndarray, angle: float) -> np.ndarray:
    cosine, sine = math.cos(angle), math.sin(angle)
    return np.asarray(
        (cosine * vector[0] - sine * vector[1], sine * vector[0] + cosine * vector[1]),
        dtype=np.float64,
    )


def build_radial_panel_tree(
    *,
    arms: int = 6,
    depth: int = 4,
    root_radius: float = 0.72,
    reach_ratio: float = 0.78,
    taper_ratio: float = 0.78,
    spiral_turn_degrees: float = 8.0,
) -> FoldState:
    if arms < 3 or depth < 1:
        raise ValueError("a radial panel tree needs at least three arms and one level")

    points: dict[str, Vec3] = {}
    panels: dict[str, Panel] = {}
    hinges: dict[str, Hinge] = {}
    child_lists: dict[str, list[str]] = {}

    root_vertices: list[str] = []
    for index in range(arms):
        angle = math.pi / 2.0 + 2.0 * math.pi * index / arms
        point_id = f"root.v{index}"
        points[point_id] = (root_radius * math.cos(angle), root_radius * math.sin(angle), 0.0)
        root_vertices.append(point_id)
    panels["root"] = Panel("root", tuple(root_vertices), 0)
    child_lists["root"] = []

    turn = math.radians(spiral_turn_degrees)
    for arm in range(arms):
        parent_panel_id = "root"
        parent_edge = (root_vertices[arm], root_vertices[(arm + 1) % arms])
        for level in range(depth):
            start = np.asarray(points[parent_edge[0]], dtype=np.float64)
            end = np.asarray(points[parent_edge[1]], dtype=np.float64)
            midpoint = (start + end) / 2.0
            edge = end[:2] - start[:2]
            edge_length = float(np.linalg.norm(edge))
            edge_unit = edge / max(edge_length, 1e-12)
            radial = normalize((midpoint[0], midpoint[1], 0.0))[:2]
            outward = _rotate_xy(radial, turn * (level + 1))
            reach = edge_length * reach_ratio
            far_width = edge_length * taper_ratio
            far_midpoint = midpoint[:2] + reach * outward
            far_first = far_midpoint - 0.5 * far_width * edge_unit
            far_second = far_midpoint + 0.5 * far_width * edge_unit

            panel_id = f"a{arm}.d{level}"
            vertex_ids = tuple(f"{panel_id}.v{index}" for index in range(4))
            points[vertex_ids[0]] = tuple(start.tolist())
            points[vertex_ids[1]] = tuple(end.tolist())
            points[vertex_ids[2]] = (float(far_second[0]), float(far_second[1]), 0.0)
            points[vertex_ids[3]] = (float(far_first[0]), float(far_first[1]), 0.0)
            panels[panel_id] = Panel(panel_id, vertex_ids, arm + 2 * level)
            child_lists.setdefault(parent_panel_id, []).append(panel_id)
            child_lists.setdefault(panel_id, [])

            hinge_id = f"{panel_id}.hinge"
            hinges[hinge_id] = Hinge(
                hinge_id,
                parent_panel_id,
                panel_id,
                parent_edge,
                (vertex_ids[0], vertex_ids[1]),
            )
            parent_panel_id = panel_id
            parent_edge = (vertex_ids[3], vertex_ids[2])

    return FoldState(
        state_id="radial-panel-tree-flat",
        points=points,
        panels=panels,
        hinges=hinges,
        children={key: tuple(value) for key, value in child_lists.items()},
    )


def _panel_subtree(state: FoldState, root_panel_id: str) -> tuple[str, ...]:
    ordered: list[str] = []
    stack = [root_panel_id]
    while stack:
        panel_id = stack.pop()
        ordered.append(panel_id)
        stack.extend(reversed(state.children.get(panel_id, ())))
    return tuple(ordered)


def apply_fold_gene(state: FoldState, gene: FoldGene) -> FoldState:
    if gene.direction not in {"M", "V"}:
        raise ValueError("fold direction must be M or V")
    if not 0.0 < gene.angle_degrees < 180.0:
        raise ValueError("a fold angle must lie strictly between 0 and 180 degrees")
    hinge = state.hinges[gene.hinge_id]
    moved_panels = _panel_subtree(state, hinge.child_panel_id)
    moved_points = tuple(
        dict.fromkeys(
            point_id
            for panel_id in moved_panels
            for point_id in state.panels[panel_id].vertex_ids
        )
    )
    axis_start = np.asarray(state.points[hinge.child_edge[0]], dtype=np.float64)
    axis_end = np.asarray(state.points[hinge.child_edge[1]], dtype=np.float64)
    axis = tuple((axis_end - axis_start).tolist())
    normalize(axis)

    points = dict(state.points)
    for point_id in moved_points:
        relative = tuple((np.asarray(points[point_id], dtype=np.float64) - axis_start).tolist())
        rotated = np.asarray(rotate_axis_angle(relative, axis, gene.signed_angle_radians)) + axis_start
        points[point_id] = tuple(rotated.tolist())

    applied = AppliedFold(
        gene=gene,
        axis_start=tuple(axis_start.tolist()),
        axis_end=tuple(axis_end.tolist()),
        moved_panel_ids=moved_panels,
        moved_point_ids=moved_points,
    )
    return replace(
        state,
        state_id=f"{state.state_id}-{len(state.applied) + 1:02d}",
        points=points,
        applied=(*state.applied, applied),
    )


def execute_fold_program(initial: FoldState, program: FoldProgram) -> tuple[FoldState, ...]:
    states = [initial]
    current = initial
    for gene in program.genes:
        current = apply_fold_gene(current, gene)
        states.append(current)
    return tuple(states)


def _pairwise_distances(points: Iterable[Vec3]) -> tuple[float, ...]:
    values = [np.asarray(point, dtype=np.float64) for point in points]
    return tuple(
        float(np.linalg.norm(values[first] - values[second]))
        for first in range(len(values))
        for second in range(first + 1, len(values))
    )


def validate_fold_state(initial: FoldState, state: FoldState) -> dict[str, float | bool]:
    rigidity_residual = 0.0
    planarity_residual = 0.0
    for panel_id, panel in state.panels.items():
        before = _pairwise_distances(initial.points[item] for item in panel.vertex_ids)
        after = _pairwise_distances(state.points[item] for item in panel.vertex_ids)
        rigidity_residual = max(
            rigidity_residual,
            max((abs(first - second) for first, second in zip(before, after, strict=True)), default=0.0),
        )
        if len(panel.vertex_ids) >= 4:
            vertices = [np.asarray(state.points[item], dtype=np.float64) for item in panel.vertex_ids]
            normal = np.cross(vertices[1] - vertices[0], vertices[2] - vertices[0])
            normal_norm = float(np.linalg.norm(normal))
            if normal_norm > 1e-12:
                normal /= normal_norm
                planarity_residual = max(
                    planarity_residual,
                    max(abs(float(np.dot(vertex - vertices[0], normal))) for vertex in vertices[3:]),
                )

    hinge_residual = 0.0
    for hinge in state.hinges.values():
        for parent_id, child_id in zip(hinge.parent_edge, hinge.child_edge, strict=True):
            hinge_residual = max(
                hinge_residual,
                float(
                    np.linalg.norm(
                        np.asarray(state.points[parent_id], dtype=np.float64)
                        - np.asarray(state.points[child_id], dtype=np.float64)
                    )
                ),
            )

    reachable = set(_panel_subtree(state, "root"))
    tree_holds = len(state.hinges) == len(state.panels) - 1 and reachable == set(state.panels)
    return {
        "panel_rigidity_max_residual": rigidity_residual,
        "panel_planarity_max_residual": planarity_residual,
        "hinge_coincidence_max_residual": hinge_residual,
        "hinge_graph_is_tree": tree_holds,
        "passed": (
            rigidity_residual <= 1e-9
            and planarity_residual <= 1e-9
            and hinge_residual <= 1e-9
            and tree_holds
        ),
    }


def state_to_spatial_figure(state: FoldState, figure_id: str, program: FoldProgram | None = None) -> SpatialFigure:
    builder = SpatialBuilder(
        figure_id,
        "origami_fold_dna",
        {
            "panel_count": len(state.panels),
            "hinge_count": len(state.hinges),
            "fold_dna": program.dna if program else "",
            "fold_count": len(state.applied),
        },
    )
    for point_id, point in state.points.items():
        builder.point(point_id, point)
    hinge_child_edges = {hinge.child_edge for hinge in state.hinges.values()}
    for panel in state.panels.values():
        builder.face(f"{panel.panel_id}.face", panel.vertex_ids, panel.pigment_index)
        for index, start_id in enumerate(panel.vertex_ids):
            end_id = panel.vertex_ids[(index + 1) % len(panel.vertex_ids)]
            role = "result" if (start_id, end_id) in hinge_child_edges else "secondary"
            builder.edge(f"{panel.panel_id}.edge{index}", start_id, end_id, role)
    figure = builder.build()

    trace = list(figure.construction_trace)
    base_depth = figure.composition_depth + 1
    for fold_index, applied in enumerate(state.applied):
        for point_id in applied.moved_point_ids:
            trace.append(
                ConstructionStep(
                    operation="Rotate3",
                    inputs=(point_id, applied.gene.hinge_id),
                    outputs=(f"{point_id}.fold{fold_index + 1}",),
                    depth=base_depth + fold_index,
                    parameters={
                        "axis_start": list(applied.axis_start),
                        "axis_end": list(applied.axis_end),
                        "angle_radians": applied.gene.signed_angle_radians,
                        "gene": applied.gene.token,
                    },
                )
            )
    return replace(figure, construction_trace=tuple(trace))


def make_fold_programs(*, arms: int = 6, depth: int = 4) -> tuple[FoldProgram, ...]:
    hinges = [f"a{arm}.d{level}.hinge" for arm in range(arms) for level in range(depth)]

    bloom = tuple(
        FoldGene(
            f"a{arm}.d{level}.hinge",
            "V" if (arm + level) % 2 == 0 else "M",
            24.0 + 11.0 * level,
        )
        for level in reversed(range(depth))
        for arm in range(arms)
    )
    lantern = tuple(
        FoldGene(
            f"a{arm}.d{level}.hinge",
            "M" if level % 2 == 0 else "V",
            32.0 + 8.0 * ((arm + 2 * level) % 4),
        )
        for arm in range(arms)
        for level in range(depth)
    )
    wave = tuple(
        FoldGene(
            hinge_id,
            "V" if index % 3 else "M",
            28.0 + 7.0 * (index % 5),
        )
        for index, hinge_id in enumerate(sorted(hinges, key=lambda item: (int(item[1]), int(item[4]))))
    )
    return (
        FoldProgram("21", "Alternating spiral bloom", bloom),
        FoldProgram("22", "Radial pleat lantern", lantern),
        FoldProgram("23", "Travelling fold canopy", wave),
    )
