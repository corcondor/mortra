"""Finite typed theorem-hypergraph search for Euclidean predicates.

The engine is deliberately independent of benchmark questions.  A theorem is
a typed Horn hyperedge from premise atoms to one conclusion atom.  Search uses
a backward relevance slice from the requested goal and forward saturation from
the given facts.  Every accepted goal carries a replayable proof DAG.

This is the symbolic common denominator of FormalGeo's forward/backward search,
AutoGPS's proof graph, and the symbolic half of neural-symbolic geometry
systems.  It contains no language model and no answer oracle.
"""

from __future__ import annotations

from array import array
from bisect import bisect_left
from dataclasses import dataclass
from functools import lru_cache
from itertools import permutations
import time
from typing import Iterable, Iterator, Mapping


_EQANGLE_GENERATORS: tuple[tuple[int, ...], ...] = (
    (1, 0, 2, 3, 4, 5, 6, 7),
    (0, 1, 3, 2, 4, 5, 6, 7),
    (0, 1, 2, 3, 5, 4, 6, 7),
    (0, 1, 2, 3, 4, 5, 7, 6),
    (2, 3, 0, 1, 6, 7, 4, 5),
    (4, 5, 6, 7, 0, 1, 2, 3),
    (0, 1, 4, 5, 2, 3, 6, 7),
    (6, 7, 2, 3, 4, 5, 0, 1),
)


def _permutation_group(
    generators: tuple[tuple[int, ...], ...],
) -> tuple[tuple[int, ...], ...]:
    identity = tuple(range(len(generators[0])))
    group = {identity}
    frontier = [identity]
    while frontier:
        current = frontier.pop()
        for generator in generators:
            composed = tuple(current[generator[index]] for index in identity)
            if composed not in group:
                group.add(composed)
                frontier.append(composed)
    return tuple(sorted(group))


_EQANGLE_GROUP = _permutation_group(_EQANGLE_GENERATORS)


@lru_cache(maxsize=65536)
def _eqangle_argument_orbit(args: tuple[str, ...]) -> tuple[tuple[str, ...], ...]:
    if len(args) != 8:
        return (args,)
    return tuple(
        sorted({tuple(args[permutation[index]] for index in range(8)) for permutation in _EQANGLE_GROUP})
    )


@dataclass(frozen=True, order=True)
class Atom:
    predicate: str
    arguments: tuple[str, ...]

    @lru_cache(maxsize=65536)
    def canonical(self) -> "Atom":
        name = self.predicate.lower()
        args = self.arguments
        if name in {"para", "perp", "cong", "npara", "nperp"} and len(args) == 4:
            left = tuple(sorted(args[:2]))
            right = tuple(sorted(args[2:]))
            first, second = sorted((left, right))
            args = (*first, *second)
        elif name in {"coll", "cyclic", "ncoll", "diff"}:
            args = tuple(sorted(args))
        elif name in {"eqangle", "eqratio"} and len(args) == 8:
            args = min(_eqangle_argument_orbit(args))
        return Atom(name, tuple(args))


@dataclass(frozen=True)
class Theorem:
    name: str
    premises: tuple[Atom, ...]
    conclusion: Atom


@dataclass(frozen=True)
class ProofStep:
    atom: Atom
    theorem: str
    premises: tuple[Atom, ...]
    depth: int


@dataclass(frozen=True)
class HypergraphProof:
    goal: Atom
    steps: tuple[ProofStep, ...]
    rounds: int
    explored_hyperedges: int
    relevant_theorems: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "goal": _render_atom(self.goal),
            "rounds": self.rounds,
            "explored_hyperedges": self.explored_hyperedges,
            "relevant_theorems": list(self.relevant_theorems),
            "steps": [
                {
                    "atom": _render_atom(step.atom),
                    "theorem": step.theorem,
                    "premises": [_render_atom(item) for item in step.premises],
                    "depth": step.depth,
                }
                for step in self.steps
            ],
        }


