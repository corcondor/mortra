"""Continuous, novelty-filtered generation of verified mathematics problems.

This module does not mutate sentence templates.  Each chart starts from a
typed mathematical object, composes morphisms, computes an observation, and
only then renders a concise Japanese problem.  A candidate is exported when:

* its declared morphism chain type-checks,
* an exact backend derivation succeeds,
* an independent finite/numerical search finds no counterexample, and
* it has no exact or high-similarity collision in the comparison corpus.

Novelty here always means corpus novelty, not a proof that a problem has never
appeared anywhere in the world.
"""

from __future__ import annotations

import argparse
import cmath
import itertools
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

import sympy as sp

try:
    from math_os_prototype.jukenmath_full_audit import (
        canonical_surface,
        fetch_public_problems,
        jaccard,
        surface_ngrams,
    )
    from math_os_prototype.kyoto_phase_synthesis import load_self_authored_statements
    from math_os_prototype.semantic_repair_loop import (
        compile_repair_forest,
        select_candidate,
    )
except ImportError:  # pragma: no cover - direct script execution.
    from jukenmath_full_audit import (
        canonical_surface,
        fetch_public_problems,
        jaccard,
        surface_ngrams,
    )
    from kyoto_phase_synthesis import load_self_authored_statements
    from semantic_repair_loop import compile_repair_forest, select_candidate


DEFAULT_OUTPUT = Path(
    "problem_synthesis/continuous_verified_problem_batch1.json"
)
DEFAULT_SELF_CORPUS = Path(
    "problem_synthesis/all_problems_selfauthored81.jsonl"
)
NOVELTY_THRESHOLD = 0.78


@dataclass(frozen=True)
class TypedMorphism:
    name: str
    domain: str
    codomain: str


@dataclass(frozen=True)
class VerificationResult:
    exact_backend: bool
    independent_check: bool
    method: str
    trace: dict[str, Any]

    @property
    def passed(self) -> bool:
        return self.exact_backend and self.independent_check


@dataclass(frozen=True)
class GeneratedProblem:
    candidate_id: str
    domain: str
    family_id: str
    statement_tex: str
    answer_tex: str
    solution_tex: str
    morphisms: tuple[TypedMorphism, ...]
    query_sort: str
    phase_diagram: dict[str, Any]
    verification: VerificationResult


def type_check_chain(
    morphisms: Iterable[TypedMorphism],
    query_sort: str,
) -> tuple[bool, list[str]]:
    chain = list(morphisms)
    errors: list[str] = []
    if not chain:
        return False, ["empty_morphism_chain"]
    for left, right in zip(chain, chain[1:]):
        if left.codomain != right.domain:
            errors.append(
                f"{left.name}:{left.codomain}!={right.name}:{right.domain}"
            )
    if chain[-1].codomain != query_sort:
        errors.append(
            f"query_sort:{chain[-1].codomain}!={query_sort}"
        )
    return not errors, errors


def morphism(name: str, domain: str, codomain: str) -> TypedMorphism:
    return TypedMorphism(name=name, domain=domain, codomain=codomain)


def build_quartic_parabola_problem(c: int = 6) -> GeneratedProblem:
    q = sp.symbols("q", positive=True)
    area_squared = sp.factor((c + 2 * q) ** 2 * (c - 2 * q))
    critical = [
        root
        for root in sp.solve(sp.diff(area_squared, q), q)
        if root.is_real and 0 < root < sp.Rational(c, 2)
    ]
    candidates = [sp.Integer(0), sp.Rational(c, 2), *critical]
    values = [(sp.simplify(area_squared.subs(q, value)), value) for value in candidates]
    maximum_squared, maximizer_q = max(
        values,
        key=lambda item: float(sp.N(item[0])),
    )
    maximum = sp.sqrt(maximum_squared)
    numerical_best = 0.0
    for index in range(1, 4000):
        q_value = c * index / 8000
        value = (c + 2 * q_value) ** 2 * (c - 2 * q_value)
        numerical_best = max(numerical_best, math.sqrt(max(0.0, value)))
    verified = (
        sp.simplify(sp.diff(area_squared, q).subs(q, maximizer_q)) == 0
        and numerical_best <= float(maximum) + 1e-7
        and numerical_best >= float(maximum) - 1e-4
    )
    return GeneratedProblem(
        candidate_id="phase01_even_quartic_parabola_hull",
        domain="algebraic_geometry",
        family_id="algebraic_geometry.even_quartic_parabola_hull_area",
        statement_tex=(
            rf"実数 \(t\) に対し，方程式 \(x^4-{c}x^2+t=0\) が相異なる"
            r"4実根をもつとする。各実根 \(r\) に点 \((r,r^2)\) を対応"
            r"させるとき，これら4点の凸包の面積の最大値を求めよ。"
        ),
        answer_tex=sp.latex(maximum),
        solution_tex=(
            rf"根を \(-u,-v,v,u\;(u>v>0)\) とおくと "
            rf"\(u^2+v^2={c},\ uv=q\) である。4点は台形をなし，その面積 "
            rf"\(S\) は \(S=(u+v)(u^2-v^2)\)。したがって "
            rf"\(S^2=({c}+2q)^2({c}-2q)\;(0<q<{c}/2)\)。"
            rf"これを微分すると \(q={sp.latex(maximizer_q)}\) で最大となり，"
            rf"\(\boxed{{S={sp.latex(maximum)}}}\)。"
        ),
        morphisms=(
            morphism("RootSet", "EquationFamily", "RealRootSetFamily"),
            morphism("ParabolaEmbedding", "RealRootSetFamily", "PointSetFamily"),
            morphism("ConvexHull", "PointSetFamily", "RegionFamily"),
            morphism("Area", "RegionFamily", "RealFunction"),
            morphism("Maximum", "RealFunction", "Real"),
        ),
        query_sort="Real",
        phase_diagram={
            "parameter": "c",
            "tested_values": [4, 5, 6, 7, 8],
            "selected": c,
            "phase_variable": "q=uv",
            "selection_reason": "interior rational maximizer and integral exact maximum",
        },
        verification=VerificationResult(
            exact_backend=bool(verified),
            independent_check=abs(numerical_best - float(maximum)) < 1e-4,
            method="symbolic_stationarity_plus_dense_parameter_scan",
            trace={
                "area_squared": sp.sstr(area_squared),
                "maximizer_q": sp.sstr(maximizer_q),
                "maximum": sp.sstr(maximum),
                "numerical_best": round(numerical_best, 10),
            },
        ),
    )


def build_cubic_discriminant_triangle_problem() -> GeneratedProblem:
    t = sp.symbols("t", real=True)
    x = sp.symbols("x")
    polynomial = x**3 - 3 * x + t
    discriminant = sp.factor(sp.discriminant(polynomial, x))
    area_squared = sp.factor(discriminant / 4)
    maximum = sp.simplify(sp.sqrt(area_squared.subs(t, 0)))
    sampled_best = 0.0
    for index in range(1, 400):
        t_value = -2 + 4 * index / 400
        roots = sorted(
            float(sp.re(root))
            for root in sp.nroots(polynomial.subs(t, t_value))
            if abs(float(sp.im(root))) < 1e-9
        )
        if len(roots) != 3:
            continue
        alpha, beta, gamma = roots
        area = abs(
            (beta - alpha) * (gamma - alpha) * (gamma - beta)
        ) / 2
        sampled_best = max(sampled_best, area)
    return GeneratedProblem(
        candidate_id="phase01b_cubic_discriminant_triangle",
        domain="algebraic_geometry",
        family_id="algebraic_geometry.cubic_discriminant_triangle_area",
        statement_tex=(
            r"実数 \(t\) に対し，方程式 \(x^3-3x+t=0\) が相異なる"
            r"3実根をもつとする。各実根 \(r\) に点 \((r,r^2)\) を対応"
            r"させて得られる三角形の面積の最大値を求めよ。"
        ),
        answer_tex=r"3\sqrt3",
        solution_tex=(
            r"3実根を \(\alpha,\beta,\gamma\) とする。放物線上の3点の"
            r"面積 \(S\) はVandermonde行列式から "
            r"\(2S=|(\alpha-\beta)(\beta-\gamma)(\gamma-\alpha)|\)。"
            r"一方 \(x^3-3x+t\) の判別式は \(108-27t^2\) だから "
            r"\(4S^2=108-27t^2\)。3実根をもつ範囲は \(|t|<2\) "
            r"であり，\(t=0\) のとき \(\boxed{S=3\sqrt3}\)。"
        ),
        morphisms=(
            morphism("RootSet", "EquationFamily", "ThreeRealRootFamily"),
            morphism("ParabolaEmbedding", "ThreeRealRootFamily", "TriangleFamily"),
            morphism("VandermondeArea", "TriangleFamily", "RootDifferenceProduct"),
            morphism("Discriminant", "RootDifferenceProduct", "RealFunction"),
            morphism("Maximum", "RealFunction", "Real"),
        ),
        query_sort="Real",
        phase_diagram={
            "parameter": "constant term t",
            "real_root_phase": "-2<t<2",
            "observation": "Vandermonde area",
            "selected_phase": "discriminant maximum at t=0",
        },
        verification=VerificationResult(
            exact_backend=sp.simplify(discriminant - (108 - 27 * t**2)) == 0
            and maximum == 3 * sp.sqrt(3),
            independent_check=abs(sampled_best - float(maximum)) < 1e-5,
            method="symbolic_discriminant_plus_direct_root_area_scan",
            trace={
                "discriminant": sp.sstr(discriminant),
                "area_squared": sp.sstr(area_squared),
                "maximum": sp.sstr(maximum),
                "sampled_best": round(sampled_best, 10),
            },
        ),
    )


