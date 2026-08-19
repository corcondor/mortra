"""Pure control-plane helpers for typed HAGeo construction search."""

from __future__ import annotations

import math
import random
from typing import Any, Sequence, TypeVar


T = TypeVar("T")


def candidate_pool(
    extensions: Sequence[T],
    audit: dict[str, Any],
    *,
    hard_incidence_gate: bool,
    preserve_family_frontier: bool = False,
    family_order: Sequence[str] = (),
) -> list[T]:
    """Keep numerical incidence advisory unless a control ablation requests a gate."""

    profiles = {
        item["step_key"]: item
        for item in audit["numerical_incidence"].get("selected_candidates", [])
    }
    executable = [step for step in extensions if getattr(step, "key") in profiles]
    heuristic = [
        step
        for step in executable
        if profiles[getattr(step, "key")].get("is_heuristic_candidate")
    ]
    if hard_incidence_gate:
        return heuristic or executable
    if not preserve_family_frontier:
        return executable

    representative_by_family: dict[str, T] = {}
    for step in executable:
        family = str(getattr(step, "family"))
        if family not in representative_by_family:
            representative_by_family[family] = step
    ordered_families = list(dict.fromkeys(family_order))
    ordered_families.extend(
        family for family in representative_by_family if family not in ordered_families
    )
    representatives = [
        representative_by_family[family]
        for family in ordered_families
        if family in representative_by_family
    ]
    ordered: list[T] = []
    seen: set[str] = set()
    width = max(len(executable), len(representatives))
    for index in range(width):
        for values in (executable, representatives):
            if index >= len(values):
                continue
            step = values[index]
            key = str(getattr(step, "key"))
            if key in seen:
                continue
            seen.add(key)
            ordered.append(step)
    return ordered


def proof_residual_order_key(value: dict[str, Any]) -> tuple[float, ...]:
    """Order proof states without consulting an answer or problem identifier."""

    return (
        float(-value["ar_closed_goals"]),
        float(value["ar_residual_support"]),
        float(value["ar_residual_l1"]),
        float(-value["ar_known_rank"]),
        float(value["backward_obligations"]),
        float(value["open_relation_demands"]),
    )


def rank_biased_shortlist(
    pool: Sequence[T],
    *,
    count: int,
    rng: random.Random,
    temperature: float,
    trajectory_index: int = 0,
) -> list[tuple[int, T]]:
    """Draw a ranked subset with disjoint low-index strata across trajectories."""

    if count <= 0:
        return []
    available = list(enumerate(pool))
    if trajectory_index > 0 and len(available) > 1:
        tail = available[1:]
        start = ((trajectory_index - 1) * count) % len(tail)
        available = tail[start:] + tail[:start]
    if temperature <= 0 or trajectory_index > 0:
        return available[:count]
    selected: list[tuple[int, T]] = []
    continuation = math.exp(-1.0 / temperature)
    while available and len(selected) < count:
        weights = [continuation**rank for rank, _ in available]
        position = rng.choices(range(len(available)), weights=weights, k=1)[0]
        selected.append(available.pop(position))
    return selected