@dataclass(frozen=True)
class BackwardObligation:
    """A theorem instance whose conclusion is the goal and premises stay open.

    Variables not fixed by the goal or visible facts remain explicit typed
    holes.  The object is a search proposal only: it never certifies a proof.
    """

    theorem: str
    goal: Atom
    matched_premises: tuple[Atom, ...]
    open_premises: tuple[Atom, ...]
    substitution: tuple[tuple[str, str], ...]
    unbound_variables: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "theorem": self.theorem,
            "goal": _render_atom(self.goal),
            "matched_premises": [_render_atom(item) for item in self.matched_premises],
            "open_premises": [_render_atom(item) for item in self.open_premises],
            "substitution": dict(self.substitution),
            "unbound_variables": list(self.unbound_variables),
        }


Substitution = dict[str, str]


class _FactIndex:
    """Exact positional index for symmetry-aware premise unification.

    ``_unify_all`` remains the final matcher.  The index only removes facts
    that cannot match any argument orbit under the current substitution.
    """

    def __init__(self, facts: Iterable[Atom]) -> None:
        # Process one predicate bucket at a time instead of retaining a global
        # canonical set, a second global sorted tuple, and all posting lists.
        canonical_by_predicate: dict[str, set[Atom]] = {}
        for fact in facts:
            canonical = fact.canonical()
            canonical_by_predicate.setdefault(
                canonical.predicate.lower(), set()
            ).add(canonical)

        by_predicate: dict[str, tuple[Atom, ...]] = {}
        by_position: dict[tuple[str, int, int, str], array[int]] = {}
        predicates = sorted(
            canonical_by_predicate,
            key=lambda predicate: (-len(canonical_by_predicate[predicate]), predicate),
        )
        for predicate in predicates:
            ordered = tuple(sorted(canonical_by_predicate.pop(predicate), key=_render_atom))
            by_predicate[predicate] = ordered
            for fact_index, fact in enumerate(ordered):
                arity = len(fact.arguments)
                for position, value in enumerate(fact.arguments):
                    by_position.setdefault(
                        (predicate, arity, position, value), array("I")
                    ).append(fact_index)
        self.by_predicate = by_predicate
        self.by_position = by_position

    def candidates(
        self,
        pattern: Atom,
        substitution: Mapping[str, str],
    ) -> tuple[Atom, ...]:
        predicate = pattern.predicate.lower()
        facts = self.by_predicate.get(predicate, ())
        if not facts:
            return ()

        possible: set[int] = set()
        for pattern_args in _argument_orbit(pattern):
            constraints: list[array[int]] = []
            for position, expected in enumerate(pattern_args):
                value = substitution.get(expected) if _is_variable(expected) else expected
                if value is None:
                    continue
                posting = self.by_position.get(
                    (predicate, len(pattern_args), position, value)
                )
                if not posting:
                    constraints = []
                    break
                constraints.append(posting)
            else:
                if not constraints:
                    return facts
                smallest, *rest = sorted(constraints, key=len)
                matches = {
                    index
                    for index in smallest
                    if all(
                        (offset := bisect_left(posting, index)) < len(posting)
                        and posting[offset] == index
                        for posting in rest
                    )
                }
                possible.update(matches)

        if not possible:
            return ()
        return tuple(facts[index] for index in sorted(possible))


def _is_variable(value: str) -> bool:
    return value.startswith("?")


def _render_atom(atom: Atom) -> str:
    return f"{atom.predicate}({','.join(atom.arguments)})"


@lru_cache(maxsize=65536)
def _argument_orbit(atom: Atom) -> tuple[tuple[str, ...], ...]:
    """Return the finite symmetry orbit of a relation's arguments.

    Canonicalizing a ground atom is not sufficient for theorem patterns: a
    substitution fixed by an earlier premise may require the opposite line or
    endpoint orientation in a later premise.  Enumerating this small orbit
    makes unification invariant to point naming without adding theorem copies.
    """
    name = atom.predicate.lower()
    args = atom.arguments
    if name in {"para", "perp", "cong", "npara", "nperp", "eqpoint"} and len(args) == 4:
        first = (args[0], args[1])
        second = (args[2], args[3])
        variants = {
            (*left, *right)
            for left, right in ((first, second), (second, first))
            for left in (left, left[::-1])
            for right in (right, right[::-1])
        }
        return tuple(sorted(variants))
    if name in {"coll", "cyclic", "ncoll"}:
        return tuple(sorted(set(permutations(args))))
    if name in {"eqangle", "eqratio"}:
        return _eqangle_argument_orbit(args)
    return (args,)


