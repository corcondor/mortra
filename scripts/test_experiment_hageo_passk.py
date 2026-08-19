from __future__ import annotations

from types import SimpleNamespace
import random
import unittest

from worker.backend.hageo_search_control import (
    candidate_pool,
    proof_residual_order_key,
    rank_biased_shortlist,
)


class HageoPassKControlTest(unittest.TestCase):
    def test_typed_portfolio_does_not_treat_incidence_as_a_hard_gate(self) -> None:
        candidates = [SimpleNamespace(key="heuristic"), SimpleNamespace(key="formal")]
        audit = {
            "numerical_incidence": {
                "selected_candidates": [
                    {"step_key": "heuristic", "is_heuristic_candidate": True},
                    {"step_key": "formal", "is_heuristic_candidate": False},
                ]
            }
        }
        self.assertEqual(
            [item.key for item in candidate_pool(candidates, audit, hard_incidence_gate=False)],
            ["heuristic", "formal"],
        )
        self.assertEqual(
            [item.key for item in candidate_pool(candidates, audit, hard_incidence_gate=True)],
            ["heuristic"],
        )

    def test_typed_portfolio_interleaves_family_representatives(self) -> None:
        candidates = [
            SimpleNamespace(key="a9", family="a", structural_rank=(9,)),
            SimpleNamespace(key="a0", family="a", structural_rank=(0,)),
            SimpleNamespace(key="b0", family="b", structural_rank=(0,)),
        ]
        audit = {
            "numerical_incidence": {
                "selected_candidates": [
                    {"step_key": item.key, "is_heuristic_candidate": False}
                    for item in candidates
                ]
            }
        }
        ordered = candidate_pool(
            candidates,
            audit,
            hard_incidence_gate=False,
            preserve_family_frontier=True,
        )
        self.assertEqual([item.key for item in ordered[:3]], ["a9", "a0", "b0"])

    def test_goal_information_precedes_frontier_cardinality(self) -> None:
        rich = {
            "open_relation_demands": 24,
            "backward_obligations": 24,
            "ar_closed_goals": 0,
            "ar_residual_support": 2,
            "ar_residual_l1": 2.0,
            "ar_known_rank": 26,
        }
        shallow = {**rich, "open_relation_demands": 16, "ar_known_rank": 20}
        self.assertLess(proof_residual_order_key(rich), proof_residual_order_key(shallow))

    def test_ranked_shortlist_is_reproducible_and_without_replacement(self) -> None:
        first = rank_biased_shortlist(
            list("abcdef"), count=4, rng=random.Random(7), temperature=2.0
        )
        second = rank_biased_shortlist(
            list("abcdef"), count=4, rng=random.Random(7), temperature=2.0
        )
        self.assertEqual(first, second)
        self.assertEqual(len({rank for rank, _ in first}), 4)

    def test_ranked_shortlist_stratifies_independent_trajectories(self) -> None:
        pool = list("abcdefghij")
        first = rank_biased_shortlist(
            pool, count=3, rng=random.Random(0), temperature=2.0, trajectory_index=1
        )
        second = rank_biased_shortlist(
            pool, count=3, rng=random.Random(1), temperature=2.0, trajectory_index=2
        )
        self.assertEqual([rank for rank, _ in first], [1, 2, 3])
        self.assertEqual([rank for rank, _ in second], [4, 5, 6])


if __name__ == "__main__":
    unittest.main()
