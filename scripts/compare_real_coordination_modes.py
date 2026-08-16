"""Equal-dispatch comparison for real external symbolic geometry agents."""

from __future__ import annotations

import argparse
import json
import random
from datetime import UTC, datetime
from pathlib import Path


AGENTS_PER_STRICT_BUNDLE = 3  # GCLC/Wu, GCLC/Groebner, exact replay.


def _strict_success(result: dict) -> bool:
    return bool(result.get("strict_exchange_proved"))


def _trial(
    names: list[str],
    eligible: set[str],
    strict_successes: set[str],
    bundles: int,
    seed: int,
    *,
    typed_filter: bool,
) -> int:
    order = list(names)
    random.Random(seed).shuffle(order)
    if typed_filter:
        order = [name for name in order if name in eligible]
    attempted = order[:bundles]
    return sum(name in strict_successes for name in attempted)


def _distribution(values: list[int]) -> dict:
    ordered = sorted(values)
    count = len(ordered)
    return {
        "trials": count,
        "mean_additional_strict_proofs": sum(ordered) / count,
        "success_probability": sum(value > 0 for value in ordered) / count,
        "p025": ordered[int(0.025 * (count - 1))],
        "median": ordered[int(0.5 * (count - 1))],
        "p975": ordered[int(0.975 * (count - 1))],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--agent-call-budget", type=int, default=18)
    parser.add_argument("--trials", type=int, default=10000)
    args = parser.parse_args()

    report = json.loads(args.input.read_text(encoding="utf-8"))
    results = report["results"]
    names = list(results)
    eligible = {name for name, result in results.items() if "translation" in result}
    strict_successes = {
        name for name, result in results.items() if _strict_success(result)
    }
    bundles = args.agent_call_budget // AGENTS_PER_STRICT_BUNDLE
    if bundles < 1:
        raise ValueError("agent-call budget must fund at least one strict bundle")

    blackboard = [
        _trial(
            names,
            eligible,
            strict_successes,
            bundles,
            seed,
            typed_filter=False,
        )
        for seed in range(args.trials)
    ]
    local_sheaf = [
        _trial(
            names,
            eligible,
            strict_successes,
            bundles,
            seed,
            typed_filter=True,
        )
        for seed in range(args.trials)
    ]

    full_blackboard_calls = len(names) * AGENTS_PER_STRICT_BUNDLE
    full_local_calls = len(eligible) * AGENTS_PER_STRICT_BUNDLE
    baseline_solved = int(report["summary"]["baseline_solved"])
    result = {
        "experiment": "real-symbolic-coordination-equal-dispatch-control",
        "generated_at": datetime.now(UTC).isoformat(),
        "uses_llm": False,
        "uses_problem_specific_solver_logic": False,
        "input": str(args.input),
        "protocol": {
            "task_count": len(names),
            "typed_eligible_task_count": len(eligible),
            "strict_success_names": sorted(strict_successes),
            "agents_per_strict_bundle": AGENTS_PER_STRICT_BUNDLE,
            "agent_call_budget": args.agent_call_budget,
            "task_bundles": bundles,
            "random_order_trials": args.trials,
            "scheduler_cannot_observe_solver_outcomes": True,
        },
        "equal_budget": {
            "global_blackboard": _distribution(blackboard),
            "typed_local_sheaf": _distribution(local_sheaf),
            "baseline_solved": baseline_solved,
            "global_expected_score": (
                baseline_solved + sum(blackboard) / len(blackboard)
            )
            / 30,
            "typed_local_expected_score": (
                baseline_solved + sum(local_sheaf) / len(local_sheaf)
            )
            / 30,
        },
        "full_coverage": {
            "global_blackboard_agent_calls": full_blackboard_calls,
            "typed_local_sheaf_agent_calls": full_local_calls,
            "agent_call_reduction": full_blackboard_calls - full_local_calls,
            "agent_call_reduction_rate": 1 - full_local_calls / full_blackboard_calls,
            "same_strict_proofs": sorted(strict_successes),
        },
        "claim_scope": (
            "This control tests typed local routing with measured real solver outcomes. "
            "It does not claim learned decentralized consensus or end-to-end gradients."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result["equal_budget"], ensure_ascii=False, indent=2))
    print(json.dumps(result["full_coverage"], ensure_ascii=False, indent=2))
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