def _unify_all(
    pattern: Atom,
    ground: Atom,
    initial: Mapping[str, str] | None = None,
) -> Iterator[Substitution]:
    if pattern.predicate.lower() != ground.predicate.lower() or len(pattern.arguments) != len(ground.arguments):
        return
    ground_args = ground.canonical().arguments
    yielded: set[tuple[tuple[str, str], ...]] = set()
    for pattern_args in _argument_orbit(pattern):
        substitution = dict(initial or {})
        valid = True
        for expected, actual in zip(pattern_args, ground_args):
            if _is_variable(expected):
                previous = substitution.get(expected)
                if previous is not None and previous != actual:
                    valid = False
                    break
                substitution[expected] = actual
            elif expected != actual:
                valid = False
                break
        if not valid:
            continue
        key = tuple(sorted(substitution.items()))
        if key not in yielded:
            yielded.add(key)
            yield substitution


def _unify(pattern: Atom, ground: Atom, initial: Mapping[str, str] | None = None) -> Substitution | None:
    return next(_unify_all(pattern, ground, initial), None)


def atom_pattern_unifications(
    pattern: Atom,
    ground: Atom,
    initial: Mapping[str, str] | None = None,
) -> tuple[tuple[tuple[str, str], ...], ...]:
    """Return all finite symmetry-aware substitutions for a typed atom."""

    return tuple(
        tuple(sorted(substitution.items()))
        for substitution in _unify_all(pattern, ground, initial)
    )


def _instantiate(pattern: Atom, substitution: Mapping[str, str]) -> Atom | None:
    values: list[str] = []
    for value in pattern.arguments:
        if _is_variable(value):
            if value not in substitution:
                return None
            values.append(substitution[value])
        else:
            values.append(value)
    return Atom(pattern.predicate, tuple(values)).canonical()


def _instantiate_partial(pattern: Atom, substitution: Mapping[str, str]) -> Atom:
    return Atom(
        pattern.predicate,
        tuple(
            substitution.get(value, value) if _is_variable(value) else value
            for value in pattern.arguments
        ),
    ).canonical()


def _obligation_rank(item: BackwardObligation) -> tuple[int, int, int, int, str]:
    goal_points = set(item.goal.arguments)
    open_points = {
        point
        for premise in item.open_premises
        for point in premise.arguments
        if not _is_variable(point)
    }
    return (
        len(item.unbound_variables),
        len(item.open_premises),
        -len(item.matched_premises),
        -len(goal_points & open_points),
        item.theorem,
    )


