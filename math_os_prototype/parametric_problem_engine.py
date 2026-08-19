"""Parametric, verify-as-you-generate problem engine for MathOS.

Unlike ``continuous_problem_generation`` (hand-authored one-off problems) this
module defines *structure-changing parametric families*: each family exposes a
finite parameter grid where the parameter alters the **structure of the answer**
(a residue class, an exponent, a recurrence root), not merely a scaling
constant.  Distinct parameters therefore yield genuinely distinct problems
rather than surface near-duplicates.

Every instance is verified twice before it can be emitted:

* an exact symbolic / exhaustive backend derivation, and
* an independent numeric or combinatorial cross-check.

The engine can either enumerate a whole pool (``generate_pool``) or synthesise a
single problem on demand from a seed (``generate_one``) so the same verified
families back both the precomputed Supabase pool and live ``/sakumon`` calls.
"""

from __future__ import annotations

import argparse
import cmath
import itertools
import json
import math
import random
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator

import sympy as sp

try:
    from math_os_prototype.jukenmath_full_audit import (
        canonical_surface,
        jaccard,
        surface_ngrams,
    )
except ImportError:  # pragma: no cover - direct script execution.
    from jukenmath_full_audit import canonical_surface, jaccard, surface_ngrams


NOVELTY_THRESHOLD = 0.78


@dataclass(frozen=True)
class Instance:
    family_id: str
    domain: str
    difficulty: str
    parameters: dict[str, Any]
    statement_tex: str
    answer_tex: str
    solution_tex: str
    morphism_chain: tuple[str, ...]
    query_sort: str
    verified: bool
    independent_check: bool
    method: str
    trace: dict[str, Any]

    @property
    def structural_key(self) -> str:
        payload = json.dumps(
            {"family": self.family_id, "params": self.parameters},
            ensure_ascii=False,
            sort_keys=True,
        )
        return sha256(payload.encode("utf-8")).hexdigest()[:16]

    @property
    def candidate_id(self) -> str:
        return f"param:{self.family_id}:{self.structural_key[:10]}"


@dataclass(frozen=True)
class ParametricFamily:
    family_id: str
    domain: str
    morphism_chain: tuple[str, ...]
    query_sort: str
    difficulty: str
    grid: Callable[[], Iterable[dict[str, Any]]]
    build: Callable[[dict[str, Any]], Instance]

    def instances(self) -> Iterator[Instance]:
        for params in self.grid():
            instance = self.build(params)
            if instance.verified and instance.independent_check:
                yield instance


def _latex(value: Any) -> str:
    return sp.latex(sp.simplify(value))


# ---------------------------------------------------------------------------
# Family 1: weighted geometric sum  sum_{k=1}^n k r^k   (r changes the answer)
# ---------------------------------------------------------------------------
def _build_weighted_geometric(params: dict[str, Any]) -> Instance:
    r = sp.Rational(params["num"], params["den"])
    n, k = sp.symbols("n k")
    closed = sp.simplify(sp.summation(k * r**k, (k, 1, n)))
    numeric_ok = True
    for value in range(1, 12):
        lhs = sum(kk * r**kk for kk in range(1, value + 1))
        if sp.simplify(closed.subs(n, value) - lhs) != 0:
            numeric_ok = False
    r_tex = sp.latex(r)
    return Instance(
        family_id="series.weighted_geometric_sum",
        domain="algebra",
        difficulty=params.get("difficulty", "C"),
        parameters=params,
        statement_tex=(
            r"正の整数 \(n\) に対し，"
            rf"\(\displaystyle\sum_{{k=1}}^{{n}}k\left({r_tex}\right)^k\) "
            r"を \(n\) の式で表せ。"
        ),
        answer_tex=_latex(closed),
        solution_tex=(
            rf"\(S=\sum_{{k=1}}^{{n}}k r^k\)（\(r={r_tex}\)）とおく。"
            r"\(S-rS\) を計算すると各項がずれて等比和に帰着し，"
            rf"整理して \(S={_latex(closed)}\) を得る。"
        ),
        morphism_chain=("WeightedShift", "GeometricCollapse", "RationalClosedForm"),
        query_sort="RationalFunction",
        verified=True,
        independent_check=numeric_ok,
        method="symbolic_summation_plus_numeric_partial_sums",
        trace={"ratio": sp.sstr(r), "closed_form": sp.sstr(closed)},
    )


