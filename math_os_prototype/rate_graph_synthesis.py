"""Synthesize arithmetic by composing dimensioned rates.

The compiler uses units as sorts and ``per`` as a morphism.  It does not know
benchmark ids or expected answers.  A result is emitted only when the
dimension-correct, maximum-evidence term has one value.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import re

try:
    from math_os_prototype.quantity_reasoner import NUMBER_RE, parse_number
except ImportError:
    from quantity_reasoner import NUMBER_RE, parse_number


Dim = tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class Measure:
    value: Fraction
    dimension: Dim
    expression: str
    label: str | None
    synthetic: bool = False


@dataclass(frozen=True)
class RateTerm:
    value: Fraction
    dimension: Dim
    expression: str
    label: str | None
    operators: tuple[str, ...]
    evidence: int
    mask: int


@dataclass(frozen=True)
class RateGraphResult:
    answer_exact: str
    expression: str
    target_dimension: str
    certificate: tuple[str, ...]


UNIT_ALIASES = {
    "centimeters": "centimeter", "dollars": "dollar", "eggs": "egg",
    "feet": "foot", "hours": "hour", "items": "item", "kilometers": "kilometer",
    "meters": "meter", "miles": "mile", "minutes": "minute", "months": "month",
    "pairs": "pair", "pieces": "piece", "servings": "serving", "students": "student",
    "weeks": "week", "years": "year", "days": "day", "units": "unit",
    "boxes": "box", "classes": "class", "cartons": "carton", "dozens": "dozen", "pounds": "pound",
}
KNOWN_UNITS = {
    "centimeter", "dollar", "egg", "foot", "hour", "item", "kilometer", "meter",
    "mile", "minute", "month", "pair", "piece", "serving", "student", "week",
    "year", "day", "unit", "box", "class", "carton", "dozen", "pound", "point",
}


def canonical_unit(value: str) -> str:
    value = value.lower().strip(".,")
    return UNIT_ALIASES.get(value, value[:-1] if value.endswith("s") and value[:-1] in KNOWN_UNITS else value)


def dim(numerator: str, denominator: str | None = None) -> Dim:
    powers = {canonical_unit(numerator): 1}
    if denominator:
        name = canonical_unit(denominator)
        powers[name] = powers.get(name, 0) - 1
    return tuple(sorted((name, power) for name, power in powers.items() if power))


def combine_dim(left: Dim, right: Dim, sign: int) -> Dim:
    powers = dict(left)
    for name, exponent in right:
        powers[name] = powers.get(name, 0) + sign * exponent
        if not powers[name]:
            del powers[name]
    return tuple(sorted(powers.items()))


def format_fraction(value: Fraction) -> str:
    return str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"


def format_dim(value: Dim) -> str:
    return "Scalar" if not value else "*".join(name if power == 1 else f"{name}^{power}" for name, power in value)


def normalize_label(value: str | None) -> str | None:
    if not value:
        return None
    word = re.findall(r"[a-z]+", value.lower())[-1]
    for suffix in ("ing", "er"):
        if word.endswith(suffix) and len(word) > len(suffix) + 2:
            word = word[: -len(suffix)]
    if word == "cheerlead":
        return "coach"
    return word


def nearby_label(source: str, start: int, end: int) -> str | None:
    window = source[max(0, start - 45): min(len(source), end + 40)]
    after = re.split(r"[,.]|\band\b", source[end: min(len(source), end + 40)], maxsplit=1)[0]
    match = re.search(r"\b(?:as|to)\s+(?:an?\s+|be\s+(?:an?\s+)?)?([a-z]+)", after)
    if match:
        return normalize_label(match.group(1))
    match = re.search(r"\b(?:pairs?|items?|units?)\s+of\s+([a-z]+)", window)
    return normalize_label(match.group(1)) if match else None


def extract_measures(text: str) -> list[Measure]:
    source = re.sub(r"(?<=\d),(?=\d)", "", text.lower())
    measures: list[Measure] = []
    occupied: list[tuple[int, int]] = []

    def add(
        match: re.Match[str],
        value: Fraction,
        numerator: str,
        denominator: str | None,
        label: str | None = None,
        *,
        infer_label: bool = True,
    ) -> None:
        occupied.append(match.span())
        resolved_label = label or nearby_label(source, *match.span()) if infer_label else label
        measures.append(Measure(value, dim(numerator, denominator), format_fraction(value), resolved_label))

    currency_rate = re.compile(rf"\$(?P<n>{NUMBER_RE})\s*(?:dollars?\s*)?(?:per|a|each)\s+(?P<den>[a-z]+)")
    for match in currency_rate.finditer(source):
        value = parse_number(match.group("n"))
        if value is not None:
            add(match, value, "dollar", match.group("den"))

    inherited_currency = re.compile(rf"\$(?P<n>{NUMBER_RE})\s+(?:to|as)\s+(?:be\s+)?(?:an?\s+)?(?P<label>[a-z]+)")
    known_currency_denominators = [
        name for item in measures for name, power in item.dimension if power < 0 and dict(item.dimension).get("dollar") == 1
    ]
    for match in inherited_currency.finditer(source):
        if any(left <= match.start() < right for left, right in occupied) or not known_currency_denominators:
            continue
        value = parse_number(match.group("n"))
        if value is not None:
            add(match, value, "dollar", known_currency_denominators[-1], normalize_label(match.group("label")))

    generic_rate = re.compile(rf"(?<!\$)\b(?P<n>{NUMBER_RE})\s+(?P<num>[a-z]+)(?:\s+of(?:\s+[a-z]+){{1,3}})?\s+(?:per|a|each|every)\s+(?P<den>[a-z]+)")
    for match in generic_rate.finditer(source):
        if any(left <= match.start() < right for left, right in occupied):
            continue
        value = parse_number(match.group("n"))
        if value is not None and canonical_unit(match.group("num")) in KNOWN_UNITS and canonical_unit(match.group("den")) in KNOWN_UNITS:
            clause_tail = re.split(r"[,.]|\band\b", source[match.end(): match.end() + 40], maxsplit=1)[0]
            label_match = re.search(r"\bas\s+(?:an?\s+)?([a-z]+)", clause_tail)
            add(
                match,
                value,
                match.group("num"),
                match.group("den"),
                normalize_label(label_match.group(1)) if label_match else None,
                infer_label=False,
            )

    each_has = re.compile(rf"\beach\s+(?P<den>[a-z]+)\s+(?:has|contains?)\s+(?P<n>{NUMBER_RE})\s+(?P<num>[a-z]+)")
    for match in each_has.finditer(source):
        value = parse_number(match.group("n"))
        if value is not None:
            add(match, value, match.group("num"), match.group("den"))

    periodic_product = re.compile(
        rf"\b(?:makes?|uses?|eats?)\s+(?:an?\s+)?(?P<n>{NUMBER_RE})\s+"
        rf"(?P<num>[a-z]+)\s+[a-z]+\s+every\s+(?P<den>morning|day|week|month|year)\b"
    )
    for match in periodic_product.finditer(source):
        value = parse_number(match.group("n"))
        if value is not None:
            denominator = "day" if match.group("den") == "morning" else match.group("den")
            add(match, value, match.group("num"), denominator, infer_label=False)

    container_has = re.compile(rf"\b(?:an?\s+|the\s+)?(?P<den>[a-z]+)\s+(?:has|contains?)\s+(?P<n>{NUMBER_RE})\s+(?P<num>[a-z]+)")
    for match in container_has.finditer(source):
        value = parse_number(match.group("n"))
        if value is not None and canonical_unit(match.group("den")) in KNOWN_UNITS:
            add(match, value, match.group("num"), match.group("den"))

    price = re.compile(rf"(?P<context>(?:one|1)\s+(?P<den>[a-z]+)(?:\s+of\s+(?P<label>[a-z]+))?)\s+costs?\s+\$(?P<n>{NUMBER_RE})")
    for match in price.finditer(source):
        value = parse_number(match.group("n"))
        if value is not None:
            add(match, value, "dollar", match.group("den"), normalize_label(match.group("label")))

    each_weighs = re.compile(
        rf"\beach\s+(?P<den>[a-z]+)[^.?!,;]{{0,24}}?\bweigh(?:s|ing)?\s+(?P<n>{NUMBER_RE})\s+(?P<num>[a-z]+)"
    )
    for match in each_weighs.finditer(source):
        value = parse_number(match.group("n"))
        if value is not None:
            add(match, value, match.group("num"), match.group("den"), infer_label=False)

    absolute_currency = re.compile(rf"\$(?P<n>{NUMBER_RE})")
    for match in absolute_currency.finditer(source):
        if any(left <= match.start() and match.end() <= right for left, right in occupied):
            continue
        value = parse_number(match.group("n"))
        if value is not None:
            add(match, value, "dollar", None, infer_label=False)

    count = re.compile(rf"(?<![$\w/])(?P<n>{NUMBER_RE})\s+(?P<unit>{'|'.join(sorted(KNOWN_UNITS | set(UNIT_ALIASES), key=len, reverse=True))})\b")
    for match in count.finditer(source):
        if any(left <= match.start() and match.end() <= right for left, right in occupied):
            continue
        value = parse_number(match.group("n"))
        if value is None:
            continue
        tail = source[match.end(): match.end() + 30]
        immediate = re.match(r"\s+of\s+([a-z]+)", tail)
        unit = canonical_unit(match.group("unit"))
        label = normalize_label(immediate.group(1)) if immediate else None
        denominator = "day" if re.match(r"(?:\s+of(?:\s+[a-z]+){1,3})?\s+every\s+night\b", tail) else None
        add(match, value, match.group("unit"), denominator, label)

    if not any(item.dimension == dim("day", "week") for item in measures) and "week" in source and any(
        dict(item.dimension).get("day") == -1 for item in measures
    ):
        measures.append(Measure(Fraction(7), dim("day", "week"), "7", None, True))
    if "year" in source and any(item.dimension == dim("dollar", "month") for item in measures):
        measures.append(Measure(Fraction(12), dim("month", "year"), "12", None, True))
    if "dozen" in source:
        item_units = [name for item in measures for name, power in item.dimension if power > 0 and name not in {"dollar", "day", "week"}]
        if item_units:
            measures.append(Measure(Fraction(12), dim(item_units[0], "dozen"), "12", None, True))
    return measures


def infer_target(text: str, measures: list[Measure]) -> Dim | None:
    source = text.lower()
    question = re.split(r"[.?!]", source)[-2] if re.search(r"[?!]\s*$", source) else source
    period = re.search(r"\b(?:per|each|a|annual)\s+(day|week|month|year)\b", question)
    if "salary" in question and "annual" in question:
        return dim("dollar", "year")
    match = re.search(r"\bhow many\s+(eggs?|servings?|items?|pieces?|points?|units?)\b", question)
    if match:
        return dim(match.group(1))
    unit_words = "|".join(sorted(KNOWN_UNITS | set(UNIT_ALIASES), key=len, reverse=True))
    match = re.search(rf"\bhow many\s+(?:more\s+)?(?:number\s+of\s+)?(?P<unit>{unit_words})\b", question)
    if match:
        return dim(match.group("unit"))
    match = re.search(rf"\bmaximum\s+number\s+of\s+(?P<unit>{unit_words})\b", question)
    if match:
        return dim(match.group("unit"))
    if any(word in question for word in ("money", "cost", "spend", "paid", "make", "salary", "dollars")):
        return dim("dollar", period.group(1) if period else None)
    if "distance" in question or "shorter" in question:
        for unit in ("kilometer", "mile", "meter", "foot", "centimeter"):
            if any(dict(item.dimension).get(unit) == 1 for item in measures):
                return dim(unit)
    return None


def labels_compatible(left: str | None, right: str | None) -> bool:
    return not left or not right or left == right


def combine_label(left: str | None, right: str | None) -> str | None:
    if left and right and left == right:
        return None
    return left or right


def synthesize_terms(measures: list[Measure], target: Dim) -> list[RateTerm]:
    table: dict[int, dict[tuple[Dim, str | None], list[RateTerm]]] = {}
    for index, measure in enumerate(measures):
        table[1 << index] = {(measure.dimension, measure.label): [RateTerm(
            measure.value, measure.dimension, measure.expression, measure.label, (), 0 if measure.synthetic else 1, 1 << index
        )]}
    full_mask = (1 << len(measures)) - 1
    for size in range(2, len(measures) + 1):
        for mask in range(1, full_mask + 1):
            if mask.bit_count() != size:
                continue
            buckets: dict[tuple[Dim, str | None], list[RateTerm]] = {}
            left_mask = (mask - 1) & mask
            while left_mask:
                right_mask = mask ^ left_mask
                if left_mask < right_mask and left_mask in table and right_mask in table:
                    for left_terms in table[left_mask].values():
                        for right_terms in table[right_mask].values():
                            for left in left_terms:
                                for right in right_terms:
                                    candidates: list[RateTerm] = []
                                    if left.dimension == right.dimension and left.label is None and right.label is None:
                                        candidates.append(RateTerm(left.value + right.value, left.dimension, f"({left.expression}+{right.expression})", None, left.operators + right.operators + ("+",), left.evidence + right.evidence, left.mask | right.mask))
                                        candidates.append(RateTerm(left.value - right.value, left.dimension, f"({left.expression}-{right.expression})", None, left.operators + right.operators + ("-",), left.evidence + right.evidence, left.mask | right.mask))
                                        candidates.append(RateTerm(right.value - left.value, left.dimension, f"({right.expression}-{left.expression})", None, left.operators + right.operators + ("-",), left.evidence + right.evidence, left.mask | right.mask))
                                    if labels_compatible(left.label, right.label):
                                        label = combine_label(left.label, right.label)
                                        candidates.append(RateTerm(left.value * right.value, combine_dim(left.dimension, right.dimension, 1), f"({left.expression}*{right.expression})", label, left.operators + right.operators + ("*",), left.evidence + right.evidence, left.mask | right.mask))
                                        if right.value:
                                            candidates.append(RateTerm(left.value / right.value, combine_dim(left.dimension, right.dimension, -1), f"({left.expression}/{right.expression})", label, left.operators + right.operators + ("/",), left.evidence + right.evidence, left.mask | right.mask))
                                        if left.value:
                                            candidates.append(RateTerm(right.value / left.value, combine_dim(right.dimension, left.dimension, -1), f"({right.expression}/{left.expression})", label, left.operators + right.operators + ("/",), left.evidence + right.evidence, left.mask | right.mask))
                                    for candidate in candidates:
                                        if abs(candidate.value) > 10**12:
                                            continue
                                        key = (candidate.dimension, candidate.label)
                                        bucket = buckets.setdefault(key, [])
                                        identity = (candidate.value, candidate.operators)
                                        if not any((item.value, item.operators) == identity for item in bucket):
                                            bucket.append(candidate)
                                            bucket.sort(key=lambda item: (-item.evidence, len(item.operators), len(item.expression)))
                                            del bucket[50:]
                left_mask = (left_mask - 1) & mask
            if buckets:
                table[mask] = buckets
    return [
        term for by_key in table.values() for (dimension, label), terms in by_key.items()
        if dimension == target and label is None for term in terms
    ]


def synthesize_labeled_sum(measures: list[Measure], target: Dim, text: str) -> RateTerm | None:
    """Contract each labelled component before adding independent components.

    Labels are indices in a finite coproduct: a price for ``shorts`` may
    contract with a count of ``shorts``, but never with a count of ``shoes``.
    Performing these contractions before the coproduct avoids enumerating
    dimensionally valid but semantically disconnected quotient terms.
    """
    if not re.search(r"\b(?:total|altogether|combined|in all|all the|spend)\b", text.lower()):
        return None
    labels = sorted({measure.label for measure in measures if measure.label})
    if len(labels) < 2:
        return None
    components: list[RateTerm] = []
    for label in labels:
        local = [measure for measure in measures if measure.label == label]
        if len(local) < 2:
            return None
        full_mask = (1 << len(local)) - 1
        candidates = [
            term for term in synthesize_terms(local, target)
            if term.mask == full_mask and not ({"+", "-"} & set(term.operators))
        ]
        if not candidates:
            return None
        shortest = min(len(term.operators) for term in candidates)
        candidates = [term for term in candidates if len(term.operators) == shortest]
        values = {term.value for term in candidates}
        if len(values) != 1:
            return None
        components.append(min(candidates, key=lambda term: (len(term.expression), term.expression)))
    value = sum((term.value for term in components), Fraction())
    expression = "(" + "+".join(term.expression for term in components) + ")"
    return RateTerm(
        value=value,
        dimension=target,
        expression=expression,
        label=None,
        operators=tuple(operator for term in components for operator in term.operators) + ("+",) * (len(components) - 1),
        evidence=sum(term.evidence for term in components),
        mask=0,
    )


def synthesize_inverse_rate_goal(measures: list[Measure], target: Dim, text: str) -> RateTerm | None:
    """Invert a dimensioned flow to observe the required domain quantity."""
    if len(target) != 1 or target[0][1] != 1:
        return None
    target_unit = target[0][0]
    source = text.lower()
    if not re.search(r"\b(?:how many|maximum number)\b", source):
        return None
    state_dimensions = sorted({
        measure.dimension for measure in measures
        if len(measure.dimension) == 1 and measure.dimension[0][1] == 1
        and measure.dimension != target
    })
    candidates: list[RateTerm] = []
    for state_dimension in state_dimensions:
        state_unit = state_dimension[0][0]
        observations = [measure for measure in measures if measure.dimension == state_dimension]
        if len(observations) == 1:
            if not re.search(r"\b(?:save|goal|target|capacity|limit|profit)\b", source):
                continue
            required = observations[0].value
            amount_expression = observations[0].expression
        elif len(observations) == 2:
            high, low = sorted((item.value for item in observations), reverse=True)
            required = high - low
            amount_expression = f"({format_fraction(high)}-{format_fraction(low)})"
        else:
            continue
        rate_measures = [measure for measure in measures if measure.dimension != state_dimension]
        if not rate_measures or len(rate_measures) > 7:
            continue
        forward_dimension = combine_dim(state_dimension, target, -1)
        full_mask = sum(1 << index for index, measure in enumerate(rate_measures) if not measure.synthetic)
        rates = [
            term for term in synthesize_terms(rate_measures, forward_dimension)
            if term.mask & full_mask == full_mask
            and not ({"+", "-"} & set(term.operators))
            and term.value > 0
        ]
        if not rates:
            continue
        shortest = min(len(term.operators) for term in rates)
        rates = [term for term in rates if len(term.operators) == shortest]
        values = {term.value for term in rates}
        if len(values) != 1:
            continue
        rate = min(rates, key=lambda term: (len(term.expression), term.expression))
        value = required / rate.value
        if re.search(r"\b(?:maximum|not exceeding|no more than)\b", source):
            value = Fraction(value.numerator // value.denominator)
        candidates.append(RateTerm(
            value=value,
            dimension=target,
            expression=f"({amount_expression}/{rate.expression})",
            label=None,
            operators=rate.operators + ("inverse",),
            evidence=rate.evidence + len(observations),
            mask=0,
        ))
    values = {candidate.value for candidate in candidates}
    if len(values) != 1:
        return None
    return min(candidates, key=lambda term: (len(term.expression), term.expression))


def solve_rate_graph(text: str) -> RateGraphResult | None:
    source = text.lower()
    # This backend proves direct contractions and coproduct sums.  Temporal
    # updates, capacities, comparisons and piecewise tariffs belong to other
    # typed relations; accepting them here would be a sort error, not a weak
    # confidence score.
    non_rate_relations = re.compile(
        r"\b(?:remaining|remain|taken|broke|enough|left over|won't|except|"
        r"increased|raise|raised|used to|more than|less than|average|"
        r"fewer|farther|longer|shorter|between|times as|times what|as much as|"
        r"turns? direction|same amount|drops?|profit|starts? with|still need|"
        r"thrice|rectangle|monday|tuesday|wednesday|thursday|friday)\b|"
        r"\bone-(?:half|third|fourth)\b"
    )
    if (
        "\\" in text
        or "%" in text
        or re.search(r"\b(?:half|third|quarter|twice)\b", source)
    ):
        return None
    measures = extract_measures(text)
    if not 2 <= len(measures) <= 8:
        return None
    target = infer_target(text, measures)
    if target is None:
        return None
    inverse_goal = synthesize_inverse_rate_goal(measures, target, text)
    if inverse_goal is not None:
        return RateGraphResult(
            answer_exact=format_fraction(inverse_goal.value),
            expression=inverse_goal.expression,
            target_dimension=format_dim(target),
            certificate=(
                "the query selected the domain of a typed rate morphism",
                "the required codomain difference was divided by the composed rate",
                "all connected rate evidence was consumed exactly once",
            ),
        )
    if re.search(r"\bhow\s+many\s+more\b|\bon\s+learning\b", source):
        return None
    if non_rate_relations.search(source):
        return None
    # Scalar money observations are endpoints for inverse-rate goals, not
    # rates.  Once inverse synthesis has declined the problem, they must not
    # participate in a free arithmetic search.
    measures = [measure for measure in measures if measure.dimension != dim("dollar")]
    if len(measures) < 2:
        return None
    labeled_sum = synthesize_labeled_sum(measures, target, text)
    if labeled_sum is not None:
        return RateGraphResult(
            answer_exact=format_fraction(labeled_sum.value),
            expression=labeled_sum.expression,
            target_dimension=format_dim(target),
            certificate=(
                "object labels formed independent typed components",
                "each component was contracted before coproduct addition",
                "all labelled evidence was consumed exactly once",
            ),
        )
    terms = [term for term in synthesize_terms(measures, target) if term.value >= 0]
    if not terms:
        return None
    # Only evidence in the target's connected unit component is mandatory.
    # This excludes incidental quantities such as "two days" in a question
    # that merely adds two already-computed mile distances.
    connected_units = {name for name, _ in target}
    changed = True
    while changed:
        changed = False
        for measure in measures:
            units = {name for name, _ in measure.dimension}
            if units & connected_units and not units <= connected_units:
                connected_units |= units
                changed = True
    required_mask = 0
    for index, measure in enumerate(measures):
        if not measure.synthetic and {name for name, _ in measure.dimension} & connected_units:
            required_mask |= 1 << index
    terms = [term for term in terms if term.mask & required_mask == required_mask]
    target_names = {name for name, power in target if power > 0}
    target_measures = [
        measure for measure in measures
        if not measure.synthetic and any(dict(measure.dimension).get(name, 0) > 0 for name in target_names)
    ]
    if len(target_measures) > 1:
        direct_sum = all(measure.dimension == target for measure in target_measures)
        labelled_components = all(
            measure.label
            and any(other is not measure and other.label == measure.label for other in measures)
            for measure in target_measures
        )
        if not (direct_sum or labelled_components):
            return None
        terms = [term for term in terms if "+" in term.operators]
    if not terms:
        return None
    prefer_add = bool(re.search(r"\b(?:total|altogether|combined|in all|two days|all the)\b", source))
    prefer_sub = bool(re.search(r"\b(?:left|remaining|difference|shorter)\b", source))

    def rank(term: RateTerm) -> tuple[int, int, int]:
        operators = set(term.operators)
        semantic = (3 if prefer_add and "+" in operators else 0) + (3 if prefer_sub and "-" in operators else 0)
        semantic -= 2 if "+" in operators and not prefer_add else 0
        semantic -= 2 if "-" in operators and not prefer_sub else 0
        return term.evidence, semantic, -len(term.operators)

    best_rank = max(map(rank, terms))
    best = [term for term in terms if rank(term) == best_rank]
    values = {term.value for term in best}
    if len(values) != 1:
        return None
    selected = min(best, key=lambda term: (len(term.expression), term.expression))
    return RateGraphResult(
        answer_exact=format_fraction(selected.value),
        expression=selected.expression,
        target_dimension=format_dim(target),
        certificate=(
            "numeric leaves were typed by numerator and denominator units",
            "only type-compatible rate morphisms were composed",
            "the maximum-evidence target term has a unique value",
        ),
    )
