"""Verify protocol integrity for the OR-preserving proof-DAG ablation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()
    artifact = json.loads(args.artifact.read_text(encoding="utf-8"))

    assert artifact["experiment"] == "or_preserving_proof_dag_meet_ablation"
    assert artifact["uses_external_llm"] is False
    assert artifact["uses_problem_or_answer_memory"] is False
    assert artifact["acceptance_truth_plane"] == "yuclid_native_certificate_replay_only"
    assert artifact["pairs"]
    assert all(item["valid_pair"] for item in artifact["pairs"])
    assert all(item["control_success_preserved"] for item in artifact["pairs"])
    assert all(item["same_solved_status"] for item in artifact["pairs"])
    assert len(artifact["runs"]) == 2 * len(artifact["pairs"])

    print(
        json.dumps(
            {
                "pairs": len(artifact["pairs"]),
                "control_successes_preserved": sum(
                    item["control_success_preserved"] for item in artifact["pairs"]
                ),
                "totals": artifact["totals"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
