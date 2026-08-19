from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from api.solve import solve_problem


class PublicSolveTests(unittest.TestCase):
    def test_quadratic_equation_is_solved_and_verified(self) -> None:
        status, payload = solve_problem(r"$x^2-5x+6=0$ を解け。")

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assertEqual(card["answer_tex"], r"\(\left\{2,\;3\right\}\)")
        self.assertTrue(card["verification"]["exact_backend"])

    def test_three_real_cubic_roots_use_compact_trigonometric_form(self) -> None:
        status, payload = solve_problem(r"$x^3-2026x^2-2029x-1=0$ を解け。")

        self.assertEqual(status, 200)
        answer = payload["cards"][0]["answer_tex"]
        self.assertIn(r"\cos", answer)
        self.assertNotIn(r"\sqrt{3} i", answer)

    def test_definite_integral_uses_exact_backend(self) -> None:
        status, payload = solve_problem(r"$\int_0^1 x^2\,dx$ を求めよ。")

        self.assertEqual(status, 200)
        self.assertEqual(payload["cards"][0]["answer_tex"], r"\(\frac{1}{3}\)")

    def test_limit_uses_exact_backend(self) -> None:
        status, payload = solve_problem(r"$\lim_{x\to0}\frac{\sin x}{x}$ を求めよ。")

        self.assertEqual(status, 200)
        self.assertEqual(payload["cards"][0]["answer_tex"], r"\(1\)")

    def test_derivative_uses_defined_expression(self) -> None:
        status, payload = solve_problem(r"$f(x)=x^3-2x$ の導関数を求めよ。")

        self.assertEqual(status, 200)
        self.assertEqual(payload["cards"][0]["answer_tex"], r"\(3 x^{2} - 2\)")

    def test_unverified_problem_is_not_given_a_fabricated_answer(self) -> None:
        status, payload = solve_problem("任意の未定義対象について新しい定理を証明せよ。")

        self.assertEqual(status, 422)
        self.assertEqual(payload["generated"], 0)
        self.assertNotIn("cards", payload)

    def test_verified_geometry_falls_back_to_typed_mathos_pipeline(self) -> None:
        problem = (
            r"平面上に一辺$\sqrt3$の正方形を固定する."
            r"一辺$\sqrt2+\sqrt6$の正三角形を,この正方形を含むように自由に動かすとき,"
            r"正三角形の通過領域の面積を求めよ."
        )
        status, payload = solve_problem(problem)

        self.assertEqual(status, 200)
        self.assertIn(r"2 \pi", payload["cards"][0]["answer_tex"])

    def test_partial_subexpression_does_not_verify_the_whole_problem(self) -> None:
        problem = (
            r"$\alpha=\cos\frac{2\pi}{11}$を根に持つ最小多項式を$f(x)$とする。"
            r"$S=\frac{1}{1-x}$で変換した不動点反復の収束次数と誤差定数を求めよ。"
        )
        status, payload = solve_problem(problem)

        self.assertEqual(status, 422)
        self.assertEqual(payload["generated"], 0)

    def test_hilbert_witness_returns_constructed_functions_and_derivation(self) -> None:
        problem = (
            r"\[\frac{\int_{0}^{1}f(x)g(x)dx}{\sqrt{\int_{0}^{1}f(x)^2dx}"
            r"\sqrt{\int_{0}^{1}g(x)^2dx}}=\cos\frac{\pi}{6}\]を満たす関数を一組求めよ."
        )
        status, payload = solve_problem(problem)

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assertIn("f(x)=1", card["answer_tex"])
        self.assertIn("正規直交", card["solution_tex"])

    def test_prime_triangle_theorem_returns_all_case_proof(self) -> None:
        status, payload = solve_problem(
            "三辺が全て素数である三角形の外接円半径は無理数であることを示せ."
        )

        self.assertEqual(status, 200)
        self.assertIn(r"R\notin\mathbb{Q}", payload["cards"][0]["answer_tex"])
        self.assertIn("三辺とも", payload["cards"][0]["solution_tex"])


if __name__ == "__main__":
    unittest.main()