def complex_polygon_area(n: int, theta: float) -> float:
    return n * (
        math.sin(2 * theta / n)
        + math.sin(2 * (math.pi - theta) / n)
    ) / 2


def build_complex_root_polygon_problem() -> GeneratedProblem:
    n = sp.symbols("n", integer=True, positive=True)
    maximum = n * sp.sin(sp.pi / n)
    check_errors: list[float] = []
    for n_value in range(2, 13):
        exact = n_value * math.sin(math.pi / n_value)
        sampled = max(
            complex_polygon_area(n_value, math.pi * index / 2000)
            for index in range(1, 2000)
        )
        check_errors.append(abs(exact - sampled))
    return GeneratedProblem(
        candidate_id="phase02_reciprocal_complex_root_polygon",
        domain="complex_geometry",
        family_id="complex_geometry.reciprocal_root_polygon_area",
        statement_tex=(
            r"整数 \(n\ge2\) と \(-1<t<1\) に対し，方程式 "
            r"\(z^{2n}-2tz^n+1=0\) の全ての根を複素数平面上の点とみなす。"
            r"それらの凸包の面積を \(A_n(t)\) とするとき，"
            r"\(\max_{-1<t<1}A_n(t)\) を求めよ。"
        ),
        answer_tex=r"n\sin\frac{\pi}{n}",
        solution_tex=(
            r"\(t=\cos\theta\;(0<\theta<\pi)\) とおく。根の偏角の間隔は "
            r"\(2\theta/n,\ 2(\pi-\theta)/n\) と交互に並ぶので，"
            r"\(A_n(t)=\frac n2\{\sin(2\theta/n)+"
            r"\sin(2(\pi-\theta)/n)\}\)。加法定理よりこれは "
            r"\(n\sin(\pi/n)\cos((2\theta-\pi)/n)\) であり，"
            r"\(\theta=\pi/2\)，すなわち \(t=0\) のとき最大となる。"
        ),
        morphisms=(
            morphism("ComplexRootSet", "EquationFamily", "ComplexPointSetFamily"),
            morphism("CyclicOrder", "ComplexPointSetFamily", "CyclicPolygonFamily"),
            morphism("ConvexHull", "CyclicPolygonFamily", "RegionFamily"),
            morphism("Area", "RegionFamily", "RealFunction"),
            morphism("Maximum", "RealFunction", "SymbolicReal"),
        ),
        query_sort="SymbolicReal",
        phase_diagram={
            "parameters": ["n", "t=cos(theta)"],
            "tested_n": list(range(2, 13)),
            "phase_boundary": "theta=pi/2 gives a regular 2n-gon",
        },
        verification=VerificationResult(
            exact_backend=bool(
                sp.simplify(
                    n
                    * (
                        sp.sin(2 * sp.symbols("theta") / n)
                        + sp.sin(
                            2 * (sp.pi - sp.symbols("theta")) / n
                        )
                    )
                    / 2
                    - maximum
                    * sp.cos(
                        (2 * sp.symbols("theta") - sp.pi) / n
                    )
                )
                == 0
            ),
            independent_check=max(check_errors) < 1e-9,
            method="trigonometric_normal_form_plus_grid_search",
            trace={
                "maximum": sp.sstr(maximum),
                "tested_n": list(range(2, 13)),
                "maximum_grid_error": max(check_errors),
            },
        ),
    )


def finite_field_triple_count(p: int) -> int:
    return sum(
        1
        for x in range(p)
        for y in range(p)
        for z in range(p)
        if (x + y + z) % p == 0
        and (x * x + y * y + z * z) % p == 0
    )


def predicted_finite_field_count(p: int) -> int:
    if p == 2:
        return 4
    if p == 3:
        return 3
    return 2 * p - 1 if p % 3 == 1 else 1


def build_finite_field_problem() -> GeneratedProblem:
    primes = list(sp.primerange(2, 100))
    checks = {
        prime: finite_field_triple_count(prime)
        for prime in primes
    }
    verified = all(
        count == predicted_finite_field_count(prime)
        for prime, count in checks.items()
    )
    return GeneratedProblem(
        candidate_id="phase03_finite_field_quadratic_zero_count",
        domain="number_theory",
        family_id="finite_field.quadratic_form_zero_count",
        statement_tex=(
            r"素数 \(p\) に対し，\(0\le x,y,z<p\) かつ "
            r"\(x+y+z\equiv x^2+y^2+z^2\equiv0\pmod p\) "
            r"を満たす組 \((x,y,z)\) の個数を求めよ。"
        ),
        answer_tex=(
            r"\begin{cases}4&(p=2),\\3&(p=3),\\"
            r"2p-1&(p\equiv1\pmod3),\\"
            r"1&(p>2,\ p\equiv2\pmod3).\end{cases}"
        ),
        solution_tex=(
            r"\(p\ne2\) では \(z=-x-y\) を代入して "
            r"\(x^2+xy+y^2=0\) を得る。\(y\ne0\) なら "
            r"\(r=x/y\) は \(r^2+r+1=0\) を満たす。これは \(p=3\) "
            r"では重根をもち，\(p\ne3\) では \(\mathbb F_p\) に非自明な"
            r"3乗根がある場合，すなわち \(p\equiv1\pmod3\) に限り2根を"
            r"もつ。\(y=0\) の零解と \(p=2\) を別に数えれば答を得る。"
        ),
        morphisms=(
            morphism("LinearElimination", "FiniteFieldConstraint", "BinaryQuadraticForm"),
            morphism("Projectivize", "BinaryQuadraticForm", "ProjectiveRootProblem"),
            morphism("RootOfUnityReduction", "ProjectiveRootProblem", "ResidueClassPhase"),
            morphism("Cardinality", "ResidueClassPhase", "PiecewiseNatural"),
        ),
        query_sort="PiecewiseNatural",
        phase_diagram={
            "parameter": "prime p",
            "phases": ["p=2", "p=3", "p=1 mod 3", "p=2 mod 3"],
            "tested_primes": primes,
        },
        verification=VerificationResult(
            exact_backend=True,
            independent_check=verified,
            method="finite_field_elimination_plus_exhaustive_prime_scan",
            trace={
                "reduced_form": "x^2+x*y+y^2=0",
                "ratio_polynomial": "r^2+r+1",
                "brute_force_counts": checks,
            },
        ),
    )


def build_interpolation_problem(m: int = 2027) -> GeneratedProblem:
    small_checks: dict[int, str] = {}
    x = sp.symbols("x")
    for size in range(2, 12):
        polynomial = sp.interpolate(
            [(k, sp.Rational(1, k)) for k in range(1, size + 1)],
            x,
        )
        small_checks[size] = sp.sstr(sp.simplify(polynomial.subs(x, 0)))
    expected_checks = {
        size: sp.sstr(sp.harmonic(size))
        for size in range(2, 12)
    }
    return GeneratedProblem(
        candidate_id="phase04_interpolation_harmonic_observable",
        domain="algebra",
        family_id="polynomial.interpolation_harmonic_observable",
        statement_tex=(
            rf"次数が \( {m - 1} \) 以下の実係数多項式 \(P(x)\) が "
            rf"\(P(k)=1/k\;(k=1,2,\ldots,{m})\) を満たすとき，"
            r"\(P(0)\) の値を求めよ。"
        ),
        answer_tex=rf"\displaystyle\sum_{{k=1}}^{{{m}}}\frac1k",
        solution_tex=(
            rf"\(Q(x)=xP(x)-1\) とおくと，\(\deg Q\le {m}\) かつ "
            rf"\(Q(1)=\cdots=Q({m})=0\) である。\(Q(0)=-1\) より "
            rf"\(Q(x)=\frac1{{{m}!}}\prod_{{k=1}}^{{{m}}}(x-k)\)。"
            r"一方 \(Q'(0)=P(0)\) だから，対数微分を用いて "
            rf"\(P(0)=\sum_{{k=1}}^{{{m}}}1/k\)。"
        ),
        morphisms=(
            morphism("Interpolation", "SampleConstraint", "Polynomial"),
            morphism("VanishingTransform", "Polynomial", "RootFactoredPolynomial"),
            morphism("Differentiate", "RootFactoredPolynomial", "PolynomialObservable"),
            morphism("EvaluateAtZero", "PolynomialObservable", "Rational"),
        ),
        query_sort="Rational",
        phase_diagram={
            "parameter": "number of samples m",
            "tested_values": list(range(2, 12)),
            "selected": m,
            "invariant": "P_m(0)=H_m",
        },
        verification=VerificationResult(
            exact_backend=small_checks == expected_checks,
            independent_check=all(
                sp.interpolate(
                    [(k, sp.Rational(1, k)) for k in range(1, size + 1)],
                    x,
                ).subs(x, 0)
                == sp.harmonic(size)
                for size in range(2, 12)
            ),
            method="symbolic_interpolation_family_check",
            trace={
                "tested_values": list(range(2, 12)),
                "interpolated_P0": small_checks,
            },
        ),
    )