def synthesize_backward_obligations(
    facts: Iterable[Atom],
    goal: Atom,
    theorems: Iterable[Theorem],
    *,
    max_open_premises: int = 4,
    max_states_per_rule: int = 256,
    max_results: int = 64,
    deadline: float | None = None,
) -> tuple[BackwardObligation, ...]:
    """Instantiate missing theorem premises from a fixed typed rule bank.

    The search is finite and label independent.  It unifies a requested goal
    with every theorem conclusion, then joins any subset of premises against
    visible facts.  Remaining premises become typed holes; no hidden
    auxiliary construction or benchmark identifier is consulted.
    """

    known = {fact.canonical() for fact in facts}
    fact_index = _FactIndex(known)
    wanted = goal.canonical()
    theorem_index: dict[tuple[str, int], list[Theorem]] = {}
    for theorem in theorems:
        conclusion = theorem.conclusion
        theorem_index.setdefault(
            (conclusion.predicate.lower(), len(conclusion.arguments)), []
        ).append(theorem)
    results: dict[
        tuple[str, tuple[Atom, ...], tuple[tuple[str, str], ...]], BackwardObligation
    ] = {}
    def current_results() -> tuple[BackwardObligation, ...]:
        return tuple(sorted(results.values(), key=_obligation_rank)[:max_results])

    def expired() -> bool:
        return deadline is not None and time.perf_counter() >= deadline

    for theorem in theorem_index.get(
        (wanted.predicate.lower(), len(wanted.arguments)), ()
    ):
        if expired():
            return current_results()
        for initial in _unify_all(theorem.conclusion, wanted):
            if expired():
                return current_results()
            states: list[tuple[Substitution, tuple[Atom, ...], tuple[Atom, ...]]] = [
                (initial, (), ())
            ]
            for premise in theorem.premises:
                if expired():
                    return current_results()
                next_states: list[
                    tuple[Substitution, tuple[Atom, ...], tuple[Atom, ...]]
                ] = []
                for substitution, matched, opened in states:
                    if expired():
                        return current_results()
                    for fact in fact_index.candidates(premise, substitution):
                        if expired():
                            return current_results()
                        for merged in _unify_all(premise, fact, substitution):
                            next_states.append((merged, (*matched, fact), opened))
                    if len(opened) < max_open_premises:
                        next_states.append((substitution, matched, (*opened, premise)))
                deduplicated: dict[
                    tuple[
                        tuple[tuple[str, str], ...], tuple[Atom, ...], tuple[Atom, ...]
                    ],
                    tuple[Substitution, tuple[Atom, ...], tuple[Atom, ...]],
                ] = {}
                for state in next_states:
                    substitution, matched, opened = state
                    key = (
                        tuple(sorted(substitution.items())),
                        tuple(sorted(set(matched))),
                        opened,
                    )
                    deduplicated.setdefault(key, state)
                states = sorted(
                    deduplicated.values(),
                    key=lambda state: (
                        len(state[2]),
                        -len(state[1]),
                        tuple(sorted(state[0].items())),
                    ),
                )[:max_states_per_rule]
                if not states:
                    break
            for substitution, matched, opened in states:
                open_premises = tuple(
                    _instantiate_partial(premise, substitution) for premise in opened
                )
                if not open_premises or any(item in known for item in open_premises):
                    continue
                unbound = tuple(
                    sorted(
                        {
                            argument
                            for premise in open_premises
                            for argument in premise.arguments
                            if _is_variable(argument)
                        }
                    )
                )
                item = BackwardObligation(
                    theorem=theorem.name,
                    goal=wanted,
                    matched_premises=tuple(sorted(set(matched))),
                    open_premises=open_premises,
                    substitution=tuple(sorted(substitution.items())),
                    unbound_variables=unbound,
                )
                key = (item.theorem, item.open_premises, item.substitution)
                previous = results.get(key)
                if previous is None or _obligation_rank(item) < _obligation_rank(previous):
                    results[key] = item
    return current_results()


