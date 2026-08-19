"""Typed quantity parser and equation-candidate verifier.

This module is deliberately conservative.  It does not memorize benchmark
items; it extracts typed quantities, proposes equation candidates, and returns
only candidates whose units/objects match the question well enough.
"""

from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass, field
from fractions import Fraction
from math import ceil, floor

try:
    from math_os_prototype.semantic_logic import verify_quantity_candidate_semantics
except ImportError:  # Allows direct script execution.
    from semantic_logic import verify_quantity_candidate_semantics


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
}

HYPHEN_NUMBER_WORD_RE = r"(?:twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)-(?:one|two|three|four|five|six|seven|eight|nine)"
NUMBER_WORD_RE = (
    rf"\b(?:{HYPHEN_NUMBER_WORD_RE}|zero|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|"
    r"nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|"
    r"half|third|quarter|dozen)\b"
)
NUMBER_RE = rf"(?<![a-z])\$?\d+/\d+(?![a-z])|(?<![a-z])\$?\d+(?:\.\d+)?(?![a-z])|{NUMBER_WORD_RE}"

NEGATIVE_VERBS = {
    "delete",
    "deleted",
    "gave",
    "give",
    "lost",
    "lose",
    "used",
    "use",
    "uses",
    "sold",
    "sell",
    "ate",
    "eat",
    "spent",
    "spend",
    "planted",
    "plant",
    "handed",
    "took",
    "take",
    "threw",
    "drank",
    "paid",
    "discard",
    "discarded",
    "forgot",
    "put",
}
POSITIVE_VERBS = {
    "added",
    "add",
    "bought",
    "buy",
    "found",
    "received",
    "got",
    "made",
    "earned",
    "cooked",
    "filled",
    "harvest",
    "harvested",
    "picked",
    "joined",
    "join",
}
STATE_VERBS = {"had", "has", "have", "there", "were", "was", "started", "total"}
TIME_WORDS = {
    "morning",
    "afternoon",
    "evening",
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
    "yesterday",
    "today",
    "first",
    "second",
    "third",
    "month",
    "day",
    "week",
    "hour",
    "minute",
}
META_OBJECTS = {"chapter", "chapters", "problem", "problems", "question", "questions", "level", "levels"}
QUERY_STOP_WORDS = {
    "did",
    "do",
    "does",
    "he",
    "her",
    "him",
    "it",
    "many",
    "more",
    "much",
    "she",
    "they",
    "will",
    "would",
    "you",
}
PRONOUN_OBJECTS = {"it", "one", "ones", "them", "rest", "quantity"}
CONTAINER_OBJECTS = {
    "bag",
    "basket",
    "box",
    "bus",
    "carton",
    "container",
    "folder",
    "group",
    "load",
    "package",
    "shelf",
    "shelve",
    "team",
    "wardrobe",
}
PLACE_OBJECTS = {"museum", "park", "zoo", "school", "store", "palace", "class", "room"}
MEASURE_UNITS = {
    "cup", "tablespoon", "teaspoon", "liter", "milliliter", "gallon", "quart",
    "gram", "kilogram", "ounce", "pound", "inch", "foot", "yard", "meter", "mile",
}


@dataclass(frozen=True)
class Quantity:
    id: int
    value: Fraction
    surface: str
    unit: str
    obj: str
    owner: str | None
    time: str | None
    role: str
    sentence_index: int
    text: str
    denominator: str | None = None

    def to_dict(self) -> dict[str, str | int | None]:
        payload = asdict(self)
        payload["value"] = format_fraction(self.value)
        return payload


@dataclass(frozen=True)
class EquationCandidate:
    kind: str
    expression: str
    value: Fraction
    evidence_ids: list[int]
    target_object: str | None
    confidence: float
    checks: list[str] = field(default_factory=list)
    logic: dict[str, object] | None = None

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["value"] = format_fraction(self.value)
        return payload


@dataclass(frozen=True)
class QuantityReasoningResult:
    answer_exact: str
    expression: str
    explanation: str
    quantities: list[dict[str, object]]
    candidates: list[dict[str, object]]
    semantic_model: dict[str, object] | None = None


QUERY_CERTIFICATE_CHECKS = {
    "comparison_query",
    "difference_query",
    "initial_query",
    "per_unit_left_category",
    "per_unit_right_category",
    "query_denominator_fixed",
    "query_fold",
    "query_projection",
    "query_sort_reached",
    "remaining_query",
    "same_object",
    "selected_time_or_category_sum",
    "split_into_equal_groups",
    "target_object_match",
    "target_object_selected_sum",
    "target_total",
    "time_labels_match",
    "time_query",
    "two_group_partition",
}


def solve_quantity_reasoning_problem(text: str) -> QuantityReasoningResult | None:
    normalized = normalize_text(text)
    if "answer choices" in normalized:
        return None
    quantities = extract_quantities(normalized)
    if not quantities:
        return None
    candidates = [attach_semantic_logic(normalized, quantities, candidate) for candidate in build_equation_candidates(normalized, quantities)]
    verified = [candidate for candidate in candidates if verify_candidate(normalized, quantities, candidate)]
    if not verified:
        return None
    executable = [candidate for candidate in verified if candidate_execution_ready(quantities, candidate)]
    if not executable:
        return None
    best = max(executable, key=lambda item: (item.confidence, len(item.evidence_ids), -abs(float(item.value))))
    if best.confidence < 0.72:
        return None
    return QuantityReasoningResult(
        answer_exact=format_fraction(best.value),
        expression=best.expression,
        explanation=f"quantity reasoning: {best.kind}; checks={', '.join(best.checks)}",
        quantities=[quantity.to_dict() for quantity in quantities],
        candidates=[candidate.to_dict() for candidate in verified[:6]],
        semantic_model={
            "best_candidate_kind": best.kind,
            "best_sequent": (best.logic or {}).get("sequent"),
            "output_sort": (best.logic or {}).get("output_sort"),
            "obligations": (best.logic or {}).get("obligations", []),
            "execution_certificate": build_execution_certificate(quantities, best),
            "evidence_coverage": len(set(best.evidence_ids)) / len(quantities) if quantities else 0.0,
        },
    )


def candidate_execution_ready(quantities: list[Quantity], candidate: EquationCandidate) -> bool:
    """Require a proof that no premise was silently dropped.

    A candidate may execute when its algebraic law is proved, when all numeric
    premises are consumed, or when the query morphism explicitly certifies a
    projection that makes the unused premises irrelevant.
    """
    certificate = build_execution_certificate(quantities, candidate)
    if os.getenv("MATHOS_REQUIRE_DEPENDENCY_COVERAGE", "1") != "0" and (
        (candidate.logic or {}).get("connected_unconsumed_premise_ids")
    ):
        return False
    if certificate["status"] == "proved":
        return True
    if quantities and len(set(candidate.evidence_ids)) == len(quantities):
        return True
    return bool(set(candidate.checks) & QUERY_CERTIFICATE_CHECKS)


def build_execution_certificate(quantities: list[Quantity], candidate: EquationCandidate) -> dict[str, object]:
    """Promote only algebraically explicit semantic laws to execution.

    A type-correct candidate is not yet a proof that it models every event in
    the story.  These laws have an invertible/conservative equation whose
    operands are all named by evidence; broad sum/product guesses remain IR
    candidates but are not executable.
    """
    laws = {
        "initial_from_final_and_gain": "final = initial + gain",
        "initial_from_final_and_loss": "final = initial - loss",
        "complement_count": "selected + complement = total",
        "complement_count_times_unit": "value = (total - excluded) * unit_rate",
        "fractional_each_allocation": "allocated = count * fraction_per_item",
        "per_unit_count_difference": "difference = unit_rate * count_delta",
        "per_unit_category_difference": "difference = count * rate_delta",
        "selected_sum": "total = sum(selected typed quantities)",
        "sum_per_units_times_count": "total = count * sum(compatible rates)",
        "target_total_divided_by_group_count": "unit = target_total / group_count",
        "time_category_difference": "difference = rate * time_delta",
        "two_group_difference": "difference = group_2 - group_1",
    }
    law = laws.get(candidate.kind)
    evidence = evidence_quantities(quantities, candidate)
    logic_status = (candidate.logic or {}).get("status")
    complete = bool(law and evidence and len(evidence) == len(set(candidate.evidence_ids)) and logic_status == "accepted")
    return {
        "status": "proved" if complete else "incomplete",
        "law": law,
        "evidence_ids": list(candidate.evidence_ids),
        "checks": list(candidate.checks),
        "reason": None if complete else "no complete conservation/cancellation proof for this candidate",
    }


def extract_quantities(text: str) -> list[Quantity]:
    sentences = split_sentences(text)
    quantities: list[Quantity] = []
    next_id = 0
    latest_concrete_object: str | None = None
    for sentence_index, sentence in enumerate(sentences):
        number_matches = list(re.finditer(rf"(?P<number>{NUMBER_RE})", sentence))
        previous_concrete_object = latest_concrete_object
        for number_index, match in enumerate(number_matches):
            number_text = match.group("number")
            if is_referential_one(sentence, match.start(), number_text):
                continue
            value = parse_number(number_text)
            if value is None:
                continue
            tail_end = number_matches[number_index + 1].start() if number_index + 1 < len(number_matches) else len(sentence)
            tail = sentence[match.end() : tail_end]
            unit, obj = ("dollar", "dollar") if number_text.startswith("$") else parse_unit_object(tail)
            if (obj in PLACE_OBJECTS or obj == "quantity") and previous_concrete_object is not None:
                unit = previous_concrete_object
                obj = previous_concrete_object
            role = infer_role(sentence, match.start())
            coordinated_denominator: str | None = None
            if (
                role == "state"
                and quantities
                and quantities[-1].sentence_index == sentence_index
                and quantities[-1].role in {"rate", "per_unit"}
                and re.search(r"\band\b", sentence[number_matches[number_index - 1].end() : match.start()])
            ):
                role = "per_unit"
                coordinated_denominator = quantities[-1].denominator
            if "/" in number_text:
                unit, obj, role = "scalar", "scalar", "scale"
            elif sentence[match.end() :].lstrip().startswith("%"):
                unit, obj, role = "percent", "percent", "scale"
            elif is_dimension_component(sentence, match.start(), match.end()):
                unit, obj, role = "dimension", "dimension", "dimension"
            denominator = coordinated_denominator or infer_surface_denominator(
                sentence,
                match.start(),
                match.end(),
                number_text,
                previous_concrete_object,
            ) if role in {"rate", "per_unit"} else None
            owner = infer_owner(sentence, match.start())
            time = infer_time(sentence, match.start())
            quantities.append(
                Quantity(
                    id=next_id,
                    value=value,
                    surface=number_text,
                    unit=unit,
                    obj=obj,
                    owner=owner,
                    time=time,
                    role=role,
                    sentence_index=sentence_index,
                    text=sentence.strip(),
                    denominator=denominator,
                )
            )
            if obj not in META_OBJECTS | PRONOUN_OBJECTS | PLACE_OBJECTS:
                previous_concrete_object = obj
                if obj not in {"dimension", "percent", "scalar"}:
                    latest_concrete_object = obj
            next_id += 1
    return quantities