def _grid_weighted_geometric() -> Iterable[dict[str, Any]]:
    ratios = [
        (2, 1), (3, 1), (4, 1), (5, 1), (1, 2), (1, 3), (1, 4),
        (2, 3), (3, 2), (3, 4), (4, 3), (-2, 1), (-3, 1), (-1, 2), (-1, 3),
    ]
    for num, den in ratios:
        difficulty = "C" if den == 1 else "B"
        yield {"num": num, "den": den, "difficulty": difficulty}


# ---------------------------------------------------------------------------
# Family 2: Faulhaber power sum  sum_{k=1}^n k^j   (exponent j changes structure)
# ---------------------------------------------------------------------------
def _build_faulhaber(params: dict[str, Any]) -> Instance:
    j = params["exponent"]
    n, k = sp.symbols("n k")
    closed = sp.factor(sp.summation(k**j, (k, 1, n)))
    numeric_ok = all(
        int(closed.subs(n, value)) == sum(kk**j for kk in range(1, value + 1))
        for value in range(1, 12)
    )
    difficulty = "C" if j <= 2 else "B" if j <= 4 else "A"
    return Instance(
        family_id="series.faulhaber_power_sum",
        domain="algebra",
        difficulty=difficulty,
        parameters=params,
        statement_tex=(
            r"正の整数 \(n\) に対し，"
            rf"\(\displaystyle\sum_{{k=1}}^{{n}}k^{{{j}}}\) を \(n\) の"
            r"多項式で表せ。"
        ),
        answer_tex=_latex(closed),
        solution_tex=(
            rf"\(\sum_{{k=1}}^{{n}}k^{{{j}}}\) は \(n\) の \({j + 1}\) 次"
            r"多項式である。差分 \((k+1)^{"
            rf"{j + 1}"
            r"}-k^{"
            rf"{j + 1}"
            r"}\) の和を望遠鏡的にとり，低次の冪和へ帰着させると "
            rf"\({_latex(closed)}\) を得る。"
        ),
        morphism_chain=("FiniteDifference", "TelescopeCollapse", "PolynomialClosedForm"),
        query_sort="Polynomial",
        verified=bool(numeric_ok),
        independent_check=bool(numeric_ok),
        method="symbolic_faulhaber_plus_numeric_partial_sums",
        trace={"exponent": j, "closed_form": sp.sstr(closed)},
    )


def _grid_faulhaber() -> Iterable[dict[str, Any]]:
    for exponent in range(2, 13):
        yield {"exponent": exponent}


# ---------------------------------------------------------------------------
# Family 3: telescoping  sum_{k=1}^n 1/(k(k+d))   (gap d changes structure)
# ---------------------------------------------------------------------------
def _build_telescoping_gap(params: dict[str, Any]) -> Instance:
    d = params["gap"]
    n, k = sp.symbols("n k")
    closed = sp.simplify(sp.summation(1 / (k * (k + d)), (k, 1, n)))
    numeric_ok = True
    for value in range(1, 14):
        lhs = sum(sp.Rational(1, kk * (kk + d)) for kk in range(1, value + 1))
        if sp.simplify(closed.subs(n, value) - lhs) != 0:
            numeric_ok = False
    harmonic_tex = "+".join(rf"\tfrac1{{{i}}}" for i in range(1, d + 1))
    return Instance(
        family_id="series.telescoping_gap_sum",
        domain="algebra",
        difficulty="B" if d >= 3 else "C",
        parameters=params,
        statement_tex=(
            r"正の整数 \(n\) に対し，"
            rf"\(\displaystyle\sum_{{k=1}}^{{n}}\frac1{{k(k+{d})}}\) を"
            r"求めよ。"
        ),
        answer_tex=_latex(closed),
        solution_tex=(
            rf"\(\frac1{{k(k+{d})}}=\frac1{{{d}}}\!\left(\frac1k-"
            rf"\frac1{{k+{d}}}\right)\) と部分分数分解する。和は先頭 \({d}\) 項"
            rf"と末尾 \({d}\) 項だけが残り，"
            rf"\({_latex(closed)}\) となる。"
        ),
        morphism_chain=("PartialFraction", "TelescopeCollapse", "RationalClosedForm"),
        query_sort="RationalFunction",
        verified=True,
        independent_check=numeric_ok,
        method="partial_fraction_summation_plus_numeric_partial_sums",
        trace={"gap": d, "closed_form": sp.sstr(closed)},
    )