def stratify_backward_obligations(
    obligations: Iterable[BackwardObligation],
    *,
    limit: int,
    witness_fraction: float = 0.25,
) -> tuple[BackwardObligation, ...]:
    """Preserve existential proof branches under a fixed finite budget.

    Ground branches and branches with typed witness holes are alternative OR
    paths.  A global rank by fewest unbound variables can otherwise erase all
    constructive paths before an auxiliary-point search sees them.  This
    scheduler reserves a bounded fraction for witness-bearing alternatives;
    it neither asserts that a witness exists nor changes the truth plane.
    """

    if limit < 1:
        raise ValueError("limit must be positive")
    if not 0.0 <= witness_fraction <= 1.0:
        raise ValueError("witness_fraction must be in [0, 1]")
    ranked = tuple(sorted(obligations, key=_obligation_rank))
    ground = [item for item in ranked if not item.unbound_variables]
    witness = [item for item in ranked if item.unbound_variables]
    witness_budget = (
        min(len(witness), max(1, round(limit * witness_fraction)))
        if witness and witness_fraction > 0.0
        else 0
    )
    ground_budget = min(len(ground), limit - witness_budget)
    spare = limit - ground_budget - witness_budget
    if spare > 0:
        extra_ground = min(spare, len(ground) - ground_budget)
        ground_budget += extra_ground
        spare -= extra_ground
    if spare > 0:
        witness_budget += min(spare, len(witness) - witness_budget)

    selected_ground = ground[:ground_budget]
    selected_witness = witness[:witness_budget]
    result: list[BackwardObligation] = []
    ground_index = 0
    witness_index = 0
    # At 25%, place one witness branch after every three ground branches so
    # a later atom-level cap cannot erase all constructive alternatives.
    stride = max(
        1,
        round((1.0 - witness_fraction) / max(witness_fraction, 1e-9)),
    )
    while ground_index < len(selected_ground) or witness_index < len(selected_witness):
        for _ in range(stride):
            if ground_index >= len(selected_ground):
                break
            result.append(selected_ground[ground_index])
            ground_index += 1
        if witness_index < len(selected_witness):
            result.append(selected_witness[witness_index])
            witness_index += 1
    return tuple(result[:limit])


def matched_theorem_support_facts(
    facts: Iterable[Atom],
    goals: Iterable[Atom],
    theorems: Iterable[Theorem],
    *,
    max_matches: int = 256,
) -> tuple[Atom, ...]:
    """Return ground premises of complete theorem matches feeding the goals.

    ``synthesize_backward_obligations`` intentionally omits a theorem instance
    once all of its premises are already known.  Fact-basis compression still
    needs those premises, otherwise a large native closure can discard the
    very support that closes the goal.  This helper exposes only matched input
    facts; it does not certify or add any conclusion.
    """

    known = {item.canonical() for item in facts}
    fact_index = _predicate_fact_index(known)
    support: set[Atom] = set()
    matches = 0
    for goal in goals:
        wanted = goal.canonical()
        for theorem in theorems:
            for initial in _unify_all(theorem.conclusion, wanted):
                for _, matched in _premise_matches(
                    theorem.premises,
                    known,
                    substitution=initial,
                    fact_index=fact_index,
                ):
                    support.update(item.canonical() for item in matched)
                    matches += 1
                    if matches >= max_matches:
                        return tuple(sorted(support, key=_render_atom))
    return tuple(sorted(support, key=_render_atom))


def _predicate_fact_index(facts: Iterable[Atom]) -> dict[str, tuple[Atom, ...]]:
    grouped: dict[str, list[Atom]] = {}
    for fact in facts:
        canonical = fact.canonical()
        grouped.setdefault(canonical.predicate, []).append(canonical)
    return {
        predicate: tuple(sorted(items, key=_render_atom))
        for predicate, items in grouped.items()
    }


def _premise_matches(
    premises: tuple[Atom, ...],
    facts: set[Atom],
    index: int = 0,
    substitution: Substitution | None = None,
    fact_index: Mapping[str, tuple[Atom, ...]] | None = None,
    candidate_budget: list[int] | None = None,
    deadline: float | None = None,
) -> Iterator[tuple[Substitution, tuple[Atom, ...]]]:
    if deadline is not None and time.perf_counter() >= deadline:
        return
    if fact_index is None:
        fact_index = _predicate_fact_index(facts)
    if index == len(premises):
        yield dict(substitution or {}), ()
        return
    pattern = premises[index]
    for fact in fact_index.get(pattern.canonical().predicate, ()):
        if deadline is not None and time.perf_counter() >= deadline:
            return
        if candidate_budget is not None:
            if candidate_budget[0] <= 0:
                return
            candidate_budget[0] -= 1
        for merged in _unify_all(pattern, fact, substitution):
            for final, tail in _premise_matches(
                premises,
                facts,
                index + 1,
                merged,
                fact_index,
                candidate_budget,
                deadline,
            ):
                yield final, (fact,) + tail