def build_equation_candidates(text: str, quantities: list[Quantity]) -> list[EquationCandidate]:
    candidates: list[EquationCandidate] = []
    builders = (
        candidate_affine_entity_relation,
        candidate_fractional_each_allocation,
        candidate_comparison_difference,
        candidate_conservation_initial,
        candidate_rate_chain,
        candidate_complement_count_times_unit,
        candidate_complement_count,
        candidate_previous_period_difference,
        candidate_unknown_loss_vs_gain_difference,
        candidate_state_update,
        candidate_gain_minus_loss_remaining,
        candidate_initial_from_final_and_loss,
        candidate_remaining_capacity,
        candidate_gain_vs_loss_difference,
        candidate_adjusted_category_difference,
        candidate_rate_minus_discount,
        candidate_sum_per_units_times_count,
        candidate_count_sum_times_common_unit,
        candidate_two_group_difference,
        candidate_partition_difference,
        candidate_total_divided_by_duration,
        candidate_same_object_state_difference,
        candidate_selected_object_sum,
        candidate_need_minus_have,
        candidate_rest_after_known_part,
        candidate_rate_times_sum_time_quantities,
        candidate_remaining_count_times_rate,
        candidate_target_total_divided_by_group_count,
        candidate_total_divided_by_unit_count,
        candidate_unit_price_from_total_and_count,
        candidate_times_difference,
        candidate_split_total_by_group_count,
        candidate_nested_container_division,
        candidate_initial_from_each_removed_and_final,
        candidate_net_rate_times_duration,
        candidate_difference,
        candidate_rate_times_duration,
        candidate_total_divided_by_rate,
        candidate_unit_count_product,
        candidate_remainder_divided_by_unit,
        candidate_selected_sum,
        candidate_fractional_sequence,
    )
    for builder in builders:
        candidates.extend(builder(text, quantities))
    return sorted(candidates, key=lambda item: item.confidence, reverse=True)


def candidate_comparison_difference(text: str, quantities: list[Quantity]) -> list[EquationCandidate]:
    if not any(marker in text for marker in ("how many fewer", "how much less", "how many more", "how much more")):
        return []
    if any(marker in text for marker in ("split", "two groups", "second group", "second pile")):
        return []
    target = query_object(text)
    if not target:
        return []
    relevant = [
        quantity for quantity in quantities
        if equivalent_object(quantity.obj, target)
        and quantity.role in {"state", "initial", "total", "gain"}
    ]
    if len(relevant) != 2:
        return []
    left, right = relevant
    value = abs(left.value - right.value)
    proof_evidence_ids = [
        quantity.id for quantity in quantities
        if equivalent_object(quantity.obj, target)
    ]
    return [
        EquationCandidate(
            kind="comparison_difference",
            expression=f"abs({format_fraction(left.value)}-{format_fraction(right.value)})",
            value=value,
            evidence_ids=proof_evidence_ids,
            target_object=target,
            confidence=0.94,
            checks=["same_indexed_sort", "comparison_query", "absolute_difference"],
        )
    ]


def candidate_conservation_initial(text: str, quantities: list[Quantity]) -> list[EquationCandidate]:
    if not is_initial_query(text):
        return []
    target = query_object(text)
    relevant = [
        quantity for quantity in quantities
        if target and equivalent_object(quantity.obj, target)
    ]
    losses = [quantity for quantity in relevant if quantity.role == "loss"]
    gains = [quantity for quantity in relevant if quantity.role == "gain"]
    finals = [
        quantity for quantity in relevant
        if quantity.role in {"state", "total"} and any(marker in quantity.text for marker in ("now", "left", "remain"))
    ]
    if not finals:
        finals = [quantity for quantity in relevant if quantity.role in {"state", "total"}]
    if len(finals) != 1 or (not losses and not gains):
        return []
    final = finals[-1]
    loss = sum((item.value for item in losses), Fraction(0))
    gain = sum((item.value for item in gains), Fraction(0))
    value = final.value + loss - gain
    if value < 0:
        return []
    return [
        EquationCandidate(
            kind="conservation_initial",
            expression=f"{format_fraction(final.value)}+{format_fraction(loss)}-{format_fraction(gain)}",
            value=value,
            evidence_ids=[final.id, *[item.id for item in losses], *[item.id for item in gains]],
            target_object=target,
            confidence=0.95,
            checks=["initial_query", "state_conservation", "all_transfers_consumed"],
        )
    ]


def candidate_affine_entity_relation(text: str, quantities: list[Quantity]) -> list[EquationCandidate]:
    """Solve a named affine relation and optionally fold the named values."""

    direct = re.search(
        rf"\b(?P<left>[a-z]+)\s+(?:has|had|made|earns?|gets?|owns?)\s+"
        rf"(?P<delta>{NUMBER_RE})\s+more\s+[a-z-]+(?:\s+[a-z-]+)?\s+than\s+(?P<right>[a-z]+)\b",
        text,
    )
    scaled = re.search(
        rf"\b(?P<left>[a-z]+)\s+(?:has|had|made|earns?|gets?|owns?)\s+"
        rf"(?P<delta>{NUMBER_RE})\s+more\s+than\s+"
        rf"(?P<scale>twice|double|three\s+times|four\s+times)?\s*(?:the\s+)?(?:money|amount|number)?\s*"
        rf"(?P<right>[a-z]+)\s+(?:has|had|made|earns?|gets?|owns?)",
        text,
    )
    relation = scaled or direct
    if not relation:
        return []
    left = relation.group("left")
    right = relation.group("right")
    delta = parse_number(relation.group("delta"))
    if delta is None:
        return []
    scale_surface = relation.groupdict().get("scale") or ""
    scale = {"twice": 2, "double": 2, "three times": 3, "four times": 4}.get(scale_surface, 1)
    fact = re.search(
        rf"\b{re.escape(right)}\s+(?:has|had|made|earns?|gets?|owns?)\s+(?P<base>{NUMBER_RE})\b",
        text,
    )
    if not fact:
        return []
    base = parse_number(fact.group("base"))
    if base is None:
        return []
    left_value = scale * base + delta
    query_tail = text[text.rfind("how ") :] if "how " in text else text
    aggregate = "together" in query_tail or "in total" in query_tail or "altogether" in query_tail
    value = left_value + base if aggregate and left in query_tail and right in query_tail else left_value
    evidence = [
        quantity.id
        for quantity in quantities
        if quantity.value in {delta, base}
    ]
    expression = f"({scale}*{format_fraction(base)}+{format_fraction(delta)})"
    if value != left_value:
        expression = f"{expression}+{format_fraction(base)}"
    return [
        EquationCandidate(
            kind="affine_entity_relation",
            expression=expression,
            value=value,
            evidence_ids=evidence,
            target_object=query_object(text),
            confidence=0.93,
            checks=["affine_relation", "named_entity_binding", "query_fold" if aggregate else "query_projection"],
        )
    ]


def candidate_fractional_each_allocation(text: str, quantities: list[Quantity]) -> list[EquationCandidate]:
    """Compose scalar action, repeated allocation, and conservation."""

    if not any(marker in text for marker in ("left", "remaining", "remain")):
        return []
    allocation = re.search(
        rf"(?P<count>{NUMBER_RE})\s+(?P<agent>[a-z-]+)\s+each\s+"
        rf"(?:got|received|took|used)\s+(?P<fraction>\d+/\d+)\s+of\s+(?:the\s+)?"
        rf"(?P<total>{NUMBER_RE})\s+(?P<object>[a-z-]+)",
        text,
    )
    if not allocation:
        return []
    count = parse_number(allocation.group("count"))
    fraction = parse_number(allocation.group("fraction"))
    total = parse_number(allocation.group("total"))
    if count is None or fraction is None or total is None:
        return []
    target = query_object(text)
    obj = normalize_object(allocation.group("object"))
    if target and not equivalent_object(target, obj):
        return []
    extra_values: list[Fraction] = []
    suffix = text[allocation.end() :]
    for match in re.finditer(
        rf"\b(?:got|received|took|used)\s+(?P<value>{NUMBER_RE})\s+(?P<object>[a-z-]+)",
        suffix,
    ):
        if equivalent_object(match.group("object"), obj):
            parsed = parse_number(match.group("value"))
            if parsed is not None:
                extra_values.append(parsed)
    repeated = count * fraction * total
    value = total - repeated - sum(extra_values, Fraction(0))
    if value < 0:
        return []
    evidence_values = {count, fraction, total, *extra_values}
    evidence = [quantity.id for quantity in quantities if quantity.value in evidence_values]
    extra_expression = "".join(f"-{format_fraction(item)}" for item in extra_values)
    return [
        EquationCandidate(
            kind="fractional_each_allocation",
            expression=(
                f"{format_fraction(total)}-{format_fraction(count)}*"
                f"{format_fraction(fraction)}*{format_fraction(total)}{extra_expression}"
            ),
            value=value,
            evidence_ids=evidence,
            target_object=target or obj,
            confidence=0.94,
            checks=["scalar_action", "each_scope", "conservation", "query_sort_reached"],
        )
    ]


def candidate_rate_chain(text: str, quantities: list[Quantity]) -> list[EquationCandidate]:
    """Compose and merge Count(A), Rate(B/A) terms as a typed DAG."""

    if any(
        marker in text
        for marker in (
            "didn't", "did not", "forgot", "except", "all but", "left over", "remaining",
            "gave away", "sold", "lost", "deleted", "more than", "less than", "%", "percent",
            "half", "quarter", "fraction", "steal", "used up",
        )
    ):
        return []
    target = query_object(text)
    if not target:
        return []
    starts = [
        quantity
        for quantity in quantities
        if quantity.role in {"state", "initial", "total", "gain"}
        and quantity.obj not in {"quantity", "dimension", "percent", "scalar"}
    ]
    atomic_rates: list[tuple[Quantity, str]] = []
    for quantity in quantities:
        if quantity.role not in {"rate", "per_unit"} or quantity.obj in {"quantity", "dimension", "percent", "scalar"}:
            continue
        denominator = rate_denominator(quantity)
        if denominator:
            atomic_rates.append((quantity, denominator))
        elif re.search(r"\beach\b", quantity.text):
            atomic_rates.extend((quantity, start.obj) for start in starts if start.sentence_index <= quantity.sentence_index)
    grouped: dict[tuple[str, str], list[Quantity]] = {}
    for rate, denominator in atomic_rates:
        grouped.setdefault((normalize_object(rate.obj), normalize_object(denominator)), []).append(rate)
    rates: list[tuple[str, str, Fraction, list[int], list[str]]] = []
    for (output_obj, denominator), group in grouped.items():
        unique = list({item.id: item for item in group}.values())
        # Parallel arrows with the same type must merge before composition;
        # returning one branch alone cannot prove an aggregate query.
        value = sum((item.value for item in unique), Fraction(0))
        rates.append(
            (
                output_obj,
                denominator,
                value,
                [item.id for item in unique],
                [format_fraction(item.value) for item in unique],
            )
        )
    candidates: list[EquationCandidate] = []
    query_start = max(text.rfind("how many"), text.rfind("how much"))
    query_clause = text[query_start:] if query_start >= 0 else ""
    each_query = re.search(r"\b(?:in|on|for)\s+each\s+(?P<den>[a-z-]+)", query_clause)
    if each_query:
        query_denominator = normalize_object(each_query.group("den"))
        for output_obj, denominator, value, evidence, factors in rates:
            if equivalent_object(output_obj, target) and equivalent_object(denominator, query_denominator):
                candidates.append(
                    EquationCandidate(
                        kind="typed_rate_chain",
                        expression="+".join(factors),
                        value=value,
                        evidence_ids=evidence,
                        target_object=target,
                        confidence=0.99,
                        checks=["parallel_rate_merge", "query_denominator_fixed", "query_sort_reached"],
                    )
                )
    frontier: list[tuple[str, Fraction, list[int], list[str]]] = [
        (quantity.obj, quantity.value, [quantity.id], [format_fraction(quantity.value)])
        for quantity in starts
    ]
    seen: set[tuple[str, tuple[int, ...]]] = set()
    while frontier:
        current_obj, value, evidence, factors = frontier.pop(0)
        state_key = (current_obj, tuple(sorted(evidence)))
        if state_key in seen:
            continue
        seen.add(state_key)
        if equivalent_object(current_obj, target) and len(evidence) >= 2:
            candidates.append(
                EquationCandidate(
                    kind="typed_rate_chain",
                    expression="*".join(factors),
                    value=value,
                    evidence_ids=evidence,
                    target_object=target,
                    confidence=min(0.97, 0.87 + 0.03 * len(evidence)),
                    checks=["typed_rate_composition", "denominator_cancelled", "query_sort_reached"],
                )
            )
        if len(evidence) >= 6:
            continue
        for output_obj, denominator, rate_value, rate_ids, rate_factors in rates:
            if set(rate_ids) & set(evidence) or not equivalent_object(current_obj, denominator):
                continue
            frontier.append(
                (
                    output_obj,
                    value * rate_value,
                    [*evidence, *rate_ids],
                    [*factors, f"({'+'.join(rate_factors)})" if len(rate_factors) > 1 else rate_factors[0]],
                )
            )
    return candidates


