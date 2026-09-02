from __future__ import annotations

from fractions import Fraction
import json
import math
import unittest

import sympy as sp

try:
    from math_os_prototype.reasoning_pipeline import run_reasoning_pipeline
    from math_os_prototype.structural_theorem_query import (
        _balanced_grid_regression_chart,
        _complex_argument_product_chart,
        _complex_power_polar_interval_chart,
        _coordinate_tangent_disk_projection_chart,
        _cubic_arc_dot_chord_sweep_chart,
        _cubic_tangent_equiangular_chart,
        _disk_affine_section_kernel,
        _equiangular_line_slope_chart,
        _four_face_tangent_disk_sweep_chart,
        _integer_angle_triangle,
        _machin_pi_interval_chart,
        _monotone_stieltjes_upper_sum,
        _parabola_reflection_integer_triangle_chart,
        _parametric_symmetric_area_interval_chart,
        _polar_circle_doubling_chart,
        _polar_rose_revolution_volume_chart,
        _rational_angle_reciprocal_power_chart,
        _rational_radius_power_obstruction_witness,
        _regular_polygon_extrema_obstruction_chart,
        _second_order_recurrence_chart,
        _tangent_partial_fraction_bound_chart,
        _alternating_trig_interval_chart,
        compile_structural_theorem_query,
        execute_structural_theorem_query,
    )