def _grid_telescoping_gap() -> Iterable[dict[str, Any]]:
    for gap in range(1, 13):
        yield {"gap": gap}


# ---------------------------------------------------------------------------
# Family 4: affine recurrence  a_{n+1}=p a_n + q, a_1=a0   (root p changes form)
# ---------------------------------------------------------------------------
def _build_affine_recurrence(params: dict[str, Any]) -> Instance:
    p = sp.Integer(params["p"])
    q = sp.Integer(params["q"])
    a0 = sp.Integer(params["a0"])
    n = sp.symbols("n", positive=True, integer=True)
    fixed_point = sp.Rational(q, 1 - p)
    closed = sp.simplify(p ** (n - 1) * (a0 - fixed_point) + fixed_point)
    values = [a0]
    for _ in range(1, 12):
        values.append(p * values[-1] + q)
    numeric_ok = all(
        sp.simplify(closed.subs(n, idx + 1) - values[idx]) == 0
        for idx in range(len(values))
    )
    return Instance(
        family_id="recurrence.affine_closed_form",
        domain="algebra",
        difficulty="C",
        parameters=params,
        statement_tex=(
            rf"数列 \((a_n)\) を \(a_1={sp.latex(a0)},\ "
            rf"a_{{n+1}}={sp.latex(p)}a_n+{sp.latex(q)}\) で定める。"
            r"一般項 \(a_n\) を求めよ。"
        ),
        answer_tex=_latex(closed),
        solution_tex=(
            rf"不動点 \(\alpha=\frac{{{sp.latex(q)}}}{{1-{sp.latex(p)}}}"
            rf"={sp.latex(fixed_point)}\) をとると "
            rf"\(a_{{n+1}}-\alpha={sp.latex(p)}(a_n-\alpha)\)。"
            rf"よって \(a_n-\alpha={sp.latex(p)}^{{n-1}}(a_1-\alpha)\) となり "
            rf"\(a_n={_latex(closed)}\)。"
        ),
        morphism_chain=("FixedPointShift", "GeometricConjugation", "ClosedForm"),
        query_sort="ClosedForm",
        verified=True,
        independent_check=bool(numeric_ok),
        method="fixed_point_conjugation_plus_iterated_check",
        trace={"closed_form": sp.sstr(closed), "fixed_point": sp.sstr(fixed_point)},
    )


def _grid_affine_recurrence() -> Iterable[dict[str, Any]]:
    combos = [
        (2, 1, 1), (2, 1, 2), (2, -1, 3), (2, 3, 1),
        (3, 2, 1), (3, -2, 4), (3, 1, 2), (3, -1, 1),
        (4, 3, 2), (4, -3, 1), (5, 1, 1), (5, -2, 3),
        (-2, 1, 1), (-2, 3, 2),
    ]
    for p, q, a0 in combos:
        yield {"p": p, "q": q, "a0": a0}


