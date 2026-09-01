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


if __name__ == "__main__":
    unittest.main()
