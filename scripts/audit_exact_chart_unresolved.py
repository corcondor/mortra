"""Audit every unresolved frozen problem against the exact-chart registry."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from worker.backend.exact_geometry_chart_portfolio import (  # noqa: E402
    certify_jgex_with_exact_chart_portfolio,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _dataset(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) % 2:
        raise ValueError("HAGeo dataset must contain name/source line pairs")
    return {lines[index]: lines[index + 1] for index in range(0, len(lines), 2)}


def audit_unresolved(
    union_path: Path,
    dataset_path: Path,
    natural_dataset_path: Path | None = None,
) -> dict[str, object]:
    union = json.loads(union_path.read_text(encoding="utf-8"))
    sources = _dataset(dataset_path)
    natural_sources = (
        json.loads(natural_dataset_path.read_text(encoding="utf-8"))
        if natural_dataset_path is not None
        else {}
    )
    unresolved = tuple(map(str, union["sets"]["unresolved_frozen_problems"]))
    missing = sorted(set(unresolved) - set(sources))
    if missing:
        raise ValueError(f"unresolved problems missing from dataset: {missing}")

    started = time.perf_counter()
    results = {}
    for name in unresolved:
        result = certify_jgex_with_exact_chart_portfolio(
            sources[name],
            include_diagram=False,
            natural_statement=natural_sources.get(name),
        )
        selected = result.selected
        repaired_only = bool(
            selected
            and selected.application.get("formalization_repair_required", False)
        )
        results[name] = {
            "matched": result.solved and not repaired_only,
            "proved_after_quantifier_repair_only": repaired_only,
            "chart_id": selected.chart_id if selected is not None else None,
            "proof_sha256": (
                selected.chart_certificate_sha256 if selected is not None else None
            ),
            "source_sha256": result.source_sha256,
            "ambiguous": result.ambiguous,
            "natural_statement_sha256": result.natural_statement_sha256,
        }
    elapsed = time.perf_counter() - started
    matched = sum(bool(item["matched"]) for item in results.values())
    repaired_only = sum(
        bool(item["proved_after_quantifier_repair_only"])
        for item in results.values()
    )
    ambiguous = sum(bool(item["ambiguous"]) for item in results.values())
    return {
        "experiment": "exact_chart_unresolved_runtime_audit",
        "protocol": {
            "uses_external_llm": False,
            "uses_expected_answer": False,
            "matching": (
                "problem-name-independent structural matcher + exact certificate replay"
            ),
            "source_union": str(union_path.as_posix()),
            "source_union_sha256": _sha256(union_path),
            "dataset": str(dataset_path.as_posix()),
            "dataset_sha256": _sha256(dataset_path),
            "natural_dataset": (
                str(natural_dataset_path.as_posix())
                if natural_dataset_path is not None
                else None
            ),
            "natural_dataset_sha256": (
                _sha256(natural_dataset_path)
                if natural_dataset_path is not None
                else None
            ),
        },
        "summary": {
            "evaluated": len(unresolved),
            "matched": matched,
            "rejected": len(unresolved) - matched,
            "ambiguous": ambiguous,
            "proved_after_quantifier_repair_only": repaired_only,
            "elapsed_seconds": elapsed,
        },
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--union", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--natural-dataset", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit_unresolved(args.union, args.dataset, args.natural_dataset)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0 if not report["summary"]["matched"] and not report["summary"]["ambiguous"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