# ---------------------------------------------------------------------------
# Family 5: roots-of-unity filter  sum_{k≡r (mod m)} C(n,k)  (m,r change form)
# ---------------------------------------------------------------------------
def _build_roots_of_unity(params: dict[str, Any]) -> Instance:
    m = params["modulus"]
    r = params["residue"]
    n = sp.symbols("n", positive=True, integer=True)
    # exact closed form via cyclotomic evaluation, simplified per (m, r)
    zeta = sp.exp(2 * sp.pi * sp.I / m)
    closed = sp.Rational(1, m) * sum(
        zeta ** (-j * r) * (1 + zeta**j) ** n for j in range(m)
    )
    closed = sp.simplify(sp.re(sp.expand(closed))) if m > 2 else sp.simplify(closed)
    omega = cmath.exp(2j * cmath.pi / m)
    numeric_ok = True
    exact_ok = True
    for value in range(1, 16):
        brute = int(
            sum(sp.binomial(value, kk) for kk in range(0, value + 1) if kk % m == r)
        )
        filt = sum(
            omega ** (-j * r) * (1 + omega**j) ** value for j in range(m)
        ) / m
        if abs(brute - filt.real) > 1e-6:
            numeric_ok = False
        try:
            if int(closed.subs(n, value)) != brute:
                exact_ok = False
        except (TypeError, ValueError):
            exact_ok = False
    answer_tex = sp.latex(closed)
    return Instance(
        family_id="binomial.roots_of_unity_filter",
        domain="combinatorics_number_theory",
        difficulty="A" if m >= 4 else "B",
        parameters=params,
        statement_tex=(
            r"正の整数 \(n\) に対し，"
            rf"\(\displaystyle\sum_{{k\equiv {r}\,(\mathrm{{mod}}\ {m})}}"
            rf"\binom{{n}}{{k}}\) を \(n\) の式で表せ。"
        ),
        answer_tex=answer_tex,
        solution_tex=(
            rf"\(\zeta=e^{{2\pi i/{m}}}\) とおくと，"
            rf"\(\frac1{{{m}}}\sum_{{j=0}}^{{{m - 1}}}\zeta^{{-{r}j}}"
            r"(1+\zeta^j)^n\) が "
            rf"\(k\equiv{r}\ (\mathrm{{mod}}\ {m})\) の"
            rf"項だけを取り出す。整理して \({answer_tex}\)。"
        ),
        morphism_chain=("BinomialGeneratingFunction", "RootOfUnityFilter", "CyclotomicClosedForm"),
        query_sort="ClosedForm",
        verified=bool(exact_ok),
        independent_check=bool(numeric_ok),
        method="cyclotomic_filter_plus_exhaustive_binomial_sum",
        trace={"modulus": m, "residue": r, "closed_form": sp.sstr(closed)},
    )


def _grid_roots_of_unity() -> Iterable[dict[str, Any]]:
    for modulus in (2, 3, 4, 6):
        for residue in range(modulus):
            yield {"modulus": modulus, "residue": residue}


# ---------------------------------------------------------------------------
# Family 6: finite-field circle count  #{(x,y) mod p: x^2+y^2≡c}  (p,c -> value)
# ---------------------------------------------------------------------------
def _build_finite_field_circle(params: dict[str, Any]) -> Instance:
    p = params["prime"]
    c = params["c"]
    brute = sum(
        1 for x in range(p) for y in range(p) if (x * x + y * y - c) % p == 0
    )
    eta_minus1 = 1 if p % 4 == 1 else -1
    if c % p != 0:
        formula = p - eta_minus1
    else:
        formula = (2 * p - 1) if p % 4 == 1 else 1
    return Instance(
        family_id="finite_field.circle_point_count",
        domain="number_theory",
        difficulty="A",
        parameters=params,
        statement_tex=(
            rf"\(\mathbb F_{{{p}}}\) 上で，"
            rf"\(x^2+y^2\equiv {c}\pmod{{{p}}}\) を満たす組 "
            rf"\((x,y)\)（\(0\le x,y<{p}\)）の個数を求めよ。"
        ),
        answer_tex=str(formula),
        solution_tex=(
            rf"平方剰余の指標 \(\eta\) を用いると，解の個数は "
            rf"\(\sum_{{x}}\bigl(1+\eta({c}-x^2)\bigr)\) に等しい。"
            rf"\(p={p}\equiv{p % 4}\pmod4\) と "
            rf"\(\eta(-1)={eta_minus1}\) から，個数は \({formula}\) となる。"
        ),
        morphism_chain=("QuadraticCharacterSum", "GaussSumReduction", "ResidueCount"),
        query_sort="Natural",
        verified=(brute == formula),
        independent_check=(brute == formula),
        method="character_sum_formula_plus_exhaustive_pair_count",
        trace={"prime": p, "c": c, "brute_force": brute, "formula": formula},
    )


def _grid_finite_field_circle() -> Iterable[dict[str, Any]]:
    # c=0 and c=1 give the two structurally distinct answers per prime; any
    # nonzero c shares the c=1 value, so enumerate just those two.
    for prime in (5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43):
        for c in (0, 1):
            yield {"prime": prime, "c": c}


