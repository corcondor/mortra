"""Finite open AND-OR proof DAGs for typed auxiliary-construction search."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import hashlib
import time
from typing import Iterable

from worker.backend.geometry_proof_hypergraph import Atom, Theorem
from worker.backend.typed_logic_circuit import (
    standardize_theorem_variables,
    substitute_symbolic_atom,
    symbolic_atom_unifications,
)


EXECUTABLE_SIDE_CONDITION_PREDICATES = frozenset(
    {
        "diff",
        "ncoll",
        "npara",
        "nperp",
        "sameclock",
        "sameside",
        "nsameside",
        "obtuse_angle",
    }
)


def _is_variable(value: str) -> bool:
    return value.startswith("?")


def _render_atom(atom: Atom) -> str:
    return f"{atom.predicate}({','.join(atom.arguments)})"


def _alpha_normalize_frontier(atoms: Iterable[Atom]) -> tuple[Atom, ...]:
    return _alpha_normalize_atoms(atoms)


def _alpha_normalize_atoms(atoms: Iterable[Atom]) -> tuple[Atom, ...]:
    substitution: dict[str, str] = {}
    normalized: list[Atom] = []
    for atom in atoms:
        arguments: list[str] = []
        for argument in atom.arguments:
            if _is_variable(argument):
                substitution.setdefault(argument, f"?h{len(substitution)}")
                arguments.append(substitution[argument])
            else:
                arguments.append(argument)
        normalized.append(Atom(atom.predicate, tuple(arguments)).canonical())
    return tuple(sorted(set(normalized), key=_render_atom))


def alpha_normalize_symbolic_atoms(atoms: Iterable[Atom]) -> tuple[Atom, ...]:
    """Canonicalize a symbolic atom set while preserving shared hole identity."""

    return _alpha_normalize_atoms(atoms)


def _branch_id(
    parent_id: str | None,
    theorem_chain: tuple[str, ...],
    frontier: tuple[Atom, ...],
    rule_depth: int,
) -> str:
    material = "|".join(
        (
            parent_id or "root",
            str(rule_depth),
            *theorem_chain,
            *map(_render_atom, frontier),
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class OpenProofBranch:
    """One coherent AND frontier under one sequence of OR choices."""

    branch_id: str
    parent_id: str | None
    rule_depth: int
    theorem_chain: tuple[str, ...]
    frontier: tuple[Atom, ...]
    matched_facts: tuple[Atom, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "branch_id": self.branch_id,
            "parent_id": self.parent_id,
            "rule_depth": self.rule_depth,
            "theorem_chain": list(self.theorem_chain),
            "frontier": [_render_atom(atom) for atom in self.frontier],
            "matched_facts": [_render_atom(atom) for atom in self.matched_facts],
        }


@dataclass(frozen=True)
class OpenProofDAG:
    goal: Atom
    branches: tuple[OpenProofBranch, ...]
    unique_frontier_atoms: tuple[Atom, ...]
    max_rule_depth: int
    search_states: int
    fact_unifications: int
    rule_unifications: int
    rejected_nonprogressing_decompositions: int
    rejected_revisited_frontiers: int
    truncated: bool

    @property
    def open_branches(self) -> tuple[OpenProofBranch, ...]:
        return tuple(branch for branch in self.branches if branch.frontier)

    def to_dict(self) -> dict[str, object]:
        return {
            "goal": _render_atom(self.goal),
            "max_rule_depth": self.max_rule_depth,
            "search_states": self.search_states,
            "fact_unifications": self.fact_unifications,
            "rule_unifications": self.rule_unifications,
            "rejected_nonprogressing_decompositions": (
                self.rejected_nonprogressing_decompositions
            ),
            "rejected_revisited_frontiers": self.rejected_revisited_frontiers,
            "truncated": self.truncated,
            "branch_count": len(self.branches),
            "open_branch_count": len(self.open_branches),
            "unique_frontier_atom_count": len(self.unique_frontier_atoms),
            "branches": [branch.to_dict() for branch in self.branches],
        }


@dataclass(frozen=True)
class NativeProofDAGProgress:
    """Exact native-closure progress against coherent open proof branches.

    Numerical side conditions are deliberately excluded here: Newclid checks
    them against the constructed realization while applying a rule.  This
    score only measures whether a candidate added symbolic facts required by
    one and the same AND branch.  It is a search signal, never a proof result.
    """

    branch_count: int
    progressed_branch_count: int
    structurally_closed_branch_count: int
    best_structural_residual_count: int
    max_exact_covered_atoms: int
    unique_exact_covered_atoms: int
    support_improved_branch_count: int
    max_support_overlap_gain: int
    total_support_overlap_gain: int

    def to_dict(self) -> dict[str, int]:
        return {
            "branch_count": self.branch_count,
            "progressed_branch_count": self.progressed_branch_count,
            "structurally_closed_branch_count": (
                self.structurally_closed_branch_count
            ),
            "best_structural_residual_count": (
                self.best_structural_residual_count
            ),
            "max_exact_covered_atoms": self.max_exact_covered_atoms,
            "unique_exact_covered_atoms": self.unique_exact_covered_atoms,
            "support_improved_branch_count": self.support_improved_branch_count,
            "max_support_overlap_gain": self.max_support_overlap_gain,
            "total_support_overlap_gain": self.total_support_overlap_gain,
        }


@dataclass(frozen=True)
class NativeProofDAGIncrement:
    """Progress added by one construction relative to its parent state."""

    newly_progressed_branch_count: int
    newly_structurally_closed_branch_count: int
    max_exact_covered_atoms_gain: int
    unique_exact_covered_atoms_gain: int
    support_improved_branch_count_gain: int
    support_overlap_gain: int

    def to_dict(self) -> dict[str, int]:
        return {
            "newly_progressed_branch_count": self.newly_progressed_branch_count,
            "newly_structurally_closed_branch_count": (
                self.newly_structurally_closed_branch_count
            ),
            "max_exact_covered_atoms_gain": self.max_exact_covered_atoms_gain,
            "unique_exact_covered_atoms_gain": self.unique_exact_covered_atoms_gain,
            "support_improved_branch_count_gain": (
                self.support_improved_branch_count_gain
            ),
            "support_overlap_gain": self.support_overlap_gain,
        }


def native_proof_dag_increment(
    parent: NativeProofDAGProgress,
    child: NativeProofDAGProgress,
) -> NativeProofDAGIncrement:
    """Return monotone gains so inherited progress is not credited twice."""

    return NativeProofDAGIncrement(
        newly_progressed_branch_count=max(
            0,
            child.progressed_branch_count - parent.progressed_branch_count,
        ),
        newly_structurally_closed_branch_count=max(
            0,
            child.structurally_closed_branch_count
            - parent.structurally_closed_branch_count,
        ),
        max_exact_covered_atoms_gain=max(
            0,
            child.max_exact_covered_atoms - parent.max_exact_covered_atoms,
        ),
        unique_exact_covered_atoms_gain=max(
            0,
            child.unique_exact_covered_atoms - parent.unique_exact_covered_atoms,
        ),
        support_improved_branch_count_gain=max(
            0,
            child.support_improved_branch_count
            - parent.support_improved_branch_count,
        ),
        support_overlap_gain=max(
            0,
            child.total_support_overlap_gain - parent.total_support_overlap_gain,
        ),
    )


def assess_native_proof_dag_progress(
    facts: Iterable[Atom],
    branches: Iterable[OpenProofBranch],
    *,
    baseline_facts: Iterable[Atom] = (),
) -> NativeProofDAGProgress:
    """Measure exact fact coverage without flattening alternative branches."""

    known = {fact.canonical() for fact in facts}
    baseline = {fact.canonical() for fact in baseline_facts}
    known_by_predicate: dict[str, tuple[Atom, ...]] = {}
    baseline_by_predicate: dict[str, tuple[Atom, ...]] = {}
    for predicate in {atom.predicate for atom in known}:
        known_by_predicate[predicate] = tuple(
            atom for atom in known if atom.predicate == predicate
        )
    for predicate in {atom.predicate for atom in baseline}:
        baseline_by_predicate[predicate] = tuple(
            atom for atom in baseline if atom.predicate == predicate
        )
    branch_tuple = tuple(branches)
    progressed = 0
    structurally_closed = 0
    best_residual: int | None = None
    max_covered = 0
    covered_union: set[Atom] = set()
    support_improved = 0
    max_support_gain = 0
    total_support_gain = 0
    for branch in branch_tuple:
        structural = tuple(
            atom.canonical()
            for atom in branch.frontier
            if atom.predicate.lower()
            not in EXECUTABLE_SIDE_CONDITION_PREDICATES
        )
        covered = tuple(atom for atom in structural if atom in known)
        residual_count = len(structural) - len(covered)
        if covered:
            progressed += 1
            covered_union.update(covered)
        if structural and residual_count == 0:
            structurally_closed += 1
        branch_support_gain = 0
        for atom in structural:
            support = set(atom.arguments)
            current_overlap = max(
                (
                    len(support.intersection(candidate.arguments))
                    for candidate in known_by_predicate.get(atom.predicate, ())
                ),
                default=0,
            )
            baseline_overlap = max(
                (
                    len(support.intersection(candidate.arguments))
                    for candidate in baseline_by_predicate.get(atom.predicate, ())
                ),
                default=0,
            )
            branch_support_gain += max(0, current_overlap - baseline_overlap)
        if branch_support_gain:
            support_improved += 1
            total_support_gain += branch_support_gain
            max_support_gain = max(max_support_gain, branch_support_gain)
        if best_residual is None or residual_count < best_residual:
            best_residual = residual_count
        max_covered = max(max_covered, len(covered))
    return NativeProofDAGProgress(
        branch_count=len(branch_tuple),
        progressed_branch_count=progressed,
        structurally_closed_branch_count=structurally_closed,
        best_structural_residual_count=(
            best_residual if best_residual is not None else -1
        ),
        max_exact_covered_atoms=max_covered,
        unique_exact_covered_atoms=len(covered_union),
        support_improved_branch_count=support_improved,
        max_support_overlap_gain=max_support_gain,
        total_support_overlap_gain=total_support_gain,
    )


@dataclass(frozen=True)
class ForwardProofFragment:
    """A candidate-supported implication with explicit residual premises."""

    fragment_id: str
    parent_id: str | None
    rule_depth: int
    theorem_chain: tuple[str, ...]
    conclusion: Atom
    residual_frontier: tuple[Atom, ...]
    source_atoms: tuple[Atom, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "fragment_id": self.fragment_id,
            "parent_id": self.parent_id,
            "rule_depth": self.rule_depth,
            "theorem_chain": list(self.theorem_chain),
            "conclusion": _render_atom(self.conclusion),
            "residual_frontier": [
                _render_atom(atom) for atom in self.residual_frontier
            ],
            "source_atoms": [_render_atom(atom) for atom in self.source_atoms],
        }


@dataclass(frozen=True)
class CandidateForwardCone:
    candidate_atoms: tuple[Atom, ...]
    fragments: tuple[ForwardProofFragment, ...]
    max_rule_depth: int
    search_states: int
    rule_unifications: int
    fact_unifications: int
    truncated: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "candidate_atoms": [_render_atom(atom) for atom in self.candidate_atoms],
            "max_rule_depth": self.max_rule_depth,
            "search_states": self.search_states,
            "rule_unifications": self.rule_unifications,
            "fact_unifications": self.fact_unifications,
            "truncated": self.truncated,
            "fragment_count": len(self.fragments),
            "fragments": [fragment.to_dict() for fragment in self.fragments],
        }


@dataclass(frozen=True)
class _PendingBranch:
    parent_id: str | None
    rule_depth: int
    theorem_chain: tuple[str, ...]
    frontier: tuple[Atom, ...]
    matched_facts: tuple[Atom, ...]


@dataclass(frozen=True)
class DecompositionProgressReview:
    """Exact review of whether a backward rule changes the open proof state."""

    accepted: bool
    reason: str
    parent_frontier: tuple[Atom, ...]
    child_frontier: tuple[Atom, ...]


def review_decomposition_progress(
    parent_frontier: Iterable[Atom],
    child_frontier: Iterable[Atom],
) -> DecompositionProgressReview:
    """Reject theorem decompositions that only restate or enlarge a frontier.

    The proof state is the alpha-normalized conjunction of open obligations.
    Reaching the same state again cannot enable a new exact proof because facts
    and the theorem bank are fixed during compilation.  A strict superset is
    also non-progressing: it retains every old obligation and merely adds work.
    This is a symbolic analogue of LEAP's decomposition reviewer, but does not
    use an LLM or a problem-specific score.
    """

    parent = _alpha_normalize_frontier(parent_frontier)
    child = _alpha_normalize_frontier(child_frontier)
    if child == parent:
        return DecompositionProgressReview(
            False,
            "alpha_equivalent_frontier",
            parent,
            child,
        )
    if set(parent) < set(child):
        return DecompositionProgressReview(
            False,
            "strict_frontier_superset",
            parent,
            child,
        )
    return DecompositionProgressReview(True, "frontier_changed", parent, child)


def _normalize_fragment_atoms(
    conclusion: Atom,
    residual: Iterable[Atom],
) -> tuple[Atom, tuple[Atom, ...]]:
    substitution: dict[str, str] = {}

    def normalize(atom: Atom) -> Atom:
        arguments: list[str] = []
        for argument in atom.arguments:
            if _is_variable(argument):
                substitution.setdefault(argument, f"?h{len(substitution)}")
                arguments.append(substitution[argument])
            else:
                arguments.append(argument)
        return Atom(atom.predicate, tuple(arguments)).canonical()

    normalized_conclusion = normalize(conclusion)
    normalized_residual = tuple(
        sorted({normalize(atom) for atom in residual}, key=_render_atom)
    )
    return normalized_conclusion, normalized_residual


def _fragment_id(
    parent_id: str | None,
    theorem_chain: tuple[str, ...],
    conclusion: Atom,
    residual: tuple[Atom, ...],
    source_atoms: tuple[Atom, ...],
) -> str:
    material = "|".join(
        (
            parent_id or "candidate",
            *theorem_chain,
            _render_atom(conclusion),
            *map(_render_atom, residual),
            *map(_render_atom, source_atoms),
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


@lru_cache(maxsize=16)
def _cached_premise_index(
    theorems: tuple[Theorem, ...],
) -> dict[str, tuple[tuple[Theorem, int], ...]]:
    index: dict[str, list[tuple[Theorem, int]]] = {}
    for theorem in theorems:
        for premise_index, premise in enumerate(theorem.premises):
            index.setdefault(premise.predicate.lower(), []).append(
                (theorem, premise_index)
            )
    return {
        predicate: tuple(
            sorted(items, key=lambda item: (len(item[0].premises), item[0].name, item[1]))
        )
        for predicate, items in index.items()
    }


def compile_candidate_forward_cone(
    facts: Iterable[Atom],
    candidate_atoms: Iterable[Atom],
    theorems: Iterable[Theorem],
    *,
    targets: Iterable[Atom] = (),
    max_rule_depth: int = 2,
    max_fragments: int = 256,
    max_search_states: int = 10_000,
    max_residual_atoms: int = 6,
    max_wall_seconds: float | None = None,
) -> CandidateForwardCone:
    """Build finite candidate-supported proof fragments without asserting truth.

    A fragment means ``candidate atoms AND residual_frontier => conclusion``.
    Missing theorem premises stay explicit instead of being silently assumed.
    This permits a bounded meet with a backward proof branch while exact native
    certificate replay remains the only acceptance criterion.
    """

    if max_rule_depth < 0:
        raise ValueError("max_rule_depth must be non-negative")
    if max_fragments < 1 or max_search_states < 1:
        raise ValueError("search budgets must be positive")
    if max_residual_atoms < 0:
        raise ValueError("max_residual_atoms must be non-negative")
    if max_wall_seconds is not None and max_wall_seconds <= 0:
        raise ValueError("max_wall_seconds must be positive")

    deadline = (
        time.perf_counter() + max_wall_seconds
        if max_wall_seconds is not None
        else None
    )

    def wall_expired() -> bool:
        return deadline is not None and time.perf_counter() >= deadline

    canonical_candidates = tuple(
        sorted({item.canonical() for item in candidate_atoms}, key=_render_atom)
    )
    roots = [
        ForwardProofFragment(
            fragment_id=_fragment_id(None, (), atom, (), (atom,)),
            parent_id=None,
            rule_depth=0,
            theorem_chain=(),
            conclusion=atom,
            residual_frontier=(),
            source_atoms=(atom,),
        )
        for atom in canonical_candidates
    ]
    if max_rule_depth == 0:
        return CandidateForwardCone(
            candidate_atoms=canonical_candidates,
            fragments=tuple(roots),
            max_rule_depth=0,
            search_states=len(roots),
            rule_unifications=0,
            fact_unifications=0,
            truncated=False,
        )

    canonical_facts = tuple(sorted({item.canonical() for item in facts}, key=_render_atom))
    target_atoms = tuple(item.canonical() for item in targets)
    target_predicates = {item.predicate for item in target_atoms}
    target_arguments = {argument for item in target_atoms for argument in item.arguments}

    known_by_predicate: dict[str, tuple[tuple[Atom, bool], ...]] = {}
    for atom in (*canonical_facts, *canonical_candidates):
        known_by_predicate.setdefault(atom.predicate, tuple())
    for predicate in tuple(known_by_predicate):
        tagged = [
            *((atom, False) for atom in canonical_facts if atom.predicate == predicate),
            *((atom, True) for atom in canonical_candidates if atom.predicate == predicate),
        ]
        known_by_predicate[predicate] = tuple(dict.fromkeys(tagged))

    theorem_tuple = tuple(theorems)
    ordered_index = _cached_premise_index(theorem_tuple)

    fragments: list[ForwardProofFragment] = list(roots)
    layer = roots
    search_states = len(roots)
    rule_unifications = 0
    fact_unifications = 0
    serial = 0
    truncated = False

    def rank(fragment: ForwardProofFragment) -> tuple[object, ...]:
        holes = {
            argument
            for atom in (fragment.conclusion, *fragment.residual_frontier)
            for argument in atom.arguments
            if _is_variable(argument)
        }
        conclusion_overlap = len(
            set(fragment.conclusion.arguments).intersection(target_arguments)
        )
        structural_residual_count = sum(
            atom.predicate not in EXECUTABLE_SIDE_CONDITION_PREDICATES
            for atom in fragment.residual_frontier
        )
        return (
            0 if fragment.conclusion.predicate in target_predicates else 1,
            structural_residual_count,
            len(fragment.residual_frontier),
            len(holes),
            -len(fragment.source_atoms),
            -conclusion_overlap,
            fragment.rule_depth,
            _render_atom(fragment.conclusion),
            fragment.theorem_chain,
        )

    def deduplicate(items: Iterable[ForwardProofFragment]) -> list[ForwardProofFragment]:
        nonlocal truncated
        unique: dict[
            tuple[Atom, tuple[Atom, ...], tuple[Atom, ...]], ForwardProofFragment
        ] = {}
        for item in sorted(items, key=rank):
            key = (item.conclusion, item.residual_frontier, item.source_atoms)
            unique.setdefault(key, item)
        ranked = sorted(unique.values(), key=rank)
        if len(ranked) > max_fragments:
            truncated = True
        return ranked[:max_fragments]

    for depth in range(1, max_rule_depth + 1):
        if wall_expired():
            truncated = True
            break
        children: list[ForwardProofFragment] = []
        child_keys: set[tuple[Atom, tuple[Atom, ...], tuple[Atom, ...]]] = set()
        for parent in layer:
            if search_states >= max_search_states or wall_expired():
                truncated = True
                break
            for theorem, selected_index in ordered_index.get(
                parent.conclusion.predicate.lower(), ()
            ):
                if wall_expired():
                    truncated = True
                    break
                serial += 1
                standardized = standardize_theorem_variables(theorem, serial)
                selected = standardized.premises[selected_index]
                for initial in symbolic_atom_unifications(selected, parent.conclusion):
                    if wall_expired():
                        truncated = True
                        break
                    rule_unifications += 1
                    states: list[
                        tuple[dict[str, str], tuple[Atom, ...], frozenset[Atom]]
                    ] = [
                        (
                            initial,
                            tuple(
                                substitute_symbolic_atom(atom, initial)
                                for atom in parent.residual_frontier
                            ),
                            frozenset(parent.source_atoms),
                        )
                    ]
                    for index, premise in enumerate(standardized.premises):
                        if index == selected_index:
                            continue
                        next_states: list[
                            tuple[dict[str, str], tuple[Atom, ...], frozenset[Atom]]
                        ] = []
                        for substitution, residual, sources in states:
                            if wall_expired():
                                truncated = True
                                break
                            partial = substitute_symbolic_atom(premise, substitution)
                            for known, is_candidate in known_by_predicate.get(
                                partial.predicate.lower(), ()
                            ):
                                if wall_expired():
                                    truncated = True
                                    break
                                for merged in symbolic_atom_unifications(
                                    partial, known, substitution
                                ):
                                    fact_unifications += 1
                                    next_states.append(
                                        (
                                            merged,
                                            tuple(
                                                substitute_symbolic_atom(atom, merged)
                                                for atom in residual
                                            ),
                                            (
                                                sources | {known}
                                                if is_candidate
                                                else sources
                                            ),
                                        )
                                    )
                            if len(residual) < max_residual_atoms:
                                next_states.append(
                                    (substitution, (*residual, partial), sources)
                                )
                        states = sorted(
                            next_states,
                            key=lambda item: (
                                len(item[1]),
                                -len(item[2]),
                                tuple(sorted(item[0].items())),
                            ),
                        )[:64]
                        if not states:
                            break
                    for substitution, residual, sources in states:
                        if wall_expired():
                            truncated = True
                            break
                        conclusion = substitute_symbolic_atom(
                            standardized.conclusion, substitution
                        )
                        normalized_conclusion, normalized_residual = (
                            _normalize_fragment_atoms(conclusion, residual)
                        )
                        if len(normalized_residual) > max_residual_atoms:
                            continue
                        source_atoms = tuple(sorted(sources, key=_render_atom))
                        theorem_chain = (*parent.theorem_chain, theorem.name)
                        child = ForwardProofFragment(
                            fragment_id=_fragment_id(
                                parent.fragment_id,
                                theorem_chain,
                                normalized_conclusion,
                                normalized_residual,
                                source_atoms,
                            ),
                            parent_id=parent.fragment_id,
                            rule_depth=depth,
                            theorem_chain=theorem_chain,
                            conclusion=normalized_conclusion,
                            residual_frontier=normalized_residual,
                            source_atoms=source_atoms,
                        )
                        state_key = (
                            child.conclusion,
                            child.residual_frontier,
                            child.source_atoms,
                        )
                        if state_key in child_keys:
                            continue
                        child_keys.add(state_key)
                        children.append(child)
                        search_states += 1
                        if search_states >= max_search_states:
                            truncated = True
                            break
                    if search_states >= max_search_states or wall_expired():
                        break
                if search_states >= max_search_states or wall_expired():
                    break
            if search_states >= max_search_states or wall_expired():
                break
        layer = deduplicate(children)
        fragments.extend(layer)
        if not layer or search_states >= max_search_states or wall_expired():
            break

    return CandidateForwardCone(
        candidate_atoms=canonical_candidates,
        fragments=tuple(fragments),
        max_rule_depth=max_rule_depth,
        search_states=search_states,
        rule_unifications=rule_unifications,
        fact_unifications=fact_unifications,
        truncated=truncated,
    )


def compile_open_proof_dag(
    facts: Iterable[Atom],
    goal: Atom,
    theorems: Iterable[Theorem],
    *,
    max_rule_depth: int = 2,
    max_branches: int = 256,
    max_search_states: int = 10_000,
    max_wall_seconds: float | None = None,
    review_decompositions: bool = True,
    rank_by_predicate_distance: bool = True,
) -> OpenProofDAG:
    """Compile bounded partial proofs while preserving AND and OR structure.

    Every branch is one coherent sequence of OR rule choices. Its ``frontier``
    is the conjunction of still-open premises. Branches are never flattened
    together, so a construction cannot earn credit by satisfying premises from
    mutually incompatible proofs.
    """

    if max_rule_depth < 1:
        raise ValueError("max_rule_depth must be positive")
    if max_branches < 1 or max_search_states < 1:
        raise ValueError("search budgets must be positive")
    if max_wall_seconds is not None and max_wall_seconds <= 0:
        raise ValueError("max_wall_seconds must be positive")

    deadline = (
        time.perf_counter() + max_wall_seconds
        if max_wall_seconds is not None
        else None
    )

    canonical_facts = tuple(sorted({fact.canonical() for fact in facts}, key=_render_atom))
    facts_by_predicate = {
        predicate: tuple(
            fact for fact in canonical_facts if fact.predicate.lower() == predicate
        )
        for predicate in sorted({fact.predicate.lower() for fact in canonical_facts})
    }
    rules_by_predicate: dict[str, list[Theorem]] = {}
    for theorem in theorems:
        rules_by_predicate.setdefault(
            theorem.conclusion.predicate.lower(), []
        ).append(theorem)
    ordered_rules = {
        predicate: tuple(
            sorted(items, key=lambda item: (len(item.premises), item.name))
        )
        for predicate, items in rules_by_predicate.items()
    }

    # Verifier-derived control signal: estimate the finite AND-cost from each
    # relation kind to relation kinds already present in the proof state.  This
    # optimistic abstraction ignores point substitutions, so it can only rank
    # branches; exact fact closure remains the acceptance criterion.
    predicate_distance: dict[str, int] = {
        predicate: 0 for predicate in facts_by_predicate
    }
    all_predicates = set(predicate_distance) | set(ordered_rules)
    for theorem_items in ordered_rules.values():
        for theorem in theorem_items:
            all_predicates.update(
                premise.predicate.lower() for premise in theorem.premises
            )
    for _ in range(max(1, len(all_predicates))):
        changed = False
        for conclusion, theorem_items in ordered_rules.items():
            for theorem in theorem_items:
                premise_distances = [
                    predicate_distance.get(premise.predicate.lower())
                    for premise in theorem.premises
                ]
                if any(item is None for item in premise_distances):
                    continue
                candidate = 1 + sum(
                    item for item in premise_distances if item is not None
                )
                previous = predicate_distance.get(conclusion)
                if previous is None or candidate < previous:
                    predicate_distance[conclusion] = candidate
                    changed = True
        if not changed:
            break

    root_goal = goal.canonical()
    layer = [
        _PendingBranch(
            parent_id=None,
            rule_depth=0,
            theorem_chain=(),
            frontier=(root_goal,),
            matched_facts=(),
        )
    ]
    branches: list[OpenProofBranch] = []
    search_states = 0
    fact_unifications = 0
    rule_unifications = 0
    rejected_nonprogressing_decompositions = 0
    rejected_revisited_frontiers = 0
    serial = 0
    truncated = False
    minimum_frontier_depth: dict[tuple[Atom, ...], int] = {}

    def wall_budget_exhausted() -> bool:
        nonlocal truncated
        if deadline is None or time.perf_counter() < deadline:
            return False
        truncated = True
        return True

    def pending_rank(item: _PendingBranch) -> tuple[object, ...]:
        frontier = _alpha_normalize_frontier(item.frontier)
        variables = {
            argument
            for atom in frontier
            for argument in atom.arguments
            if _is_variable(argument)
        }
        ground_arguments = {
            argument
            for atom in frontier
            for argument in atom.arguments
            if not _is_variable(argument)
        }
        goal_overlap = len(ground_arguments.intersection(root_goal.arguments))
        distances = [predicate_distance.get(atom.predicate.lower()) for atom in frontier]
        unreachable = sum(distance is None for distance in distances)
        proof_distance = sum(
            distance for distance in distances if distance is not None
        )
        return (
            unreachable if rank_by_predicate_distance else 0,
            proof_distance if rank_by_predicate_distance else 0,
            len(variables),
            len(frontier),
            -len(item.matched_facts),
            -goal_overlap,
            tuple(_render_atom(atom) for atom in frontier),
            item.theorem_chain,
        )

    def deduplicate(items: Iterable[_PendingBranch]) -> list[_PendingBranch]:
        nonlocal truncated, rejected_revisited_frontiers
        unique: dict[tuple[Atom, ...], _PendingBranch] = {}
        for item in sorted(items, key=pending_rank):
            frontier = _alpha_normalize_frontier(item.frontier)
            previous_depth = minimum_frontier_depth.get(frontier)
            if (
                review_decompositions
                and previous_depth is not None
                and previous_depth < item.rule_depth
            ):
                rejected_revisited_frontiers += 1
                continue
            normalized = _PendingBranch(
                parent_id=item.parent_id,
                rule_depth=item.rule_depth,
                theorem_chain=item.theorem_chain,
                frontier=frontier,
                matched_facts=item.matched_facts,
            )
            unique.setdefault(frontier, normalized)
        for frontier, item in unique.items():
            previous_depth = minimum_frontier_depth.get(frontier)
            if previous_depth is None or item.rule_depth < previous_depth:
                minimum_frontier_depth[frontier] = item.rule_depth
        ranked = sorted(unique.values(), key=pending_rank)
        if len(ranked) > max_branches:
            truncated = True
        return ranked[:max_branches]

    def close_known(item: _PendingBranch) -> list[_PendingBranch]:
        nonlocal fact_unifications, search_states, truncated
        active = [item]
        closed: list[_PendingBranch] = []
        seen: set[tuple[Atom, ...]] = set()
        while active and search_states < max_search_states:
            if wall_budget_exhausted():
                closed.extend(active)
                active.clear()
                break
            current = active.pop()
            search_states += 1
            frontier = _alpha_normalize_frontier(current.frontier)
            if frontier in seen:
                continue
            seen.add(frontier)
            fact_children: list[_PendingBranch] = []
            for selected_index, selected in enumerate(frontier):
                remaining = frontier[:selected_index] + frontier[selected_index + 1 :]
                for fact in facts_by_predicate.get(selected.predicate.lower(), ()):
                    if wall_budget_exhausted():
                        closed.append(current)
                        active.clear()
                        return closed
                    for substitution in symbolic_atom_unifications(selected, fact):
                        fact_unifications += 1
                        fact_children.append(
                            _PendingBranch(
                                parent_id=current.parent_id,
                                rule_depth=current.rule_depth,
                                theorem_chain=current.theorem_chain,
                                frontier=_alpha_normalize_frontier(
                                    substitute_symbolic_atom(rest, substitution)
                                    for rest in remaining
                                ),
                                matched_facts=tuple(
                                    sorted(
                                        {*current.matched_facts, fact},
                                        key=_render_atom,
                                    )
                                ),
                            )
                        )
                if fact_children:
                    break
            if fact_children:
                active.extend(fact_children)
            else:
                closed.append(
                    _PendingBranch(
                        parent_id=current.parent_id,
                        rule_depth=current.rule_depth,
                        theorem_chain=current.theorem_chain,
                        frontier=frontier,
                        matched_facts=current.matched_facts,
                    )
                )
        if active:
            truncated = True
        return closed

    for depth in range(max_rule_depth + 1):
        if wall_budget_exhausted():
            break
        closed_layer: list[_PendingBranch] = []
        for pending in layer:
            if search_states >= max_search_states:
                truncated = True
                break
            closed_layer.extend(close_known(pending))
        layer = deduplicate(closed_layer)
        current_branches: list[OpenProofBranch] = []
        for pending in layer:
            branch_id = _branch_id(
                pending.parent_id,
                pending.theorem_chain,
                pending.frontier,
                pending.rule_depth,
            )
            current_branches.append(
                OpenProofBranch(
                    branch_id=branch_id,
                    parent_id=pending.parent_id,
                    rule_depth=pending.rule_depth,
                    theorem_chain=pending.theorem_chain,
                    frontier=pending.frontier,
                    matched_facts=pending.matched_facts,
                )
            )
        if depth > 0:
            branches.extend(current_branches)
        if depth == max_rule_depth or search_states >= max_search_states:
            break

        children: list[_PendingBranch] = []
        for branch in current_branches:
            if wall_budget_exhausted():
                break
            for selected_index, selected in enumerate(branch.frontier):
                remaining = (
                    branch.frontier[:selected_index]
                    + branch.frontier[selected_index + 1 :]
                )
                for theorem in ordered_rules.get(selected.predicate.lower(), ()):
                    if wall_budget_exhausted():
                        break
                    serial += 1
                    standardized = standardize_theorem_variables(theorem, serial)
                    for substitution in symbolic_atom_unifications(
                        selected, standardized.conclusion
                    ):
                        rule_unifications += 1
                        child_frontier = _alpha_normalize_frontier(
                            substitute_symbolic_atom(atom, substitution)
                            for atom in (*standardized.premises, *remaining)
                        )
                        if review_decompositions:
                            review = review_decomposition_progress(
                                branch.frontier,
                                child_frontier,
                            )
                            if not review.accepted:
                                rejected_nonprogressing_decompositions += 1
                                continue
                        children.append(
                            _PendingBranch(
                                parent_id=branch.branch_id,
                                rule_depth=depth + 1,
                                theorem_chain=(*branch.theorem_chain, theorem.name),
                                frontier=child_frontier,
                                matched_facts=branch.matched_facts,
                            )
                        )
                        if search_states + len(children) >= max_search_states:
                            truncated = True
                            break
                    if search_states + len(children) >= max_search_states:
                        break
                if wall_budget_exhausted():
                    break
                if search_states + len(children) >= max_search_states:
                    break
            if search_states + len(children) >= max_search_states:
                break
        layer = deduplicate(children)
        search_states += len(children)
        if (search_states >= max_search_states or wall_budget_exhausted()) and layer:
            # These theorem applications are valid partial proof branches even
            # when either budget ends before the next fact-closing pass. Keep
            # them as scheduling evidence; proof acceptance still requires
            # native certificate replay.
            for pending in layer:
                branch_id = _branch_id(
                    pending.parent_id,
                    pending.theorem_chain,
                    pending.frontier,
                    pending.rule_depth,
                )
                branches.append(
                    OpenProofBranch(
                        branch_id=branch_id,
                        parent_id=pending.parent_id,
                        rule_depth=pending.rule_depth,
                        theorem_chain=pending.theorem_chain,
                        frontier=pending.frontier,
                        matched_facts=pending.matched_facts,
                    )
                )

    unique_atoms = tuple(
        sorted(
            {atom for branch in branches for atom in branch.frontier},
            key=_render_atom,
        )
    )
    return OpenProofDAG(
        goal=goal.canonical(),
        branches=tuple(branches),
        unique_frontier_atoms=unique_atoms,
        max_rule_depth=max_rule_depth,
        search_states=search_states,
        fact_unifications=fact_unifications,
        rule_unifications=rule_unifications,
        rejected_nonprogressing_decompositions=(
            rejected_nonprogressing_decompositions
        ),
        rejected_revisited_frontiers=rejected_revisited_frontiers,
        truncated=truncated,
    )
