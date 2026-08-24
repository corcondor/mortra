"""Residual-driven CEGIS for finite typed auxiliary constructions.

Candidate generation and mathematical acceptance remain separate.  The chart
residual is only a proposal filter; a construction is promoted only after an
exact external verifier returns a replayable certificate.  This makes the
loop usable with Newclid, GCLC, Wu, or Groebner verifiers without making any
one representation the source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Sequence

from worker.backend.geometry_proof_hypergraph import Atom
from worker.backend.geometry_representation_atlas import (
    RelationChartResidual,
    lift_relation,
    relation_chart_residual,
)
from worker.backend.typed_lemma_cegis import LemmaVerification
from worker.backend.typed_construction_contracts import (
    assess_construction_requirements,
)


@dataclass(frozen=True)
class TypedConstructionProposal:
    key: str
    family: str
    inputs: tuple[str, ...]
    postconditions: tuple[Atom, ...]
    requirements: tuple[Atom, ...] = ()


@dataclass(frozen=True)
class ConstructionCEGISTrial:
    proposal: TypedConstructionProposal
    before_rank: tuple[int, int, int]
    after_rank: tuple[int, int, int]
    residual_reduced: bool
    chart_replayed: bool
    verification: LemmaVerification | None
    requirements_satisfied: bool = True
    open_requirements: tuple[Atom, ...] = ()
    contradictory_requirements: tuple[Atom, ...] = ()

    @property
    def accepted(self) -> bool:
        return bool(
            self.residual_reduced
            and self.chart_replayed
            and self.requirements_satisfied
            and self.verification is not None
            and self.verification.certified
        )


@dataclass(frozen=True)
class ConstructionCEGISResult:
    baseline: RelationChartResidual
    trials: tuple[ConstructionCEGISTrial, ...]
    accepted: tuple[ConstructionCEGISTrial, ...]
    rejected_counterexamples: tuple[ConstructionCEGISTrial, ...]
    unknown: tuple[ConstructionCEGISTrial, ...]
    skipped_no_residual_progress: tuple[ConstructionCEGISTrial, ...]


def proposal_residual(
    facts: Iterable[Atom],
    branches: Iterable[Iterable[Atom]],
    proposal: TypedConstructionProposal,
) -> RelationChartResidual:
    return relation_chart_residual(
        (*tuple(facts), *proposal.postconditions),
        branches,
    )


def rank_construction_proposals(
    facts: Iterable[Atom],
    branches: Iterable[Iterable[Atom]],
    proposals: Sequence[TypedConstructionProposal],
) -> tuple[tuple[TypedConstructionProposal, tuple[int, int, int], bool], ...]:
    facts = tuple(facts)
    branches = tuple(tuple(branch) for branch in branches)
    baseline = relation_chart_residual(facts, branches)
    ranked = []
    for proposal in proposals:
        assessment = assess_construction_requirements(proposal.requirements, facts)
        residual = proposal_residual(facts, branches, proposal)
        ranked.append(
            (
                proposal,
                residual.selected_rank,
                (
                    assessment.executable
                    and residual.selected_rank < baseline.selected_rank
                ),
            )
        )
    return tuple(
        sorted(
            ranked,
            key=lambda item: (
                0
                if assess_construction_requirements(
                    item[0].requirements, facts
                ).executable
                else 1,
                0 if item[2] else 1,
                item[1],
                item[0].family,
                item[0].inputs,
                item[0].key,
            ),
        )
    )


def run_residual_construction_cegis(
    facts: Iterable[Atom],
    branches: Iterable[Iterable[Atom]],
    proposals: Sequence[TypedConstructionProposal],
    *,
    verifier: Callable[[TypedConstructionProposal], LemmaVerification],
    counterexample_oracle: Callable[
        [TypedConstructionProposal], LemmaVerification | None
    ]
    | None = None,
    max_verifications: int = 32,
) -> ConstructionCEGISResult:
    """Refute first and verify only candidates reducing a coherent branch."""

    facts = tuple(facts)
    branches = tuple(tuple(branch) for branch in branches)
    baseline = relation_chart_residual(facts, branches)
    trials: list[ConstructionCEGISTrial] = []
    verified_count = 0
    for proposal, after_rank, reduced in rank_construction_proposals(
        facts, branches, proposals
    ):
        requirement_assessment = assess_construction_requirements(
            proposal.requirements, facts
        )
        lifts = tuple(
            lift
            for atom in proposal.postconditions
            if (lift := lift_relation(atom)) is not None
        )
        chart_replayed = bool(lifts) and all(item.replayed for item in lifts)
        verification = None
        if reduced and chart_replayed and verified_count < max_verifications:
            refutation = (
                counterexample_oracle(proposal)
                if counterexample_oracle is not None
                else None
            )
            if refutation is not None and refutation.status == "counterexample":
                verification = refutation
            else:
                verification = verifier(proposal)
            verified_count += 1
        trials.append(
            ConstructionCEGISTrial(
                proposal=proposal,
                before_rank=baseline.selected_rank,
                after_rank=after_rank,
                residual_reduced=reduced,
                chart_replayed=chart_replayed,
                verification=verification,
                requirements_satisfied=requirement_assessment.executable,
                open_requirements=requirement_assessment.open,
                contradictory_requirements=requirement_assessment.contradictory,
            )
        )
    trial_tuple = tuple(trials)
    return ConstructionCEGISResult(
        baseline=baseline,
        trials=trial_tuple,
        accepted=tuple(item for item in trial_tuple if item.accepted),
        rejected_counterexamples=tuple(
            item
            for item in trial_tuple
            if item.verification is not None
            and item.verification.status == "counterexample"
        ),
        unknown=tuple(
            item
            for item in trial_tuple
            if item.residual_reduced
            and item.chart_replayed
            and item.requirements_satisfied
            and not item.accepted
            and not (
                item.verification is not None
                and item.verification.status == "counterexample"
            )
        ),
        skipped_no_residual_progress=tuple(
            item
            for item in trial_tuple
            if (
                not item.residual_reduced
                or not item.chart_replayed
                or not item.requirements_satisfied
            )
        ),
    )


__all__ = [
    "ConstructionCEGISResult",
    "ConstructionCEGISTrial",
    "TypedConstructionProposal",
    "proposal_residual",
    "rank_construction_proposals",
    "run_residual_construction_cegis",
]
