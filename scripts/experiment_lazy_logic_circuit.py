"""Measure goal-directed proof compilation against exhaustive grounding.

The experiment uses the same label/value-agnostic Horn rules in every mode.
Only the compilation strategy changes.  All successful circuits must replay
their certificates through the original native agents.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.experiment_symbolic_sheaf_learning import Episode, build_split  # noqa: E402
from scripts.experiment_typed_logic_circuit import (  # noqa: E402
    build_reachability_episode,
    matched_negative_goal,
)
from worker.backend.typed_logic_circuit import (  # noqa: E402
    compile_goal_directed_proof_circuit,
    compile_typed_proof_circuit,
    schedule_circuit,
)


@dataclass
class Aggregate:
    episodes: int = 0
    exhaustive_solved: int = 0
    lazy_solved: int = 0
    lazy_negative_abstained: int = 0
    exhaustive_matches: int = 0
    lazy_matches: int = 0
    exhaustive_gates: int = 0
    lazy_gates: int = 0
    exhaustive_seconds: float = 0.0
    lazy_seconds: float = 0.0
    lazy_negative_seconds: float = 0.0
    lazy_states: int = 0
    lazy_backtracks: int = 0

    def add(self, record: dict[str, object]) -> None:
        self.episodes += 1
        self.exhaustive_solved += int(record["exhaustive_solved"])
        self.lazy_solved += int(record["lazy_solved"])
        self.lazy_negative_abstained += int(record["lazy_negative_abstained"])
        self.exhaustive_matches += int(record["exhaustive_matches"])
        self.lazy_matches += int(record["lazy_matches"])
        self.exhaustive_gates += int(record["exhaustive_gates"])
        self.lazy_gates += int(record["lazy_gates"])
        self.exhaustive_seconds += float(record["exhaustive_seconds"])
        self.lazy_seconds += float(record["lazy_seconds"])
        self.lazy_negative_seconds += float(record["lazy_negative_seconds"])
        self.lazy_states += int(record["lazy_states"])
        self.lazy_backtracks += int(record["lazy_backtracks"])

    def report(self) -> dict[str, float | int]:
        result = asdict(self)
        if self.episodes:
            result.update(
                {
                    "exhaustive_mean_matches": self.exhaustive_matches / self.episodes,
                    "lazy_mean_matches": self.lazy_matches / self.episodes,
                    "match_reduction_rate": (
                        1 - self.lazy_matches / self.exhaustive_matches
                        if self.exhaustive_matches
                        else 0.0
                    ),
                    "exhaustive_mean_gates": self.exhaustive_gates / self.episodes,
                    "lazy_mean_gates": self.lazy_gates / self.episodes,
                    "gate_reduction_rate": (
                        1 - self.lazy_gates / self.exhaustive_gates
                        if self.exhaustive_gates
                        else 0.0
                    ),
                    "exhaustive_mean_seconds": self.exhaustive_seconds / self.episodes,
                    "lazy_mean_seconds": self.lazy_seconds / self.episodes,
                    "lazy_negative_mean_seconds": self.lazy_negative_seconds / self.episodes,
                }
            )
        return result


def evaluate_episode(episode: Episode) -> dict[str, object]:
    started = time.perf_counter()
    exhaustive = compile_typed_proof_circuit(
        episode.givens,
        episode.goal,
        episode.agents,
        max_rounds=12,
    )
    exhaustive_seconds = time.perf_counter() - started
    proof_budget = max(1, len(exhaustive.proof_slice()))
    exhaustive_result = schedule_circuit(
        exhaustive,
        episode.vocabulary,
        episode.agents,
        mode="circuit",
        budget_per_round=1,
        max_rounds=proof_budget,
    )

    started = time.perf_counter()
    lazy = compile_goal_directed_proof_circuit(
        episode.givens,
        episode.goal,
        episode.agents,
        max_rule_applications=proof_budget,
        max_search_states=20_000,
    )
    lazy_seconds = time.perf_counter() - started
    lazy_result = schedule_circuit(
        lazy,
        episode.vocabulary,
        episode.agents,
        mode="circuit",
        budget_per_round=1,
        max_rounds=proof_budget,
    )

    negative_goal = matched_negative_goal(episode, exhaustive)
    negative_seconds = 0.0
    negative_abstained = True
    negative_matches = 0
    negative_states = 0
    if negative_goal is not None:
        started = time.perf_counter()
        lazy_negative = compile_goal_directed_proof_circuit(
            episode.givens,
            negative_goal,
            episode.agents,
            max_rule_applications=proof_budget,
            max_search_states=20_000,
        )
        negative_seconds = time.perf_counter() - started
        negative_matches = lazy_negative.compile_matches
        negative_states = lazy_negative.search_states
        negative_result = schedule_circuit(
            lazy_negative,
            episode.vocabulary,
            episode.agents,
            mode="circuit",
            budget_per_round=1,
            max_rounds=proof_budget,
        )
        negative_abstained = not negative_result.solved and not negative_result.replayed

    return {
        "id": episode.episode_id,
        "domain": episode.domain,
        "proof_budget": proof_budget,
        "exhaustive_solved": exhaustive_result.replayed,
        "lazy_solved": lazy_result.replayed,
        "lazy_negative_abstained": negative_abstained,
        "exhaustive_matches": exhaustive.compile_matches,
        "lazy_matches": lazy.compile_matches,
        "lazy_negative_matches": negative_matches,
        "exhaustive_gates": len(exhaustive.gates),
        "lazy_gates": len(lazy.gates),
        "exhaustive_seconds": exhaustive_seconds,
        "lazy_seconds": lazy_seconds,
        "lazy_negative_seconds": negative_seconds,
        "lazy_states": lazy.search_states,
        "lazy_negative_states": negative_states,
        "lazy_backtracks": lazy.backtracks,
    }


def summarize(records: list[dict[str, object]]) -> dict[str, object]:
    overall = Aggregate()
    domains: dict[str, Aggregate] = {}
    for record in records:
        overall.add(record)
        domains.setdefault(str(record["domain"]), Aggregate()).add(record)
    ratios = [
        float(record["lazy_matches"]) / float(record["exhaustive_matches"])
        for record in records
        if int(record["exhaustive_matches"]) > 0
    ]
    return {
        "overall": overall.report(),
        "by_domain": {
            name: aggregate.report()
            for name, aggregate in sorted(domains.items())
        },
        "median_per_episode_match_ratio": statistics.median(ratios) if ratios else 0.0,
        "maximum_per_episode_match_ratio": max(ratios) if ratios else 0.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes-per-domain", type=int, default=100)
    parser.add_argument("--reachability-episodes", type=int, default=100)
    parser.add_argument("--distractors", type=int, default=12)
    parser.add_argument("--seed-start", type=int, default=110_000)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "lazy-logic-circuit-heldout-2026-08-17.json",
    )
    args = parser.parse_args()

    episodes = build_split(
        args.seed_start,
        args.episodes_per_domain,
        args.distractors,
    )
    episodes.extend(
        build_reachability_episode(
            args.seed_start + 100_000 + index,
            args.distractors,
        )
        for index in range(args.reachability_episodes)
    )
    records = []
    for index, episode in enumerate(episodes, start=1):
        record = evaluate_episode(episode)
        records.append(record)
        if index % 50 == 0:
            print(f"[{index}/{len(episodes)}]", flush=True)

    report = {
        "experiment": "goal-directed-lazy-typed-logic-circuit",
        "protocol": {
            "training": "none",
            "uses_llm": False,
            "uses_problem_id_or_reference_answer": False,
            "positive_episodes": len(records),
            "matched_negative_episodes": len(records),
            "same_rules_and_native_verifiers": True,
            "only_changed_variable": "proof-circuit compilation strategy",
        },
        "summary": summarize(records),
        "records": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
