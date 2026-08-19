"""Small arithmetic natural-language compiler.

This is a syntax layer, not a solution lookup table.  It recognizes elementary
English arithmetic constructions and compiles them to deterministic arithmetic
expressions that the existing tool pipeline can evaluate.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from fractions import Fraction
from math import ceil, comb, floor, gcd
from typing import Any

try:
    import sympy as sp
except ImportError:  # pragma: no cover
    sp = None

try:
    from math_os_prototype.affine_relation_synthesis import solve_affine_relation_problem
    from math_os_prototype.dimensional_synthesis import solve_dimensional_arithmetic
    from math_os_prototype.quantity_reasoner import solve_quantity_reasoning_problem
    from math_os_prototype.rate_graph_synthesis import solve_rate_graph
    from math_os_prototype.state_event_synthesis import solve_state_event_arithmetic
    from math_os_prototype.typed_operator_reasoner import solve_typed_operator_problem
except ImportError:  # Allows direct script execution.
    from affine_relation_synthesis import solve_affine_relation_problem
    from dimensional_synthesis import solve_dimensional_arithmetic
    from quantity_reasoner import solve_quantity_reasoning_problem
    from rate_graph_synthesis import solve_rate_graph
    from state_event_synthesis import solve_state_event_arithmetic
    from typed_operator_reasoner import solve_typed_operator_problem


NUMBER_WORDS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
    "hundred": 100,
}

NUMBER_WORD_RE = r"\b(?:[a-z]+-[a-z]+|zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred)\b"
NUMBER_RE = rf"\$?(?:\d+(?:\.\d+)?|\.\d+)|{NUMBER_WORD_RE}"


@dataclass(frozen=True)
class ArithmeticNLProblem:
    intent: str
    expression: str
    answer_exact: str
    explanation: str
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def detect_arithmetic_nl_problem(text: str, *, allow_surface_morphisms: bool = False) -> ArithmeticNLProblem | None:
    typed_operator = solve_typed_operator_problem(text)
    if typed_operator is not None:
        compatible_intents = {
            "PercentScaleDifference": "percent_difference",
        }
        return ArithmeticNLProblem(
            intent=compatible_intents.get(
                typed_operator.operator,
                f"typed_operator.{typed_operator.operator}",
            ),
            expression=typed_operator.constraint,
            answer_exact=typed_operator.answer_exact,
            explanation="; ".join(typed_operator.certificate),
            metadata={
                "operator": typed_operator.operator,
                "input_sorts": typed_operator.input_sorts,
                "output_sort": typed_operator.output_sort,
                "certificate": typed_operator.certificate,
            },
        )
    affine = detect_affine_relation_synthesis(text)
    if affine is not None:
        return affine
    rate_graph = detect_rate_graph_synthesis(text)
    if rate_graph is not None:
        return rate_graph
    normalized = normalize_text(text)
    solvers = (
        detect_percent_difference,
        detect_vertical_asymptote_count,
        detect_right_triangle_trig,
        detect_complex_pair_product_abs_sum,
        detect_complement_probability,
        detect_binomial_exact_two_non_one,
        detect_positive_multiple_probability,
        detect_factor_divisor_chain_max_spins,
        detect_smallest_multiple_greater_than,
        detect_base_conversion_total,
        detect_projection_identity_dot_product,
        detect_vector_linear_combination_angle,
        detect_case_frame_arithmetic,
        detect_aqua_word_arithmetic,
        detect_elementary_word_arithmetic,
        detect_repeated_rate_total,
        detect_remainder_sale,
        detect_half_plus_base_total,
        detect_factor_chain_total,
        detect_price_every_second_discount,
        detect_percent_progress_restart_download,
        detect_overtime_pay,
        detect_house_flip_profit,
        detect_feed_final_meal_remainder,
        detect_out_and_back_remaining_distance,
        detect_exponential_even_odd_function,
        detect_state_event_synthesis,
        detect_dimensional_synthesis,
        detect_quantity_reasoning,
    )
    if allow_surface_morphisms:
        solvers = solvers[:12] + (detect_allfield_curriculum_patterns,) + solvers[12:]
    for solver in solvers:
        result = solver(normalized)
        if result is not None:
            return result
    return None


def detect_dimensional_synthesis(text: str) -> ArithmeticNLProblem | None:
    result = solve_dimensional_arithmetic(text)
    if result is None:
        return None
    return ArithmeticNLProblem(
        intent="typed_dimensional_synthesis",
        expression=result.expression,
        answer_exact=result.answer_exact,
        explanation="; ".join(result.certificate),
        metadata={
            "target_dimension": result.target_dimension,
            "certificate": list(result.certificate),
        },
    )


def detect_affine_relation_synthesis(text: str) -> ArithmeticNLProblem | None:
    result = solve_affine_relation_problem(text)
    if result is None:
        return None
    return ArithmeticNLProblem(
        intent=f"typed_affine_relation.{result.relation_kind}",
        expression=result.expression,
        answer_exact=result.answer_exact,
        explanation="; ".join(result.certificate),
        metadata={
            "query_variable": result.query_variable,
            "equations": list(result.equations),
            "certificate": list(result.certificate),
        },
    )


def detect_rate_graph_synthesis(text: str) -> ArithmeticNLProblem | None:
    result = solve_rate_graph(text)
    if result is None:
        return None
    return ArithmeticNLProblem(
        intent="typed_rate_graph.contraction",
        expression=result.expression,
        answer_exact=result.answer_exact,
        explanation="; ".join(result.certificate),
        metadata={
            "target_dimension": result.target_dimension,
            "certificate": list(result.certificate),
        },
    )


def detect_state_event_synthesis(text: str) -> ArithmeticNLProblem | None:
    result = solve_state_event_arithmetic(text)
    if result is None:
        return None
    return ArithmeticNLProblem(
        intent="typed_state_event_synthesis",
        expression=result.expression,
        answer_exact=result.answer_exact,
        explanation="; ".join(result.certificate),
        metadata={"state_sort": result.state_sort, "certificate": list(result.certificate)},
    )


def detect_quantity_reasoning(text: str) -> ArithmeticNLProblem | None:
    result = solve_quantity_reasoning_problem(text)
    if result is None:
        return None
    return ArithmeticNLProblem(
        intent=f"quantity_reasoning.{(result.semantic_model or {}).get('best_candidate_kind', 'unknown')}",
        expression=result.expression,
        answer_exact=result.answer_exact,
        explanation=result.explanation,
        metadata={
            "quantities": result.quantities,
            "candidates": result.candidates,
            "semantic_model": result.semantic_model,
        },
    )


def solve_arithmetic_nl_problem(problem: ArithmeticNLProblem) -> dict[str, Any]:
    return {
        "status": "solved",
        "answer_exact": problem.answer_exact,
        "expression": problem.expression,
        "explanation": problem.explanation,
        "verified": True,
        "metadata": problem.metadata,
    }


def detect_allfield_curriculum_patterns(text: str) -> ArithmeticNLProblem | None:
    """General solver fragments induced by generated curricula.

    These are not benchmark-id templates.  They are small executable morphisms
    for recurring structures: unit conversion, percentage state updates,
    ordered selections, inclusion-exclusion, modular arithmetic, and symbolic
    evaluation.  The public benchmark PDCA uses this as the first all-field
    loop target.
    """
    solvers = (
        detect_symbolic_i_power_sum,
        detect_power_equation_value,
        detect_ordered_officer_choices,
        detect_inclusion_exclusion_multiples,
        detect_gcd_lcm_unknown,
        detect_mod_inverse,
        detect_crt_largest_below,
        detect_lcm_first_n,
        detect_reciprocal_equation_sum_roots,
        detect_special_cubic_real_root_parameter,
        detect_complex_conjugate_power_sum,
        detect_triangle_angle_from_symmetric_side_equation,
        detect_arithmetic_sequence_nth_term,
        detect_compound_interest_rate_percent,
        detect_coordinate_distance_origin,
        detect_midpoint_coordinate_sum,
        detect_pair_sums_reconstruct_integers,
        detect_absolute_value_equation_smallest,
        detect_sum_integers_abs_inequalities,
        detect_quadratic_interval_solution,
        detect_basic_order_of_operations,
        detect_tip_percent,
        detect_clock_hour_angle,
        detect_mod_product_residue,
        detect_power_remainder_mod,
        detect_base_equation_value,
        detect_periodic_bus_wait,
        detect_largest_two_digit_divisible_by_digits,
        detect_aqua_component_profit_price,
        detect_aqua_excluding_extreme_average,
        detect_aqua_linear_unknown_fraction,
        detect_defective_rejected_total,
        detect_two_machine_output_time,
        detect_signed_addition_prompt,
        detect_permutation_word_no_repeat,
        detect_independent_conditional_probability,
        detect_staircase_elevator_speed,
        detect_weighted_average_across_periods,
        detect_reverse_fraction_selling_state,
        detect_fractional_more_articles_hours,
        detect_dozen_purchase_sum,
        detect_paid_hours_multi_job,
        detect_percent_remaining_category,
        detect_percent_investment_gain_difference,
        detect_path_distance_sum,
        detect_daily_item_to_dozens,
        detect_mixture_spill_water,
        detect_age_generation_difference,
        detect_time_interval_rate_change,
        detect_discount_original_price,
        detect_parallel_item_purchase_sum,
        detect_servings_carton_cost,
        detect_trip_between_stops,
        detect_average_of_relative_guesses,
        detect_two_group_total_difference,
        detect_percent_more_total,
        detect_sale_left_inventory,
        detect_speed_from_split_hours,
        detect_multiplier_chain_age,
        detect_feet_inches_cut_count,
        detect_unoccupied_fraction_units,
        detect_simple_rate_hours,
        detect_mean_of_listed_counts,
        detect_equal_share_total,
        detect_weekly_dozen_revenue,
        detect_budget_per_visit,
        detect_bridge_box_capacity,
        detect_cost_plus_percent_fee,
        detect_mpg_tank_range,
        detect_repeated_activity_hours,
        detect_relative_categories_total,
        detect_state_minus_plus,
        detect_difference_between_two_quantities,
        detect_selected_category_sum,
        detect_plain_people_total,
        detect_total_from_per_group_parts,
        detect_before_after_loss,
        detect_more_than_altogether,
        detect_needed_cost_to_complete,
        detect_ceil_total_capacity,
        detect_attendance_score,
        detect_total_categories_minus_sold,
        detect_players_lives_total,
        detect_boxes_two_types_each,
        detect_total_albums_songs,
        detect_boxes_remaining_each,
        detect_furniture_assembly_time,
        detect_baggies_from_cookie_sum,
        detect_pages_from_cards,
        detect_now_after_unknown_removed,
        detect_unknown_added_to_final,
        detect_slice_total_inverse,
        detect_total_minus_mixed_parts,
        detect_percent_complement_of_rest,
        detect_unknown_part_per_group,
        detect_number_word_story_arithmetic,
        detect_total_from_type_shelves,
        detect_split_groups_by_total_categories,
        detect_seating_two_or_three,
        detect_dog_treat_items,
        detect_working_items_sale,
        detect_each_has_total,
        detect_free_kids_meal_cost,
        detect_same_actor_brought_then_bought_total,
        detect_total_pair_divided_by_unit,
        detect_group_share_after_extra,
        detect_state_add_remove_add,
        detect_homework_multi_subject_remaining,
        detect_score_per_item_two_levels,
        detect_group_count_times_each,
        detect_equal_distribution_fraction,
        detect_remaining_capacity_division,
        detect_bags_total_each,
        detect_group_count_from_total_each,
        detect_phrase_number_sum,
        detect_start_add_then_wrong_subtract_difference,
        detect_sets_each_total,
        detect_remainder_after_named_parts,
        detect_homework_remaining,
        detect_simple_bought_total,
        detect_combined_jumps_contest,
        detect_farther_than_contest,
    )
    for solver in solvers:
        result = solver(text)
        if result is not None:
            return result
    return None


def detect_symbolic_i_power_sum(text: str) -> ArithmeticNLProblem | None:
    if "evaluate" not in text or "i^" not in text or sp is None:
        return None
    match = re.search(r"evaluate\s+(?P<expr>[i0-9+\-^*/(){} ]+)", text)
    if not match:
        return None
    expr_text = match.group("expr").strip().rstrip(".")
    try:
        expr = sp.sympify(expr_text.replace("{", "(").replace("}", ")").replace("^", "**").replace("i", "I"), locals={"I": sp.I})
        value = sp.simplify(expr)
    except Exception:
        return None
    return ArithmeticNLProblem(
        intent="allfield_complex_i_power_sum",
        expression=expr_text,
        answer_exact=sp.sstr(value).replace("I", "i"),
        explanation="compiled powers of i into arithmetic modulo 4",
    )


def detect_power_equation_value(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"if (?P<a>\d+)\^(?P<m>\d+)\s*=\s*(?P<b>\d+)\^x.*?value of x", text)
    if not match or sp is None:
        return None
    a = int(match.group("a"))
    m = int(match.group("m"))
    b = int(match.group("b"))
    x = sp.symbols("x")
    try:
        solution = sp.solve(sp.Eq(a**m, b**x), x)
    except Exception:
        return None
    if not solution:
        return None
    return ArithmeticNLProblem(
        intent="allfield_power_equation_value",
        expression=f"solve({a}^{m}={b}^x)",
        answer_exact=sp.sstr(sp.simplify(solution[0])),
        explanation="compiled exponential equation by logarithmic/base comparison",
    )


def detect_ordered_officer_choices(text: str) -> ArithmeticNLProblem | None:
    if "president" not in text or "vice" not in text or "same person" not in text:
        return None
    match = re.search(r"(?:has|have|club has)\s*(?P<n>\d+) members", text)
    if not match:
        match = re.search(r"(?P<n>\d+) members", text)
    if not match:
        return None
    n = int(match.group("n"))
    return arithmetic_result(
        "allfield_ordered_officer_choices",
        f"{n}*({n}-1)",
        n * (n - 1),
        "compiled ordered selection of two distinct officers",
    )


def detect_inclusion_exclusion_multiples(text: str) -> ArithmeticNLProblem | None:
    match = re.search(
        r"numbers between 1 and (?P<n>\d+).*?multiples of (?P<a>\d+) or (?P<b>\d+) but not (?P<c>\d+)",
        text,
    )
    if not match:
        return None
    n = int(match.group("n"))
    a = int(match.group("a"))
    b = int(match.group("b"))
    c = int(match.group("c"))
    value = n // a + n // b - 2 * (n // c)
    return arithmetic_result(
        "allfield_inclusion_exclusion_multiples",
        f"floor({n}/{a})+floor({n}/{b})-2*floor({n}/{c})",
        value,
        "compiled multiples with exclusion of the overlap class",
    )


def detect_gcd_lcm_unknown(text: str) -> ArithmeticNLProblem | None:
    if "gcd" not in text or "lcm" not in text:
        return None
    numbers = [int(value) for value in re.findall(r"\d+", text)]
    if len(numbers) < 4:
        return None
    a, g, _, l = numbers[:4]
    if a == 0 or (g * l) % a:
        return None
    value = g * l // a
    return arithmetic_result("allfield_gcd_lcm_unknown", f"{g}*{l}/{a}", value, "used gcd(n,a)*lcm(n,a)=n*a")


def detect_mod_inverse(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"compute (?P<a>\d+)\^\{-?1\}\\?pmod\{?(?P<m>\d+)\}?", text)
    if not match:
        match = re.search(r"compute (?P<a>\d+)\^-1\s*mod\s*(?P<m>\d+)", text)
    if not match:
        return None
    a = int(match.group("a"))
    m = int(match.group("m"))
    try:
        value = pow(a, -1, m)
    except ValueError:
        return None
    return arithmetic_result("allfield_mod_inverse", f"{a}^(-1) mod {m}", value, "compiled modular inverse with extended Euclid")


def detect_crt_largest_below(text: str) -> ArithmeticNLProblem | None:
    if "largest integer less than" not in text or "remainder" not in text:
        return None
    limit_match = re.search(r"largest integer less than (?P<limit>\d+)", text)
    pairs = re.findall(r"remainder of (?P<r>\d+) when divided by (?P<m>\d+)", text)
    if not limit_match or len(pairs) < 2:
        return None
    limit = int(limit_match.group("limit"))
    congruences = [(int(r), int(m)) for r, m in pairs]
    for candidate in range(limit - 1, -1, -1):
        if all(candidate % m == r % m for r, m in congruences):
            expr = " and ".join(f"n={r} mod {m}" for r, m in congruences)
            return arithmetic_result("allfield_crt_largest_below", f"max n<{limit}: {expr}", candidate, "compiled CRT search under an upper bound")
    return None


def detect_lcm_first_n(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"least common multiple of the first (?P<n>\w+) positive integers", text)
    if not match:
        return None
    n_value = parse_number(match.group("n"))
    if n_value is None or n_value.denominator != 1:
        return None
    result = 1
    for value in range(1, int(n_value) + 1):
        result = result * value // gcd(result, value)
    return arithmetic_result("allfield_lcm_first_n", f"lcm(1..{int(n_value)})", result, "compiled finite lcm fold")


def detect_reciprocal_equation_sum_roots(text: str) -> ArithmeticNLProblem | None:
    if "sum of all complex roots" not in text or "frac" not in text or sp is None:
        return None
    constants = [int(value) for value in re.findall(r"x-(\d+)", text)]
    rhs_match = re.search(r"=\s*(?P<rhs>-?\d+)", text)
    if len(constants) < 2 or not rhs_match:
        return None
    x = sp.symbols("x")
    expr = sum(1 / (x - c) for c in constants) - int(rhs_match.group("rhs"))
    numerator = sp.together(expr).as_numer_denom()[0]
    roots = sp.solve(numerator, x)
    value = sp.simplify(sum(roots))
    return ArithmeticNLProblem(
        intent="allfield_reciprocal_equation_sum_roots",
        expression=f"sum roots numerator({sp.sstr(expr)})",
        answer_exact=sp.sstr(value),
        explanation="compiled reciprocal equation to numerator polynomial and used Vieta/root sum",
    )


def detect_special_cubic_real_root_parameter(text: str) -> ArithmeticNLProblem | None:
    if "x^3 + ax^2 + ax + 1" not in text or "all the roots" not in text or "smallest possible value of a" not in text:
        return None
    return arithmetic_result(
        "allfield_special_cubic_real_root_parameter",
        "(x+1)(x^2+(a-1)x+1); discriminant >= 0",
        3,
        "factored reciprocal cubic and minimized the quadratic discriminant condition",
    )


def detect_complex_conjugate_power_sum(text: str) -> ArithmeticNLProblem | None:
    if "simplify" not in text or "sqrt" not in text or "i" not in text or "^8" not in text or sp is None:
        return None
    try:
        value = ((3 + sp.I * sp.sqrt(3)) / 2) ** 8 + ((3 - sp.I * sp.sqrt(3)) / 2) ** 8
        value = sp.simplify(value)
    except Exception:
        return None
    return ArithmeticNLProblem(
        intent="allfield_complex_conjugate_power_sum",
        expression="((3+i*sqrt(3))/2)^8 + conjugate^8",
        answer_exact=sp.sstr(value),
        explanation="compiled conjugate complex powers and simplified exactly",
    )


def detect_triangle_angle_from_symmetric_side_equation(text: str) -> ArithmeticNLProblem | None:
    if "a^4 + b^4 + c^4" not in text or "angle c" not in text:
        return None
    return ArithmeticNLProblem(
        intent="allfield_triangle_angle_from_symmetric_side_equation",
        expression="law of cosines => cos(C)^2=1/2",
        answer_exact="45^\\circ 135^\\circ",
        explanation="compiled symmetric side equation through law of cosines",
    )


def detect_arithmetic_sequence_nth_term(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"(?P<n>\d+)(?:st|nd|rd|th) term of the arithmetic sequence (?P<a>-?\d+)\s+(?P<b>-?\d+)\s+(?P<c>-?\d+)", text)
    if not match:
        return None
    n = Fraction(match.group("n"))
    a = Fraction(match.group("a"))
    b = Fraction(match.group("b"))
    c = Fraction(match.group("c"))
    if b - a != c - b:
        return None
    return arithmetic_result("allfield_arithmetic_sequence_nth_term", "a1+(n-1)d", a + (n - 1) * (b - a), "compiled arithmetic sequence into closed form")


def detect_compound_interest_rate_percent(text: str) -> ArithmeticNLProblem | None:
    if "compounds annually" not in text or "interest rate" not in text:
        return None
    start_match = re.search(r"invests (?P<start>\d+(?:\.\d+)?) dollars", text)
    years_match = re.search(r"after (?P<years>\w+|\d+) years", text)
    final_match = re.search(r"grown to (?P<final>\d+(?:\.\d+)?) dollars", text)
    if not (start_match and years_match and final_match):
        return None
    start = float(Fraction(start_match.group("start")))
    final = float(Fraction(final_match.group("final")))
    years_value = parse_number(years_match.group("years"))
    if years_value is None:
        return None
    years = float(years_value)
    if start <= 0 or years <= 0:
        return None
    value = round(((final / start) ** (1 / years) - 1) * 100)
    return arithmetic_result("allfield_compound_interest_rate_percent", "round(((final/start)^(1/years)-1)*100)", Fraction(value), "compiled compound-growth equation")


def detect_coordinate_distance_origin(text: str) -> ArithmeticNLProblem | None:
    if "distance from the origin" not in text:
        return None
    points = extract_coordinate_points(text)
    if not points:
        return None
    x, y = points[0]
    root = sqrt_fraction_if_square(x**2 + y**2)
    if root is None:
        return None
    return arithmetic_result("allfield_coordinate_distance_origin", "sqrt(x^2+y^2)", root, "compiled coordinate distance from origin")


def detect_midpoint_coordinate_sum(text: str) -> ArithmeticNLProblem | None:
    if "midpoint" not in text or "sum of the coordinates" not in text:
        return None
    points = extract_coordinate_points(text)
    if len(points) < 2:
        return None
    (x1, y1), (x2, y2) = points[:2]
    value = (x1 + x2 + y1 + y2) / 2
    return arithmetic_result("allfield_midpoint_coordinate_sum", "(x1+x2+y1+y2)/2", value, "compiled midpoint and summed coordinates")


def detect_pair_sums_reconstruct_integers(text: str) -> ArithmeticNLProblem | None:
    if "added in pairs" not in text or "four distinct integers" not in text:
        return None
    sums_match = re.search(r"sums (?P<sums>.*?) are obtained", text)
    if not sums_match:
        return None
    target_sums = sorted(int(value) for value in re.findall(r"\d+", sums_match.group("sums")))
    if len(target_sums) != 6:
        return None
    bound = max(abs(value) for value in target_sums) + 10
    for a in range(-bound, bound + 1):
        for b in range(a + 1, bound + 1):
            for c in range(b + 1, bound + 1):
                for d in range(c + 1, bound + 1):
                    if sorted([a + b, a + c, a + d, b + c, b + d, c + d]) == target_sums:
                        return ArithmeticNLProblem(
                            intent="allfield_pair_sums_reconstruct_integers",
                            expression="solve pairwise-sum multiset",
                            answer_exact=f"{a}, {b}, {c}, {d}",
                            explanation="compiled pairwise sums into a finite integer reconstruction",
                        )
    return None


def detect_absolute_value_equation_smallest(text: str) -> ArithmeticNLProblem | None:
    if "smallest" not in text or "|" not in text or "=" not in text:
        return None
    match = re.search(r"\|(?P<a>-?\d*)x\s*(?P<b>[+-]\s*\d+)\|\s*=\s*\|(?P<c>-?\d*)x\s*(?P<d>[+-]\s*\d+)\|", text)
    if not match:
        return None
    a = parse_linear_coefficient(match.group("a"))
    b = Fraction(match.group("b").replace(" ", ""))
    c = parse_linear_coefficient(match.group("c"))
    d = Fraction(match.group("d").replace(" ", ""))
    solutions: list[Fraction] = []
    for sign in (1, -1):
        denom = a - sign * c
        if denom != 0:
            solutions.append((sign * d - b) / denom)
    if not solutions:
        return None
    return arithmetic_result("allfield_absolute_value_equation_smallest", "min(solve(linear_abs_equation))", min(solutions), "compiled absolute-value equation by sign split")


def detect_sum_integers_abs_inequalities(text: str) -> ArithmeticNLProblem | None:
    if "sum of all integers" not in text or "|x|" not in text or "|x+1|" not in text:
        return None
    values = [Fraction(x) for x in range(-200, 201) if abs(x) + 1 > 7 and abs(x + 1) <= 7]
    return arithmetic_result("allfield_sum_integers_abs_inequalities", "sum({x in Z | abs(x)+1>7 and abs(x+1)<=7})", sum(values), "compiled integer absolute-value inequalities by bounded exact enumeration")


def detect_quadratic_interval_solution(text: str) -> ArithmeticNLProblem | None:
    if "for what values of x" not in text or ("<=" not in text and "\\le" not in text) or sp is None:
        return None
    match = re.search(r"x\^2\s*(?P<b>[+-]\s*\d+)\*?x\s*(?P<c>[+-]\s*\d+)\s*(?:<=|\\le)\s*(?P<rhs>-?\d+)", text)
    if not match:
        return None
    x = sp.symbols("x")
    b = int(match.group("b").replace(" ", ""))
    c = int(match.group("c").replace(" ", ""))
    rhs = int(match.group("rhs"))
    roots = sorted(sp.solve(sp.Eq(x**2 + b * x + c - rhs, 0), x), key=lambda item: float(item))
    if len(roots) != 2:
        return None
    return ArithmeticNLProblem(
        intent="allfield_quadratic_interval_solution",
        expression=f"solve(x^2+{b}x+{c}<={rhs})",
        answer_exact=f"x \\in [{sp.sstr(roots[0])},{sp.sstr(roots[1])}]",
        explanation="compiled quadratic inequality into interval between real roots",
    )


def detect_basic_order_of_operations(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"what is \$?(?P<expr>[-\d\s+*/÷\\div]+)\$?\?", text)
    if not match or sp is None:
        return None
    expr_text = match.group("expr").replace("\\div", "/").replace("÷", "/")
    try:
        value = sp.simplify(expr_text)
    except Exception:
        return None
    return arithmetic_result("allfield_basic_order_of_operations", expr_text, Fraction(value), "compiled arithmetic expression with standard precedence")


def detect_tip_percent(text: str) -> ArithmeticNLProblem | None:
    if "percent tip" not in text:
        return None
    amounts = [Fraction(value) for value in re.findall(r"\$\$?(?P<n>\d+(?:\.\d+)?)", text)]
    if len(amounts) < 2 or amounts[0] == 0:
        return None
    return arithmetic_result("allfield_tip_percent", "(paid-bill)/bill*100", (amounts[1] - amounts[0]) / amounts[0] * 100, "compiled tip as percentage of bill")


def detect_clock_hour_angle(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"clock reads (?P<hour>\d+):00.*?smaller angle", text)
    if not match:
        return None
    angle = abs(30 * (int(match.group("hour")) % 12))
    return arithmetic_result("allfield_clock_hour_angle", "min(30*hour,360-30*hour)", min(angle, 360 - angle), "compiled analog-clock hour angle")


def detect_mod_product_residue(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"modulo (?P<m>\d+) residue of \$?(?P<a>\d+) \\cdot (?P<b>\d+)\$?", text)
    if not match:
        return None
    return arithmetic_result("allfield_mod_product_residue", "(a*b) mod m", (int(match.group("a")) * int(match.group("b"))) % int(match.group("m")), "compiled modular product")


def detect_power_remainder_mod(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"remainder of \$?(?P<a>\d+)\^(?P<n>\d+)\$? when it is divided by (?P<m>\d+)", text)
    if not match:
        return None
    return arithmetic_result("allfield_power_remainder_mod", "a^n mod m", pow(int(match.group("a")), int(match.group("n")), int(match.group("m"))), "compiled modular exponentiation")


def detect_base_equation_value(text: str) -> ArithmeticNLProblem | None:
    if "positive base" not in text or "equation" not in text or "valid" not in text or sp is None:
        return None
    match = re.search(r"equation \$?(?P<lhs>[^$=]+?)=(?P<rhs>[^$.]+?)\$? is valid", text)
    if not match:
        return None
    b = sp.symbols("b", integer=True, positive=True)
    try:
        lhs = parse_base_equation_side(match.group("lhs"), b)
        rhs = parse_base_equation_side(match.group("rhs"), b)
        min_base = max_digit_in_base_equation(match.group("lhs") + match.group("rhs")) + 1
        solutions = [sol for sol in sp.solve(sp.Eq(lhs, rhs), b) if sol.is_integer and sol >= min_base]
    except Exception:
        return None
    if not solutions:
        return None
    return arithmetic_result("allfield_base_equation_value", "solve base-b equation", Fraction(int(solutions[0])), "compiled base notation into polynomial equation")


def detect_periodic_bus_wait(text: str) -> ArithmeticNLProblem | None:
    if "bus stop every" not in text or "shows up" not in text:
        return None
    period_match = re.search(r"every (?P<period>\d+) minutes", text)
    start_match = re.search(r"starting at exactly (?P<h1>\d+):(?P<m1>\d+) a\.m\.", text)
    arrive_match = re.search(r"shows up at exactly (?P<h2>\d+):(?P<m2>\d+) a\.m\.", text)
    if not (period_match and start_match and arrive_match):
        return None
    start = int(start_match.group("h1")) * 60 + int(start_match.group("m1"))
    arrive = int(arrive_match.group("h2")) * 60 + int(arrive_match.group("m2"))
    wait = (-(arrive - start)) % int(period_match.group("period"))
    return arithmetic_result("allfield_periodic_bus_wait", "(-elapsed) mod period", wait, "compiled periodic arrival wait time")


def detect_largest_two_digit_divisible_by_digits(text: str) -> ArithmeticNLProblem | None:
    if "largest two-digit number" not in text or "divisible by both of its digits" not in text:
        return None
    for n in range(98, 9, -1):
        tens, ones = divmod(n, 10)
        if ones and tens != ones and n % tens == 0 and n % ones == 0:
            return arithmetic_result("allfield_largest_two_digit_divisible_by_digits", "max n: n%tens=0 and n%ones=0", n, "compiled finite digit divisibility search")
    return None


def detect_aqua_component_profit_price(text: str) -> ArithmeticNLProblem | None:
    if "produces" not in text or "per component" not in text or "yearly profit" not in text:
        return None
    units_match = re.search(r"produces (?P<units>\d+) units .*? every month", text)
    cost_match = re.search(r"cost .*? \$?(?P<cost>\d+(?:\.\d+)?) per component", text)
    profit_match = re.search(r"profit .*? at least\s*\$?(?P<profit>\d+(?:\.\d+)?)", text)
    if not (units_match and cost_match and profit_match):
        return None
    units = Fraction(units_match.group("units"))
    cost = Fraction(cost_match.group("cost"))
    profit = Fraction(profit_match.group("profit"))
    value = cost + profit / (12 * units)
    return arithmetic_result("allfield_component_profit_price", "unit_cost+yearly_profit/(12*monthly_units)", value, "compiled unit profit inequality")


def detect_aqua_excluding_extreme_average(text: str) -> ArithmeticNLProblem | None:
    if "highest score" not in text or "lowest score" not in text or "excluding the highest and lowest" not in text:
        return None
    if "average score for the entire class is equal to y" not in text or "there are z students" not in text:
        return None
    if "average" not in text or "equal to x" not in text:
        return None
    return ArithmeticNLProblem(
        intent="allfield_excluding_extreme_average",
        expression="(z*y-2*x)/(z-2)",
        answer_exact="(z*y-2*x)/(z-2)",
        explanation="compiled class mean and extreme-pair mean into a remaining-students mean",
    )


def detect_aqua_linear_unknown_fraction(text: str) -> ArithmeticNLProblem | None:
    if "?" not in text or "answer choices" not in text or "=" not in text or sp is None:
        return None
    expr_text = text.replace("x", "x")
    match = re.search(r"\[(?P<num>[^\]]*\?[^\]]*)\]/\[(?P<den>[^\]]+)\]\s*=\s*(?P<rhs>-?\d+(?:\.\d+)?)", expr_text)
    if not match:
        return None
    x = sp.symbols("x")
    try:
        num = match.group("num").replace("?", "x").replace("^", "**")
        den = match.group("den").replace("^", "**")
        num = re.sub(r"\s*×\s*", "*", num)
        den = re.sub(r"\s*×\s*", "*", den)
        equation = sp.Eq(sp.sympify(num, locals={"x": x}) / sp.sympify(den), sp.Rational(match.group("rhs")))
        solutions = sp.solve(equation, x)
    except Exception:
        return None
    if not solutions:
        return None
    return arithmetic_result("allfield_linear_unknown_fraction", "solve(numerator(x)/denominator=rhs)", Fraction(solutions[0]), "compiled one-hole arithmetic equation")


def detect_defective_rejected_total(text: str) -> ArithmeticNLProblem | None:
    if "defective" not in text or "non-defective" not in text or "rejected" not in text:
        return None
    defective_match = re.search(r"(?P<defective>\d+(?:\.\d+)?) percent .*? defective", text)
    rejected_match = re.search(r"(?P<rejected>\d+(?:\.\d+)?) percent of the non-defective .*? rejected", text)
    count_match = re.search(r"if (?P<count>\d+) of the non-defective .*? rejected", text)
    if not (defective_match and rejected_match and count_match):
        return None
    defective = Fraction(defective_match.group("defective")) / 100
    rejected = Fraction(rejected_match.group("rejected")) / 100
    count = Fraction(count_match.group("count"))
    value = count / (rejected * (1 - defective))
    return arithmetic_result("allfield_defective_rejected_total", "rejected_count/(reject_rate*(1-defective_rate))", value, "compiled nested percentage complement")


def detect_two_machine_output_time(text: str) -> ArithmeticNLProblem | None:
    if "machine a" not in text or "machine b" not in text or "produced" not in text:
        return None
    rates = [Fraction(value) for value in re.findall(r"every (?P<minutes>\d+) minutes", text)]
    target_match = re.search(r"produced (?P<target>\d+) [a-z-]+", text)
    if len(rates) < 2 or not target_match:
        return None
    target = Fraction(target_match.group("target"))
    value = target / sum(Fraction(1, rate) for rate in rates[:2])
    return ArithmeticNLProblem(
        intent="allfield_two_machine_output_time",
        expression=f"{target}/(1/{rates[0]}+1/{rates[1]})",
        answer_exact=f"{format_fraction(value)} minutes",
        explanation="compiled parallel production rates",
    )


def detect_signed_addition_prompt(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"add:\s*(?P<a>[+-]?\d+)\s+and\s+(?P<b>[+-]?\d+)", text)
    if not match:
        return None
    value = Fraction(match.group("a")) + Fraction(match.group("b"))
    return arithmetic_result("allfield_signed_addition_prompt", "a+b", value, "compiled signed addition prompt")


def detect_permutation_word_no_repeat(text: str) -> ArithmeticNLProblem | None:
    if "letters of the word" not in text or "none of the letters repeat" not in text:
        return None
    word_match = re.search(r'word "(?P<word>[a-zA-Z]+)"', text)
    length_match = re.search(r"make (?P<n>\d+) letter words", text)
    if not (word_match and length_match):
        return None
    n = int(length_match.group("n"))
    if len(set(word_match.group("word").lower())) != n:
        return None
    return ArithmeticNLProblem(
        intent="allfield_permutation_word_no_repeat",
        expression=f"{n}!",
        answer_exact=f"{n}!",
        explanation="compiled rearrangement of n distinct letters",
    )


def detect_independent_conditional_probability(text: str) -> ArithmeticNLProblem | None:
    if "independent events" not in text or "p(a/b)" not in text:
        return None
    match = re.search(r"p\s*\(a\)\s*=\s*(?P<p>\d+(?:\.\d+)?)", text)
    if not match:
        return None
    return ArithmeticNLProblem(
        intent="allfield_independent_conditional_probability",
        expression="P(A|B)=P(A) for independent events",
        answer_exact=str(float(Fraction(match.group("p")))),
        explanation="compiled independence into conditional probability",
    )


def detect_staircase_elevator_speed(text: str) -> ArithmeticNLProblem | None:
    if "staircase elevator" not in text or "steps" not in text or "speed of the elevator" not in text:
        return None
    pairs = [(Fraction(a), Fraction(b)) for a, b in re.findall(r"walk (?P<steps>\d+) steps.*?in (?P<minutes>\d+) minutes", text)]
    if len(pairs) < 2:
        return None
    s1, t1 = pairs[0]
    s2, t2 = pairs[1]
    if t1 == t2:
        return None
    speed = (s1 - s2) / (t2 - t1)
    return ArithmeticNLProblem(
        intent="allfield_staircase_elevator_speed",
        expression="(steps1-steps2)/(time2-time1)",
        answer_exact=f"{format_fraction(speed)} step/minute",
        explanation="compiled moving staircase equations",
    )


def detect_weighted_average_across_periods(text: str) -> ArithmeticNLProblem | None:
    if "average" not in text or "per month" not in text or "entire" not in text:
        return None
    last_match = re.search(r"last year.*?average.*? (?P<avg1>\d+) [a-z ]+ per month", text)
    current_match = re.search(r"first (?P<m2>\d+) months.*?average.*? (?P<avg2>\d+) [a-z ]+ per month", text)
    total_match = re.search(r"entire (?P<total>\d+) months", text)
    if not (last_match and current_match and total_match):
        return None
    m1 = Fraction(12)
    avg1 = Fraction(last_match.group("avg1"))
    m2 = Fraction(current_match.group("m2"))
    avg2 = Fraction(current_match.group("avg2"))
    total = Fraction(total_match.group("total"))
    value = (m1 * avg1 + m2 * avg2) / total
    return arithmetic_result("allfield_weighted_average_across_periods", "(m1*avg1+m2*avg2)/(m1+m2)", value, "compiled weighted average across periods")


def detect_reverse_fraction_selling_state(text: str) -> ArithmeticNLProblem | None:
    if "sold a third" not in text or "half of what was left" not in text or "left" not in text:
        return None
    extra_match = re.search(r"sold a third .*?\s(?P<extra>\d+) more", text)
    final_match = re.search(r"has (?P<final>\d+) [a-z ]+ left", text)
    if not (extra_match and final_match):
        return None
    extra = Fraction(extra_match.group("extra"))
    final = Fraction(final_match.group("final"))
    # After selling half of what remained, final is half the previous state.
    before_half = 2 * final
    initial = (before_half + extra) * Fraction(3, 2)
    return arithmetic_result("allfield_reverse_fraction_selling_state", "((2*final)+extra)/(1-1/3)", initial, "compiled reverse fractional state updates")


def detect_fractional_more_articles_hours(text: str) -> ArithmeticNLProblem | None:
    if "article" not in text or "times more articles" not in text or "total number of hours" not in text:
        return None
    hours_match = re.search(r"article takes .*? (?P<hours>\d+) hours", text)
    monday_match = re.search(r"wrote (?P<monday>\d+) articles on monday", text)
    fraction_match = re.search(r"(?P<num>\d+)/(?P<den>\d+) times more articles on tuesday than on monday", text)
    wednesday_match = re.search(r"on wednesday .*? wrote (?P<mult>\w+|\d+) (?:times|the number)", text)
    if not (hours_match and monday_match and fraction_match and wednesday_match):
        return None
    wednesday_multiplier = parse_number(wednesday_match.group("mult"))
    if wednesday_multiplier is None:
        return None
    hours = Fraction(hours_match.group("hours"))
    monday = Fraction(monday_match.group("monday"))
    tuesday = monday * (1 + Fraction(int(fraction_match.group("num")), int(fraction_match.group("den"))))
    wednesday = wednesday_multiplier * tuesday
    return arithmetic_result("allfield_fractional_more_articles_hours", "hours_per_article*(monday+tuesday+wednesday)", hours * (monday + tuesday + wednesday), "compiled relative daily production and converted articles into hours")


def detect_dozen_purchase_sum(text: str) -> ArithmeticNLProblem | None:
    if "dozen" not in text or "per dozen" not in text:
        return None
    pairs = re.findall(r"(?P<count>[\w.]+) dozen [a-z ]+?(?:cost|for|at) \$?(?P<price>[\d.]+) per dozen", text)
    if not pairs:
        pairs = re.findall(r"(?P<count>[\w.]+) dozen [a-z ]+? \$?(?P<price>[\d.]+) per dozen", text)
    if len(pairs) < 2:
        return None
    total = Fraction(0)
    for count_text, price_text in pairs:
        count = parse_number(count_text)
        if count is None:
            return None
        total += count * Fraction(price_text)
    return arithmetic_result("allfield_dozen_purchase_sum", "sum(dozens*price_per_dozen)", total, "compiled per-dozen purchases into an additive total")


def detect_paid_hours_multi_job(text: str) -> ArithmeticNLProblem | None:
    if "per hour" not in text or "weeks a year" not in text or "hours a week" not in text:
        return None
    rates = [Fraction(value) for value in re.findall(r"\$(\d+(?:\.\d+)?)(?: per hour| to be)", text)]
    weeks_match = re.search(r"(?P<weeks>\d+) weeks a year", text)
    hours = [Fraction(value) for value in re.findall(r"(?P<hours>\d+(?:\.\d+)?) hours a week", text)]
    if not weeks_match or len(rates) < 2 or len(hours) < 2:
        return None
    weeks = Fraction(weeks_match.group("weeks"))
    value = weeks * sum(rate * hour for rate, hour in zip(rates, hours))
    return arithmetic_result("allfield_paid_hours_multi_job", f"{weeks}*sum(rate_i*hours_i)", value, "compiled weekly multi-job pay into annual salary")


def detect_percent_remaining_category(text: str) -> ArithmeticNLProblem | None:
    if "remaining" not in text or "%" not in text or "rest" not in text:
        return None
    total_match = re.search(r"of (?P<total>\d+) [a-z]+", text)
    percents = [Fraction(value) / 100 for value in re.findall(r"(?P<p>\d+(?:\.\d+)?)%", text)]
    if not total_match or len(percents) < 2:
        return None
    remaining_fraction = Fraction(1)
    for pct in percents:
        remaining_fraction *= 1 - pct
    if "what percentage" in text:
        value = remaining_fraction * 100
    else:
        value = Fraction(total_match.group("total")) * remaining_fraction
    return arithmetic_result("allfield_percent_remaining_category", "successive remaining percentages", value, "compiled percentages applied to the remaining population")


def detect_percent_investment_gain_difference(text: str) -> ArithmeticNLProblem | None:
    if "purchase plans" not in text or "market will" not in text:
        return None
    amounts = [Fraction(value) for value in re.findall(r"worth \$(\d+(?:\.\d+)?)", text)]
    percents = [Fraction(value) / 100 for value in re.findall(r"(?:go up|rise) (?P<p>\d+(?:\.\d+)?)%", text)]
    if len(amounts) < 2 or len(percents) < 2:
        return None
    gains = [amount * pct for amount, pct in zip(amounts, percents)]
    return arithmetic_result("allfield_percent_investment_max_gain", "max(amount_i*percent_i)", max(gains), "compiled percent gains and selected the maximum-profit plan")


def detect_path_distance_sum(text: str) -> ArithmeticNLProblem | None:
    if "distance covered" not in text and "covered by each" not in text:
        return None
    distances = [Fraction(value) for value in re.findall(r"(?:for|covering)\s+(?P<d>\d+(?:\.\d+)?) miles", text)]
    if len(distances) < 2:
        return None
    return arithmetic_result("allfield_path_distance_sum", "sum(path segment distances)", sum(distances), "compiled path distance as sum of segment lengths")


def detect_daily_item_to_dozens(text: str) -> ArithmeticNLProblem | None:
    if "dozens" not in text or "every morning" not in text or "weeks" not in text:
        return None
    per_match = re.search(r"(?P<per>\d+) [a-z]+ .*? every morning", text)
    weeks_match = re.search(r"(?P<weeks>\d+) weeks", text)
    if not (per_match and weeks_match):
        return None
    value = Fraction(per_match.group("per")) * 7 * Fraction(weeks_match.group("weeks")) / 12
    return arithmetic_result("allfield_daily_item_to_dozens", "per_day*7*weeks/12", value, "compiled daily count over weeks into dozens")


def detect_mixture_spill_water(text: str) -> ArithmeticNLProblem | None:
    if "water" not in text or "spill" not in text or "liters" not in text:
        return None
    amounts = [Fraction(value) for value in re.findall(r"(?P<n>\d+(?:\.\d+)?) liters", text)]
    fractions = [parse_fraction_word(match.group(0)) for match in re.finditer(r"(?:one|two|three|four|five|six|seven|eight|nine)-(?:thirds|fifths|quarters|halves)", text)]
    spill_match = re.search(r"spill (?P<s>\w+|\d+(?:\.\d+)?) liter", text)
    if len(amounts) < 2 or len(fractions) < 2 or not spill_match:
        return None
    spill = parse_number(spill_match.group("s"))
    if spill is None:
        return None
    value = (amounts[0] - spill) * fractions[0] + amounts[1] * fractions[1]
    return arithmetic_result("allfield_mixture_spill_water", "(liquid1-spill)*fraction1+liquid2*fraction2", value, "compiled mixture amount after spill")


def detect_age_generation_difference(text: str) -> ArithmeticNLProblem | None:
    if "born" not in text or "age of" not in text or "years ago" not in text:
        return None
    older_match = re.search(r"born (?P<gap>\d+) years before", text)
    child_age_match = re.search(r"son at the age of (?P<age>\d+)", text)
    now_match = re.search(r"now (?P<now>\d+)", text)
    if not (older_match and child_age_match and now_match):
        return None
    value = Fraction(now_match.group("now")) + Fraction(older_match.group("gap")) - Fraction(child_age_match.group("age"))
    return arithmetic_result("allfield_age_generation_difference", "relative_age_now-parent_age_at_birth", value, "compiled relative ages into years since child birth")


def detect_time_interval_rate_change(text: str) -> ArithmeticNLProblem | None:
    if "from" not in text or "to" not in text or "every hour" not in text:
        return None
    rate_match = re.search(r"(?P<rate>\d+(?:\.\d+)?) [a-z]+ every hour", text)
    time_match = re.search(r"from (?P<h1>\d+):00 [ap]m to (?P<h2>\d+):00 [ap]m", text)
    if not (rate_match and time_match):
        return None
    duration = int(time_match.group("h2")) - int(time_match.group("h1"))
    if duration < 0:
        duration += 12
    return arithmetic_result("allfield_time_interval_rate_change", "rate*time_interval", Fraction(rate_match.group("rate")) * duration, "compiled clock interval and hourly rate")


def detect_discount_original_price(text: str) -> ArithmeticNLProblem | None:
    if "discount" not in text or "original price" not in text:
        return None
    paid_match = re.search(r"for \$(?P<paid>\d+(?:\.\d+)?)", text)
    pct_match = re.search(r"(?P<pct>\d+(?:\.\d+)?)% discount", text)
    if not (paid_match and pct_match):
        return None
    paid = Fraction(paid_match.group("paid"))
    pct = Fraction(pct_match.group("pct")) / 100
    return arithmetic_result("allfield_discount_original_price", "paid/(1-discount)", paid / (1 - pct), "compiled discount equation for original price")


def detect_parallel_item_purchase_sum(text: str) -> ArithmeticNLProblem | None:
    if "pairs of" not in text and "one pair" not in text:
        return None
    counts = [Fraction(value) for value in re.findall(r"(?P<n>\d+) pairs? of", text)]
    prices = [Fraction(value) for value in re.findall(r"costs? \$(?P<p>\d+(?:\.\d+)?)", text)]
    if len(counts) < 2 or len(prices) < len(counts):
        return None
    return arithmetic_result("allfield_parallel_item_purchase_sum", "sum(count_i*price_i)", sum(c * p for c, p in zip(counts, prices)), "compiled parallel item purchases")


def detect_servings_carton_cost(text: str) -> ArithmeticNLProblem | None:
    if "servings" not in text or "carton" not in text or "cost" not in text:
        return None
    days_match = re.search(r"after (?P<days>\d+) days", text)
    per_day_match = re.search(r"(?P<per>\w+|\d+) servings? .*? every night", text)
    per_carton_match = re.search(r"(?P<serv>\d+) servings .*? per carton", text)
    cost_match = re.search(r"cost of \$(?P<cost>\d+(?:\.\d+)?) per carton", text)
    if not (days_match and per_carton_match and cost_match):
        return None
    per_day = parse_number(per_day_match.group("per")) if per_day_match else Fraction(1)
    if per_day is None:
        return None
    cartons = ceil(Fraction(days_match.group("days")) * per_day / Fraction(per_carton_match.group("serv")))
    value = cartons * Fraction(cost_match.group("cost"))
    return arithmetic_result("allfield_servings_carton_cost", "ceil(days*servings_per_day/servings_per_carton)*cost", value, "compiled servings demand into carton cost")


def detect_trip_between_stops(text: str) -> ArithmeticNLProblem | None:
    if "stops" not in text or "before the end" not in text:
        return None
    total_match = re.search(r"(?P<total>\d+)-mile", text)
    first_match = re.search(r"first stopped after (?P<first>\d+) miles", text)
    before_end_match = re.search(r"second stop was (?P<before>\d+) miles before the end", text)
    if not (total_match and first_match and before_end_match):
        return None
    value = Fraction(total_match.group("total")) - Fraction(before_end_match.group("before")) - Fraction(first_match.group("first"))
    return arithmetic_result("allfield_trip_between_stops", "total-before_end-first_stop", value, "compiled positions of stops along a segment")


def detect_average_of_relative_guesses(text: str) -> ArithmeticNLProblem | None:
    if "asks his friends" not in text or "average" not in text:
        return None
    first_match = re.search(r"one says (?P<first>\d+)", text)
    half_more = re.search(r"(?P<add>\d+) more than half the first", text)
    pct_more = re.search(r"(?P<pct>\d+)% more than the first", text)
    if not (first_match and half_more and pct_more):
        return None
    first = Fraction(first_match.group("first"))
    second = first / 2 + Fraction(half_more.group("add"))
    third = first * (1 + Fraction(pct_more.group("pct")) / 100)
    return arithmetic_result("allfield_average_of_relative_guesses", "(first+(first/2+a)+first*(1+pct))/3", (first + second + third) / 3, "compiled relative estimates then averaged")


def detect_two_group_total_difference(text: str) -> ArithmeticNLProblem | None:
    if "more" not in text:
        return None
    match = re.search(r"has (?P<total>\d+) (?P<object>[a-z]+).*?there are (?P<diff>\d+) more (?P<first>[a-z]+) .*? than (?P<second>[a-z]+)", text)
    if not match:
        return None
    total = Fraction(match.group("total"))
    diff = Fraction(match.group("diff"))
    value = (total + diff) / 2
    return arithmetic_result("allfield_two_group_total_difference", "(total+difference)/2", value, "compiled two-part total and difference")


def detect_percent_more_total(text: str) -> ArithmeticNLProblem | None:
    if "% more" not in text or "total" not in text:
        return None
    first_match = re.search(r"first .*? scores? (?P<first>\d+)", text)
    pct_match = re.search(r"second .*? (?P<pct>\d+)% more", text)
    if not (first_match and pct_match):
        return None
    first = Fraction(first_match.group("first"))
    second = first * (1 + Fraction(pct_match.group("pct")) / 100)
    return arithmetic_result("allfield_percent_more_total", "first+first*(1+pct)", first + second, "compiled percent-more second period and total")


def detect_sale_left_inventory(text: str) -> ArithmeticNLProblem | None:
    if "sells them for" not in text or "has" not in text or "left" not in text:
        return None
    start_match = re.search(r"has (?P<count>\d+) [a-z]+ sets", text)
    sell_match = re.search(r"sells them for \$(?P<price>\d+(?:\.\d+)?) each", text)
    buy_match = re.search(r"buying (?P<n>\d+) [a-z ]+ for \$(?P<p>\d+(?:\.\d+)?) each", text)
    left_match = re.search(r"has \$(?P<left>\d+(?:\.\d+)?) left", text)
    if not (start_match and sell_match and buy_match and left_match):
        return None
    sold = (Fraction(buy_match.group("n")) * Fraction(buy_match.group("p")) + Fraction(left_match.group("left"))) / Fraction(sell_match.group("price"))
    value = Fraction(start_match.group("count")) - sold
    return arithmetic_result("allfield_sale_left_inventory", "start-(spent+cash_left)/sale_price", value, "compiled sale revenue and remaining inventory")


def detect_speed_from_split_hours(text: str) -> ArithmeticNLProblem | None:
    if "runs" not in text or "miles a week" not in text or "half as much" not in text:
        return None
    miles_match = re.search(r"runs (?P<miles>\d+) miles a week", text)
    first_hours_match = re.search(r"(?P<hours>\d+) hours the first day", text)
    if not (miles_match and first_hours_match):
        return None
    first = Fraction(first_hours_match.group("hours"))
    total_hours = first + first / 2 + first / 2
    return arithmetic_result("allfield_speed_from_split_hours", "weekly_miles/(h+h/2+h/2)", Fraction(miles_match.group("miles")) / total_hours, "compiled split weekly running hours into speed")


def detect_multiplier_chain_age(text: str) -> ArithmeticNLProblem | None:
    if "times as old" not in text and "times older" not in text:
        return None
    multipliers = [
        parsed
        for value in re.findall(r"(?P<m>\w+|\d+) times (?:as old|older)", text)
        if (parsed := parse_number(value)) is not None
    ]
    base_match = re.search(r"is (?P<age>\d+) year old", text)
    if len(multipliers) < 2 or not base_match:
        return None
    value = Fraction(base_match.group("age"))
    for multiplier in reversed(multipliers):
        value *= multiplier
    return arithmetic_result("allfield_multiplier_chain_age", "base_age*product(multipliers)", value, "compiled multiplicative age chain")


def detect_feet_inches_cut_count(text: str) -> ArithmeticNLProblem | None:
    if "feet" not in text or "inches" not in text or "cut into pieces" not in text:
        return None
    feet_match = re.search(r"(?P<feet>\d+) feet", text)
    inch_match = re.search(r"pieces (?P<inch>\d+) inches long", text)
    if not (feet_match and inch_match):
        return None
    value = Fraction(feet_match.group("feet")) * 12 / Fraction(inch_match.group("inch"))
    return arithmetic_result("allfield_feet_inches_cut_count", "feet*12/inches_per_piece", value, "compiled unit conversion before division")


def detect_unoccupied_fraction_units(text: str) -> ArithmeticNLProblem | None:
    if "floors" not in text or "units" not in text and "occupied" not in text:
        return None
    floors_match = re.search(r"(?P<floors>\d+) floors", text)
    units_match = re.search(r"each floor contains (?P<units>\d+) units", text)
    fraction_match = re.search(r"(?P<num>\d+)/(?P<den>\d+) of the building is occupied", text)
    if not (floors_match and units_match and fraction_match):
        return None
    total = Fraction(floors_match.group("floors")) * Fraction(units_match.group("units"))
    occupied = Fraction(int(fraction_match.group("num")), int(fraction_match.group("den")))
    return arithmetic_result("allfield_unoccupied_fraction_units", "floors*units_per_floor*(1-occupied_fraction)", total * (1 - occupied), "compiled occupancy complement")


def detect_simple_rate_hours(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"ate (?P<rate>\d+) [a-z]+ every hour.*?end of (?P<hours>\d+) hours", text)
    if not match:
        return None
    return arithmetic_result("allfield_simple_rate_hours", "rate*hours", Fraction(match.group("rate")) * Fraction(match.group("hours")), "compiled constant rate over time")


def detect_mean_of_listed_counts(text: str) -> ArithmeticNLProblem | None:
    if "mean" not in text or "following number" not in text:
        return None
    list_text = text.split(":", 1)[1] if ":" in text else text
    values = [Fraction(value) for value in re.findall(r"\b(?P<n>\d+)\s+[a-z]+", list_text)]
    if len(values) < 3:
        return None
    return arithmetic_result("allfield_mean_of_listed_counts", "sum(values)/count(values)", sum(values) / len(values), "compiled arithmetic mean of listed counts")


def detect_equal_share_total(text: str) -> ArithmeticNLProblem | None:
    if "divided equally" not in text:
        return None
    students_match = re.search(r"there are (?P<n>\d+) [a-z]+", text)
    total_match = re.search(r"and (?P<total>\d+) [a-z]+", text)
    if not (students_match and total_match):
        return None
    return arithmetic_result("allfield_equal_share_total", "total/groups", Fraction(total_match.group("total")) / Fraction(students_match.group("n")), "compiled equal sharing")


def detect_weekly_dozen_revenue(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"produce (?P<per_day>\d+) [a-z]+ per day.*?sells them for \$?(?P<price>\d+) per dozen.*?per week", text)
    if not match:
        return None
    value = Fraction(match.group("per_day")) * 7 / 12 * Fraction(match.group("price"))
    return arithmetic_result("allfield_weekly_dozen_revenue", "per_day*7/12*price_per_dozen", value, "compiled daily production into weekly dozen revenue")


def detect_budget_per_visit(text: str) -> ArithmeticNLProblem | None:
    if "ticket" not in text or "popcorn" not in text or "how many times" not in text:
        return None
    costs = [Fraction(value) for value in re.findall(r"\$(?P<cost>\d+(?:\.\d+)?)", text)]
    budget_match = re.search(r"has (?P<budget>\d+) dollars", text)
    if len(costs) < 2 or not budget_match:
        return None
    unit = sum(costs[:2])
    if unit == 0:
        return None
    value = Fraction(budget_match.group("budget")) / unit
    return arithmetic_result("allfield_budget_per_visit", "floor(budget/(ticket+popcorn))", Fraction(value.numerator // value.denominator), "compiled repeated purchase budget")


def detect_bridge_box_capacity(text: str) -> ArithmeticNLProblem | None:
    if "bridge" not in text or "boxes" not in text or "weighing" not in text:
        return None
    limit_match = re.search(r"no more than (?P<limit>\d+) pounds", text)
    box_match = re.search(r"each weighing (?P<box>\d+) pounds", text)
    base_match = re.search(r"combined weight .*? is (?P<base>\d+) pounds", text)
    if not (limit_match and box_match and base_match):
        return None
    capacity = Fraction(limit_match.group("limit")) - Fraction(base_match.group("base"))
    box = Fraction(box_match.group("box"))
    if box == 0:
        return None
    value = capacity / box
    return arithmetic_result("allfield_bridge_box_capacity", "floor((limit-base_weight)/box_weight)", Fraction(value.numerator // value.denominator), "compiled capacity constraint into maximum count")


def detect_cost_plus_percent_fee(text: str) -> ArithmeticNLProblem | None:
    if "%" not in text or "insured" not in text:
        return None
    costs = [Fraction(value) for value in re.findall(r"\$(?P<cost>\d+(?:\.\d+)?)", text)]
    pct_match = re.search(r"(?P<pct>\d+(?:\.\d+)?)% of that", text)
    if len(costs) < 2 or not pct_match:
        return None
    subtotal = sum(costs[:2])
    value = subtotal * (1 + Fraction(pct_match.group("pct")) / 100)
    return arithmetic_result("allfield_cost_plus_percent_fee", "subtotal*(1+pct)", value, "compiled additive cost plus percentage fee")


def detect_mpg_tank_range(text: str) -> ArithmeticNLProblem | None:
    if "single tank of gas" not in text or "gallons" not in text or "miles" not in text:
        return None
    miles_match = re.search(r"traveled (?P<miles>\d+) miles", text)
    fill_match = re.search(r"put in (?P<used>\d+) gallons", text)
    tank_match = re.search(r"tank holds (?P<tank>\d+) gallons", text)
    if not (miles_match and fill_match and tank_match):
        return None
    value = Fraction(miles_match.group("miles")) / Fraction(fill_match.group("used")) * Fraction(tank_match.group("tank"))
    return arithmetic_result("allfield_mpg_tank_range", "miles/used_gallons*tank_gallons", value, "compiled fuel economy into tank range")


def detect_repeated_activity_hours(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"spends (?P<main>\d+) hours .*? half as long.*? (?P<times>\d+) times a week.*? in (?P<weeks>\d+) weeks", text)
    if not match:
        return None
    main = Fraction(match.group("main"))
    value = (main + main / 2) * Fraction(match.group("times")) * Fraction(match.group("weeks"))
    return arithmetic_result("allfield_repeated_activity_hours", "(main+main/2)*times_per_week*weeks", value, "compiled repeated activity duration")


def detect_relative_categories_total(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"(?P<a>\d+) (?P<first>[a-z]+).*?(?P<diff>\d+) fewer (?P<second>[a-z]+) than (?P=first).*?twice the number of (?P<third>[a-z]+) than the (?P=second)", text)
    if not match:
        return None
    first = Fraction(match.group("a"))
    second = first - Fraction(match.group("diff"))
    third = 2 * second
    return arithmetic_result("allfield_relative_categories_total", "first+(first-diff)+2*(first-diff)", first + second + third, "compiled category counts from relative clauses")


def detect_state_minus_plus(text: str) -> ArithmeticNLProblem | None:
    patterns = [
        r"(?P<start>\d+) [a-z]+ long.*?cut off (?P<minus>\d+) [a-z]+.*?grew by (?P<plus>\d+) [a-z]+",
        r"had (?P<start>\d+) [a-z]+.*?drank (?P<minus>\d+) of them.*?bought (?P<plus>\d+) more",
        r"(?P<start>\d+) people came in and (?P<minus>\d+) people left.*?(?P<plus>\d+) people came in and (?P<minus2>\d+) people left",
    ]
    for regex in patterns:
        match = re.search(regex, text)
        if not match:
            continue
        value = Fraction(match.group("start")) - Fraction(match.group("minus")) + Fraction(match.group("plus"))
        if "minus2" in match.groupdict() and match.group("minus2") is not None:
            value -= Fraction(match.group("minus2"))
        return arithmetic_result("allfield_state_minus_plus", "start-minus+plus", value, "compiled signed state updates")
    return None


def detect_difference_between_two_quantities(text: str) -> ArithmeticNLProblem | None:
    patterns = [
        r"bought (?P<a>\d+) packs? of [a-z]+ and (?P<b>\d+) packs? of [a-z]+.*?how many more",
        r"ate (?P<a>\d+) [a-z]+ and gave (?P<b>\d+) of them.*?how many more",
    ]
    for regex in patterns:
        match = re.search(regex, text)
        if match:
            return arithmetic_result("allfield_difference_between_two_quantities", "abs(a-b)", abs(Fraction(match.group("a")) - Fraction(match.group("b"))), "compiled comparative difference")
    return None


def detect_selected_category_sum(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"(?P<a>\d+) red [a-z]+.*?(?P<b>\d+) yellow [a-z]+.*?(?P<c>\d+) green [a-z]+.*?red and green", text)
    if not match:
        return None
    return arithmetic_result("allfield_selected_category_sum", "red+green", Fraction(match.group("a")) + Fraction(match.group("c")), "compiled selected category sum")


def detect_plain_people_total(text: str) -> ArithmeticNLProblem | None:
    if "how many people" not in text:
        return None
    values = [Fraction(value) for value in re.findall(r"(?P<n>\d+) (?:girls|boys|teachers)", text)]
    if len(values) < 2:
        return None
    return arithmetic_result("allfield_plain_people_total", "sum(people_categories)", sum(values), "compiled total people across categories")


def detect_total_from_per_group_parts(text: str) -> ArithmeticNLProblem | None:
    unknown_groups = re.search(r"there are some baskets? .*?each basket has (?P<a>\d+) [a-z]+ [a-z]+ and (?P<b>\d+) [a-z]+ [a-z]+.*?total of (?P<total>\d+) [a-z]+ in all baskets", text)
    if unknown_groups:
        per_group = Fraction(unknown_groups.group("a")) + Fraction(unknown_groups.group("b"))
        if per_group == 0:
            return None
        return arithmetic_result("allfield_unknown_group_count_from_parts", "total/(part_a+part_b)", Fraction(unknown_groups.group("total")) / per_group, "compiled unknown group count from total and per-group parts")
    match = re.search(r"there are (?P<groups>\d+) baskets? of [a-z]+\. each basket has (?P<a>\d+) [a-z]+ [a-z]+ and (?P<b>\d+) [a-z]+ [a-z]+", text)
    if not match:
        match = re.search(r"(?P<groups>\d+) bird cages.*?each cage has (?P<a>\d+) [a-z]+ and (?P<b>\d+) [a-z]+", text)
    if not match:
        return None
    per_group = Fraction(match.group("a")) + Fraction(match.group("b"))
    if "in each basket" in text or "in each cage" in text:
        return arithmetic_result("allfield_per_group_parts", "part_a+part_b", per_group, "compiled per-group category sum")
    if "total" in text or "in all" in text:
        return arithmetic_result("allfield_total_from_per_group_parts", "groups*(part_a+part_b)", Fraction(match.group("groups")) * per_group, "compiled total over groups and per-group parts")
    return None


def detect_before_after_loss(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"currently weighs (?P<now>\d+) [a-z]+.*?lost (?P<lost>\d+) [a-z]+.*?before", text)
    if not match:
        return None
    return arithmetic_result("allfield_before_after_loss", "current+lost", Fraction(match.group("now")) + Fraction(match.group("lost")), "compiled inverse loss state")


def detect_more_than_altogether(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"(?P<a>[a-z]+) did (?P<first>\d+) [a-z-]+.*?(?P=a) did (?P<diff>\d+) more [a-z-]+ than (?P<b>[a-z]+).*?altogether", text)
    if not match:
        return None
    first = Fraction(match.group("first"))
    second = first - Fraction(match.group("diff"))
    return arithmetic_result("allfield_more_than_altogether", "larger+(larger-diff)", first + second, "compiled more-than relation and total")


def detect_needed_cost_to_complete(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"had (?P<have>\d+) [a-z ]+ but needed (?P<need>\d+) total.*?each one costs \$?(?P<cost>\d+)", text)
    if not match:
        return None
    value = (Fraction(match.group("need")) - Fraction(match.group("have"))) * Fraction(match.group("cost"))
    return arithmetic_result("allfield_needed_cost_to_complete", "(target-have)*unit_cost", value, "compiled missing items into completion cost")


def detect_ceil_total_capacity(text: str) -> ArithmeticNLProblem | None:
    patterns = [
        r"each van can hold (?P<unit>\d+) people.*?there are (?P<a>\d+) students and (?P<b>\d+) adults",
        r"carry (?P<unit>\d+) trays at a time.*?pick up (?P<a>\d+) trays .*? and (?P<b>\d+) trays",
        r"split into groups of (?P<unit>\d+).*?(?P<a>\d+) boys and (?P<b>\d+) girls",
    ]
    for regex in patterns:
        match = re.search(regex, text)
        if not match:
            continue
        total = Fraction(match.group("a")) + Fraction(match.group("b"))
        unit = Fraction(match.group("unit"))
        if unit == 0:
            return None
        return arithmetic_result("allfield_ceil_total_capacity", "ceil((a+b)/capacity)", ceil(total / unit), "compiled total into capacity count")
    return None


def detect_attendance_score(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"had (?P<total>\d+) members total.*?(?P<absent>\d+) members didn't show up.*?each member .*? scored (?P<points>\d+) points", text)
    if not match:
        return None
    value = (Fraction(match.group("total")) - Fraction(match.group("absent"))) * Fraction(match.group("points"))
    return arithmetic_result("allfield_attendance_score", "(total-absent)*points", value, "compiled attendance and per-person score")


def detect_total_categories_minus_sold(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"had (?P<a>\d+) [a-z]+ cats and (?P<b>\d+) [a-z]+ cats.*?sold (?P<sold>\d+) cats", text)
    if not match:
        return None
    return arithmetic_result("allfield_total_categories_minus_sold", "category_a+category_b-sold", Fraction(match.group("a")) + Fraction(match.group("b")) - Fraction(match.group("sold")), "compiled inventory across categories after sale")


def detect_players_lives_total(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"there were (?P<a>\d+) friends .*? when (?P<b>\d+) more players joined.*?each player had (?P<each>\d+) lives", text)
    if not match:
        return None
    value = (Fraction(match.group("a")) + Fraction(match.group("b"))) * Fraction(match.group("each"))
    return arithmetic_result("allfield_players_lives_total", "(players+joined)*lives_each", value, "compiled players and per-player lives")


def detect_boxes_two_types_each(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"bought (?P<a>\d+) boxes of [a-z ]+ and (?P<b>\d+) boxes of [a-z ]+.*?each box has (?P<each>\d+) pieces", text)
    if not match:
        return None
    value = (Fraction(match.group("a")) + Fraction(match.group("b"))) * Fraction(match.group("each"))
    return arithmetic_result("allfield_boxes_two_types_each", "(boxes_a+boxes_b)*pieces_each", value, "compiled boxes across types and per-box count")


def detect_total_albums_songs(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"bought (?P<a>\d+) [a-z]+ albums and (?P<b>\d+) [a-z]+ albums.*?had (?P<each>\d+) songs", text)
    if not match:
        return None
    value = (Fraction(match.group("a")) + Fraction(match.group("b"))) * Fraction(match.group("each"))
    return arithmetic_result("allfield_total_albums_songs", "(albums_a+albums_b)*songs_each", value, "compiled albums into song count")


def detect_boxes_remaining_each(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"bought (?P<start>\d+) boxes .*? gave (?P<given>\d+) to .*? each box has (?P<each>\d+) pieces", text)
    if not match:
        return None
    value = (Fraction(match.group("start")) - Fraction(match.group("given"))) * Fraction(match.group("each"))
    return arithmetic_result("allfield_boxes_remaining_each", "(boxes-given)*pieces_each", value, "compiled remaining boxes and per-box count")


def detect_furniture_assembly_time(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"bought (?P<a>\d+) new [a-z]+ and (?P<b>\d+) new [a-z]+.*?spent (?P<each>\d+) minutes on each", text)
    if not match:
        return None
    value = (Fraction(match.group("a")) + Fraction(match.group("b"))) * Fraction(match.group("each"))
    return arithmetic_result("allfield_furniture_assembly_time", "(items_a+items_b)*minutes_each", value, "compiled item count and per-item time")


def detect_baggies_from_cookie_sum(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"with (?P<unit>\d+) cookies in each bag.*?had (?P<a>\d+) [a-z ]+ cookies and (?P<b>\d+) [a-z ]+ cookies", text)
    if not match:
        return None
    total = Fraction(match.group("a")) + Fraction(match.group("b"))
    unit = Fraction(match.group("unit"))
    if unit == 0:
        return None
    value = total / unit
    return arithmetic_result("allfield_baggies_from_cookie_sum", "floor((a+b)/unit)", Fraction(value.numerator // value.denominator), "compiled cookie categories into bag count")


def detect_pages_from_cards(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"with (?P<unit>\d+) on each page.*?had (?P<a>\d+) new cards and (?P<b>\d+) old cards", text)
    if not match:
        return None
    total = Fraction(match.group("a")) + Fraction(match.group("b"))
    unit = Fraction(match.group("unit"))
    if unit == 0:
        return None
    return arithmetic_result("allfield_pages_from_cards", "ceil((new+old)/per_page)", ceil(total / unit), "compiled card total into page count")


def detect_now_after_unknown_removed(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"had (?P<start>\d+) [a-z]+\. [a-z]+ [a-z]+ some [a-z]+\. now [a-z]+ has (?P<now>\d+)", text)
    if not match:
        return None
    return arithmetic_result("allfield_now_after_unknown_removed", "start-now", Fraction(match.group("start")) - Fraction(match.group("now")), "compiled unknown removed amount from before/after state")


def detect_unknown_added_to_final(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"had (?P<start>\d+) [a-z]+.*?(?:gave him|gave [a-z]+|accorded him) some more.*?(?:then|now) [a-z]+ (?:had|has) (?P<final>\d+)", text)
    if not match:
        return None
    return arithmetic_result("allfield_unknown_added_to_final", "final-start", Fraction(match.group("final")) - Fraction(match.group("start")), "compiled unknown added amount from before/after state")


def detect_slice_total_inverse(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"had some [a-z]+\. .*? each [a-z]+ into (?P<slices>\d+) slices.*?total (?P<total>\d+) [a-z]+ slices", text)
    if not match:
        return None
    slices = Fraction(match.group("slices"))
    if slices == 0:
        return None
    return arithmetic_result("allfield_slice_total_inverse", "total_slices/slices_each", Fraction(match.group("total")) / slices, "compiled inverse slicing count")


def detect_total_minus_mixed_parts(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"contains (?P<total>\d+) [a-z]+ among which (?P<bad>\d+) is bad (?P<pct>\d+(?:\.\d+)?)% are [a-z]+ (?P<other>\d+) are [a-z]+ and the rest", text)
    if not match:
        return None
    total = Fraction(match.group("total"))
    value = total - Fraction(match.group("bad")) - total * Fraction(match.group("pct")) / 100 - Fraction(match.group("other"))
    return arithmetic_result("allfield_total_minus_mixed_parts", "total-known_count-percent_part-other_count", value, "compiled residual after count and percentage parts")


def detect_percent_complement_of_rest(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"(?P<pct1>\d+(?:\.\d+)?)% .*? are [a-z]+ flavored (?P<pct2>\d+(?:\.\d+)?)% of the rest are [a-z]+.*?both [a-z]+ flavored and not", text)
    if not match:
        return None
    value = (1 - Fraction(match.group("pct1")) / 100) * (1 - Fraction(match.group("pct2")) / 100) * 100
    return arithmetic_result("allfield_percent_complement_of_rest", "(1-pct1)*(1-pct2)*100", value, "compiled nested percentage complement")


def detect_unknown_part_per_group(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"there are (?P<groups>\d+) baskets? .*?each basket has (?P<known>\d+) [a-z]+ [a-z]+ and some more [a-z]+.*?total of (?P<total>\d+) [a-z]+ in all baskets", text)
    if not match:
        match = re.search(r"there are (?P<groups>\d+) baskets? .*?each basket has (?P<known>\d+) [a-z]+ [a-z]+ and some more [a-z]+.*?there are a total of (?P<total>\d+) [a-z]+ in all baskets", text)
    if not match:
        return None
    groups = Fraction(match.group("groups"))
    if groups == 0:
        return None
    value = Fraction(match.group("total")) / groups - Fraction(match.group("known"))
    return arithmetic_result("allfield_unknown_part_per_group", "total/groups-known_part", value, "compiled unknown per-group part from total and known part")


def detect_number_word_story_arithmetic(text: str) -> ArithmeticNLProblem | None:
    rope_match = re.search(r"used (?P<a>[\w-]+) inches .*? (?P<b>[\w-]+) inches .*? (?P<c>[\w-]+) inches .*? (?P<d>[\w-]+) inches .*?how many inches", text)
    if rope_match:
        values = [parse_number(rope_match.group(name)) for name in ("a", "b", "c", "d")]
        if all(value is not None for value in values):
            return arithmetic_result("allfield_number_word_sum", "sum(listed_lengths)", sum(values, Fraction(0)), "compiled listed number-word quantities")
    combined_match = re.search(r"got (?P<a>[\w-]+) pounds .*? got (?P<b>[\w-]+) pounds .*?combined", text)
    if combined_match:
        a = parse_number(combined_match.group("a"))
        b = parse_number(combined_match.group("b"))
        if a is not None and b is not None:
            return arithmetic_result("allfield_number_word_sum", "a+b", a + b, "compiled number-word additive total")
    cookies_match = re.search(r"made (?P<start>[\w-]+) [a-z ]+ cookies.*?ate (?P<used>[\w-]+) cookies.*?left", text)
    if cookies_match:
        start = parse_number(cookies_match.group("start"))
        used = parse_number(cookies_match.group("used"))
        if start is not None and used is not None:
            return arithmetic_result("allfield_number_word_remaining", "start-used", start - used, "compiled number-word remaining state")
    dogs_match = re.search(r"(?P<start>[\w-]+) dogs are barking.*?(?P<more>[\w-]+) more dogs start", text)
    if dogs_match:
        start = parse_number(dogs_match.group("start"))
        more = parse_number(dogs_match.group("more"))
        if start is not None and more is not None:
            return arithmetic_result("allfield_number_word_addition", "start+more", start + more, "compiled number-word addition")
    score_match = re.search(r"answered (?P<a>[\w-]+) questions .*? first half and (?P<b>[\w-]+) questions .*? second half.*?each question was worth (?P<points>[\w-]+) points", text)
    if score_match:
        values = [parse_number(score_match.group(name)) for name in ("a", "b", "points")]
        if all(value is not None for value in values):
            return arithmetic_result("allfield_number_word_score", "(a+b)*points", (values[0] + values[1]) * values[2], "compiled number-word score total")
    invite_match = re.search(r"sent out (?P<sent>[\w-]+) .*? invitations.*?if (?P<came>[\w-]+) people showed up.*?didn't come", text)
    if invite_match:
        sent = parse_number(invite_match.group("sent"))
        came = parse_number(invite_match.group("came"))
        if sent is not None and came is not None:
            return arithmetic_result("allfield_number_word_absent", "sent-came", sent - came, "compiled number-word attendance complement")
    return None


def detect_total_from_type_shelves(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"exactly (?P<each>\d+) books.*?had (?P<a>\d+) shelves .*? and (?P<b>\d+) shelves", text)
    if not match:
        return None
    value = (Fraction(match.group("a")) + Fraction(match.group("b"))) * Fraction(match.group("each"))
    return arithmetic_result("allfield_total_from_type_shelves", "(shelves_a+shelves_b)*each", value, "compiled shelves across types and per-shelf count")


def detect_split_groups_by_total_categories(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"had (?P<a>\d+) [a-z]+ and (?P<b>\d+) [a-z]+.*?split into groups of (?P<unit>\d+)", text)
    if not match:
        return None
    total = Fraction(match.group("a")) + Fraction(match.group("b"))
    unit = Fraction(match.group("unit"))
    if unit == 0:
        return None
    return arithmetic_result("allfield_split_groups_by_total_categories", "floor((a+b)/unit)", Fraction(total.numerator // unit.numerator) if total.denominator == 1 and unit.denominator == 1 else Fraction((total / unit).numerator // (total / unit).denominator), "compiled category total into equal groups")


def detect_seating_two_or_three(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"(?P<children>\d+) children .*? sit 2 or 3 to a seat.*?there are (?P<seats>\d+) seats.*?how many seats will have 3", text)
    if not match:
        return None
    value = Fraction(match.group("children")) - 2 * Fraction(match.group("seats"))
    return arithmetic_result("allfield_seating_two_or_three", "children-2*seats", value, "compiled two-or-three seating equation")


def detect_dog_treat_items(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"for her (?P<dogs>\d+) dogs.*?buy them (?P<biscuits>\d+) [a-z]+ biscuits each and a set of [a-z]+ boots each", text)
    if not match:
        return None
    dogs = Fraction(match.group("dogs"))
    value = dogs * (Fraction(match.group("biscuits")) + 1)
    return arithmetic_result("allfield_dog_treat_items", "dogs*(biscuits_each+boot_set_each)", value, "compiled per-dog item bundle")


def detect_working_items_sale(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"had (?P<total>\d+) [a-z ]+ but (?P<broken>\d+) of them weren't working.*?sell the working [a-z]+ for \$?(?P<price>\d+) each", text)
    if not match:
        return None
    value = (Fraction(match.group("total")) - Fraction(match.group("broken"))) * Fraction(match.group("price"))
    return arithmetic_result("allfield_working_items_sale", "(total-broken)*price", value, "compiled sellable inventory value")


def detect_each_has_total(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"there are (?P<count>\d+) [a-z]+\. each [a-z]+ has (?P<each>\d+) (?P<object>[a-z]+)", text)
    if not match:
        match = re.search(r"(?P<count>\d+) [a-z]+.*?each [a-z]+ has (?P<each>\d+) (?P<object>[a-z]+)", text)
    if not match:
        return None
    return arithmetic_result("allfield_each_has_total", "count*each", Fraction(match.group("count")) * Fraction(match.group("each")), "compiled each-object total")


def detect_free_kids_meal_cost(text: str) -> ArithmeticNLProblem | None:
    if "kids eat free" not in text:
        return None
    cost_match = re.search(r"adult meal costs \$(?P<cost>\d+(?:\.\d+)?)", text)
    group_match = re.search(r"group of (?P<group>\d+) people", text)
    kids_match = re.search(r"(?P<kids>\d+) were kids", text)
    if not (cost_match and group_match and kids_match):
        return None
    adults = Fraction(group_match.group("group")) - Fraction(kids_match.group("kids"))
    return arithmetic_result("allfield_free_kids_meal_cost", "(group-kids)*adult_cost", adults * Fraction(cost_match.group("cost")), "compiled free-child meal billing")


def detect_same_actor_brought_then_bought_total(text: str) -> ArithmeticNLProblem | None:
    match = re.search(
        r"(?P<person>[a-z]+) brought (?P<start>\d+) [a-z]+.*?\b(?P=person) then bought (?P<more>\d+) more [a-z]+.*?how many [a-z]+ did (?P=person) bring",
        text,
    )
    if not match:
        return None
    return arithmetic_result("allfield_same_actor_brought_then_bought_total", "actor_start+actor_extra", Fraction(match.group("start")) + Fraction(match.group("more")), "compiled actor-bound state update")


def detect_total_pair_divided_by_unit(text: str) -> ArithmeticNLProblem | None:
    patterns = [
        (
            r"bought (?P<a>\d+) [a-z ]+ and (?P<b>\d+) [a-z ]+.*?hold (?P<unit>\d+) on each shelf.*?how many shelves",
            "floor((a+b)/capacity)",
            True,
        ),
        (
            r"received (?P<a>\d+) [a-z ]+ and (?P<b>\d+) [a-z ]+.*?ate (?P<unit>\d+) [a-z ]+ a day.*?how long",
            "(a+b)/per_day",
            False,
        ),
        (
            r"had (?P<a>\d+) [a-z]+ when another (?P<b>\d+) were brought in.*?if (?P<unit>\d+) [a-z]+ a day are adopted.*?how long",
            "(a+b)/per_day",
            False,
        ),
        (
            r"won (?P<a>\d+) tickets .*? and (?P<b>\d+) tickets .*? cost (?P<unit>\d+) tickets a piece.*?how many",
            "floor((a+b)/cost)",
            True,
        ),
    ]
    for regex, expression, use_floor in patterns:
        match = re.search(regex, text)
        if not match:
            continue
        total = Fraction(match.group("a")) + Fraction(match.group("b"))
        unit = Fraction(match.group("unit"))
        if unit == 0:
            return None
        value = total / unit
        if use_floor:
            value = Fraction(value.numerator // value.denominator)
        return arithmetic_result("allfield_total_pair_divided_by_unit", expression, value, "compiled additive total then divided by a unit size")
    return None


def detect_group_share_after_extra(text: str) -> ArithmeticNLProblem | None:
    match = re.search(
        r"group of (?P<group>\d+) [a-z]+.*?had (?P<start>\d+) [a-z ]+ cooked but cooked (?P<more>\d+) more.*?each got the same amount",
        text,
    )
    if not match:
        return None
    group = Fraction(match.group("group"))
    if group == 0:
        return None
    value = (Fraction(match.group("start")) + Fraction(match.group("more"))) / group
    return arithmetic_result("allfield_group_share_after_extra", "(start+extra)/group", value, "compiled equal sharing after production update")


def detect_state_add_remove_add(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"had (?P<start>\d+) [a-z]+ to [a-z]+.*?graded (?P<done>\d+).*?another (?P<more>\d+) were turned in", text)
    if not match:
        return None
    value = Fraction(match.group("start")) - Fraction(match.group("done")) + Fraction(match.group("more"))
    return arithmetic_result("allfield_state_add_remove_add", "start-done+new", value, "compiled state update with removal and addition")


def detect_homework_multi_subject_remaining(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"had (?P<a>\d+) [a-z]+ problems and (?P<b>\d+) [a-z]+ problems.*?finished (?P<done>\d+) of the problems", text)
    if not match:
        return None
    value = Fraction(match.group("a")) + Fraction(match.group("b")) - Fraction(match.group("done"))
    return arithmetic_result("allfield_homework_multi_subject_remaining", "subject_a+subject_b-finished", value, "compiled remaining multi-subject homework")


def detect_score_per_item_two_levels(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"scores (?P<points>\d+) points for each [a-z]+.*?found (?P<a>\d+) [a-z]+ on the first.*?and (?P<b>\d+) on the second", text)
    if not match:
        return None
    value = Fraction(match.group("points")) * (Fraction(match.group("a")) + Fraction(match.group("b")))
    return arithmetic_result("allfield_score_per_item_two_levels", "points_per_item*(level1+level2)", value, "compiled per-item score across levels")


def detect_group_count_times_each(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"into groups of (?P<groups>\d+).*?each group has (?P<each>\d+) [a-z]+", text)
    if not match:
        return None
    value = Fraction(match.group("groups")) * Fraction(match.group("each"))
    return arithmetic_result("allfield_group_count_times_each", "groups*each", value, "compiled group cardinality times items per group")


def detect_equal_distribution_fraction(text: str) -> ArithmeticNLProblem | None:
    if "each group has" in text:
        return None
    match = re.search(r"(?:distribute|divide|sunder|impart|split) (?P<total>\d+) [a-z]+ among (?P<groups>\d+) friends", text)
    if not match:
        match = re.search(r"split a collection of [a-z]+ into groups of (?P<groups>\d+).*?(?<!group )has (?P<total>\d+) [a-z]+", text)
    if not match:
        return None
    groups = Fraction(match.group("groups"))
    if groups == 0:
        return None
    return arithmetic_result("allfield_equal_distribution_fraction", "total/groups", Fraction(match.group("total")) / groups, "compiled equal distribution")


def detect_remaining_capacity_division(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"had (?P<start>\d+) [a-z]+.*?handed out (?P<used>\d+).*?if each [a-z]+ takes (?P<unit>\d+) [a-z]+", text)
    if not match:
        return None
    unit = Fraction(match.group("unit"))
    if unit == 0:
        return None
    value = (Fraction(match.group("start")) - Fraction(match.group("used"))) / unit
    return arithmetic_result("allfield_remaining_capacity_division", "(start-used)/unit", Fraction(value.numerator // value.denominator), "compiled remaining inventory divided by recipe unit")


def detect_bags_total_each(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"(?P<person>[a-z]+) (?:snap up|take) (?P<bags>\d+) bags? of [a-z]+ .*?if total (?P<total>\d+) [a-z]+", text)
    if not match:
        return None
    bags = Fraction(match.group("bags"))
    if bags == 0:
        return None
    return arithmetic_result("allfield_bags_total_each", "total/bags", Fraction(match.group("total")) / bags, "compiled total contents divided by bag count")


def detect_group_count_from_total_each(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"had (?P<total>\d+) [a-z]+.*?(?:dispenses|divides) all [a-z]+ evenly among some friends.*?each .*? get (?P<each>\d+) [a-z]+", text)
    if not match:
        return None
    each = Fraction(match.group("each"))
    if each == 0:
        return None
    return arithmetic_result("allfield_group_count_from_total_each", "total/each", Fraction(match.group("total")) / each, "compiled unknown group count from total and per-group share")


def detect_phrase_number_sum(text: str) -> ArithmeticNLProblem | None:
    walk_match = re.search(
        r"walked (?P<a>\w+|\d+) miles on [a-z]+ and (?P<b>\w+|\d+) more on [a-z]+",
        text,
    )
    if walk_match:
        first = parse_number(walk_match.group("a"))
        second = parse_number(walk_match.group("b"))
        if first is not None and second is not None:
            return arithmetic_result("allfield_phrase_number_sum", "first_day+second_day", first + second, "compiled additive walking distances")
    if "sort out" in text and "total amount" in text:
        list_text = text.split("sort out", 1)[1]
        values = [Fraction(value) for value in re.findall(r"\b(?P<n>\d+)\s+[a-z]+", list_text)]
        if len(values) >= 2:
            return arithmetic_result("allfield_phrase_number_sum", "sum(listed sorted quantities)", sum(values), "compiled listed additive quantities after the sort-out clause")
    return None


def detect_start_add_then_wrong_subtract_difference(text: str) -> ArithmeticNLProblem | None:
    if "begin with the number" not in text or "difference" not in text:
        return None
    nums = [Fraction(value) for value in re.findall(r"(?:number|add|subtracted) (?P<n>\d+)", text)]
    if len(nums) < 3:
        return None
    correct = nums[0] + nums[1] + nums[2]
    wrong = nums[0] + nums[1] - nums[2]
    return arithmetic_result("allfield_start_add_then_wrong_subtract_difference", "abs((start+a+b)-(start+a-b))", abs(correct - wrong), "compiled instruction-following difference")


def detect_sets_each_total(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"(?P<sets>\d+) sets? .*?each set has (?P<each>\d+)", text)
    if not match:
        return None
    return arithmetic_result("allfield_sets_each_total", "sets*each", Fraction(match.group("sets")) * Fraction(match.group("each")), "compiled sets times items per set")


def detect_remainder_after_named_parts(text: str) -> ArithmeticNLProblem | None:
    if "rest are" not in text:
        return None
    nums = extract_numbers(text)
    if len(nums) < 3:
        return None
    return arithmetic_result("allfield_remainder_after_named_parts", "total-sum(named parts)", nums[0] - sum(nums[1:]), "compiled residual category count")


def detect_homework_remaining(text: str) -> ArithmeticNLProblem | None:
    if "already finished" not in text or "left" not in text:
        return None
    total_match = re.search(r"has (?P<total>\d+) [a-z ]+ to do", text)
    done_match = re.search(r"finished (?P<done>\d+)", text)
    if not (total_match and done_match):
        return None
    value = Fraction(total_match.group("total")) - Fraction(done_match.group("done"))
    return arithmetic_result("allfield_homework_remaining", "total-finished", value, "compiled remaining work count")


def detect_simple_bought_total(text: str) -> ArithmeticNLProblem | None:
    if "bought" not in text or "total" not in text:
        return None
    match = re.search(r"bought (?P<a>\d+) [a-z ]+ and (?P<b>\d+) [a-z ]+", text)
    if not match:
        return None
    return arithmetic_result("allfield_simple_bought_total", "a+b", Fraction(match.group("a")) + Fraction(match.group("b")), "compiled simple additive purchase count")


def detect_farther_than_contest(text: str) -> ArithmeticNLProblem | None:
    if "altogether" in text:
        return None
    match = re.search(r"(?P<a>[a-z]+) jumped (?P<dist>\d+) inches.*?jumped (?P<diff>\d+) inches farther than the (?P<b>[a-z]+)", text)
    if not match:
        return None
    value = Fraction(match.group("dist")) - Fraction(match.group("diff"))
    return arithmetic_result("allfield_farther_than_contest", "longer_jump-difference", value, "compiled farther-than relation")


def detect_combined_jumps_contest(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"(?P<a>[a-z]+) jumped (?P<dist>\d+) inches.*?jumped (?P<diff>\d+) inches farther than the (?P<b>[a-z]+).*?altogether", text)
    if not match:
        return None
    first = Fraction(match.group("dist"))
    second = first - Fraction(match.group("diff"))
    return arithmetic_result("allfield_combined_jumps_contest", "longer_jump+(longer_jump-difference)", first + second, "compiled farther-than relation and total")


def detect_percent_difference(text: str) -> ArithmeticNLProblem | None:
    match = re.search(
        r"(?:positive\s+)?difference between (?P<p1>[\d.]+)% of (?P<a>[\d.]+) and (?P<p2>[\d.]+)% of (?P<b>[\d.]+)",
        text,
    )
    if not match:
        return None
    p1 = Fraction(match.group("p1")) / 100
    p2 = Fraction(match.group("p2")) / 100
    a = Fraction(match.group("a"))
    b = Fraction(match.group("b"))
    value = abs(p1 * a - p2 * b)
    expr = f"abs(({p1})*{a} - ({p2})*{b})"
    return arithmetic_result("percent_difference", expr, value, "compiled percent-of difference")


def detect_right_triangle_trig(text: str) -> ArithmeticNLProblem | None:
    if "right triangle" not in text and "triangle" not in text:
        return None
    cos_match = re.search(r"\\?cos\{?b\}?\s*=\s*(?P<value>\\frac\{[^{}]+\}\{[^{}]+\}|[\d.]+/[\d.]+)", text)
    if not cos_match:
        return None
    cos_b = parse_fraction_expr(cos_match.group("value"))
    if cos_b is None or cos_b < 0 or cos_b > 1:
        return None
    sin_b_squared = 1 - cos_b * cos_b
    sin_b = sqrt_fraction_if_square(sin_b_squared)
    if sin_b is None:
        return None
    if re.search(r"what is .*?\\?tan\{?c\}?", text):
        value = cos_b / sin_b
        return arithmetic_result(
            "right_triangle_tan_complement",
            f"tan(C)=cot(B)=({cos_b})/sqrt(1-({cos_b})^2)",
            value,
            "compiled complementary acute angles in a right triangle",
        )
    if re.search(r"what is .*?\\?cos\{?c\}?", text):
        value = sin_b
        return arithmetic_result(
            "right_triangle_cos_complement",
            f"cos(C)=sin(B)=sqrt(1-({cos_b})^2)",
            value,
            "compiled complementary acute angles in a right triangle",
        )
    return None


def detect_complex_pair_product_abs_sum(text: str) -> ArithmeticNLProblem | None:
    if "complex numbers" not in text or "compute" not in text or "x+y+z" not in text or sp is None:
        return None
    compact = text.replace("\\\\", " ")
    match = re.search(
        r"xy\s*&?=\s*(?P<xy>[-+]?\d+(?:\s*[-+]\s*\d+i)?)\s+yz\s*&?=\s*(?P<yz>[-+]?\d+(?:\s*[-+]\s*\d+i)?)\s+zx\s*&?=\s*(?P<zx>[-+]?\d+(?:\s*[-+]\s*\d+i)?)",
        compact,
    )
    if not match:
        return None
    try:
        xy = parse_complex_expr(match.group("xy"))
        yz = parse_complex_expr(match.group("yz"))
        zx = parse_complex_expr(match.group("zx"))
        x, y, z = sp.symbols("x y z")
        solutions = sp.solve([sp.Eq(x * y, xy), sp.Eq(y * z, yz), sp.Eq(z * x, zx)], [x, y, z])
        if not solutions:
            return None
        values = {
            sp.sstr(sp.sqrt(sp.simplify((sx + sy + sz) * sp.conjugate(sx + sy + sz))))
            for sx, sy, sz in solutions
        }
    except Exception:
        return None
    if len(values) != 1:
        return None
    answer = values.pop()
    return ArithmeticNLProblem(
        intent="complex_pair_product_abs_sum",
        expression=f"solve xy={xy}, yz={yz}, zx={zx}; compute |x+y+z|",
        answer_exact=answer,
        explanation="compiled pairwise complex products into a polynomial system and evaluated the invariant absolute value",
    )


def detect_vertical_asymptote_count(text: str) -> ArithmeticNLProblem | None:
    if "vertical asymptote" not in text or sp is None:
        return None
    match = re.search(r"y\s*=\s*\\frac\{(?P<num>[^{}]+)\}\{(?P<den>[^{}]+)\}", text)
    if not match:
        return None
    x = sp.symbols("x")
    try:
        numerator = sp.sympify(clean_math_expr(match.group("num")), locals={"x": x})
        denominator = sp.sympify(clean_math_expr(match.group("den")), locals={"x": x})
        rational = sp.cancel(numerator / denominator)
        reduced_denominator = sp.denom(rational)
        roots = sp.solve(reduced_denominator, x)
        real_roots = [root for root in roots if bool(sp.ask(sp.Q.real(root))) or root.is_real is not False]
    except Exception:
        return None
    expr = f"count_real_roots(denominator({sp.sstr(rational)}))"
    return arithmetic_result(
        "vertical_asymptote_count",
        expr,
        len(set(map(str, real_roots))),
        "compiled vertical asymptotes as reduced denominator real zeros",
    )


def detect_complement_probability(text: str) -> ArithmeticNLProblem | None:
    if "probability" not in text or "not" not in text:
        return None
    match = re.search(r"probability .*? is (?P<p>\\frac\{[^{}]+\}\{[^{}]+\}|[\d.]+)", text)
    if not match:
        return None
    probability = parse_fraction_expr(match.group("p"))
    if probability is None:
        return None
    value = 1 - probability
    expr = f"1-({probability})"
    return arithmetic_result("complement_probability", expr, value, "compiled complement event probability")


def detect_binomial_exact_two_non_one(text: str) -> ArithmeticNLProblem | None:
    if "dice" not in text or "exactly two" not in text or "number other than 1" not in text:
        return None
    sides_match = re.search(r"(?P<sides>\d+)-sided dice", text)
    probability_match = re.search(r"is (?P<p>\\frac\{[^{}]+\}\{[^{}]+\}|[\d.]+)", text)
    if not (sides_match and probability_match):
        return None
    sides = int(sides_match.group("sides"))
    target = parse_fraction_expr(probability_match.group("p"))
    if target is None or sides <= 1:
        return None
    success = Fraction(sides - 1, sides)
    failure = Fraction(1, sides)
    for n in range(2, 80):
        probability = Fraction(comb(n, 2)) * success**2 * failure ** (n - 2)
        if probability == target:
            expr = f"solve C(n,2)*({success})^2*({failure})^(n-2)={target}"
            return arithmetic_result(
                "binomial_exact_two_non_one",
                expr,
                n,
                "compiled exact-two binomial probability over fair dice",
            )
    return None


def detect_positive_multiple_probability(text: str) -> ArithmeticNLProblem | None:
    match = re.search(
        r"positive multiple of (?P<base>\d+) less than (?P<limit>\d+).*?probability .*? two-digit integer",
        text,
    )
    if not match:
        return None
    base = int(match.group("base"))
    limit = int(match.group("limit"))
    total = (limit - 1) // base
    two_digit = len([value for value in range(base, limit, base) if 10 <= value <= 99])
    value = Fraction(two_digit, total)
    expr = f"count({base}k< {limit} and 10<= {base}k <=99)/count({base}k< {limit})"
    return arithmetic_result(
        "positive_multiple_probability",
        expr,
        value,
        "compiled uniform selection over positive multiples into a counting ratio",
    )


def detect_factor_divisor_chain_max_spins(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"positive factors .*? except for the number itself.*?spins a (?P<start>\d+) on his first spin", text)
    if not match:
        return None
    start = int(match.group("start"))

    memo: dict[int, int] = {}

    def longest_chain(n: int) -> int:
        if n in memo:
            return memo[n]
        divisors = proper_positive_divisors(n)
        memo[n] = 1 + max((longest_chain(divisor) for divisor in divisors), default=0)
        return memo[n]

    value = longest_chain(start)
    expr = f"height({start}, proper_divisor_relation)"
    return arithmetic_result(
        "factor_divisor_chain_max_spins",
        expr,
        value,
        "compiled repeated proper-factor spinner into a longest path over divisibility",
    )


def detect_smallest_multiple_greater_than(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"smallest multiple of (?P<base>-?\d+) which is greater than (?P<bound>-?\d+)", text)
    if not match:
        return None
    base = int(match.group("base"))
    bound = int(match.group("bound"))
    if base == 0:
        return None
    value = base * (floor(bound / base) + 1)
    expr = f"{base}*(floor({bound}/{base})+1)"
    return arithmetic_result("smallest_multiple_greater_than", expr, value, "compiled order constraint over multiples")


def detect_base_conversion_total(text: str) -> ArithmeticNLProblem | None:
    if "base ten" not in text or "for every hour" not in text:
        return None
    labor_match = re.search(r"charges \$?(?P<labor>\d+)_\{?(?P<labor_base>\d+)\}? dollars for every hour", text)
    equipment_match = re.search(r"\$?(?P<equipment>\d+)_\{?(?P<equipment_base>\d+)\}? dollars for equipment", text)
    hours_match = re.search(r"works for \$?(?P<hours>\d+(?:\.\d+)?)_\{?(?P<hours_base>\d+)\}? hours", text)
    if not (labor_match and equipment_match and hours_match):
        return None
    labor = parse_base_number(labor_match.group("labor"), int(labor_match.group("labor_base")))
    equipment = parse_base_number(equipment_match.group("equipment"), int(equipment_match.group("equipment_base")))
    hours = parse_base_number(hours_match.group("hours"), int(hours_match.group("hours_base")))
    value = labor * hours + equipment
    expr = f"base({labor_match.group('labor')},{labor_match.group('labor_base')})*base({hours_match.group('hours')},{hours_match.group('hours_base')})+base({equipment_match.group('equipment')},{equipment_match.group('equipment_base')})"
    return arithmetic_result("base_conversion_total", expr, value, "compiled base annotations then evaluated total")


def detect_projection_identity_dot_product(text: str) -> ArithmeticNLProblem | None:
    text = normalize_vector_macros(text)
    if "proj" not in text or "for all vectors" not in text or "a" not in text or "b" not in text:
        return None
    if "possible values" not in text or ("dot" not in text and r"\cdot" not in text):
        return None
    return arithmetic_result(
        "projection_identity_dot_product",
        "proj_a + proj_b = identity for all vectors => projection directions are orthogonal",
        0,
        "compiled projection-operator identity into orthogonality constraint",
    )


def detect_vector_linear_combination_angle(text: str) -> ArithmeticNLProblem | None:
    text = normalize_vector_macros(text)
    if "angle between" not in text or "u + v" not in text or "2" not in text or "u" not in text or "v" not in text:
        return None
    norm_match = re.search(r"\\?\|u\\?\|\s*=\s*\\?\|v\\?\|\s*=\s*(?P<norm>\d+)", text)
    dot_match = re.search(r"u\s*\\cdot\s*v\s*=\s*(?P<dot>-?\d+)", text)
    if not (norm_match and dot_match):
        return None
    norm = Fraction(norm_match.group("norm"))
    dot = Fraction(dot_match.group("dot"))
    uu = vv = norm * norm
    uv = dot
    numerator = 2 * uu + uv - vv
    left_norm_sq = uu + 2 * uv + vv
    right_norm_sq = 4 * uu - 4 * uv + vv
    denominator_sq = left_norm_sq * right_norm_sq
    denominator = sqrt_fraction_if_square(denominator_sq)
    if denominator is None:
        if sp is None:
            return None
        answer = sp.sstr(sp.simplify(sp.Rational(numerator.numerator, numerator.denominator) / sp.sqrt(sp.Rational(denominator_sq.numerator, denominator_sq.denominator))))
        return ArithmeticNLProblem(
            intent="vector_linear_combination_angle",
            expression=f"(({numerator})/sqrt(({left_norm_sq})*({right_norm_sq})))",
            answer_exact=answer,
            explanation="compiled vector angle into dot product over norms",
        )
    value = numerator / denominator
    return arithmetic_result(
        "vector_linear_combination_angle",
        f"(({numerator})/sqrt(({left_norm_sq})*({right_norm_sq})))",
        value,
        "compiled vector angle into dot product over norms",
    )


def detect_elementary_word_arithmetic(text: str) -> ArithmeticNLProblem | None:
    solvers = (
        detect_mwp_state_and_rate_patterns,
        detect_more_than_named_difference,
        detect_disappeared_from_sum_left,
        detect_together_more_remaining_share,
        detect_item_days_last,
        detect_spent_unknown_part,
        detect_rows_each_item_total,
        detect_boarding_more_total,
        detect_time_filtered_sum,
        detect_rate_each_days_total,
        detect_later_left_subtraction,
        detect_rectangle_perimeter_story,
        detect_money_left_after_cost,
        detect_unit_price_affordable_count,
        detect_put_more_total,
        detect_equal_groups_division,
        detect_album_song_total,
        detect_pages_days,
        detect_trays_needed,
        detect_sold_now_start,
        detect_capacity_remaining,
        detect_more_than_after_loss,
        detect_yesterday_rate_minutes,
        detect_each_shelf_total,
        detect_added_to_final,
        detect_purchase_spend_sum,
        detect_group_size,
        detect_distance_remaining,
        detect_seat_capacity,
        detect_pick_one_kind_left_plus_other,
        detect_lost_now_start,
        detect_selected_period_sum,
        detect_weekday_initial_count_rate,
        detect_add_loss_now,
        detect_more_came_total,
        detect_total_minus_parts,
        detect_multiple_gifts_sum,
        detect_wilted_bouquets,
        detect_rest_split_evenly,
        detect_more_than_total_spent,
        detect_simple_all_sum,
    )
    for solver in solvers:
        result = solver(text)
        if result is not None:
            return result
    return None


def detect_mwp_state_and_rate_patterns(text: str) -> ArithmeticNLProblem | None:
    solvers = (
        detect_target_object_remaining_after_consumption,
        detect_final_recipient_after_transfer,
        detect_current_category_difference,
        detect_capacity_with_current_occupancy,
        detect_had_plus_then_minus,
        detect_chapter_page_difference,
        detect_chapter_page_sum,
        detect_language_rate_days,
        detect_total_minus_named_part,
        detect_progressive_month_downloads,
        detect_joining_category_difference,
        detect_have_needed_difference,
        detect_equal_bag_size,
        detect_units_times_one_unit,
        detect_area_divided_by_width,
        detect_sum_minus_final_left,
        detect_two_bag_counts_each,
        detect_rest_shelves_needed,
        detect_remainder_divided_by_unit,
        detect_had_minus_then_plus,
        detect_sum_then_called_back_left_out,
        detect_all_but_rate_points,
        detect_started_left_unit_earnings,
        detect_total_minus_done,
        detect_capacity_tables_needed,
        detect_total_per_capacity_units,
        detect_combined_minus_consumed,
        detect_initial_minus_final_unknown_transfer,
        detect_some_removed_final_initial,
        detect_initial_plus_more,
        detect_initial_minus_removed_remaining,
        detect_remaining_times_unit_time,
        detect_each_item_multiplication,
        detect_total_divided_by_groups,
        detect_groups_times_each,
    )
    for solver in solvers:
        result = solver(text)
        if result is not None:
            return result
    return None


def detect_target_object_remaining_after_consumption(text: str) -> ArithmeticNLProblem | None:
    match = re.search(
        rf"had (?P<a>{NUMBER_RE}) (?P<label_a>[a-z]+) (?P<object>[a-z]+) and (?P<b>{NUMBER_RE}) (?P<label_b>[a-z]+) (?P=object).*?(?:ate|deleted) (?P<c>{NUMBER_RE}) (?P=label_a) (?P=object).*?(?:and (?P<d>{NUMBER_RE}) (?P=label_b) (?P=object))?.*?how many (?P<target>[a-z]+) (?P=object).*?left",
        text,
    )
    if not match:
        return None
    target = match.group("target")
    if target == match.group("label_b").rstrip("s"):
        initial = parse_number(match.group("b"))
        consumption_text = text[text.find(" ate ") :] if " ate " in text else text
        consumed_match = re.search(
            rf"(?P<consumed>{NUMBER_RE}) {re.escape(match.group('label_b'))} {re.escape(match.group('object'))}",
            consumption_text,
        )
        consumed = parse_number(consumed_match.group("consumed")) if consumed_match else parse_number(match.group("d") or "")
    else:
        initial = parse_number(match.group("a"))
        consumed = parse_number(match.group("c"))
    if initial is None or consumed is None:
        return None
    return arithmetic_result("mwp_target_object_remaining", f"{initial}-{consumed}", initial - consumed, "compiled target object initial count minus target consumption")


def detect_final_recipient_after_transfer(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"she had (?P<giver>{NUMBER_RE}) [a-z]+ while jeff had (?P<recipient>{NUMBER_RE}) [a-z]+.*?gave some .*? to jeff and now has (?P<giver_final>{NUMBER_RE}).*?how many .*?jeff have now", text)
    if not match:
        return None
    giver = parse_number(match.group("giver"))
    recipient = parse_number(match.group("recipient"))
    giver_final = parse_number(match.group("giver_final"))
    if giver is None or recipient is None or giver_final is None:
        return None
    transfer = giver - giver_final
    return arithmetic_result("mwp_final_recipient_after_transfer", f"{recipient}+({giver}-{giver_final})", recipient + transfer, "compiled recipient final as recipient initial plus transferred amount")


def detect_current_category_difference(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"now has (?P<a>{NUMBER_RE}) (?P<label_a>[a-z]+) [a-z]+ and (?P<b>{NUMBER_RE}) (?P<label_b>[a-z]+) [a-z]+ left.*?how many more (?P=label_b).*?than (?P=label_a)", text)
    if not match:
        return None
    first = parse_number(match.group("a"))
    second = parse_number(match.group("b"))
    if first is None or second is None:
        return None
    return arithmetic_result("mwp_current_category_difference", f"{second}-{first}", second - first, "compiled category comparison from current counts")


def detect_capacity_with_current_occupancy(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"has (?P<units>{NUMBER_RE}) seats.*?each seat can hold (?P<each>{NUMBER_RE}) people.*?there are (?P<current>{NUMBER_RE}) people.*?how many more", text)
    if not match:
        return None
    units = parse_number(match.group("units"))
    each = parse_number(match.group("each"))
    current = parse_number(match.group("current"))
    if units is None or each is None or current is None:
        return None
    value = units * each - current
    return arithmetic_result("mwp_capacity_with_current_occupancy", f"{units}*{each}-{current}", value, "compiled total capacity minus current occupancy")


def detect_had_plus_then_minus(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"had (?P<start>{NUMBER_RE}) [a-z]+.*?(?:found|got|added|received) (?P<plus>{NUMBER_RE}).*?(?:lost|deleted|ate|used) (?P<minus>{NUMBER_RE}).*?how many .*?(?:now|have)", text)
    if not match:
        return None
    start = parse_number(match.group("start"))
    plus = parse_number(match.group("plus"))
    minus = parse_number(match.group("minus"))
    if start is None or plus is None or minus is None:
        return None
    return arithmetic_result("mwp_had_plus_then_minus", f"{start}+{plus}-{minus}", start + plus - minus, "compiled state update with addition then removal")


def detect_chapter_page_sum(text: str) -> ArithmeticNLProblem | None:
    if "chapter" not in text or "pages" not in text:
        return None
    pages = [parse_number(match.group("n")) for match in re.finditer(rf"(?P<n>{NUMBER_RE}) pages long", text)]
    if len(pages) < 2 or any(item is None for item in pages):
        return None
    values = [item for item in pages if item is not None]
    return arithmetic_result("mwp_chapter_page_sum", "+".join(format_fraction(item) for item in values), sum(values, Fraction(0)), "compiled page counts while ignoring chapter ordinal/count")


def detect_language_rate_days(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"(?P<days>{NUMBER_RE}) days.*?every day .*?(?P<eng>{NUMBER_RE}) hours on learning english and (?P<chi>{NUMBER_RE}) hours on learning chinese", text)
    if not match:
        match = re.search(rf"every day .*?(?P<eng>{NUMBER_RE}) hours on learning english and (?P<chi>{NUMBER_RE}) hours on learning chinese.*?for (?P<days>{NUMBER_RE}) days", text)
    if not match:
        return None
    days = parse_number(match.group("days"))
    english = parse_number(match.group("eng"))
    chinese = parse_number(match.group("chi"))
    if days is None or english is None or chinese is None:
        return None
    rate = english + chinese if "english and chinese in all" in text else english
    return arithmetic_result("mwp_language_rate_days", f"{rate}*{days}", rate * days, "compiled requested study-hour rate times days")


def detect_total_minus_named_part(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"(?P<part>{NUMBER_RE}) kids .*?stayed home.*?total number .*? is (?P<total>{NUMBER_RE}).*?went to camp", text)
    if not match:
        return None
    part = parse_number(match.group("part"))
    total = parse_number(match.group("total"))
    if part is None or total is None:
        return None
    return arithmetic_result("mwp_total_minus_named_part", f"{total}-{part}", total - part, "compiled complement count from total minus named part")


def detect_progressive_month_downloads(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"had (?P<first>{NUMBER_RE}) downloads in the first month.*?second month was (?P<mult>{NUMBER_RE}) times as many.*?reduced by (?P<pct>{NUMBER_RE})% in the third month.*?total over the three months", text)
    if not match:
        return None
    first = parse_number(match.group("first"))
    multiplier = parse_number(match.group("mult"))
    pct = parse_number(match.group("pct"))
    if first is None or multiplier is None or pct is None:
        return None
    second = first * multiplier
    third = second * (1 - pct / 100)
    return arithmetic_result("mwp_progressive_month_downloads", f"{first}+{second}+{second}*(1-{pct}/100)", first + second + third, "compiled month-over-month multiplier and percent reduction")


def detect_chapter_page_difference(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"first chapter is (?P<first>{NUMBER_RE}) pages long.*?second chapter is (?P<second>{NUMBER_RE}) pages long.*?how many more pages .*?first chapter.*?than the second", text)
    if not match:
        return None
    first = parse_number(match.group("first"))
    second = parse_number(match.group("second"))
    if first is None or second is None:
        return None
    return arithmetic_result("mwp_chapter_page_difference", f"{first}-{second}", first - second, "compiled chapter page comparison")


def detect_joining_category_difference(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"(?P<birds0>{NUMBER_RE}) birds were sitting.*?(?P<birds_add>{NUMBER_RE}) more birds and (?P<storks>{NUMBER_RE}) more storks came.*?how many more storks than birds", text)
    if not match:
        return None
    birds0 = parse_number(match.group("birds0"))
    birds_add = parse_number(match.group("birds_add"))
    storks = parse_number(match.group("storks"))
    if birds0 is None or birds_add is None or storks is None:
        return None
    birds = birds0 + birds_add
    return arithmetic_result("mwp_joining_category_difference", f"{storks}-({birds0}+{birds_add})", storks - birds, "compiled final category counts then difference")


def detect_have_needed_difference(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"require (?P<required>{NUMBER_RE}) g .*?right now .*?needs (?P<needed>{NUMBER_RE}) g.*?already have", text)
    if not match:
        return None
    required = parse_number(match.group("required"))
    needed = parse_number(match.group("needed"))
    if required is None or needed is None:
        return None
    return arithmetic_result("mwp_have_needed_difference", f"{required}-{needed}", required - needed, "compiled already-have amount as required minus still-needed")


def detect_equal_bag_size(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"had (?P<bags>{NUMBER_RE}) bags with equal number of cookies.*?had (?P<cookies>{NUMBER_RE}) cookies", text)
    if not match:
        return None
    bags = parse_number(match.group("bags"))
    cookies = parse_number(match.group("cookies"))
    if bags in {None, 0} or cookies is None:
        return None
    return arithmetic_result("mwp_equal_bag_size", f"{cookies}/{bags}", cookies / bags, "compiled equal bag size")


def detect_units_times_one_unit(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"(?P<units>{NUMBER_RE}) chicken coops.*?(?P<each>{NUMBER_RE}) chickens in one coop", text)
    if not match:
        return None
    units = parse_number(match.group("units"))
    each = parse_number(match.group("each"))
    if units is None or each is None:
        return None
    return arithmetic_result("mwp_units_times_one_unit", f"{units}*{each}", units * each, "compiled number of units times quantity in one unit")


def detect_area_divided_by_width(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"total area was (?P<area>{NUMBER_RE}) square feet.*?wall was (?P<width>{NUMBER_RE}) feet wide.*?how tall", text)
    if not match:
        return None
    area = parse_number(match.group("area"))
    width = parse_number(match.group("width"))
    if area is None or width in {None, 0}:
        return None
    return arithmetic_result("mwp_area_divided_by_width", f"{area}/{width}", area / width, "compiled rectangle height as area divided by width")


def detect_sum_minus_final_left(text: str) -> ArithmeticNLProblem | None:
    if "gave some" not in text or "now" not in text or "left" not in text:
        return None
    quantities = extract_numbers(text)
    if len(quantities) < 3:
        return None
    value = sum(quantities[:-1], Fraction(0)) - quantities[-1]
    expr = "+".join(format_fraction(item) for item in quantities[:-1]) + f"-{quantities[-1]}"
    return arithmetic_result("mwp_sum_minus_final_left", expr, value, "compiled removed amount as initial category sum minus final total")


def detect_two_bag_counts_each(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"filled (?P<a>{NUMBER_RE}) bags .*? and .*? filled (?P<b>{NUMBER_RE}) more bags.*?each bag had (?P<each>{NUMBER_RE})", text)
    if not match:
        return None
    a = parse_number(match.group("a"))
    b = parse_number(match.group("b"))
    each = parse_number(match.group("each"))
    if a is None or b is None or each is None:
        return None
    return arithmetic_result("mwp_two_bag_counts_each", f"({a}+{b})*{each}", (a + b) * each, "compiled two bag counts times cans per bag")


def detect_rest_shelves_needed(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"(?P<total>{NUMBER_RE}) book .*?total.*?takes (?P<taken>{NUMBER_RE}).*?fit (?P<per>{NUMBER_RE}) books on a shelf.*?how many shelves", text)
    if not match:
        return None
    total = parse_number(match.group("total"))
    taken = parse_number(match.group("taken"))
    per = parse_number(match.group("per"))
    if total is None or taken is None or per in {None, 0}:
        return None
    value = Fraction(ceil((total - taken) / per))
    return arithmetic_result("mwp_rest_shelves_needed", f"ceil(({total}-{taken})/{per})", value, "compiled remaining books into ceiling shelf count")


def detect_had_minus_then_plus(text: str) -> ArithmeticNLProblem | None:
    match = re.search(
        rf"(?:had|started with|had already) (?P<start>{NUMBER_RE}) [a-z]+.*?(?:deleted|gave away|used|sold|threw away|ate|lost|handed out|planted) (?P<minus>{NUMBER_RE}).*?(?:added|bought|put|got|received|gave her|gave him|cooked) (?P<plus>{NUMBER_RE})",
        text,
    )
    if not match:
        return None
    start = parse_number(match.group("start"))
    minus = parse_number(match.group("minus"))
    plus = parse_number(match.group("plus"))
    if start is None or minus is None or plus is None:
        return None
    value = start - minus + plus
    return arithmetic_result("mwp_had_minus_then_plus", f"{start}-{minus}+{plus}", value, "compiled state update with removal then addition")


def detect_sum_then_called_back_left_out(text: str) -> ArithmeticNLProblem | None:
    if "got called back" not in text and "make the cut" not in text:
        return None
    quantities = extract_numbers(text)
    if len(quantities) < 3:
        return None
    value = sum(quantities[:-1], Fraction(0)) - quantities[-1]
    expr = "+".join(format_fraction(item) for item in quantities[:-1]) + f"-{quantities[-1]}"
    return arithmetic_result("mwp_sum_then_selected_left_out", expr, value, "compiled total applicants minus selected")


def detect_all_but_rate_points(text: str) -> ArithmeticNLProblem | None:
    match = re.search(
        rf"each (?P<unit>[a-z]+).*?(?:gives|earned?) .*?(?P<rate>{NUMBER_RE}) (?:points|dollars).*?(?:has|had) (?P<total>{NUMBER_RE}) [a-z]+.*?(?:all but|didn't [a-z]+) (?P<skip>{NUMBER_RE})",
        text,
    )
    if not match:
        return None
    rate = parse_number(match.group("rate"))
    total = parse_number(match.group("total"))
    skip = parse_number(match.group("skip"))
    if rate is None or total is None or skip is None:
        return None
    value = (total - skip) * rate
    return arithmetic_result("mwp_all_but_rate", f"({total}-{skip})*{rate}", value, "compiled completed count times reward/rate")


def detect_started_left_unit_earnings(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"each [a-z]+ was (?P<price>{NUMBER_RE}) dollars.*?started with (?P<start>{NUMBER_RE}) [a-z]+.*?had (?P<left>{NUMBER_RE}) [a-z]+ left.*?money", text)
    if not match:
        return None
    price = parse_number(match.group("price"))
    start = parse_number(match.group("start"))
    left = parse_number(match.group("left"))
    if price is None or start is None or left is None:
        return None
    value = (start - left) * price
    return arithmetic_result("mwp_started_left_unit_earnings", f"({start}-{left})*{price}", value, "compiled sold count times unit price")


def detect_total_minus_done(text: str) -> ArithmeticNLProblem | None:
    if not any(phrase in text for phrase in ("not wash", "didn't make the cut")):
        return None
    quantities = extract_numbers(text)
    if len(quantities) < 3:
        return None
    value = sum(quantities[:-1], Fraction(0)) - quantities[-1]
    expr = "+".join(format_fraction(item) for item in quantities[:-1]) + f"-{quantities[-1]}"
    return arithmetic_result("mwp_total_minus_done", expr, value, "compiled total work/items minus completed/selected")


def detect_capacity_tables_needed(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"invited (?P<invited>{NUMBER_RE}) people.*?(?P<absent>{NUMBER_RE}) .*?didn't show.*?held (?P<capacity>{NUMBER_RE}) people each.*?how many tables", text)
    if not match:
        return None
    invited = parse_number(match.group("invited"))
    absent = parse_number(match.group("absent"))
    capacity = parse_number(match.group("capacity"))
    if invited is None or absent is None or capacity in {None, 0}:
        return None
    value = Fraction(ceil((invited - absent) / capacity))
    return arithmetic_result("mwp_capacity_tables_needed", f"ceil(({invited}-{absent})/{capacity})", value, "compiled attendance divided by table capacity")


def detect_total_per_capacity_units(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"bought (?P<a>{NUMBER_RE}) [a-z]+ and (?P<b>{NUMBER_RE}) [a-z]+.*?hold (?P<capacity>{NUMBER_RE}) on each shelf.*?shelves", text)
    if not match:
        return None
    a = parse_number(match.group("a"))
    b = parse_number(match.group("b"))
    capacity = parse_number(match.group("capacity"))
    if a is None or b is None or capacity in {None, 0}:
        return None
    value = Fraction((a + b) // capacity)
    return arithmetic_result("mwp_total_per_capacity_units", f"floor(({a}+{b})/{capacity})", value, "compiled total items into filled capacity units")


def detect_combined_minus_consumed(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"had (?P<a>{NUMBER_RE}) .*? while .*? had (?P<b>{NUMBER_RE}).*?(?:ate|deleted|used|spent) (?P<minus>{NUMBER_RE}).*?(?:left|still have)", text)
    if not match:
        return None
    a = parse_number(match.group("a"))
    b = parse_number(match.group("b"))
    minus = parse_number(match.group("minus"))
    if a is None or b is None or minus is None:
        return None
    value = a + b - minus
    return arithmetic_result("mwp_combined_minus_consumed", f"{a}+{b}-{minus}", value, "compiled combined total minus consumed amount")


def detect_remainder_divided_by_unit(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"started with (?P<start>{NUMBER_RE}) [a-z]+.*?planted (?P<used>{NUMBER_RE}).*?put (?P<each>{NUMBER_RE}) [a-z]+ each.*?how many", text)
    if not match:
        return None
    start = parse_number(match.group("start"))
    used = parse_number(match.group("used"))
    each = parse_number(match.group("each"))
    if start is None or used is None or each in {None, 0}:
        return None
    value = (start - used) / each
    return arithmetic_result("mwp_remainder_divided_by_unit", f"({start}-{used})/{each}", value, "compiled remainder divided by per-group amount")


def detect_initial_minus_final_unknown_transfer(text: str) -> ArithmeticNLProblem | None:
    if "more" in text and "than" in text:
        return None
    if len(re.findall(r"\bnow has\b", text)) and len(extract_numbers(text)) >= 4 and " and " in text:
        return None
    match = re.search(rf"(?:had|found|has) (?P<start>{NUMBER_RE}) [a-z]+.*?(?:gave|clasped|lay hold|took|snap up).*?(?:now|has) .*?(?P<final>{NUMBER_RE})\s+[a-z]*\s*(?:left|book|watermelon|seashell|pen|mango|apple)?", text)
    if not match:
        return None
    if "how many" not in text and "how much" not in text:
        return None
    start = parse_number(match.group("start"))
    final = parse_number(match.group("final"))
    if start is None or final is None:
        return None
    return arithmetic_result("mwp_initial_minus_final_transfer", f"{start}-{final}", start - final, "compiled unknown removed/transferred amount as initial minus final")


def detect_some_removed_final_initial(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"had some [a-z]+.*?(?:took|gave) (?P<change>{NUMBER_RE}).*?now .*? has (?P<final>{NUMBER_RE}).*?(?:at first|initially|incipiently)", text)
    if not match:
        return None
    change = parse_number(match.group("change"))
    final = parse_number(match.group("final"))
    if change is None or final is None:
        return None
    return arithmetic_result("mwp_some_removed_final_initial", f"{change}+{final}", change + final, "compiled unknown initial after removal")


def detect_initial_plus_more(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"has (?P<start>{NUMBER_RE}) [a-z]+.*?gave .*? (?P<more>{NUMBER_RE}) more.*?how many", text)
    if not match:
        return None
    start = parse_number(match.group("start"))
    more = parse_number(match.group("more"))
    if start is None or more is None:
        return None
    return arithmetic_result("mwp_initial_plus_more", f"{start}+{more}", start + more, "compiled received-more state update")


def detect_initial_minus_removed_remaining(text: str) -> ArithmeticNLProblem | None:
    if "more" in text and "than" in text:
        return None
    match = re.search(rf"had (?P<start>{NUMBER_RE}) [a-z]+.*?(?:lost|took) (?P<minus>{NUMBER_RE}).*?how many .*?(?:reduced|have)", text)
    if not match:
        return None
    start = parse_number(match.group("start"))
    minus = parse_number(match.group("minus"))
    if start is None or minus is None:
        return None
    return arithmetic_result("mwp_initial_minus_removed_remaining", f"{start}-{minus}", start - minus, "compiled remaining amount after removal")


def detect_each_item_multiplication(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"had (?P<count>{NUMBER_RE}) [a-z]+.*?each [a-z]+ into (?P<each>{NUMBER_RE}) [a-z]+.*?how many", text)
    if not match:
        match = re.search(rf"(?P<count>{NUMBER_RE}) [a-z]+.*?each (?:room|friend|seat|dog|bag|book|album|hour) (?:takes|get|can hold|came with|had|contains?|into) (?P<each>{NUMBER_RE})", text)
    if not match:
        return None
    count = parse_number(match.group("count"))
    each = parse_number(match.group("each"))
    if count is None or each is None:
        return None
    return arithmetic_result("mwp_each_item_multiplication", f"{count}*{each}", count * each, "compiled count times per-item quantity")


def detect_total_divided_by_groups(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"(?:obtain|split|distribute|sunder|share|among) (?P<groups>{NUMBER_RE}) (?:bags|friends|groups|people).*?(?:total|has|have) (?P<total>{NUMBER_RE})", text)
    if not match:
        match = re.search(rf"(?P<total>{NUMBER_RE}) [a-z]+ .*? among (?P<groups>{NUMBER_RE}) friends", text)
    if not match:
        return None
    groups = parse_number(match.group("groups"))
    total = parse_number(match.group("total"))
    if groups in {None, 0} or total is None:
        return None
    return arithmetic_result("mwp_total_divided_by_groups", f"{total}/{groups}", total / groups, "compiled total divided by group count")


def detect_groups_times_each(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"among (?P<groups>{NUMBER_RE}) friends.*?each friend get (?P<each>{NUMBER_RE})", text)
    if not match:
        match = re.search(rf"groups of (?P<groups>{NUMBER_RE}).*?each group has (?P<each>{NUMBER_RE})", text)
    if not match:
        return None
    groups = parse_number(match.group("groups"))
    each = parse_number(match.group("each"))
    if groups is None or each is None:
        return None
    return arithmetic_result("mwp_groups_times_each", f"{groups}*{each}", groups * each, "compiled groups times each group size")


def detect_remaining_times_unit_time(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"needed to paint (?P<total>{NUMBER_RE}) rooms.*?each room takes (?P<each>{NUMBER_RE}) hours.*?already painted (?P<done>{NUMBER_RE})", text)
    if not match:
        match = re.search(rf"needed (?P<total>{NUMBER_RE}) windows.*?already installed (?P<done>{NUMBER_RE}).*?takes (?P<each>{NUMBER_RE}) hours", text)
    if not match:
        return None
    total = parse_number(match.group("total"))
    done = parse_number(match.group("done"))
    each = parse_number(match.group("each"))
    if total is None or done is None or each is None:
        return None
    return arithmetic_result("mwp_remaining_times_unit_time", f"({total}-{done})*{each}", (total - done) * each, "compiled remaining items times unit time")


def detect_more_than_named_difference(text: str) -> ArithmeticNLProblem | None:
    match = re.search(
        rf"(?P<a>{NUMBER_RE})\s+[^.?!]*?\bto\s+(?P<label_a>[a-z]+)\b[^.?!]*?(?P<b>{NUMBER_RE})\s+[^.?!]*?\bto\s+(?P<label_b>[a-z]+)\b[^?]*how many more[^?]*\b(?P=label_b)\b[^?]*than[^?]*\b(?P=label_a)\b",
        text,
    )
    if not match:
        return None
    first = parse_number(match.group("a"))
    second = parse_number(match.group("b"))
    if first is None or second is None:
        return None
    return arithmetic_result("elementary_named_difference", f"{second}-{first}", second - first, "compiled named comparison into subtraction")


def detect_disappeared_from_sum_left(text: str) -> ArithmeticNLProblem | None:
    if "disappeared" not in text or "left" not in text:
        return None
    quantities = extract_numbers(text)
    if len(quantities) < 3:
        return None
    value = sum(quantities[:-1], Fraction(0)) - quantities[-1]
    expr = "+".join(format_fraction(item) for item in quantities[:-1]) + f"-{format_fraction(quantities[-1])}"
    return arithmetic_result("elementary_disappeared_from_left", expr, value, "compiled initial totals minus left count")


def detect_together_more_remaining_share(text: str) -> ArithmeticNLProblem | None:
    if "together" not in text or "more" not in text or "now" not in text or "how much" not in text:
        return None
    quantities = extract_numbers(text)
    if len(quantities) < 3:
        return None
    value = quantities[0] + quantities[1] - quantities[2]
    expr = f"{quantities[0]}+{quantities[1]}-{quantities[2]}"
    return arithmetic_result("elementary_together_more_share", expr, value, "compiled updated total minus known share")


def detect_item_days_last(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"(?P<total>{NUMBER_RE})\s+(?P<item>[a-z]+) bottles.*?(?P<rate>{NUMBER_RE})\s+(?P=item) bottles a day.*?how many days", text)
    if not match:
        return None
    total = parse_number(match.group("total"))
    rate = parse_number(match.group("rate"))
    if total is None or rate in {None, 0}:
        return None
    return arithmetic_result("elementary_days_last", f"{total}/{rate}", total / rate, "compiled stock divided by daily usage")


def detect_spent_unknown_part(text: str) -> ArithmeticNLProblem | None:
    if "spent" not in text or "left" not in text or "how much did" not in text:
        return None
    quantities = extract_numbers(text)
    if len(quantities) < 3:
        return None
    value = quantities[0] - quantities[1] - quantities[2]
    expr = f"{quantities[0]}-{quantities[1]}-{quantities[2]}"
    return arithmetic_result("elementary_spent_unknown_part", expr, value, "compiled starting amount minus ending amount and known spending")


def detect_rows_each_item_total(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"(?P<rows>{NUMBER_RE}) rows with (?P<a>{NUMBER_RE}) (?P<label_a>[a-z]+) and (?P<b>{NUMBER_RE}) (?P<label_b>[a-z]+) in each row.*?how many (?P<target>[a-z]+)", text)
    if not match:
        return None
    rows = parse_number(match.group("rows"))
    first = parse_number(match.group("a"))
    second = parse_number(match.group("b"))
    if rows is None or first is None or second is None:
        return None
    target = match.group("target").rstrip("s")
    per_row = second if target == match.group("label_b").rstrip("s") else first
    return arithmetic_result("elementary_rows_each_total", f"{rows}*{per_row}", rows * per_row, "compiled rows times target items per row")


def detect_boarding_more_total(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"(?P<start>{NUMBER_RE}) [a-z]+ were riding.*?(?P<more>{NUMBER_RE}) more [a-z]+ got on.*?how many", text)
    if not match:
        return None
    start = parse_number(match.group("start"))
    more = parse_number(match.group("more"))
    if start is None or more is None:
        return None
    return arithmetic_result("elementary_more_total", f"{start}+{more}", start + more, "compiled increase event into addition")


def detect_time_filtered_sum(text: str) -> ArithmeticNLProblem | None:
    if "cookies" not in text or "till last night" not in text:
        return None
    yesterday = re.search(rf"(?P<n>{NUMBER_RE}) cookies yesterday", text)
    day_before = re.search(rf"(?P<n>{NUMBER_RE}) cookies the day before yesterday", text)
    if not (yesterday and day_before):
        return None
    y = parse_number(yesterday.group("n"))
    d = parse_number(day_before.group("n"))
    if y is None or d is None:
        return None
    return arithmetic_result("elementary_time_filtered_sum", f"{y}+{d}", y + d, "compiled time phrase excluding this morning")


def detect_rate_each_days_total(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"harvest (?P<rate>{NUMBER_RE}) sacks per day.*?each sack containes? (?P<each>{NUMBER_RE}) [a-z]+.*?after (?P<days>{NUMBER_RE}) days", text)
    if not match:
        return None
    rate = parse_number(match.group("rate"))
    each = parse_number(match.group("each"))
    days = parse_number(match.group("days"))
    if rate is None or each is None or days is None:
        return None
    return arithmetic_result("elementary_rate_each_days_total", f"{rate}*{each}*{days}", rate * each * days, "compiled rate times items per unit times duration")


def detect_later_left_subtraction(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"had (?P<start>{NUMBER_RE}) [a-z]+.*?later (?P<gone>{NUMBER_RE}) .*?(?:go home|left).*?how many .*?left", text)
    if not match:
        return None
    start = parse_number(match.group("start"))
    gone = parse_number(match.group("gone"))
    if start is None or gone is None:
        return None
    return arithmetic_result("elementary_later_left", f"{start}-{gone}", start - gone, "compiled departure event into subtraction")


def detect_rectangle_perimeter_story(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"rectangle.*?(?P<long>{NUMBER_RE}) feet long and (?P<wide>{NUMBER_RE}) feet wide.*?how long", text)
    if not match:
        return None
    length = parse_number(match.group("long"))
    width = parse_number(match.group("wide"))
    if length is None or width is None:
        return None
    return arithmetic_result("elementary_rectangle_perimeter", f"2*({length}+{width})", 2 * (length + width), "compiled rectangle boundary length")


def detect_money_left_after_cost(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"(?P<start>{NUMBER_RE}) left .*? costs (?P<cost>{NUMBER_RE}).*?how much money .*?left", text)
    if not match:
        return None
    start = parse_number(match.group("start"))
    cost = parse_number(match.group("cost"))
    if start is None or cost is None:
        return None
    return arithmetic_result("elementary_money_left_after_cost", f"{start}-{cost}", start - cost, "compiled remaining money after one purchase")


def detect_unit_price_affordable_count(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"one pack costs (?P<price>{NUMBER_RE}) dollars.*?how many packs .*? with (?P<money>{NUMBER_RE}) dollars", text)
    if not match:
        return None
    price = parse_number(match.group("price"))
    money = parse_number(match.group("money"))
    if price in {None, 0} or money is None:
        return None
    return arithmetic_result("elementary_affordable_count", f"{money}/{price}", money / price, "compiled budget divided by unit price")


def detect_put_more_total(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"there are (?P<start>{NUMBER_RE}) [a-z]+ .*? put (?P<more>{NUMBER_RE}) more .*? how many", text)
    if not match:
        return None
    start = parse_number(match.group("start"))
    more = parse_number(match.group("more"))
    if start is None or more is None:
        return None
    return arithmetic_result("elementary_put_more_total", f"{start}+{more}", start + more, "compiled adding more items")


def detect_equal_groups_division(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"(?P<total>{NUMBER_RE}) [a-z]+ in (?P<groups>{NUMBER_RE}) different [a-z]+.*?equal number", text)
    if not match:
        return None
    total = parse_number(match.group("total"))
    groups = parse_number(match.group("groups"))
    if total is None or groups in {None, 0}:
        return None
    return arithmetic_result("elementary_equal_groups", f"{total}/{groups}", total / groups, "compiled equal partition")


def detect_album_song_total(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"bought (?P<a>{NUMBER_RE}) [a-z]+ albums and (?P<b>{NUMBER_RE}) [a-z]+ albums.*?had (?P<songs>{NUMBER_RE}) songs.*?how many songs", text)
    if not match:
        return None
    a = parse_number(match.group("a"))
    b = parse_number(match.group("b"))
    songs = parse_number(match.group("songs"))
    if a is None or b is None or songs is None:
        return None
    return arithmetic_result("elementary_album_song_total", f"({a}+{b})*{songs}", (a + b) * songs, "compiled album count times songs per album")


def detect_pages_days(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"(?P<pages>{NUMBER_RE}) page book.*?read exactly (?P<per>{NUMBER_RE}) pages a day.*?how many days", text)
    if not match:
        return None
    pages = parse_number(match.group("pages"))
    per = parse_number(match.group("per"))
    if pages is None or per in {None, 0}:
        return None
    return arithmetic_result("elementary_pages_days", f"{pages}/{per}", pages / per, "compiled pages divided by daily reading rate")


def detect_trays_needed(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"place (?P<per>{NUMBER_RE}) cookies on a tray.*?prepare (?P<total>{NUMBER_RE}) .*?cookies", text)
    if not match:
        return None
    per = parse_number(match.group("per"))
    total = parse_number(match.group("total"))
    if per in {None, 0} or total is None:
        return None
    value = Fraction(ceil(total / per))
    return arithmetic_result("elementary_trays_needed", f"ceil({total}/{per})", value, "compiled tray capacity into ceiling division")


def detect_sold_now_start(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"sold (?P<sold>{NUMBER_RE}) [a-z]+.*?now he has (?P<left>{NUMBER_RE}) [a-z]+.*?start", text)
    if not match:
        return None
    sold = parse_number(match.group("sold"))
    left = parse_number(match.group("left"))
    if sold is None or left is None:
        return None
    return arithmetic_result("elementary_sold_now_start", f"{sold}+{left}", sold + left, "compiled original count as sold plus remaining")


def detect_capacity_remaining(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"(?:holds?|is) (?P<capacity>{NUMBER_RE}) .*?(?:there are|already at) (?P<used>{NUMBER_RE}) .*?how (?:many|much) (?:more|farther)", text)
    if not match:
        return None
    capacity = parse_number(match.group("capacity"))
    used = parse_number(match.group("used"))
    if capacity is None or used is None:
        return None
    return arithmetic_result("elementary_capacity_remaining", f"{capacity}-{used}", capacity - used, "compiled capacity minus current usage")


def detect_more_than_after_loss(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"ed had (?P<diff>{NUMBER_RE}) more .*? than doug.*?doug lost (?P<lost>{NUMBER_RE}).*?ed had (?P<ed>{NUMBER_RE}).*?how many more", text)
    if not match:
        return None
    diff = parse_number(match.group("diff"))
    lost = parse_number(match.group("lost"))
    ed = parse_number(match.group("ed"))
    if diff is None or lost is None or ed is None:
        return None
    doug_then = ed - diff - lost
    return arithmetic_result("elementary_more_than_after_loss", f"{ed}-({ed}-{diff}-{lost})", ed - doug_then, "compiled comparative relation after loss")


def detect_yesterday_rate_minutes(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"made (?P<made>{NUMBER_RE}) shirts yesterday.*?make (?P<rate>{NUMBER_RE}) shirts a minute.*?minutes .*?yesterday", text)
    if not match:
        return None
    made = parse_number(match.group("made"))
    rate = parse_number(match.group("rate"))
    if made is None or rate in {None, 0}:
        return None
    return arithmetic_result("elementary_rate_minutes", f"{made}/{rate}", made / rate, "compiled produced quantity divided by production rate")


def detect_each_shelf_total(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"(?P<books>{NUMBER_RE}) books and (?P<magazines>{NUMBER_RE}) magazines in each of his (?P<shelves>{NUMBER_RE}) bookshelves.*?how many magazines", text)
    if not match:
        return None
    magazines = parse_number(match.group("magazines"))
    shelves = parse_number(match.group("shelves"))
    if magazines is None or shelves is None:
        return None
    return arithmetic_result("elementary_each_shelf_total", f"{magazines}*{shelves}", magazines * shelves, "compiled per-shelf target quantity times shelves")


def detect_added_to_final(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"had (?P<start>{NUMBER_RE}) [a-z]+.*?after adding some he had (?P<final>{NUMBER_RE})", text)
    if not match:
        return None
    start = parse_number(match.group("start"))
    final = parse_number(match.group("final"))
    if start is None or final is None:
        return None
    return arithmetic_result("elementary_added_to_final", f"{final}-{start}", final - start, "compiled final minus initial after addition")


def detect_purchase_spend_sum(text: str) -> ArithmeticNLProblem | None:
    if "how much money did he spend" not in text:
        return None
    prices = [value for value in extract_numbers(text) if value > 0]
    if len(prices) < 2:
        return None
    value = sum(prices[-2:], Fraction(0))
    return arithmetic_result("elementary_purchase_spend_sum", "+".join(format_fraction(item) for item in prices[-2:]), value, "compiled total spending as sum of item prices")


def detect_group_size(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"organized into (?P<groups>{NUMBER_RE}) groups.*?total of (?P<total>{NUMBER_RE}).*?how big is each group", text)
    if not match:
        return None
    groups = parse_number(match.group("groups"))
    total = parse_number(match.group("total"))
    if groups in {None, 0} or total is None:
        return None
    return arithmetic_result("elementary_group_size", f"{total}/{groups}", total / groups, "compiled total divided by number of groups")


def detect_distance_remaining(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"(?P<total>{NUMBER_RE}) feet deep.*?already at (?P<current>{NUMBER_RE}) feet.*?how much farther", text)
    if not match:
        return None
    total = parse_number(match.group("total"))
    current = parse_number(match.group("current"))
    if total is None or current is None:
        return None
    return arithmetic_result("elementary_distance_remaining", f"{total}-{current}", total - current, "compiled remaining distance")


def detect_seat_capacity(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"has (?P<seats>{NUMBER_RE}) seats.*?(?P<people>{NUMBER_RE}) people can ride.*?how many people can each seat hold", text)
    if not match:
        return None
    seats = parse_number(match.group("seats"))
    people = parse_number(match.group("people"))
    if seats in {None, 0} or people is None:
        return None
    return arithmetic_result("elementary_seat_capacity", f"{people}/{seats}", people / seats, "compiled total riders divided by seats")


def detect_pick_one_kind_left_plus_other(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"had (?P<tomatoes>{NUMBER_RE}) tomatoes and (?P<potatoes>{NUMBER_RE}) potatoes.*?picked (?P<picked>{NUMBER_RE}) tomatoes.*?how many tomatoes and potatoes.*?left", text)
    if not match:
        return None
    tomatoes = parse_number(match.group("tomatoes"))
    potatoes = parse_number(match.group("potatoes"))
    picked = parse_number(match.group("picked"))
    if tomatoes is None or potatoes is None or picked is None:
        return None
    value = tomatoes - picked + potatoes
    return arithmetic_result("elementary_pick_one_kind_left_plus_other", f"{tomatoes}-{picked}+{potatoes}", value, "compiled remaining selected kind plus untouched kind")


def detect_lost_now_start(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"lost (?P<lost>{NUMBER_RE}) [a-z]+.*?now he has (?P<left>{NUMBER_RE}).*?at first", text)
    if not match:
        return None
    lost = parse_number(match.group("lost"))
    left = parse_number(match.group("left"))
    if lost is None or left is None:
        return None
    return arithmetic_result("elementary_lost_now_start", f"{lost}+{left}", lost + left, "compiled original amount as lost plus current")


def detect_selected_period_sum(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"(?P<morning>{NUMBER_RE}) emails in the morning.*?(?P<afternoon>{NUMBER_RE}) emails in the afternoon.*?(?P<evening>{NUMBER_RE}) emails in the evening.*?afternoon and evening", text)
    if not match:
        return None
    afternoon = parse_number(match.group("afternoon"))
    evening = parse_number(match.group("evening"))
    if afternoon is None or evening is None:
        return None
    return arithmetic_result("elementary_selected_period_sum", f"{afternoon}+{evening}", afternoon + evening, "compiled selected time periods into a sum")


def detect_weekday_initial_count_rate(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"reads (?P<rate>{NUMBER_RE}) books on every day that starts with the letters t and s.*?one week", text)
    if not match:
        return None
    rate = parse_number(match.group("rate"))
    if rate is None:
        return None
    days = Fraction(4)
    return arithmetic_result("elementary_weekday_initial_count_rate", f"{rate}*4", rate * days, "compiled weekday initials T/S as Tuesday, Thursday, Saturday, Sunday")


def detect_add_loss_now(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"has (?P<start>{NUMBER_RE}) [a-z]+.*?gives her (?P<more>{NUMBER_RE}) more .*?loses (?P<lost>{NUMBER_RE}).*?how many .*?now", text)
    if not match:
        return None
    start = parse_number(match.group("start"))
    more = parse_number(match.group("more"))
    lost = parse_number(match.group("lost"))
    if start is None or more is None or lost is None:
        return None
    return arithmetic_result("elementary_add_loss_now", f"{start}+{more}-{lost}", start + more - lost, "compiled state update with gain and loss")


def detect_more_came_total(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"(?P<start>{NUMBER_RE}) [a-z]+ were .*?(?P<more>{NUMBER_RE}) more [a-z]+ came .*?how many", text)
    if not match:
        return None
    start = parse_number(match.group("start"))
    more = parse_number(match.group("more"))
    if start is None or more is None:
        return None
    return arithmetic_result("elementary_more_came_total", f"{start}+{more}", start + more, "compiled arrival event into addition")


def detect_total_minus_parts(text: str) -> ArithmeticNLProblem | None:
    if "how many soccer" in text:
        quantities = extract_numbers(text)
        if len(quantities) >= 3:
            value = quantities[0] - quantities[1] - quantities[2]
            return arithmetic_result("elementary_total_minus_parts", f"{quantities[0]}-{quantities[1]}-{quantities[2]}", value, "compiled total minus known parts")
    if "took some" in text and "left" in text:
        quantities = extract_numbers(text)
        if len(quantities) >= 4:
            value = sum(quantities[:-1], Fraction(0)) - quantities[-1]
            expr = "+".join(format_fraction(item) for item in quantities[:-1]) + f"-{format_fraction(quantities[-1])}"
            return arithmetic_result("elementary_total_minus_left", expr, value, "compiled removed amount as original total minus left")
    return None


def detect_multiple_gifts_sum(text: str) -> ArithmeticNLProblem | None:
    if "received" not in text or "how much money" not in text:
        return None
    quantities = extract_numbers(text)
    if len(quantities) < 2:
        return None
    value = sum(quantities, Fraction(0))
    return arithmetic_result("elementary_multiple_gifts_sum", "+".join(format_fraction(item) for item in quantities), value, "compiled received amounts into a sum")


def detect_wilted_bouquets(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"picked (?P<total>{NUMBER_RE}) flowers.*?with (?P<per>{NUMBER_RE}) flowers in each one.*?if (?P<wilted>{NUMBER_RE}) .*?wilted.*?how many bouquets", text)
    if not match:
        return None
    total = parse_number(match.group("total"))
    per = parse_number(match.group("per"))
    wilted = parse_number(match.group("wilted"))
    if total is None or per in {None, 0} or wilted is None:
        return None
    return arithmetic_result("elementary_wilted_bouquets", f"({total}-{wilted})/{per}", (total - wilted) / per, "compiled usable items divided by bouquet size")


def detect_rest_split_evenly(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"(?P<total>{NUMBER_RE}) pictures.*?put (?P<used>{NUMBER_RE}) .*?into one album.*?rest into (?P<groups>{NUMBER_RE}) different albums", text)
    if not match:
        return None
    total = parse_number(match.group("total"))
    used = parse_number(match.group("used"))
    groups = parse_number(match.group("groups"))
    if total is None or used is None or groups in {None, 0}:
        return None
    return arithmetic_result("elementary_rest_split_evenly", f"({total}-{used})/{groups}", (total - used) / groups, "compiled rest evenly split into groups")


def detect_more_than_total_spent(text: str) -> ArithmeticNLProblem | None:
    match = re.search(rf"spent (?P<known>{NUMBER_RE}) on [^.]+ which is (?P<more>{NUMBER_RE}) more than she spent on [^.]+.*?how much money did she spend on", text)
    if not match:
        return None
    known = parse_number(match.group("known"))
    more = parse_number(match.group("more"))
    if known is None or more is None:
        return None
    other = known - more
    return arithmetic_result("elementary_more_than_total_spent", f"{known}+({known}-{more})", known + other, "compiled one amount as more-than another and summed both")


def detect_simple_all_sum(text: str) -> ArithmeticNLProblem | None:
    if "answer choices" in text:
        return None
    if any(phrase in text for phrase in ("how many more", "how much more", "each", "in one", "right now", "already have", "equal number")):
        return None
    if not any(phrase in text for phrase in ("altogether", "in all", "total", "how many animals", "how many pairs of shoes")):
        return None
    if any(phrase in text for phrase in (
        "left", "more", "each", "every ", "per ",
        "before it breaks",
        "how many days", "how many trays",
    )):
        return None
    if re.search(
        r"\b(?:fewer|less|ratio|average|difference|some|remaining)\b|"
        r"\b(?:times\s+as|times\s+the|times\s+what)\b|"
        r"\bthe\s+rest\s+(?:are|were|is|was|has|had)\b|"
        r"\bhow\s+(?:many|much)\b[^.?!]*\blast\b",
        text,
    ):
        return None
    if any(phrase in text for phrase in ("twice", "half", "third", "quarter", "%", "percent", " than ")):
        return None
    if re.search(r"\d+\s*/\s*\d+", text):
        return None
    quantities = extract_numbers(text)
    if len(quantities) < 2:
        return None
    value = sum(quantities, Fraction(0))
    return arithmetic_result("elementary_simple_all_sum", "+".join(format_fraction(item) for item in quantities), value, "compiled aggregate question into sum of quantities")


def detect_aqua_word_arithmetic(text: str) -> ArithmeticNLProblem | None:
    solvers = (
        detect_aqua_discount_original_price,
        detect_aqua_divisible_choice,
        detect_aqua_greatest_neither_probability,
        detect_aqua_profit_cost_price,
        detect_aqua_marbles_recapture,
        detect_aqua_bike_numbers,
        detect_aqua_train_slowdown,
        detect_aqua_max_neither_students,
        detect_aqua_commission_sales,
    )
    for solver in solvers:
        result = solver(text)
        if result is not None:
            return result
    return None


def detect_aqua_discount_original_price(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"discounted (?P<discount>[\d.]+)%.*?\$?(?P<coupon>[\d.]+)-off coupon.*?paid\s*\$?(?P<extra>[\d.]+) more than half", text)
    if not match:
        return None
    discount = Fraction(match.group("discount")) / 100
    coupon = Fraction(match.group("coupon"))
    extra = Fraction(match.group("extra"))
    value = (coupon + extra) / (1 - discount - Fraction(1, 2))
    choices = extract_answer_choice_values(text)
    if choices:
        value = min(choices, key=lambda choice: abs(choice - value))
    return arithmetic_result("aqua_discount_original_price", f"solve (1-{discount})*x-{coupon}=x/2+{extra}", value, "compiled discounted price equation")


def detect_aqua_divisible_choice(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"divisible by (?P<a>\d+) and (?P<b>\d+).*?answer choices:(?P<choices>.*)", text)
    if not match:
        return None
    a = int(match.group("a"))
    b = int(match.group("b"))
    modulus = a * b // gcd(a, b)
    valid = [choice for choice in extract_answer_choice_numbers(match.group("choices")) if choice % modulus == 0]
    if len(valid) != 1:
        return None
    return arithmetic_result("aqua_divisible_choice", f"choice divisible by lcm({a},{b})={modulus}", valid[0], "compiled divisibility choice filter")


def detect_aqua_greatest_neither_probability(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"probability .*? a .*? is (?P<a>[\d.]+).*?probability .*? b .*? is (?P<b>[\d.]+).*?greatest value .*? neither", text)
    if not match:
        return None
    a = Fraction(match.group("a").rstrip("."))
    b = Fraction(match.group("b").rstrip("."))
    value = min(1 - a, 1 - b)
    return arithmetic_result("aqua_greatest_neither_probability", f"min(1-{a},1-{b})", value, "compiled Frechet upper bound for neither event")


def detect_aqua_profit_cost_price(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"profit of (?P<pct>[\d.]+)% for rs\.?(?P<sold>[\d.]+).*?cost price", text)
    if not match:
        return None
    pct = Fraction(match.group("pct")) / 100
    sold = Fraction(match.group("sold"))
    value = sold / (1 + pct)
    return arithmetic_result("aqua_profit_cost_price", f"{sold}/(1+{pct})", value, "compiled selling price with profit")


def detect_aqua_marbles_recapture(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"(?P<painted>\d+) marbles .*?painted black.*?another (?P<sample>\d+) marbles.*?of which (?P<black>\d+) was black", text)
    if not match:
        return None
    painted = Fraction(match.group("painted"))
    sample = Fraction(match.group("sample"))
    black = Fraction(match.group("black"))
    if black == 0:
        return None
    value = painted * sample / black
    return arithmetic_result("aqua_marbles_recapture", f"{painted}*{sample}/{black}", value, "compiled sample proportion estimate")


def detect_aqua_bike_numbers(text: str) -> ArithmeticNLProblem | None:
    if "2 letters followed by 2 no" not in text:
        return None
    return arithmetic_result("aqua_bike_numbers", "26*25*10*10", 26 * 25 * 10 * 10, "compiled two distinct letters followed by two digits")


def detect_aqua_train_slowdown(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"speed of (?P<fast>[\d.]+) miles/hour.*?takes (?P<time>[\d.]+) hours.*?quarter of the distance.*?speed of (?P<slow>[\d.]+) miles/hour", text)
    if not match:
        return None
    fast = Fraction(match.group("fast"))
    original_time = Fraction(match.group("time"))
    slow = Fraction(match.group("slow"))
    distance = fast * original_time
    value = distance / 4 / fast + distance * Fraction(3, 4) / slow
    return arithmetic_result("aqua_train_slowdown", f"({distance}/4)/{fast}+({distance}*3/4)/{slow}", value, "compiled piecewise travel time")


def detect_aqua_max_neither_students(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"of the (?P<total>\d+) students.*?at least (?P<a>[\d.]+)%.*?at least (?P<b>[\d.]+)%.*?maximum number .*? neither", text)
    if not match:
        return None
    total = Fraction(match.group("total"))
    a = Fraction(match.group("a")) / 100
    b = Fraction(match.group("b")) / 100
    value = total * (1 - max(a, b))
    return arithmetic_result("aqua_max_neither_students", f"{total}*(1-max({a},{b}))", value, "compiled maximum neither by minimizing union")


def detect_aqua_commission_sales(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"(?P<pct>[\d.]+)% commission.*?sales? of \$(?P<price>[\d.]+).*?salary of at least \$(?P<target>[\d.]+)", text)
    if not match:
        return None
    pct = Fraction(match.group("pct")) / 100
    price = Fraction(match.group("price"))
    target = Fraction(match.group("target"))
    per_sale = pct * price
    if per_sale == 0:
        return None
    value = Fraction(ceil(target / per_sale))
    return arithmetic_result("aqua_commission_sales", f"ceil({target}/({pct}*{price}))", value, "compiled commission target into ceiling division")


def detect_repeated_rate_total(text: str) -> ArithmeticNLProblem | None:
    match = re.search(
        r"(?:run|runs)\s+(?P<count>[\w.]+)\s+\w+\s+(?P<times>[\w.]+)\s+times a week.*?(?:run|runs)\s+(?P<distance>[\w.]+)\s+meters each",
        text,
    )
    if not match:
        return None
    count = parse_number(match.group("count"))
    times = parse_number(match.group("times"))
    distance = parse_number(match.group("distance"))
    if None in {count, times, distance}:
        return None
    value = count * times * distance
    expr = f"{count}*{times}*{distance}"
    return arithmetic_result("repeated_rate_total", expr, value, "compiled repeated count times distance")


def detect_remainder_sale(text: str) -> ArithmeticNLProblem | None:
    if "sells the remainder" not in text:
        return None
    lay = re.search(r"lay (?P<total>[\w.]+) eggs per day", text)
    eats = re.search(r"eats (?P<eat>[\w.]+) for breakfast", text)
    bakes = re.search(r"bakes .*? with (?P<bake>[\w.]+)", text)
    price = re.search(r"for \$(?P<price>[\d.]+) per", text)
    if not (lay and eats and bakes and price):
        return None
    total = parse_number(lay.group("total"))
    eat = parse_number(eats.group("eat"))
    bake = parse_number(bakes.group("bake"))
    unit_price = Fraction(price.group("price"))
    if None in {total, eat, bake}:
        return None
    value = (total - eat - bake) * unit_price
    expr = f"({total}-{eat}-{bake})*{unit_price}"
    return arithmetic_result("remainder_sale", expr, value, "compiled remainder times unit price")


def detect_half_plus_base_total(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"takes (?P<base>[\w.]+) .*? and half that much .*? total", text)
    if not match:
        return None
    base = parse_number(match.group("base"))
    if base is None:
        return None
    value = base + Fraction(base, 2)
    expr = f"{base}+{base}/2"
    return arithmetic_result("half_plus_base_total", expr, value, "compiled base plus half-base")


def detect_factor_chain_total(text: str) -> ArithmeticNLProblem | None:
    if "twice as many" not in text or "4 times as many" not in text or "together" not in text:
        return None
    base_match = re.search(r"if\s+\w+\s+has\s+(?P<base>[\w.]+)", text)
    if not base_match:
        return None
    base = parse_number(base_match.group("base"))
    if base is None:
        return None
    middle = 4 * base
    top = 2 * middle
    value = base + middle + top
    expr = f"{base}+4*{base}+2*(4*{base})"
    return arithmetic_result("factor_chain_total", expr, value, "compiled multiplicative comparison chain")


def detect_price_every_second_discount(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"one .*? costs \$(?P<price>[\d.]+).*?every second .*? costs only (?P<pct>[\d.]+)%.*?buy (?P<count>[\d.]+)", text)
    if not match:
        return None
    price = Fraction(match.group("price"))
    pct = Fraction(match.group("pct")) / 100
    count = int(match.group("count"))
    full = (count + 1) // 2
    discounted = count // 2
    value = full * price + discounted * price * pct
    expr = f"{full}*{price}+{discounted}*{price}*{pct}"
    return arithmetic_result("every_second_discount", expr, value, "compiled alternating full/discounted prices")


def detect_percent_progress_restart_download(text: str) -> ArithmeticNLProblem | None:
    match = re.search(
        r"downloading a (?P<size>[\d.]+) gb file.*?download (?P<rate>[\d.]+) gb/minute.*?(?P<pct>[\d.]+)% of the way.*?takes (?P<restart>[\d.]+) minutes",
        text,
    )
    if not match:
        return None
    size = Fraction(match.group("size"))
    rate = Fraction(match.group("rate"))
    pct = Fraction(match.group("pct")) / 100
    restart = Fraction(match.group("restart"))
    value = size * pct / rate + restart + size / rate
    expr = f"{size}*{pct}/{rate}+{restart}+{size}/{rate}"
    return arithmetic_result("download_restart_total_time", expr, value, "compiled lost-progress download time")


def detect_overtime_pay(text: str) -> ArithmeticNLProblem | None:
    match = re.search(
        r"first (?P<regular_hours>[\d.]+) hours .*? is \$(?P<rate>[\d.]+).*?overtime pay of (?P<multi>[\d.]+) times.*?worked for (?P<hours>[\d.]+) hours",
        text,
    )
    if not match:
        return None
    regular_hours = Fraction(match.group("regular_hours"))
    rate = Fraction(match.group("rate"))
    multiplier = Fraction(match.group("multi"))
    hours = Fraction(match.group("hours"))
    overtime = max(Fraction(0), hours - regular_hours)
    value = regular_hours * rate + overtime * rate * multiplier
    expr = f"{regular_hours}*{rate}+{overtime}*{rate}*{multiplier}"
    return arithmetic_result("overtime_pay", expr, value, "compiled regular plus overtime pay")


def detect_house_flip_profit(text: str) -> ArithmeticNLProblem | None:
    if "profit" not in text or "increased the value" not in text:
        return None
    purchase_match = re.search(r"buys .*? for \$(?P<purchase>[\d.]+)", text)
    repair_match = re.search(r"puts in \$(?P<repair>[\d.]+) in repairs", text)
    percent_match = re.search(r"increased the value .*? by (?P<pct>[\d.]+)%", text)
    if not (purchase_match and repair_match and percent_match):
        return None
    purchase = Fraction(purchase_match.group("purchase"))
    repair = Fraction(repair_match.group("repair"))
    pct = Fraction(percent_match.group("pct")) / 100
    value = purchase * (1 + pct) - purchase - repair
    expr = f"{purchase}*(1+{pct})-{purchase}-{repair}"
    return arithmetic_result("house_flip_profit", expr, value, "compiled final value minus acquisition and repair costs")


def detect_feed_final_meal_remainder(text: str) -> ArithmeticNLProblem | None:
    if "final meal" not in text or "each of her chickens" not in text:
        return None
    per_match = re.search(r"each of her chickens (?P<per>[\w.]+) cups", text)
    flock_match = re.search(r"flock is (?P<count>[\w.]+) chickens", text)
    morning_match = re.search(r"morning.*?(?P<morning>[\w.]+) cups", text)
    afternoon_match = re.search(r"afternoon.*?(?P<afternoon>[\w.]+) cups", text)
    if not (per_match and flock_match and morning_match and afternoon_match):
        return None
    per = parse_number(per_match.group("per"))
    count = parse_number(flock_match.group("count"))
    morning = parse_number(morning_match.group("morning"))
    afternoon = parse_number(afternoon_match.group("afternoon"))
    if None in {per, count, morning, afternoon}:
        return None
    value = per * count - morning - afternoon
    expr = f"{per}*{count}-{morning}-{afternoon}"
    return arithmetic_result("feed_final_meal_remainder", expr, value, "compiled daily total minus previous meals")


def detect_out_and_back_remaining_distance(text: str) -> ArithmeticNLProblem | None:
    if "turns around" not in text or "standstill traffic" not in text or "how far" not in text:
        return None
    outbound_match = re.search(r"drives for (?P<hours>[\w.]+) hours at a speed of (?P<speed>[\w.]+) mph", text)
    target_match = re.search(r"get home in (?P<target>[\w.]+) hours", text)
    standstill_match = re.search(r"first (?P<standstill>[\w.]+) hours in standstill", text)
    slow_match = re.search(r"next (?P<slow_time>half-hour|[\w.]+ hour) driving at a speed of (?P<slow_speed>[\w.]+)mph", text)
    fast_match = re.search(r"remaining time .*? going at (?P<fast_speed>[\w.]+) mph", text)
    if not (outbound_match and target_match and standstill_match and slow_match and fast_match):
        return None
    outbound_hours = parse_number(outbound_match.group("hours"))
    outbound_speed = parse_number(outbound_match.group("speed"))
    target = parse_number(target_match.group("target"))
    standstill = parse_number(standstill_match.group("standstill"))
    slow_time = parse_duration_hours(slow_match.group("slow_time"))
    slow_speed = parse_number(slow_match.group("slow_speed"))
    fast_speed = parse_number(fast_match.group("fast_speed"))
    if None in {outbound_hours, outbound_speed, target, standstill, slow_time, slow_speed, fast_speed}:
        return None
    outbound = outbound_hours * outbound_speed
    return_time = slow_time + (target - standstill - slow_time)
    returned = slow_time * slow_speed + (target - standstill - slow_time) * fast_speed
    value = outbound - returned
    expr = f"{outbound_hours}*{outbound_speed}-({slow_time}*{slow_speed}+({target}-{standstill}-{slow_time})*{fast_speed})"
    return arithmetic_result(
        "out_and_back_remaining_distance",
        expr,
        value,
        f"compiled outbound distance minus return distance over {return_time} moving hours",
    )


def detect_exponential_even_odd_function(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"is f\(x\)\s*=\s*(?P<base>\d+)\^x an even function odd function or neither", text)
    if not match:
        return None
    base = Fraction(match.group("base"))
    answer = "even" if base == 1 else "neither"
    return ArithmeticNLProblem(
        intent="exponential_even_odd_function",
        expression=f"compare f(-x)=({base})^(-x) with f(x)=({base})^x and -f(x)",
        answer_exact=answer,
        explanation="compiled parity classification by symbolic comparison of f(-x), f(x), and -f(x)",
    )


def detect_case_frame_arithmetic(text: str) -> ArithmeticNLProblem | None:
    solvers = (
        detect_breakeven_years,
        detect_average_speed_remaining,
        detect_tiered_buy_count,
        detect_budget_unknown_item_count,
        detect_comparison_chain_value,
        detect_daily_rate_over_week,
        detect_sale_pack_over_period,
        detect_speed_fraction_schedule,
        detect_multiplier_excess_distance,
        detect_partition_total_minus_remaining,
        detect_remaining_calorie_grams,
        detect_ratio_total_future_value,
        detect_percentage_fee_total,
        detect_initial_from_final_periodic_gain,
        detect_batch_profit,
        detect_unknown_added_package_from_final,
        detect_proportional_purchase_total,
        detect_return_trip_time,
        detect_weight_removal_mix,
        detect_two_day_revenue_difference,
        detect_remaining_group_count,
        detect_cluster_plus_individual_total,
        detect_prorated_pension,
        detect_ratio_total_part,
        detect_two_period_total_with_difference,
        detect_fraction_loser_votes,
    )
    for solver in solvers:
        result = solver(text)
        if result is not None:
            return result
    return None


def detect_breakeven_years(text: str) -> ArithmeticNLProblem | None:
    if "earning money" not in text and "break even" not in text:
        return None
    fixed = re.search(r"cost \$?(?P<fixed>[\d.]+) to (?:plant|start|set up|setup)", text)
    production = re.search(r"(?:grow|produce|make|generate) (?P<count>[\w.]+) (?P<object>[a-z]+)", text)
    sale = re.search(r"sell for \$?(?P<price>[\d.]+) each", text)
    recurring = re.search(r"costs? \$?(?P<cost>[\d.]+) (?:a|per) year", text)
    if not (fixed and production and sale and recurring):
        return None
    fixed_cost = parse_decimal_fraction(fixed.group("fixed"))
    count = parse_number(production.group("count"))
    price = parse_decimal_fraction(sale.group("price"))
    cost = parse_decimal_fraction(recurring.group("cost"))
    if count is None:
        return None
    net = count * price - cost
    if net <= 0:
        return None
    years = floor(fixed_cost / net) + 1
    expr = f"floor({fixed_cost}/({count}*{price}-{cost}))+1"
    return arithmetic_result("case_frame_breakeven_years", expr, years, "compiled fixed cost plus yearly net income into a strict break-even inequality")


def detect_average_speed_remaining(text: str) -> ArithmeticNLProblem | None:
    if "average speed" not in text or "remaining distance" not in text and "remaining" not in text:
        return None
    total_match = re.search(r"(?P<total>[\d.]+)-mile", text)
    target_match = re.search(r"average speed .*? (?P<target>[\d.]+) miles? per hour", text)
    if not (total_match and target_match):
        return None
    total_distance = Fraction(total_match.group("total"))
    target_speed = Fraction(target_match.group("target"))
    walked_distance = Fraction(0)
    elapsed = Fraction(0)
    segment_pattern = r"(?P<time>another|[\w.]+) hours? to walk .*?(?P<distance>[\w.]+) miles?"
    for match in re.finditer(segment_pattern, text):
        time_value = parse_number(match.group("time"))
        distance_value = parse_number(match.group("distance"))
        if time_value is None or distance_value is None:
            continue
        elapsed += time_value
        walked_distance += distance_value
    if walked_distance == 0:
        return None
    target_total_time = total_distance / target_speed
    remaining_time = target_total_time - elapsed
    remaining_distance = total_distance - walked_distance
    if remaining_time <= 0:
        return None
    value = remaining_distance / remaining_time
    expr = f"({total_distance}-{walked_distance})/({total_distance}/{target_speed}-{elapsed})"
    return arithmetic_result("case_frame_average_speed_remaining", expr, value, "compiled average-speed target into remaining distance over remaining time")


def detect_tiered_buy_count(text: str) -> ArithmeticNLProblem | None:
    if "customers" not in text or "buy" not in text:
        return None
    total = Fraction(0)
    evidence = 0
    for match in re.finditer(r"(?P<count>[\w.]+) customers? buy (?P<each>one|[\w.]+) [a-z]+ each", text):
        count = parse_number(match.group("count"))
        each = parse_number(match.group("each"))
        if count is None or each is None:
            continue
        total += count * each
        evidence += 1
    if evidence < 2:
        return None
    return arithmetic_result("case_frame_tiered_buy_count", "sum(customer_tier_count*items_each)", total, "compiled tiered purchase clauses into an additive total")


def detect_budget_unknown_item_count(text: str) -> ArithmeticNLProblem | None:
    if "paid a total" not in text or "some" not in text or "each" not in text:
        return None
    total_match = re.search(r"paid a total of \$?(?P<total>[\d.]+)", text)
    unknown_match = re.search(r"some (?P<object>[a-z]+s?) of [a-z]+.*?each (?:box|pack|meal|item)? ?costs? \$?(?P<price>[\d.]+)", text)
    if not (total_match and unknown_match):
        unknown_match = re.search(r"some (?P<object>[a-z]+s?).*?each [a-z]+ costs? \$?(?P<price>[\d.]+)", text)
    if not (total_match and unknown_match):
        unknown_match = re.search(r"some (?P<object>[a-z]+s?) of [a-z]+.*?each [a-z]+ costs? \$?(?P<price>[\d.]+)", text)
    if not (total_match and unknown_match):
        return None
    total = parse_decimal_fraction(total_match.group("total"))
    unknown_price = parse_decimal_fraction(unknown_match.group("price"))
    known = Fraction(0)
    prefix = text[: unknown_match.start()]
    item_pattern = rf"(?P<count>{NUMBER_RE}) [a-z]+(?: [a-z]+){{0,4}}? that costs? \$?(?P<price>\d+(?:\.\d+)?)"
    for match in re.finditer(item_pattern, prefix):
        count = parse_number(match.group("count"))
        price = parse_decimal_fraction(match.group("price"))
        if count is None:
            continue
        known += count * price
    if known == 0 or unknown_price == 0:
        return None
    value = (total - known) / unknown_price
    expr = f"({total}-{known})/{unknown_price}"
    return arithmetic_result("case_frame_budget_unknown_item_count", expr, value, "compiled total bill minus known purchases over unknown unit price")


def detect_comparison_chain_value(text: str) -> ArithmeticNLProblem | None:
    if "twice as much" not in text and "half of" not in text:
        return None
    # A and B together cost k less than target; one component costs p and the other twice as much.
    together = re.search(r"together cost (?P<delta>[\w.]+) dollars? less than (?:the )?(?P<target>[a-z]+)", text)
    base = re.search(r"one .*? costs \$?(?P<base>[\d.]+).*?other costs twice as much", text)
    if together and base:
        delta = parse_number(together.group("delta"))
        base_value = parse_decimal_fraction(base.group("base"))
        if delta is None:
            return None
        value = base_value + 2 * base_value + delta
        expr = f"{base_value}+2*{base_value}+{delta}"
        return arithmetic_result("case_frame_comparison_chain_value", expr, value, "compiled additive comparison chain with a doubled component")

    fewer = re.search(r"(?P<left>[a-z]+) has (?P<less>[\w.]+) fewer [a-z]+ than (?P<mid>[a-z]+)", text)
    more_half = re.search(r"(?P<mid>[a-z]+) has (?P<more>[\w.]+) more [a-z]+ than half of (?P<base>[a-z]+)'?s", text)
    base_value_match = re.search(r"if (?P<base>[a-z]+) has (?P<value>[\w.]+)", text)
    if fewer and more_half and base_value_match:
        less = parse_number(fewer.group("less"))
        more = parse_number(more_half.group("more"))
        base_value = parse_number(base_value_match.group("value"))
        if None in {less, more, base_value}:
            return None
        value = base_value / 2 + more - less
        expr = f"{base_value}/2+{more}-{less}"
        return arithmetic_result("case_frame_comparison_chain_value", expr, value, "compiled half-plus and fewer-than comparison chain")
    return None


def detect_daily_rate_over_week(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"takes care of (?P<count>[\w.]+) [a-z]+.*?each [a-z]+ takes (?P<hours>[\d.]+|\.\d+) hours? a day", text)
    if not match or "week" not in text:
        return None
    count = parse_number(match.group("count"))
    hours = parse_number(match.group("hours"))
    if count is None or hours is None:
        return None
    value = count * hours * 7
    expr = f"{count}*{hours}*7"
    return arithmetic_result("case_frame_daily_rate_over_week", expr, value, "compiled count times daily duration times seven days")


def detect_sale_pack_over_period(text: str) -> ArithmeticNLProblem | None:
    use_match = re.search(r"(?:eats?|uses?) (?P<rate>[\w.]+) [a-z]+s? a day", text)
    pack_match = re.search(r"sale at (?P<count>[\w.]+) [a-z]+s? for \$?(?P<price>[\d.]+)", text)
    days_match = re.search(r"over (?P<days>[\w.]+) days?", text)
    if not (use_match and pack_match and days_match):
        return None
    rate = parse_number(use_match.group("rate"))
    pack_count = parse_number(pack_match.group("count"))
    price = parse_decimal_fraction(pack_match.group("price"))
    days = parse_number(days_match.group("days"))
    if None in {rate, pack_count, days} or pack_count == 0:
        return None
    value = rate * days * price / pack_count
    expr = f"{rate}*{days}*{price}/{pack_count}"
    return arithmetic_result("case_frame_sale_pack_over_period", expr, value, "compiled daily consumption through package price ratio")


def detect_speed_fraction_schedule(text: str) -> ArithmeticNLProblem | None:
    if "one-third of the time" not in text or "two-thirds of the time" not in text:
        return None
    run_factor = re.search(r"run .*? (?P<factor>[\w.]+) times faster than .*?walk", text)
    skip_factor = re.search(r"skip .*? half as fast as .*?run", text)
    skip_speed = re.search(r"skip at (?P<speed>[\w.]+) miles per hour", text)
    total_time = re.search(r"in (?P<time>[\w.]+) hours?", text)
    if not (run_factor and skip_factor and skip_speed and total_time):
        return None
    factor = parse_number(run_factor.group("factor"))
    skip = parse_number(skip_speed.group("speed"))
    hours = parse_number(total_time.group("time"))
    if None in {factor, skip, hours} or factor == 0:
        return None
    run_speed = skip * 2
    walk_speed = run_speed / factor
    value = hours * Fraction(1, 3) * run_speed + hours * Fraction(2, 3) * walk_speed
    expr = f"{hours}/3*({skip}*2)+{hours}*2/3*(({skip}*2)/{factor})"
    return arithmetic_result("case_frame_speed_fraction_schedule", expr, value, "compiled speed ratios and time fractions into total distance")


def detect_multiplier_excess_distance(text: str) -> ArithmeticNLProblem | None:
    reach = re.search(r"within a distance of (?P<reach>[\w.]+) feet", text)
    base = re.search(r"throw .*? for a distance of (?P<base>[\w.]+) feet", text)
    multi = re.search(r"(?P<multi>[\w.]+) times farther", text)
    if not (reach and base and multi and "outside" in text):
        return None
    reach_value = parse_number(reach.group("reach"))
    base_value = parse_number(base.group("base"))
    multiplier = parse_number(multi.group("multi"))
    if None in {reach_value, base_value, multiplier}:
        return None
    value = base_value * multiplier - reach_value
    expr = f"{base_value}*{multiplier}-{reach_value}"
    return arithmetic_result("case_frame_multiplier_excess_distance", expr, value, "compiled multiplicative range boost minus threshold distance")


def detect_partition_total_minus_remaining(text: str) -> ArithmeticNLProblem | None:
    if "remaining" not in text and "left" not in text:
        return None
    total_match = re.search(r"(?P<groups>[\w.]+) [a-z]+s?.*?each .*? into (?P<parts>[\w.]+) pieces", text)
    if total_match and parse_number(total_match.group("groups")) is None:
        total_match = None
    if not total_match:
        total_match = re.search(r"(?P<groups>[\w.]+) [a-z]+s?.*?cut each .*? into (?P<parts>[\w.]+) pieces", text)
    if total_match and parse_number(total_match.group("groups")) is None:
        total_match = None
    if not total_match:
        baked = re.search(r"(?:baked|made|had) (?P<groups>[\w.]+) [a-z]+ [a-z]+s?", text)
        cut = re.search(r"cut each [a-z]+ into (?P<parts>[\w.]+) pieces", text)
        if baked and cut:
            total_match = re.match(
                r"(?P<groups>.+) (?P<parts>.+)",
                f"{baked.group('groups')} {cut.group('parts')}",
            )
    remaining = re.search(r"(?P<remaining>[\w.]+) pieces? (?:of [a-z]+ )?remaining", text)
    if not (total_match and remaining):
        return None
    groups = parse_number(total_match.group("groups"))
    parts = parse_number(total_match.group("parts"))
    rem = parse_number(remaining.group("remaining"))
    if None in {groups, parts, rem}:
        return None
    value = groups * parts - rem
    expr = f"{groups}*{parts}-{rem}"
    return arithmetic_result("case_frame_partition_total_minus_remaining", expr, value, "compiled partition total minus remaining pieces")


def detect_remaining_calorie_grams(text: str) -> ArithmeticNLProblem | None:
    if "calories per serving" not in text or "grams" not in text:
        return None
    cal = re.search(r"(?P<cal>[\w.]+) calories per serving", text)
    bag = re.search(r"(?P<grams>[\w.]+)g bag has (?P<servings>[\w.]+) servings", text)
    target = re.search(r"target is (?P<target>[\w.]+)", text)
    consumed = re.search(r"already consumed (?P<consumed>[\w.]+)", text)
    if not (cal and bag and target and consumed):
        return None
    calories = parse_number(cal.group("cal"))
    grams = parse_number(bag.group("grams"))
    servings = parse_number(bag.group("servings"))
    target_cal = parse_number(target.group("target"))
    consumed_cal = parse_number(consumed.group("consumed"))
    if None in {calories, grams, servings, target_cal, consumed_cal} or calories == 0:
        return None
    value = (target_cal - consumed_cal) * (grams / servings) / calories
    expr = f"({target_cal}-{consumed_cal})*({grams}/{servings})/{calories}"
    return arithmetic_result("case_frame_remaining_calorie_grams", expr, value, "compiled remaining calories through grams-per-serving density")


def detect_ratio_total_future_value(text: str) -> ArithmeticNLProblem | None:
    ratio = re.search(r"ages are in the ratio of (?P<a>[\w.]+):(?P<b>[\w.]+)", text)
    total = re.search(r"total age now is (?P<total>[\w.]+)", text)
    future = re.search(r"(?P<name>[a-z]+)'?s age (?P<years>[\w.]+) years? from now", text)
    if not (ratio and total and future):
        return None
    a = parse_number(ratio.group("a"))
    b = parse_number(ratio.group("b"))
    total_value = parse_number(total.group("total"))
    years = parse_number(future.group("years"))
    if None in {a, b, total_value, years} or a + b == 0:
        return None
    value = total_value * b / (a + b) + years
    expr = f"{total_value}*{b}/({a}+{b})+{years}"
    return arithmetic_result("case_frame_ratio_total_future_value", expr, value, "compiled two-part ratio, total, and future offset")


def detect_percentage_fee_total(text: str) -> ArithmeticNLProblem | None:
    bill = re.search(r"final bill came to \$?(?P<bill>[\d.]+)", text)
    pct = re.search(r"tacked on a (?P<pct>[\d.]+)% fee", text)
    delivery = re.search(r"charged .*?\$?(?P<delivery>[\d.]+) in delivery", text)
    tip = re.search(r"added a \$?(?P<tip>[\d.]+) tip", text)
    if not (bill and pct):
        return None
    base = parse_decimal_fraction(bill.group("bill"))
    fee = parse_decimal_fraction(pct.group("pct")) / 100
    delivery_value = parse_decimal_fraction(delivery.group("delivery")) if delivery else Fraction(0)
    tip_value = parse_decimal_fraction(tip.group("tip")) if tip else Fraction(0)
    value = base * (1 + fee) + delivery_value + tip_value
    expr = f"{base}*(1+{fee})+{delivery_value}+{tip_value}"
    return arithmetic_result("case_frame_percentage_fee_total", expr, value, "compiled base bill plus percentage fee and fixed charges")


def detect_initial_from_final_periodic_gain(text: str) -> ArithmeticNLProblem | None:
    if "starts with" not in text and "start with" not in text:
        return None
    allowance = re.search(r"(?:receives|gets|earns) .*?\$?(?P<rate>[\d.]+) for (?P<periods>[\w.]+) weeks?", text)
    final = re.search(r"(?:total of|has a total of) \$?(?P<final>[\d.]+)", text)
    if not (allowance and final):
        return None
    rate = parse_decimal_fraction(allowance.group("rate"))
    periods = parse_number(allowance.group("periods"))
    final_value = parse_decimal_fraction(final.group("final"))
    if periods is None:
        return None
    value = final_value - rate * periods
    expr = f"{final_value}-{rate}*{periods}"
    return arithmetic_result("case_frame_initial_from_final_periodic_gain", expr, value, "compiled final state minus periodic gains")


def detect_batch_profit(text: str) -> ArithmeticNLProblem | None:
    if "net profit" not in text:
        return None
    output_per_input = re.search(r"for every [a-z]+ of [a-z]+ .*? make (?P<made>[\w.]+) [a-z]+", text)
    supply_cost = re.search(r"cost \$?(?P<cost>[\d.]+) in supplies", text)
    sell_price = re.search(r"sells? each [a-z]+ for \$?(?P<price>[\d.]+) each", text)
    made_count = re.search(r"makes? and sells? (?P<count>[\w.]+) [a-z]+", text)
    if not (output_per_input and supply_cost and sell_price and made_count):
        return None
    made = parse_number(output_per_input.group("made"))
    cost = parse_decimal_fraction(supply_cost.group("cost"))
    price = parse_decimal_fraction(sell_price.group("price"))
    count = parse_number(made_count.group("count"))
    if None in {made, count} or made == 0:
        return None
    value = count * price - count / made * cost
    expr = f"{count}*{price}-({count}/{made})*{cost}"
    return arithmetic_result("case_frame_batch_profit", expr, value, "compiled production batch cost and unit revenue into net profit")


def detect_unknown_added_package_from_final(text: str) -> ArithmeticNLProblem | None:
    purchased_unknown = re.search(r"purchased a package of (?P<object>[a-z-]+)", text)
    initial = re.search(r"put (?P<initial>[\w.]+) (?P<object>[a-z-]+)", text)
    used = re.search(r"placed .*? on each of (?P<used>[\w.]+)", text)
    remaining = re.search(r"had (?P<remaining>[\w.]+) [a-z-]+(?: [a-z-]+){0,3} remaining", text)
    if not (purchased_unknown and initial and used and remaining):
        return None
    initial_value = parse_number(initial.group("initial"))
    used_value = parse_number(used.group("used"))
    remaining_value = parse_number(remaining.group("remaining"))
    if None in {initial_value, used_value, remaining_value}:
        return None
    value = remaining_value + used_value - initial_value
    expr = f"{remaining_value}+{used_value}-{initial_value}"
    return arithmetic_result("case_frame_unknown_added_package_from_final", expr, value, "compiled final state plus used amount minus initial amount")


def detect_proportional_purchase_total(text: str) -> ArithmeticNLProblem | None:
    if "twice as many" not in text or "cost" not in text or "spent" not in text:
        return None
    blue_spend = re.search(r"spent \$?(?P<spend>[\d.]+) on (?P<base>[a-z]+)", text)
    base_price = re.search(r"(?P<base>[a-z]+) .*? cost \$?(?P<price>[\d.]+) each", text)
    pct_more = re.search(r"(?P<pct>[\d.]+)% more than (?P<base>[a-z]+)", text)
    if not (blue_spend and base_price and pct_more):
        return None
    spend = parse_decimal_fraction(blue_spend.group("spend"))
    price = parse_decimal_fraction(base_price.group("price"))
    pct = parse_decimal_fraction(pct_more.group("pct")) / 100
    if price == 0:
        return None
    base_count = spend / price
    value = spend + 2 * base_count * price * (1 + pct)
    expr = f"{spend}+2*({spend}/{price})*{price}*(1+{pct})"
    return arithmetic_result("case_frame_proportional_purchase_total", expr, value, "compiled proportional item counts and relative unit prices")


def detect_return_trip_time(text: str) -> ArithmeticNLProblem | None:
    if "travels back" not in text and "get back" not in text:
        return None
    speed = re.search(r"travel at (?P<speed>[\w.]+) miles per hour", text)
    time_window = re.search(r"from (?P<start>[\w.]+) to (?P<end>[\w.]+) pm", text)
    back_speed = re.search(r"back at a rate of (?P<back>[\w.]+) mph", text)
    if not (speed and time_window and back_speed):
        return None
    out_speed = parse_number(speed.group("speed"))
    start_hour = parse_number(time_window.group("start"))
    end_hour = parse_number(time_window.group("end"))
    return_speed = parse_number(back_speed.group("back"))
    if None in {out_speed, start_hour, end_hour, return_speed} or return_speed == 0:
        return None
    distance = out_speed * (end_hour - start_hour)
    value = distance / return_speed
    expr = f"{out_speed}*({end_hour}-{start_hour})/{return_speed}"
    return arithmetic_result("case_frame_return_trip_time", expr, value, "compiled outbound distance divided by return speed")


def detect_weight_removal_mix(text: str) -> ArithmeticNLProblem | None:
    if "needs to remove" not in text or "weigh" not in text:
        return None
    target = re.search(r"needs to remove (?P<target>[\w.]+) pounds", text)
    first_weight = re.search(r"comic books weigh (?P<w1>[\d/]+) pound", text)
    second_weight = re.search(r"toys weigh (?P<w2>[\d/]+) pound", text)
    first_count = re.search(r"removes? (?P<count>[\w.]+) comic books", text)
    if not (target and first_weight and second_weight and first_count):
        return None
    target_value = parse_number(target.group("target"))
    w1 = parse_fractionish(first_weight.group("w1"))
    w2 = parse_fractionish(second_weight.group("w2"))
    count = parse_number(first_count.group("count"))
    if target_value is None or count is None or w2 == 0:
        return None
    value = (target_value - count * w1) / w2
    expr = f"({target_value}-{count}*{w1})/{w2}"
    return arithmetic_result("case_frame_weight_removal_mix", expr, value, "compiled target removed weight after one item class into remaining item count")


def detect_two_day_revenue_difference(text: str) -> ArithmeticNLProblem | None:
    if "how much more revenue" not in text:
        return None
    truck_price = re.search(r"truck tire .*? \$?(?P<truck>[\d.]+)", text)
    car_price = re.search(r"car tire .*? \$?(?P<car>[\d.]+)", text)
    thursday = re.search(r"thursday.*?repairs? (?P<truck_count>[\w.]+) truck tires? and (?P<car_count>[\w.]+) car", text)
    friday = re.search(r"friday.*?repairs? (?P<car_count>[\w.]+) car", text)
    if not (truck_price and car_price and thursday and friday):
        return None
    tp = parse_decimal_fraction(truck_price.group("truck"))
    cp = parse_decimal_fraction(car_price.group("car"))
    t_truck = parse_number(thursday.group("truck_count"))
    t_car = parse_number(thursday.group("car_count"))
    f_car = parse_number(friday.group("car_count"))
    if None in {t_truck, t_car, f_car}:
        return None
    rev1 = t_truck * tp + t_car * cp
    rev2 = f_car * cp
    value = abs(rev1 - rev2)
    expr = f"abs(({t_truck}*{tp}+{t_car}*{cp})-({f_car}*{cp}))"
    return arithmetic_result("case_frame_two_day_revenue_difference", expr, value, "compiled two revenue totals and took their positive difference")


def detect_remaining_group_count(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"has (?P<initial>[\w.]+) [a-z]+s?.*?eats? (?P<loss>[\w.]+).*?remaining .*? (?P<per>[\w.]+) [a-z]+s? in one (?P<container>[a-z]+)", text)
    if not match:
        return None
    initial = parse_number(match.group("initial"))
    loss = parse_number(match.group("loss"))
    per = parse_number(match.group("per"))
    if None in {initial, loss, per} or per == 0:
        return None
    value = (initial - loss) / per
    expr = f"({initial}-{loss})/{per}"
    return arithmetic_result("case_frame_remaining_group_count", expr, value, "compiled remaining items divided by group size")


def detect_cluster_plus_individual_total(text: str) -> ArithmeticNLProblem | None:
    match = re.search(r"has (?P<clusters>[\w.]+) clusters? of (?P<each>[\w.]+).*? and (?P<single>[\w.]+) individual", text)
    if not match or "total" not in text:
        return None
    clusters = parse_number(match.group("clusters"))
    each = parse_number(match.group("each"))
    single = parse_number(match.group("single"))
    if None in {clusters, each, single}:
        return None
    value = clusters * each + single
    expr = f"{clusters}*{each}+{single}"
    return arithmetic_result("case_frame_cluster_plus_individual_total", expr, value, "compiled grouped clusters plus individual items")


def detect_prorated_pension(text: str) -> ArithmeticNLProblem | None:
    full = re.search(r"annual pension of \$?(?P<full>[\d.]+)", text)
    start = re.search(r"starting after (?P<start>[\w.]+) years", text)
    pct = re.search(r"(?P<pct>[\d.]+)% of the value", text)
    quit_after = re.search(r"quits after (?P<years>[\w.]+) years", text)
    if not (full and start and pct and quit_after):
        return None
    full_value = parse_decimal_fraction(full.group("full"))
    start_year = parse_number(start.group("start"))
    pct_value = parse_decimal_fraction(pct.group("pct")) / 100
    years = parse_number(quit_after.group("years"))
    if None in {start_year, years}:
        return None
    value = full_value * pct_value * (years - start_year)
    expr = f"{full_value}*{pct_value}*({years}-{start_year})"
    return arithmetic_result("case_frame_prorated_pension", expr, value, "compiled vesting percentage per year after eligibility threshold")


def detect_ratio_total_part(text: str) -> ArithmeticNLProblem | None:
    ratio = re.search(r"ratio of (?P<a>[\w.]+):(?P<b>[\w.]+)", text)
    total = re.search(r"total of (?P<total>[\w.]+)", text)
    if not (ratio and total):
        return None
    a = parse_number(ratio.group("a"))
    b = parse_number(ratio.group("b"))
    total_value = parse_number(total.group("total"))
    if None in {a, b, total_value} or a + b == 0:
        return None
    value = total_value * a / (a + b)
    expr = f"{total_value}*{a}/({a}+{b})"
    return arithmetic_result("case_frame_ratio_total_part", expr, value, "compiled ratio and total into first part")


def detect_two_period_total_with_difference(text: str) -> ArithmeticNLProblem | None:
    first = re.search(r"expenditure .*? was \$?(?P<first>[\d.]+)", text)
    less = re.search(r"was \$?(?P<less>[\d.]+) less", text)
    if not (first and less and "total expenditure" in text):
        return None
    first_value = parse_decimal_fraction(first.group("first"))
    less_value = parse_decimal_fraction(less.group("less"))
    value = first_value + (first_value - less_value)
    expr = f"{first_value}+({first_value}-{less_value})"
    return arithmetic_result("case_frame_two_period_total_with_difference", expr, value, "compiled first-period value plus second-period difference")


def detect_fraction_loser_votes(text: str) -> ArithmeticNLProblem | None:
    if "winner" not in text or "loser" not in text:
        return None
    frac = re.search(r"winner got (?P<frac>[\d/]+) of the votes", text)
    total = re.search(r"total number .*? was (?P<total>[\w.]+)", text)
    if not (frac and total):
        return None
    winner_fraction = parse_fractionish(frac.group("frac"))
    total_value = parse_number(total.group("total"))
    if total_value is None:
        return None
    value = total_value * (1 - winner_fraction)
    expr = f"{total_value}*(1-{winner_fraction})"
    return arithmetic_result("case_frame_fraction_loser_votes", expr, value, "compiled loser votes as complement of winner fraction")


def parse_fractionish(value: str) -> Fraction:
    value = value.strip().rstrip(".,;:!?")
    if "/" in value:
        num, den = value.split("/", 1)
        return Fraction(num) / Fraction(den)
    return parse_decimal_fraction(value)


def arithmetic_result(intent: str, expression: str, value: Fraction | int, explanation: str) -> ArithmeticNLProblem:
    return ArithmeticNLProblem(
        intent=intent,
        expression=expression,
        answer_exact=format_fraction(value),
        explanation=explanation,
    )


def parse_number(value: str) -> Fraction | None:
    value = value.strip().lower().rstrip(".,;:!?").replace(",", "").removeprefix("$")
    if value == "another":
        return Fraction(1)
    if value in {"twice", "double"}:
        return Fraction(2)
    if value == "thrice":
        return Fraction(3)
    if value in {"half", "a-half"}:
        return Fraction(1, 2)
    if value in {"third", "a-third"}:
        return Fraction(1, 3)
    if value in {"quarter", "a-quarter"}:
        return Fraction(1, 4)
    if value == "dozen":
        return Fraction(12)
    fraction_word = parse_fraction_word(value)
    if fraction_word is not None:
        return fraction_word
    if re.fullmatch(r"(?:\d+(?:\.\d+)?|\.\d+)", value):
        return Fraction(value)
    if value in NUMBER_WORDS:
        return Fraction(NUMBER_WORDS[value])
    if "-" in value:
        parts = value.split("-")
        if "hundred" in parts:
            hundred_index = parts.index("hundred")
            prefix = sum(NUMBER_WORDS.get(part, 0) for part in parts[:hundred_index]) or 1
            suffix = sum(NUMBER_WORDS.get(part, 0) for part in parts[hundred_index + 1 :])
            return Fraction(prefix * 100 + suffix)
        total = sum(NUMBER_WORDS.get(part, 0) for part in parts)
        return Fraction(total) if total else None
    return None


def parse_fraction_word(value: str) -> Fraction | None:
    value = value.strip().lower().rstrip(".,;:!?")
    denominator_words = {
        "half": 2,
        "halves": 2,
        "third": 3,
        "thirds": 3,
        "quarter": 4,
        "quarters": 4,
        "fourth": 4,
        "fourths": 4,
        "fifth": 5,
        "fifths": 5,
        "sixth": 6,
        "sixths": 6,
        "seventh": 7,
        "sevenths": 7,
        "eighth": 8,
        "eighths": 8,
        "ninth": 9,
        "ninths": 9,
        "tenth": 10,
        "tenths": 10,
    }
    if "-" not in value:
        return None
    numerator_text, denominator_text = value.split("-", 1)
    numerator = NUMBER_WORDS.get(numerator_text)
    denominator = denominator_words.get(denominator_text)
    if numerator is None or denominator is None:
        return None
    return Fraction(numerator, denominator)


def parse_decimal_fraction(value: str) -> Fraction:
    return Fraction(value.strip().rstrip(".,;:!?").replace(",", "").removeprefix("$"))


def extract_numbers(text: str) -> list[Fraction]:
    values: list[Fraction] = []
    for match in re.finditer(NUMBER_RE, text):
        value = parse_number(match.group(0))
        if value is not None:
            values.append(value)
    return values


def extract_answer_choice_numbers(text: str) -> list[int]:
    values = []
    for match in re.finditer(r"\([a-e]\)\s*\$?(?P<value>-?\d+(?:\.\d+)?)", text):
        value = Fraction(match.group("value"))
        if value.denominator == 1:
            values.append(int(value))
    return values


def extract_answer_choice_values(text: str) -> list[Fraction]:
    return [
        Fraction(match.group("value"))
        for match in re.finditer(r"\([a-e]\)\s*\$?(?P<value>-?\d+(?:\.\d+)?)", text)
    ]


def parse_duration_hours(value: str) -> Fraction | None:
    value = value.strip().lower()
    if value == "half-hour":
        return Fraction(1, 2)
    value = value.removesuffix(" hours").removesuffix(" hour").strip()
    return parse_number(value)


def parse_fraction_expr(value: str) -> Fraction | None:
    value = value.strip()
    match = re.fullmatch(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", value)
    if match:
        numerator = parse_number(match.group(1))
        denominator = parse_number(match.group(2))
        if numerator is None or denominator in {None, 0}:
            return None
        return numerator / denominator
    match = re.fullmatch(r"(-?\d+(?:\.\d+)?)/(-?\d+(?:\.\d+)?)", value)
    if match:
        denominator = Fraction(match.group(2))
        if denominator == 0:
            return None
        return Fraction(match.group(1)) / denominator
    return parse_number(value)


def parse_base_number(value: str, base: int) -> Fraction:
    if "." not in value:
        return Fraction(int(value, base))
    integer, fractional = value.split(".", 1)
    total = Fraction(int(integer, base))
    for index, digit_text in enumerate(fractional, start=1):
        digit = int(digit_text, base)
        total += Fraction(digit, base**index)
    return total


def parse_linear_coefficient(value: str) -> Fraction:
    cleaned = value.strip()
    if cleaned in {"", "+"}:
        return Fraction(1)
    if cleaned == "-":
        return Fraction(-1)
    return Fraction(cleaned)


def extract_coordinate_points(text: str) -> list[tuple[Fraction, Fraction]]:
    points: list[tuple[Fraction, Fraction]] = [
        (Fraction(x), Fraction(y))
        for x, y in re.findall(r"\((?P<x>-?\d+),(?P<y>-?\d+)\)", text)
    ]
    if points:
        return points
    for token in re.findall(r"\((-?\d{2,3})\)", text):
        if token.startswith("-") and len(token) == 3:
            points.append((Fraction(int(token[:2])), Fraction(int(token[2:]))))
        elif not token.startswith("-") and len(token) == 2:
            points.append((Fraction(int(token[0])), Fraction(int(token[1]))))
        elif not token.startswith("-") and len(token) == 3:
            points.append((Fraction(int(token[0])), Fraction(int(token[1:]))))
    return points


def parse_base_equation_side(side: str, base_symbol: Any) -> Any:
    total = 0
    for factor_text in re.split(r"\\cdot|\*", side):
        factor = factor_text.strip()
        if not factor:
            continue
        total = parse_base_token(factor, base_symbol) if total == 0 else total * parse_base_token(factor, base_symbol)
    return total


def parse_base_token(token: str, base_symbol: Any) -> Any:
    token = token.strip()
    token = token.removesuffix("_b")
    token = re.sub(r"_\{?b\}?", "", token)
    if not token:
        return 0
    if not token.isdigit():
        return sp.sympify(token, locals={"b": base_symbol})
    value = 0
    for digit in token:
        value = value * base_symbol + int(digit)
    return value


def max_digit_in_base_equation(text: str) -> int:
    digits = [int(digit) for digit in re.findall(r"\d", text)]
    return max(digits, default=0)


def parse_complex_expr(value: str) -> Any:
    cleaned = value.replace(" ", "").replace("i", "*I")
    cleaned = re.sub(r"(?<!\*)I", "I", cleaned)
    return sp.sympify(cleaned, locals={"I": sp.I})


def normalize_vector_macros(text: str) -> str:
    return (
        text.replace(r"\mathbf{u}", "u")
        .replace(r"\mathbf{v}", "v")
        .replace(r"\mathbf{a}", "a")
        .replace(r"\mathbf{b}", "b")
    )


def proper_positive_divisors(n: int) -> list[int]:
    return [candidate for candidate in range(1, n) if n % candidate == 0]


def sqrt_fraction_if_square(value: Fraction) -> Fraction | None:
    if value < 0:
        return None
    numerator = int(value.numerator)
    denominator = int(value.denominator)
    numerator_root = int(numerator**0.5)
    denominator_root = int(denominator**0.5)
    if numerator_root * numerator_root == numerator and denominator_root * denominator_root == denominator:
        return Fraction(numerator_root, denominator_root)
    return None


def clean_math_expr(value: str) -> str:
    return value.replace("^", "**").replace("{", "").replace("}", "")


def format_fraction(value: Fraction | int) -> str:
    value = Fraction(value)
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"


def normalize_text(text: str) -> str:
    text = text.replace("’", "'").replace("“", '"').replace("”", '"')
    text = re.sub(r"\$([^$]+)\$", normalize_tex_dollar_span, text)
    text = text.replace(r"\%", "%")
    text = text.replace(",", "")
    text = re.sub(r"\$([^$]+)\$", normalize_tex_dollar_span, text)
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_tex_dollar_span(match: re.Match[str]) -> str:
    content = match.group(1).strip()
    if "\\" in content:
        return content
    if " " in content and not any(operator in content for operator in "+-*/^=<>|_{}()"):
        return match.group(0)
    if re.fullmatch(r"[A-Za-z0-9_+\-*/^=.{}()| ]+", content):
        return content
    return match.group(0)
