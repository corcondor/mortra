"""Generate vivid ornaments from two parameterized compositions of existing geometry.

The two programs are deliberately generic:

* an orbit of points plus index maps that decide which points are connected;
* a short word on the triangular lattice, closed under rotations/reflections.

Names such as spiral, rosette, knot, or snowflake never enter the mathematical
vocabulary.  They are only visual readings of programs over MORTRA's existing
Point3, Line3, Plane3, Boundary, Rotate3, midpoint, and reflect operations.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal, Sequence

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from math_os_prototype.spatial_visual_basis import (  # noqa: E402
    Camera,
    SpatialBuilder,
    SpatialFigure,
    new_morphism_count,
    rotate_axis_angle,
    semantic_hash,
)
from scripts.generate_spatial_rotation_studies import (  # noqa: E402
    StudySpec,
    render_spatial_figure,
)


OUTPUT_DIR = ROOT / "brand" / "studies" / "iterated-ornament-20260904"
IMAGE_SIZE = 1200


Connection = tuple[Literal["stride", "affine"], int, int, str]


@dataclass(frozen=True)
class OrbitProgram:
    study_id: str
    title: str
    mode: Literal["closed", "affine", "branching"]
    count: int
    connections: tuple[Connection, ...]
    layers: tuple[tuple[float, float, float], ...] = ()
    angle: float = 0.0
    scale: float = 1.0
    translation: tuple[float, float, float] = (0.0, 0.0, 0.0)
    branch_depth: int = 0
    branch_angles: tuple[float, ...] = ()
    ribbon: bool = False


@dataclass(frozen=True)
class HexWordProgram:
    study_id: str
    title: str
    direction_word: tuple[int, ...]
    scales: tuple[float, ...]
    width: float
    step: float
    reflected_alternation: bool
    lift: float
    phase: float = 0.0

    @property
    def rotational_order(self) -> int:
        return 3 if self.lift > 0.0 or self.reflected_alternation else 6


def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    names = ("segoeuib.ttf", "arialbd.ttf") if bold else ("segoeui.ttf", "arial.ttf")
    for name in names:
        path = Path("C:/Windows/Fonts") / name
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def _connect_polygon(
    builder: SpatialBuilder,
    prefix: str,
    vertex_ids: Sequence[str],
    role: str = "result",
) -> None:
    for index, start in enumerate(vertex_ids):
        builder.edge(f"{prefix}.e{index}", start, vertex_ids[(index + 1) % len(vertex_ids)], role)


def _closed_orbit(builder: SpatialBuilder, program: OrbitProgram) -> list[list[str]]:
    rings: list[list[str]] = []
    for layer_index, (radius, z, phase) in enumerate(program.layers):
        seed = f"l{layer_index}.seed"
        builder.point(seed, (radius, 0.0, z), node=True)
        ring = [seed]
        for index in range(1, program.count):
            point_id = f"l{layer_index}.p{index}"
            builder.rotated_point(
                point_id,
                seed,
                axis=(0.0, 0.0, 1.0),
                angle=phase + 2.0 * math.pi * index / program.count,
                node=True,
            )
            ring.append(point_id)
        rings.append(ring)

    for layer_index, ring in enumerate(rings):
        for kind, first, second, role in program.connections:
            for index, start_id in enumerate(ring):
                target = (index + first) % len(ring) if kind == "stride" else (first * index + second) % len(ring)
                builder.edge(f"l{layer_index}.{kind}.{first}.{second}.{index}", start_id, ring[target], role)

    if program.ribbon and len(rings) >= 2:
        for layer_index in range(len(rings) - 1):
            inner, outer = rings[layer_index], rings[layer_index + 1]
            for index in range(program.count):
                following = (index + 1) % program.count
                ids = (inner[index], outer[index], outer[following], inner[following])
                builder.face(f"ribbon.{layer_index}.{index}", ids, index + 2 * layer_index)
    return rings


def _affine_orbit(builder: SpatialBuilder, program: OrbitProgram) -> list[list[str]]:
    strands: list[list[str]] = []
    starts = program.layers or ((3.35, -0.30, 0.0), (-3.05, 0.30, math.pi))
    for strand_index, (radius, z, phase) in enumerate(starts):
        seed_id = f"s{strand_index}.p0"
        builder.point(seed_id, (radius * math.cos(phase), radius * math.sin(phase), z), node=True)
        strand = [seed_id]
        for index in range(1, program.count):
            point_id = f"s{strand_index}.p{index}"
            builder.rotated_point(
                point_id,
                strand[-1],
                axis=(0.12, -0.08, 1.0),
                angle=program.angle,
                scale=program.scale,
                translation=program.translation,
                node=True,
            )
            strand.append(point_id)
        strands.append(strand)

    for strand_index, strand in enumerate(strands):
        for kind, first, second, role in program.connections:
            for index, start_id in enumerate(strand):
                target = index + first if kind == "stride" else first * index + second
                if 0 <= target < len(strand):
                    builder.edge(f"s{strand_index}.{kind}.{first}.{second}.{index}", start_id, strand[target], role)

    if len(strands) >= 2:
        for index in range(program.count - 1):
            builder.edge(f"bridge.{index}", strands[0][index], strands[1][program.count - 1 - index], "secondary")
            if program.ribbon and index % 2 == 0:
                ids = (
                    strands[0][index],
                    strands[0][index + 1],
                    strands[1][program.count - 2 - index],
                    strands[1][program.count - 1 - index],
                )
                builder.face(f"bridge.face.{index}", ids, index)
    return strands


def _branching_orbit(builder: SpatialBuilder, program: OrbitProgram) -> list[list[str]]:
    back = "tree.back"
    root = "tree.root"
    builder.point(back, (0.0, -3.35, -0.12))
    builder.point(root, (0.0, -2.55, 0.0), node=True)
    builder.edge("tree.trunk", back, root, "result")
    frontier = [(root, back)]
    levels: list[list[str]] = [[root]]
    for depth in range(program.branch_depth):
        next_frontier: list[tuple[str, str]] = []
        level: list[str] = []
        for parent_index, (parent, previous) in enumerate(frontier):
            siblings: list[str] = []
            for child_index, branch_angle in enumerate(program.branch_angles):
                child = f"tree.d{depth}.p{parent_index}.c{child_index}"
                builder.rotated_point(
                    child,
                    previous,
                    center=builder.points[parent],
                    axis=(0.08 * (-1) ** child_index, 0.03, 1.0),
                    angle=math.pi + branch_angle,
                    scale=program.scale,
                    translation=(0.0, 0.0, 0.035 * (-1) ** (depth + child_index)),
                    node=True,
                )
                builder.edge(f"tree.edge.{depth}.{parent_index}.{child_index}", parent, child, "result")
                next_frontier.append((child, parent))
                level.append(child)
                siblings.append(child)
            if len(siblings) >= 2 and depth >= 1:
                ids = (parent, siblings[0], siblings[-1])
                builder.face(f"tree.face.{depth}.{parent_index}", ids, depth + parent_index)
        levels.append(level)
        frontier = next_frontier
    return levels


def build_orbit_program(program: OrbitProgram) -> SpatialFigure:
    builder = SpatialBuilder(
        f"ornament-{program.study_id}",
        "orbit_index_map",
        {"program": asdict(program), "generator": "point orbit + index maps"},
    )
    if program.mode == "closed":
        _closed_orbit(builder, program)
    elif program.mode == "affine":
        _affine_orbit(builder, program)
    else:
        _branching_orbit(builder, program)
    return builder.build()


def _direction_vector(index: int) -> np.ndarray:
    angle = (index % 6) * math.pi / 3.0
    return np.asarray((math.cos(angle), math.sin(angle)), dtype=np.float64)


def _word_segments(program: HexWordProgram) -> list[tuple[np.ndarray, np.ndarray]]:
    point = np.asarray((0.38, 0.0), dtype=np.float64)
    segments: list[tuple[np.ndarray, np.ndarray]] = []
    for direction in program.direction_word:
        following = point + program.step * _direction_vector(direction)
        segments.append((point, following))
        point = following
    return segments


def build_hex_word_program(program: HexWordProgram) -> SpatialFigure:
    builder = SpatialBuilder(
        f"ornament-{program.study_id}",
        "triangular_lattice_word",
        {"program": asdict(program), "generator": "direction word + dihedral closure"},
    )

    # A construction hexagon and its diagonals expose the triangular lattice.
    boundary: list[str] = []
    boundary_seed = "guide.boundary.seed"
    builder.point(boundary_seed, (2.85, 0.0, -0.10))
    boundary.append(boundary_seed)
    for index in range(1, 6):
        point_id = f"guide.boundary.p{index}"
        builder.rotated_point(point_id, boundary_seed, axis=(0.0, 0.0, 1.0), angle=index * math.pi / 3.0)
        boundary.append(point_id)
    _connect_polygon(builder, "guide.boundary", boundary, "guide")
    for index in range(3):
        builder.edge(f"guide.axis.{index}", boundary[index], boundary[index + 3], "guide")

    segments = _word_segments(program)
    for level, scale in enumerate(program.scales):
        for segment_index, (start, end) in enumerate(segments):
            tangent = end - start
            tangent /= max(float(np.linalg.norm(tangent)), 1e-9)
            normal = np.asarray((-tangent[1], tangent[0]))
            half_width = program.width / 2.0
            seed_xy = (
                start + half_width * normal,
                end + half_width * normal,
                end - half_width * normal,
                start - half_width * normal,
            )
            seed_ids: list[str] = []
            for vertex_index, xy in enumerate(seed_xy):
                seed_id = f"l{level}.s{segment_index}.seed{vertex_index}"
                builder.point(seed_id, (float(xy[0]), float(xy[1]), 0.0))
                seed_ids.append(seed_id)

            for sector in range(6):
                ids: list[str] = []
                for vertex_index, seed_id in enumerate(seed_ids):
                    source_id = seed_id
                    if program.reflected_alternation and sector % 2:
                        reflected_id = f"l{level}.s{segment_index}.q{sector}.mirror{vertex_index}"
                        builder.reflected_point(
                            reflected_id,
                            seed_id,
                            plane_normal=(0.0, 1.0, 0.0),
                        )
                        source_id = reflected_id
                    point_id = f"l{level}.s{segment_index}.q{sector}.v{vertex_index}"
                    z = program.lift * (0.32 + 0.68 * ((sector + level) % 2))
                    builder.rotated_point(
                        point_id,
                        source_id,
                        axis=(0.0, 0.0, 1.0),
                        angle=program.phase + sector * math.pi / 3.0,
                        scale=scale,
                        translation=(0.0, 0.0, z + 0.10 * level),
                    )
                    ids.append(point_id)
                face_id = f"l{level}.s{segment_index}.q{sector}.face"
                builder.face(face_id, ids, sector + 2 * level)
                _connect_polygon(builder, face_id, ids, "result")

    center_seed = "center.seed"
    builder.point(center_seed, (program.width * 0.85, 0.0, program.lift + 0.14))
    center_ids = [center_seed]
    for index in range(1, 6):
        point_id = f"center.p{index}"
        builder.rotated_point(point_id, center_seed, axis=(0.0, 0.0, 1.0), angle=index * math.pi / 3.0)
        center_ids.append(point_id)
    builder.face("center.face", center_ids, 3)
    _connect_polygon(builder, "center.face", center_ids)
    return builder.build()


ORBIT_PROGRAMS = (
    OrbitProgram(
        "11", "Contractive chord current", "affine", 62,
        (("stride", 1, 0, "result"), ("stride", 9, 0, "secondary"), ("stride", 17, 0, "guide")),
        ((3.25, -0.28, 0.10), (-3.05, 0.24, 3.02)), 0.405, 0.965, (0.018, -0.010, 0.010), ribbon=False,
    ),
    OrbitProgram(
        "12", "Modular spectral web", "closed", 48,
        (("stride", 1, 0, "guide"), ("affine", 7, 1, "result"), ("affine", 13, 5, "secondary")),
        ((3.15, -0.20, 0.0),), ribbon=False,
    ),
    OrbitProgram(
        "13", "Double orbit lens", "closed", 36,
        (("stride", 1, 0, "result"), ("stride", 11, 0, "secondary")),
        ((2.35, -0.42, 0.0), (3.25, 0.44, 0.087)), ribbon=True,
    ),
    OrbitProgram(
        "14", "Recursive light canopy", "branching", 0, (),
        scale=0.73, branch_depth=6, branch_angles=(-0.47, 0.47), ribbon=True,
    ),
)


HEX_PROGRAMS = (
    HexWordProgram("15", "Six-arm ribbon lock", (0, 1, 3, 2, 4), (1.0,), 0.32, 0.74, False, 0.48, 0.0),
    HexWordProgram("16", "Reflected crystal braid", (0, 1, 0, 5, 3, 4), (1.0, 0.57), 0.25, 0.61, True, 0.62, math.pi / 12.0),
    HexWordProgram("17", "Nested triangular current", (0, 2, 1, 4, 3), (1.0, 0.66, 0.39), 0.22, 0.58, False, 0.72, math.pi / 18.0),
    HexWordProgram("18", "Prismatic lattice pavilion", (0, 1, 3, 5, 2, 4), (1.0, 0.64), 0.34, 0.68, True, 1.12, math.pi / 10.0),
)


RENDER_SPECS = {
    "11": StudySpec("11", "Contractive chord current", "orbit_index_map", "sapphire-amber", Camera(34, 37, -6, 10.8, 2.0), False, True, True, "glass", True),
    "12": StudySpec("12", "Modular spectral web", "orbit_index_map", "prism-coral", Camera(22, 52, 4, 10.2, 2.0), False, True, True, "glass", True),
    "13": StudySpec("13", "Double orbit lens", "orbit_index_map", "spectrum-glass", Camera(42, 27, -4, 10.6, 2.0), False, True, False, "glass", True),
    "14": StudySpec("14", "Recursive light canopy", "orbit_index_map", "prism-coral", Camera(54, 48, -2, 10.4, 2.0), False, False, False, "glass", True),
    "15": StudySpec("15", "Six-arm ribbon lock", "triangular_lattice_word", "sapphire-amber", Camera(42, 48, 0, 11.0, 2.0), False, True, False, "glass", True),
    "16": StudySpec("16", "Reflected crystal braid", "triangular_lattice_word", "prism-coral", Camera(48, 43, -3, 11.5, 2.0), False, True, False, "glass", True),
    "17": StudySpec("17", "Nested triangular current", "triangular_lattice_word", "spectrum-glass", Camera(28, 55, 4, 12.0, 2.1), False, True, False, "glass", True),
    "18": StudySpec("18", "Prismatic lattice pavilion", "triangular_lattice_word", "spectrum-glass", Camera(38, 29, -7, 12.2, 2.0), False, False, False, "glass", True),
}


def build_all() -> list[tuple[str, str, SpatialFigure]]:
    values = [(program.study_id, program.title, build_orbit_program(program)) for program in ORBIT_PROGRAMS]
    values.extend((program.study_id, program.title, build_hex_word_program(program)) for program in HEX_PROGRAMS)
    return values


def _rotation_residual(figure: SpatialFigure, order: int) -> float:
    used = {item for edge in figure.edges if edge.role != "guide" for item in (edge.start_id, edge.end_id)}
    points = [np.asarray(figure.points[item], dtype=np.float64) for item in used]
    if not points:
        return math.inf
    residual = 0.0
    for point in points:
        rotated = np.asarray(rotate_axis_angle(tuple(point), (0.0, 0.0, 1.0), 2.0 * math.pi / order))
        residual = max(residual, min(float(np.linalg.norm(rotated - candidate)) for candidate in points))
    return residual


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _review_sheet(records: list[dict[str, object]], output: Path) -> None:
    width, columns, margin, gap = 2100, 4, 48, 28
    tile = (width - 2 * margin - (columns - 1) * gap) // columns
    header, caption = 168, 72
    rows = math.ceil(len(records) / columns)
    sheet = Image.new("RGB", (width, header + rows * (tile + caption + gap) + margin), "#ECE8E2")
    draw = ImageDraw.Draw(sheet)
    draw.text((margin, 34), "MORTRA / ITERATED ORNAMENT STUDIES", font=_font(42, bold=True), fill="#162F42")
    draw.text(
        (margin, 94),
        "two parameterized programs / existing geometry only / directional light + translucent material",
        font=_font(23),
        fill="#617783",
    )
    for index, record in enumerate(records):
        row, column = divmod(index, columns)
        x = margin + column * (tile + gap)
        y = header + row * (tile + caption + gap)
        image = Image.open(str(record["path"])).convert("RGB").resize((tile, tile), Image.Resampling.LANCZOS)
        sheet.paste(image, (x, y))
        draw.text((x, y + tile + 10), f"{record['study_id']}  {record['title']}", font=_font(20, bold=True), fill="#162F42")
        draw.text(
            (x, y + tile + 40),
            f"{record['construction_steps']} steps / {record['face_count']} translucent faces",
            font=_font(16),
            fill="#667985",
        )
    sheet.save(output, optimize=True)


def generate(output_dir: Path = OUTPUT_DIR, *, size: int = IMAGE_SIZE) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    figures = build_all()
    for study_id, title, figure in figures:
        image = render_spatial_figure(figure, RENDER_SPECS[study_id], size=size)
        path = output_dir / f"mortra-ornament-{study_id}.png"
        image.save(path, optimize=True)
        records.append(
            {
                "study_id": study_id,
                "title": title,
                "family": figure.family,
                "path": str(path),
                "semantic_sha256": semantic_hash(figure),
                "image_sha256": _sha256(path),
                "point_count": len(figure.points),
                "edge_count": len(figure.edges),
                "face_count": len(figure.faces),
                "construction_steps": len(figure.construction_trace),
                "composition_depth": figure.composition_depth,
                "operations": sorted(figure.operations_used),
                "new_morphism_count": new_morphism_count(figure),
            }
        )

    hex_programs = {program.study_id: program for program in HEX_PROGRAMS}
    hex_residuals = {
        study_id: {
            "declared_order": hex_programs[study_id].rotational_order,
            "max_residual": _rotation_residual(figure, hex_programs[study_id].rotational_order),
        }
        for study_id, _, figure in figures
        if figure.family == "triangular_lattice_word"
    }
    review = output_dir / "mortra-iterated-ornament-review.png"
    _review_sheet(records, review)
    checks = {
        "eight_structurally_distinct_figures": len({item["semantic_sha256"] for item in records}) == 8,
        "eight_distinct_renders": len({item["image_sha256"] for item in records}) == 8,
        "zero_new_geometry_morphisms": all(item["new_morphism_count"] == 0 for item in records),
        "all_programs_exceed_one_hundred_construction_steps": all(item["construction_steps"] > 100 for item in records),
        "hex_programs_match_declared_rotational_closure": all(
            float(value["max_residual"]) <= 1e-9 for value in hex_residuals.values()
        ),
        "reflection_is_composed_where_requested": all(
            "reflect" in next(item for item in records if item["study_id"] == program.study_id)["operations"]
            for program in HEX_PROGRAMS
            if program.reflected_alternation
        ),
    }
    manifest = {
        "schema": "mortra.iterated-ornament.v1",
        "generated_at": "2026-09-04",
        "parameterized_generators": [
            "point orbit + index-map connections",
            "triangular-lattice direction word + dihedral closure",
        ],
        "new_geometry_morphisms": 0,
        "render_model": {
            "diffuse": "0.20 + 0.80 abs(n dot l)",
            "specular": "abs(n dot normalize(l+v))^42",
            "fresnel": "0.035 + 0.965(1-abs(n dot v))^5",
            "transmission": "exp(-0.34/max(abs(n dot v),0.18))",
            "shadow": "intersection of the ray p-t*l with a ground plane, followed by penumbra blur",
        },
        "rotational_closure": hex_residuals,
        "records": records,
        "checks": checks,
        "passed": all(checks.values()),
        "review_path": str(review),
        "review_sha256": _sha256(review),
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    manifest = generate()
    print(
        json.dumps(
            {
                "output": str(OUTPUT_DIR),
                "passed": manifest["passed"],
                "studies": len(manifest["records"]),
                "checks": manifest["checks"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if manifest["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
