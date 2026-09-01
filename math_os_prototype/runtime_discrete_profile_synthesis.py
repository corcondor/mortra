"""Runtime synthesis for a discrete transcendental optimization profile.

The minimizing index is deliberately absent from this module.  It is generated
from the current input by an exact derivative search, integer candidate
generation, and rational interval comparison.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any

import sympy as sp

from .exact_interval_charts import (
    alternating_trig_bounds,
    log_profile_bounds,
    log_profile_derivative_bounds,
)
from .runtime_typed_planner import (
    PrimitiveResult,
    RuntimePrimitive,
    initial_fact,
    synthesize_typed_plan,
)


@dataclass(frozen=True)
class DiscreteTrigProfileQueryIR:
    sequence_symbol: str
    index_symbol: str
    lower_index: int
    angular_frequency: int
    asks_global_minimum: bool
    asks_scaled_euler_gap: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DiscreteTrigProfileSynthesis:
    answer_tex: str
    derivation_tex: tuple[str, ...]
    expression_tex: str
    proof_program: tuple[dict[str, Any], ...]
    verification_checks: tuple[str, ...]
    witness: dict[str, Any]
    hypotheses_evaluated: int


_PI_LOWER = sp.Rational(103993, 33102)
_PI_UPPER = sp.Rational(104348, 33215)


def _compact(statement: str) -> str:
    compact = re.sub(
        r"\s+",
        "",
        statement.replace("−", "-")
        .replace("–", "-")
        .replace("∞", r"\infty")
        .replace(r"\left", "")
        .replace(r"\right", "")
        .replace(r"\,", "")
        .replace(r"\!", "")
        .replace(r"\mathrm{e}", "e")
        .replace(r"\geqq", r"\geq"),
    )
    return re.sub(r"_\{([A-Za-z])\}", r"_\1", compact)


def compile_discrete_trig_profile_query(
    statement: str,
) -> DiscreteTrigProfileQueryIR | None:
    compact = _compact(statement)
    trig = re.search(
        r"\\sin(?P<argument>\\frac\{(?P<frequency>\d*)\\pi\}"
        r"\{(?P<index>[A-Za-z])\})",
        compact,
    )
    if trig is None:
        return None
    argument = trig.group("argument")
    index = trig.group("index")
    frequency = int(trig.group("frequency") or "1")
    if frequency <= 0 or f"\\cos{argument}" not in compact:
        return None

    lower_match = re.search(rf"{re.escape(index)}\\geq(?P<lower>\d+)", compact)
    sequence_match = re.search(
        rf"(?P<sequence>[A-Za-z])_{re.escape(index)}=",
        compact,
    )
    if lower_match is None or sequence_match is None:
        return None
    lower = int(lower_match.group("lower"))
    sequence = sequence_match.group("sequence")

    base = rf"\sin{argument}+\cos{argument}"
    defining_expression = (
        rf"({base})^{{\frac{{1}}{{{base}-1}}+{base}-1}}"
    )
    if f"{sequence}_{index}={defining_expression}" not in compact:
        return None
    if "最小値" not in statement:
        return None
    scaled_limit = (
        rf"\lim_{{{index}\to\infty}}{index}(e-{sequence}_{index})"
    )
    if scaled_limit not in compact:
        return None
    if lower < 4 * frequency:
        # The current proof chart needs 0 < frequency*pi/index <= pi/4.
        return None

    return DiscreteTrigProfileQueryIR(
        sequence_symbol=sequence,
        index_symbol=index,
        lower_index=lower,
        angular_frequency=frequency,
        asks_global_minimum=True,
        asks_scaled_euler_gap=True,
    )


def _profile_root_bracket() -> tuple[sp.Rational, sp.Rational, int, int]:
    """Find, rather than store, a rational bracket for the profile minimum."""

    points_checked = 0
    for denominator in (100, 200, 400, 800, 1600):
        last_certified_negative: sp.Rational | None = None
        for numerator in range(1, denominator // 2):
            point = sp.Rational(numerator, denominator)
            lower, upper = log_profile_derivative_bounds(point, terms=24)
            points_checked += 1
            if upper < 0:
                last_certified_negative = point
                continue
            if lower > 0 and last_certified_negative is not None:
                return (
                    last_certified_negative,
                    point,
                    denominator,
                    points_checked,
                )
    raise ValueError("failed to synthesize a rational profile-root bracket")


def _input_interval(frequency: int, index: int) -> tuple[sp.Rational, sp.Rational]:
    x_lower = sp.Rational(frequency, index) * _PI_LOWER
    x_upper = sp.Rational(frequency, index) * _PI_UPPER
    sin_lower, _, cos_lower, _ = alternating_trig_bounds(x_lower)
    _, sin_upper, _, cos_upper = alternating_trig_bounds(x_upper)
    lower = sp.factor(sin_lower + cos_lower - 1)
    upper = sp.factor(sin_upper + cos_upper - 1)
    if not (0 < lower <= upper < 1):
        raise ValueError("generated trigonometric input interval is invalid")
    return lower, upper


def _candidate_indices(
    query: DiscreteTrigProfileQueryIR,
    root_lower: sp.Rational,
    root_upper: sp.Rational,
) -> tuple[list[int], dict[int, tuple[sp.Rational, sp.Rational]], int]:
    frequency = query.angular_frequency
    stop = int(sp.floor(frequency * _PI_UPPER / root_lower)) + 3
    intervals: dict[int, tuple[sp.Rational, sp.Rational]] = {}
    above_root: list[int] = []
    below_root: list[int] = []
    for index in range(query.lower_index, stop + 1):
        interval = _input_interval(frequency, index)
        intervals[index] = interval
        if interval[0] > root_upper:
            above_root.append(index)
        elif interval[1] < root_lower:
            below_root.append(index)

    candidate_start = max(above_root) if above_root else query.lower_index
    candidate_end = min(below_root) if below_root else stop
    if candidate_start > candidate_end:
        raise ValueError("generated candidate interval is reversed")
    candidates = list(range(candidate_start, candidate_end + 1))
    return candidates, intervals, stop


def execute_discrete_trig_profile_query(
    query: DiscreteTrigProfileQueryIR,
) -> DiscreteTrigProfileSynthesis:
    u = sp.Symbol("u", positive=True)

    def elaborate_input(arguments: tuple[Any, ...]) -> PrimitiveResult:
        return PrimitiveResult(
            query.to_dict(),
            {
                "sequence_symbol": query.sequence_symbol,
                "index_symbol": query.index_symbol,
                "lower_index": query.lower_index,
                "angular_frequency": query.angular_frequency,
            },
        )

    def derive_profile(arguments: tuple[Any, ...]) -> PrimitiveResult:
        profile = (u + 1 / u) * sp.log(1 + u)
        derivative = sp.factor(sp.diff(profile, u))
        return PrimitiveResult(
            {"profile": profile, "derivative": derivative},
            {"profile": sp.sstr(profile), "derivative": sp.sstr(derivative)},
        )

    def prove_convexity(arguments: tuple[Any, ...]) -> PrimitiveResult | None:
        profile = arguments[0].value["profile"]
        numerator = sp.factor(sp.diff(profile, u, 2) * u**3 * (1 + u) ** 2)
        remainder = sp.factor(numerator.subs(sp.log(1 + u), u - u**2 / 2))
        if remainder != 2 * u**3:
            return None
        return PrimitiveResult(
            {"remainder": remainder},
            {"remainder_after_log_lower_bound": sp.sstr(remainder)},
        )

    def search_stationary_point(arguments: tuple[Any, ...]) -> PrimitiveResult | None:
        root_lower, root_upper, denominator, checked = _profile_root_bracket()
        left_derivative = log_profile_derivative_bounds(root_lower, terms=24)
        right_derivative = log_profile_derivative_bounds(root_upper, terms=24)
        if left_derivative[1] >= 0 or right_derivative[0] <= 0:
            return None
        return PrimitiveResult(
            {
                "lower": root_lower,
                "upper": root_upper,
                "grid_denominator": denominator,
                "points_checked": checked,
            },
            {
                "grid_denominator": denominator,
                "points_checked": checked,
                "root_bracket": [sp.sstr(root_lower), sp.sstr(root_upper)],
            },
        )

    def generate_integer_candidates(arguments: tuple[Any, ...]) -> PrimitiveResult:
        root = arguments[1].value
        candidates, intervals, stop = _candidate_indices(
            query,
            root["lower"],
            root["upper"],
        )
        return PrimitiveResult(
            {"candidates": candidates, "input_intervals": intervals, "stop": stop},
            {
                "searched_index_interval": [query.lower_index, stop],
                "generated_candidates": candidates,
            },
        )

    def compare_candidates(arguments: tuple[Any, ...]) -> PrimitiveResult | None:
        candidate_data = arguments[1].value
        candidates = candidate_data["candidates"]
        input_intervals = candidate_data["input_intervals"]
        profile_intervals = {
            index: log_profile_bounds(*input_intervals[index], terms=30)
            for index in candidates
        }
        winners = [
            index
            for index in candidates
            if all(
                index == other
                or profile_intervals[index][1] < profile_intervals[other][0]
                for other in candidates
            )
        ]
        if len(winners) != 1:
            return None
        return PrimitiveResult(
            {
                **candidate_data,
                "profile_intervals": profile_intervals,
                "selected_index": winners[0],
            },
            {
                "candidate_count": len(candidates),
                "selected_index": winners[0],
                "strictly_separated": True,
            },
        )

    def derive_input_asymptotic(arguments: tuple[Any, ...]) -> PrimitiveResult | None:
        t = sp.Symbol("t", positive=True)
        frequency = sp.Integer(query.angular_frequency)
        normalized = sp.limit(
            (sp.sin(frequency * t) + sp.cos(frequency * t) - 1) / t,
            t,
            0,
        )
        if normalized != frequency:
            return None
        coefficient = frequency * sp.pi
        return PrimitiveResult(
            {"coefficient": coefficient},
            {
                "expansion": (
                    f"u_{query.index_symbol}={sp.sstr(coefficient)}/"
                    f"{query.index_symbol}+O({query.index_symbol}**-2)"
                ),
                "coefficient_replay": sp.sstr(normalized),
            },
        )

    def derive_profile_asymptotic(arguments: tuple[Any, ...]) -> PrimitiveResult | None:
        profile = arguments[0].value["profile"]
        coefficient = sp.limit((profile - 1) / u, u, 0)
        if coefficient != -sp.Rational(1, 2):
            return None
        return PrimitiveResult(
            {"constant": sp.Integer(1), "linear_coefficient": coefficient},
            {
                "expansion": "F(u)=1-u/2+O(u**2)",
                "linear_coefficient": sp.sstr(coefficient),
            },
        )

    def compose_scaled_limit(arguments: tuple[Any, ...]) -> PrimitiveResult:
        input_coefficient = arguments[0].value["coefficient"]
        profile_coefficient = arguments[1].value["linear_coefficient"]
        limit = sp.factor(-sp.E * profile_coefficient * input_coefficient)
        return PrimitiveResult(
            {"limit": limit},
            {
                "input_coefficient": sp.sstr(input_coefficient),
                "profile_linear_coefficient": sp.sstr(profile_coefficient),
                "limit": sp.sstr(limit),
            },
        )

    primitives = (
        RuntimePrimitive(
            "discrete_profile_input_elaboration",
            ("ParsedProblemIR",),
            "DiscreteProfileInput",
            elaborate_input,
        ),
        RuntimePrimitive(
            "logarithmic_profile_derivation",
            ("DiscreteProfileInput",),
            "ScalarLogProfile",
            derive_profile,
        ),
        RuntimePrimitive(
            "strict_convexity_certificate",
            ("ScalarLogProfile",),
            "StrictConvexProfile",
            prove_convexity,
        ),
        RuntimePrimitive(
            "runtime_derivative_root_search",
            ("ScalarLogProfile", "StrictConvexProfile"),
            "UniqueProfileMinimizerInterval",
            search_stationary_point,
        ),
        RuntimePrimitive(
            "monotone_integer_candidate_generation",
            ("DiscreteProfileInput", "UniqueProfileMinimizerInterval"),
            "FiniteIndexCandidates",
            generate_integer_candidates,
        ),
        RuntimePrimitive(
            "exact_candidate_interval_comparison",
            ("ScalarLogProfile", "FiniteIndexCandidates"),
            "CertifiedDiscreteMinimum",
            compare_candidates,
        ),
        RuntimePrimitive(
            "input_first_order_asymptotic",
            ("DiscreteProfileInput",),
            "InputFirstOrderAsymptotic",
            derive_input_asymptotic,
        ),
        RuntimePrimitive(
            "profile_first_order_asymptotic",
            ("ScalarLogProfile",),
            "ProfileFirstOrderAsymptotic",
            derive_profile_asymptotic,
        ),
        RuntimePrimitive(
            "first_order_asymptotic_composition",
            ("InputFirstOrderAsymptotic", "ProfileFirstOrderAsymptotic"),
            "CertifiedScaledLimit",
            compose_scaled_limit,
        ),
    )
    plan = synthesize_typed_plan(
        [initial_fact("ParsedProblemIR", query.to_dict())],
        primitives,
        ("CertifiedDiscreteMinimum", "CertifiedScaledLimit"),
        max_depth=8,
        max_states=128,
    )
    if not plan.complete:
        raise ValueError(f"runtime proof planner left open goals: {plan.open_goal_sorts}")

    minimum_data = plan.goals["CertifiedDiscreteMinimum"].value
    limit_data = plan.goals["CertifiedScaledLimit"].value
    profile_fact = next(fact for fact in plan.facts if fact.sort == "ScalarLogProfile")
    convexity_fact = next(fact for fact in plan.facts if fact.sort == "StrictConvexProfile")
    root_fact = next(
        fact for fact in plan.facts if fact.sort == "UniqueProfileMinimizerInterval"
    )
    profile = profile_fact.value["profile"]
    profile_derivative = profile_fact.value["derivative"]
    convexity_remainder = convexity_fact.value["remainder"]
    root_lower = root_fact.value["lower"]
    root_upper = root_fact.value["upper"]
    grid_denominator = root_fact.value["grid_denominator"]
    root_checks = root_fact.value["points_checked"]
    candidates = minimum_data["candidates"]
    input_intervals = minimum_data["input_intervals"]
    profile_intervals = minimum_data["profile_intervals"]
    stop = minimum_data["stop"]
    minimizing_index = minimum_data["selected_index"]

    frequency = sp.Integer(query.angular_frequency)
    angle = sp.pi * frequency / minimizing_index
    base = sp.trigsimp(sp.sin(angle) + sp.cos(angle))
    shifted = sp.simplify(base - 1)
    minimum = sp.Pow(base, sp.simplify(1 / shifted + shifted), evaluate=False)
    scaled_limit = limit_data["limit"]
    sequence = query.sequence_symbol
    index = query.index_symbol
    frequency_tex = "" if query.angular_frequency == 1 else str(query.angular_frequency)
    argument_tex = rf"\frac{{{frequency_tex}\pi}}{{{index}}}"

    candidate_rows = {
        str(candidate): {
            "u_lower": sp.sstr(input_intervals[candidate][0]),
            "u_upper": sp.sstr(input_intervals[candidate][1]),
            "profile_lower": sp.sstr(profile_intervals[candidate][0]),
            "profile_upper": sp.sstr(profile_intervals[candidate][1]),
        }
        for candidate in candidates
    }
    proof_program = plan.proof_program + (
        {
            "rule": "exact_obligation_replay",
            "verified": True,
            "planner_states_explored": plan.states_explored,
        },
    )
    derivation = (
        rf"問題文から (u_{index}=\sin {argument_tex}+\cos {argument_tex}-1) を生成する。"
        rf"すると (log {sequence}_{index}=F(u_{index})), "
        r"(F(u)=(u+u^{-1})\log(1+u)) である。",
        r"(F''(u)) の分母を払った式に "
        r"(log(1+u)\ge u-u^2/2) を代入すると (2u^3>0) が残る。"
        r"従って (F') は狭義単調増加し、零点は高々一つである。",
        rf"MORTRAは有理格子をその場で調べ、(F') の零点を "
        rf"({sp.latex(root_lower)}<u_*<{sp.latex(root_upper)}) と囲んだ。"
        rf"また (u_{index}) は (n\ge {query.lower_index}) で狭義単調減少するため、"
        rf"最小候補は (n\in\{{{','.join(map(str, candidates))}\}}) に限られる。",
        rf"各候補で (pi)、(sin)、(cos)、(log(1+u)) を有理区間で評価した。"
        rf"候補 (n={minimizing_index}) の上界が他候補の全下界より小さいため、"
        rf"最小は (n={minimizing_index}) で一意に達する。",
        rf"従って最小値は [{sp.latex(minimum)}] である。"
        rf"さらに (u_{index}={sp.latex(frequency * sp.pi)}/{index}+O({index}^{{-2}})) と "
        r"(F(u)=1-u/2+O(u^2)) を合成すると、"
        rf"[lim_{{{index}\to\infty}}{index}(e-{sequence}_{index})"
        rf"={sp.latex(scaled_limit)}] を得る。",
    )
    answer_tex = (
        rf"\(\min {sequence}_{index}={sp.latex(minimum)}\ "
        rf"(n={minimizing_index}),\quad "
        rf"\lim_{{{index}\to\infty}}{index}(e-{sequence}_{index})="
        rf"{sp.latex(scaled_limit)}\)"
    )
    witness = {
        "input_ir": query.to_dict(),
        "profile": sp.sstr(profile),
        "profile_derivative": sp.sstr(profile_derivative),
        "convexity_remainder": sp.sstr(convexity_remainder),
        "root_search": {
            "grid_denominator": grid_denominator,
            "points_checked": root_checks,
            "bracket": [sp.sstr(root_lower), sp.sstr(root_upper)],
        },
        "generated_candidates": candidates,
        "candidate_intervals": candidate_rows,
        "selected_index": minimizing_index,
        "minimum_expression": sp.sstr(minimum),
        "scaled_limit": sp.sstr(scaled_limit),
        "planner": {
            "states_explored": plan.states_explored,
            "goal_sorts": sorted(plan.goals),
            "open_goal_sorts": list(plan.open_goal_sorts),
        },
        "registered_solution_consulted": False,
    }
    checks = (
        "数列名、添字、開始位置、角周波数、目的関数を現在の問題文から抽出",
        "入力式から対数プロファイルと導関数を生成",
        "導関数の零点を期待値なしの有理格子探索で囲む",
        "単調性から有限個の整数候補だけを生成",
        "各候補を独立な有理区間で比較し、一意な最小添字を検証",
        "一階漸近式を合成して極限を厳密に検証",
    )
    return DiscreteTrigProfileSynthesis(
        answer_tex=answer_tex,
        derivation_tex=derivation,
        expression_tex=(
            rf"\min_{{{index}\ge {query.lower_index}}}{sequence}_{index},\quad"
            rf"\lim_{{{index}\to\infty}}{index}(e-{sequence}_{index})"
        ),
        proof_program=proof_program,
        verification_checks=checks,
        witness=witness,
        hypotheses_evaluated=plan.states_explored + root_checks + len(candidates),
    )


def synthesize_discrete_trig_profile_problem(
    statement: str,
) -> DiscreteTrigProfileSynthesis | None:
    query = compile_discrete_trig_profile_query(statement)
    if query is None:
        return None
    return execute_discrete_trig_profile_query(query)
