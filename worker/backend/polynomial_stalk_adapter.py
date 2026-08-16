"""Exchange local polynomial-elimination certificates through the coordinator."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, replace
from statistics import fmean

import sympy as sp

from worker.backend.geometry_proof_hypergraph import Atom
from worker.backend.local_polynomial_elimination import (
    LocalEliminationResult,
    LocalEliminationStep,
)
from worker.backend.symbolic_sheaf_coordination import (
    AgentProposal,
    ExactSheafCoordinator,
    LocalCertificate,
    PredicateSignature,
    TypedVocabulary,
)


def polynomial_zero_atom(polynomial: str) -> Atom:
    digest = hashlib.sha256(polynomial.encode()).hexdigest()
    return Atom("poly_zero", (f"p_{digest}",))


@dataclass(frozen=True)
class PolynomialStalk:
    initial_atoms: tuple[Atom, ...]
    derived_atoms: tuple[Atom, ...]
    expression_by_atom: dict[Atom, str]
    certificates: tuple[tuple[LocalEliminationStep, str], ...]


@dataclass(frozen=True)
class PolynomialStalkCoordinationReport:
    local_agent_count: int
    active_agent_count: int
    maximum_separator_variable_width: int
    initial_fact_count: int
    derived_goal_count: int
    solved_goal_count: int
    replayed_goal_count: int
    accepted_certificate_count: int
    rejected_certificate_count: int
    maximum_proof_depth: int
    mean_proof_depth: float
    external_goal_matched: bool
    external_goal_solved: bool
    external_goal_replayed: bool
    external_goal_proof_depth: int


def build_polynomial_stalk(result: LocalEliminationResult) -> PolynomialStalk:
    expressions = {
        polynomial_zero_atom(expression): expression
        for expression in (
            *result.initial_polynomials,
            *(output for step in result.steps for output in step.output_polynomials),
        )
    }
    certificates = tuple(
        (step, output) for step in result.steps for output in step.output_polynomials
    )
    initial_atoms = tuple(
        polynomial_zero_atom(item) for item in result.initial_polynomials
    )
    initial_set = set(initial_atoms)
    derived_atoms = tuple(
        dict.fromkeys(
            polynomial_zero_atom(output)
            for _, output in certificates
            if polynomial_zero_atom(output) not in initial_set
        )
    )
    return PolynomialStalk(
        initial_atoms=initial_atoms,
        derived_atoms=derived_atoms,
        expression_by_atom=expressions,
        certificates=certificates,
    )


class PolynomialEliminationStalkAdapter:
    imports = frozenset({"poly_zero"})
    exports = frozenset({"poly_zero"})

    def __init__(
        self,
        stalk: PolynomialStalk,
        *,
        agent_id: str = "polynomial-local-elimination-stalk",
    ) -> None:
        self.agent_id = agent_id
        self.stalk = stalk
        self._expected = {
            (step.certificate_sha256, polynomial_zero_atom(output)): (step, output)
            for step, output in stalk.certificates
        }

    def propose(
        self,
        facts: frozenset[Atom],
        goal: Atom,
        *,
        round_index: int,
    ) -> AgentProposal:
        canonical_facts = {item.canonical() for item in facts}
        certificates: list[LocalCertificate] = []
        for step, output in self.stalk.certificates:
            premises = tuple(
                polynomial_zero_atom(item) for item in step.input_polynomials
            )
            conclusion = polynomial_zero_atom(output)
            if conclusion in canonical_facts or not set(premises) <= canonical_facts:
                continue
            certificates.append(
                LocalCertificate(
                    agent_id=self.agent_id,
                    rule_name=step.certificate_sha256,
                    conclusion=conclusion,
                    premises=premises,
                    native_payload={
                        "round": round_index,
                        "method": step.method,
                        "variable": step.variable,
                        "separator_variables": step.separator_variables,
                        "output_polynomial": output,
                        "replay_residuals": step.replay_residuals,
                        "ideal_membership_witnesses": tuple(
                            asdict(item) for item in step.ideal_membership_witnesses
                        ),
                        "replayed": step.replayed,
                    },
                )
            )
        return AgentProposal(
            certificates=tuple(certificates),
            open_obligations=() if goal.canonical() in canonical_facts else (goal,),
        )

    def verify(self, certificate: LocalCertificate, facts: frozenset[Atom]) -> bool:
        expected = self._expected.get(
            (certificate.rule_name, certificate.conclusion.canonical())
        )
        if expected is None:
            return False
        step, output = expected
        premises = tuple(polynomial_zero_atom(item) for item in step.input_polynomials)
        return (
            certificate.agent_id == self.agent_id
            and step.replayed
            and certificate.premises == premises
            and set(premises) <= {item.canonical() for item in facts}
            and certificate.native_payload.get("output_polynomial") == output
            and certificate.native_payload.get("replayed") is True
            and certificate.native_payload.get("ideal_membership_witnesses")
            == tuple(asdict(item) for item in step.ideal_membership_witnesses)
        )


def coordinate_polynomial_stalk(
    result: LocalEliminationResult,
    *,
    external_goal_polynomial: str | None = None,
) -> PolynomialStalkCoordinationReport:
    """Replay every nontrivial derived polynomial through the typed coordinator."""

    stalk = build_polynomial_stalk(result)
    entities = {
        argument
        for atom in (*stalk.initial_atoms, *stalk.derived_atoms)
        for argument in atom.arguments
    }
    adapters = tuple(
        PolynomialEliminationStalkAdapter(
            replace(stalk, certificates=tuple(certificates)),
            agent_id=(f"polynomial-stalk-{index:03d}-{step.certificate_sha256[:12]}"),
        )
        for index, step in enumerate(result.steps)
        if (
            certificates := tuple(
                (candidate_step, output)
                for candidate_step, output in stalk.certificates
                if candidate_step == step
            )
        )
    )
    coordinator = ExactSheafCoordinator(
        TypedVocabulary(
            signatures={"poly_zero": PredicateSignature("poly_zero", ("Polynomial",))},
            entity_sorts={entity: "Polynomial" for entity in entities},
        ),
        adapters,
    )
    results = tuple(
        coordinator.solve(
            stalk.initial_atoms,
            goal,
            max_rounds=max(1, len(result.steps) + 1),
        )
        for goal in stalk.derived_atoms
    )
    depths = tuple(len(item.proof_slice()) for item in results)
    active_agents = {
        certificate.agent_id for item in results for certificate in item.proof_slice()
    }
    external_result = None
    if external_goal_polynomial is not None:
        goal = sp.sympify(external_goal_polynomial)
        for atom, expression in stalk.expression_by_atom.items():
            ratio = sp.cancel(sp.sympify(expression) / goal) if goal != 0 else sp.nan
            if ratio != 0 and not ratio.free_symbols:
                external_result = coordinator.solve(
                    stalk.initial_atoms,
                    atom,
                    max_rounds=max(1, len(result.steps) + 1),
                )
                break
    return PolynomialStalkCoordinationReport(
        local_agent_count=len(adapters),
        active_agent_count=len(active_agents),
        maximum_separator_variable_width=max(
            (len(item.separator_variables) for item in result.steps),
            default=0,
        ),
        initial_fact_count=len(stalk.initial_atoms),
        derived_goal_count=len(results),
        solved_goal_count=sum(item.solved for item in results),
        replayed_goal_count=sum(item.replayed for item in results),
        accepted_certificate_count=sum(len(item.certificates) for item in results),
        rejected_certificate_count=sum(len(item.rejected) for item in results),
        maximum_proof_depth=max(depths, default=0),
        mean_proof_depth=fmean(depths) if depths else 0.0,
        external_goal_matched=external_result is not None,
        external_goal_solved=bool(external_result and external_result.solved),
        external_goal_replayed=bool(external_result and external_result.replayed),
        external_goal_proof_depth=(
            len(external_result.proof_slice()) if external_result else 0
        ),
    )
