"""Compare predicate-only scheduling with typed AND-OR proof circuits.

The experiment contains no language model, problem identifier branch, answer
oracle, or learned numeric constant.  Existing three-domain held-out episodes
are supplemented with a standard relational reachability task whose chain
length and labels vary by seed.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
import json
from pathlib import Path
import random
import statistics
import sys
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.experiment_symbolic_sheaf_learning import Episode, build_split  # noqa: E402
from worker.backend.geometry_proof_hypergraph import Atom, Theorem  # noqa: E402
from worker.backend.symbolic_sheaf_coordination import (  # noqa: E402
    PredicateSignature,
    RuleClosureAdapter,
    TypedVocabulary,
)
from worker.backend.typed_logic_circuit import (  # noqa: E402
    CompiledProofCircuit,
    compile_typed_proof_circuit,
    schedule_circuit,
)


MODES = ("predicate", "current", "circuit_soft", "circuit")


def atom(name: str, *arguments: str) -> Atom:
    return Atom(name, tuple(arguments)).canonical()


def build_reachability_episode(seed: int, distractors: int) -> Episode:
    rng = random.Random(seed)
    chain_edges = 4 + seed % 4
    labels = [f"V{seed}_{index}" for index in range(chain_edges + 1 + 2 * distractors + 1)]
    rng.shuffle(labels)
    chain = labels[:chain_edges + 1]
    noise = labels[chain_edges + 1:-1]
    givens = [atom("active", chain[0])]
    givens.extend(atom("edge", left, right) for left, right in zip(chain, chain[1:]))
    for index in range(distractors):
        givens.append(atom("active", noise[2 * index]))
        givens.append(atom("edge", noise[2 * index], noise[2 * index + 1]))
    agent = RuleClosureAdapter(
        "reachability",
        (Theorem(
            "advance",
            (atom("active", "?A"), atom("edge", "?A", "?B")),
            atom("active", "?B"),
        ),),
        imports={"active", "edge"},
        exports={"active"},
    )
    vocabulary = TypedVocabulary(
        signatures={
            "active": PredicateSignature("active", ("Node",)),
            "edge": PredicateSignature("edge", ("Node", "Node")),
        },
        entity_sorts={label: "Node" for label in labels},
    )
    return Episode(
        f"reachability-{seed}",
        "reachability",
        vocabulary,
        (agent,),
        tuple(givens),
        atom("active", chain[-1]),
    )


def all_theorems(episode: Episode) -> tuple[Theorem, ...]:
    return tuple(
        theorem
        for agent in episode.agents
        for theorem in tuple(getattr(agent, "theorems", ()))
    )


def matched_negative_goal(episode: Episode, circuit: CompiledProofCircuit) -> Atom | None:
    signature = episode.vocabulary.signatures[circuit.goal.predicate]
    arguments = list(circuit.goal.arguments)
    for index, sort in enumerate(signature.argument_sorts):
        entities = sorted(
            entity
            for entity, entity_sort in episode.vocabulary.entity_sorts.items()
            if entity_sort == sort and entity != arguments[index]
        )
        for entity in entities:
            candidate_args = list(arguments)
            candidate_args[index] = entity
            candidate = Atom(circuit.goal.predicate, tuple(candidate_args)).canonical()
            valid, _ = episode.vocabulary.validate(candidate)
            if valid and candidate not in circuit.atom_depth:
                return candidate
    return None


@dataclass
class ModeTotals:
    solved: int = 0
    replayed: int = 0
    false_accepts: int = 0
    positive_transmissions: int = 0
    negative_transmissions: int = 0

    def to_dict(self) -> dict[str, int]:
        return self.__dict__.copy()


def evaluate(episodes: Iterable[Episode]) -> dict[str, object]:
    totals = {mode: ModeTotals() for mode in MODES}
    domains: dict[str, dict[str, ModeTotals]] = {}
    compile_gates: list[int] = []
    compile_matches: list[int] = []
    proof_lengths: list[int] = []
    negative_count = 0
    predicate_false_abstractions = 0
    records: list[dict[str, object]] = []

    for episode in episodes:
        circuit = compile_typed_proof_circuit(
            episode.givens,
            episode.goal,
            episode.agents,
            max_rounds=12,
        )
        proof_length = len(circuit.proof_slice())
        if not circuit.provable or proof_length == 0:
            raise RuntimeError(f"positive episode failed to compile: {episode.episode_id}")
        compile_gates.append(len(circuit.gates))
        compile_matches.append(circuit.compile_matches)
        proof_lengths.append(proof_length)
        domain_totals = domains.setdefault(
            episode.domain,
            {mode: ModeTotals() for mode in MODES},
        )
        record: dict[str, object] = {
            "id": episode.episode_id,
            "domain": episode.domain,
            "gates": len(circuit.gates),
            "compile_matches": circuit.compile_matches,
            "proof_length": proof_length,
            "positive": {},
            "negative": {},
        }

        for mode in MODES:
            result = schedule_circuit(
                circuit,
                episode.vocabulary,
                episode.agents,
                mode=mode,
                budget_per_round=1,
                max_rounds=proof_length,
            )
            totals[mode].solved += int(result.solved)
            totals[mode].replayed += int(result.replayed)
            totals[mode].positive_transmissions += result.transmitted
            domain_totals[mode].solved += int(result.solved)
            domain_totals[mode].replayed += int(result.replayed)
            domain_totals[mode].positive_transmissions += result.transmitted
            record["positive"][mode] = {
                "solved": result.solved,
                "replayed": result.replayed,
                "transmitted": result.transmitted,
            }

        negative_goal = matched_negative_goal(episode, circuit)
        if negative_goal is not None:
            negative_count += 1
            negative_circuit = replace(circuit, goal=negative_goal)
            predicate_abstract = negative_circuit.predicate_abstraction_provable(
                all_theorems(episode)
            )
            predicate_false_abstractions += int(predicate_abstract)
            record["negative_goal"] = f"{negative_goal.predicate}({','.join(negative_goal.arguments)})"
            record["predicate_abstraction_claims_provable"] = predicate_abstract
            for mode in MODES:
                result = schedule_circuit(
                    negative_circuit,
                    episode.vocabulary,
                    episode.agents,
                    mode=mode,
                    budget_per_round=1,
                    max_rounds=proof_length,
                )
                false_accept = int(result.solved or result.replayed)
                totals[mode].false_accepts += false_accept
                totals[mode].negative_transmissions += result.transmitted
                domain_totals[mode].false_accepts += false_accept
                domain_totals[mode].negative_transmissions += result.transmitted
                record["negative"][mode] = {
                    "false_accept": bool(false_accept),
                    "transmitted": result.transmitted,
                }
        records.append(record)

    episode_count = len(records)
    return {
        "protocol": {
            "positive_episodes": episode_count,
            "matched_negative_episodes": negative_count,
            "transfer_budget": "one certificate per round",
            "round_budget": "minimum exact proof length of the positive pair",
            "training": "none",
            "truth_plane": "native exact certificate replay",
            "control_plane": (
                "predicate collapse vs argument overlap vs typed AND-OR soft-all "
                "vs typed AND-OR top-1 provenance"
            ),
        },
        "overall": {mode: value.to_dict() for mode, value in totals.items()},
        "by_domain": {
            domain: {mode: value.to_dict() for mode, value in values.items()}
            for domain, values in sorted(domains.items())
        },
        "circuit": {
            "mean_gates": statistics.fmean(compile_gates),
            "max_gates": max(compile_gates),
            "mean_ground_rule_matches": statistics.fmean(compile_matches),
            "max_ground_rule_matches": max(compile_matches),
            "mean_minimum_proof_length": statistics.fmean(proof_lengths),
            "max_minimum_proof_length": max(proof_lengths),
            "predicate_collapsed_false_provability": predicate_false_abstractions,
            "predicate_collapsed_negative_total": negative_count,
        },
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes-per-domain", type=int, default=100)
    parser.add_argument("--reachability-episodes", type=int, default=100)
    parser.add_argument("--distractors", type=int, default=12)
    parser.add_argument("--seed-start", type=int, default=70000)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "typed-logic-circuit-heldout-2026-08-17.json",
    )
    args = parser.parse_args()

    episodes = build_split(
        args.seed_start,
        args.episodes_per_domain,
        args.distractors,
    )
    episodes.extend(
        build_reachability_episode(
            args.seed_start + 10000 + index,
            args.distractors,
        )
        for index in range(args.reachability_episodes)
    )
    report = evaluate(episodes)
    report["sources"] = {
        "logical_neural_networks": "arXiv:2006.13155",
        "neural_logic_machines": "arXiv:1904.11694",
        "tensorlog": "arXiv:1605.06523",
        "scallop": "NeurIPS 2021 d367eef13f90793bd8121e2f675f0dc2",
        "differentiable_logic_gates": "arXiv:2210.08277",
        "sheaf_admm": "arXiv:2605.31005",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {key: value for key, value in report.items() if key != "records"}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