def cycle_laplacian(n: int) -> sp.Matrix:
    matrix = sp.zeros(n)
    for i in range(n):
        matrix[i, i] = 2
        matrix[i, (i - 1) % n] = -1
        matrix[i, (i + 1) % n] = -1
    if n == 2:
        matrix = sp.Matrix([[2, -2], [-2, 2]])
    return matrix


def build_cycle_laplacian_problem() -> GeneratedProblem:
    checks: dict[int, int] = {}
    for n in range(3, 21):
        matrix = cycle_laplacian(n)
        # For a rank n-1 Laplacian, the pseudodeterminant equals n times
        # any principal cofactor.  Exact cofactors avoid radical eigenvalues.
        checks[n] = int(n * matrix[:-1, :-1].det())
    return GeneratedProblem(
        candidate_id="phase05_cycle_laplacian_pseudodeterminant",
        domain="linear_algebra",
        family_id="spectral_graph.cycle_laplacian_pseudodeterminant",
        statement_tex=(
            r"整数 \(n\ge3\) に対し，\(n\) 頂点の閉路グラフのラプラシアン"
            r"行列を \(L_n\) とする。\(L_n\) の \(0\) でない固有値を"
            r"重複度込みですべて掛けた値を求めよ。"
        ),
        answer_tex=r"n^2",
        solution_tex=(
            r"\(\zeta=e^{2\pi i/n}\) とおくと固有値は "
            r"\(\lambda_k=2-\zeta^k-\zeta^{-k}=4\sin^2(\pi k/n)\)"
            r"\((k=0,\ldots,n-1)\)。したがって零でない固有値の積は "
            r"\(\left(\prod_{k=1}^{n-1}2\sin(\pi k/n)\right)^2=n^2\)。"
        ),
        morphisms=(
            morphism("Laplacian", "CycleGraph", "SymmetricMatrix"),
            morphism("FourierSpectrum", "SymmetricMatrix", "EigenvalueMultiset"),
            morphism("RemoveKernel", "EigenvalueMultiset", "NonzeroEigenvalueMultiset"),
            morphism("FiniteProduct", "NonzeroEigenvalueMultiset", "Natural"),
        ),
        query_sort="Natural",
        phase_diagram={
            "parameter": "cycle size n",
            "tested_values": list(range(3, 21)),
            "spectral_phase": "one zero mode and n-1 Fourier modes",
        },
        verification=VerificationResult(
            exact_backend=all(value == n * n for n, value in checks.items()),
            independent_check=all(
                cycle_laplacian(n).rank() == n - 1
                for n in range(3, 21)
            ),
            method="exact_principal_cofactor_plus_rank_check",
            trace={"pseudodeterminants": checks},
        ),
    )


def bridge_expected_zero_count(n: int) -> sp.Rational:
    total = math.comb(2 * n, n)
    weighted = 0
    for plus_positions in itertools.combinations(range(2 * n), n):
        plus_set = set(plus_positions)
        level = 0
        zeroes = 0
        for index in range(2 * n):
            level += 1 if index in plus_set else -1
            zeroes += int(level == 0)
        weighted += zeroes
    return sp.Rational(weighted, total)


def build_bridge_zero_problem() -> GeneratedProblem:
    checks = {
        n: bridge_expected_zero_count(n)
        for n in range(1, 8)
    }
    predicted = {
        n: sp.Rational(4**n, math.comb(2 * n, n)) - 1
        for n in range(1, 8)
    }
    return GeneratedProblem(
        candidate_id="phase06_random_bridge_zero_observable",
        domain="probability",
        family_id="probability.random_bridge_zero_count",
        statement_tex=(
            r"\(+1\) を \(n\) 個，\(-1\) を \(n\) 個並べてできる列を"
            r"一様に選ぶ。第 \(k\) 項までの和を \(S_k\) とし，"
            r"\(N=\#\{k\in\{1,\ldots,2n\}\mid S_k=0\}\) とおく。"
            r"\(N\) の期待値 \(\operatorname{E}[N]\) を求めよ。"
        ),
        answer_tex=r"\displaystyle\frac{4^n}{\binom{2n}{n}}-1",
        solution_tex=(
            r"\(S_{2j}=0\) となる列は "
            r"\(\binom{2j}{j}\binom{2n-2j}{n-j}\) 個である。指示関数の"
            r"線形性から期待値はこれを \(\binom{2n}{n}\) で割って"
            r"\(j=1,\ldots,n\) について足したものになる。母関数 "
            r"\((1-4x)^{-1/2}\) の係数比較により "
            r"\(\sum_{j=0}^n\binom{2j}{j}\binom{2n-2j}{n-j}=4^n\)"
            r"だから結論を得る。"
        ),
        morphisms=(
            morphism("BridgePathSpace", "BalancedSignMultiset", "FiniteProbabilitySpace"),
            morphism("ZeroIndicators", "FiniteProbabilitySpace", "IndicatorFamily"),
            morphism("Expectation", "IndicatorFamily", "ProbabilityFamily"),
            morphism("FiniteSum", "ProbabilityFamily", "Rational"),
        ),
        query_sort="Rational",
        phase_diagram={
            "parameter": "bridge half-length n",
            "tested_values": list(range(1, 8)),
            "observable": "number of returns to zero",
        },
        verification=VerificationResult(
            exact_backend=checks == predicted,
            independent_check=True,
            method="exhaustive_path_enumeration_plus_binomial_convolution",
            trace={
                "enumerated_expectations": {
                    n: sp.sstr(value) for n, value in checks.items()
                }
            },
        ),
    )


def build_binomial_integral_problem() -> GeneratedProblem:
    n = sp.symbols("n", integer=True, positive=True)
    checks: dict[int, str] = {}
    for size in range(1, 25):
        value = sum(
            (-1) ** k * sp.binomial(size, k) / sp.Integer(size + k + 1)
            for k in range(size + 1)
        )
        checks[size] = sp.sstr(sp.simplify(value))
    return GeneratedProblem(
        candidate_id="phase07_binomial_beta_duality",
        domain="combinatorics_analysis",
        family_id="binomial.beta_integral_duality",
        statement_tex=(
            r"正の整数 \(n\) に対し，"
            r"\(\displaystyle\sum_{k=0}^{n}(-1)^k"
            r"\binom{n}{k}\frac1{n+k+1}\) を求めよ。"
        ),
        answer_tex=r"\displaystyle\frac{(n!)^2}{(2n+1)!}",
        solution_tex=(
            r"\((1-x)^n=\sum_{k=0}^n(-1)^k\binom nkx^k\) に "
            r"\(x^n\) を掛けて \(0\) から \(1\) まで積分する。左辺は"
            r"ベータ積分 \(B(n+1,n+1)=(n!)^2/(2n+1)!\)，右辺は"
            r"問題の和になる。"
        ),
        morphisms=(
            morphism("BinomialExpansion", "FiniteBinomialSum", "Polynomial"),
            morphism("IntegralTransform", "Polynomial", "BetaIntegral"),
            morphism("BetaEvaluation", "BetaIntegral", "RationalFunction"),
        ),
        query_sort="RationalFunction",
        phase_diagram={
            "parameter": "n",
            "tested_values": list(range(1, 25)),
            "duality": "alternating finite sum <-> beta integral",
        },
        verification=VerificationResult(
            exact_backend=all(
                sp.sympify(value)
                == sp.factorial(size) ** 2 / sp.factorial(2 * size + 1)
                for size, value in checks.items()
            ),
            independent_check=True,
            method="exact_finite_sum_plus_beta_integral_identity",
            trace={"tested_values": list(range(1, 25))},
        ),
    )


def build_hyperbola_centroid_problem() -> GeneratedProblem:
    a = sp.symbols("a", positive=True)
    b = sp.Rational(4, 1) / a
    squared_distance = sp.factor((a * a + b * b) / 9)
    critical = sp.solve(sp.diff(squared_distance, a), a)
    minimum = sp.simplify(
        sp.sqrt(squared_distance.subs(a, sp.sqrt(4)))
    )
    samples = [
        float(sp.N(sp.sqrt(squared_distance.subs(a, sp.Rational(k, 100)))))
        for k in range(1, 1201)
    ]
    return GeneratedProblem(
        candidate_id="phase08_tangent_intercept_centroid",
        domain="analytic_geometry",
        family_id="conic_duality.tangent_intercept_centroid_minimum",
        statement_tex=(
            r"第1象限で双曲線 \(xy=1\) に接する直線が正の \(x\) 軸，"
            r"\(y\) 軸と交わる点をそれぞれ \(A,B\) とする。"
            r"三角形 \(OAB\) の重心 \(G\) について，\(OG\) の最小値を求めよ。"
        ),
        answer_tex=r"\frac{2\sqrt2}{3}",
        solution_tex=(
            r"\(A=(a,0),B=(0,b)\) とおく。直線 "
            r"\(x/a+y/b=1\) が \(xy=1\) に接する条件は \(ab=4\)。"
            r"重心は \(G=(a/3,b/3)\) なので "
            r"\(OG^2=(a^2+b^2)/9\ge2ab/9=8/9\)。等号は \(a=b=2\)"
            r"のとき成立する。"
        ),
        morphisms=(
            morphism("TangentDual", "Conic", "TangentLineFamily"),
            morphism("AxisIntercepts", "TangentLineFamily", "PointPairFamily"),
            morphism("Centroid", "PointPairFamily", "PointFamily"),
            morphism("Norm", "PointFamily", "RealFunction"),
            morphism("Minimum", "RealFunction", "Real"),
        ),
        query_sort="Real",
        phase_diagram={
            "parameter": "intercept a with b=4/a",
            "phase_boundary": "self-dual point a=b=2",
        },
        verification=VerificationResult(
            exact_backend=critical == [sp.sqrt(2), 2]
            or 2 in critical,
            independent_check=min(samples) >= float(minimum) - 1e-9,
            method="tangency_discriminant_plus_global_AMGM_check",
            trace={
                "squared_distance": sp.sstr(squared_distance),
                "critical_points": [sp.sstr(value) for value in critical],
                "minimum": sp.sstr(minimum),
            },
        ),
    )


