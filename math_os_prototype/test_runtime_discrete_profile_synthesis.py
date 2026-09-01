from __future__ import annotations

import unittest

import sympy as sp

from math_os_prototype.runtime_discrete_profile_synthesis import (
    compile_discrete_trig_profile_query,
    synthesize_discrete_trig_profile_problem,
)


def _problem(frequency: int, lower: int, index: str, sequence: str) -> str:
    coefficient = "" if frequency == 1 else str(frequency)
    argument = rf"\frac{{{coefficient}\pi}}{{{index}}}"
    return rf"""
    自然数 \({index}\geq {lower}\) に対し，
    \[
    {sequence}_{index}=(\sin{argument}+\cos{argument})^{{
    \frac{{1}}{{\sin{argument}+\cos{argument}-1}}
    +\sin{argument}+\cos{argument}-1}}
    \]
    と定める。数列 \(\{{{sequence}_{index}\}}\) の最小値を求め，さらに
    \[
    \lim_{{{index}\to\infty}}{index}(e-{sequence}_{index})
    \]
    を求めよ。
    """


class RuntimeDiscreteProfileSynthesisTests(unittest.TestCase):
    def test_original_profile_discovers_twelve_at_runtime(self) -> None:
        result = synthesize_discrete_trig_profile_problem(_problem(1, 4, "n", "a"))

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.witness["selected_index"], 12)
        self.assertIn(12, result.witness["generated_candidates"])
        self.assertEqual(result.witness["scaled_limit"], "E*pi/2")
        self.assertFalse(result.witness["registered_solution_consulted"])
        rules = [step["rule"] for step in result.proof_program]
        self.assertIn("runtime_derivative_root_search", rules)
        self.assertIn("monotone_integer_candidate_generation", rules)
        self.assertIn("exact_candidate_interval_comparison", rules)

    def test_changed_frequency_recomputes_minimizer_and_limit(self) -> None:
        result = synthesize_discrete_trig_profile_problem(_problem(2, 8, "m", "b"))

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.witness["selected_index"], 24)
        self.assertEqual(sp.sympify(result.witness["scaled_limit"]), sp.E * sp.pi)
        self.assertEqual(result.witness["input_ir"]["angular_frequency"], 2)

    def test_unregistered_third_frequency_selects_non_scaled_index(self) -> None:
        result = synthesize_discrete_trig_profile_problem(_problem(3, 12, "k", "z"))

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.witness["selected_index"], 37)
        self.assertNotEqual(result.witness["selected_index"], 3 * 12)
        self.assertEqual(
            sp.sympify(result.witness["scaled_limit"]),
            3 * sp.E * sp.pi / 2,
        )

    def test_changed_exponent_is_not_silently_accepted(self) -> None:
        malformed = _problem(1, 4, "n", "a").replace(
            r"+\sin\frac{\pi}{n}+\cos\frac{\pi}{n}-1",
            r"+2\sin\frac{\pi}{n}+\cos\frac{\pi}{n}-1",
        )

        self.assertIsNone(compile_discrete_trig_profile_query(malformed))


if __name__ == "__main__":
    unittest.main()
