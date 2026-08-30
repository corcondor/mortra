"""Dimension-indexed geometry IR for engineering construction and drawings.

The IR deliberately keeps the operator vocabulary small.  Named CAD features such
as ``Extrude``, ``Revolve`` and ``Loft`` are parameters of ``SWEEP`` rather than
independent primitive morphisms.  Likewise, orthographic views and section views
are instances of ``PROJECT`` and ``SLICE``.

This module has no CAD-kernel dependency.  A backend may execute the same program
with OpenCascade, a symbolic kernel, a robot planner, or an n-dimensional research
backend.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Iterable


class BasisOp(str, Enum):
    """The reusable morphism basis.

    ``INPUT`` is intentionally absent.  Input cells and equations are mathematical
    data, while the entries below are operations on that data.
    """

    TRANSFORM = "transform"
    SWEEP = "sweep"
    COMBINE = "combine"
    SELECT = "select"
    SLICE = "slice"
    PROJECT = "project"
    CONSTRAIN = "constrain"
    ANNOTATE = "annotate"


@dataclass(frozen=True)
class GeometricType:
    """A k-dimensional cell embedded in an n-dimensional ambient space."""

    ambient_dimension: int
    intrinsic_dimension: int
    kind: str = "cell"

    def __post_init__(self) -> None:
        if self.ambient_dimension < 0:
            raise ValueError("ambient_dimension must be non-negative")
        if not 0 <= self.intrinsic_dimension <= self.ambient_dimension:
            raise ValueError(
                "intrinsic_dimension must lie between 0 and ambient_dimension"
            )

    @property
    def codimension(self) -> int:
        return self.ambient_dimension - self.intrinsic_dimension


@dataclass(frozen=True)
class EntityRef:
    name: str
    geometric_type: GeometricType
    role: str = "geometry"


@dataclass(frozen=True)
class MorphismStep:
    step_id: str
    op: BasisOp
    inputs: tuple[str, ...]
    output: str
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConstructionProgram:
    """A typed, replayable feature DAG."""

    program_id: str
    entities: dict[str, EntityRef] = field(default_factory=dict)
    steps: list[MorphismStep] = field(default_factory=list)

    def declare(
        self,
        name: str,
        geometric_type: GeometricType,
        *,
        role: str = "geometry",
    ) -> EntityRef:
        if name in self.entities:
            raise ValueError(f"duplicate entity: {name}")
        ref = EntityRef(name, geometric_type, role)
        self.entities[name] = ref
        return ref

    def apply(
        self,
        op: BasisOp,
        inputs: Iterable[EntityRef],
        output_name: str,
        output_type: GeometricType,
        **parameters: Any,
    ) -> EntityRef:
        input_refs = tuple(inputs)
        if output_name in self.entities:
            raise ValueError(f"duplicate entity: {output_name}")
        for ref in input_refs:
            if self.entities.get(ref.name) != ref:
                raise ValueError(f"undeclared input entity: {ref.name}")

        self._validate_signature(op, input_refs, output_type, parameters)
        output = self.declare(output_name, output_type)
        self.steps.append(
            MorphismStep(
                step_id=f"s{len(self.steps) + 1:03d}",
                op=op,
                inputs=tuple(ref.name for ref in input_refs),
                output=output_name,
                parameters=dict(parameters),
            )
        )
        return output

    @staticmethod
    def _validate_signature(
        op: BasisOp,
        inputs: tuple[EntityRef, ...],
        output: GeometricType,
        parameters: dict[str, Any],
    ) -> None:
        if not inputs:
            raise ValueError(f"{op.value} requires at least one input")
        source = inputs[0].geometric_type

        if op in {BasisOp.TRANSFORM, BasisOp.CONSTRAIN, BasisOp.ANNOTATE}:
            if len(inputs) != 1 or output != source:
                raise ValueError(f"{op.value} must preserve the geometric type")
            return

        if op is BasisOp.SWEEP:
            path_dimension = int(parameters.get("path_dimension", 1))
            expected_intrinsic = min(
                output.ambient_dimension,
                source.intrinsic_dimension + path_dimension,
            )
            if output.intrinsic_dimension != expected_intrinsic:
                raise ValueError(
                    "sweep output dimension must equal source dimension plus path "
                    "dimension, capped by the ambient dimension"
                )
            if output.ambient_dimension < source.ambient_dimension:
                raise ValueError("sweep cannot lower the ambient dimension")
            return

        if op is BasisOp.COMBINE:
            if len(inputs) < 2:
                raise ValueError("combine requires at least two inputs")
            if any(ref.geometric_type != source for ref in inputs[1:]):
                raise ValueError("combine inputs must have identical geometric types")
            if output != source:
                raise ValueError("combine must preserve the geometric type")
            return

        if op is BasisOp.SELECT:
            if output.ambient_dimension != source.ambient_dimension:
                raise ValueError("select must preserve ambient dimension")
            if output.intrinsic_dimension >= source.intrinsic_dimension:
                raise ValueError("select must return lower-dimensional features")
            return

        if op is BasisOp.SLICE:
            codimension = int(parameters.get("codimension", 1))
            if output.ambient_dimension != source.ambient_dimension:
                raise ValueError("slice preserves ambient coordinates")
            if output.intrinsic_dimension != source.intrinsic_dimension - codimension:
                raise ValueError("slice output dimension is inconsistent with codimension")
            return

        if op is BasisOp.PROJECT:
            if output.ambient_dimension >= source.ambient_dimension:
                raise ValueError("project must lower the ambient dimension")
            if output.intrinsic_dimension > min(
                source.intrinsic_dimension, output.ambient_dimension
            ):
                raise ValueError("project output has impossible intrinsic dimension")
            return

        raise ValueError(f"unsupported basis operation: {op}")

    def operator_histogram(self) -> dict[str, int]:
        counts = {op.value: 0 for op in BasisOp}
        for step in self.steps:
            counts[step.op.value] += 1
        return counts

    def to_dict(self) -> dict[str, Any]:
        return {
            "program_id": self.program_id,
            "basis_version": "engineering-geometry-8op-v1",
            "entities": {name: asdict(ref) for name, ref in self.entities.items()},
            "steps": [
                {
                    **asdict(step),
                    "op": step.op.value,
                }
                for step in self.steps
            ],
            "operator_histogram": self.operator_histogram(),
        }


LEGACY_CONSTRUCTION_ALIASES: dict[str, tuple[BasisOp, dict[str, Any]]] = {
    "Rotate3": (BasisOp.TRANSFORM, {"family": "rigid_rotation"}),
    "Extrude": (BasisOp.SWEEP, {"trajectory": "line"}),
    "Revolve": (BasisOp.SWEEP, {"trajectory": "circle"}),
    "Loft": (BasisOp.SWEEP, {"trajectory": "section_family"}),
    "Boundary": (BasisOp.SELECT, {"selector": "boundary"}),
    "CrossSection": (BasisOp.SLICE, {"slice": "affine_flat"}),
}


def basis_summary() -> dict[str, Any]:
    """Machine-readable statement of the compression boundary."""

    return {
        "basis": [op.value for op in BasisOp],
        "basis_size": len(BasisOp),
        "legacy_aliases": {
            name: {"op": op.value, **params}
            for name, (op, params) in LEGACY_CONSTRUCTION_ALIASES.items()
        },
        "dimension_policy": (
            "The operator set is independent of ambient dimension.  Concrete CAD "
            "backends may support only a subset such as R2 and R3."
        ),
    }
