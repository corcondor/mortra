"""Run the existing Designer without allowing its exhaustive-world oracle.

This is a capability check, not a replacement Designer and not a new benchmark.
The observer records existing decisions; it never supplies alternative feedback.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[2]


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def relative(filename):
    try:
        return Path(filename).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return Path(filename).name


class ForbiddenOracle(RuntimeError):
    """Raised at function entry, before the oracle body can run."""


class Observer:
    def __init__(self, forbidden, watched, on_generated=None):
        self.forbidden = {fn.__code__: name for name, fn in forbidden.items()}
        self.watched = {fn.__code__: name for name, fn in watched.items()}
        self.on_generated = on_generated
        self.events = []
        self.generated = []
        self.actions = []
        self.calls = Counter()

    def __call__(self, frame, event, result):
        code = frame.f_code
        if event == "call" and code in self.forbidden:
            caller = frame.f_back
            record = {"event": "FORBIDDEN_ORACLE_CALL", "function": self.forbidden[code],
                      "source": relative(code.co_filename), "line": code.co_firstlineno,
                      "caller": relative(caller.f_code.co_filename), "caller_line": caller.f_lineno,
                      "body_executed": False, "oracle_result_supplied": False}
            self.events.append(record)
            raise ForbiddenOracle(f"Oracle prohibited: {record['function']} at {record['caller']}:{record['caller_line']}")
        name = self.watched.get(code)
        if name is None:
            return
        if event == "call":
            self.calls[name] += 1
            if name == "engine_step":
                self.actions.append({"state": list(frame.f_locals["s"]), "action": frame.f_locals["a"]})
            else:
                self.events.append({"event": "CALL", "function": name})
        elif event == "return" and name == "generate" and isinstance(result, dict):
            genome = json.loads(json.dumps(result))
            self.generated.append(genome)
            self.events.append({"event": "GENERATED", "genome_sha256": digest(genome)})
            if self.on_generated:
                self.on_generated(len(self.generated) - 1, genome)


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def frozen_hashes():
    files = [p for p in (ROOT / "experiments").rglob("*.py")
             if "autonomous_completion" not in p.parts]
    files += [ROOT / "scripts/evaluate_cross_domain_generalization.py"]
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(files)}


def run_attempt(directory):
    from experiments.game_frontier_v1 import world as world_v1
    from experiments.game_frontier_v11 import world
    from experiments.game_frontier_v12 import run as designer

    directory.mkdir(parents=True, exist_ok=False)
    before = frozen_hashes()
    observer = Observer(
        {"v1.exact_oracle": world_v1.exact_oracle, "v1.1.oracle": world.oracle},
        {"generate": designer.frozen.generate, "mutate": designer.frozen.mutate,
         "prepare": designer.frozen.prepare, "train_candidate": designer.frozen.train_candidate,
         "choose": designer.frozen.choose, "run_condition": designer.run_condition,
         "engine_step": world.Engine.step},
        lambda index, genome: save(directory / "generated" / f"candidate_{index:02d}.json", genome))
    save(directory / "config.json", designer.config(1))
    start, cpu = time.perf_counter(), time.process_time()
    status, error = "UNEXPECTED_COMPLETION", None
    previous_profile = sys.getprofile()
    try:
        sys.setprofile(observer)
        # Use the existing public entrypoint and its first registered smoke seed.
        designer.evolve(1, 3101, directory / "original_run")
    except ForbiddenOracle as exc:
        status, error = "BLOCKED_ORACLE_DEPENDENCY", str(exc)
        with (directory / "traceback.txt").open("x", encoding="utf-8") as stream:
            traceback.print_exc(file=stream)
    except Exception as exc:
        status, error = "EXECUTION_ERROR", repr(exc)
        with (directory / "traceback.txt").open("x", encoding="utf-8") as stream:
            traceback.print_exc(file=stream)
    finally:
        sys.setprofile(previous_profile)
    wall, cpu = time.perf_counter() - start, time.process_time() - cpu
    unchanged = before == frozen_hashes()
    result = {
        "status": status, "error": error, "objective_completed": False,
        "stage": 1, "seed": 3101, "seed_scope": "existing smoke seed; not a fresh world claim",
        "generated_candidates": len(observer.generated), "candidate_hashes": [digest(g) for g in observer.generated],
        "function_calls": dict(observer.calls), "engine_step_calls": len(observer.actions),
        "oracle_attempts_blocked": sum(e["event"] == "FORBIDDEN_ORACLE_CALL" for e in observer.events),
        "source_bytes_unchanged": unchanged, "wall_seconds": wall, "cpu_seconds": cpu,
        "peak_process_rss_bytes": designer.io.peak_rss(),
        "timing_scope": "whole entrypoint including observer/source verification; not a performance benchmark",
        "random_comparison": "NOT_EXECUTED: candidate preparation stopped before tasks/self-play",
        "improvements": [], "mortra_discovered_structures": [],
        "codex_game_or_policy_changes": [],
    }
    save(directory / "events.json", observer.events)
    save(directory / "action_trace.json", observer.actions)
    save(directory / "source_sha_before.json", before)
    save(directory / "result.json", result)
    if not unchanged:
        raise AssertionError("Frozen source bytes changed")
    return result, observer.events


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    save(args.output / "source_snapshot.json", {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "head": git("rev-parse", "HEAD"), "branch": git("branch", "--show-current"),
        "git_status": git("status", "--short"), "command": sys.argv,
        "python": sys.version, "platform": platform.platform(),
        "packages": {name: importlib.metadata.version(name) for name in ("numpy", "matplotlib", "psutil", "pytest")},
        "github_run_id": os.environ.get("GITHUB_RUN_ID"), "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "frozen_sources": frozen_hashes(),
    })
    attempts = [run_attempt(args.output / f"attempt_{i}") for i in (1, 2)]
    ignored = {"wall_seconds", "cpu_seconds", "peak_process_rss_bytes"}
    logical = [{k: v for k, v in result.items() if k not in ignored} for result, _ in attempts]
    reproduced = logical[0] == logical[1] and attempts[0][1] == attempts[1][1]
    blocked = all(item["status"] == "BLOCKED_ORACLE_DEPENDENCY" for item in logical)
    no_steps = all(item["engine_step_calls"] == 0 for item in logical)
    summary = {"objective": "MORTRA autonomously completes and improves a playable game",
               "objective_status": "NOT_COMPLETED", "entrypoint": "experiments.game_frontier_v12.run.evolve(1, 3101, output)",
               "attempts": 2, "same_stop_reproduced": reproduced, "blocked_before_oracle_body": blocked,
               "zero_engine_steps": no_steps, "attempt_results": [a[0] for a in attempts],
               "scope": "Existing v1.2 Designer entrypoint only; not a conclusion about all MORTRA variants",
               "harness_audit_completed": reproduced and blocked and no_steps}
    save(args.output / "summary.json", summary)
    with (args.output / "README.md").open("x", encoding="utf-8") as stream:
        stream.write("# Autonomous completion: execution record\n\n"
                     "Objective status: NOT_COMPLETED. This is not a completed playable game.\n\n"
                     "The unmodified v1.2 Designer was called twice with its existing Stage 1 seed 3101. "
                     "No new objective, reward, game rule, target, strategy or mutation was supplied by Codex. "
                     "An observer denied the existing exhaustive-world oracle at function entry. "
                     "No oracle result or fabricated substitute was returned.\n\n"
                     "## Requested deliverables\n"
                     "- Artifact: raw generated candidates in attempt_*/generated; no completed game.\n"
                     "- Verification: summary.json, source hashes, identical non-timing records across two attempts.\n"
                     "- Improvement history: empty; the Designer stopped before self-play/mutation.\n"
                     "- MORTRA-discovered structures: none recorded; dependency diagnosis is external code inspection.\n"
                     "- Failed attempts: preserve both original_run/incomplete.json and tracebacks. "
                     "The stop is an unavailable required dependency under the requested no-oracle rule, not measured policy failure.\n"
                     "- Reproduction: use the recorded commit and .github/workflows/mortra-autonomous-completion.yml; "
                     "python -m experiments.autonomous_completion.probe --output <new-directory>.\n\n"
                     "The two executions are reproduction attempts, not two autonomous improvements or independent games. "
                     "No random-policy comparison ran because task construction had not occurred. "
                     "A green workflow means the stop was recorded and reproduced, not that MORTRA completed the objective.\n")
    save(args.output / "artifact_hashes.json", {
        p.relative_to(args.output).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(args.output.rglob("*")) if p.is_file()})
    print(json.dumps(summary, indent=2), flush=True)
    if not summary["harness_audit_completed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
