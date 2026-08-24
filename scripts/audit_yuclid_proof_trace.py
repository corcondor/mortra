"""Export a complete, term-preserving trace from a Yuclid proof certificate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from worker.backend.yuclid_proof_trace import load_proof_trace, render_markdown  # noqa: E402


def _display(path: Path) -> str:
    resolved = path.resolve()
    return (
        resolved.relative_to(ROOT).as_posix()
        if resolved.is_relative_to(ROOT)
        else resolved.as_posix()
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--problem-name", required=True)
    parser.add_argument("--proof", type=Path, required=True)
    parser.add_argument("--json-output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, required=True)
    args = parser.parse_args()

    proof_path = args.proof.resolve()
    proof_display = _display(proof_path)
    nodes = load_proof_trace(proof_path)
    payload = {
        "experiment": "yuclid_complete_proof_trace",
        "problem_name": args.problem_name,
        "proof_path": proof_display,
        "deduction_count": len(nodes),
        "terminal_assertions": list(nodes[-1].assertions) if nodes else [],
        "all_assumptions_linked": all(
            producer is not None
            for node in nodes
            for producer in node.assumption_producers
        ),
        "unlinked_assumption_count": sum(
            producer is None
            for node in nodes
            for producer in node.assumption_producers
        ),
        "ambiguous_equation_link_count": sum(
            mode == "equation_points_fallback_ambiguous"
            for node in nodes
            for mode in node.assumption_link_modes
        ),
        "cross_chart_bridge_nodes": [
            node.index for node in nodes if node.is_cross_chart_bridge
        ],
        "nodes": [node.to_dict() for node in nodes],
    }
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    args.markdown_output.write_text(
        render_markdown(args.problem_name, proof_display, nodes), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "problem": args.problem_name,
                "deductions": len(nodes),
                "terminal": payload["terminal_assertions"],
                "unlinked_assumptions": payload["unlinked_assumption_count"],
                "ambiguous_equation_links": payload["ambiguous_equation_link_count"],
                "cross_chart_bridges": payload["cross_chart_bridge_nodes"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
