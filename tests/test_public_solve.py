from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from api.solve import solve_problem


class PublicSolveTests(unittest.TestCase):
    def test_rational_angle_power_identity_exports_its_actual_proof_route(self) -> None:
        problem = (
            r"$0<2p<q$ を満たす互いに素な自然数 $p,q$ と自然数 $n\geqq2$ に対し，"
            r"$\cos^n\frac{p\pi}{q}+\sin^n\frac{p\pi}{q}="
            r"\cos\frac{np\pi}{q}+\sin\frac{np\pi}{q}$ が成り立つ組 $(n,p,q)$ をすべて求めよ．"
        )

        status, payload = solve_problem(problem)

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
        self.assertIn("図による確認", document)
        self.assertIn("使った射と役割", document)
        self.assertIn("証明義務", document)
        self.assertIn("O8", document)
        self.assertIn(card["verification"]["certificate_sha256"], document)

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
        self.assertEqual(card["artifact_version"], 2)
        self.assertEqual(card["diagram"]["kind"], "plane")
        self.assertEqual(card["diagram"]["title"], "方程式の零点")
        self.assertGreater(len(card["diagram"]["shapes"]), 1)
        self.assertIn("因数分解", card["solution_tex"])
        self.assertIn(r"\begin{tikzpicture}", card["diagram_tikz"])
        self.assertIn(r"\documentclass[uplatex,dvipdfmx,11pt]{jsarticle}", card["solution_document_tex"])
        self.assertIn(card["answer_tex"], card["solution_document_tex"])
        self.assertRegex(card["verification"]["certificate_sha256"], r"^[0-9a-f]{64}$")
        self.assertIn(card["verification"]["certificate_sha256"], card["solution_document_tex"])
        self.assertEqual(card["proof_trace"], payload["trace"])

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

    def test_definite_integral_uses_exact_backend(self) -> None:
        status, payload = solve_problem(r"$\int_0^1 x^2\,dx$ を求めよ。")

        self.assertEqual(status, 200)
        card = payload["cards"][0]
        self.assertEqual(card["answer_tex"], r"\(\frac{1}{3}\)")
        self.assertEqual(card["diagram"]["kind"], "plane")
        self.assertIn("微積分の基本定理", card["solution_tex"])

    def test_limit_uses_exact_backend(self) -> None:
        status, payload = solve_problem(r"$\lim_{x\to0}\frac{\sin x}{x}$ を求めよ。")

        self.assertEqual(status, 200)
        self.assertEqual(payload["cards"][0]["answer_tex"], r"\(1\)")

    def test_unevaluated_limit_is_not_certified(self) -> None:
        status, payload = solve_problem(r"$\lim_{n\to\infty}(S_n-T_n)$ を求めよ。")

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
