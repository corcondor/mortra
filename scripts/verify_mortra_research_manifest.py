"""Verify the published MORTRA research artifacts against their manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    root = args.manifest.resolve().parents[1]
    artifact_checks = {
        relative: (root / relative).is_file()
        and sha256(root / relative) == expected
        for relative, expected in manifest["reference_artifacts"].items()
    }

    portfolio_path = root / "data" / "jgex-exact-portfolio-expanded19-2026-08-16.json"
    portfolio = json.loads(portfolio_path.read_text(encoding="utf-8"))
    yuclid_path = root / "data" / "yuclid-imo-ag-30-all-ar-2026-08-15.json"
    yuclid = json.loads(yuclid_path.read_text(encoding="utf-8"))

    expected = manifest["semantic_acceptance"]
    evidence = portfolio["exact_backend"]["evidence"]
    actual_certificate_hashes = {
        problem: records[0]["certificate_sha256"]
        for problem, records in evidence.items()
    }
    original_score = yuclid["scores"]["original_imo_ag_30"]
    semantic_checks = {
        "manifest_declares_no_llm": manifest["uses_llm"] is False,
        "yuclid_declares_no_llm": yuclid["protocol"]["uses_external_llm"] is False,
        "yuclid_baseline_is_17_of_30": (
            original_score["solved"] == 17 and original_score["total"] == 30
        ),
        "portfolio_is_20_of_30": (
            f'{portfolio["portfolio"]["solved"]}/{portfolio["portfolio"]["total"]}'
            == expected["portfolio"]
        ),
        "proved_names_match": (
            portfolio["exact_backend"]["proved_names"] == expected["proved_names"]
        ),
        "certificate_hashes_match": (
            actual_certificate_hashes == expected["certificate_sha256"]
        ),
        "acceptance_rule_is_exact": (
            portfolio["acceptance_rule"] == "exact_replay=true and remainder=0"
        ),
    }
    report = {
        "artifact_hashes": artifact_checks,
        "semantic_acceptance": semantic_checks,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not all((*artifact_checks.values(), *semantic_checks.values())):
        return 1
    print("MORTRA research manifest verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
