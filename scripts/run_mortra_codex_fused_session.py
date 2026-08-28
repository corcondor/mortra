"""Keep MORTRA and the current Codex turn in one blocking JSONL session."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from worker.backend.mortra_codex_fused_session import (  # noqa: E402
    FusedResearchSession,
    TRANSPORT,
)
from worker.backend.mortra_research_dialogue import (  # noqa: E402
    ResearchDialogueLedger,
    payload_sha256,
)


OBJECTIVE_CODE = "synchronous_mortra_codex_strict_geometry_improvement"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _dataset(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) % 2:
        raise ValueError("dataset must contain name/source line pairs")
    return {lines[index]: lines[index + 1] for index in range(0, len(lines), 2)}


def _stop_obligation(*, solved: bool, source: str) -> dict[str, Any] | None:
    if solved:
        return None
    from scripts.experiment_mortra_codex_research_dialogue import (
        _nearest_chart_contracts,
    )

    return {
        "kind": "no_replayed_exact_certificate",
        "nearest_chart_contracts": _nearest_chart_contracts(source),
    }


def _snapshot(
    *,
    union_path: Path,
    dataset_path: Path,
    natural_dataset_path: Path,
) -> dict[str, Any]:
    from scripts.experiment_mortra_codex_research_dialogue import (
        _attempt_summary,
        _goal,
        _operation_multiset,
    )
    from worker.backend.exact_geometry_chart_portfolio import (
        certify_jgex_with_exact_chart_portfolio,
        registered_exact_chart_contracts,
    )
    from worker.backend.geometry_natural_semantics import (
        extract_geometry_natural_semantics,
    )

    union = json.loads(union_path.read_text(encoding="utf-8"))
    sources = _dataset(dataset_path)
    natural_sources = json.loads(natural_dataset_path.read_text(encoding="utf-8"))
    names = tuple(map(str, union["sets"]["unresolved_frozen_problems"]))
    problems: dict[str, Any] = {}
    for name in names:
        source = sources[name]
        natural = natural_sources.get(name, "")
        result = certify_jgex_with_exact_chart_portfolio(
            source,
            include_diagram=False,
            natural_statement=natural,
        )
        summary = _attempt_summary(result)
        problems[name] = {
            **summary,
            "source_sha256": result.source_sha256,
            "natural_statement_sha256": result.natural_statement_sha256,
            "operation_multiset": _operation_multiset(source),
            "goal": _goal(source),
            "natural_semantic_atoms": list(
                extract_geometry_natural_semantics(natural).typed_atoms
            ),
            "stop_obligation": _stop_obligation(
                solved=bool(result.solved),
                source=source,
            ),
        }
    return {
        "protocol": TRANSPORT,
        "union_sha256": _sha256(union_path),
        "dataset_sha256": _sha256(dataset_path),
        "natural_dataset_sha256": _sha256(natural_dataset_path),
        "registered_chart_contracts_sha256": payload_sha256(
            registered_exact_chart_contracts()
        ),
        "summary": {
            "evaluated": len(names),
            "solved": sum(bool(item["solved"]) for item in problems.values()),
            "remaining_unproved": sum(
                not bool(item["solved"]) for item in problems.values()
            ),
            "quantifier_repair_only": sum(
                bool(item["proved_after_quantifier_repair_only"])
                for item in problems.values()
            ),
        },
        "problems": problems,
    }


def _fresh_snapshot(args: argparse.Namespace) -> dict[str, Any]:
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--snapshot-worker",
        "--union",
        str(args.union),
        "--dataset",
        str(args.dataset),
        "--natural-dataset",
        str(args.natural_dataset),
    ]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return json.loads(completed.stdout)


def _emit(value: dict[str, Any]) -> None:
    print(json.dumps(value, ensure_ascii=True, sort_keys=True), flush=True)


def _source_hashes(paths: list[str]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for raw_path in paths:
        path = (ROOT / raw_path).resolve()
        path.relative_to(ROOT)
        hashes[path.relative_to(ROOT).as_posix()] = _sha256(path)
    return hashes


def _frozen_identity(args: argparse.Namespace) -> tuple[str, tuple[str, ...]]:
    union = json.loads(args.union.read_text(encoding="utf-8"))
    names = tuple(map(str, union["sets"]["unresolved_frozen_problems"]))
    identity = {
        "union_sha256": _sha256(args.union),
        "dataset_sha256": _sha256(args.dataset),
        "natural_dataset_sha256": _sha256(args.natural_dataset),
        "problem_names": names,
    }
    return payload_sha256(identity), names


def _run_session(args: argparse.Namespace) -> int:
    cohort_sha256, names = _frozen_identity(args)
    if args.ledger.exists():
        ledger = ResearchDialogueLedger.load(args.ledger)
        if ledger.frozen_cohort_sha256 != cohort_sha256:
            raise ValueError("ledger belongs to a different frozen cohort")
    else:
        ledger = ResearchDialogueLedger.create(
            objective_code=OBJECTIVE_CODE,
            frozen_cohort_sha256=cohort_sha256,
        )
    session = FusedResearchSession(
        ledger=ledger,
        ledger_path=args.ledger,
        frozen_problem_names=names,
    )
    event = session.begin_cycle(_fresh_snapshot(args))
    _emit(event)
    active_fingerprint = str(event["cycle_fingerprint"])

    for line in sys.stdin:
        try:
            command = json.loads(line)
            command_type = command.get("type")
            if command_type == "ping":
                _emit(
                    {
                        "protocol": TRANSPORT,
                        "event": "pong",
                        "cycle_fingerprint": active_fingerprint,
                    }
                )
            elif command_type == "hypothesis":
                active_fingerprint = str(command["cycle_fingerprint"])
                _emit(
                    session.submit_hypothesis(
                        cycle_fingerprint=active_fingerprint,
                        payload=dict(command["payload"]),
                    )
                )
            elif command_type == "evaluate":
                active_fingerprint = str(command["cycle_fingerprint"])
                treatment = _fresh_snapshot(args)
                _emit(
                    session.close_cycle(
                        cycle_fingerprint=active_fingerprint,
                        treatment_snapshot=treatment,
                        intervention_source_sha256=_source_hashes(
                            list(command.get("intervention_source_paths", []))
                        ),
                    )
                )
                event = session.begin_cycle(treatment)
                active_fingerprint = str(event["cycle_fingerprint"])
                _emit(event)
            elif command_type == "shutdown":
                _emit({"protocol": TRANSPORT, "event": "shutdown_ack"})
                return 0
            else:
                raise ValueError(f"unsupported command type: {command_type}")
        except Exception as error:
            _emit(
                {
                    "protocol": TRANSPORT,
                    "event": "protocol_error",
                    "error_type": type(error).__name__,
                    "error": str(error),
                }
            )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--union", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--natural-dataset", type=Path, required=True)
    parser.add_argument("--ledger", type=Path)
    parser.add_argument("--snapshot-worker", action="store_true")
    args = parser.parse_args()
    if args.snapshot_worker:
        print(
            json.dumps(
                _snapshot(
                    union_path=args.union,
                    dataset_path=args.dataset,
                    natural_dataset_path=args.natural_dataset,
                ),
                ensure_ascii=True,
                sort_keys=True,
            )
        )
        return 0
    if args.ledger is None:
        parser.error("--ledger is required for a fused session")
    return _run_session(args)


if __name__ == "__main__":
    raise SystemExit(main())
