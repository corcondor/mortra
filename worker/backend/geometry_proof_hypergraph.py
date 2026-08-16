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

from dataclasses import dataclass
from itertools import permutations
from typing import Iterable, Iterator, Mapping


@dataclass(frozen=True, order=True)
class Atom:
    predicate: str
    arguments: tuple[str, ...]

    def canonical(self) -> "Atom":
        name = self.predicate.lower()
        args = self.arguments
        if name in {"para", "perp", "cong"} and len(args) == 4:
            left = tuple(sorted(args[:2]))
            right = tuple(sorted(args[2:]))
            first, second = sorted((left, right))
            args = (*first, *second)
        elif name in {"coll", "cyclic"}:
            args = tuple(sorted(args))
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


Substitution = dict[str, str]


def _is_variable(value: str) -> bool:
    return value.startswith("?")


def _render_atom(atom: Atom) -> str:
    return f"{atom.predicate}({','.join(atom.arguments)})"


def _argument_orbit(atom: Atom) -> tuple[tuple[str, ...], ...]:
    """Return the finite symmetry orbit of a relation's arguments.

    Canonicalizing a ground atom is not sufficient for theorem patterns: a
    substitution fixed by an earlier premise may require the opposite line or
    endpoint orientation in a later premise.  Enumerating this small orbit
    makes unification invariant to point naming without adding theorem copies.
    """
    name = atom.predicate.lower()
    args = atom.arguments
    if name in {"para", "perp", "cong"} and len(args) == 4:
        first = (args[0], args[1])
        second = (args[2], args[3])
        variants = {
            (*left, *right)
            for left, right in ((first, second), (second, first))
            for left in (left, left[::-1])
            for right in (right, right[::-1])
        }
        return tuple(sorted(variants))
    if name in {"coll", "cyclic"}:
        return tuple(sorted(set(permutations(args))))
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


def _premise_matches(
    premises: tuple[Atom, ...],
    facts: set[Atom],
    index: int = 0,
    substitution: Substitution | None = None,
) -> Iterator[tuple[Substitution, tuple[Atom, ...]]]:
    if index == len(premises):
        yield dict(substitution or {}), ()
        return
    pattern = premises[index]
    for fact in facts:
        for merged in _unify_all(pattern, fact, substitution):
            for final, tail in _premise_matches(premises, facts, index + 1, merged):
                yield final, (fact,) + tail


def _backward_relevant(goal: Atom, theorems: tuple[Theorem, ...], max_depth: int) -> set[str]:
    relevant: set[str] = set()
    frontier = {goal.canonical()}
    seen = set(frontier)
    for _ in range(max_depth):
        next_frontier: set[Atom] = set()
        for wanted in frontier:
            for theorem in theorems:
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
    ) -> HypergraphProof | None:
        goal = goal.canonical()
        known = {fact.canonical() for fact in facts}
        proof: dict[Atom, ProofStep] = {
            fact: ProofStep(fact, "given", (), 0) for fact in known
        }
        if goal in known:
            return HypergraphProof(goal, (proof[goal],), 0, 0, ())

        relevant_names = _backward_relevant(goal, self.theorems, max_rounds)
        rules = tuple(rule for rule in self.theorems if rule.name in relevant_names)
        explored = 0
        for round_index in range(1, max_rounds + 1):
            candidates: list[tuple[tuple[int, int, int, str], Atom, Theorem, tuple[Atom, ...]]] = []
            existing_entities = {arg for atom in known for arg in atom.arguments}
            for theorem in rules:
                for substitution, matched in _premise_matches(theorem.premises, known):
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
            (atom("eqangle", "?A", "?B", "?C", "?D", "?E", "?F"), atom("eqangle", "?D", "?E", "?F", "?G", "?H", "?I")),
            atom("eqangle", "?A", "?B", "?C", "?G", "?H", "?I"),
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
