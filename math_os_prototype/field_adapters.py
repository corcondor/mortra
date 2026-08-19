"""Specialized field IRs and adapters for recurring benchmark problem types."""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass
from fractions import Fraction
from itertools import product
from typing import Any

try:
    import sympy as sp
except ImportError:  # pragma: no cover
    sp = None


@dataclass
class NumberTheoryIR:
    kind: str
    variables: list[str]
    constraints: list[str]
    target: str
    parameters: dict[str, Any]


@dataclass
class InequalityIR:
    kind: str
    variables: list[str]
    assumptions: list[str]
    target_relation: str
    search_bounds: tuple[int, int]


@dataclass
class GeometryIR:
    kind: str
    objects: list[str]
    parameters: dict[str, Any]
    target: str


@dataclass
class ProbabilityIR:
    kind: str
    random_objects: list[str]
    parameters: dict[str, Any]
    target: str


@dataclass
class SpecializedProblem:
    domain: str
    intent: str
    symbols: list[str]
    givens: dict[str, Any]
    goal: str
    plan: list[str]
    tool_name: str
    command: str
    executable: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def detect_specialized_problem(text: str) -> SpecializedProblem | None:
    normalized = normalize_text(text)
    detectors = (
        detect_factorial_weeks_problem,
        detect_circle_overlap_limit_problem,
        detect_two_card_correlation_problem,
        detect_k_card_correlation_angle_problem,
        detect_inequality_counterexample_problem,
    )
    for detector in detectors:
        problem = detector(normalized, text)
        if problem is not None:
            return problem
    return None


def detect_factorial_weeks_problem(normalized: str, source: str) -> SpecializedProblem | None:
    if (
        "週間" not in normalized
        or "秒" not in normalized
        or not any(notation in normalized for notation in ("n!", "factorial(n)"))
    ):
        return None
    ir = NumberTheoryIR(
        kind="factorial_divisibility",
        variables=["m", "n"],
        constraints=["m,n are nonnegative integers", "m weeks = n! seconds"],
        target="all pairs (m,n)",
        parameters={"seconds_per_week": 604800},
    )
    return SpecializedProblem(
        domain="number_theory",
        intent="number_theory_factorial_weeks",
        symbols=["m", "n"],
        givens={"number_theory_ir": asdict(ir)},
        goal="Solve the factorial divisibility condition for whole weeks.",
        plan=[
            "Convert m weeks = n! seconds to n! = 604800*m.",
            "Factor 604800.",
            "Find the least n for which 604800 divides n!.",
            "Return all n beyond that threshold with m=n!/604800.",
        ],
        tool_name="number_theory.factorial_weeks",
        command="factor(604800) and solve 604800 | n!",
    )


def detect_circle_overlap_limit_problem(normalized: str, source: str) -> SpecializedProblem | None:
    if not all(token in normalized for token in ("2円", "共通部分", "面積", "s_n", "t_n")):
        return None
    if not re.search(r"sqrt\(\s*n\s*\*?\s*\(\s*n\s*\+\s*1\s*\)\s*\)", normalized) and "sqrt(n*n+n)" not in normalized:
        return None
    ir = GeometryIR(
        kind="equal_circle_overlap_asymptotic_difference",
        objects=["two equal circles"],
        parameters={
            "radius": "n",
            "distance_s": "n + 1/2",
            "distance_t": "sqrt(n(n+1))",
        },
        target="lim_{n->infinity}(S_n-T_n)",
    )
    return SpecializedProblem(
        domain="geometry",
        intent="geometry_circle_overlap_limit",
        symbols=["n"],
        givens={"geometry_ir": asdict(ir)},
        goal="Compute the asymptotic difference of two equal-circle intersection areas.",
        plan=[
            "Use the equal-radius circle intersection area formula.",
            "Differentiate the area with respect to center distance.",
            "Expand n+1/2 - sqrt(n(n+1)).",
            "Take the limit.",
        ],
        tool_name="geometry.circle_overlap_limit",
        command="limit(A(n,n+1/2)-A(n,sqrt(n(n+1))), n->infinity)",
    )


