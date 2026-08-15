"""Merge independently replayed JGEX certificates into one portfolio report."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--reports", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    baseline_score = baseline["scores"]["original_imo_ag_30"]
    certificates: dict[str, dict] = {}
    evidence: dict[str, list[dict]] = {}

    for path in args.reports:
        report = json.loads(path.read_text(encoding="utf-8"))
        for problem, result in report["results"].items():
            if result["status"] != "proved":
                continue
            certificate = result["certificate"]
            if not certificate["exact_replay"] or certificate["remainder"] != "0":
                raise ValueError(f"invalid exact certificate for {problem} in {path}")
            previous = certificates.get(problem)
            if previous is not None and (
                previous["certificate_sha256"] != certificate["certificate_sha256"]
            ):
                raise ValueError(f"conflicting exact certificates for {problem}")
            certificates[problem] = certificate
            evidence.setdefault(problem, []).append(
                {
                    "report": str(path),
                    "elapsed_seconds": result["elapsed_seconds"],
                    "certificate_sha256": certificate["certificate_sha256"],
                }
            )

    solved = int(baseline_score["solved"]) + len(certificates)
    total = int(baseline_score["total"])
    output = {
        "experiment": "jgex_exact_certificate_portfolio",
        "generated_at": datetime.now(UTC).isoformat(),
        "uses_llm": False,
        "acceptance_rule": "exact_replay=true and remainder=0",
        "baseline": {
            "report": str(args.baseline),
            "solved": baseline_score["solved"],
            "total": total,
        },
        "exact_backend": {
            "proved": len(certificates),
            "proved_names": sorted(certificates),
            "evidence": evidence,
        },
        "portfolio": {
            "solved": solved,
            "total": total,
            "score": solved / total,
        },
        "source_reports": [str(path) for path in args.reports],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(output["portfolio"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
