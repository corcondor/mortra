"""Reduce cProfile files to a small auditable HAGeo timing artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import pstats
from pathlib import Path


def function_stats(profile: Path, function: str) -> dict[str, float | int]:
    stats = pstats.Stats(str(profile))
    matches = [values for key, values in stats.stats.items() if key[2] == function]
    if len(matches) != 1:
        raise ValueError(f"expected one {function!r} entry in {profile}, got {len(matches)}")
    primitive, total, own, cumulative, _callers = matches[0]
    return {
        "primitive_calls": primitive,
        "total_calls": total,
        "own_seconds": own,
        "cumulative_seconds": cumulative,
    }


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--before-profile", type=Path, required=True)
    parser.add_argument("--after-profile", type=Path, required=True)
    parser.add_argument("--before-artifact", type=Path, required=True)
    parser.add_argument("--after-artifact", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    before_enum = function_stats(args.before_profile, "enumerate_typed_candidates")
    after_enum = function_stats(args.after_profile, "enumerate_typed_candidates")
    candidate_calls = function_stats(args.after_profile, "numerical_precondition_holds")
    rank_calls_before = function_stats(args.before_profile, "_generated_role_signature")
    rank_calls_after = function_stats(args.after_profile, "ranked_candidate")
    before = json.loads(args.before_artifact.read_text(encoding="utf-8"))
    after = json.loads(args.after_artifact.read_text(encoding="utf-8"))
    before_elapsed = float(before["attempt_results"][0]["elapsed_seconds"])
    after_elapsed = float(after["attempt_results"][0]["elapsed_seconds"])

    payload = {
        "experiment": "hageo_passk_cpu_profile_summary",
        "measured_cpu": {
            "candidate_count": int(candidate_calls["total_calls"]),
            "before_attempt_seconds": before_elapsed,
            "after_lazy_attempt_seconds": after_elapsed,
            "observed_software_speedup": before_elapsed / after_elapsed,
            "before_enumeration_seconds_profiled": before_enum["cumulative_seconds"],
            "after_enumeration_seconds_profiled": after_enum["cumulative_seconds"],
            "enumeration_speedup_profiled": (
                float(before_enum["cumulative_seconds"])
                / float(after_enum["cumulative_seconds"])
            ),
            "old_generated_role_signature_calls": rank_calls_before["total_calls"],
            "new_ranked_candidate_calls": rank_calls_after["total_calls"],
        },
        "source_sha256": {
            "before_profile": sha256(args.before_profile),
            "after_profile": sha256(args.after_profile),
            "before_artifact": sha256(args.before_artifact),
            "after_artifact": sha256(args.after_artifact),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