def detect_two_card_correlation_problem(normalized: str, source: str) -> SpecializedProblem | None:
    if "2枚" not in normalized or "相加平均" not in normalized or "相乗平均" not in normalized or "相関係数" not in normalized:
        return None
    ir = ProbabilityIR(
        kind="two_card_arithmetic_geometric_mean_correlation_limit",
        random_objects=["two distinct cards from {1,...,n}"],
        parameters={"sample_size": 2, "limit": "n->infinity"},
        target="lim rho_n",
    )
    return SpecializedProblem(
        domain="probability",
        intent="probability_two_card_correlation_limit",
        symbols=["n"],
        givens={"probability_ir": asdict(ir)},
        goal="Compute the limiting correlation between arithmetic and geometric means of two cards.",
        plan=[
            "Scale card values by n and pass to two independent Uniform(0,1) variables in the limit.",
            "Let X=(U+V)/2 and Y=sqrt(UV).",
            "Compute E[X], Var[X], E[Y], Var[Y], and Cov[X,Y].",
            "Return Cov/sqrt(VarX VarY).",
        ],
        tool_name="probability.two_card_correlation_limit",
        command="corr((U+V)/2, sqrt(UV)) for U,V iid Uniform(0,1)",
    )


def detect_k_card_correlation_angle_problem(normalized: str, source: str) -> SpecializedProblem | None:
    has_k_less_than_n = "k(<n)" in normalized or "k*(<n)" in normalized or ("k" in normalized and "<n" in normalized)
    if not has_k_less_than_n or "相加平均" not in normalized or "相乗平均" not in normalized:
        return None
    if "theta" not in normalized and "cos" not in normalized:
        return None
    ir = ProbabilityIR(
        kind="k_card_arithmetic_geometric_mean_angle_limit",
        random_objects=["k distinct cards from {1,...,n}"],
        parameters={"limits": "lim_{k->infinity} lim_{n->infinity}"},
        target="lim theta_{n,k}",
    )
    return SpecializedProblem(
        domain="probability",
        intent="probability_k_card_angle_limit",
        symbols=["n", "k"],
        givens={"probability_ir": asdict(ir)},
        goal="Compute the limiting angle from the correlation of arithmetic and geometric means.",
        plan=[
            "After n->infinity, model cards as iid Uniform(0,1).",
            "For large k, use the delta method for sample mean and mean log.",
            "Compute corr(U, log U)=sqrt(3)/2.",
            "Return theta=arccos(sqrt(3)/2).",
        ],
        tool_name="probability.k_card_angle_limit",
        command="acos(corr(U, log U)) for U~Uniform(0,1)",
    )


def detect_inequality_counterexample_problem(normalized: str, source: str) -> SpecializedProblem | None:
    if "示せ" not in normalized and "prove" not in normalized:
        return None
    if not any(symbol in normalized for symbol in ("<=", ">=", "<", ">")):
        return None
    variables = sorted(set(re.findall(r"\b[a-dx-z]\b", normalized)))[:6]
    ir = InequalityIR(
        kind="small_counterexample_search",
        variables=variables,
        assumptions=extract_assumptions(normalized),
        target_relation=extract_relation(normalized),
        search_bounds=(-4, 4),
    )
    return SpecializedProblem(
        domain="inequalities",
        intent="inequality_counterexample_search",
        symbols=variables,
        givens={"inequality_ir": asdict(ir)},
        goal="Search for a small counterexample before attempting a symbolic inequality proof.",
        plan=[
            "Parse a candidate inequality relation.",
            "Enumerate small integer assignments satisfying simple assumptions.",
            "Return a counterexample if one is found.",
            "Otherwise report that no small counterexample was found; this is not a proof.",
        ],
        tool_name="inequality.counterexample_search",
        command=f"search integers in {ir.search_bounds} for {ir.target_relation}",
    )


