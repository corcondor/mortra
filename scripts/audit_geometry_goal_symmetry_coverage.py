"""Measure theorem-entry coverage gained from relation symmetry semantics.

This audit never reads expected answers or auxiliary clauses.  It compares the
former position-wise goal unifier with the current symmetry-aware typed atom
unifier across every goal in a JGEX dataset.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.experiment_newclid_construction_stalk import (  # noqa: E402
    JGEXProblemBuilder,
    formulation_goal_atoms,
    jgex_formulation_from_txt_file,
    native_rule_theorems,
    normalize_legacy_formulation,
)
from worker.backend.geometry_proof_hypergraph import (  # noqa: E402
    Atom,
    atom_pattern_unifications,
)


def _legacy_position_unifies(pattern: Atom, goal: Atom) -> bool:
    if pattern.predicate.lower() != goal.predicate.lower():
        return False
    if len(pattern.arguments) != len(goal.arguments):
        return False
    substitution: dict[str, str] = {}
    for expected, actual in zip(pattern.arguments, goal.arguments):
        if expected.startswith("?"):
            previous = substitution.get(expected)
            if previous is not None and previous != actual:
                return False
            substitution[expected] = actual
        elif expected != actual:
            return False
    return True


def audit(dataset: Path) -> dict[str, Any]:
    formulations = jgex_formulation_from_txt_file(dataset.resolve())
    builder = JGEXProblemBuilder(np.random.default_rng(0))
    theorem_conclusions = tuple(
        (theorem.name, theorem.conclusion) for theorem in native_rule_theorems()
    )
    predicate_totals: Counter[str] = Counter()
    predicate_legacy: Counter[str] = Counter()
    predicate_symmetric: Counter[str] = Counter()
    predicate_full: Counter[str] = Counter()
    recovered: dict[str, list[dict[str, Any]]] = defaultdict(list)
    recovered_by_morphism: dict[str, list[dict[str, Any]]] = defaultdict(list)
    total_goals = legacy_covered = symmetric_covered = full_covered = 0
    representation_morphisms = {
        "equal-angle-transitivity",
        "equal-ratio-transitivity",
    }

    for problem_name, raw in formulations.items():
        formulation, _ = normalize_legacy_formulation(raw, builder.jgex_defs)
        for goal in formulation_goal_atoms(formulation):
            total_goals += 1
            predicate = goal.predicate.lower()
            predicate_totals[predicate] += 1
            matching = [
                (name, conclusion)
                for name, conclusion in theorem_conclusions
                if conclusion.predicate.lower() == predicate
            ]
            native_matching = [
                item for item in matching if item[0] not in representation_morphisms
            ]
            legacy_matches = [
                name
                for name, conclusion in native_matching
                if _legacy_position_unifies(conclusion, goal)
            ]
            symmetric_matches = [
                name
                for name, conclusion in native_matching
                if atom_pattern_unifications(conclusion, goal)
            ]
            full_matches = [
                name
                for name, conclusion in matching
                if atom_pattern_unifications(conclusion, goal)
            ]
            if legacy_matches:
                legacy_covered += 1
                predicate_legacy[predicate] += 1
            if symmetric_matches:
                symmetric_covered += 1
                predicate_symmetric[predicate] += 1
            if full_matches:
                full_covered += 1
                predicate_full[predicate] += 1
            if symmetric_matches and not legacy_matches:
                recovered[predicate].append(
                    {
                        "problem_name": problem_name,
                        "goal": {
                            "predicate": goal.predicate,
                            "arguments": list(goal.arguments),
                        },
                        "matching_theorems": symmetric_matches,
                    }
                )
            if full_matches and not symmetric_matches:
                recovered_by_morphism[predicate].append(
                    {
                        "problem_name": problem_name,
                        "goal": {
                            "predicate": goal.predicate,
                            "arguments": list(goal.arguments),
                        },
                        "matching_theorems": full_matches,
                    }
                )

    predicates = sorted(predicate_totals)
    return {
        "experiment": "geometry_goal_theorem_entry_symmetry_coverage",
        "protocol": {
            "uses_external_llm": False,
            "uses_expected_answers": False,
            "uses_dataset_auxiliary_clauses": False,
            "comparison": "position_wise_unification_vs_relation_symmetry_orbit",
        },
        "dataset": dataset.resolve().as_posix(),
        "summary": {
            "problems": len(formulations),
            "goals": total_goals,
            "native_legacy_covered": legacy_covered,
            "native_symmetry_covered": symmetric_covered,
            "full_representation_covered": full_covered,
            "recovered_by_symmetry": symmetric_covered - legacy_covered,
            "recovered_by_universal_morphism": full_covered - symmetric_covered,
            "native_legacy_rate": legacy_covered / total_goals if total_goals else 0.0,
            "native_symmetry_rate": symmetric_covered / total_goals if total_goals else 0.0,
            "full_representation_rate": full_covered / total_goals if total_goals else 0.0,
        },
        "by_predicate": {
            predicate: {
                "goals": predicate_totals[predicate],
                "legacy_covered": predicate_legacy[predicate],
                "symmetry_covered": predicate_symmetric[predicate],
                "full_representation_covered": predicate_full[predicate],
                "recovered_by_symmetry": len(recovered[predicate]),
                "recovered_by_universal_morphism": len(
                    recovered_by_morphism[predicate]
                ),
            }
            for predicate in predicates
        },
        "recovered_goals": dict(recovered),
        "morphism_recovered_goals": dict(recovered_by_morphism),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.dataset)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
