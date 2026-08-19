"""Executable backend contracts for LiftCertificate experiments.

This module is deliberately small.  It executes only when a typed semantic graph
already contains an admissible LiftCertificate.  The goal is to test whether the
abstract object/morphism/constraint representation carries enough information
to compute the answer without using benchmark IDs or memorized answers.
"""

from __future__ import annotations

import re
from fractions import Fraction
from math import comb, isqrt
from typing import Any

try:
    import sympy as sp
except ImportError:  # pragma: no cover
    sp = None

try:
    from math_os_prototype.prime_power_symmetry import analyze_prime_power_symmetry
except ImportError:  # pragma: no cover
    from prime_power_symmetry import analyze_prime_power_symmetry


def solve_from_lift_certificates(semantic_graph: dict[str, Any]) -> dict[str, Any] | None:
    certs = [cert for cert in semantic_graph.get("lift_certificates", []) or [] if cert.get("admissible")]
    for cert in certs:
        family_id = str(cert.get("family_id") or "")
        if family_id == "elementary_number_theory.prime_power_symmetric_primality":
            return solve_prime_power_symmetric_primality(cert)
        if family_id == "discrete_affine_sequence.nth_term":
            answer = solve_affine_sequence(semantic_graph)
        elif family_id == "inner_product_geometry.distance":
            answer = solve_distance(semantic_graph)
        elif family_id == "affine_geometry.midpoint_observable":
            answer = solve_midpoint_coordinate_sum(semantic_graph)
        elif family_id == "quotient_ring.residue":
            answer = solve_residue(semantic_graph)
        elif family_id == "ordered_field.scalar_percent_action":
            answer = solve_percent_tip(semantic_graph)
        elif family_id == "circle_group.clock_angle":
            answer = solve_clock_angle(semantic_graph)
        elif family_id == "probability.complement_event":
            answer = solve_complement_probability(semantic_graph)
        elif family_id == "ordered_field.absolute_value_equation":
            answer = solve_absolute_value_equation(semantic_graph)
        elif family_id == "real_closed_field.quadratic_interval":
            answer = solve_quadratic_interval(semantic_graph)
        elif family_id == "ordered_field.compound_growth_rate":
            answer = solve_compound_growth_rate(semantic_graph)
        elif family_id == "state_event.additive_quantity":
            answer = solve_state_event_additive_quantity(semantic_graph)
        elif family_id == "polynomial_notation.base_expansion":
            answer = solve_base_equation(semantic_graph)
        elif family_id == "real_closed_field.quadratic_root_observable":
            answer = solve_quadratic_root_observable(semantic_graph)
        elif family_id == "polynomial_ring.remainder_linear_divisor":
            answer = solve_polynomial_remainder(semantic_graph)
        elif family_id == "polynomial_ring.remainder_repeated_linear_divisor":
            answer = solve_repeated_linear_remainder(semantic_graph)
        elif family_id == "vector_space.linear_system_2x2":
            answer = solve_linear_system_2x2(semantic_graph)
        elif family_id == "elementary_functions.log_equation":
            answer = solve_log_equation(semantic_graph)
        elif family_id == "elementary_functions.exponential_equation":
            answer = solve_exponential_equation(semantic_graph)
        elif family_id == "elementary_functions.trig_pythagorean":
            answer = solve_trig_pythagorean(semantic_graph)
        elif family_id == "combinatorics.binomial_coefficient":
            answer = solve_binomial_coefficient(semantic_graph)
        elif family_id == "probability.binomial_exact":
            answer = solve_binomial_probability(semantic_graph)
        elif family_id == "inner_product_geometry.dot_product":
            answer = solve_dot_product(semantic_graph)
        elif family_id == "affine_geometry.line_intersection":
            answer = solve_line_intersection(semantic_graph)
        elif family_id == "euclidean_geometry.circle_radius":
            answer = solve_circle_radius(semantic_graph)
        elif family_id == "calculus.polynomial_derivative_value":
            answer = solve_polynomial_derivative_value(semantic_graph)
        elif family_id == "calculus.polynomial_definite_integral":
            answer = solve_polynomial_definite_integral(semantic_graph)
        else:
            answer = None
        if answer is not None:
            return {
                "status": "solved",
                "answer_exact": answer,
                "provenance": "lift_certificate_backend",
                "family_id": family_id,
                "canonical_signature": cert.get("canonical_signature"),
            }
    return None


