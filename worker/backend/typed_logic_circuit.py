"""Typed AND-OR proof circuits with exact certificate replay.

The circuit is compiled from ground Horn-rule applications.  Premises form an
AND gate and alternative derivations of one conclusion form an OR gate.  A
continuous backward demand pass is used only to schedule proof attempts; truth
is determined solely by replaying native certificates.

This module intentionally keeps full ground atoms.  Collapsing ``p(a, b)`` and
``p(c, d)`` to the predicate name ``p`` is useful as a control ablation, but is
not a sound proof representation.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Mapping, Sequence

from worker.backend.geometry_proof_hypergraph import (
    Atom,
    Theorem,
    _instantiate,
    _premise_matches,
)
from worker.backend.symbolic_sheaf_coordination import (
    LocalCertificate,
    SymbolicAgentAdapter,
    TypedVocabulary,
    render_atom,
)


@dataclass(frozen=True)
class ProofGate:
    """One ground Horn-rule application."""

    agent_id: str
    theorem: str
    premises: tuple[Atom, ...]
    conclusion: Atom
    depth: int

    @property
    def key(self) -> tuple[str, str, tuple[Atom, ...], Atom]:
        return self.agent_id, self.theorem, self.premises, self.conclusion


@dataclass(frozen=True)
class CircuitScheduleResult:
    mode: str
    solved: bool
    replayed: bool
    rounds: int
    transmitted: int
    accepted: tuple[Atom, ...]
    certificates: tuple[LocalCertificate, ...]


@dataclass(frozen=True)
class CompiledProofCircuit:
    givens: frozenset[Atom]
    goal: Atom
    gates: tuple[ProofGate, ...]
    atom_depth: Mapping[Atom, int]
    compile_matches: int
    compile_rounds: int

    @property
    def provable(self) -> bool:
        return self.goal in self.atom_depth

    def gates_by_conclusion(self) -> dict[Atom, tuple[ProofGate, ...]]:
        grouped: dict[Atom, list[ProofGate]] = {}
        for gate in self.gates:
            grouped.setdefault(gate.conclusion, []).append(gate)
        return {
            atom: tuple(sorted(items, key=_gate_order))
            for atom, items in grouped.items()
        }

    def minimum_costs(self) -> tuple[dict[Atom, float], dict[Atom, ProofGate]]:
        """Return the smallest replay cost and one witness gate per atom."""
        costs = {atom: 0.0 for atom in self.givens}
        witness: dict[Atom, ProofGate] = {}
        for gate in sorted(self.gates, key=_gate_order):
            if not all(premise in costs for premise in gate.premises):
                continue
            candidate = 1.0 + sum(costs[premise] for premise in gate.premises)
            previous = costs.get(gate.conclusion, math.inf)
            if candidate < previous:
                costs[gate.conclusion] = candidate
                witness[gate.conclusion] = gate
        return costs, witness

    def proof_slice(self) -> tuple[ProofGate, ...]:
        costs, witness = self.minimum_costs()
        if self.goal not in costs:
            return ()
        selected: dict[tuple[str, str, tuple[Atom, ...], Atom], ProofGate] = {}

        def visit(atom: Atom) -> None:
            gate = witness.get(atom)
            if gate is None or gate.key in selected:
                return
            for premise in gate.premises:
                visit(premise)
            selected[gate.key] = gate

        visit(self.goal)
        return tuple(sorted(selected.values(), key=_gate_order))

    def backward_demands(
        self,
        *,
        temperature: float = 1.0,
        top_k: int | None = 1,
    ) -> tuple[dict[Atom, float], dict[tuple, float]]:
        """Propagate a continuous goal demand over exact AND-OR structure.

        The lowest-cost ``top_k`` OR alternatives share demand through a
        softmax over structural proof cost.  Keeping ``top_k=1`` produces one
        coherent proof provenance instead of interleaving equally cheap
        branches under a tight transfer budget.  Every premise of an AND gate
        receives the gate demand.  The resulting real values prioritize
        search but never assert truth.
        """
        if top_k is not None and top_k < 1:
            raise ValueError("top_k must be positive")
        costs, _ = self.minimum_costs()
        if self.goal not in costs:
            return {}, {}
        by_conclusion = self.gates_by_conclusion()
        atom_demand: dict[Atom, float] = {self.goal: 1.0}
        gate_demand: dict[tuple, float] = {}
        ordered_atoms = sorted(
            (atom for atom in costs if atom not in self.givens),
            key=lambda atom: self.atom_depth.get(atom, 0),
            reverse=True,
        )
        for conclusion in ordered_atoms:
            demand = atom_demand.get(conclusion, 0.0)
            if demand <= 0.0:
                continue
            alternatives = [
                gate
                for gate in by_conclusion.get(conclusion, ())
                if all(premise in costs for premise in gate.premises)
            ]
            if not alternatives:
                continue
            alternatives.sort(
                key=lambda gate: (
                    1.0 + sum(costs[premise] for premise in gate.premises),
                    _gate_order(gate),
                )
            )
            if top_k is not None:
                alternatives = alternatives[:top_k]
            logits = [
                -(1.0 + sum(costs[premise] for premise in gate.premises))
                / max(temperature, 1e-9)
                for gate in alternatives
            ]
            shift = max(logits)
            weights = [math.exp(value - shift) for value in logits]
            normalizer = sum(weights)
            for gate, weight in zip(alternatives, weights):
                share = demand * weight / normalizer
                gate_demand[gate.key] = gate_demand.get(gate.key, 0.0) + share
                for premise in gate.premises:
                    atom_demand[premise] = atom_demand.get(premise, 0.0) + share
        return atom_demand, gate_demand

    def predicate_abstraction_provable(self, theorems: Iterable[Theorem]) -> bool:
        """Unsound control: discard all arguments and retain predicate names."""
        known = {atom.predicate for atom in self.givens}
        changed = True
        rules = tuple(theorems)
        while changed:
            changed = False
            for theorem in rules:
                if all(item.predicate.lower() in known for item in theorem.premises):
                    conclusion = theorem.conclusion.predicate.lower()
                    if conclusion not in known:
                        known.add(conclusion)
                        changed = True
        return self.goal.predicate in known


def _gate_order(gate: ProofGate) -> tuple[int, str, str, str]:
    return (
        gate.depth,
        render_atom(gate.conclusion),
        gate.agent_id,
        gate.theorem,
    )


def _agent_theorems(
    agents: Sequence[SymbolicAgentAdapter],
) -> tuple[tuple[SymbolicAgentAdapter, Theorem], ...]:
    result: list[tuple[SymbolicAgentAdapter, Theorem]] = []
    for agent in agents:
        for theorem in tuple(getattr(agent, "theorems", ())):
            result.append((agent, theorem))
    return tuple(result)


def compile_typed_proof_circuit(
    givens: Iterable[Atom],
    goal: Atom,
    agents: Sequence[SymbolicAgentAdapter],
    *,
    max_rounds: int = 12,
) -> CompiledProofCircuit:
    """Compile the minimum-depth ground proof DAG reachable from ``givens``.

    All rule matching is label- and value-agnostic.  Gates are retained only
    when their conclusion first becomes reachable, making the resulting graph
    acyclic while preserving all alternatives at the minimum derivation depth.
    """
    canonical_givens = frozenset(atom.canonical() for atom in givens)
    canonical_goal = goal.canonical()
    known = set(canonical_givens)
    depth: dict[Atom, int] = {atom: 0 for atom in known}
    gates: dict[tuple, ProofGate] = {}
    matches = 0
    completed_rounds = 0
    agent_rules = _agent_theorems(agents)

    for round_index in range(1, max_rounds + 1):
        snapshot = set(known)
        additions: dict[Atom, list[ProofGate]] = {}
        for agent, theorem in agent_rules:
            for substitution, matched in _premise_matches(theorem.premises, snapshot):
                matches += 1
                conclusion = _instantiate(theorem.conclusion, substitution)
                if conclusion is None:
                    continue
                conclusion = conclusion.canonical()
                premises = tuple(item.canonical() for item in matched)
                if conclusion in snapshot or conclusion in premises:
                    continue
                gate = ProofGate(
                    agent_id=agent.agent_id,
                    theorem=theorem.name,
                    premises=premises,
                    conclusion=conclusion,
                    depth=round_index,
                )
                additions.setdefault(conclusion, []).append(gate)
        if not additions:
            break
        for conclusion, alternatives in additions.items():
            depth[conclusion] = round_index
            known.add(conclusion)
            for gate in alternatives:
                gates.setdefault(gate.key, gate)
        completed_rounds = round_index

    return CompiledProofCircuit(
        givens=canonical_givens,
        goal=canonical_goal,
        gates=tuple(sorted(gates.values(), key=_gate_order)),
        atom_depth=depth,
        compile_matches=matches,
        compile_rounds=completed_rounds,
    )


def schedule_circuit(
    circuit: CompiledProofCircuit,
    vocabulary: TypedVocabulary,
    agents: Sequence[SymbolicAgentAdapter],
    *,
    mode: str,
    budget_per_round: int = 1,
    max_rounds: int = 8,
) -> CircuitScheduleResult:
    """Execute compiled gates under a finite certificate-transfer budget."""
    if mode not in {"predicate", "current", "circuit_soft", "circuit"}:
        raise ValueError(f"unsupported mode: {mode}")
    if budget_per_round < 1 or max_rounds < 1:
        raise ValueError("budgets and rounds must be positive")

    agent_by_id = {agent.agent_id: agent for agent in agents}
    accepted = set(circuit.givens)
    certificates: list[LocalCertificate] = []
    attempted: set[tuple] = set()
    atom_demand, gate_demand = circuit.backward_demands(
        top_k=None if mode == "circuit_soft" else 1
    )
    rounds = 0

    for round_index in range(1, max_rounds + 1):
        available = [
            gate
            for gate in circuit.gates
            if gate.key not in attempted
            and gate.conclusion not in accepted
            and set(gate.premises) <= accepted
        ]
        if mode in {"circuit_soft", "circuit"}:
            available = [gate for gate in available if gate_demand.get(gate.key, 0.0) > 0.0]
        if not available:
            break

        def rank(gate: ProofGate) -> tuple[float, str, str]:
            if mode == "predicate":
                score = float(gate.conclusion.predicate == circuit.goal.predicate)
            elif mode == "current":
                score = (
                    8.0 * float(gate.conclusion == circuit.goal)
                    + 1.5 * len(set(gate.conclusion.arguments) & set(circuit.goal.arguments))
                    + float(gate.conclusion.predicate == circuit.goal.predicate)
                )
            else:
                score = 100.0 * gate_demand.get(gate.key, 0.0) + atom_demand.get(gate.conclusion, 0.0)
            return -score, render_atom(gate.conclusion), gate.agent_id

        available.sort(key=rank)
        selected = available[:budget_per_round]
        for gate in selected:
            attempted.add(gate.key)
            certificate = LocalCertificate(
                agent_id=gate.agent_id,
                rule_name=gate.theorem,
                conclusion=gate.conclusion,
                premises=gate.premises,
                native_payload={"circuit_depth": gate.depth, "round": round_index},
            )
            valid_type, _ = vocabulary.validate(certificate.conclusion)
            agent = agent_by_id[gate.agent_id]
            if valid_type and agent.verify(certificate, frozenset(accepted)):
                accepted.add(gate.conclusion)
                certificates.append(certificate)
        rounds = round_index
        if circuit.goal in accepted:
            break

    solved = circuit.goal in accepted
    replayed = solved and replay_certificates(circuit.givens, circuit.goal, certificates, agents)
    return CircuitScheduleResult(
        mode=mode,
        solved=solved,
        replayed=replayed,
        rounds=rounds,
        transmitted=len(attempted),
        accepted=tuple(sorted(accepted, key=render_atom)),
        certificates=tuple(certificates),
    )


def replay_certificates(
    givens: Iterable[Atom],
    goal: Atom,
    certificates: Sequence[LocalCertificate],
    agents: Sequence[SymbolicAgentAdapter],
) -> bool:
    known = {atom.canonical() for atom in givens}
    agent_by_id = {agent.agent_id: agent for agent in agents}
    for certificate in certificates:
        if not set(certificate.premises) <= known:
            return False
        agent = agent_by_id.get(certificate.agent_id)
        if agent is None or not agent.verify(certificate, frozenset(known)):
            return False
        known.add(certificate.conclusion.canonical())
    return goal.canonical() in known
