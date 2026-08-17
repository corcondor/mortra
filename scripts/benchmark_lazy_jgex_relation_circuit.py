"""Benchmark lazy typed proof circuits on real JGEX relation certificates.

The benchmark uses setup clauses from the fixed IMO-AG-30 unresolved set with
dataset auxiliary clauses hidden.  It evaluates local, independently replayed
relation obligations; it does not count them as solved global IMO problems.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from newclid.jgex.formulation import JGEXFormulation, jgex_formulation_from_txt_file  # noqa: E402

from scripts.experiment_typed_logic_circuit import matched_negative_goal  # noqa: E402
from worker.backend.geometry_proof_hypergraph import Atom  # noqa: E402
from worker.backend.jgex_local_relation_stalk import (  # noqa: E402
    JGEXRelationStalkAdapter,
    extract_jgex_relation_stalk,
)
from worker.backend.symbolic_sheaf_coordination import (  # noqa: E402
    ExactSheafCoordinator,
    PredicateSignature,
    TypedVocabulary,
)
from worker.backend.typed_logic_circuit import (  # noqa: E402
    compile_goal_directed_proof_circuit,
    compile_typed_proof_circuit,
    schedule_circuit,
)


DEFAULT_NEWCLID = Path.home() / ".cache" / "mortra-research-sources" / "Newclid"


def setup_only(problem: JGEXFormulation) -> str:
    return str(
        JGEXFormulation(
            name=problem.name,
            setup_clauses=problem.setup_clauses,
            auxiliary_clauses=(),
            goals=problem.goals,
        )
    )


def vocabulary(atoms: tuple[Atom, ...]) -> TypedVocabulary:
    signatures: dict[str, PredicateSignature] = {}
    entities: set[str] = set()
    for atom in atoms:
        signature = PredicateSignature(
            atom.predicate,
            ("Point",) * len(atom.arguments),
        )
        previous = signatures.get(atom.predicate)
        if previous is not None and previous != signature:
            raise ValueError(f"inconsistent relation arity: {atom.predicate}")
        signatures[atom.predicate] = signature
        entities.update(atom.arguments)
    return TypedVocabulary(
        signatures=signatures,
        entity_sorts={entity: "Point" for entity in entities},
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_NEWCLID / "newclid" / "problems_datasets" / "imo.txt",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=ROOT / "data" / "yuclid-imo-ag-30-all-ar-2026-08-15.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "lazy-jgex-relation-benchmark-2026-08-17.json",
    )
    args = parser.parse_args()

    formulations = jgex_formulation_from_txt_file(args.dataset)
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    unresolved = [
        name
        for name, result in baseline["results"].items()
        if result["status"] != "solved" and name in formulations
    ]

    records = []
    problems = {}
    for index, name in enumerate(unresolved, start=1):
        print(f"[{index}/{len(unresolved)}] {name}", flush=True)
        stalk = extract_jgex_relation_stalk(setup_only(formulations[name]))
        adapter = JGEXRelationStalkAdapter(stalk)
        conclusions = tuple(
            conclusion
            for certificate in stalk.certificates
            for conclusion in certificate.conclusions
        )
        all_atoms = (*stalk.source_atoms, *conclusions)
        if not all_atoms:
            problems[name] = {
                "source_atoms": 0,
                "local_goals": 0,
                "current_replayed": 0,
                "exhaustive_replayed": 0,
                "lazy_replayed": 0,
            }
            continue
        typed_vocabulary = vocabulary(all_atoms)
        coordinator = ExactSheafCoordinator(typed_vocabulary, (adapter,))
        problem_counts = {
            "source_atoms": len(stalk.source_atoms),
            "local_goals": len(conclusions),
            "current_replayed": 0,
            "exhaustive_replayed": 0,
            "lazy_replayed": 0,
        }

        for goal in conclusions:
            current = coordinator.solve(stalk.source_atoms, goal)
            started = time.perf_counter()
            exhaustive = compile_typed_proof_circuit(
                stalk.source_atoms,
                goal,
                (adapter,),
                max_rounds=12,
            )
            exhaustive_seconds = time.perf_counter() - started
            proof_budget = max(1, len(exhaustive.proof_slice()))
            exhaustive_result = schedule_circuit(
                exhaustive,
                typed_vocabulary,
                (adapter,),
                mode="circuit",
                budget_per_round=1,
                max_rounds=proof_budget,
            )

            started = time.perf_counter()
            lazy = compile_goal_directed_proof_circuit(
                stalk.source_atoms,
                goal,
                (adapter,),
                max_rule_applications=proof_budget,
                max_search_states=20_000,
            )
            lazy_seconds = time.perf_counter() - started
            lazy_result = schedule_circuit(
                lazy,
                typed_vocabulary,
                (adapter,),
                mode="circuit",
                budget_per_round=1,
                max_rounds=proof_budget,
            )

            negative_goal = matched_negative_goal(
                type("EpisodeView", (), {"vocabulary": typed_vocabulary})(),
                exhaustive,
            )
            negative_abstained = True
            if negative_goal is not None:
                negative = compile_goal_directed_proof_circuit(
                    stalk.source_atoms,
                    negative_goal,
                    (adapter,),
                    max_rule_applications=proof_budget,
                    max_search_states=20_000,
                )
                negative_result = schedule_circuit(
                    negative,
                    typed_vocabulary,
                    (adapter,),
                    mode="circuit",
                    budget_per_round=1,
                    max_rounds=proof_budget,
                )
                negative_abstained = not negative_result.replayed

            current_replayed = bool(current.solved and current.replayed)
            problem_counts["current_replayed"] += int(current_replayed)
            problem_counts["exhaustive_replayed"] += int(exhaustive_result.replayed)
            problem_counts["lazy_replayed"] += int(lazy_result.replayed)
            records.append(
                {
                    "problem": name,
                    "goal": f"{goal.predicate}({','.join(goal.arguments)})",
                    "current_replayed": current_replayed,
                    "exhaustive_replayed": exhaustive_result.replayed,
                    "lazy_replayed": lazy_result.replayed,
                    "negative_abstained": negative_abstained,
                    "proof_budget": proof_budget,
                    "exhaustive_matches": exhaustive.compile_matches,
                    "lazy_matches": lazy.compile_matches,
                    "exhaustive_gates": len(exhaustive.gates),
                    "lazy_gates": len(lazy.gates),
                    "exhaustive_seconds": exhaustive_seconds,
                    "lazy_seconds": lazy_seconds,
                    "lazy_states": lazy.search_states,
                    "lazy_backtracks": lazy.backtracks,
                }
            )
        problems[name] = problem_counts

    goal_count = len(records)
    current_score = sum(int(item["current_replayed"]) for item in records)
    exhaustive_score = sum(int(item["exhaustive_replayed"]) for item in records)
    lazy_score = sum(int(item["lazy_replayed"]) for item in records)
    negatives = sum(int(item["negative_abstained"]) for item in records)
    exhaustive_matches = sum(int(item["exhaustive_matches"]) for item in records)
    lazy_matches = sum(int(item["lazy_matches"]) for item in records)
    exhaustive_gates = sum(int(item["exhaustive_gates"]) for item in records)
    lazy_gates = sum(int(item["lazy_gates"]) for item in records)
    report = {
        "experiment": "lazy-typed-circuit-real-jgex-relations",
        "protocol": {
            "uses_llm": False,
            "uses_problem_specific_rules": False,
            "uses_reference_answers": False,
            "dataset_auxiliary_clauses_hidden": True,
            "fixed_global_benchmark": "IMO-AG-30 unresolved 13",
            "score_scope": "independently replayed local relation obligations",
        },
        "summary": {
            "global_imo_baseline": 17,
            "global_imo_strict_portfolio_before_and_after": 19,
            "global_imo_total": 30,
            "local_goal_total": goal_count,
            "current_local_replayed": current_score,
            "exhaustive_circuit_local_replayed": exhaustive_score,
            "lazy_circuit_local_replayed": lazy_score,
            "matched_negative_abstained": negatives,
            "exhaustive_matches": exhaustive_matches,
            "lazy_matches": lazy_matches,
            "match_reduction_rate": (
                1 - lazy_matches / exhaustive_matches if exhaustive_matches else 0.0
            ),
            "exhaustive_gates": exhaustive_gates,
            "lazy_gates": lazy_gates,
            "gate_reduction_rate": (
                1 - lazy_gates / exhaustive_gates if exhaustive_gates else 0.0
            ),
            "exhaustive_seconds": sum(float(item["exhaustive_seconds"]) for item in records),
            "lazy_seconds": sum(float(item["lazy_seconds"]) for item in records),
        },
        "problems": problems,
        "records": records,
        "claim_scope": (
            "The local score measures real certificate replay and compilation cost. "
            "The global IMO score is unchanged because this experiment schedules "
            "existing local lemmas but does not invent new global constructions."
        ),
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