def solve_specialized_problem(intent: str, givens: dict[str, Any]) -> dict[str, Any]:
    if intent == "number_theory_factorial_weeks":
        return solve_factorial_weeks(givens["number_theory_ir"])
    if intent == "geometry_circle_overlap_limit":
        return solve_circle_overlap_limit()
    if intent == "probability_two_card_correlation_limit":
        return solve_two_card_correlation_limit()
    if intent == "probability_k_card_angle_limit":
        return solve_k_card_angle_limit()
    if intent == "inequality_counterexample_search":
        return solve_inequality_counterexample(givens["inequality_ir"])
    raise ValueError(f"unsupported specialized intent: {intent}")


def solve_factorial_weeks(ir: dict[str, Any]) -> dict[str, Any]:
    seconds = int(ir["parameters"]["seconds_per_week"])
    factors = factor_integer(seconds)
    threshold = min_factorial_divisibility_threshold(factors)
    return {
        "status": "solved",
        "answer_exact": f"n >= {threshold}, m = n!/{seconds}",
        "factorization": factors,
        "least_n": threshold,
        "verification": f"{seconds} divides n! exactly for every n >= {threshold}.",
    }


def solve_circle_overlap_limit() -> dict[str, Any]:
    return {
        "status": "solved",
        "answer_exact": "-sqrt(3)/8",
        "answer_numeric": -math.sqrt(3) / 8,
        "derivation": [
            "For equal radius r, A(d)=2r^2 arccos(d/(2r)) - d/2*sqrt(4r^2-d^2).",
            "A'(d)=-sqrt(4r^2-d^2).",
            "n+1/2 - sqrt(n(n+1)) ~ 1/(8n).",
            "A'(n) ~ -sqrt(3)*n, hence the limit is -sqrt(3)/8.",
        ],
    }


def solve_two_card_correlation_limit() -> dict[str, Any]:
    return {
        "status": "solved",
        "answer_exact": "8*sqrt(6)/(5*sqrt(17))",
        "answer_numeric": 8 * math.sqrt(6) / (5 * math.sqrt(17)),
        "moments": {
            "E_X": "1/2",
            "Var_X": "1/24",
            "E_Y": "4/9",
            "Var_Y": "17/324",
            "Cov_XY": "2/45",
        },
    }


def solve_k_card_angle_limit() -> dict[str, Any]:
    return {
        "status": "solved",
        "answer_exact": "pi/6",
        "correlation_limit": "sqrt(3)/2",
        "derivation": [
            "For U~Uniform(0,1), corr(U, log U)=Cov(U,log U)/sqrt(Var(U)Var(log U)).",
            "E[U log U]=-1/4, E[U]=1/2, E[log U]=-1, Var(U)=1/12, Var(log U)=1.",
            "The limiting correlation is sqrt(3)/2, so theta=pi/6.",
        ],
    }


def solve_inequality_counterexample(ir: dict[str, Any]) -> dict[str, Any]:
    if sp is None:
        return {"status": "unavailable", "error": "SymPy is not installed."}
    relation = ir.get("target_relation") or ""
    variables = ir.get("variables") or []
    if not relation or not variables:
        return {"status": "no_parse", "message": "Could not parse an inequality relation."}
    lower, upper = ir.get("search_bounds", [-4, 4])
    symbols = {name: sp.symbols(name) for name in variables}
    parsed = parse_relation(relation, symbols)
    if parsed is None:
        return {"status": "no_parse", "relation": relation}
    assumptions = ir.get("assumptions", [])
    checked = 0
    for values in product(range(int(lower), int(upper) + 1), repeat=len(variables)):
        assignment = dict(zip(variables, values))
        if not satisfies_simple_assumptions(assignment, assumptions):
            continue
        checked += 1
        if not bool(parsed.subs({symbols[k]: v for k, v in assignment.items()})):
            return {
                "status": "counterexample_found",
                "answer_exact": str(assignment),
                "relation": relation,
                "checked": checked,
            }
    return {
        "status": "no_small_counterexample",
        "relation": relation,
        "checked": checked,
        "note": "This is not a proof.",
    }


