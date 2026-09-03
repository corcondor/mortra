from __future__ import annotations

import hashlib
import json
import math
import sys
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Callable, Sequence

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from math_os_prototype.spatial_visual_basis import (  # noqa: E402
    Camera,
    PALETTES,
    SpatialBuilder,
    SpatialFigure,
    SpatialPalette,
    edge_length_signature,
    face_normal,
    new_morphism_count,
    normalize,
    project_points,
    rotate_figure,
    semantic_hash,
)


OUTPUT_DIR = ROOT / "brand" / "studies" / "spatial-rotation-20260904"
SEED = 20260904
IMAGE_SIZE = 1024


@dataclass(frozen=True)
class StudySpec:
    study_id: str
    title: str
    family: str
    palette: str
    camera: Camera
    hatch: bool = False
    show_guides: bool = True
    line_only: bool = False


def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    names = ("segoeuib.ttf", "arialbd.ttf") if bold else ("segoeui.ttf", "arial.ttf")
    for name in names:
        path = Path("C:/Windows/Fonts") / name
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def _rgb(value: str) -> np.ndarray:
    value = value.removeprefix("#")
    return np.asarray([int(value[index : index + 2], 16) for index in (0, 2, 4)], dtype=np.float64)


def _rgba(value: str, alpha: int) -> tuple[int, int, int, int]:
    rgb = _rgb(value).astype(np.uint8)
    return int(rgb[0]), int(rgb[1]), int(rgb[2]), alpha


def _mix(first: str, second: str, amount: float) -> tuple[int, int, int, int]:
    value = _rgb(first) * amount + _rgb(second) * (1.0 - amount)
    return int(value[0]), int(value[1]), int(value[2]), 255


