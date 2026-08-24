"""Audit complete proof traces for every solved item in a native HAGeo run."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from worker.backend.yuclid_proof_trace import load_proof_trace, render_markdown  # noqa: E402


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def audit_one(
    problem_name: str,
    result: dict[str, Any],
    *,
    output_dir: Path,
) -> tuple[str, dict[str, Any]]:
    proof_path = ROOT / str(result["proof_path"])
    nodes = load_proof_trace(proof_path)
    unlinked = sum(
        producer is None
        for node in nodes
        for producer in node.assumption_producers
    )
    ambiguous = sum(
        mode == "equation_points_fallback_ambiguous"
        for node in nodes
        for mode in node.assumption_link_modes
    )
    numerical_guards = sum(node.channel == "numerical_guard" for node in nodes)
    cross_chart = [node.index for node in nodes if node.is_cross_chart_bridge]
    terminal = list(nodes[-1].assertions) if nodes else []
    trace_ok = bool(nodes and unlinked == 0 and ambiguous == 0 and terminal)
    payload = {
        "experiment": "yuclid_complete_proof_trace",
        "problem_name": problem_name,
        "proof_path": proof_path.relative_to(ROOT).as_posix(),
        "trace_integrity_passed": trace_ok,
        "deduction_count": len(nodes),
        "terminal_assertions": terminal,
        "all_assumptions_linked": unlinked == 0,
        "unlinked_assumption_count": unlinked,
        "ambiguous_equation_link_count": ambiguous,
        "numerical_guard_count": numerical_guards,
        "cross_chart_bridge_nodes": cross_chart,
        "nodes": [node.to_dict() for node in nodes],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / f"{problem_name}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / f"{problem_name}.md").write_text(
        render_markdown(problem_name, proof_path.relative_to(ROOT).as_posix(), nodes),
        encoding="utf-8",
    )
    return problem_name, {
        key: value for key, value in payload.items() if key != "nodes"
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()

    report = _load(args.report.resolve())
    solved = {
        name: result
        for name, result in report.get("results", {}).items()
        if result.get("status") == "solved"
    }
    output_dir = args.output_dir.resolve()
    rows: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {
            executor.submit(
                audit_one,
                name,
                result,
                output_dir=output_dir,
            ): name
            for name, result in solved.items()
        }
        for future in as_completed(futures):
            name, row = future.result()
            rows[name] = row
            print(
                json.dumps(
                    {
                        "problem": name,
                        "trace_integrity_passed": row["trace_integrity_passed"],
                    }
                ),
                flush=True,
            )

    passed = sum(row["trace_integrity_passed"] is True for row in rows.values())
    manifest = {
        "experiment": "hageo_native_complete_proof_trace_audit",
        "protocol": {
            "uses_external_llm": False,
            "acceptance": (
                "the complete proof trace must be nonempty, every assumption must "
                "have a producer, and no ambiguous equation fallback may remain"
            ),
        },
        "summary": {
            "claimed_solved": len(solved),
            "trace_integrity_passed": passed,
            "trace_integrity_failed": len(solved) - passed,
            "all_passed": passed == len(solved),
            "total_deductions": sum(row["deduction_count"] for row in rows.values()),
            "total_numerical_guards": sum(
                row["numerical_guard_count"] for row in rows.values()
            ),
            "total_cross_chart_bridges": sum(
                len(row["cross_chart_bridge_nodes"]) for row in rows.values()
            ),
        },
        "results": dict(sorted(rows.items())),
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest["summary"], ensure_ascii=False), flush=True)
    return 0 if manifest["summary"]["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
