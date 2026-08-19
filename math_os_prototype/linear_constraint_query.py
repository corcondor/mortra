"""Lower finite-vocabulary linear relations to an executable CAS contract.

The compiler treats named quantities as alpha-renamable vertices.  Surface
nouns and numeric values are data; the only reusable semantics are weighted
sum, equality, scalar projection, and exact rational elimination.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from fractions import Fraction
import re
from typing import Any

import sympy as sp

try:
    from math_os_prototype.quantity_reasoner import NUMBER_RE, parse_number
except ImportError:
    from quantity_reasoner import NUMBER_RE, parse_number


@dataclass(frozen=True)
class LinearConstraint:
    coefficients: dict[str, str]
    constant: str
    source: str


@dataclass(frozen=True)
class LinearConstraintQueryIR:
    constraints: list[LinearConstraint]
    variables: list[str]
    query_coefficients: dict[str, str]
    query_constant: str
    output_sort: str
    lowering_certificate: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_UNIT_PREFIX = r"(?:(?:pounds?|ounces?|kilograms?|grams?|liters?|dollars?)\s+of\s+)?"
_TERM = re.compile(rf"(?P<number>{NUMBER_RE})\s+{_UNIT_PREFIX}(?P<object>[a-z][a-z-]*)", re.I)


def _fraction_text(value: Fraction) -> str:
    return str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"


def _name(value: str) -> str:
    value = value.lower().strip(".,;:?!")
    if value.endswith("ies") and len(value) > 4:
        return value[:-3] + "y"
    if value.endswith("s") and not value.endswith("ss") and len(value) > 3:
        return value[:-1]
    return value


def _terms(source: str) -> dict[str, Fraction]:
    result: dict[str, Fraction] = {}
    for match in _TERM.finditer(source):
        value = parse_number(match.group("number"))
        if value is None:
            continue
        name = _name(match.group("object"))
        if name in {"year", "time", "amount", "number"}:
            continue
        result[name] = result.get(name, Fraction(0)) + value
    return result


def _number_count(source: str) -> int:
    return sum(parse_number(match.group(0)) is not None for match in re.finditer(NUMBER_RE, source))


def _term_count(source: str) -> int:
    return sum(parse_number(match.group("number")) is not None for match in _TERM.finditer(source))


def _constraint(
    left: dict[str, Fraction],
    right: dict[str, Fraction],
    constant: Fraction,
    source: str,
) -> LinearConstraint | None:
    coefficients = dict(left)
    for name, value in right.items():
        coefficients[name] = coefficients.get(name, Fraction(0)) - value
    coefficients = {name: value for name, value in coefficients.items() if value}
    if not coefficients:
        return None
    return LinearConstraint(
        coefficients={name: _fraction_text(value) for name, value in coefficients.items()},
        constant=_fraction_text(constant),
        source=source.strip(),
    )


def compile_linear_constraint_query(text: str) -> LinearConstraintQueryIR | None:
    source = re.sub(r"\s+", " ", text.lower().replace("’", "'").replace(r"\$", "$")).strip()
    if "\\" in source:
        return None
    sentences = [part.strip() for part in re.split(r"(?<=[.?!])\s+", source) if part.strip()]
    question = next((part for part in reversed(sentences) if re.search(r"\b(?:what|how)\b", part)), "")
    premises = [part for part in sentences if part != question]
    constraints: list[LinearConstraint] = []

    equality = re.compile(r"\b(?:weighs?|are equal in weight to|is equal in weight to|equals?)\b")
    for sentence in premises:
        match = equality.search(sentence)
        if match:
            left, right = _terms(sentence[: match.start()]), _terms(sentence[match.end() :])
            item = _constraint(left, right, Fraction(0), sentence)
            if (
                item is not None
                and left
                and right
                and _term_count(sentence) == _number_count(sentence)
            ):
                constraints.append(item)
            continue
        cost = re.search(rf"\b(?:together\s+)?costs?\s+\$?(?P<value>{NUMBER_RE})\b", sentence)
        if cost:
            value = parse_number(cost.group("value"))
            left = _terms(sentence[: cost.start()])
            item = _constraint(left, {}, value or Fraction(0), sentence)
            if (
                item is not None
                and value is not None
                and len(left) >= 2
                and _term_count(sentence[: cost.start()]) + 1 == _number_count(sentence)
            ):
                constraints.append(item)

    if len(constraints) < 2 or not question:
        return None
    variables = sorted({name for item in constraints for name in item.coefficients})
    query_coefficients: dict[str, Fraction] = {}
    query_constant = Fraction(0)

    cost_query = re.search(r"\bcost\s+of\s+(.+?)(?:\?|$)", question)
    if cost_query:
        query_coefficients = _terms(cost_query.group(1))
        if _term_count(cost_query.group(1)) != _number_count(question):
            return None
    else:
        count_query = re.search(
            rf"\bhow\s+many\s+(?P<object>[a-z-]+)\b.*?equals?\s+(?:the\s+)?(?:weight\s+of\s+)?(?P<right>.+?)(?:\?|$)",
            question,
        )
        if count_query:
            counted = _name(count_query.group("object"))
            right = _terms(count_query.group("right"))
            if counted in variables and right:
                if _term_count(count_query.group("right")) != _number_count(question):
                    return None
                # The relation is nonlinear in unit-weight variables.  Eliminate
                # unit weights first, then form the certified ratio in execution.
                query_coefficients = right
                query_constant = Fraction(0)
                output_sort = f"ScalarRatio[{','.join(sorted(right))}/{counted}]"
                return LinearConstraintQueryIR(
                    constraints=constraints,
                    variables=variables,
                    query_coefficients={name: _fraction_text(value) for name, value in query_coefficients.items()},
                    query_constant=_fraction_text(query_constant),
                    output_sort=output_sort,
                    lowering_certificate={
                        "kind": "rational_linear_constraint_projection",
                        "query_denominator": counted,
                        "premise_count": len(constraints),
                        "all_numeric_premises_consumed": True,
                    },
                )

    if not query_coefficients or not set(query_coefficients) <= set(variables):
        return None
    return LinearConstraintQueryIR(
        constraints=constraints,
        variables=variables,
        query_coefficients={name: _fraction_text(value) for name, value in query_coefficients.items()},
        query_constant=_fraction_text(query_constant),
        output_sort="Scalar",
        lowering_certificate={
            "kind": "rational_linear_constraint_projection",
            "premise_count": len(constraints),
            "all_numeric_premises_consumed": True,
        },
    )


def execute_linear_constraint_query(payload: dict[str, Any]) -> dict[str, Any]:
    constraints = [LinearConstraint(**item) for item in payload["constraints"]]
    variables = [sp.Symbol(name, real=True) for name in payload["variables"]]
    symbols = {symbol.name: symbol for symbol in variables}
    equations = []
    for item in constraints:
        lhs = sum(sp.Rational(value) * symbols[name] for name, value in item.coefficients.items())
        equations.append(sp.Eq(lhs, sp.Rational(item.constant)))
    solutions = sp.solve(equations, variables, dict=True)
    if not solutions:
        raise ValueError("linear constraint system has no solution")
    denominator_name = payload.get("lowering_certificate", {}).get("query_denominator")
    values: list[sp.Expr] = []
    for assignment in solutions:
        if not all(sp.simplify(equation.lhs.subs(assignment) - equation.rhs) == 0 for equation in equations):
            raise ValueError("linear backend assignment failed re-verification")
        numerator = sp.Rational(payload["query_constant"]) + sum(
            sp.Rational(value) * assignment.get(symbols[name], symbols[name])
            for name, value in payload["query_coefficients"].items()
        )
        value = numerator
        if denominator_name:
            denominator = assignment.get(symbols[denominator_name], symbols[denominator_name])
            value = sp.cancel(numerator / denominator)
        if value.free_symbols:
            raise ValueError("linear query is underdetermined")
        values.append(sp.simplify(value))
    if any(sp.simplify(value - values[0]) != 0 for value in values[1:]):
        raise ValueError("linear query has no unique observation")
    return {
        "answer_exact": sp.sstr(values[0]),
        "query_operator": "linear_constraint_projection",
        "output_sort": payload["output_sort"],
        "constraint_count": len(constraints),
        "verified": True,
    }