def _paper(size: int, palette: SpatialPalette, rng: np.random.Generator) -> Image.Image:
    base = np.broadcast_to(_rgb(palette.paper), (size, size, 3)).copy()
    coarse = rng.normal(0.0, 1.0, (max(8, size // 28), max(8, size // 28))).astype(np.float32)
    coarse_image = Image.fromarray(np.uint8(np.clip(128 + 42 * coarse, 0, 255)))
    coarse_image = coarse_image.resize((size, size), Image.Resampling.BICUBIC).filter(ImageFilter.GaussianBlur(size / 210))
    broad = np.asarray(coarse_image, dtype=np.float64) - 128.0
    grain = rng.normal(0.0, 0.9, (size, size))
    fibers = np.zeros((size, size), dtype=np.float64)
    for _ in range(max(18, size // 24)):
        y = int(rng.integers(0, size))
        fibers[max(0, y - 1) : min(size, y + 2)] += float(rng.uniform(-1.0, 1.0))
    texture = 0.055 * broad + grain + fibers
    return Image.fromarray(np.uint8(np.clip(base + texture[..., None], 0, 255))).convert("RGBA")


def _record_point(
    builder: SpatialBuilder,
    point_id: str,
    value: tuple[float, float, float],
    *,
    inputs: Sequence[str] = (),
    node: bool = False,
) -> None:
    builder.point(point_id, value, inputs=inputs, node=node)


def _connect_face_edges(builder: SpatialBuilder, prefix: str, vertex_ids: Sequence[str], role: str = "result") -> None:
    for index, start in enumerate(vertex_ids):
        builder.edge(f"{prefix}.e{index}", start, vertex_ids[(index + 1) % len(vertex_ids)], role)


def _add_octahedron(
    builder: SpatialBuilder,
    prefix: str,
    center: tuple[float, float, float],
    scale: float,
    axis: tuple[float, float, float],
    angle: float,
    pigment_offset: int,
) -> None:
    local = {
        "xp": (scale, 0.0, 0.0),
        "xm": (-scale, 0.0, 0.0),
        "yp": (0.0, scale, 0.0),
        "ym": (0.0, -scale, 0.0),
        "zp": (0.0, 0.0, scale),
        "zm": (0.0, 0.0, -scale),
    }
    for name, point in local.items():
        seed_id = f"{prefix}.seed.{name}"
        _record_point(builder, seed_id, point)
        builder.rotated_point(
            f"{prefix}.{name}",
            seed_id,
            axis=axis,
            angle=angle,
            translation=center,
        )
    faces = []
    for x_name in ("xp", "xm"):
        for y_name in ("yp", "ym"):
            for z_name in ("zp", "zm"):
                faces.append((x_name, y_name, z_name))
    for index, face in enumerate(faces):
        ids = tuple(f"{prefix}.{name}" for name in face)
        builder.face(f"{prefix}.f{index}", ids, pigment_offset + index)
        _connect_face_edges(builder, f"{prefix}.f{index}", ids)


def _add_tetrahedron(
    builder: SpatialBuilder,
    prefix: str,
    center: tuple[float, float, float],
    scale: float,
    axis: tuple[float, float, float],
    angle: float,
    pigment_offset: int,
    *,
    include_faces: bool = True,
    edge_role: str = "result",
) -> None:
    raw = (
        (1.0, 1.0, 1.0),
        (1.0, -1.0, -1.0),
        (-1.0, 1.0, -1.0),
        (-1.0, -1.0, 1.0),
    )
    for index, point in enumerate(raw):
        unit = tuple(scale * coordinate / math.sqrt(3.0) for coordinate in point)
        seed_id = f"{prefix}.seed.v{index}"
        _record_point(builder, seed_id, unit)
        builder.rotated_point(
            f"{prefix}.v{index}",
            seed_id,
            axis=axis,
            angle=angle,
            translation=center,
        )
    faces = ((0, 1, 2), (0, 3, 1), (0, 2, 3), (1, 3, 2))
    for index, face in enumerate(faces):
        ids = tuple(f"{prefix}.v{item}" for item in face)
        if include_faces:
            builder.face(f"{prefix}.f{index}", ids, pigment_offset + index)
        _connect_face_edges(builder, f"{prefix}.f{index}", ids, edge_role)


def build_monogram_construction() -> SpatialFigure:
    builder = SpatialBuilder("spatial-01", "constructed_monogram", {"grid": [8, 8], "circle_orders": [12, 24]})
    for x in range(-4, 5):
        a = f"grid.x{x}.a"
        b = f"grid.x{x}.b"
        _record_point(builder, a, (x * 0.42, -2.15, -0.03))
        _record_point(builder, b, (x * 0.42, 2.15, -0.03))
        builder.edge(f"grid.x{x}", a, b, "guide")
    for y in range(-5, 6):
        a = f"grid.y{y}.a"
        b = f"grid.y{y}.b"
        _record_point(builder, a, (-2.05, y * 0.42, -0.03))
        _record_point(builder, b, (2.05, y * 0.42, -0.03))
        builder.edge(f"grid.y{y}", a, b, "guide")
    for radius_index, radius in enumerate((0.82, 1.65, 2.05)):
        ids = []
        for index in range(48):
            angle = 2.0 * math.pi * index / 48
            point_id = f"circle{radius_index}.p{index}"
            _record_point(builder, point_id, (radius * math.cos(angle), radius * math.sin(angle), 0.0))
            ids.append(point_id)
        for index in range(48):
            builder.edge(f"circle{radius_index}.e{index}", ids[index], ids[(index + 1) % 48], "guide")
    ribbons = (
        ((-1.70, -1.60), (-1.70, 1.55), (-1.12, 1.55), (0.0, -0.12), (0.0, -1.18), (-1.12, 0.38), (-1.12, -1.60)),
        ((1.70, -1.60), (1.70, 1.55), (1.12, 1.55), (0.0, -0.12), (0.0, -1.18), (1.12, 0.38), (1.12, -1.60)),
    )
    for ribbon_index, polygon in enumerate(ribbons):
        ids = []
        for index, (x, y) in enumerate(polygon):
            point_id = f"ribbon{ribbon_index}.p{index}"
            _record_point(builder, point_id, (x, y, 0.08))
            ids.append(point_id)
        builder.face(f"ribbon{ribbon_index}.face", ids, ribbon_index)
        _connect_face_edges(builder, f"ribbon{ribbon_index}", ids)
    return builder.build()


def build_polyhedral_orbit() -> SpatialFigure:
    order = 8
    builder = SpatialBuilder("spatial-02", "polyhedral_orbit", {"order": order, "solid": "octahedron"})
    for index in range(order):
        angle = 2.0 * math.pi * index / order
        center = (3.35 * math.cos(angle), 3.35 * math.sin(angle), 1.12 * math.sin(3.0 * angle))
        axis = normalize((math.cos(angle), math.sin(angle), 0.92))
        _add_octahedron(builder, f"o{index}", center, 0.70, tuple(axis), angle * 0.71, index)
    return builder.build()


def build_recursive_tetra_crown() -> SpatialFigure:
    builder = SpatialBuilder(
        "spatial-03",
        "recursive_tetra_crown",
        {"levels": 3, "branching": 4, "scale_ratio": 0.46},
    )
    root_axis = tuple(normalize((1.0, 0.7, 0.35)))
    root_angle = 0.31
    root_scale = 2.34
    _add_tetrahedron(
        builder,
        "root",
        (0.0, 0.0, 0.0),
        root_scale,
        root_axis,
        root_angle,
        0,
        include_faces=False,
        edge_role="secondary",
    )
    root_vertices = [np.asarray(builder.points[f"root.v{index}"], dtype=np.float64) for index in range(4)]
    pigment = 0
    for branch, direction in enumerate(root_vertices):
        outward = normalize(direction)
        for level, (distance, scale) in enumerate(((0.78, 0.90), (1.18, 0.55), (1.48, 0.32))):
            center_vector = distance * direction
            center = tuple(center_vector.tolist())
            axis = tuple(normalize(outward + np.asarray((0.22, -0.16, 0.28))))
            _add_tetrahedron(
                builder,
                f"b{branch}.l{level}",
                center,
                scale,
                axis,
                root_angle + branch * math.pi / 5.0 + level * math.pi / 7.0,
                pigment,
                edge_role="result" if level < 2 else "secondary",
            )
            pigment += 1
    return builder.build()


def build_geodesic_dome() -> SpatialFigure:
    longitude_count = 20
    latitude_count = 7
    radius = 3.4
    builder = SpatialBuilder(
        "spatial-04", "geodesic_dome", {"longitudes": longitude_count, "latitudes": latitude_count, "radius": radius}
    )
    _record_point(builder, "top", (0.0, 0.0, radius), node=True)
    rings: list[list[str]] = []
    for latitude in range(1, latitude_count + 1):
        theta = 0.5 * math.pi * latitude / latitude_count
        seed_id = f"ring{latitude}.p0"
        seed = (radius * math.sin(theta), 0.0, radius * math.cos(theta))
        _record_point(builder, seed_id, seed)
        ring = [seed_id]
        for longitude in range(1, longitude_count):
            point_id = f"ring{latitude}.p{longitude}"
            builder.rotated_point(point_id, seed_id, axis=(0.0, 0.0, 1.0), angle=2.0 * math.pi * longitude / longitude_count)
            ring.append(point_id)
        rings.append(ring)
    for longitude in range(longitude_count):
        ids = ("top", rings[0][longitude], rings[0][(longitude + 1) % longitude_count])
        builder.face(f"cap.f{longitude}", ids, longitude)
        _connect_face_edges(builder, f"cap.f{longitude}", ids)
    for latitude in range(latitude_count - 1):
        inner = rings[latitude]
        outer = rings[latitude + 1]
        for longitude in range(longitude_count):
            ids = (
                inner[longitude],
                outer[longitude],
                outer[(longitude + 1) % longitude_count],
                inner[(longitude + 1) % longitude_count],
            )
            builder.face(f"band{latitude}.f{longitude}", ids, latitude + longitude)
            _connect_face_edges(builder, f"band{latitude}.f{longitude}", ids)
            if (latitude + longitude) % 2 == 0:
                builder.edge(f"diag{latitude}.{longitude}", inner[longitude], outer[(longitude + 1) % longitude_count], "guide")
    return builder.build()


def build_stellated_layers() -> SpatialFigure:
    builder = SpatialBuilder("spatial-05", "stellated_layers", {"layers": 4, "order": 9})
    order = 18
    rings: list[list[str]] = []
    for layer, (scale, phase, z) in enumerate(((3.05, 0.0, -0.52), (2.45, 0.23, -0.05), (1.82, -0.17, 0.46), (1.12, 0.31, 0.92))):
        ring = []
        for index in range(order):
            radius = scale if index % 2 == 0 else scale * 0.39
            angle = 2.0 * math.pi * index / order + phase
            point_id = f"l{layer}.p{index}"
            _record_point(builder, point_id, (radius * math.cos(angle), radius * math.sin(angle), z))
            ring.append(point_id)
        rings.append(ring)
        builder.face(f"l{layer}.face", ring, layer)
        _connect_face_edges(builder, f"l{layer}", ring)
    for layer in range(len(rings) - 1):
        for index in range(order):
            builder.edge(f"bridge{layer}.{index}", rings[layer][index], rings[layer + 1][(index + 3) % order], "result")
    return builder.build()


def _hex_coordinates(radius: int) -> list[tuple[int, int]]:
    values = []
    for q in range(-radius, radius + 1):
        for r in range(-radius, radius + 1):
            if max(abs(q), abs(r), abs(q + r)) <= radius:
                values.append((q, r))
    return values


def build_hex_substitution() -> SpatialFigure:
    coordinates = [item for item in _hex_coordinates(2) if (2 * item[0] + item[1]) % 4 != 1]
    builder = SpatialBuilder("spatial-06", "hexagonal_substitution", {"radius": 2, "cells": len(coordinates)})
    for cell_index, (q, r) in enumerate(coordinates):
        center_x = 1.08 * math.sqrt(3.0) * (q + r / 2.0)
        center_y = 1.62 * r
        height = 0.18 + 0.24 * ((q - r) % 3)
        top_ids = []
        bottom_ids = []
        for index in range(6):
            angle = math.pi / 6.0 + index * math.pi / 3.0
            dx, dy = 0.88 * math.cos(angle), 0.88 * math.sin(angle)
            top = f"c{cell_index}.t{index}"
            bottom = f"c{cell_index}.b{index}"
            _record_point(builder, top, (center_x + dx, center_y + dy, height))
            _record_point(builder, bottom, (center_x + dx, center_y + dy, -0.10))
            top_ids.append(top)
            bottom_ids.append(bottom)
        builder.face(f"c{cell_index}.top", top_ids, cell_index)
        _connect_face_edges(builder, f"c{cell_index}.top", top_ids)
        for index in range(6):
            ids = (top_ids[index], top_ids[(index + 1) % 6], bottom_ids[(index + 1) % 6], bottom_ids[index])
            builder.face(f"c{cell_index}.side{index}", ids, cell_index + index + 1)
            _connect_face_edges(builder, f"c{cell_index}.side{index}", ids)
    return builder.build()


def build_spiral_graph() -> SpatialFigure:
    count = 88
    builder = SpatialBuilder("spatial-07", "spatial_graph_orbit", {"nodes": count, "strides": [1, 13, 21]})
    ids = []
    for index in range(count):
        angle = index * 0.46
        radius = 0.28 + 0.035 * index
        point_id = f"n{index}"
        _record_point(
            builder,
            point_id,
            (radius * math.cos(angle), radius * math.sin(angle), 0.82 * math.sin(index * 0.19)),
            node=True,
        )
        ids.append(point_id)
    for stride, role in ((1, "result"), (13, "secondary"), (21, "guide")):
        for index in range(count - stride):
            if stride > 1 and index % 2:
                continue
            builder.edge(f"s{stride}.e{index}", ids[index], ids[index + stride], role)
    return builder.build()


def build_twisted_tunnel() -> SpatialFigure:
    sections = 18
    sides = 12
    builder = SpatialBuilder("spatial-08", "twisted_tunnel", {"sections": sections, "sides": sides, "twist_turns": 1.5})
    rings: list[list[str]] = []
    for section in range(sections):
        t = section / (sections - 1)
        x = -3.6 + 7.2 * t
        center_y = 0.44 * math.sin(2.0 * math.pi * t)
        center_z = 0.35 * math.cos(math.pi * t) - 0.18
        twist = 3.0 * math.pi * t
        ring = []
        for side in range(sides):
            angle = 2.0 * math.pi * side / sides + twist
            ry = 1.35 * (0.82 + 0.18 * math.cos(math.pi * t))
            rz = 1.72 * (0.90 + 0.10 * math.sin(2.0 * math.pi * t))
            point_id = f"r{section}.p{side}"
            _record_point(builder, point_id, (x, center_y + ry * math.cos(angle), center_z + rz * math.sin(angle)))
            ring.append(point_id)
        rings.append(ring)
    for section in range(sections - 1):
        for side in range(sides):
            ids = (
                rings[section][side],
                rings[section + 1][side],
                rings[section + 1][(side + 1) % sides],
                rings[section][(side + 1) % sides],
            )
            builder.face(f"b{section}.f{side}", ids, section + side)
            _connect_face_edges(builder, f"b{section}.f{side}", ids, "result" if side % 3 == 0 else "secondary")
    return builder.build()


def build_torus_knot_mesh() -> SpatialFigure:
    sections = 30
    sides = 7
    builder = SpatialBuilder("spatial-09", "torus_knot_mesh", {"sections": sections, "sides": sides, "winding": [2, 3]})
    rings: list[list[str]] = []
    for section in range(sections):
        t = 2.0 * math.pi * section / sections
        center = np.asarray(
            [
                (2.65 + 0.62 * math.cos(3.0 * t)) * math.cos(2.0 * t),
                (2.65 + 0.62 * math.cos(3.0 * t)) * math.sin(2.0 * t),
                0.62 * math.sin(3.0 * t),
            ],
            dtype=np.float64,
        )
        tangent = normalize(
            (
                -2.0 * (2.65 + 0.62 * math.cos(3.0 * t)) * math.sin(2.0 * t) - 1.86 * math.sin(3.0 * t) * math.cos(2.0 * t),
                2.0 * (2.65 + 0.62 * math.cos(3.0 * t)) * math.cos(2.0 * t) - 1.86 * math.sin(3.0 * t) * math.sin(2.0 * t),
                1.86 * math.cos(3.0 * t),
            )
        )
        radial = normalize((math.cos(2.0 * t), math.sin(2.0 * t), 0.0))
        binormal = normalize(np.cross(tangent, radial))
        ring = []
        for side in range(sides):
            angle = 2.0 * math.pi * side / sides + 0.5 * t
            point = center + 0.34 * (math.cos(angle) * radial + math.sin(angle) * binormal)
            point_id = f"r{section}.p{side}"
            _record_point(builder, point_id, tuple(point.tolist()))
            ring.append(point_id)
        rings.append(ring)
    for section in range(sections):
        following = (section + 1) % sections
        for side in range(sides):
            ids = (
                rings[section][side],
                rings[following][side],
                rings[following][(side + 1) % sides],
                rings[section][(side + 1) % sides],
            )
            builder.face(f"f{section}.{side}", ids, section + side)
            _connect_face_edges(builder, f"f{section}.{side}", ids, "secondary" if side % 2 else "result")
    return builder.build()


BUILDERS: dict[str, Callable[[], SpatialFigure]] = {
    "constructed_monogram": build_monogram_construction,
    "polyhedral_orbit": build_polyhedral_orbit,
    "recursive_tetra_crown": build_recursive_tetra_crown,
    "geodesic_dome": build_geodesic_dome,
    "stellated_layers": build_stellated_layers,
    "hexagonal_substitution": build_hex_substitution,
    "spatial_graph_orbit": build_spiral_graph,
    "twisted_tunnel": build_twisted_tunnel,
    "torus_knot_mesh": build_torus_knot_mesh,
}


STUDIES = (
    StudySpec("01", "Constructed M", "constructed_monogram", "graphite-rose", Camera(0, 90, 0, 9, 1.8, "orthographic"), True),
    StudySpec("02", "Polyhedral orbit", "polyhedral_orbit", "graphite-rose", Camera(34, 39, -3, 11.5, 2.1), True),
    StudySpec("03", "Recursive tetra crown", "recursive_tetra_crown", "blush-cobalt", Camera(100, 20, 2, 11.0, 2.0), True),
    StudySpec("04", "Cobalt geodesic dome", "geodesic_dome", "cobalt-paper", Camera(35, 18, 0, 10.5, 2.0), False),
    StudySpec("05", "Blush stellation", "stellated_layers", "mint-rose", Camera(48, 44, 8, 9.0, 1.8), True),
    StudySpec("06", "Hexagonal substitution", "hexagonal_substitution", "saffron-ink", Camera(48, 36, -3, 11.5, 2.0), True),
    StudySpec("07", "Spatial graph orbit", "spatial_graph_orbit", "mineral-night", Camera(30, 32, -8, 9.0, 1.9), False, True, True),
    StudySpec("08", "Twisted blue tunnel", "twisted_tunnel", "cobalt-paper", Camera(42, 16, -8, 10.5, 2.0), False),
    StudySpec("09", "Torus knot skin", "torus_knot_mesh", "blush-cobalt", Camera(136, 25, 5, 10.0, 1.9), True),
)


def _screen_transform(projected: dict[str, object], size: int, padding: float = 0.075):
    xs = [point.x for point in projected.values()]
    ys = [point.y for point in projected.values()]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    scale = min(
        size * (1.0 - 2.0 * padding) / max(max_x - min_x, 1e-9),
        size * (1.0 - 2.0 * padding) / max(max_y - min_y, 1e-9),
    )
    center_x = (min_x + max_x) / 2.0
    center_y = (min_y + max_y) / 2.0

    def transform(point_id: str) -> tuple[float, float]:
        point = projected[point_id]
        return size / 2.0 + scale * (point.x - center_x), size / 2.0 - scale * (point.y - center_y)

    return transform


def _jittered_polygon(
    points: Sequence[tuple[float, float]],
    rng: np.random.Generator,
    amount: float,
) -> list[tuple[float, float]]:
    return [
        (x + float(rng.normal(0.0, amount)), y + float(rng.normal(0.0, amount)))
        for x, y in points
    ]


def _hatch_face(
    canvas: Image.Image,
    polygon: Sequence[tuple[float, float]],
    color: str,
    alpha: int,
    slope: float,
    spacing: int,
) -> None:
    size = canvas.width
    mask = Image.new("L", canvas.size, 0)
    ImageDraw.Draw(mask).polygon(polygon, fill=255)
    lines = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(lines)
    for offset in range(-size, 2 * size, spacing):
        draw.line((0, offset, size, offset + slope * size), fill=_rgba(color, alpha), width=1)
    clipped_alpha = ImageChops.multiply(lines.getchannel("A"), mask)
    lines.putalpha(clipped_alpha)
    canvas.alpha_composite(lines)


def render_spatial_figure(
    figure: SpatialFigure,
    spec: StudySpec,
    *,
    size: int = IMAGE_SIZE,
    seed_offset: int = 0,
) -> Image.Image:
    palette = PALETTES[spec.palette]
    rng = np.random.default_rng(SEED + int(spec.study_id) * 7919 + seed_offset)
    canvas = _paper(size, palette, rng)
    projected = project_points(figure, spec.camera)
    screen = _screen_transform(projected, size)
    eye_direction = camera_direction(spec.camera)
    light = normalize((-0.55, -0.35, 0.76))

    if spec.show_guides:
        guides = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        guide_draw = ImageDraw.Draw(guides)
        center = size / 2.0
        for radius in (0.16, 0.28, 0.40):
            value = size * radius
            guide_draw.ellipse((center - value, center - value, center + value, center + value), outline=_rgba(palette.guide, 32), width=1)
        guide_draw.line((size * 0.08, center, size * 0.92, center), fill=_rgba(palette.guide, 28), width=1)
        guide_draw.line((center, size * 0.08, center, size * 0.92), fill=_rgba(palette.guide, 28), width=1)
        canvas.alpha_composite(guides)

    faces = sorted(
        figure.faces,
        key=lambda face: sum(projected[item].depth for item in face.vertex_ids) / len(face.vertex_ids),
        reverse=True,
    )
    if not spec.line_only:
        for face_index, face in enumerate(faces):
            polygon = [screen(item) for item in face.vertex_ids]
            normal = face_normal(figure, face)
            diffuse = abs(float(np.dot(normal, light)))
            facing = abs(float(np.dot(normal, eye_direction)))
            tone = min(1.0, 0.08 + 0.70 * diffuse + 0.22 * (1.0 - facing))
            pigment = palette.pigments[face.pigment_index % len(palette.pigments)]
            fill = _mix(pigment, palette.paper, 0.42 + 0.50 * tone)
            layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(layer)
            for pass_index, alpha in enumerate((46, 64, 86)):
                draw.polygon(
                    _jittered_polygon(polygon, rng, 0.42 + 0.30 * pass_index),
                    fill=(fill[0], fill[1], fill[2], int(alpha * (0.65 + 0.55 * tone))),
                )
            bleed = layer.filter(ImageFilter.GaussianBlur(1.15))
            canvas.alpha_composite(bleed)
            canvas.alpha_composite(layer)
            if spec.hatch and face_index % 4 == 0:
                _hatch_face(canvas, polygon, palette.ink, 38, 0.42 + 0.16 * (face_index % 3), 12 + face_index % 5)

    edge_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    edge_draw = ImageDraw.Draw(edge_layer)
    depths = [point.depth for point in projected.values()]
    depth_min, depth_max = min(depths), max(depths)
    for edge in figure.edges:
        first = screen(edge.start_id)
        second = screen(edge.end_id)
        relative_depth = (
            (projected[edge.start_id].depth + projected[edge.end_id].depth) / 2.0 - depth_min
        ) / max(depth_max - depth_min, 1e-9)
        if edge.role == "guide":
            color, alpha, width = palette.guide, 44, 1
        elif edge.role == "secondary":
            color = palette.pigments[0] if spec.line_only else palette.ink
            alpha, width = int(96 + 62 * (1.0 - relative_depth)), 1
        else:
            color = palette.pigments[1] if spec.line_only else palette.ink
            alpha, width = int(158 + 84 * (1.0 - relative_depth)), 2
        edge_draw.line((first, second), fill=_rgba(color, alpha), width=width)
        if edge.role == "result":
            jitter = float(rng.normal(0.0, 0.34))
            edge_draw.line(
                ((first[0] + jitter, first[1] - jitter), (second[0] + jitter, second[1] - jitter)),
                fill=_rgba(color, max(20, alpha // 3)),
                width=1,
            )
    canvas.alpha_composite(edge_layer)

    if figure.node_ids:
        nodes = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        node_draw = ImageDraw.Draw(nodes)
        for index, point_id in enumerate(figure.node_ids):
            x, y = screen(point_id)
            radius = 1.5 + 2.6 * (1.0 - (projected[point_id].depth - depth_min) / max(depth_max - depth_min, 1e-9))
            color = palette.accent if index % 7 == 0 else palette.ink
            node_draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=_rgba(color, 190))
        canvas.alpha_composite(nodes)

    return canvas.convert("RGB")


def camera_direction(camera: Camera) -> np.ndarray:
    azimuth = math.radians(camera.azimuth_degrees)
    elevation = math.radians(camera.elevation_degrees)
    return normalize(
        (
            math.cos(elevation) * math.cos(azimuth),
            math.cos(elevation) * math.sin(azimuth),
            math.sin(elevation),
        )
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _contact_sheet(records: Sequence[dict[str, object]], output: Path) -> None:
    width = 2048
    margin = 44
    gap = 30
    columns = 3
    tile = (width - 2 * margin - (columns - 1) * gap) // columns
    header = 170
    caption = 78
    rows = math.ceil(len(records) / columns)
    height = header + rows * (tile + caption + gap) + margin
    sheet = Image.new("RGB", (width, height), "#E9E5DF")
    draw = ImageDraw.Draw(sheet)
    draw.text((margin, 36), "MORTRA / SPATIAL COMPOSITION STUDIES", font=_font(42, bold=True), fill="#172A34")
    draw.text(
        (margin, 96),
        "same finite geometry basis / arbitrary-axis rotation / perspective / normal-driven pigment",
        font=_font(23),
        fill="#58707A",
    )
    for index, record in enumerate(records):
        row, column = divmod(index, columns)
        x = margin + column * (tile + gap)
        y = header + row * (tile + caption + gap)
        image = Image.open(record["path"]).convert("RGB").resize((tile, tile), Image.Resampling.LANCZOS)
        sheet.paste(image, (x, y))
        draw.text((x, y + tile + 12), f"{record['study_id']}  {record['title']}", font=_font(22, bold=True), fill="#172A34")
        draw.text(
            (x, y + tile + 43),
            f"{record['point_count']} points / {record['edge_count']} edges / {record['face_count']} faces",
            font=_font(17),
            fill="#64747A",
        )
    sheet.save(output)


def _camera_orbit_strip(figure: SpatialFigure, base_spec: StudySpec, output: Path) -> list[str]:
    views = []
    hashes = []
    for index, azimuth in enumerate((0, 45, 90, 135, 180)):
        camera = replace(base_spec.camera, azimuth_degrees=azimuth, elevation_degrees=26 + 4 * (index % 2))
        spec = replace(base_spec, camera=camera, hatch=False, show_guides=False)
        view = render_spatial_figure(figure, spec, size=480, seed_offset=200 + index)
        views.append((azimuth, view))
        hashes.append(hashlib.sha256(view.tobytes()).hexdigest())
    strip = Image.new("RGB", (5 * 480, 550), "#ECE8E2")
    draw = ImageDraw.Draw(strip)
    for index, (azimuth, view) in enumerate(views):
        strip.paste(view, (480 * index, 0))
        draw.text((480 * index + 18, 500), f"azimuth {azimuth} deg", font=_font(20, bold=True), fill="#243A43")
    strip.save(output)
    return hashes


def _arbitrary_axis_animation(figure: SpatialFigure, base_spec: StudySpec, output: Path) -> list[str]:
    frames: list[Image.Image] = []
    hashes: list[str] = []
    frame_count = 24
    axis = (1.0, 2.0, 3.0)
    for index in range(frame_count):
        angle = 2.0 * math.pi * index / frame_count
        rotated = rotate_figure(figure, axis, angle, f"animation-{index:02d}")
        spec = replace(base_spec, hatch=False, show_guides=False)
        frame = render_spatial_figure(rotated, spec, size=480, seed_offset=410)
        frames.append(frame)
        hashes.append(hashlib.sha256(frame.tobytes()).hexdigest())
    frames[0].save(
        output,
        save_all=True,
        append_images=frames[1:],
        duration=90,
        loop=0,
        disposal=2,
    )
    return hashes


def generate(output_dir: Path = OUTPUT_DIR) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    figures: dict[str, SpatialFigure] = {}
    for spec in STUDIES:
        figure = BUILDERS[spec.family]()
        figures[spec.study_id] = figure
        image = render_spatial_figure(figure, spec)
        path = output_dir / f"mortra-spatial-{spec.study_id}.png"
        image.save(path)
        record = {
            "study_id": spec.study_id,
            "title": spec.title,
            "family": spec.family,
            "palette": spec.palette,
            "camera": asdict(spec.camera),
            "path": str(path),
            "image_sha256": _sha256(path),
            "semantic_sha256": semantic_hash(figure),
            "point_count": len(figure.points),
            "edge_count": len(figure.edges),
            "face_count": len(figure.faces),
            "composition_depth": figure.composition_depth,
            "operations": sorted(figure.operations_used),
            "render_operations": ["Projection"],
            "new_morphism_count": new_morphism_count(figure),
        }
        records.append(record)

    contact_sheet = output_dir / "mortra-spatial-studies-review.png"
    _contact_sheet(records, contact_sheet)
    orbit_strip = output_dir / "camera-orbit-polyhedral-study.png"
    camera_hashes = _camera_orbit_strip(figures["02"], STUDIES[1], orbit_strip)
    animation = output_dir / "arbitrary-axis-polyhedral-orbit.gif"
    animation_hashes = _arbitrary_axis_animation(figures["02"], STUDIES[1], animation)

    rotated = rotate_figure(figures["03"], (1.0, 2.0, 3.0), 0.731, "invariance-audit")
    original_lengths = edge_length_signature(figures["03"])
    rotated_lengths = edge_length_signature(rotated)
    rotation_residual = max(
        (abs(first - second) for first, second in zip(original_lengths, rotated_lengths, strict=True)),
        default=0.0,
    )
    semantic_hashes = [str(record["semantic_sha256"]) for record in records]
    image_hashes = [str(record["image_sha256"]) for record in records]
    checks = {
        "nine_distinct_semantic_families": len(set(semantic_hashes)) == len(records) == 9,
        "nine_distinct_rendered_images": len(set(image_hashes)) == len(records) == 9,
        "zero_new_geometry_morphisms": all(record["new_morphism_count"] == 0 for record in records),
        "arbitrary_axis_rotation_preserves_edge_lengths": rotation_residual <= 1e-9,
        "five_camera_orbit_views_are_distinct": len(set(camera_hashes)) == 5,
        "arbitrary_axis_animation_has_distinct_frames": len(set(animation_hashes)) == len(animation_hashes) == 24,
        "all_spatial_views_contain_geometry": all(
            record["point_count"] >= 12 and record["edge_count"] >= 12 for record in records
        ),
    }
    manifest = {
        "schema": "mortra.spatial-visual-basis.v1",
        "seed": SEED,
        "records": records,
        "camera_orbit": {
            "semantic_sha256": semantic_hash(figures["02"]),
            "view_sha256": camera_hashes,
            "path": str(orbit_strip),
        },
        "arbitrary_axis_animation": {
            "axis": [1.0, 2.0, 3.0],
            "frame_count": len(animation_hashes),
            "frame_sha256": animation_hashes,
            "path": str(animation),
        },
        "rotation_invariance_max_edge_residual": rotation_residual,
        "checks": checks,
        "passed": all(checks.values()),
        "contact_sheet": str(contact_sheet),
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def main() -> int:
    manifest = generate()
    print(
        json.dumps(
            {
                "output": str(OUTPUT_DIR),
                "passed": manifest["passed"],
                "studies": len(manifest["records"]),
                "rotation_residual": manifest["rotation_invariance_max_edge_residual"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if manifest["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
