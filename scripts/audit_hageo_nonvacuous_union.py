"""Re-audit a chained HAGeo union and remove vacuous unit-ideal proofs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from worker.backend.certified_geometry_portfolio import (  # noqa: E402
    audit_geometry_artifact,
)
from scripts.hageo_frozen_split import load_frozen_problem_names  # noqa: E402


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve(root: Path, value: object) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else root / path


def _display(root: Path, path: Path) -> str:
    resolved = path.resolve()
    return (
        resolved.relative_to(root.resolve()).as_posix()
        if resolved.is_relative_to(root.resolve())
        else resolved.as_posix()
    )


def _unit_ideal_basis(proof: Mapping[str, Any]) -> bool:
    certificate = proof.get("certificate")
    if not isinstance(certificate, Mapping):
        return False
    basis = tuple(map(str, certificate.get("groebner_basis", ())))
    return basis in {("1",), ("-1",)}


def audit_nonvacuous_union(
    union_path: Path,
    *,
    frozen_path: Path,
    root: Path = ROOT,
) -> dict[str, Any]:
    """Trace all incremental ledgers and exclude exact proofs of an empty setup."""

    union_path = union_path.resolve()
    root = root.resolve()
    top = _load(union_path)
    frozen_path = frozen_path.resolve()
    frozen = set(load_frozen_problem_names(frozen_path))
    total = len(frozen)
    if int(top["summary"]["total"]) != total:
        raise ValueError("union total does not match frozen split size")
    claimed = set(map(str, top["sets"]["primary_union"]))
    outside_split = claimed - frozen
    excluded: dict[str, dict[str, object]] = {}
    audited: dict[str, dict[str, object]] = {}
    chain: list[dict[str, object]] = []
    seen: set[Path] = set()
    current = union_path

    while current not in seen:
        seen.add(current)
        payload = _load(current)
        protocol = payload.get("protocol", {})
        additions = protocol.get("addition_artifacts", {})
        if not isinstance(additions, Mapping):
            raise ValueError(f"invalid addition_artifacts in {current}")
        chain.append(
            {
                "path": _display(root, current),
                "sha256": _sha256(current),
                "reported_solved": payload.get("summary", {}).get(
                    "primary_certified_solved"
                ),
                "addition_count": len(additions),
            }
        )
        for problem, raw_metadata in additions.items():
            if not isinstance(raw_metadata, Mapping):
                raise ValueError(f"invalid addition metadata for {problem}")
            metadata = dict(raw_metadata)
            proof_path = _resolve(root, metadata.get("proof_path", ""))
            artifact_path = _resolve(root, metadata.get("artifact", ""))
            if not proof_path.is_file() or not artifact_path.is_file():
                raise ValueError(f"missing proof or artifact for {problem}")
            observed_proof_hash = _sha256(proof_path)
            if observed_proof_hash != str(metadata.get("proof_file_sha256", "")):
                raise ValueError(f"proof hash mismatch for {problem}")
            certificate_source = str(metadata.get("certificate_source") or "unknown")
            proof = (
                _load(proof_path)
                if certificate_source in {
                    "jgex_exact_elimination",
                    "baseline_jgex_exact",
                }
                else None
            )
            if proof is not None and _unit_ideal_basis(proof):
                exact = proof.get("certificate", {})
                artifact_payload = _load(artifact_path)
                artifact_certificate = artifact_payload.get("certificate", {})
                excluded[str(problem)] = {
                    "reason": (
                        "integrity_verified_but_unit_groebner_basis_has_no_"
                        "independent_nonempty_witness"
                    ),
                    "artifact": _display(root, artifact_path),
                    "proof_path": _display(root, proof_path),
                    "proof_file_sha256": observed_proof_hash,
                    "proof_file_hash_matches_metadata": True,
                    "internal_certificate_sha256": exact.get(
                        "certificate_sha256"
                    ),
                    "internal_certificate_hash_matches_artifact": (
                        isinstance(artifact_certificate, Mapping)
                        and exact.get("certificate_sha256")
                        == artifact_certificate.get("proof_sha256")
                    ),
                    "exact_replay": exact.get("exact_replay") is True,
                    "remainder": exact.get("remainder"),
                    "groebner_basis": exact.get("groebner_basis"),
                    "construction_consistency_field_present": (
                        "construction_consistency" in exact
                    ),
                    "independent_nonempty_witness_present": bool(
                        exact.get("nonempty_witness")
                    ),
                    "mathematical_conclusion_status": (
                        "not_refuted_but_not_certified_by_this_artifact"
                    ),
                }
                continue
            audit = audit_geometry_artifact(
                certificate_source,
                artifact_path,
                root=root,
            )
            if not audit.admitted:
                raise ValueError(
                    f"non-unit addition failed certificate audit for {problem}: "
                    f"{audit.reason}"
                )
            audited[str(problem)] = {
                "certificate_kind": audit.certificate_kind,
                "reason": audit.reason,
                "artifact": _display(root, artifact_path),
                "proof_path": _display(root, proof_path),
            }

        base = protocol.get("base_union")
        if not isinstance(base, Mapping) or not base.get("path"):
            break
        next_path = _resolve(root, base["path"]).resolve()
        if not next_path.is_file():
            raise ValueError(f"base union is missing: {next_path}")
        if _sha256(next_path) != str(base.get("sha256", "")):
            raise ValueError(f"base union hash mismatch: {next_path}")
        current = next_path

    strict = (claimed & frozen) - set(excluded)
    excluded_unique = outside_split | set(excluded)
    unresolved = frozen - strict
    return {
        "experiment": "hageo_nonvacuous_capability_union_audit",
        "protocol": {
            "uses_external_llm": False,
            "uses_expected_answer": False,
            "truth_plane": "audited proof artifact with matching certificate file hash",
            "consistency_policy": (
                "unit Groebner ideals are rejected unless an independent "
                "non-emptiness witness is replayed"
            ),
            "source_union": {
                "path": _display(root, union_path),
                "sha256": _sha256(union_path),
            },
            "frozen_split": {
                "path": _display(root, frozen_path),
                "sha256": _sha256(frozen_path),
            },
            "audited_chain": chain,
        },
        "summary": {
            "total": total,
            "claimed_certified_solved": len(claimed),
            "claimed_inside_frozen_split": len(claimed & frozen),
            "excluded_outside_frozen_split": len(outside_split),
            "excluded_vacuous_unit_ideal": len(excluded),
            "excluded_unique_total": len(excluded_unique),
            "primary_certified_solved": len(strict),
            "primary_certified_score": len(strict) / total,
            "unresolved_frozen_problems": len(unresolved),
        },
        "sets": {
            "claimed_primary_union": sorted(claimed),
            "excluded_outside_frozen_split": sorted(outside_split),
            "excluded_vacuous_unit_ideal": sorted(excluded),
            "primary_union": sorted(strict),
            "unresolved_frozen_problems": sorted(unresolved),
        },
        "excluded_artifacts": excluded,
        "audited_incremental_artifacts": audited,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--union", type=Path, required=True)
    parser.add_argument("--frozen-baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit_nonvacuous_union(
        args.union,
        frozen_path=args.frozen_baseline,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
