"""Typed atom alignment for construction candidates and open proof obligations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from worker.backend.geometry_proof_hypergraph import (
    Atom,
    Theorem,
    atom_pattern_unifications,
)
from worker.backend.typed_open_proof_dag import (
    CandidateForwardCone,
    EXECUTABLE_SIDE_CONDITION_PREDICATES,
    ForwardProofFragment,
    OpenProofBranch,
    alpha_normalize_symbolic_atoms,
    compile_candidate_forward_cone,
)
from worker.backend.typed_logic_circuit import (
    substitute_symbolic_atom,
    symbolic_atom_unifications,
)


UNREACHABLE_DISTANCE = 10**6


def _is_variable(value: str) -> bool:
    return value.startswith("?")


@dataclass(frozen=True)
class TypedObligationSignature:
    atom: Atom
    holes: tuple[str, ...]
    known_entities: tuple[str, ...]

    @property
    def requires_witness(self) -> bool:
        return bool(self.holes)


def obligation_signature(atom: Atom) -> TypedObligationSignature:
    canonical = atom.canonical()
    return TypedObligationSignature(
        atom=canonical,
        holes=tuple(
            dict.fromkeys(
                argument for argument in canonical.arguments if _is_variable(argument)
            )
        ),
        known_entities=tuple(
            dict.fromkeys(
                argument for argument in canonical.arguments if not _is_variable(argument)
            )
        ),
    )


def candidate_directly_satisfies_obligation(
    candidate_atoms: Sequence[Atom],
    demand: Atom,
) -> bool:
    """Accept direct construction coverage only with a compatible output hole.

    A ground relation such as ``cyclic(p,q,r,t)`` is a proposition to prove;
    constructing a fresh point on some circle is not a direct witness for it.
    Ground obligations therefore require the exact fact.  Existential
    obligations require every typed hole to be bound by symmetry-aware
    unification.
    """

    signature = obligation_signature(demand)
    candidates = tuple(atom.canonical() for atom in candidate_atoms)
    if not signature.requires_witness:
        return signature.atom in candidates
    required = set(signature.holes)
    for candidate in candidates:
        for substitution in atom_pattern_unifications(signature.atom, candidate):
            bindings = dict(substitution)
            if required <= bindings.keys() and all(
                not _is_variable(bindings[hole]) for hole in required
            ):
                return True
    return False


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


@dataclass(frozen=True)
class ProofDAGCandidateAlignment:
    direct_match_count: int
    direct_hole_binding_count: int
    matching_branch_count: int
    best_branch_id: str | None
    best_branch_depth: int | None
    best_frontier_size: int | None
    branch_count: int

    @property
    def has_direct_match(self) -> bool:
        return self.direct_match_count > 0

    @property
    def rank(self) -> tuple[int, ...]:
        if not self.has_direct_match:
            return (1,)
        return (
            0,
            -self.direct_match_count,
            -self.direct_hole_binding_count,
            self.best_branch_depth or 0,
            self.best_frontier_size or 0,
            -self.matching_branch_count,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "direct_match_count": self.direct_match_count,
            "direct_hole_binding_count": self.direct_hole_binding_count,
            "matching_branch_count": self.matching_branch_count,
            "best_branch_id": self.best_branch_id,
            "best_branch_depth": self.best_branch_depth,
            "best_frontier_size": self.best_frontier_size,
            "branch_count": self.branch_count,
            "rank": list(self.rank),
        }


@dataclass(frozen=True)
class ProofDAGMeetAlignment:
    meet_count: int
    cyclic_match_rejections: int
    best_branch_id: str | None
    best_fragment_id: str | None
    best_meet_atom: str | None
    best_forward_depth: int | None
    best_backward_depth: int | None
    best_residual_size: int | None
    best_structural_residual_count: int | None
    best_residual_hole_count: int | None
    best_source_atom_count: int | None
    best_residual_atoms: tuple[str, ...]
    best_source_atoms: tuple[str, ...]
    best_theorem_chain: tuple[str, ...]
    best_backward_frontier_size: int | None
    branch_count: int
    fragment_count: int

    @property
    def has_meet(self) -> bool:
        return self.meet_count > 0

    @property
    def has_residual_reduction(self) -> bool:
        return (
            self.has_meet
            and self.best_residual_size is not None
            and self.best_backward_frontier_size is not None
            and self.best_residual_size < self.best_backward_frontier_size
        )

    @property
    def rank(self) -> tuple[int, ...]:
        if not self.has_meet:
            return (1,)
        return (
            0,
            self.best_structural_residual_count or 0,
            self.best_residual_size or 0,
            self.best_residual_hole_count or 0,
            (self.best_forward_depth or 0) + (self.best_backward_depth or 0),
            -(self.best_source_atom_count or 0),
            -self.meet_count,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "meet_count": self.meet_count,
            "cyclic_match_rejections": self.cyclic_match_rejections,
            "best_branch_id": self.best_branch_id,
            "best_fragment_id": self.best_fragment_id,
            "best_meet_atom": self.best_meet_atom,
            "best_forward_depth": self.best_forward_depth,
            "best_backward_depth": self.best_backward_depth,
            "best_residual_size": self.best_residual_size,
            "best_structural_residual_count": self.best_structural_residual_count,
            "best_residual_hole_count": self.best_residual_hole_count,
            "best_source_atom_count": self.best_source_atom_count,
            "best_residual_atoms": list(self.best_residual_atoms),
            "best_source_atoms": list(self.best_source_atoms),
            "best_theorem_chain": list(self.best_theorem_chain),
            "best_backward_frontier_size": self.best_backward_frontier_size,
            "has_residual_reduction": self.has_residual_reduction,
            "branch_count": self.branch_count,
            "fragment_count": self.fragment_count,
            "rank": list(self.rank),
        }


@dataclass(frozen=True)
class LazyProofDAGCandidateAlignment:
    """Auditable result of budgeted, residual-guided cone expansion."""

    alignment: ProofDAGMeetAlignment
    predicate_distance: int
    best_known_argument_overlap: int
    fewest_missing_known_arguments: int
    explored_depth: int
    search_states: int
    stage_search_states: tuple[int, ...]
    promoted: bool
    residual_improvements: int
    truncated: bool

    @property
    def has_meet(self) -> bool:
        return self.alignment.has_meet

    @property
    def exploration_rank(self) -> tuple[int, ...]:
        if self.alignment.has_meet:
            return (
                0,
                self.alignment.best_structural_residual_count or 0,
                self.alignment.best_residual_size or 0,
                self.alignment.best_residual_hole_count or 0,
                (self.alignment.best_forward_depth or 0)
                + (self.alignment.best_backward_depth or 0),
                -self.best_known_argument_overlap,
                -self.alignment.meet_count,
            )
        return (
            1,
            self.predicate_distance,
            -self.best_known_argument_overlap,
            self.fewest_missing_known_arguments,
        )

    @property
    def has_closed_structural_residual(self) -> bool:
        return (
            self.alignment.has_meet
            and self.alignment.best_structural_residual_count == 0
        )

    @property
    def rank(self) -> tuple[int, ...]:
        """Only a structurally closed meet may override the base scheduler."""

        if not self.has_closed_structural_residual:
            return (1,)
        return (
            0,
            self.alignment.best_residual_size or 0,
            self.alignment.best_residual_hole_count or 0,
            (self.alignment.best_forward_depth or 0)
            + (self.alignment.best_backward_depth or 0),
            -self.alignment.meet_count,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            **self.alignment.to_dict(),
            "lazy_rank": list(self.rank),
            "exploration_rank": list(self.exploration_rank),
            "has_closed_structural_residual": self.has_closed_structural_residual,
            "predicate_distance": self.predicate_distance,
            "best_known_argument_overlap": self.best_known_argument_overlap,
            "fewest_missing_known_arguments": self.fewest_missing_known_arguments,
            "explored_depth": self.explored_depth,
            "search_states": self.search_states,
            "stage_search_states": list(self.stage_search_states),
            "promoted": self.promoted,
            "residual_improvements": self.residual_improvements,
            "truncated": self.truncated,
        }


def _best_direct_branch_matching(
    candidate_atoms: Sequence[Atom],
    frontier: Sequence[Atom],
) -> tuple[int, int]:
    edges: dict[tuple[int, int], tuple[tuple[tuple[str, str], ...], ...]] = {}
    for candidate_index, candidate in enumerate(candidate_atoms):
        for demand_index, demand in enumerate(frontier):
            substitutions = atom_pattern_unifications(demand, candidate)
            if substitutions:
                edges[(candidate_index, demand_index)] = substitutions

    best = (0, 0)

    def visit(
        candidate_index: int,
        used_demands: frozenset[int],
        match_count: int,
        hole_bindings: frozenset[tuple[str, str]],
    ) -> None:
        nonlocal best
        if candidate_index == len(candidate_atoms):
            best = max(best, (match_count, len(hole_bindings)))
            return
        visit(candidate_index + 1, used_demands, match_count, hole_bindings)
        for demand_index in range(len(frontier)):
            if demand_index in used_demands:
                continue
            for substitution in edges.get((candidate_index, demand_index), ()):
                bindings = frozenset(
                    (variable, value)
                    for variable, value in substitution
                    if _is_variable(variable)
                )
                visit(
                    candidate_index + 1,
                    used_demands | {demand_index},
                    match_count + 1,
                    hole_bindings | bindings,
                )

    visit(0, frozenset(), 0, frozenset())
    return best


def align_candidate_to_proof_branches(
    candidate_atoms: Sequence[Atom],
    branches: Sequence[OpenProofBranch],
) -> ProofDAGCandidateAlignment:
    """Align within each OR branch; never combine premises across branches."""

    ranked: list[tuple[tuple[int, ...], OpenProofBranch, int, int]] = []
    matching_branches = 0
    for branch in branches:
        direct_matches, hole_bindings = _best_direct_branch_matching(
            candidate_atoms, branch.frontier
        )
        if direct_matches:
            matching_branches += 1
        rank = (
            -direct_matches,
            -hole_bindings,
            branch.rule_depth,
            len(branch.frontier),
            branch.branch_id,
        )
        ranked.append((rank, branch, direct_matches, hole_bindings))
    if not ranked:
        return ProofDAGCandidateAlignment(0, 0, 0, None, None, None, 0)
    _rank, best_branch, direct_matches, hole_bindings = min(ranked)
    return ProofDAGCandidateAlignment(
        direct_match_count=direct_matches,
        direct_hole_binding_count=hole_bindings,
        matching_branch_count=matching_branches,
        best_branch_id=(best_branch.branch_id if direct_matches else None),
        best_branch_depth=(best_branch.rule_depth if direct_matches else None),
        best_frontier_size=(len(best_branch.frontier) if direct_matches else None),
        branch_count=len(branches),
    )


def align_candidate_cone_to_proof_branches(
    cone: CandidateForwardCone,
    branches: Sequence[OpenProofBranch],
) -> ProofDAGMeetAlignment:
    """Meet one forward fragment with one coherent backward OR branch.

    A match is only a scheduling signal. Any unproved premises from both sides
    remain in ``best_residual_size`` and native certificate replay still
    decides correctness.
    """

    matches: list[
        tuple[
            tuple[object, ...],
            OpenProofBranch,
            ForwardProofFragment,
            Atom,
            int,
            int,
            int,
            int,
            tuple[Atom, ...],
        ]
    ] = []
    cyclic_match_rejections = 0
    for branch in branches:
        for demand_index, demand in enumerate(branch.frontier):
            remaining = (
                branch.frontier[:demand_index]
                + branch.frontier[demand_index + 1 :]
            )
            for fragment in cone.fragments:
                for substitution in symbolic_atom_unifications(
                    fragment.conclusion, demand
                ):
                    residual = alpha_normalize_symbolic_atoms(
                        substitute_symbolic_atom(atom, substitution)
                        for atom in (*fragment.residual_frontier, *remaining)
                    )
                    instantiated_demand = substitute_symbolic_atom(
                        demand, substitution
                    ).canonical()
                    if instantiated_demand in residual:
                        cyclic_match_rejections += 1
                        continue
                    holes = {
                        argument
                        for atom in residual
                        for argument in atom.arguments
                        if _is_variable(argument)
                    }
                    ground_bindings = sum(
                        _is_variable(key) and not _is_variable(value)
                        for key, value in substitution.items()
                    )
                    source_count = len(fragment.source_atoms)
                    structural_residual_count = sum(
                        atom.predicate
                        not in EXECUTABLE_SIDE_CONDITION_PREDICATES
                        for atom in residual
                    )
                    rank = (
                        structural_residual_count,
                        len(residual),
                        len(holes),
                        fragment.rule_depth + branch.rule_depth,
                        -source_count,
                        -ground_bindings,
                        fragment.rule_depth,
                        branch.rule_depth,
                        branch.branch_id,
                        fragment.fragment_id,
                    )
                    matches.append(
                        (
                            rank,
                            branch,
                            fragment,
                            demand,
                            len(residual),
                            structural_residual_count,
                            len(holes),
                            source_count,
                            residual,
                        )
                    )
    if not matches:
        return ProofDAGMeetAlignment(
            0,
            cyclic_match_rejections,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            (),
            (),
            (),
            None,
            len(branches),
            len(cone.fragments),
        )
    (
        _rank,
        best_branch,
        best_fragment,
        best_demand,
        residual_size,
        structural_residual_count,
        residual_holes,
        source_count,
        best_residual,
    ) = min(matches, key=lambda item: item[0])
    return ProofDAGMeetAlignment(
        meet_count=len(matches),
        cyclic_match_rejections=cyclic_match_rejections,
        best_branch_id=best_branch.branch_id,
        best_fragment_id=best_fragment.fragment_id,
        best_meet_atom=(
            f"{best_demand.predicate}({','.join(best_demand.arguments)})"
        ),
        best_forward_depth=best_fragment.rule_depth,
        best_backward_depth=best_branch.rule_depth,
        best_residual_size=residual_size,
        best_structural_residual_count=structural_residual_count,
        best_residual_hole_count=residual_holes,
        best_source_atom_count=source_count,
        best_residual_atoms=tuple(
            f"{atom.predicate}({','.join(atom.arguments)})"
            for atom in best_residual
        ),
        best_source_atoms=tuple(
            f"{atom.predicate}({','.join(atom.arguments)})"
            for atom in best_fragment.source_atoms
        ),
        best_theorem_chain=best_fragment.theorem_chain,
        best_backward_frontier_size=len(best_branch.frontier),
        branch_count=len(branches),
        fragment_count=len(cone.fragments),
    )


def _forward_predicate_distances(
    theorems: Sequence[Theorem],
    target_predicates: set[str],
) -> dict[str, int]:
    """Return a problem-independent lower bound on forward proof distance."""

    reverse_edges: dict[str, set[str]] = {}
    for theorem in theorems:
        conclusion = theorem.conclusion.predicate.lower()
        reverse_edges.setdefault(conclusion, set()).update(
            premise.predicate.lower() for premise in theorem.premises
        )
    distances = {predicate.lower(): 0 for predicate in target_predicates}
    frontier = list(distances)
    while frontier:
        conclusion = frontier.pop(0)
        next_distance = distances[conclusion] + 1
        for premise in sorted(reverse_edges.get(conclusion, ())):
            if premise in distances and distances[premise] <= next_distance:
                continue
            distances[premise] = next_distance
            frontier.append(premise)
    return distances


def _candidate_to_branch_gap(
    candidate_atoms: Sequence[Atom],
    branches: Sequence[OpenProofBranch],
    predicate_distances: Mapping[str, int],
) -> tuple[int, int, int]:
    target_atoms = tuple(atom for branch in branches for atom in branch.frontier)
    if not candidate_atoms or not target_atoms:
        return UNREACHABLE_DISTANCE, 0, UNREACHABLE_DISTANCE
    best_distance = min(
        (
            predicate_distances.get(
                candidate.predicate.lower(), UNREACHABLE_DISTANCE
            )
            for candidate in candidate_atoms
        ),
        default=UNREACHABLE_DISTANCE,
    )
    best_overlap = 0
    fewest_missing = UNREACHABLE_DISTANCE
    for target in target_atoms:
        known = {value for value in target.arguments if not _is_variable(value)}
        for candidate in candidate_atoms:
            overlap = len(known.intersection(candidate.arguments))
            best_overlap = max(best_overlap, overlap)
            fewest_missing = min(fewest_missing, len(known) - overlap)
    return best_distance, best_overlap, fewest_missing


def _meet_quality(alignment: ProofDAGMeetAlignment) -> tuple[int, ...]:
    if not alignment.has_meet:
        return (1, UNREACHABLE_DISTANCE)
    return (
        0,
        alignment.best_structural_residual_count or 0,
        alignment.best_residual_size or 0,
        alignment.best_residual_hole_count or 0,
    )


def align_candidate_groups_lazily(
    facts: Iterable[Atom],
    candidate_groups: Mapping[str, Sequence[Atom]],
    theorems: Sequence[Theorem],
    branches: Sequence[OpenProofBranch],
    *,
    tiebreaks: Mapping[str, tuple[object, ...]] | None = None,
    max_rule_depth: int = 2,
    max_fragments: int = 48,
    initial_search_states: int = 64,
    promoted_search_states: int = 500,
    promotion_limit: int = 8,
) -> tuple[
    dict[str, LazyProofDAGCandidateAlignment],
    dict[str, CandidateForwardCone],
]:
    """Allocate deeper proof search only to candidates reducing typed residuals.

    Every candidate receives the same shallow observation.  Later rounds are
    assigned to a bounded Pareto prefix ordered by coherent meet residual,
    predicate reachability, argument overlap, and a caller-supplied structural
    tiebreak.  Native proof replay remains the acceptance boundary.
    """

    if max_rule_depth < 1:
        raise ValueError("max_rule_depth must be positive")
    if min(max_fragments, initial_search_states, promoted_search_states) < 1:
        raise ValueError("search budgets must be positive")
    if promotion_limit < 1:
        raise ValueError("promotion_limit must be positive")

    canonical_facts = tuple(facts)
    theorem_tuple = tuple(theorems)
    targets = tuple(atom for branch in branches for atom in branch.frontier)
    target_predicates = {atom.predicate.lower() for atom in targets}
    distances = _forward_predicate_distances(theorem_tuple, target_predicates)
    tiebreaks = tiebreaks or {}
    cones: dict[str, CandidateForwardCone] = {}
    results: dict[str, LazyProofDAGCandidateAlignment] = {}
    stage_states: dict[str, list[int]] = {key: [] for key in candidate_groups}
    improvements = {key: 0 for key in candidate_groups}
    promoted_keys: set[str] = set()

    def observe(key: str, depth: int, state_budget: int) -> None:
        atoms = tuple(candidate_groups[key])
        cone = compile_candidate_forward_cone(
            canonical_facts,
            atoms,
            theorem_tuple,
            targets=targets,
            max_rule_depth=depth,
            max_fragments=max_fragments,
            max_search_states=state_budget,
        )
        alignment = align_candidate_cone_to_proof_branches(cone, branches)
        previous = results.get(key)
        if previous is not None and _meet_quality(alignment) < _meet_quality(
            previous.alignment
        ):
            improvements[key] += 1
        if previous is not None and previous.exploration_rank < LazyProofDAGCandidateAlignment(
            alignment=alignment,
            predicate_distance=previous.predicate_distance,
            best_known_argument_overlap=previous.best_known_argument_overlap,
            fewest_missing_known_arguments=previous.fewest_missing_known_arguments,
            explored_depth=depth,
            search_states=0,
            stage_search_states=(),
            promoted=True,
            residual_improvements=improvements[key],
            truncated=cone.truncated,
        ).exploration_rank:
            alignment = previous.alignment
        distance, overlap, missing = _candidate_to_branch_gap(
            atoms, branches, distances
        )
        stage_states[key].append(cone.search_states)
        cones[key] = cone
        results[key] = LazyProofDAGCandidateAlignment(
            alignment=alignment,
            predicate_distance=distance,
            best_known_argument_overlap=overlap,
            fewest_missing_known_arguments=missing,
            explored_depth=depth,
            search_states=sum(stage_states[key]),
            stage_search_states=tuple(stage_states[key]),
            promoted=key in promoted_keys,
            residual_improvements=improvements[key],
            truncated=cone.truncated,
        )

    initial_depth = min(1, max_rule_depth)
    for key in sorted(candidate_groups):
        observe(key, initial_depth, initial_search_states)

    for depth in range(2, max_rule_depth + 1):
        ranked = sorted(
            candidate_groups,
            key=lambda key: (
                results[key].rank,
                results[key].exploration_rank,
                tiebreaks.get(key, ()),
                key,
            ),
        )
        promoted = ranked[: min(promotion_limit, len(ranked))]
        promoted_keys.update(promoted)
        for key in promoted:
            observe(key, depth, promoted_search_states)

    for key, result in tuple(results.items()):
        results[key] = LazyProofDAGCandidateAlignment(
            alignment=result.alignment,
            predicate_distance=result.predicate_distance,
            best_known_argument_overlap=result.best_known_argument_overlap,
            fewest_missing_known_arguments=result.fewest_missing_known_arguments,
            explored_depth=result.explored_depth,
            search_states=result.search_states,
            stage_search_states=result.stage_search_states,
            promoted=key in promoted_keys,
            residual_improvements=result.residual_improvements,
            truncated=result.truncated,
        )
    return results, cones


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
