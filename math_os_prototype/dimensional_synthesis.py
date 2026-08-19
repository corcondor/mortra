"""Dimension-checked arithmetic program synthesis.

This module does not dispatch on benchmark ids or remembered problem families.
It lifts numeric phrases to typed quantities, enumerates small arithmetic terms,
and accepts a term only when its output dimension matches the question and the
surface relations determine a unique best value.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction

try:
    from math_os_prototype.quantity_reasoner import NUMBER_RE, parse_number
except ImportError:
    from quantity_reasoner import NUMBER_RE, parse_number


Dim = tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class TypedQuantity:
    value: Fraction
    dimension: Dim
    surface: str
    start: int


@dataclass(frozen=True)
class Term:
    value: Fraction
    dimension: Dim
    expression: str
    operators: tuple[str, ...]
    complexity: int


@dataclass(frozen=True)
class DimensionalSynthesisResult:
    answer_exact: str
    expression: str
    target_dimension: str
    certificate: tuple[str, ...]


STOP_WORDS = {
    "a", "an", "the", "his", "her", "their", "its", "of", "new", "old",
    "regular", "diet", "fresh", "more", "less", "total", "equal", "only",
}
TIME_UNITS = {"second", "minute", "hour", "day", "week", "month", "year", "morning"}
PERSON_WORDS = {"adult", "boy", "child", "friend", "girl", "kid", "people", "person", "student"}
QUERY_STOP = {
    "did", "do", "does", "had", "has", "have", "he", "her", "him", "is", "it",
    "she", "they", "will", "would", "you", "now", "there", "altogether", "total",
    "are", "was", "were", "riding", "before", "after",
}


def normalize_word(word: str) -> str:
    word = word.lower().strip(".,;:!?()[]{}")
    if word == "shelves":
        return "shelf"
    if word == "people":
        return "person"
    if word == "children":
        return "child"
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith("es") and len(word) > 4 and word[-3] in "sxz":
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss") and len(word) > 3:
        return word[:-1]
    return word


def canonical_unit(word: str) -> str:
    word = normalize_word(word)
    if word in PERSON_WORDS:
        return "person"
    if word == "morning":
        return "day"
    return word


def dim(**powers: int) -> Dim:
    return tuple(sorted((name, exponent) for name, exponent in powers.items() if exponent))


def combine_dim(left: Dim, right: Dim, sign: int) -> Dim:
    powers = dict(left)
    for name, exponent in right:
        powers[name] = powers.get(name, 0) + sign * exponent
        if powers[name] == 0:
            del powers[name]
    return tuple(sorted(powers.items()))


def format_dim(value: Dim) -> str:
    if not value:
        return "Scalar"
    return "*".join(name if exponent == 1 else f"{name}^{exponent}" for name, exponent in value)


def format_fraction(value: Fraction) -> str:
    return str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"


def _local_object(text: str, end: int) -> tuple[str | None, str | None]:
    tail = re.split(r"[.?!]", text[end : end + 100], maxsplit=1)[0]
    denominator_match = re.search(r"\b(?:per|every|for each|on each|in each)\s+(?:an?\s+|the\s+)?([a-z-]+)", tail)
    denominator = canonical_unit(denominator_match.group(1)) if denominator_match else None
    local = re.split(
        r"\b(?:per|every|for each|on each|in each|each|than|that|which|who|and|while|if|when|then|but|after|before|to|from|at|in|on|for|with|by|got|came|joined|left|went|were|was|are|is)\b",
        tail,
        maxsplit=1,
    )[0]
    words = [normalize_word(word) for word in re.findall(r"[a-z]+(?:-[a-z]+)?", local)]
    words = [word for word in words if word not in STOP_WORDS]
    if not words:
        return None, denominator
    # A counted phrase normally has its head at the end.  In "3 egg omelet",
    # the first noun is the measured ingredient and is also the query object.
    if len(words) == 2 and words[-1] in {"omelet", "packet", "package", "box", "bag"}:
        return canonical_unit(words[0]), denominator
    return canonical_unit(words[-1]), denominator


def extract_typed_quantities(text: str) -> list[TypedQuantity]:
    normalized = text.lower()
    result: list[TypedQuantity] = []
    previous_object: str | None = None
    for match in re.finditer(rf"(?P<number>{NUMBER_RE})", normalized):
        surface = match.group("number")
        value = parse_number(surface)
        if value is None:
            continue
        obj, denominator = _local_object(normalized, match.end())
        before = normalized[max(0, match.start() - 50) : match.start()]
        if denominator is None:
            before_clause = re.split(r"[.?!]", before)[-1]
            each_before = re.search(r"\b(?:each|every|per)\s+([a-z-]+).{0,35}$", before_clause)
            if each_before:
                denominator = canonical_unit(each_before.group(1))
        if surface.startswith("$"):
            obj = "dollar"
        if denominator is None and re.match(r"\s*each\b", normalized[match.end() : match.end() + 20]) and previous_object:
            denominator = previous_object
        if obj is None and denominator and previous_object:
            obj = previous_object
        if obj is None and previous_object:
            local_before = normalized[max(0, match.start() - 20) : match.start()]
            if re.search(r"(?:\band\b|,)\s*$", local_before):
                obj = previous_object
        if obj is None:
            continue
        obj = canonical_unit(obj)
        powers = {obj: 1}
        if denominator:
            powers[denominator] = powers.get(denominator, 0) - 1
        quantity = TypedQuantity(value, dim(**powers), surface, match.start())
        if re.search(r"\bthe\s+$", before) and any(
            previous.value == quantity.value and previous.dimension == quantity.dimension for previous in result
        ):
            continue
        result.append(quantity)
        if obj not in TIME_UNITS:
            previous_object = obj
    return result


def infer_target_dimension(text: str, quantities: list[TypedQuantity]) -> Dim | None:
    normalized = text.lower()
    questions = re.split(r"(?<=[.?!])\s+", normalized)
    question = next((part for part in reversed(questions) if "how " in part or "what " in part), questions[-1])
    each_match = re.search(r"\b(?:how many|how much)\s+(?:does|do|did|would|will)?\s*(?:each|per)\s+([a-z-]+)", question)
    if each_match:
        denominator = canonical_unit(each_match.group(1))
        numerators = [name for quantity in quantities for name, exponent in quantity.dimension if exponent > 0 and name != denominator]
        if numerators:
            powers = {numerators[-1]: 1, denominator: -1}
            period = re.search(r"\bper\s+(second|minute|hour|day|week|month|year)\b", question)
            if period:
                period_name = canonical_unit(period.group(1))
                powers[period_name] = powers.get(period_name, 0) - 1
            return dim(**powers)
    direct = re.search(r"\b(?:how many|how much)\s+([a-z-]+(?:\s+[a-z-]+){0,2})", question)
    if direct:
        words = [canonical_unit(word) for word in re.findall(r"[a-z-]+", direct.group(1))]
        words = [word for word in words if word not in QUERY_STOP]
        if words:
            target = words[0]
            if target in {"dozen", "dozens"}:
                return dim(dozen=1)
            if target in {"percentage", "percent"}:
                return dim(percent=1)
            return dim(**{target: 1})
    if "salary" in question or "cost" in question or "paid" in question or "money" in question:
        return dim(dollar=1)
    if "distance" in question:
        for quantity in quantities:
            for name, exponent in quantity.dimension:
                if exponent > 0 and name in {"mile", "meter", "foot", "inch", "centimeter", "kilometer"}:
                    return dim(**{name: 1})
    return None


def _operator_preferences(text: str) -> dict[str, int]:
    source = text.lower()
    score = {"+": 0, "-": 0, "*": 0, "/": 0}
    if re.search(r"\b(total|altogether|combined|in all|sum)\b", source) or " and " in source:
        score["+"] += 3
    if re.search(r"\b(left|remaining|rest|shorter|difference|fewer|less|away)\b|more than", source):
        score["-"] += 4
    if re.search(r"\b(per|every|each|times|rate)\b", source):
        score["*"] += 2
    if re.search(r"\b(equally|among|split|divide|divided|groups?|shelves|each .* get|how long|last)\b", source):
        score["/"] += 4
    return score


def _enumerate_terms(quantities: list[TypedQuantity], *, cap_per_dimension: int = 8) -> list[Term]:
    count = len(quantities)
    table: dict[int, dict[Dim, list[Term]]] = {}
    for index, quantity in enumerate(quantities):
        table[1 << index] = {
            quantity.dimension: [Term(quantity.value, quantity.dimension, format_fraction(quantity.value), (), 0)]
        }
    for size in range(2, count + 1):
        for mask in range(1, 1 << count):
            if mask.bit_count() != size:
                continue
            by_dimension: dict[Dim, list[Term]] = {}
            submask = (mask - 1) & mask
            while submask:
                other = mask ^ submask
                if other and submask < other and submask in table and other in table:
                    for left_terms in table[submask].values():
                        for right_terms in table[other].values():
                            for left in left_terms:
                                for right in right_terms:
                                    candidates: list[Term] = []
                                    if left.dimension == right.dimension:
                                        candidates.extend(
                                            [
                                                Term(left.value + right.value, left.dimension, f"({left.expression}+{right.expression})", left.operators + right.operators + ("+",), left.complexity + right.complexity + 1),
                                                Term(left.value - right.value, left.dimension, f"({left.expression}-{right.expression})", left.operators + right.operators + ("-",), left.complexity + right.complexity + 1),
                                                Term(right.value - left.value, left.dimension, f"({right.expression}-{left.expression})", left.operators + right.operators + ("-",), left.complexity + right.complexity + 1),
                                            ]
                                        )
                                    product_dim = combine_dim(left.dimension, right.dimension, 1)
                                    candidates.append(Term(left.value * right.value, product_dim, f"({left.expression}*{right.expression})", left.operators + right.operators + ("*",), left.complexity + right.complexity + 1))
                                    if right.value:
                                        quotient_dim = combine_dim(left.dimension, right.dimension, -1)
                                        candidates.append(Term(left.value / right.value, quotient_dim, f"({left.expression}/{right.expression})", left.operators + right.operators + ("/",), left.complexity + right.complexity + 1))
                                    if left.value:
                                        quotient_dim = combine_dim(right.dimension, left.dimension, -1)
                                        candidates.append(Term(right.value / left.value, quotient_dim, f"({right.expression}/{left.expression})", left.operators + right.operators + ("/",), left.complexity + right.complexity + 1))
                                    for candidate in candidates:
                                        bucket = by_dimension.setdefault(candidate.dimension, [])
                                        key = (candidate.value, tuple(sorted(candidate.operators)), candidate.expression)
                                        if not any((item.value, tuple(sorted(item.operators)), item.expression) == key for item in bucket):
                                            bucket.append(candidate)
                                            bucket.sort(key=lambda item: (item.complexity, len(item.expression)))
                                            del bucket[cap_per_dimension:]
                submask = (submask - 1) & mask
            if by_dimension:
                table[mask] = by_dimension
    full = table.get((1 << count) - 1, {})
    return [term for terms in full.values() for term in terms]


def solve_dimensional_arithmetic(text: str) -> DimensionalSynthesisResult | None:
    # TeX commands are parsed by the MathJSON/TeX AST path.  Treating command
    # arguments as plain decimal tokens would silently corrupt fractions.
    if "\\" in text:
        return None
    quantities = extract_typed_quantities(text)
    numeric_matches = [
        match
        for match in re.finditer(NUMBER_RE, text.lower())
        if parse_number(match.group(0)) is not None
    ]
    quantity_starts = {quantity.start for quantity in quantities}
    quantity_values = {quantity.value for quantity in quantities}
    question_start = max(text.rfind("."), text.rfind("?", 0, max(0, len(text) - 1)), text.rfind("!")) + 1
    # A dimensional program is complete only if every numeric premise became a
    # typed leaf.  Otherwise a unique value can still be obtained by silently
    # dropping an event, which is not a proof of the story problem.
    for match in numeric_matches:
        if match.start() in quantity_starts:
            continue
        value = parse_number(match.group(0))
        if match.start() >= question_start and value in quantity_values:
            continue
        return None
    # Four leaves already cover 15 binary tree shapes with typed operators.
    # Larger stories must first be decomposed into event constraints; blindly
    # enumerating all arithmetic trees would be exponential and is rejected.
    if not 2 <= len(quantities) <= 4:
        return None
    target = infer_target_dimension(text, quantities)
    if target is None:
        return None
    terms = [term for term in _enumerate_terms(quantities) if term.dimension == target and term.value >= 0]
    # Dimensions determine multiplication and division, but cannot distinguish
    # addition from subtraction between equal-typed quantities.  Those cases
    # require an explicit State/Event relation graph and are not executed here.
    terms = [term for term in terms if not ({"+", "-"} & set(term.operators))]
    if not terms:
        return None
    preferences = _operator_preferences(text)

    def rank(term: Term) -> tuple[int, int, int]:
        present = set(term.operators)
        semantic = sum(weight for operator, weight in preferences.items() if operator in present)
        unsupported = sum(1 for operator in present if preferences[operator] == 0)
        return semantic - unsupported, -term.complexity, -len(term.expression)

    terms.sort(key=rank, reverse=True)
    best_rank = rank(terms[0])
    best = [term for term in terms if rank(term) == best_rank]
    values = {term.value for term in terms}
    if len(values) != 1:
        return None
    selected = min(best, key=lambda term: (len(term.expression), term.expression))
    return DimensionalSynthesisResult(
        answer_exact=format_fraction(selected.value),
        expression=selected.expression,
        target_dimension=format_dim(target),
        certificate=(
            "all numeric premises were used exactly once",
            f"output dimension type-checks as {format_dim(target)}",
            "the highest-ranked dimension-correct program has a unique value",
        ),
    )
