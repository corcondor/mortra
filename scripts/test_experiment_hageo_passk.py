from __future__ import annotations

from types import SimpleNamespace
import random
import unittest

from worker.backend.geometry_proof_hypergraph import Atom
from worker.backend.hageo_search_control import (
    candidate_made_causal_progress,
    candidate_policy_spec,
    candidate_pool,
    next_relation_demands,
    proof_dag_search_roots,
    proof_residual_order_key,
    relation_demand_transition,
    rank_biased_shortlist,
    mixed_credit_residual_shortlist,
    obligation_conditioned_credit_ranking,
    obligation_conditioned_selection_key,
    verified_obligation_credit,
)


class HageoPassKControlTest(unittest.TestCase):
    def test_residual_ablation_differs_only_by_feedback(self) -> None:
        static = candidate_policy_spec("residual-static")
        feedback = candidate_policy_spec("residual-feedback")

        self.assertEqual(static.alignment_mode, "typed-atom")
        self.assertEqual(static.alignment_mode, feedback.alignment_mode)
        self.assertEqual(static.hard_incidence_gate, feedback.hard_incidence_gate)
        self.assertEqual(
            static.preserve_family_frontier,
            feedback.preserve_family_frontier,
        )
        self.assertFalse(static.residual_feedback)
        self.assertTrue(feedback.residual_feedback)

    def test_contract_portfolio_adds_only_typed_candidate_synthesis(self) -> None:
        control = candidate_policy_spec("residual-portfolio")
        treatment = candidate_policy_spec("contract-portfolio")

        self.assertEqual(control.alignment_mode, treatment.alignment_mode)
        self.assertEqual(control.hard_incidence_gate, treatment.hard_incidence_gate)
        self.assertEqual(control.residual_feedback, treatment.residual_feedback)
        self.assertFalse(control.typed_contract_synthesis)
        self.assertTrue(treatment.typed_contract_synthesis)

    def test_residual_construction_enables_ground_goal_synthesis(self) -> None:
        policy = candidate_policy_spec("residual-construction")

        self.assertTrue(policy.structured)
        self.assertEqual(policy.alignment_mode, "proof-dag-priority")
        self.assertTrue(policy.residual_feedback)
        self.assertTrue(policy.typed_contract_synthesis)
        self.assertTrue(policy.ground_residual_synthesis)

    def test_ground_residual_policy_keeps_or_branches_inside_proof_dag(self) -> None:
        policy = candidate_policy_spec("residual-construction")
        final_goals = (Atom("cyclic", ("a", "b", "c", "d")),)
        flattened_alternatives = tuple(
            Atom("coll", (f"x{index}", "a", "b")) for index in range(64)
        )

        search_roots = proof_dag_search_roots(
            final_goals,
            flattened_alternatives,
            ground_residual_synthesis=policy.ground_residual_synthesis,
        )

        self.assertEqual(search_roots, final_goals)

    def test_ground_candidate_requires_native_parent_obligation_closure(self) -> None:
        self.assertTrue(
            candidate_made_causal_progress(
                solved=False,
                ground_residual_synthesis=True,
                matched_obligation_atoms=0,
                closed_parent_demands=1,
                circular_goal_transport=False,
                typed_plan_supported=False,
            )
        )
        self.assertFalse(
            candidate_made_causal_progress(
                solved=False,
                ground_residual_synthesis=True,
                matched_obligation_atoms=4,
                closed_parent_demands=0,
                circular_goal_transport=False,
                typed_plan_supported=False,
            )
        )
        self.assertFalse(
            candidate_made_causal_progress(
                solved=False,
                ground_residual_synthesis=True,
                matched_obligation_atoms=0,
                closed_parent_demands=2,
                circular_goal_transport=True,
                typed_plan_supported=True,
            )
        )

    def test_typed_plan_can_continue_but_cannot_count_as_truth(self) -> None:
        self.assertTrue(
            candidate_made_causal_progress(
                solved=False,
                ground_residual_synthesis=True,
                matched_obligation_atoms=0,
                closed_parent_demands=0,
                circular_goal_transport=False,
                typed_plan_supported=True,
            )
        )

    def test_terminal_credit_changes_control_plane_not_truth_plane(self) -> None:
        feedback = candidate_policy_spec("residual-feedback")
        terminal = candidate_policy_spec("terminal-credit")

        self.assertEqual(feedback.alignment_mode, terminal.alignment_mode)
        self.assertEqual(feedback.hard_incidence_gate, terminal.hard_incidence_gate)
        self.assertEqual(
            feedback.preserve_family_frontier,
            terminal.preserve_family_frontier,
        )
        self.assertEqual(feedback.residual_feedback, terminal.residual_feedback)
        self.assertFalse(feedback.terminal_credit)
        self.assertTrue(terminal.terminal_credit)

    def test_mixed_terminal_credit_reserves_exactly_one_slot(self) -> None:
        mixed = candidate_policy_spec("terminal-credit-mixed")
        control = candidate_policy_spec("residual-portfolio")

        self.assertTrue(mixed.terminal_credit)
        self.assertEqual(mixed.terminal_credit_mix, 1)
        self.assertEqual(mixed.hard_incidence_gate, control.hard_incidence_gate)
        self.assertEqual(mixed.alignment_mode, control.alignment_mode)
        self.assertEqual(mixed.residual_feedback, control.residual_feedback)

    def test_mixed_shortlist_preserves_residual_frontier(self) -> None:
        pool = [SimpleNamespace(key=value) for value in "abcde"]
        ranking = [
            {"candidate": "e", "credit_score": 0.4},
            {"candidate": "d", "credit_score": 0.3},
        ]

        selected, channels = mixed_credit_residual_shortlist(
            pool,
            ranking,
            count=4,
            rng=random.Random(0),
            temperature=0.0,
            credit_slots=1,
        )

        self.assertEqual([item.key for _, item in selected], ["e", "a", "b", "c"])
        self.assertEqual(
            [item["channel"] for item in channels],
            ["terminal_credit", "residual_frontier", "residual_frontier", "residual_frontier"],
        )

    def test_obligation_credit_requires_positive_credit_and_direct_match(self) -> None:
        ranking = [
            {"candidate": "foot", "credit_score": 0.4},
            {"candidate": "mirror", "credit_score": 0.3},
            {"candidate": "midpoint", "credit_score": 0.0},
        ]

        conditioned = obligation_conditioned_credit_ranking(
            ranking,
            {"mirror": ["coll(?x,a,b)"]},
        )

        self.assertEqual([item["candidate"] for item in conditioned], ["mirror"])
        self.assertEqual(conditioned[0]["direct_match_count"], 1)

    def test_obligation_credit_is_used_only_after_native_closure(self) -> None:
        residual = {
            "ar_closed_goals": 0,
            "closed_parent_demands": 1,
            "introduced_relation_demands": 0,
            "ar_residual_support": 1,
            "ar_residual_l1": 1.0,
            "ar_known_rank": 5,
            "backward_obligations": 2,
            "open_relation_demands": 1,
        }

        verified = obligation_conditioned_selection_key(
            solved=False,
            residual=residual,
            verified_credit=True,
            static_rank=3,
        )
        unverified = obligation_conditioned_selection_key(
            solved=False,
            residual=residual,
            verified_credit=False,
            static_rank=0,
        )

        self.assertLess(verified, unverified)

    def test_typed_hole_is_closed_by_ground_native_fact(self) -> None:
        transition = relation_demand_transition(
            (Atom("perp", ("?x", "a", "b", "c")),),
            (),
            proved=(Atom("perp", ("d", "a", "b", "c")),),
        )

        self.assertEqual(transition["closed_parent_demands"], 1)
        self.assertEqual(
            transition["closed_parent_obligations"],
            ["perp(?x,a,b,c)"],
        )

    def test_existing_parent_fact_is_not_credited_to_candidate(self) -> None:
        known = Atom("perp", ("d", "a", "b", "c"))
        transition = relation_demand_transition(
            (Atom("perp", ("?x", "a", "b", "c")),),
            (),
            proved=(known, Atom("coll", ("d", "a", "b"))),
            parent_proved=(known,),
        )

        self.assertEqual(transition["closed_parent_demands"], 0)
        self.assertEqual(transition["closed_parent_obligations"], [])
        self.assertEqual(transition["new_native_facts"], 1)

    def test_credit_requires_closure_of_the_same_matched_obligation(self) -> None:
        residual = {
            "closed_parent_obligations": ["coll(?x,a,b)"],
        }

        self.assertFalse(
            verified_obligation_credit(
                selection_channel="obligation_credit_probe",
                matched_obligations=["perp(?x,a,b,c)"],
                residual=residual,
            )
        )
        self.assertTrue(
            verified_obligation_credit(
                selection_channel="obligation_credit_probe",
                matched_obligations=["coll(?x,a,b)"],
                residual=residual,
            )
        )

    def test_closed_loop_advances_to_observed_relation_demands(self) -> None:
        current = ("old-a", "old-b")
        observed = ("new-a",)

        self.assertEqual(
            next_relation_demands(current, observed, feedback_enabled=False),
            current,
        )
        self.assertEqual(
            next_relation_demands(current, observed, feedback_enabled=True),
            observed,
        )

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

    def test_demand_transition_detects_progress_at_equal_cardinality(self) -> None:
        transition = relation_demand_transition(
            ("circle(a,b,c,d)", "perp(a,b,c,d)"),
            ("circle(a,b,c,d)", "para(a,b,c,d)"),
            proved=("perp(a,b,c,d)",),
        )

        self.assertEqual(transition["closed_parent_demands"], 1)
        self.assertEqual(transition["introduced_relation_demands"], 1)

    def test_closed_parent_demand_improves_candidate_rank(self) -> None:
        stalled = {
            "open_relation_demands": 24,
            "backward_obligations": 24,
            "ar_closed_goals": 0,
            "ar_residual_support": 2,
            "ar_residual_l1": 2.0,
            "ar_known_rank": 20,
            "closed_parent_demands": 0,
            "introduced_relation_demands": 0,
        }
        progressed = {
            **stalled,
            "closed_parent_demands": 1,
            "introduced_relation_demands": 1,
        }

        self.assertLess(
            proof_residual_order_key(progressed),
            proof_residual_order_key(stalled),
        )

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

    def test_certificate_credit_head_survives_trajectory_stratification(self) -> None:
        shortlist = rank_biased_shortlist(
            list("abcdefghij"),
            count=3,
            rng=random.Random(0),
            temperature=2.0,
            trajectory_index=2,
            protected_prefix=1,
        )

        self.assertEqual(shortlist[0], (0, "a"))
        self.assertEqual(len(shortlist), 3)


if __name__ == "__main__":
    unittest.main()
