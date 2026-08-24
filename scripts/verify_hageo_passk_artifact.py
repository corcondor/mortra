"""Replay a solved HAGeo Pass@K trajectory from its typed construction path."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.experiment_newclid_construction_stalk import (  # noqa: E402
    ConstructionStep,
    JGEXFormulation,
    JGEXProblemBuilder,
    build_branch,
    build_prefix_stable_branch,
    jgex_formulation_from_txt_file,
    normalize_legacy_formulation,
)
from worker.backend.yuclid_native_verifier import verify_problem  # noqa: E402


STEP_PATTERN = re.compile(r"^(?P<family>[^()]+)\((?P<inputs>.*)\)->(?P<output>[^,()]+)$")


def _parse_step(raw: str) -> ConstructionStep:
    match = STEP_PATTERN.fullmatch(raw)
    if match is None:
        raise ValueError(f"invalid construction step: {raw}")
    inputs = tuple(item for item in match.group("inputs").split(",") if item)
    return ConstructionStep(match.group("family"), match.group("output"), inputs)


def _solved_trajectory(
    artifact: dict[str, object],
) -> tuple[int | None, int, list[str], str, dict[str, object]]:
    """Normalize legacy Pass@K and current auxiliary-search artifacts."""

    protocol = artifact.get("protocol")
    if not isinstance(protocol, dict):
        raise ValueError("artifact has no protocol")
    seed = int(protocol["seed"])
    attempt_results = artifact.get("attempt_results")
    if isinstance(attempt_results, list):
        solved = next(
            (
                item
                for item in attempt_results
                if isinstance(item, dict) and item.get("solved")
            ),
            None,
        )
        if solved is None:
            raise ValueError("artifact has no solved attempt")
        attempt = int(solved["attempt"])
        attempt_seed = seed + 1_000_003 * attempt
        path = [str(item) for item in solved["path"]]
        raw_expected = artifact.get("certificate") or {
            "input_sha256": solved.get("input_sha256"),
            "proof_sha256": solved.get("proof_sha256"),
        }
        branch_build_mode = "full-path"
    elif artifact.get("solved") and artifact.get("solved_path"):
        attempt = None
        attempt_seed = seed
        path = [str(item) for item in artifact["solved_path"]]
        raw_expected = artifact.get("confirmation") or {}
        branch_build_mode = str(protocol.get("branch_build_mode", "full-path"))
    else:
        raise ValueError("artifact has no solved trajectory")
    if not isinstance(raw_expected, dict):
        raise ValueError("artifact certificate has an invalid shape")
    return attempt, attempt_seed, path, branch_build_mode, raw_expected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--yuclid-exe", type=Path, required=True)
    parser.add_argument("--runtime-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ar-profile", choices=("ratio-only", "standard", "all"), default="all")
    args = parser.parse_args()

    artifact = json.loads(args.artifact.read_text(encoding="utf-8"))
    seed = int(artifact["protocol"]["seed"])
    attempt, attempt_seed, path, branch_build_mode, expected = _solved_trajectory(
        artifact
    )
    steps = tuple(_parse_step(item) for item in path)

    formulations = jgex_formulation_from_txt_file(args.dataset.resolve())
    raw = formulations[artifact["problem_name"]]
    raw = JGEXFormulation(
        name=raw.name,
        setup_clauses=raw.setup_clauses,
        auxiliary_clauses=(),
        goals=raw.goals,
    )
    def replay_once() -> tuple[object, object]:
        builder = JGEXProblemBuilder(np.random.default_rng(seed))
        formulation, normalization = normalize_legacy_formulation(raw, builder.jgex_defs)
        base_problem = (
            builder.with_problem(formulation)
            .include_auxiliary_clauses(False)
            .build()
        )
        replay_problem = (
            build_prefix_stable_branch(base_problem, steps, seed=attempt_seed)
            if branch_build_mode in {"incremental", "prefix-replay"}
            else build_branch(base_problem, steps, seed=attempt_seed)
        )
        replay = verify_problem(
            replay_problem,
            yuclid_exe=args.yuclid_exe.resolve(),
            ar_profile=args.ar_profile,
        )
        return replay, normalization

    replay, normalization = replay_once()
    repeated, _ = replay_once()
    input_hash_matches = replay.input_sha256 == expected.get("input_sha256")
    proof_hash_matches = replay.proof_sha256 == expected.get("proof_sha256")
    expected_hashes_present = bool(
        expected.get("input_sha256") and expected.get("proof_sha256")
    )
    result = {
        "experiment": "hageo_passk_independent_certificate_replay",
        "problem_name": artifact["problem_name"],
        "source_artifact": args.artifact.resolve().relative_to(ROOT).as_posix(),
        "attempt": attempt,
        "attempt_seed": attempt_seed,
        "path": path,
        "branch_build_mode": branch_build_mode,
        "normalization": {
            "rewritten_constructions": normalization.rewritten_constructions,
            "unchanged_constructions": normalization.unchanged_constructions,
            "unresolved_constructions": normalization.unresolved_constructions,
        },
        "replay_solved": replay.solved,
        "input_sha256": replay.input_sha256,
        "proof_sha256": replay.proof_sha256,
        "expected_hashes_present": expected_hashes_present,
        "input_hash_matches": input_hash_matches,
        "proof_hash_matches": proof_hash_matches,
        "repeat_replay_solved": repeated.solved,
        "repeat_input_hash_matches": replay.input_sha256 == repeated.input_sha256,
        "repeat_proof_hash_matches": replay.proof_sha256 == repeated.proof_sha256,
        "source_byte_hash_note": (
            "Acceptance requires the source artifact hashes and two fresh replay "
            "hashes to agree. Run benchmark and replay with a fixed PYTHONHASHSEED."
        ),
        "accepted": bool(
            replay.solved
            and repeated.solved
            and expected_hashes_present
            and input_hash_matches
            and proof_hash_matches
            and replay.input_sha256 == repeated.input_sha256
            and replay.proof_sha256 == repeated.proof_sha256
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
