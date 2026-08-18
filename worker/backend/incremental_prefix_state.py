"""Generic prefix-stable state cache for finite symbolic search paths."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Callable, Generic, Hashable, Sequence, TypeVar


StateT = TypeVar("StateT")
StepT = TypeVar("StepT")


@dataclass(frozen=True)
class PrefixStateCacheAudit:
    cached_state_count: int
    cache_hits: int
    cache_misses: int
    transition_count: int
    transition_seconds: float


class PrefixStateCache(Generic[StateT, StepT]):
    """Memoize immutable search prefixes while transitions clone their parent."""

    def __init__(
        self,
        base_state: StateT,
        *,
        key: Callable[[StepT], Hashable],
        transition: Callable[[StateT, StepT, tuple[StepT, ...]], StateT],
    ) -> None:
        self._key = key
        self._transition = transition
        self._states: dict[tuple[Hashable, ...], StateT] = {(): base_state}
        self._hits = 0
        self._misses = 0
        self._transitions = 0
        self._transition_seconds = 0.0

    def build(self, steps: Sequence[StepT]) -> StateT:
        path = tuple(steps)
        signature = tuple(self._key(step) for step in path)
        cached = self._states.get(signature)
        if cached is not None:
            self._hits += 1
            return cached
        self._misses += 1
        parent = self.build(path[:-1])
        started = perf_counter()
        state = self._transition(parent, path[-1], path)
        self._transition_seconds += perf_counter() - started
        self._transitions += 1
        self._states[signature] = state
        return state

    @property
    def audit(self) -> PrefixStateCacheAudit:
        return PrefixStateCacheAudit(
            cached_state_count=len(self._states),
            cache_hits=self._hits,
            cache_misses=self._misses,
            transition_count=self._transitions,
            transition_seconds=self._transition_seconds,
        )


def replay_prefix_state(
    base_state: StateT,
    steps: Sequence[StepT],
    *,
    transition: Callable[[StateT, StepT, tuple[StepT, ...]], StateT],
) -> StateT:
    state = base_state
    path = tuple(steps)
    for index, step in enumerate(path):
        state = transition(state, step, path[: index + 1])
    return state