def solve_prime_power_symmetric_primality(cert: dict[str, Any]) -> dict[str, Any]:
    """Return explicitly bounded evidence; never present it as an unbounded proof."""
    report = analyze_prime_power_symmetry(
        search_limit=100,
        sieve_bound=1000,
        run_primality_checks=True,
    )
    if report.examples:
        a, b, c, first, second = report.examples[0]
        answer = f"Found probable example (a,b,c)=({a},{b},{c}): {first}, {second}"
    else:
        answer = (
            f"Bounded verification: no example for a <= {report.search_limit}; "
            "the unbounded existence question remains unresolved."
        )
    return {
        "status": "bounded_evidence",
        "answer_exact": answer,
        "provenance": "kernel:prime_power_symmetric_primality",
        "family_id": report.problem,
        "canonical_signature": cert.get("canonical_signature"),
        "report": report.to_dict(),
    }


def solve_affine_sequence(graph: dict[str, Any]) -> str | None:
    values: dict[int, Fraction] = {}
    for expression in constraint_expressions(graph):
        match = re.search(r"NthTerm\(seq,\s*(\d+)\)\s*=\s*(-?\d+(?:/\d+)?)", expression)
        if match:
            values[int(match.group(1))] = Fraction(match.group(2))
    target = query_target(graph, "NthTerm")
    target_match = re.search(r"NthTerm\(seq,\s*(\d+)\)", target)
    if not target_match or 1 not in values or 2 not in values:
        return None
    n = int(target_match.group(1))
    d = values[2] - values[1]
    return format_fraction(values[1] + (n - 1) * d)


def solve_distance(graph: dict[str, Any]) -> str | None:
    point = extract_named_point(graph, "P")
    if point is None:
        return None
    x, y = point
    return sqrt_answer(x * x + y * y)


def solve_midpoint_coordinate_sum(graph: dict[str, Any]) -> str | None:
    first = extract_named_point(graph, "A")
    second = extract_named_point(graph, "B")
    if first is None or second is None:
        return None
    x1, y1 = first
    x2, y2 = second
    x_mid = Fraction(x1 + x2, 2)
    y_mid = Fraction(y1 + y2, 2)
    source = str(graph.get("source_text") or "").lower()
    if "reflected" in source or "reflection" in source:
        if re.search(r"\$?x\$?\s*[- ]\s*axis", source):
            y_mid = -y_mid
        elif re.search(r"\$?y\$?\s*[- ]\s*axis", source):
            x_mid = -x_mid
        elif "origin" in source:
            x_mid = -x_mid
            y_mid = -y_mid
    return format_fraction(x_mid + y_mid)


def solve_residue(graph: dict[str, Any]) -> str | None:
    for expression in constraint_expressions(graph):
        match = re.search(r"PowerMod\((-?\d+),\s*(\d+),\s*(\d+)\)", expression)
        if match:
            return str(pow(int(match.group(1)), int(match.group(2)), int(match.group(3))))
        match = re.search(r"ModResidue\((-?\d+),\s*(\d+)\)", expression)
        if match:
            return str(int(match.group(1)) % int(match.group(2)))
    return None


def solve_percent_tip(graph: dict[str, Any]) -> str | None:
    amounts = [Fraction(item) for item in re.findall(r"\$(\d+(?:\.\d+)?(?:/\d+)?)", str(graph.get("source_text") or ""))]
    if len(amounts) >= 2:
        bill = min(amounts[0], amounts[1])
        paid = max(amounts[0], amounts[1])
        if bill == 0:
            return None
        return format_fraction((paid - bill) / bill * 100)

    amounts = []
    for expression in constraint_expressions(graph):
        match = re.search(r"observe_[^(]+\([^)]*\)\s*=\s*(-?\d+(?:\.\d+)?(?:/\d+)?)", expression)
        if match:
            amounts.append(Fraction(match.group(1)))
    if len(amounts) < 2:
        return None
    bill = min(amounts[0], amounts[1])
    paid = max(amounts[0], amounts[1])
    if bill == 0:
        return None
    return format_fraction((paid - bill) / bill * 100)