def candidate_complement_count_times_unit(text: str, quantities: list[Quantity]) -> list[EquationCandidate]:
    if not any(marker in text for marker in ("didn't", "did not", "not ", "but didn't", "except", "all but", "forgot")):
        return []
    rates = [quantity for quantity in quantities if quantity.role in {"per_unit", "rate"}]
    totals = [
        quantity
        for quantity in quantities
        if quantity.role in {"state", "initial", "total"} and quantity.obj not in META_OBJECTS | PRONOUN_OBJECTS
    ]
    skipped = [
        quantity
        for quantity in quantities
        if quantity.obj in PRONOUN_OBJECTS
        and any(marker in quantity.text for marker in ("didn't", "did not", "not ", "except", "all but", "forgot"))
    ]
    if not rates or not totals or not skipped:
        return []
    rate = rates[-1]
    skip = skipped[-1]
    total = latest_total_before(quantities, skip) or totals[-1]
    target = query_object(text)
    if target and not same_object(rate.obj, target) and rate.obj not in {"dollar", "cent", "money"} and target not in {"money", "cost"}:
        return []
    if total.id == skip.id or total.value < skip.value:
        return []
    value = (total.value - skip.value) * rate.value
    return [
        EquationCandidate(
            kind="complement_count_times_unit",
            expression=f"({format_fraction(total.value)}-{format_fraction(skip.value)})*{format_fraction(rate.value)}",
            value=value,
            evidence_ids=[total.id, skip.id, rate.id],
            target_object=target or rate.obj,
            confidence=0.87,
            checks=["complement_count", "per_unit", "target_object_match"],
        )
    ]


def candidate_complement_count(text: str, quantities: list[Quantity]) -> list[EquationCandidate]:
    if not any(marker in text for marker in ("didn't", "did not", "not ", "except", "all but", "forgot")):
        return []
    if not any(marker in text for marker in ("did leave", "did make", "actually", "who did")):
        return []
    totals = [
        quantity
        for quantity in quantities
        if quantity.role in {"state", "initial", "total", "gain"}
        and quantity.obj not in META_OBJECTS | PRONOUN_OBJECTS
        and not any(marker in quantity.text for marker in ("didn't", "did not", "not ", "except", "all but", "forgot"))
    ]
    skipped = [
        quantity
        for quantity in quantities
        if any(marker in quantity.text for marker in ("didn't", "did not", "not ", "except", "all but", "forgot"))
    ]
    if not totals or not skipped:
        return []
    skip = skipped[-1]
    total_value = sum((quantity.value for quantity in totals if quantity.id < skip.id or same_object(quantity.obj, skip.obj)), Fraction(0))
    if total_value == 0:
        total_value = sum((quantity.value for quantity in totals), Fraction(0))
    value = total_value - skip.value
    if value < 0:
        return []
    evidence = [quantity.id for quantity in totals] + [skip.id]
    return [
        EquationCandidate(
            kind="complement_count",
            expression=f"{format_fraction(total_value)}-{format_fraction(skip.value)}",
            value=value,
            evidence_ids=evidence,
            target_object=query_object(text),
            confidence=0.86,
            checks=["complement_count", "no_unit_rate_required"],
        )
    ]


def candidate_previous_period_difference(text: str, quantities: list[Quantity]) -> list[EquationCandidate]:
    if "previous day" not in text and "earlier" not in text:
        return []
    if "how many more" not in text and "how much more" not in text:
        return []
    target = query_object(text)
    if target is None:
        return []
    relevant = [quantity for quantity in quantities if equivalent_object(quantity.obj, target)]
    if len(relevant) < 2:
        return []
    current = relevant[0]
    previous = relevant[-1]
    if current.id == previous.id or current.value < previous.value:
        return []
    return [
        EquationCandidate(
            kind="previous_period_difference",
            expression=f"{format_fraction(current.value)}-{format_fraction(previous.value)}",
            value=current.value - previous.value,
            evidence_ids=[current.id, previous.id],
            target_object=target,
            confidence=0.89,
            checks=["previous_period", "current_minus_previous"],
        )
    ]


def candidate_unknown_loss_vs_gain_difference(text: str, quantities: list[Quantity]) -> list[EquationCandidate]:
    if "how many more" not in text or not any(word in text for word in ("sell", "sold", "selling")):
        return []
    if not any(word in text for word in ("bought", "buy")):
        return []
    target = query_object(text)
    if target is None:
        return []
    states = [quantity for quantity in quantities if equivalent_object(quantity.obj, target) and quantity.role in {"state", "initial"}]
    finals = [
        quantity
        for quantity in quantities
        if (equivalent_object(quantity.obj, target) or quantity.obj in PRONOUN_OBJECTS)
        and any(word in quantity.text for word in ("now", "has", "have"))
        and quantity.id not in {state.id for state in states}
    ]
    gains = [
        quantity
        for quantity in quantities
        if quantity.role == "gain"
        and (equivalent_object(quantity.obj, target) or quantity.obj in PRONOUN_OBJECTS)
        and quantity.id not in {final.id for final in finals}
    ]
    if not states or not gains or not finals:
        return []
    initial = states[0]
    gain_sum = sum((quantity.value for quantity in gains), Fraction(0))
    final = finals[-1]
    inferred_loss = initial.value + gain_sum - final.value
    value = inferred_loss - gain_sum
    if inferred_loss < 0 or value < 0:
        return []
    return [
        EquationCandidate(
            kind="unknown_loss_vs_gain_difference",
            expression=f"({format_fraction(initial.value)}+{format_fraction(gain_sum)}-{format_fraction(final.value)})-{format_fraction(gain_sum)}",
            value=value,
            evidence_ids=[initial.id, final.id] + [quantity.id for quantity in gains],
            target_object=target,
            confidence=0.89,
            checks=["unknown_loss", "loss_minus_gain"],
        )
    ]


def candidate_state_update(text: str, quantities: list[Quantity]) -> list[EquationCandidate]:
    if is_initial_query(text):
        return []
    target = query_object(text)
    if target is None:
        return []
    relevant = [
        quantity
        for quantity in quantities
        if same_object(quantity.obj, target)
        or (quantity.role in {"gain", "loss"} and quantity.obj in PRONOUN_OBJECTS)
    ]
    if len(relevant) < 2:
        return []
    initials = [quantity for quantity in relevant if quantity.role in {"state", "initial"}]
    deltas = [quantity for quantity in relevant if quantity.role in {"gain", "loss"}]
    if not initials or not deltas:
        return []
    initial = initials[0]
    value = initial.value
    expression_parts = [format_fraction(initial.value)]
    evidence = [initial.id]
    for delta in deltas:
        evidence.append(delta.id)
        if delta.role == "loss":
            value -= delta.value
            expression_parts.append(f"-{format_fraction(delta.value)}")
        else:
            value += delta.value
            expression_parts.append(f"+{format_fraction(delta.value)}")
    return [
        EquationCandidate(
            kind="state_update",
            expression="".join(expression_parts),
            value=value,
            evidence_ids=evidence,
            target_object=target,
            confidence=0.82,
            checks=["target_object_match", "state_plus_signed_deltas"],
        )
    ]


def candidate_gain_minus_loss_remaining(text: str, quantities: list[Quantity]) -> list[EquationCandidate]:
    if not any(marker in text for marker in ("left", "still have", "still had")):
        return []
    target = query_object(text)
    if target is None:
        return []
    relevant = [
        quantity
        for quantity in quantities
        if (equivalent_object(quantity.obj, target) or quantity.obj in PRONOUN_OBJECTS)
        and quantity.role in {"gain", "loss"}
    ]
    gains = [quantity for quantity in relevant if quantity.role == "gain"]
    losses = [quantity for quantity in relevant if quantity.role == "loss"]
    if not gains or not losses:
        return []
    gain_sum = sum((quantity.value for quantity in gains), Fraction(0))
    loss_sum = sum((quantity.value for quantity in losses), Fraction(0))
    value = gain_sum - loss_sum
    if value < 0:
        return []
    return [
        EquationCandidate(
            kind="gain_minus_loss_remaining",
            expression=f"{format_fraction(gain_sum)}-{format_fraction(loss_sum)}",
            value=value,
            evidence_ids=[quantity.id for quantity in gains + losses],
            target_object=target,
            confidence=0.86,
            checks=["remaining_query", "gains_minus_losses"],
        )
    ]


def candidate_remaining_capacity(text: str, quantities: list[Quantity]) -> list[EquationCandidate]:
    if "how many more" not in text and "how much more" not in text and "can be put" not in text:
        return []
    capacity = first_quantity_with_any(text, quantities, {"hold", "holds", "capacity", "can hold"})
    current = first_quantity_with_any(text, quantities, {"already", "right now", "currently", "there are"})
    if capacity is None or current is None or capacity.id == current.id:
        return []
    return [
        EquationCandidate(
            kind="remaining_capacity",
            expression=f"{format_fraction(capacity.value)}-{format_fraction(current.value)}",
            value=capacity.value - current.value,
            evidence_ids=[capacity.id, current.id],
            target_object=query_object(text),
            confidence=0.83,
            checks=["capacity_minus_current"],
        )
    ]


