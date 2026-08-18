"""Exact Yuclid verifier for generated Newclid ``ProblemSetup`` objects."""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from py_yuclid.yuclid_adapter import _write_yuclid_setup


AR_PROFILES: dict[str, tuple[str, ...]] = {
    "ratio-only": (
        "--disable-ar-dist",
        "--disable-ar-squared",
        "--disable-eqn-statements",
        "--disable-ar-sin",
    ),
    "standard": ("--disable-ar-sin",),
    "all": (),
}


@dataclass(frozen=True)
class YuclidVerification:
    solved: bool
    status: str
    elapsed_seconds: float
    all_deduction_count: int
    goal_deduction_count: int
    input_sha256: str
    proof_sha256: str
    payload: dict[str, Any]


def verify_problem(
    problem_setup: Any,
    *,
    yuclid_exe: Path,
    ar_profile: str,
) -> YuclidVerification:
    if ar_profile not in AR_PROFILES:
        raise ValueError(f"unknown AR profile: {ar_profile}")
    started = time.perf_counter()
    input_text = "\n".join(_write_yuclid_setup(problem_setup)) + "\n"
    with tempfile.TemporaryDirectory(prefix="mortra-yuclid-") as temp_dir:
        input_path = Path(temp_dir) / "problem.txt"
        input_path.write_text(input_text, encoding="utf-8")
        command = [
            str(yuclid_exe),
            "--err-on-failure",
            "--use-json",
            "--mode",
            "ddar",
            "--log-level",
            "warning",
            *AR_PROFILES[ar_profile],
            "--input-file",
            str(input_path),
        ]
        process = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    if process.returncode not in {0, 2}:
        raise RuntimeError(
            f"Yuclid failed with exit code {process.returncode}: "
            f"{process.stderr[-2000:]}"
        )
    payload = json.loads(process.stdout)
    status = str(payload.get("status", "unknown"))
    all_deductions = payload.get("all_deductions", [])
    goal_deductions = payload.get("deductions_for_goal", [])
    return YuclidVerification(
        solved=status == "solved",
        status=status,
        elapsed_seconds=time.perf_counter() - started,
        all_deduction_count=len(all_deductions) if isinstance(all_deductions, list) else 0,
        goal_deduction_count=(
            len(goal_deductions) if isinstance(goal_deductions, list) else 0
        ),
        input_sha256=hashlib.sha256(input_text.encode("utf-8")).hexdigest(),
        proof_sha256=hashlib.sha256(process.stdout.encode("utf-8")).hexdigest(),
        payload=payload,
    )
