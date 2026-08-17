"""Replay a synthesized JGEX construction with independent symbolic backends."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from experiment_jgex_exact_unsolved_set import _run_isolated
from reproduce_gclc_methods import run_method
from worker.backend.jgex_gclc_translator import (
    canonical_typed_goal_key,
    translate_jgex_to_gclc,
)


DEFAULT_GCLC = (
    Path.home()
    / ".cache"
    / "mortra-research-sources"
    / "gclc"
    / "build"
    / "Release"
    / "gclc.exe"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--gclc-executable", type=Path, default=DEFAULT_GCLC)
    parser.add_argument("--gclc-timeout-seconds", type=int, default=60)
    parser.add_argument("--exact-timeout-seconds", type=float, default=120.0)
    parser.add_argument("--sketch-attempts", type=int, default=5)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    artifact = json.loads(args.artifact.read_text(encoding="utf-8"))
    formulation = artifact.get("constructed_formulation")
    if not formulation or artifact.get("solved") is not True:
        raise ValueError("artifact has no native-proved constructed formulation")
    if not args.gclc_executable.is_file():
        raise FileNotFoundError(args.gclc_executable)

    started = time.perf_counter()
    attempts: list[dict] = []
    accepted_translation = None
    accepted_runs: list[dict] = []
    for sketch_seed in range(args.sketch_attempts):
        translation = translate_jgex_to_gclc(formulation, sketch_seed=sketch_seed)
        with tempfile.TemporaryDirectory(prefix="mortra-open-goal-gclc-") as directory:
            input_path = Path(directory) / f"{artifact['problem_name']}.gcl"
            input_path.write_text(translation.source, encoding="utf-8")
            runs = [
                run_method(
                    args.gclc_executable,
                    input_path,
                    flag,
                    method,
                    prover_timeout_seconds=args.gclc_timeout_seconds,
                )
                for flag, method in (("-w", "wu"), ("-g", "groebner"))
            ]
        attempts.append(
            {
                "sketch_seed": sketch_seed,
                "source_sha256": translation.source_sha256,
                "runs": runs,
            }
        )
        accepted_translation = translation
        accepted_runs = runs
        if any(run["proved"] for run in runs):
            break
        if not all("bad definition" in run["transcript"].lower() for run in runs):
            break

    assert accepted_translation is not None
    gclc_proved = any(run["proved"] for run in accepted_runs)
    exact = _run_isolated(formulation, args.exact_timeout_seconds)
    exact_certificate = exact.get("certificate") or {}
    typed_goal_agreement = canonical_typed_goal_key(
        str(exact_certificate.get("channel", "")),
        tuple(exact_certificate.get("points", ())),
    ) == canonical_typed_goal_key(
        accepted_translation.goal_channel,
        accepted_translation.goal_points,
    )
    strict_exchange_proved = bool(
        gclc_proved
        and exact.get("status") == "proved"
        and typed_goal_agreement
    )
    report = {
        "experiment": "open-goal-construction-independent-exchange-no-llm",
        "generated_at": datetime.now(UTC).isoformat(),
        "problem_name": artifact["problem_name"],
        "source_artifact": args.artifact.resolve().relative_to(ROOT).as_posix(),
        "protocol": {
            "uses_external_llm": False,
            "uses_dataset_auxiliary_clauses": False,
            "acceptance": "GCLC native proof and independent exact replay agree on typed goal",
        },
        "translation": {
            "construction_vocabulary": accepted_translation.construction_vocabulary,
            "goal_channel": accepted_translation.goal_channel,
            "goal_points": accepted_translation.goal_points,
            "source_sha256": accepted_translation.source_sha256,
            "source": accepted_translation.source,
        },
        "gclc": {
            "proved": gclc_proved,
            "runs": accepted_runs,
            "sketch_attempts": attempts,
        },
        "exact": exact,
        "typed_goal_agreement": typed_goal_agreement,
        "strict_exchange_proved": strict_exchange_proved,
        "elapsed_seconds": time.perf_counter() - started,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "problem_name": report["problem_name"],
                "gclc_proved": gclc_proved,
                "exact_status": exact.get("status"),
                "typed_goal_agreement": typed_goal_agreement,
                "strict_exchange_proved": strict_exchange_proved,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