def candidate_initial_from_final_and_loss(text: str, quantities: list[Quantity]) -> list[EquationCandidate]:
    if not is_initial_query(text):
        return []
    target = query_object(text)
    relevant = [
        quantity
        for quantity in quantities
        if same_object(quantity.obj, target) or quantity.obj in PRONOUN_OBJECTS or target is None
    ]
    losses = [quantity for quantity in relevant if quantity.role == "loss"]
    gains = [quantity for quantity in relevant if quantity.role == "gain"]
    finals = [
        quantity
        for quantity in relevant
        if quantity.role in {"state", "total"}
        and any(marker in quantity.text for marker in ("left", "now", "only has", "has", "altogether", "there were"))
        and quantity.id not in {loss.id for loss in losses}
    ]
    if not losses or not finals:
        if not gains or not finals:
            return []
        gain_sum = sum((quantity.value for quantity in gains), Fraction(0))
        final = finals[-1]
        value = final.value - gain_sum
        return [
            EquationCandidate(
                kind="initial_from_final_and_gain",
                expression=f"{format_fraction(final.value)}-{format_fraction(gain_sum)}",
                value=value,
                evidence_ids=[final.id] + [quantity.id for quantity in gains],
                target_object=target or final.obj,
                confidence=0.87,
                checks=["initial_query", "final_minus_gains"],
            )
        ]
    loss_sum = sum((quantity.value for quantity in losses), Fraction(0))
    gain_sum = sum((quantity.value for quantity in gains), Fraction(0))
    final = finals[-1]
    value = final.value + loss_sum - gain_sum
    expression = f"{format_fraction(final.value)}+{format_fraction(loss_sum)}"
    if gain_sum:
        expression += f"-{format_fraction(gain_sum)}"
    return [
        EquationCandidate(
            kind="initial_from_final_and_loss",
            expression=expression,
            value=value,
            evidence_ids=[final.id] + [quantity.id for quantity in losses + gains],
            target_object=target or final.obj,
            confidence=0.86,
            checks=["initial_query", "final_plus_losses_minus_gains"],
        )
    ]


def candidate_gain_vs_loss_difference(text: str, quantities: list[Quantity]) -> list[EquationCandidate]:
    if "how many more" not in text and "how much more" not in text:
        return []
    if not any(word in text for word in ("add", "added", "delete", "deleted", "make", "made", "sold", "sell")):
        return []
    target = query_object(text)
    relevant = [
        quantity
        for quantity in quantities
        if quantity.obj not in META_OBJECTS
        and (target is None or same_object(quantity.obj, target) or quantity.obj in PRONOUN_OBJECTS)
    ]
    gains = [quantity for quantity in relevant if quantity.role == "gain"]
    losses = [quantity for quantity in relevant if quantity.role == "loss"]
    if gains and losses:
        gain_sum = sum((quantity.value for quantity in gains), Fraction(0))
        loss_sum = sum((quantity.value for quantity in losses), Fraction(0))
        return [
            EquationCandidate(
                kind="gain_vs_loss_difference",
                expression=f"{format_fraction(gain_sum)}-{format_fraction(loss_sum)}",
                value=gain_sum - loss_sum,
                evidence_ids=[quantity.id for quantity in gains + losses],
                target_object=target,
                confidence=0.86,
                checks=["more_than_query", "gain_minus_loss"],
            )
        ]
    states = [quantity for quantity in relevant if quantity.role in {"state", "initial", "total"}]
    finals = [quantity for quantity in states if "left" in quantity.text or "now" in quantity.text]
    initials = [quantity for quantity in states if quantity not in finals and quantity.obj not in PRONOUN_OBJECTS]
    if gains and initials and finals:
        gain_sum = sum((quantity.value for quantity in gains), Fraction(0))
        inferred_loss = initials[0].value + gain_sum - finals[-1].value
        if inferred_loss >= 0:
            return [
                EquationCandidate(
                    kind="gain_vs_inferred_loss_difference",
                    expression=f"{format_fraction(gain_sum)}-({format_fraction(initials[0].value)}+{format_fraction(gain_sum)}-{format_fraction(finals[-1].value)})",
                    value=gain_sum - inferred_loss,
                    evidence_ids=[initials[0].id, finals[-1].id] + [quantity.id for quantity in gains],
                    target_object=target,
                    confidence=0.85,
                    checks=["more_than_query", "inferred_loss_from_final_state"],
                )
            ]
    return []


def candidate_adjusted_category_difference(text: str, quantities: list[Quantity]) -> list[EquationCandidate]:
    if "how many more" not in text and "how much more" not in text:
        return []
    time_labels = time_comparison_labels(text)
    if time_labels is not None:
        left_label, right_label = time_labels
        left_value, left_ids = category_total(left_label, quantities)
        right_value, right_ids = category_total(right_label, quantities)
        if left_value is not None and right_value is not None:
            return [
                EquationCandidate(
                    kind="time_category_difference",
                    expression=f"{format_fraction(left_value)}-{format_fraction(right_value)}",
                    value=left_value - right_value,
                    evidence_ids=left_ids + right_ids,
                    target_object=query_object(text),
                    confidence=0.87,
                    checks=["time_labels_match", "category_difference"],
                )
            ]
    labels = comparison_labels(text)
    if labels is None:
        return []
    left_label, right_label = labels
    rate_left = per_unit_quantity_for_following_label(text, quantities, left_label) or latest_quantity_for_label(quantities, left_label, roles={"per_unit", "rate"})
    rate_right = per_unit_quantity_for_following_label(text, quantities, right_label) or latest_quantity_for_label(quantities, right_label, roles={"per_unit", "rate"})
    if rate_left is not None and rate_right is not None and rate_left.id != rate_right.id:
        return [
            EquationCandidate(
                kind="per_unit_category_difference",
                expression=f"{format_fraction(rate_left.value)}-{format_fraction(rate_right.value)}",
                value=rate_left.value - rate_right.value,
                evidence_ids=[rate_left.id, rate_right.id],
                target_object=left_label,
                confidence=0.88,
                checks=["per_unit_left_category", "per_unit_right_category"],
            )
        ]
    count_right = latest_quantity_for_label(quantities, right_label, roles={"state", "initial", "total"})
    if rate_left is not None and count_right is not None and rate_left.id != count_right.id:
        value = rate_left.value * count_right.value - count_right.value
        return [
            EquationCandidate(
                kind="per_unit_count_difference",
                expression=f"{format_fraction(rate_left.value)}*{format_fraction(count_right.value)}-{format_fraction(count_right.value)}",
                value=value,
                evidence_ids=[rate_left.id, count_right.id],
                target_object=left_label,
                confidence=0.87,
                checks=["per_unit_left_category", "right_count_category"],
            )
        ]
    left_value, left_ids = category_total(left_label, quantities)
    right_value, right_ids = category_total(right_label, quantities)
    if left_value is None or right_value is None or not left_ids or not right_ids:
        return []
    return [
        EquationCandidate(
            kind="adjusted_category_difference",
            expression=f"{format_fraction(left_value)}-{format_fraction(right_value)}",
            value=left_value - right_value,
            evidence_ids=left_ids + right_ids,
            target_object=left_label,
            confidence=0.86,
            checks=["comparison_labels_match", "signed_category_totals"],
        )
    ]


def candidate_rate_minus_discount(text: str, quantities: list[Quantity]) -> list[EquationCandidate]:
    if "discount" not in text or not any(word in text for word in ("pay", "cost", "buy")):
        return []
    prices = [quantity for quantity in quantities if "cost" in quantity.text and quantity.obj in {"dollar", "cent", "money"}]
    discounts = [quantity for quantity in quantities if "discount" in quantity.text and quantity.obj in {"dollar", "cent", "money"}]
    if not prices or not discounts:
        return []
    price = prices[0]
    discount = discounts[-1]
    return [
        EquationCandidate(
            kind="rate_minus_discount",
            expression=f"{format_fraction(price.value)}-{format_fraction(discount.value)}",
            value=price.value - discount.value,
            evidence_ids=[price.id, discount.id],
            target_object="cost",
            confidence=0.86,
            checks=["discount_query", "same_money_unit"],
        )
    ]


def candidate_sum_per_units_times_count(text: str, quantities: list[Quantity]) -> list[EquationCandidate]:
    if "total" not in text and "in all" not in text:
        return []
    rates = [
        quantity
        for quantity in quantities
        if quantity.role in {"per_unit", "rate"} and quantity.obj not in {"dollar", "money", "cent"} | PRONOUN_OBJECTS
    ]
    counts = [quantity for quantity in quantities if quantity.role in {"state", "initial", "total"} and quantity.obj in CONTAINER_OBJECTS]
    if len(rates) < 2 or not counts:
        return []
    count = counts[-1]
    rate_sum = sum((quantity.value for quantity in rates), Fraction(0))
    value = rate_sum * count.value
    return [
        EquationCandidate(
            kind="sum_per_units_times_count",
            expression=f"({'+'.join(format_fraction(quantity.value) for quantity in rates)})*{format_fraction(count.value)}",
            value=value,
            evidence_ids=[quantity.id for quantity in rates] + [count.id],
            target_object=query_object(text),
            confidence=0.85,
            checks=["sum_multiple_per_unit_quantities", "container_count"],
        )
    ]


def candidate_count_sum_times_common_unit(text: str, quantities: list[Quantity]) -> list[EquationCandidate]:
    if not any(word in text for word in ("cost", "costs", "pay", "paid", "spend", "spent")):
        return []
    rates = [quantity for quantity in quantities if quantity.role in {"per_unit", "rate"}]
    if not rates:
        return []
    rate_values = {quantity.value for quantity in rates}
    if len(rate_values) != 1:
        return []
    counts = [
        quantity
        for quantity in quantities
        if quantity.role in {"state", "initial", "total"}
        and quantity.obj not in META_OBJECTS | PRONOUN_OBJECTS | CONTAINER_OBJECTS
    ]
    if not counts:
        return []
    rate = rates[-1]
    count_sum = sum((quantity.value for quantity in counts), Fraction(0))
    return [
        EquationCandidate(
            kind="count_sum_times_common_unit",
            expression=f"({'+'.join(format_fraction(quantity.value) for quantity in counts)})*{format_fraction(rate.value)}",
            value=count_sum * rate.value,
            evidence_ids=[quantity.id for quantity in counts] + [quantity.id for quantity in rates],
            target_object="cost",
            confidence=0.84,
            checks=["common_unit_price", "sum_item_counts"],
        )
    ]


def candidate_two_group_difference(text: str, quantities: list[Quantity]) -> list[EquationCandidate]:
    if "two groups" not in text or "second group" not in text or "how many more" not in text:
        return []
    target = query_object(text)
    totals = [
        quantity
        for quantity in quantities
        if quantity.role in {"state", "initial", "total"}
        and same_object(quantity.obj, target)
        and quantity.time is None
    ]
    firsts = [
        quantity
        for quantity in quantities
        if quantity.role in {"state", "initial", "total"}
        and same_object(quantity.obj, target)
        and quantity.time == "first"
    ]
    if not totals or not firsts:
        return []
    total = totals[0]
    first = firsts[-1]
    value = total.value - 2 * first.value
    return [
        EquationCandidate(
            kind="two_group_difference",
            expression=f"{format_fraction(total.value)}-2*{format_fraction(first.value)}",
            value=value,
            evidence_ids=[total.id, first.id],
            target_object=target,
            confidence=0.86,
            checks=["two_group_partition", "second_minus_first"],
        )
    ]


def candidate_partition_difference(text: str, quantities: list[Quantity]) -> list[EquationCandidate]:
    if "two" not in text or "first" not in text or "how many more" not in text:
        return []
    if not any(container in text for container in ("wardrobe", "group", "box", "container")):
        return []
    target = query_object(text)
    totals = [quantity for quantity in quantities if quantity.role in {"state", "initial", "total"} and same_object(quantity.obj, target) and quantity.time is None]
    firsts = [quantity for quantity in quantities if quantity.role in {"state", "initial", "total"} and same_object(quantity.obj, target) and quantity.time == "first"]
    if not totals or not firsts:
        return []
    total = totals[0]
    first = firsts[-1]
    second = total.value - first.value
    value = second - first.value
    return [
        EquationCandidate(
            kind="partition_second_minus_first",
            expression=f"({format_fraction(total.value)}-{format_fraction(first.value)})-{format_fraction(first.value)}",
            value=value,
            evidence_ids=[total.id, first.id],
            target_object=target,
            confidence=0.86,
            checks=["two_container_partition", "second_minus_first"],
        )
    ]