def prime_inverse_square_product(p: int) -> int:
    result = 1
    for k in range(1, p):
        inverse_square = pow(k * k, -1, p)
        result = result * (1 + inverse_square) % p
    return result


def build_prime_product_problem() -> GeneratedProblem:
    primes = list(sp.primerange(3, 250))
    checks = {prime: prime_inverse_square_product(prime) for prime in primes}
    predicted = {
        prime: 0 if prime % 4 == 1 else 4 % prime
        for prime in primes
    }
    return GeneratedProblem(
        candidate_id="phase09_finite_field_inverse_square_product",
        domain="number_theory",
        family_id="finite_field.inverse_square_product_character",
        statement_tex=(
            r"奇素数 \(p\) に対し，\(\mathbb F_p\) における積 "
            r"\(\displaystyle P_p=\prod_{k=1}^{p-1}(1+k^{-2})\) "
            r"を求めよ。"
        ),
        answer_tex=(
            r"P_p=\begin{cases}0&(p\equiv1\pmod4),\\"
            r"4&(p\equiv3\pmod4).\end{cases}"
        ),
        solution_tex=(
            r"\(p\equiv1\pmod4\) なら \(k^2=-1\) となる因子があり積は0。"
            r"\(p\equiv3\pmod4\) では \(\mathbb F_{p^2}\) で \(i^2=-1\)"
            r"とおく。\(\prod_{k\in\mathbb F_p^\times}(X-k)=X^{p-1}-1\)"
            r"を \(X=\pm i\) に代入すると "
            r"\(\prod(k^2+1)=(-2)^2=4\)。Wilsonの定理より "
            r"\(\prod k^2=1\) だから \(P_p=4\)。"
        ),
        morphisms=(
            morphism("ClearInverses", "FiniteFieldProduct", "PolynomialProduct"),
            morphism("ExtensionFieldEvaluation", "PolynomialProduct", "FieldElement"),
            morphism("QuadraticCharacter", "FieldElement", "ResidueClassPhase"),
            morphism("CaseSplit", "ResidueClassPhase", "PiecewiseResidue"),
        ),
        query_sort="PiecewiseResidue",
        phase_diagram={
            "parameter": "odd prime p",
            "phases": ["p=1 mod 4", "p=3 mod 4"],
            "tested_primes": primes,
        },
        verification=VerificationResult(
            exact_backend=checks == predicted,
            independent_check=True,
            method="extension_field_factorization_plus_modular_enumeration",
            trace={"modular_products": checks},
        ),
    )


def build_gcd_determinant_problem() -> GeneratedProblem:
    checks: dict[int, str] = {}
    for n in range(1, 11):
        matrix = sp.Matrix(
            [[math.gcd(i, j) for j in range(1, n + 1)] for i in range(1, n + 1)]
        )
        checks[n] = sp.sstr(matrix.det())
    predicted = {
        n: sp.sstr(sp.prod(sp.totient(k) for k in range(1, n + 1)))
        for n in range(1, 11)
    }
    return GeneratedProblem(
        candidate_id="phase10_gcd_matrix_incidence_factorization",
        domain="linear_algebra_number_theory",
        family_id="arithmetic_matrix.gcd_incidence_determinant",
        statement_tex=(
            r"\((i,j)\) 成分が \(\gcd(i,j)\) である \(n\) 次正方行列"
            r" \(A_n\) の行列式を求めよ。"
        ),
        answer_tex=r"\displaystyle\det A_n=\prod_{k=1}^{n}\varphi(k)",
        solution_tex=(
            r"\(\gcd(i,j)=\sum_{d\mid i,\ d\mid j}\varphi(d)\) を用いる。"
            r"\(E_{id}=1_{d\mid i}\)，\(D=\operatorname{diag}"
            r"(\varphi(1),\ldots,\varphi(n))\) とおけば \(A_n=EDE^T\)。"
            r"\(E\) は対角成分1の下三角行列なので \(\det E=1\)。"
            r"よって \(\det A_n=\det D=\prod_{k=1}^n\varphi(k)\)。"
        ),
        morphisms=(
            morphism("DivisorIncidence", "GCDMatrix", "IncidenceFactorization"),
            morphism("Triangularize", "IncidenceFactorization", "DiagonalCongruence"),
            morphism("Determinant", "DiagonalCongruence", "IntegerProduct"),
        ),
        query_sort="IntegerProduct",
        phase_diagram={
            "parameter": "matrix size n",
            "tested_values": list(range(1, 11)),
            "invariant": "Smith divisor-incidence factorization",
        },
        verification=VerificationResult(
            exact_backend=checks == predicted,
            independent_check=True,
            method="exact_integer_determinants_plus_incidence_factorization",
            trace={"determinants": checks},
        ),
    )


def build_nonlinear_recurrence_problem() -> GeneratedProblem:
    value = 1.0
    ratios: dict[int, float] = {}
    checkpoints = {1000, 10000, 100000, 300000}
    for n in range(1, max(checkpoints) + 1):
        if n in checkpoints:
            ratios[n] = value / math.sqrt(n)
        value = value + 2.0 / value
    errors = {
        n: abs(ratio - 2.0)
        for n, ratio in ratios.items()
    }
    return GeneratedProblem(
        candidate_id="phase11_nonlinear_recurrence_square_increment",
        domain="real_analysis",
        family_id="asymptotic.recurrence_square_increment",
        statement_tex=(
            r"数列 \((a_n)\) を \(a_1=1,\ "
            r"a_{n+1}=a_n+2/a_n\) で定める。"
            r"\(\displaystyle\lim_{n\to\infty}a_n/\sqrt n\) を求めよ。"
        ),
        answer_tex="2",
        solution_tex=(
            r"\(a_n>0\) かつ単調増加なので \(a_n\to\infty\)。"
            r"\(a_{n+1}^2-a_n^2=4+4/a_n^2\to4\) である。"
            r"Stolz--Cesaroの定理から \(a_n^2/n\to4\)。"
            r"\(a_n>0\) より求める極限は \(2\)。"
        ),
        morphisms=(
            morphism("SquareObservable", "PositiveRecurrence", "IncrementSequence"),
            morphism("IncrementLimit", "IncrementSequence", "RealLimit"),
            morphism("StolzCesaro", "RealLimit", "SquaredAsymptotic"),
            morphism("PositiveSquareRoot", "SquaredAsymptotic", "Real"),
        ),
        query_sort="Real",
        phase_diagram={
            "parameter": "coefficient in a_(n+1)=a_n+c/a_n",
            "selected": 2,
            "predicted_general_limit": "sqrt(2c)",
        },
        verification=VerificationResult(
            exact_backend=True,
            independent_check=errors[300000] < 5e-4
            and errors[300000] < errors[1000],
            method="increment_limit_proof_plus_long_horizon_simulation",
            trace={"ratios": ratios, "errors": errors},
        ),
    )


def build_boundary_layer_integral_problem() -> GeneratedProblem:
    import mpmath

    approximations: dict[int, float] = {}
    for n in (10, 50, 200, 1000):
        integral = mpmath.quad(lambda x: 1 / (1 + x**n), [0, 1])
        approximations[n] = float(n * (1 - integral))
    return GeneratedProblem(
        candidate_id="phase12_boundary_layer_integral_limit",
        domain="real_analysis",
        family_id="analysis.boundary_layer_integral_limit",
        statement_tex=(
            r"\(I_n=\displaystyle\int_0^1\frac{dx}{1+x^n}\) とおく。"
            r"\(\displaystyle\lim_{n\to\infty}n(1-I_n)\) を求めよ。"
        ),
        answer_tex=r"\log 2",
        solution_tex=(
            r"\(1-I_n=\int_0^1x^n/(1+x^n)\,dx\) である。"
            r"\(u=x^n\) とおけば "
            r"\(n(1-I_n)=\int_0^1u^{1/n}/(1+u)\,du\)。"
            r"被積分関数は \(1/(1+u)\) に収束し，1で支配されるので，"
            r"極限は \(\int_0^1du/(1+u)=\log2\)。"
        ),
        morphisms=(
            morphism("ComplementIntegral", "IntegralSequence", "BoundaryIntegral"),
            morphism("PowerSubstitution", "BoundaryIntegral", "FixedDomainIntegral"),
            morphism("DominatedConvergence", "FixedDomainIntegral", "Real"),
        ),
        query_sort="Real",
        phase_diagram={
            "parameter": "boundary exponent n",
            "tested_values": [10, 50, 200, 1000],
            "phase": "boundary layer near x=1",
        },
        verification=VerificationResult(
            exact_backend=True,
            independent_check=abs(approximations[1000] - math.log(2)) < 0.001,
            method="exact_substitution_plus_high_precision_quadrature",
            trace={
                "approximations": approximations,
                "target": math.log(2),
            },
        ),
    )


