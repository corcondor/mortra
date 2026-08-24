"""Isolated CLI for MORTRA's replayable Wolfram JGEX specialist."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from worker.backend.wolfram_polynomial_certificate import (  # noqa: E402
    certify_jgex_with_wolfram,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--wolfram-exe", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=600)
    parser.add_argument(
        "--preprocessing",
        choices=(
            "relational",
            "explicit",
            "local_relational",
            "goal_local_relational",
        ),
        default="relational",
    )
    parser.add_argument(
        "--reduction-mode",
        choices=("direct", "extended_groebner"),
        default="direct",
    )
    parser.add_argument(
        "--saturation-mode",
        choices=("none", "single", "cumulative"),
        default="single",
    )
    parser.add_argument("--max-saturation-factors", type=int, default=64)
    parser.add_argument("--local-max-output-terms", type=int, default=64)
    args = parser.parse_args()

    source = args.input.read_text(encoding="utf-8").strip()
    certificate = certify_jgex_with_wolfram(
        source,
        executable=args.wolfram_exe,
        timeout_seconds=args.timeout_seconds,
        preprocessing=args.preprocessing,
        reduction_mode=args.reduction_mode,
        saturation_mode=args.saturation_mode,
        max_saturation_factors=args.max_saturation_factors,
        local_max_output_terms=args.local_max_output_terms,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(asdict(certificate), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0 if certificate.status == "proved" else 2


if __name__ == "__main__":
    raise SystemExit(main())