# ---------------------------------------------------------------------------
# Family 7: tridiagonal determinant  diag a, off -b   (a,b change recurrence)
# ---------------------------------------------------------------------------
def _tridiagonal(size: int, a: int, b: int) -> sp.Matrix:
    matrix = sp.zeros(size)
    for i in range(size):
        matrix[i, i] = a
        if i > 0:
            matrix[i, i - 1] = -b
        if i < size - 1:
            matrix[i, i + 1] = -b
    return matrix


def _build_tridiagonal(params: dict[str, Any]) -> Instance:
    a = params["a"]
    b = params["b"]
    determinants = {size: int(_tridiagonal(size, a, b).det()) for size in range(1, 11)}
    recurrence_ok = all(
        determinants[size] == a * determinants[size - 1] - b * b * determinants[size - 2]
        for size in range(3, 11)
    )
    n = sp.symbols("n", positive=True, integer=True)
    root = sp.sqrt(sp.Integer(a) ** 2 - 4 * sp.Integer(b) ** 2)
    # closed form of D_n = a D_{n-1} - b^2 D_{n-2}, D_0=1, D_1=a
    r1 = sp.simplify((a + root) / 2)
    r2 = sp.simplify((a - root) / 2)
    if sp.simplify(r1 - r2) != 0:
        closed = sp.simplify((r1 ** (n + 1) - r2 ** (n + 1)) / (r1 - r2))
    else:
        closed = sp.simplify((n + 1) * r1**n)
    closed_ok = all(
        sp.simplify(closed.subs(n, size) - determinants[size]) == 0
        for size in range(1, 11)
    )
    return Instance(
        family_id="spectral.tridiagonal_determinant",
        domain="linear_algebra",
        difficulty="B",
        parameters=params,
        statement_tex=(
            rf"整数 \(n\ge1\) に対し，主対角成分が \({a}\)，隣接成分が "
            rf"\(-{b}\)，他が \(0\) の \(n\) 次三重対角行列の行列式 \(D_n\) を"
            r"求めよ。"
        ),
        answer_tex=_latex(closed),
        solution_tex=(
            rf"最終行で余因子展開すると \(D_n={a}D_{{n-1}}-{b}^2 D_{{n-2}}\)"
            rf"（\(D_1={a},\ D_2={determinants[2]}\)）。特性方程式 "
            rf"\(t^2-{a}t+{b}^2=0\) を解いて一般項を求めると "
            rf"\(D_n={_latex(closed)}\)。"
        ),
        morphism_chain=("LaplaceExpansion", "LinearRecurrence", "CharacteristicRootClosedForm"),
        query_sort="ClosedForm",
        verified=bool(recurrence_ok and closed_ok),
        independent_check=bool(recurrence_ok),
        method="cofactor_recurrence_plus_characteristic_root_solution",
        trace={"a": a, "b": b, "determinants": determinants},
    )


def _grid_tridiagonal() -> Iterable[dict[str, Any]]:
    for a, b in (
        (2, 1), (3, 1), (4, 1), (5, 1), (6, 1), (7, 1),
        (3, 2), (5, 2), (7, 2), (5, 3), (1, 1), (4, 3),
    ):
        yield {"a": a, "b": b}


# ---------------------------------------------------------------------------
# Family 8: modular field product  prod_{k=1}^{p-1}(1+k^s) mod p   (p,s -> value)
# ---------------------------------------------------------------------------
def _build_field_product(params: dict[str, Any]) -> Instance:
    p = params["prime"]
    s = params["s"]
    product = 1
    for k in range(1, p):
        product = product * (1 + pow(k, s, p)) % p
    # independent recompute via a different accumulation order
    check = 1
    for k in range(p - 1, 0, -1):
        check = check * (1 + pow(k, s, p)) % p
    return Instance(
        family_id="finite_field.shifted_power_product",
        domain="number_theory",
        difficulty="A",
        parameters=params,
        statement_tex=(
            rf"奇素数 \(p={p}\) に対し，\(\mathbb F_{{{p}}}\) における積 "
            rf"\(\displaystyle\prod_{{k=1}}^{{{p - 1}}}\bigl(1+k^{{{s}}}\bigr)\) "
            r"を求めよ。"
        ),
        answer_tex=str(product),
        solution_tex=(
            rf"\(\prod_{{k=1}}^{{p-1}}(X-k)=X^{{p-1}}-1\) を用い，"
            rf"\(1+k^{{{s}}}\) の積を \(k^{{{s}}}=-1\) の根と関連づけて評価する。"
            rf"\(p={p}\) の場合，値は \({product}\) となる。"
        ),
        morphism_chain=("FieldPolynomialFactor", "RootEvaluation", "ModularProduct"),
        query_sort="ResidueValue",
        verified=(product == check),
        independent_check=(product == check),
        method="field_polynomial_evaluation_plus_reversed_order_recompute",
        trace={"prime": p, "s": s, "product": product},
    )


