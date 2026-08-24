"""Exact certificate exchange across native prover languages via MMT views."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Mapping

from worker.backend.geometry_proof_hypergraph import Atom
from worker.backend.symbolic_sheaf_coordination import (
    LocalCertificate,
    SymbolicAgentAdapter,
)


@dataclass(frozen=True, order=True)
class MMTAtom:
    symbol_uri: str
    arguments: tuple[str, ...]


@dataclass(frozen=True)
class MMTSymbolAssignment:
    native_predicate: str
    shared_symbol_uri: str
    argument_order: tuple[int, ...] = ()
    argument_sorts: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.native_predicate or not self.shared_symbol_uri:
            raise ValueError("symbol assignments must be named")
        if self.argument_order and set(self.argument_order) != set(
            range(len(self.argument_order))
        ):
            raise ValueError("argument_order must be a permutation")
        if self.argument_sorts and self.argument_order and (
            len(self.argument_sorts) != len(self.argument_order)
        ):
            raise ValueError("argument_sorts and argument_order must have equal arity")
        if any(not sort for sort in self.argument_sorts):
            raise ValueError("argument sorts must be named")

    @property
    def shared_argument_sorts(self) -> tuple[str, ...]:
        if not self.argument_sorts:
            return ()
        order = self.argument_order or tuple(range(len(self.argument_sorts)))
        return tuple(self.argument_sorts[index] for index in order)

    @property
    def native_arity(self) -> int | None:
        if self.argument_sorts:
            return len(self.argument_sorts)
        if self.argument_order:
            return len(self.argument_order)
        return None


@dataclass(frozen=True)
class MMTTheoryView:
    agent_id: str
    native_theory_uri: str
    shared_theory_uri: str
    assignments: tuple[MMTSymbolAssignment, ...]

    def __post_init__(self) -> None:
        native = [
            (item.native_predicate.lower(), item.native_arity)
            for item in self.assignments
        ]
        shared = [item.shared_symbol_uri for item in self.assignments]
        if len(native) != len(set(native)):
            raise ValueError(
                "native predicate/arity assignments must be unique inside a theory view"
            )
        if len(shared) != len(set(shared)):
            raise ValueError("shared symbols must be unique inside a theory view")
        arities_by_predicate: dict[str, set[int | None]] = {}
        for predicate, arity in native:
            arities_by_predicate.setdefault(predicate, set()).add(arity)
        ambiguous = {
            predicate
            for predicate, arities in arities_by_predicate.items()
            if None in arities and len(arities) > 1
        }
        if ambiguous:
            raise ValueError(
                "an untyped native assignment cannot overlap typed arity overloads: "
                f"{sorted(ambiguous)}"
            )

    @property
    def _by_native(self) -> Mapping[str, tuple[MMTSymbolAssignment, ...]]:
        grouped: dict[str, list[MMTSymbolAssignment]] = {}
        for item in self.assignments:
            grouped.setdefault(item.native_predicate.lower(), []).append(item)
        return {
            predicate: tuple(
                sorted(
                    items,
                    key=lambda item: (
                        item.native_arity is None,
                        item.native_arity if item.native_arity is not None else -1,
                        item.shared_symbol_uri,
                    ),
                )
            )
            for predicate, items in grouped.items()
        }

    @property
    def _by_shared(self) -> Mapping[str, MMTSymbolAssignment]:
        return {item.shared_symbol_uri: item for item in self.assignments}

    def push(self, atom: Atom) -> MMTAtom | None:
        canonical = atom.canonical()
        candidates = self._by_native.get(canonical.predicate, ())
        matching = tuple(
            item
            for item in candidates
            if item.native_arity is None
            or item.native_arity == len(canonical.arguments)
        )
        if len(matching) != 1:
            return None
        assignment = matching[0]
        order = assignment.argument_order or tuple(range(len(canonical.arguments)))
        if len(order) != len(canonical.arguments):
            return None
        if assignment.argument_sorts and (
            len(assignment.argument_sorts) != len(canonical.arguments)
        ):
            return None
        return MMTAtom(
            assignment.shared_symbol_uri,
            tuple(canonical.arguments[index] for index in order),
        )

    def pull(self, atom: MMTAtom) -> Atom | None:
        assignment = self._by_shared.get(atom.symbol_uri)
        if assignment is None:
            return None
        order = assignment.argument_order or tuple(range(len(atom.arguments)))
        if len(order) != len(atom.arguments):
            return None
        if assignment.shared_argument_sorts and (
            len(assignment.shared_argument_sorts) != len(atom.arguments)
        ):
            return None
        native_arguments = [""] * len(atom.arguments)
        for shared_index, native_index in enumerate(order):
            native_arguments[native_index] = atom.arguments[shared_index]
        return Atom(assignment.native_predicate, tuple(native_arguments)).canonical()


_REAL_LITERAL = re.compile(r"^[+-]?(?:\d+(?:\.\d+)?|\d+/\d+)$")
_ANGLE_LITERAL = re.compile(
    r"^(?:[+-]?(?:(?:\d+(?:\.\d+)?)?pi(?:/\d+(?:\.\d+)?)?|\d+(?:\.\d+)?(?:deg|degree|degrees|o|°)))$",
    re.IGNORECASE,
)


def _argument_matches_sort(value: str, sort: str) -> bool:
    token = value.strip()
    if not token or token.startswith("?"):
        return False
    normalized = sort.lower()
    if normalized == "opaque":
        return True
    if normalized in {"real", "rational", "integer", "natural"}:
        return bool(_REAL_LITERAL.fullmatch(token))
    if normalized == "angle":
        return bool(_ANGLE_LITERAL.fullmatch(token))
    if normalized.startswith(("point", "line", "plane", "circle", "sphere")):
        return not (
            _REAL_LITERAL.fullmatch(token)
            or _ANGLE_LITERAL.fullmatch(token)
            or token in {"*", "+", "-", "="}
        )
    return not (_REAL_LITERAL.fullmatch(token) or _ANGLE_LITERAL.fullmatch(token))


@dataclass(frozen=True)
class MMTProofEnvelope:
    source_agent_id: str
    native_certificate: LocalCertificate
    conclusion: MMTAtom
    premises: tuple[MMTAtom, ...]


@dataclass(frozen=True)
class MMTCoordinationRound:
    index: int
    proposed: int
    accepted: int
    rejected: int


@dataclass(frozen=True)
class MMTCoordinationResult:
    goal: MMTAtom
    accepted_facts: tuple[MMTAtom, ...]
    certificates: tuple[MMTProofEnvelope, ...]
    rounds: tuple[MMTCoordinationRound, ...]
    solved: bool
    replayed: bool


class MMTExactCoordinator:
    """Compose verified native certificates without merging native syntax."""

    def __init__(
        self,
        agents: Iterable[SymbolicAgentAdapter],
        views: Iterable[MMTTheoryView],
    ) -> None:
        self.agents = tuple(agents)
        self._agent_by_id = {agent.agent_id: agent for agent in self.agents}
        self._view_by_id = {view.agent_id: view for view in views}
        if set(self._agent_by_id) != set(self._view_by_id):
            raise ValueError("every native agent must have exactly one MMT theory view")
        signatures: dict[str, tuple[str, ...]] = {}
        for view in self._view_by_id.values():
            for assignment in view.assignments:
                signature = assignment.shared_argument_sorts
                if not signature:
                    continue
                previous = signatures.get(assignment.shared_symbol_uri)
                if previous is not None and previous != signature:
                    raise ValueError(
                        "incompatible shared symbol signature: "
                        f"{assignment.shared_symbol_uri}: {previous} != {signature}"
                    )
                signatures[assignment.shared_symbol_uri] = signature
        self.shared_signatures = signatures

    def _well_typed_shared_atom(self, atom: MMTAtom) -> bool:
        signature = self.shared_signatures.get(atom.symbol_uri)
        return signature is None or (
            len(signature) == len(atom.arguments)
            and all(
                _argument_matches_sort(argument, sort)
                for argument, sort in zip(atom.arguments, signature, strict=True)
            )
        )

    def solve(
        self,
        givens: Iterable[MMTAtom],
        goal: MMTAtom,
        *,
        max_rounds: int = 16,
    ) -> MMTCoordinationResult:
        canonical_givens = tuple(givens)
        initial_accepted = {
            item for item in canonical_givens if self._well_typed_shared_atom(item)
        }
        accepted = set(initial_accepted)
        if not self._well_typed_shared_atom(goal):
            raise ValueError("goal arity does not match its shared MMT signature")
        envelopes: list[MMTProofEnvelope] = []
        traces: list[MMTCoordinationRound] = []
        for round_index in range(1, max_rounds + 1):
            proposed = accepted_count = rejected = 0
            additions: dict[MMTAtom, MMTProofEnvelope] = {}
            for agent in self.agents:
                view = self._view_by_id[agent.agent_id]
                native_facts = frozenset(
                    item
                    for fact in accepted
                    if (item := view.pull(fact)) is not None
                )
                native_goal = view.pull(goal)
                if native_goal is None:
                    # A forward agent may still export a useful intermediate
                    # fact even when its native theory has no symbol for the
                    # final goal.  Keep the goal opaque instead of silencing it.
                    native_goal = Atom("__mmt_unmapped_goal__", goal.arguments)
                proposal = agent.propose(
                    native_facts,
                    native_goal,
                    round_index=round_index,
                )
                for certificate in proposal.certificates:
                    proposed += 1
                    if not agent.verify(certificate, native_facts):
                        rejected += 1
                        continue
                    conclusion = view.push(certificate.conclusion)
                    premises = tuple(view.push(item) for item in certificate.premises)
                    if conclusion is None or any(item is None for item in premises):
                        rejected += 1
                        continue
                    typed_premises = tuple(item for item in premises if item is not None)
                    if not self._well_typed_shared_atom(conclusion) or any(
                        not self._well_typed_shared_atom(item)
                        for item in typed_premises
                    ):
                        rejected += 1
                        continue
                    if not set(typed_premises) <= accepted:
                        rejected += 1
                        continue
                    additions.setdefault(
                        conclusion,
                        MMTProofEnvelope(
                            source_agent_id=agent.agent_id,
                            native_certificate=certificate,
                            conclusion=conclusion,
                            premises=typed_premises,
                        ),
                    )
            for conclusion, envelope in additions.items():
                if conclusion not in accepted:
                    accepted.add(conclusion)
                    envelopes.append(envelope)
                    accepted_count += 1
            traces.append(
                MMTCoordinationRound(
                    index=round_index,
                    proposed=proposed,
                    accepted=accepted_count,
                    rejected=rejected,
                )
            )
            if goal in accepted or not additions:
                break
        replayed = self._replay(initial_accepted, envelopes, goal)
        return MMTCoordinationResult(
            goal=goal,
            accepted_facts=tuple(sorted(accepted)),
            certificates=tuple(envelopes),
            rounds=tuple(traces),
            solved=goal in accepted,
            replayed=replayed,
        )

    def _replay(
        self,
        givens: set[MMTAtom],
        envelopes: list[MMTProofEnvelope],
        goal: MMTAtom,
    ) -> bool:
        known = set(givens)
        for envelope in envelopes:
            if not set(envelope.premises) <= known:
                return False
            agent = self._agent_by_id[envelope.source_agent_id]
            view = self._view_by_id[envelope.source_agent_id]
            native_facts = frozenset(
                item for fact in known if (item := view.pull(fact)) is not None
            )
            if not agent.verify(envelope.native_certificate, native_facts):
                return False
            if view.push(envelope.native_certificate.conclusion) != envelope.conclusion:
                return False
            known.add(envelope.conclusion)
        return goal in known
