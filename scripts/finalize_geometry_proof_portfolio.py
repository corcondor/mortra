#!/usr/bin/env python3
"""Merge independently replayed geometry proofs into one auditable portfolio.

This script never attempts a proof and never infers success from a numerical
score.  A construction result is admitted only when its native confirmation
contains the input and proof hashes.  A Wu/Groebner result is admitted only
when the zero decomposition reports a complete cover and replayed identities.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _confirmed_construction(payload: dict[str, Any]) -> bool:
    confirmation = payload.get("confirmation") or {}
    return bool(
        payload.get("solved")
        and confirmation.get("solved")
        and confirmation.get("input_sha256")
        and confirmation.get("proof_sha256")
    )


def _confirmed_zero_decomposition(result: dict[str, Any]) -> bool:
    decomposition = result.get("decomposition") or result.get("result") or result
    return bool(
        decomposition.get("coverage_complete")
        and (
            decomposition.get("all_computed_identities_replayed")
            or decomposition.get("all_identities_replayed")
        )
        and decomposition.get("unresolved_leaf_count") == 0
    )


def _zero_decomposition_entries(
    payload: dict[str, Any], path: Path
) -> list[tuple[str, dict[str, Any]]]:
    results = payload.get("results")
    if isinstance(results, dict):
        return [(str(problem), result) for problem, result in results.items()]
    problem = str(payload.get("problem_name") or path.stem)
    return [(problem, payload)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument(
        "--construction",
        type=Path,
        action="append",
        default=[],
        help="Native construction-search result with confirmation hashes.",
    )
    parser.add_argument(
        "--zero-decomposition",
        type=Path,
        action="append",
        default=[],
        help="Wu/Groebner zero-decomposition result.",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    baseline = _load(args.baseline)
    summary = baseline.get("summary") or {}
    total = int(summary["total"])
    accepted: dict[str, dict[str, Any]] = {
        name: {
            "problem": name,
            "source": "baseline",
            "artifact": str(args.baseline),
            "artifact_sha256": _sha256(args.baseline),
        }
        for name in summary.get("portfolio_names", [])
    }
    rejected: list[dict[str, Any]] = []

    for path in args.construction:
        payload = _load(path)
        problem = str(payload.get("problem_name") or path.stem)
        if not _confirmed_construction(payload):
            rejected.append(
                {
                    "problem": problem,
                    "source": "construction",
                    "artifact": str(path),
                    "reason": "missing_native_confirmation",
                }
            )
            continue
        accepted[problem] = {
            "problem": problem,
            "source": "construction_native_replay",
            "artifact": str(path),
            "artifact_sha256": _sha256(path),
            "solved_path": payload.get("solved_path"),
            "input_sha256": payload["confirmation"]["input_sha256"],
            "proof_sha256": payload["confirmation"]["proof_sha256"],
        }

    for path in args.zero_decomposition:
        payload = _load(path)
        for problem, result in _zero_decomposition_entries(payload, path):
            if not _confirmed_zero_decomposition(result):
                rejected.append(
                    {
                        "problem": problem,
                        "source": "wu_groebner",
                        "artifact": str(path),
                        "reason": "incomplete_or_unreplayed_cover",
                    }
                )
                continue
            accepted[problem] = {
                "problem": problem,
                "source": "wu_groebner_complete_cover",
                "artifact": str(path),
                "artifact_sha256": _sha256(path),
            }

    accepted_names = sorted(accepted)
    baseline_names = set(summary.get("portfolio_names", []))
    additions = sorted(set(accepted_names) - baseline_names)
    output = {
        "experiment": "geometry-proof-portfolio",
        "protocol": {
            "acceptance": (
                "native proof replay with input/proof hashes, or complete "
                "Wu/Groebner zero-set cover with replayed identities"
            ),
            "forbidden": [
                "numerical-only acceptance",
                "conditional regular-locus proof counted as total proof",
                "problem answer lookup",
            ],
        },
        "summary": {
            "baseline_solved": len(baseline_names),
            "newly_admitted": len(additions),
            "portfolio_solved": len(accepted_names),
            "total": total,
            "portfolio_score": len(accepted_names) / total,
            "new_problem_names": additions,
            "portfolio_names": accepted_names,
        },
        "accepted": [accepted[name] for name in accepted_names],
        "rejected": rejected,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(output["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
