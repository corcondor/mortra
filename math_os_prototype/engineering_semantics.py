"""Typed engineering assertions layered on the geometric construction DAG.

Geometry answers where a feature is.  Manufacturing drawings also need to say
what the feature means: material, tolerances, datums, joints, and applied loads.
Those facts do not create geometry, so they are represented by three reusable
assertion forms rather than new geometric morphisms.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json
from numbers import Real
from typing import Any, Mapping, Sequence


class AssertionForm(str, Enum):
    PROPERTY = "property"
    RELATION = "relation"
    ACTION = "action"


_PROPERTY_UNITS: dict[str, str | None] = {
    "material": None,
    "density": "kg/m^3",
    "manufacturing_process": None,
    "linear_tolerance": "mm",
    "angular_tolerance": "deg",
    "surface_roughness": "um",
}
_RELATION_SYMBOLS = frozenset({"datum", "joint"})
_ACTION_UNITS = {
    "force": "N",
    "moment": "N*mm",
}


def _action_component_count(symbol: str, ambient_dimension: int) -> int:
    if ambient_dimension < 1:
        raise ValueError("ambient dimension must be positive")
    if symbol == "force":
        return ambient_dimension
    if symbol == "moment":
        # In R^n a moment is an antisymmetric rank-2 tensor.  Its independent
        # components correspond to the coordinate planes (i, j), i < j.
        return ambient_dimension * (ambient_dimension - 1) // 2
    raise ValueError(f"unsupported engineering action: {symbol}")


def _is_number(value: Any) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool)


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
class EngineeringAssertion:
    form: AssertionForm
    symbol: str
    subject: str
    value: Any
    unit: str | None = None
    objects: tuple[str, ...] = ()
    frame: str = "global"

    def __post_init__(self) -> None:
        if not self.subject:
            raise ValueError("engineering assertion subject must not be empty")
        _json_value(self.value, path=f"assertion[{self.symbol}].value")

        if self.form is AssertionForm.PROPERTY:
            if self.symbol not in _PROPERTY_UNITS:
                raise ValueError(f"unsupported engineering property: {self.symbol}")
            expected_unit = _PROPERTY_UNITS[self.symbol]
            if self.unit != expected_unit:
                raise ValueError(
                    f"property {self.symbol} requires unit {expected_unit!r}"
                )
            if self.objects:
                raise ValueError("property assertions cannot have object entities")
            if self.symbol in {"material", "manufacturing_process"}:
                if not isinstance(self.value, str) or not self.value.strip():
                    raise ValueError(f"property {self.symbol} requires text")
            elif not _is_number(self.value) or float(self.value) <= 0:
                raise ValueError(f"property {self.symbol} requires a positive number")
            return

        if self.form is AssertionForm.RELATION:
            if self.symbol not in _RELATION_SYMBOLS:
                raise ValueError(f"unsupported engineering relation: {self.symbol}")
            if self.unit is not None:
                raise ValueError("relation assertions do not carry units")
            if not isinstance(self.value, str) or not self.value.strip():
                raise ValueError(f"relation {self.symbol} requires a text value")
            if self.symbol == "datum" and self.objects:
                raise ValueError("a datum assertion labels its subject directly")
            if self.symbol == "joint" and not self.objects:
                raise ValueError("a joint assertion requires at least one object entity")
            return

        if self.form is AssertionForm.ACTION:
            if self.symbol not in _ACTION_UNITS:
                raise ValueError(f"unsupported engineering action: {self.symbol}")
            expected_unit = _ACTION_UNITS[self.symbol]
            if self.unit != expected_unit:
                raise ValueError(
                    f"action {self.symbol} requires unit {expected_unit!r}"
                )
            if self.objects:
                raise ValueError("action assertions cannot have object entities")
            if not isinstance(self.value, (list, tuple)) or not self.value:
                raise ValueError(f"action {self.symbol} requires components")
            if not all(_is_number(item) for item in self.value):
                raise ValueError(f"action {self.symbol} components must be numeric")
            return

        raise ValueError(f"unsupported assertion form: {self.form}")

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "EngineeringAssertion":
        allowed = {"form", "symbol", "subject", "value", "unit", "objects", "frame"}
        unknown = sorted(set(payload) - allowed)
        if unknown:
            raise ValueError(f"engineering assertion contains unsupported fields: {unknown}")
        required = {"form", "symbol", "subject", "value"}
        missing = sorted(required - set(payload))
        if missing:
            raise ValueError(f"engineering assertion is missing fields: {missing}")
        return cls(
            form=AssertionForm(str(payload["form"])),
            symbol=str(payload["symbol"]),
            subject=str(payload["subject"]),
            value=payload["value"],
            unit=(str(payload["unit"]) if payload.get("unit") is not None else None),
            objects=tuple(str(item) for item in payload.get("objects", [])),
            frame=str(payload.get("frame", "global")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "form": self.form.value, "objects": list(self.objects)}


@dataclass(frozen=True)
class CompiledEngineeringSemantics:
    drawing_notes: tuple[str, ...]
    derived_values: dict[str, Any]
    constructor_histogram: dict[str, int]
    assertion_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "drawing_notes": list(self.drawing_notes),
            "derived_values": self.derived_values,
            "constructor_histogram": self.constructor_histogram,
            "assertion_hash": self.assertion_hash,
        }


class EngineeringSemanticGraph:
    """Validate and compile semantic assertions without changing geometry."""

    def __init__(self, assertions: Sequence[EngineeringAssertion]):
        self.assertions = tuple(assertions)

    def compile(
        self,
        *,
        ambient_dimensions: Mapping[str, int],
        measures: Mapping[str, Mapping[str, float]] | None = None,
    ) -> CompiledEngineeringSemantics:
        measures = measures or {}
        notes: list[str] = []
        derived: dict[str, Any] = {}
        histogram = {form.value: 0 for form in AssertionForm}
        properties: dict[tuple[str, str], EngineeringAssertion] = {}

        for assertion in self.assertions:
            if assertion.subject not in ambient_dimensions:
                raise ValueError(
                    f"engineering assertion references unknown entity: {assertion.subject}"
                )
            missing_objects = [
                name for name in assertion.objects if name not in ambient_dimensions
            ]
            if missing_objects:
                raise ValueError(
                    "engineering relation references unknown entities: "
                    f"{missing_objects}"
                )
            if assertion.form is AssertionForm.ACTION:
                ambient_dimension = ambient_dimensions[assertion.subject]
                expected = _action_component_count(
                    assertion.symbol,
                    ambient_dimension,
                )
                if len(assertion.value) != expected:
                    raise ValueError(
                        f"action {assertion.symbol} on {assertion.subject} has "
                        f"{len(assertion.value)} components; expected {expected} "
                        f"in ambient dimension {ambient_dimension}"
                    )
            if assertion.form is AssertionForm.PROPERTY:
                key = (assertion.subject, assertion.symbol)
                if key in properties:
                    raise ValueError(
                        f"duplicate property {assertion.symbol} on {assertion.subject}"
                    )
                properties[key] = assertion
            histogram[assertion.form.value] += 1
            notes.append(self._drawing_note(assertion))

        for (subject, symbol), density in properties.items():
            if symbol != "density":
                continue
            volume_mm3 = measures.get(subject, {}).get("volume_mm3")
            if volume_mm3 is None:
                continue
            mass_kg = float(volume_mm3) * 1e-9 * float(density.value)
            derived[f"{subject}.mass_kg"] = mass_kg
            notes.append(f"CALCULATED MASS: {mass_kg:.6g} kg")

        encoded = json.dumps(
            [assertion.to_dict() for assertion in self.assertions],
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return CompiledEngineeringSemantics(
            drawing_notes=tuple(notes),
            derived_values=derived,
            constructor_histogram=histogram,
            assertion_hash=hashlib.sha256(encoded).hexdigest(),
        )

    @staticmethod
    def _drawing_note(assertion: EngineeringAssertion) -> str:
        symbol = assertion.symbol
        if assertion.form is AssertionForm.PROPERTY:
            labels = {
                "material": "MATERIAL",
                "density": "DENSITY",
                "manufacturing_process": "PROCESS",
                "linear_tolerance": "GENERAL LINEAR TOLERANCE",
                "angular_tolerance": "GENERAL ANGULAR TOLERANCE",
                "surface_roughness": "SURFACE TEXTURE Ra",
            }
            suffix = f" {assertion.unit}" if assertion.unit else ""
            prefix = "±" if "tolerance" in symbol else ""
            return f"{labels[symbol]}: {prefix}{assertion.value}{suffix}"
        if assertion.form is AssertionForm.RELATION:
            if symbol == "datum":
                subject = assertion.subject.replace("_", " ").upper()
                return f"DATUM {assertion.value}: {subject}"
            subject = assertion.subject.replace("_", " ").upper()
            objects = ", ".join(
                name.replace("_", " ").upper() for name in assertion.objects
            )
            joint_kind = assertion.value.upper()
            return f"JOINT {joint_kind}: {subject} -> {objects}"
        components = ", ".join(f"{float(value):g}" for value in assertion.value)
        frame = assertion.frame.replace("_", " ").upper()
        subject = assertion.subject.replace("_", " ").upper()
        return (
            f"{symbol.upper()} [{frame}]: "
            f"({components}) {assertion.unit} ON {subject}"
        )
