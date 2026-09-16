from __future__ import annotations

import unittest

from math_os_prototype.runtime_typed_planner import (
    PrimitiveResult,
    RuntimePrimitive,
    initial_fact,
    synthesize_typed_plan,
)


class RuntimeTypedPlannerTests(unittest.TestCase):
    def test_planner_composes_only_goal_relevant_primitives(self) -> None:
        primitives = (
            RuntimePrimitive(
                "a_to_b",
                ("A",),
                "B",
                lambda facts: PrimitiveResult(facts[0].value + 1, {"verified": True}),
            ),
            RuntimePrimitive(
                "b_to_c",
                ("B",),
                "C",
                lambda facts: PrimitiveResult(facts[0].value * 2, {"verified": True}),
            ),
            RuntimePrimitive(
                "irrelevant_branch",
                ("A",),
                "X",
                lambda facts: PrimitiveResult(999, {"verified": True}),
            ),
        )

        plan = synthesize_typed_plan([initial_fact("A", 3)], primitives, ["C"])

        self.assertTrue(plan.complete)
        self.assertEqual(plan.goals["C"].value, 8)
        self.assertEqual(
            [step["rule"] for step in plan.proof_program],
            ["a_to_b", "b_to_c"],
        )
        self.assertFalse(any(fact.sort == "X" for fact in plan.facts))

    def test_missing_primitive_remains_an_explicit_open_goal(self) -> None:
        plan = synthesize_typed_plan(
            [initial_fact("A", 1)],
            (),
            ["CertifiedAnswer"],
        )

        self.assertFalse(plan.complete)
        self.assertEqual(plan.open_goal_sorts, ("CertifiedAnswer",))

    def test_goal_sort_terminates_before_another_expensive_alternative(self):
        def alternatives(args):
            yield lambda: PrimitiveResult(7, {"verified": True})
            yield lambda: self.fail("goal already reached")
        plan = synthesize_typed_plan([initial_fact("A", 1)], [
            RuntimePrimitive("prove", ("A",), "Proof", lambda a: None, alternatives)],
            ["Proof"], fair=True)
        self.assertTrue(plan.complete)
        self.assertEqual(plan.states_explored, 2)


class OfferAccountingTests(unittest.TestCase):
    """What `max_states` counts, with and without `max_offers`.

    The domain below refuses four of every five applications. Nothing about the
    candidates changes between the two cases; only the accounting does.
    """

    @staticmethod
    def _mostly_refusing(accept_every: int = 5):
        state = {"offers": 0}

        def alternatives(facts):
            parent = facts[0].value
            for index in range(1000):
                def invoke(parent=parent, index=index):
                    state["offers"] += 1
                    if state["offers"] % accept_every:
                        return None
                    return PrimitiveResult(parent + index + 1, {"verified": True})
                yield invoke

        primitive = RuntimePrimitive(
            "step", ("N",), "N", lambda facts: None, alternatives=alternatives)
        return primitive, state

    def test_without_max_offers_a_refusal_costs_the_same_as_a_state(self) -> None:
        primitive, counter = self._mostly_refusing()
        plan = synthesize_typed_plan(
            [initial_fact("N", 0)], (primitive,), ["N"],
            goal_predicates={"N": lambda fact: False},
            max_states=21, max_depth=3, fair=True)
        # 20 applications are offered after the initial fact; one in five is
        # accepted, so the budget stops the search at four retained states.
        self.assertEqual(counter["offers"], 20)
        self.assertEqual(plan.states_explored, 21)
        self.assertEqual(plan.offers_examined, 20)
        self.assertEqual(len(plan.facts), 5)

    def test_with_max_offers_the_budget_counts_accepted_applications(self) -> None:
        primitive, counter = self._mostly_refusing()
        plan = synthesize_typed_plan(
            [initial_fact("N", 0)], (primitive,), ["N"],
            goal_predicates={"N": lambda fact: False},
            max_states=21, max_offers=200, max_depth=3, fair=True)
        # The same candidates, the same refusals; twenty states are now reached
        # because the eighty refusals no longer consume the state budget.
        self.assertEqual(plan.states_explored, 21)
        self.assertEqual(len(plan.facts), 21)
        self.assertEqual(plan.offers_examined, 100)
        self.assertEqual(counter["offers"], 100)

    def test_max_offers_terminates_a_domain_that_accepts_nothing(self) -> None:
        def alternatives(facts):
            for _ in range(10_000):
                yield lambda: None

        primitive = RuntimePrimitive(
            "step", ("N",), "N", lambda facts: None, alternatives=alternatives)
        plan = synthesize_typed_plan(
            [initial_fact("N", 0)], (primitive,), ["N"],
            goal_predicates={"N": lambda fact: False},
            max_states=257, max_offers=64, max_depth=3, fair=True)
        self.assertEqual(plan.offers_examined, 64)
        self.assertEqual(plan.states_explored, 1)
        self.assertEqual(len(plan.facts), 1)

    def test_the_option_changes_no_result_when_nothing_is_refused(self) -> None:
        primitives = (
            RuntimePrimitive(
                "a_to_b", ("A",), "B",
                lambda facts: PrimitiveResult(facts[0].value + 1, {"verified": True})),
            RuntimePrimitive(
                "b_to_c", ("B",), "C",
                lambda facts: PrimitiveResult(facts[0].value * 2, {"verified": True})),
        )
        without = synthesize_typed_plan([initial_fact("A", 3)], primitives, ["C"])
        with_offers = synthesize_typed_plan(
            [initial_fact("A", 3)], primitives, ["C"], max_offers=4096)
        self.assertTrue(without.complete and with_offers.complete)
        self.assertEqual(without.goals["C"].value, with_offers.goals["C"].value)
        self.assertEqual(without.proof_program, with_offers.proof_program)


if __name__ == "__main__":
    unittest.main()
