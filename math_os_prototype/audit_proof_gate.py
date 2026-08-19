"""Measure what a proof-status gate changes in a saved public benchmark.

This is an evaluation-only ablation.  It never changes an answer and therefore
cannot be credited with solving an additional problem.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable


def is_answered(record: dict[str, Any]) -> bool:
    return record.get("answer") not in (None, "")


def summarize(
    records: list[dict[str, Any]],
    predicate: Callable[[dict[str, Any]], bool],
) -> dict[str, int | float]:
    selected = [record for record in records if predicate(record)]
    correct = sum(bool(record.get("exact_match")) for record in selected)
    answered = len(selected)
    total = len(records)
    return {
        "total": total,
        "answered": answered,
        "correct": correct,
        "wrong": answered - correct,
        "abstained": total - answered,
        "exact_match_rate": correct / total if total else 0.0,
        "answer_precision": correct / answered if answered else 0.0,
    }


def audit(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = list(payload.get("records") or [])
    current = summarize(records, is_answered)
    verification_gate = summarize(
        records,
        lambda record: is_answered(record) and record.get("verification") == "verified",
    )
    obligation_gate = summarize(
        records,
        lambda record: (
            is_answered(record)
            and int(record.get("backend_obligation_count") or 0) > 0
            and int(record.get("executed_tool_count") or 0)
            == int(record.get("backend_obligation_count") or 0)
        ),
    )
    return {
        "source": str(path),
        "current": current,
        "verification_gate": verification_gate,
        "backend_obligation_gate": obligation_gate,
        "deltas": {
            "verification_gate_exact": verification_gate["correct"] - current["correct"],
            "verification_gate_wrong": verification_gate["wrong"] - current["wrong"],
            "verification_gate_precision": (
                verification_gate["answer_precision"] - current["answer_precision"]
            ),
            "backend_gate_exact": obligation_gate["correct"] - current["correct"],
            "backend_gate_wrong": obligation_gate["wrong"] - current["wrong"],
            "backend_gate_precision": (
                obligation_gate["answer_precision"] - current["answer_precision"]
            ),
        },
        "interpretation": (
            "A proof gate can remove unsupported answers, but it cannot create "
            "new correct answers. Exact-match growth requires additional typed "
            "lowering and executable backend realizers."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("benchmark", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(args.benchmark)
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
