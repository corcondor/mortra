"""Verify the published exact candidate-gate ablation summary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()
    artifact = json.loads(args.artifact.read_text(encoding="utf-8"))
    assert artifact["experiment"] == "exact_pre_evaluation_candidate_gate_ablation"
    assert artifact["uses_external_llm"] is False
    assert artifact["uses_problem_or_answer_memory"] is False
    assert artifact["pairs"]
    assert all(pair["valid_pair"] for pair in artifact["pairs"])
    assert all(pair["proof_preserved"] for pair in artifact["pairs"])

    runs = artifact["runs"]
    off = [run for run in runs if run["mode"] == "off"]
    combined = [run for run in runs if run["mode"] == "combined"]
    assert len(off) == len(combined) == len(artifact["pairs"])
    off_paths = sum(run["evaluated_paths"] for run in off)
    combined_paths = sum(run["evaluated_paths"] for run in combined)
    off_errors = sum(run["error_count"] for run in off)
    combined_errors = sum(run["error_count"] for run in combined)
    assert combined_paths <= off_paths
    assert combined_errors == 0
    assert combined_errors < off_errors
    print(
        json.dumps(
            {
                "pairs": len(artifact["pairs"]),
                "proofs_preserved": sum(
                    pair["proof_preserved"] for pair in artifact["pairs"]
                ),
                "evaluated_paths": {"off": off_paths, "combined": combined_paths},
                "errors": {"off": off_errors, "combined": combined_errors},
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
