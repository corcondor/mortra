"""Shared CLI contracts for the geometry proof backend stack."""

from __future__ import annotations

import time


EXACT_SPECIALIST_REPRESENTATIONS = (
    "explicit",
    "relational",
    "local_relational",
    "goal_local_relational",
    "typed_relation_separator",
    "construction_block_dag",
)


def remaining_stage_seconds(
    deadline: float,
    *,
    now: float | None = None,
) -> float:
    """Return a non-negative remaining wall-clock budget for one stage."""

    observed = time.perf_counter() if now is None else now
    return max(0.0, deadline - observed)
