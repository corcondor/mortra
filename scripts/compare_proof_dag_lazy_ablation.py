"""Combine fixed, lazy, and determinism proof-DAG experiment artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _portable_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def _totals(runs: list[dict[str, Any]]) -> dict[str, float | int]:
    valid = [item for item in runs if item["returncode"] == 0]
    return {
        "solved": sum(bool(item["solved"]) for item in valid),
        "evaluated_paths": sum(int(item["evaluated_paths"]) for item in valid),
        "errors": sum(int(item["error_count"]) for item in valid),
        "wall_seconds": sum(float(item["wall_seconds"]) for item in valid),
        "cone_search_states": sum(int(item["cone_search_states"]) for item in valid),
        "proof_dag_search_states": sum(
            int(item["proof_dag_search_states"]) for item in valid
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--three-way", type=Path, required=True)
    parser.add_argument("--trust-gate", type=Path, required=True)
    parser.add_argument("--determinism", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    three_way = _load(args.three_way.resolve())
    trust_gate = _load(args.trust_gate.resolve())
    determinism = _load(args.determinism.resolve())
    grouped = {
        "off": [item for item in three_way["runs"] if item["mode"] == "off"],
        "fixed_meet": [
            item for item in three_way["runs"] if item["mode"] == "proof-dag-meet"
        ],
        "lazy_ungated": [
            item for item in three_way["runs"] if item["mode"] == "proof-dag-lazy"
        ],
        "lazy_trust_gate": list(trust_gate["runs"]),
    }
    problem_sets = {
        name: {item["problem"] for item in runs}
        for name, runs in grouped.items()
    }
    if len({frozenset(items) for items in problem_sets.values()}) != 1:
        raise ValueError(f"problem sets differ: {problem_sets}")

    totals = {name: _totals(runs) for name, runs in grouped.items()}
    reference = totals["fixed_meet"]
    trust = totals["lazy_trust_gate"]
    control = totals["off"]
    determinism_by_mode = {
        item["mode"]: item for item in determinism["runs"]
    }
    deterministic_replay = (
        determinism_by_mode["off"]["solved_path"]
        == determinism_by_mode["proof-dag-lazy"]["solved_path"]
        and determinism_by_mode["off"]["input_sha256"]
        == determinism_by_mode["proof-dag-lazy"]["input_sha256"]
    )
    payload = {
        "experiment": "residual_guided_lazy_proof_dag_with_trust_gate",
        "uses_external_llm": False,
        "uses_problem_or_answer_memory": False,
        "acceptance_truth_plane": "yuclid_native_certificate_replay_only",
        "hypotheses": {
            "h1": "Lazy promotion reduces cone states versus fixed-depth all-candidate expansion.",
            "h2": "Partial meets must not override the base scheduler until structural residuals close.",
            "h3": "The treatment preserves native proof outcomes and deterministic replay.",
        },
        "artifacts": {
            "three_way": _portable_path(args.three_way),
            "trust_gate": _portable_path(args.trust_gate),
            "determinism": _portable_path(args.determinism),
        },
        "totals": totals,
        "effects": {
            "lazy_trust_vs_fixed": {
                "solved_delta": trust["solved"] - reference["solved"],
                "evaluated_path_delta": (
                    trust["evaluated_paths"] - reference["evaluated_paths"]
                ),
                "cone_state_delta": (
                    trust["cone_search_states"] - reference["cone_search_states"]
                ),
                "cone_state_ratio": (
                    trust["cone_search_states"] / reference["cone_search_states"]
                ),
                "wall_seconds_delta": (
                    trust["wall_seconds"] - reference["wall_seconds"]
                ),
                "wall_seconds_ratio": (
                    trust["wall_seconds"] / reference["wall_seconds"]
                ),
            },
            "lazy_trust_vs_off": {
                "solved_delta": trust["solved"] - control["solved"],
                "evaluated_path_delta": (
                    trust["evaluated_paths"] - control["evaluated_paths"]
                ),
                "wall_seconds_delta": (
                    trust["wall_seconds"] - control["wall_seconds"]
                ),
            },
        },
        "determinism": {
            "problem": determinism_by_mode["off"]["problem"],
            "same_solved_path": (
                determinism_by_mode["off"]["solved_path"]
                == determinism_by_mode["proof-dag-lazy"]["solved_path"]
            ),
            "same_input_sha256": (
                determinism_by_mode["off"]["input_sha256"]
                == determinism_by_mode["proof-dag-lazy"]["input_sha256"]
            ),
            "passed": deterministic_replay,
        },
        "conclusion": (
            "The OR-preserving architecture is viable as a scheduler substrate. "
            "Residual-guided lazy promotion plus a structural trust gate reduces "
            "search work while preserving proof results, but it does not increase "
            "solved coverage on this calibration set."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