def _backward_relevant(
    goal: Atom,
    theorems: tuple[Theorem, ...],
    max_depth: int,
    *,
    deadline: float | None = None,
) -> set[str]:
    relevant: set[str] = set()
    frontier = {goal.canonical()}
    seen = set(frontier)
    for _ in range(max_depth):
        if deadline is not None and time.perf_counter() >= deadline:
            break
        next_frontier: set[Atom] = set()
        for wanted in frontier:
            if deadline is not None and time.perf_counter() >= deadline:
                break
            for theorem in theorems:
                if deadline is not None and time.perf_counter() >= deadline:
                    break
                substitution = _unify(theorem.conclusion, wanted)
                if substitution is None:
                    continue
                relevant.add(theorem.name)
                for premise in theorem.premises:
                    instantiated = _instantiate(premise, substitution)
                    if instantiated is not None and instantiated not in seen:
                        seen.add(instantiated)
                        next_frontier.add(instantiated)
        frontier = next_frontier
        if not frontier:
            break
    return relevant


def _dependency_rank(
    conclusion: Atom,
    premises: tuple[Atom, ...],
    goal: Atom,
    existing_entities: set[str],
) -> tuple[int, int, int, str]:
    goal_entities = set(goal.arguments)
    overlap = len(goal_entities & set(conclusion.arguments))
    introduced = len(set(conclusion.arguments) - existing_entities)
    premise_overlap = sum(len(goal_entities & set(item.arguments)) for item in premises)
    return (-overlap, introduced, -premise_overlap, _render_atom(conclusion))


class BidirectionalHypergraphProver:
    def __init__(self, theorems: Iterable[Theorem]) -> None:
        self.theorems = tuple(theorems)

    def prove(
        self,
        facts: Iterable[Atom],
        goal: Atom,
        *,
        max_rounds: int = 12,
        deadline: float | None = None,
    ) -> HypergraphProof | None:
        goal = goal.canonical()
        known = {fact.canonical() for fact in facts}
        proof: dict[Atom, ProofStep] = {
            fact: ProofStep(fact, "given", (), 0) for fact in known
        }
        if goal in known:
            return HypergraphProof(goal, (proof[goal],), 0, 0, ())

        if deadline is not None and time.perf_counter() >= deadline:
            return None
        relevant_names = _backward_relevant(
            goal,
            self.theorems,
            max_rounds,
            deadline=deadline,
        )
        rules = tuple(rule for rule in self.theorems if rule.name in relevant_names)
        explored = 0
        for round_index in range(1, max_rounds + 1):
            if deadline is not None and time.perf_counter() >= deadline:
                return None
            candidates: list[tuple[tuple[int, int, int, str], Atom, Theorem, tuple[Atom, ...]]] = []
            existing_entities = {arg for atom in known for arg in atom.arguments}
            fact_index = _predicate_fact_index(known)
            for theorem in rules:
                if deadline is not None and time.perf_counter() >= deadline:
                    return None
                for substitution, matched in _premise_matches(
                    theorem.premises,
                    known,
                    fact_index=fact_index,
                    deadline=deadline,
                ):
                    if deadline is not None and time.perf_counter() >= deadline:
                        return None
                    explored += 1
                    conclusion = _instantiate(theorem.conclusion, substitution)
                    if conclusion is None or conclusion in known:
                        continue
                    rank = _dependency_rank(conclusion, matched, goal, existing_entities)
                    candidates.append((rank, conclusion, theorem, matched))
            if not candidates:
                return None
            candidates.sort(key=lambda item: item[0])
            additions: dict[Atom, tuple[Theorem, tuple[Atom, ...]]] = {}
            for _, conclusion, theorem, matched in candidates:
                additions.setdefault(conclusion, (theorem, matched))
            for conclusion, (theorem, matched) in additions.items():
                depth = 1 + max((proof[item].depth for item in matched), default=0)
                proof[conclusion] = ProofStep(conclusion, theorem.name, matched, depth)
            known.update(additions)
            if goal in known:
                ordered = self._proof_slice(goal, proof)
                return HypergraphProof(
                    goal,
                    ordered,
                    round_index,
                    explored,
                    tuple(sorted(relevant_names)),
                )
        return None

    @staticmethod
    def _proof_slice(goal: Atom, proof: Mapping[Atom, ProofStep]) -> tuple[ProofStep, ...]:
        selected: dict[Atom, ProofStep] = {}

        def visit(atom: Atom) -> None:
            if atom in selected:
                return
            step = proof[atom]
            for premise in step.premises:
                visit(premise)
            selected[atom] = step

        visit(goal)
        return tuple(sorted(selected.values(), key=lambda item: (item.depth, _render_atom(item.atom))))


