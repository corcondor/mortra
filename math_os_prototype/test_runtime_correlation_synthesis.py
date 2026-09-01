from __future__ import annotations

import json
import unittest

import sympy as sp

from math_os_prototype.runtime_correlation_synthesis import (
    compile_correlation_limit_query,
    synthesize_correlation_limit_problem,
)


CANONICAL_PROBLEM = r"""
1から$n$までの自然数が書かれたカードが1枚ずつあり，2枚を同時に引いたカードの値の
相加平均，相乗平均を $X_n,\ Y_n$ とする．また，$X_n,\ Y_n$ の相関係数を
$\rho_n$ とする．
\[
\lim_{n\to\infty}\rho_n
\]
を求めよ．
"""


GROWING_SAMPLE_ANGLE_PROBLEM = r"""
1から$n$までの自然数が書かれたカードが1枚ずつあり，$k(<n)$枚を同時に引き，
その相加平均，相乗平均を$X_{n,k},Y_{n,k}$とし，
$X_{n,k}$と$Y_{n,k}$の相関係数を$\cos\theta_{n,k}$とする.
\[
\lim_{k\to\infty}\lim_{n\to\infty}\theta_{n,k}
\]
を求めよ.
"""


class RuntimeCorrelationSynthesisTests(unittest.TestCase):
    def test_two_card_mean_correlation_is_composed_at_runtime(self) -> None:
        result = synthesize_correlation_limit_problem(CANONICAL_PROBLEM)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.answer_tex, r"\(\frac{8 \sqrt{102}}{85}\)")
        self.assertEqual(
            result.witness["generated_moment_obligations"],
            ["E_X", "E_Y", "E_X2", "E_Y2", "E_XY"],
        )
        self.assertEqual(result.witness["moments"], result.witness["independent_moments"])
        self.assertEqual(result.witness["covariance"], "2/45")
        self.assertEqual(result.witness["variance_left"], "1/24")
        self.assertEqual(result.witness["variance_right"], "17/324")
        rules = [step["rule"] for step in result.proof_program]
        self.assertIn("correlation_dependency_expansion", rules)
        self.assertIn("independent_double_integral_replay", rules)
        serialized = json.dumps(result.proof_program, ensure_ascii=False)
        self.assertNotIn("problem_id", serialized)
        self.assertNotIn("expected_answer", serialized)

    def test_symbol_renaming_is_read_from_the_current_statement(self) -> None:
        statement = r"""
        1から$m$までの番号を一枚ずつ書いたカードから二枚を引く。
        算術平均と幾何平均を $A_m, B_m$ とし、その相関係数を $r_m$ とする。
        \(\lim_{m\to\infty}r_m\) を求めよ。
        """

        result = synthesize_correlation_limit_problem(statement)

        self.assertIsNotNone(result)
        assert result is not None
        query = result.witness["input_ir"]
        self.assertEqual(query["sample"]["upper_symbol"], "m")
        self.assertEqual(query["limit_symbol"], "m")
        self.assertEqual(query["observables"][0]["output_symbol"], "A")
        self.assertEqual(query["observables"][1]["output_symbol"], "B")
        self.assertEqual(result.witness["correlation"], "8*sqrt(102)/85")

    def test_same_moment_compiler_handles_sum_and_product(self) -> None:
        statement = r"""
        1から$N$までの整数が書かれたカードが1枚ずつある。2枚を同時に引き、
        その値の和を $S_N$、積を $P_N$ とする。$S_N,P_N$ の相関係数を $c_N$ とする。
        \[\lim_{N\to\infty}c_N\] を求めよ。
        """

        result = synthesize_correlation_limit_problem(statement)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.witness["observable_expressions"], {"S": "u + v", "P": "u*v"})
        self.assertEqual(
            sp.simplify(sp.sympify(result.witness["correlation"]) - sp.sqrt(sp.Rational(6, 7))),
            0,
        )
        self.assertNotEqual(result.witness["moments"]["E_Y"], "4/9")

    def test_replacement_sampling_is_not_silently_certified(self) -> None:
        statement = r"""
        1から$n$までの整数から復元抽出で2回選ぶ。相加平均と相乗平均を
        $X_n,Y_n$ とし、相関係数を $r_n$ とする。\(\lim_{n\to\infty}r_n\) を求めよ。
        """

        self.assertIsNone(compile_correlation_limit_query(statement))

    def test_growing_sample_angle_is_composed_from_current_goals(self) -> None:
        result = synthesize_correlation_limit_problem(GROWING_SAMPLE_ANGLE_PROBLEM)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.answer_tex, r"\(\frac{\pi}{6}\)")
        sample_symbol = sp.Symbol("k", positive=True, integer=True)
        for name, expression in result.witness["finite_k_moments"].items():
            replayed = result.witness["independent_finite_k_moments"][name]
            self.assertEqual(
                sp.simplify(
                    sp.sympify(expression, locals={"k": sample_symbol})
                    - sp.sympify(replayed, locals={"k": sample_symbol})
                ),
                0,
            )
        self.assertEqual(result.witness["scaled_variance_arithmetic_limit"], "1/12")
        self.assertEqual(result.witness["scaled_variance_geometric_limit"], "exp(-2)")
        self.assertEqual(result.witness["scaled_covariance_limit"], "exp(-1)/4")
        self.assertEqual(result.witness["correlation"], "sqrt(3)/2")
        rules = [step["rule"] for step in result.proof_program]
        self.assertIn("growing_sample_moment_dependency_expansion", rules)
        self.assertIn("logarithmic_asymptotic_replay", rules)
        self.assertIn("principal_angle_from_correlation", rules)
        serialized = json.dumps(result.proof_program, ensure_ascii=False)
        self.assertNotIn("problem_id", serialized)
        self.assertNotIn("expected_answer", serialized)

    def test_direct_correlation_goal_does_not_invoke_angle_recovery(self) -> None:
        statement = r"""
        1から$m$までの自然数が書かれたカードが1枚ずつあり，$r(<m)$枚を同時に引く。
        その算術平均と幾何平均を$A_{m,r},B_{m,r}$とし、相関係数を$\rho_{m,r}$とする。
        \[\lim_{r\to\infty}\lim_{m\to\infty}\rho_{m,r}\]を求めよ。
        """

        result = synthesize_correlation_limit_problem(statement)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.answer_tex, r"\(\frac{\sqrt{3}}{2}\)")
        query = result.witness["input_ir"]
        self.assertEqual(query["sample"]["sample_size"], "r")
        self.assertEqual(query["target_representation"], "correlation")
        rules = [step["rule"] for step in result.proof_program]
        self.assertNotIn("principal_angle_from_correlation", rules)
        self.assertEqual(result.witness["planner"]["goal_sorts"], ["CertifiedCorrelation"])


if __name__ == "__main__":
    unittest.main()
