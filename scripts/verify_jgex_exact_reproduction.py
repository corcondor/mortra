"""Verify semantic equality of two exact-certificate portfolio reports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _certificate_hashes(report: dict) -> dict[str, tuple[str, ...]]:
    evidence = report["exact_backend"]["evidence"]
    return {
        problem: tuple(
            sorted({item["certificate_sha256"] for item in records})
        )
        for problem, records in evidence.items()
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected", type=Path, required=True)
    parser.add_argument("--actual", type=Path, required=True)
    args = parser.parse_args()

    expected = json.loads(args.expected.read_text(encoding="utf-8"))
    actual = json.loads(args.actual.read_text(encoding="utf-8"))
    checks = {
        "portfolio": actual["portfolio"] == expected["portfolio"],
        "proved_names": (
            actual["exact_backend"]["proved_names"]
            == expected["exact_backend"]["proved_names"]
        ),
        "certificate_hashes": (
            _certificate_hashes(actual) == _certificate_hashes(expected)
        ),
        "acceptance_rule": (
            actual["acceptance_rule"] == expected["acceptance_rule"]
        ),
    }
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    if not all(checks.values()):
        return 1
    print("JGEX exact portfolio reproduction verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
