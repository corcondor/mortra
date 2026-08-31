"""Run the finite-language CAD and exact higher-dimensional experiments."""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from math_os_prototype.engineering_cad_backend import (  # noqa: E402
    export_exact_shape_artifact,
    export_part_artifacts,
)
from math_os_prototype.engineering_program_spec import (  # noqa: E402
    DeclarativeCadExecutor,
    EngineeringProgramSpec,
    SEED_KINDS,
)
from math_os_prototype.engineering_geometry_ir import basis_summary  # noqa: E402
from math_os_prototype.nd_cell_backend import ExactCellExecutor, render_wireframe_svg  # noqa: E402


PROGRAM_FILES = (
    "declarative-flange.json",
    "helical-spring.json",
    "rounded-link-plate.json",
    "normal-offset-gasket.json",
    "thin-wall-enclosure.json",
    "filleted-post.json",
)

RUNTIME_FILES = (
    ROOT / "math_os_prototype" / "engineering_geometry_ir.py",
    ROOT / "math_os_prototype" / "engineering_cad_backend.py",
    ROOT / "math_os_prototype" / "engineering_program_spec.py",
)


def runtime_hash() -> str:
    digest = hashlib.sha256()
    for path in RUNTIME_FILES:
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def exact_hypercube(dimension: int, output: Path) -> dict[str, object]:
    if dimension < 3:
        raise ValueError("the experiment renders hypercubes in dimension 3 or above")
    executor = ExactCellExecutor(f"exact-rational-hypercube-{dimension}d")
    cell = executor.point("origin", (0,) * dimension)
    for index in range(dimension):
        direction = [0] * dimension
        direction[index] = 1
        cell = executor.linear_sweep(cell, f"axis_sweep_{index + 1}", direction)
    projection_directions = (
        (Fraction(1), Fraction(0)),
        (Fraction(0), Fraction(1)),
        (Fraction(3, 5), Fraction(2, 5)),
        (Fraction(-2, 5), Fraction(3, 5)),
        (Fraction(1, 3), Fraction(-1, 2)),
        (Fraction(-1, 4), Fraction(-2, 3)),
    )
    drawing = executor.project(
        cell,
        "drawing",
        tuple(
            tuple(projection_directions[index][axis] for index in range(dimension))
            for axis in range(2)
        ),
    )
    svg = output / f"hypercube-{dimension}d-rational-projection.svg"
    if dimension == 4:
        render_wireframe_svg(
            drawing,
            svg,
            title="Cell(4, R^4) - exact rational projection into R^2",
        )
    record = {
        "arithmetic": "rational_exact",
        "ambient_dimension": cell.ref.geometric_type.ambient_dimension,
        "intrinsic_dimension": cell.ref.geometric_type.intrinsic_dimension,
        "vertices": len(cell.vertices),
        "edges": len(cell.edges),
        "projected_vertices": len(drawing.vertices),
        "projected_edges": len(drawing.edges),
        "new_basis_operations": 0,
        "program": executor.program.to_dict(),
        "cell": cell.to_dict(),
        "projection": drawing.to_dict(),
        "svg": svg.name if dimension == 4 else None,
    }
    (output / f"hypercube-{dimension}d-rational-projection.json").write_text(
        json.dumps(record, indent=2), encoding="utf-8"
    )
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "artifacts" / "declarative-engineering-generalization-20260831",
    )
    parser.add_argument(
        "--cadtestbench-audit",
        type=Path,
        default=ROOT
        / "artifacts"
        / "declarative-engineering-generalization-20260831-normal-bundle"
        / "cadtestbench-operator-coverage-v2.json",
    )
    parser.add_argument(
        "--program",
        action="append",
        default=[],
        help="Run only the named JSON file or program id; may be repeated.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse a completed case only when its stored program hash matches.",
    )
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.mkdir(parents=True, exist_ok=True)
    source = ROOT / "data" / "engineering_programs"

    started = time.perf_counter()
    current_runtime_hash = runtime_hash()
    records = []
    selected = set(args.program)
    filenames = [
        filename
        for filename in PROGRAM_FILES
        if not selected
        or filename in selected
        or Path(filename).stem in selected
    ]
    if selected and not filenames:
        parser.error(f"no program matched: {sorted(selected)}")

    progress_path = output / "progress.json"
    for filename in filenames:
        spec = EngineeringProgramSpec.from_json(source / filename)
        case_dir = output / spec.program_id
        manifest_path = case_dir / f"{spec.program_id}.json"
        manifest = None
        if args.resume and manifest_path.exists():
            candidate = json.loads(manifest_path.read_text(encoding="utf-8"))
            artifact_names = candidate.get("artifacts", {}).values()
            artifacts_exist = all((case_dir / name).exists() for name in artifact_names)
            if (
                candidate.get("metadata", {}).get("program_hash") == spec.stable_hash
                and candidate.get("metadata", {}).get("runtime_hash")
                == current_runtime_hash
                and artifacts_exist
            ):
                manifest = candidate

        reused = manifest is not None
        if manifest is None:
            result = DeclarativeCadExecutor().execute(spec)
            part = result.to_engineering_part()
            part.metadata["runtime_hash"] = current_runtime_hash
            manifest = (
                export_exact_shape_artifact(part, case_dir)
                if spec.metadata.get("artifact_profile") == "exact_shape_only"
                else export_part_artifacts(part, case_dir)
            )
        records.append(
            {
                "spec_file": filename,
                "program_hash": spec.stable_hash,
                "arbitrary_native_input": False,
                "reused": reused,
                **manifest,
            }
        )
        print(
            f"{spec.program_id:32s} passed={manifest['passed']} "
            f"volume={manifest['geometry']['volume_mm3']:.3f} reused={reused}",
            flush=True,
        )
        progress_path.write_text(
            json.dumps(
                {
                    "experiment": "finite-language-engineering-generalization-v2",
                    "completed": [record["part_id"] for record in records],
                    "pending": [
                        Path(item).stem
                        for item in filenames[len(records) :]
                    ],
                    "elapsed_seconds": time.perf_counter() - started,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    hypercubes = [exact_hypercube(dimension, output) for dimension in (4, 5, 6)]
    cad_audit = (
        json.loads(args.cadtestbench_audit.read_text(encoding="utf-8"))
        if args.cadtestbench_audit.exists()
        else None
    )
    used_ops = sorted(
        {
            op
            for record in records
            for op, count in record["program"]["operator_histogram"].items()
            if count
        }
    )
    summary = {
        "experiment": "finite-language-engineering-generalization-v2",
        "basis": basis_summary(),
        "finite_seed_kinds": sorted(SEED_KINDS),
        "arbitrary_native_input_allowed": False,
        "runtime_hash": current_runtime_hash,
        "cad_cases": len(records),
        "cad_cases_passed": sum(bool(record["passed"]) for record in records),
        "all_cad_breps_valid": all(record["geometry"]["is_valid"] for record in records),
        "all_cad_single_solid": all(
            record["geometry"]["solid_count"] == 1 for record in records
        ),
        "used_basis_operations": used_ops,
        "new_basis_operations": 0,
        "higher_dimensional_execution": [
            {
                key: value
                for key, value in hypercube.items()
                if key not in {"program", "cell", "projection"}
            }
            for hypercube in hypercubes
        ],
        "cadtestbench_structural_audit": (
            {
                "scope": cad_audit["scope"],
                "program_files": cad_audit["program_files"],
                "construction_calls": cad_audit["construction_calls"],
                "runtime_covered_construction_calls": cad_audit[
                    "runtime_covered_construction_calls"
                ],
                "runtime_covered_construction_call_ratio": cad_audit[
                    "runtime_covered_construction_call_ratio"
                ],
                "files_with_only_runtime_covered_construction": cad_audit[
                    "files_with_only_runtime_covered_construction"
                ],
                "files_with_only_runtime_covered_construction_ratio": cad_audit[
                    "files_with_only_runtime_covered_construction_ratio"
                ],
            }
            if cad_audit
            else None
        ),
        "elapsed_seconds": time.perf_counter() - started,
        "records": [
            {
                "part_id": record["part_id"],
                "passed": record["passed"],
                "geometry": record["geometry"],
                "program_hash": record["program_hash"],
                "operator_histogram": record["program"]["operator_histogram"],
                "reused": record["reused"],
                "timings_seconds": record.get("timings_seconds", {}),
                "artifacts": record["artifacts"],
            }
            for record in records
        ],
    }
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps({
        "cad_cases": summary["cad_cases"],
        "cad_cases_passed": summary["cad_cases_passed"],
        "hypercube_dimensions": [
            record["ambient_dimension"] for record in hypercubes
        ],
        "hypercube_vertex_counts": [record["vertices"] for record in hypercubes],
        "hypercube_edge_counts": [record["edges"] for record in hypercubes],
        "elapsed_seconds": summary["elapsed_seconds"],
    }, indent=2))
    return 0 if summary["cad_cases"] == summary["cad_cases_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