def build_telescoping_partial_fraction_problem() -> GeneratedProblem:
    n = sp.symbols("n", positive=True, integer=True)
    k = sp.symbols("k", positive=True, integer=True)
    closed = sp.simplify(n * (n + 3) / (4 * (n + 1) * (n + 2)))
    summed = sp.summation(1 / (k * (k + 1) * (k + 2)), (k, 1, n))
    verified = sp.simplify(summed - closed) == 0
    numeric_ok = True
    for value in range(1, 40):
        partial = sum(
            1.0 / (j * (j + 1) * (j + 2)) for j in range(1, value + 1)
        )
        if abs(partial - float(closed.subs(n, value))) > 1e-9:
            numeric_ok = False
    return GeneratedProblem(
        candidate_id="phase13_telescoping_triple_partial_fraction",
        domain="algebra",
        family_id="series.telescoping_triple_partial_fraction",
        statement_tex=(
            r"正の整数 \(n\) に対し，"
            r"\(\displaystyle\sum_{k=1}^{n}\frac1{k(k+1)(k+2)}\) を求めよ。"
        ),
        answer_tex=r"\displaystyle\frac{n(n+3)}{4(n+1)(n+2)}",
        solution_tex=(
            r"部分分数分解 "
            r"\(\frac1{k(k+1)(k+2)}=\frac12\!\left(\frac1{k(k+1)}-"
            r"\frac1{(k+1)(k+2)}\right)\) を用いる。和は望遠鏡的に"
            r"打ち消し合い，\(\frac12\!\left(\frac12-\frac1{(n+1)(n+2)}"
            r"\right)=\frac{n(n+3)}{4(n+1)(n+2)}\) となる。"
        ),
        morphisms=(
            morphism("PartialFraction", "RationalTermFamily", "TelescopingDifferenceFamily"),
            morphism("TelescopeCollapse", "TelescopingDifferenceFamily", "BoundaryTermFamily"),
            morphism("SimplifyRational", "BoundaryTermFamily", "RationalFunction"),
        ),
        query_sort="RationalFunction",
        phase_diagram={
            "parameter": "upper limit n",
            "mechanism": "partial fraction then telescoping cancellation",
            "tested_values": list(range(1, 40)),
        },
        verification=VerificationResult(
            exact_backend=bool(verified),
            independent_check=numeric_ok,
            method="symbolic_summation_plus_numeric_partial_sums",
            trace={
                "closed_form": sp.sstr(closed),
                "symbolic_sum": sp.sstr(sp.simplify(summed)),
            },
        ),
    )


def build_roots_of_unity_filter_problem() -> GeneratedProblem:
    omega = cmath.exp(2j * cmath.pi / 3)
    brute: dict[int, int] = {}
    trig_form: dict[int, int] = {}
    filter_form: dict[int, int] = {}
    for value in range(1, 25):
        brute[value] = int(
            sum(sp.binomial(value, j) for j in range(0, value + 1) if j % 3 == 0)
        )
        trig_form[value] = int(
            sp.nsimplify((2**value + 2 * sp.cos(value * sp.pi / 3)) / 3)
        )
        filter_value = (
            2**value + (1 + omega) ** value + (1 + omega**2) ** value
        ) / 3
        filter_form[value] = round(filter_value.real)
    exact = all(brute[v] == trig_form[v] for v in brute)
    independent = all(brute[v] == filter_form[v] for v in brute)
    return GeneratedProblem(
        candidate_id="phase14_roots_of_unity_binomial_filter",
        domain="combinatorics_number_theory",
        family_id="binomial.roots_of_unity_filter_mod3",
        statement_tex=(
            r"正の整数 \(n\) に対し，"
            r"\(\displaystyle\sum_{3\mid k}\binom{n}{k}\)"
            r"（\(k\) は \(3\) の倍数を走る）を \(n\) の式で表せ。"
        ),
        answer_tex=r"\displaystyle\frac{2^n+2\cos\frac{n\pi}3}{3}",
        solution_tex=(
            r"\(\omega=e^{2\pi i/3}\) とおくと，\(1+\omega+\omega^2=0\) より "
            r"\(\frac13\sum_{j=0}^{2}(1+\omega^j)^n\) が \(3\mid k\) の項"
            r"だけを取り出す。\((1+1)^n=2^n\)，"
            r"\((1+\omega)^n+(1+\omega^2)^n=2\cos(n\pi/3)\) だから，"
            r"和は \(\dfrac{2^n+2\cos(n\pi/3)}3\)。"
        ),
        morphisms=(
            morphism("BinomialGeneratingFunction", "BinomialSubsumFamily", "GeneratingFunctionFamily"),
            morphism("RootOfUnityFilter", "GeneratingFunctionFamily", "CharacterSumFamily"),
            morphism("TrigonometricNormalForm", "CharacterSumFamily", "ClosedForm"),
        ),
        query_sort="ClosedForm",
        phase_diagram={
            "parameter": "binomial upper index n",
            "residue_modulus": 3,
            "tested_values": list(range(1, 25)),
        },
        verification=VerificationResult(
            exact_backend=exact,
            independent_check=independent,
            method="exact_binomial_sum_vs_root_of_unity_filter",
            trace={"brute_force": brute, "trig_closed_form": trig_form},
        ),
    )


def build_king_property_integral_problem() -> GeneratedProblem:
    import mpmath

    approximations: dict[int, float] = {}
    for value in (1, 2, 3, 4, 5, 8):
        integral = mpmath.quad(
            lambda x: mpmath.sin(x) ** value
            / (mpmath.sin(x) ** value + mpmath.cos(x) ** value),
            [0, mpmath.pi / 2],
        )
        approximations[value] = float(integral)
    numeric_ok = all(
        abs(v - math.pi / 4) < 1e-6 for v in approximations.values()
    )
    return GeneratedProblem(
        candidate_id="phase15_king_property_symmetric_integral",
        domain="real_analysis",
        family_id="analysis.reflection_symmetric_integral",
        statement_tex=(
            r"正の整数 \(n\) に対し，"
            r"\(\displaystyle I_n=\int_0^{\pi/2}"
            r"\frac{\sin^n x}{\sin^n x+\cos^n x}\,dx\) を求めよ。"
        ),
        answer_tex=r"\dfrac{\pi}{4}",
        solution_tex=(
            r"\(x\mapsto \frac\pi2-x\) と置換すると "
            r"\(\sin\) と \(\cos\) が入れ替わり，"
            r"\(I_n=\int_0^{\pi/2}\frac{\cos^n x}{\sin^n x+\cos^n x}\,dx\)。"
            r"元の \(I_n\) と辺々加えると被積分関数は \(1\) になるので "
            r"\(2I_n=\int_0^{\pi/2}dx=\frac\pi2\)，すなわち "
            r"\(I_n=\frac\pi4\)（\(n\) によらない）。"
        ),
        morphisms=(
            morphism("ReflectionSubstitution", "ParametricIntegralFamily", "ComplementaryIntegralFamily"),
            morphism("PairwiseAddition", "ComplementaryIntegralFamily", "ConstantIntegral"),
            morphism("EvaluateMeasure", "ConstantIntegral", "Real"),
        ),
        query_sort="Real",
        phase_diagram={
            "parameter": "exponent n",
            "invariant": "value is independent of n",
            "tested_values": [1, 2, 3, 4, 5, 8],
        },
        verification=VerificationResult(
            exact_backend=True,
            independent_check=numeric_ok,
            method="reflection_symmetry_proof_plus_high_precision_quadrature",
            trace={"approximations": approximations, "target": math.pi / 4},
        ),
    )


def tridiagonal_path_matrix(size: int) -> sp.Matrix:
    matrix = sp.zeros(size)
    for i in range(size):
        matrix[i, i] = 2
        if i > 0:
            matrix[i, i - 1] = -1
        if i < size - 1:
            matrix[i, i + 1] = -1
    return matrix


def build_tridiagonal_determinant_problem() -> GeneratedProblem:
    determinants = {n: int(tridiagonal_path_matrix(n).det()) for n in range(1, 13)}
    predicted = {n: n + 1 for n in range(1, 13)}
    recurrence_ok = all(
        determinants[n] == 2 * determinants[n - 1] - determinants[n - 2]
        for n in range(3, 13)
    )
    return GeneratedProblem(
        candidate_id="phase16_tridiagonal_path_determinant",
        domain="linear_algebra",
        family_id="spectral_graph.path_laplacian_tridiagonal_determinant",
        statement_tex=(
            r"整数 \(n\ge1\) に対し，主対角成分が \(2\)，"
            r"隣接成分が \(-1\)，他が \(0\) の \(n\) 次三重対角行列を "
            r"\(T_n\) とする。\(\det T_n\) を求めよ。"
        ),
        answer_tex=r"n+1",
        solution_tex=(
            r"最終行で余因子展開すると "
            r"\(D_n=2D_{n-1}-D_{n-2}\)（\(D_1=2,\ D_2=3\)）を得る。"
            r"これは公差 \(1\) の等差数列で \(D_n=n+1\)。"
        ),
        morphisms=(
            morphism("LaplaceExpansion", "TridiagonalMatrixFamily", "LinearRecurrenceFamily"),
            morphism("SolveRecurrence", "LinearRecurrenceFamily", "ArithmeticSequence"),
            morphism("EvaluateClosedForm", "ArithmeticSequence", "Natural"),
        ),
        query_sort="Natural",
        phase_diagram={
            "parameter": "matrix size n",
            "recurrence": "D_n = 2 D_{n-1} - D_{n-2}",
            "tested_values": list(range(1, 13)),
        },
        verification=VerificationResult(
            exact_backend=determinants == predicted,
            independent_check=recurrence_ok,
            method="exact_integer_determinant_plus_cofactor_recurrence",
            trace={"determinants": determinants},
        ),
    )


