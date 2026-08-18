"""Audit HAGeo-409 lifting without attempting theorem proofs."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from newclid.jgex.formulation import JGEXFormulation, jgex_formulation_from_txt_file
from newclid.jgex.problem_builder import JGEXProblemBuilder

from worker.backend.jgex_legacy_normalizer import normalize_legacy_formulation


def split_of(identifier: str) -> str:
    bucket = int.from_bytes(hashlib.sha256(identifier.encode()).digest()[:8], "big") % 10
    if bucket < 6:
        return "dev"
    if bucket < 8:
        return "calibration"
    return "held_out"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    formulations = jgex_formulation_from_txt_file(args.dataset.resolve())
    results: dict[str, dict[str, object]] = {}
    vocabulary = Counter()
    for identifier, raw in formulations.items():
        for clause in (*raw.setup_clauses, *raw.auxiliary_clauses):
            vocabulary.update(item.name for item in clause.constructions)
        try:
            builder = JGEXProblemBuilder(np.random.default_rng(0))
            setup_only = JGEXFormulation(
                name=raw.name,
                setup_clauses=raw.setup_clauses,
                auxiliary_clauses=(),
                goals=raw.goals,
            )
            normalized, report = normalize_legacy_formulation(
                setup_only, builder.jgex_defs
            )
            builder.with_problem(normalized).include_auxiliary_clauses(False).build()
            results[identifier] = {
                "status": "buildable",
                "split": split_of(identifier),
                "normalization": asdict(report),
            }
        except Exception as error:
            results[identifier] = {
                "status": "build_error",
                "split": split_of(identifier),
                "error_type": type(error).__name__,
                "error": str(error)[:1000],
            }

    status_counts = Counter(item["status"] for item in results.values())
    split_counts = {
        split: Counter(
            item["status"]
            for item in results.values()
            if item["split"] == split
        )
        for split in ("dev", "calibration", "held_out")
    }
    report = {
        "experiment": "hageo409_jgex_compatibility_audit",
        "protocol": {
            "uses_external_llm": False,
            "uses_answers": False,
            "uses_auxiliary_clauses": False,
            "split": "sha256(problem_id) mod 10: dev 0-5, calibration 6-7, held_out 8-9",
        },
        "summary": {
            "total": len(results),
            "status_counts": dict(status_counts),
            "split_counts": {
                split: dict(counts) for split, counts in split_counts.items()
            },
            "construction_vocabulary_size": len(vocabulary),
            "construction_vocabulary": dict(vocabulary.most_common()),
        },
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
