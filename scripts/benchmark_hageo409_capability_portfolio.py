"""Run exact, differentiable, and hybrid HAGeo search agents fairly.

The differentiable controller changes scheduling only.  Every admitted result
must contain a replayed native Yuclid certificate, and the exact agent is never
removed from the portfolio.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.benchmark_hageo409_auxiliary import run_problem
from worker.backend.capability_preserving_portfolio import (
    ProofAgentRun,
    summarize_capability_preserving_portfolio,
)


AGENTS = {
    "exact": "ar-residual-pareto",
    "formal_sheaf": "native-formal-sheaf",
    "formal_sheaf_preserving": "native-formal-sheaf-portfolio",
    "differentiable": "differentiable-consensus",
    "hybrid": "consensus-portfolio",
    "unified_formal_sheaf": "unified-formal-sheaf-portfolio",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--yuclid-exe", type=Path, required=True)
    parser.add_argument("--runtime-path", type=Path, required=True)
    parser.add_argument("--controller", type=Path, required=True)
    parser.add_argument("--problems", nargs="+", required=True)
    parser.add_argument(
        "--agents",
        nargs="+",
        choices=tuple(AGENTS),
        default=("exact", "formal_sheaf", "unified_formal_sheaf"),
        help=(
            "Independent agents to run with the full per-agent budget. "
            "Certificate union, rather than a shared half-beam, preserves capability."
        ),
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--max-depth", type=int, default=2)
    parser.add_argument("--branch-limit", type=int, default=32)
    parser.add_argument("--beam-width", type=int, default=12)
    parser.add_argument("--timeout-seconds", type=float, default=600.0)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--per-family-limit", type=int, default=1)
    parser.add_argument("--incidence-oversample-per-family", type=int, default=16)
    args = parser.parse_args()
    selected_agents = tuple(dict.fromkeys(args.agents))

    args.run_dir.mkdir(parents=True, exist_ok=True)
    jobs = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        for problem in sorted(set(args.problems)):
            for agent in selected_agents:
                beam_ranking = AGENTS[agent]
                output = (args.run_dir / f"{problem}-{agent}.json").resolve()
                future = executor.submit(
                    run_problem,
                    python=args.python.resolve(),
                    dataset=args.dataset.resolve(),
                    yuclid_exe=args.yuclid_exe.resolve(),
                    runtime_path=args.runtime_path.resolve(),
                    problem=problem,
                    output=output,
                    timeout_seconds=args.timeout_seconds,
                    max_depth=args.max_depth,
                    branch_limit=args.branch_limit,
                    beam_width=args.beam_width,
                    seed=args.seed,
                    beam_ranking=beam_ranking,
                    controller=(
                        args.controller.resolve()
                        if beam_ranking in {
                            "differentiable-consensus",
                            "consensus-portfolio",
                            "unified-formal-sheaf-portfolio",
                        }
                        else None
                    ),
                    per_family_limit=args.per_family_limit,
                    incidence_oversample_per_family=(
                        args.incidence_oversample_per_family
                    ),
                )
                jobs.append((future, problem, agent, beam_ranking))

        raw_runs = []
        proof_runs = []
        for future, problem, agent, beam_ranking in jobs:
            result = future.result()
            result.update({"agent": agent, "beam_ranking": beam_ranking})
            raw_runs.append(result)
            proof_runs.append(
                ProofAgentRun(
                    problem=problem,
                    agent=agent,
                    solved=bool(result.get("solved")),
                    native_confirmed=bool(result.get("native_confirmed")),
                    artifact=result.get("artifact"),
                    status=str(result.get("status", "execution_error")),
                )
            )
            print(json.dumps(result, ensure_ascii=False), flush=True)

    if "exact" not in selected_agents:
        raise ValueError("capability-preserving evaluation requires the exact agent")
    summary = summarize_capability_preserving_portfolio(
        args.problems,
        proof_runs,
        exact_agent="exact",
    )
    report = {
        "experiment": "hageo409_capability_preserving_agent_portfolio",
        "protocol": {
            "uses_external_llm": False,
            "agents": {name: AGENTS[name] for name in selected_agents},
            "differentiable_control_plane": (
                "heterogeneous formal-language stalks plus positive learned "
                "trusts and unrolled sheaf-consensus ADMM"
            ),
            "truth_plane": "native Yuclid certificate replay only",
            "acceptance": "union of replayed certificates; no voting",
            "capability_preservation": "exact agent always receives equal budget",
            "controller": args.controller.resolve().relative_to(ROOT).as_posix(),
            "controller_sha256": hashlib.sha256(
                args.controller.read_bytes()
            ).hexdigest(),
            "equal_agent_budget": {
                "max_depth": args.max_depth,
                "branch_limit": args.branch_limit,
                "beam_width": args.beam_width,
                "timeout_seconds": args.timeout_seconds,
                "seed": args.seed,
                "per_family_limit": args.per_family_limit,
                "incidence_oversample_per_family": (
                    args.incidence_oversample_per_family
                ),
            },
            "scope": (
                "search-policy agent portfolio; Wu/Groebner certificate exchange "
                "remains a separate exact agent path"
            ),
        },
        "summary": summary,
        "runs": sorted(raw_runs, key=lambda item: (item["problem"], item["agent"])),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