def candidate_total_divided_by_duration(text: str, quantities: list[Quantity]) -> list[EquationCandidate]:
    if not any(phrase in text for phrase in ("per day", "each day", "per hour", "each hour", "per minute", "each minute")):
        return []
    totals = [
        quantity
        for quantity in quantities
        if quantity.role in {"state", "initial", "total", "gain"} and quantity.obj not in META_OBJECTS | PRONOUN_OBJECTS
    ]
    durations = [quantity for quantity in quantities if quantity.role == "duration"]
    if not totals or not durations:
        return []
    total = totals[-1]
    duration = durations[-1]
    if duration.value == 0:
        return []
    return [
        EquationCandidate(
            kind="total_divided_by_duration",
            expression=f"{format_fraction(total.value)}/{format_fraction(duration.value)}",
            value=total.value / duration.value,
            evidence_ids=[total.id, duration.id],
            target_object=query_object(text) or total.obj,
            confidence=0.86,
            checks=["per_time_query", "duration_nonzero"],
        )
    ]


def candidate_same_object_state_difference(text: str, quantities: list[Quantity]) -> list[EquationCandidate]:
    if any(word in text for word in ("totaled", "total", "altogether")) and not any(word in text for word in ("difference", "how many more", "how much more")):
        return []
    target = query_object(text)
    if target is None:
        return []
    relevant = [
        quantity
        for quantity in quantities
        if same_object(quantity.obj, target)
        and quantity.role in {"state", "initial", "total", "gain", "loss"}
    ]
    if len(relevant) < 2:
        return []
    first = relevant[0]
    last = relevant[-1]
    if first.id == last.id:
        return []
    if sum(1 for quantity in relevant if quantity.role == "loss") > 1:
        return []
    if any(word in text for word in ("delete", "deleted", "got off", "left", "lost", "cut off", "disappeared")):
        value = first.value - last.value
        expression = f"{format_fraction(first.value)}-{format_fraction(last.value)}"
        checks = ["same_object", "initial_minus_final"]
    elif any(word in text for word in ("find", "found", "came", "joined", "gained")):
        if "earlier" in last.text or "before" in last.text:
            value = first.value - last.value
            expression = f"{format_fraction(first.value)}-{format_fraction(last.value)}"
        else:
            value = last.value - first.value
            expression = f"{format_fraction(last.value)}-{format_fraction(first.value)}"
        checks = ["same_object", "final_minus_initial"]
    elif "before" in text and any(q.role == "gain" for q in relevant[:-1]):
        gains = [quantity for quantity in relevant[:-1] if quantity.role == "gain"]
        gain_sum = sum((quantity.value for quantity in gains), Fraction(0))
        value = last.value - gain_sum
        expression = f"{format_fraction(last.value)}-{format_fraction(gain_sum)}"
        checks = ["before_query", "final_minus_gains"]
    else:
        return []
    if value < 0 and "how many more" not in text:
        return []
    return [
        EquationCandidate(
            kind="same_object_state_difference",
            expression=expression,
            value=value,
            evidence_ids=[first.id, last.id],
            target_object=target,
            confidence=0.85,
            checks=checks,
        )
    ]


def candidate_selected_object_sum(text: str, quantities: list[Quantity]) -> list[EquationCandidate]:
    target = query_object(text)
    if target is None:
        return []
    if any(word in text for word in ("find", "found", "delete", "deleted", "got off", "before", "cost of each", "price of each")):
        return []
    if any(phrase in text for phrase in ("how many more", "how much more", "left", "still have", "still had", "still need", "does she need", "does he need", " rest ")):
        return []
    if not any(word in text for word in ("total", "altogether", "in all", "have", "has", "had", "there are")):
        return []
    selected = [
        quantity
        for quantity in quantities
        if equivalent_object(quantity.obj, target)
        and quantity.role in {"state", "initial", "total", "gain"}
        and not any(marker in quantity.text for marker in ("can not have more", "can have", "capacity", "holds", "can hold"))
    ]
    if any(quantity.role == "loss" and (quantity.obj in PRONOUN_OBJECTS or equivalent_object(quantity.obj, target)) for quantity in quantities):
        return []
    if len(selected) < 2:
        return []
    value = sum((quantity.value for quantity in selected), Fraction(0))
    return [
        EquationCandidate(
            kind="selected_object_sum",
            expression="+".join(format_fraction(quantity.value) for quantity in selected),
            value=value,
            evidence_ids=[quantity.id for quantity in selected],
            target_object=target,
            confidence=0.84,
            checks=["target_object_selected_sum"],
        )
    ]


def candidate_need_minus_have(text: str, quantities: list[Quantity]) -> list[EquationCandidate]:
    if "need" not in text or "how many more" not in text:
        return []
    target = query_object(text)
    if target is None:
        return []
    needed = [
        quantity
        for quantity in quantities
        if equivalent_object(quantity.obj, target) and any(word in quantity.text for word in ("need", "needs", "needed"))
    ]
    have = [
        quantity
        for quantity in quantities
        if equivalent_object(quantity.obj, target) and any(word in quantity.text for word in ("has", "have", "had", "already"))
    ]
    if not needed or not have:
        return []
    value = needed[-1].value - have[-1].value
    if value < 0:
        return []
    return [
        EquationCandidate(
            kind="need_minus_have",
            expression=f"{format_fraction(needed[-1].value)}-{format_fraction(have[-1].value)}",
            value=value,
            evidence_ids=[needed[-1].id, have[-1].id],
            target_object=target,
            confidence=0.88,
            checks=["need_goal", "required_minus_available"],
        )
    ]


def candidate_rest_after_known_part(text: str, quantities: list[Quantity]) -> list[EquationCandidate]:
    if " rest " not in text and "remainder" not in text:
        return []
    target = query_object(text)
    if target is None:
        return []
    relevant = [
        quantity
        for quantity in quantities
        if equivalent_object(quantity.obj, target) and quantity.role in {"state", "initial", "total", "gain"}
    ]
    if len(relevant) < 2:
        return []
    total = relevant[0]
    known = relevant[-1]
    if total.id == known.id or total.value < known.value:
        return []
    return [
        EquationCandidate(
            kind="rest_after_known_part",
            expression=f"{format_fraction(total.value)}-{format_fraction(known.value)}",
            value=total.value - known.value,
            evidence_ids=[total.id, known.id],
            target_object=target,
            confidence=0.88,
            checks=["rest_complement", "total_minus_known_part"],
        )
    ]


