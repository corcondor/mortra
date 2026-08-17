"""Typed relation channels shared by symbolic geometry agents.

The adapter preserves domain relation names instead of collapsing every proof
state to one scalar closure size.  Numerical scores are search controls only;
proof acceptance remains the responsibility of each native verifier.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping


RELATION_ALIASES: dict[str, str] = {
    "coll": "coll",
    "collinear": "coll",
    "perp": "perp",
    "perpendicular": "perp",
    "para": "para",
    "parallel": "para",
    "cyclic": "cyclic",
    "cong": "cong",
    "same_length": "cong",
    "eqangle": "eqangle",
    "equal_angle": "eqangle",
    "eqratio": "eqratio",
    "harmonic": "eqratio",
}


@dataclass(frozen=True)
class RelationChannelMetrics:
    target_assertion_count: int
    target_support_weight: int
    near_goal_assertion_count: int
    transition_potential: float
    transition_channel_coverage: int
    channel_counts: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class RelationStalkSection:
    agent: str
    channel: str
    support: tuple[str, ...]
    proof_reference: str


@dataclass(frozen=True)
class RelationFrontierWitness:
    """A novel native deduction that lies on a channel path to the goal."""

    channel: str
    points: tuple[str, ...]
    support: tuple[str, ...]
    distance_to_goal: int
    goal_support_overlap: int
    rule: str
    proof_reference: str


def canonical_relation(name: str) -> str:
    normalized = name.strip().lower()
    return RELATION_ALIASES.get(normalized, normalized)


AssertionKey = tuple[str, tuple[str, ...]]


def _deduction_assertions(
    payload: Mapping[str, Any],
) -> Iterable[tuple[Mapping[str, Any], Mapping[str, Any]]]:
    deductions = payload.get("all_deductions", ())
    if not isinstance(deductions, list):
        return
    for deduction in deductions:
        if not isinstance(deduction, Mapping):
            continue
        assertions = deduction.get("assertions", ())
        if not isinstance(assertions, list):
            continue
        for assertion in assertions:
            if isinstance(assertion, Mapping):
                yield deduction, assertion


def assertion_key(assertion: Mapping[str, Any]) -> AssertionKey:
    """Return a stable key without imposing false symmetries on relations."""

    return (
        canonical_relation(str(assertion.get("name", ""))),
        tuple(str(point).lower() for point in assertion.get("points", ())),
    )


def yuclid_assertion_keys(payload: Mapping[str, Any]) -> set[AssertionKey]:
    return {
        assertion_key(assertion)
        for _, assertion in _deduction_assertions(payload)
    }


def backward_relation_distances(
    rule_channels: Iterable[tuple[Iterable[str], Iterable[str]]],
    *,
    goal_channels: set[str],
    max_distance: int = 6,
) -> dict[str, int]:
    """Compute which relation channels can feed a goal through native rules."""

    rules = [
        (
            {canonical_relation(name) for name in premises},
            {canonical_relation(name) for name in conclusions},
        )
        for premises, conclusions in rule_channels
    ]
    distances = {canonical_relation(channel): 0 for channel in goal_channels}
    frontier = set(distances)
    for distance in range(1, max_distance + 1):
        next_frontier: set[str] = set()
        for premises, conclusions in rules:
            if conclusions & frontier:
                for premise in premises:
                    if premise not in distances:
                        distances[premise] = distance
                        next_frontier.add(premise)
        if not next_frontier:
            break
        frontier = next_frontier
    return distances


def yuclid_relation_metrics(
    payload: Mapping[str, Any],
    *,
    goal_channels: set[str],
    goal_support: set[str],
    excluded_assertion_keys: set[AssertionKey] | None = None,
    exclude_direct_construction: bool = False,
    transition_distances: Mapping[str, int] | None = None,
) -> RelationChannelMetrics:
    channels = {canonical_relation(channel) for channel in goal_channels}
    counts: Counter[str] = Counter()
    target_count = 0
    support_weight = 0
    near_goal_count = 0
    transition_potential = 0.0
    transition_channels: set[str] = set()
    near_threshold = max(1, len(goal_support) - 1)
    excluded = excluded_assertion_keys or set()
    normalized_goal_support = {point.lower() for point in goal_support}
    for deduction, assertion in _deduction_assertions(payload):
        channel = canonical_relation(str(assertion.get("name", "")))
        counts[channel] += 1
        if assertion_key(assertion) in excluded:
            continue
        if (
            exclude_direct_construction
            and str(deduction.get("newclid_rule", "")).strip().lower()
            == "by construction"
        ):
            continue
        if transition_distances is not None and channel in transition_distances:
            distance = transition_distances[channel]
            transition_potential += 1.0 / (distance + 1.0)
            transition_channels.add(channel)
        if channel not in channels:
            continue
        target_count += 1
        points = {str(point).lower() for point in assertion.get("points", ())}
        overlap = len(points & normalized_goal_support)
        support_weight += overlap * overlap
        if overlap >= near_threshold:
            near_goal_count += 1
    return RelationChannelMetrics(
        target_count,
        support_weight,
        near_goal_count,
        transition_potential,
        len(transition_channels),
        tuple(sorted(counts.items())),
    )


def yuclid_relation_frontier(
    payload: Mapping[str, Any],
    *,
    goal_support: set[str],
    transition_distances: Mapping[str, int],
    excluded_assertion_keys: set[AssertionKey] | None = None,
    exclude_direct_construction: bool = True,
    limit: int = 8,
) -> tuple[RelationFrontierWitness, ...]:
    """Extract the closest replayable intermediate relations to an open goal.

    This is a search-control boundary, not a proof rule.  Every witness comes
    from Yuclid's native deduction payload and remains tied to a content hash.
    """

    excluded = excluded_assertion_keys or set()
    normalized_goal_support = {point.lower() for point in goal_support}
    witnesses: dict[AssertionKey, RelationFrontierWitness] = {}
    for deduction, assertion in _deduction_assertions(payload):
        key = assertion_key(assertion)
        channel = key[0]
        if key in excluded or channel not in transition_distances:
            continue
        rule = str(deduction.get("newclid_rule", "")).strip()
        if exclude_direct_construction and rule.lower() == "by construction":
            continue
        raw_support = deduction.get("point_deps", ())
        if isinstance(raw_support, str):
            support = tuple(sorted({item.lower() for item in raw_support.split() if item}))
        elif isinstance(raw_support, (list, tuple)):
            support = tuple(sorted({str(item).lower() for item in raw_support if str(item)}))
        else:
            support = ()
        points = key[1]
        effective_support = set(points) | set(support)
        overlap = len(effective_support & normalized_goal_support)
        material = json.dumps(
            {"deduction": deduction, "assertion": assertion},
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
        witness = RelationFrontierWitness(
            channel=channel,
            points=points,
            support=support,
            distance_to_goal=int(transition_distances[channel]),
            goal_support_overlap=overlap,
            rule=rule or "native",
            proof_reference=hashlib.sha256(material.encode("utf-8")).hexdigest(),
        )
        previous = witnesses.get(key)
        if previous is None or (
            witness.distance_to_goal,
            -witness.goal_support_overlap,
            len(witness.support),
            witness.rule,
        ) < (
            previous.distance_to_goal,
            -previous.goal_support_overlap,
            len(previous.support),
            previous.rule,
        ):
            witnesses[key] = witness
    ranked = sorted(
        witnesses.values(),
        key=lambda item: (
            item.distance_to_goal,
            -item.goal_support_overlap,
            len(set(item.support) - normalized_goal_support),
            item.channel,
            item.points,
            item.rule,
        ),
    )
    return tuple(ranked[: max(0, limit)])


def _gclc_prove_block(source: str) -> str:
    active_lines = [
        line.strip()
        for line in source.splitlines()
        if line.strip() and not line.lstrip().startswith("%")
    ]
    for index, line in enumerate(active_lines):
        if re.search(r"\bprove\b", line):
            return " ".join(active_lines[index:])
    return ""


def gclc_goal_channel(source: str) -> str | None:
    prove = _gclc_prove_block(source)
    match = re.search(r"\bprove\s*\{\s*([A-Za-z_][A-Za-z0-9_]*)", prove)
    if not match:
        return None
    head = match.group(1).lower()
    if head != "equal":
        return canonical_relation(head)
    if "sratio" in prove or "ratio" in prove:
        return "eqratio"
    if "segment" in prove:
        return "cong"
    if "angle" in prove:
        return "eqangle"
    return "algebraic_equal"


def gclc_goal_section(path: Path, *, proof_reference: str) -> RelationStalkSection | None:
    source = path.read_text(encoding="utf-8", errors="replace")
    channel = gclc_goal_channel(source)
    if channel is None:
        return None
    active = _gclc_prove_block(source)
    tokens = re.findall(r"\b[A-Z][A-Za-z0-9_]*\b", active)
    return RelationStalkSection("gclc", channel, tuple(sorted(set(tokens))), proof_reference)


def sections_compatible(left: RelationStalkSection, right: RelationStalkSection) -> bool:
    return left.channel == right.channel and bool(set(left.support) & set(right.support))
