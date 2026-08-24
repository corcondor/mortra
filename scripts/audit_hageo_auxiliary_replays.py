"""Independently replay every solved trajectory in an auxiliary cohort report."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONHASHSEED": "0"},
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--yuclid-exe", type=Path, required=True)
    parser.add_argument("--runtime-path", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()

    report = _load(args.report.resolve())
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    audits: dict[str, dict[str, object]] = {}
    solved_runs = [item for item in report.get("runs", ()) if item.get("solved")]
    for run in solved_runs:
        problem = str(run["problem"])
        artifact = ROOT / str(run["artifact"])
        replay = output_dir / f"{problem}.replay.json"
        replay_process = _run(
            [
                sys.executable,
                "-B",
                str(ROOT / "scripts" / "verify_hageo_passk_artifact.py"),
                "--dataset",
                str(args.dataset.resolve()),
                "--artifact",
                str(artifact),
                "--yuclid-exe",
                str(args.yuclid_exe.resolve()),
                "--runtime-path",
                str(args.runtime_path.resolve()),
                "--output",
                str(replay),
            ]
        )
        replay_payload = _load(replay) if replay.is_file() else {}
        accepted = replay_process.returncode == 0 and replay_payload.get("accepted") is True
        proof_trace_json = output_dir / f"{problem}.proof-trace.json"
        proof_trace_markdown = output_dir / f"{problem}.proof-trace.md"
        trace_process: subprocess.CompletedProcess[str] | None = None
        confirmation = _load(artifact).get("confirmation", {})
        proof_value = confirmation.get("proof_path") if isinstance(confirmation, dict) else None
        if accepted and proof_value:
            trace_process = _run(
                [
                    sys.executable,
                    "-B",
                    str(ROOT / "scripts" / "audit_yuclid_proof_trace.py"),
                    "--problem-name",
                    problem,
                    "--proof",
                    str(ROOT / str(proof_value)),
                    "--json-output",
                    str(proof_trace_json),
                    "--markdown-output",
                    str(proof_trace_markdown),
                ]
            )
        trace_ok = bool(
            trace_process is not None
            and trace_process.returncode == 0
            and proof_trace_json.is_file()
            and proof_trace_markdown.is_file()
        )
        trace_payload = _load(proof_trace_json) if trace_ok else {}
        trace_integrity = bool(
            trace_ok
            and trace_payload.get("all_assumptions_linked") is True
            and int(trace_payload.get("unlinked_assumption_count", -1)) == 0
            and int(trace_payload.get("ambiguous_equation_link_count", -1)) == 0
        )
        numerical_guard_count = sum(
            node.get("channel") == "numerical_guard"
            for node in trace_payload.get("nodes", ())
            if isinstance(node, dict)
        )
        audits[problem] = {
            "artifact": artifact.relative_to(ROOT).as_posix(),
            "replay": replay.relative_to(ROOT).as_posix() if replay.is_file() else None,
            "accepted": accepted,
            "trace_ok": trace_ok,
            "trace_integrity": trace_integrity,
            "deduction_count": trace_payload.get("deduction_count"),
            "unlinked_assumption_count": trace_payload.get(
                "unlinked_assumption_count"
            ),
            "ambiguous_equation_link_count": trace_payload.get(
                "ambiguous_equation_link_count"
            ),
            "numerical_guard_count": numerical_guard_count,
            "proof_trace_json": (
                proof_trace_json.relative_to(ROOT).as_posix() if trace_ok else None
            ),
            "proof_trace_markdown": (
                proof_trace_markdown.relative_to(ROOT).as_posix() if trace_ok else None
            ),
            "replay_stderr_tail": replay_process.stderr[-1000:],
            "trace_stderr_tail": (
                trace_process.stderr[-1000:] if trace_process is not None else ""
            ),
        }
        print(
            json.dumps(
                {"problem": problem, "accepted": accepted, "trace_ok": trace_ok},
                ensure_ascii=False,
            ),
            flush=True,
        )

    accepted_count = sum(item["accepted"] is True for item in audits.values())
    trace_count = sum(item["trace_ok"] is True for item in audits.values())
    trace_integrity_count = sum(
        item["trace_integrity"] is True for item in audits.values()
    )
    manifest = {
        "experiment": "hageo_auxiliary_independent_replay_audit",
        "protocol": {
            "uses_external_llm": False,
            "pythonhashseed": "0",
            "acceptance": (
                "source input/proof hashes match two deterministic native replays"
            ),
            "source_report": args.report.resolve().relative_to(ROOT).as_posix(),
        },
        "summary": {
            "claimed_solved": len(solved_runs),
            "accepted": accepted_count,
            "proof_traces": trace_count,
            "trace_integrity_passed": trace_integrity_count,
            "all_accepted": accepted_count == len(solved_runs),
            "all_traces_built": trace_count == len(solved_runs),
            "all_trace_integrity_passed": trace_integrity_count == len(solved_runs),
        },
        "audits": audits,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest["summary"], ensure_ascii=False), flush=True)
    return 0 if (
        manifest["summary"]["all_accepted"]
        and manifest["summary"]["all_trace_integrity_passed"]
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
