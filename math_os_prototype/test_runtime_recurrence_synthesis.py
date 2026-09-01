from __future__ import annotations

import json
import unittest

from math_os_prototype.runtime_recurrence_synthesis import (
    compile_recurrence_triangle_floor_query,
    synthesize_recurrence_triangle_floor_problem,
)


CANONICAL_PROBLEM = r"""
\(n\in\mathbb N\) に対して \(x_n,x_{n+1},x_{n+2}\) が三角形の三辺をなし、
正の数列 \(\{x_n\}\) が
\[
x_{n+2}=p x_{n+1}+q x_n\qquad(p,q>0)
\]
を満たす。
\[
\lim_{n\to\infty}\left\lfloor
\frac{x_{n+2}}{x_n}+\frac{x_n}{x_{n+2}}
\right\rfloor
\]
を求めよ。
"""


class RuntimeRecurrenceSynthesisTests(unittest.TestCase):
    def test_triangle_constrained_recurrence_is_composed_at_runtime(self) -> None:
        result = synthesize_recurrence_triangle_floor_problem(CANONICAL_PROBLEM)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.answer_tex, r"\(2\)")
        self.assertEqual(
            result.witness["input_ir"]["recurrence"]["coefficients"]
            if "coefficients" in result.witness["input_ir"]["recurrence"]
            else [
                result.witness["input_ir"]["recurrence"]["leading_coefficient"],
                result.witness["input_ir"]["recurrence"]["trailing_coefficient"],
            ],
            ["p", "q"],
        )
        self.assertEqual(result.witness["endpoint_values"], {"at_inverse_phi": "3", "at_phi": "3"})
        rules = [step["rule"] for step in result.proof_program]
        self.assertIn("triangle_inequality_limit_projection", rules)
        self.assertIn("alternating_subdominant_endpoint_exclusion", rules)
        self.assertIn("eventual_floor_stability", rules)
        serialized = json.dumps(result.proof_program, ensure_ascii=False)
        self.assertNotIn("problem_id", serialized)
        self.assertNotIn("expected_answer", serialized)

    def test_alpha_renaming_and_numeric_coefficients_are_elaborated(self) -> None:
        statement = r"""
        正の数列 \(\{y_k\}\) が
        \(y_{k+2}=1/2y_{k+1}+1/2y_k\) を満たし、
        各 \(k\) で \(y_k,y_{k+1},y_{k+2}\) は三角形の三辺である。
        \[
        \lim_{k\to\infty}\left\lfloor
        \frac{y_k}{y_{k+2}}+\frac{y_{k+2}}{y_k}
        \right\rfloor
        \]
        を求めよ。
        """

        result = synthesize_recurrence_triangle_floor_problem(statement)

        self.assertIsNotNone(result)
        assert result is not None
        recurrence = result.witness["input_ir"]["recurrence"]
        self.assertEqual(recurrence["sequence_symbol"], "y")
        self.assertEqual(recurrence["index_symbol"], "k")
        self.assertEqual(recurrence["leading_coefficient"], "1/2")
        self.assertEqual(recurrence["trailing_coefficient"], "1/2")
        self.assertEqual(result.witness["companion_matrix"], [["0", "1"], ["1/2", "1/2"]])

    def test_missing_strict_triangle_hypothesis_is_not_certified(self) -> None:
        statement = r"""
        正の数列 \(x_{n+2}=p x_{n+1}+q x_n\ (p,q>0)\) に対して
        \(\lim_{n\to\infty}\lfloor x_{n+2}/x_n+x_n/x_{n+2}\rfloor\) を求めよ。
        """

        self.assertIsNone(compile_recurrence_triangle_floor_query(statement))


if __name__ == "__main__":
    unittest.main()
