"""Audit the positive-similarity chart against a frozen unresolved cohort."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from worker.backend.positive_similarity_six_circumcenters_chart import (
    certify_jgex_positive_similarity_six_circumcenters_application,
)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _formulations(markdown: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for section in re.split(r"(?m)^## ", markdown)[1:]:
        name, _, body = section.partition("\n")
        match = re.search(r"```text\s*\n(.*?)\n```", body, flags=re.DOTALL)
        if match:
            result[name.strip()] = match.group(1).strip()
    return result


def audit(
    *,
    base_union_path: Path,
    dossier_path: Path,
) -> dict[str, Any]:
    base_union = _load(base_union_path)
    unresolved = tuple(base_union["sets"]["unresolved_frozen_problems"])
    formulations = _formulations(dossier_path.read_text(encoding="utf-8"))
    missing = sorted(set(unresolved) - formulations.keys())
    if missing:
        raise ValueError(f"dossier is missing unresolved formulations: {missing}")

    results: dict[str, dict[str, object]] = {}
    for name in unresolved:
        source = formulations[name]
        application = certify_jgex_positive_similarity_six_circumcenters_application(
            source
        )
        results[name] = {
            "matched": application.replayed,
            "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
            "chart_certificate_sha256": (
                application.chart_certificate_sha256 if application.replayed else None
            ),
        }

    matched = [name for name, result in results.items() if result["matched"]]
    return {
        "experiment": "positive_similarity_chart_unresolved_counterfactual_audit",
        "protocol": {
            "uses_external_llm": False,
            "uses_expected_answer": False,
            "dispatches_on_problem_id": False,
            "base_union": {
                "path": base_union_path.as_posix(),
                "sha256": _sha256(base_union_path),
            },
            "dossier": {
                "path": dossier_path.as_posix(),
                "sha256": _sha256(dossier_path),
            },
        },
        "summary": {
            "evaluated": len(results),
            "matched": len(matched),
            "rejected": len(results) - len(matched),
            "matched_problem_names": matched,
        },
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-union", type=Path, required=True)
    parser.add_argument("--dossier", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    payload = audit(
        base_union_path=args.base_union.resolve(),
        dossier_path=args.dossier.resolve(),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload["summary"], ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
