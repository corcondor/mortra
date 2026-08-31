"""OpenCascade execution backend for MORTRA's engineering geometry IR.

This module builds exact boundary representations (B-reps), records every geometry
operation in :mod:`engineering_geometry_ir`, and derives drawings from the same
solid.  It intentionally avoids a second, hand-written drawing model.

The optional dependency is installed in a dedicated research environment:

    C:/Users/81808/.cache/mortra-cad-venv/Scripts/python.exe

The web worker does not need OpenCascade unless it executes this backend.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
import json
import math
from pathlib import Path
import time
from typing import Any, Callable, Iterable, Sequence

from .engineering_geometry_ir import BasisOp, ConstructionProgram, EntityRef, GeometricType


def _load_build123d() -> dict[str, Any]:
    try:
        from build123d import (  # type: ignore
            Axis,
            Compound,
            Draft,
            Edge,
            ExtensionLine,
            Face,
            LineType,
            Location,
            PageSize,
            Plane,
            Pos,
            ShapeList,
            Sketch,
            Solid,
            TechnicalDrawing,
            Text,
            Unit,
            Vector,
            Wire,
            section,
        )
        from build123d.exporters import Drawing, ExportDXF, ExportSVG
        from build123d.exporters3d import export_step
    except ImportError as exc:  # pragma: no cover - depends on the research venv
        raise RuntimeError(
            "The engineering CAD backend requires build123d/OpenCascade. "
            "Run it with C:/Users/81808/.cache/mortra-cad-venv/Scripts/python.exe"
        ) from exc

    return locals()


def _export_stl_serial(
    shape: Any,
    path: Path,
    *,
    tolerance: float,
    angular_tolerance: float,
) -> None:
    """Mesh a B-rep without OpenCascade's parallel meshing path.

    The parallel path in the pinned Windows OCP build stalls on swept helical
    faces.  Serial meshing is deterministic and keeps STEP as the exact source.
    """

    from OCP.BRepMesh import BRepMesh_IncrementalMesh  # type: ignore
    from OCP.StlAPI import StlAPI_Writer  # type: ignore

    mesh = BRepMesh_IncrementalMesh(
        shape.wrapped,
        tolerance,
        True,
        angular_tolerance,
        False,
    )
    mesh.Perform()
    writer = StlAPI_Writer()
    writer.ASCIIMode = False
    if not writer.Write(shape.wrapped, str(path)):
        raise RuntimeError(f"failed to export STL: {path}")


@dataclass
class CadEntity:
    ref: EntityRef
    shape: Any


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    observed: Any
    expected: Any
    tolerance: float | None = None
    message: str = ""


@dataclass(frozen=True)
class DrawingViewSpec:
    name: str
    look_from: tuple[float, float, float]
    look_up: tuple[float, float, float]
    page_box: tuple[float, float, float, float]
    include_hidden: bool = True


@dataclass(frozen=True)
class DrawingPlacement:
    scale: float
    translation: tuple[float, float]
    bbox: Any


@dataclass
class EngineeringPart:
    part_id: str
    title: str
    entity: CadEntity
    program: ConstructionProgram
    nominal_dimensions_mm: dict[str, float]
    checks: list[CheckResult]
    section_plane: str = "XZ"
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)


class CadExecutor:
    """Execute the eight generic morphisms while recording a typed DAG."""

    def __init__(self, program_id: str):
        self.b3d = _load_build123d()
        self.program = ConstructionProgram(program_id)
        self.annotations: dict[str, dict[str, Any]] = {}
        self.constraint_results: list[CheckResult] = []

    def input_cell(
        self,
        name: str,
        shape: Any,
        *,
        ambient_dimension: int,
        intrinsic_dimension: int,
        kind: str,
    ) -> CadEntity:
        ref = self.program.declare(
            name,
            GeometricType(ambient_dimension, intrinsic_dimension, kind),
            role="input",
        )
        return CadEntity(ref, shape)

    def transform(
        self,
        entity: CadEntity,
        name: str,
        *,
        translation: tuple[float, float, float] | None = None,
        rotation_axis: Any | None = None,
        angle_degrees: float = 0.0,
        scale: float | tuple[float, float, float] | None = None,
        scale_about: tuple[float, float, float] = (0.0, 0.0, 0.0),
        mirror_plane: Any | None = None,
    ) -> CadEntity:
        shape = entity.shape
        if rotation_axis is not None and angle_degrees:
            shape = shape.rotate(rotation_axis, angle_degrees)
        if scale is not None:
            shape = shape.scale(scale, about=scale_about)
        if mirror_plane is not None:
            shape = shape.mirror(mirror_plane)
        if translation is not None:
            shape = shape.translate(translation)
        ref = self.program.apply(
            BasisOp.TRANSFORM,
            [entity.ref],
            name,
            entity.ref.geometric_type,
            translation=translation,
            angle_degrees=angle_degrees,
            scale=scale,
            scale_about=scale_about,
            mirror_plane=str(mirror_plane) if mirror_plane is not None else None,
        )
        return CadEntity(ref, shape)

    def linear_sweep(
        self,
        profile: CadEntity,
        name: str,
        vector: tuple[float, float, float],
    ) -> CadEntity:
        Solid = self.b3d["Solid"]
        shape = Solid.extrude(profile.shape, vector)
        output_type = GeometricType(
            max(3, profile.ref.geometric_type.ambient_dimension),
            min(3, profile.ref.geometric_type.intrinsic_dimension + 1),
            "region",
        )
        ref = self.program.apply(
            BasisOp.SWEEP,
            [profile.ref],
            name,
            output_type,
            path_dimension=1,
            trajectory="line",
            vector=vector,
        )
        return CadEntity(ref, shape)

    def rotary_sweep(
        self,
        profile: CadEntity,
        name: str,
        *,
        axis: Any,
        angle_degrees: float = 360.0,
    ) -> CadEntity:
        Solid = self.b3d["Solid"]
        shape = Solid.revolve(profile.shape, angle_degrees, axis)
        ref = self.program.apply(
            BasisOp.SWEEP,
            [profile.ref],
            name,
            GeometricType(3, 3, "region"),
            path_dimension=1,
            trajectory="circle",
            angle_degrees=angle_degrees,
        )
        return CadEntity(ref, shape)

    def loft_sweep(
        self,
        profiles: Sequence[CadEntity],
        name: str,
        *,
        ruled: bool = False,
    ) -> CadEntity:
        if len(profiles) < 2:
            raise ValueError("loft requires at least two profile cells")
        Solid = self.b3d["Solid"]
        wires = [
            p.shape.outer_wire() if hasattr(p.shape, "outer_wire") else p.shape
            for p in profiles
        ]
        shape = Solid.make_loft(wires, ruled=ruled)
        ref = self.program.apply(
            BasisOp.SWEEP,
            [p.ref for p in profiles],
            name,
            GeometricType(3, 3, "region"),
            path_dimension=1,
            trajectory="section_family",
            ruled=ruled,
        )
        return CadEntity(ref, shape)

    def path_sweep(
        self,
        profile: CadEntity,
        path: CadEntity,
        name: str,
        *,
        is_frenet: bool = False,
    ) -> CadEntity:
        """Sweep one profile along an explicit typed path.

        Helices, splines, and polylines remain path data.  They do not become new
        operation families: every case is recorded as the same ``sweep`` morphism.
        """
        Solid = self.b3d["Solid"]
        shape = Solid.sweep(profile.shape, path.shape, is_frenet=is_frenet)
        output_type = GeometricType(
            max(3, profile.ref.geometric_type.ambient_dimension),
            min(3, profile.ref.geometric_type.intrinsic_dimension + 1),
            "region",
        )
        ref = self.program.apply(
            BasisOp.SWEEP,
            [profile.ref, path.ref],
            name,
            output_type,
            path_dimension=1,
            trajectory="explicit_path",
            is_frenet=is_frenet,
        )
        return CadEntity(ref, shape)

    def combine(
        self,
        operation: str,
        entities: Sequence[CadEntity],
        name: str,
    ) -> CadEntity:
        if len(entities) < 2:
            raise ValueError("combine requires at least two entities")
        shape = entities[0].shape
        for other in entities[1:]:
            if operation == "union":
                shape = shape.fuse(other.shape)
            elif operation == "difference":
                shape = shape.cut(other.shape)
            elif operation == "intersection":
                shape = shape.intersect(other.shape)
            else:
                raise ValueError(f"unknown boolean operation: {operation}")
        if hasattr(shape, "clean"):
            shape = shape.clean()
        ref = self.program.apply(
            BasisOp.COMBINE,
            [entity.ref for entity in entities],
            name,
            entities[0].ref.geometric_type,
            operation=operation,
        )
        return CadEntity(ref, shape)

    def constrain(
        self,
        entity: CadEntity,
        name: str,
        predicate: Callable[[Any], tuple[bool, Any]],
        *,
        expected: Any,
        tolerance: float | None = None,
        description: str = "",
        output_name: str | None = None,
    ) -> CadEntity:
        passed, observed = predicate(entity.shape)
        check = CheckResult(
            name=name,
            passed=bool(passed),
            observed=observed,
            expected=expected,
            tolerance=tolerance,
            message=description,
        )
        self.constraint_results.append(check)
        ref = self.program.apply(
            BasisOp.CONSTRAIN,
            [entity.ref],
            output_name
            or f"{entity.ref.name}__checked_{len(self.constraint_results)}",
            entity.ref.geometric_type,
            predicate=name,
            passed=bool(passed),
        )
        return CadEntity(ref, entity.shape)

    def annotate(
        self,
        entity: CadEntity,
        name: str,
        output_name: str | None = None,
        **annotations: Any,
    ) -> CadEntity:
        self.annotations[name] = dict(annotations)
        ref = self.program.apply(
            BasisOp.ANNOTATE,
            [entity.ref],
            output_name or f"{entity.ref.name}__annotated_{len(self.annotations)}",
            entity.ref.geometric_type,
            annotation_set=name,
            fields=sorted(annotations),
        )
        return CadEntity(ref, entity.shape)

    def select(
        self,
        entity: CadEntity,
        name: str,
        *,
        selector: str,
    ) -> CadEntity:
        """Select a lower-dimensional feature without introducing a CAD feature API."""
        Compound = self.b3d["Compound"]
        source_dimension = entity.ref.geometric_type.intrinsic_dimension
        if selector == "outer_boundary" and hasattr(entity.shape, "outer_wire"):
            shape = entity.shape.outer_wire()
            output_dimension = source_dimension - 1
        elif selector == "edges" and hasattr(entity.shape, "edges"):
            shape = Compound(list(entity.shape.edges()))
            output_dimension = 1
        elif selector == "faces" and hasattr(entity.shape, "faces"):
            shape = Compound(list(entity.shape.faces()))
            output_dimension = 2
        else:
            raise ValueError(f"unsupported selector for this entity: {selector}")
        ref = self.program.apply(
            BasisOp.SELECT,
            [entity.ref],
            name,
            GeometricType(
                entity.ref.geometric_type.ambient_dimension,
                output_dimension,
                selector,
            ),
            selector=selector,
        )
        return CadEntity(ref, shape)

    def slice(self, entity: CadEntity, name: str, plane: Any) -> CadEntity:
        section = self.b3d["section"](entity.shape, plane)
        ref = self.program.apply(
            BasisOp.SLICE,
            [entity.ref],
            name,
            GeometricType(3, 2, "section"),
            codimension=1,
            plane=str(plane),
        )
        return CadEntity(ref, section)

    def project(
        self,
        entity: CadEntity,
        name: str,
        *,
        look_from: tuple[float, float, float],
        look_up: tuple[float, float, float],
        include_hidden: bool = True,
    ) -> tuple[CadEntity, Any]:
        Drawing = self.b3d["Drawing"]
        drawing = Drawing(
            entity.shape,
            look_from=look_from,
            look_up=look_up,
            with_hidden=include_hidden,
        )
        ref = self.program.apply(
            BasisOp.PROJECT,
            [entity.ref],
            name,
            GeometricType(2, 2, "drawing"),
            projection="orthographic",
            look_from=look_from,
            look_up=look_up,
            include_hidden=include_hidden,
        )
        return CadEntity(ref, drawing.visible_lines), drawing


def _close(observed: float, expected: float, tolerance: float) -> tuple[bool, float]:
    return abs(observed - expected) <= tolerance, observed


def _valid(shape: Any) -> tuple[bool, bool]:
    value = bool(shape.is_valid)
    return value, value


def _solid_count(shape: Any) -> tuple[bool, int]:
    count = len(shape.solids())
    return count == 1, count


def build_flange(
    *,
    outer_radius: float = 34.0,
    bore_radius: float = 12.0,
    thickness: float = 8.0,
    bolt_radius: float = 3.2,
    bolt_circle_radius: float = 25.0,
    bolt_count: int = 6,
) -> EngineeringPart:
    b3d = _load_build123d()
    Face, Wire, Plane = b3d["Face"], b3d["Wire"], b3d["Plane"]
    ex = CadExecutor("flange")

    annulus = Face(Wire.make_circle(outer_radius), [Wire.make_circle(bore_radius)])
    profile = ex.input_cell(
        "annulus_profile", annulus, ambient_dimension=3, intrinsic_dimension=2, kind="region"
    )
    body = ex.linear_sweep(profile, "flange_body", (0, 0, thickness))

    hole_profile = ex.input_cell(
        "bolt_hole_profile",
        Face(Wire.make_circle(bolt_radius)),
        ambient_dimension=3,
        intrinsic_dimension=2,
        kind="region",
    )
    hole_solids: list[CadEntity] = []
    for index in range(bolt_count):
        angle = 2 * math.pi * index / bolt_count
        placed = ex.transform(
            hole_profile,
            f"bolt_profile_{index + 1}",
            translation=(
                bolt_circle_radius * math.cos(angle),
                bolt_circle_radius * math.sin(angle),
                0,
            ),
        )
        hole_solids.append(
            ex.linear_sweep(placed, f"bolt_hole_{index + 1}", (0, 0, thickness))
        )
    part = ex.combine("difference", [body, *hole_solids], "finished_flange")

    expected_volume = math.pi * (
        outer_radius**2 - bore_radius**2 - bolt_count * bolt_radius**2
    ) * thickness
    part = ex.constrain(
        part,
        "valid_brep",
        _valid,
        expected=True,
        description="OpenCascade B-rep validity",
    )
    part = ex.constrain(
        part,
        "single_solid",
        _solid_count,
        expected=1,
        description="All material must form one connected solid",
    )
    part = ex.constrain(
        part,
        "analytic_volume",
        lambda s: _close(s.volume, expected_volume, 1e-5),
        expected=expected_volume,
        tolerance=1e-5,
        description="Annulus minus six through holes, times thickness",
    )
    part = ex.annotate(
        part,
        "nominal_dimensions",
        outer_diameter=2 * outer_radius,
        bore_diameter=2 * bore_radius,
        thickness=thickness,
        bolt_hole_diameter=2 * bolt_radius,
        bolt_circle_diameter=2 * bolt_circle_radius,
        bolt_count=bolt_count,
    )
    return EngineeringPart(
        "flange",
        "Six-hole mounting flange",
        part,
        ex.program,
        {
            "outer_diameter": 2 * outer_radius,
            "bore_diameter": 2 * bore_radius,
            "thickness": thickness,
            "bolt_hole_diameter": 2 * bolt_radius,
            "bolt_circle_diameter": 2 * bolt_circle_radius,
            "bolt_count": bolt_count,
        },
        ex.constraint_results,
        section_plane="XZ",
        metadata={
            "family": "profile + linear sweep + patterned subtraction",
            "drawing_notes": [
                f"OD {2 * outer_radius:g}   BORE {2 * bore_radius:g}",
                f"{bolt_count} x HOLE {2 * bolt_radius:g} ON PCD {2 * bolt_circle_radius:g}",
                f"THICKNESS {thickness:g}",
            ],
        },
    )


def build_stepped_shaft(
    *,
    lengths: tuple[float, float, float] = (24.0, 34.0, 20.0),
    radii: tuple[float, float, float] = (10.0, 15.0, 8.0),
    bore_radius: float = 3.0,
) -> EngineeringPart:
    b3d = _load_build123d()
    Axis, Face, Wire = b3d["Axis"], b3d["Face"], b3d["Wire"]
    ex = CadExecutor("stepped_shaft")
    x1, x2, x3 = lengths
    r1, r2, r3 = radii
    points = [
        (0, 0),
        (0, r1),
        (x1, r1),
        (x1, r2),
        (x1 + x2, r2),
        (x1 + x2, r3),
        (x1 + x2 + x3, r3),
        (x1 + x2 + x3, 0),
    ]
    profile = ex.input_cell(
        "shaft_profile",
        Face(Wire.make_polygon(points)),
        ambient_dimension=3,
        intrinsic_dimension=2,
        kind="region",
    )
    outer = ex.rotary_sweep(profile, "outer_shaft", axis=Axis.X)

    bore_profile = ex.input_cell(
        "bore_profile",
        Face(Wire.make_polygon([(0, 0), (0, bore_radius), (sum(lengths), bore_radius), (sum(lengths), 0)])),
        ambient_dimension=3,
        intrinsic_dimension=2,
        kind="region",
    )
    bore = ex.rotary_sweep(bore_profile, "axial_bore", axis=Axis.X)
    part = ex.combine("difference", [outer, bore], "finished_shaft")

    expected_volume = math.pi * sum(
        length * (radius**2 - bore_radius**2)
        for length, radius in zip(lengths, radii)
    )
    part = ex.constrain(part, "valid_brep", _valid, expected=True)
    part = ex.constrain(part, "single_solid", _solid_count, expected=1)
    part = ex.constrain(
        part,
        "analytic_volume",
        lambda s: _close(s.volume, expected_volume, 1e-5),
        expected=expected_volume,
        tolerance=1e-5,
    )
    part = ex.annotate(
        part,
        "nominal_dimensions",
        total_length=sum(lengths),
        step_lengths=lengths,
        step_diameters=tuple(2 * radius for radius in radii),
        bore_diameter=2 * bore_radius,
    )
    return EngineeringPart(
        "stepped_shaft",
        "Hollow stepped shaft",
        part,
        ex.program,
        {
            "length": sum(lengths),
            "maximum_diameter": 2 * max(radii),
            "bore_diameter": 2 * bore_radius,
        },
        ex.constraint_results,
        section_plane="YZ",
        metadata={
            "family": "profile + rotary sweep + subtraction",
            "drawing_notes": [
                f"LENGTH {sum(lengths):g}",
                "STEP OD " + " / ".join(f"{2 * radius:g}" for radius in radii),
                f"THRU BORE {2 * bore_radius:g}",
            ],
        },
    )


def build_angle_bracket(
    *,
    width: float = 72.0,
    depth: float = 48.0,
    height: float = 44.0,
    thickness: float = 6.0,
    hole_radius: float = 4.0,
) -> EngineeringPart:
    b3d = _load_build123d()
    Axis, Face = b3d["Axis"], b3d["Face"]
    ex = CadExecutor("angle_bracket")

    base_profile = ex.input_cell(
        "base_profile",
        Face.make_rect(width, depth),
        ambient_dimension=3,
        intrinsic_dimension=2,
        kind="region",
    )
    base = ex.linear_sweep(base_profile, "base_plate", (0, 0, thickness))

    web_profile = ex.input_cell(
        "web_profile_xy",
        Face.make_rect(width, height),
        ambient_dimension=3,
        intrinsic_dimension=2,
        kind="region",
    )
    web_profile = ex.transform(
        web_profile,
        "web_profile_vertical",
        rotation_axis=Axis.X,
        angle_degrees=90,
        translation=(0, -depth / 2, thickness + height / 2),
    )
    web = ex.linear_sweep(web_profile, "vertical_web", (0, thickness, 0))
    body = ex.combine("union", [base, web], "bracket_body")

    Wire = b3d["Wire"]
    hole_profile = ex.input_cell(
        "base_hole_profile",
        Face(Wire.make_circle(hole_radius)),
        ambient_dimension=3,
        intrinsic_dimension=2,
        kind="region",
    )
    holes: list[CadEntity] = []
    for index, x in enumerate((-width / 4, width / 4), start=1):
        placed = ex.transform(
            hole_profile,
            f"base_hole_profile_{index}",
            translation=(x, 0, 0),
        )
        holes.append(ex.linear_sweep(placed, f"base_hole_{index}", (0, 0, thickness)))
    part = ex.combine("difference", [body, *holes], "finished_bracket")

    expected_volume = width * depth * thickness + width * height * thickness
    expected_volume -= 2 * math.pi * hole_radius**2 * thickness
    part = ex.constrain(part, "valid_brep", _valid, expected=True)
    part = ex.constrain(part, "single_solid", _solid_count, expected=1)
    part = ex.constrain(
        part,
        "analytic_volume",
        lambda s: _close(s.volume, expected_volume, 1e-5),
        expected=expected_volume,
        tolerance=1e-5,
    )
    part = ex.annotate(
        part,
        "nominal_dimensions",
        width=width,
        depth=depth,
        height=height,
        thickness=thickness,
        base_hole_diameter=2 * hole_radius,
    )
    return EngineeringPart(
        "angle_bracket",
        "Two-plane mounting bracket",
        part,
        ex.program,
        {
            "width": width,
            "depth": depth,
            "height": height,
            "thickness": thickness,
            "hole_diameter": 2 * hole_radius,
        },
        ex.constraint_results,
        section_plane="YZ",
        metadata={
            "family": "orthogonal sweeps + union + patterned subtraction",
            "drawing_notes": [
                f"WIDTH {width:g}   DEPTH {depth:g}",
                f"HEIGHT {height:g}   THICKNESS {thickness:g}",
                f"2 x HOLE {2 * hole_radius:g}",
            ],
        },
    )


def build_transition_duct(
    *,
    lower_size: tuple[float, float] = (64.0, 46.0),
    upper_radius: float = 20.0,
    height: float = 58.0,
    wall: float = 3.0,
) -> EngineeringPart:
    b3d = _load_build123d()
    Face, Plane, Wire = b3d["Face"], b3d["Plane"], b3d["Wire"]
    ex = CadExecutor("transition_duct")

    outer_bottom = ex.input_cell(
        "outer_bottom",
        Face.make_rect(*lower_size),
        ambient_dimension=3,
        intrinsic_dimension=2,
        kind="region",
    )
    outer_top = ex.input_cell(
        "outer_top",
        Face(Wire.make_circle(upper_radius, Plane.XY.offset(height))),
        ambient_dimension=3,
        intrinsic_dimension=2,
        kind="region",
    )
    outer = ex.loft_sweep([outer_bottom, outer_top], "outer_loft")

    inner_bottom = ex.input_cell(
        "inner_bottom",
        Face.make_rect(lower_size[0] - 2 * wall, lower_size[1] - 2 * wall),
        ambient_dimension=3,
        intrinsic_dimension=2,
        kind="region",
    )
    inner_top = ex.input_cell(
        "inner_top",
        Face(Wire.make_circle(upper_radius - wall, Plane.XY.offset(height))),
        ambient_dimension=3,
        intrinsic_dimension=2,
        kind="region",
    )
    inner = ex.loft_sweep([inner_bottom, inner_top], "inner_loft")
    part = ex.combine("difference", [outer, inner], "finished_duct")
    part = ex.constrain(part, "valid_brep", _valid, expected=True)
    part = ex.constrain(part, "single_solid", _solid_count, expected=1)
    part = ex.constrain(
        part,
        "positive_wall_volume",
        lambda s: (s.volume > 0, s.volume),
        expected="> 0",
    )
    part = ex.annotate(
        part,
        "nominal_dimensions",
        lower_width=lower_size[0],
        lower_depth=lower_size[1],
        upper_diameter=2 * upper_radius,
        height=height,
        nominal_wall=wall,
    )
    return EngineeringPart(
        "transition_duct",
        "Rectangular-to-round transition duct",
        part,
        ex.program,
        {
            "lower_width": lower_size[0],
            "lower_depth": lower_size[1],
            "upper_diameter": 2 * upper_radius,
            "height": height,
            "wall": wall,
        },
        ex.constraint_results,
        section_plane="XZ",
        metadata={
            "family": "section-family sweep + subtraction",
            "drawing_notes": [
                f"INLET {lower_size[0]:g} x {lower_size[1]:g}",
                f"OUTLET OD {2 * upper_radius:g}",
                f"HEIGHT {height:g}   WALL {wall:g}",
            ],
        },
    )


def build_lattice_panel(
    *,
    size: float = 72.0,
    bar_width: float = 5.0,
    thickness: float = 4.0,
    count: int = 5,
) -> EngineeringPart:
    b3d = _load_build123d()
    Axis, Face = b3d["Axis"], b3d["Face"]
    ex = CadExecutor("lattice_panel")
    base_profile = ex.input_cell(
        "bar_profile",
        Face.make_rect(size, bar_width),
        ambient_dimension=3,
        intrinsic_dimension=2,
        kind="region",
    )
    bar = ex.linear_sweep(base_profile, "bar_solid", (0, 0, thickness))
    spacing = (size - bar_width) / (count - 1)
    entities: list[CadEntity] = []
    for index in range(count):
        offset = -size / 2 + bar_width / 2 + index * spacing
        entities.append(
            ex.transform(bar, f"horizontal_{index + 1}", translation=(0, offset, 0))
        )
    vertical_seed = ex.transform(
        bar,
        "vertical_seed",
        rotation_axis=Axis.Z,
        angle_degrees=90,
    )
    for index in range(count):
        offset = -size / 2 + bar_width / 2 + index * spacing
        entities.append(
            ex.transform(vertical_seed, f"vertical_{index + 1}", translation=(offset, 0, 0))
        )
    part = ex.combine("union", entities, "finished_lattice")

    expected_area = 2 * count * size * bar_width - count**2 * bar_width**2
    expected_volume = expected_area * thickness
    part = ex.constrain(part, "valid_brep", _valid, expected=True)
    part = ex.constrain(part, "single_solid", _solid_count, expected=1)
    part = ex.constrain(
        part,
        "analytic_volume",
        lambda s: _close(s.volume, expected_volume, 1e-5),
        expected=expected_volume,
        tolerance=1e-5,
    )
    part = ex.annotate(
        part,
        "nominal_dimensions",
        panel_size=size,
        bar_width=bar_width,
        thickness=thickness,
        bars_per_direction=count,
    )
    return EngineeringPart(
        "lattice_panel",
        "Parametric architectural lattice",
        part,
        ex.program,
        {"width": size, "height": size, "thickness": thickness},
        ex.constraint_results,
        section_plane="XZ",
        metadata={
            "family": "repeated transforms + union",
            "drawing_notes": [
                f"PANEL {size:g} x {size:g}",
                f"BAR {bar_width:g}   THICKNESS {thickness:g}",
                f"{count} BARS PER DIRECTION",
            ],
        },
    )


def build_spoked_wheel(
    *,
    outer_radius: float = 38.0,
    rim_width: float = 6.0,
    hub_radius: float = 10.0,
    bore_radius: float = 4.0,
    thickness: float = 7.0,
    spoke_width: float = 5.0,
    spoke_count: int = 6,
) -> EngineeringPart:
    b3d = _load_build123d()
    Axis, Face, Wire = b3d["Axis"], b3d["Face"], b3d["Wire"]
    ex = CadExecutor("spoked_wheel")
    inner_radius = outer_radius - rim_width

    rim_profile = ex.input_cell(
        "rim_profile",
        Face(Wire.make_circle(outer_radius), [Wire.make_circle(inner_radius)]),
        ambient_dimension=3,
        intrinsic_dimension=2,
        kind="region",
    )
    rim = ex.linear_sweep(rim_profile, "rim", (0, 0, thickness))
    hub_profile = ex.input_cell(
        "hub_profile",
        Face(Wire.make_circle(hub_radius), [Wire.make_circle(bore_radius)]),
        ambient_dimension=3,
        intrinsic_dimension=2,
        kind="region",
    )
    hub = ex.linear_sweep(hub_profile, "hub", (0, 0, thickness))

    overlap = 1.0
    spoke_length = inner_radius - hub_radius + 2 * overlap
    spoke_center = (inner_radius + hub_radius) / 2
    spoke_profile = ex.input_cell(
        "spoke_profile",
        Face.make_rect(spoke_length, spoke_width),
        ambient_dimension=3,
        intrinsic_dimension=2,
        kind="region",
    )
    spokes: list[CadEntity] = []
    for index in range(spoke_count):
        angle_degrees = 360 * index / spoke_count
        angle = math.radians(angle_degrees)
        placed = ex.transform(
            spoke_profile,
            f"spoke_profile_{index + 1}",
            rotation_axis=Axis.Z,
            angle_degrees=angle_degrees,
            translation=(spoke_center * math.cos(angle), spoke_center * math.sin(angle), 0),
        )
        spokes.append(ex.linear_sweep(placed, f"spoke_{index + 1}", (0, 0, thickness)))
    part = ex.combine("union", [rim, hub, *spokes], "finished_spoked_wheel")
    part = ex.constrain(part, "valid_brep", _valid, expected=True)
    part = ex.constrain(part, "single_solid", _solid_count, expected=1)
    part = ex.constrain(
        part,
        "positive_volume",
        lambda shape: (shape.volume > 0, shape.volume),
        expected="> 0",
    )
    part = ex.annotate(
        part,
        "nominal_dimensions",
        outer_diameter=2 * outer_radius,
        bore_diameter=2 * bore_radius,
        thickness=thickness,
        spoke_width=spoke_width,
        spoke_count=spoke_count,
    )
    return EngineeringPart(
        "spoked_wheel",
        "Six-spoke wheel",
        part,
        ex.program,
        {
            "outer_diameter": 2 * outer_radius,
            "bore_diameter": 2 * bore_radius,
            "thickness": thickness,
            "spoke_width": spoke_width,
            "spoke_count": spoke_count,
        },
        ex.constraint_results,
        section_plane="XZ",
        metadata={
            "family": "annular sweeps + repeated radial transforms + union",
            "evaluation_role": "topology_holdout",
            "drawing_notes": [
                f"OD {2 * outer_radius:g}   BORE {2 * bore_radius:g}",
                f"{spoke_count} SPOKES x {spoke_width:g}",
                f"THICKNESS {thickness:g}",
            ],
        },
    )


def build_clevis_bracket(
    *,
    base_width: float = 54.0,
    base_depth: float = 42.0,
    base_thickness: float = 6.0,
    lug_width: float = 24.0,
    lug_height: float = 34.0,
    lug_thickness: float = 6.0,
    lug_gap: float = 16.0,
    pin_radius: float = 4.0,
) -> EngineeringPart:
    b3d = _load_build123d()
    Axis, Face, Plane, Wire = b3d["Axis"], b3d["Face"], b3d["Plane"], b3d["Wire"]
    ex = CadExecutor("clevis_bracket")

    base_profile = ex.input_cell(
        "base_profile",
        Face.make_rect(base_width, base_depth),
        ambient_dimension=3,
        intrinsic_dimension=2,
        kind="region",
    )
    base = ex.linear_sweep(base_profile, "base", (0, 0, base_thickness))
    lug_seed = ex.input_cell(
        "lug_profile_xy",
        Face.make_rect(lug_width, lug_height),
        ambient_dimension=3,
        intrinsic_dimension=2,
        kind="region",
    )
    lugs: list[CadEntity] = []
    for name, start_y in (
        ("left", -lug_gap / 2 - lug_thickness),
        ("right", lug_gap / 2),
    ):
        profile = ex.transform(
            lug_seed,
            f"{name}_lug_profile",
            rotation_axis=Axis.X,
            angle_degrees=90,
            translation=(0, start_y, base_thickness + lug_height / 2),
        )
        lugs.append(ex.linear_sweep(profile, f"{name}_lug", (0, lug_thickness, 0)))
    body = ex.combine("union", [base, *lugs], "clevis_body")

    pin_profile = ex.input_cell(
        "pin_hole_profile",
        Face(Wire.make_circle(pin_radius, Plane.XZ)),
        ambient_dimension=3,
        intrinsic_dimension=2,
        kind="region",
    )
    pin_profile = ex.transform(
        pin_profile,
        "pin_hole_profile_placed",
        translation=(0, -base_depth / 2, base_thickness + 0.68 * lug_height),
    )
    pin_hole = ex.linear_sweep(pin_profile, "pin_hole", (0, base_depth, 0))
    part = ex.combine("difference", [body, pin_hole], "finished_clevis")
    part = ex.constrain(part, "valid_brep", _valid, expected=True)
    part = ex.constrain(part, "single_solid", _solid_count, expected=1)
    part = ex.constrain(
        part,
        "positive_volume",
        lambda shape: (shape.volume > 0, shape.volume),
        expected="> 0",
    )
    part = ex.annotate(
        part,
        "nominal_dimensions",
        base_width=base_width,
        base_depth=base_depth,
        lug_height=lug_height,
        lug_gap=lug_gap,
        pin_diameter=2 * pin_radius,
    )
    return EngineeringPart(
        "clevis_bracket",
        "Twin-lug clevis bracket",
        part,
        ex.program,
        {
            "base_width": base_width,
            "base_depth": base_depth,
            "lug_height": lug_height,
            "lug_gap": lug_gap,
            "pin_diameter": 2 * pin_radius,
        },
        ex.constraint_results,
        section_plane="YZ",
        metadata={
            "family": "orthogonal sweeps + union + transverse subtraction",
            "evaluation_role": "topology_holdout",
            "drawing_notes": [
                f"BASE {base_width:g} x {base_depth:g} x {base_thickness:g}",
                f"LUG HEIGHT {lug_height:g}   GAP {lug_gap:g}",
                f"THRU PIN HOLE {2 * pin_radius:g}",
            ],
        },
    )


def build_cross_drilled_manifold(
    *,
    width: float = 58.0,
    depth: float = 44.0,
    height: float = 34.0,
    vertical_bore_radius: float = 5.0,
    cross_bore_radius: float = 4.0,
) -> EngineeringPart:
    b3d = _load_build123d()
    Face, Plane, Wire = b3d["Face"], b3d["Plane"], b3d["Wire"]
    ex = CadExecutor("cross_drilled_manifold")

    body_profile = ex.input_cell(
        "block_profile",
        Face.make_rect(width, depth),
        ambient_dimension=3,
        intrinsic_dimension=2,
        kind="region",
    )
    body = ex.linear_sweep(body_profile, "block", (0, 0, height))

    vertical_profile = ex.input_cell(
        "vertical_bore_profile",
        Face(Wire.make_circle(vertical_bore_radius)),
        ambient_dimension=3,
        intrinsic_dimension=2,
        kind="region",
    )
    vertical = ex.linear_sweep(vertical_profile, "vertical_bore", (0, 0, height))
    x_profile = ex.input_cell(
        "x_bore_profile",
        Face(Wire.make_circle(cross_bore_radius, Plane.YZ)),
        ambient_dimension=3,
        intrinsic_dimension=2,
        kind="region",
    )
    x_profile = ex.transform(
        x_profile,
        "x_bore_profile_placed",
        translation=(-width / 2, 0, height / 2),
    )
    x_bore = ex.linear_sweep(x_profile, "x_bore", (width, 0, 0))
    y_profile = ex.input_cell(
        "y_bore_profile",
        Face(Wire.make_circle(cross_bore_radius, Plane.XZ)),
        ambient_dimension=3,
        intrinsic_dimension=2,
        kind="region",
    )
    y_profile = ex.transform(
        y_profile,
        "y_bore_profile_placed",
        translation=(0, -depth / 2, height / 2),
    )
    y_bore = ex.linear_sweep(y_profile, "y_bore", (0, depth, 0))
    part = ex.combine(
        "difference",
        [body, vertical, x_bore, y_bore],
        "finished_manifold",
    )
    part = ex.constrain(part, "valid_brep", _valid, expected=True)
    part = ex.constrain(part, "single_solid", _solid_count, expected=1)
    part = ex.constrain(
        part,
        "positive_volume",
        lambda shape: (shape.volume > 0, shape.volume),
        expected="> 0",
    )
    part = ex.annotate(
        part,
        "nominal_dimensions",
        width=width,
        depth=depth,
        height=height,
        vertical_bore_diameter=2 * vertical_bore_radius,
        cross_bore_diameter=2 * cross_bore_radius,
    )
    return EngineeringPart(
        "cross_drilled_manifold",
        "Three-axis manifold block",
        part,
        ex.program,
        {
            "width": width,
            "depth": depth,
            "height": height,
            "vertical_bore_diameter": 2 * vertical_bore_radius,
            "cross_bore_diameter": 2 * cross_bore_radius,
        },
        ex.constraint_results,
        section_plane="XZ",
        metadata={
            "family": "prismatic sweep + three orthogonal subtractions",
            "evaluation_role": "topology_holdout",
            "drawing_notes": [
                f"BLOCK {width:g} x {depth:g} x {height:g}",
                f"VERTICAL BORE {2 * vertical_bore_radius:g}",
                f"2 x CROSS BORE {2 * cross_bore_radius:g}",
            ],
        },
    )


PART_BUILDERS: dict[str, Callable[..., EngineeringPart]] = {
    "flange": build_flange,
    "stepped_shaft": build_stepped_shaft,
    "angle_bracket": build_angle_bracket,
    "transition_duct": build_transition_duct,
    "lattice_panel": build_lattice_panel,
}

TOPOLOGY_HOLDOUT_BUILDERS: dict[str, Callable[..., EngineeringPart]] = {
    "spoked_wheel": build_spoked_wheel,
    "clevis_bracket": build_clevis_bracket,
    "cross_drilled_manifold": build_cross_drilled_manifold,
}


def _shape_edges(shape: Any) -> list[Any]:
    if shape is None:
        return []
    return list(shape.edges()) if hasattr(shape, "edges") else []


def _translated(edges: Iterable[Any], origin: tuple[float, float]) -> list[Any]:
    return [edge.translate((origin[0], origin[1], 0)) for edge in edges]


def _view_bbox(edges: Sequence[Any], Compound: Any) -> Any:
    return Compound(list(edges)).bounding_box()


def _fit_scale(
    bbox: Any,
    page_box: tuple[float, float, float, float],
    *,
    padding: float = 5.0,
    maximum: float = 1.5,
) -> float:
    min_x, min_y, max_x, max_y = page_box
    available_width = max_x - min_x - 2 * padding
    available_height = max_y - min_y - 2 * padding
    width = max(float(bbox.size.X), 1e-9)
    height = max(float(bbox.size.Y), 1e-9)
    return min(maximum, available_width / width, available_height / height)


def _place_shapes(
    shapes: Iterable[Any],
    source_bbox: Any,
    page_box: tuple[float, float, float, float],
    scale: float,
    Compound: Any,
) -> tuple[list[Any], DrawingPlacement]:
    min_x, min_y, max_x, max_y = page_box
    target_x = (min_x + max_x) / 2
    target_y = (min_y + max_y) / 2
    source_center = source_bbox.center()
    translation = (target_x - source_center.X, target_y - source_center.Y)
    placed = [
        shape.scale(scale, about=(source_center.X, source_center.Y, 0)).translate(
            (translation[0], translation[1], 0)
        )
        for shape in shapes
    ]
    placed_bbox = _view_bbox(placed, Compound)
    return placed, DrawingPlacement(scale, translation, placed_bbox)


def _hatch_faces(
    faces: Iterable[Any],
    Edge: Any,
    *,
    spacing: float = 4.0,
    angle_degrees: float = 45.0,
) -> list[Any]:
    """Clip parallel hatch lines against exact section faces."""

    angle = math.radians(angle_degrees)
    direction = (math.cos(angle), math.sin(angle))
    normal = (-direction[1], direction[0])
    hatches: list[Any] = []
    for face in faces:
        bbox = face.bounding_box()
        center = bbox.center()
        corners = [
            (bbox.min.X, bbox.min.Y),
            (bbox.min.X, bbox.max.Y),
            (bbox.max.X, bbox.min.Y),
            (bbox.max.X, bbox.max.Y),
        ]
        projected = [x * normal[0] + y * normal[1] for x, y in corners]
        center_projection = center.X * normal[0] + center.Y * normal[1]
        start = math.floor((min(projected) - center_projection) / spacing) * spacing
        stop = math.ceil((max(projected) - center_projection) / spacing) * spacing
        diagonal = math.hypot(bbox.size.X, bbox.size.Y) + 2 * spacing
        offset = start
        while offset <= stop + 1e-9:
            line_center = (
                center.X + normal[0] * offset,
                center.Y + normal[1] * offset,
            )
            line = Edge.make_line(
                (
                    line_center[0] - direction[0] * diagonal,
                    line_center[1] - direction[1] * diagonal,
                ),
                (
                    line_center[0] + direction[0] * diagonal,
                    line_center[1] + direction[1] * diagonal,
                ),
            )
            clipped = line.intersect(face)
            if clipped is not None and hasattr(clipped, "edges"):
                hatches.extend(clipped.edges())
            offset += spacing
    return hatches


def _center_lines(bbox: Any, Edge: Any, margin: float = 3.0) -> list[Any]:
    center = bbox.center()
    return [
        Edge.make_line((bbox.min.X - margin, center.Y), (bbox.max.X + margin, center.Y)),
        Edge.make_line((center.X, bbox.min.Y - margin), (center.X, bbox.max.Y + margin)),
    ]


def _dimension_pair(
    bbox: Any,
    *,
    horizontal_label: str,
    vertical_label: str,
    ExtensionLine: Any,
    Edge: Any,
    Draft: Any,
) -> list[Any]:
    draft = Draft(font_size=2.8, decimal_precision=1, display_units=False, line_width=0.22)
    horizontal = Edge.make_line(
        (bbox.min.X, bbox.max.Y),
        (bbox.max.X, bbox.max.Y),
    )
    vertical = Edge.make_line(
        (bbox.max.X, bbox.min.Y),
        (bbox.max.X, bbox.max.Y),
    )
    return [
        ExtensionLine(
            border=horizontal,
            offset=(0, 8),
            draft=draft,
            label=horizontal_label,
        ),
        ExtensionLine(
            border=vertical,
            offset=(8, 0),
            draft=draft,
            label=vertical_label,
        ),
    ]


def export_part_artifacts(part: EngineeringPart, output_dir: Path) -> dict[str, Any]:
    """Export STEP, STL, B-rep-derived drawings, and a replay manifest."""

    b3d = _load_build123d()
    (
        Compound,
        Draft,
        Edge,
        ExtensionLine,
        ExportDXF,
        ExportSVG,
        LineType,
        PageSize,
        Plane,
        Pos,
        TechnicalDrawing,
        Text,
        Unit,
        export_step,
        section,
    ) = (
        b3d["Compound"],
        b3d["Draft"],
        b3d["Edge"],
        b3d["ExtensionLine"],
        b3d["ExportDXF"],
        b3d["ExportSVG"],
        b3d["LineType"],
        b3d["PageSize"],
        b3d["Plane"],
        b3d["Pos"],
        b3d["TechnicalDrawing"],
        b3d["Text"],
        b3d["Unit"],
        b3d["export_step"],
        b3d["section"],
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    step_path = output_dir / f"{part.part_id}.step"
    stl_path = output_dir / f"{part.part_id}.stl"
    svg_path = output_dir / f"{part.part_id}-drawing.svg"
    dxf_path = output_dir / f"{part.part_id}-drawing.dxf"
    manifest_path = output_dir / f"{part.part_id}.json"

    timings: dict[str, float] = {}
    stage_started = time.perf_counter()
    export_step(part.entity.shape, step_path)
    timings["step_export"] = time.perf_counter() - stage_started

    # STEP remains the exact B-rep. STL is a display/manufacturing mesh, so an
    # explicit 0.05 mm chord tolerance avoids pathological over-tessellation of
    # long helical faces caused by the library's 0.001 mm default.
    stage_started = time.perf_counter()
    _export_stl_serial(
        part.entity.shape,
        stl_path,
        tolerance=0.05,
        angular_tolerance=0.15,
    )
    timings["stl_mesh_export"] = time.perf_counter() - stage_started

    # Third-angle layout. The lower-right quadrant is reserved for the title block.
    views = [
        DrawingViewSpec("TOP", (0, 0, 160), (0, 1, 0), (-184, 28, -24, 122), False),
        DrawingViewSpec("FRONT", (0, -160, 0), (0, 0, 1), (-184, -55, -24, 17), True),
        DrawingViewSpec("RIGHT", (160, 0, 0), (0, 0, 1), (-12, -55, 82, 17), True),
        DrawingViewSpec("ISOMETRIC", (150, -150, 120), (0, 0, 1), (30, 28, 184, 122), True),
    ]
    visible: list[Any] = []
    hidden: list[Any] = []
    centers: list[Any] = []
    labels: list[Any] = []
    dimensions: list[Any] = []
    section_fills: list[Any] = []
    section_hatches: list[Any] = []
    view_metrics: list[dict[str, Any]] = []

    stage_started = time.perf_counter()
    raw_views: list[tuple[DrawingViewSpec, list[Any], list[Any], Any]] = []
    for view in views:
        Drawing = b3d["Drawing"]
        drawing = Drawing(
            part.entity.shape,
            look_from=view.look_from,
            look_up=view.look_up,
            with_hidden=view.include_hidden,
        )
        part.program.apply(
            BasisOp.PROJECT,
            [part.entity.ref],
            f"drawing_{view.name.lower()}",
            GeometricType(2, 2, "drawing"),
            projection="orthographic",
            look_from=view.look_from,
            look_up=view.look_up,
            include_hidden=view.include_hidden,
        )
        vis = _shape_edges(drawing.visible_lines)
        hid = _shape_edges(drawing.hidden_lines)
        bbox = _view_bbox(vis, Compound)
        raw_views.append((view, vis, hid, bbox))
    timings["orthographic_hidden_line_projection"] = (
        time.perf_counter() - stage_started
    )

    orthographic_scale = min(
        _fit_scale(bbox, view.page_box, maximum=1.5)
        for view, _, _, bbox in raw_views[:3]
    )

    for index, (view, raw_vis, raw_hid, raw_bbox) in enumerate(raw_views):
        scale = (
            orthographic_scale
            if index < 3
            else _fit_scale(raw_bbox, view.page_box, maximum=1.35)
        )
        placed, placement = _place_shapes(
            [*raw_vis, *raw_hid], raw_bbox, view.page_box, scale, Compound
        )
        vis = placed[: len(raw_vis)]
        hid = placed[len(raw_vis) :]
        visible.extend(vis)
        hidden.extend(hid)
        bbox = _view_bbox(vis, Compound)
        centers.extend(_center_lines(bbox, Edge))
        label = Text(view.name, 3.3)
        labels.append(Pos(bbox.center().X, bbox.min.Y - 6) * label)
        view_metrics.append(
            {
                "name": view.name,
                "visible_edges": len(vis),
                "hidden_edges": len(hid),
                "bbox": {
                    "width": bbox.size.X,
                    "height": bbox.size.Y,
                },
                "source_bbox": {
                    "width": raw_bbox.size.X,
                    "height": raw_bbox.size.Y,
                },
                "drawing_scale": placement.scale,
                "page_box": list(view.page_box),
            }
        )
        if index == 1:
            dimensions.extend(
                _dimension_pair(
                    bbox,
                    horizontal_label=f"{raw_bbox.size.X:.1f}",
                    vertical_label=f"{raw_bbox.size.Y:.1f}",
                    ExtensionLine=ExtensionLine,
                    Edge=Edge,
                    Draft=Draft,
                )
            )

    stage_started = time.perf_counter()
    section_plane = getattr(Plane, part.section_plane)
    raw_section = section(part.entity.shape, section_plane)
    part.program.apply(
        BasisOp.SLICE,
        [part.entity.ref],
        f"section_{part.section_plane.lower()}",
        GeometricType(3, 2, "section"),
        codimension=1,
        plane=part.section_plane,
    )
    local_section = section_plane.to_local_coords(raw_section)
    local_faces = list(local_section.faces())
    local_edges = _shape_edges(local_section)
    raw_hatches = _hatch_faces(local_faces, Edge)
    section_box = (-184, -121, -18, -71)
    if local_edges:
        local_bbox = _view_bbox(local_edges, Compound)
        section_scale = min(
            orthographic_scale,
            _fit_scale(local_bbox, section_box, maximum=orthographic_scale),
        )
        section_edges, section_placement = _place_shapes(
            local_edges, local_bbox, section_box, section_scale, Compound
        )
        section_fills, _ = _place_shapes(
            local_faces, local_bbox, section_box, section_scale, Compound
        )
        section_hatches, _ = _place_shapes(
            raw_hatches, local_bbox, section_box, section_scale, Compound
        )
        visible.extend(section_edges)
        section_bbox = _view_bbox(section_edges, Compound)
        label = Text(f"SECTION {part.section_plane}", 3.3)
        labels.append(Pos(section_bbox.center().X, section_bbox.min.Y - 6) * label)
    else:
        section_bbox = None
        section_placement = None
    timings["section_and_hatching"] = time.perf_counter() - stage_started

    note_lines = ["NOMINAL DIMENSIONS", *part.metadata.get("drawing_notes", [])]
    for index, note in enumerate(note_lines):
        labels.append(Pos(103, 8 - index * 6) * Text(note, 2.7))

    border = TechnicalDrawing(
        designed_by="MORTRA",
        design_date=date.today(),
        page_size=PageSize.A3,
        title=part.title,
        sub_title="THIRD-ANGLE PROJECTION / UNITS: mm",
        drawing_number=f"MORTRA-{part.part_id.upper()}",
        sheet_number=1,
        drawing_scale=1,
        nominal_text_size=5,
        line_width=0.28,
    )
    svg = ExportSVG(unit=Unit.MM, line_weight=0.28, margin=3)
    svg.add_layer("section-fill", fill_color="#e8eef1", line_color=None, line_weight=0.0)
    svg.add_layer("hidden", line_color="#7a8792", line_weight=0.18, line_type=LineType.HIDDEN)
    svg.add_layer("center", line_color="#2b6170", line_weight=0.16, line_type=LineType.ISO_LONG_DASH_DOT)
    svg.add_layer("hatch", line_color="#52636d", line_weight=0.13)
    svg.add_layer("visible", fill_color=None, line_color="#0b1520", line_weight=0.30)
    svg.add_layer("text", fill_color="#0b1520", line_color=None, line_weight=0.0)
    svg.add_layer("dimensions", fill_color="#0b1520", line_color="#0b1520", line_weight=0.18)
    svg.add_shape(section_fills, layer="section-fill")
    svg.add_shape(hidden, layer="hidden")
    svg.add_shape(centers, layer="center")
    svg.add_shape(section_hatches, layer="hatch")
    svg.add_shape(border, layer="visible")
    svg.add_shape(border.faces(), layer="text")
    svg.add_shape(visible, layer="visible")
    svg.add_shape([*labels, *dimensions], layer="dimensions")
    stage_started = time.perf_counter()
    svg.write(svg_path)
    timings["svg_export"] = time.perf_counter() - stage_started

    dxf = ExportDXF(unit=Unit.MM, line_weight=0.28)
    dxf.add_layer("visible", line_weight=0.30)
    dxf.add_layer("hidden", line_weight=0.18, line_type=LineType.HIDDEN)
    dxf.add_layer("center", line_weight=0.13, line_type=LineType.ISO_LONG_DASH_DOT)
    dxf.add_layer("hatch", line_weight=0.13)
    dxf.add_layer("dimensions", line_weight=0.18)
    dxf.add_shape(border, layer="visible")
    dxf.add_shape(visible, layer="visible")
    dxf.add_shape(hidden, layer="hidden")
    dxf.add_shape(centers, layer="center")
    dxf.add_shape(section_hatches, layer="hatch")
    dxf.add_shape([*labels, *dimensions], layer="dimensions")
    stage_started = time.perf_counter()
    dxf.write(dxf_path)
    timings["dxf_export"] = time.perf_counter() - stage_started

    bbox = part.entity.shape.bounding_box()
    manifest = {
        "part_id": part.part_id,
        "title": part.title,
        "passed": part.passed,
        "kernel": "build123d/OpenCascade exact B-rep",
        "dimensions_mm": part.nominal_dimensions_mm,
        "geometry": {
            "volume_mm3": part.entity.shape.volume,
            "surface_area_mm2": part.entity.shape.area,
            "solid_count": len(part.entity.shape.solids()),
            "face_count": len(part.entity.shape.faces()),
            "edge_count": len(part.entity.shape.edges()),
            "bbox_mm": [bbox.size.X, bbox.size.Y, bbox.size.Z],
            "is_valid": bool(part.entity.shape.is_valid),
        },
        "checks": [check.__dict__ for check in part.checks],
        "views": view_metrics,
        "section": {
            "plane": part.section_plane,
            "face_count": len(raw_section.faces()),
            "area_mm2": raw_section.area,
            "hatch_segment_count": len(section_hatches),
            "drawing_scale": section_placement.scale if section_placement else None,
            "page_box": list(section_box),
        },
        "program": part.program.to_dict(),
        "metadata": part.metadata,
        "mesh": {
            "format": "STL",
            "exporter": "OpenCascade serial BRepMesh + StlAPI_Writer",
            "linear_deflection_mm": 0.05,
            "angular_deflection_rad": 0.15,
            "file_size_bytes": stl_path.stat().st_size,
        },
        "timings_seconds": timings,
        "artifacts": {
            "step": step_path.name,
            "stl": stl_path.name,
            "svg": svg_path.name,
            "dxf": dxf_path.name,
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def export_exact_shape_artifact(
    part: EngineeringPart, output_dir: Path
) -> dict[str, Any]:
    """Export an exact STEP and replay certificate without forcing tessellation.

    Smooth path sweeps can be exact and valid while being prohibitively slow to
    mesh in the pinned Windows OCP build.  This profile records that distinction
    instead of treating an unfinished STL or drawing as a successful artifact.
    """

    output_dir.mkdir(parents=True, exist_ok=True)
    step_path = output_dir / f"{part.part_id}.step"
    manifest_path = output_dir / f"{part.part_id}.json"
    export_step = _load_build123d()["export_step"]
    started = time.perf_counter()
    export_step(part.entity.shape, step_path)
    elapsed = time.perf_counter() - started
    bbox = part.entity.shape.bounding_box()
    manifest = {
        "part_id": part.part_id,
        "title": part.title,
        "passed": part.passed,
        "artifact_profile": "exact_shape_only",
        "kernel": "build123d/OpenCascade exact B-rep",
        "dimensions_mm": part.nominal_dimensions_mm,
        "geometry": {
            "volume_mm3": part.entity.shape.volume,
            "surface_area_mm2": part.entity.shape.area,
            "solid_count": len(part.entity.shape.solids()),
            "face_count": len(part.entity.shape.faces()),
            "edge_count": len(part.entity.shape.edges()),
            "bbox_mm": [bbox.size.X, bbox.size.Y, bbox.size.Z],
            "is_valid": bool(part.entity.shape.is_valid),
        },
        "checks": [check.__dict__ for check in part.checks],
        "views": [],
        "section": None,
        "program": part.program.to_dict(),
        "metadata": part.metadata,
        "timings_seconds": {"step_export": elapsed},
        "artifacts": {"step": step_path.name},
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def build_all_parts() -> list[EngineeringPart]:
    return [builder() for builder in PART_BUILDERS.values()]