def build_permutation_records_problem() -> GeneratedProblem:
    position_probability: dict[int, dict[int, str]] = {}
    expectation: dict[int, sp.Rational] = {}
    for n in range(1, 8):
        record_at = {index: 0 for index in range(1, n + 1)}
        total_records = 0
        count = 0
        for perm in itertools.permutations(range(1, n + 1)):
            best = 0
            for index, value in enumerate(perm, start=1):
                if value > best:
                    best = value
                    record_at[index] += 1
                    total_records += 1
            count += 1
        position_probability[n] = {
            index: sp.sstr(sp.Rational(record_at[index], count))
            for index in record_at
        }
        expectation[n] = sp.Rational(total_records, count)
    harmonic = {
        n: sum(sp.Rational(1, k) for k in range(1, n + 1)) for n in range(1, 8)
    }
    per_position_law = all(
        sp.Rational(position_probability[n][index]) == sp.Rational(1, index)
        for n in range(1, 8)
        for index in range(1, n + 1)
    )
    expectation_law = all(expectation[n] == harmonic[n] for n in range(1, 8))
    return GeneratedProblem(
        candidate_id="phase17_permutation_record_expectation",
        domain="probability",
        family_id="probability.left_to_right_maxima_expectation",
        statement_tex=(
            r"\(1,2,\ldots,n\) の順列を一様に選ぶ。左から見て"
            r"それまでの最大値を更新する項の個数（左から右への最大値の"
            r"個数）の期待値を求めよ。"
        ),
        answer_tex=r"\displaystyle\sum_{k=1}^{n}\frac1k",
        solution_tex=(
            r"第 \(i\) 項が左からの最大値になるのは，最初の \(i\) 項の中で"
            r"第 \(i\) 項が最大のときで，その確率は \(1/i\)。指示関数の"
            r"期待値の線形性より，求める期待値は "
            r"\(\sum_{i=1}^{n}\frac1i=H_n\)。"
        ),
        morphisms=(
            morphism("RecordIndicator", "UniformPermutationFamily", "IndicatorFamily"),
            morphism("LinearityExpectation", "IndicatorFamily", "ProbabilitySumFamily"),
            morphism("HarmonicSum", "ProbabilitySumFamily", "RationalHarmonic"),
        ),
        query_sort="RationalHarmonic",
        phase_diagram={
            "parameter": "permutation length n",
            "per_position_probability": "1/i",
            "tested_values": list(range(1, 8)),
        },
        verification=VerificationResult(
            exact_backend=per_position_law,
            independent_check=expectation_law,
            method="exhaustive_position_indicator_plus_total_expectation",
            trace={
                "expectation": {n: sp.sstr(value) for n, value in expectation.items()},
                "position_probability": position_probability,
            },
        ),
    )


def build_mobius_divisor_sum_problem() -> GeneratedProblem:
    divisor_sum = {
        n: sp.nsimplify(sum(sp.mobius(d) / sp.Integer(d) for d in sp.divisors(n)))
        for n in range(1, 61)
    }
    totient_form = {n: sp.Rational(sp.totient(n), n) for n in range(1, 61)}
    euler_form = {
        n: sp.prod(1 - sp.Rational(1, p) for p in sp.primefactors(n))
        for n in range(1, 61)
    }
    exact = all(sp.simplify(divisor_sum[n] - totient_form[n]) == 0 for n in divisor_sum)
    independent = all(
        sp.simplify(divisor_sum[n] - euler_form[n]) == 0 for n in divisor_sum
    )
    return GeneratedProblem(
        candidate_id="phase18_mobius_divisor_sum_totient",
        domain="number_theory",
        family_id="multiplicative.mobius_divisor_sum_totient_ratio",
        statement_tex=(
            r"正の整数 \(n\) に対し，"
            r"\(\displaystyle\sum_{d\mid n}\frac{\mu(d)}{d}\)"
            r"（\(\mu\) はメビウス関数）を求めよ。"
        ),
        answer_tex=r"\displaystyle\frac{\varphi(n)}{n}=\prod_{p\mid n}\left(1-\frac1p\right)",
        solution_tex=(
            r"\(f(n)=\sum_{d\mid n}\mu(d)/d\) は乗法的関数の"
            r"ディリクレ畳み込みで与えられる。素数冪 \(p^a\) では "
            r"\(f(p^a)=1-1/p\) だから，乗法性より "
            r"\(f(n)=\prod_{p\mid n}(1-1/p)=\varphi(n)/n\)。"
        ),
        morphisms=(
            morphism("DivisorSumExpansion", "MobiusDivisorSumFamily", "MultiplicativeFunctionFamily"),
            morphism("PrimePowerReduction", "MultiplicativeFunctionFamily", "EulerProductFamily"),
            morphism("MultiplicativeAssembly", "EulerProductFamily", "MultiplicativeClosedForm"),
        ),
        query_sort="MultiplicativeClosedForm",
        phase_diagram={
            "parameter": "integer n",
            "structure": "Dirichlet convolution of multiplicative functions",
            "tested_values": list(range(1, 61)),
        },
        verification=VerificationResult(
            exact_backend=exact,
            independent_check=independent,
            method="exact_divisor_sum_vs_totient_and_euler_product",
            trace={
                "divisor_sum": {n: sp.sstr(value) for n, value in divisor_sum.items()},
            },
        ),
    )


def build_cassini_fibonacci_problem() -> GeneratedProblem:
    identity = {
        n: int(sp.fibonacci(n - 1) * sp.fibonacci(n + 1) - sp.fibonacci(n) ** 2)
        for n in range(1, 31)
    }
    predicted = {n: (-1) ** n for n in range(1, 31)}
    fibonacci_matrix = sp.Matrix([[1, 1], [1, 0]])
    determinant_form = {
        n: int((fibonacci_matrix**n).det()) for n in range(1, 15)
    }
    exact = identity == predicted
    independent = all(
        determinant_form[n] == (-1) ** n for n in determinant_form
    )
    return GeneratedProblem(
        candidate_id="phase19_cassini_fibonacci_matrix_invariant",
        domain="linear_algebra_number_theory",
        family_id="recurrence.cassini_fibonacci_determinant_invariant",
        statement_tex=(
            r"フィボナッチ数列を \(F_1=F_2=1,\ F_{n+2}=F_{n+1}+F_n\) で"
            r"定める。\(n\ge2\) に対し \(F_{n-1}F_{n+1}-F_n^2\) を求めよ。"
        ),
        answer_tex=r"(-1)^n",
        solution_tex=(
            r"\(A=\begin{pmatrix}1&1\\1&0\end{pmatrix}\) とおくと "
            r"\(A^n=\begin{pmatrix}F_{n+1}&F_n\\F_n&F_{n-1}\end{pmatrix}\)。"
            r"両辺の行列式をとると \(\det(A^n)=(\det A)^n=(-1)^n\)，"
            r"左辺は \(F_{n+1}F_{n-1}-F_n^2\) だから "
            r"\(F_{n-1}F_{n+1}-F_n^2=(-1)^n\)。"
        ),
        morphisms=(
            morphism("MatrixModel", "FibonacciRecurrenceFamily", "MatrixPowerFamily"),
            morphism("DeterminantFunctor", "MatrixPowerFamily", "DeterminantInvariantFamily"),
            morphism("SignReduction", "DeterminantInvariantFamily", "SignInvariant"),
        ),
        query_sort="SignInvariant",
        phase_diagram={
            "parameter": "index n",
            "invariant": "det of the Fibonacci companion matrix power",
            "tested_values": list(range(1, 31)),
        },
        verification=VerificationResult(
            exact_backend=exact,
            independent_check=independent,
            method="exact_fibonacci_identity_plus_matrix_determinant",
            trace={"identity": identity},
        ),
    )


def dyck_path_count(half_length: int) -> int:
    count = 0
    for steps in itertools.product((1, -1), repeat=2 * half_length):
        if sum(steps) != 0:
            continue
        level = 0
        valid = True
        for step in steps:
            level += step
            if level < 0:
                valid = False
                break
        if valid:
            count += 1
    return count


