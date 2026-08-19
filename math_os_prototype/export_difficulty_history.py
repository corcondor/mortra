"""Recompute reproducible MathOS pool metrics from Git snapshots.

The historical difficulty score is deliberately excluded from the primary
series: its observed AUC against human judgements is only 0.086.  This report
tracks certified structural depth and verification coverage instead.
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


POOL_PATH = "problem_synthesis/entrance_exam_pool.json"
HUMAN_DIFFICULTY_AUC = 0.086


def _git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], stderr=subprocess.DEVNULL)


def _rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("problems", "items", "pool"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return []


def _chain(record: dict[str, Any]) -> list[str]:
    curriculum = record.get("curriculum_certificate") or {}
    lift = record.get("lift_certificate") or {}
    chain = curriculum.get("abstract_morphism_chain") or lift.get("morphism_chain") or []
    return [str(step) for step in chain]


def _lowering_chain(record: dict[str, Any]) -> list[str]:
    certificate = record.get("curriculum_certificate") or {}
    chain = certificate.get("lowering_chain") or []
    return [str(step) for step in chain]


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = round(q * (len(ordered) - 1))
    return float(ordered[index])


def _median(values: list[float]) -> float:
    return round(float(statistics.median(values)), 3) if values else 0.0


def _snapshot(commit: str, timestamp: str, message: str) -> dict[str, Any]:
    payload = json.loads(_git("show", f"{commit}:{POOL_PATH}"))
    rows = _rows(payload)
    depths = [len(_chain(row)) for row in rows]
    primitive_counts = [len(set(_lowering_chain(row))) for row in rows]
    verified = [
        row
        for row in rows
        if (row.get("verification") or {}).get("exact_backend") is True
        and (row.get("verification") or {}).get("independent_check") is True
    ]
    structures = {
        str(row.get("structure_key"))
        for row in rows
        if row.get("structure_key")
    }
    families = {
        str(row.get("family_id"))
        for row in rows
        if row.get("family_id")
    }
    similarities = [
        float((row.get("novelty") or {}).get("maximum_surface_jaccard"))
        for row in rows
        if isinstance((row.get("novelty") or {}).get("maximum_surface_jaccard"), (int, float))
    ]
    return {
        "commit": commit[:8],
        "timestamp": timestamp,
        "message": message,
        "problem_count": len(rows),
        "family_count": len(families),
        "unique_structure_count": len(structures),
        "unique_structure_rate": round(len(structures) / len(rows), 4) if rows else 0.0,
        "verified_count": len(verified),
        "verified_rate": round(len(verified) / len(rows), 4) if rows else 0.0,
        "morphism_depth": {
            "median": _median(depths),
            "p90": _percentile(depths, 0.90),
            "max": max(depths, default=0),
        },
        "distinct_school_primitives": {
            "median": _median(primitive_counts),
            "p90": _percentile(primitive_counts, 0.90),
            "max": max(primitive_counts, default=0),
        },
        "surface_similarity_median": _median(similarities),
    }


def build_history() -> dict[str, Any]:
    fmt = "%H%x1f%aI%x1f%s%x1e"
    raw = _git("log", "--all", f"--pretty=format:{fmt}", "--", POOL_PATH).decode("utf-8")
    records: list[tuple[str, str, str]] = []
    for entry in raw.split("\x1e"):
        fields = entry.strip().split("\x1f", 2)
        if len(fields) == 3:
            records.append((fields[0], fields[1], fields[2]))
    snapshots = [_snapshot(*record) for record in reversed(records)]
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "source": {
            "repository": "math_os_prototype",
            "path": POOL_PATH,
            "snapshot_count": len(snapshots),
        },
        "interpretation": {
            "primary_metric": "certified morphism-chain depth",
            "not_human_difficulty": True,
            "human_difficulty_auc": HUMAN_DIFFICULTY_AUC,
            "warning": (
                "Structural depth measures the number of certified transformations. "
                "It is not yet a calibrated estimate of difficulty perceived by humans."
            ),
        },
        "snapshots": snapshots,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build_history()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "snapshots": len(report["snapshots"]),
        "output": str(args.output),
        "latest": report["snapshots"][-1] if report["snapshots"] else None,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