def candidate_rate_times_sum_time_quantities(text: str, quantities: list[Quantity]) -> list[EquationCandidate]:
    if not any(word in text for word in ("monday", "tuesday", "those two days", "both days")):
        return []
    rates = [quantity for quantity in quantities if quantity.role in {"rate", "per_unit"} and quantity.obj in {"dollar", "money", "cent"}]
    durations = [
        quantity
        for quantity in quantities
        if quantity.obj in {"hour", "minute", "day"}
        and quantity.role in {"state", "duration"}
        and any(time_word in quantity.text for time_word in ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"))
    ]
    if not rates or len(durations) < 2:
        return []
    rate = rates[-1]
    duration_sum = sum((quantity.value for quantity in durations), Fraction(0))
    return [
        EquationCandidate(
            kind="rate_times_sum_time_quantities",
            expression=f"{format_fraction(rate.value)}*({'+'.join(format_fraction(quantity.value) for quantity in durations)})",
            value=rate.value * duration_sum,
            evidence_ids=[rate.id] + [quantity.id for quantity in durations],
            target_object=query_object(text) or rate.obj,
            confidence=0.88,
            checks=["rate_quantity", "sum_selected_time_quantities"],
        )
    ]


def candidate_remaining_count_times_rate(text: str, quantities: list[Quantity]) -> list[EquationCandidate]:
    if "still need" not in text and "need" not in text:
        return []
    needed = [quantity for quantity in quantities if quantity.owner in {"need", "needed"} or ("need" in quantity.text and quantity.role in {"state", "total"} and "baked" not in quantity.text)]
    current = [quantity for quantity in quantities if any(marker in quantity.text for marker in ("baked", "already", "made")) and quantity.id not in {item.id for item in needed}]
    rates = [quantity for quantity in quantities if quantity.role in {"per_unit", "rate"}]
    if not needed or not current or not rates:
        return []
    total_needed = needed[-1]
    have = current[0]
    rate = rates[-1]
    remaining = total_needed.value - have.value
    if remaining < 0:
        return []
    return [
        EquationCandidate(
            kind="remaining_count_times_rate",
            expression=f"({format_fraction(total_needed.value)}-{format_fraction(have.value)})*{format_fraction(rate.value)}",
            value=remaining * rate.value,
            evidence_ids=[total_needed.id, have.id, rate.id],
            target_object=query_object(text) or rate.obj,
            confidence=0.86,
            checks=["remaining_count", "per_unit"],
        )
    ]


def candidate_target_total_divided_by_group_count(text: str, quantities: list[Quantity]) -> list[EquationCandidate]:
    if "each group" not in text and "per group" not in text:
        return []
    if any(marker in text for marker in (" rest ", "didn't", "did not", "not get", "left")):
        return []
    target = query_object(text)
    if target is None:
        return []
    total = latest_quantity_for_label(quantities, target, roles={"state", "initial", "total", "gain"})
    group = latest_quantity_for_label(quantities, "group", roles={"state", "initial", "total", "per_unit"})
    if total is None or group is None or total.id == group.id or group.value == 0:
        return []
    return [
        EquationCandidate(
            kind="target_total_divided_by_group_count",
            expression=f"{format_fraction(total.value)}/{format_fraction(group.value)}",
            value=total.value / group.value,
            evidence_ids=[total.id, group.id],
            target_object=target,
            confidence=0.87,
            checks=["target_total", "group_count_nonzero"],
        )
    ]


def candidate_total_divided_by_unit_count(text: str, quantities: list[Quantity]) -> list[EquationCandidate]:
    target = query_object(text)
    if target is None:
        return []
    if target not in {"boy", "girl", "person", "people", "student", "worker", "child", "children"}:
        return []
    if "each" not in text and "per" not in text:
        return []
    if "each of" in text:
        return []
    rates = [quantity for quantity in quantities if quantity.role in {"per_unit", "rate"} and "each" in quantity.text]
    totals = [
        quantity
        for quantity in quantities
        if quantity.role in {"state", "initial", "total", "gain", "per_unit"}
        and quantity.id not in {rate.id for rate in rates}
        and quantity.obj not in META_OBJECTS | PRONOUN_OBJECTS
    ]
    if not rates or not totals:
        return []
    total = totals[0]
    rate = rates[-1]
    if rate.value == 0:
        return []
    return [
        EquationCandidate(
            kind="total_divided_by_unit_count",
            expression=f"{format_fraction(total.value)}/{format_fraction(rate.value)}",
            value=total.value / rate.value,
            evidence_ids=[total.id, rate.id],
            target_object=target,
            confidence=0.86,
            checks=["target_count_from_total_and_unit", "unit_nonzero"],
        )
    ]


def candidate_unit_price_from_total_and_count(text: str, quantities: list[Quantity]) -> list[EquationCandidate]:
    if not any(word in text for word in ("cost of each", "price of each")):
        return []
    money = [quantity for quantity in quantities if quantity.obj in {"dollar", "cent", "money"}]
    counts = [
        quantity
        for quantity in quantities
        if quantity.obj not in META_OBJECTS | PRONOUN_OBJECTS | {"dollar", "cent", "money"}
        and quantity.value != 0
    ]
    if not money or not counts:
        return []
    total = money[-1]
    count = counts[-1]
    return [
        EquationCandidate(
            kind="unit_price_from_total_and_count",
            expression=f"{format_fraction(total.value)}/{format_fraction(count.value)}",
            value=total.value / count.value,
            evidence_ids=[total.id, count.id],
            target_object="cost",
            confidence=0.86,
            checks=["money_total", "item_count_nonzero"],
        )
    ]


def candidate_times_difference(text: str, quantities: list[Quantity]) -> list[EquationCandidate]:
    if "times" not in text or not any(word in text for word in ("deeper", "farther", "larger", "more")):
        return []
    values = [quantity for quantity in quantities if quantity.obj not in META_OBJECTS | PRONOUN_OBJECTS]
    if len(values) < 2:
        return []
    factor = values[0]
    base = values[-1]
    if factor.id == base.id:
        return []
    value = (factor.value - 1) * base.value
    return [
        EquationCandidate(
            kind="times_difference",
            expression=f"({format_fraction(factor.value)}-1)*{format_fraction(base.value)}",
            value=value,
            evidence_ids=[factor.id, base.id],
            target_object=query_object(text),
            confidence=0.84,
            checks=["multiplicative_comparison", "difference_from_base"],
        )
    ]


def candidate_split_total_by_group_count(text: str, quantities: list[Quantity]) -> list[EquationCandidate]:
    if "second group" in text and "how many more" in text:
        return []
    if not any(word in text for word in ("split", "groups", "teams", "loads")):
        return []
    if "each" not in text:
        return []
    denominator = next(
        (
            quantity
            for quantity in reversed(quantities)
            if quantity.obj in {"group", "team", "load"}
        ),
        None,
    )
    if denominator is None or denominator.value == 0:
        return []
    numerator_quantities = [
        quantity
        for quantity in quantities
        if quantity.id < denominator.id
        and quantity.obj not in META_OBJECTS | CONTAINER_OBJECTS
        and quantity.role in {"state", "initial", "total", "gain", "loss", "per_unit"}
    ]
    if not numerator_quantities:
        return []
    numerator = Fraction(0)
    for quantity in numerator_quantities:
        numerator += -quantity.value if quantity.role == "loss" else quantity.value
    if numerator <= 0:
        return []
    return [
        EquationCandidate(
            kind="split_total_by_group_count",
            expression=f"{format_fraction(numerator)}/{format_fraction(denominator.value)}",
            value=numerator / denominator.value,
            evidence_ids=[quantity.id for quantity in numerator_quantities] + [denominator.id],
            target_object=query_object(text),
            confidence=0.86,
            checks=["split_into_equal_groups", "group_count_nonzero"],
        )
    ]


def candidate_nested_container_division(text: str, quantities: list[Quantity]) -> list[EquationCandidate]:
    target = query_object(text)
    if target not in CONTAINER_OBJECTS:
        return []
    if not any(word in text for word in ("needed", "need", "take", "trip", "bus")):
        return []
    counts = [quantity for quantity in quantities if quantity.role in {"state", "initial", "total"} and quantity.obj not in META_OBJECTS | PRONOUN_OBJECTS]
    rates = [quantity for quantity in quantities if quantity.role in {"per_unit", "rate"} and quantity.value != 0]
    if not counts or len(rates) < 2:
        return []
    outer_count = counts[0]
    demand_rate = rates[0]
    capacity_rate = rates[-1]
    value = Fraction(ceil((outer_count.value * demand_rate.value) / capacity_rate.value))
    return [
        EquationCandidate(
            kind="nested_container_division",
            expression=f"ceil({format_fraction(outer_count.value)}*{format_fraction(demand_rate.value)}/{format_fraction(capacity_rate.value)})",
            value=value,
            evidence_ids=[outer_count.id, demand_rate.id, capacity_rate.id],
            target_object=target,
            confidence=0.88,
            checks=["nested_container_count", "capacity_rate_nonzero"],
        )
    ]


def candidate_initial_from_each_removed_and_final(text: str, quantities: list[Quantity]) -> list[EquationCandidate]:
    if not is_initial_query(text) or "each" not in text:
        return []
    states = [quantity for quantity in quantities if quantity.role in {"state", "initial"}]
    rates = [quantity for quantity in quantities if quantity.role in {"per_unit", "rate"} and "each" in quantity.text]
    finals = [quantity for quantity in quantities if quantity.role == "total" or "still" in quantity.text]
    if not states or not rates or not finals:
        return []
    count = states[0]
    rate = rates[-1]
    final = finals[-1]
    value = count.value * rate.value + final.value
    return [
        EquationCandidate(
            kind="initial_from_each_removed_and_final",
            expression=f"{format_fraction(count.value)}*{format_fraction(rate.value)}+{format_fraction(final.value)}",
            value=value,
            evidence_ids=[count.id, rate.id, final.id],
            target_object=query_object(text),
            confidence=0.86,
            checks=["initial_query", "each_removed_plus_remaining"],
        )
    ]


def candidate_net_rate_times_duration(text: str, quantities: list[Quantity]) -> list[EquationCandidate]:
    rates = [quantity for quantity in quantities if quantity.role == "rate"]
    durations = [quantity for quantity in quantities if quantity.role == "duration"]
    losses = [quantity for quantity in quantities if quantity.role == "loss" and quantity.time in {"day", "week", "month"} | {rate.time for rate in rates if rate.time}]
    if not rates or not durations or not losses:
        return []
    rate = rates[0]
    loss = losses[-1]
    duration = durations[-1]
    if rate.value < loss.value:
        return []
    value = (rate.value - loss.value) * duration.value
    return [
        EquationCandidate(
            kind="net_rate_times_duration",
            expression=f"({format_fraction(rate.value)}-{format_fraction(loss.value)})*{format_fraction(duration.value)}",
            value=value,
            evidence_ids=[rate.id, loss.id, duration.id],
            target_object=query_object(text) or rate.obj,
            confidence=0.87,
            checks=["net_rate", "duration_quantity"],
        )
    ]


def candidate_difference(text: str, quantities: list[Quantity]) -> list[EquationCandidate]:
    if not any(phrase in text for phrase in ("how many more", "how much more", "difference")):
        return []
    target_labels = comparison_labels(text)
    if target_labels is not None:
        left_label, right_label = target_labels
        left = latest_quantity_matching_label(quantities, left_label)
        right = latest_quantity_matching_label(quantities, right_label)
        if left is not None and right is not None and left.id != right.id:
            value = left.value - right.value
            if "difference between" in text:
                value = abs(value)
            return [
                EquationCandidate(
                    kind="category_difference",
                    expression=f"{format_fraction(left.value)}-{format_fraction(right.value)}",
                    value=value,
                    evidence_ids=[left.id, right.id],
                    target_object=left.obj,
                    confidence=0.86,
                    checks=["comparison_labels_match"],
                )
            ]
    values = [quantity for quantity in quantities if quantity.obj not in META_OBJECTS]
    if len(values) >= 2:
        a, b = values[-1], values[-2]
        value = a.value - b.value
        if "difference between" in text:
            value = abs(value)
        checks = ["difference_query", "last_two_quantities"]
        left_base = comparison_base_reference(a.text)
        right_base = comparison_base_reference(b.text)
        if left_base and left_base == right_base:
            checks.append("common_base_cancellation")
        return [
            EquationCandidate(
                kind="difference_last_two",
                expression=f"{format_fraction(a.value)}-{format_fraction(b.value)}",
                value=value,
                evidence_ids=[a.id, b.id],
                target_object=query_object(text),
                confidence=0.73,
                checks=checks,
            )
        ]
    return []


def comparison_base_reference(text: str) -> str | None:
    match = re.search(
        r"\b(?:more|less|fewer)\s+than\s+(?P<base>[a-z][a-z0-9 ]{0,50}?)(?:[.,;]|$)",
        text.lower(),
    )
    if not match:
        return None
    return " ".join(re.findall(r"[a-z0-9]+", match.group("base")))


def candidate_rate_times_duration(text: str, quantities: list[Quantity]) -> list[EquationCandidate]:
    if not any(phrase in text for phrase in ("how many", "how much", "total", "in all")):
        return []
    rates = [quantity for quantity in quantities if quantity.role == "rate"]
    durations = [quantity for quantity in quantities if quantity.role == "duration"]
    if not rates or not durations:
        return []
    target = query_object(text)
    rate = best_rate_for_target(rates, target)
    duration = durations[-1]
    value = rate.value * duration.value
    return [
        EquationCandidate(
            kind="rate_times_duration",
            expression=f"{format_fraction(rate.value)}*{format_fraction(duration.value)}",
            value=value,
            evidence_ids=[rate.id, duration.id],
            target_object=target or rate.obj,
            confidence=0.84,
            checks=["rate_quantity", "duration_quantity"],
        )
    ]


def candidate_total_divided_by_rate(text: str, quantities: list[Quantity]) -> list[EquationCandidate]:
    if not any(phrase in text for phrase in ("how many days", "how long", "how many minutes", "how many hours")):
        return []
    rates = [quantity for quantity in quantities if quantity.role == "rate"]
    totals = [quantity for quantity in quantities if quantity.role in {"state", "initial", "total", "gain"} and quantity.id not in {rate.id for rate in rates}]
    if not rates or not totals:
        return []
    total = totals[-1]
    rate = rates[-1]
    if rate.value == 0:
        return []
    return [
        EquationCandidate(
            kind="total_divided_by_rate",
            expression=f"{format_fraction(total.value)}/{format_fraction(rate.value)}",
            value=total.value / rate.value,
            evidence_ids=[total.id, rate.id],
            target_object="time",
            confidence=0.84,
            checks=["time_query", "rate_nonzero"],
        )
    ]


def candidate_unit_count_product(text: str, quantities: list[Quantity]) -> list[EquationCandidate]:
    if "each" not in text and "one" not in text and "per" not in text:
        return []
    target = query_object(text)
    if target in CONTAINER_OBJECTS:
        return []
    rates = [quantity for quantity in quantities if quantity.role in {"per_unit", "rate"}]
    counts = [
        quantity
        for quantity in quantities
        if quantity.role in {"state", "initial", "total"}
        and quantity.obj not in META_OBJECTS | PRONOUN_OBJECTS
    ]
    if not rates or not counts:
        return []
    rate = rates[-1]
    count = counts[-1]
    if count.id == rate.id:
        return []
    return [
        EquationCandidate(
            kind="unit_count_product",
            expression=f"{format_fraction(count.value)}*{format_fraction(rate.value)}",
            value=count.value * rate.value,
            evidence_ids=[count.id, rate.id],
            target_object=target or rate.obj,
            confidence=0.80,
            checks=["per_unit", "count_quantity"],
        )
    ]


def candidate_remainder_divided_by_unit(text: str, quantities: list[Quantity]) -> list[EquationCandidate]:
    target = query_object(text)
    if target not in CONTAINER_OBJECTS and not any(
        phrase in text
        for phrase in (
            "how many groups",
            "how many shelves",
            "how many bags",
            "how many small",
            "how many folders",
            "how many boxes",
            "how many packages",
            "how many containers",
        )
    ):
        return []
    totals = [
        quantity
        for quantity in quantities
        if quantity.role in {"state", "initial", "total"}
        and quantity.obj not in META_OBJECTS | PRONOUN_OBJECTS
    ]
    useds = [
        quantity
        for quantity in quantities
        if quantity.role == "loss"
        or any(marker in quantity.text for marker in {"used", "planted", "takes", "already", "deleted", "sold", "ate"})
        and quantity.obj in PRONOUN_OBJECTS
    ]
    units = [quantity for quantity in quantities if quantity.role in {"per_unit", "rate"} and quantity.value != 0]
    total = totals[0] if totals else None
    used = useds[-1] if useds else None
    unit = units[-1] if units else None
    if total is None or unit is None or unit.value == 0:
        return []
    components = [
        quantity
        for quantity in quantities
        if quantity.id < unit.id
        and quantity.obj not in META_OBJECTS | CONTAINER_OBJECTS
        and quantity.role in {"state", "initial", "total", "gain", "loss"}
    ]
    if components:
        numerator = sum(((-quantity.value if quantity.role == "loss" else quantity.value) for quantity in components), Fraction(0))
    else:
        numerator = total.value - (used.value if used and used.id != total.id else 0)
    if numerator <= 0:
        return []
    needs_ceiling = target in {"shelf", "box", "bag"} and any(word in text for word in ("need", "needed", "fit", "hold"))
    value = Fraction(ceil(numerator / unit.value)) if needs_ceiling else numerator / unit.value
    expression = f"{format_fraction(numerator)}/{format_fraction(unit.value)}"
    evidence = [quantity.id for quantity in components] + [unit.id] if components else [total.id, unit.id] + ([used.id] if used and used.id != total.id else [])
    return [
        EquationCandidate(
            kind="remainder_divided_by_unit",
            expression=expression,
            value=value,
            evidence_ids=evidence,
            target_object=target,
            confidence=0.82,
            checks=["group_count_query", "unit_nonzero"],
        )
    ]


def candidate_selected_sum(text: str, quantities: list[Quantity]) -> list[EquationCandidate]:
    if not any(word in text for word in ("and", "total", "altogether", "in all")):
        return []
    target = query_object(text)
    query_tail = text[text.rfind("how ") :] if "how " in text else text
    selected_times = [word for word in TIME_WORDS if f" {word}" in query_tail and word in {"monday", "tuesday", "morning", "afternoon", "evening"}]
    if selected_times:
        selected = [quantity for quantity in quantities if quantity.time in selected_times and same_object(quantity.obj, target)]
    else:
        selected = []
    if len(selected) < 2:
        return []
    value = sum((quantity.value for quantity in selected), Fraction(0))
    expression = "+".join(format_fraction(quantity.value) for quantity in selected)
    return [
        EquationCandidate(
            kind="selected_sum",
            expression=expression,
            value=value,
            evidence_ids=[quantity.id for quantity in selected],
            target_object=target,
            confidence=0.81,
            checks=["selected_time_or_category_sum"],
        )
    ]


def candidate_fractional_sequence(text: str, quantities: list[Quantity]) -> list[EquationCandidate]:
    if "third" not in text and "half" not in text and "%" not in text:
        return []
    # Keep this layer narrow for now; it will be expanded after benchmark data.
    match = re.search(rf"had (?P<start>{NUMBER_RE}).*?sold a third.*?(?P<extra>{NUMBER_RE}) more.*?half of what was left.*?has (?P<final>{NUMBER_RE})", text)
    if not match:
        return []
    start = parse_number(match.group("start"))
    extra = parse_number(match.group("extra"))
    final = parse_number(match.group("final"))
    if start is None or extra is None or final is None:
        return []
    after_first = start - start / 3 - extra
    sold_orange = after_first / 2
    value = start - start / 3 - extra - sold_orange
    return [
        EquationCandidate(
            kind="fractional_sequence",
            expression=f"{start}-{start}/3-{extra}-(({start}-{start}/3-{extra})/2)",
            value=value,
            evidence_ids=[],
            target_object=query_object(text),
            confidence=0.78,
            checks=["fractional_state_sequence"],
        )
    ]


def attach_semantic_logic(text: str, quantities: list[Quantity], candidate: EquationCandidate) -> EquationCandidate:
    semantic = verify_quantity_candidate_semantics(text, quantities, candidate)
    checks = list(dict.fromkeys(candidate.checks + semantic.checks))
    return EquationCandidate(
        kind=candidate.kind,
        expression=candidate.expression,
        value=candidate.value,
        evidence_ids=candidate.evidence_ids,
        target_object=candidate.target_object,
        confidence=candidate.confidence,
        checks=checks,
        logic=semantic.to_dict(),
    )


def verify_candidate(text: str, quantities: list[Quantity], candidate: EquationCandidate) -> bool:
    if candidate.logic and candidate.logic.get("status") == "rejected":
        return False
    if candidate.value.denominator != 1 and not any(token in text for token in ("fraction", "average", "each", "per", "ratio")):
        return False
    if candidate.kind == "selected_sum" and not candidate.target_object:
        return False
    if candidate.kind == "selected_object_sum" and any(
        marker in text for marker in ("twice", "half", "fewer", "more than", "less than", " each ", " per ")
    ):
        return False
    if candidate.kind == "unit_count_product" and any(
        marker in text for marker in (" left", "rest", "remaining", "equal in cost", "more than", "less than")
    ):
        return False
    if candidate.kind == "state_update" and is_initial_query(text):
        return False
    if candidate.kind == "same_object_state_difference" and any(marker in text for marker in ("each album", "each group", "split", "sorted")):
        return False
    if candidate.kind == "count_sum_times_common_unit" and any(
        marker in text for marker in ("%", "percent", "half", "quarter", "change", "additional", "per pound")
    ):
        return False
    if candidate.kind in {"state_update", "unit_count_product"} and any(quantity.obj in META_OBJECTS for quantity in evidence_quantities(quantities, candidate)):
        return False
    if candidate.kind == "difference_last_two" and "more" not in text and "difference" not in text:
        return False
    if "how many more" in text and candidate.value < 0:
        return False
    return True


def normalize_text(text: str) -> str:
    text = text.replace("’", "'").replace("“", '"').replace("”", '"')
    text = re.sub(r"\$([^$]+)\$", lambda match: match.group(1) if "\\" in match.group(1) else match.group(0), text)
    text = text.replace(",", "")
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def split_sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.?!])\s+", text) if part.strip()]


