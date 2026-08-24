"""Merge certificate-backed development ledgers for frozen held-out search."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from worker.backend.terminal_trajectory_credit import (
    TerminalCreditEvent,
    TerminalCreditLedger,
)


def build_ledger(artifacts: list[Path]) -> dict[str, Any]:
    if not artifacts:
        raise ValueError("at least one development artifact is required")
    combined: TerminalCreditLedger | None = None
    sources: list[dict[str, Any]] = []
    observed_hashes: set[str] = set()
    for artifact_path in artifacts:
        raw = artifact_path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest in observed_hashes:
            raise ValueError(f"duplicate development artifact: {artifact_path}")
        observed_hashes.add(digest)
        artifact = json.loads(raw)
        if not isinstance(artifact, dict) or not artifact.get("solved"):
            raise ValueError(f"development artifact is not solved: {artifact_path}")
        payload = artifact.get("terminal_credit_ledger")
        if isinstance(payload, dict):
            ledger = TerminalCreditLedger.from_dict(payload)
        else:
            ledger = TerminalCreditLedger()
            for attempt in artifact.get("attempt_results", ()):
                if not isinstance(attempt, dict) or not attempt.get("solved"):
                    continue
                ledger.observe(
                    TerminalCreditEvent.from_dict(event)
                    for event in attempt.get("terminal_credit_events", ())
                )
            payload = ledger.to_dict()
        if not ledger.scores():
            raise ValueError(f"development artifact has no replayed credit: {artifact_path}")
        if combined is None:
            combined = TerminalCreditLedger(prior_weight=ledger.prior_weight)
        combined.merge(ledger)
        sources.append(
            {
                "artifact": artifact_path.resolve().as_posix(),
                "sha256": digest,
                "problem_name": artifact.get("problem_name"),
                "native_solved": True,
                "signature_count": payload.get("signature_count"),
                "event_count": payload.get("event_count"),
            }
        )
    assert combined is not None
    return {
        "experiment": "mortra_terminal_credit_development_ledger",
        "protocol": {
            "development_only": True,
            "held_out_updates": False,
            "uses_external_llm": False,
            "uses_problem_id_in_signature": False,
            "uses_expected_answer": False,
            "truth_plane": "native_certificate_replay_only",
        },
        "sources": sources,
        "terminal_credit_ledger": combined.to_dict(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = build_ledger([path.resolve() for path in args.artifact])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["terminal_credit_ledger"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