def solve_clock_angle(graph: dict[str, Any]) -> str | None:
    text = str(graph.get("source_text") or "")
    match = re.search(r"(?:reads|clock reads)\s*(\d{1,2}):00", text, flags=re.IGNORECASE)
    if match:
        hour = int(match.group(1)) % 12
    else:
        values = []
        for expression in constraint_expressions(graph):
            match = re.search(r"=\s*(\d+)$", expression)
            if match:
                values.append(int(match.group(1)))
        if not values:
            return None
        hour = values[0] % 12
    angle = abs(30 * hour)
    return str(min(angle, 360 - angle))


def solve_complement_probability(graph: dict[str, Any]) -> str | None:
    for expression in constraint_expressions(graph):
        match = re.search(r"P\(event\)\s*=\s*(.+)$", expression)
        if match:
            probability = parse_fraction_like(match.group(1))
            if probability is not None:
                return format_fraction(Fraction(1) - probability)
    return None


def solve_absolute_value_equation(graph: dict[str, Any]) -> str | None:
    if sp is None:
        return None
    for expression in constraint_expressions(graph):
        match = re.search(r"AbsEquation\((.+?)=(.+?)\)", expression)
        if not match:
            continue
        x = sp.symbols("x")
        try:
            left = sp.sympify(normalize_linear_expression(match.group(1)), locals={"x": x})
            right = sp.sympify(normalize_linear_expression(match.group(2)), locals={"x": x})
            solutions = set()
            for sign in (1, -1):
                for solution in sp.solve(sp.Eq(left, sign * right), x):
                    solutions.add(sp.simplify(solution))
            if not solutions:
                return None
            ordered = sorted(solutions, key=lambda item: float(item))
            return str(ordered[0])
        except Exception:
            return None
    return None


def solve_quadratic_interval(graph: dict[str, Any]) -> str | None:
    if sp is None:
        return None
    for expression in constraint_expressions(graph):
        match = re.search(r"x\^2\s*([+-]\s*\d+)\*x\s*([+-]\s*\d+)\s*<=\s*(-?\d+)", expression)
        if not match:
            continue
        x = sp.symbols("x")
        b = int(match.group(1).replace(" ", ""))
        c = int(match.group(2).replace(" ", ""))
        rhs = int(match.group(3))
        roots = sorted(sp.solve(sp.Eq(x**2 + b * x + c - rhs, 0), x), key=lambda item: float(item))
        if len(roots) != 2:
            return None
        return f"x \\in [{sp.sstr(roots[0])},{sp.sstr(roots[1])}]"
    return None


def solve_compound_growth_rate(graph: dict[str, Any]) -> str | None:
    for expression in constraint_expressions(graph):
        match = re.search(r"CompoundGrowth\((\d+(?:\.\d+)?),\s*rate_percent,\s*(\w+|\d+)\)\s*=\s*(\d+(?:\.\d+)?)", expression)
        if not match:
            continue
        start = float(Fraction(match.group(1)))
        years = parse_number_word(match.group(2))
        final = float(Fraction(match.group(3)))
        if start <= 0 or years is None or years <= 0:
            return None
        rate = round(((final / start) ** (1 / years) - 1) * 100)
        return str(rate)
    return None


def solve_state_event_additive_quantity(graph: dict[str, Any]) -> str | None:
    target = query_target(graph, "StateQuery")
    target_match = re.search(r"StateQuery\(([^,]+),([^,]+),final\)", target)
    if not target_match:
        return None
    owner = target_match.group(1)
    obj = target_match.group(2)
    initial_values: list[Fraction] = []
    deltas: list[Fraction] = []
    for expression in constraint_expressions(graph):
        initial = re.search(rf"InitialState\({re.escape(owner)},{re.escape(obj)}\)\s*=\s*(-?\d+(?:/\d+)?)", expression)
        if initial:
            initial_values.append(Fraction(initial.group(1)))
            continue
        delta = re.search(rf"Delta\({re.escape(owner)},{re.escape(obj)}\)\s*=\s*(-?\d+(?:/\d+)?)", expression)
        if delta:
            deltas.append(Fraction(delta.group(1)))
    if len(initial_values) != 1:
        return None
    if not deltas:
        return None
    return format_fraction(initial_values[0] + sum(deltas, Fraction(0)))


