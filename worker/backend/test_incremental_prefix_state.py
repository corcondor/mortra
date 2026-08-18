from worker.backend.incremental_prefix_state import (
    PrefixStateCache,
    replay_prefix_state,
)


def _append(
    state: tuple[tuple[str, tuple[str, ...]], ...],
    step: str,
    path: tuple[str, ...],
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    return (*state, (step, path))


def test_incremental_cache_matches_full_prefix_replay() -> None:
    steps = ("a", "b", "c")
    cache = PrefixStateCache((), key=lambda step: step, transition=_append)

    assert cache.build(steps) == replay_prefix_state(
        (), steps, transition=_append
    )


def test_shared_parent_is_constructed_once() -> None:
    cache = PrefixStateCache((), key=lambda step: step, transition=_append)

    cache.build(("a", "b"))
    cache.build(("a", "c"))
    cache.build(("a", "b"))

    assert cache.audit.transition_count == 3
    assert cache.audit.cache_hits >= 2
    assert cache.audit.cached_state_count == 4
