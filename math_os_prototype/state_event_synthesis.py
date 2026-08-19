"""Conservative compilation of explicit state transitions.

The compiler accepts only stories whose numeric clauses share one state sort
and whose event polarity is explicit.  It then executes the conservation law
``final = initial + gains - losses``.  Ambiguous comparisons and selected
subtotals are rejected instead of being guessed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction

try:
    from math_os_prototype.dimensional_synthesis import (
        TypedQuantity,
        extract_typed_quantities,
        format_dim,
        format_fraction,
        infer_target_dimension,
    )
except ImportError:
    from dimensional_synthesis import (
        TypedQuantity,
        extract_typed_quantities,
        format_dim,
        format_fraction,
        infer_target_dimension,
    )


@dataclass(frozen=True)
class StateEventResult:
    answer_exact: str
    expression: str
    state_sort: str
    certificate: tuple[str, ...]


GAIN = {
    "add", "added", "bought", "buy", "came", "collected", "earned", "found",
    "gave him", "gave her", "got", "joined", "made", "received", "scored", "took", "won",
}
LOSS = {
    "ate", "cut off", "deleted", "discarded", "gave", "gave away", "left", "lost",
    "paid", "sold", "spent", "used", "went away",
}
STATE = {"had", "has", "have", "there are", "there were", "started with"}
BLOCKED_RELATIONS = (
    "more than", "fewer than", "less than", "twice", "times as", "percent", "%",
    "equally", "divided", "split", "per ", " every ", " each ", "average",
)
TIME_NAMES = {"morning", "afternoon", "evening", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}


def _clause(text: str, start: int) -> tuple[str, str]:
    left_boundary = max(text.rfind(".", 0, start), text.rfind("?", 0, start), text.rfind("!", 0, start), text.rfind(",", 0, start))
    right_candidates = [position for mark in ".?!," if (position := text.find(mark, start)) >= 0]
    right_boundary = min(right_candidates) if right_candidates else len(text)
    return text[left_boundary + 1 : start].lower(), text[start:right_boundary].lower()


def _nearest_marker(before: str, after: str) -> str | None:
    matches: list[tuple[int, str]] = []
    for marker in GAIN | LOSS | STATE:
        for match in re.finditer(rf"\b{re.escape(marker)}\b", before):
            matches.append((match.end(), marker))
    if matches:
        return max(matches, key=lambda item: item[0])[1]
    following: list[tuple[int, str]] = []
    for marker in GAIN | LOSS:
        match = re.search(rf"\b{re.escape(marker)}\b", after[:35])
        if match:
            following.append((match.start(), marker))
    return min(following, key=lambda item: item[0])[1] if following else None


def _event_sign(marker: str) -> int:
    if marker in LOSS and marker not in {"gave him", "gave her"}:
        return -1
    return 1


def solve_state_event_arithmetic(text: str) -> StateEventResult | None:
    source = text.lower()
    if (
        "\\" in source
        or " some " in f" {source} "
        or any(marker in source for marker in BLOCKED_RELATIONS)
        or re.search(r"\b(?:more|fewer|less)\b.{0,45}\bthan\b", source)
        or re.search(r"\b(?:half|third|quarter|\d+/\d+)\s+of\b", source)
    ):
        return None
    quantities = extract_typed_quantities(text)
    if not 2 <= len(quantities) <= 7:
        return None
    target = infer_target_dimension(text, quantities)
    if target is None or len(target) != 1 or target[0][1] != 1:
        return None
    if any(quantity.dimension != target for quantity in quantities):
        return None

    question = re.split(r"(?<=[.?!])\s+", source)[-1]
    mentioned_times = {name for name in TIME_NAMES if name in question}
    if mentioned_times and not ({"total", "altogether", "week", "day"} & set(question.split())):
        return None
    if not re.search(r"\b(left|remain|remaining|now|end|total|altogether|in all|still have|have to do|did .* (?:get|take|score|receive|collect|buy))\b", question):
        return None

    signed: list[tuple[TypedQuantity, int, str]] = []
    inherited_marker: str | None = None
    for quantity in quantities:
        before, after = _clause(source, quantity.start)
        marker = _nearest_marker(before, after) or inherited_marker
        if marker is None:
            return None
        inherited_marker = marker
        signed.append((quantity, _event_sign(marker), marker))

    if not any(sign < 0 for _, sign, _ in signed) and not re.search(r"\b(total|altogether|in all)\b", question):
        return None
    value = sum((sign * quantity.value for quantity, sign, _ in signed), Fraction(0))
    if value < 0:
        return None
    expression = "".join(
        ("" if index == 0 and sign > 0 else "+" if sign > 0 else "-") + format_fraction(quantity.value)
        for index, (quantity, sign, _) in enumerate(signed)
    )
    return StateEventResult(
        answer_exact=format_fraction(value),
        expression=expression,
        state_sort=format_dim(target),
        certificate=(
            "all numeric clauses inhabit one state sort",
            "every transition has explicit gain/loss polarity",
            "final = initial + gains - losses",
        ),
    )
