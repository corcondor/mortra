"""Finite, serializable input language for MORTRA engineering geometry.

The OpenCascade backend still accepts native shapes for low-level research.  This
module is the public generative boundary: a program may only start from the
allowlisted cells below and may only compose MORTRA's eight basis operations.
No Python callback, arbitrary CAD object, or part-specific command can cross this
boundary.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

from .engineering_cad_backend import (
    CadEntity,
    CadExecutor,
    EngineeringPart,
    _close,
    _solid_count,
    _valid,
)
from .engineering_geometry_ir import BasisOp


SEED_KINDS = frozenset(
    {
        "disk",
        "rectangle",
        "polygon",
        "segment_path",
        "polyline_path",
        "circle_path",
        "helix_path",
        "sketch",
    }
)


def _json_value(value: Any, *, path: str) -> None:
    if value is None or isinstance(value, (bool, int, float, str)):
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _json_value(item, path=f"{path}[{index}]")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"{path} contains a non-string key")
            _json_value(item, path=f"{path}.{key}")
        return
    raise TypeError(f"{path} is not serializable data: {type(value).__name__}")


@dataclass(frozen=True)
class SeedSpec:
    name: str
    kind: str
    parameters: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.kind not in SEED_KINDS:
            raise ValueError(f"unknown seed kind: {self.kind}")
        _json_value(self.parameters, path=f"seed[{self.name}].parameters")


@dataclass(frozen=True)
class StepSpec:
    output: str
    op: BasisOp
    inputs: tuple[str, ...]
    parameters: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _json_value(self.parameters, path=f"step[{self.output}].parameters")


@dataclass(frozen=True)
class EngineeringProgramSpec:
    program_id: str
    seeds: tuple[SeedSpec, ...]
    steps: tuple[StepSpec, ...]
    output: str
    title: str = "Declarative engineering part"
    nominal_dimensions_mm: dict[str, float] = field(default_factory=dict)
    section_plane: str = "XZ"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _json_value(self.nominal_dimensions_mm, path="nominal_dimensions_mm")
        _json_value(self.metadata, path="metadata")
        known: set[str] = set()
        for seed in self.seeds:
            if seed.name in known:
                raise ValueError(f"duplicate entity: {seed.name}")
            known.add(seed.name)
        for step in self.steps:
            if step.output in known:
                raise ValueError(f"duplicate entity: {step.output}")
            missing = [name for name in step.inputs if name not in known]
            if missing:
                raise ValueError(
                    f"step {step.output} references unavailable inputs: {missing}"
                )
            known.add(step.output)
        if self.output not in known:
            raise ValueError(f"unknown output entity: {self.output}")

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "EngineeringProgramSpec":
        seeds = tuple(
            SeedSpec(
                name=str(item["name"]),
                kind=str(item["kind"]),
                parameters=dict(item.get("parameters", {})),
            )
            for item in payload.get("seeds", [])
        )
        steps = tuple(
            StepSpec(
                output=str(item["output"]),
                op=BasisOp(str(item["op"])),
                inputs=tuple(str(name) for name in item.get("inputs", [])),
                parameters=dict(item.get("parameters", {})),
            )
            for item in payload.get("steps", [])
        )
        return cls(
            program_id=str(payload["program_id"]),
            title=str(payload.get("title", "Declarative engineering part")),
            seeds=seeds,
            steps=steps,
            output=str(payload["output"]),
            nominal_dimensions_mm={
                str(key): float(value)
                for key, value in payload.get("nominal_dimensions_mm", {}).items()
            },
            section_plane=str(payload.get("section_plane", "XZ")),
            metadata=dict(payload.get("metadata", {})),
        )

    @classmethod
    def from_json(cls, path: Path) -> "EngineeringProgramSpec":
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "mortra-engineering-program-v1",
            "program_id": self.program_id,
            "title": self.title,
            "seeds": [
                {
                    "name": seed.name,
                    "kind": seed.kind,
                    "parameters": seed.parameters,
                }
                for seed in self.seeds
            ],
            "steps": [
                {
                    "output": step.output,
                    "op": step.op.value,
                    "inputs": list(step.inputs),
                    "parameters": step.parameters,
                }
                for step in self.steps
            ],
            "output": self.output,
            "nominal_dimensions_mm": self.nominal_dimensions_mm,
            "section_plane": self.section_plane,
            "metadata": self.metadata,
        }

    @property
    def stable_hash(self) -> str:
        encoded = json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


@dataclass
class DeclarativeCadResult:
    spec: EngineeringProgramSpec
    executor: CadExecutor
    entities: dict[str, CadEntity]
    drawings: dict[str, Any]

    @property
    def output(self) -> CadEntity:
        return self.entities[self.spec.output]

    def to_engineering_part(self) -> EngineeringPart:
        drawing_notes = [
            f"{name.replace('_', ' ').upper()}: {value:g} mm"
            for name, value in self.spec.nominal_dimensions_mm.items()
        ]
        metadata = {
            **self.spec.metadata,
            "program_schema": "mortra-engineering-program-v1",
            "program_hash": self.spec.stable_hash,
            "seed_kinds": sorted({seed.kind for seed in self.spec.seeds}),
            "arbitrary_native_input": False,
            "drawing_notes": drawing_notes,
        }
        return EngineeringPart(
            part_id=self.spec.program_id,
            title=self.spec.title,
            entity=self.output,
            program=self.executor.program,
            nominal_dimensions_mm=dict(self.spec.nominal_dimensions_mm),
            checks=list(self.executor.constraint_results),
            section_plane=self.spec.section_plane,
            metadata=metadata,
        )


class DeclarativeCadExecutor:
    """Interpret data-only programs through the existing eight-operation backend."""

    def execute(self, spec: EngineeringProgramSpec) -> DeclarativeCadResult:
        executor = CadExecutor(spec.program_id)
        entities: dict[str, CadEntity] = {}
        drawings: dict[str, Any] = {}
        for seed in spec.seeds:
            entities[seed.name] = self._make_seed(executor, seed)
        for step in spec.steps:
            inputs = [entities[name] for name in step.inputs]
            entity, drawing = self._apply_step(executor, step, inputs)
            entities[step.output] = entity
            if drawing is not None:
                drawings[step.output] = drawing
        return DeclarativeCadResult(spec, executor, entities, drawings)

    @staticmethod
    def _plane(
        b3d: Mapping[str, Any],
        name: str,
        offset: float = 0.0,
        frame: Mapping[str, Any] | None = None,
    ) -> Any:
        Plane = b3d["Plane"]
        if frame is not None:
            if "origin" not in frame or "z_dir" not in frame:
                raise ValueError("a plane frame requires origin and z_dir")
            kwargs = {
                "origin": tuple(float(value) for value in frame["origin"]),
                "z_dir": tuple(float(value) for value in frame["z_dir"]),
            }
            if "x_dir" in frame:
                kwargs["x_dir"] = tuple(float(value) for value in frame["x_dir"])
            plane = Plane(**kwargs)
            return plane.offset(offset) if offset else plane
        try:
            plane = {"XY": Plane.XY, "XZ": Plane.XZ, "YZ": Plane.YZ}[name]
        except KeyError as exc:
            raise ValueError(f"unsupported plane: {name}") from exc
        return plane.offset(offset) if offset else plane

    def _make_seed(self, executor: CadExecutor, seed: SeedSpec) -> CadEntity:
        b3d = executor.b3d
        Face, Wire, Edge = b3d["Face"], b3d["Wire"], b3d["Edge"]
        params = seed.parameters
        plane = self._plane(
            b3d,
            str(params.get("plane", "XY")),
            float(params.get("offset", 0.0)),
            params.get("frame"),
        )

        if seed.kind == "disk":
            radius = float(params["radius"])
            if radius <= 0:
                raise ValueError("disk radius must be positive")
            shape = Face(Wire.make_circle(radius, plane))
            intrinsic = 2
            kind = "region"
        elif seed.kind == "rectangle":
            width, height = float(params["width"]), float(params["height"])
            if width <= 0 or height <= 0:
                raise ValueError("rectangle dimensions must be positive")
            shape = Face.make_rect(width, height, plane)
            intrinsic = 2
            kind = "region"
        elif seed.kind == "polygon":
            points = [tuple(float(value) for value in point) for point in params["points"]]
            if len(points) < 3:
                raise ValueError("polygon requires at least three points")
            shape = Face(Wire.make_polygon(points))
            intrinsic = 2
            kind = "region"
        elif seed.kind == "segment_path":
            shape = Edge.make_line(tuple(params["start"]), tuple(params["end"]))
            intrinsic = 1
            kind = "path"
        elif seed.kind == "polyline_path":
            points = [tuple(float(value) for value in point) for point in params["points"]]
            if len(points) < 2:
                raise ValueError("polyline requires at least two points")
            shape = Wire.make_polygon(points, close=bool(params.get("close", False)))
            intrinsic = 1
            kind = "path"
        elif seed.kind == "circle_path":
            radius = float(params["radius"])
            if radius <= 0:
                raise ValueError("circle radius must be positive")
            shape = Wire.make_circle(radius, plane)
            intrinsic = 1
            kind = "path"
        elif seed.kind == "helix_path":
            shape = Edge.make_helix(
                pitch=float(params["pitch"]),
                height=float(params["height"]),
                radius=float(params["radius"]),
                center=tuple(params.get("center", (0.0, 0.0, 0.0))),
                normal=tuple(params.get("normal", (0.0, 0.0, 1.0))),
                angle=float(params.get("angle_degrees", 0.0)),
                lefthand=bool(params.get("lefthand", False)),
            )
            intrinsic = 1
            kind = "path"
        elif seed.kind == "sketch":
            commands = list(params.get("commands", []))
            if not commands:
                raise ValueError("sketch requires at least one command")

            def world_point(values: Any) -> tuple[float, float, float]:
                point = tuple(float(value) for value in values)
                if len(point) == 2:
                    converted = plane.from_local_coords((point[0], point[1], 0.0))
                    return (converted.X, converted.Y, converted.Z)
                if len(point) == 3:
                    return point
                raise ValueError("sketch points must have two or three coordinates")

            start = world_point(params["start"])
            current = start
            edges = []
            for command in commands:
                family = str(command["kind"])
                end = world_point(command["to"])
                if family == "line":
                    edge = Edge.make_line(current, end)
                elif family == "arc3":
                    edge = Edge.make_three_point_arc(
                        current, world_point(command["mid"]), end
                    )
                elif family == "radius_arc":
                    radius = float(command["radius"])
                    chord = tuple(end[i] - current[i] for i in range(3))
                    chord_length = math.sqrt(sum(value * value for value in chord))
                    if chord_length == 0 or 2 * abs(radius) < chord_length - 1e-12:
                        raise ValueError("arc radius cannot reach its endpoint")
                    half = chord_length / 2
                    sagitta = abs(radius) - math.sqrt(
                        max(0.0, radius * radius - half * half)
                    )
                    normal = plane.z_dir
                    perpendicular = (
                        normal.Y * chord[2] - normal.Z * chord[1],
                        normal.Z * chord[0] - normal.X * chord[2],
                        normal.X * chord[1] - normal.Y * chord[0],
                    )
                    perpendicular_length = math.sqrt(
                        sum(value * value for value in perpendicular)
                    )
                    sign = 1.0 if radius > 0 else -1.0
                    midpoint = tuple(
                        (current[i] + end[i]) / 2
                        + sign * sagitta * perpendicular[i] / perpendicular_length
                        for i in range(3)
                    )
                    edge = Edge.make_three_point_arc(current, midpoint, end)
                else:
                    raise ValueError(f"unsupported sketch command: {family}")
                edges.append(edge)
                current = end
            closed = bool(params.get("close", False))
            if closed and current != start:
                edges.append(Edge.make_line(current, start))
            wire = Wire(edges)
            if bool(params.get("filled", closed)):
                if not closed:
                    raise ValueError("an open sketch cannot be filled")
                shape = Face(wire)
                intrinsic = 2
                kind = "region"
            else:
                shape = wire
                intrinsic = 1
                kind = "path"
        else:  # SeedSpec validates this; kept as a closed-world guard.
            raise ValueError(f"unsupported seed kind: {seed.kind}")

        return executor.input_cell(
            seed.name,
            shape,
            ambient_dimension=3,
            intrinsic_dimension=intrinsic,
            kind=kind,
        )

    def _apply_step(
        self,
        executor: CadExecutor,
        step: StepSpec,
        inputs: list[CadEntity],
    ) -> tuple[CadEntity, Any | None]:
        params = step.parameters
        drawing = None
        if step.op is BasisOp.TRANSFORM:
            axis_name = params.get("rotation_axis")
            axis = None
            if axis_name is not None:
                Axis = executor.b3d["Axis"]
                try:
                    axis = {"X": Axis.X, "Y": Axis.Y, "Z": Axis.Z}[str(axis_name)]
                except KeyError as exc:
                    raise ValueError(f"unsupported rotation axis: {axis_name}") from exc
            mirror_name = params.get("mirror_plane")
            mirror_plane = (
                self._plane(executor.b3d, str(mirror_name))
                if mirror_name is not None
                else None
            )
            scale_value = params.get("scale")
            if isinstance(scale_value, list):
                scale_value = tuple(float(value) for value in scale_value)
            elif scale_value is not None:
                scale_value = float(scale_value)
            entity = executor.transform(
                inputs[0],
                step.output,
                translation=(
                    tuple(float(value) for value in params["translation"])
                    if "translation" in params
                    else None
                ),
                rotation_axis=axis,
                angle_degrees=float(params.get("angle_degrees", 0.0)),
                scale=scale_value,
                scale_about=tuple(
                    float(value) for value in params.get("scale_about", (0, 0, 0))
                ),
                mirror_plane=mirror_plane,
            )
        elif step.op is BasisOp.SWEEP:
            family = str(params["trajectory"])
            if family == "line":
                entity = executor.linear_sweep(
                    inputs[0],
                    step.output,
                    tuple(float(value) for value in params["vector"]),
                )
            elif family == "circle":
                Axis = executor.b3d["Axis"]
                axis_name = str(params.get("axis", "Z"))
                try:
                    axis = {"X": Axis.X, "Y": Axis.Y, "Z": Axis.Z}[axis_name]
                except KeyError as exc:
                    raise ValueError(f"unsupported rotary axis: {axis_name}") from exc
                entity = executor.rotary_sweep(
                    inputs[0],
                    step.output,
                    axis=axis,
                    angle_degrees=float(params.get("angle_degrees", 360.0)),
                )
            elif family == "section_family":
                entity = executor.loft_sweep(
                    inputs,
                    step.output,
                    ruled=bool(params.get("ruled", False)),
                )
            elif family == "explicit_path":
                if len(inputs) != 2:
                    raise ValueError("explicit_path sweep requires profile and path")
                entity = executor.path_sweep(
                    inputs[0],
                    inputs[1],
                    step.output,
                    is_frenet=bool(params.get("is_frenet", False)),
                )
            else:
                raise ValueError(f"unsupported sweep trajectory: {family}")
        elif step.op is BasisOp.COMBINE:
            entity = executor.combine(str(params["operation"]), inputs, step.output)
        elif step.op is BasisOp.SELECT:
            entity = executor.select(
                inputs[0], step.output, selector=str(params["selector"])
            )
        elif step.op is BasisOp.SLICE:
            plane = self._plane(
                executor.b3d,
                str(params.get("plane", "XZ")),
                float(params.get("offset", 0.0)),
            )
            entity = executor.slice(inputs[0], step.output, plane)
        elif step.op is BasisOp.PROJECT:
            entity, drawing = executor.project(
                inputs[0],
                step.output,
                look_from=tuple(float(value) for value in params["look_from"]),
                look_up=tuple(float(value) for value in params["look_up"]),
                include_hidden=bool(params.get("include_hidden", True)),
            )
        elif step.op is BasisOp.CONSTRAIN:
            entity = self._constrain(executor, step, inputs[0])
        elif step.op is BasisOp.ANNOTATE:
            entity = executor.annotate(
                inputs[0],
                str(params.get("name", "metadata")),
                output_name=step.output,
                **dict(params.get("fields", {})),
            )
        else:  # pragma: no cover - exhaustive BasisOp guard
            raise ValueError(f"unsupported operation: {step.op.value}")
        return entity, drawing

    @staticmethod
    def _constrain(
        executor: CadExecutor,
        step: StepSpec,
        entity: CadEntity,
    ) -> CadEntity:
        params = step.parameters
        predicate_name = str(params["predicate"])
        tolerance = (
            float(params["tolerance"]) if "tolerance" in params else None
        )
        if predicate_name == "valid_brep":
            predicate = _valid
            expected: Any = True
        elif predicate_name == "single_solid":
            predicate = _solid_count
            expected = 1
        elif predicate_name == "positive_volume":
            predicate = lambda shape: (shape.volume > 0, shape.volume)
            expected = "> 0"
        elif predicate_name == "volume_close":
            expected = float(params["expected"])
            tolerance = tolerance if tolerance is not None else 1e-6
            predicate = lambda shape: _close(shape.volume, expected, tolerance)
        else:
            raise ValueError(f"unsupported constraint predicate: {predicate_name}")
        return executor.constrain(
            entity,
            predicate_name,
            predicate,
            expected=expected,
            tolerance=tolerance,
            description=str(params.get("description", "")),
            output_name=step.output,
        )
