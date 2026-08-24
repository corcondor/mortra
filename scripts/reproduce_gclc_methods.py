"""GCLCのArea/Wu/Gröbner法を同じ公式入力で再現する。"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = Path.home() / ".cache" / "mortra-research-sources" / "gclc"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_value(source: Path, *arguments: str) -> str | None:
    completed = subprocess.run(
        ["git", "-C", str(source), *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return completed.stdout.strip() if completed.returncode == 0 else None


def run_method(
    executable: Path,
    input_path: Path,
    flag: str,
    method: str,
    *,
    prover_timeout_seconds: int | None = None,
    proof_output: Path | None = None,
) -> dict:
    with tempfile.TemporaryDirectory(prefix=f"mortra-gclc-{method}-") as directory:
        workspace = Path(directory)
        copied = workspace / input_path.name
        shutil.copy2(input_path, copied)
        if prover_timeout_seconds is not None:
            source = copied.read_text(encoding="utf-8", errors="replace")
            copied.write_text(
                f"prover_timeout {prover_timeout_seconds}\n{source}",
                encoding="utf-8",
            )
        started = time.perf_counter()
        # The internal prover timer does not cover every translation and
        # elimination phase.  Keep a small hard-stop margin instead of the old
        # fixed 60 s floor, which made bounded local-lemma portfolios scale
        # linearly by a minute for every censored candidate.
        external_timeout = max(10, (prover_timeout_seconds or 0) + 5)
        try:
            completed = subprocess.run(
                [str(executable), str(copied), flag],
                cwd=workspace,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=external_timeout,
                check=False,
            )
            return_code = completed.returncode
            stdout = completed.stdout
            stderr = completed.stderr
            external_timeout_reached = False
        except subprocess.TimeoutExpired as error:
            return_code = None
            stdout = (
                error.stdout.decode("utf-8", errors="replace")
                if isinstance(error.stdout, bytes)
                else error.stdout or ""
            )
            stderr = (
                error.stderr.decode("utf-8", errors="replace")
                if isinstance(error.stderr, bytes)
                else error.stderr or ""
            )
            external_timeout_reached = True
        elapsed = time.perf_counter() - started
        transcript = f"{stdout}\n{stderr}".strip()
        # GCLC echoes its temporary working directory. Keep the transcript
        # reproducible without publishing machine-specific absolute paths.
        transcript = transcript.replace(str(workspace), "<TEMP>")
        proof_path = workspace / f"{copied.stem}_proof.tex"
        internal_timeout_reached = (
            "conjecture not proved - timeout" in transcript.lower()
        )
        proved = (
            return_code == 0
            and "conjecture successfully proved" in transcript.lower()
            and proof_path.exists()
        )
        if proof_output is not None and proof_path.exists():
            proof_output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(proof_path, proof_output)
        return {
            "method": method,
            "flag": flag,
            "return_code": return_code,
            "proved": proved,
            "external_timeout_reached": external_timeout_reached,
            "internal_timeout_reached": internal_timeout_reached,
            "timed_out": external_timeout_reached or internal_timeout_reached,
            "external_timeout_seconds": external_timeout,
            "elapsed_seconds": elapsed,
            "proof_sha256": sha256(proof_path) if proof_path.exists() else None,
            "proof_bytes": proof_path.stat().st_size if proof_path.exists() else 0,
            "proof_output": str(proof_output) if proof_output is not None and proof_path.exists() else None,
            "prover_timeout_seconds": prover_timeout_seconds,
            "transcript": transcript,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--executable", type=Path)
    parser.add_argument("--input", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "gclc-three-method-reproduction-2026-08-15.json",
    )
    args = parser.parse_args()
    executable = args.executable or args.source / "build" / "Release" / "gclc.exe"
    input_path = args.input or args.source / "samples" / "samples_prover" / "thm_midpoint.gcl"
    if not executable.exists():
        raise FileNotFoundError(executable)
    if not input_path.exists():
        raise FileNotFoundError(input_path)

    methods = [
        run_method(executable, input_path, "-a", "area"),
        run_method(executable, input_path, "-w", "wu"),
        run_method(executable, input_path, "-g", "groebner"),
    ]
    report = {
        "experiment": "gclc-three-native-provers-reproduction",
        "generated_at": datetime.now(UTC).isoformat(),
        "uses_llm": False,
        "source": {
            "repository": "https://github.com/janicicpredrag/gclc",
            "commit": git_value(args.source, "rev-parse", "HEAD"),
            "commit_date": git_value(args.source, "show", "-s", "--format=%cI", "HEAD"),
            "build_requirements_discovered": [
                "CMAKE_CXX_STANDARD=20",
                "CMAKE_CXX_FLAGS=/DNOMINMAX",
            ],
        },
        "input": {
            "path": str(input_path),
            "sha256": sha256(input_path),
        },
        "summary": {
            "method_count": len(methods),
            "proved": sum(item["proved"] for item in methods),
            "all_proved": all(item["proved"] for item in methods),
        },
        "methods": methods,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))
    print(args.output)
    return 0 if report["summary"]["all_proved"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
