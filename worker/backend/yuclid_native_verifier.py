"""Exact Yuclid verifier for generated Newclid ``ProblemSetup`` objects."""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from worker.backend.geometry_relation_channels import canonical_relation
from worker.backend.hageo_mmt_certificate_bridge import shared_argument_sorts


AR_PROFILES: dict[str, tuple[str, ...]] = {
    "ratio-only": (
        "--disable-ar-dist",
        "--disable-ar-squared",
        "--disable-eqn-statements",
        "--disable-ar-sin",
    ),
    "standard": ("--disable-ar-sin",),
    "all": (),
    "all-no-law-of-sines": ("--disable-law-of-sines",),
    "all-no-sin-angle-transfer": ("--disable-sin-angle-transfer",),
    "all-no-sine-bridges": (
        "--disable-law-of-sines",
        "--disable-sin-angle-transfer",
    ),
    # 単一フラグの介入。ar-sin 束の内訳を1つずつ切って、どれが解を担うか見る
    "no-dist": ("--disable-ar-dist",),
    "no-squared": ("--disable-ar-squared",),
    "no-eqn": ("--disable-eqn-statements",),
}


@dataclass(frozen=True)
class RelationSignatureCount:
    predicate: str
    argument_sorts: tuple[str, ...]
    count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "predicate": self.predicate,
            "argument_sorts": list(self.argument_sorts),
            "count": self.count,
        }


def _assertions_from_records(records: Any) -> list[dict[str, Any]]:
    if not isinstance(records, list):
        return []
    assertions: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        nested = record.get("assertions")
        if isinstance(nested, list):
            assertions.extend(item for item in nested if isinstance(item, dict))
        elif "name" in record:
            assertions.append(record)
    return assertions


def relation_signature_counts(records: Any) -> tuple[RelationSignatureCount, ...]:
    """Summarize a native closure without retaining its potentially huge body."""

    counter: Counter[tuple[str, tuple[str, ...]]] = Counter()
    for assertion in _assertions_from_records(records):
        predicate = canonical_relation(str(assertion.get("name", "unknown")))
        points = assertion.get("points", ())
        arity = len(points) if isinstance(points, (list, tuple)) else 0
        signature = shared_argument_sorts(predicate, arity)
        counter[(predicate, signature)] += 1
    return tuple(
        RelationSignatureCount(predicate, sorts, count)
        for (predicate, sorts), count in sorted(counter.items())
    )


@dataclass(frozen=True)
class YuclidVerification:
    solved: bool
    status: str
    elapsed_seconds: float
    all_deduction_count: int
    goal_deduction_count: int
    input_sha256: str
    proof_sha256: str
    closure_signatures: tuple[RelationSignatureCount, ...]
    goal_signatures: tuple[RelationSignatureCount, ...]
    deduction_rule_counts: tuple[tuple[str, int], ...]
    payload: dict[str, Any]


class YuclidTimeoutError(TimeoutError):
    """A candidate verification was right-censored by its resource budget."""

    def __init__(self, timeout_seconds: float) -> None:
        self.timeout_seconds = float(timeout_seconds)
        super().__init__(f"Yuclid right-censored after {self.timeout_seconds:g}s")


def verify_problem(
    problem_setup: Any,
    *,
    yuclid_exe: Path,
    ar_profile: str,
    timeout_seconds: float | None = None,
) -> YuclidVerification:
    # py_yuclid resolves its native binary during module import.  Keep that
    # environment-sensitive dependency at the execution boundary so the typed
    # closure analysis remains testable without a machine-local Yuclid path.
    from py_yuclid.yuclid_adapter import _write_yuclid_setup

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
        try:
            process = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise YuclidTimeoutError(float(timeout_seconds or 0.0)) from exc
    if process.returncode not in {0, 2}:
        raise RuntimeError(
            f"Yuclid failed with exit code {process.returncode}: "
            f"{process.stderr[-2000:]}"
        )
    payload = json.loads(process.stdout)
    status = str(payload.get("status", "unknown"))
    all_deductions = payload.get("all_deductions", [])
    goal_deductions = payload.get("deductions_for_goal", [])
    rule_counts: Counter[str] = Counter()
    if isinstance(all_deductions, list):
        for deduction in all_deductions:
            if isinstance(deduction, dict):
                rule_counts[str(deduction.get("newclid_rule", "unknown"))] += 1
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
        closure_signatures=relation_signature_counts(all_deductions),
        goal_signatures=relation_signature_counts(payload.get("goals", [])),
        deduction_rule_counts=tuple(sorted(rule_counts.items())),
        payload=payload,
    )
