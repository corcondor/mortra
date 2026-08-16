"""Measure verified local relation exchange on a fixed heavy JGEX slice."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from newclid.jgex.formulation import (  # noqa: E402
    JGEXFormulation,
    jgex_formulation_from_txt_file,
)

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


DEFAULT_NEWCLID = Path.home() / ".cache" / "mortra-research-sources" / "Newclid"
DEFAULT_PROBLEMS = ("2008_p6", "2010_p2", "2020_p1", "2021_p3")


def _setup_only(problem: JGEXFormulation) -> str:
    return str(
        JGEXFormulation(
            name=problem.name,
            setup_clauses=problem.setup_clauses,
            auxiliary_clauses=(),
            goals=problem.goals,
        )
    )


def _vocabulary(atoms: tuple[Atom, ...]) -> TypedVocabulary:
    signatures: dict[str, PredicateSignature] = {}
    entities: set[str] = set()
    for atom in atoms:
        previous = signatures.get(atom.predicate)
        signature = PredicateSignature(
            atom.predicate,
            ("Point",) * len(atom.arguments),
        )
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
    parser.add_argument("--problems", nargs="*", default=DEFAULT_PROBLEMS)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "jgex-local-relation-stalk-fixed4-2026-08-16.json",
    )
    args = parser.parse_args()

    formulations = jgex_formulation_from_txt_file(args.dataset)
    results: dict[str, dict] = {}
    total_goals = 0
    total_solved = 0
    total_hidden = 0
    for problem_name in args.problems:
        stalk = extract_jgex_relation_stalk(_setup_only(formulations[problem_name]))
        all_conclusions = tuple(
            conclusion
            for certificate in stalk.certificates
            for conclusion in certificate.conclusions
        )
        all_atoms = (*stalk.source_atoms, *all_conclusions)
        coordinator = ExactSheafCoordinator(
            _vocabulary(all_atoms),
            (JGEXRelationStalkAdapter(stalk),),
        )
        goals: list[dict] = []
        for goal in all_conclusions:
            result = coordinator.solve(stalk.source_atoms, goal)
            goals.append(
                {
                    "goal": f"{goal.predicate}({','.join(goal.arguments)})",
                    "solved": result.solved,
                    "replayed": result.replayed,
                    "proof": [
                        {
                            "rule": item.rule_name,
                            "native_payload": dict(item.native_payload),
                        }
                        for item in result.proof_slice()
                    ],
                }
            )
        solved = sum(item["solved"] and item["replayed"] for item in goals)
        hidden = sum(len(item.hidden_points) for item in stalk.certificates)
        total_goals += len(goals)
        total_solved += solved
        total_hidden += hidden
        results[problem_name] = {
            "source_atom_count": len(stalk.source_atoms),
            "certificate_count": len(stalk.certificates),
            "relation_counts": dict(stalk.relation_counts),
            "hidden_internal_point_count": hidden,
            "certificates": [asdict(item) for item in stalk.certificates],
            "local_goals": goals,
            "local_goals_replayed": solved,
            "local_goals_total": len(goals),
        }

    report = {
        "experiment": "jgex-typed-local-relation-stalk-fixed4",
        "generated_at": datetime.now(UTC).isoformat(),
        "uses_llm": False,
        "uses_problem_specific_solver_logic": False,
        "dataset_auxiliary_clauses_hidden": True,
        "fixed_problem_names": list(args.problems),
        "summary": {
            "local_goals_replayed": total_solved,
            "local_goals_total": total_goals,
            "local_replay_rate": total_solved / total_goals if total_goals else 0.0,
            "hidden_internal_points": total_hidden,
        },
        "results": results,
        "claim_scope": (
            "This proves finite typed local relation exchange and certificate replay. "
            "It does not claim that the four global IMO goals are solved."
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
