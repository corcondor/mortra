"""Run MORTRA's exact geometry chart registry and persist every proof view."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from worker.backend.exact_geometry_chart_portfolio import (  # noqa: E402
    certify_jgex_with_exact_chart_portfolio,
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _display(path: Path) -> str:
    resolved = path.resolve()
    return (
        resolved.relative_to(ROOT).as_posix()
        if resolved.is_relative_to(ROOT)
        else resolved.as_posix()
    )


def _run_one(*, input_path: Path, output_dir: Path, name: str) -> None:
    source = input_path.read_text(encoding="utf-8").strip()
    result = certify_jgex_with_exact_chart_portfolio(source, include_diagram=True)
    result_payload = result.to_dict()
    selected = result.selected
    portfolio_path = output_dir / f"{name}.chart-portfolio.json"

    _write(
        portfolio_path,
        json.dumps(result_payload, ensure_ascii=False, indent=2) + "\n",
    )
    if selected is not None:
        _write(output_dir / f"{name}.proof.md", selected.proof_markdown)
        if selected.diagram_svg is not None:
            _write(output_dir / f"{name}.proof-focus.svg", selected.diagram_svg)
    artifact = {
        "experiment": "mortra_exact_geometry_chart_application",
        "protocol": {
            "uses_external_llm": False,
            "uses_expected_answer": False,
            "uses_problem_id_in_solver": False,
            "truth_plane": "replayed structural exact-chart certificate",
        },
        "problem_name": name,
        "solved": result.solved,
        "certificate": (
            {
                "source": "jgex_exact_chart",
                "proof_path": _display(portfolio_path),
                "proof_file_sha256": _sha256(portfolio_path),
                "proof_sha256": selected.chart_certificate_sha256,
                "input_sha256": result.source_sha256,
            }
            if selected is not None and result.solved
            else None
        ),
    }
    _write(
        output_dir / f"{name}.artifact.json",
        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--input", type=Path)
    inputs.add_argument("--input-dir", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--problem-name")
    args = parser.parse_args()

    if args.input is not None:
        _run_one(
            input_path=args.input,
            output_dir=args.output_dir,
            name=args.problem_name or args.input.stem,
        )
        return 0

    if args.problem_name is not None:
        parser.error("--problem-name is only valid with --input")
    for input_path in sorted(args.input_dir.glob("*.txt")):
        _run_one(
            input_path=input_path,
            output_dir=args.output_dir,
            name=input_path.stem,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
