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
from typing import Iterable, Iterator, Mapping, Sequence

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
    compile_strategy: str = "exhaustive_forward"
    search_states: int = 0
    backtracks: int = 0

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


def _gate_order(gate: ProofGate) -> tuple[int, str, str, str, tuple[str, ...]]:
    return (
        gate.depth,
        render_atom(gate.conclusion),
        gate.agent_id,
        gate.theorem,
        tuple(render_atom(item) for item in gate.premises),
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
        compile_strategy="exhaustive_forward",
    )


@dataclass(frozen=True)
class _PendingRule:
    agent_id: str
    theorem: str
    premises: tuple[Atom, ...]
    conclusion: Atom


def _logic_variable(value: str) -> bool:
    return value.startswith("?")


def _resolve_term(value: str, substitution: Mapping[str, str]) -> str:
    seen: set[str] = set()
    current = value
    while _logic_variable(current) and current in substitution and current not in seen:
        seen.add(current)
        current = substitution[current]
    return current


def _substitute_atom(atom: Atom, substitution: Mapping[str, str]) -> Atom:
    return Atom(
        atom.predicate,
        tuple(_resolve_term(value, substitution) for value in atom.arguments),
    )


def _unify_terms(
    left: str,
    right: str,
    substitution: Mapping[str, str],
) -> dict[str, str] | None:
    result = dict(substitution)
    left = _resolve_term(left, result)
    right = _resolve_term(right, result)
    if left == right:
        return result
    if _logic_variable(left):
        result[left] = right
        return result
    if _logic_variable(right):
        result[right] = left
        return result
    return None


def _unify_symbolic_atoms(
    left: Atom,
    right: Atom,
    substitution: Mapping[str, str],
) -> Iterator[dict[str, str]]:
    """Unify two possibly non-ground atoms, respecting relation symmetries."""
    if left.predicate.lower() != right.predicate.lower():
        return
    if len(left.arguments) != len(right.arguments):
        return
    # The theorem module already defines the finite argument orbit used by the
    # native verifier. Importing it locally keeps this compiler aligned with
    # the verifier without making the public Atom API larger.
    from worker.backend.geometry_proof_hypergraph import _argument_orbit

    yielded: set[tuple[tuple[str, str], ...]] = set()
    for left_arguments in _argument_orbit(left):
        for right_arguments in _argument_orbit(right):
            merged: dict[str, str] | None = dict(substitution)
            for left_value, right_value in zip(left_arguments, right_arguments):
                if merged is None:
                    break
                merged = _unify_terms(left_value, right_value, merged)
            if merged is None:
                continue
            normalized = {
                key: _resolve_term(value, merged)
                for key, value in merged.items()
            }
            key = tuple(sorted(normalized.items()))
            if key not in yielded:
                yielded.add(key)
                yield normalized


def _standardize_theorem(theorem: Theorem, serial: int) -> Theorem:
    suffix = f"__lazy_{serial}"

    def rename(atom: Atom) -> Atom:
        return Atom(
            atom.predicate,
            tuple(
                f"{value}{suffix}" if _logic_variable(value) else value
                for value in atom.arguments
            ),
        )

    return Theorem(
        theorem.name,
        tuple(rename(premise) for premise in theorem.premises),
        rename(theorem.conclusion),
    )


def symbolic_atom_unifications(
    left: Atom,
    right: Atom,
    initial: Mapping[str, str] | None = None,
) -> tuple[dict[str, str], ...]:
    """Expose the circuit's finite symmetry-aware symbolic unifier."""

    return tuple(_unify_symbolic_atoms(left, right, initial or {}))


def substitute_symbolic_atom(
    atom: Atom,
    substitution: Mapping[str, str],
) -> Atom:
    """Apply a possibly chained symbolic substitution without grounding it."""

    return _substitute_atom(atom, substitution)


def standardize_theorem_variables(theorem: Theorem, serial: int) -> Theorem:
    """Rename one theorem's variables apart for a bounded backward branch."""

    return _standardize_theorem(theorem, serial)


def _ground_atom(atom: Atom, substitution: Mapping[str, str]) -> Atom | None:
    resolved = _substitute_atom(atom, substitution)
    if any(_logic_variable(value) for value in resolved.arguments):
        return None
    return resolved.canonical()


