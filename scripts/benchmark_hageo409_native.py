"""Run the same native Yuclid DDAR command on a frozen HAGeo-409 split."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys
import tempfile
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _bootstrap_runtime() -> object | None:
    if "--yuclid-exe" in sys.argv:
        index = sys.argv.index("--yuclid-exe")
        directory = str(Path(sys.argv[index + 1]).resolve().parent)
        os.environ["PATH"] = directory + os.pathsep + os.environ.get("PATH", "")
    if "--runtime-path" not in sys.argv:
        return None
    index = sys.argv.index("--runtime-path")
    directory = str(Path(sys.argv[index + 1]).resolve())
    os.environ["PATH"] = directory + os.pathsep + os.environ.get("PATH", "")
    if sys.platform == "win32" and hasattr(os, "add_dll_directory"):
        return os.add_dll_directory(directory)
    return None


_DLL_DIRECTORY = _bootstrap_runtime()

from newclid.jgex.formulation import JGEXFormulation, jgex_formulation_from_txt_file
from newclid.jgex.problem_builder import JGEXProblemBuilder
from py_yuclid.yuclid_adapter import _write_yuclid_setup

from scripts.reproduce_yuclid_imo_ag_30 import AR_PROFILES, run_problem
from worker.backend.jgex_legacy_normalizer import normalize_legacy_formulation


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--compatibility-audit", type=Path, required=True)
    parser.add_argument("--yuclid-exe", type=Path, required=True)
    parser.add_argument("--runtime-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--split", choices=("dev", "calibration", "held_out"), default="held_out"
    )
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--ar-profile", choices=tuple(AR_PROFILES), default="all")
    args = parser.parse_args()

    compatibility = json.loads(
        args.compatibility_audit.read_text(encoding="utf-8")
    )
    names = sorted(
        name
        for name, item in compatibility["results"].items()
        if item["split"] == args.split and item["status"] == "buildable"
    )
    if args.limit > 0:
        names = names[: args.limit]
    formulations = jgex_formulation_from_txt_file(args.dataset.resolve())
    results: dict[str, dict[str, object]] = {}
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="mortra-hageo409-") as directory:
        input_root = Path(directory)
        inputs: dict[str, Path] = {}
        for name in names:
            raw = formulations[name]
            builder = JGEXProblemBuilder(np.random.default_rng(0))
            setup_only = JGEXFormulation(
                name=raw.name,
                setup_clauses=raw.setup_clauses,
                auxiliary_clauses=(),
                goals=raw.goals,
            )
            normalized, normalization = normalize_legacy_formulation(
                setup_only, builder.jgex_defs
            )
            problem = (
                builder.with_problem(normalized)
                .include_auxiliary_clauses(False)
                .build()
            )
            input_path = input_root / f"{name}.txt"
            input_path.write_text(
                "\n".join(_write_yuclid_setup(problem)) + "\n",
                encoding="utf-8",
            )
            inputs[name] = input_path
            results[name] = {"normalization": asdict(normalization)}

        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
            future_names = {
                executor.submit(
                    run_problem,
                    args.yuclid_exe.resolve(),
                    inputs[name],
                    args.timeout_seconds,
                    str(args.runtime_path.resolve()),
                    AR_PROFILES[args.ar_profile],
                ): name
                for name in names
            }
            for future in as_completed(future_names):
                name = future_names[future]
                try:
                    results[name].update(future.result())
                except Exception as error:
                    results[name].update(
                        {
                            "status": "execution_error",
                            "error": f"{type(error).__name__}: {error}",
                        }
                    )
                print(
                    json.dumps(
                        {"problem": name, "status": results[name]["status"]},
                        ensure_ascii=False,
                    ),
                    flush=True,
                )

    status_counts: dict[str, int] = {}
    for item in results.values():
        status = str(item["status"])
        status_counts[status] = status_counts.get(status, 0) + 1
    solved = status_counts.get("solved", 0)
    report = {
        "experiment": "hageo409_native_yuclid_baseline",
        "protocol": {
            "uses_external_llm": False,
            "uses_dataset_auxiliary_clauses": False,
            "same_command_for_every_problem": True,
            "split": args.split,
            "ar_profile": args.ar_profile,
            "timeout_seconds": args.timeout_seconds,
            "workers": args.workers,
        },
        "summary": {
            "total": len(names),
            "solved": solved,
            "score": solved / len(names) if names else 0.0,
            "status_counts": status_counts,
            "wall_seconds": time.perf_counter() - started,
        },
        "problem_names": names,
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
