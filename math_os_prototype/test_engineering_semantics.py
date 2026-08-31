from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from math_os_prototype.engineering_program_spec import (
    DeclarativeCadExecutor,
    EngineeringProgramSpec,
)
from math_os_prototype.engineering_semantics import (
    EngineeringAssertion,
    EngineeringSemanticGraph,
)


ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data" / "engineering_programs"


def test_three_assertion_forms_cover_properties_relations_and_actions() -> None:
    assertions = [
        EngineeringAssertion.from_dict(
            {
                "form": "property",
                "symbol": "material",
                "subject": "solid",
                "value": "Al 6061-T6",
            }
        ),
        EngineeringAssertion.from_dict(
            {
                "form": "relation",
                "symbol": "datum",
                "subject": "base_face",
                "value": "A",
            }
        ),
        EngineeringAssertion.from_dict(
            {
                "form": "relation",
                "symbol": "joint",
                "subject": "solid",
                "objects": ["bolt"],
                "value": "bolted",
            }
        ),
        EngineeringAssertion.from_dict(
            {
                "form": "action",
                "symbol": "force",
                "subject": "load_point",
                "value": [0, 0, -500],
                "unit": "N",
            }
        ),
    ]
    compiled = EngineeringSemanticGraph(assertions).compile(
        ambient_dimensions={
            "solid": 3,
            "base_face": 3,
            "bolt": 3,
            "load_point": 3,
        }
    )
    assert compiled.constructor_histogram == {
        "property": 1,
        "relation": 2,
        "action": 1,
    }
    assert len(compiled.assertion_hash) == 64
    assert any("MATERIAL" in note for note in compiled.drawing_notes)
    assert any("DATUM A" in note for note in compiled.drawing_notes)
    assert any("JOINT BOLTED" in note for note in compiled.drawing_notes)
    assert any("FORCE" in note for note in compiled.drawing_notes)


def test_density_derives_mass_without_a_geometry_operation() -> None:
    density = EngineeringAssertion.from_dict(
        {
            "form": "property",
            "symbol": "density",
            "subject": "solid",
            "value": 2700,
            "unit": "kg/m^3",
        }
    )
    compiled = EngineeringSemanticGraph([density]).compile(
        ambient_dimensions={"solid": 3},
        measures={"solid": {"volume_mm3": 1_000_000}},
    )
    assert compiled.derived_values["solid.mass_kg"] == pytest.approx(2.7)


def test_action_dimension_is_checked_in_any_ambient_dimension() -> None:
    action = EngineeringAssertion.from_dict(
        {
            "form": "action",
            "symbol": "force",
            "subject": "cell",
            "value": [1, 2, 3, 4],
            "unit": "N",
        }
    )
    EngineeringSemanticGraph([action]).compile(ambient_dimensions={"cell": 4})
    with pytest.raises(ValueError, match="expected 3"):
        EngineeringSemanticGraph([action]).compile(ambient_dimensions={"cell": 3})


def test_moment_uses_bivector_component_count_in_higher_dimensions() -> None:
    moment = EngineeringAssertion.from_dict(
        {
            "form": "action",
            "symbol": "moment",
            "subject": "cell",
            "value": [1, 2, 3, 4, 5, 6],
            "unit": "N*mm",
        }
    )
    EngineeringSemanticGraph([moment]).compile(ambient_dimensions={"cell": 4})
    with pytest.raises(ValueError, match="expected 3 in ambient dimension 3"):
        EngineeringSemanticGraph([moment]).compile(ambient_dimensions={"cell": 3})


def test_semantic_vocabulary_is_closed() -> None:
    with pytest.raises(ValueError, match="unsupported engineering property"):
        EngineeringAssertion.from_dict(
            {
                "form": "property",
                "symbol": "special_flange_rule",
                "subject": "solid",
                "value": 1,
            }
        )


def test_engineering_semantics_do_not_change_geometry_program() -> None:
    payload = json.loads(
        (PROGRAMS / "declarative-flange.json").read_text(encoding="utf-8")
    )
    baseline = DeclarativeCadExecutor().execute(
        EngineeringProgramSpec.from_dict(payload)
    ).to_engineering_part()

    enriched_payload = copy.deepcopy(payload)
    enriched_payload["engineering_semantics"] = [
        {
            "form": "property",
            "symbol": "material",
            "subject": payload["output"],
            "value": "Al 6061-T6",
        },
        {
            "form": "property",
            "symbol": "density",
            "subject": payload["output"],
            "value": 2700,
            "unit": "kg/m^3",
        },
        {
            "form": "property",
            "symbol": "linear_tolerance",
            "subject": payload["output"],
            "value": 0.1,
            "unit": "mm",
        },
        {
            "form": "property",
            "symbol": "surface_roughness",
            "subject": payload["output"],
            "value": 3.2,
            "unit": "um",
        },
    ]
    enriched = DeclarativeCadExecutor().execute(
        EngineeringProgramSpec.from_dict(enriched_payload)
    ).to_engineering_part()

    assert enriched.entity.shape.volume == pytest.approx(baseline.entity.shape.volume)
    assert enriched.program.operator_histogram() == baseline.program.operator_histogram()
    semantics = enriched.metadata["engineering_semantics"]
    assert semantics["constructor_histogram"] == {
        "property": 4,
        "relation": 0,
        "action": 0,
    }
    assert semantics["derived_values"][f"{payload['output']}.mass_kg"] > 0
