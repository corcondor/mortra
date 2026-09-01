from __future__ import annotations

import json
import unittest

from math_os_prototype.finite_orbit_synthesis import (
    compile_finite_orbit_query,
    synthesize_finite_orbit_problem,
)


PROBLEM_79 = r"""
数列 \(\{a_n\}\) を
\[
a_1=a_2=\frac{\pi}{4},\qquad a_{n+2}=a_{n+1}+a_n
\]
によって定める。
\begin{enumerate}
\item 次の極限を求めよ。
\[
\lim_{N\to\infty}\frac1N\sum_{k=1}^{N}\sin a_k
\]
\item 多項式 \(P_m(x)\) を
\[
P_0(x)=1,\quad P_1(x)=x,\quad
P_{m+2}(x)=2xP_{m+1}(x)-P_m(x)
\]
によって定める。\(P_m(\cos x)=\cos mx\) を示せ。
\item 次の極限を \(m\) に応じて求めよ。
\[
\lim_{N\to\infty}\frac1N\sum_{k=1}^{N}P_m(\sin a_k)
\]
\end{enumerate}
"""


class FiniteOrbitSynthesisTests(unittest.TestCase):
    def test_problem_79_is_composed_from_runtime_operations(self) -> None:
        result = synthesize_finite_orbit_problem(PROBLEM_79)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertIn(r"\frac{1}{6}", result.answer_tex)
        self.assertIn(r"m\equiv 0\pmod{8}", result.answer_tex)
        self.assertIn(r"- \frac{1}{3}", result.answer_tex)
        self.assertEqual(result.witness["modulus"], 8)
        self.assertEqual(result.witness["state_period"], 12)
        self.assertEqual(
            result.witness["cycle_values"],
            [1, 1, 2, 3, 5, 0, 5, 5, 2, 7, 1, 0],
        )
        self.assertEqual(
            result.witness["parameter_values"],
            result.witness["independent_parameter_values"],
        )
        rules = [step["rule"] for step in result.proof_program]
        self.assertIn("finite_orbit_enumeration", rules)
        self.assertIn("modular_matrix_replay", rules)
        self.assertIn("finite_character_aggregation", rules)
        serialized = json.dumps(result.proof_program, ensure_ascii=False)
        self.assertNotIn("problem_id", serialized)
        self.assertNotIn("expected_answer", serialized)
        self.assertEqual(
            result.witness["runtime_plan"]["goal_sorts"],
            [
                "CertifiedPeriodicAverage",
                "CertifiedPolynomialIdentity",
                "CertifiedPolynomialOrbitProfile",
            ],
        )
        self.assertEqual(result.witness["runtime_plan"]["open_goal_sorts"], [])

    def test_alpha_renaming_and_changed_recurrence_are_recomputed(self) -> None:
        statement = r"""
        \(b_2=\frac{\pi}{6},\ b_3=\frac{\pi}{3}\) とし、
        \(b_{j+2}=2b_{j+1}-b_j\) で数列を定める。
        \[
        \lim_{N\to\infty}\frac1N\sum_{r=2}^{N}\cos b_r
        \]
        を求めよ。
        """

        result = synthesize_finite_orbit_problem(statement)

        self.assertIsNotNone(result)
        assert result is not None
        recurrence = result.witness["input_ir"]["recurrence"]
        self.assertEqual(recurrence["sequence_symbol"], "b")
        self.assertEqual(recurrence["index_symbol"], "j")
        self.assertEqual(recurrence["start_index"], 2)
        self.assertEqual(recurrence["coefficients"], (2, -1))
        self.assertEqual(result.witness["modulus"], 12)
        self.assertEqual(result.witness["state_period"], 12)
        self.assertEqual(result.answer_tex, r"\(0\)")
        rules = [step["rule"] for step in result.proof_program]
        self.assertNotIn("polynomial_recurrence_elaboration", rules)
        self.assertNotIn("finite_character_aggregation", rules)
        self.assertEqual(
            result.witness["runtime_plan"]["goal_sorts"],
            ["CertifiedPeriodicAverage"],
        )

    def test_renamed_polynomial_is_used_without_a_fixed_output_symbol(self) -> None:
        statement = r"""
        \(d_1=d_2=\frac{\pi}{4}\), \(d_{r+2}=d_{r+1}+d_r\) とする。
        \(Q_0(t)=1\), \(Q_1(t)=t\),
        \(Q_{j+2}(t)=2tQ_{j+1}(t)-Q_j(t)\) と定める。
        \[
        \lim_{N\to\infty}\frac1N\sum_{s=1}^{N}Q_j(\sin d_s)
        \]
        を求めよ。
        """

        result = synthesize_finite_orbit_problem(statement)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertIn(r"j\equiv 0\pmod{8}", result.answer_tex)
        self.assertNotIn("P_", result.answer_tex)
        self.assertNotIn("Q_{j}(t)=", result.answer_tex)
        self.assertIn(r"Q_{j}(\cos t)=\cos(jt)", " ".join(result.derivation_tex))

    def test_unsupported_non_rational_angle_is_not_falsely_certified(self) -> None:
        statement = r"""
        \(a_1=a_2=\sqrt2\), \(a_{n+2}=a_{n+1}+a_n\) とする。
        \(\lim_{N\to\infty}\frac1N\sum_{k=1}^{N}\sin a_k\) を求めよ。
        """

        self.assertIsNone(compile_finite_orbit_query(statement))
        self.assertIsNone(synthesize_finite_orbit_problem(statement))


if __name__ == "__main__":
    unittest.main()
