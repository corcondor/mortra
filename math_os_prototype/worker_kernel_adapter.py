"""Adapter for the authoritative TypeScript MathOS execution kernel.

The Python benchmark process owns corpus isolation and scoring. Mathematical
elaboration and typed-term search are delegated to the Worker kernel used by
the production application, so benchmark and product no longer drift.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Iterable


def worker_directory() -> Path:
    configured = os.environ.get("MATHOS_WORKER_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parent.parent / "math-web" / "worker"


def evaluate_with_worker(
    cases: Iterable[dict[str, Any]],
    *,
    timeout_seconds: int = 900,
) -> list[dict[str, Any]]:
    requests = [
        {
            "id": str(case.get("id") or ""),
            "statement": str(case["statement"]),
            "atlas": str(case.get("atlas") or "unified"),
            "max_depth": int(case.get("max_depth") or 7),
            "max_states": int(case.get("max_states") or 10_000),
            "compact": True,
        }
        for case in cases
    ]
    if not requests:
        return []
    directory = worker_directory()
    bridge = directory / "src" / "benchmark-bridge.ts"
    if not bridge.exists():
        raise FileNotFoundError(f"authoritative Worker bridge was not found: {bridge}")
    executable = "npx.cmd" if os.name == "nt" else "npx"
    completed = subprocess.run(
        [executable, "tsx", "src/benchmark-bridge.ts"],
        cwd=directory,
        input=json.dumps(requests, ensure_ascii=False),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout_seconds,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"Worker benchmark bridge failed ({completed.returncode}): {detail}")
    output = json.loads(completed.stdout)
    if not isinstance(output, list) or len(output) != len(requests):
        raise RuntimeError("Worker benchmark bridge returned a mismatched result batch")
    return output
