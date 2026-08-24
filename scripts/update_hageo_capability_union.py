"""Extend a frozen HAGeo capability union with audited proof artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from worker.backend.certified_geometry_portfolio import (  # noqa: E402
    audit_geometry_artifact,
)
from scripts.hageo_frozen_split import (  # noqa: E402
    load_frozen_problem_names,
    require_frozen_membership,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    return (
        resolved.relative_to(ROOT).as_posix()
        if resolved.is_relative_to(ROOT)
        else resolved.as_posix()
    )


def _verified_problem(artifact_path: Path) -> tuple[str, dict[str, Any]]:
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    if not artifact.get("solved"):
        raise ValueError(f"artifact is not solved: {artifact_path}")
    certificate = artifact.get("certificate")
    if not isinstance(certificate, dict):
        raise ValueError(f"artifact has no certificate: {artifact_path}")
    proof_path = ROOT / str(certificate.get("proof_path", ""))
    if not proof_path.is_file():
        raise ValueError(f"certificate file is missing: {proof_path}")
    observed = _sha256(proof_path)
    expected = str(certificate.get("proof_file_sha256", ""))
    if observed != expected:
        raise ValueError(
            f"certificate hash mismatch for {artifact_path}: "
            f"expected={expected}, observed={observed}"
        )
    audit = audit_geometry_artifact(
        str(certificate.get("source") or "unknown"),
        artifact_path,
        root=ROOT,
    )
    if not audit.admitted:
        raise ValueError(
            f"certificate audit rejected {artifact_path}: {audit.reason}"
        )
    return str(artifact["problem_name"]), {
        "artifact": _display_path(artifact_path),
        "artifact_sha256": _sha256(artifact_path),
        "certificate_source": certificate.get("source"),
        "certificate_kind": audit.certificate_kind,
        "audit_reason": audit.reason,
        "proof_path": certificate["proof_path"],
        "proof_sha256": certificate.get("proof_sha256"),
        "proof_file_sha256": observed,
    }


def build_union(
    base_path: Path,
    additions: tuple[Path, ...],
    frozen_path: Path,
) -> dict[str, Any]:
    base = json.loads(base_path.read_text(encoding="utf-8"))
    previous = set(map(str, base["sets"]["primary_union"]))
    verified = dict(_verified_problem(path) for path in additions)
    added = set(verified)
    frozen_names = load_frozen_problem_names(frozen_path)
    require_frozen_membership(previous, frozen_names, label="base union")
    require_frozen_membership(added, frozen_names, label="submitted additions")
    union = previous | added
    total = len(frozen_names)
    if int(base["summary"]["total"]) != total:
        raise ValueError("base total does not match frozen split size")
    return {
        "experiment": "hageo_certified_capability_union_increment",
        "protocol": {
            "uses_external_llm": False,
            "uses_expected_answer": False,
            "double_counting": "set union by frozen problem name",
            "truth_plane": (
                "audited proof artifact with matching certificate file hash"
            ),
            "base_union": {
                "path": _display_path(base_path),
                "sha256": _sha256(base_path),
            },
            "frozen_split": {
                "path": _display_path(frozen_path),
                "sha256": _sha256(frozen_path),
            },
            "addition_artifacts": verified,
        },
        "summary": {
            "total": total,
            "previous_certified_solved": len(previous),
            "submitted_certified_solved": len(added),
            "overlap_with_previous": len(previous & added),
            "new_certified_unique": len(added - previous),
            "primary_certified_solved": len(union),
            "primary_certified_score": len(union) / total,
        },
        "sets": {
            "previous_primary_union": sorted(previous),
            "submitted_certified": sorted(added),
            "overlap_with_previous": sorted(previous & added),
            "new_certified_unique": sorted(added - previous),
            "primary_union": sorted(union),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--addition", type=Path, action="append", required=True)
    parser.add_argument("--frozen-baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build_union(
        args.base.resolve(),
        tuple(path.resolve() for path in args.addition),
        args.frozen_baseline.resolve(),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
