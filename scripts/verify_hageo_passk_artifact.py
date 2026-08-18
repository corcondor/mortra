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
    solved = next(
        (item for item in artifact["attempt_results"] if item.get("solved")),
        None,
    )
    if solved is None:
        raise ValueError("artifact has no solved attempt")
    seed = int(artifact["protocol"]["seed"])
    attempt_seed = seed + 1_000_003 * int(solved["attempt"])
    steps = tuple(_parse_step(item) for item in solved["path"])

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
        replay_problem = build_branch(base_problem, steps, seed=attempt_seed)
        replay = verify_problem(
            replay_problem,
            yuclid_exe=args.yuclid_exe.resolve(),
            ar_profile=args.ar_profile,
        )
        return replay, normalization

    replay, normalization = replay_once()
    repeated, _ = replay_once()
    expected = artifact.get("certificate") or {
        "input_sha256": solved.get("input_sha256"),
        "proof_sha256": solved.get("proof_sha256"),
    }
    result = {
        "experiment": "hageo_passk_independent_certificate_replay",
        "problem_name": artifact["problem_name"],
        "source_artifact": args.artifact.resolve().relative_to(ROOT).as_posix(),
        "attempt": solved["attempt"],
        "attempt_seed": attempt_seed,
        "path": solved["path"],
        "normalization": {
            "rewritten_constructions": normalization.rewritten_constructions,
            "unchanged_constructions": normalization.unchanged_constructions,
            "unresolved_constructions": normalization.unresolved_constructions,
        },
        "replay_solved": replay.solved,
        "input_sha256": replay.input_sha256,
        "proof_sha256": replay.proof_sha256,
        "input_hash_matches": replay.input_sha256 == expected.get("input_sha256"),
        "proof_hash_matches": replay.proof_sha256 == expected.get("proof_sha256"),
        "repeat_replay_solved": repeated.solved,
        "repeat_input_hash_matches": replay.input_sha256 == repeated.input_sha256,
        "repeat_proof_hash_matches": replay.proof_sha256 == repeated.proof_sha256,
        "source_byte_hash_note": (
            "Source hashes are diagnostic because an unfixed PYTHONHASHSEED can "
            "change serialization order. Acceptance requires two fresh replays."
        ),
        "accepted": bool(
            replay.solved
            and repeated.solved
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
