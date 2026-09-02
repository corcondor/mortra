from __future__ import annotations

import sys
import json
import unittest
from pathlib import Path
from unittest.mock import patch


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from api.solve import solve_problem, solve_public_problem


class PublicSolveTests(unittest.TestCase):
    def assert_runtime_synthesis_card(self, card: dict[str, object]) -> None:
        certificate = card["execution_certificate"]
        verification = card["verification"]
        self.assertEqual(certificate["capability_origin"], "synthesized_proof_program")
        self.assertFalse(certificate["registered_composite_used"])
        self.assertTrue(certificate["verified"])
        self.assertTrue(verification["exact_backend"])
        self.assertTrue(verification["independent_check"])
        self.assertGreater(len(card["solution_tex"]), 80)
        self.assertNotIn("\ufffd", json.dumps(card, ensure_ascii=False, default=str))

    def test_current_input_function_variation_generates_exact_table_and_plot(self) -> None:
        status, payload = solve_public_problem(
            "関数 f(x)=x^3-3x の増減、極大値、極小値を求め、グラフの概形を描け。"
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assert_runtime_synthesis_card(card)
        self.assertEqual(card["diagram"]["kind"], "calculus")
        self.assertEqual(card["diagram"]["variable"], "x")
        self.assertEqual(card["diagram"]["functionTex"], "x^{3} - 3 x")
        self.assertEqual(card["diagram"]["derivativeTex"], r"3 \left(x - 1\right) \left(x + 1\right)")
        self.assertEqual(card["diagram"]["domainTex"], r"\mathbb{R}")
        self.assertTrue(card["diagram"]["certificateMethod"])
        self.assertNotIn("undefined", json.dumps(card["diagram"], ensure_ascii=False))
        self.assertIn("x=-1", card["answer_tex"])
        self.assertIn("x=1", card["answer_tex"])
        self.assertIn("2", card["answer_tex"])
        self.assertIn(r"したがって \(x=", card["solution_tex"])
        self.assertNotIn("したがって x=", card["solution_tex"])

    def test_normalized_inner_product_constructs_exact_function_pair(self) -> None:
        status, payload = solve_public_problem(
            r"\frac{\int_0^1 f(x)g(x)dx}{\sqrt{\int_0^1 f(x)^2dx}\sqrt{\int_0^1 g(x)^2dx}}"
            r"=\cos\frac{\pi}{6} を満たす関数 f(x),g(x) を一組求め、図示せよ。"
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assert_runtime_synthesis_card(card)
        self.assertEqual(
            card["execution_certificate"]["tool_name"],
            "mortra.runtime_normalized_inner_product_realization",
        )
        self.assertEqual(card["diagram"]["kind"], "plane")
        self.assertIn(r"f(x)=1", card["answer_tex"])
        self.assertIn(r"g(x)=\sqrt{3} x", card["answer_tex"])
        witness = card["execution_certificate"]["witness"]
        self.assertEqual(witness["gram_matrix"], [["1", "sqrt(3)/2"], ["sqrt(3)/2", "1"]])
        self.assertEqual(witness["normalized_inner_product"], "sqrt(3)/2")

    def test_normalized_inner_product_accepts_corpus_style_braced_bounds(self) -> None:
        status, payload = solve_public_problem(
            r"\frac{\int_{0}^{1} f(x)g(x)\,dx}"
            r"{\sqrt{\int_{0}^{1} f(x)^2\,dx}\sqrt{\int_{0}^{1} g(x)^2\,dx}}"
            r"=\cos\frac{\pi}{6} を満たす関数 f(x),g(x) を一組求め、図示せよ。"
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assert_runtime_synthesis_card(card)
        self.assertEqual(
            card["execution_certificate"]["tool_name"],
            "mortra.runtime_normalized_inner_product_realization",
        )
        self.assertIn(r"f(x)=1", card["answer_tex"])
        self.assertIn(r"g(x)=\sqrt{3} x", card["answer_tex"])

    def test_normalized_inner_product_recomputes_interval_and_target(self) -> None:
        status, payload = solve_public_problem(
            r"区間 [2,5] 上で \frac{\int_2^5 p(t)q(t)dt}"
            r"{\sqrt{\int_2^5 p(t)^2dt}\sqrt{\int_2^5 q(t)^2dt}}=\frac12 "
            r"を満たす関数 p(t),q(t) を一組求め、図示せよ。"
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assert_runtime_synthesis_card(card)
        self.assertIn(r"p(t)=\frac{\sqrt{3}}{3}", card["answer_tex"])
        self.assertIn(r"q(t)=\frac{\sqrt{3} \left(t - 3\right)}{3}", card["answer_tex"])
        witness = card["execution_certificate"]["witness"]
        self.assertEqual(witness["interval"], ["2", "5"])
        self.assertEqual(witness["target"], "1/2")
        self.assertEqual(witness["normalized_inner_product"], "1/2")

    def test_primitive_right_triangle_center_fraction_is_synthesized_from_current_input(self) -> None:
        statement = (
            "3辺の長さが互いに素な自然数である直角三角形の外心をO,"
            "内心をIとする. $OI^{2}$ の小数部分を求めよ."
        )

        status, payload = solve_public_problem(statement)

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assert_runtime_synthesis_card(card)
        self.assertEqual(card["answer_tex"], r"\(\dfrac14\)")
        self.assertEqual(
            card["execution_certificate"]["tool_name"],
            "mortra.runtime_primitive_right_triangle_center_fraction",
        )
        self.assertEqual(card["diagram"]["kind"], "plane")
        self.assertEqual(len(card["visual_explanation"]["steps"]), 3)
        self.assertIn(r"c^2\equiv1\pmod4", card["solution_tex"])

    def test_primitive_right_triangle_center_fraction_uses_renamed_centers(self) -> None:
        statement = (
            "三辺が互いに素な正の整数である直角三角形について,"
            "外心をP, 内心をJとする. $JP^2$ の小数部分を求めよ."
        )

        status, payload = solve_public_problem(statement)

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assert_runtime_synthesis_card(card)
        witness = card["execution_certificate"]["witness"]
        self.assertEqual(witness["center_labels"], {"circumcenter": "P", "incenter": "J"})
        self.assertIn(r"PJ^2", card["solution_tex"])

    def test_center_fraction_chart_rejects_missing_primitivity(self) -> None:
        statement = (
            "3辺の長さが自然数である直角三角形の外心をO,"
            "内心をIとする. $OI^2$ の小数部分を求めよ."
        )

        status, payload = solve_public_problem(statement)

        self.assertEqual(status, 422)
        self.assertEqual(payload["generated"], 0)

    def test_normalized_inner_product_rejects_impossible_target(self) -> None:
        status, payload = solve_public_problem(
            r"\frac{\int_{0}^{1} f(x)g(x)\,dx}"
            r"{\sqrt{\int_{0}^{1} f(x)^2\,dx}\sqrt{\int_{0}^{1} g(x)^2\,dx}}"
            r"=2 を満たす実関数 f(x),g(x) を一組求め、図示せよ。"
        )

        self.assertEqual(status, 200)
        self.assertEqual(payload["generated"], 1)
        card = payload["cards"][0]
        self.assert_runtime_synthesis_card(card)
        self.assertEqual(
            card["execution_certificate"]["tool_name"],
            "mortra.runtime_normalized_inner_product_infeasibility",
        )
        self.assertIn("存在しない", card["answer_tex"])
        self.assertEqual(card["execution_certificate"]["witness"]["exists"], False)
        self.assertEqual(card["execution_certificate"]["witness"]["target_squared_minus_one"], "3")
        self.assertEqual(card["diagram"]["kind"], "plane")

    def test_function_variation_recomputes_after_coefficient_change(self) -> None:
        status, payload = solve_public_problem(
            "関数 f(x)=x^3-12x の増減、極大値、極小値を求め、グラフの概形を描け。"
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assert_runtime_synthesis_card(card)
        self.assertIn("x=-2", card["answer_tex"])
        self.assertIn("x=2", card["answer_tex"])
        self.assertIn("16", card["answer_tex"])

    def test_current_input_triangle_centers_generate_exact_construction(self) -> None:
        status, payload = solve_public_problem(
            "座標平面上の三角形 A(0,0), B(6,0), C(2,4) の外心と内心を求め、"
            "解答に必要な補助線を含む図を描け。"
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assert_runtime_synthesis_card(card)
        self.assertEqual(card["diagram"]["kind"], "plane")
        self.assertIn(r"O=\left(3,1\right)", card["answer_tex"])
        self.assertGreaterEqual(len(card["diagram"]["shapes"]), 8)

    def test_triangle_centers_recompute_after_coordinate_change(self) -> None:
        status, payload = solve_public_problem(
            "座標平面上の三角形 A(0,0), B(8,0), C(0,6) の外心と内心を求め、図を描け。"
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assert_runtime_synthesis_card(card)
        self.assertIn(r"O=\left(4,3\right)", card["answer_tex"])
        self.assertIn(r"I=\left(2,2\right)", card["answer_tex"])

    def test_orthocenter_reflections_generate_fresh_exact_proof_and_diagrams(self) -> None:
        status, payload = solve_public_problem(
            "鋭角三角形 ABC の垂心を H とする。H を辺 BC、CA、AB に関して"
            "対称移動した3点が三角形 ABC の外接円上にあることを証明し、"
            "各対称点と補助線を含む図を描け。"
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assert_runtime_synthesis_card(card)
        self.assertEqual(
            card["execution_certificate"]["tool_name"],
            "mortra.runtime_orthocenter_line_reflection_circumcircle",
        )
        self.assertEqual(card["diagram"]["kind"], "plane")
        self.assertEqual(len(card["visual_explanation"]["steps"]), 4)
        self.assertTrue(card["publication_contract"]["diagram_for_every_visual_step"])
        witness = card["execution_certificate"]["witness"]
        self.assertEqual(len(witness["typed_ir"]["reflections"]), 3)
        self.assertTrue(all(value == "Integer(0)" for value in witness["display_circle_residuals"].values()))
        self.assertIn("任意の一辺", card["solution_tex"])

    def test_orthocenter_reflection_solver_generalizes_over_labels_and_each_side_wording(self) -> None:
        status, payload = solve_public_problem(
            "三角形 PQR の垂心を T とする。T を三角形 PQR の各辺に関して"
            "それぞれ折り返して得られる三点が、PQR の外接円周上にあることを示せ。"
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assert_runtime_synthesis_card(card)
        witness = card["execution_certificate"]["witness"]
        self.assertEqual(witness["typed_ir"]["vertices"], ["P", "Q", "R"])
        self.assertEqual(
            [item["result"] for item in witness["typed_ir"]["reflections"]],
            ["T_P", "T_Q", "T_R"],
        )

    def test_orthocenter_reflection_solver_accepts_named_single_reflection(self) -> None:
        status, payload = solve_public_problem(
            "三角形 ABC の垂心を H とする。辺 BC に関する H の対称点を X とする。"
            "X が三角形 ABC の外接円上にあることを証明せよ。"
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assert_runtime_synthesis_card(card)
        witness = card["execution_certificate"]["witness"]
        self.assertEqual(witness["typed_ir"]["reflections"], [{
            "source": "H",
            "axis": ["B", "C"],
            "result": "X",
            "opposite_vertex": "A",
        }])

    def test_current_input_coin_run_generates_state_equations_and_diagram(self) -> None:
        status, payload = solve_public_problem(
            "公平な硬貨を繰り返し投げ、表が2回連続した時点で終了する。"
            "終了までの投数の期待値を求め、状態遷移図を用いて説明せよ。"
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assert_runtime_synthesis_card(card)
        self.assertEqual(card["answer_tex"], r"\(6\)")
        self.assertEqual(card["diagram"]["kind"], "state")
        self.assertEqual(len(card["diagram"]["states"]), 3)

    def test_coin_run_recomputes_for_three_consecutive_heads(self) -> None:
        status, payload = solve_public_problem(
            "公平な硬貨を繰り返し投げ、表が3回連続した時点で終了する。"
            "終了までの投数の期待値を求め、状態遷移図を用いて説明せよ。"
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assert_runtime_synthesis_card(card)
        self.assertEqual(card["answer_tex"], r"\(14\)")
        self.assertEqual(len(card["diagram"]["states"]), 4)

    def test_nested_radical_iteration_replays_a_current_input_certificate(self) -> None:
        status, payload = solve_public_problem(
            r"$\sqrt{4^{1\sqrt{4^{1\sqrt{4^{1\cdots}}}}}} \text{の値を求めよ.}$"
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assert_runtime_synthesis_card(card)
        self.assertEqual(card["answer_tex"], r"\(\infty\)")
        self.assertEqual(
            card["execution_certificate"]["tool_name"],
            "sympy.iteration_query",
        )
        self.assertIn("固定点", card["solution_tex"])

    def test_cubic_centroid_locus_replays_after_coefficient_change(self) -> None:
        status, payload = solve_public_problem(
            r"曲線 $y=x^3-5x+7$ 上の3点を頂点とする正三角形の重心の軌跡が囲む部分の面積を求めよ."
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assert_runtime_synthesis_card(card)
        self.assertEqual(
            card["answer_tex"],
            r"\(\frac{4 \pi \left(5 - \sqrt{3}\right)}{9}\)",
        )
        self.assertEqual(
            card["execution_certificate"]["tool_name"],
            "sympy.cubic_centroid_locus",
        )
        self.assertIn("Fourier", card["solution_tex"])

    def test_second_order_recurrence_compiles_to_matrix_and_closed_form(self) -> None:
        status, payload = solve_public_problem(
            "数列 {a_n} を a_0=2, a_1=5, a_{n+2}=3a_{n+1}-2a_n で定める。"
            "一般項と a_{10} を求め、漸化式を表す遷移行列を図示せよ。"
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assert_runtime_synthesis_card(card)
        self.assertIn("3071", card["answer_tex"])
        self.assertEqual(card["diagram"]["kind"], "state")
        self.assertEqual(card["execution_certificate"]["witness"]["coefficients"], ["3", "-2"])

    def test_second_order_recurrence_recomputes_changed_coefficients(self) -> None:
        status, payload = solve_public_problem(
            "数列 {b_n} を b_0=1, b_1=3, b_{n+2}=4b_{n+1}-3b_n で定める。"
            "一般項と b_6 を求め、遷移行列を図示せよ。"
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assert_runtime_synthesis_card(card)
        self.assertIn("729", card["answer_tex"])
        self.assertEqual(card["execution_certificate"]["witness"]["coefficients"], ["4", "-3"])

    def test_second_order_recurrence_answers_the_requested_generating_function(self) -> None:
        status, payload = solve_public_problem(
            "数列 a_0=2, a_1=3, a_{n+2}=4a_{n+1}-3a_n の母関数を求めよ。"
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assert_runtime_synthesis_card(card)
        self.assertEqual(
            card["answer_tex"],
            r"\[A(z)=\sum_{n=0}^\infty a_n z^n=\frac{2 - 5 z}{3 z^{2} - 4 z + 1}\]",
        )
        witness = card["execution_certificate"]["witness"]
        self.assertEqual(witness["observable"], "ordinary_generating_function")
        self.assertEqual(witness["replayed_coefficients"][:5], ["Integer(2)", "Integer(3)", "Integer(6)", "Integer(15)", "Integer(42)"])
        self.assertIn("母関数", card["solution_tex"])
        self.assertNotIn("a_n=", card["answer_tex"])
        diagram_text = json.dumps(card["diagram"], ensure_ascii=False)
        self.assertNotIn("\\", diagram_text)
        self.assertNotIn("_{", diagram_text)

    def test_generating_function_recomputes_after_coefficient_change(self) -> None:
        status, payload = solve_public_problem(
            "数列 c_0=1, c_1=4, c_{n+2}=5c_{n+1}-6c_n の母関数を求めよ。"
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assert_runtime_synthesis_card(card)
        self.assertEqual(
            card["answer_tex"],
            r"\[A(z)=\sum_{n=0}^\infty c_n z^n=\frac{1 - z}{6 z^{2} - 5 z + 1}\]",
        )
        self.assertEqual(
            card["execution_certificate"]["witness"]["replayed_coefficients"][:4],
            ["Integer(1)", "Integer(4)", "Integer(14)", "Integer(46)"],
        )

    def test_recurrence_dirichlet_series_proves_exponential_divergence(self) -> None:
        status, payload = solve_public_problem(
            "数列 a_0=2, a_1=3, a_{n+2}=4a_{n+1}-3a_n のディリクレ級数を求めよ。"
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assert_runtime_synthesis_card(card)
        self.assertEqual(
            card["execution_certificate"]["tool_name"],
            "mortra.runtime_second_order_dirichlet_series",
        )
        witness = card["execution_certificate"]["witness"]
        self.assertEqual(witness["observable"], "dirichlet_series")
        self.assertEqual(witness["convergence_domain"], "empty")
        self.assertEqual(witness["dominant_ratio_limit"], "1")
        self.assertIn("すべての", card["answer_tex"])
        self.assertIn("発散", card["solution_tex"])
        self.assertEqual(card["diagram"]["kind"], "state")

    def test_recurrence_dirichlet_series_recomputes_changed_growth_rate(self) -> None:
        status, payload = solve_public_problem(
            "数列 b_0=2, b_1=3, b_{n+2}=3b_{n+1}-2b_n のディリクレ級数を求めよ。"
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assert_runtime_synthesis_card(card)
        witness = card["execution_certificate"]["witness"]
        self.assertEqual(witness["convergence_domain"], "empty")
        self.assertIn("Integer(2)", witness["dominant_root"])
        self.assertNotIn("Integer(3)", witness["dominant_root"])

    def test_recurrence_dirichlet_series_handles_exponentially_decaying_modes(self) -> None:
        status, payload = solve_public_problem(
            "数列 c_0=2, c_1=5/6, c_{n+2}=5/6c_{n+1}-1/6c_n のディリクレ級数を求めよ。"
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assert_runtime_synthesis_card(card)
        witness = card["execution_certificate"]["witness"]
        self.assertEqual(witness["convergence_domain"], "complex-plane")
        self.assertIn("polylog", witness["dirichlet_series"])
        self.assertIn("s\\in\\mathbb C", card["answer_tex"])

    def test_recurrence_dirichlet_series_does_not_fall_back_to_a_different_observable(self) -> None:
        status, payload = solve_public_problem(
            "数列 d_0=1, d_1=1, d_{n+2}=2d_{n+1}-d_n のディリクレ級数を求めよ。"
        )

        self.assertEqual(status, 422)
        self.assertEqual(payload["generated"], 0)

    def test_linear_congruence_enumerates_every_residue_class(self) -> None:
        status, payload = solve_public_problem(
            "整数 x について、合同式 14x≡30 (mod 100) を満たす剰余類をすべて求めよ。"
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assert_runtime_synthesis_card(card)
        self.assertEqual(card["execution_certificate"]["witness"]["solutions"], [45, 95])

    def test_factorial_valuation_uses_prime_power_multiplicities(self) -> None:
        status, payload = solve_public_problem("100! を割り切る最大の 2 のべき 2^k を求めよ。")

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assert_runtime_synthesis_card(card)
        self.assertEqual(card["answer_tex"], r"\(k=97\)")
        self.assertEqual(card["execution_certificate"]["witness"]["terms"], [50, 25, 12, 6, 3, 1])

    def test_biased_coin_run_uses_input_probability(self) -> None:
        status, payload = solve_public_problem(
            "表の出る確率が 1/3 の硬貨を独立に投げ、表が3回連続した時点で終了する。"
            "終了までの投数の期待値を求め、状態遷移図で説明せよ。"
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assert_runtime_synthesis_card(card)
        self.assertEqual(card["answer_tex"], r"\(39\)")
        self.assertEqual(card["execution_certificate"]["witness"]["probability_heads"], "1/3")

    def test_rational_variation_keeps_poles_separate_from_critical_points(self) -> None:
        status, payload = solve_public_problem(
            "関数 f(x)=(x^2+1)/(x-1) の増減と極値を求め、漸近線を含むグラフの概形を描け。"
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assert_runtime_synthesis_card(card)
        self.assertEqual(card["diagram"]["kind"], "calculus")
        self.assertIn(r"1 - \sqrt{2}", card["answer_tex"])
        self.assertIn(r"y=x + 1", card["answer_tex"])
        self.assertEqual(card["execution_certificate"]["witness"]["poles"], ["Integer(1)"])

    def test_positive_monomial_extremum_is_recomputed_from_exponents(self) -> None:
        status, payload = solve_public_problem(
            "正の実数 x,y が x+y=10 を満たすとき、x^2y の最大値と、そのときの x,y を求めよ。"
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assert_runtime_synthesis_card(card)
        self.assertIn(r"\frac{4000}{27}", card["answer_tex"])
        self.assertEqual(card["execution_certificate"]["witness"]["exponents"], [2, 1])
        self.assertEqual(card["diagram"]["kind"], "plane")

    def test_tetrahedron_volume_and_projection_share_the_same_coordinates(self) -> None:
        status, payload = solve_public_problem(
            "空間内の4点 A(0,0,0), B(2,0,0), C(0,3,0), D(0,0,4) が作る四面体の体積を求め、"
            "座標軸と四面体を図示せよ。"
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assert_runtime_synthesis_card(card)
        self.assertEqual(card["answer_tex"], r"\(V=4\)")
        self.assertEqual(card["diagram"]["kind"], "plane")
        self.assertGreaterEqual(len(card["diagram"]["shapes"]), 13)

    def test_first_repeat_die_expectation_has_an_independent_survival_sum(self) -> None:
        status, payload = solve_public_problem(
            "公平な6面体のさいころを繰り返し投げ、初めて同じ目が2回現れた時点で終了する。"
            "終了までの投数の期待値を求め、状態遷移図で説明せよ。"
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assert_runtime_synthesis_card(card)
        self.assertEqual(card["answer_tex"], r"\(E_0=\frac{1223}{324}\)")
        self.assertEqual(card["diagram"]["kind"], "state")
        self.assertEqual(card["execution_certificate"]["witness"]["sides"], 6)

    def test_linear_trigonometric_equation_returns_all_half_open_period_roots(self) -> None:
        status, payload = solve_public_problem(
            "0≤x<2π において sin x+cos x=1 を満たす x をすべて求め、二つのグラフの交点として図示せよ。"
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assert_runtime_synthesis_card(card)
        self.assertEqual(card["answer_tex"], r"\(x=0,\;\frac{\pi}{2}\)")
        self.assertEqual(card["diagram"]["kind"], "plane")
        self.assertEqual(len(card["execution_certificate"]["witness"]["solutions"]), 2)

    def test_runtime_structural_kernels_recompute_unseen_parameters(self) -> None:
        cases = (
            (
                "関数 f(x)=(x^2+4)/(x-2) の増減と極値を求め、漸近線を含むグラフの概形を描け。",
                r"2 + 2 \sqrt{2}",
                "mortra.runtime_rational_variation",
            ),
            (
                "正の実数 u,v が u+v=15 を満たすとき、u^3v^2 の最大値と、そのときの u,v を求めよ。",
                "26244",
                "mortra.runtime_positive_monomial_extremum",
            ),
            (
                "空間内の4点 P(0,0,0), Q(3,0,0), R(0,4,0), S(0,0,5) が作る四面体の体積を求め、"
                "座標軸と四面体を図示せよ。",
                r"V=10",
                "mortra.runtime_tetrahedron_determinant_volume",
            ),
            (
                "公平な4面体のさいころを繰り返し投げ、初めて同じ目が2回現れた時点で終了する。"
                "終了までの投数の期待値を求め、状態遷移図で説明せよ。",
                r"\frac{103}{32}",
                "mortra.runtime_first_repeat_die_expectation",
            ),
            (
                "0≤t<2π において 2sin t=1 を満たす t をすべて求め、二つのグラフの交点として図示せよ。",
                r"\frac{5 \pi}{6}",
                "mortra.runtime_linear_trigonometric_equation",
            ),
            (
                "整数 z について、合同式 18z≡12 (mod 30) を満たす剰余類をすべて求めよ。",
                r"29",
                "mortra.runtime_linear_congruence",
            ),
            (
                "75! を割り切る最大の 3 のべき 3^k を求めよ。",
                r"k=35",
                "mortra.runtime_factorial_prime_valuation",
            ),
        )
        for statement, expected, tool_name in cases:
            with self.subTest(statement=statement):
                status, payload = solve_public_problem(statement)
                self.assertEqual(status, 200)
                card = payload["cards"][0]
                self.assert_runtime_synthesis_card(card)
                self.assertIn(expected, card["answer_tex"])
                self.assertEqual(card["execution_certificate"]["tool_name"], tool_name)

    def test_current_input_integral_inequality_generates_exact_visual_proof(self) -> None:
        status, payload = solve_public_problem(
            r"I=\int_0^{\pi/2}\{\cos(\cos x+\sin x)+\sin(\cos x+\sin x)\}\,dx "
            r"とする。0<I<2 を証明せよ。"
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assert_runtime_synthesis_card(card)
        self.assertEqual(card["answer_tex"], r"\[0<I<2.\]")
        self.assertIn("Cauchy--Schwarz", card["solution_tex"])
        self.assertIn(r"\pi<22/7", card["solution_tex"])
        self.assertIn("diagram", card)

    def test_original_bare_integral_inequality_elaborates_to_the_same_proof(self) -> None:
        status, payload = solve_public_problem(
            r"$\displaystyle\int_0^{\frac{\pi}2}"
            r"\{\cos(\cos x+\sin x)+\sin(\cos x+\sin x)\}\,dx<2$"
            "\nを示せ。"
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assert_runtime_synthesis_card(card)
        self.assertEqual(
            card["execution_certificate"]["tool_name"],
            "mortra.runtime_complement_angle_integral_bound",
        )
        self.assertIn(r"\int", card["statement_tex"])
        self.assertIn(r"0<I<2", card["answer_tex"])
        self.assertEqual(
            card["execution_certificate"]["proof_program"][0]["input_form"],
            "bare",
        )

    def test_formula_only_ocr_integral_inequality_elaborates_to_the_same_proof(self) -> None:
        status, payload = solve_public_problem(
            "$$\n"
            r"\int_{0}^{\frac{\pi}{2}} \{\cos (\cos x+\sin x)+\sin (\cos x+\sin x)\} \,dx<2"
            "\n$$"
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assert_runtime_synthesis_card(card)
        self.assertEqual(
            card["execution_certificate"]["tool_name"],
            "mortra.runtime_complement_angle_integral_bound",
        )
        self.assertIn(r"0<I<2", card["answer_tex"])
        self.assertEqual(
            card["execution_certificate"]["proof_program"][0]["input_form"],
            "bare",
        )

    def test_bare_integral_chart_preserves_the_requested_bound(self) -> None:
        status, payload = solve_public_problem(
            r"\int_0^{\pi/2}\{\cos(\cos x+\sin x)+\sin(\cos x+\sin x)\}\,dx<3 を示せ."
        )

        if status == 200:
            tool = payload["cards"][0]["execution_certificate"].get("tool_name")
            self.assertNotEqual(tool, "mortra.runtime_complement_angle_integral_bound")

    def test_integral_chart_does_not_accept_a_different_integrand(self) -> None:
        status, payload = solve_public_problem(
            r"I=\int_0^{\pi/2}\sin(\cos x+\sin x)\,dx とする。0<I<2 を証明せよ。"
        )

        if status == 200:
            tool = payload["cards"][0]["execution_certificate"].get("tool_name")
            self.assertNotEqual(tool, "mortra.runtime_complement_angle_integral_bound")

    def test_bare_japanese_linear_system_projects_requested_expression(self) -> None:
        status, payload = solve_public_problem(
            "実数 x, y が 2x+y=11, x-y=1 を満たすとき、x+3y を求めよ。"
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assertIn("13", card["answer_tex"])
        self.assertTrue(card["verification"]["exact_backend"])
        self.assertTrue(card["verification"]["independent_check"])

    def test_bare_japanese_symmetric_root_expression_uses_vieta_chart(self) -> None:
        status, payload = solve_public_problem(
            "方程式 x^2-3x-7=0 の二つの根を α, β とするとき、α^3+β^3 を求めよ。"
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assertIn("90", card["answer_tex"])
        self.assertIn("symmetric_root_expression", card["family_id"])
        self.assertTrue(card["verification"]["independent_check"])

    def test_bare_linear_projection_recomputes_after_alpha_and_number_changes(self) -> None:
        cases = (
            (
                "実数 p, q が 4p-q=17, p+2q=1 を満たすとき、3p+q を求めよ。",
                r"\frac{92}{9}",
            ),
            ("実数 u, v が 3u+2v=19, u-v=3 を満たすとき、u+4v を求めよ。", "13"),
        )
        for statement, expected in cases:
            with self.subTest(statement=statement):
                status, payload = solve_public_problem(statement)
                self.assertEqual(status, 200)
                self.assertIn(expected, payload["cards"][0]["answer_tex"])

    def test_public_product_accepts_a_current_input_bound_theorem_schema(self) -> None:
        problem = (
            r"実数 $\alpha$ が $\sin\alpha+\cos\alpha=\frac{1}{37}$ を満たしているとする。"
            r"$\sin^n\alpha+\cos^n\alpha>\frac{1}{37}$ となる正の整数 $n$ をすべて求めよ。"
        )

        status, payload = solve_public_problem(problem)

        self.assertEqual(status, 200)
        self.assertIs(payload["uses_external_llm"], False)
        card = payload["cards"][0]
        certificate = card["execution_certificate"]
        self.assertEqual(card["answer_tex"], r"\(\{2, 3, 4, 5, 6, 8, 10, 12\}\)")
        self.assertTrue(certificate["registered_composite_used"])
        self.assertFalse(certificate["registered_completed_route_used"])
        self.assertTrue(certificate["cold_generalization_validated"])
        self.assertEqual(
            certificate["public_release_basis"],
            "current-input-bound verified parameterized theorem replay",
        )

    def test_public_product_solves_tetrahedron_cube_with_explicit_global_theorem_dependency(self) -> None:
        problem = "一辺が1である正四面体に完全に含むことができる立方体の一辺の大きさの最大値を求めよ。"

        status, payload = solve_public_problem(problem)

        self.assertEqual(status, 200)
        self.assertIs(payload["uses_external_llm"], False)
        card = payload["cards"][0]
        self.assertIn(r"\frac{\sqrt{6}}", card["answer_tex"])
        self.assertIn("tikzpicture", card["diagram_tikz"])
        self.assertEqual(card["diagram"]["kind"], "plane")
        self.assertEqual(
            card["visual_explanation"]["steps"][-1]["diagram"]["kind"],
            "plane",
        )
        self.assertIn(
            "section-square",
            {
                shape.get("id")
                for shape in card["visual_explanation"]["steps"][-1]["diagram"][
                    "shapes"
                ]
            },
        )
        self.assertIn("三次元配置の模式図", card["solution_document_tex"])
        self.assertIn("Croft", card["solution_tex"])
        certificate = card["execution_certificate"]
        self.assertTrue(certificate["cold_generalization_validated"])
        self.assertFalse(certificate["registered_completed_route_used"])
        self.assertEqual(
            certificate["witness"]["proof_basis"],
            "published_global_theorem_with_exact_current_input_replay",
        )
        dependency = certificate["witness"]["trusted_theorem_dependencies"][0]
        self.assertEqual(
            dependency["theorem_id"],
            "croft.1980.regular_cube_in_regular_tetrahedron",
        )
        self.assertTrue(dependency["registry_integrity_valid"])
        self.assertEqual(
            certificate["runtime_binding"]["input_sha256"],
            certificate["statement_sha256"],
        )

    def test_public_product_solves_an_unregistered_exact_integral(self) -> None:
        status, payload = solve_public_problem(r"$\int_0^1 x^3\,dx$ を求めよ。")

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assertIn(r"\frac{1}{4}", card["answer_tex"])
        self.assertFalse(card["execution_certificate"]["registered_composite_used"])

    def test_rational_angle_power_identity_exports_its_actual_proof_route(self) -> None:
        problem = (
            r"$0<2p<q$ を満たす互いに素な自然数 $p,q$ と自然数 $n\geqq2$ に対し，"
            r"$\cos^n\frac{p\pi}{q}+\sin^n\frac{p\pi}{q}="
            r"\cos\frac{np\pi}{q}+\sin\frac{np\pi}{q}$ が成り立つ組 $(n,p,q)$ をすべて求めよ．"
        )

        status, payload = solve_public_problem(problem)

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assertNotEqual(
            card["family_id"],
            "solve.symbolic_algebra.symbolic_query_solve_inequality",
        )
        self.assertEqual(card["answer_tex"], r"\(\{(n,p,q)=(2,1,4)\}\)")
        self.assertEqual(len(card["proof_roadmap"]), 6)
        self.assertEqual(len(card["proof_obligations"]), 8)
        self.assertIn("cyclotomic.conjugate.uniform_norm_bound.v1", card["morphism_chain"])
        document = card["solution_document_tex"]
        self.assertIn("一手ずつ見る図解", document)
        self.assertIn("使った射と役割", document)
        self.assertIn("証明義務", document)
        self.assertIn("O8", document)
        self.assertIn(card["verification"]["certificate_sha256"], document)

    def test_rational_angle_power_identity_accepts_ascii_and_alpha_renaming(self) -> None:
        problem = (
            "0<2a<b を満たす互いに素な自然数 a,b と自然数 m>=2 に対し、"
            "cos^m(a*pi/b)+sin^m(a*pi/b)=cos(m*a*pi/b)+sin(m*a*pi/b) "
            "が成り立つ組 (m,a,b) をすべて求めよ。"
        )

        status, payload = solve_public_problem(problem)

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assertEqual(card["answer_tex"], r"\(\{(m,a,b)=(2,1,4)\}\)")
        certificate = card["execution_certificate"]
        self.assertEqual(
            certificate["query_objects"]["variable_binding"],
            {"power": "m", "numerator": "a", "denominator": "b"},
        )
        self.assertTrue(certificate["cold_generalization_validated"])
        self.assertIn("標準記号", card["solution_tex"])

    def test_rational_angle_power_identity_rejects_inconsistent_binders(self) -> None:
        problem = (
            "0<2a<b を満たす互いに素な自然数 a,b と自然数 m>=2 に対し、"
            "cos^m(a*pi/b)+sin^m(a*pi/b)=cos(k*a*pi/b)+sin(k*a*pi/b) "
            "が成り立つ組 (m,a,b) をすべて求めよ。"
        )

        status, payload = solve_public_problem(problem)

        self.assertEqual(status, 422)
        self.assertEqual(payload["generated"], 0)

    def test_rational_angle_reciprocal_power_is_solved_by_cyclotomic_trace(self) -> None:
        problem = (
            r"$\dfrac{\theta}{\pi}$ が有理数であるとする。"
            r"$\tan^n\theta+\dfrac{1}{\tan^n\theta}=2^p$ を満たす"
            r"自然数 $n$、素数 $p$、実数 $\theta$ をすべて求めよ。"
        )

        status, payload = solve_problem(problem)

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assertIn(r"n=1", card["answer_tex"])
        self.assertIn(r"\frac{\pi}{12}", card["answer_tex"])
        self.assertIn(r"\varphi(m)\le4", card["solution_tex"])
        self.assertEqual(
            card["family_id"],
            "solve.structural_theorem."
            "structural_theorem_rational_angle_reciprocal_power_of_two",
        )
        self.assertTrue(card["execution_certificate"]["verified"])
        self.assertEqual(
            card["execution_certificate"]["witness"]["proof_kernel_count"],
            4,
        )

    def test_quadratic_equation_is_solved_and_verified(self) -> None:
        status, payload = solve_problem(r"$x^2-5x+6=0$ を解け。")

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assertEqual(card["answer_tex"], r"\(\left\{2,\;3\right\}\)")
        self.assertTrue(card["verification"]["exact_backend"])
        self.assertEqual(card["artifact_version"], 4)
        self.assertEqual(card["field_labels"], ["代数"])
        self.assertTrue(card["publication_contract"]["exact_answer_required"])
        self.assertTrue(card["publication_contract"]["decimal_only_final_answer_forbidden"])
        self.assertTrue(card["publication_contract"]["diagram_for_every_visual_step"])
        self.assertTrue(card["publication_contract"]["commentary_required"])
        self.assertGreaterEqual(len(card["visual_explanation"]["steps"]), 1)
        self.assertTrue(
            all(
                step["diagram"]["kind"] == "plane"
                for step in card["visual_explanation"]["steps"]
            )
        )
        visual_titles = [step["title"] for step in card["visual_explanation"]["steps"]]
        self.assertIn("数式を正確に読み取る", visual_titles)
        self.assertIn("方程式を厳密に解く", visual_titles)
        self.assertNotIn("SymPyExpression", visual_titles)
        self.assertEqual(
            card["visual_explanation"]["steps"][-1]["diagram"],
            card["diagram"],
        )
        self.assertEqual(card["diagram"]["kind"], "plane")
        self.assertEqual(card["diagram"]["title"], "方程式の零点")
        self.assertGreater(len(card["diagram"]["shapes"]), 1)
        self.assertIn("因数分解", card["solution_tex"])
        self.assertIn(r"\begin{tikzpicture}", card["diagram_tikz"])
        self.assertIn(r"\documentclass[uplatex,dvipdfmx,11pt]{jsarticle}", card["solution_document_tex"])
        self.assertIn(card["answer_tex"], card["solution_document_tex"])
        self.assertIn("分野：代数", card["solution_document_tex"])
        self.assertIn(r"\section*{講評}", card["solution_document_tex"])
        self.assertRegex(card["verification"]["certificate_sha256"], r"^[0-9a-f]{64}$")
        self.assertIn(card["verification"]["certificate_sha256"], card["solution_document_tex"])
        self.assertEqual(card["proof_trace"], payload["trace"])

    def test_regular_polygon_roll_exports_exact_stepwise_visual_solution(self) -> None:
        problem = (
            "正の整数 n>=3 に対し，外接円の半径が1である二つの正n角形を考える。"
            "固定する正n角形はすべて同じ中心Oと同じ頂点P_1を共有するように配置する。"
            "一方を固定し，他方を，一辺を共有する状態から，接点が常に両者の頂点となるように，"
            "固定した正n角形の外側を滑ることなく一周させる。"
            "動く正n角形が通過する部分をD_nとする。D_3,D_4,...,D_nの共通部分の面積を"
            "S_nとするとき，lim S_nを求めよ。"
        )

        status, payload = solve_public_problem(problem)

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        visual = card["visual_explanation"]
        self.assertTrue(visual["composition_verified"])
        self.assertEqual(len(visual["steps"]), 9)
        self.assertTrue(all(step.get("diagram") for step in visual["steps"]))
        self.assertEqual(card["publication_contract"]["visual_step_count"], 9)
        self.assertIn(r"\mathcal A", card["answer_tex"])
        self.assertNotIn("16.082", card["answer_tex"])
        self.assertIn("一手ずつ見る図解", card["solution_document_tex"])
        self.assertIn("arc[start angle", card["solution_document_tex"])
        for index in range(3, 8):
            self.assertIn(f"n={index}", card["solution_document_tex"])

    def test_regular_polygon_roll_does_not_infer_missing_alignment(self) -> None:
        problem = (
            "正の整数 n>=3 に対し、外接円の半径が1である二つの正n角形を考える。"
            "一方を固定し、他方を一辺を共有する状態から、接点が常に両者の頂点となるように、"
            "固定した正n角形の外側を滑ることなく一周させる。"
            "動く正n角形が通過する部分をD_nとする。D_3,D_4,...,D_nの共通部分の面積を"
            "S_nとするとき、lim S_nを求め、運動と通過領域を図示せよ。"
        )

        status, payload = solve_public_problem(problem)

        self.assertEqual(status, 422)
        self.assertEqual(payload["generated"], 0)

    def test_solution_tex_normalizes_extracted_list_environments(self) -> None:
        status, payload = solve_problem(
            r"\begin{enumerate}\item[(1)] $x^2-5x+6=0$ を解け。\end{enumerate}"
        )

        self.assertEqual(status, 200)
        document = payload["cards"][0]["solution_document_tex"]
        self.assertNotIn(r"\begin{enumerate}", document)
        self.assertIn(r"\textbf{(1)}", document)

    def test_three_real_cubic_roots_use_compact_trigonometric_form(self) -> None:
        with patch("api.solve.sp.solve", side_effect=AssertionError("cubic chart must bypass sp.solve")):
            status, payload = solve_problem(r"$x^3-2026x^2-2029x-1=0$ を解け。")

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        answer = card["answer_tex"]
        self.assertIn(r"\cos", answer)
        self.assertNotIn(r"\sqrt{3} i", answer)
        self.assertIn("三倍角公式", card["solution_tex"])
        self.assertIn("triple-angle identity", card["verification"]["method"])
        self.assertEqual(len(card["verification"]["checks"]), 3)

    def test_three_real_cubic_chart_generalizes_beyond_source_problem(self) -> None:
        with patch("api.solve.sp.solve", side_effect=AssertionError("cubic chart must bypass sp.solve")):
            status, payload = solve_problem(r"$x^3-3x+1=0$ を解け。")

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assertIn(r"\arccos", card["answer_tex"])
        self.assertEqual(card["diagram"]["title"], "三次方程式の3実根")

    def test_three_real_cubic_derivation_has_a_well_formed_square_root(self) -> None:
        status, payload = solve_problem(r"$x^3-7x+3=0$ を解け。")

        self.assertEqual(status, 200)
        solution = payload["cards"][0]["solution_tex"]
        self.assertNotIn(r"\sqrt{--", solution)
        self.assertIn(r"\sqrt{\frac{7}{3}}", solution)

    def test_definite_integral_uses_exact_backend(self) -> None:
        status, payload = solve_problem(r"$\int_0^1 x^2\,dx$ を求めよ。")

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assertEqual(card["answer_tex"], r"\(\frac{1}{3}\)")
        self.assertEqual(card["diagram"]["kind"], "plane")
        self.assertIn("微積分の基本定理", card["solution_tex"])
        self.assertEqual(card["field_labels"], ["解析"])

    def test_probability_statistics_output_has_admissions_commentary(self) -> None:
        from math_os_prototype.solution_artifact import attach_solution_artifact

        card = attach_solution_artifact(
            {
                "statement_tex": "二つの確率変数の相関係数を求めよ。",
                "answer_tex": r"\(\rho=\frac14\)",
                "solution_tex": "期待値、分散、共分散を順に求める。",
                "family_id": "solve.probability.correlation",
                "domain": "probability",
                "morphism_chain": ["ProblemText", "TypedSemanticIR", "VerifiedAnswer"],
                "verification": {"method": "exact finite sum"},
            },
            ["有限和を厳密計算", "定義へ代入して検証"],
        )

        self.assertEqual(card["field_labels"], ["確率・統計"])
        self.assertIn("新課程の確率・統計", card["editorial"]["admissions_context"])
        self.assertIn("相関係数", card["solution_document_tex"])

    def test_verified_visual_program_compiles_for_an_unrelated_geometry_proof(self) -> None:
        from math_os_prototype.solution_artifact import attach_solution_artifact

        initial = {
            "version": 1,
            "kind": "plane",
            "title": "三角形ABC",
            "caption": "初期配置",
            "viewport": {"xMin": -1, "xMax": 5, "yMin": -1, "yMax": 4},
            "axes": False,
            "shapes": [
                {
                    "id": "triangle",
                    "kind": "polyline",
                    "points": [{"x": 0, "y": 0}, {"x": 4, "y": 0}, {"x": 1, "y": 3}],
                    "closed": True,
                    "tone": "secondary",
                },
                {"id": "A", "kind": "point", "point": {"x": 0, "y": 0}, "label": "A"},
                {"id": "B", "kind": "point", "point": {"x": 4, "y": 0}, "label": "B"},
                {"id": "C", "kind": "point", "point": {"x": 1, "y": 3}, "label": "C"},
            ],
        }
        roadmap = [
            {
                "morphism_id": "geometry.midpoint.construct.v1",
                "label_ja": "中点を構成",
                "source_ja": "三角形ABC",
                "target_ja": "中点Mを含む図",
                "role_ja": "辺BCの中点Mを図へ加える。",
                "visual_actions": [
                    {
                        "op": "add",
                        "shape": {
                            "id": "M",
                            "kind": "point",
                            "point": {"x": 2.5, "y": 1.5},
                            "label": "M",
                            "tone": "accent",
                        },
                    }
                ],
            },
            {
                "morphism_id": "geometry.median.focus.v1",
                "label_ja": "中線へ着目",
                "source_ja": "中点Mを含む図",
                "target_ja": "中線AMの拡大図",
                "role_ja": "必要な部分へ拡大し、中線AMを強調する。",
                "visual_actions": [
                    {
                        "op": "add",
                        "shape": {
                            "id": "AM",
                            "kind": "polyline",
                            "points": [{"x": 0, "y": 0}, {"x": 2.5, "y": 1.5}],
                            "tone": "primary",
                        },
                    },
                    {"op": "focus", "shape_ids": ["A", "M", "AM"], "margin": 0.25},
                ],
            },
        ]
        card = attach_solution_artifact(
            {
                "statement_tex": "三角形ABCで辺BCの中点をMとする。",
                "answer_tex": r"\(AM\text{ は中線}\)",
                "solution_tex": "中点を構成し、AとMを結ぶ。",
                "family_id": "geometry.midpoint.median",
                "domain": "geometry",
                "morphism_chain": ["ProblemText", "TypedSemanticIR", "VerifiedAnswer"],
                "verification": {"method": "exact affine midpoint check"},
                "visual_initial_diagram": initial,
                "diagram": initial,
                "execution_certificate": {
                    "witness": {"shared_chart": {"proof_roadmap": roadmap}}
                },
            },
            ["M=(B+C)/2 を厳密検証"],
        )

        self.assertTrue(card["publication_contract"]["visual_program_compiled"])
        self.assertEqual(card["publication_contract"]["visual_step_count"], 2)
        self.assertEqual(len(card["visual_explanation"]["steps"][0]["diagram"]["shapes"]), 5)
        self.assertEqual(card["visual_explanation"]["steps"][1]["diagram"], card["diagram"])
        self.assertIn("中線へ着目", card["solution_document_tex"])

    def test_limit_uses_exact_backend(self) -> None:
        status, payload = solve_problem(r"$\lim_{x\to0}\frac{\sin x}{x}$ を求めよ。")

        self.assertEqual(status, 200)
        self.assertEqual(payload["cards"][0]["answer_tex"], r"\(1\)")

    def test_unevaluated_limit_is_not_certified(self) -> None:
        status, payload = solve_problem(r"$\lim_{n\to\infty}(S_n-T_n)$ を求めよ。")

        self.assertEqual(status, 422)
        self.assertEqual(payload["generated"], 0)
        self.assertEqual(
            payload["diagnostics"]["schema"],
            "mortra.single-problem-failure.v1",
        )
        self.assertTrue(payload["diagnostics"]["operations"])

    def test_correlation_limit_is_synthesized_in_cold_mode(self) -> None:
        problem = (
            r"1から$n$までのカードから2枚を引く。相加平均と相乗平均を"
            r"$X_n,Y_n$ とし、その相関係数を $\rho_n$ とする。"
            r"$\lim_{n\to\infty}\rho_n$ を求めよ。"
        )

        status, payload = solve_problem(problem, allow_theorem_kernels=False)

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assertEqual(card["answer_tex"], r"\(\frac{8 \sqrt{102}}{85}\)")
        certificate = card["execution_certificate"]
        self.assertEqual(certificate["capability_origin"], "synthesized_proof_program")
        self.assertFalse(certificate["registered_composite_used"])
        self.assertEqual(certificate["composite_cache_role"], "not_consulted")
        self.assertEqual(
            certificate["witness"]["generated_moment_obligations"],
            ["E_X", "E_Y", "E_X2", "E_Y2", "E_XY"],
        )
        rules = [step["rule"] for step in certificate["proof_program"]]
        self.assertIn("correlation_dependency_expansion", rules)
        self.assertIn("independent_double_integral_replay", rules)

    def test_correlation_program_recomputes_different_observables(self) -> None:
        problem = (
            r"1から$N$までの整数が書かれたカードが1枚ずつある。2枚を同時に引き、"
            r"その値の和を $S_N$、積を $P_N$ とする。$S_N,P_N$ の相関係数を $c_N$ とする。"
            r"$\lim_{N\to\infty}c_N$ を求めよ。"
        )

        status, payload = solve_problem(problem, allow_theorem_kernels=False)

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assertEqual(card["answer_tex"], r"\(\frac{\sqrt{42}}{7}\)")
        certificate = card["execution_certificate"]
        self.assertFalse(certificate["registered_composite_used"])
        self.assertEqual(
            certificate["witness"]["observable_expressions"],
            {"S": "u + v", "P": "u*v"},
        )

    def test_triangle_recurrence_floor_limit_is_synthesized_in_cold_mode(self) -> None:
        problem = r"""
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

        status, payload = solve_problem(problem, allow_theorem_kernels=False)

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assertEqual(card["answer_tex"], r"\(2\)")
        certificate = card["execution_certificate"]
        self.assertEqual(certificate["capability_origin"], "synthesized_proof_program")
        self.assertFalse(certificate["registered_composite_used"])
        self.assertEqual(certificate["composite_cache_role"], "not_consulted")
        rules = [step["rule"] for step in certificate["proof_program"]]
        self.assertIn("companion_matrix_lift", rules)
        self.assertIn("alternating_subdominant_endpoint_exclusion", rules)
        self.assertIn("eventual_floor_stability", rules)

    def test_discrete_profile_minimum_is_discovered_in_cold_mode(self) -> None:
        problem = r"""
        自然数 \(n\geq4\) に対し，
        \[
        a_n=(\sin\frac{\pi}{n}+\cos\frac{\pi}{n})^{
        \frac{1}{\sin\frac{\pi}{n}+\cos\frac{\pi}{n}-1}
        +\sin\frac{\pi}{n}+\cos\frac{\pi}{n}-1}
        \]
        と定める。数列 \(\{a_n\}\) の最小値を求め，さらに
        \[\lim_{n\to\infty}n(e-a_n)\]
        を求めよ。
        """

        status, payload = solve_problem(problem, allow_theorem_kernels=False)

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        certificate = card["execution_certificate"]
        self.assertEqual(certificate["capability_origin"], "synthesized_proof_program")
        self.assertFalse(certificate["registered_composite_used"])
        self.assertEqual(certificate["witness"]["selected_index"], 12)
        self.assertEqual(certificate["witness"]["scaled_limit"], "E*pi/2")
        rules = [step["rule"] for step in certificate["proof_program"]]
        self.assertIn("runtime_derivative_root_search", rules)
        self.assertIn("exact_candidate_interval_comparison", rules)

    def test_limit_does_not_treat_an_unresolved_geometric_distance_as_a_scalar_product(self) -> None:
        problem = (
            r"原点を $O$，曲線 $P:y=x^2$ とする。$P$ を角 $\theta$ 回転した曲線との"
            r"交点を $R$ とする。$\lim_{\theta\to0}\theta^2\cdot OR$ を求めよ。"
        )

        status, payload = solve_problem(problem, allow_theorem_kernels=False)

        self.assertEqual(status, 422)
        self.assertEqual(payload["generated"], 0)

    def test_curated_structural_theorem_is_not_used_in_cold_mode(self) -> None:
        status, payload = solve_problem(
            "自然数 1 から $n$ までの和が、$n$ 以下の素数の積と等しいとき、$n$を求めよ。",
            allow_theorem_kernels=False,
        )

        self.assertEqual(status, 422)
        self.assertEqual(payload["generated"], 0)
        self.assertEqual(payload["evaluation_mode"], "cold")

    def test_registered_parameterized_morphism_remains_available_for_research_replay(self) -> None:
        problem = (
            r"実数 $\alpha$ が $\sin\alpha+\cos\alpha=\frac{1}{37}$ を満たしているとする。"
            r"$\sin^n\alpha+\cos^n\alpha>\frac{1}{37}$ となる正の整数 $n$ をすべて求めよ。"
        )

        status, payload = solve_problem(problem, allow_theorem_kernels=True)

        self.assertEqual(status, 200)
        self.assertEqual(payload["evaluation_mode"], "portfolio")
        card = payload["cards"][0]
        self.assertEqual(
            card["family_id"],
            "solve.structural_theorem.structural_theorem_trigonometric_power_sum_threshold",
        )
        contract = card["execution_certificate"]["cold_generalization_contract"]
        self.assertTrue(card["execution_certificate"]["registered_composite_used"])
        self.assertEqual(
            contract["required_object_keys"],
            ["sum_numerator", "sum_denominator"],
        )
        self.assertNotIn("expected_answer", card["execution_certificate"])

    def test_unregistered_exponential_inequality_synthesizes_a_proof_program(self) -> None:
        status, payload = solve_problem(
            r"$2^{\sqrt2}<e$を示せ。",
            allow_theorem_kernels=False,
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        certificate = card["execution_certificate"]
        self.assertEqual(certificate["capability_origin"], "synthesized_proof_program")
        self.assertGreater(certificate["search_statistics"]["hypotheses_evaluated"], 1)
        self.assertIn(
            "exponential_taylor_lower",
            [step["rule"] for step in certificate["proof_program"]],
        )
        self.assertNotIn("problem_id", certificate)
        self.assertNotIn("expected_answer", certificate)

    def test_same_primitive_search_recomposes_for_unregistered_constants(self) -> None:
        for problem in (
            r"$4^{\frac13}<e$を示せ。",
            r"$e<1+\sqrt3$を示せ。",
        ):
            with self.subTest(problem=problem):
                status, payload = solve_problem(
                    problem,
                    allow_theorem_kernels=False,
                )
                self.assertEqual(status, 200)
                certificate = payload["cards"][0]["execution_certificate"]
                self.assertEqual(
                    certificate["capability_origin"],
                    "synthesized_proof_program",
                )

    def test_finite_orbit_problem_is_synthesized_before_multipart_decomposition(self) -> None:
        problem = r"""
        数列 \(\{a_n\}\) を
        \[
        a_1=a_2=\frac{\pi}{4},\qquad a_{n+2}=a_{n+1}+a_n
        \]
        によって定める。
        \begin{enumerate}
        \item \(\displaystyle\lim_{N\to\infty}\frac1N\sum_{k=1}^{N}\sin a_k\) を求めよ。
        \item \(P_0(x)=1\), \(P_1(x)=x\),
        \(P_{m+2}(x)=2xP_{m+1}(x)-P_m(x)\) と定める。
        \(P_m(\cos x)=\cos mx\) を示せ。
        \item \(\displaystyle\lim_{N\to\infty}\frac1N\sum_{k=1}^{N}P_m(\sin a_k)\)
        を \(m\) に応じて求めよ。
        \end{enumerate}
        """

        status, payload = solve_problem(problem, allow_theorem_kernels=False)

        self.assertEqual(status, 200)
        self.assertEqual(payload["evaluation_mode"], "cold")
        card = payload["cards"][0]
        certificate = card["execution_certificate"]
        self.assertEqual(certificate["capability_origin"], "synthesized_proof_program")
        self.assertFalse(certificate["registered_composite_used"])
        self.assertEqual(certificate["composite_cache_role"], "not_consulted")
        self.assertEqual(certificate["witness"]["modulus"], 8)
        self.assertEqual(certificate["witness"]["state_period"], 12)
        self.assertIn(r"\frac{1}{6}", card["answer_tex"])
        self.assertIn(r"m\equiv 4\pmod{8}", card["answer_tex"])
        rules = [step["rule"] for step in certificate["proof_program"]]
        self.assertIn("modular_matrix_replay", rules)
        self.assertIn("exact_obligation_replay", rules)

    def test_finite_orbit_public_solver_recomputes_changed_symbols_and_coefficients(self) -> None:
        problem = r"""
        \(b_2=\frac{\pi}{6},\ b_3=\frac{\pi}{3}\) とし、
        \(b_{j+2}=2b_{j+1}-b_j\) で数列を定める。
        \(\displaystyle\lim_{N\to\infty}\frac1N\sum_{r=2}^{N}\cos b_r\) を求めよ。
        """

        status, payload = solve_problem(problem, allow_theorem_kernels=False)

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        certificate = card["execution_certificate"]
        self.assertEqual(card["answer_tex"], r"\(0\)")
        self.assertEqual(certificate["witness"]["modulus"], 12)
        recurrence = certificate["witness"]["input_ir"]["recurrence"]
        self.assertEqual(recurrence["sequence_symbol"], "b")
        self.assertEqual(recurrence["coefficients"], (2, -1))
        self.assertFalse(certificate["registered_composite_used"])

    def test_false_exponential_inequality_is_not_published_without_a_certificate(self) -> None:
        status, payload = solve_problem(
            r"$8^{\frac12}<e$を示せ。",
            allow_theorem_kernels=False,
        )

        self.assertEqual(status, 422)
        self.assertEqual(payload["generated"], 0)
        self.assertIn("証明書", payload["error"])

    def test_trigonometric_geometric_progression_is_elaborated_from_its_relation(self) -> None:
        status, payload = solve_problem(
            r"$\sin\theta,$ $\cos\theta,$ $\tan\theta$がこの順で等比数列をなすような"
            r"$\cos\theta$を求めよ。",
            allow_theorem_kernels=False,
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assertEqual(card["family_id"], "solve.exact.typed_relation_elimination")
        self.assertIn(r"c^{3} + c^{2} - 1", card["solution_tex"])
        self.assertIn("resultant elimination", card["verification"]["method"])

    def test_trigonometric_geometric_progression_is_alpha_renamable(self) -> None:
        status, payload = solve_problem(
            r"$\sin\phi,$ $\cos\phi,$ $\tan\phi$がこの順で等比数列をなすような"
            r"$\cos\phi$を求めよ。",
            allow_theorem_kernels=False,
        )

        self.assertEqual(status, 200)
        self.assertEqual(payload["cards"][0]["family_id"], "solve.exact.typed_relation_elimination")

    def test_public_default_uses_theorem_portfolio(self) -> None:
        status, payload = solve_problem(
            "自然数 1 から $n$ までの和が、$n$ 以下の素数の積と等しいとき、$n$を求めよ。"
        )

        self.assertEqual(status, 200)
        self.assertEqual(payload["evaluation_mode"], "portfolio")
        self.assertTrue(payload["cards"][0]["verification"]["exact_backend"])

    def test_derivative_uses_defined_expression(self) -> None:
        status, payload = solve_problem(r"$f(x)=x^3-2x$ の導関数を求めよ。")

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assertEqual(card["answer_tex"], r"\(3 x^{2} - 2\)")
        self.assertEqual(card["diagram"]["kind"], "plane")
        self.assertEqual(card["diagram"]["title"], "関数と導関数")
        self.assertIn("各項を微分", card["solution_tex"])

    def test_unverified_problem_is_not_given_a_fabricated_answer(self) -> None:
        status, payload = solve_problem("任意の未定義対象について新しい定理を証明せよ。")

        self.assertEqual(status, 422)
        self.assertEqual(payload["generated"], 0)
        self.assertNotIn("cards", payload)

    def test_fixed_parameter_geometry_answer_is_not_published_as_generation(self) -> None:
        problem = (
            r"平面上に一辺$\sqrt3$の正方形を固定する."
            r"一辺$\sqrt2+\sqrt6$の正三角形を,この正方形を含むように自由に動かすとき,"
            r"正三角形の通過領域の面積を求めよ."
        )
        status, payload = solve_problem(problem)

        self.assertEqual(status, 422)
        self.assertEqual(payload["generated"], 0)
        self.assertNotIn("cards", payload)

    def test_partial_subexpression_does_not_verify_the_whole_problem(self) -> None:
        problem = (
            r"$\alpha=\cos\frac{2\pi}{11}$を根に持つ最小多項式を$f(x)$とする。"
            r"$S=\frac{1}{1-x}$で変換した不動点反復の収束次数と誤差定数を求めよ。"
        )
        status, payload = solve_problem(problem)

        self.assertEqual(status, 422)
        self.assertEqual(payload["generated"], 0)

    def test_numbered_obligations_require_every_part_to_be_certified(self) -> None:
        problem = (
            r"\begin{enumerate}"
            r"\item[(1)] $\int_0^1 x\,dx$ を求めよ。"
            r"\item[(2)] $f(x)=x^3-2x$ の導関数を求めよ。"
            r"\end{enumerate}"
        )

        status, payload = solve_problem(problem, allow_theorem_kernels=False)

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assertEqual(card["family_id"], "solve.composite.all_obligations")
        self.assertEqual(len(card["proof_obligations"]), 2)
        self.assertTrue(all(item["status"] == "verified" for item in card["proof_obligations"]))
        self.assertIn(r"\frac{1}{2}", card["answer_tex"])
        self.assertIn(r"3 x^{2} - 2", card["answer_tex"])

    def test_one_solved_part_does_not_certify_a_two_part_problem(self) -> None:
        problem = (
            r"\begin{enumerate}"
            r"\item[(1)] $\int_0^1 x\,dx$ を求めよ。"
            r"\item[(2)] 任意の未知の位相空間の分類を証明せよ。"
            r"\end{enumerate}"
        )

        status, payload = solve_problem(problem, allow_theorem_kernels=False)

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

    def test_trigonometric_power_sum_problem_uses_transition_recurrence(self) -> None:
        status, payload = solve_problem(
            r"実数 $\theta$ が $\sin\theta+\cos\theta=\frac{1}{2027}$ を満たしているとする。"
            r"$\sin^n\theta+\cos^n\theta>\frac{1}{2027}$ となる正の整数 $n$ をすべて求めよ。"
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assertIn(r"22", card["answer_tex"])
        self.assertIn("遷移行列", card["solution_tex"])
        self.assertEqual(card["family_id"], "solve.structural_theorem.structural_theorem_trigonometric_power_sum_threshold")

    def test_binomial_exponential_limit_uses_edge_bulk_decomposition(self) -> None:
        status, payload = solve_problem(
            r"$\lim_{n\to\infty}\left\{\sum_{k=0}^{n}"
            r"\left(1+\frac{1}{\binom{n}{k}}\right)^{\binom{n}{k}}-en\right\}$を求めよ。"
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assertIn("4 - e", card["answer_tex"])
        self.assertIn("逆二項係数和", card["solution_tex"])
        self.assertEqual(card["family_id"], "solve.structural_theorem.structural_theorem_binomial_exponential_edge_limit")

    def test_exponential_tangent_inequality_uses_convex_endpoint_proof(self) -> None:
        status, payload = solve_problem(
            r"$x>1$ において、$\tan\left(e\left(1-\frac{1}{x}\right)^x\right)"
            r"+\frac{1}{x}<\frac{\pi}{2}$ を示せ。"
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assertIn("成立", card["answer_tex"])
        self.assertIn("凸", card["solution_tex"])
        self.assertIn("Taylor", card["solution_tex"])

    def test_mobius_polynomial_fixed_point_returns_both_parts(self) -> None:
        status, payload = solve_problem(
            r"$\alpha=\cos\frac{2\pi}{11}$ の最小多項式を "
            r"$f(x)=32x^5+16x^4-32x^3-12x^2+6x+1$ とする。"
            r"$S=\frac{1}{1-x}$ により $S^{*}=g(S^{*})$ とし、"
            r"$g(S)=C_{0}+\frac{C_{1}}S+\frac{C_{2}}{S^2}$ の形に表す。"
            r"$C_{0}$ と $k=|g'(S^{*})|$ を求めよ。"
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assertIn(r"C_{0}", card["answer_tex"])
        self.assertIn(r"\cos{\left(\frac{\pi}{11} \right)}", card["answer_tex"])
        self.assertIn("商環", card["solution_tex"])
        self.assertEqual(
            card["family_id"],
            "solve.structural_theorem.structural_theorem_mobius_polynomial_fixed_point",
        )

    def test_permuted_trigonometric_cubic_returns_proof_and_maximum(self) -> None:
        status, payload = solve_problem(
            r"$0<\theta<\frac{\pi}{2}$ とし、$(a,b,c)$ は"
            r"$(\sin\theta,\cos\theta,\tan\theta)$の置換とする。"
            r"$x^3+ax^2+bx+c=0$が虚数解をもつことを示せ。"
            r"三解が複素平面上で正三角形の頂点をなすとき、その面積の最大値を求めよ。"
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assertIn(r"\max\Delta", card["answer_tex"])
        self.assertIn("Newton", card["solution_tex"])
        self.assertIn("減次", card["solution_tex"])
        self.assertEqual(
            card["family_id"],
            "solve.structural_theorem.structural_theorem_permuted_trigonometric_cubic",
        )

    def test_rotated_parabola_volume_reports_both_one_sided_limits(self) -> None:
        status, payload = solve_problem(
            r"曲線$P:y=x^2$を原点中心に角$\theta$だけ回転した曲線をQとする。"
            r"PとQで囲まれた領域をx軸周りに回転した体積を$V(\theta)$とする。"
            r"$\lim_{\theta\to0}\theta^5V(\theta)$を求めよ。"
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assertIn("存在しない", card["answer_tex"])
        self.assertIn(r"\frac{128 \pi}{15}", card["answer_tex"])
        self.assertIn("吹き上げ", card["solution_tex"])
        self.assertIn("左右", card["solution_tex"])

    def test_prime_two_side_triangle_radii_problem_returns_all_triangles(self) -> None:
        status, payload = solve_problem(
            "二辺の長さが素数で、外接円半径と内接円半径の積も素数となる"
            "整数三角形をすべて求めよ。"
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assertIn("(5,7,8)", card["answer_tex"])
        self.assertIn("(7,8,13)", card["answer_tex"])
        self.assertIn("Rr", card["solution_tex"])
        self.assertIn("合同", card["solution_tex"])
        self.assertEqual(
            card["family_id"],
            "solve.structural_theorem.structural_theorem_prime_two_side_triangle_radii_product",
        )

    def test_integer_triangle_mean_radii_prime_chain_returns_357(self) -> None:
        status, payload = solve_problem(
            r"整数三角形の三辺の相加平均を$A$、相乗平均を$G$、"
            r"外接円半径を$R$、内接円半径を$r$とする。"
            r"$2\sqrt{3}r\le G\le A\le\sqrt{3}R$を示し、"
            r"$2\sqrt{3}r,A,\sqrt{3}R$が相異なる素数となる三辺を求めよ。"
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assertIn("(3,5,7)", card["answer_tex"])
        self.assertIn("Heron", card["solution_tex"])
        self.assertIn("等差", card["solution_tex"])
        self.assertEqual(
            card["family_id"],
            "solve.structural_theorem.structural_theorem_integer_triangle_mean_radii_prime_chain",
        )

    def test_triangle_angle_product_region_returns_exact_area(self) -> None:
        status, payload = solve_problem(
            r"A,B,Cはある三角形の角である。点 "
            r"$(\cos A\cos B\cos C,\sin A\sin B\sin C)$ "
            r"の通過する領域の面積を求めよ。"
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assertIn(r"\dfrac{\pi}{16}", card["answer_tex"])
        self.assertIn("Jacobian", card["solution_tex"])
        self.assertIn("cot A,cot B,cot C", card["solution_tex"])
        self.assertEqual(
            card["family_id"],
            "solve.structural_theorem.structural_theorem_triangle_angle_product_region_area",
        )

    def test_triangle_sine_exponential_ratio_returns_the_sharp_constant(self) -> None:
        status, payload = solve_problem(
            r"任意の三角形ABCに対して"
            r"\frac{(1+\sin A)^{\frac{1}{\sin A}+\frac12}"
            r"+(1+\sin B)^{\frac{1}{\sin B}+\frac12}"
            r"+(1+\sin C)^{\frac{1}{\sin C}+\frac12}-3e}"
            r"{\sin A\sin B+\sin B\sin C+\sin C\sin A}<M"
            r"が成り立つ実数Mの最小値を求めよ。"
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assertIn(r"\dfrac{e}{6}", card["answer_tex"])
        self.assertIn("log(1+x)>", card["solution_tex"])
        self.assertIn("x=u+v", card["solution_tex"])
        self.assertEqual(
            card["family_id"],
            "solve.structural_theorem.structural_theorem_triangle_sine_exponential_ratio_supremum",
        )

    def test_cayley_exponential_integral_problem_returns_three_verified_comparisons(self) -> None:
        status, payload = solve_problem(
            r"0<x<2とし、\mathrm{Ei}(x)=\lim_{s\to\infty}"
            r"\int_x^s\frac{e^{-t}}{t}\,dtと定める。"
            r"(1)e^xと\dfrac{2+x}{2-x}を比較せよ。"
            r"(2)\ln\frac{2+x}{2-x}と\frac{2+\ln x}{2-\ln x}を比較せよ。"
            r"(3)\mathrm{Ei}(2)と\dfrac{3}{8e^2}を比較せよ。"
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assertIn(r"e^x<\dfrac{2+x}{2-x}", card["answer_tex"])
        self.assertIn(r"\mathrm{Ei}(2)<\dfrac{3}{8e^2}", card["answer_tex"])
        self.assertIn(r"H'(u)=\frac{u^2}{4-u^2}", card["solution_tex"])
        self.assertIn(r"\frac{202027}{3120000}", card["solution_tex"])
        self.assertEqual(
            card["family_id"],
            "solve.structural_theorem.structural_theorem_cayley_exponential_integral_comparisons",
        )

    def test_complex_argument_problem_returns_condition_and_rational_pi_bounds(self) -> None:
        status, payload = solve_problem(
            r"正の整数nに対し、複素数平面上の点 $z_n=n+i$ を考える。"
            r"整数列 $1\le j_1\le\cdots\le j_m\le n$ に対して"
            r"$\tan(\arg z_{j_1}+\cdots+\arg z_{j_m})=1$ となる条件を求め、"
            r"それを用いて $3.141<\pi<3.142$ を示せ。"
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assertIn(r"\sum_{q\ge0}", card["answer_tex"])
        self.assertIn(r"3.141<\pi<3.142", card["answer_tex"])
        self.assertIn("(2+i)(3+i)=5+5i", card["solution_tex"])
        self.assertIn("21940173935/6983843328", card["solution_tex"])
        self.assertEqual(
            card["family_id"],
            "solve.structural_theorem.structural_theorem_complex_argument_arctangent_certificate",
        )

    def test_complex_power_problem_returns_global_interval_certificate(self) -> None:
        status, payload = solve_problem(
            r"(1) 自然数nにおいて、\operatorname{Im}"
            r"\left(1+\frac{i}{n}\right)^nが最大となるnを全て求めよ。"
            r"(2) 正の実数xにおいて、\operatorname{Im}"
            r"\left(1+\frac{i}{x}\right)^x<\frac{e}{2^{\sqrt2}}を示せ。"
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assertIn(r"n=1,2", card["answer_tex"])
        self.assertIn(r"\frac{e}{2^{\sqrt2}}", card["answer_tex"])
        self.assertIn("440個の有理区間", card["solution_tex"])
        self.assertIn("23581/34020", card["solution_tex"])
        self.assertEqual(
            card["family_id"],
            "solve.structural_theorem.structural_theorem_complex_binomial_imaginary_extremum",
        )

    def test_parametric_curve_problem_returns_a_verified_area_bound(self) -> None:
        status, payload = solve_problem(
            r"実数 $t$ が $-\pi\leq t\leq\pi$ の範囲を動くとき、点 "
            r"$P\left(\cos\left(\frac{\pi\sin t}{2t}\right),"
            r"\sin(t-\sin t)\right)$ の描く曲線を $C$ とする。"
            r"曲線 $C$ によって囲まれる部分の面積を $S$ とするとき、"
            r"$S<1$ を示せ。"
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assertEqual(card["answer_tex"], r"\(S<1\)")
        self.assertIn("Riemann--Stieltjes", card["solution_tex"])
        self.assertIn("499638101/500000000", card["solution_tex"])
        self.assertEqual(
            card["family_id"],
            "solve.structural_theorem.structural_theorem_parametric_symmetric_area_bound",
        )

    def test_rose_revolution_problem_returns_volume_limit_and_strict_bounds(self) -> None:
        status, payload = solve_problem(
            r"正の整数 $n\ge2$ に対し、曲線 $r=\sin n\theta$ によって囲まれる領域を "
            r"$x$軸のまわりに1回転して得られる立体の体積を $V_n$ とする。"
            r"(1) $V_n$を求め、極限 $\alpha=\lim_{n\to\infty}V_n$ を求めよ。"
            r"(2) $V_n>\alpha$ および $\dfrac{11305}{972}(2-\sqrt3)<\pi$ を示せ。"
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assertIn(r"\frac{8\pi n^3}", card["answer_tex"])
        self.assertIn(r"\alpha=\frac{16}{9}", card["answer_tex"])
        self.assertIn("Euler", card["solution_tex"])
        self.assertIn("1728", card["solution_tex"])
        self.assertEqual(
            card["family_id"],
            "solve.structural_theorem.structural_theorem_polar_rose_revolution_volume",
        )

    def test_cubic_tangent_problem_returns_points_range_and_minimum_area(self) -> None:
        status, payload = solve_problem(
            r"実数 $c$ に対し、曲線 $C_c:y=x^3-cx$ を考える。点 $P$ から "
            r"$C_c$ に相異なる3本の接線 $\ell_1,\ell_2,\ell_3$ が引け、"
            r"$\ell_1,\ell_2$ のなす角と $\ell_2,\ell_3$ のなす角がともに "
            r"$\dfrac{\pi}{3}$ である。接点を $A,B,C$ とする。"
            r"(1) $c=3$ のとき $P$ をすべて求めよ。"
            r"(2) $c$ の範囲を求めよ。"
            r"(3) 三角形 $ABC$ の面積の最小値を求めよ。"
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assertIn(r"3+\delta\sqrt6", card["answer_tex"])
        self.assertIn(r"c\in[\sqrt3,\infty)", card["answer_tex"])
        self.assertIn("5543", card["answer_tex"])
        self.assertIn("Vandermonde", card["solution_tex"])
        self.assertEqual(
            card["family_id"],
            "solve.structural_theorem.structural_theorem_cubic_tangent_equiangular_extremum",
        )

    def test_regular_polygon_extrema_problem_returns_a_replayed_impossibility_proof(self) -> None:
        status, payload = solve_problem(
            r"$n\ge3$ とする。モニックな有理数係数 $(n+1)$次多項式 "
            r"$y=f(x)$ の極値点は正 $n$ 角形の頂点をなさないことを示せ。"
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assertIn("存在しない", card["answer_tex"])
        self.assertIn("Chebyshev", card["solution_tex"])
        self.assertIn(r"R^n=\frac{2^{n-1}(n-1)}{n}", card["solution_tex"])
        self.assertIn("進付値", card["solution_tex"])
        self.assertEqual(
            card["family_id"],
            "solve.structural_theorem."
            "structural_theorem_rational_polynomial_regular_polygon_extrema_impossible",
        )

    def test_balanced_grid_regression_problem_returns_both_exact_approximations(self) -> None:
        status, payload = solve_problem(
            r"座標平面上の格子点集合 "
            r"$\{(x,y)\in\mathbb Z^2\mid1\le x,y\le2n\}$ を"
            r"要素数が等しい二つの部分集合に分ける。各部分集合に対し"
            r"回帰直線を一つずつ定め、これら二直線の成す角が"
            r"$\frac{\pi}{3}$になるべく近くなるように点を選ぶ。"
            r"(1) $n=2$のとき、$\sqrt{3}$を有理近似せよ。"
            r"(2) $n=3$のとき、$\sqrt{3}$を有理近似せよ。"
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assertIn(r"\frac{7016}{4053}", card["answer_tex"])
        self.assertIn(r"\frac{627}{362}", card["answer_tex"])
        self.assertIn("十分統計", card["solution_tex"])
        self.assertIn("対称性代表", card["solution_tex"])
        self.assertEqual(
            card["family_id"],
            "solve.structural_theorem."
            "structural_theorem_balanced_grid_regression_angle_approximation",
        )
        self.assertEqual(
            card["execution_certificate"]["operator"],
            "balanced_grid_regression_angle_approximation",
        )
        self.assertTrue(card["execution_certificate"]["verified"])
        self.assertRegex(
            card["verification"]["certificate_sha256"],
            r"^[0-9a-f]{64}$",
        )
        self.assertIn(
            "not an independent external theorem prover",
            card["verification"]["verification_scope"],
        )

    def test_cubic_arc_dot_chord_problem_returns_exact_swept_area(self) -> None:
        status, payload = solve_problem(
            r"原点を$\textrm{O}$とする。"
            r"曲線$y=x^3-12x^2+45x-54$の$x$軸とともに有界領域を囲む弧上を"
            r"点$\textrm{P},\textrm{Q}$が"
            r"$\overrightarrow{\textrm{OP}}\cdot"
            r"\overrightarrow{\textrm{OQ}}=20$を満たしながら動くとき、"
            r"線分$\textrm{PQ}$の通過領域の面積を求めよ。"
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assertIn(r"\frac{31877}{5184}", card["answer_tex"])
        self.assertIn(r"\frac14\log 2", card["answer_tex"])
        self.assertIn("(R-1)", card["solution_tex"])
        self.assertIn("包絡線", card["solution_tex"])
        self.assertEqual(
            card["family_id"],
            "solve.structural_theorem."
            "structural_theorem_cubic_arc_dot_chord_sweep_area",
        )
        self.assertEqual(
            card["execution_certificate"]["operator"],
            "cubic_arc_dot_chord_sweep_area",
        )
        self.assertTrue(card["execution_certificate"]["verified"])
        self.assertRegex(
            card["verification"]["certificate_sha256"],
            r"^[0-9a-f]{64}$",
        )

    def test_coordinate_tangent_disk_problem_returns_exact_projected_area(self) -> None:
        status, payload = solve_problem(
            r"半径1の円板 $D$ が $x,y,z\geq0$ の範囲に含まれ、"
            r"3つの座標平面のそれぞれとただ1点を共有しながら動く。"
            r"$D$ の通過領域を $xy$ 平面に正射影して得られる"
            r"図形の面積を求めよ。"
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assertIn(r"3+\frac{\pi}{4}", card["answer_tex"])
        self.assertIn("支持関数", card["solution_tex"])
        self.assertIn("四分円", card["solution_tex"])
        self.assertEqual(
            card["family_id"],
            "solve.structural_theorem."
            "structural_theorem_coordinate_tangent_disk_projection_area",
        )
        self.assertEqual(
            card["execution_certificate"]["operator"],
            "coordinate_tangent_disk_projection_area",
        )
        self.assertTrue(card["execution_certificate"]["verified"])
        self.assertRegex(
            card["verification"]["certificate_sha256"],
            r"^[0-9a-f]{64}$",
        )

    def test_four_face_tangent_disk_problem_returns_exact_swept_volume(self) -> None:
        status, payload = solve_problem(
            r"1辺の長さが2の立方体"
            r"$C=\{(x,y,z)\mid0\le x,y,z\le2\}$に半径1の円板$D$が含まれる。"
            r"$D$の円周が立方体の4つの面$x=0,y=0,z=0,z=2$の内部と"
            r"それぞれただ1点を共有しながら動くとき、"
            r"$D$の通過領域の体積を求めよ。"
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assertIn(r"\frac{\pi^2}{2}", card["answer_tex"])
        self.assertIn("四分円環", card["solution_tex"])
        self.assertIn("Cavalieri", card["solution_tex"])
        self.assertEqual(
            card["family_id"],
            "solve.structural_theorem."
            "structural_theorem_four_face_tangent_disk_swept_volume",
        )
        self.assertEqual(
            card["execution_certificate"]["operator"],
            "four_face_tangent_disk_swept_volume",
        )
        self.assertTrue(card["execution_certificate"]["verified"])
        self.assertRegex(
            card["verification"]["certificate_sha256"],
            r"^[0-9a-f]{64}$",
        )

    def test_polar_circle_problem_returns_doubling_orbit_and_both_proofs(self) -> None:
        status, payload = solve_problem(
            r"極座標平面上の曲線 $C:r=\sin\theta$ 上に原点Oと異なる相異なる5点 "
            r"$P_1,\ldots,P_5$ があり、$P_kP_{k+1}=P_kO$、$P_5P_1=P_5O$、"
            r"$OP_1<OP_2<OP_3<OP_4<OP_5$ を満たす。"
            r"$\frac{1}{OP_1}=\frac{1}{OP_2}+\frac{1}{OP_3}+\frac{1}{OP_4}+\frac{1}{OP_5}$ "
            r"および $\frac{1}{P_1P_3}+\frac{1}{P_2P_5}="
            r"\frac{1}{P_1P_4}+\frac{1}{P_2P_4}+\frac{1}{P_3P_5}$ を示せ。"
        )

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assertIn(r"2^{k-1}\pi/31", card["answer_tex"])
        self.assertIn("倍角写像", card["solution_tex"])
        self.assertIn("cot3x+cot7x", card["solution_tex"])
        self.assertEqual(
            card["family_id"],
            "solve.structural_theorem.structural_theorem_polar_circle_doubling_reciprocal_identities",
        )

    def test_reflected_parabola_integer_triangle_returns_impossibility_proof(self) -> None:
        statement = (
            r"放物線P : $y = x^2 $、直線Q : $y =ax +b$を考える."
            r"放物線と直線の交点を A, B とする。\\"
            r"PをQで折り返した像とPとの交点のうちQ上にない点を C とする."
            r"AB,BC,CAがすべて整数となるような$a,b$は存在するか."
        )

        status, payload = solve_problem(statement)

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assertIn("存在しない", card["answer_tex"])
        self.assertIn("m^2-n^2", card["solution_tex"])
        self.assertEqual(
            card["family_id"],
            "solve.structural_theorem."
            "structural_theorem_parabola_reflection_integer_triangle_impossibility",
        )
        self.assertEqual(
            card["execution_certificate"]["operator"],
            "parabola_reflection_integer_triangle_impossibility",
        )
        self.assertEqual(
            card["execution_certificate"]["witness"]["proof_kernel_count"],
            2,
        )
        self.assertTrue(card["execution_certificate"]["verified"])
        self.assertRegex(
            card["verification"]["certificate_sha256"],
            r"^[0-9a-f]{64}$",
        )


if __name__ == "__main__":
    unittest.main()
