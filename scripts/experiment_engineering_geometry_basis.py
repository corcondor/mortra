"""Run the dimension-independent engineering-geometry experiment."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from math_os_prototype.engineering_cad_backend import (  # noqa: E402
    PART_BUILDERS,
    TOPOLOGY_HOLDOUT_BUILDERS,
    export_part_artifacts,
)
from math_os_prototype.engineering_geometry_ir import basis_summary  # noqa: E402


HOLDOUTS = {
    "flange_holdout": (
        "flange",
        {
            "outer_radius": 39.0,
            "bore_radius": 10.5,
            "thickness": 11.0,
            "bolt_radius": 2.8,
            "bolt_circle_radius": 28.0,
            "bolt_count": 8,
        },
    ),
    "shaft_holdout": (
        "stepped_shaft",
        {
            "lengths": (18.0, 27.0, 31.0),
            "radii": (9.0, 16.0, 11.0),
            "bore_radius": 2.0,
        },
    ),
    "duct_holdout": (
        "transition_duct",
        {
            "lower_size": (78.0, 38.0),
            "upper_radius": 17.0,
            "height": 67.0,
            "wall": 2.5,
        },
    ),
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default="artifacts/engineering-geometry-basis-20260831",
    )
    parser.add_argument(
        "--drawings",
        choices=("all", "representative", "none"),
        default="representative",
    )
    args = parser.parse_args()
    output = ROOT / args.output
    output.mkdir(parents=True, exist_ok=True)

    started = time.perf_counter()
    records = []
    parts = []
    for name, builder in PART_BUILDERS.items():
        part = builder()
        parts.append((name, "basis", part))
    for case_name, (builder_name, parameters) in HOLDOUTS.items():
        part = PART_BUILDERS[builder_name](**parameters)
        part.part_id = case_name
        part.title = f"Held-out parameterization: {part.title}"
        part.metadata["evaluation_role"] = "synthetic_holdout"
        parts.append((case_name, "parameter_holdout", part))
    for name, builder in TOPOLOGY_HOLDOUT_BUILDERS.items():
        part = builder()
        parts.append((name, "topology_holdout", part))

    drawing_ids = {
        name for name, role, _ in parts if args.drawings == "all"
    }
    if args.drawings == "representative":
        drawing_ids = {"flange", "stepped_shaft", "angle_bracket", "transition_duct"}

    for name, role, part in parts:
        if name in drawing_ids:
            manifest = export_part_artifacts(part, output / name)
        else:
            bbox = part.entity.shape.bounding_box()
            manifest = {
                "part_id": part.part_id,
                "title": part.title,
                "passed": part.passed,
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
                "program": part.program.to_dict(),
                "metadata": part.metadata,
            }
            case_dir = output / name
            case_dir.mkdir(parents=True, exist_ok=True)
            (case_dir / f"{name}.json").write_text(
                json.dumps(manifest, indent=2), encoding="utf-8"
            )
        records.append({"role": role, **manifest})
        print(
            f"{name:22s} {role:7s} "
            f"passed={manifest['passed']} "
            f"volume={manifest['geometry']['volume_mm3']:.3f}"
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
        "experiment": "dimension-independent-engineering-geometry-basis-v1",
        "basis": basis_summary(),
        "cases": len(records),
        "basis_cases": sum(record["role"] == "basis" for record in records),
        "holdout_cases": sum(record["role"] != "basis" for record in records),
        "parameter_holdout_cases": sum(
            record["role"] == "parameter_holdout" for record in records
        ),
        "topology_holdout_cases": sum(
            record["role"] == "topology_holdout" for record in records
        ),
        "passed_cases": sum(bool(record["passed"]) for record in records),
        "all_brep_valid": all(record["geometry"]["is_valid"] for record in records),
        "all_single_solid": all(record["geometry"]["solid_count"] == 1 for record in records),
        "used_operator_families": used_ops,
        "used_operator_family_count": len(used_ops),
        "new_operator_families_needed_by_holdouts": sorted(
            set(
                op
                for record in records
                if record["role"] != "basis"
                for op, count in record["program"]["operator_histogram"].items()
                if count
            )
            - set(
                op
                for record in records
                if record["role"] == "basis"
                for op, count in record["program"]["operator_histogram"].items()
                if count
            )
        ),
        "elapsed_seconds": time.perf_counter() - started,
        "records": [
            {
                "part_id": record["part_id"],
                "role": record["role"],
                "passed": record["passed"],
                "geometry": record["geometry"],
                "operator_histogram": record["program"]["operator_histogram"],
            }
            for record in records
        ],
    }
    summary_path = output / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"summary -> {summary_path}")
    return 0 if summary["passed_cases"] == summary["cases"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
