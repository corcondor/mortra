"""Residual-driven depth and trial allocation for exact proof search.

The controller never decides mathematical truth.  It observes only typed proof
residuals and allocates the next finite search budget.  A native certificate
checker remains the sole acceptance rule.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class ProofResidual:
    open_relation_demands: int
    backward_obligations: int
    ar_supported_goals: int
    ar_closed_goals: int
    ar_residual_support: int
    ar_residual_l1: float
    ar_known_rank: int

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ProofResidual":
        return cls(
            open_relation_demands=int(value.get("open_relation_demands", 0)),
            backward_obligations=int(value.get("backward_obligations", 0)),
            ar_supported_goals=int(value.get("ar_supported_goals", 0)),
            ar_closed_goals=int(value.get("ar_closed_goals", 0)),
            ar_residual_support=int(value.get("ar_residual_support", 0)),
            ar_residual_l1=float(value.get("ar_residual_l1", 0.0)),
            ar_known_rank=int(value.get("ar_known_rank", 0)),
        )

    @property
    def order_key(self) -> tuple[float, ...]:
        """Smaller is better; every coordinate has proof-state semantics."""

        # Newly useful facts can expose more backward obligations, so raw
        # frontier size is not a monotone proof residual.  Goal closure and
        # exact algebraic residual lead; frontier counts only break ties.
        return (
            float(-self.ar_closed_goals),
            float(self.ar_residual_support),
            float(self.ar_residual_l1),
            float(-self.ar_known_rank),
            float(self.backward_obligations),
            float(self.open_relation_demands),
        )

    def improves(self, other: "ProofResidual") -> bool:
        return self.order_key < other.order_key

    def to_dict(self) -> dict[str, int | float]:
        return {
            "open_relation_demands": self.open_relation_demands,
            "backward_obligations": self.backward_obligations,
            "ar_supported_goals": self.ar_supported_goals,
            "ar_closed_goals": self.ar_closed_goals,
            "ar_residual_support": self.ar_residual_support,
            "ar_residual_l1": self.ar_residual_l1,
            "ar_known_rank": self.ar_known_rank,
        }


@dataclass(frozen=True)
class SearchStage:
    depth: int
    attempts: int
    feedback_candidates: int = 16


@dataclass(frozen=True)
class StageObservation:
    stage: SearchStage
    solved: bool
    completed_attempts: int
    unique_paths: int
    execution_errors: int
    best_residual: ProofResidual | None
    right_censored: bool = False


@dataclass(frozen=True)
class BudgetDecision:
    continue_search: bool
    reason: str
    next_stage: SearchStage | None


def best_attempt_residual(
    attempts: Sequence[Mapping[str, Any]],
) -> ProofResidual | None:
    values = [
        ProofResidual.from_mapping(item["proof_residual"])
        for item in attempts
        if isinstance(item.get("proof_residual"), Mapping)
    ]
    return min(values, key=lambda item: item.order_key) if values else None


class AdaptiveBudgetPolicy:
    """Allocate K before N only when the exact residual has stalled."""

    def __init__(
        self,
        *,
        start_depth: int = 2,
        max_depth: int = 8,
        depth_step: int = 2,
        initial_attempts: int = 4,
        max_attempts: int = 32,
        attempt_growth: int = 2,
        initial_feedback_candidates: int = 16,
        max_feedback_candidates: int = 16,
        feedback_growth: int = 3,
    ) -> None:
        if min(
            start_depth,
            max_depth,
            depth_step,
            initial_attempts,
            max_attempts,
            initial_feedback_candidates,
            max_feedback_candidates,
        ) < 1:
            raise ValueError("all adaptive budgets must be positive")
        if (
            start_depth > max_depth
            or initial_attempts > max_attempts
            or initial_feedback_candidates > max_feedback_candidates
        ):
            raise ValueError("initial budget must not exceed maximum budget")
        if attempt_growth < 2 or feedback_growth < 2:
            raise ValueError("budget growth must be at least two")
        self.start_depth = start_depth
        self.max_depth = max_depth
        self.depth_step = depth_step
        self.initial_attempts = initial_attempts
        self.max_attempts = max_attempts
        self.attempt_growth = attempt_growth
        self.initial_feedback_candidates = initial_feedback_candidates
        self.max_feedback_candidates = max_feedback_candidates
        self.feedback_growth = feedback_growth

    @property
    def initial_stage(self) -> SearchStage:
        return SearchStage(
            self.start_depth,
            self.initial_attempts,
            self.initial_feedback_candidates,
        )

    def decide(
        self,
        observations: Sequence[StageObservation],
        *,
        baseline: ProofResidual,
    ) -> BudgetDecision:
        if not observations:
            return BudgetDecision(True, "initial", self.initial_stage)
        current = observations[-1]
        if current.solved:
            return BudgetDecision(False, "native_certificate_found", None)
        if current.right_censored:
            return BudgetDecision(False, "right_censored_stage_timeout", None)
        if current.completed_attempts == 0 and current.execution_errors > 0:
            return BudgetDecision(False, "all_attempts_failed_to_execute", None)

        previous_best = baseline
        for observation in observations[:-1]:
            if (
                observation.best_residual is not None
                and observation.best_residual.improves(previous_best)
            ):
                previous_best = observation.best_residual
        improved = (
            current.best_residual is not None
            and current.best_residual.improves(previous_best)
        )

        if current.stage.feedback_candidates < self.max_feedback_candidates:
            return BudgetDecision(
                True,
                "candidate_feedback_window_increase",
                SearchStage(
                    current.stage.depth,
                    current.stage.attempts,
                    min(
                        self.max_feedback_candidates,
                        current.stage.feedback_candidates * self.feedback_growth,
                    ),
                ),
            )
        if improved and current.stage.depth < self.max_depth:
            return BudgetDecision(
                True,
                "typed_residual_improved_deepen",
                SearchStage(
                    min(self.max_depth, current.stage.depth + self.depth_step),
                    self.initial_attempts,
                    self.initial_feedback_candidates,
                ),
            )
        if current.stage.attempts < self.max_attempts:
            return BudgetDecision(
                True,
                "residual_stalled_increase_independent_trials",
                SearchStage(
                    current.stage.depth,
                    min(self.max_attempts, current.stage.attempts * self.attempt_growth),
                    current.stage.feedback_candidates,
                ),
            )
        if current.stage.depth < self.max_depth:
            return BudgetDecision(
                True,
                "trial_budget_saturated_deepen",
                SearchStage(
                    min(self.max_depth, current.stage.depth + self.depth_step),
                    self.initial_attempts,
                    self.initial_feedback_candidates,
                ),
            )
        return BudgetDecision(False, "finite_budget_exhausted", None)
