"""Replay and cross-check exact-chart artifacts from a transfer audit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from worker.backend.certified_geometry_portfolio import (  # noqa: E402
    audit_geometry_artifact,
)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve(root: Path, value: object) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else root / path


def audit_transfer_artifacts(
    *,
    transfer_report_path: Path,
    artifact_dir: Path,
    root: Path = ROOT,
) -> dict[str, object]:
    transfer = _load(transfer_report_path)
    expected = set(map(str, transfer.get("sets", {}).get("strict_matches", ())))
    observed = {
        path.name.removesuffix(".artifact.json")
        for path in artifact_dir.glob("*.artifact.json")
    }
    missing = sorted(expected - observed)
    unexpected = sorted(observed - expected)
    if missing or unexpected:
        raise ValueError(
            f"artifact cohort mismatch: missing={missing}, unexpected={unexpected}"
        )

    audits: dict[str, dict[str, object]] = {}
    total_residuals = 0
    for name in sorted(expected):
        artifact_path = artifact_dir / f"{name}.artifact.json"
        artifact = _load(artifact_path)
        certificate = artifact.get("certificate") or {}
        proof_path = _resolve(root, certificate.get("proof_path", ""))
        proof = _load(proof_path)
        selected = proof.get("selected") or {}
        chart = selected.get("certificate") or {}
        application = selected.get("application") or {}
        transfer_row = transfer["results"][name]
        native = audit_geometry_artifact(
            "exact_chart_transfer",
            artifact_path,
            root=root,
        )
        residuals = chart.get("replay_residuals") or {}
        checks = {
            "native_certificate_replay": native.admitted,
            "artifact_solved": artifact.get("solved") is True,
            "problem_name": artifact.get("problem_name") == name,
            "strict_transfer_match": transfer_row.get("strict_match") is True,
            "chart_id": selected.get("chart_id") == transfer_row.get("chart_id"),
            "chart_certificate_hash": (
                selected.get("chart_certificate_sha256")
                == transfer_row.get("certificate_sha256")
                == certificate.get("proof_sha256")
            ),
            "source_hash": (
                proof.get("source_sha256")
                == transfer_row.get("source_sha256")
                == certificate.get("input_sha256")
            ),
            "no_quantifier_repair": application.get(
                "formalization_repair_required", False
            )
            is not True,
            "not_ambiguous": proof.get("ambiguous") is False,
            "nonempty_zero_residuals": bool(residuals)
            and all(str(value) == "0" for value in residuals.values()),
        }
        failed = sorted(key for key, passed in checks.items() if not passed)
        total_residuals += len(residuals)
        audits[name] = {
            "accepted": not failed,
            "failed_checks": failed,
            "native_reason": native.reason,
            "certificate_kind": native.certificate_kind,
            "chart_id": transfer_row.get("chart_id"),
            "certificate_sha256": transfer_row.get("certificate_sha256"),
            "replay_residual_count": len(residuals),
        }

    accepted = sum(bool(row["accepted"]) for row in audits.values())
    return {
        "experiment": "exact_chart_complement_transfer_artifact_replay",
        "protocol": {
            "uses_external_llm": False,
            "uses_expected_answer": False,
            "uses_problem_id_in_solver": False,
            "transfer_report": transfer_report_path.as_posix(),
            "artifact_dir": artifact_dir.as_posix(),
            "truth_plane": "native exact-chart certificate replay and hash-chain audit",
        },
        "summary": {
            "expected": len(expected),
            "audited": len(audits),
            "accepted": accepted,
            "rejected": len(audits) - accepted,
            "replay_residuals": total_residuals,
        },
        "audits": audits,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transfer-report", type=Path, required=True)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit_transfer_artifacts(
        transfer_report_path=args.transfer_report,
        artifact_dir=args.artifact_dir,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    return 0 if not result["summary"]["rejected"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