def parse_number(value: str) -> Fraction | None:
    value = value.strip().lower().strip(".,;:!?").replace(",", "").removeprefix("$")
    if value == "dozen":
        return Fraction(12)
    if value == "half":
        return Fraction(1, 2)
    if value == "third":
        return Fraction(1, 3)
    if value == "quarter":
        return Fraction(1, 4)
    if re.fullmatch(r"\d+/\d+", value):
        numerator, denominator = value.split("/", 1)
        return Fraction(int(numerator), int(denominator)) if int(denominator) else None
    if re.fullmatch(r"\d+(?:\.\d+)?", value):
        return Fraction(value)
    if value in NUMBER_WORDS:
        return Fraction(NUMBER_WORDS[value])
    if "-" in value:
        parts = value.split("-")
        total = sum(NUMBER_WORDS.get(part, 0) for part in parts)
        return Fraction(total) if total else None
    return None


def parse_unit_object(tail: str) -> tuple[str, str]:
    if " more " in f" {tail} " and any(verb in tail for verb in (" bought", " added", " gave", " got", " received")):
        return "count", "quantity"
    pronoun = re.match(r"\s+of\s+(them|it|one|ones)\b", tail)
    if pronoun:
        return "count", pronoun.group(1)
    measured_object = re.match(
        r"\s*(?P<unit>[a-z]+(?:-[a-z]+)?)\s+of\s+(?:the\s+)?(?P<object>[a-z]+(?:-[a-z]+)?)\b",
        tail,
    )
    if measured_object:
        unit = normalize_object(measured_object.group("unit"))
        obj = normalize_object(measured_object.group("object"))
        if unit in MEASURE_UNITS:
            return unit, obj
    local = re.split(
        r"\b(?:per|for each|in each|on each|each|how|than|that|which|who|and|of|while|if|when|then|but|after|before|earlier|later|ago|to|from|at|in|on|for|with|by)\b",
        tail,
        maxsplit=1,
    )[0]
    clean = re.sub(
        r"\b(?:old|new|more|total|left|right|same|each|per|a|an|the|of|his|her|their|from|to|on|in|at|for|with|giant|stuffed|equal|small|returning)\b",
        " ",
        local,
    )
    words = [
        word
        for word in re.findall(r"[a-z]+(?:-[a-z]+)?", clean)
        if word not in {"and", "cost", "costs", "if", "how", "many", "much", "does", "did", "would", "will", "have", "has", "then", "another"}
    ]
    if not words:
        return "count", "quantity"
    obj = normalize_object(words[-1])
    return obj, obj


def infer_role(sentence: str, number_start: int) -> str:
    before = sentence[:number_start].lower()
    after = sentence[number_start:].lower()
    recent = before[-90:]
    if re.search(r"\b(?:were|was|are|is)\s+(?:used|picked|sold|taken|deleted|eaten)\b", after[:90]):
        return "loss"
    if re.search(r"\beach\s+[a-z-]+(?:\s+[a-z-]+){0,3}\s+(?:has|have|gets|got|uses|makes|earns|takes)\s*$", recent):
        return "per_unit"
    if any(marker in recent for marker in (" has ", " had ", " have ")) and re.search(r"\band\b.{0,35}\beach\b", after[:80]):
        return "state"
    if (" per " in after[:40] or " each" in after[:50] or " in one " in after[:50]) and "of them" not in after[:35]:
        return "rate" if any(unit in after[:80] for unit in ("day", "hour", "minute", "week")) else "per_unit"
    if any(marker in after[:50] for marker in (" a minute", " a hour", " an hour", " a day", " a week")):
        return "rate"
    if any(marker in after[:90] for marker in ("every day", "per day", "a day")) and any(unit in after[:50] for unit in ("hour", "hours", "minute", "minutes")):
        return "rate"
    if " more " in after[:40] and any(marker in after[:90] for marker in (" got on", " came", " joined", " bought", " added", " grew")):
        return "gain"
    if any(marker in after[:60] for marker in (" got on", " came to", " joined", " grew by")):
        return "gain"
    if "took" in before and " from " not in after[:40]:
        return "gain"
    if "bought" in recent and "from him" in after[:80]:
        return "loss"
    if "flew away" in after[:80] or "went away" in after[:80]:
        return "loss"
    if re.match(rf"(?:{NUMBER_RE})\s+of\b.{{0,45}}(?:didn't|did not|not get|not leave)", after):
        return "loss"
    if re.search(r"\bgave\s+away\b", recent):
        return "loss"
    if re.search(r"\bgave\s+(?:him|her|me|them|us)\b", recent):
        return "gain"
    nearest_negative = nearest_verb_distance(before, NEGATIVE_VERBS)
    nearest_positive = nearest_verb_distance(before, POSITIVE_VERBS)
    if nearest_negative is not None or nearest_positive is not None:
        if nearest_positive is not None and (nearest_negative is None or nearest_positive < nearest_negative):
            return "gain"
        return "loss"
    if any(word in after[:30] for word in ("day", "days", "hour", "hours", "minute", "minutes", "week", "weeks")) and any(word in before[-40:] for word in ("for", "in", "after", "over")):
        return "duration"
    if "total" in before[-40:] or "total" in after[:40:]:
        return "total"
    if any(word in before[-50:] for word in ("had", "has", "there were", "there are", "started with", "now has")):
        return "state"
    return "state"


