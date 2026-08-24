from __future__ import annotations

import unittest

from worker.backend.yuclid_proof_trace import build_proof_trace, classify_term


class YuclidProofTraceTests(unittest.TestCase):
    def test_distinguishes_sine_and_squared_distance_terms(self) -> None:
        self.assertEqual(classify_term(r"\sin² ∠(a b c)"), "sine_squared")
        self.assertEqual(classify_term("|a-b|^2"), "squared_distance")
        self.assertEqual(classify_term("∠(a-b)"), "directed_angle")

    def test_links_exact_statement_and_marks_mixed_bridge(self) -> None:
        mixed = {
            "name": "equation_class Yuclid::SinOrDist",
            "points": ["a", "b", "c"],
            "lhs_terms": {r"\sin² ∠(a b c)": "1/1", "|a-b|^2": "-1/1"},
        }
        payload = {
            "deductions_for_goal": [
                {
                    "deduction_type": "rule",
                    "newclid_rule": "ignore",
                    "assumptions": [],
                    "assertions": [mixed],
                },
                {
                    "deduction_type": "ar",
                    "ar_reason": "ratio chasing",
                    "assumptions": [mixed],
                    "assertions": [
                        {
                            "name": "cong",
                            "points": ["a", "b", "a", "c"],
                            "lhs_terms": {"|a-b|^2": "1/1", "|a-c|^2": "-1/1"},
                        }
                    ],
                },
            ]
        }
        nodes = build_proof_trace(payload)
        self.assertEqual(nodes[1].assumption_producers, (0,))
        self.assertEqual(nodes[1].assumption_link_modes, ("exact",))
        self.assertTrue(nodes[1].is_cross_chart_bridge)

    def test_links_type_erased_equation_by_ordered_points(self) -> None:
        payload = {
            "deductions_for_goal": [
                {
                    "deduction_type": "rule",
                    "newclid_rule": "ignore",
                    "assumptions": [],
                    "assertions": [
                        {
                            "name": "equation_class Yuclid::SinOrDist",
                            "points": ["a", "b", "c", "d", "e", "f"],
                        }
                    ],
                },
                {
                    "deduction_type": "ar",
                    "ar_reason": "ratio chasing",
                    "assumptions": [
                        {
                            "name": "equation_class Yuclid::SinOrDist",
                            "points": ["a", "b", "c", "d", "e", "f"],
                            "lhs_terms": {
                                r"\sin² ∠(a b c)": "1/1",
                                r"\sin² ∠(d e f)": "-1/1",
                            },
                        }
                    ],
                    "assertions": [{"name": "eqangle", "points": ["a", "b"]}],
                },
            ]
        }
        nodes = build_proof_trace(payload)
        self.assertEqual(nodes[1].assumption_producers, (0,))
        self.assertEqual(
            nodes[1].assumption_link_modes, ("equation_points_fallback",)
        )


if __name__ == "__main__":
    unittest.main()
