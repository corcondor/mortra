"""Combine independently certified HAGeo agents without double counting."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--auxiliary", type=Path, required=True)
    parser.add_argument("--exact", type=Path, required=True)
    parser.add_argument("--calibration", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    baseline = _load(args.baseline)
    auxiliary = _load(args.auxiliary)
    exact = _load(args.exact)
    baseline_names = {
        name
        for name, result in baseline["results"].items()
        if result.get("status") == "solved"
    }
    auxiliary_names = set(auxiliary["summary"]["newly_solved_names"])
    exact_names = {
        str(result["problem"])
        for result in exact["results"]
        if result.get("solved") and result.get("native_confirmed")
    }
    calibration_names: set[str] = set()
    if args.calibration:
        calibration = _load(args.calibration)
        if calibration.get("solved") and calibration.get("native_confirmed"):
            calibration_names.add(str(calibration["problem"]))

    evaluated_without_calibration = baseline_names | auxiliary_names | exact_names
    engineering_union = evaluated_without_calibration | calibration_names
    total = int(baseline["summary"]["total"])
    report = {
        "experiment": "hageo_certified_capability_union",
        "created_at": datetime.now(UTC).isoformat(),
        "protocol": {
            "uses_external_llm": False,
            "truth_plane": "union of exact or native proof certificates",
            "timeouts": "right-censored unknown; never counted as solved or wrong",
            "double_counting": "set union by problem name",
            "calibration_excluded_from_primary_score": bool(args.calibration),
            "inputs": {
                "baseline": _sha256(args.baseline),
                "auxiliary": _sha256(args.auxiliary),
                "exact": _sha256(args.exact),
                "calibration": _sha256(args.calibration) if args.calibration else None,
            },
        },
        "summary": {
            "total": total,
            "baseline_solved": len(baseline_names),
            "auxiliary_new": len(auxiliary_names - baseline_names),
            "exact_solved": len(exact_names),
            "exact_unique_beyond_previous_portfolio": len(
                exact_names - baseline_names - auxiliary_names
            ),
            "primary_certified_solved": len(evaluated_without_calibration),
            "primary_certified_score": len(evaluated_without_calibration) / total,
            "calibration_certified_solved": len(calibration_names),
            "engineering_certified_solved": len(engineering_union),
            "engineering_certified_score": len(engineering_union) / total,
            "exact_right_censored": int(exact["summary"]["right_censored"]),
        },
        "sets": {
            "baseline": sorted(baseline_names),
            "auxiliary_new": sorted(auxiliary_names - baseline_names),
            "exact": sorted(exact_names),
            "exact_overlap_with_auxiliary": sorted(exact_names & auxiliary_names),
            "exact_unique_beyond_previous_portfolio": sorted(
                exact_names - baseline_names - auxiliary_names
            ),
            "calibration": sorted(calibration_names),
            "primary_union": sorted(evaluated_without_calibration),
            "engineering_union": sorted(engineering_union),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
