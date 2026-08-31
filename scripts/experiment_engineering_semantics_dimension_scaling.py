"""Measure engineering semantics and finite-dimensional geometry reuse.

The experiment has two independent parts:

1. Attach manufacturing semantics to existing declarative CAD programs and
   verify that no geometric result or construction operator changes.
2. Execute the affine subset of the same geometry IR in dimensions 4..12 with
   exact rational arithmetic, then render a representative projection.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
from fractions import Fraction
import json
from pathlib import Path
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from math_os_prototype.engineering_cad_backend import export_part_artifacts  # noqa: E402
from math_os_prototype.engineering_program_spec import (  # noqa: E402
    DeclarativeCadExecutor,
    EngineeringProgramSpec,
)
from math_os_prototype.engineering_semantics import (  # noqa: E402
    AssertionForm,
    EngineeringAssertion,
)
from math_os_prototype.nd_cell_backend import (  # noqa: E402
    ExactCellExecutor,
    render_wireframe_svg,
)


PROGRAMS = ROOT / "data" / "engineering_programs"
CASES: dict[str, tuple[str, tuple[EngineeringAssertion, ...]]] = {
    "declarative-flange": (
        "declarative-flange.json",
        (
            EngineeringAssertion(
                AssertionForm.PROPERTY, "material", "result", "ASTM A36 STEEL"
            ),
            EngineeringAssertion(
                AssertionForm.PROPERTY, "density", "result", 7850, "kg/m^3"
            ),
            EngineeringAssertion(
                AssertionForm.PROPERTY,
                "manufacturing_process",
                "result",
                "CNC MILLING AND DRILLING",
            ),
            EngineeringAssertion(
                AssertionForm.PROPERTY, "linear_tolerance", "result", 0.1, "mm"
            ),
            EngineeringAssertion(
                AssertionForm.PROPERTY, "angular_tolerance", "result", 0.5, "deg"
            ),
            EngineeringAssertion(
                AssertionForm.PROPERTY, "surface_roughness", "result", 3.2, "um"
            ),
            EngineeringAssertion(
                AssertionForm.RELATION, "datum", "outer_disk", "A"
            ),
            EngineeringAssertion(
                AssertionForm.ACTION,
                "force",
                "result",
                (0, 0, -1200),
                "N",
                frame="datum_A",
            ),
        ),
    ),
    "thin-wall-enclosure": (
        "thin-wall-enclosure.json",
        (
            EngineeringAssertion(
                AssertionForm.PROPERTY, "material", "result", "5052-H32 ALUMINUM"
            ),
            EngineeringAssertion(
                AssertionForm.PROPERTY, "density", "result", 2680, "kg/m^3"
            ),
            EngineeringAssertion(
                AssertionForm.PROPERTY,
                "manufacturing_process",
                "result",
                "SHEET METAL FORMING",
            ),
            EngineeringAssertion(
                AssertionForm.PROPERTY, "linear_tolerance", "result", 0.2, "mm"
            ),
            EngineeringAssertion(
                AssertionForm.PROPERTY, "surface_roughness", "result", 1.6, "um"
            ),
            EngineeringAssertion(
                AssertionForm.RELATION, "datum", "footprint", "A"
            ),
            EngineeringAssertion(
                AssertionForm.ACTION,
                "force",
                "result",
                (0, 0, -250),
                "N",
                frame="datum_A",
            ),
        ),
    ),
    "helical-spring": (
        "helical-spring.json",
        (
            EngineeringAssertion(
                AssertionForm.PROPERTY,
                "material",
                "result",
                "17-7PH STAINLESS STEEL",
            ),
            EngineeringAssertion(
                AssertionForm.PROPERTY, "density", "result", 7800, "kg/m^3"
            ),
            EngineeringAssertion(
                AssertionForm.PROPERTY,
                "manufacturing_process",
                "result",
                "COLD COILING AND HEAT TREATMENT",
            ),
            EngineeringAssertion(
                AssertionForm.PROPERTY, "linear_tolerance", "result", 0.05, "mm"
            ),
            EngineeringAssertion(
                AssertionForm.PROPERTY, "surface_roughness", "result", 0.8, "um"
            ),
            EngineeringAssertion(
                AssertionForm.RELATION, "datum", "centerline", "C"
            ),
            EngineeringAssertion(
                AssertionForm.ACTION,
                "force",
                "result",
                (0, 0, -180),
                "N",
                frame="datum_C",
            ),
        ),
    ),
}


def _geometry_signature(shape: Any) -> dict[str, Any]:
    bbox = shape.bounding_box()
    return {
        "volume_mm3": float(shape.volume),
        "surface_area_mm2": float(shape.area),
        "solid_count": len(shape.solids()),
        "face_count": len(shape.faces()),
        "edge_count": len(shape.edges()),
        "bbox_mm": [float(bbox.size.X), float(bbox.size.Y), float(bbox.size.Z)],
        "is_valid": bool(shape.is_valid),
    }


def _same_numbers(left: Any, right: Any, tolerance: float = 1e-8) -> bool:
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(
            _same_numbers(a, b, tolerance) for a, b in zip(left, right)
        )
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return abs(float(left) - float(right)) <= tolerance
    return left == right


def _run_semantic_cases(output: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for case_id, (filename, assertions) in CASES.items():
        baseline_spec = EngineeringProgramSpec.from_json(PROGRAMS / filename)
        semantic_spec = replace(baseline_spec, engineering_semantics=assertions)

        baseline = DeclarativeCadExecutor().execute(baseline_spec)
        candidate = DeclarativeCadExecutor().execute(semantic_spec)
        baseline_part = baseline.to_engineering_part()
        candidate_part = candidate.to_engineering_part()
        baseline_geometry = _geometry_signature(baseline_part.entity.shape)
        candidate_geometry = _geometry_signature(candidate_part.entity.shape)
        baseline_ops = baseline_part.program.operator_histogram()
        candidate_ops = candidate_part.program.operator_histogram()
        semantics = candidate_part.metadata["engineering_semantics"]
        geometry_unchanged = _same_numbers(baseline_geometry, candidate_geometry)
        operators_unchanged = baseline_ops == candidate_ops

        case_dir = output / case_id
        manifest = export_part_artifacts(candidate_part, case_dir)
        record = {
            "case_id": case_id,
            "source": str((PROGRAMS / filename).relative_to(ROOT)),
            "geometry_unchanged": geometry_unchanged,
            "operators_unchanged": operators_unchanged,
            "baseline_geometry": baseline_geometry,
            "semantic_geometry": candidate_geometry,
            "operator_histogram": candidate_ops,
            "semantic_constructor_histogram": semantics["constructor_histogram"],
            "semantic_assertion_hash": semantics["assertion_hash"],
            "derived_values": semantics["derived_values"],
            "drawing_notes": semantics["drawing_notes"],
            "drawing_svg": manifest["artifacts"].get("svg"),
            "passed": bool(
                geometry_unchanged
                and operators_unchanged
                and baseline_geometry["is_valid"]
                and semantics["derived_values"]
            ),
        }
        records.append(record)
        print(
            f"{case_id:24s} geometry={geometry_unchanged} "
            f"operators={operators_unchanged} "
            f"mass={next(iter(semantics['derived_values'].values())):.6g} kg"
        )
    return records


def _hypercube(dimension: int) -> tuple[ExactCellExecutor, Any]:
    executor = ExactCellExecutor(f"exact-hypercube-{dimension}d")
    cell = executor.point("origin", (0,) * dimension)
    for index in range(dimension):
        direction = [0] * dimension
        direction[index] = 1
        cell = executor.linear_sweep(cell, f"axis_{index + 1}", direction)
    return executor, cell


def _projection_matrix(dimension: int) -> tuple[tuple[Fraction, ...], ...]:
    # A rational octagonal direction cycle produces a balanced zonotope without
    # introducing a dimension-specific rendering or an inexact trigonometric step.
    directions = (
        (1, 0),
        (1, 1),
        (0, 1),
        (-1, 1),
        (-1, 0),
        (-1, -1),
        (0, -1),
        (1, -1),
    )
    row_x = tuple(Fraction(directions[index % 8][0]) for index in range(dimension))
    row_y = tuple(Fraction(directions[index % 8][1]) for index in range(dimension))
    return row_x, row_y


def _run_dimension_cases(output: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for dimension in (4, 6, 8, 10, 12):
        started = time.perf_counter()
        executor, cell = _hypercube(dimension)
        expected_vertices = 2**dimension
        expected_edges = dimension * 2 ** (dimension - 1)
        exact = all(
            isinstance(value, Fraction)
            for vertex in cell.vertices
            for value in vertex
        )
        record = {
            "ambient_dimension": dimension,
            "intrinsic_dimension": cell.ref.geometric_type.intrinsic_dimension,
            "vertex_count": len(cell.vertices),
            "edge_count": len(cell.edges),
            "expected_vertex_count": expected_vertices,
            "expected_edge_count": expected_edges,
            "rational_exact": exact,
            "operator_histogram": executor.program.operator_histogram(),
            "elapsed_seconds": time.perf_counter() - started,
            "passed": bool(
                exact
                and len(cell.vertices) == expected_vertices
                and len(cell.edges) == expected_edges
                and cell.ref.geometric_type.intrinsic_dimension == dimension
            ),
        }
        if dimension == 8:
            projection = executor.project(
                cell, "drawing_projection", _projection_matrix(dimension)
            )
            drawing = output / "exact-8d-projection.svg"
            render_wireframe_svg(
                projection,
                drawing,
                title="Cell(8, R^8) projected exactly to R^2",
            )
            record["projection_svg"] = str(drawing.relative_to(output))
            record["projected_vertex_count"] = len(projection.vertices)
            record["projected_edge_count"] = len(projection.edges)
        records.append(record)
        print(
            f"{dimension:2d}D vertices={len(cell.vertices):5d} "
            f"edges={len(cell.edges):6d} exact={exact}"
        )
    return records


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default="artifacts/engineering-semantics-dimension-scaling-20260831",
    )
    args = parser.parse_args()
    output = ROOT / args.output
    output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()

    semantic_records = _run_semantic_cases(output)
    dimension_records = _run_dimension_cases(output)
    summary = {
        "experiment": "engineering-semantics-and-dimension-scaling-v1",
        "geometry_operator_basis_changed": False,
        "semantic_assertion_forms": [form.value for form in AssertionForm],
        "semantic_cases": len(semantic_records),
        "semantic_cases_passed": sum(record["passed"] for record in semantic_records),
        "all_semantic_geometry_unchanged": all(
            record["geometry_unchanged"] for record in semantic_records
        ),
        "all_semantic_operator_histograms_unchanged": all(
            record["operators_unchanged"] for record in semantic_records
        ),
        "dimension_cases": len(dimension_records),
        "dimension_cases_passed": sum(record["passed"] for record in dimension_records),
        "maximum_executed_dimension": max(
            record["ambient_dimension"] for record in dimension_records
        ),
        "scope_boundary": {
            "physical_engineering_drawing_dimension": 3,
            "exact_affine_polytopal_backend": "arbitrary finite dimension",
            "smooth_brep_backend": "three dimensions",
            "higher_dimensional_results_are_physical_claims": False,
        },
        "elapsed_seconds": time.perf_counter() - started,
        "semantic_records": semantic_records,
        "dimension_records": dimension_records,
    }
    summary["passed"] = bool(
        summary["semantic_cases_passed"] == summary["semantic_cases"]
        and summary["dimension_cases_passed"] == summary["dimension_cases"]
    )
    summary_path = output / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"summary -> {summary_path}")
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