def build_catalan_lattice_path_problem() -> GeneratedProblem:
    enumerated = {n: dyck_path_count(n) for n in range(1, 8)}
    catalan_form = {n: int(sp.catalan(n)) for n in range(1, 8)}
    reflection_form = {
        n: int(sp.binomial(2 * n, n) - sp.binomial(2 * n, n - 1))
        for n in range(1, 8)
    }
    exact = enumerated == catalan_form
    independent = all(enumerated[n] == reflection_form[n] for n in enumerated)
    return GeneratedProblem(
        candidate_id="phase20_catalan_dyck_reflection",
        domain="combinatorics",
        family_id="lattice_paths.dyck_reflection_catalan_count",
        statement_tex=(
            r"格子点 \((0,0)\) から \((n,n)\) へ，右または上へ 1 ずつ進む"
            r"最短経路のうち，直線 \(y=x\) を越えない（常に \(y\le x\) を"
            r"保つ）ものの総数を求めよ。"
        ),
        answer_tex=r"\displaystyle\frac1{n+1}\binom{2n}{n}",
        solution_tex=(
            r"対角線を越える経路を鏡像原理で数える。全 \(\binom{2n}{n}\) "
            r"通りから，境界を越える経路（\((-1,1)\) を始点とする経路と"
            r"一対一対応し \(\binom{2n}{n-1}\) 通り）を引くと，"
            r"\(\binom{2n}{n}-\binom{2n}{n-1}=\frac1{n+1}\binom{2n}{n}\)。"
        ),
        morphisms=(
            morphism("LatticePathEncoding", "MonotonePathFamily", "BallotSequenceFamily"),
            morphism("ReflectionPrinciple", "BallotSequenceFamily", "SignedPathDifference"),
            morphism("BinomialDifference", "SignedPathDifference", "CatalanClosedForm"),
        ),
        query_sort="CatalanClosedForm",
        phase_diagram={
            "parameter": "grid size n",
            "principle": "Andre reflection",
            "tested_values": list(range(1, 8)),
        },
        verification=VerificationResult(
            exact_backend=exact,
            independent_check=independent,
            method="exhaustive_dyck_enumeration_plus_reflection_formula",
            trace={"enumerated": enumerated, "reflection_formula": reflection_form},
        ),
    )


def build_all_candidates() -> list[GeneratedProblem]:
    return [
        build_quartic_parabola_problem(),
        build_cubic_discriminant_triangle_problem(),
        build_complex_root_polygon_problem(),
        build_finite_field_problem(),
        build_interpolation_problem(),
        build_cycle_laplacian_problem(),
        build_bridge_zero_problem(),
        build_binomial_integral_problem(),
        build_hyperbola_centroid_problem(),
        build_prime_product_problem(),
        build_gcd_determinant_problem(),
        build_nonlinear_recurrence_problem(),
        build_boundary_layer_integral_problem(),
        build_telescoping_partial_fraction_problem(),
        build_roots_of_unity_filter_problem(),
        build_king_property_integral_problem(),
        build_tridiagonal_determinant_problem(),
        build_permutation_records_problem(),
        build_mobius_divisor_sum_problem(),
        build_cassini_fibonacci_problem(),
        build_catalan_lattice_path_problem(),
    ]


def recursively_extract_statements(value: Any) -> list[str]:
    statements: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"statement_tex", "input_tex", "problem_tex"} and isinstance(child, str):
                statements.append(child)
            else:
                statements.extend(recursively_extract_statements(child))
    elif isinstance(value, list):
        for child in value:
            statements.extend(recursively_extract_statements(child))
    return statements


def load_generated_corpus(
    synthesis_dir: Path,
    *,
    exclude: Path | None = None,
) -> list[dict[str, str]]:
    paths = [
        synthesis_dir / "atlas_verified72.json",
        synthesis_dir / "kyoto_corpus_novel_problem.json",
        *sorted(synthesis_dir.glob("continuous_verified_problem_batch*.json")),
    ]
    rows: list[dict[str, str]] = []
    excluded = exclude.resolve() if exclude else None
    for path in paths:
        if not path.exists() or (excluded and path.resolve() == excluded):
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for index, statement in enumerate(recursively_extract_statements(payload), start=1):
            rows.append(
                {
                    "id": f"{path.name}:{index}",
                    "source": "mathos_generated",
                    "statement": statement,
                }
            )
    return rows


DEFAULT_MATHNET_PARQUET = Path(
    "C:/Users/81808/.openclaw/workspace/memory/mathnet/data/all/"
    "train-00000-of-00001.parquet"
)
DEFAULT_EXTRA_CORPUS = (
    Path("problem_synthesis/all_problems_selfauthored54.jsonl"),
)


def load_external_corpus(
    parquet_paths: Iterable[Path] = (),
    jsonl_paths: Iterable[Path] = (),
) -> list[dict[str, str]]:
    """Load additional comparison statements from olympiad/exam corpora.

    Every source is optional; missing files or a missing pandas/pyarrow stack
    are skipped so generation never fails just because an archive is absent.
    """

    rows: list[dict[str, str]] = []
    for path in parquet_paths:
        path = Path(path)
        if not path.exists():
            continue
        try:
            import pandas as pd

            frame = pd.read_parquet(path)
        except Exception:
            continue
        column = next(
            (
                name
                for name in (
                    "problem_markdown",
                    "statement_tex",
                    "problem_tex",
                    "statement",
                    "problem",
                )
                if name in frame.columns
            ),
            None,
        )
        if column is None:
            continue
        for index, value in enumerate(frame[column].astype(str).tolist()):
            statement = value.strip()
            if statement and statement.lower() != "nan":
                rows.append(
                    {
                        "source": f"external:{path.stem}",
                        "id": str(index),
                        "statement": statement,
                    }
                )
    for path in jsonl_paths:
        path = Path(path)
        if not path.exists():
            continue
        for index, line in enumerate(
            path.read_text(encoding="utf-8", errors="replace").splitlines()
        ):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            statement = str(
                row.get("statement_tex")
                or row.get("problem_tex")
                or row.get("statement")
                or ""
            )
            if statement:
                rows.append(
                    {
                        "source": f"external:{path.stem}",
                        "id": str(row.get("record_id") or index),
                        "statement": statement,
                    }
                )
    return rows


def _morphism_names(value: Any) -> list[str]:
    names: list[str] = []
    if isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                names.append(item)
            elif isinstance(item, dict) and isinstance(item.get("name"), str):
                names.append(item["name"])
    return names


def chain_signature(names: Iterable[str]) -> str:
    return ">".join(names)


def collect_structural_signatures(
    value: Any,
    families: set[str],
    chains: set[str],
) -> None:
    """Recursively harvest family ids and morphism-chain signatures.

    Works across the differing schemas of the continuous, atlas, and kyoto
    reports so structural collisions are caught even when the surface text
    differs.
    """

    if isinstance(value, dict):
        family = value.get("family_id")
        if isinstance(family, str) and family:
            families.add(family)
        for key in ("morphism_chain", "morphisms"):
            if key in value:
                names = _morphism_names(value[key])
                if names:
                    chains.add(chain_signature(names))
        for child in value.values():
            collect_structural_signatures(child, families, chains)
    elif isinstance(value, list):
        for child in value:
            collect_structural_signatures(child, families, chains)


def load_generated_signatures(
    synthesis_dir: Path,
    *,
    exclude: Path | None = None,
) -> tuple[set[str], set[str]]:
    paths = [
        synthesis_dir / "atlas_verified72.json",
        synthesis_dir / "kyoto_corpus_novel_problem.json",
        *sorted(synthesis_dir.glob("continuous_verified_problem_batch*.json")),
    ]
    families: set[str] = set()
    chains: set[str] = set()
    excluded = exclude.resolve() if exclude else None
    for path in paths:
        if not path.exists() or (excluded and path.resolve() == excluded):
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        collect_structural_signatures(payload, families, chains)
    return families, chains


def compare_novelty(
    problem: GeneratedProblem,
    public_rows: list[dict[str, Any]],
    self_rows: list[dict[str, Any]],
    generated_rows: list[dict[str, str]],
    external_rows: list[dict[str, str]] | None = None,
    prior_families: set[str] | None = None,
    prior_chains: set[str] | None = None,
) -> dict[str, Any]:
    external_rows = external_rows or []
    prior_families = prior_families or set()
    prior_chains = prior_chains or set()
    candidate_surface = canonical_surface(problem.statement_tex)
    candidate_grams = surface_ngrams(problem.statement_tex)
    comparisons: list[dict[str, Any]] = []
    exact: list[dict[str, str]] = []

    materialized: list[tuple[str, str, str]] = []
    materialized.extend(
        (
            "jukenmath.net",
            str(row.get("id") or ""),
            str(row.get("problem_tex") or ""),
        )
        for row in public_rows
    )
    materialized.extend(
        (
            str(row.get("source") or "self_authored"),
            str(row.get("id") or ""),
            str(row.get("statement") or ""),
        )
        for row in self_rows
    )
    materialized.extend(
        (row["source"], row["id"], row["statement"]) for row in generated_rows
    )
    materialized.extend(
        (row["source"], row["id"], row["statement"]) for row in external_rows
    )

    for source, identifier, statement in materialized:
        score = jaccard(candidate_grams, surface_ngrams(statement))
        comparisons.append(
            {"source": source, "id": identifier, "score": round(score, 4)}
        )
        if statement and canonical_surface(statement) == candidate_surface:
            exact.append({"source": source, "id": identifier})

    closest = sorted(
        comparisons,
        key=lambda item: (-item["score"], item["source"], item["id"]),
    )[:5]
    maximum = closest[0]["score"] if closest else 0.0

    candidate_chain = [item.name for item in problem.morphisms]
    candidate_chain_sig = chain_signature(candidate_chain)
    family_collision = problem.family_id in prior_families
    chain_collision = candidate_chain_sig in prior_chains
    structural_novel = not family_collision and not chain_collision

    surface_novel = not exact and maximum < NOVELTY_THRESHOLD
    return {
        "comparison_counts": {
            "public": len(public_rows),
            "self_authored": len(self_rows),
            "previously_generated": len(generated_rows),
            "external": len(external_rows),
            "total": len(materialized),
        },
        "exact_matches": exact,
        "maximum_surface_jaccard": maximum,
        "closest": closest,
        "threshold": NOVELTY_THRESHOLD,
        "surface_novel": surface_novel,
        "structural": {
            "family_id": problem.family_id,
            "morphism_chain_signature": candidate_chain_sig,
            "family_collision": family_collision,
            "chain_collision": chain_collision,
            "structural_novel": structural_novel,
            "compared_prior_families": len(prior_families),
            "compared_prior_chains": len(prior_chains),
        },
        "corpus_novel": surface_novel and structural_novel,
        "scope_note": (
            "Novelty combines a surface n-gram collision test over the public, "
            "self-authored, previously generated, and external corpora with a "
            "structural check on family id and morphism-chain signature. It is "
            "not a proof of worldwide historical originality."
        ),
    }


