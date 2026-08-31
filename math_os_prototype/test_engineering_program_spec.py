from __future__ import annotations

import copy
import importlib.util
import json
import math
from pathlib import Path

import pytest

from math_os_prototype.engineering_program_spec import (
    DeclarativeCadExecutor,
    EngineeringProgramSpec,
    SeedSpec,
    StepSpec,
)
from math_os_prototype.engineering_geometry_ir import BasisOp


ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data" / "engineering_programs"


def test_seed_language_is_closed_and_rejects_code_objects() -> None:
    with pytest.raises(ValueError, match="unknown seed kind"):
        SeedSpec("gear", "involute_gear", {})
    with pytest.raises(TypeError, match="not serializable"):
        SeedSpec("disk", "disk", {"radius": lambda: 3})


def test_program_rejects_forward_references() -> None:
    with pytest.raises(ValueError, match="unavailable inputs"):
        EngineeringProgramSpec.from_dict(
            {
                "program_id": "bad",
                "seeds": [],
                "steps": [
                    {
                        "output": "solid",
                        "op": "sweep",
                        "inputs": ["missing"],
                        "parameters": {"trajectory": "line", "vector": [0, 0, 1]},
                    }
                ],
                "output": "solid",
            }
        )


def test_public_language_rejects_hidden_part_specific_parameters() -> None:
    with pytest.raises(ValueError, match="unsupported parameters"):
        SeedSpec("profile", "rectangle", {"width": 2, "height": 3, "gear": 17})
    with pytest.raises(ValueError, match="unsupported parameters"):
        StepSpec(
            "solid",
            BasisOp.SWEEP,
            ("profile",),
            {
                "trajectory": "line",
                "vector": [0, 0, 1],
                "part_family": "bracket",
            },
        )


def test_normal_bundle_language_has_one_closed_generic_family() -> None:
    StepSpec(
        "offset",
        BasisOp.SWEEP,
        ("boundary", "source"),
        {
            "trajectory": "normal_bundle",
            "cross_section": "interval",
            "result": "parallel_set",
            "distance": 2,
        },
    )
    with pytest.raises(ValueError, match="normal_bundle semantics"):
        StepSpec(
            "bad",
            BasisOp.SWEEP,
            ("boundary", "source"),
            {
                "trajectory": "normal_bundle",
                "cross_section": "logo_shape",
                "result": "parallel_set",
                "distance": 2,
            },
        )


def test_planar_and_solid_blends_share_the_same_normal_bundle_semantics() -> None:
    spec = EngineeringProgramSpec.from_dict(
        {
            "program_id": "planar_blend_holdout",
            "seeds": [
                {
                    "name": "rectangle",
                    "kind": "rectangle",
                    "parameters": {"width": 20, "height": 10},
                }
            ],
            "steps": [
                {
                    "output": "corners",
                    "op": "select",
                    "inputs": ["rectangle"],
                    "parameters": {"selector": "vertices"},
                },
                {
                    "output": "rounded_profile",
                    "op": "sweep",
                    "inputs": ["corners", "rectangle"],
                    "parameters": {
                        "trajectory": "normal_bundle",
                        "cross_section": "disk_sector",
                        "result": "blend",
                        "distance": 2,
                    },
                },
                {
                    "output": "result",
                    "op": "sweep",
                    "inputs": ["rounded_profile"],
                    "parameters": {"trajectory": "line", "vector": [0, 0, 3]},
                },
            ],
            "output": "result",
        }
    )
    result = DeclarativeCadExecutor().execute(spec)
    assert result.output.shape.is_valid
    assert result.output.shape.volume == pytest.approx(
        3 * (200 - 16 + 4 * math.pi), abs=1e-7
    )


pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("build123d") is None,
    reason="build123d/OpenCascade research environment is not active",
)


def test_declarative_flange_replays_without_arbitrary_native_input() -> None:
    spec = EngineeringProgramSpec.from_json(PROGRAMS / "declarative-flange.json")
    result = DeclarativeCadExecutor().execute(spec)
    part = result.to_engineering_part()
    assert part.passed
    assert part.entity.shape.is_valid
    assert len(part.entity.shape.solids()) == 1
    assert part.metadata["arbitrary_native_input"] is False
    assert len(spec.stable_hash) == 64
    assert set(part.program.operator_histogram()) == {
        "transform",
        "sweep",
        "combine",
        "select",
        "slice",
        "project",
        "constrain",
        "annotate",
    }


def test_entity_renaming_does_not_change_constructed_geometry() -> None:
    payload = json.loads(
        (PROGRAMS / "declarative-flange.json").read_text(encoding="utf-8")
    )
    original = DeclarativeCadExecutor().execute(
        EngineeringProgramSpec.from_dict(payload)
    ).output.shape

    renamed = copy.deepcopy(payload)
    names = [seed["name"] for seed in renamed["seeds"]]
    names.extend(step["output"] for step in renamed["steps"])
    mapping = {name: f"e{index:03d}" for index, name in enumerate(names)}
    for seed in renamed["seeds"]:
        seed["name"] = mapping[seed["name"]]
    for step in renamed["steps"]:
        step["inputs"] = [mapping[name] for name in step["inputs"]]
        step["output"] = mapping[step["output"]]
    renamed["output"] = mapping[renamed["output"]]
    renamed["program_id"] = "renamed_flange"
    replay = DeclarativeCadExecutor().execute(
        EngineeringProgramSpec.from_dict(renamed)
    ).output.shape

    assert replay.volume == pytest.approx(original.volume, abs=1e-8)
    assert len(replay.faces()) == len(original.faces())
    assert len(replay.edges()) == len(original.edges())


