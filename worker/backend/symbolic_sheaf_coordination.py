"""記号推論器を改造せず、型付き共有境界だけで協調させる実験核。"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, Mapping, Protocol, Sequence

from worker.backend.geometry_proof_hypergraph import (
    Atom,
    Theorem,
    _instantiate,
    _premise_matches,
)


def render_atom(atom: Atom) -> str:
    canonical = atom.canonical()
    return f"{canonical.predicate}({','.join(canonical.arguments)})"


@dataclass(frozen=True)
class PredicateSignature:
    name: str
    argument_sorts: tuple[str, ...]


@dataclass(frozen=True)
class TypedVocabulary:
    signatures: Mapping[str, PredicateSignature]
    entity_sorts: Mapping[str, str]

    def validate(self, atom: Atom) -> tuple[bool, str | None]:
        canonical = atom.canonical()
        signature = self.signatures.get(canonical.predicate)
        if signature is None:
            return False, f"unknown predicate: {canonical.predicate}"
        if len(signature.argument_sorts) != len(canonical.arguments):
            return False, f"arity mismatch: {render_atom(canonical)}"
        for entity, expected in zip(canonical.arguments, signature.argument_sorts):
            actual = self.entity_sorts.get(entity)
            if actual is None:
                return False, f"unknown entity: {entity}"
            if expected != "Any" and actual != expected:
                return False, f"sort mismatch: {entity}:{actual} != {expected}"
        return True, None


@dataclass(frozen=True)
class LocalCertificate:
    agent_id: str
    rule_name: str
    conclusion: Atom
    premises: tuple[Atom, ...]
    native_payload: Mapping[str, object] = field(default_factory=dict, compare=False)


@dataclass(frozen=True)
class AgentProposal:
    certificates: tuple[LocalCertificate, ...]
    open_obligations: tuple[Atom, ...] = ()
    priorities: Mapping[str, float] = field(default_factory=dict, compare=False)


class SymbolicAgentAdapter(Protocol):
    agent_id: str
    imports: frozenset[str]
    exports: frozenset[str]

    def propose(
        self,
        facts: frozenset[Atom],
        goal: Atom,
        *,
        round_index: int,
    ) -> AgentProposal: ...

    def verify(self, certificate: LocalCertificate, facts: frozenset[Atom]) -> bool: ...


class RuleClosureAdapter:
    """Horn規則を持つ既存核の最小アダプタ。規則集合自体は変更しない。"""

    def __init__(
        self,
        agent_id: str,
        theorems: Iterable[Theorem],
        *,
        imports: Iterable[str],
        exports: Iterable[str],
        max_certificates_per_round: int | None = None,
    ) -> None:
        self.agent_id = agent_id
        self.theorems = tuple(theorems)
        self.imports = frozenset(name.lower() for name in imports)
        self.exports = frozenset(name.lower() for name in exports)
        if max_certificates_per_round is not None and max_certificates_per_round < 1:
            raise ValueError("max_certificates_per_round must be positive")
        self.max_certificates_per_round = max_certificates_per_round
        self._theorem_by_name = {theorem.name: theorem for theorem in self.theorems}

    def _visible(self, facts: frozenset[Atom]) -> set[Atom]:
        return {
            fact.canonical()
            for fact in facts
            if fact.canonical().predicate in self.imports
        }

    def propose(
        self,
        facts: frozenset[Atom],
        goal: Atom,
        *,
        round_index: int,
    ) -> AgentProposal:
        visible = self._visible(facts)
        certificates: dict[Atom, LocalCertificate] = {}
        goal_predicate = goal.canonical().predicate
        theorems = sorted(
            self.theorems,
            key=lambda theorem: (
                theorem.conclusion.canonical().predicate != goal_predicate,
                theorem.name,
            ),
        )
        candidate_budget = None
        if self.max_certificates_per_round is not None:
            candidate_budget = [max(4096, self.max_certificates_per_round * 64)]
        for theorem in theorems:
            for substitution, matched in _premise_matches(
                theorem.premises,
                visible,
                candidate_budget=candidate_budget,
            ):
                conclusion = _instantiate(theorem.conclusion, substitution)
                if conclusion is None:
                    continue
                conclusion = conclusion.canonical()
                if conclusion in facts or conclusion.predicate not in self.exports:
                    continue
                certificates.setdefault(
                    conclusion,
                    LocalCertificate(
                        agent_id=self.agent_id,
                        rule_name=theorem.name,
                        conclusion=conclusion,
                        premises=tuple(item.canonical() for item in matched),
                        native_payload={"round": round_index},
                    ),
                )
                if (
                    self.max_certificates_per_round is not None
                    and len(certificates) >= self.max_certificates_per_round
                ):
                    break
            if (
                candidate_budget is not None
                and (
                    candidate_budget[0] <= 0
                    or len(certificates) >= self.max_certificates_per_round
                )
            ):
                break
        goal_key = render_atom(goal)
        priorities = {
            render_atom(certificate.conclusion): (
                1.0 if certificate.conclusion == goal.canonical() else 0.25
            )
            for certificate in certificates.values()
        }
        priorities.setdefault(goal_key, 1.0)
        ordered = sorted(
            certificates.values(),
            key=lambda certificate: (
                certificate.conclusion.canonical() != goal.canonical(),
                render_atom(certificate.conclusion),
            ),
        )
        if self.max_certificates_per_round is not None:
            ordered = ordered[: self.max_certificates_per_round]
        return AgentProposal(
            certificates=tuple(ordered),
            open_obligations=() if goal.canonical() in visible else (goal.canonical(),),
            priorities=priorities,
        )

    def verify(self, certificate: LocalCertificate, facts: frozenset[Atom]) -> bool:
        if certificate.agent_id != self.agent_id:
            return False
        theorem = self._theorem_by_name.get(certificate.rule_name)
        if theorem is None:
            return False
        premises = tuple(item.canonical() for item in certificate.premises)
        if not set(premises) <= {item.canonical() for item in facts}:
            return False
        for substitution, matched in _premise_matches(theorem.premises, set(premises)):
            if set(matched) != set(premises):
                continue
            conclusion = _instantiate(theorem.conclusion, substitution)
            if conclusion is not None and conclusion.canonical() == certificate.conclusion.canonical():
                return True
        return False


@dataclass(frozen=True)
class RejectedCertificate:
    certificate: LocalCertificate
    reason: str


@dataclass(frozen=True)
class CoordinationRound:
    index: int
    proposed: int
    accepted: int
    rejected: int
    primal_residual: float
    dual_residual: float


@dataclass(frozen=True)
class CoordinationResult:
    goal: Atom
    givens: tuple[Atom, ...]
    accepted_facts: tuple[Atom, ...]
    certificates: tuple[LocalCertificate, ...]
    rejected: tuple[RejectedCertificate, ...]
    rounds: tuple[CoordinationRound, ...]
    solved: bool
    replayed: bool

    def proof_slice(self, target: Atom | None = None) -> tuple[LocalCertificate, ...]:
        target = (target or self.goal).canonical()
        certificate_by_conclusion = {
            item.conclusion.canonical(): item for item in self.certificates
        }
        selected: dict[Atom, LocalCertificate] = {}

        def visit(atom: Atom) -> None:
            canonical = atom.canonical()
            certificate = certificate_by_conclusion.get(canonical)
            if certificate is None or canonical in selected:
                return
            for premise in certificate.premises:
                visit(premise)
            selected[canonical] = certificate

        visit(target)
        return tuple(selected.values())


class ExactSheafCoordinator:
    """同じ共有状態を見た提案を一斉更新し、証明書付き事実だけを併合する。"""

    def __init__(
        self,
        vocabulary: TypedVocabulary,
        agents: Iterable[SymbolicAgentAdapter],
    ) -> None:
        self.vocabulary = vocabulary
        self.agents = tuple(agents)
        self._agent_by_id = {agent.agent_id: agent for agent in self.agents}
        if len(self._agent_by_id) != len(self.agents):
            raise ValueError("agent_id must be unique")

    def solve(
        self,
        givens: Iterable[Atom],
        goal: Atom,
        *,
        max_rounds: int = 16,
        stop_on_goal: bool = True,
    ) -> CoordinationResult:
        canonical_givens = tuple(sorted({item.canonical() for item in givens}, key=render_atom))
        goal = goal.canonical()
        for atom in (*canonical_givens, goal):
            valid, reason = self.vocabulary.validate(atom)
            if not valid:
                raise ValueError(reason)

        accepted = set(canonical_givens)
        certificates: dict[Atom, LocalCertificate] = {}
        rejected: list[RejectedCertificate] = []
        traces: list[CoordinationRound] = []

        for round_index in range(1, max_rounds + 1):
            snapshot = frozenset(accepted)
            proposals = [
                (agent, agent.propose(snapshot, goal, round_index=round_index))
                for agent in self.agents
            ]
            candidates: list[tuple[SymbolicAgentAdapter, LocalCertificate]] = [
                (agent, certificate)
                for agent, proposal in proposals
                for certificate in proposal.certificates
            ]
            additions: dict[Atom, LocalCertificate] = {}
            rejected_this_round = 0
            for agent, certificate in candidates:
                conclusion = certificate.conclusion.canonical()
                valid, reason = self.vocabulary.validate(conclusion)
                if not valid:
                    rejected.append(RejectedCertificate(certificate, reason or "invalid type"))
                    rejected_this_round += 1
                    continue
                if conclusion.predicate not in agent.exports:
                    rejected.append(RejectedCertificate(certificate, "predicate is outside export boundary"))
                    rejected_this_round += 1
                    continue
                if not agent.verify(certificate, snapshot):
                    rejected.append(RejectedCertificate(certificate, "certificate replay failed"))
                    rejected_this_round += 1
                    continue
                if conclusion not in accepted:
                    additions.setdefault(conclusion, certificate)

            accepted.update(additions)
            certificates.update(additions)
            solved = goal in accepted
            traces.append(
                CoordinationRound(
                    index=round_index,
                    proposed=len(candidates),
                    accepted=len(additions),
                    rejected=rejected_this_round,
                    primal_residual=float(rejected_this_round + (0 if solved else 1)),
                    dual_residual=float(len(additions)),
                )
            )
            if (solved and stop_on_goal) or not additions:
                break

        replayed = self._replay(canonical_givens, goal, tuple(certificates.values()))
        return CoordinationResult(
            goal=goal,
            givens=canonical_givens,
            accepted_facts=tuple(sorted(accepted, key=render_atom)),
            certificates=tuple(certificates.values()),
            rejected=tuple(rejected),
            rounds=tuple(traces),
            solved=goal in accepted,
            replayed=replayed,
        )

    def _replay(
        self,
        givens: Sequence[Atom],
        goal: Atom,
        certificates: Sequence[LocalCertificate],
    ) -> bool:
        known = {item.canonical() for item in givens}
        pending = list(certificates)
        changed = True
        while changed and pending:
            changed = False
            next_pending: list[LocalCertificate] = []
            for certificate in pending:
                agent = self._agent_by_id.get(certificate.agent_id)
                if agent is None or not set(certificate.premises) <= known:
                    next_pending.append(certificate)
                    continue
                if not agent.verify(certificate, frozenset(known)):
                    return False
                known.add(certificate.conclusion.canonical())
                changed = True
            pending = next_pending
        return goal.canonical() in known and not pending


@dataclass(frozen=True)
class AdmmConsensusResult:
    consensus: Mapping[str, float]
    local_allocations: Mapping[str, Mapping[str, float]]
    iterations: int
    primal_residual: float
    dual_residual: float


def _project_simplex(values: Sequence[float]) -> list[float]:
    if not values:
        return []
    ordered = sorted(values, reverse=True)
    cumulative = 0.0
    rho = 0
    for index, value in enumerate(ordered, start=1):
        cumulative += value
        threshold = (cumulative - 1.0) / index
        if value - threshold > 0:
            rho = index
    theta = (sum(ordered[:rho]) - 1.0) / rho
    return [max(value - theta, 0.0) for value in values]


def allocate_consensus_budget(
    preferences: Mapping[str, Mapping[str, float]],
    *,
    rho: float = 1.0,
    tolerance: float = 1e-9,
    max_iterations: int = 250,
) -> AdmmConsensusResult:
    """ADMMは探索予算だけを合意させ、証明の受理には使用しない。"""
    if not preferences:
        raise ValueError("at least one agent preference is required")
    obligations = sorted({key for values in preferences.values() for key in values})
    if not obligations:
        raise ValueError("at least one obligation is required")
    agent_ids = sorted(preferences)

    def normalized(agent_id: str) -> list[float]:
        raw = [max(float(preferences[agent_id].get(key, 0.0)), 0.0) for key in obligations]
        total = sum(raw)
        if total == 0:
            return [1.0 / len(raw)] * len(raw)
        return [value / total for value in raw]

    targets = {agent_id: normalized(agent_id) for agent_id in agent_ids}
    local = {agent_id: list(values) for agent_id, values in targets.items()}
    dual = {agent_id: [0.0] * len(obligations) for agent_id in agent_ids}
    consensus = _project_simplex([
        sum(targets[agent_id][index] for agent_id in agent_ids) / len(agent_ids)
        for index in range(len(obligations))
    ])
    primal = float("inf")
    dual_residual = float("inf")

    for iteration in range(1, max_iterations + 1):
        for agent_id in agent_ids:
            local[agent_id] = _project_simplex([
                (targets[agent_id][index] + rho * (consensus[index] - dual[agent_id][index]))
                / (1.0 + rho)
                for index in range(len(obligations))
            ])
        previous = list(consensus)
        consensus = _project_simplex([
            sum(local[agent_id][index] + dual[agent_id][index] for agent_id in agent_ids)
            / len(agent_ids)
            for index in range(len(obligations))
        ])
        for agent_id in agent_ids:
            dual[agent_id] = [
                dual[agent_id][index] + local[agent_id][index] - consensus[index]
                for index in range(len(obligations))
            ]
        primal = math.sqrt(sum(
            (local[agent_id][index] - consensus[index]) ** 2
            for agent_id in agent_ids
            for index in range(len(obligations))
        ))
        dual_residual = rho * math.sqrt(len(agent_ids)) * math.sqrt(sum(
            (consensus[index] - previous[index]) ** 2
            for index in range(len(obligations))
        ))
        if primal <= tolerance and dual_residual <= tolerance:
            break

    return AdmmConsensusResult(
        consensus=dict(zip(obligations, consensus)),
        local_allocations={
            agent_id: dict(zip(obligations, local[agent_id]))
            for agent_id in agent_ids
        },
        iterations=iteration,
        primal_residual=primal,
        dual_residual=dual_residual,
    )


@dataclass(frozen=True)
class FormalProblemCandidate:
    premises: tuple[Atom, ...]
    conclusion: Atom
    proof: tuple[LocalCertificate, ...]
    participating_agents: tuple[str, ...]
    proof_depth: int

    @property
    def formal_statement(self) -> str:
        left = ", ".join(render_atom(item) for item in self.premises)
        return f"{left} |- {render_atom(self.conclusion)}"


def synthesize_problem_from_coordination(
    result: CoordinationResult,
    *,
    min_agents: int = 2,
    min_steps: int = 2,
) -> FormalProblemCandidate | None:
    """検証済み協調証明を逆向きに読み、必要な前提だけを持つ形式問題を作る。"""
    if not result.solved or not result.replayed:
        return None
    proof = result.proof_slice()
    agents = tuple(sorted({item.agent_id for item in proof}))
    if len(proof) < min_steps or len(agents) < min_agents:
        return None
    derived = {item.conclusion.canonical() for item in proof}
    required = {
        premise.canonical()
        for certificate in proof
        for premise in certificate.premises
        if premise.canonical() not in derived
    }
    depth_by_atom: dict[Atom, int] = {item: 0 for item in required}
    for certificate in proof:
        depth_by_atom[certificate.conclusion.canonical()] = 1 + max(
            (depth_by_atom.get(item.canonical(), 0) for item in certificate.premises),
            default=0,
        )
    return FormalProblemCandidate(
        premises=tuple(sorted(required, key=render_atom)),
        conclusion=result.goal,
        proof=proof,
        participating_agents=agents,
        proof_depth=depth_by_atom.get(result.goal, 0),
    )
