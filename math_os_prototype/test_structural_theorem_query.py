from __future__ import annotations

import math
import unittest

import sympy as sp

try:
    from math_os_prototype.reasoning_pipeline import run_reasoning_pipeline
    from math_os_prototype.structural_theorem_query import (
        _integer_angle_triangle,
        compile_structural_theorem_query,
        execute_structural_theorem_query,
    )
except ImportError:
    from reasoning_pipeline import run_reasoning_pipeline
    from structural_theorem_query import _integer_angle_triangle, compile_structural_theorem_query, execute_structural_theorem_query


def run(operator: str, objects: dict, output_sort: str = "Product") -> dict:
    return execute_structural_theorem_query(
        {
            "operator": operator,
            "objects": objects,
            "output_sort": output_sort,
            "lowering_certificate": {
                "kind": "typed_structural_theorem",
                "operator": operator,
                "alpha_renamable": True,
                "memorized_answer": False,
            },
        }
    )


class StructuralTheoremQueryTests(unittest.TestCase):
    def test_circle_overlap_kernel_changes_with_offset(self) -> None:
        result = run("circle_overlap_difference_limit", {"offset_numerator": 3, "offset_denominator": 2})
        self.assertEqual(sp.sympify(result["answer_exact"]), -9 * sp.sqrt(3) / 8)

    def test_prime_power_kernel_changes_with_base(self) -> None:
        result = run("prime_power_sum_composite", {"base": 4})
        self.assertEqual(result["certificate"]["witness"]["successor_prime"], 5)
        self.assertGreater(result["certificate"]["witness"]["exceptional_divisor"], 1)

    def test_dodecahedron_kernel_scales_quadratically(self) -> None:
        unit = sp.sympify(run("regular_dodecahedron_max_triangle", {"edge": "1"})["answer_exact"])
        doubled = sp.sympify(run("regular_dodecahedron_max_triangle", {"edge": "2"})["answer_exact"])
        self.assertEqual(sp.simplify(doubled - 4 * unit), 0)

    def test_elementary_symmetric_prime_classification_on_finite_probe(self) -> None:
        primes = list(sp.primerange(2, 20))

        def predicted(p: int, q: int, r: int) -> bool:
            return (
                (p == 2 and q in {2, 3})
                or (p, q, r) in {(2, 5, 5), (2, 5, 7), (3, 3, 3), (3, 3, 5), (3, 3, 7)}
            )

        for p in primes:
            for q in primes:
                for r in primes:
                    if not p <= q <= r:
                        continue
                    sides = (p + q + r, p * q + q * r + r * p, p * q * r)
                    actual = 2 * max(sides) < sum(sides)
                    self.assertEqual(actual, predicted(p, q, r), (p, q, r))

    def test_ordered_prime_power_triangle_finite_probe(self) -> None:
        primes = list(sp.primerange(2, 30))
        for i, p in enumerate(primes):
            for j, q in enumerate(primes[i + 1 :], i + 1):
                for r in primes[j + 1 :]:
                    sides = (p**q, q**r, r**p)
                    self.assertGreaterEqual(2 * max(sides), sum(sides))

    def test_rational_sine_prime_ratio_finite_probe(self) -> None:
        hits = []
        primes = list(sp.primerange(2, 200))
        for p in primes:
            for q in primes:
                if p <= q:
                    continue
                square = p * p + 6 * p * q + q * q
                if math.isqrt(square) ** 2 == square:
                    hits.append((p, q))
        self.assertEqual(hits, [(3, 2)])

    def test_triangular_primorial_finite_probe(self) -> None:
        primorial = 1
        hits = []
        for n in range(1, 1001):
            if sp.isprime(n):
                primorial *= n
            if n * (n + 1) // 2 == primorial:
                hits.append(n)
        self.assertEqual(hits, [1, 3])

    def test_results_carry_replay_certificate(self) -> None:
        result = run("ordered_prime_power_triangle", {})
        self.assertTrue(result["verified"])
        self.assertEqual(result["certificate"]["kind"], "structural_theorem_replay")

    def test_trigonometric_area_uses_exact_tail_certificates(self) -> None:
        cosine = run("trigonometric_side_area_extremum", {"function": "cos", "direction": "minimum"})
        sine = run("trigonometric_side_area_extremum", {"function": "sin", "direction": "maximum"})
        self.assertEqual(cosine["certificate"]["witness"]["sturm_roots_on_5_6_to_1"], 0)
        self.assertEqual(sine["certificate"]["witness"]["extremizing_n"], 5)

    def test_sine_integral_bound_has_positive_rational_margin(self) -> None:
        result = run("sine_integral_rational_bounds", {})
        margin = sp.Rational(result["certificate"]["witness"]["upper_margin"])
        self.assertGreater(margin, 0)

    def test_nested_sine_cosine_bound_has_exact_positive_margin(self) -> None:
        result = run("nested_sine_cosine_integral_bound", {}, "Proposition")
        margin = sp.Rational(result["certificate"]["witness"]["strict_margin_numerator_lower_bound"])
        self.assertGreater(margin, 0)

    def test_sine_cosine_iteration_uses_rational_interval_certificate(self) -> None:
        result = run("sine_cosine_iteration_integral_bound", {"include_scaffold": True}, "ProofBundle")
        margins = result["certificate"]["witness"]["exact_interval_margins"]
        self.assertEqual(set(margins), {"endpoint_one", "endpoint_sqrt2", "derivative_one", "derivative_sqrt2"})
        self.assertTrue(all(sp.Rational(value) > 0 for value in margins.values()))

    def test_positive_recurrence_triangle_limit_uses_open_root_interval(self) -> None:
        result = run("positive_recurrence_triangle_limit", {}, "Integer")
        self.assertEqual(result["answer_exact"], "2")
        self.assertEqual(result["certificate"]["witness"]["target_interval"], "[2,3)")

    def test_angle_multiple_construction_generalizes_to_unseen_n(self) -> None:
        for n in range(1, 13):
            sides = _integer_angle_triangle(n)
            self.assertTrue(all(isinstance(side, int) and side > 0 for side in sides), (n, sides))
            self.assertLess(2 * max(sides), sum(sides), (n, sides))

    def test_log_exponential_region_replays_symbolic_area(self) -> None:
        result = run("log_exponential_support_region", {"log_offset": 2}, "RegionMeasure")
        area = sp.sympify(result["certificate"]["witness"]["area"])
        self.assertEqual(sp.simplify(area - (sp.E**2 - 4 * sp.E + 5) / 4), 0)

    def test_triangle_angle_sum_has_exact_equality_witness(self) -> None:
        result = run("triangle_angle_sine_sum_maximum", {}, "Real")
        self.assertEqual(result["answer_exact"], "3")

    def test_discrete_exponential_minimum_uses_convexity_not_prefix_search(self) -> None:
        result = run("discrete_trigonometric_exponential_asymptotic", {"lower_index": 4}, "Product")
        witness = result["certificate"]["witness"]
        self.assertEqual(witness["minimizing_n"], 12)
        self.assertNotIn("prefix_checked_through", witness)
        self.assertLess(sp.Rational(witness["derivative_upper_at_11_over_50"]), 0)
        self.assertGreater(sp.Rational(witness["derivative_lower_at_28_over_125"]), 0)
        self.assertGreater(sp.Rational(witness["log_a13_minus_log_a12_lower"]), 0)
        self.assertIn("E*pi/2", result["answer_exact"])

    def test_power_mean_recurrence_generalizes_across_initial_values(self) -> None:
        for first, second in ((1, 2), (3, 5)):
            result = run(
                "power_mean_linearized_recurrence",
                {"first": first, "second": second, "weight_denominator": 2},
                "ProofBundle",
            )
            witness = result["certificate"]["witness"]
            self.assertEqual(witness["recurrence_residual"], "0")
            expected = sp.Integer(first) ** sp.Rational(1, 3) * sp.Integer(second) ** sp.Rational(2, 3)
            self.assertEqual(sp.simplify(sp.sympify(witness["joint_parameter_limit"]) - expected), 0)

    def test_power_mean_recurrence_compiler_reads_initial_values(self) -> None:
        statement = (
            r"実数$p\neq0$に対し$x_1=3,\,x_2=5,\,"
            r"x_{n+2}=\left(\frac{x_{n+1}^p+x_n^p}{2}\right)^{\frac1p}とする。"
            r"\lim_{p\to0}\lim_{n\to\infty}x_nを求めよ。"
        )
        compiled = compile_structural_theorem_query(statement)
        self.assertIsNotNone(compiled)
        self.assertEqual(compiled.operator, "power_mean_linearized_recurrence")
        self.assertEqual(compiled.objects["first"], 3)
        self.assertEqual(compiled.objects["second"], 5)

    def test_new_structural_compilers_are_not_problem_id_routes(self) -> None:
        statements = {
            "nested_sine_cosine_integral_bound": r"$\int_0^{\frac{\pi}2}\{\cos(\cos x+\sin x)+\sin(\cos x+\sin x)\}\,dx<2$ を示せ.",
            "positive_recurrence_triangle_limit": r"正の数列で $x_{n+2}=px_{n+1}+qx_n\ (p,q>0)$、各連続三項が三角形の三辺。$\lim\left\lfloor\frac{x_{n+2}}{x_n}+\frac{x_n}{x_{n+2}}\right\rfloor$ を求めよ.",
            "rational_angle_multiple_integer_triangles": r"三辺全てが整数で $\angle C=2\angle A$, $\angle C=3\angle A$ の例を求め、全自然数nで $\angle C=n\angle A$ の存在を示せ.",
            "log_exponential_support_region": r"実数a,bが任意の正の実数xに対して $\log x+2<ax+b<e^x$。存在範囲の面積を求めよ.",
            "triangle_angle_sine_sum_maximum": r"三角形の内角A,B,Cについて $\sin(A+B\cos C)+\sin(B+C\cos A)+\sin(C+A\cos B)$ の最大値を求めよ.",
        }
        for expected, statement in statements.items():
            compiled = compile_structural_theorem_query(statement)
            self.assertIsNotNone(compiled, expected)
            self.assertEqual(compiled.operator, expected)

    def test_iteration_compiler_accepts_direct_and_scaffold_forms(self) -> None:
        direct = (
            r"$f_1(x)=\cos x+\sin x, f_{n+1}(x)=\cos\{f_n(x)\}+\sin\{f_n(x)\}$. "
            r"$\int_0^{\frac{\pi}2}f_n(x)dx\le 2$ を示せ."
        )
        scaffold = (
            r"$f_1(x)=\cos x+\sin x, f_{n+1}(x)=f_1(f_n(x))$. "
            r"$f_1(f_1(t))\leq\frac4\pi+\frac{\sqrt{3}-1}{2}(t-\frac4\pi)$. "
            r"$\int_0^{\frac{\pi}{2}}f_n(x)dx\leq 2$ を示せ."
        )
        for statement, include_scaffold in ((direct, False), (scaffold, True)):
            compiled = compile_structural_theorem_query(statement)
            self.assertIsNotNone(compiled)
            self.assertEqual(compiled.operator, "sine_cosine_iteration_integral_bound")
            self.assertEqual(compiled.objects["include_scaffold"], include_scaffold)

    def test_dedicated_theorem_route_skips_redundant_generic_search(self) -> None:
        statement = (
            r"素数 $p>q$ に対し、$\sin\alpha+\sin\beta=\cos\alpha+\cos\beta="
            r"\dfrac{p-q}{p+q}$ かつ $\sin\alpha,\sin\beta\in\mathbb{Q}$ のとき値を求めよ。"
        )
        result = run_reasoning_pipeline(statement)
        self.assertEqual(result.math_search["status"], "skipped_dedicated_ir")
        self.assertEqual(result.parser["intent"], "structural_theorem_rational_sine_prime_ratio")
        self.assertIn("{4/5,-3/5}", result.explanation)


if __name__ == "__main__":
    unittest.main()