def test_helical_holdout_uses_existing_sweep_operation() -> None:
    spec = EngineeringProgramSpec.from_json(PROGRAMS / "helical-spring.json")
    result = DeclarativeCadExecutor().execute(spec)
    part = result.to_engineering_part()
    assert part.passed
    assert part.entity.shape.is_valid
    assert len(part.entity.shape.solids()) == 1
    assert part.entity.shape.volume == pytest.approx(1980.19235467032, abs=0.01)
    histogram = part.program.operator_histogram()
    assert histogram["sweep"] == 1
    assert all(
        count == 0
        for name, count in histogram.items()
        if name not in {"sweep", "constrain"}
    )


def test_generic_line_arc_sketch_compiles_without_a_new_morphism() -> None:
    spec = EngineeringProgramSpec.from_dict(
        {
            "program_id": "capsule_profile",
            "seeds": [
                {
                    "name": "profile",
                    "kind": "sketch",
                    "parameters": {
                        "start": [-10, -5],
                        "commands": [
                            {"kind": "line", "to": [10, -5]},
                            {"kind": "radius_arc", "radius": -5, "to": [10, 5]},
                            {"kind": "line", "to": [-10, 5]},
                            {"kind": "arc3", "mid": [-15, 0], "to": [-10, -5]},
                        ],
                        "close": True,
                        "filled": True,
                    },
                }
            ],
            "steps": [
                {
                    "output": "solid",
                    "op": "sweep",
                    "inputs": ["profile"],
                    "parameters": {"trajectory": "line", "vector": [0, 0, 6]},
                },
                {
                    "output": "result",
                    "op": "constrain",
                    "inputs": ["solid"],
                    "parameters": {"predicate": "valid_brep"},
                },
            ],
            "output": "result",
        }
    )
    result = DeclarativeCadExecutor().execute(spec)
    assert result.output.shape.is_valid
    assert result.output.shape.volume == pytest.approx(
        6 * (200 + 25 * math.pi), abs=1e-7
    )
    assert result.executor.program.operator_histogram()["sweep"] == 1


def test_scale_and_mirror_are_transform_parameters() -> None:
    spec = EngineeringProgramSpec.from_dict(
        {
            "program_id": "affine-transform",
            "seeds": [
                {"name": "disk", "kind": "disk", "parameters": {"radius": 1}}
            ],
            "steps": [
                {
                    "output": "cylinder",
                    "op": "sweep",
                    "inputs": ["disk"],
                    "parameters": {"trajectory": "line", "vector": [0, 0, 1]},
                },
                {
                    "output": "scaled",
                    "op": "transform",
                    "inputs": ["cylinder"],
                    "parameters": {"scale": 2},
                },
                {
                    "output": "result",
                    "op": "transform",
                    "inputs": ["scaled"],
                    "parameters": {"mirror_plane": "YZ"},
                },
            ],
            "output": "result",
        }
    )
    result = DeclarativeCadExecutor().execute(spec)
    assert result.output.shape.volume == pytest.approx(8 * 3.141592653589793)
    assert result.executor.program.operator_histogram()["transform"] == 2


@pytest.mark.parametrize(
    ("filename", "expected_volume"),
    [
        ("normal-offset-gasket.json", 824.5486677646163),
        ("thin-wall-enclosure.json", 7152.0),
        ("filleted-post.json", 5922.743338823081),
    ],
)
def test_normal_bundle_holdouts_close_exact_brep_obligations(
    filename: str,
    expected_volume: float,
) -> None:
    spec = EngineeringProgramSpec.from_json(PROGRAMS / filename)
    result = DeclarativeCadExecutor().execute(spec)
    part = result.to_engineering_part()

    assert part.passed
    assert part.entity.shape.is_valid
    assert len(part.entity.shape.solids()) == 1
    assert part.entity.shape.volume == pytest.approx(expected_volume, abs=1e-5)
    assert part.program.operator_histogram()["sweep"] >= 2
    assert any(
        step.op is BasisOp.SWEEP
        and step.parameters.get("trajectory") == "normal_bundle"
        for step in part.program.steps
    )


@pytest.mark.parametrize(
    ("filename", "new_distance"),
    [
        ("normal-offset-gasket.json", 4.0),
        ("thin-wall-enclosure.json", -3.0),
        ("filleted-post.json", 4.0),
    ],
)
def test_normal_bundle_parameters_change_geometry_without_new_operations(
    filename: str,
    new_distance: float,
) -> None:
    payload = json.loads((PROGRAMS / filename).read_text(encoding="utf-8"))
    baseline = DeclarativeCadExecutor().execute(
        EngineeringProgramSpec.from_dict(payload)
    ).output.shape
    changed = copy.deepcopy(payload)
    for step in changed["steps"]:
        if step["parameters"].get("trajectory") == "normal_bundle":
            step["parameters"]["distance"] = new_distance
    changed["program_id"] += "_parameter_holdout"
    candidate = DeclarativeCadExecutor().execute(
        EngineeringProgramSpec.from_dict(changed)
    ).output.shape

    assert candidate.is_valid
    assert len(candidate.solids()) == 1
    assert candidate.volume != pytest.approx(baseline.volume, abs=1e-5)
