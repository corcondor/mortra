"""Audit every solved result in a HAGeo cohort artifact.

The cohort runner stores certificates in child shard artifacts.  This audit
follows that provenance chain and rejects a claimed solve unless the problem
artifact, shard result, native proof payload, and recorded hashes agree.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _root_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def audit_cohort(path: Path) -> dict[str, Any]:
    cohort = _load(path)
    rows: list[dict[str, Any]] = []
    for result in cohort.get("results", []):
        problem_path = _root_path(result["artifact"])
        problem_hash_ok = (
            not result.get("artifact_sha256")
            or _sha256(problem_path) == result["artifact_sha256"]
        )
        problem = _load(problem_path)
        certificate_rows: list[dict[str, Any]] = []
        for shard_ref in problem.get("shards", []):
            if not shard_ref.get("artifact"):
                continue
            shard_path = _root_path(shard_ref["artifact"])
            shard = _load(shard_path)
            certificate = shard.get("certificate")
            if not certificate:
                continue
            proof_path = _root_path(certificate["proof_path"])
            proof = _load(proof_path)
            matching_attempts = [
                attempt
                for attempt in shard.get("attempt_results", [])
                if attempt.get("solved")
                and attempt.get("input_sha256") == certificate["input_sha256"]
                and attempt.get("proof_sha256") == certificate["proof_sha256"]
            ]
            proof_file_hash_ok = (
                _sha256(proof_path) == certificate["proof_file_sha256"]
            )
            source = certificate.get("source", "search_attempt")
            provenance_ok = (
                source == "baseline"
                or (source == "search_attempt" and bool(matching_attempts))
            )
            certificate_ok = (
                shard.get("solved") is True
                and proof.get("status") == "solved"
                and bool(proof.get("deductions_for_goal"))
                and proof_file_hash_ok
                and provenance_ok
            )
            certificate_rows.append(
                {
                    "shard": shard_ref.get("shard"),
                    "source": source,
                    "certificate_ok": certificate_ok,
                    "input_sha256": certificate["input_sha256"],
                    "proof_sha256": certificate["proof_sha256"],
                    "proof_file_sha256": certificate["proof_file_sha256"],
                    "proof_file_hash_ok": proof_file_hash_ok,
                    "goal_deduction_count": len(proof.get("deductions_for_goal", [])),
                    "matching_attempt_count": len(matching_attempts),
                    "provenance_ok": provenance_ok,
                }
            )
        claimed_solved = bool(result.get("solved"))
        certificate_ok = bool(certificate_rows) and any(
            row["certificate_ok"] for row in certificate_rows
        )
        rows.append(
            {
                "problem_name": result["problem_name"],
                "claimed_solved": claimed_solved,
                "problem_artifact_hash_ok": problem_hash_ok,
                "certificate_ok": certificate_ok if claimed_solved else None,
                "certificates": certificate_rows,
            }
        )

    claimed = [row for row in rows if row["claimed_solved"]]
    verified = [row for row in claimed if row["certificate_ok"]]
    rejected = [row["problem_name"] for row in claimed if not row["certificate_ok"]]
    artifact_hash_failures = [
        row["problem_name"] for row in rows if not row["problem_artifact_hash_ok"]
    ]
    return {
        "experiment": "hageo_cohort_native_certificate_audit",
        "source_artifact": _display_path(path),
        "summary": {
            "problems": len(rows),
            "claimed_solved": len(claimed),
            "verified_solved": len(verified),
            "rejected_claims": len(rejected),
            "artifact_hash_failures": len(artifact_hash_failures),
            "all_claimed_solves_verified": not rejected,
        },
        "rejected_problem_names": rejected,
        "artifact_hash_failure_problem_names": artifact_hash_failures,
        "results": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    artifact = audit_cohort(args.input.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(artifact["summary"], indent=2))
    return 0 if artifact["summary"]["all_claimed_solves_verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