def solve_base_equation(graph: dict[str, Any]) -> str | None:
    if sp is None:
        return None
    raw = None
    for expression in constraint_expressions(graph):
        match = re.search(r"BaseEquation\((.+?)=(.+?)\)", expression)
        if match:
            raw = (match.group(1).strip(), match.group(2).strip())
            break
    if raw is None:
        return None
    b = sp.symbols("b", integer=True, positive=True)
    try:
        lhs = parse_base_expression(raw[0], b)
        rhs = parse_base_expression(raw[1], b)
        min_base = max_digit(raw[0] + raw[1]) + 1
        solutions = [sol for sol in sp.solve(sp.Eq(lhs, rhs), b) if sol.is_integer and sol >= min_base]
        if not solutions:
            return None
        return str(int(solutions[0]))
    except Exception:
        return None


def constraint_expressions(graph: dict[str, Any]) -> list[str]:
    return [str(item.get("expression") or "") for item in graph.get("constraints", []) or []]


def query_target(graph: dict[str, Any], prefix: str) -> str:
    for query in graph.get("queries", []) or []:
        target = str(query.get("target") or "")
        expression = str(query.get("expression") or "")
        if prefix in target or prefix in expression:
            return target or expression
    return ""


def extract_named_point(graph: dict[str, Any], name: str) -> tuple[int, int] | None:
    for expression in constraint_expressions(graph):
        match = re.search(rf"\b{re.escape(name)}\s*=\s*\((-?\d+),\s*(-?\d+)\)", expression)
        if match:
            return int(match.group(1)), int(match.group(2))
    for obj in graph.get("objects", []) or []:
        if obj.get("name") == name:
            expression = str(obj.get("expression") or "")
            match = re.search(r"\((-?\d+),\s*(-?\d+)\)", expression)
            if match:
                return int(match.group(1)), int(match.group(2))
    return None


def solve_quadratic_root_observable(graph: dict[str, Any]) -> str | None:
    for expression in constraint_expressions(graph):
        match = re.search(r"QuadraticEquation\((-?\d+),([+-]?\d+),([+-]?\d+)\)", expression)
        if not match:
            continue
        a = Fraction(int(match.group(1)))
        b = Fraction(int(match.group(2)))
        c = Fraction(int(match.group(3)))
        target = " ".join(str(item.get("target") or "") for item in graph.get("queries", []) or [])
        if "product" in target:
            return format_fraction(c / a)
        return format_fraction(-b / a)
    return None


def solve_polynomial_remainder(graph: dict[str, Any]) -> str | None:
    if sp is None:
        return None
    for expression in constraint_expressions(graph):
        match = re.search(r"PolynomialRemainder\((.+),\s*x-(-?\d+)\)", expression)
        if not match:
            continue
        x = sp.symbols("x")
        try:
            polynomial = sp.sympify(normalize_polynomial_expression(match.group(1)), locals={"x": x})
            value = sp.simplify(polynomial.subs(x, int(match.group(2))))
            return sp.sstr(value)
        except Exception:
            return None
    return None


def solve_repeated_linear_remainder(graph: dict[str, Any]) -> str | None:
    for expression in constraint_expressions(graph):
        match = re.search(r"RepeatedLinearRemainder\(x\^(\d+),\s*x-(-?\d+),\s*2\)", expression)
        if not match:
            continue
        n = int(match.group(1))
        a = int(match.group(2))
        if n < 1:
            return None
        # f(x)=x^n, remainder mod (x-a)^2 is f(a)+f'(a)(x-a).
        constant = a**n
        slope = n * (a ** (n - 1))
        intercept = constant - slope * a
        if slope == 0:
            return str(intercept)
        if intercept == 0:
            return f"{slope}*x"
        sign = "+" if intercept > 0 else "-"
        return f"{slope}*x {sign} {abs(intercept)}"
    return None