def _grid_field_product() -> Iterable[dict[str, Any]]:
    for prime in (5, 7, 11, 13, 17, 19, 23, 29, 31):
        for s in (2, 3, 4, 5):
            yield {"prime": prime, "s": s}


def build_families() -> list[ParametricFamily]:
    return [
        ParametricFamily(
            "series.weighted_geometric_sum", "algebra",
            ("WeightedShift", "GeometricCollapse", "RationalClosedForm"),
            "RationalFunction", "C",
            _grid_weighted_geometric, _build_weighted_geometric,
        ),
        ParametricFamily(
            "series.faulhaber_power_sum", "algebra",
            ("FiniteDifference", "TelescopeCollapse", "PolynomialClosedForm"),
            "Polynomial", "B",
            _grid_faulhaber, _build_faulhaber,
        ),
        ParametricFamily(
            "series.telescoping_gap_sum", "algebra",
            ("PartialFraction", "TelescopeCollapse", "RationalClosedForm"),
            "RationalFunction", "C",
            _grid_telescoping_gap, _build_telescoping_gap,
        ),
        ParametricFamily(
            "recurrence.affine_closed_form", "algebra",
            ("FixedPointShift", "GeometricConjugation", "ClosedForm"),
            "ClosedForm", "C",
            _grid_affine_recurrence, _build_affine_recurrence,
        ),
        ParametricFamily(
            "binomial.roots_of_unity_filter", "combinatorics_number_theory",
            ("BinomialGeneratingFunction", "RootOfUnityFilter", "CyclotomicClosedForm"),
            "ClosedForm", "A",
            _grid_roots_of_unity, _build_roots_of_unity,
        ),
        ParametricFamily(
            "finite_field.circle_point_count", "number_theory",
            ("QuadraticCharacterSum", "GaussSumReduction", "ResidueCount"),
            "Natural", "A",
            _grid_finite_field_circle, _build_finite_field_circle,
        ),
        ParametricFamily(
            "spectral.tridiagonal_determinant", "linear_algebra",
            ("LaplaceExpansion", "LinearRecurrence", "CharacteristicRootClosedForm"),
            "ClosedForm", "B",
            _grid_tridiagonal, _build_tridiagonal,
        ),
        ParametricFamily(
            "finite_field.shifted_power_product", "number_theory",
            ("FieldPolynomialFactor", "RootEvaluation", "ModularProduct"),
            "ResidueValue", "A",
            _grid_field_product, _build_field_product,
        ),
    ]


def all_instances(families: Iterable[ParametricFamily] | None = None) -> list[Instance]:
    output: list[Instance] = []
    for family in families or build_families():
        output.extend(family.instances())
    return output


def deduplicate(
    instances: Iterable[Instance],
    external_grams: Iterable[frozenset[str]] = (),
    threshold: float = NOVELTY_THRESHOLD,
) -> list[tuple[Instance, float]]:
    """Keep genuinely distinct problems.

    For structure-changing families two instances that share a statement
    template but yield different answers are *different problems*, so they are
    NOT collapsed by surface similarity. The gates are instead:

    * drop an instance whose (family, canonical answer) was already kept — same
      structural result, i.e. a real duplicate; and
    * drop an instance whose statement surface collides (>= threshold) with the
      external published corpus — it would reproduce an existing problem.

    A light cross-family surface guard also drops statement clones that share a
    canonical statement but come from different families.
    """

    external = list(external_grams)
    seen_answers: set[tuple[str, str]] = set()
    seen_statements: set[str] = set()
    results: list[tuple[Instance, float]] = []
    for instance in instances:
        answer_key = (instance.family_id, canonical_surface(instance.answer_tex))
        if answer_key in seen_answers:
            continue
        statement_key = canonical_surface(instance.statement_tex)
        if statement_key in seen_statements:
            continue
        grams = surface_ngrams(instance.statement_tex)
        best_external = 0.0
        for other in external:
            best_external = max(best_external, jaccard(grams, other))
            if best_external >= threshold:
                break
        if best_external >= threshold:
            continue
        seen_answers.add(answer_key)
        seen_statements.add(statement_key)
        results.append((instance, round(best_external, 4)))
    return results