def euclidean_relation_theorems() -> tuple[Theorem, ...]:
    """Small representation-level bank; all schemas are label/value agnostic."""
    atom = lambda name, *args: Atom(name, tuple(args))
    return (
        Theorem(
            "circle-definition-congruence-view",
            (
                atom("cong", "?O", "?A", "?O", "?B"),
                atom("cong", "?O", "?B", "?O", "?C"),
            ),
            atom("circle", "?O", "?A", "?B", "?C"),
        ),
        Theorem(
            "circle-radius-congruence-ab",
            (atom("circle", "?O", "?A", "?B", "?C"),),
            atom("cong", "?O", "?A", "?O", "?B"),
        ),
        Theorem(
            "circle-radius-congruence-bc",
            (atom("circle", "?O", "?A", "?B", "?C"),),
            atom("cong", "?O", "?B", "?O", "?C"),
        ),
        Theorem(
            "parallel-transitivity",
            (atom("para", "?A", "?B", "?C", "?D"), atom("para", "?C", "?D", "?E", "?F")),
            atom("para", "?A", "?B", "?E", "?F"),
        ),
        Theorem(
            "perpendicular-transport-over-parallel",
            (atom("perp", "?A", "?B", "?C", "?D"), atom("para", "?C", "?D", "?E", "?F")),
            atom("perp", "?A", "?B", "?E", "?F"),
        ),
        Theorem(
            "common-perpendicular-implies-parallel",
            (atom("perp", "?A", "?B", "?C", "?D"), atom("perp", "?E", "?F", "?C", "?D")),
            atom("para", "?A", "?B", "?E", "?F"),
        ),
        Theorem(
            "segment-congruence-transitivity",
            (atom("cong", "?A", "?B", "?C", "?D"), atom("cong", "?C", "?D", "?E", "?F")),
            atom("cong", "?A", "?B", "?E", "?F"),
        ),
        Theorem(
            "equal-angle-transitivity",
            (
                atom("eqangle", "?A", "?B", "?C", "?D", "?E", "?F", "?G", "?H"),
                atom("eqangle", "?E", "?F", "?G", "?H", "?I", "?J", "?K", "?L"),
            ),
            atom("eqangle", "?A", "?B", "?C", "?D", "?I", "?J", "?K", "?L"),
        ),
        Theorem(
            "equal-ratio-transitivity",
            (
                atom("eqratio", "?A", "?B", "?C", "?D", "?E", "?F", "?G", "?H"),
                atom("eqratio", "?E", "?F", "?G", "?H", "?I", "?J", "?K", "?L"),
            ),
            atom("eqratio", "?A", "?B", "?C", "?D", "?I", "?J", "?K", "?L"),
        ),
    )


def prove_typed_predicates(
    predicates: Iterable[object],
    goal: object,
    *,
    max_rounds: int = 12,
) -> HypergraphProof | None:
    """Bridge ``geometry_natural_formalizer.TypedPredicate`` into the prover."""
    facts = [
        Atom(str(getattr(item, "name")), tuple(getattr(item, "points")))
        for item in predicates
    ]
    goal_atom = Atom(str(getattr(goal, "name")), tuple(getattr(goal, "points")))
    return BidirectionalHypergraphProver(euclidean_relation_theorems()).prove(
        facts,
        goal_atom,
        max_rounds=max_rounds,
    )