def solve_linear_system_2x2(graph: dict[str, Any]) -> str | None:
    for expression in constraint_expressions(graph):
        match = re.search(r"LinearSystem2\((-?\d+),([+-]?\d+),(-?\d+),(-?\d+),([+-]?\d+),(-?\d+)\)", expression)
        if not match:
            continue
        a, b, c, d, e, f = [Fraction(int(item)) for item in match.groups()]
        determinant = a * e - b * d
        if determinant == 0:
            return None
        x = (c * e - b * f) / determinant
        y = (a * f - c * d) / determinant
        target = " ".join(str(item.get("target") or "") for item in graph.get("queries", []) or [])
        if "x+y" in target:
            return format_fraction(x + y)
        return f"({format_fraction(x)},{format_fraction(y)})"
    return None


def solve_log_equation(graph: dict[str, Any]) -> str | None:
    for expression in constraint_expressions(graph):
        match = re.search(r"LogEquation\((\d+),x,(-?\d+)\)", expression)
        if match:
            base = int(match.group(1))
            exponent = int(match.group(2))
            if exponent >= 0:
                return str(base**exponent)
            return format_fraction(Fraction(1, base ** abs(exponent)))
    return None


def solve_exponential_equation(graph: dict[str, Any]) -> str | None:
    for expression in constraint_expressions(graph):
        match = re.search(r"ExponentialEquation\((\d+),x,(\d+)\)", expression)
        if not match:
            continue
        base = int(match.group(1))
        target = int(match.group(2))
        value = 1
        for exponent in range(0, 64):
            if value == target:
                return str(exponent)
            value *= base
        return None
    return None


def solve_trig_pythagorean(graph: dict[str, Any]) -> str | None:
    for expression in constraint_expressions(graph):
        match = re.search(r"SinValue\(theta,(\d+/\d+)\)", expression)
        if match:
            sine = Fraction(match.group(1))
            return format_fraction(Fraction(1) - sine * sine)
    return None


def solve_binomial_coefficient(graph: dict[str, Any]) -> str | None:
    for expression in constraint_expressions(graph):
        match = re.search(r"BinomialCoefficient\((\d+),(\d+)\)", expression)
        if match:
            n = int(match.group(1))
            k = int(match.group(2))
            if 0 <= k <= n:
                return str(comb(n, k))
    return None


def solve_binomial_probability(graph: dict[str, Any]) -> str | None:
    for expression in constraint_expressions(graph):
        match = re.search(r"BinomialProbability\((\d+),(\d+),(\d+/\d+|\d+(?:\.\d+)?)\)", expression)
        if not match:
            continue
        n = int(match.group(1))
        k = int(match.group(2))
        probability = parse_fraction_like(match.group(3))
        if probability is None or not 0 <= k <= n:
            return None
        value = Fraction(comb(n, k)) * probability**k * (1 - probability) ** (n - k)
        return format_fraction(value)
    return None


def solve_dot_product(graph: dict[str, Any]) -> str | None:
    for expression in constraint_expressions(graph):
        match = re.search(r"DotProductVectors\((-?\d+),(-?\d+),(-?\d+),(-?\d+)\)", expression)
        if match:
            a, b, c, d = [int(item) for item in match.groups()]
            return str(a * c + b * d)
    return None


def solve_line_intersection(graph: dict[str, Any]) -> str | None:
    for expression in constraint_expressions(graph):
        match = re.search(r"LineIntersection\((-?\d+),([+-]?\d+),(-?\d+),([+-]?\d+)\)", expression)
        if not match:
            continue
        m1 = Fraction(int(match.group(1)))
        b1 = Fraction(int(match.group(2)))
        m2 = Fraction(int(match.group(3)))
        b2 = Fraction(int(match.group(4)))
        if m1 == m2:
            return None
        x = (b2 - b1) / (m1 - m2)
        y = m1 * x + b1
        return format_fraction(x + y)
    return None


def solve_circle_radius(graph: dict[str, Any]) -> str | None:
    for expression in constraint_expressions(graph):
        match = re.search(r"CircleRadiusData\((-?\d+),(-?\d+),(-?\d+),(-?\d+)\)", expression)
        if match:
            h, k, x, y = [int(item) for item in match.groups()]
            return sqrt_answer((x - h) ** 2 + (y - k) ** 2)
    return None