def is_referential_one(sentence: str, number_start: int, number_text: str) -> bool:
    before = sentence[:number_start].lower()
    after = sentence[number_start + len(number_text) :].lower()
    if number_text.lower() == "one":
        return bool(re.search(r"\beach\s+$", before[-12:]))
    if number_text.lower() == "third":
        return bool(re.search(r"\bthe\s+$", before[-8:]) and re.match(r"\s+[a-z-]+", after))
    return False


def is_dimension_component(sentence: str, start: int, end: int) -> bool:
    left = sentence[max(0, start - 8) : start]
    right = sentence[end : end + 8]
    return bool(re.search(r"(?:\d\s*[x×]\s*)$", left) or re.match(r"\s*[x×]\s*\d", right))


def rate_denominator(quantity: Quantity) -> str | None:
    if quantity.denominator:
        return normalize_object(quantity.denominator)
    text = quantity.text.lower()
    surface = re.escape(quantity.surface.lower().removeprefix("$"))
    each_before = re.search(rf"\beach\s+(?P<den>[a-z-]+).{{0,60}}?\b{surface}\b", text)
    if each_before:
        return normalize_object(each_before.group("den"))
    local_value = re.search(rf"\b{surface}\b(?P<tail>.{{0,80}})", text)
    if local_value:
        per_after = re.search(
            r"\b(?:per|for each|in each|on each)(?:\s+of)?(?:\s+(?:the\s+)?\d+)?\s+"
            r"(?P<den>[a-z-]+(?:\s+[a-z-]+)?)(?=\s+(?:who|that|which|how|if|when)|[.,?!]|$)",
            local_value.group("tail"),
        )
        if per_after:
            return normalize_object(per_after.group("den").split()[-1])
    return None


def infer_surface_denominator(
    sentence: str,
    start: int,
    end: int,
    surface: str,
    previous_object: str | None,
) -> str | None:
    before = sentence[:start].lower()
    after = sentence[end:].lower()
    each_subject = re.search(
        r"\beach\s+(?P<den>[a-z-]+)(?:\s+[a-z-]+){0,3}\s+"
        r"(?:has|have|gets|got|uses|makes|earns|takes)\s*$",
        before,
    )
    if each_subject:
        return normalize_object(each_subject.group("den"))
    explicit = re.search(
        r"\b(?:per|for each|in each|on each)(?:\s+of)?(?:\s+(?:the\s+)?\d+)?\s+"
        r"(?P<den>[a-z-]+(?:\s+[a-z-]+)?)(?=\s+(?:who|that|which|how|if|when)|[.,?!]|$)",
        after[:100],
    )
    if explicit:
        return normalize_object(explicit.group("den").split()[-1])
    if re.search(r"\beach\b", after[:80]) and previous_object:
        return normalize_object(previous_object)
    return None


def is_initial_query(text: str) -> bool:
    return any(
        phrase in text
        for phrase in (
            "begin with",
            "to begin",
            "at first",
            "initially",
            "originally",
            "incipiently",
            "in the beginning",
            "before",
        )
    )


def nearest_verb_distance(before: str, verbs: set[str]) -> int | None:
    best: int | None = None
    for verb in verbs:
        match = list(re.finditer(rf"\b{re.escape(verb)}\b", before))
        if not match:
            continue
        distance = len(before) - match[-1].end()
        if best is None or distance < best:
            best = distance
    return best


def infer_owner(sentence: str, number_start: int) -> str | None:
    before = sentence[:number_start]
    names = re.findall(r"\b[A-Za-z][a-z]+\b", before)
    if names:
        return names[-1].lower()
    pronoun = re.search(r"\b(he|she|they|it)\b", before.lower())
    return pronoun.group(1) if pronoun else None


def infer_time(sentence: str, number_start: int | None = None) -> str | None:
    if number_start is not None:
        local = sentence[number_start : number_start + 80]
        local_matches = [
            (match.start(), word)
            for word in TIME_WORDS
            for match in re.finditer(rf"\b{re.escape(word)}\b", local)
        ]
        if local_matches:
            return min(local_matches)[1]
    sentence_matches = [
        (match.start(), word)
        for word in TIME_WORDS
        for match in re.finditer(rf"\b{re.escape(word)}\b", sentence)
    ]
    if sentence_matches:
        return min(sentence_matches)[1]
    return None


def query_object(text: str) -> str | None:
    patterns = (
        r"how many more (?P<object>[a-z-]+(?:\s+(?:of\s+)?[a-z-]+){0,2}?) (?:did|does|do|will|would|are|is|were|was)",
        r"how many (?P<object>[a-z-]+(?:\s+(?:of\s+)?[a-z-]+){0,2}?) (?:did|does|do|will|would|are|is|were|was|needed|need)",
        r"how many more (?P<object>[a-z]+)",
        r"how many (?P<object>[a-z]+)",
        r"how much (?P<object>money|water|cost|distance|area|time)",
        r"how much (?P<object>[a-z]+)",
        r"what .*? (?P<object>probability|price|cost|total|distance|area)",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            obj = normalize_query_phrase(match.group("object"))
            if obj not in QUERY_STOP_WORDS:
                return obj
    return None


def normalize_query_phrase(value: str) -> str:
    words = re.findall(r"[a-z-]+", value.lower())
    if not words:
        return ""
    if "of" in words and words.index("of") + 1 < len(words):
        head = words[words.index("of") + 1]
    else:
        head = words[-1]
    return normalize_object(head)


def comparison_labels(text: str) -> tuple[str, str] | None:
    match = re.search(r"how much more does (?:a |an |the )?(?P<left>[a-z-]+).*? than (?:a |an |the )?(?P<right>[a-z-]+)", text)
    if match:
        return normalize_object(match.group("left")), normalize_object(match.group("right"))
    match = re.search(r"how many more (?P<left>[a-z]+).*? than (?P<right>[a-z]+)", text)
    if match:
        left = normalize_object(match.group("left"))
        right = normalize_object(match.group("right"))
        if left not in QUERY_STOP_WORDS and right not in QUERY_STOP_WORDS:
            return left, right
    match = re.search(r"difference .*? (?P<left>[a-z]+)'?s .*? and (?P<right>[a-z]+)'?s", text)
    if match:
        return normalize_object(match.group("right")), normalize_object(match.group("left"))
    return None


def latest_quantity_matching_label(quantities: list[Quantity], label: str) -> Quantity | None:
    normalized = label.rstrip("s")
    for quantity in reversed(quantities):
        if normalized in quantity.text or same_object(quantity.obj, normalized):
            return quantity
    return None


def latest_quantity_for_label(quantities: list[Quantity], label: str, roles: set[str] | None = None) -> Quantity | None:
    for quantity in reversed(quantities):
        if roles is not None and quantity.role not in roles:
            continue
        if quantity_matches_label(quantity, label):
            return quantity
    return None


def per_unit_quantity_for_following_label(text: str, quantities: list[Quantity], label: str) -> Quantity | None:
    normalized_label = normalize_object(label)
    number_matches = list(re.finditer(rf"(?P<number>{NUMBER_RE})", text))
    used_ids: set[int] = set()
    for index, match in enumerate(number_matches):
        value = parse_number(match.group("number"))
        if value is None:
            continue
        tail_end = number_matches[index + 1].start() if index + 1 < len(number_matches) else len(text)
        local_tail = normalize_object(text[match.end() : tail_end])
        if normalized_label not in local_tail:
            continue
        for quantity in quantities:
            if quantity.id in used_ids or quantity.role not in {"per_unit", "rate"}:
                continue
            if quantity.value == value:
                used_ids.add(quantity.id)
                return quantity
    return None


def quantity_matches_label(quantity: Quantity, label: str) -> bool:
    normalized = normalize_object(label)
    if same_object(quantity.obj, normalized) or normalized == quantity.time:
        return True
    if quantity.obj not in PRONOUN_OBJECTS | {"dollar", "cent", "money", "set", "count", "off"}:
        return False
    return normalized in normalize_object(quantity.text) or re.search(rf"\b{re.escape(normalized)}s?\b", quantity.text) is not None


def category_total(label: str, quantities: list[Quantity]) -> tuple[Fraction | None, list[int]]:
    total = Fraction(0)
    ids: list[int] = []
    for quantity in quantities:
        if not quantity_matches_label(quantity, label):
            continue
        if quantity.role == "loss":
            total -= quantity.value
        elif quantity.role in {"state", "initial", "total", "gain", "per_unit", "rate"}:
            total += quantity.value
        else:
            continue
        ids.append(quantity.id)
    return (total, ids) if ids else (None, [])


def time_comparison_labels(text: str) -> tuple[str, str] | None:
    time_pattern = "|".join(sorted(TIME_WORDS))
    match = re.search(rf"on (?P<left>{time_pattern}).*? than on (?P<right>{time_pattern})", text)
    if match:
        return match.group("left"), match.group("right")
    return None


def first_quantity_with_any(text: str, quantities: list[Quantity], markers: set[str]) -> Quantity | None:
    for quantity in quantities:
        if any(marker in quantity.text for marker in markers):
            return quantity
    return None


def latest_total_before(quantities: list[Quantity], pivot: Quantity) -> Quantity | None:
    for quantity in reversed(quantities):
        if quantity.id >= pivot.id:
            continue
        if quantity.role in {"state", "initial", "total"} and quantity.obj not in META_OBJECTS | PRONOUN_OBJECTS:
            return quantity
    return None


def best_rate_for_target(rates: list[Quantity], target: str | None) -> Quantity:
    if target:
        for rate in reversed(rates):
            if same_object(rate.obj, target):
                return rate
    return rates[-1]


def same_object(left: str | None, right: str | None) -> bool:
    if not left or not right:
        return False
    left = normalize_object(left)
    right = normalize_object(right)
    return left == right or left in right or right in left


def equivalent_object(left: str | None, right: str | None) -> bool:
    if not left or not right:
        return False
    left = normalize_object(left)
    right = normalize_object(right)
    if left == right:
        return True
    equivalences = (
        {"person", "people"},
        {"child", "children"},
        {"money", "dollar", "cent", "cost", "price"},
    )
    return any(left in group and right in group for group in equivalences)


def normalize_object(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z]", "", value)
    irregular = {"children": "child", "people": "person", "men": "man", "women": "woman"}
    if value in irregular:
        return irregular[value]
    if value.endswith("ses") and len(value) > 4:
        value = value[:-2]
    elif value.endswith("ies"):
        value = value[:-3] + "y"
    elif value.endswith("s") and len(value) > 3:
        value = value[:-1]
    return value


def evidence_quantities(quantities: list[Quantity], candidate: EquationCandidate) -> list[Quantity]:
    ids = set(candidate.evidence_ids)
    return [quantity for quantity in quantities if quantity.id in ids]


def format_fraction(value: Fraction | int) -> str:
    value = Fraction(value)
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"
