"""Merge independently replayed rerun proofs into the frozen certified union."""

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


def _display(path: Path) -> str:
    resolved = path.resolve()
    return (
        resolved.relative_to(ROOT).as_posix()
        if resolved.is_relative_to(ROOT)
        else resolved.as_posix()
    )


def build_union(
    base_path: Path,
    cohort_path: Path,
    audit_path: Path,
    frozen_path: Path,
) -> dict[str, Any]:
    base = _load(base_path)
    cohort = _load(cohort_path)
    audit = _load(audit_path)
    if not cohort.get("run_state", {}).get("complete"):
        raise ValueError("cohort run is incomplete")
    if not audit.get("summary", {}).get("all_accepted"):
        raise ValueError("not every claimed solve passed independent replay")
    if not audit.get("summary", {}).get("all_trace_integrity_passed"):
        raise ValueError("not every claimed solve passed proof-trace integrity")

    claimed = {
        str(run["problem"])
        for run in cohort.get("runs", ())
        if run.get("solved") is True
    }
    accepted = {
        str(name)
        for name, row in audit.get("audits", {}).items()
        if row.get("accepted") is True and row.get("trace_integrity") is True
    }
    if claimed != accepted:
        raise ValueError("cohort solved set and independent audit set differ")

    previous = set(map(str, base["sets"]["primary_union"]))
    frozen = set(load_frozen_problem_names(frozen_path))
    require_frozen_membership(previous, frozen, label="base union")
    require_frozen_membership(accepted, frozen, label="rerun accepted set")
    union = previous | accepted
    additions = accepted - previous
    guard_counts = {
        name: int(audit["audits"][name].get("numerical_guard_count", 0))
        for name in sorted(accepted)
    }
    total = len(frozen)
    return {
        "experiment": "hageo_frozen_certified_union_after_current_rerun",
        "protocol": {
            "uses_external_llm": False,
            "uses_expected_answer": False,
            "double_counting": "set union by frozen problem name",
            "native_acceptance": (
                "two deterministic Yuclid replays, matching input/proof hashes, "
                "and complete proof-trace linkage"
            ),
            "standards": {
                "native_yuclid_certificate": (
                    "accepted; this is the benchmark certificate standard"
                ),
                "fully_guard_discharged_formal_proof": (
                    "not claimed; numerical guards remain explicit in traces"
                ),
            },
            "inputs": {
                "base": {"path": _display(base_path), "sha256": _sha256(base_path)},
                "cohort": {
                    "path": _display(cohort_path),
                    "sha256": _sha256(cohort_path),
                },
                "audit": {
                    "path": _display(audit_path),
                    "sha256": _sha256(audit_path),
                },
                "frozen_split": {
                    "path": _display(frozen_path),
                    "sha256": _sha256(frozen_path),
                },
            },
        },
        "summary": {
            "total": total,
            "previous_certified_solved": len(previous),
            "rerun_claimed_solved": len(claimed),
            "rerun_independently_accepted": len(accepted),
            "overlap_with_previous": len(previous & accepted),
            "new_certified_unique": len(additions),
            "primary_certified_solved": len(union),
            "primary_certified_score": len(union) / total,
            "fully_guard_discharged_additions_claimed": 0,
        },
        "sets": {
            "previous_primary_union": sorted(previous),
            "rerun_accepted": sorted(accepted),
            "overlap_with_previous": sorted(previous & accepted),
            "new_certified_unique": sorted(additions),
            "primary_union": sorted(union),
            "unresolved_frozen_problems": sorted(frozen - union),
        },
        "native_trace_numerical_guard_counts": guard_counts,
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
        args.base.resolve(),
        args.cohort.resolve(),
        args.audit.resolve(),
        args.frozen_baseline.resolve(),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(artifact["summary"], ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
