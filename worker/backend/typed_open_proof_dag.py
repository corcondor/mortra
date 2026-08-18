"""Finite open AND-OR proof DAGs for typed auxiliary-construction search."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import hashlib
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
            "truncated": self.truncated,
            "branch_count": len(self.branches),
            "open_branch_count": len(self.open_branches),
            "unique_frontier_atom_count": len(self.unique_frontier_atoms),
            "branches": [branch.to_dict() for branch in self.branches],
        }


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

    canonical_facts = tuple(sorted({item.canonical() for item in facts}, key=_render_atom))
    canonical_candidates = tuple(
        sorted({item.canonical() for item in candidate_atoms}, key=_render_atom)
    )
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
        children: list[ForwardProofFragment] = []
        child_keys: set[tuple[Atom, tuple[Atom, ...], tuple[Atom, ...]]] = set()
        for parent in layer:
            if search_states >= max_search_states:
                truncated = True
                break
            for theorem, selected_index in ordered_index.get(
                parent.conclusion.predicate.lower(), ()
            ):
                serial += 1
                standardized = standardize_theorem_variables(theorem, serial)
                selected = standardized.premises[selected_index]
                for initial in symbolic_atom_unifications(selected, parent.conclusion):
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
                            partial = substitute_symbolic_atom(premise, substitution)
                            for known, is_candidate in known_by_predicate.get(
                                partial.predicate.lower(), ()
                            ):
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
                    if search_states >= max_search_states:
                        break
                if search_states >= max_search_states:
                    break
            if search_states >= max_search_states:
                break
        layer = deduplicate(children)
        fragments.extend(layer)
        if not layer or search_states >= max_search_states:
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
    serial = 0
    truncated = False

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
        return (
            len(variables),
            len(frontier),
            -len(item.matched_facts),
            -goal_overlap,
            tuple(_render_atom(atom) for atom in frontier),
            item.theorem_chain,
        )

    def deduplicate(items: Iterable[_PendingBranch]) -> list[_PendingBranch]:
        nonlocal truncated
        unique: dict[tuple[Atom, ...], _PendingBranch] = {}
        for item in sorted(items, key=pending_rank):
            frontier = _alpha_normalize_frontier(item.frontier)
            normalized = _PendingBranch(
                parent_id=item.parent_id,
                rule_depth=item.rule_depth,
                theorem_chain=item.theorem_chain,
                frontier=frontier,
                matched_facts=item.matched_facts,
            )
            unique.setdefault(frontier, normalized)
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
            for selected_index, selected in enumerate(branch.frontier):
                remaining = (
                    branch.frontier[:selected_index]
                    + branch.frontier[selected_index + 1 :]
                )
                for theorem in ordered_rules.get(selected.predicate.lower(), ()):
                    serial += 1
                    standardized = standardize_theorem_variables(theorem, serial)
                    for substitution in symbolic_atom_unifications(
                        selected, standardized.conclusion
                    ):
                        rule_unifications += 1
                        children.append(
                            _PendingBranch(
                                parent_id=branch.branch_id,
                                rule_depth=depth + 1,
                                theorem_chain=(*branch.theorem_chain, theorem.name),
                                frontier=_alpha_normalize_frontier(
                                    substitute_symbolic_atom(atom, substitution)
                                    for atom in (*standardized.premises, *remaining)
                                ),
                                matched_facts=branch.matched_facts,
                            )
                        )
                        if search_states + len(children) >= max_search_states:
                            truncated = True
                            break
                    if search_states + len(children) >= max_search_states:
                        break
                if search_states + len(children) >= max_search_states:
                    break
            if search_states + len(children) >= max_search_states:
                break
        layer = deduplicate(children)
        search_states += len(children)

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
        truncated=truncated,
    )
