"""Controlled LLM-free coordination experiment inspired by Sheaf-ADMM.

The benchmark is intentionally a mechanism test, not a claim about IMO score.
It uses fresh entity labels/numbers in every episode, trains only structural
restriction weights on replayed proof DAGs, freezes them, and then evaluates a
held-out split under an equal certificate-transfer budget.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from worker.backend.geometry_proof_hypergraph import Atom, Theorem  # noqa: E402
from worker.backend.symbolic_sheaf_coordination import (  # noqa: E402
    AgentProposal,
    ExactSheafCoordinator,
    LocalCertificate,
    PredicateSignature,
    RuleClosureAdapter,
    TypedVocabulary,
)
from worker.backend.symbolic_sheaf_learning import (  # noqa: E402
    BudgetedSheafCoordinator,
    ProofFlowLearner,
)


def atom(name: str, *arguments: str) -> Atom:
    return Atom(name, tuple(arguments))


@dataclass(frozen=True)
class Episode:
    episode_id: str
    domain: str
    vocabulary: TypedVocabulary
    agents: tuple[RuleClosureAdapter, ...]
    givens: tuple[Atom, ...]
    goal: Atom


def _geometry_episode(seed: int, distractors: int) -> Episode:
    rng = random.Random(seed)
    # Lines are first-class typed objects here.  This removes endpoint naming
    # from the coordination experiment while the geometry kernel separately
    # tests the point-pair symmetry orbit.
    transport_rules = (
        Theorem(
            "perpendicular-transport",
            (atom("g_perp", "?A", "?C"), atom("g_para", "?C", "?E")),
            atom("g_perp", "?A", "?E"),
        ),
        Theorem(
            "parallel-transitivity",
            (atom("g_para", "?A", "?C"), atom("g_para", "?C", "?E")),
            atom("g_para", "?A", "?E"),
        ),
    )
    incidence_rules = (
        Theorem(
            "common-perpendicular",
            (
                atom("g_perp", "?A", "?E"),
                atom("g_perp", "?G", "?E"),
                atom("distinct", "?A", "?G"),
            ),
            atom("g_para", "?A", "?G"),
        ),
        Theorem(
            "parallel-symmetry",
            (atom("g_para", "?A", "?G"),),
            atom("g_parallel_view", "?G", "?A"),
        ),
    )
    transport = RuleClosureAdapter(
        "transport",
        transport_rules,
        imports={"g_perp", "g_para"},
        exports={"g_perp", "g_para"},
    )
    incidence = RuleClosureAdapter(
        "incidence",
        incidence_rules,
        imports={"g_perp", "g_para", "distinct"},
        exports={"g_para", "g_parallel_view"},
    )
    labels = [f"L{seed}_{index}" for index in range(4 * (distractors + 1))]
    rng.shuffle(labels)

    def block(offset: int) -> tuple[str, ...]:
        return tuple(labels[offset:offset + 4])

    a, c, e, g = block(0)
    givens = [
        atom("g_perp", a, c),
        atom("g_para", c, e),
        atom("g_perp", g, e),
        atom("distinct", a, g),
    ]
    for index in range(1, distractors + 1):
        q = block(index * 4)
        givens.extend((
            atom("g_perp", q[0], q[1]),
            atom("g_para", q[1], q[2]),
            atom("g_perp", q[3], q[2]),
            atom("g_para", q[0], q[1]),
            atom("distinct", q[0], q[3]),
        ))
    vocabulary = TypedVocabulary(
        signatures={
            "g_perp": PredicateSignature("g_perp", ("Line", "Line")),
            "g_para": PredicateSignature("g_para", ("Line", "Line")),
            "g_parallel_view": PredicateSignature("g_parallel_view", ("Line", "Line")),
            "distinct": PredicateSignature("distinct", ("Line", "Line")),
        },
        entity_sorts={label: "Line" for label in labels},
    )
    return Episode(
        f"geometry-{seed}",
        "geometry",
        vocabulary,
        (transport, incidence),
        tuple(givens),
        atom("g_para", a, g),
    )


def _integer_episode(seed: int, distractors: int) -> Episode:
    rng = random.Random(seed)
    projection_rules = (
        Theorem("gcd-left", (atom("gcd", "?A", "?B", "?D"),), atom("divides", "?D", "?A")),
        Theorem("gcd-right", (atom("gcd", "?A", "?B", "?D"),), atom("divides", "?D", "?B")),
        Theorem(
            "factor-product",
            (atom("divides", "?D", "?A"), atom("product", "?A", "?B", "?P")),
            atom("divides", "?D", "?P"),
        ),
    )
    closure_rules = (
        Theorem(
            "divisor-sum",
            (
                atom("divides", "?D", "?A"),
                atom("divides", "?D", "?B"),
                atom("sum", "?A", "?B", "?S"),
            ),
            atom("divides", "?D", "?S"),
        ),
        Theorem(
            "divisor-difference",
            (
                atom("divides", "?D", "?A"),
                atom("divides", "?D", "?B"),
                atom("difference", "?A", "?B", "?S"),
            ),
            atom("divides", "?D", "?S"),
        ),
    )
    projection = RuleClosureAdapter(
        "projection",
        projection_rules,
        imports={"gcd", "divides", "product"},
        exports={"divides"},
    )
    closure = RuleClosureAdapter(
        "closure",
        closure_rules,
        imports={"divides", "sum", "difference"},
        exports={"divides"},
    )
    givens: list[Atom] = []
    values: set[str] = set()

    def add_case(multiplier: int) -> tuple[str, str, str, str]:
        divisor = rng.randint(2, 13)
        left = divisor * rng.randint(2, 19) * multiplier
        right = divisor * rng.randint(2, 19) * multiplier
        total = left + right
        values.update(map(str, (divisor, left, right, total)))
        givens.extend((atom("gcd", str(left), str(right), str(divisor)), atom("sum", str(left), str(right), str(total))))
        return str(divisor), str(left), str(right), str(total)

    target = add_case(1)
    for index in range(distractors):
        divisor, left, right, _total = add_case(index + 2)
        product = int(left) * int(right)
        difference = abs(int(left) - int(right))
        values.update(map(str, (product, difference)))
        givens.extend((
            atom("product", left, right, str(product)),
            atom("difference", max(left, right, key=int), min(left, right, key=int), str(difference)),
        ))
    vocabulary = TypedVocabulary(
        signatures={
            name: PredicateSignature(name, ("Natural",) * arity)
            for name, arity in {
                "gcd": 3,
                "divides": 2,
                "sum": 3,
                "product": 3,
                "difference": 3,
            }.items()
        },
        entity_sorts={value: "Natural" for value in values},
    )
    return Episode(
        f"integer-{seed}",
        "integer",
        vocabulary,
        (projection, closure),
        tuple(givens),
        atom("divides", target[0], target[3]),
    )


def _set_episode(seed: int, distractors: int) -> Episode:
    rng = random.Random(seed)
    order = RuleClosureAdapter(
        "order",
        [
            Theorem(
                "subset-span",
                (atom("subset", "?A", "?B"), atom("subset", "?B", "?C")),
                atom("subset_span", "?A", "?C"),
            ),
            Theorem(
                "span-extension",
                (atom("subset_span", "?A", "?B"), atom("subset", "?B", "?C")),
                atom("subset_span", "?A", "?C"),
            ),
        ],
        imports={"subset", "subset_span"},
        exports={"subset_span"},
    )
    restriction = RuleClosureAdapter(
        "restriction",
        [
            Theorem(
                "disjoint-restriction",
                (atom("subset_span", "?A", "?C"), atom("disjoint", "?C", "?D")),
                atom("disjoint", "?A", "?D"),
            ),
            Theorem(
                "empty-intersection",
                (atom("disjoint", "?A", "?B"),),
                atom("empty_intersection", "?A", "?B"),
            ),
        ],
        imports={"subset_span", "disjoint"},
        exports={"disjoint", "empty_intersection"},
    )
    labels = [f"S{seed}_{index}" for index in range(4 * (distractors + 1))]
    rng.shuffle(labels)
    givens: list[Atom] = []

    def add_case(offset: int) -> tuple[str, str, str, str]:
        a, b, c, d = labels[offset:offset + 4]
        givens.extend((atom("subset", a, b), atom("subset", b, c), atom("disjoint", c, d)))
        return a, b, c, d

    target = add_case(0)
    for index in range(1, distractors + 1):
        add_case(index * 4)
    vocabulary = TypedVocabulary(
        signatures={
            "subset": PredicateSignature("subset", ("Set", "Set")),
            "subset_span": PredicateSignature("subset_span", ("Set", "Set")),
            "disjoint": PredicateSignature("disjoint", ("Set", "Set")),
            "empty_intersection": PredicateSignature("empty_intersection", ("Set", "Set")),
        },
        entity_sorts={label: "Set" for label in labels},
    )
    return Episode(
        f"set-{seed}",
        "set",
        vocabulary,
        (order, restriction),
        tuple(givens),
        atom("disjoint", target[0], target[3]),
    )


GENERATORS: tuple[Callable[[int, int], Episode], ...] = (
    _geometry_episode,
    _integer_episode,
    _set_episode,
)


class InvalidAgent:
    agent_id = "invalid"

    def __init__(self, predicates: Sequence[str]) -> None:
        self.imports = frozenset(predicates)
        self.exports = frozenset(predicates)

    def propose(self, facts, goal, *, round_index):
        return AgentProposal((LocalCertificate(
            self.agent_id,
            "unsupported-goal",
            goal,
            (),
            {"round": round_index},
        ),))

    def verify(self, certificate, facts):
        return False


def build_split(start_seed: int, episodes_per_domain: int, distractors: int) -> list[Episode]:
    episodes: list[Episode] = []
    for domain_index, generator in enumerate(GENERATORS):
        for offset in range(episodes_per_domain):
            episodes.append(generator(start_seed + domain_index * 100_000 + offset, distractors))
    return episodes


def fit_learner(episodes: Sequence[Episode]) -> ProofFlowLearner:
    learner = ProofFlowLearner()
    for episode in episodes:
        result = ExactSheafCoordinator(episode.vocabulary, episode.agents).solve(
            episode.givens,
            episode.goal,
            stop_on_goal=False,
        )
        learner.fit_episode(result, episode.agents)
    return learner


def evaluate(
    episodes: Sequence[Episode],
    *,
    learner: ProofFlowLearner,
    budget: int,
    include_fault_agent: bool = False,
    include_records: bool = False,
) -> dict[str, object]:
    variants = (
        "independent",
        "strict",
        "blackboard",
        "learned_global_blackboard",
        "sheaf_static",
        "sheaf_learned",
    )
    counts = {name: 0 for name in variants}
    replayed = {name: 0 for name in variants}
    proposed = {name: 0 for name in variants}
    transmitted = {name: 0 for name in variants}
    peer_messages = {name: 0 for name in variants}
    by_domain = {
        domain: {name: 0 for name in variants}
        for domain in ("geometry", "integer", "set")
    }
    false_accepts = 0
    rejected_invalid = 0
    episode_records: list[dict[str, object]] = []

    for episode in episodes:
        episode_record: dict[str, object] = {
            "episode_id": episode.episode_id,
            "domain": episode.domain,
            "variants": {},
        }
        variant_records: dict[str, dict[str, object]] = episode_record["variants"]  # type: ignore[assignment]
        independent_results = [
            ExactSheafCoordinator(episode.vocabulary, [agent]).solve(episode.givens, episode.goal)
            for agent in episode.agents
        ]
        independent_solved = any(item.solved and item.replayed for item in independent_results)
        counts["independent"] += int(independent_solved)
        replayed["independent"] += int(independent_solved)
        by_domain[episode.domain]["independent"] += int(independent_solved)
        variant_records["independent"] = {
            "solved": independent_solved,
            "replayed": independent_solved,
            "communication": 0,
        }

        strict = ExactSheafCoordinator(episode.vocabulary, episode.agents).solve(
            episode.givens,
            episode.goal,
            stop_on_goal=False,
        )
        strict_ok = strict.solved and strict.replayed
        counts["strict"] += int(strict_ok)
        replayed["strict"] += int(strict.replayed)
        proposed["strict"] += sum(item.proposed for item in strict.rounds)
        transmitted["strict"] += sum(item.proposed for item in strict.rounds)
        by_domain[episode.domain]["strict"] += int(strict_ok)
        strict_communication = sum(item.proposed for item in strict.rounds)
        variant_records["strict"] = {
            "solved": strict_ok,
            "replayed": strict.replayed,
            "communication": strict_communication,
        }

        for name, use_sheaf, policy, local_views in (
            ("blackboard", False, None, False),
            ("learned_global_blackboard", False, learner, False),
            ("sheaf_static", True, None, True),
            ("sheaf_learned", True, learner, True),
        ):
            agents: tuple = episode.agents
            if include_fault_agent and name == "sheaf_learned":
                agents = (InvalidAgent(tuple(episode.vocabulary.signatures)), *agents)
            result = BudgetedSheafCoordinator(
                episode.vocabulary,
                agents,
                learner=policy,
                use_sheaf=use_sheaf,
                local_views=local_views,
            ).solve(episode.givens, episode.goal, transfer_budget=budget, max_rounds=10)
            ok = result.solved and result.replayed
            counts[name] += int(ok)
            replayed[name] += int(result.replayed)
            proposed[name] += result.proposed_total
            transmitted[name] += result.transmitted_total + result.peer_messages_total
            peer_messages[name] += result.peer_messages_total
            by_domain[episode.domain][name] += int(ok)
            if name == "sheaf_learned" and include_fault_agent:
                false_accepts += int(result.solved and not result.replayed)
                rejected_invalid += sum(item.agent_id == "invalid" for item in result.rejected)
            variant_records[name] = {
                "solved": ok,
                "replayed": result.replayed,
                "communication": result.transmitted_total + result.peer_messages_total,
                "selected_certificates": result.transmitted_total,
                "peer_messages": result.peer_messages_total,
            }
        episode_records.append(episode_record)

    total = len(episodes)
    paired_differences = [
        int(record["variants"]["sheaf_learned"]["communication"])  # type: ignore[index]
        - int(record["variants"]["learned_global_blackboard"]["communication"])  # type: ignore[index]
        for record in episode_records
    ]
    bootstrap_rng = random.Random(20260815)
    bootstrap_means = sorted(
        statistics.fmean(
            paired_differences[bootstrap_rng.randrange(len(paired_differences))]
            for _ in paired_differences
        )
        for _ in range(2000)
    ) if paired_differences else [0.0]
    lower_index = int(0.025 * (len(bootstrap_means) - 1))
    upper_index = int(0.975 * (len(bootstrap_means) - 1))
    return {
        "episodes": total,
        "budget_per_round": budget,
        "solved": counts,
        "solve_rate": {name: counts[name] / total for name in variants},
        "replayed": replayed,
        "proposed": proposed,
        "transmitted": transmitted,
        "peer_messages": peer_messages,
        "communication_reduction_vs_strict": {
            name: (
                1.0 - transmitted[name] / transmitted["strict"]
                if transmitted["strict"] else 0.0
            )
            for name in ("blackboard", "learned_global_blackboard", "sheaf_static", "sheaf_learned")
        },
        "by_domain": by_domain,
        "fault_control": {
            "enabled": include_fault_agent,
            "false_accepts": false_accepts,
            "invalid_certificates_rejected": rejected_invalid,
        },
        "paired_sheaf_vs_global_blackboard": {
            "metric": "communication messages; negative favors sheaf",
            "mean_difference": statistics.fmean(paired_differences) if paired_differences else 0.0,
            "median_difference": statistics.median(paired_differences) if paired_differences else 0.0,
            "sheaf_wins": sum(item < 0 for item in paired_differences),
            "ties": sum(item == 0 for item in paired_differences),
            "global_blackboard_wins": sum(item > 0 for item in paired_differences),
            "bootstrap_95pct_mean_ci": [bootstrap_means[lower_index], bootstrap_means[upper_index]],
            "bootstrap_samples": 2000,
        },
        **({"episode_records": episode_records} if include_records else {}),
    }


def choose_budget(dev: Sequence[Episode], learner: ProofFlowLearner) -> tuple[int, list[dict[str, object]]]:
    trials: list[dict[str, object]] = []
    for budget in (1, 2, 3, 4, 6):
        result = evaluate(dev, learner=learner, budget=budget)
        trials.append(result)
    best_solved = max(int(item["solved"]["sheaf_learned"]) for item in trials)  # type: ignore[index]
    eligible = [
        item for item in trials
        if int(item["solved"]["sheaf_learned"]) == best_solved  # type: ignore[index]
    ]
    chosen = min(eligible, key=lambda item: int(item["budget_per_round"]))
    return int(chosen["budget_per_round"]), trials


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "symbolic-sheaf-learning-experiment-post-repair-2026-08-15.json",
    )
    parser.add_argument("--train-per-domain", type=int, default=30)
    parser.add_argument("--dev-per-domain", type=int, default=20)
    parser.add_argument("--test-per-domain", type=int, default=100)
    parser.add_argument("--train-start", type=int, default=10_000)
    parser.add_argument("--dev-start", type=int, default=20_000)
    parser.add_argument("--test-start", type=int, default=40_000)
    parser.add_argument("--phase", default="post-repair-confirmation")
    args = parser.parse_args()

    train = build_split(args.train_start, args.train_per_domain, distractors=3)
    dev = build_split(args.dev_start, args.dev_per_domain, distractors=5)
    # The test uses more distractors and disjoint labels/numbers than train/dev.
    test = build_split(args.test_start, args.test_per_domain, distractors=7)
    learner = fit_learner(train)
    budget, dev_trials = choose_budget(dev, learner)
    test_result = evaluate(
        test,
        learner=learner,
        budget=budget,
        include_fault_agent=False,
        include_records=True,
    )
    fault_result = evaluate(test, learner=learner, budget=budget, include_fault_agent=True)

    report = {
        "experiment": "llm-free-symbolic-sheaf-admm-v2",
        "phase": args.phase,
        "generated_at": datetime.now(UTC).isoformat(),
        "uses_llm": False,
        "source_basis": {
            "paper": "arXiv:2605.31005",
            "repository": "https://github.com/SakanaAI/sheaf-admm",
            "commit": "1e2b5d648361802234348b0b1a7fb3a222128e7d",
            "ported_mechanisms": [
                "private x / consensus z / scaled dual y",
                "typed pairwise restriction maps",
                "sheaf Laplacian z solve",
                "primal / dual / sheaf residual diagnostics",
            ],
            "deliberate_difference": (
                "Neural encoders/decoders and end-to-end gradients are replaced by exact "
                "certificate replay plus Beta-Bernoulli learning of structural proof flows."
            ),
        },
        "protocol": {
            "train": len(train),
            "dev": len(dev),
            "frozen_test": len(test),
            "domains": ["geometry", "integer", "set"],
            "test_only_once": True,
            "entity_and_numeric_overlap_across_splits": False,
            "learner_inputs": [
                "agent role",
                "premise-predicate multiset",
                "conclusion predicate",
                "replayed certificate dataflow",
            ],
            "forbidden_inputs": ["problem text", "problem ID", "entity label", "numeric answer"],
            "selected_budget": budget,
            "split_seeds": {
                "train_start": args.train_start,
                "dev_start": args.dev_start,
                "test_start": args.test_start,
            },
        },
        "learner": learner.to_dict(),
        "dev_budget_trials": dev_trials,
        "frozen_test": test_result,
        "fault_ablation": {
            "sheaf_learned_solved": fault_result["solved"]["sheaf_learned"],
            "sheaf_learned_replayed": fault_result["replayed"]["sheaf_learned"],
            **fault_result["fault_control"],
        },
        "claim_scope": (
            "This tests self-organized search allocation on held-out typed proof tasks. "
            "It is not a reproduction of the paper's neural Sudoku/maze scores and not "
            "an external olympiad benchmark improvement."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "budget": budget,
        "frozen_test": test_result["solved"],
        "transmitted": test_result["transmitted"],
        "fault_control": report["fault_ablation"],
    }, ensure_ascii=False))
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
