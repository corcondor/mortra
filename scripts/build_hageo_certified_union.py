"""Extend a HAGeo certified portfolio with an audited cohort result."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.hageo_frozen_split import (  # noqa: E402
    load_frozen_problem_names,
    require_frozen_membership,
)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_union(
    base_path: Path,
    cohort_path: Path,
    audit_path: Path,
    frozen_path: Path,
) -> dict[str, Any]:
    base = _load(base_path)
    cohort = _load(cohort_path)
    audit = _load(audit_path)
    if not audit["summary"]["all_claimed_solves_verified"]:
        raise ValueError("cohort contains an unverified solved claim")
    if audit["summary"]["artifact_hash_failures"]:
        raise ValueError("cohort contains modified problem artifacts")

    audited_solved = {
        row["problem_name"]
        for row in audit["results"]
        if row["claimed_solved"] and row["certificate_ok"]
    }
    cohort_solved = set(cohort.get("solved_names", []))
    if audited_solved != cohort_solved:
        raise ValueError("audited solved set does not match cohort solved set")

    base_primary = set(base["sets"]["primary_union"])
    frozen_names = load_frozen_problem_names(frozen_path)
    require_frozen_membership(base_primary, frozen_names, label="base union")
    require_frozen_membership(audited_solved, frozen_names, label="audited cohort")
    new_unique = audited_solved - base_primary
    primary_union = base_primary | audited_solved
    total = len(frozen_names)
    if int(base["summary"]["total"]) != total:
        raise ValueError("base total does not match frozen split size")
    return {
        "experiment": "hageo_certified_capability_union",
        "protocol": {
            "uses_external_llm": False,
            "truth_plane": "set union of audited native proof certificates",
            "double_counting": "set union by frozen problem name",
            "calibration_excluded_from_primary_score": True,
            "inputs": {
                "base_union_sha256": _sha256(base_path),
                "cohort_sha256": _sha256(cohort_path),
                "certificate_audit_sha256": _sha256(audit_path),
                "frozen_split_sha256": _sha256(frozen_path),
            },
        },
        "summary": {
            "total": total,
            "base_primary_certified_solved": len(base_primary),
            "cohort_verified_solved": len(audited_solved),
            "cohort_overlap_with_base": len(audited_solved & base_primary),
            "new_certified_unique": len(new_unique),
            "primary_certified_solved": len(primary_union),
            "primary_certified_score": len(primary_union) / total,
        },
        "sets": {
            "base_primary_union": sorted(base_primary),
            "cohort_verified": sorted(audited_solved),
            "cohort_overlap_with_base": sorted(audited_solved & base_primary),
            "new_certified_unique": sorted(new_unique),
            "primary_union": sorted(primary_union),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--cohort", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--frozen-baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    artifact = build_union(
        args.base,
        args.cohort,
        args.audit,
        args.frozen_baseline,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(artifact["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
