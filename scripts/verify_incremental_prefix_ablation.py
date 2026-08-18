"""Verify the acceptance conditions of an incremental-prefix ablation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()

    artifact = json.loads(args.artifact.read_text(encoding="utf-8"))
    assert artifact["uses_external_llm"] is False
    assert artifact["uses_problem_or_answer_memory"] is False
    runs = {run["mode"]: run for run in artifact["runs"]}
    assert set(runs) == {"prefix-replay", "incremental"}
    replay = runs["prefix-replay"]
    incremental = runs["incremental"]
    assert replay["returncode"] == incremental["returncode"] == 0
    assert replay["solved"] == incremental["solved"]
    assert replay["solved_path"] == incremental["solved_path"]
    assert replay["evaluated_paths"] == incremental["evaluated_paths"]
    assert replay["error_count"] == incremental["error_count"]
    assert replay["input_sha256"]
    assert replay["input_sha256"] == incremental["input_sha256"]
    assert artifact["equivalent_exact_input_and_search_result"] is True
    assert incremental["prefix_state_cache"]["transition_count"] > 0
    print(
        json.dumps(
            {
                "verified": True,
                "problem": artifact["problem"],
                "wall_seconds_delta": artifact["wall_seconds_delta"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
