"""局所Gröbner証明書を型付き共有境界として交換する。"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import sympy as sp

from worker.backend.chordal_buchberger_elimination import (
    ChordalBuchbergerEliminationResult,
)
from worker.backend.geometry_proof_hypergraph import Atom
from worker.backend.symbolic_sheaf_coordination import (
    AgentProposal,
    ExactSheafCoordinator,
    LocalCertificate,
    PredicateSignature,
    TypedVocabulary,
)


def _polynomial_atom(polynomial: str) -> Atom:
    digest = hashlib.sha256(polynomial.encode()).hexdigest()
    return Atom("poly_zero", (f"p_{digest}",))


@dataclass(frozen=True)
class ChordalPolynomialCoordinationReport:
    local_agent_count: int
    active_agent_count: int
    initial_fact_count: int
    transported_polynomial_count: int
    accepted_certificate_count: int
    rejected_certificate_count: int
    proof_depth: int
    goal_certificate_available: bool
    goal_solved: bool
    goal_replayed: bool


@dataclass(frozen=True)
class _ExpectedCertificate:
    conclusion: str
    inputs: tuple[str, ...]
    multipliers: tuple[str, ...]

    @property
    def active_inputs(self) -> tuple[str, ...]:
        return tuple(
            item
            for item, multiplier in zip(self.inputs, self.multipliers)
            if sp.sympify(multiplier) != 0
        )


class _PolynomialIdentityAdapter:
    imports = frozenset({"poly_zero"})
    exports = frozenset({"poly_zero"})

    def __init__(
        self,
        agent_id: str,
        expected: tuple[tuple[str, _ExpectedCertificate], ...],
    ) -> None:
        self.agent_id = agent_id
        self._expected = dict(expected)

    def propose(
        self,
        facts: frozenset[Atom],
        goal: Atom,
        *,
        round_index: int,
    ) -> AgentProposal:
        known = {item.canonical() for item in facts}
        certificates: list[LocalCertificate] = []
        for rule_name, expected in self._expected.items():
            conclusion = _polynomial_atom(expected.conclusion)
            premises = tuple(_polynomial_atom(item) for item in expected.active_inputs)
            if conclusion in known or not set(premises) <= known:
                continue
            certificates.append(
                LocalCertificate(
                    agent_id=self.agent_id,
                    rule_name=rule_name,
                    conclusion=conclusion,
                    premises=premises,
                    native_payload={
                        "round": round_index,
                        "conclusion": expected.conclusion,
                        "inputs": expected.inputs,
                        "multipliers": expected.multipliers,
                    },
                )
            )
        return AgentProposal(
            certificates=tuple(certificates),
            open_obligations=() if goal.canonical() in known else (goal.canonical(),),
        )

    def verify(self, certificate: LocalCertificate, facts: frozenset[Atom]) -> bool:
        if certificate.agent_id != self.agent_id:
            return False
        expected = self._expected.get(certificate.rule_name)
        if expected is None:
            return False
        premises = tuple(_polynomial_atom(item) for item in expected.active_inputs)
        if certificate.premises != premises:
            return False
        if not set(premises) <= {item.canonical() for item in facts}:
            return False
        if certificate.conclusion.canonical() != _polynomial_atom(
            expected.conclusion
        ):
            return False
        residual = sp.expand(
            sp.sympify(expected.conclusion)
            - sum(
                (
                    sp.sympify(multiplier) * sp.sympify(polynomial)
                    for multiplier, polynomial in zip(
                        expected.multipliers,
                        expected.inputs,
                    )
                ),
                sp.Integer(0),
            )
        )
        return residual == 0


def coordinate_chordal_polynomial_stalk(
    result: ChordalBuchbergerEliminationResult,
) -> ChordalPolynomialCoordinationReport:
    """全局所証明を再計算し、元の仮定から目標までのDAGを作る。"""

    expected_by_agent: list[tuple[str, list[tuple[str, _ExpectedCertificate]]]] = []
    transported: set[str] = set()
    for index, step in enumerate(result.steps):
        expected: list[tuple[str, _ExpectedCertificate]] = []
        for identity in step.internal_identities:
            rule_name = f"{step.certificate_sha256}:{identity.certificate_sha256}"
            expected.append(
                (
                    rule_name,
                    _ExpectedCertificate(
                        conclusion=identity.polynomial,
                        inputs=identity.premises,
                        multipliers=identity.multipliers,
                    ),
                )
            )
        transported.update(step.output_polynomials)
        if expected:
            expected_by_agent.append((f"chordal-clique-{index:03d}", expected))

    goal_available = bool(
        result.goal_membership
        and result.goal_membership.proved
        and result.goal_membership.replayed
    )
    if goal_available:
        assert result.goal_membership is not None
        if result.terminal_buchberger is not None:
            expected_by_agent.append(
                (
                    "chordal-terminal-basis",
                    [
                        (
                            identity.certificate_sha256,
                            _ExpectedCertificate(
                                conclusion=identity.polynomial,
                                inputs=identity.premises,
                                multipliers=identity.multipliers,
                            ),
                        )
                        for identity in result.terminal_buchberger.identities
                    ],
                )
            )
        expected_by_agent.append(
            (
                "chordal-terminal-membership",
                [
                    (
                        result.goal_membership.certificate_sha256,
                        _ExpectedCertificate(
                            conclusion=result.goal_membership.goal_polynomial,
                            inputs=result.goal_membership.premises,
                            multipliers=result.goal_membership.multipliers,
                        ),
                    )
                ],
            )
        )

    adapters = tuple(
        _PolynomialIdentityAdapter(agent_id, tuple(expected))
        for agent_id, expected in expected_by_agent
    )
    initial_atoms = tuple(
        _polynomial_atom(item) for item in result.initial_polynomials
    )
    goal_polynomial = (
        result.goal_membership.goal_polynomial
        if result.goal_membership is not None
        else "__unproved_goal__"
    )
    goal = _polynomial_atom(goal_polynomial)
    certificate_polynomials = {
        polynomial
        for _, expected in expected_by_agent
        for _, item in expected
        for polynomial in (item.conclusion, *item.inputs)
    }
    all_atoms = {
        *initial_atoms,
        goal,
        *(_polynomial_atom(item) for item in transported),
        *(_polynomial_atom(item) for item in certificate_polynomials),
    }
    entities = {
        argument for atom in all_atoms for argument in atom.canonical().arguments
    }
    coordinator = ExactSheafCoordinator(
        TypedVocabulary(
            signatures={"poly_zero": PredicateSignature("poly_zero", ("Polynomial",))},
            entity_sorts={entity: "Polynomial" for entity in entities},
        ),
        adapters,
    )
    coordination = coordinator.solve(
        initial_atoms,
        goal,
        max_rounds=max(1, len(adapters) + 1),
    )
    proof = coordination.proof_slice()
    return ChordalPolynomialCoordinationReport(
        local_agent_count=len(adapters),
        active_agent_count=len({item.agent_id for item in proof}),
        initial_fact_count=len(initial_atoms),
        transported_polynomial_count=len(transported),
        accepted_certificate_count=len(coordination.certificates),
        rejected_certificate_count=len(coordination.rejected),
        proof_depth=len(proof),
        goal_certificate_available=goal_available,
        goal_solved=coordination.solved and goal_available,
        goal_replayed=coordination.replayed and goal_available,
    )
