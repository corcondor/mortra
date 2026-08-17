"""Select exact-geometry obligations for finite degeneracy experiments."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


def conditional_goal_proved(result: Mapping[str, Any]) -> bool:
    """Return the exact eliminator verdict, with legacy artifact fallback."""

    exact = result.get("result")
    if isinstance(exact, Mapping) and "conditional_goal_proved" in exact:
        return bool(exact["conditional_goal_proved"])

    coordination = result.get("coordination")
    return bool(
        isinstance(coordination, Mapping)
        and coordination.get("conditional_goal_solved", False)
    )


def open_regularity_count(result: Mapping[str, Any]) -> int:
    """Read the number of unresolved non-degeneracy obligations."""

    coordination = result.get("coordination")
    if isinstance(coordination, Mapping):
        value = coordination.get("open_regularity_count")
        if value is not None:
            return int(value)

    exact = result.get("result")
    if isinstance(exact, Mapping):
        conditions = exact.get("open_regularity_conditions", ())
        if isinstance(conditions, (list, tuple)):
            return len(conditions)
        value = exact.get("open_regularity_count")
        if value is not None:
            return int(value)
    return 0


def eligible_conditional_names(
    baseline: Mapping[str, Any],
    requested: Iterable[str],
) -> tuple[str, ...]:
    """Select completed exact proofs that still require finite case splitting."""

    results = baseline["results"]
    return tuple(
        name
        for name in requested
        if name in results
        and results[name].get("status") == "completed"
        and conditional_goal_proved(results[name])
        and open_regularity_count(results[name]) > 0
    )
