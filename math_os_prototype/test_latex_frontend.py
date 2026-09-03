import unittest

from math_os_prototype.latex_frontend import normalize_latex_math


class LatexFrontendNormalizationTest(unittest.TestCase):
    def test_layout_commands_do_not_become_symbolic_variables(self) -> None:
        normalized = normalize_latex_math(
            r"\displaystyle \operatorname{Im}(1+\frac{i}{x})^x"
        )
        self.assertEqual(normalized, "Im (1+((i)/(x)))**x")
        self.assertNotIn("d*i*s*p*l*a*y", normalized)

    def test_spacing_and_delimiter_sizes_preserve_the_expression(self) -> None:
        self.assertEqual(
            normalize_latex_math(r"\quad \Bigl(\alpha+\beta\Bigr)"),
            "(alpha+beta)",
        )
        self.assertEqual(
            normalize_latex_math(r"\qquad f_{n+1}(x)"),
            "f_(n+1)*(x)",
        )

    def test_semantic_function_and_greek_commands_are_not_removed(self) -> None:
        self.assertEqual(
            normalize_latex_math(r"\sin\theta x+\cos\theta"),
            "sin(theta) x+cos(theta)",
        )

    def test_binders_and_structural_operators_survive_token_lowering(self) -> None:
        self.assertEqual(
            normalize_latex_math(r"\int_0^1(1-x^2)^n\,dx"),
            "integral_0**1*(1-x**2)**n dx",
        )
        self.assertEqual(
            normalize_latex_math(r"\lim_{n\to\infty}V_n"),
            "limit_n to infinity V_n",
        )
        self.assertEqual(
            normalize_latex_math(r"\sum_{k=0}^n x_k"),
            "sum_(k=0)**n x_k",
        )
        self.assertEqual(normalize_latex_math(r"\arg z_{jm}"), "arg(z_jm)")
        self.assertEqual(normalize_latex_math(r"\angle C"), "angle C")


if __name__ == "__main__":
    unittest.main()
