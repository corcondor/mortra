from __future__ import annotations

import unittest

from worker.backend.adaptive_search_budget import (
    AdaptiveBudgetPolicy,
    ProofResidual,
    SearchStage,
    StageObservation,
    best_attempt_residual,
)


def residual(open_demands: int, support: int = 4) -> ProofResidual:
    return ProofResidual(open_demands, 2, 1, 0, support, float(support), 20)


class AdaptiveSearchBudgetTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = AdaptiveBudgetPolicy(
            start_depth=2,
            max_depth=6,
            depth_step=2,
            initial_attempts=4,
            max_attempts=16,
        )

    def test_improvement_deepens_without_spending_max_k(self) -> None:
        observation = StageObservation(
            SearchStage(2, 4), False, 4, 4, 0, residual(4)
        )
        decision = self.policy.decide([observation], baseline=residual(5))
        self.assertEqual(decision.reason, "typed_residual_improved_deepen")
        self.assertEqual(decision.next_stage, SearchStage(4, 4))

    def test_stall_increases_independent_trials_before_depth(self) -> None:
        observation = StageObservation(
            SearchStage(2, 4), False, 4, 4, 0, residual(5)
        )
        decision = self.policy.decide([observation], baseline=residual(5))
        self.assertEqual(
            decision.reason, "residual_stalled_increase_independent_trials"
        )
        self.assertEqual(decision.next_stage, SearchStage(2, 8))

    def test_native_certificate_stops(self) -> None:
        observation = StageObservation(
            SearchStage(2, 4), True, 1, 1, 0, residual(0, 0)
        )
        decision = self.policy.decide([observation], baseline=residual(5))
        self.assertFalse(decision.continue_search)
        self.assertEqual(decision.reason, "native_certificate_found")

    def test_feedback_window_expands_before_depth_or_trials(self) -> None:
        policy = AdaptiveBudgetPolicy(
            start_depth=2,
            max_depth=6,
            initial_attempts=1,
            max_attempts=4,
            initial_feedback_candidates=16,
            max_feedback_candidates=48,
            feedback_growth=3,
        )
        observation = StageObservation(
            SearchStage(2, 1, 16), False, 1, 1, 0, residual(4)
        )
        decision = policy.decide([observation], baseline=residual(5))
        self.assertEqual(decision.reason, "candidate_feedback_window_increase")
        self.assertEqual(decision.next_stage, SearchStage(2, 1, 48))

    def test_stage_timeout_is_recorded_instead_of_increasing_budget(self) -> None:
        observation = StageObservation(
            SearchStage(2, 4), False, 0, 0, 0, None, right_censored=True
        )
        decision = self.policy.decide([observation], baseline=residual(5))
        self.assertFalse(decision.continue_search)
        self.assertEqual(decision.reason, "right_censored_stage_timeout")

    def test_best_attempt_residual_prioritizes_algebraic_residual_over_frontier_size(self) -> None:
        value = best_attempt_residual(
            [
                {"proof_residual": residual(5).to_dict()},
                {"proof_residual": residual(4, 9).to_dict()},
            ]
        )
        self.assertEqual(value, residual(5))


if __name__ == "__main__":
    unittest.main()
