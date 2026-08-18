"""Verify the published claims of the lazy proof-DAG experiment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _source_path(artifact: Path, value: str) -> Path:
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    cwd_candidate = Path.cwd() / candidate
    if cwd_candidate.exists():
        return cwd_candidate
    return artifact.resolve().parent.parent / candidate


def _totals(runs: list[dict[str, object]]) -> dict[str, int]:
    valid = [item for item in runs if item["returncode"] == 0]
    return {
        "solved": sum(bool(item["solved"]) for item in valid),
        "evaluated_paths": sum(int(item["evaluated_paths"]) for item in valid),
        "errors": sum(int(item["error_count"]) for item in valid),
        "cone_search_states": sum(int(item["cone_search_states"]) for item in valid),
        "proof_dag_search_states": sum(
            int(item["proof_dag_search_states"]) for item in valid
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.artifact.read_text(encoding="utf-8"))

    assert payload["uses_external_llm"] is False
    assert payload["uses_problem_or_answer_memory"] is False
    assert payload["acceptance_truth_plane"] == "yuclid_native_certificate_replay_only"
    totals = payload["totals"]
    fixed = totals["fixed_meet"]
    lazy = totals["lazy_trust_gate"]
    control = totals["off"]
    three_way = json.loads(
        _source_path(args.artifact, payload["artifacts"]["three_way"]).read_text(
            encoding="utf-8"
        )
    )
    trust_gate = json.loads(
        _source_path(args.artifact, payload["artifacts"]["trust_gate"]).read_text(
            encoding="utf-8"
        )
    )
    determinism = json.loads(
        _source_path(args.artifact, payload["artifacts"]["determinism"]).read_text(
            encoding="utf-8"
        )
    )
    source_groups = {
        "off": [item for item in three_way["runs"] if item["mode"] == "off"],
        "fixed_meet": [
            item for item in three_way["runs"] if item["mode"] == "proof-dag-meet"
        ],
        "lazy_ungated": [
            item for item in three_way["runs"] if item["mode"] == "proof-dag-lazy"
        ],
        "lazy_trust_gate": trust_gate["runs"],
    }
    for name, runs in source_groups.items():
        source_totals = _totals(runs)
        for key, value in source_totals.items():
            assert totals[name][key] == value
    assert lazy["solved"] == fixed["solved"] == control["solved"]
    assert lazy["errors"] == fixed["errors"] == control["errors"] == 0
    assert lazy["cone_search_states"] < fixed["cone_search_states"]
    assert lazy["evaluated_paths"] < fixed["evaluated_paths"]
    assert lazy["evaluated_paths"] < control["evaluated_paths"]
    determinism_by_mode = {item["mode"]: item for item in determinism["runs"]}
    assert (
        determinism_by_mode["off"]["input_sha256"]
        == determinism_by_mode["proof-dag-lazy"]["input_sha256"]
    )
    assert (
        determinism_by_mode["off"]["solved_path"]
        == determinism_by_mode["proof-dag-lazy"]["solved_path"]
    )
    assert payload["determinism"]["passed"] is True
    print(
        json.dumps(
            {
                "solved": lazy["solved"],
                "evaluated_paths": lazy["evaluated_paths"],
                "cone_search_states": lazy["cone_search_states"],
                "deterministic_replay": True,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
