"""Typed atom alignment for construction candidates and open proof obligations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from worker.backend.geometry_proof_hypergraph import (
    Atom,
    atom_pattern_unifications,
)


UNREACHABLE_DISTANCE = 10**6


def _is_variable(value: str) -> bool:
    return value.startswith("?")


@dataclass(frozen=True)
class TypedAtomAlignment:
    direct_match_count: int
    direct_hole_binding_count: int
    best_relation_distance: int
    best_known_argument_overlap: int
    fewest_missing_known_arguments: int
    candidate_atom_count: int
    demand_count: int

    @property
    def rank(self) -> tuple[int, ...]:
        return (
            0 if self.direct_match_count else 1,
            -self.direct_match_count,
            -self.direct_hole_binding_count,
            self.best_relation_distance,
            -self.best_known_argument_overlap,
            self.fewest_missing_known_arguments,
            -self.candidate_atom_count,
        )

    def to_dict(self) -> dict[str, int | list[int]]:
        return {
            "direct_match_count": self.direct_match_count,
            "direct_hole_binding_count": self.direct_hole_binding_count,
            "best_relation_distance": self.best_relation_distance,
            "best_known_argument_overlap": self.best_known_argument_overlap,
            "fewest_missing_known_arguments": self.fewest_missing_known_arguments,
            "candidate_atom_count": self.candidate_atom_count,
            "demand_count": self.demand_count,
            "rank": list(self.rank),
        }


def instantiate_relation_templates(
    parameters: Sequence[str],
    templates: Sequence[Atom],
    values: Sequence[str],
) -> tuple[Atom, ...]:
    if len(parameters) != len(values):
        raise ValueError(
            f"relation template arity mismatch: {len(parameters)} != {len(values)}"
        )
    substitution = dict(zip(parameters, values))
    return tuple(
        Atom(
            template.predicate,
            tuple(substitution.get(argument, argument) for argument in template.arguments),
        ).canonical()
        for template in templates
    )


def align_candidate_atoms(
    candidate_atoms: Sequence[Atom],
    demands: Sequence[Atom],
    relation_distances: Mapping[str, Mapping[str, int]],
) -> TypedAtomAlignment:
    """Rank a candidate without problem IDs, labels, answers, or theorem names."""

    facts = tuple(atom.canonical() for atom in candidate_atoms)
    wanted = tuple(demand.canonical() for demand in demands)
    if not facts or not wanted:
        return TypedAtomAlignment(
            0,
            0,
            UNREACHABLE_DISTANCE,
            0,
            0,
            len(facts),
            len(wanted),
        )

    direct_matches = 0
    hole_bindings: set[tuple[str, str]] = set()
    best_distance = UNREACHABLE_DISTANCE
    best_overlap = 0
    fewest_missing = UNREACHABLE_DISTANCE
    for demand in wanted:
        known_arguments = {
            argument for argument in demand.arguments if not _is_variable(argument)
        }
        distances_to_demand = relation_distances.get(demand.predicate, {})
        for fact in facts:
            substitutions = atom_pattern_unifications(demand, fact)
            if substitutions:
                direct_matches += 1
                for substitution in substitutions:
                    hole_bindings.update(
                        (variable, value)
                        for variable, value in substitution
                        if _is_variable(variable)
                    )
            best_distance = min(
                best_distance,
                0
                if fact.predicate == demand.predicate
                else distances_to_demand.get(
                    fact.predicate, UNREACHABLE_DISTANCE
                ),
            )
            overlap = len(known_arguments.intersection(fact.arguments))
            best_overlap = max(best_overlap, overlap)
            fewest_missing = min(fewest_missing, len(known_arguments) - overlap)
    return TypedAtomAlignment(
        direct_matches,
        len(hole_bindings),
        best_distance,
        best_overlap,
        fewest_missing,
        len(facts),
        len(wanted),
    )