except ImportError:
    from reasoning_pipeline import run_reasoning_pipeline
    from structural_theorem_query import (
        _balanced_grid_regression_chart,
        _complex_argument_product_chart,
        _complex_power_polar_interval_chart,
        _coordinate_tangent_disk_projection_chart,
        _cubic_arc_dot_chord_sweep_chart,
        _cubic_tangent_equiangular_chart,
        _disk_affine_section_kernel,
        _equiangular_line_slope_chart,
        _four_face_tangent_disk_sweep_chart,
        _integer_angle_triangle,
        _machin_pi_interval_chart,
        _monotone_stieltjes_upper_sum,
        _parabola_reflection_integer_triangle_chart,
        _parametric_symmetric_area_interval_chart,
        _polar_circle_doubling_chart,
        _polar_rose_revolution_volume_chart,
        _rational_angle_reciprocal_power_chart,
        _rational_radius_power_obstruction_witness,
        _regular_polygon_extrema_obstruction_chart,
        _second_order_recurrence_chart,
        _tangent_partial_fraction_bound_chart,
        _alternating_trig_interval_chart,
        compile_structural_theorem_query,
        execute_structural_theorem_query,
    )


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
    def test_alternating_trig_interval_chart_is_shared_across_proof_shapes(self) -> None:
        chart = _alternating_trig_interval_chart([sp.Rational(1), sp.Rational(1, 4)])
        self.assertEqual(chart["chart_id"], "transcendental.sin_cos.alternating_interval.v1")
        self.assertEqual(len(chart["evaluations"]), 2)

        discrete = run(
            "discrete_trigonometric_exponential_asymptotic",
            {"lower_index": 4},
            "Product",
        )
        iteration = run(
            "sine_cosine_iteration_integral_bound",
            {"include_scaffold": True},
            "ProofBundle",
        )
        discrete_chart = discrete["certificate"]["witness"]["trigonometric_interval_chart"]
        iteration_chart = iteration["certificate"]["witness"]["trigonometric_interval_chart"]
        self.assertEqual(discrete_chart["chart_id"], chart["chart_id"])
        self.assertEqual(iteration_chart["chart_id"], chart["chart_id"])

    def test_machin_pi_chart_is_shared_by_distinct_analytic_charts(self) -> None:
        pi_chart = _machin_pi_interval_chart()
        self.assertEqual(pi_chart["chart_id"], "constant.pi.machin_arctangent_interval.v1")
        self.assertLess(Fraction(pi_chart["lower"]), Fraction(pi_chart["upper"]))

        complex_power = _complex_power_polar_interval_chart()
        parametric_area = _parametric_symmetric_area_interval_chart(partition_count=72)
        self.assertEqual(complex_power["pi_interval_chart"], pi_chart)
        self.assertEqual(parametric_area["pi_interval_chart"], pi_chart)

    def test_second_order_recurrence_chart_is_shared_across_domains(self) -> None:
        generic = _second_order_recurrence_chart("a", "b")
        self.assertEqual(generic["chart_id"], "recurrence.order2.companion.characteristic.v1")
        self.assertEqual(generic["characteristic_polynomial"], "-a*lambda - b + lambda**2")
        self.assertEqual(generic["cayley_hamilton_residual"], [["0", "0"], ["0", "0"]])

        power_mean = run(
            "power_mean_linearized_recurrence",
            {"first": 1, "second": 2, "weight_denominator": 2},
        )
        positive = run("positive_recurrence_triangle_limit", {}, "Integer")
        integer_angle = run("rational_angle_multiple_integer_triangles", {})
        fibonacci = run("fibonacci_angle_period_average", {})
        prime_neighbors = run("fibonacci_prime_neighbors", {})
        threshold = run(
            "trigonometric_power_sum_threshold",
            {"sum_numerator": 1, "sum_denominator": 2},
        )
        witnesses = [
            power_mean["certificate"]["witness"]["recurrence_chart"],
            positive["certificate"]["witness"]["recurrence_chart"],
            integer_angle["certificate"]["witness"]["recurrence_chart"],
            fibonacci["certificate"]["witness"]["recurrence_chart"],
            prime_neighbors["certificate"]["witness"]["recurrence_chart"],
            threshold["certificate"]["witness"]["newton_recurrence_chart"],
            threshold["certificate"]["witness"]["parity_recurrence_chart"],
        ]
        self.assertTrue(all(chart["chart_id"] == generic["chart_id"] for chart in witnesses))

    def test_disk_affine_section_kernel_is_shared_and_scales_exactly(self) -> None:
        kernel = _disk_affine_section_kernel(2, 3)
        self.assertEqual(kernel["kernel_id"], "disk.affine_section.support_kernel.v1")
        self.assertEqual(kernel["radius"], "2")
        self.assertEqual(kernel["ambient_dimension"], 3)
        self.assertEqual(kernel["coordinate_half_widths"][0], "r*sqrt(1-n_1^2)")
        self.assertEqual(kernel["codimension_one_slice_radius_squared"], "4 - delta**2")
        self.assertTrue(all(kernel["proof_obligations"].values()))

        projection = _coordinate_tangent_disk_projection_chart(2)
        volume = _four_face_tangent_disk_sweep_chart(2, 4)
        self.assertEqual(projection["base_kernel"], kernel)
        self.assertEqual(volume["base_kernel"], kernel)

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
        witness = result["certificate"]["witness"]
        self.assertEqual(margin, sp.Rational(1, 1325))
        self.assertEqual(
            witness["shared_chart"]["chart_id"],
            "concave_composition.complementary_angle.bound.v1",
        )
        self.assertTrue(all(witness["shared_chart"]["proof_obligations"].values()))
        self.assertIn(r"d=\pi/2-4/\pi", result["derivation_tex"][1])

    def test_sine_cosine_iteration_uses_rational_interval_certificate(self) -> None:
        result = run("sine_cosine_iteration_integral_bound", {"include_scaffold": True}, "ProofBundle")
        margins = result["certificate"]["witness"]["exact_interval_margins"]
        self.assertEqual(set(margins), {"endpoint_one", "endpoint_sqrt2", "derivative_one", "derivative_sqrt2"})
        self.assertTrue(all(sp.Rational(value) > 0 for value in margins.values()))
        witness = result["certificate"]["witness"]
        self.assertEqual(
            witness["shared_chart"]["chart_id"],
            "sine_cosine.iteration.two_step_affine_bound.v1",
        )
        self.assertTrue(all(witness["coarse_margin_checks"].values()))
        self.assertEqual(witness["fixed_point_gap_lower"], "7259089/314501600")
        json.dumps(result, ensure_ascii=False)
        self.assertIn(r"H'''(t)", result["derivation_tex"][3])
        self.assertNotIn("composed with", " ".join(result["derivation_tex"]))

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

    def test_trigonometric_power_sum_uses_parity_transition_chart(self) -> None:
        result = run(
            "trigonometric_power_sum_threshold",
            {"sum_numerator": 1, "sum_denominator": 2027},
            "FiniteSet",
        )
        self.assertEqual(
            result["answer_exact"],
            "[2, 3, 4, 5, 6, 8, 10, 12, 14, 16, 18, 20, 22]",
        )
        witness = result["certificate"]["witness"]
        self.assertEqual(witness["first_even_failure"], 24)
        self.assertEqual(witness["first_odd_failure"], 7)
        self.assertEqual(witness["newton_recurrence_replayed_through"], 24)
        self.assertEqual(
            witness["shared_chart"]["chart_id"],
            "trigonometric.power_sum.parity_threshold.v1",
        )
        self.assertTrue(all(witness["shared_chart"]["proof_obligations"].values()))
        self.assertIn(r"\sin\theta", result["derivation_tex"][0])
        self.assertNotIn("sin(theta)", " ".join(result["derivation_tex"]))

    def test_trigonometric_power_sum_chart_changes_with_the_sum(self) -> None:
        one_half = run(
            "trigonometric_power_sum_threshold",
            {"sum_numerator": 1, "sum_denominator": 2},
            "FiniteSet",
        )
        one_seventh = run(
            "trigonometric_power_sum_threshold",
            {"sum_numerator": 1, "sum_denominator": 7},
            "FiniteSet",
        )
        self.assertNotEqual(one_half["answer_exact"], one_seventh["answer_exact"])
        self.assertNotEqual(
            one_half["certificate"]["witness"]["parity_transition_matrix"],
            one_seventh["certificate"]["witness"]["parity_transition_matrix"],
        )

    def test_trigonometric_power_sum_compiler_reads_the_rational_threshold(self) -> None:
        statement = (
            r"実数 $\theta$ が $\sin\theta+\cos\theta=\frac{1}{37}$ を満たす。"
            r"$\sin^n\theta+\cos^n\theta>\frac{1}{37}$ となる正の整数 $n$ をすべて求めよ。"
        )
        compiled = compile_structural_theorem_query(statement)
        self.assertIsNotNone(compiled)
        self.assertEqual(compiled.operator, "trigonometric_power_sum_threshold")
        self.assertEqual(compiled.objects, {"sum_numerator": 1, "sum_denominator": 37})

    def test_binomial_exponential_edge_limit_has_uniform_error_certificate(self) -> None:
        result = run(
            "binomial_exponential_edge_limit",
            {"increment_numerator": 1, "increment_denominator": 1},
            "Real",
        )
        self.assertEqual(sp.simplify(sp.sympify(result["answer_exact"]) - (4 - sp.E)), 0)
        witness = result["certificate"]["witness"]
        self.assertEqual(sp.limit(sp.sympify(witness["total_error_bound"]), sp.Symbol("n"), sp.oo), 0)
        self.assertTrue(all(sp.sympify(value) >= 0 for value in witness["finite_bound_margins"].values()))

    def test_binomial_exponential_edge_limit_changes_with_increment(self) -> None:
        result = run(
            "binomial_exponential_edge_limit",
            {"increment_numerator": 2, "increment_denominator": 1},
            "Real",
        )
        self.assertEqual(sp.simplify(sp.sympify(result["answer_exact"]) - (6 - sp.E**2)), 0)

    def test_binomial_exponential_edge_limit_compiler_uses_structure(self) -> None:
        statement = (
            r"$\lim_{n\to\infty}\left\{\sum_{k=0}^{n}"
            r"\left(1+\frac{1}{\binom{n}{k}}\right)^{\binom{n}{k}}-en\right\}$を求めよ。"
        )
        compiled = compile_structural_theorem_query(statement)
        self.assertIsNotNone(compiled)
        self.assertEqual(compiled.operator, "binomial_exponential_edge_limit")

        japanese_notation = (
            r"$\lim_{n\to\infty}\left\{\sum_{k=0}^{n}"
            r"\left(1+\frac{1}{{}_n C_k}\right)^{{}_n C_k}-en\right\}$を求めよ。"
        )
        normalized = compile_structural_theorem_query(japanese_notation)
        self.assertIsNotNone(normalized)
        self.assertEqual(normalized.operator, "binomial_exponential_edge_limit")
        self.assertEqual(normalized.objects, compiled.objects)

    def test_exponential_tangent_bound_has_exact_endpoint_certificates(self) -> None:
        result = run("exponential_tangent_convex_bound", {}, "Proposition")
        self.assertEqual(result["answer_exact"], "成立")
        bounds = result["certificate"]["witness"]["endpoint_bounds"]
        self.assertLess(sp.Rational(bounds["tan(1)"]), sp.Rational(bounds["common_upper"]))
        self.assertLess(sp.Rational(bounds["1+tan(1/2)"]), sp.Rational(bounds["common_upper"]))
        self.assertLess(2 * sp.Rational(bounds["common_upper"]), sp.Rational(bounds["pi_lower"]))

    def test_exponential_tangent_bound_compiler_recognizes_equivalent_spacing(self) -> None:
        statement = (
            r"$x>1$ において、$\tan\left(e\left(1-\frac{1}{x}\right)^x\right)"
            r"+\frac{1}{x}<\frac{\pi}{2}$ を示せ。"
        )
        compiled = compile_structural_theorem_query(statement)
        self.assertIsNotNone(compiled)
        self.assertEqual(compiled.operator, "exponential_tangent_convex_bound")

    def test_mobius_polynomial_fixed_point_uses_quotient_ring_reduction(self) -> None:
        result = run(
            "mobius_polynomial_fixed_point",
            {
                "coefficients": ["32", "16", "-32", "-12", "6", "1"],
                "cyclotomic_order": 11,
            },
            "Product",
        )
        witness = result["certificate"]["witness"]
        self.assertEqual(witness["constant_term"], "10")
        self.assertEqual(witness["root_remainder"], "0")
        self.assertEqual(witness["fixed_point_identity"], "0")
        self.assertEqual(witness["derivative_sign"], "positive")
        c = sp.Symbol("c")
        expected = 2 * (1 - c) * (8 * c**3 + 4 * c**2 - 4 * c - 1)
        self.assertEqual(sp.expand(sp.sympify(witness["derivative_remainder"]) - expected), 0)

    def test_mobius_polynomial_fixed_point_generalizes_to_another_order(self) -> None:
        result = run(
            "mobius_polynomial_fixed_point",
            {"coefficients": ["4", "2", "-1"], "cyclotomic_order": 5},
            "Product",
        )
        witness = result["certificate"]["witness"]
        self.assertEqual(witness["constant_term"], "2")
        self.assertEqual(witness["root_remainder"], "0")
        self.assertNotEqual(witness["contraction_factor"], "0")

    def test_mobius_polynomial_fixed_point_compiler_extracts_the_polynomial(self) -> None:
        statement = (
            r"$\alpha=\cos\frac{2\pi}{11}$ の最小多項式は "
            r"$f(x)=32x^5+16x^4-32x^3-12x^2+6x+1$ である。"
            r"$S=\frac{1}{1-x}$ とし、$S^{*}=g(S^{*})$、"
            r"$g(S)=C_{0}+\frac{C_{1}}S+\frac{C_{2}}{S^2}$ とする。"
            r"$g'(S^{*})$ から収束率を求めよ。"
        )
        compiled = compile_structural_theorem_query(statement)
        self.assertIsNotNone(compiled)
        self.assertEqual(compiled.operator, "mobius_polynomial_fixed_point")
        self.assertEqual(compiled.objects["cyclotomic_order"], 11)
        self.assertEqual(compiled.objects["coefficients"], ["32", "16", "-32", "-12", "6", "1"])

    def test_permuted_trigonometric_cubic_closes_all_six_permutations(self) -> None:
        result = run("permuted_trigonometric_cubic", {}, "ProofBundle")
        witness = result["certificate"]["witness"]
        self.assertEqual(len(witness["permutation_obstructions"]), 6)
        self.assertEqual(len(witness["competitor_cases"]), 5)
        self.assertEqual(witness["depressed_cubic_condition"], "p=b-a^2/3=0")
        self.assertGreater(sp.sympify(witness["separation_margin"]), 0)
        self.assertGreater(sp.sympify(witness["target_margin_factorization"]), 0)

    def test_permuted_trigonometric_cubic_compiler_uses_the_structure(self) -> None:
        statement = (
            r"$0<\theta<\frac{\pi}{2}$ とし、$(a,b,c)$ は "
            r"$(\sin\theta,\cos\theta,\tan\theta)$ の置換とする。"
            r"$x^3+ax^2+bx+c=0$ が虚数解を持つことを示し、"
            r"三解が正三角形をなすときの面積を求めよ。"
        )
        compiled = compile_structural_theorem_query(statement)
        self.assertIsNotNone(compiled)
        self.assertEqual(compiled.operator, "permuted_trigonometric_cubic")

    def test_rotated_parabola_volume_detects_the_missing_two_sided_limit(self) -> None:
        result = run("rotated_parabola_volume_limit", {"degree": 2}, "ExtendedReal")
        witness = result["certificate"]["witness"]
        self.assertEqual(witness["section_integral"], "128/15")
        self.assertEqual(witness["right_limit"], "128*pi/15")
        self.assertEqual(witness["left_limit"], "-128*pi/15")
        self.assertIn("does not exist", result["answer_exact"])

    def test_rotated_parabola_volume_compiler_preserves_limit_direction(self) -> None:
        statement = (
            r"原点を中心に曲線 $P:y=x^2$ を角 $\theta$ だけ回転した曲線をQとする。"
            r"PとQで囲まれた領域をx軸周りに回転した体積を$V(\theta)$とする。"
            r"$\lim_{\theta\to0}\theta^5V(\theta)$を求めよ。"
        )
        compiled = compile_structural_theorem_query(statement)
        self.assertIsNotNone(compiled)
        self.assertEqual(compiled.operator, "rotated_parabola_volume_limit")

    def test_prime_two_side_triangle_radii_chart_is_exhaustive(self) -> None:
        result = run("prime_two_side_triangle_radii_product", {}, "FiniteSet")
        witness = result["certificate"]["witness"]
        self.assertEqual(
            witness["solutions"],
            [[5, 7, 8], [5, 12, 13], [5, 16, 19], [7, 8, 13]],
        )
        self.assertEqual(witness["k_range"], [2, 8])
        self.assertIn("ell=q", witness["forced_product_prime"])
        self.assertEqual(witness["shared_metric_chart"], "triangle.metric.heron_radii.v1")
        self.assertEqual(len(witness["solution_metric_certificates"]), 4)
        self.assertTrue(
            all(
                certificate["chart_id"] == witness["shared_metric_chart"]
                for certificate in witness["solution_metric_certificates"]
            )
        )
        self.assertTrue(
            all(
                not candidate["q_is_prime"]
                or candidate["radii_product_equals_q"]
                for candidate in witness["finite_candidates"]
            )
        )

    def test_triangle_angle_product_region_uses_permutation_quotient(self) -> None:
        result = run("triangle_angle_product_region_area", {}, "PositiveReal")
        witness = result["certificate"]["witness"]
        self.assertEqual(result["answer_exact"], "pi/16")
        self.assertEqual(
            witness["shared_chart"]["chart_id"],
            "triangle.angle_products.symmetric_quotient.v1",
        )
        self.assertEqual(witness["shared_chart"]["area"], "pi/16")
        self.assertIn("roots", witness["injectivity_certificate"])

    def test_triangle_angle_product_compiler_ignores_angle_variable_names(self) -> None:
        statement = (
            r"P,Q,Rをある三角形の角とする。点 "
            r"$(\cos P\cos Q\cos R,\sin P\sin Q\sin R)$ "
            r"の通過する領域の面積を求めよ。"
        )
        compiled = compile_structural_theorem_query(statement)
        self.assertIsNotNone(compiled)
        self.assertEqual(compiled.operator, "triangle_angle_product_region_area")

    def test_prime_two_side_triangle_radii_compiler_connects_geometry_to_divisibility(self) -> None:
        statement = (
            "二辺の長さが素数で、外接円半径と内接円半径の積も素数となる"
            "整数三角形をすべて求めよ。"
        )
        compiled = compile_structural_theorem_query(statement)
        self.assertIsNotNone(compiled)
        self.assertEqual(compiled.operator, "prime_two_side_triangle_radii_product")

    def test_integer_triangle_mean_radii_prime_chain_is_unique(self) -> None:
        result = run("integer_triangle_mean_radii_prime_chain", {}, "ProofBundle")
        witness = result["certificate"]["witness"]
        self.assertEqual(witness["sides"], [3, 5, 7])
        self.assertEqual(witness["prime_values"], ["3", "5", "7"])
        self.assertEqual(witness["positive_difference_solution"], "d=2*A/5")
        self.assertIn("P*A*Q", witness["prime_product_identity"])
        self.assertEqual(witness["shared_metric_chart"], "triangle.metric.heron_radii.v1")
        self.assertEqual(
            witness["metric_chart"]["radius_relation_chart"]["chart_id"],
            "triangle.radii.euler_sum_product.v1",
        )
        self.assertEqual(
            witness["shared_chart"]["chart_id"],
            "integer_triangle.mean_radii.prime_rigidity.v1",
        )
        self.assertTrue(all(witness["shared_chart"]["proof_obligations"].values()))
        self.assertIn("三辺の一つが1なら", "\n".join(result["derivation"]))

    def test_fibonacci_prime_neighbors_closes_norm_and_index_branches(self) -> None:
        result = run("fibonacci_prime_neighbors", {}, "Product")
        witness = result["certificate"]["witness"]
        self.assertEqual(witness["prime_pair"], [5, 3])
        self.assertEqual(witness["indices"], [3, 4])
        self.assertEqual(witness["mod_q_branches"], ["p=q+1", "p=2*q-1"])
        self.assertEqual(
            witness["shared_chart"]["chart_id"],
            "trigonometric_norm.fibonacci_prime_neighbor.v1",
        )
        self.assertTrue(all(witness["shared_chart"]["proof_obligations"].values()))
        self.assertIn("p^2-p*q-q^2=1", witness["tangent_norm_equation"])
        self.assertIn("F_m prime", witness["prime_index_criterion"])
        self.assertIn("F_{n+1}^2-F_{n+1}F_n-F_n^2=(-1)^n", result["answer_tex"])

    def test_triangle_radii_chart_is_reused_across_metric_region_and_bounds(self) -> None:
        shared = "triangle.radii.euler_sum_product.v1"

        prime_metric = run("prime_two_side_triangle_radii_product", {}, "FiniteSet")
        prime_witness = prime_metric["certificate"]["witness"]
        self.assertTrue(
            all(
                item["radius_relation_chart"]["chart_id"] == shared
                for item in prime_witness["solution_metric_certificates"]
            )
        )

        region = run("triangle_radii_symmetric_region", {}, "Region")
        self.assertEqual(
            region["certificate"]["witness"]["radius_relation_chart"]["chart_id"],
            shared,
        )

        bound = run(
            "triangle_radii_exponential_bound",
            {"chart": "cosine_sum"},
            "PositiveReal",
        )
        radius_chart = bound["certificate"]["witness"]["radius_relation_chart"]
        self.assertEqual(radius_chart["chart_id"], shared)
        self.assertEqual(radius_chart["normalized_domain"], "0<u<=1/2")
        self.assertEqual(radius_chart["upper_boundary"], "y<=2*x^2/9")

    def test_integer_triangle_mean_radii_prime_chain_compiler_reads_both_parts(self) -> None:
        statement = (
            r"整数三角形の三辺の相加平均を$A$、相乗平均を$G$、"
            r"外接円半径を$R$、内接円半径を$r$とする。"
            r"$2\sqrt{3}r\le G\le A\le\sqrt{3}R$を示せ。"
            r"さらに$2\sqrt{3}r,A,\sqrt{3}R$が相異なる素数となる三辺を求めよ。"
        )
        compiled = compile_structural_theorem_query(statement)
        self.assertIsNotNone(compiled)
        self.assertEqual(compiled.operator, "integer_triangle_mean_radii_prime_chain")

    def test_triangle_sine_exponential_ratio_has_global_and_sharp_certificates(self) -> None:
        result = run("triangle_sine_exponential_ratio_supremum", {}, "PositiveReal")
        witness = result["certificate"]["witness"]
        self.assertEqual(result["answer_exact"], "E/6")
        self.assertEqual(witness["local_second_order_coefficient"], "E/12")
        self.assertEqual(witness["sharpness_quadratic_ratio_limit"], "2")
        self.assertEqual(
            witness["triangle_chart"]["chart_id"],
            "triangle.side_cone.quadratic.v1",
        )
        self.assertEqual(witness["uniform_positivity_margin"], 1)

    def test_triangle_sine_exponential_ratio_compiler_reads_the_quotient(self) -> None:
        statement = (
            r"任意の三角形ABCに対して"
            r"\frac{(1+\sin A)^{\frac{1}{\sin A}+\frac12}"
            r"+(1+\sin B)^{\frac{1}{\sin B}+\frac12}"
            r"+(1+\sin C)^{\frac{1}{\sin C}+\frac12}-3e}"
            r"{\sin A\sin B+\sin B\sin C+\sin C\sin A}<M"
            r"が成り立つ実数Mの最小値を求めよ。"
        )
        compiled = compile_structural_theorem_query(statement)
        self.assertIsNotNone(compiled)
        self.assertEqual(compiled.operator, "triangle_sine_exponential_ratio_supremum")

    def test_cayley_exponential_integral_comparisons_share_one_chart(self) -> None:
        result = run("cayley_exponential_integral_comparisons", {}, "ProofBundle")
        witness = result["certificate"]["witness"]
        self.assertEqual(witness["shared_chart"]["chart_id"], "cayley.exp_log.order.v1")
        self.assertEqual(witness["log_two_rational_margin"], "13/6000")
        self.assertEqual(witness["positive_branch_margin"], "57973/3120000")
        self.assertEqual(witness["tail_minorant_integral"], "exp(-2)/8")
        self.assertIn(r"\operatorname{Ei}(2)", result["derivation_tex"][3])
        self.assertNotIn("integral_", " ".join(result["derivation_tex"]))

    def test_cayley_exponential_integral_compiler_reads_all_three_parts(self) -> None:
        statement = (
            r"0<x<2とし、\mathrm{Ei}(x)=\lim_{s\to\infty}"
            r"\int_x^s\frac{e^{-t}}{t}\,dtと定める。"
            r"(1)e^xと\dfrac{2+x}{2-x}を比較せよ。"
            r"(2)\ln\frac{2+x}{2-x}と\frac{2+\ln x}{2-\ln x}を比較せよ。"
            r"(3)\mathrm{Ei}(2)と\dfrac{3}{8e^2}を比較せよ。"
        )
        compiled = compile_structural_theorem_query(statement)
        self.assertIsNotNone(compiled)
        self.assertEqual(compiled.operator, "cayley_exponential_integral_comparisons")

    def test_complex_argument_chart_certifies_condition_and_pi_interval(self) -> None:
        result = run("complex_argument_arctangent_certificate", {}, "ProofBundle")
        witness = result["certificate"]["witness"]
        self.assertEqual(
            witness["shared_product_chart"]["chart_id"],
            "complex.argument.symmetric_product.v1",
        )
        self.assertEqual(witness["shared_product_chart"]["gaussian_product"], "5 + 5*I")
        self.assertEqual(witness["pi_lower"], "21940173935/6983843328")
        self.assertEqual(witness["pi_upper"], "498668825/158723712")
        self.assertEqual(
            witness["half_interval"]["chart_id"],
            "arctangent.alternating_interval.v1",
        )
        self.assertGreater(Fraction(witness["lower_margin_over_3_141"]), 0)
        self.assertGreater(Fraction(witness["upper_margin_below_3_142"]), 0)

    def test_complex_power_chart_covers_all_positive_reals_exactly(self) -> None:
        chart = _complex_power_polar_interval_chart()
        self.assertEqual(chart["chart_id"], "complex.power.polar_interval.v1")
        self.assertEqual(chart["integer_maximizers"], [1, 2])
        self.assertEqual(chart["interval_count"], 440)
        self.assertLess(
            Fraction(chart["worst_log_upper"]),
            Fraction(chart["comparison_threshold"]),
        )
        self.assertEqual(chart["target_margin"], "571/6615000")

    def test_complex_power_compiler_reads_integer_and_real_parts(self) -> None:
        statement = (
            r"(1) 自然数mについて、\operatorname{Im}"
            r"\left(1+\frac{i}{m}\right)^mが最大となるmを全て求めよ。"
            r"(2) 正の実数tについて、\operatorname{Im}"
            r"\left(1+\frac{i}{t}\right)^t<\frac{e}{2^{\sqrt2}}を示せ。"
        )
        compiled = compile_structural_theorem_query(statement)
        self.assertIsNotNone(compiled)
        self.assertEqual(compiled.operator, "complex_binomial_imaginary_extremum")

    def test_parametric_area_chart_certifies_a_strict_stieltjes_upper_sum(self) -> None:
        chart = _parametric_symmetric_area_interval_chart()
        self.assertEqual(
            chart["chart_id"],
            "parametric.symmetric_area.stieltjes_interval.v1",
        )
        self.assertEqual(chart["partition_count"], 72)
        self.assertEqual(chart["peak_intervals"], 1)
        self.assertEqual(chart["upper_area"], "499638101/500000000")
        self.assertGreater(Fraction(chart["strict_margin"]), 0)

    def test_stieltjes_atom_recomposes_on_unrelated_interval_data(self) -> None:
        upper_sum = _monotone_stieltjes_upper_sum(
            [
                (Fraction(0), Fraction(0)),
                (Fraction(1, 2), Fraction(1, 2)),
                (Fraction(1), Fraction(1)),
            ],
            [Fraction(1), Fraction(1, 2)],
        )
        self.assertEqual(upper_sum, Fraction(3, 4))

    def test_parametric_area_compiler_is_alpha_renamable(self) -> None:
        statement = (
            r"実数 $u$ が $-\pi\leq u\leq\pi$ を動くとき、点 "
            r"$P\left(\cos\left(\frac{\pi\sin u}{2u}\right),"
            r"\sin(u-\sin u)\right)$ の描く曲線が囲む面積を $S$ とする。"
            r"$S<1$ を示せ。"
        )
        compiled = compile_structural_theorem_query(statement)
        self.assertIsNotNone(compiled)
        self.assertEqual(compiled.operator, "parametric_symmetric_area_bound")
        self.assertEqual(compiled.objects["parameter"], "u")

    def test_rose_revolution_chart_replays_volume_limit_and_pi_bound(self) -> None:
        chart = _polar_rose_revolution_volume_chart()
        self.assertEqual(chart["chart_id"], "polar.rose.revolution_harmonic.v1")
        self.assertEqual(
            chart["volume"],
            "8*pi*n^3*cot(pi/(2*n))/((n^2-1)*(9*n^2-1))",
        )
        self.assertEqual(chart["limit"], "16/9")
        self.assertEqual(
            chart["volume_at_six"],
            "1728*pi*(2+sqrt(3))/11305",
        )
        self.assertEqual(chart["pi_lower"], "11305*(2-sqrt(3))/972")

    def test_tangent_partial_fraction_atom_has_exact_normalization(self) -> None:
        chart = _tangent_partial_fraction_bound_chart()
        self.assertEqual(
            chart["chart_id"],
            "trigonometric.tangent.partial_fraction_bound.v1",
        )
        self.assertEqual(chart["odd_square_sum"], "pi^2/8")
        self.assertIn("x*cot(x)>", chart["dual_bound"])

    def test_rose_revolution_compiler_is_alpha_renamable(self) -> None:
        statement = (
            r"正の整数 $m\ge2$ に対し、曲線 $r=\sin m\theta$ によって囲まれる領域を "
            r"$x$軸のまわりに1回転して得られる立体の体積を $V_m$ とする。"
            r"(1) $V_m$ と $\alpha=\lim_{m\to\infty}V_m$ を求めよ。"
            r"(2) $V_m>\alpha$ および $\dfrac{11305}{972}(2-\sqrt3)<\pi$ を示せ。"
        )
        compiled = compile_structural_theorem_query(statement)
        self.assertIsNotNone(compiled)
        self.assertEqual(compiled.operator, "polar_rose_revolution_volume")
        self.assertEqual(compiled.objects["index"], "m")

    def test_equiangular_slope_atom_uses_symmetric_relations(self) -> None:
        chart = _equiangular_line_slope_chart()
        self.assertEqual(
            chart["chart_id"],
            "projective.lines.equiangular_slope_normal_form.v1",
        )
        self.assertEqual(chart["slope_polynomial"], "m^3-3*h*m^2-3*m+h")
        self.assertEqual(
            chart["symmetric_characterization"],
            [
                "sigma_2(m_1,m_2,m_3)=-3",
                "sigma_1(m_1,m_2,m_3)+3*sigma_3(m_1,m_2,m_3)=0",
            ],
        )

    def test_cubic_tangent_chart_replays_range_and_area_minimum(self) -> None:
        chart = _cubic_tangent_equiangular_chart()
        self.assertEqual(chart["coefficient_range"], "c>=sqrt(3)")
        self.assertEqual(
            chart["contact_discriminant"],
            "(r^2+1)^3*(r^2+9)/(96*r)>0",
        )
        self.assertEqual(
            chart["minimum_area_squared"],
            "(5543*sqrt(241)-5647)/300000",
        )

    def test_cubic_tangent_compiler_is_alpha_renamable(self) -> None:
        statement = (
            r"実数 $d$ に対し、曲線 $D_d:y=x^3-dx$ を考える。点 $Q$ から "
            r"$D_d$ に相異なる3本の接線 $k_1,k_2,k_3$ が引け、"
            r"$k_1,k_2$ のなす角と $k_2,k_3$ のなす角がともに "
            r"$\frac{\pi}{3}$ である。接点を $A,B,C$ とする。"
            r"(1) $d=3$ のとき $Q$ を求めよ。(2) $d$ の範囲を求めよ。"
            r"(3) 三角形 $ABC$ の面積の最小値を求めよ。"
        )
        compiled = compile_structural_theorem_query(statement)
        self.assertIsNotNone(compiled)
        self.assertEqual(compiled.operator, "cubic_tangent_equiangular_extremum")
        self.assertEqual(compiled.objects["coefficient"], "d")

    def test_regular_polygon_extrema_chart_composes_three_atoms(self) -> None:
        chart = _regular_polygon_extrema_obstruction_chart()
        self.assertEqual(
            chart["atomic_chart_ids"],
            [
                "regular_polygon.projection.chebyshev_fiber.v1",
                "polynomial.critical_values.chebyshev_antiderivative.v1",
                "rational_power.padically_obstructed.v1",
            ],
        )
        self.assertEqual(
            chart["forced_radius_power"],
            "R^n=2^(n-1)*(n-1)/n",
        )
        witness = _rational_radius_power_obstruction_witness(8)
        self.assertEqual(witness["prime"], 7)
        self.assertEqual(witness["valuation"], 1)
        self.assertEqual(witness["required_multiple"], 4)

    def test_regular_polygon_extrema_compiler_is_alpha_renamable(self) -> None:
        statement = (
            r"$m\ge3$ とする。モニックな有理数係数 $(m+1)$次多項式 "
            r"$y=g(x)$ の極値点は正 $m$ 角形の頂点をなさないことを示せ。"
        )
        compiled = compile_structural_theorem_query(statement)
        self.assertIsNotNone(compiled)
        self.assertEqual(
            compiled.operator,
            "rational_polynomial_regular_polygon_extrema_impossible",
        )
        self.assertEqual(compiled.objects["index"], "m")

    def test_rational_angle_reciprocal_power_chart_is_finite_and_exact(self) -> None:
        chart = _rational_angle_reciprocal_power_chart()
        self.assertEqual(
            chart["allowed_orders"],
            [1, 2, 3, 4, 5, 6, 8, 10, 12],
        )
        self.assertEqual(chart["sqrt2_even_trace_mod4"], [2, 2, 2, 2])
        self.assertEqual(chart["sqrt3_trace_mod8_period"], [2, 4, 6, 4])
        self.assertEqual(
            [
                (
                    record["power"],
                    record["prime_exponent"],
                    record["angle_numerator"],
                    record["angle_denominator"],
                )
                for record in chart["solution_records"]
            ],
            [(1, 2, 1, 12), (1, 2, 5, 12)],
        )
        self.assertTrue(all(chart["proof_obligations"].values()))

    def test_rational_angle_reciprocal_power_compiler_is_alpha_renamable(self) -> None:
        statement = (
            r"$\dfrac{\phi}{\pi}$ が有理数であるとする。"
            r"$\tan^m\phi+\dfrac{1}{\tan^m\phi}=2^r$ を満たす"
            r"自然数 $m$、素数 $r$、実数 $\phi$ をすべて求めよ。"
        )
        compiled = compile_structural_theorem_query(statement)
        self.assertIsNotNone(compiled)
        self.assertEqual(
            compiled.operator,
            "rational_angle_reciprocal_power_of_two",
        )
        self.assertEqual(compiled.objects["power_index"], "m")
        self.assertEqual(compiled.objects["prime_index"], "r")
        self.assertEqual(compiled.objects["angle_index"], "phi")

        mutation = statement.replace("=2^r", "=3^r")
        self.assertIsNone(compile_structural_theorem_query(mutation))

    def test_rational_angle_reciprocal_power_executor_replays_solution(self) -> None:
        result = run(
            "rational_angle_reciprocal_power_of_two",
            {"power_index": "n", "prime_index": "p", "base": 2},
            "FiniteSet",
        )
        self.assertTrue(result["verified"])
        self.assertIn("n=1, p=2", result["answer_exact"])
        witness = result["certificate"]["witness"]
        self.assertEqual(witness["proof_kernel_count"], 4)
        self.assertEqual(
            witness["allowed_orders"],
            [1, 2, 3, 4, 5, 6, 8, 10, 12],
        )

        renamed = run(
            "rational_angle_reciprocal_power_of_two",
            {
                "power_index": "m",
                "prime_index": "r",
                "angle_index": "phi",
                "base": 2,
            },
            "FiniteSet",
        )
        self.assertIn("m=1, r=2", renamed["answer_exact"])
        self.assertIn(r"\phi\equiv\frac{\pi}{12}", renamed["answer_tex"])

    def test_balanced_grid_regression_chart_compresses_without_losing_optimum(self) -> None:
        chart = _balanced_grid_regression_chart(4)
        self.assertEqual(
            chart["atomic_chart_ids"],
            [
                "finite_set.regression.sufficient_statistics.v1",
                "column_selection.cardinality_sum_interval.v1",
                "grid_partition.complement_reflection_quotient.v1",
                "rational_angle.tangent_order_certificate.v1",
            ],
        )
        self.assertEqual(chart["selected_side"], "below")
        self.assertEqual(chart["selected"]["tangent"], "7016/4053")
        self.assertEqual(chart["below"]["first_slope"], "46/63")
        self.assertEqual(chart["below"]["second_slope"], "-42/95")
        self.assertLess(
            chart["symmetry_representatives_evaluated"],
            chart["raw_compressed_states"],
        )
        self.assertLess(
            chart["raw_compressed_states"],
            chart["raw_subset_count"],
        )

    def test_balanced_grid_regression_compiler_is_alpha_renamable(self) -> None:
        statement = (
            r"格子点集合 $\{(u,v)\in\mathbb Z^2\mid 1\le u,v\le2m\}$ を"
            r"要素数が等しい二つの部分集合に分け、それぞれの回帰直線の成す角を"
            r"$\frac{\pi}{3}$ に最も近づける。(1) $m=2$、(2) $m=3$ のとき"
            r"$\sqrt{3}$ を有理近似せよ。"
        )
        compiled = compile_structural_theorem_query(statement)
        self.assertIsNotNone(compiled)
        self.assertEqual(
            compiled.operator,
            "balanced_grid_regression_angle_approximation",
        )
        self.assertEqual(compiled.objects["index"], "m")
        self.assertEqual(compiled.objects["grid_sides"], [4, 6])

    def test_cubic_arc_dot_chord_chart_rejects_the_spurious_component(self) -> None:
        chart = _cubic_arc_dot_chord_sweep_chart(
            (1, -12, 45, -54),
            20,
        )
        self.assertEqual(
            chart["atomic_chart_ids"],
            [
                "cubic.chord.symmetric_remainder.v1",
                "symmetric_constraint.component_feasibility.v1",
                "segment_family.vertical_envelope.v1",
                "piecewise_rational_area.integration.v1",
            ],
        )
        self.assertEqual(
            chart["dot_constraint_symmetric_factorization"],
            "(P - 1)*(P**2 - 3*P*S + 10*P - 3*S + 11)",
        )
        self.assertEqual(
            chart["secondary_component_infeasibility_gap"],
            "2/(3*(P + 1))",
        )
        self.assertEqual(chart["fixed_product"], "1")
        self.assertEqual(chart["area"], "log(2)/4 + 31877/5184")

    def test_cubic_arc_dot_chord_compiler_is_alpha_renamable(self) -> None:
        statement = (
            r"原点をOとする。曲線 $y=z^3-12z^2+45z-54$ の"
            r"$z$軸とともに有界領域を囲む弧上を点P,Qが"
            r"$\overrightarrow{OP}\cdot\overrightarrow{OQ}=20$を満たして動く。"
            r"線分PQの通過領域の面積を求めよ。"
        )
        compiled = compile_structural_theorem_query(statement)
        self.assertIsNotNone(compiled)
        self.assertEqual(
            compiled.operator,
            "cubic_arc_dot_chord_sweep_area",
        )
        self.assertEqual(compiled.objects["variable"], "z")
        self.assertEqual(compiled.objects["coefficients"], [1, -12, 45, -54])

    def test_coordinate_tangent_disk_projection_chart_scales_by_area(self) -> None:
        unit = _coordinate_tangent_disk_projection_chart(1)
        doubled = _coordinate_tangent_disk_projection_chart(2)
        self.assertEqual(
            unit["atomic_chart_ids"],
            [
                "disk.affine_section.support_kernel.v1",
                "support_function.sign_chamber.v1",
                "swept_union.measure_closure.v1",
            ],
        )
        self.assertEqual(sp.sympify(unit["area"]), 3 + sp.pi / 4)
        self.assertEqual(
            sp.simplify(
                sp.sympify(doubled["area"]) - 4 * sp.sympify(unit["area"])
            ),
            0,
        )
        self.assertTrue(
            all(unit["proof_obligations"].values())
        )

    def test_coordinate_tangent_disk_projection_compiler_reads_geometry(self) -> None:
        statement = (
            r"半径2の円板Dがx,y,z\geq0に含まれ、3つの座標平面の"
            r"それぞれとただ1点を共有しながら動く。Dの通過領域を"
            r"xy平面に正射影して得られる図形の面積を求めよ。"
        )
        compiled = compile_structural_theorem_query(statement)
        self.assertIsNotNone(compiled)
        self.assertEqual(
            compiled.operator,
            "coordinate_tangent_disk_projection_area",
        )
        self.assertEqual(compiled.objects["radius"], 2)

    def test_four_face_tangent_disk_sweep_chart_reuses_tangency_atom(self) -> None:
        unit = _four_face_tangent_disk_sweep_chart(1, 2)
        doubled = _four_face_tangent_disk_sweep_chart(2, 4)
        self.assertEqual(
            unit["atomic_chart_ids"],
            [
                "disk.affine_section.support_kernel.v1",
                "opposite_parallel_faces.normal_elimination.v1",
                "orientation_sign.radial_family_quotient.v1",
                "cavalieri.quarter_annulus.integral.v1",
            ],
        )
        self.assertEqual(sp.sympify(unit["volume"]), sp.pi**2 / 2)
        self.assertEqual(
            sp.simplify(
                sp.sympify(doubled["volume"]) - 8 * sp.sympify(unit["volume"])
            ),
            0,
        )
        self.assertTrue(all(unit["proof_obligations"].values()))

    def test_four_face_tangent_disk_compiler_reads_parallel_faces(self) -> None:
        statement = (
            r"1辺の長さが4の立方体"
            r"$C=\{(x,y,z)\mid0\le x,y,z\le4\}$に半径2の円板Dが含まれる。"
            r"Dの円周が立方体の4つの面$x=0,y=0,z=0,z=4$の内部と"
            r"それぞれただ1点を共有しながら動くとき、Dの通過領域の体積を求めよ。"
        )
        compiled = compile_structural_theorem_query(statement)
        self.assertIsNotNone(compiled)
        self.assertEqual(
            compiled.operator,
            "four_face_tangent_disk_swept_volume",
        )
        self.assertEqual(compiled.objects["radius"], 2)
        self.assertEqual(compiled.objects["cube_side"], 4)
        result = execute_structural_theorem_query(compiled.to_dict())
        self.assertEqual(result["diagram"]["kind"], "geometry")
        self.assertIn("tikzpicture", result["diagram_tikz"])

    def test_new_charts_recompose_on_nonbenchmark_parameters(self) -> None:
        product_chart = _complex_argument_product_chart((1, 2, 4))
        self.assertEqual(product_chart["gaussian_product"], "1 + 13*I")
        self.assertEqual(product_chart["real_part"], 1)
        self.assertEqual(product_chart["imaginary_part"], 13)

        orbit_chart = _polar_circle_doubling_chart(3)
        self.assertEqual(orbit_chart["modulus"], 7)
        self.assertEqual(orbit_chart["full_orbits"], [[1, 2, 4], [3, 6, 5]])
        self.assertEqual(orbit_chart["strictly_increasing_orbits"], [[1, 2, 4]])

    def test_complex_argument_compiler_is_alpha_renamable(self) -> None:
        statement = (
            r"複素数平面上で $w_k=k+i$ とする。整数列 "
            r"$1\le r_1\le\cdots\le r_s\le N$ が "
            r"$\tan(\arg w_{r_1}+\cdots+\arg w_{r_s})=1$ を満たす条件を求め、"
            r"それを用いて $3.141<\pi<3.142$ を示せ。"
        )
        compiled = compile_structural_theorem_query(statement)
        self.assertIsNotNone(compiled)
        self.assertEqual(compiled.operator, "complex_argument_arctangent_certificate")

    def test_polar_circle_doubling_chart_finds_the_unique_ordered_orbit(self) -> None:
        result = run(
            "polar_circle_doubling_reciprocal_identities",
            {"period": 5},
            "ProofBundle",
        )
        witness = result["certificate"]["witness"]
        self.assertEqual(witness["angle_numerators"], [1, 2, 4, 8, 16])
        self.assertEqual(witness["shared_chart"]["modulus"], 31)
        self.assertEqual(
            witness["shared_chart"]["chart_id"],
            "polar_circle.chord_doubling.v1",
        )
        self.assertIn("cot(3x)+cot(7x)", witness["part2_left_reduction"])

    def test_polar_circle_doubling_compiler_reads_geometry_and_reciprocals(self) -> None:
        statement = (
            r"極座標平面上の曲線 $r=\sin\theta$ 上に原点と異なる相異なる5点があり、"
            r"各隣接点間の距離が前の点の原点距離に等しい。"
            r"原点距離は狭義増加する。"
            r"$\frac{1}{d_1}=\frac{1}{d_2}+\frac{1}{d_3}+\frac{1}{d_4}+\frac{1}{d_5}$"
            r"および同様の弦長の逆数等式を示せ。"
        )
        compiled = compile_structural_theorem_query(statement)
        self.assertIsNotNone(compiled)
        self.assertEqual(compiled.operator, "polar_circle_doubling_reciprocal_identities")

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

    def test_power_mean_recurrence_emits_reversible_shared_chart(self) -> None:
        result = run(
            "power_mean_linearized_recurrence",
            {"first": 1, "second": 2, "weight_denominator": 2},
        )
        witness = result["certificate"]["witness"]
        self.assertEqual(witness["joint_parameter_limit"], "2**(2/3)")
        self.assertEqual(
            witness["shared_chart"]["chart_id"],
            "power_mean.recurrence.linearization.v1",
        )
        self.assertTrue(all(witness["shared_chart"]["proof_obligations"].values()))
        self.assertIn(r"2\lambda^2-\lambda-1", result["derivation_tex"][1])
        self.assertIn(r"2^{2/3}", witness["answer_tex"])

    def test_fibonacci_chebyshev_average_replays_all_parameter_residues(self) -> None:
        result = run("fibonacci_angle_period_average", {})
        witness = result["certificate"]["witness"]
        self.assertEqual(witness["period_mod_8"], [1, 1, 2, 3, 5, 0, 5, 5, 2, 7, 1, 0])
        self.assertEqual(witness["period_sine_sum"], "2")
        self.assertEqual(witness["direct_by_m_mod_8"], witness["formula_by_m_mod_8"])
        self.assertEqual(
            witness["shared_chart"]["chart_id"],
            "fibonacci.mod8.chebyshev.period_average.v1",
        )
        self.assertTrue(all(witness["shared_chart"]["proof_obligations"].values()))
        self.assertIn(r"m\equiv4\pmod 8", witness["answer_tex"])

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
        result = run_reasoning_pipeline(statement, allow_theorem_kernels=True)
        self.assertEqual(result.math_search["status"], "skipped_dedicated_ir")
        self.assertEqual(result.parser["intent"], "structural_theorem_rational_sine_prime_ratio")
        self.assertIn("{4/5,-3/5}", result.explanation)

    def test_reflected_parabola_integer_triangle_chart_has_two_atoms(self) -> None:
        chart = _parabola_reflection_integer_triangle_chart()
        self.assertEqual(
            chart["atomic_chart_ids"],
            [
                "parabola.rigid_motion.symmetric_four_point_invariant.v1",
                "rational_nodal_curve.primitive_divisibility_descent.v1",
            ],
        )
        self.assertTrue(all(chart["proof_obligations"].values()))
        self.assertEqual(
            chart["metric_invariant"],
            "4*x^2*M*h^4=(h^2+M)^3",
        )

    def test_reflected_parabola_integer_triangle_compiles_and_replays(self) -> None:
        statement = (
            r"放物線P : $y = x^2 $、直線Q : $y =ax +b$を考える."
            r"放物線と直線の交点を A, B とする。\\"
            r"PをQで折り返した像とPとの交点のうちQ上にない点を C とする."
            r"AB,BC,CAがすべて整数となるような$a,b$は存在するか."
        )
        compiled = compile_structural_theorem_query(statement)
        self.assertIsNotNone(compiled)
        self.assertEqual(
            compiled.operator,
            "parabola_reflection_integer_triangle_impossibility",
        )
        result = execute_structural_theorem_query(compiled.to_dict())
        self.assertTrue(result["verified"])
        self.assertEqual(result["answer_exact"], "存在しない")
        self.assertEqual(
            result["certificate"]["witness"]["proof_kernel_count"],
            2,
        )
        self.assertIn("m^2-n^2", result["certificate"]["witness"]["terminal_contradiction"])

        changed_curvature = statement.replace("y = x^2", "y = 2x^2")
        mutated = compile_structural_theorem_query(changed_curvature)
        self.assertTrue(
            mutated is None
            or mutated.operator
            != "parabola_reflection_integer_triangle_impossibility"
        )

    def test_cubic_circle_rational_hexagon_exact_minimum_replays(self) -> None:
        statement = (
            r"原点を通り、最高次係数が正である3次関数 $y=f(x)$ と単位円 "
            r"$x^2+y^2=1$ が相異なる6点で交わる。これらを結ぶ六角形の各内角が "
            r"$p_1\pi/q,\ldots,p_6\pi/q$ と表せる正の整数qの最小値とf(x)を求めよ。"
        )
        compiled = compile_structural_theorem_query(statement)
        self.assertIsNotNone(compiled)
        self.assertEqual(compiled.operator, "cubic_circle_rational_hexagon")
        result = execute_structural_theorem_query(compiled.to_dict())
        self.assertTrue(result["verified"])
        self.assertIn("q=5", result["answer_exact"])
        chart = result["certificate"]["witness"]["shared_chart"]
        self.assertEqual(chart["minimum_denominator"], 5)
        self.assertEqual(len(chart["feasible_patterns"]["5"]), 4)
        self.assertTrue(all(chart["proof_obligations"].values()))
        self.assertEqual(chart["substitution_residuals"], ["0"] * 6)
        phase_audit = chart["q_five_phase_audit"]
        self.assertEqual(phase_audit["field"], "Q(zeta_60)")
        self.assertEqual(
            phase_audit["patterns"]["(3, 4, 3, 3, 4, 3)"][
                "target_e2_phases_mod_60"
            ],
            [19, 49],
        )
        self.assertEqual(
            phase_audit["accepted_point_sets_mod_60"],
            [[1, 19, 25, 31, 49, 55]],
        )
        self.assertTrue(
            any(
                r"\operatorname{Im}(e_2)" in step
                for step in result["derivation_tex"]
            )
        )
        self.assertIn("tikzpicture", result["diagram_tikz"])
        self.assertTrue(result["certificate"]["cold_generalization_validated"])
        self.assertEqual(result["diagram"]["kind"], "plane")
        self.assertEqual(len(result["diagram"]["shapes"]), 12)

    def test_cubic_circle_rational_hexagon_scales_and_alpha_renames(self) -> None:
        statement = (
            r"原点を通る首項係数が正の三次関数 $v=g(u)$ と円 "
            r"$u^2+v^2=4$ は異なる六個の点で交わる。全交点を順に結んだ"
            r"6角形の各内角が $a_1\pi/r,\ldots,a_6\pi/r$ と表される。"
            r"正の整数 $r$ の最小値と $g(u)$ を求めよ。"
        )

        compiled = compile_structural_theorem_query(statement)

        self.assertIsNotNone(compiled)
        self.assertEqual(compiled.operator, "cubic_circle_rational_hexagon")
        self.assertEqual(compiled.objects["circle_radius"], "2")
        self.assertEqual(
            compiled.objects["variable_binding"],
            {
                "abscissa": "u",
                "ordinate": "v",
                "function": "g",
                "denominator": "r",
            },
        )
        result = execute_structural_theorem_query(compiled.to_dict())
        self.assertTrue(result["certificate"]["cold_generalization_validated"])
        self.assertIn("r=5", result["answer_exact"])
        self.assertIn("g(u)", result["answer_tex"])
        self.assertNotIn(r"\left(2\right)^2", result["answer_tex"])
        self.assertIn(r"\frac{(\sqrt5-1)}{\sqrt3}u^3", result["answer_tex"])
        derivation = "\n".join(result["derivation_tex"])
        self.assertIn(r"a_i\pi/r", derivation)
        self.assertIn(r"\(r=3\)", derivation)
        self.assertNotIn(r"p_i\pi/q", derivation)
        self.assertNotIn(r"\(f(x)", derivation)
        self.assertEqual(
            result["certificate"]["witness"]["current_input_replay"][
                "scaled_substitution_residuals"
            ],
            ["0"] * 6,
        )
        expected_leading = (sp.sqrt(5) - 1) / sp.sqrt(3)
        actual_leading = sp.sympify(
            result["certificate"]["witness"]["cubic_coefficients"]["u^3"]
        )
        self.assertEqual(sp.simplify(actual_leading - expected_leading), 0)

    def test_cubic_circle_rational_hexagon_accepts_declared_denominator_before_angles(self) -> None:
        statement = (
            "原点を通り、最高次係数が正である3次関数 y=f(x) と単位円 "
            "x^2+y^2=1 が相異なる6点で交わる。これらの交点を円周上の順に"
            "結んでできる六角形の各内角が、ある正の整数 q と整数 "
            "p_1,p_2,...,p_6 を用いて p_1π/q,p_2π/q,...,p_6π/q と"
            "表せるとする。q の最小値と、そのときの f(x) を求めよ。"
        )

        compiled = compile_structural_theorem_query(statement)

        self.assertIsNotNone(compiled)
        self.assertEqual(compiled.operator, "cubic_circle_rational_hexagon")
        result = execute_structural_theorem_query(compiled.to_dict())
        self.assertTrue(result["verified"])
        self.assertIn("q=5", result["answer_exact"])

    def test_cubic_circle_rational_hexagon_accepts_pi_after_fraction(self) -> None:
        statement = (
            r"原点を通り、最高次係数が正である3次関数 $y=f(x)$ と単位円 "
            r"$x^2+y^2=1$ が相異なる6点で交わる。これらの交点を結ぶ六角形の"
            r"各内角が $\frac{p_1}{q}\pi,\ldots,\frac{p_6}{q}\pi$ と表せる"
            r"正の整数 $q$ の最小値と $f(x)$ を求めよ。"
        )

        compiled = compile_structural_theorem_query(statement)

        self.assertIsNotNone(compiled)
        self.assertEqual(compiled.objects["variable_binding"]["denominator"], "q")

    def test_cubic_circle_rational_hexagon_rejects_changed_structure(self) -> None:
        statement = (
            r"原点を通り、最高次係数が正である3次関数 $y=f(x)$ と単位円 "
            r"$x^2+y^2=1$ が相異なる6点で交わる。これらを結ぶ六角形の各内角が "
            r"$p_1\pi/q,\ldots,p_6\pi/q$ と表せる正の整数qの最小値とf(x)を求めよ。"
        )
        mutations = (
            statement.replace("原点を通り、", ""),
            statement.replace("最高次係数が正", "最高次係数が負"),
            statement.replace("相異なる6点", "相異なる5点"),
            statement.replace("六角形", "五角形"),
            statement.replace("各内角", "各辺長"),
            statement.replace("x^2+y^2=1", "(x-1)^2+y^2=1"),
            statement.replace("x^2+y^2=1", "x^2+y^2=4"),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                compiled = compile_structural_theorem_query(mutation)
                self.assertTrue(
                    compiled is None
                    or compiled.operator != "cubic_circle_rational_hexagon"
                )

    def test_sample_mean_geomean_correlation_emits_reusable_exact_chart(self) -> None:
        statement = (
            "1からnまでのカードから2枚を同時に引き、相加平均と相乗平均の相関係数をrho_nとする。"
            r"\(\lim_{n\to\infty}\rho_n\)を求めよ。"
        )
        compiled = compile_structural_theorem_query(statement)
        self.assertIsNotNone(compiled)
        self.assertEqual(compiled.operator, "sample_mean_geomean_correlation")
        result = execute_structural_theorem_query(compiled.to_dict())
        self.assertEqual(result["answer_exact"], "8*sqrt(102)/85")
        chart = result["certificate"]["witness"]["shared_chart"]
        self.assertEqual(chart["chart_id"], "sample_mean.geomean.correlation_limit.v1")
        self.assertTrue(all(chart["proof_obligations"].values()))
        self.assertIn(r"\operatorname{Cov}(X,Y)=\frac2{45}", result["derivation_tex"][1])

    def test_k_sample_geomean_chart_closes_delta_method_obligations(self) -> None:
        statement = (
            "1からnまでのカードからk枚を同時に引き、相加平均と相乗平均の相関係数を"
            r"\(\cos\theta_{n,k}\)とする。\(\lim_{k\to\infty}\lim_{n\to\infty}\theta_{n,k}\)を求めよ。"
        )
        compiled = compile_structural_theorem_query(statement)
        self.assertIsNotNone(compiled)
        result = execute_structural_theorem_query(compiled.to_dict())
        self.assertEqual(result["answer_exact"], "pi/6")
        chart = result["certificate"]["witness"]["shared_chart"]
        self.assertIn("log_geometric_mean.delta_method.v1", chart["atomic_chart_ids"])
        self.assertTrue(all(chart["proof_obligations"].values()))
        self.assertIn(r"\operatorname{Cov}(U,\log U)=1/4", result["derivation_tex"][1])

    def test_chebyshev_integral_equation_emits_complete_reusable_chart(self) -> None:
        statement = (
            r"区間[-1,1]上の連続関数fが arccos を核にもつ積分方程式を満たす。"
            r"(1-x^2)f''(x)-xf'(x)+n^2f(x)=0を示し、fを求めよ。"
            r"n=pを奇素数、alpha=cos(2pi/p)としてP'(alpha)を求めよ。"
        )
        compiled = compile_structural_theorem_query(statement)
        self.assertIsNotNone(compiled)
        self.assertEqual(compiled.operator, "chebyshev_integral_equation")
        result = execute_structural_theorem_query(compiled.to_dict())
        self.assertTrue(result["verified"])
        chart = result["certificate"]["witness"]["shared_chart"]
        self.assertEqual(chart["chart_id"], "volterra.chebyshev.square_factor.v1")
        self.assertTrue(all(chart["proof_obligations"].values()))
        self.assertIn(r"u''+n^2u=0", result["derivation_tex"][1])
        self.assertIn(r"\frac12f''(\alpha)", result["derivation_tex"][4])

    def test_regular_tetrahedron_cube_support_optimum_scales(self) -> None:
        statement = "1辺が1である正四面体に完全に含むことができる立方体の1辺の大きさの最大値を求めよ。"
        compiled = compile_structural_theorem_query(statement)
        self.assertIsNotNone(compiled)
        self.assertEqual(compiled.operator, "regular_tetrahedron_max_cube")
        result = execute_structural_theorem_query(compiled.to_dict())
        self.assertTrue(result["verified"])
        expected = sp.sqrt(6) / (sp.sqrt(6) + 2 * sp.sqrt(2) + 3)
        self.assertEqual(sp.simplify(sp.sympify(result["answer_exact"]) - expected), 0)
        chart = result["certificate"]["witness"]["shared_chart"]
        self.assertEqual(chart["contact_residual"], ["0"] * 4)
        self.assertTrue(all(chart["proof_obligations"].values()))
        self.assertEqual(
            chart["proof_basis"],
            "published_global_theorem_with_exact_current_input_replay",
        )
        self.assertEqual(
            chart["trusted_theorem_dependencies"][0]["theorem_id"],
            "croft.1980.regular_cube_in_regular_tetrahedron",
        )
        self.assertTrue(result["certificate"]["cold_generalization_validated"])
        self.assertIn(r"\frac{8\rho}{S(U)}", result["derivation_tex"][1])
        self.assertIn("tikzpicture", result["diagram_tikz"])
        self.assertEqual(result["diagram"]["kind"], "plane")
        self.assertGreaterEqual(len(result["diagram"]["shapes"]), 16)
        self.assertIn(
            "section-square",
            {shape.get("id") for shape in result["diagram"]["shapes"]},
        )

        scaled = compile_structural_theorem_query(statement.replace("1辺が1", "1辺が2"))
        self.assertIsNotNone(scaled)
        scaled_result = execute_structural_theorem_query(scaled.to_dict())
        self.assertEqual(
            sp.simplify(sp.sympify(scaled_result["answer_exact"]) - 2 * expected),
            0,
        )
        self.assertIn("2", scaled_result["answer_tex"])

        fractional = compile_structural_theorem_query(
            statement.replace("1辺が1", "一辺の長さが7/3")
        )
        self.assertIsNotNone(fractional)
        fractional_result = execute_structural_theorem_query(fractional.to_dict())
        self.assertEqual(
            sp.simplify(
                sp.sympify(fractional_result["answer_exact"])
                - sp.Rational(7, 3) * expected
            ),
            0,
        )

        variants = (
            "一辺の長さが2の正四面体の内部に収まる立方体の一辺の最大値を求めよ。",
            r"一辺が$\frac{7}{3}$である正四面体の中に入る立方体の辺長の最大値を求めよ。",
        )
        expected_edges = (sp.Integer(2), sp.Rational(7, 3))
        for variant, variant_edge in zip(variants, expected_edges):
            with self.subTest(variant=variant):
                variant_ir = compile_structural_theorem_query(variant)
                self.assertIsNotNone(variant_ir)
                self.assertEqual(
                    variant_ir.objects,
                    {
                        "outer_polytope": "regular_tetrahedron",
                        "outer_edge": sp.sstr(variant_edge),
                        "inner_polytope": "cube",
                        "containment_mode": "euclidean_similarity_inside",
                        "objective": "maximize_inner_edge",
                        "ambient_dimension": 3,
                    },
                )
                variant_result = execute_structural_theorem_query(variant_ir.to_dict())
                self.assertEqual(
                    sp.simplify(
                        sp.sympify(variant_result["answer_exact"])
                        - variant_edge * expected
                    ),
                    0,
                )

        for invalid_edge in ("0", "-1"):
            invalid = compile_structural_theorem_query(
                statement.replace("1辺が1", f"1辺が{invalid_edge}")
            )
            self.assertIsNotNone(invalid)
            with self.assertRaises(ValueError):
                execute_structural_theorem_query(invalid.to_dict())

        self.assertIsNone(
            compile_structural_theorem_query(
                statement.replace("1辺が1", "1辺がa")
            )
        )

    def test_primitive_right_triangle_center_fraction_uses_radius_chart(self) -> None:
        statement = (
            "3辺の長さが互いに素な自然数である直角三角形の外心をO、内心をIとする。"
            "$OI^2$の小数部分を求めよ。"
        )
        compiled = compile_structural_theorem_query(statement)
        self.assertIsNotNone(compiled)
        self.assertEqual(compiled.operator, "primitive_right_triangle_center_fraction")
        result = execute_structural_theorem_query(compiled.to_dict())
        self.assertEqual(result["answer_exact"], "1/4")
        chart = result["certificate"]["witness"]["shared_chart"]
        self.assertEqual(
            chart["radius_relation_chart"]["chart_id"],
            "triangle.radii.euler_sum_product.v1",
        )
        self.assertTrue(all(chart["proof_obligations"].values()))
        self.assertIn(r"c^2\equiv1\pmod4", result["derivation_tex"][2])
        self.assertIn("tikzpicture", result["diagram_tikz"])

    def test_rational_angle_power_identity_uses_composed_galois_charts(self) -> None:
        statement = (
            r"$0<2p<q$ を満たす互いに素な自然数 $p,q$ と自然数 $n\geqq2$ に対し，"
            r"\[\cos^n\frac{p\pi}{q}+\sin^n\frac{p\pi}{q}="
            r"\cos\frac{np\pi}{q}+\sin\frac{np\pi}{q}\]"
            r"が成り立つ組 $(n,p,q)$ をすべて求めよ．"
        )
        compiled = compile_structural_theorem_query(statement)
        self.assertIsNotNone(compiled)
        self.assertEqual(compiled.operator, "rational_angle_power_identity")
        result = execute_structural_theorem_query(compiled.to_dict())
        self.assertTrue(result["verified"])
        self.assertEqual(result["answer_exact"], "{(2,1,4)}")
        chart = result["certificate"]["witness"]["shared_chart"]
        self.assertEqual(
            chart["chart_id"],
            "rational_angle.power_identity.galois_orbit.v1",
        )
        self.assertEqual(len(chart["morphism_chain"]), 4)
        self.assertEqual(
            [morphism["output_type"] for morphism in chart["morphism_chain"]],
            [
                "ForAll[UnitGroupElement,RealNormInequality]",
                "FiniteSet[ReducedDenominator]",
                "TotientUpperBound",
                "ContradictionCertificate",
            ],
        )
        self.assertEqual(chart["low_totient_orders"], [24, 48])
        self.assertEqual(len(chart["proof_roadmap"]), 6)
        self.assertEqual(len(chart["proof_obligation_records"]), 8)
        self.assertEqual(
            chart["proof_roadmap"][0]["morphism_id"],
            "cyclotomic.conjugate.uniform_norm_bound.v1",
        )
        self.assertEqual(chart["proof_obligation_records"][-1]["id"], "O8")
        self.assertIn("素因数分解", result["derivation_tex"][6])
        self.assertIn("中国剰余定理", result["derivation_tex"][2])
        self.assertTrue(all(chart["proof_obligations"].values()))
        self.assertEqual(chart["solution_records"][0]["substitution_residual"], "0")
        self.assertIn(r"\chi_4(k)\sin(2nk\alpha)\le0", result["derivation_tex"][1])
        self.assertIn("tikzpicture", result["diagram_tikz"])

        changed_rhs = statement.replace("np\\pi", "(n+1)p\\pi")
        mutated = compile_structural_theorem_query(changed_rhs)
        self.assertTrue(
            mutated is None or mutated.operator != "rational_angle_power_identity"
        )

    def test_regular_polygon_roll_limit_uses_generic_se2_sweep_chart(self) -> None:
        statement = (
            "正の整数 n>=3 に対し，外接円の半径が1である二つの正n角形を考える。"
            "固定する正n角形はすべて同じ中心Oと同じ頂点P_1を共有するように配置する。"
            "一方を固定し，他方を，一辺を共有する状態から，接点が常に両者の頂点となるように，"
            "固定した正n角形の外側を滑ることなく一周させる。"
            "動く正n角形が通過する部分をD_nとする。D_3,D_4,...,D_nの共通部分の面積を"
            "S_nとするとき，lim S_nを求めよ。"
        )
        compiled = compile_structural_theorem_query(statement)
        self.assertIsNotNone(compiled)
        self.assertEqual(
            compiled.operator,
            "regular_polygon_external_roll_common_limit",
        )
        result = execute_structural_theorem_query(compiled.to_dict())
        self.assertTrue(result["verified"])
        chart = result["certificate"]["witness"]["shared_chart"]
        self.assertEqual(
            chart["chart_id"],
            "regular_polygon.roll_sweep.common_limit.v1",
        )
        self.assertEqual(
            chart["morphism_chain"][0]["chart_id"],
            "rigid_motion.se2.sweep_orbit.v1",
        )
        self.assertIn(
            "translation",
            chart["morphism_chain"][0]["supported_motion_atoms"],
        )
        self.assertEqual(
            chart["stabilized_outer_intersection"],
            "F_3 intersect F_4 intersect F_5",
        )
        self.assertAlmostEqual(
            result["certificate"]["witness"]["answer_numeric"],
            16.082892753530352,
            places=11,
        )
        self.assertTrue(all(chart["proof_obligations"].values()))
        self.assertEqual(len(chart["active_radial_segments_on_0_pi"]), 8)
        self.assertIn("tikzpicture", result["diagram_tikz"])
        visual = result["visual_explanation"]
        self.assertTrue(visual["composition_verified"])
        self.assertEqual(len(visual["steps"]), 9)
        self.assertEqual(
            [step["id"] for step in visual["steps"][1:6]],
            [
                "cumulative-n-3",
                "cumulative-n-4",
                "cumulative-n-5",
                "cumulative-n-6",
                "cumulative-n-7",
            ],
        )
        self.assertTrue(all(step.get("diagram") for step in visual["steps"]))
        self.assertIn(r"\mathcal A", result["answer_tex"])
        self.assertNotIn("16.082", result["answer_tex"])
        self.assertNotIn("SE(2)", " ".join(result["derivation_tex"]))

        radius_two = statement.replace("半径が1", "半径が2")
        scaled_compiled = compile_structural_theorem_query(radius_two)
        self.assertIsNotNone(scaled_compiled)
        self.assertEqual(
            scaled_compiled.operator,
            "regular_polygon_external_roll_common_limit",
        )
        scaled_result = execute_structural_theorem_query(scaled_compiled.to_dict())
        self.assertTrue(scaled_result["verified"])
        self.assertEqual(
            scaled_result["certificate"]["witness"]["similarity_area_scale"],
            "4",
        )
        self.assertAlmostEqual(
            scaled_result["certificate"]["witness"]["answer_numeric"],
            4 * result["certificate"]["witness"]["answer_numeric"],
            places=10,
        )

        missing_alignment = statement.replace(
            "固定する正n角形はすべて同じ中心Oと同じ頂点P_1を共有するように配置する。",
            "",
        )
        unnormalized = compile_structural_theorem_query(missing_alignment)
        self.assertTrue(
            unnormalized is None
            or unnormalized.operator
            != "regular_polygon_external_roll_common_limit"
        )

        chord_sweep = (
            "n>=3 とし，単位円に内接する正n角形の周上を PQ=1 を保って"
            "2点P,Qが動くときの線分PQの通過領域をD_nとする。"
            "D_3,D_4,...,D_nの共通部分の面積S_nの極限を求めよ。"
        )
        chord_compiled = compile_structural_theorem_query(chord_sweep)
        self.assertTrue(
            chord_compiled is None
            or chord_compiled.operator
            != "regular_polygon_external_roll_common_limit"
        )


if __name__ == "__main__":
    unittest.main()
