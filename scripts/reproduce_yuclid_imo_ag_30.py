"""Reproduce Yuclid's symbolic IMO-AG-30 result without an LLM.

The runner intentionally contains no problem-specific proof logic. Every input is
sent to the same Yuclid DD/AR executable with the same options. The original
2019_p2 input and the easier official reformulation are reported separately.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import time
from pathlib import Path
from typing import Any


ORIGINAL_IMO_AG_30 = (
    "2000_p1",
    "2000_p6",
    "2002_p2a",
    "2002_p2b",
    "2003_p4",
    "2004_p1",
    "2004_p5",
    "2005_p5",
    "2007_p4",
    "2008_p1a",
    "2008_p1b",
    "2008_p6",
    "2009_p2",
    "2010_p2",
    "2010_p4",
    "2011_p6",
    "2012_p1",
    "2012_p5",
    "2013_p4",
    "2014_p4",
    "2015_p3",
    "2015_p4",
    "2016_p1",
    "2017_p4",
    "2018_p1",
    "2019_p2",
    "2019_p6",
    "2020_p1",
    "2021_p3",
    "2022_p4",
)

# Yuclid's CMake test suite counts this easier reformulation among its expected
# successes while retaining the original 2019_p2 in the expected-failure set.
README_REFORMULATED_30 = tuple(
    "2019_p2_easy" if name == "2019_p2" else name
    for name in ORIGINAL_IMO_AG_30
)

EXPECTED_SOLVED_BY_OFFICIAL_CTEST = {
    "2000_p1",
    "2002_p2a",
    "2002_p2b",
    "2003_p4",
    "2004_p1",
    "2004_p5",
    "2005_p5",
    "2007_p4",
    "2010_p4",
    "2012_p1",
    "2013_p4",
    "2014_p4",
    "2015_p4",
    "2016_p1",
    "2017_p4",
    "2019_p2_easy",
    "2022_p4",
}

AR_PROFILES = {
    "ratio-only": (
        "--disable-ar-dist",
        "--disable-ar-squared",
        "--disable-eqn-statements",
        "--disable-ar-sin",
    ),
    "standard": ("--disable-ar-sin",),
    "all": (),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_output(root: Path, *args: str) -> str | None:
    process = subprocess.run(
        ["git", *args],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return process.stdout.strip() if process.returncode == 0 else None


def run_problem(
    executable: Path,
    input_path: Path,
    timeout_seconds: float,
    runtime_path: str | None,
    solver_options: tuple[str, ...],
    proof_output_path: Path | None = None,
) -> dict[str, Any]:
    command = [
        str(executable),
        "--err-on-failure",
        "--use-json",
        "--mode",
        "ddar",
        "--log-level",
        "warning",
        *solver_options,
        "--input-file",
        str(input_path),
    ]
    environment = os.environ.copy()
    if runtime_path:
        environment["PATH"] = runtime_path + os.pathsep + environment.get("PATH", "")

    started = time.perf_counter()
    try:
        process = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            env=environment,
        )
        elapsed = time.perf_counter() - started
        status = {
            0: "solved",
            1: "execution_error",
            2: "saturated_unsolved",
        }.get(process.returncode, "unexpected_exit")
        stdout = process.stdout
        stderr = process.stderr
        if proof_output_path is not None:
            proof_output_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = proof_output_path.with_suffix(proof_output_path.suffix + ".tmp")
            temporary.write_text(stdout, encoding="utf-8")
            temporary.replace(proof_output_path)
        try:
            proof_payload = json.loads(stdout)
        except json.JSONDecodeError:
            proof_payload = None

        deduction_type_counts: dict[str, int] = {}
        ar_reason_counts: dict[str, int] = {}
        all_deduction_type_counts: dict[str, int] = {}
        deductions: list[dict[str, Any]] = []
        all_deductions: list[dict[str, Any]] = []
        unresolved_goals: list[dict[str, Any]] = []
        if isinstance(proof_payload, dict):
            raw_deductions = proof_payload.get("deductions_for_goal", [])
            if isinstance(raw_deductions, list):
                deductions = [item for item in raw_deductions if isinstance(item, dict)]
            raw_goals = proof_payload.get("goals", [])
            if isinstance(raw_goals, list):
                unresolved_goals = [item for item in raw_goals if isinstance(item, dict)]
            raw_all_deductions = proof_payload.get("all_deductions", [])
            if isinstance(raw_all_deductions, list):
                all_deductions = [
                    item for item in raw_all_deductions if isinstance(item, dict)
                ]
        for deduction in deductions:
            deduction_type = str(deduction.get("deduction_type", "unknown"))
            deduction_type_counts[deduction_type] = (
                deduction_type_counts.get(deduction_type, 0) + 1
            )
            if deduction_type == "ar":
                reason = str(deduction.get("ar_reason", "unknown"))
                ar_reason_counts[reason] = ar_reason_counts.get(reason, 0) + 1
        for deduction in all_deductions:
            deduction_type = str(deduction.get("deduction_type", "unknown"))
            all_deduction_type_counts[deduction_type] = (
                all_deduction_type_counts.get(deduction_type, 0) + 1
            )

        return {
            "status": status,
            "return_code": process.returncode,
            "elapsed_seconds": elapsed,
            "proof_sha256": hashlib.sha256(stdout.encode("utf-8")).hexdigest(),
            "proof_chars": len(stdout),
            "proof_path": str(proof_output_path) if proof_output_path is not None else None,
            "proof_json_parsed": proof_payload is not None,
            "solver_json_status": proof_payload.get("status")
            if isinstance(proof_payload, dict)
            else None,
            "deduction_count": len(deductions),
            "all_deduction_count": len(all_deductions),
            "deduction_type_counts": deduction_type_counts,
            "all_deduction_type_counts": all_deduction_type_counts,
            "ar_reason_counts": ar_reason_counts,
            "unresolved_goal_count": len(unresolved_goals),
            "final_assertions": deductions[-1].get("assertions", [])
            if deductions
            else [],
            "stderr_tail": stderr[-2000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "timeout",
            "return_code": None,
            "elapsed_seconds": time.perf_counter() - started,
            "proof_sha256": None,
            "proof_chars": len(exc.stdout or b""),
            "stderr_tail": "",
        }


def summarize(names: tuple[str, ...], results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for name in names:
        status = results[name]["status"]
        counts[status] = counts.get(status, 0) + 1
    solved = counts.get("solved", 0)
    return {
        "total": len(names),
        "solved": solved,
        "score": solved / len(names),
        "status_counts": counts,
        "solved_names": [name for name in names if results[name]["status"] == "solved"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--yuclid-exe", type=Path, required=True)
    parser.add_argument("--newclid-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument(
        "--ar-profile",
        choices=tuple(AR_PROFILES),
        default="standard",
        help="Yuclid algebraic-reasoning tables to enable.",
    )
    parser.add_argument(
        "--runtime-path",
        help="Directory containing dynamic Boost DLLs, when required.",
    )
    parser.add_argument(
        "--proof-dir",
        type=Path,
        help="Persist each native Yuclid JSON proof/closure for later replay.",
    )
    args = parser.parse_args()

    executable = args.yuclid_exe.resolve()
    newclid_root = args.newclid_root.resolve()
    inputs_root = newclid_root / "yuclid" / "test" / "imo_ag_30"
    if not executable.is_file():
        raise FileNotFoundError(executable)

    all_names = tuple(dict.fromkeys((*ORIGINAL_IMO_AG_30, "2019_p2_easy")))
    inputs = {
        name: inputs_root / f"translated_imo_{name}.txt" for name in all_names
    }
    missing = [str(path) for path in inputs.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing official inputs: " + ", ".join(missing))

    started = time.perf_counter()
    results: dict[str, dict[str, Any]] = {}
    solver_options = AR_PROFILES[args.ar_profile]
    for index, name in enumerate(all_names, start=1):
        print(f"[{index:02d}/{len(all_names)}] {name}", flush=True)
        result = run_problem(
            executable,
            inputs[name],
            args.timeout_seconds,
            args.runtime_path,
            solver_options,
            (args.proof_dir.resolve() / f"{name}.json") if args.proof_dir else None,
        )
        result["input_sha256"] = sha256(inputs[name])
        results[name] = result
        print(f"  {result['status']} ({result['elapsed_seconds']:.3f}s)", flush=True)

    original = summarize(ORIGINAL_IMO_AG_30, results)
    reformulated = summarize(README_REFORMULATED_30, results)
    actual_ctest_solved = {
        name for name, result in results.items() if result["status"] == "solved"
    }
    artifact = {
        "experiment": "yuclid_imo_ag_30_no_llm_reproduction",
        "protocol": {
            "same_command_for_every_problem": True,
            "uses_external_llm": False,
            "uses_auxiliary_point_generator": False,
            "yuclid_iteration_limit": 500,
            "ar_profile": args.ar_profile,
            "solver_options": solver_options,
            "timeout_seconds": args.timeout_seconds,
        },
        "environment": {
            "platform": platform.platform(),
            "processor": platform.processor(),
            "python": platform.python_version(),
            "newclid_commit": git_output(newclid_root, "rev-parse", "HEAD"),
            "newclid_commit_date": git_output(
                newclid_root, "show", "-s", "--format=%cI", "HEAD"
            ),
            "yuclid_executable": executable.name,
            "yuclid_executable_sha256": sha256(executable),
        },
        "scores": {
            "original_imo_ag_30": original,
            "readme_reformulated_imo_ag_30": reformulated,
        },
        "official_ctest_expectation": {
            "expected_solved": sorted(EXPECTED_SOLVED_BY_OFFICIAL_CTEST),
            "missing_expected_solved": sorted(
                EXPECTED_SOLVED_BY_OFFICIAL_CTEST - actual_ctest_solved
            ),
            "unexpected_solved": sorted(
                actual_ctest_solved - EXPECTED_SOLVED_BY_OFFICIAL_CTEST
            ),
        },
        "wall_seconds": time.perf_counter() - started,
        "results": results,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(artifact, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(artifact["scores"], indent=2), flush=True)
    print(f"Wrote {args.output}", flush=True)


if __name__ == "__main__":
    main()
