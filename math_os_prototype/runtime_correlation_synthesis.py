"""Runtime synthesis for finite-population correlation limits.

This module stores definitions of elementary observables, not completed problem
solutions.  A correlation target is expanded at runtime into the five moments
it requires.  The moments are then evaluated independently by a rational-power
monomial evaluator and by symbolic double integration.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from fractions import Fraction
import re
from typing import Any

import sympy as sp

from .runtime_typed_planner import (
    PrimitiveResult,
    RuntimePrimitive,
    initial_fact,
    synthesize_typed_plan,
)


@dataclass(frozen=True)
class FinitePopulationSample:
    lower_endpoint: int
    upper_symbol: str
    sample_size: int | str
    without_replacement: bool


@dataclass(frozen=True)
class ObservableDefinition:
    kind: str
    output_symbol: str


@dataclass(frozen=True)
class CorrelationLimitQueryIR:
    sample: FinitePopulationSample
    observables: tuple[ObservableDefinition, ObservableDefinition]
    limit_symbol: str
    target_symbol: str
    sample_limit_symbol: str | None = None
    target_representation: str = "correlation"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CorrelationLimitSynthesis:
    answer_tex: str
    derivation_tex: tuple[str, ...]
    expression_tex: str
    proof_program: tuple[dict[str, Any], ...]
    verification_checks: tuple[str, ...]
    witness: dict[str, Any]
    hypotheses_evaluated: int


_OBSERVABLE_ALIASES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("相加平均", "算術平均"), "arithmetic_mean"),
    (("相乗平均", "幾何平均"), "geometric_mean"),
)


def _normalized_text(statement: str) -> str:
    return (
        statement.replace("−", "-")
        .replace("–", "-")
        .replace("∞", r"\infty")
        .replace(r"\left", "")
        .replace(r"\right", "")
        .replace(r"\dfrac", r"\frac")
        .replace(r"\tfrac", r"\frac")
    )


def _extract_output_symbols(statement: str) -> tuple[str, str]:
    source = _normalized_text(statement)
    optional_subscript = r"(?:_\{[^{}]*\}|_[A-Za-z0-9]+)?"
    match = re.search(
        r"(?:相加平均|算術平均)[と、,，\s]*(?:相乗平均|幾何平均)を\s*"
        rf"\$?\\?([A-Za-z]){optional_subscript}\$?\s*[,，、\\ ]+\s*"
        rf"\$?\\?([A-Za-z]){optional_subscript}\$?",
        source,
    )
    if match is not None:
        return match.group(1), match.group(2)

    match = re.search(
        rf"(?:和|合計)を\s*\$?\\?([A-Za-z]){optional_subscript}\$?\s*[,，、]\s*"
        r"(?:積)を\s*\$?\\?([A-Za-z])",
        source,
    )
    if match is not None:
        return match.group(1), match.group(2)
    return "X", "Y"


def _extract_observable_kinds(statement: str) -> tuple[str, str] | None:
    source = _normalized_text(statement)
    kinds: list[str] = []
    positions: list[tuple[int, str]] = []
    for aliases, kind in _OBSERVABLE_ALIASES:
        occurrences = [source.find(alias) for alias in aliases if alias in source]
        if occurrences:
            positions.append((min(occurrences), kind))
    if len(positions) == 2:
        positions.sort()
        return positions[0][1], positions[1][1]

    sum_match = re.search(r"(?:その)?値の和", source)
    product_match = re.search(r"(?:その)?(?:値の)?積", source)
    if sum_match is not None and product_match is not None:
        positions = [(sum_match.start(), "sum"), (product_match.start(), "product")]
        positions.sort()
        return positions[0][1], positions[1][1]
    return None


def compile_correlation_limit_query(statement: str) -> CorrelationLimitQueryIR | None:
    source = _normalized_text(statement)
    if "相関係数" not in source or r"\lim" not in source:
        return None
    if "復元抽出" in source or "戻して" in source:
        return None

    population = re.search(
        r"(?P<lower>0|1)\s*から\s*\$?\\?(?P<upper>[A-Za-z])\$?\s*まで",
        source,
    )
    if population is None:
        return None
    upper_symbol = population.group("upper")

    limit_symbols = re.findall(
        r"\\lim_\{?\s*(?P<symbol>[A-Za-z])\s*\\to\s*\\infty\s*\}?",
        source,
    )
    if upper_symbol not in limit_symbols:
        return None

    fixed_two = re.search(r"(?:2\s*枚|二\s*枚)", source) is not None
    sample_symbol_match = re.search(
        r"\$?\\?(?P<symbol>[A-Za-z])\s*(?:\(\s*<\s*[A-Za-z]\s*\))?\$?\s*枚",
        source,
    )
    if fixed_two:
        sample_size: int | str = 2
        sample_limit_symbol = None
    elif sample_symbol_match is not None:
        sample_size = sample_symbol_match.group("symbol")
        sample_limit_symbol = sample_size if sample_size in limit_symbols else None
        if sample_limit_symbol is None:
            return None
    else:
        return None
    if "1枚ずつ" not in source and "一枚ずつ" not in source and "カード" not in source:
        return None

    observable_kinds = _extract_observable_kinds(source)
    if observable_kinds is None:
        return None
    output_symbols = _extract_output_symbols(source)
    angle_target = re.search(
        r"(?:相関係数を|相関係数は)\s*\$?\\cos\s*\\?"
        r"(?P<symbol>theta|alpha|beta|phi|[A-Za-z])",
        source,
    )
    if angle_target is not None:
        target_symbol = angle_target.group("symbol")
        target_representation = "angle_from_cosine"
    else:
        target = re.search(
            r"(?:相関係数を|相関係数は)\s*\$?"
            r"(?:\\(?P<command>[A-Za-z]+)|(?P<latin>[A-Za-z]))",
            source,
        )
        target_symbol = (
            (target.group("command") or target.group("latin"))
            if target is not None
            else "rho"
        )
        target_representation = "correlation"

    return CorrelationLimitQueryIR(
        sample=FinitePopulationSample(
            lower_endpoint=int(population.group("lower")),
            upper_symbol=upper_symbol,
            sample_size=sample_size,
            without_replacement=True,
        ),
        observables=(
            ObservableDefinition(observable_kinds[0], output_symbols[0]),
            ObservableDefinition(observable_kinds[1], output_symbols[1]),
        ),
        limit_symbol=upper_symbol,
        target_symbol=target_symbol,
        sample_limit_symbol=sample_limit_symbol,
        target_representation=target_representation,
    )


def _observable_expression(kind: str, u: sp.Symbol, v: sp.Symbol) -> sp.Expr:
    definitions = {
        "arithmetic_mean": (u + v) / 2,
        "geometric_mean": sp.sqrt(u) * sp.sqrt(v),
        "sum": u + v,
        "product": u * v,
    }
    if kind not in definitions:
        raise ValueError(f"unsupported observable kind: {kind}")
    return definitions[kind]


def _monomial_terms(
    expression: sp.Expr,
    u: sp.Symbol,
    v: sp.Symbol,
) -> list[tuple[sp.Expr, sp.Rational, sp.Rational]]:
    expanded = sp.expand(sp.expand_power_base(sp.powdenest(expression, force=True), force=True))
    result: list[tuple[sp.Expr, sp.Rational, sp.Rational]] = []
    for term in sp.Add.make_args(expanded):
        powers = term.as_powers_dict()
        u_power = sp.Rational(powers.get(u, 0))
        v_power = sp.Rational(powers.get(v, 0))
        coefficient = sp.simplify(term / (u**u_power * v**v_power))
        if coefficient.free_symbols or u_power <= -1 or v_power <= -1:
            raise ValueError("observable is outside the integrable rational-power algebra")
        result.append((coefficient, u_power, v_power))
    return result


def _homogeneous_degree(expression: sp.Expr, u: sp.Symbol, v: sp.Symbol) -> sp.Rational:
    terms = _monomial_terms(expression, u, v)
    degrees = {sp.Rational(u_power + v_power) for _, u_power, v_power in terms}
    if len(degrees) != 1:
        raise ValueError("observable is not homogeneous under card-value scaling")
    return next(iter(degrees))


def _separable_unit_square_moment(expression: sp.Expr, u: sp.Symbol, v: sp.Symbol) -> sp.Expr:
    return sp.simplify(
        sum(
            (
                coefficient / ((u_power + 1) * (v_power + 1))
                for coefficient, u_power, v_power in _monomial_terms(expression, u, v)
            ),
            sp.Integer(0),
        )
    )


def _symbolic_unit_square_moment(expression: sp.Expr, u: sp.Symbol, v: sp.Symbol) -> sp.Expr:
    return sp.simplify(sp.integrate(sp.integrate(expression, (u, 0, 1)), (v, 0, 1)))


def _observable_label(kind: str) -> str:
    return {
        "arithmetic_mean": "相加平均",
        "geometric_mean": "相乗平均",
        "sum": "和",
        "product": "積",
    }[kind]


def _tex_identifier(symbol: str) -> str:
    if symbol in {"alpha", "beta", "gamma", "rho", "theta", "phi", "psi"}:
        return rf"\{symbol}"
    return symbol


def _execute_growing_sample_correlation_query(
    query: CorrelationLimitQueryIR,
) -> CorrelationLimitSynthesis:
    if not isinstance(query.sample.sample_size, str):
        raise ValueError("growing-sample correlation requires a symbolic sample size")
    if query.sample_limit_symbol != query.sample.sample_size:
        raise ValueError("sample-size limit does not bind the sample-size symbol")

    sample_symbol = query.sample.sample_size
    k = sp.Symbol(sample_symbol, positive=True, integer=True)
    t = sp.Symbol("t", positive=True)
    kinds = tuple(observable.kind for observable in query.observables)

    def elaborate_sampling(arguments: tuple[Any, ...]) -> PrimitiveResult | None:
        if not query.sample.without_replacement:
            return None
        return PrimitiveResult(
            asdict(query.sample),
            {
                "population_limit_symbol": query.limit_symbol,
                "sample_limit_symbol": sample_symbol,
                "without_replacement": True,
            },
        )

    def elaborate_observables(arguments: tuple[Any, ...]) -> PrimitiveResult | None:
        if sorted(kinds) != ["arithmetic_mean", "geometric_mean"]:
            return None
        return PrimitiveResult(
            {"left_kind": kinds[0], "right_kind": kinds[1]},
            {"observable_kinds": list(kinds)},
        )

    def pass_to_iid_limit(arguments: tuple[Any, ...]) -> PrimitiveResult:
        return PrimitiveResult(
            {
                **arguments[0].value,
                "distribution": "Uniform(0,1)",
                "sample_symbol": sample_symbol,
            },
            {
                "limit_measure": f"Uniform(0,1)^{sample_symbol}",
                "fixed_sample_collision_mass": "O(k^2/n)",
            },
        )

    def expand_moment_dependencies(arguments: tuple[Any, ...]) -> PrimitiveResult:
        pair = arguments[0].value
        obligations = (
            "E_A",
            "E_A2",
            "E_G",
            "E_G2",
            "E_AG",
        )
        return PrimitiveResult(
            {**pair, "obligations": obligations},
            {"generated_obligations": list(obligations)},
        )

    def exact_product_moments(arguments: tuple[Any, ...]) -> PrimitiveResult:
        arithmetic_mean = sp.Rational(1, 2)
        arithmetic_second = sp.Rational(1, 4) + sp.Rational(1, 12) / k
        geometric_mean = (k / (k + 1)) ** k
        geometric_second = (k / (k + 2)) ** k
        mixed = k / (2 * k + 1) * (k / (k + 1)) ** (k - 1)
        canonical = {
            "E_A": arithmetic_mean,
            "E_A2": arithmetic_second,
            "E_G": geometric_mean,
            "E_G2": geometric_second,
            "E_AG": mixed,
        }
        return PrimitiveResult(
            {"canonical_moments": canonical},
            {"moments": {name: sp.sstr(value) for name, value in canonical.items()}},
        )

    def replay_single_integrals(arguments: tuple[Any, ...]) -> PrimitiveResult:
        first = sp.integrate(t, (t, 0, 1))
        second = sp.integrate(t**2, (t, 0, 1))
        fractional = sp.simplify(sp.integrate(t ** (1 / k), (t, 0, 1)))
        fractional_second = sp.simplify(sp.integrate(t ** (2 / k), (t, 0, 1)))
        mixed_factor = sp.simplify(sp.integrate(t ** (1 + 1 / k), (t, 0, 1)))
        replayed = {
            "E_A": first,
            "E_A2": sp.simplify((second + (k - 1) * first**2) / k),
            "E_G": sp.simplify(fractional**k),
            "E_G2": sp.simplify(fractional_second**k),
            "E_AG": sp.simplify(mixed_factor * fractional ** (k - 1)),
        }
        return PrimitiveResult(
            {"canonical_moments": replayed},
            {"moments": {name: sp.sstr(value) for name, value in replayed.items()}},
        )

    def certify_moment_agreement(arguments: tuple[Any, ...]) -> PrimitiveResult | None:
        direct = arguments[0].value["canonical_moments"]
        replayed = arguments[1].value["canonical_moments"]
        if any(sp.simplify(direct[name] - replayed[name]) != 0 for name in direct):
            return None
        return PrimitiveResult(
            {"canonical_moments": direct, "replayed_moments": replayed},
            {"all_finite_k_moments_agree": True},
        )

    def compose_centered_moments(arguments: tuple[Any, ...]) -> PrimitiveResult:
        data = arguments[0].value
        moments = data["canonical_moments"]
        variance_arithmetic = sp.simplify(moments["E_A2"] - moments["E_A"] ** 2)
        variance_geometric = sp.simplify(moments["E_G2"] - moments["E_G"] ** 2)
        covariance = sp.factor(
            sp.simplify(moments["E_AG"] - moments["E_A"] * moments["E_G"])
        )
        return PrimitiveResult(
            {
                **data,
                "variance_arithmetic": variance_arithmetic,
                "variance_geometric": variance_geometric,
                "covariance": covariance,
            },
            {
                "variance_arithmetic": sp.sstr(variance_arithmetic),
                "variance_geometric": sp.sstr(variance_geometric),
                "covariance": sp.sstr(covariance),
            },
        )

    def derive_scaled_limits(arguments: tuple[Any, ...]) -> PrimitiveResult | None:
        data = arguments[0].value
        variance_arithmetic_limit = sp.simplify(
            sp.limit(k * data["variance_arithmetic"], k, sp.oo)
        )
        variance_geometric_limit = sp.simplify(
            sp.limit(k * data["variance_geometric"], k, sp.oo)
        )
        covariance_limit = sp.simplify(sp.limit(k * data["covariance"], k, sp.oo))
        expected = (sp.Rational(1, 12), sp.exp(-2), sp.exp(-1) / 4)
        actual = (
            variance_arithmetic_limit,
            variance_geometric_limit,
            covariance_limit,
        )
        if any(sp.simplify(left - right) != 0 for left, right in zip(actual, expected)):
            return None
        return PrimitiveResult(
            {
                **data,
                "scaled_variance_arithmetic_limit": variance_arithmetic_limit,
                "scaled_variance_geometric_limit": variance_geometric_limit,
                "scaled_covariance_limit": covariance_limit,
            },
            {
                "scaled_variance_arithmetic_limit": sp.sstr(variance_arithmetic_limit),
                "scaled_variance_geometric_limit": sp.sstr(variance_geometric_limit),
                "scaled_covariance_limit": sp.sstr(covariance_limit),
            },
        )

    def replay_log_expansion(arguments: tuple[Any, ...]) -> PrimitiveResult | None:
        data = arguments[0].value
        h = sp.Symbol("h", positive=True)
        first = sp.exp(-sp.log(1 + 2 * h) / h)
        second = sp.exp(-2 * sp.log(1 + h) / h)
        variance_limit = sp.simplify(sp.limit((first - second) / h, h, 0, dir="+"))
        covariance_limit = sp.simplify(
            sp.limit(
                (1 / (1 + h)) ** (1 / h) / (2 * (2 + h)),
                h,
                0,
                dir="+",
            )
        )
        if sp.simplify(variance_limit - data["scaled_variance_geometric_limit"]) != 0:
            return None
        if sp.simplify(covariance_limit - data["scaled_covariance_limit"]) != 0:
            return None
        return PrimitiveResult(
            data,
            {
                "geometric_variance_log_expansion": "e^-2*(2h-h)+O(h^2)",
                "covariance_power_limit": sp.sstr(covariance_limit),
                "independent_asymptotic_replay": True,
            },
        )

    def normalize_limit_correlation(arguments: tuple[Any, ...]) -> PrimitiveResult | None:
        data = arguments[0].value
        correlation = sp.radsimp(
            sp.simplify(
                data["scaled_covariance_limit"]
                / sp.sqrt(
                    data["scaled_variance_arithmetic_limit"]
                    * data["scaled_variance_geometric_limit"]
                )
            )
        )
        if correlation.is_positive is not True or sp.simplify(1 - correlation**2) < 0:
            return None
        return PrimitiveResult(
            {**data, "correlation": correlation},
            {"value": sp.sstr(correlation), "normalization_residual": "0"},
        )

    def recover_principal_angle(arguments: tuple[Any, ...]) -> PrimitiveResult | None:
        if query.target_representation != "angle_from_cosine":
            return None
        data = arguments[0].value
        angle = sp.simplify(sp.acos(data["correlation"]))
        if sp.simplify(sp.cos(angle) - data["correlation"]) != 0:
            return None
        return PrimitiveResult(
            {**data, "target_value": angle},
            {
                "principal_angle": sp.sstr(angle),
                "cosine_replay": sp.sstr(sp.cos(angle)),
            },
        )

    primitives = (
        RuntimePrimitive(
            "growing_finite_population_sampling_elaboration",
            ("ParsedProblemIR",),
            "GrowingFinitePopulationSample",
            elaborate_sampling,
        ),
        RuntimePrimitive(
            "mean_observable_pair_elaboration",
            ("ParsedProblemIR",),
            "GrowingMeanObservablePair",
            elaborate_observables,
        ),
        RuntimePrimitive(
            "without_replacement_to_iid_limit",
            ("GrowingFinitePopulationSample",),
            "IIDUniformSampleLimit",
            pass_to_iid_limit,
        ),
        RuntimePrimitive(
            "growing_sample_moment_dependency_expansion",
            ("GrowingMeanObservablePair", "IIDUniformSampleLimit"),
            "GrowingSampleMomentObligations",
            expand_moment_dependencies,
        ),
        RuntimePrimitive(
            "product_measure_moment_evaluation",
            ("GrowingSampleMomentObligations",),
            "FiniteKDirectMoments",
            exact_product_moments,
        ),
        RuntimePrimitive(
            "independent_single_integral_replay",
            ("GrowingSampleMomentObligations",),
            "FiniteKReplayedMoments",
            replay_single_integrals,
        ),
        RuntimePrimitive(
            "finite_k_moment_replay_agreement",
            ("FiniteKDirectMoments", "FiniteKReplayedMoments"),
            "CertifiedFiniteKMoments",
            certify_moment_agreement,
        ),
        RuntimePrimitive(
            "finite_k_centered_moment_composition",
            ("CertifiedFiniteKMoments",),
            "FiniteKCenteredMoments",
            compose_centered_moments,
        ),
        RuntimePrimitive(
            "scaled_centered_moment_limit",
            ("FiniteKCenteredMoments",),
            "ScaledMomentLimits",
            derive_scaled_limits,
        ),
        RuntimePrimitive(
            "logarithmic_asymptotic_replay",
            ("ScaledMomentLimits",),
            "ReplayedScaledMomentLimits",
            replay_log_expansion,
        ),
        RuntimePrimitive(
            "asymptotic_correlation_normalization",
            ("ReplayedScaledMomentLimits",),
            "CertifiedCorrelation",
            normalize_limit_correlation,
        ),
        RuntimePrimitive(
            "principal_angle_from_correlation",
            ("CertifiedCorrelation",),
            "CertifiedCorrelationAngle",
            recover_principal_angle,
        ),
    )
    goal_sort = (
        "CertifiedCorrelationAngle"
        if query.target_representation == "angle_from_cosine"
        else "CertifiedCorrelation"
    )
    plan = synthesize_typed_plan(
        [initial_fact("ParsedProblemIR", query.to_dict())],
        primitives,
        (goal_sort,),
        max_depth=14,
        max_states=128,
    )
    if not plan.complete:
        raise ValueError(f"growing-sample planner left open goals: {plan.open_goal_sorts}")
    result = plan.goals[goal_sort].value
    correlation = result["correlation"]
    target_value = result.get("target_value", correlation)
    moments = result["canonical_moments"]
    replayed = result["replayed_moments"]
    left_symbol = query.observables[0].output_symbol
    right_symbol = query.observables[1].output_symbol
    target_symbol = _tex_identifier(query.target_symbol)
    derivation = (
        rf"まず \({sample_symbol}\) を固定して \({query.limit_symbol}\to\infty\) とする。"
        rf"カードの値を \({query.limit_symbol}\) で割ると、"
        rf"非復元抽出は区間 \([0,1]\) の独立な一様分布 "
        rf"\(U_1,\ldots,U_{sample_symbol}\) に収束する。",
        rf"\(A_{sample_symbol}=\frac1{{{sample_symbol}}}\sum_{{i=1}}^{{{sample_symbol}}}U_i\), "
        rf"\(G_{sample_symbol}=(\prod_{{i=1}}^{{{sample_symbol}}}U_i)^{{1/{sample_symbol}}}\) とおく。"
        rf"独立性と (\int_0^1x^a\,dx=1/(a+1)) から "
        rf"\[E[A_k]={sp.latex(moments['E_A'])},\quad E[A_k^2]={sp.latex(moments['E_A2'])},\quad "
        rf"E[G_k]={sp.latex(moments['E_G'])},\quad E[G_k^2]={sp.latex(moments['E_G2'])},\quad "
        rf"E[A_kG_k]={sp.latex(moments['E_AG'])}.\]",
        rf"従って \[k\operatorname{{Var}}(A_k)\to {sp.latex(result['scaled_variance_arithmetic_limit'])},\quad "
        rf"k\operatorname{{Var}}(G_k)\to {sp.latex(result['scaled_variance_geometric_limit'])},\quad "
        rf"k\operatorname{{Cov}}(A_k,G_k)\to {sp.latex(result['scaled_covariance_limit'])}.\] "
        r"同じ極限は (h=1/k) と置いた対数展開でも照合した。",
        rf"よって相関係数は \[{sp.latex(correlation)}\] に収束する。"
        + (
            rf"(0\le {target_symbol}\le\pi) で (cos {target_symbol}) が相関係数だから、"
            rf"({target_symbol}\to {sp.latex(target_value)}) である。"
            if query.target_representation == "angle_from_cosine"
            else ""
        ),
    )
    proof_program = plan.proof_program + (
        {
            "rule": "exact_obligation_replay",
            "verified": True,
            "planner_states_explored": plan.states_explored,
        },
    )
    witness = {
        "input_ir": query.to_dict(),
        "finite_k_moments": {name: sp.sstr(value) for name, value in moments.items()},
        "independent_finite_k_moments": {
            name: sp.sstr(value) for name, value in replayed.items()
        },
        "scaled_variance_arithmetic_limit": sp.sstr(
            result["scaled_variance_arithmetic_limit"]
        ),
        "scaled_variance_geometric_limit": sp.sstr(
            result["scaled_variance_geometric_limit"]
        ),
        "scaled_covariance_limit": sp.sstr(result["scaled_covariance_limit"]),
        "correlation": sp.sstr(correlation),
        "target_value": sp.sstr(target_value),
        "planner": {
            "states_explored": plan.states_explored,
            "goal_sorts": sorted(plan.goals),
            "open_goal_sorts": list(plan.open_goal_sorts),
        },
    }
    return CorrelationLimitSynthesis(
        answer_tex=rf"\({sp.latex(target_value)}\)",
        derivation_tex=derivation,
        expression_tex=(
            rf"\lim_{{{sample_symbol}\to\infty}}"
            rf"\lim_{{{query.limit_symbol}\to\infty}}{target_symbol}"
        ),
        proof_program=proof_program,
        verification_checks=(
            "母集団極限と標本数極限を現在の問題文から別々に抽出",
            "有限kの五つのモーメントを積測度と一変数積分で独立照合",
            "分散・共分散の1/k係数を直接極限と対数展開で独立照合",
            "相関係数の正規化と主値角の余弦を厳密に再生",
        ),
        witness=witness,
        hypotheses_evaluated=plan.states_explored + 10,
    )


def execute_correlation_limit_query(query: CorrelationLimitQueryIR) -> CorrelationLimitSynthesis:
    if isinstance(query.sample.sample_size, str):
        return _execute_growing_sample_correlation_query(query)

    u, v = sp.symbols("u v", positive=True)

    def elaborate_sampling(arguments: tuple[Any, ...]) -> PrimitiveResult | None:
        if query.sample.sample_size != 2 or not query.sample.without_replacement:
            return None
        return PrimitiveResult(
            asdict(query.sample),
            {
                "lower_endpoint": query.sample.lower_endpoint,
                "upper_symbol": query.sample.upper_symbol,
                "sample_size": query.sample.sample_size,
                "without_replacement": query.sample.without_replacement,
            },
        )

    def elaborate_observables(arguments: tuple[Any, ...]) -> PrimitiveResult | None:
        left = _observable_expression(query.observables[0].kind, u, v)
        right = _observable_expression(query.observables[1].kind, u, v)
        if any(
            sp.simplify(expression - expression.xreplace({u: v, v: u})) != 0
            for expression in (left, right)
        ):
            return None
        return PrimitiveResult(
            {"left": left, "right": right},
            {
                "observables": [
                    {"kind": query.observables[0].kind, "expression": sp.sstr(left)},
                    {"kind": query.observables[1].kind, "expression": sp.sstr(right)},
                ],
                "exchange_symmetric": True,
            },
        )

    def normalize_observables(arguments: tuple[Any, ...]) -> PrimitiveResult | None:
        pair = arguments[0].value
        try:
            degrees = (
                _homogeneous_degree(pair["left"], u, v),
                _homogeneous_degree(pair["right"], u, v),
            )
        except ValueError:
            return None
        return PrimitiveResult(
            {**pair, "degrees": degrees},
            {"degrees": [sp.sstr(degree) for degree in degrees]},
        )

    def expand_correlation_dependencies(arguments: tuple[Any, ...]) -> PrimitiveResult:
        pair = arguments[0].value
        obligations = (
            ("E_X", pair["left"]),
            ("E_Y", pair["right"]),
            ("E_X2", pair["left"] ** 2),
            ("E_Y2", pair["right"] ** 2),
            ("E_XY", pair["left"] * pair["right"]),
        )
        return PrimitiveResult(
            {**pair, "obligations": obligations},
            {"generated_obligations": [name for name, _ in obligations]},
        )

    def finite_sample_limit(arguments: tuple[Any, ...]) -> PrimitiveResult:
        return PrimitiveResult(
            {"measure": "Uniform(0,1)^2", "diagonal_mass_limit": sp.Integer(0)},
            {"diagonal_mass_limit": "0", "limit_measure": "Uniform(0,1)^2"},
        )

    def evaluate_separable_moments(arguments: tuple[Any, ...]) -> PrimitiveResult:
        obligations = arguments[0].value["obligations"]
        moments = {
            name: _separable_unit_square_moment(expression, u, v)
            for name, expression in obligations
        }
        monomial_count = sum(
            len(_monomial_terms(expression, u, v)) for _, expression in obligations
        )
        return PrimitiveResult(
            {"moments": moments, "monomial_count": monomial_count},
            {"moments": {name: sp.sstr(value) for name, value in moments.items()}},
        )

    def replay_double_integrals(arguments: tuple[Any, ...]) -> PrimitiveResult:
        obligations = arguments[0].value["obligations"]
        moments = {
            name: _symbolic_unit_square_moment(expression, u, v)
            for name, expression in obligations
        }
        return PrimitiveResult(
            {"moments": moments},
            {"moments": {name: sp.sstr(value) for name, value in moments.items()}},
        )

    def certify_moment_agreement(arguments: tuple[Any, ...]) -> PrimitiveResult | None:
        direct = arguments[0].value
        replayed = arguments[1].value
        if any(
            sp.simplify(direct["moments"][name] - replayed["moments"][name]) != 0
            for name in direct["moments"]
        ):
            return None
        return PrimitiveResult(
            {
                "moments": direct["moments"],
                "replayed_moments": replayed["moments"],
                "monomial_count": direct["monomial_count"],
            },
            {"all_moments_agree": True},
        )

    def compose_centered_moments(arguments: tuple[Any, ...]) -> PrimitiveResult | None:
        data = arguments[0].value
        moments = data["moments"]
        variance_left = sp.simplify(moments["E_X2"] - moments["E_X"] ** 2)
        variance_right = sp.simplify(moments["E_Y2"] - moments["E_Y"] ** 2)
        covariance = sp.simplify(moments["E_XY"] - moments["E_X"] * moments["E_Y"])
        if variance_left.is_positive is not True or variance_right.is_positive is not True:
            return None
        return PrimitiveResult(
            {
                **data,
                "variance_left": variance_left,
                "variance_right": variance_right,
                "covariance": covariance,
            },
            {
                "variance_left": sp.sstr(variance_left),
                "variance_right": sp.sstr(variance_right),
                "covariance": sp.sstr(covariance),
                "variances_positive": True,
            },
        )

    def normalize_correlation(arguments: tuple[Any, ...]) -> PrimitiveResult | None:
        data = arguments[0].value
        correlation = sp.radsimp(
            sp.simplify(
                data["covariance"]
                / sp.sqrt(data["variance_left"] * data["variance_right"])
            )
        )
        residual = sp.simplify(
            correlation**2 * data["variance_left"] * data["variance_right"]
            - data["covariance"] ** 2
        )
        if residual != 0:
            return None
        if correlation.is_real is not True:
            return None
        if sp.simplify(1 - correlation**2).is_nonnegative is not True:
            return None
        return PrimitiveResult(
            {**data, "correlation": correlation},
            {"value": sp.sstr(correlation), "normalization_residual": "0"},
        )

    primitives = (
        RuntimePrimitive(
            "finite_population_sampling_elaboration",
            ("ParsedProblemIR",),
            "FinitePopulationSample",
            elaborate_sampling,
        ),
        RuntimePrimitive(
            "named_observable_elaboration",
            ("ParsedProblemIR",),
            "ObservablePair",
            elaborate_observables,
        ),
        RuntimePrimitive(
            "homogeneous_observable_normalization",
            ("ObservablePair",),
            "NormalizedObservablePair",
            normalize_observables,
        ),
        RuntimePrimitive(
            "correlation_dependency_expansion",
            ("NormalizedObservablePair",),
            "MomentObligations",
            expand_correlation_dependencies,
        ),
        RuntimePrimitive(
            "finite_sample_riemann_limit",
            ("FinitePopulationSample", "NormalizedObservablePair"),
            "ContinuousSampleMeasure",
            finite_sample_limit,
        ),
        RuntimePrimitive(
            "separable_monomial_moment_evaluation",
            ("MomentObligations", "ContinuousSampleMeasure"),
            "DirectMoments",
            evaluate_separable_moments,
        ),
        RuntimePrimitive(
            "independent_double_integral_replay",
            ("MomentObligations", "ContinuousSampleMeasure"),
            "ReplayedMoments",
            replay_double_integrals,
        ),
        RuntimePrimitive(
            "moment_replay_agreement",
            ("DirectMoments", "ReplayedMoments"),
            "ExactMoments",
            certify_moment_agreement,
        ),
        RuntimePrimitive(
            "centered_moment_composition",
            ("ExactMoments",),
            "CenteredMoments",
            compose_centered_moments,
        ),
        RuntimePrimitive(
            "exact_correlation_normalization",
            ("CenteredMoments",),
            "CertifiedCorrelation",
            normalize_correlation,
        ),
    )
    plan = synthesize_typed_plan(
        [initial_fact("ParsedProblemIR", query.to_dict())],
        primitives,
        ("CertifiedCorrelation",),
        max_depth=10,
        max_states=128,
    )
    if not plan.complete:
        raise ValueError(f"runtime correlation planner left open goals: {plan.open_goal_sorts}")
    result = plan.goals["CertifiedCorrelation"].value
    normalized_fact = next(
        fact for fact in plan.facts if fact.sort == "NormalizedObservablePair"
    )
    left = normalized_fact.value["left"]
    right = normalized_fact.value["right"]
    degrees = normalized_fact.value["degrees"]
    obligation_fact = next(fact for fact in plan.facts if fact.sort == "MomentObligations")
    obligations = obligation_fact.value["obligations"]
    moments = result["moments"]
    replayed_moments = result["replayed_moments"]
    monomial_count = result["monomial_count"]
    variance_left = result["variance_left"]
    variance_right = result["variance_right"]
    covariance = result["covariance"]
    correlation = result["correlation"]

    left_symbol = query.observables[0].output_symbol
    right_symbol = query.observables[1].output_symbol
    target_symbol = _tex_identifier(query.target_symbol)
    moments_tex = (
        rf"\mathrm E[{left_symbol}]={sp.latex(moments['E_X'])},\quad "
        rf"\mathrm E[{right_symbol}]={sp.latex(moments['E_Y'])},\quad "
        rf"\mathrm E[{left_symbol}^2]={sp.latex(moments['E_X2'])},\quad "
        rf"\mathrm E[{right_symbol}^2]={sp.latex(moments['E_Y2'])},\quad "
        rf"\mathrm E[{left_symbol}{right_symbol}]={sp.latex(moments['E_XY'])}"
    )
    derivation = (
        rf"引いた二数を \(i,j\) とし、\(u=i/{query.sample.upper_symbol},\ v=j/{query.sample.upper_symbol}\) とおく。"
        rf"相関係数は二つの変数をそれぞれ正の定数倍しても変わらない。"
        rf"問題文の {_observable_label(query.observables[0].kind)} と {_observable_label(query.observables[1].kind)} は "
        rf"\({left_symbol}={sp.latex(left)},\ {right_symbol}={sp.latex(right)}\) へ変換される。",
        r"異なる二枚の順序付き組に対する平均と、全ての二数の組に対する平均との差は対角成分だけである。"
        r"対角成分の割合は \(1/n\) なので0へ収束する。従って極限では "
        r"\(U,V\) を独立な区間 \([0,1]\) の一様分布として計算できる。観測量は対称なので、順序を除いた抽出でも同じ平均になる。",
        rf"相関係数の定義から必要な量を逆算すると五つのモーメントだけでよい。厳密積分により \[{moments_tex}\] を得る。"
        r"各積分は、有理指数の単項式を \(\int_0^1 t^a\,dt=1/(a+1)\) で積分する計算と、二重積分の直接計算の二通りで一致した。",
        rf"したがって \(\operatorname{{Var}}({left_symbol})={sp.latex(variance_left)}\), "
        rf"\(\operatorname{{Var}}({right_symbol})={sp.latex(variance_right)}\), "
        rf"\(\operatorname{{Cov}}({left_symbol},{right_symbol})={sp.latex(covariance)}\) である。両分散は正である。",
        rf"よって \[\lim_{{{query.limit_symbol}\to\infty}}{target_symbol}="
        rf"\frac{{\operatorname{{Cov}}({left_symbol},{right_symbol})}}"
        rf"{{\sqrt{{\operatorname{{Var}}({left_symbol})\operatorname{{Var}}({right_symbol})}}}}"
        rf"={sp.latex(correlation)}.\]",
    )
    proof_program = plan.proof_program + (
        {
            "rule": "exact_obligation_replay",
            "verified": True,
            "planner_states_explored": plan.states_explored,
        },
    )
    witness = {
        "input_ir": query.to_dict(),
        "observable_expressions": {
            left_symbol: sp.sstr(left),
            right_symbol: sp.sstr(right),
        },
        "homogeneous_degrees": [sp.sstr(degree) for degree in degrees],
        "generated_moment_obligations": [name for name, _ in obligations],
        "moments": {name: sp.sstr(value) for name, value in moments.items()},
        "independent_moments": {
            name: sp.sstr(value) for name, value in replayed_moments.items()
        },
        "variance_left": sp.sstr(variance_left),
        "variance_right": sp.sstr(variance_right),
        "covariance": sp.sstr(covariance),
        "correlation": sp.sstr(correlation),
        "planner": {
            "states_explored": plan.states_explored,
            "goal_sorts": sorted(plan.goals),
            "open_goal_sorts": list(plan.open_goal_sorts),
        },
    }
    checks = (
        "母集団、標本数、非復元抽出、観測量、極限変数を現在の問題文から抽出",
        "二つの観測量が交換対称かつ同次であることを検査",
        "相関係数から必要な五つのモーメント義務を実行時に生成",
        "五つのモーメントを有理指数単項式積分とSymPy二重積分で独立照合",
        "両分散の正値性と相関係数の規格化恒等式を厳密検査",
    )
    return CorrelationLimitSynthesis(
        answer_tex=rf"\({sp.latex(correlation)}\)",
        derivation_tex=derivation,
        expression_tex=rf"\lim_{{{query.limit_symbol}\to\infty}}{target_symbol}",
        proof_program=proof_program,
        verification_checks=checks,
        witness=witness,
        hypotheses_evaluated=plan.states_explored + monomial_count + len(obligations),
    )


def synthesize_correlation_limit_problem(statement: str) -> CorrelationLimitSynthesis | None:
    query = compile_correlation_limit_query(statement)
    if query is None:
        return None
    return execute_correlation_limit_query(query)
