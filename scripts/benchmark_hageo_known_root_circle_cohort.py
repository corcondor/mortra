"""Audit HAGeo problems containing a known-root circle intersection.

The cohort is selected from Newclid's parsed JGEX construction tree, not from
surface text.  Each problem is lowered without dataset auxiliary clauses and
is accepted only when the exact polynomial certificate replays to zero.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import UTC, datetime
import hashlib
import json
import multiprocessing as mp
import os
from pathlib import Path
import queue
import subprocess
import sys
import time
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    return (
        resolved.relative_to(ROOT).as_posix()
        if resolved.is_relative_to(ROOT)
        else resolved.as_posix()
    )


def extract_known_root_circle_cohort(
    formulations: Mapping[str, Any],
) -> list[dict[str, object]]:
    """Select clauses whose two circles share a parsed, identical known point."""

    grouped: dict[str, list[dict[str, object]]] = {}
    for problem, formulation in formulations.items():
        for clause_index, clause in enumerate(formulation.setup_clauses):
            constructions = clause.constructions
            if len(clause.points) != 1 or len(constructions) != 2:
                continue
            if not all(
                construction.name == "on_circle" and len(construction.args) == 2
                for construction in constructions
            ):
                continue
            first, second = constructions
            if first.args[1] != second.args[1]:
                continue
            grouped.setdefault(problem, []).append(
                {
                    "clause_index": clause_index,
                    "clause": str(clause),
                    "output": clause.points[0],
                    "centers": [first.args[0], second.args[0]],
                    "shared_known_point": first.args[1],
                }
            )
    return [
        {"problem": problem, "matched_clauses": grouped[problem]}
        for problem in sorted(grouped)
    ]


def classify_result(status: str, reason: str | None = None) -> str:
    if status == "proved":
        return "exact_proof"
    if status == "unproved":
        return "nonzero_exact_remainder"
    if status == "right_censored_timeout":
        return "right_censored_timeout"
    if status == "execution_error":
        return "execution_error"

    normalized = (reason or "").lower()
    invalid_markers = (
        "parallel lines cannot define an intersection",
        "coincident circles do not define a second intersection",
        "tangent circles do not define a distinct second intersection",
        "circle intersection reuses an already-existing point",
    )
    if any(marker in normalized for marker in invalid_markers):
        return "construction_semantics_rejected"
    if (
        "unsupported" in normalized
        or "normalization left unresolved constructions" in normalized
    ):
        return "unsupported_construction_vocabulary"
    if status == "unsupported":
        return "exact_backend_limitation"
    return "unknown_failure"


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _read_progress_checkpoint(path: Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _write_certified_artifact(
    *,
    problem: str,
    source: str,
    proof_path: Path,
    proof: Mapping[str, Any],
    artifact_path: Path,
) -> None:
    certificate = proof["certificate"]
    _write_json(
        artifact_path,
        {
            "problem_name": problem,
            "solved": True,
            "certificate": {
                "source": "jgex_exact_elimination",
                "input_sha256": _sha256_bytes(source.encode("utf-8")),
                "proof_sha256": certificate["certificate_sha256"],
                "proof_path": _display_path(proof_path),
                "proof_file_sha256": _sha256(proof_path),
            },
        },
    )


def _finish_result(
    result_path: Path,
    payload: dict[str, object],
    *,
    reused: bool = False,
) -> dict[str, object]:
    payload["reused"] = reused
    if not reused:
        _write_json(result_path, payload)
    return payload


def _result_from_proof(
    *,
    cohort_entry: Mapping[str, object],
    source: str,
    input_path: Path,
    proof_path: Path,
    artifact_path: Path,
    result_path: Path,
    progress_checkpoint: Mapping[str, object] | None = None,
) -> dict[str, object]:
    problem = str(cohort_entry["problem"])
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    status = str(proof.get("status", "execution_error"))
    reason = proof.get("reason")
    exact = proof.get("certificate")
    solved = bool(
        status == "proved"
        and isinstance(exact, Mapping)
        and exact.get("exact_replay") is True
        and str(exact.get("remainder", "")) == "0"
    )
    if solved:
        _write_certified_artifact(
            problem=problem,
            source=source,
            proof_path=proof_path,
            proof=proof,
            artifact_path=artifact_path,
        )
    return _finish_result(
        result_path,
        {
            **cohort_entry,
            "status": status,
            "classification": classify_result(
                status, str(reason) if reason else None
            ),
            "solved": solved,
            "reason": reason,
            "input": _display_path(input_path),
            "proof": _display_path(proof_path),
            "proof_file_sha256": _sha256(proof_path),
            "certified_artifact": _display_path(artifact_path) if solved else None,
            "certificate_sha256": (
                exact.get("certificate_sha256")
                if isinstance(exact, Mapping)
                else None
            ),
            "construction_vocabulary": (
                exact.get("construction_vocabulary")
                if isinstance(exact, Mapping)
                else None
            ),
            "progress_checkpoint": progress_checkpoint,
        },
    )


def run_one(
    *,
    python: Path,
    source: str,
    cohort_entry: Mapping[str, object],
    run_dir: Path,
    timeout_seconds: float,
    max_saturation_rounds: int,
    local_max_steps: int | None = None,
    resume: bool,
) -> dict[str, object]:
    problem = str(cohort_entry["problem"])
    input_path = (run_dir / "inputs" / f"{problem}.txt").resolve()
    proof_path = (run_dir / "proofs" / f"{problem}.json").resolve()
    artifact_path = (run_dir / "artifacts" / f"{problem}.json").resolve()
    result_path = (run_dir / "results" / f"{problem}.json").resolve()
    progress_path = (run_dir / "progress" / f"{problem}.json").resolve()

    if resume and result_path.is_file():
        saved = json.loads(result_path.read_text(encoding="utf-8"))
        return _finish_result(result_path, saved, reused=True)

    input_path.parent.mkdir(parents=True, exist_ok=True)
    proof_path.parent.mkdir(parents=True, exist_ok=True)
    input_path.write_text(source + "\n", encoding="utf-8")
    if progress_path.is_file():
        progress_path.unlink()
    command = [
        str(python),
        "-B",
        str(ROOT / "scripts" / "run_jgex_exact_specialist.py"),
        "--input",
        str(input_path),
        "--output",
        str(proof_path),
        "--progress-output",
        str(progress_path),
        "--representation",
        "goal_local_relational",
        "--enable-affine-local-lemmas",
        "--max-saturation-rounds",
        str(max_saturation_rounds),
    ]
    if local_max_steps is not None:
        command.extend(("--local-max-steps", str(local_max_steps)))
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=None if timeout_seconds <= 0 else timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return _finish_result(result_path, {
            **cohort_entry,
            "status": "right_censored_timeout",
            "classification": "right_censored_timeout",
            "solved": False,
            "input": _display_path(input_path),
            "progress_checkpoint": _read_progress_checkpoint(progress_path),
        })

    if completed.returncode != 0 or not proof_path.is_file():
        return _finish_result(result_path, {
            **cohort_entry,
            "status": "execution_error",
            "classification": "execution_error",
            "solved": False,
            "returncode": completed.returncode,
            "stderr_tail": completed.stderr[-2000:],
            "input": _display_path(input_path),
            "progress_checkpoint": _read_progress_checkpoint(progress_path),
        })

    return _result_from_proof(
        cohort_entry=cohort_entry,
        source=source,
        input_path=input_path,
        proof_path=proof_path,
        artifact_path=artifact_path,
        result_path=result_path,
        progress_checkpoint=_read_progress_checkpoint(progress_path),
    )


def _persistent_exact_worker(
    requests: mp.Queue,
    responses: mp.Queue,
) -> None:
    from worker.backend.jgex_exact_constraint_bridge import (
        lower_jgex_to_exact_obligation,
    )

    responses.put({"kind": "ready"})
    while True:
        request = requests.get()
        if request is None:
            return
        request_id = str(request["request_id"])
        progress_path = Path(str(request["progress_path"])).resolve()
        progress_history: list[dict[str, object]] = []

        def checkpoint(event: dict[str, object]) -> None:
            progress_history.append(dict(event))
            _write_json(
                progress_path,
                {
                    "status": "running",
                    "request_id": request_id,
                    "updated_at": datetime.now(UTC).isoformat(),
                    "latest_stage": event.get("stage"),
                    "latest_event": event,
                    "progress": progress_history[-64:],
                },
            )

        try:
            certificate = lower_jgex_to_exact_obligation(
                str(request["source"]),
                representation="goal_local_relational",
                max_saturation_rounds=int(request["max_saturation_rounds"]),
                local_max_steps=(
                    int(request["local_max_steps"])
                    if request.get("local_max_steps") is not None
                    else None
                ),
                enable_affine_local_lemmas=True,
                progress_callback=checkpoint,
            )
            response = {
                "request_id": request_id,
                "status": "proved" if certificate.exact_replay else "unproved",
                "certificate": asdict(certificate),
            }
        except ValueError as error:
            response = {
                "request_id": request_id,
                "status": "unsupported",
                "reason": str(error),
            }
        except Exception as error:
            response = {
                "request_id": request_id,
                "status": "execution_error",
                "reason": f"{type(error).__name__}: {error}",
            }
        responses.put(response)


class PersistentExactWorker:
    def __init__(self, *, startup_timeout_seconds: float) -> None:
        self.context = mp.get_context("spawn")
        self.startup_timeout_seconds = startup_timeout_seconds
        self.requests: mp.Queue | None = None
        self.responses: mp.Queue | None = None
        self.process: mp.Process | None = None

    def start(self) -> None:
        self.stop()
        self.requests = self.context.Queue()
        self.responses = self.context.Queue()
        self.process = self.context.Process(
            target=_persistent_exact_worker,
            args=(self.requests, self.responses),
        )
        self.process.start()
        deadline = time.monotonic() + self.startup_timeout_seconds
        ready: dict[str, object] | None = None
        while ready is None and time.monotonic() < deadline:
            if not self.process.is_alive():
                exit_code = self.process.exitcode
                self.stop()
                raise RuntimeError(
                    f"persistent exact worker exited during startup: {exit_code}"
                )
            try:
                ready = self.responses.get(timeout=0.25)
            except queue.Empty:
                continue
        if ready is None:
            self.stop()
            raise TimeoutError("persistent exact worker did not finish startup")
        if ready.get("kind") != "ready":
            self.stop()
            raise RuntimeError(f"unexpected worker startup response: {ready!r}")

    def solve(
        self,
        *,
        request_id: str,
        source: str,
        timeout_seconds: float,
        max_saturation_rounds: int,
        local_max_steps: int | None,
        progress_path: Path,
    ) -> dict[str, object]:
        if self.process is None or not self.process.is_alive():
            self.start()
        assert self.requests is not None
        assert self.responses is not None
        self.requests.put(
            {
                "request_id": request_id,
                "source": source,
                "max_saturation_rounds": max_saturation_rounds,
                "local_max_steps": local_max_steps,
                "progress_path": str(progress_path.resolve()),
            }
        )
        try:
            response = self.responses.get(
                timeout=None if timeout_seconds <= 0 else timeout_seconds
            )
        except queue.Empty:
            self.stop()
            return {
                "status": "right_censored_timeout",
                "progress_checkpoint": _read_progress_checkpoint(progress_path),
            }
        if str(response.get("request_id")) != request_id:
            self.stop()
            return {
                "status": "execution_error",
                "reason": "persistent worker returned a mismatched request id",
            }
        return {
            **response,
            "progress_checkpoint": _read_progress_checkpoint(progress_path),
        }

    def stop(self) -> None:
        process = self.process
        requests = self.requests
        if process is not None and process.is_alive():
            if requests is not None:
                requests.put(None)
            process.join(2)
            if process.is_alive():
                process.terminate()
                process.join(5)
        self.process = None
        self.requests = None
        self.responses = None


def run_one_persistent(
    *,
    worker: PersistentExactWorker,
    source: str,
    cohort_entry: Mapping[str, object],
    run_dir: Path,
    timeout_seconds: float,
    max_saturation_rounds: int,
    local_max_steps: int | None,
    resume: bool,
) -> dict[str, object]:
    problem = str(cohort_entry["problem"])
    input_path = (run_dir / "inputs" / f"{problem}.txt").resolve()
    proof_path = (run_dir / "proofs" / f"{problem}.json").resolve()
    artifact_path = (run_dir / "artifacts" / f"{problem}.json").resolve()
    result_path = (run_dir / "results" / f"{problem}.json").resolve()
    progress_path = (run_dir / "progress" / f"{problem}.json").resolve()
    if resume and result_path.is_file():
        saved = json.loads(result_path.read_text(encoding="utf-8"))
        return _finish_result(result_path, saved, reused=True)

    input_path.parent.mkdir(parents=True, exist_ok=True)
    input_path.write_text(source + "\n", encoding="utf-8")
    if progress_path.is_file():
        progress_path.unlink()
    response = worker.solve(
        request_id=problem,
        source=source,
        timeout_seconds=timeout_seconds,
        max_saturation_rounds=max_saturation_rounds,
        local_max_steps=local_max_steps,
        progress_path=progress_path,
    )
    status = str(response.get("status", "execution_error"))
    if status == "right_censored_timeout":
        return _finish_result(
            result_path,
            {
                **cohort_entry,
                "status": status,
                "classification": "right_censored_timeout",
                "solved": False,
                "input": _display_path(input_path),
                "progress_checkpoint": response.get("progress_checkpoint"),
            },
        )

    proof_payload = {key: value for key, value in response.items() if key != "request_id"}
    _write_json(proof_path, proof_payload)
    return _result_from_proof(
        cohort_entry=cohort_entry,
        source=source,
        input_path=input_path,
        proof_path=proof_path,
        artifact_path=artifact_path,
        result_path=result_path,
        progress_checkpoint=response.get("progress_checkpoint"),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base-union", type=Path)
    parser.add_argument("--problems", nargs="*")
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument(
        "--execution-mode",
        choices=("isolated", "persistent"),
        default="persistent",
    )
    parser.add_argument("--startup-timeout-seconds", type=float, default=300.0)
    parser.add_argument("--max-saturation-rounds", type=int, default=1)
    parser.add_argument("--local-max-steps", type=int)
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Ignore per-problem result checkpoints and recompute the cohort.",
    )
    args = parser.parse_args()

    dataset = args.dataset.resolve()
    args.run_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = (args.run_dir / "cohort-manifest.json").resolve()
    completed = subprocess.run(
        (
            str(args.python.resolve()),
            "-B",
            str(ROOT / "scripts" / "extract_hageo_known_root_circle_cohort.py"),
            "--dataset",
            str(dataset),
            "--output",
            str(manifest_path),
        ),
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=args.startup_timeout_seconds,
    )
    if completed.returncode != 0 or not manifest_path.is_file():
        raise RuntimeError(
            "cohort extraction failed: "
            + (completed.stderr[-2000:] or completed.stdout[-2000:])
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cohort = list(manifest["cohort"])
    sources = {str(key): str(value) for key, value in manifest["sources"].items()}
    if args.problems:
        requested = set(args.problems)
        cohort = [entry for entry in cohort if entry["problem"] in requested]
        missing = sorted(requested - {str(entry["problem"]) for entry in cohort})
        if missing:
            raise ValueError("requested problems are outside the cohort: " + ", ".join(missing))

    base_names: set[str] = set()
    base_hash: str | None = None
    if args.base_union is not None:
        base_path = args.base_union.resolve()
        base = json.loads(base_path.read_text(encoding="utf-8"))
        base_names = set(map(str, base.get("sets", {}).get("primary_union", ())))
        base_hash = _sha256(base_path)

    results: list[dict[str, object]] = []
    if args.execution_mode == "persistent":
        persistent_worker = PersistentExactWorker(
            startup_timeout_seconds=args.startup_timeout_seconds
        )
        try:
            iterator = (
                run_one_persistent(
                    worker=persistent_worker,
                    source=sources[str(entry["problem"])],
                    cohort_entry=entry,
                    run_dir=args.run_dir.resolve(),
                    timeout_seconds=args.timeout_seconds,
                    max_saturation_rounds=args.max_saturation_rounds,
                    local_max_steps=args.local_max_steps,
                    resume=not args.no_resume,
                )
                for entry in cohort
            )
            for result in iterator:
                results.append(result)
                print(
                    json.dumps(
                        {
                            "problem": result["problem"],
                            "status": result["status"],
                            "classification": result["classification"],
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
                _write_json(
                    args.output.resolve(),
                    {
                        "experiment": (
                            "hageo_known_root_circle_intersection_cohort_checkpoint"
                        ),
                        "created_at": datetime.now(UTC).isoformat(),
                        "complete": False,
                        "expected_problem_count": len(cohort),
                        "completed_problem_count": len(results),
                        "missing_problems": sorted(
                            {str(entry["problem"]) for entry in cohort}
                            - {str(item["problem"]) for item in results}
                        ),
                        "results": sorted(
                            results, key=lambda item: str(item["problem"])
                        ),
                    },
                )
        finally:
            persistent_worker.stop()
    else:
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
            futures = {
                executor.submit(
                    run_one,
                    python=args.python.resolve(),
                    source=sources[str(entry["problem"])],
                    cohort_entry=entry,
                    run_dir=args.run_dir.resolve(),
                    timeout_seconds=args.timeout_seconds,
                    max_saturation_rounds=args.max_saturation_rounds,
                    local_max_steps=args.local_max_steps,
                    resume=not args.no_resume,
                ): str(entry["problem"])
                for entry in cohort
            }
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                print(
                    json.dumps(
                        {
                            "problem": result["problem"],
                            "status": result["status"],
                            "classification": result["classification"],
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
                _write_json(
                    args.output.resolve(),
                    {
                        "experiment": (
                            "hageo_known_root_circle_intersection_cohort_checkpoint"
                        ),
                        "created_at": datetime.now(UTC).isoformat(),
                        "complete": False,
                        "expected_problem_count": len(cohort),
                        "completed_problem_count": len(results),
                        "missing_problems": sorted(
                            {str(entry["problem"]) for entry in cohort}
                            - {str(item["problem"]) for item in results}
                        ),
                        "results": sorted(
                            results, key=lambda item: str(item["problem"])
                        ),
                    },
                )

    results.sort(key=lambda item: str(item["problem"]))
    classes = sorted({str(item["classification"]) for item in results})
    proved_names = {str(item["problem"]) for item in results if item["solved"]}
    report = {
        "experiment": "hageo_known_root_circle_intersection_cohort",
        "created_at": datetime.now(UTC).isoformat(),
        "protocol": {
            "uses_external_llm": False,
            "uses_expected_answer": False,
            "uses_problem_specific_solver_logic": False,
            "dataset_auxiliary_clauses_hidden": True,
            "cohort_selection": (
                "parsed JGEX clause with one output and exactly two on_circle "
                "constructions sharing the identical second argument"
            ),
            "truth_plane": "exact polynomial certificate replay with zero remainder",
            "timeout_semantics": "right-censored unknown",
            "timeout_seconds_per_problem": (
                args.timeout_seconds if args.timeout_seconds > 0 else None
            ),
            "workers": max(1, args.workers),
            "execution_mode": args.execution_mode,
            "startup_timeout_seconds": args.startup_timeout_seconds,
            "representation": "goal_local_relational",
            "affine_local_lemmas": True,
            "max_saturation_rounds": args.max_saturation_rounds,
            "local_max_steps": args.local_max_steps,
            "dataset_sha256": _sha256(dataset),
            "base_union_sha256": base_hash,
            "surface_regex_audit": {
                "previous_count": 37,
                "parsed_problem_count": 36,
                "false_positive": "2021GOWACAp4",
                "reason": (
                    "the surface backreference matched radius point 'a1' as if it "
                    "were the shared point 'a'; parsed arguments are distinct"
                ),
            },
        },
        "summary": {
            "cohort_total": len(results),
            "exact_proved": len(proved_names),
            "already_in_base_union": len(proved_names & base_names),
            "new_certified_candidates": len(proved_names - base_names),
            "by_classification": {
                classification: sum(
                    item["classification"] == classification for item in results
                )
                for classification in classes
            },
        },
        "sets": {
            "cohort": [str(entry["problem"]) for entry in cohort],
            "exact_proved": sorted(proved_names),
            "already_in_base_union": sorted(proved_names & base_names),
            "new_certified_candidates": sorted(proved_names - base_names),
        },
        "results": results,
    }
    _write_json(args.output.resolve(), report)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