def solve_polynomial_derivative_value(graph: dict[str, Any]) -> str | None:
    for expression in constraint_expressions(graph):
        match = re.search(r"DerivativeValue\((-?\d+),([+-]?\d+),([+-]?\d+),(-?\d+)\)", expression)
        if match:
            a = Fraction(int(match.group(1)))
            b = Fraction(int(match.group(2)))
            t = Fraction(int(match.group(4)))
            return format_fraction(2 * a * t + b)
    return None


def solve_polynomial_definite_integral(graph: dict[str, Any]) -> str | None:
    for expression in constraint_expressions(graph):
        match = re.search(r"DefiniteIntegral\(0,(-?\d+),(-?\d+),([+-]?\d+),([+-]?\d+)\)", expression)
        if match:
            r = Fraction(int(match.group(1)))
            a = Fraction(int(match.group(2)))
            b = Fraction(int(match.group(3)))
            c = Fraction(int(match.group(4)))
            return format_fraction(a * r**3 / 3 + b * r**2 / 2 + c * r)
    return None


def sqrt_answer(value: int) -> str:
    root = isqrt(value)
    if root * root == value:
        return str(root)
    return f"sqrt({value})"


def format_fraction(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"


def parse_fraction_like(value: str) -> Fraction | None:
    value = value.strip()
    frac = re.fullmatch(r"\\frac\{(-?\d+)\}\{(-?\d+)\}", value)
    if frac:
        return Fraction(int(frac.group(1)), int(frac.group(2)))
    try:
        return Fraction(value)
    except Exception:
        return None


def normalize_linear_expression(value: str) -> str:
    value = value.strip()
    value = value.replace("^", "**")
    value = re.sub(r"(?<=\d)\s*x", "*x", value)
    value = re.sub(r"(?<=\d)(?=x)", "*", value)
    return value


def normalize_polynomial_expression(value: str) -> str:
    value = value.strip()
    value = value.replace("^", "**")
    value = re.sub(r"(?<=\d)\s*x", "*x", value)
    value = re.sub(r"(?<=\d)(?=x)", "*", value)
    return value


NUMBER_WORDS_SMALL = {
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
}


def parse_number_word(value: str) -> int | None:
    value = value.lower().strip()
    if value.isdigit():
        return int(value)
    return NUMBER_WORDS_SMALL.get(value)


def parse_base_expression(value: str, base_symbol: Any) -> Any:
    value = value.replace(" ", "")
    value = value.replace("\\cdot", "*").replace("×", "*")
    value = value.replace("{", "").replace("}", "")
    value = re.sub(r"\$_?", "", value)
    parts = re.split(r"(?=[+-])", value)
    total = 0
    for part in parts:
        if not part:
            continue
        sign = -1 if part.startswith("-") else 1
        token = part.lstrip("+-")
        product = parse_base_product(token, base_symbol)
        if product is None:
            return None
        total += sign * product
    return total


def parse_base_product(value: str, base_symbol: Any) -> Any:
    factors = [item for item in value.split("*") if item]
    if not factors:
        return None
    product = 1
    for factor in factors:
        parsed = parse_base_factor(factor, base_symbol, explicit_context=len(factors) == 1)
        if parsed is None:
            return None
        product *= parsed
    return product


def parse_base_factor(value: str, base_symbol: Any, *, explicit_context: bool) -> Any:
    value = value.strip()
    if not value:
        return None
    if "_" in value:
        digits, _base = value.split("_", 1)
        if digits.isdigit():
            return digits_to_polynomial(digits, base_symbol)
        return None
    if value.isdigit():
        if len(value) >= 2:
            return digits_to_polynomial(value, base_symbol)
        return int(value)
    return None


def digits_to_polynomial(digits: str, base_symbol: Any) -> Any:
    total = 0
    for digit in digits:
        total = total * base_symbol + int(digit)
    return total


def max_digit(value: str) -> int:
    digits = [int(item) for item in re.findall(r"\d", value)]
    return max(digits) if digits else 1