def compile_goal_directed_proof_circuit(
    givens: Iterable[Atom],
    goal: Atom,
    agents: Sequence[SymbolicAgentAdapter],
    *,
    max_rule_applications: int = 24,
    max_search_states: int = 100_000,
) -> CompiledProofCircuit:
    """Compile one proof lazily from the goal by tabled SLD-style search.

    The search keeps variables until a fact or another rule binds them.  It
    therefore does not enumerate the Cartesian product of all entities before
    knowing which arguments the goal constrains.  The returned circuit still
    contains only ground gates and must pass the same native replay as the
    exhaustive compiler.
    """
    canonical_givens = frozenset(item.canonical() for item in givens)
    canonical_goal = goal.canonical()
    facts_by_predicate: dict[str, tuple[Atom, ...]] = {}
    for predicate in sorted({item.predicate for item in canonical_givens}):
        facts_by_predicate[predicate] = tuple(
            sorted(
                (item for item in canonical_givens if item.predicate == predicate),
                key=render_atom,
            )
        )
    rules_by_predicate: dict[
        str,
        tuple[tuple[SymbolicAgentAdapter, Theorem], ...],
    ] = {}
    for agent, theorem in _agent_theorems(agents):
        rules_by_predicate.setdefault(theorem.conclusion.predicate.lower(), []).append(
            (agent, theorem)
        )
    rules_by_predicate = {
        predicate: tuple(
            sorted(items, key=lambda item: (len(item[1].premises), item[0].agent_id, item[1].name))
        )
        for predicate, items in rules_by_predicate.items()
    }

    states = 0
    fact_unifications = 0
    rule_unifications = 0
    backtracks = 0
    serial = 0

    def candidate_facts(
        atom: Atom,
        substitution: Mapping[str, str],
    ) -> tuple[Atom, ...]:
        query = _substitute_atom(atom, substitution)
        candidates = []
        for fact in facts_by_predicate.get(query.predicate.lower(), ()):
            if next(_unify_symbolic_atoms(query, fact, substitution), None) is not None:
                candidates.append(fact)
        return tuple(candidates)

    def choose_goal(
        goals: tuple[Atom, ...],
        substitution: Mapping[str, str],
    ) -> int:
        ranked = []
        for index, item in enumerate(goals):
            resolved = _substitute_atom(item, substitution)
            bound = sum(not _logic_variable(value) for value in resolved.arguments)
            fact_count = len(candidate_facts(item, substitution))
            ranked.append(
                (
                    -bound,
                    0 if fact_count else 1,
                    fact_count if fact_count else math.inf,
                    len(resolved.arguments),
                    index,
                )
            )
        return min(ranked)[-1]

    def search(
        goals: tuple[Atom, ...],
        substitution: dict[str, str],
        applications: tuple[_PendingRule, ...],
        active_ground_goals: frozenset[Atom],
        rule_limit: int,
    ) -> tuple[dict[str, str], tuple[_PendingRule, ...]] | None:
        nonlocal states, fact_unifications, rule_unifications, backtracks, serial
        if states >= max_search_states:
            return None
        states += 1
        if not goals:
            return substitution, applications

        # Horn conjunction is idempotent. Variables that were distinct in a
        # rule can become equal after another premise binds them; retaining
        # both copies would turn a proof DAG into a larger proof tree.
        unique_goals: list[Atom] = []
        seen_goals: set[tuple[str, tuple[str, ...]]] = set()
        for item in goals:
            resolved = _substitute_atom(item, substitution)
            key = resolved.predicate.lower(), resolved.arguments
            if key not in seen_goals:
                seen_goals.add(key)
                unique_goals.append(item)
        goals = tuple(unique_goals)

        selected_index = choose_goal(goals, substitution)
        selected = goals[selected_index]
        remaining = goals[:selected_index] + goals[selected_index + 1 :]
        resolved_selected = _substitute_atom(selected, substitution)
        ground_selected = _ground_atom(selected, substitution)

        for fact in candidate_facts(resolved_selected, substitution):
            fact_unifications += 1
            for merged in _unify_symbolic_atoms(resolved_selected, fact, substitution):
                result = search(
                    remaining,
                    merged,
                    applications,
                    active_ground_goals,
                    rule_limit,
                )
                if result is not None:
                    return result
                backtracks += 1

        if len(applications) >= rule_limit:
            return None
        if ground_selected is not None and ground_selected in active_ground_goals:
            return None

        next_active = active_ground_goals
        if ground_selected is not None:
            next_active = frozenset((*active_ground_goals, ground_selected))
        expansions = []
        for agent, theorem in rules_by_predicate.get(
            resolved_selected.predicate.lower(), ()
        ):
            serial += 1
            standardized = _standardize_theorem(theorem, serial)
            rule_unifications += 1
            for merged in _unify_symbolic_atoms(
                resolved_selected,
                standardized.conclusion,
                substitution,
            ):
                evidence = 0
                bound_arguments = 0
                unanchored_recursive = 0
                for premise in standardized.premises:
                    resolved_premise = _substitute_atom(premise, merged)
                    premise_facts = candidate_facts(premise, merged)
                    evidence += int(bool(premise_facts))
                    bound_arguments += sum(
                        not _logic_variable(value)
                        for value in resolved_premise.arguments
                    )
                    if (
                        premise.predicate.lower() == resolved_selected.predicate.lower()
                        and not premise_facts
                    ):
                        unanchored_recursive += 1
                rank = (
                    0 if evidence else 1,
                    -evidence,
                    unanchored_recursive,
                    -bound_arguments,
                    len(standardized.premises),
                    agent.agent_id,
                    theorem.name,
                )
                expansions.append((rank, agent, theorem, standardized, merged))

        for _rank, agent, theorem, standardized, merged in sorted(
            expansions,
            key=lambda item: item[0],
        ):
            pending = _PendingRule(
                agent_id=agent.agent_id,
                theorem=theorem.name,
                premises=standardized.premises,
                conclusion=standardized.conclusion,
            )
            result = search(
                standardized.premises + remaining,
                merged,
                applications + (pending,),
                next_active,
                rule_limit,
            )
            if result is not None:
                return result
            backtracks += 1
        return None

    found = None
    for rule_limit in range(max_rule_applications + 1):
        found = search((canonical_goal,), {}, (), frozenset(), rule_limit)
        if found is not None or states >= max_search_states:
            break
    matches = fact_unifications + rule_unifications
    if found is None:
        return CompiledProofCircuit(
            givens=canonical_givens,
            goal=canonical_goal,
            gates=(),
            atom_depth={item: 0 for item in canonical_givens},
            compile_matches=matches,
            compile_rounds=0,
            compile_strategy="goal_directed_lazy",
            search_states=states,
            backtracks=backtracks,
        )

    final_substitution, pending_rules = found
    grounded: dict[tuple, tuple[str, str, tuple[Atom, ...], Atom]] = {}
    for pending in pending_rules:
        conclusion = _ground_atom(pending.conclusion, final_substitution)
        premises = tuple(
            _ground_atom(item, final_substitution) for item in pending.premises
        )
        if conclusion is None or any(item is None for item in premises):
            continue
        concrete_premises = tuple(item for item in premises if item is not None)
        key = pending.agent_id, pending.theorem, concrete_premises, conclusion
        grounded.setdefault(
            key,
            (pending.agent_id, pending.theorem, concrete_premises, conclusion),
        )

    depth: dict[Atom, int] = {item: 0 for item in canonical_givens}
    gates: list[ProofGate] = []
    unresolved = list(grounded.values())
    while unresolved:
        next_unresolved = []
        changed = False
        for agent_id, theorem_name, premises, conclusion in unresolved:
            if all(item in depth for item in premises):
                gate_depth = 1 + max((depth[item] for item in premises), default=0)
                depth[conclusion] = min(depth.get(conclusion, gate_depth), gate_depth)
                gates.append(
                    ProofGate(
                        agent_id=agent_id,
                        theorem=theorem_name,
                        premises=premises,
                        conclusion=conclusion,
                        depth=gate_depth,
                    )
                )
                changed = True
            else:
                next_unresolved.append((agent_id, theorem_name, premises, conclusion))
        if not changed:
            break
        unresolved = next_unresolved

    return CompiledProofCircuit(
        givens=canonical_givens,
        goal=canonical_goal,
        gates=tuple(sorted(gates, key=_gate_order)),
        atom_depth=depth,
        compile_matches=matches,
        compile_rounds=max((gate.depth for gate in gates), default=0),
        compile_strategy="goal_directed_lazy",
        search_states=states,
        backtracks=backtracks,
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
            agent = agent_by_id[gate.agent_id]
            certificate_factory = getattr(agent, "certificate_for_gate", None)
            if callable(certificate_factory):
                certificate = certificate_factory(gate, round_index=round_index)
            else:
                certificate = LocalCertificate(
                    agent_id=gate.agent_id,
                    rule_name=gate.theorem,
                    conclusion=gate.conclusion,
                    premises=gate.premises,
                    native_payload={"circuit_depth": gate.depth, "round": round_index},
                )
            valid_type, _ = vocabulary.validate(certificate.conclusion)
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
