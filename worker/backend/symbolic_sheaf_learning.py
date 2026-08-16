"""LLM-free sheaf coordination for exact symbolic reasoners.

The continuous layer follows the scaled ADMM decomposition used by
SakanaAI/sheaf-admm, but it is deliberately kept outside the truth path:

* ``x`` is each reasoner's private priority over typed predicate channels.
* ``z`` is the sheaf-consistent priority obtained from shared channels.
* ``y`` accumulates local-versus-shared disagreement.
* exact native certificates, never ``x/z/y``, decide which facts are true.

Restriction weights can be learned from replayed proof DAGs.  This changes
where a finite search budget is spent; it cannot make an invalid certificate
valid.  The separation is essential because averaging mathematical truth
values would be unsound.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence

import numpy as np

from worker.backend.geometry_proof_hypergraph import Atom
from worker.backend.symbolic_sheaf_coordination import (
    CoordinationResult,
    LocalCertificate,
    SymbolicAgentAdapter,
    TypedVocabulary,
    render_atom,
)


def _project_nonnegative(values: np.ndarray) -> np.ndarray:
    """The scheduler uses scores, so negative ADMM iterates carry no budget."""
    return np.maximum(values, 0.0)


@dataclass(frozen=True)
class SheafEdge:
    left: str
    right: str
    predicate: str
    left_weight: float
    right_weight: float


@dataclass(frozen=True)
class SymbolicAdmmTrace:
    iteration: int
    primal_residual: float
    dual_residual: float
    sheaf_residual: float


@dataclass(frozen=True)
class SymbolicAdmmResult:
    agents: tuple[str, ...]
    predicates: tuple[str, ...]
    x: np.ndarray = field(compare=False, repr=False)
    z: np.ndarray = field(compare=False, repr=False)
    y: np.ndarray = field(compare=False, repr=False)
    edges: tuple[SheafEdge, ...]
    trace: tuple[SymbolicAdmmTrace, ...]

    def score(self, agent_id: str, predicate: str) -> float:
        try:
            agent_index = self.agents.index(agent_id)
            predicate_index = self.predicates.index(predicate.lower())
        except ValueError:
            return 0.0
        return float(max(self.z[agent_index, predicate_index], 0.0))


@dataclass
class BetaEvidence:
    successes: float = 1.0
    failures: float = 1.0

    @property
    def mean(self) -> float:
        return self.successes / (self.successes + self.failures)

    def observe(self, success: bool) -> None:
        if success:
            self.successes += 1.0
        else:
            self.failures += 1.0


class ProofFlowLearner:
    """Learn rule and communication reliability from replayed proof slices.

    The learner sees only native certificate identities and typed dataflow.  It
    never receives question text, problem IDs, entity labels, numeric answers,
    or an oracle at inference time.
    """

    def __init__(self) -> None:
        self.rule_evidence: dict[tuple[str, str], BetaEvidence] = {}
        self.edge_evidence: dict[tuple[str, str, str], BetaEvidence] = {}
        self.training_episodes = 0
        self.replayed_episodes = 0

    @staticmethod
    def _rule_key(certificate: LocalCertificate) -> tuple[str, str]:
        signature = (
            "+".join(sorted(item.canonical().predicate for item in certificate.premises))
            + "->"
            + certificate.conclusion.canonical().predicate
        )
        return certificate.agent_id, signature

    @staticmethod
    def _theorem_key(agent_id: str, theorem: object) -> tuple[str, str]:
        premises = getattr(theorem, "premises", ())
        conclusion = getattr(theorem, "conclusion")
        signature = (
            "+".join(sorted(item.canonical().predicate for item in premises))
            + "->"
            + conclusion.canonical().predicate
        )
        return agent_id, signature

    def fit_episode(
        self,
        result: CoordinationResult,
        agents: Sequence[SymbolicAgentAdapter],
    ) -> None:
        self.training_episodes += 1
        if not result.solved or not result.replayed:
            return
        self.replayed_episodes += 1
        proof = result.proof_slice()
        used_rules = {self._rule_key(item) for item in proof}
        all_rules = {
            self._theorem_key(agent.agent_id, theorem)
            for agent in agents
            for theorem in getattr(agent, "theorems", ())
        }
        for key in all_rules | used_rules:
            self.rule_evidence.setdefault(key, BetaEvidence()).observe(key in used_rules)

        proof_by_conclusion = {
            item.conclusion.canonical(): item for item in proof
        }
        used_flows: set[tuple[str, str, str]] = set()
        for consumer in proof:
            for premise in consumer.premises:
                producer = proof_by_conclusion.get(premise.canonical())
                if producer is None or producer.agent_id == consumer.agent_id:
                    continue
                used_flows.add((
                    producer.agent_id,
                    consumer.agent_id,
                    premise.canonical().predicate,
                ))

        compatible: set[tuple[str, str, str]] = set()
        for producer in agents:
            for consumer in agents:
                if producer.agent_id == consumer.agent_id:
                    continue
                for predicate in producer.exports & consumer.imports:
                    compatible.add((producer.agent_id, consumer.agent_id, predicate))
        for key in compatible | used_flows:
            self.edge_evidence.setdefault(key, BetaEvidence()).observe(key in used_flows)

    def rule_weight(self, certificate: LocalCertificate) -> float:
        return self.rule_evidence.get(self._rule_key(certificate), BetaEvidence()).mean

    def edge_weight(self, left: str, right: str, predicate: str) -> float:
        direct = self.edge_evidence.get((left, right, predicate.lower()))
        reverse = self.edge_evidence.get((right, left, predicate.lower()))
        if direct is None and reverse is None:
            return 0.5
        values = [item.mean for item in (direct, reverse) if item is not None]
        return sum(values) / len(values)

    def to_dict(self) -> dict[str, object]:
        return {
            "training_episodes": self.training_episodes,
            "replayed_episodes": self.replayed_episodes,
            "rule_weights": {
                f"{agent}:{signature}": evidence.mean
                for (agent, signature), evidence in sorted(self.rule_evidence.items())
            },
            "edge_weights": {
                f"{left}->{right}:{predicate}": evidence.mean
                for (left, right, predicate), evidence in sorted(self.edge_evidence.items())
            },
        }


class LinearSymbolicSheafADMM:
    """Scaled ADMM over typed predicate channels and a cellular-sheaf graph.

    The z update solves the convex quadratic

        argmin_z 1/2 ||z-v||^2 + gamma/2 ||delta_F z||^2

    exactly, channel by channel.  This is ``(I + gamma L_F) z = v`` where
    ``L_F = delta_F^T delta_F`` is the sheaf Laplacian.
    """

    def __init__(
        self,
        agents: Sequence[SymbolicAgentAdapter],
        predicates: Iterable[str],
        *,
        learner: ProofFlowLearner | None = None,
        rho: float = 1.0,
        gamma: float = 1.0,
        iterations: int = 20,
        tolerance: float = 1e-9,
    ) -> None:
        if rho <= 0 or gamma < 0 or iterations < 1:
            raise ValueError("rho and iterations must be positive; gamma must be nonnegative")
        self.agents = tuple(agents)
        self.predicates = tuple(sorted({item.lower() for item in predicates}))
        self.learner = learner
        self.rho = float(rho)
        self.gamma = float(gamma)
        self.iterations = int(iterations)
        self.tolerance = float(tolerance)
        self._agent_index = {agent.agent_id: index for index, agent in enumerate(self.agents)}
        self._predicate_index = {name: index for index, name in enumerate(self.predicates)}
        self.edges = self._build_edges()

    def _build_edges(self) -> tuple[SheafEdge, ...]:
        edges: list[SheafEdge] = []
        for left_index, left in enumerate(self.agents):
            for right in self.agents[left_index + 1:]:
                shared = (left.exports & right.imports) | (right.exports & left.imports)
                for predicate in sorted(shared & set(self.predicates)):
                    weight = 1.0
                    if self.learner is not None:
                        weight = self.learner.edge_weight(
                            left.agent_id,
                            right.agent_id,
                            predicate,
                        )
                    # A small floor keeps the communication graph connected while
                    # still allowing replay evidence to reshape its conductance.
                    restriction = math.sqrt(max(weight, 0.05))
                    edges.append(SheafEdge(
                        left.agent_id,
                        right.agent_id,
                        predicate,
                        restriction,
                        restriction,
                    ))
        return tuple(edges)

    def _laplacian(self, predicate: str) -> np.ndarray:
        size = len(self.agents)
        laplacian = np.zeros((size, size), dtype=float)
        for edge in self.edges:
            if edge.predicate != predicate:
                continue
            left = self._agent_index[edge.left]
            right = self._agent_index[edge.right]
            a = edge.left_weight
            b = edge.right_weight
            laplacian[left, left] += a * a
            laplacian[right, right] += b * b
            laplacian[left, right] -= a * b
            laplacian[right, left] -= a * b
        return laplacian

    def _sheaf_residual(self, state: np.ndarray) -> float:
        residuals: list[float] = []
        for edge in self.edges:
            left = self._agent_index[edge.left]
            right = self._agent_index[edge.right]
            channel = self._predicate_index[edge.predicate]
            residuals.append(
                edge.left_weight * state[left, channel]
                - edge.right_weight * state[right, channel]
            )
        if not residuals:
            return 0.0
        return float(np.sqrt(np.mean(np.square(residuals))))

    def solve(self, local_preferences: Mapping[str, Mapping[str, float]]) -> SymbolicAdmmResult:
        shape = (len(self.agents), len(self.predicates))
        preferences = np.zeros(shape, dtype=float)
        for agent_id, channels in local_preferences.items():
            if agent_id not in self._agent_index:
                continue
            row = self._agent_index[agent_id]
            for predicate, value in channels.items():
                column = self._predicate_index.get(predicate.lower())
                if column is not None:
                    preferences[row, column] = max(float(value), 0.0)

        x = preferences.copy()
        z = preferences.copy()
        y = np.zeros_like(preferences)
        traces: list[SymbolicAdmmTrace] = []
        systems = {
            predicate: np.eye(len(self.agents)) + self.gamma * self._laplacian(predicate)
            for predicate in self.predicates
        }
        for iteration in range(1, self.iterations + 1):
            z_previous = z.copy()
            # prox of 1/2 ||x-p_i||^2 plus the scaled ADMM penalty.
            x = _project_nonnegative(
                (preferences + self.rho * (z - y)) / (1.0 + self.rho)
            )
            target = x + y
            for column, predicate in enumerate(self.predicates):
                z[:, column] = np.linalg.solve(systems[predicate], target[:, column])
            y = y + (x - z)
            primal = float(np.linalg.norm(x - z))
            dual = float(self.rho * np.linalg.norm(z - z_previous))
            sheaf = self._sheaf_residual(z)
            traces.append(SymbolicAdmmTrace(iteration, primal, dual, sheaf))
            if primal <= self.tolerance and dual <= self.tolerance:
                break
        return SymbolicAdmmResult(
            agents=tuple(agent.agent_id for agent in self.agents),
            predicates=self.predicates,
            x=x,
            z=z,
            y=y,
            edges=self.edges,
            trace=tuple(traces),
        )


@dataclass(frozen=True)
class BudgetedRound:
    index: int
    proposed: int
    transmitted: int
    peer_messages: int
    accepted: int
    rejected: int
    primal_residual: float
    dual_residual: float
    sheaf_residual: float


@dataclass(frozen=True)
class BudgetedCoordinationResult:
    goal: Atom
    givens: tuple[Atom, ...]
    accepted_facts: tuple[Atom, ...]
    certificates: tuple[LocalCertificate, ...]
    rejected: tuple[LocalCertificate, ...]
    rounds: tuple[BudgetedRound, ...]
    solved: bool
    replayed: bool
    proposed_total: int
    transmitted_total: int
    peer_messages_total: int

    def proof_slice(self) -> tuple[LocalCertificate, ...]:
        certificate_by_conclusion = {
            item.conclusion.canonical(): item for item in self.certificates
        }
        selected: dict[Atom, LocalCertificate] = {}

        def visit(atom: Atom) -> None:
            certificate = certificate_by_conclusion.get(atom.canonical())
            if certificate is None or certificate.conclusion.canonical() in selected:
                return
            for premise in certificate.premises:
                visit(premise)
            selected[certificate.conclusion.canonical()] = certificate

        visit(self.goal)
        return tuple(selected.values())


class BudgetedSheafCoordinator:
    """Spend a finite certificate-transfer budget using symbolic Sheaf-ADMM."""

    def __init__(
        self,
        vocabulary: TypedVocabulary,
        agents: Sequence[SymbolicAgentAdapter],
        *,
        learner: ProofFlowLearner | None = None,
        use_sheaf: bool = True,
        local_views: bool = False,
    ) -> None:
        self.vocabulary = vocabulary
        self.agents = tuple(agents)
        self.learner = learner
        self.use_sheaf = use_sheaf
        self.local_views = local_views
        self._agent_by_id = {agent.agent_id: agent for agent in self.agents}

    def _candidate_priority(
        self,
        certificate: LocalCertificate,
        goal: Atom,
        admm: SymbolicAdmmResult | None,
    ) -> tuple[float, str, str]:
        conclusion = certificate.conclusion.canonical()
        goal = goal.canonical()
        overlap = len(set(conclusion.arguments) & set(goal.arguments))
        direct = float(conclusion == goal)
        learned = (
            self.learner.rule_weight(certificate)
            if self.learner is not None else 0.5
        )
        consensus = admm.score(certificate.agent_id, conclusion.predicate) if admm else 0.0
        score = 8.0 * direct + 1.5 * overlap + 2.0 * learned + consensus
        return (-score, certificate.agent_id, render_atom(conclusion))

    def _replay(
        self,
        givens: Sequence[Atom],
        goal: Atom,
        certificates: Sequence[LocalCertificate],
    ) -> bool:
        known = {item.canonical() for item in givens}
        pending = list(certificates)
        while pending:
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
            if not changed:
                return False
            pending = next_pending
        return goal.canonical() in known

    def solve(
        self,
        givens: Iterable[Atom],
        goal: Atom,
        *,
        max_rounds: int = 12,
        transfer_budget: int = 2,
    ) -> BudgetedCoordinationResult:
        if transfer_budget < 1:
            raise ValueError("transfer_budget must be positive")
        canonical_givens = tuple(sorted({item.canonical() for item in givens}, key=render_atom))
        goal = goal.canonical()
        for item in (*canonical_givens, goal):
            valid, reason = self.vocabulary.validate(item)
            if not valid:
                raise ValueError(reason)

        accepted = set(canonical_givens)
        certificates: dict[Atom, LocalCertificate] = {}
        rejected: list[LocalCertificate] = []
        rounds: list[BudgetedRound] = []
        proposed_total = 0
        transmitted_total = 0
        peer_messages_total = 0
        blocked_certificates: set[tuple[str, str, Atom]] = set()
        local_facts = {
            agent.agent_id: {
                item for item in canonical_givens
                if item.predicate in agent.imports or item.predicate in agent.exports
            }
            for agent in self.agents
        }

        for round_index in range(1, max_rounds + 1):
            snapshot = frozenset(accepted)
            local_snapshots = {
                agent_id: frozenset(facts)
                for agent_id, facts in local_facts.items()
            }
            candidate_pairs: list[tuple[SymbolicAgentAdapter, LocalCertificate]] = []
            local_preferences: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
            for agent in self.agents:
                visible = local_snapshots[agent.agent_id] if self.local_views else snapshot
                proposal = agent.propose(visible, goal, round_index=round_index)
                for certificate in proposal.certificates:
                    key = (
                        certificate.agent_id,
                        certificate.rule_name,
                        certificate.conclusion.canonical(),
                    )
                    if key in blocked_certificates:
                        continue
                    candidate_pairs.append((agent, certificate))
                    weight = (
                        self.learner.rule_weight(certificate)
                        if self.learner is not None else 0.5
                    )
                    predicate = certificate.conclusion.canonical().predicate
                    local_preferences[agent.agent_id][predicate] += weight

            proposed_total += len(candidate_pairs)
            admm: SymbolicAdmmResult | None = None
            if self.use_sheaf and candidate_pairs:
                admm = LinearSymbolicSheafADMM(
                    self.agents,
                    self.vocabulary.signatures,
                    learner=self.learner,
                ).solve(local_preferences)

            candidate_pairs.sort(
                key=lambda item: self._candidate_priority(item[1], goal, admm)
                if self.use_sheaf or self.learner is not None else (
                    item[0].agent_id,
                    item[1].rule_name,
                    render_atom(item[1].conclusion),
                )
            )
            selected = candidate_pairs[:transfer_budget]
            transmitted_total += len(selected)
            additions: dict[Atom, LocalCertificate] = {}
            rejected_this_round = 0
            peer_messages_this_round = 0
            for agent, certificate in selected:
                conclusion = certificate.conclusion.canonical()
                verification_facts = (
                    local_snapshots[agent.agent_id] if self.local_views else snapshot
                )
                valid, _reason = self.vocabulary.validate(conclusion)
                if (
                    not valid
                    or conclusion.predicate not in agent.exports
                    or not agent.verify(certificate, verification_facts)
                ):
                    rejected.append(certificate)
                    blocked_certificates.add((
                        certificate.agent_id,
                        certificate.rule_name,
                        conclusion,
                    ))
                    rejected_this_round += 1
                    continue
                if conclusion not in accepted:
                    additions.setdefault(conclusion, certificate)
            accepted.update(additions)
            certificates.update(additions)
            if self.local_views:
                for conclusion, certificate in additions.items():
                    local_facts[certificate.agent_id].add(conclusion)
                    for recipient in self.agents:
                        if recipient.agent_id == certificate.agent_id:
                            continue
                        if conclusion.predicate not in recipient.imports:
                            continue
                        communicates = any(
                            edge.predicate == conclusion.predicate
                            and {edge.left, edge.right} == {
                                certificate.agent_id,
                                recipient.agent_id,
                            }
                            for edge in (admm.edges if admm else ())
                        )
                        if communicates and conclusion not in local_facts[recipient.agent_id]:
                            local_facts[recipient.agent_id].add(conclusion)
                            peer_messages_this_round += 1
                peer_messages_total += peer_messages_this_round
            else:
                for conclusion, certificate in additions.items():
                    for recipient in self.agents:
                        if recipient.agent_id == certificate.agent_id:
                            continue
                        if conclusion.predicate in recipient.imports:
                            peer_messages_this_round += 1
                    for facts in local_facts.values():
                        facts.add(conclusion)
                peer_messages_total += peer_messages_this_round
            trace = admm.trace[-1] if admm and admm.trace else None
            rounds.append(BudgetedRound(
                index=round_index,
                proposed=len(candidate_pairs),
                transmitted=len(selected),
                peer_messages=peer_messages_this_round,
                accepted=len(additions),
                rejected=rejected_this_round,
                primal_residual=trace.primal_residual if trace else 0.0,
                dual_residual=trace.dual_residual if trace else 0.0,
                sheaf_residual=trace.sheaf_residual if trace else 0.0,
            ))
            if goal in accepted or not candidate_pairs or (not additions and rejected_this_round == 0):
                break

        ordered_certificates = tuple(certificates.values())
        solved = goal in accepted
        replayed = solved and self._replay(canonical_givens, goal, ordered_certificates)
        return BudgetedCoordinationResult(
            goal=goal,
            givens=canonical_givens,
            accepted_facts=tuple(sorted(accepted, key=render_atom)),
            certificates=ordered_certificates,
            rejected=tuple(rejected),
            rounds=tuple(rounds),
            solved=solved,
            replayed=replayed,
            proposed_total=proposed_total,
            transmitted_total=transmitted_total,
            peer_messages_total=peer_messages_total,
        )