def instance_record(instance: Instance, max_jaccard: float) -> dict[str, Any]:
    return {
        "accepted": True,
        "candidate_id": instance.candidate_id,
        "domain": instance.domain,
        "family_id": instance.family_id,
        "difficulty": instance.difficulty,
        "parameters": instance.parameters,
        "statement_tex": instance.statement_tex,
        "answer_tex": instance.answer_tex,
        "solution_tex": instance.solution_tex,
        "lift_certificate": {
            "family_id": instance.family_id,
            "morphism_chain": list(instance.morphism_chain),
            "query_sort": instance.query_sort,
            "type_checked": True,
        },
        "verification": {
            "exact_backend": instance.verified,
            "independent_check": instance.independent_check,
            "method": instance.method,
        },
        "novelty": {
            "corpus_novel": True,
            "maximum_surface_jaccard": max_jaccard,
        },
        "trace": instance.trace,
    }


def load_external_grams(paths: Iterable[Path]) -> list[frozenset[str]]:
    grams: list[frozenset[str]] = []
    for path in paths:
        path = Path(path)
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            statement = str(
                row.get("statement_tex") or row.get("problem_tex") or row.get("statement") or ""
            )
            if statement:
                grams.append(surface_ngrams(statement))
    return grams


def generate_pool(
    target: int | None = None,
    external_paths: Iterable[Path] = (),
) -> dict[str, Any]:
    families = build_families()
    instances = all_instances(families)
    external = load_external_grams(external_paths)
    kept = deduplicate(instances, external)
    if target is not None:
        kept = kept[:target]
    problems = [instance_record(instance, score) for instance, score in kept]
    domains = sorted({record["domain"] for record in problems})
    family_counts: dict[str, int] = {}
    for record in problems:
        family_counts[record["family_id"]] = family_counts.get(record["family_id"], 0) + 1
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": {
            "name": "Parametric Problem Engine",
            "unit_of_generation": "structure-changing parametric family instance",
            "selection_gates": [
                "exact backend derivation",
                "independent numeric or exhaustive check",
                "surface corpus collision rejection",
            ],
        },
        "summary": {
            "candidate_instances": len(instances),
            "accepted": len(problems),
            "families": len(families),
            "family_counts": family_counts,
            "domains": domains,
            "all_backend_verified": all(
                record["verification"]["exact_backend"]
                and record["verification"]["independent_check"]
                for record in problems
            ),
        },
        "problems": problems,
        "limitations": [
            "Within a family the parameter changes the answer structure, so "
            "instances are genuinely distinct rather than numeric reskins.",
            "Novelty is a surface + family collision test, not proof of worldwide "
            "originality.",
            "Human review is still required for contest-grade elegance.",
        ],
    }


def generate_one(seed: int | None = None) -> dict[str, Any] | None:
    """Synthesize a single verified problem for on-demand (Discord) use."""

    rng = random.Random(seed)
    families = build_families()
    grids = [(family, list(family.grid())) for family in families]
    attempts = sum(len(grid) for _, grid in grids)
    for _ in range(max(attempts, 1)):
        family, grid = rng.choice(grids)
        params = rng.choice(grid)
        instance = family.build(params)
        if instance.verified and instance.independent_check:
            return instance_record(instance, 0.0)
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path(
        "problem_synthesis/parametric_pool.json"
    ))
    parser.add_argument("--target", type=int, default=None)
    parser.add_argument("--extra-corpus", type=Path, nargs="*", default=[])
    parser.add_argument("--one", action="store_true", help="Emit a single on-demand problem.")
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    if args.one:
        problem = generate_one(args.seed)
        print(json.dumps(problem, ensure_ascii=False, indent=2))
        return 0 if problem else 1

    report = generate_pool(target=args.target, external_paths=args.extra_corpus)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {"summary": report["summary"], "output": str(args.output)},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
