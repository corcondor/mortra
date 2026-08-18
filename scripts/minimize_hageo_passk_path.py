"""Find the smallest dependency-closed subpath preserving a Pass@K proof."""

from __future__ import annotations

import argparse
import itertools
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.experiment_newclid_construction_stalk import (  # noqa: E402
    JGEXFormulation,
    JGEXProblemBuilder,
    build_branch,
    jgex_formulation_from_txt_file,
    normalize_legacy_formulation,
)
from scripts.verify_hageo_passk_artifact import _parse_step  # noqa: E402
from worker.backend.yuclid_native_verifier import verify_problem  # noqa: E402


def _dependency_closed(indices: tuple[int, ...], steps: tuple[object, ...]) -> bool:
    selected = set(indices)
    producer = {step.output: index for index, step in enumerate(steps)}
    return all(
        producer.get(point) is None or producer[point] in selected
        for index in indices
        for point in steps[index].inputs
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--yuclid-exe", type=Path, required=True)
    parser.add_argument("--runtime-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ar-profile", choices=("ratio-only", "standard", "all"), default="all")
    args = parser.parse_args()

    source = json.loads(args.artifact.read_text(encoding="utf-8"))
    solved = next(item for item in source["attempt_results"] if item.get("solved"))
    steps = tuple(_parse_step(item) for item in solved["path"])
    seed = int(source["protocol"]["seed"])
    attempt_seed = seed + 1_000_003 * int(solved["attempt"])

    formulations = jgex_formulation_from_txt_file(args.dataset.resolve())
    raw = formulations[source["problem_name"]]
    raw = JGEXFormulation(
        name=raw.name,
        setup_clauses=raw.setup_clauses,
        auxiliary_clauses=(),
        goals=raw.goals,
    )
    builder = JGEXProblemBuilder(np.random.default_rng(seed))
    formulation, normalization = normalize_legacy_formulation(raw, builder.jgex_defs)
    base_problem = builder.with_problem(formulation).include_auxiliary_clauses(False).build()

    started = time.perf_counter()
    results: list[dict[str, object]] = []
    minimum_size: int | None = None
    for size in range(len(steps) + 1):
        for indices in itertools.combinations(range(len(steps)), size):
            if not _dependency_closed(indices, steps):
                continue
            subset = tuple(steps[index] for index in indices)
            try:
                problem = build_branch(base_problem, subset, seed=attempt_seed)
                replay = verify_problem(
                    problem,
                    yuclid_exe=args.yuclid_exe.resolve(),
                    ar_profile=args.ar_profile,
                )
                result = {
                    "indices": list(indices),
                    "path": [step.key for step in subset],
                    "solved": replay.solved,
                    "input_sha256": replay.input_sha256,
                    "proof_sha256": replay.proof_sha256,
                }
            except Exception as exc:
                result = {
                    "indices": list(indices),
                    "path": [step.key for step in subset],
                    "solved": False,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            results.append(result)
            if result["solved"]:
                minimum_size = size
        if minimum_size is not None:
            break

    minimal = [
        result
        for result in results
        if result["solved"] and len(result["indices"]) == minimum_size
    ]
    artifact = {
        "experiment": "hageo_passk_dependency_closed_path_minimization",
        "problem_name": source["problem_name"],
        "source_artifact": args.artifact.resolve().relative_to(ROOT).as_posix(),
        "source_attempt": solved["attempt"],
        "source_path_length": len(steps),
        "normalization": asdict(normalization),
        "tested_dependency_closed_subpaths": len(results),
        "minimum_proof_path_length": minimum_size,
        "minimal_proof_paths": minimal,
        "elapsed_seconds": time.perf_counter() - started,
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "problem": source["problem_name"],
                "source_path_length": len(steps),
                "tested": len(results),
                "minimum_proof_path_length": minimum_size,
                "minimal_proof_paths": [item["path"] for item in minimal],
                "elapsed_seconds": artifact["elapsed_seconds"],
            },
            indent=2,
        )
    )
    return 0 if minimum_size is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