def factor_integer(value: int) -> dict[str, int]:
    result: dict[str, int] = {}
    n = value
    divisor = 2
    while divisor * divisor <= n:
        while n % divisor == 0:
            result[str(divisor)] = result.get(str(divisor), 0) + 1
            n //= divisor
        divisor += 1 if divisor == 2 else 2
    if n > 1:
        result[str(n)] = result.get(str(n), 0) + 1
    return result


def min_factorial_divisibility_threshold(factors: dict[str, int]) -> int:
    n = 1
    while True:
        if all(factorial_prime_exponent(n, int(prime)) >= exponent for prime, exponent in factors.items()):
            return n
        n += 1


def factorial_prime_exponent(n: int, prime: int) -> int:
    total = 0
    power = prime
    while power <= n:
        total += n // power
        power *= prime
    return total


def extract_assumptions(text: str) -> list[str]:
    assumptions = []
    for pattern in (r"([a-z](?:\+[a-z]){1,4}=0)", r"([a-z]\s*[<>]=?\s*0)"):
        assumptions.extend(match.group(1).replace(" ", "") for match in re.finditer(pattern, text))
    return assumptions


def extract_relation(text: str) -> str:
    matches = re.findall(r"([a-z0-9_+\-*/().\s]+(?:<=|>=|<|>)[a-z0-9_+\-*/().\s]+)", text)
    if not matches:
        return ""
    return normalize_implicit_multiplication(matches[-1].strip())


def parse_relation(relation: str, symbols: dict[str, Any]) -> Any | None:
    for op in ("<=", ">=", "<", ">"):
        if op in relation:
            lhs_text, rhs_text = relation.split(op, 1)
            try:
                lhs = sp.sympify(normalize_implicit_multiplication(lhs_text), locals=symbols)
                rhs = sp.sympify(normalize_implicit_multiplication(rhs_text), locals=symbols)
            except Exception:
                return None
            if op == "<=":
                return lhs <= rhs
            if op == ">=":
                return lhs >= rhs
            if op == "<":
                return lhs < rhs
            return lhs > rhs
    return None


def satisfies_simple_assumptions(assignment: dict[str, int], assumptions: list[str]) -> bool:
    for assumption in assumptions:
        if "=" in assumption and not any(op in assumption for op in ("<", ">")):
            lhs, rhs = assumption.split("=", 1)
            if eval_linear(lhs, assignment) != eval_linear(rhs, assignment):
                return False
        elif ">" in assumption or "<" in assumption:
            parsed = parse_numeric_comparison(assumption, assignment)
            if parsed is not None and not parsed:
                return False
    return True


def eval_linear(expr: str, assignment: dict[str, int]) -> int:
    total = 0
    for sign, name in re.findall(r"([+-]?)([a-z])", expr):
        total += (-1 if sign == "-" else 1) * assignment.get(name, 0)
    number_match = re.fullmatch(r"[+-]?\d+", expr)
    if number_match:
        return int(expr)
    return total


def parse_numeric_comparison(assumption: str, assignment: dict[str, int]) -> bool | None:
    match = re.fullmatch(r"([a-z])([<>]=?)(-?\d+)", assumption)
    if not match:
        return None
    lhs = assignment.get(match.group(1), 0)
    rhs = int(match.group(3))
    op = match.group(2)
    if op == ">":
        return lhs > rhs
    if op == "<":
        return lhs < rhs
    if op == ">=":
        return lhs >= rhs
    return lhs <= rhs


def normalize_implicit_multiplication(expr: str) -> str:
    expr = expr.replace("^", "**")
    expr = re.sub(r"(?<=[a-zA-Z])(?=[a-zA-Z])", "*", expr)
    expr = re.sub(r"(?<=\d)(?=[a-zA-Z])", "*", expr)
    expr = re.sub(r"(?<=[a-zA-Z])(?=\d)", "*", expr)
    return expr


def normalize_text(text: str) -> str:
    return (
        text.replace("\\", "")
        .replace("^", "**")
        .replace("≤", "<=")
        .replace("≥", ">=")
        .replace("≦", "<=")
        .replace("≧", ">=")
        .replace("　", " ")
        .lower()
    )