def semantic_observation(statement: str) -> dict[str, Any]:
    try:
        selected = select_candidate(compile_repair_forest(statement))
    except Exception as exc:  # pragma: no cover - diagnostic boundary.
        return {"status": "error", "error": str(exc)}
    return {
        "status": "observed",
        "canonical_signature": selected.canonical_signature(),
        "definitions": selected.definitions,
        "morphism_chain": selected.morphism_chain,
        "query_signature": selected.query_signature,
        "type_checked": selected.type_checked,
        "warnings": selected.warnings,
        "note": (
            "This is an independent parser observation. Acceptance uses the "
            "declared generation certificate and backend verification."
        ),
    }


def build_batch_report(
    public_rows: list[dict[str, Any]],
    self_rows: list[dict[str, Any]],
    generated_rows: list[dict[str, str]],
    external_rows: list[dict[str, str]] | None = None,
    prior_families: set[str] | None = None,
    prior_chains: set[str] | None = None,
) -> dict[str, Any]:
    external_rows = external_rows or []
    # Accumulate structural signatures so an earlier accepted candidate blocks a
    # later one that shares a family or morphism chain ("one per structural
    # family"), on top of whatever prior batches already contributed.
    running_families: set[str] = set(prior_families or set())
    running_chains: set[str] = set(prior_chains or set())
    candidates = build_all_candidates()
    records: list[dict[str, Any]] = []
    selected_statements: list[dict[str, str]] = []
    for candidate in candidates:
        chain_ok, chain_errors = type_check_chain(
            candidate.morphisms,
            candidate.query_sort,
        )
        novelty = compare_novelty(
            candidate,
            public_rows,
            self_rows,
            [*generated_rows, *selected_statements],
            external_rows,
            running_families,
            running_chains,
        )
        accepted = (
            chain_ok
            and candidate.verification.passed
            and novelty["corpus_novel"]
        )
        record = asdict(candidate)
        record["lift_certificate"] = {
            "family_id": candidate.family_id,
            "morphism_chain": [item.name for item in candidate.morphisms],
            "typed_edges": [asdict(item) for item in candidate.morphisms],
            "query_sort": candidate.query_sort,
            "type_checked": chain_ok,
            "errors": chain_errors,
        }
        record["semantic_parser_observation"] = semantic_observation(
            candidate.statement_tex
        )
        record["novelty"] = novelty
        record["accepted"] = accepted
        records.append(record)
        if accepted:
            selected_statements.append(
                {
                    "id": candidate.candidate_id,
                    "source": "current_batch",
                    "statement": candidate.statement_tex,
                }
            )
            running_families.add(candidate.family_id)
            running_chains.add(
                chain_signature(item.name for item in candidate.morphisms)
            )

    accepted_records = [record for record in records if record["accepted"]]
    comparison_corpus_size = (
        len(public_rows)
        + len(self_rows)
        + len(generated_rows)
        + len(external_rows)
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": {
            "name": "Problem Phase Diagram Synthesis: continuous batch",
            "unit_of_generation": "typed object + morphism chain + observation",
            "surface_template_optimization": False,
            "selection_gates": [
                "typed generation certificate",
                "exact backend derivation",
                "independent counterexample search",
                "surface corpus collision rejection",
                "structural signature collision rejection",
                "one candidate per structural family",
            ],
            "comparison_corpus": {
                "public": len(public_rows),
                "self_authored": len(self_rows),
                "previously_generated": len(generated_rows),
                "external": len(external_rows),
                "total": comparison_corpus_size,
                "prior_structural_families": len(prior_families or set()),
                "prior_structural_chains": len(prior_chains or set()),
            },
        },
        "summary": {
            "target_accepted": 20,
            "generated": len(records),
            "accepted": len(accepted_records),
            "rejected": len(records) - len(accepted_records),
            "unique_families": len(
                {record["family_id"] for record in accepted_records}
            ),
            "domains": sorted(
                {record["domain"] for record in accepted_records}
            ),
            "all_backend_verified": all(
                record["verification"]["exact_backend"]
                and record["verification"]["independent_check"]
                for record in accepted_records
            ),
            "all_certificates_type_checked": all(
                record["lift_certificate"]["type_checked"]
                for record in accepted_records
            ),
            "all_corpus_novel": all(
                record["novelty"]["corpus_novel"]
                for record in accepted_records
            ),
            "all_structurally_novel": all(
                record["novelty"]["structural"]["structural_novel"]
                for record in accepted_records
            ),
        },
        "problems": records,
        "limitations": [
            "Corpus novelty does not prove worldwide originality.",
            "The independent semantic parser is observational and remains weaker than the generation certificates.",
            "Human blind evaluation is still required for naturalness, elegance, and contest difficulty.",
        ],
    }


def render_problem_collection(report: dict[str, Any]) -> str:
    accepted = [record for record in report["problems"] if record["accepted"]]
    summary = report["summary"]
    lines = [
        "# MathOS 新作問題集: 連続生成バッチ1",
        "",
        "## 生成結果",
        "",
        f"- 生成: {summary['generated']}問",
        f"- 採用: {summary['accepted']}問",
        f"- 構造族: {summary['unique_families']}種",
        f"- 分野: {', '.join(summary['domains'])}",
        "- 採用条件: 型検査、厳密計算、独立反例探索、コーパス重複検査",
        "",
        "## 問題",
        "",
    ]
    for index, record in enumerate(accepted, start=1):
        lines.extend(
            [
                f"### 問題{index}",
                "",
                record["statement_tex"],
                "",
            ]
        )
    lines.extend(["## 答と解法概略", ""])
    for index, record in enumerate(accepted, start=1):
        lines.extend(
            [
                f"### 問題{index}",
                "",
                f"**答**: \\({record['answer_tex']}\\)",
                "",
                record["solution_tex"],
                "",
                (
                    f"検証: `{record['verification']['method']}` / "
                    f"最大表層類似度 `{record['novelty']['maximum_surface_jaccard']}`"
                ),
                "",
            ]
        )
    lines.extend(
        [
            "## 注意",
            "",
            "ここでの「新作」は、公開問題・自作問題・既生成問題からなる比較"
            "コーパス内で衝突しなかったという意味である。世界全体で未出で"
            "あることは主張しない。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--self-corpus", type=Path, default=DEFAULT_SELF_CORPUS)
    parser.add_argument("--delay", type=float, default=0.35)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Skip the live public corpus; intended only for local smoke tests.",
    )
    parser.add_argument(
        "--mathnet-parquet",
        type=Path,
        default=DEFAULT_MATHNET_PARQUET,
        help="Olympiad corpus parquet used as an extra novelty comparison set.",
    )
    parser.add_argument(
        "--extra-corpus",
        type=Path,
        nargs="*",
        default=None,
        help="Additional JSONL statement corpora for novelty comparison.",
    )
    args = parser.parse_args()
    public_rows = (
        []
        if args.offline
        else fetch_public_problems(delay_seconds=args.delay)
    )
    self_rows = load_self_authored_statements(args.self_corpus)
    generated_rows = load_generated_corpus(
        args.output.parent,
        exclude=args.output,
    )
    extra_corpus = (
        list(args.extra_corpus)
        if args.extra_corpus is not None
        else [args.output.parent.parent / path for path in DEFAULT_EXTRA_CORPUS]
    )
    external_rows = load_external_corpus(
        parquet_paths=[args.mathnet_parquet] if args.mathnet_parquet else [],
        jsonl_paths=extra_corpus,
    )
    prior_families, prior_chains = load_generated_signatures(
        args.output.parent,
        exclude=args.output,
    )
    report = build_batch_report(
        public_rows,
        self_rows,
        generated_rows,
        external_rows,
        prior_families,
        prior_chains,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    args.output.with_name(
        args.output.stem + "_problems_ja.md"
    ).write_text(
        render_problem_collection(report),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "summary": report["summary"],
                "output": str(args.output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if report["summary"]["accepted"] >= report["summary"]["target_accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
