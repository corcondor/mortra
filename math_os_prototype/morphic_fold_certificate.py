"""Compile existing fold-summary composition into a polynomial proof model."""

from __future__ import annotations

from collections import deque
from fractions import Fraction
from functools import lru_cache

import sympy as sp

from math_os_prototype.finite_polynomial_orbit import PolynomialOrbit, certify_recurrence
from math_os_prototype.rigid_fold_problem_discovery import (
    FOLD_GENERATORS, GENERATOR_BY_SYMBOL, IDENTITY_FRAME, FoldWordSummary,
    UniformFoldSubstitution, _compose_frames, _summarize_single_generator,
    apply_fold_generator, compose_fold_word_summaries,
)

FIELDS = ("N", "dx", "dy", "dz", "sx", "sy", "sz", "Q", "cx", "cy", "cz")


def _normal_axis(frame: tuple) -> int:
    return next(axis for axis, coordinate in enumerate(frame[2]) if coordinate)


def _axis_representatives() -> tuple:
    representatives = {}
    queue = deque([IDENTITY_FRAME])
    seen = {IDENTITY_FRAME}
    while queue and len(representatives) < 3:
        frame = queue.popleft()
        representatives.setdefault(_normal_axis(frame), frame)
        for generator in FOLD_GENERATORS:
            target, _center = apply_fold_generator(frame, (0, 0, 0), generator)
            if target not in seen:
                queue.append(target)
                seen.add(target)
    return tuple(representatives[axis] for axis in range(3))


def _components(summary: FoldWordSummary) -> tuple:
    counts = [0, 0, 0]
    for frame, count in summary.panel_frame_counts:
        counts[_normal_axis(frame)] += count
    return (
        summary.step_count, *summary.doubled_end_center, *summary.doubled_center_sum,
        summary.doubled_center_squared_sum, *counts,
    )


@lru_cache(maxsize=32)
def compile_morphic_fold(substitution: UniformFoldSubstitution, maximum_phases: int = 4096):
    """Discover the exact orientation cycle, then use the existing composition."""
    if len(substitution.images) != len(FOLD_GENERATORS):
        raise ValueError("one image per fold generator is required")
    symbols = tuple(GENERATOR_BY_SYMBOL)
    initial_summaries = tuple(_summarize_single_generator(GENERATOR_BY_SYMBOL[s]) for s in symbols)
    frames = tuple(summary.end_frame for summary in initial_summaries)
    seen = {}
    schedule = []
    while frames not in seen:
        if len(schedule) >= maximum_phases:
            raise ValueError("orientation cycle not found within phase budget")
        seen[frames] = len(schedule)
        schedule.append(frames)
        frames = tuple(
            _compose_frames(frames[symbols.index(left)], frames[symbols.index(right)])
            for left, right in substitution.images
        )
    cycle_start = seen[frames]
    variables = tuple(sp.Symbol(f"{symbol}_{field}") for symbol in symbols for field in FIELDS)
    representatives = _axis_representatives()
    updates = []
    for phase_frames in schedule:
        symbolic = {}
        for index, symbol in enumerate(symbols):
            values = variables[index * len(FIELDS):(index + 1) * len(FIELDS)]
            symbolic[symbol] = FoldWordSummary(
                values[0], phase_frames[index], tuple(values[1:4]), tuple(values[4:7]),
                values[7], tuple(zip(representatives, values[8:11], strict=True)),
            )
        composed = tuple(
            compose_fold_word_summaries(symbolic[left], symbolic[right])
            for left, right in substitution.images
        )
        updates.append(tuple(sp.expand(value) for summary in composed for value in _components(summary)))
    model = PolynomialOrbit(
        variables, tuple(updates),
        tuple(Fraction(value) for summary in initial_summaries for value in _components(summary)),
        cycle_start,
    )
    return model, tuple(schedule)


def fold_observation(model: PolynomialOrbit, observable: str, seed_symbol: str = "A") -> sp.Expr:
    """Compatibility expressions for the old, explicitly fixed question catalog."""
    if seed_symbol not in GENERATOR_BY_SYMBOL:
        raise ValueError("unknown seed symbol")
    offset = tuple(GENERATOR_BY_SYMBOL).index(seed_symbol) * len(FIELDS)
    values = dict(zip(FIELDS, model.variables[offset:offset + len(FIELDS)], strict=True))
    if observable == "endpoint_distance_second":
        return sum(values[field] ** 2 for field in ("dx", "dy", "dz")) / 4
    if observable == "endpoint_height_second":
        return values["dz"] ** 2 / 4
    if observable == "panel_center_distance_second_sum":
        return values["Q"] / 4
    if observable == "horizontal_panel_counts":
        return values["cz"] + 1
    if observable == "parallel_panel_pair_counts":
        counts = (values["cx"], values["cy"], values["cz"] + 1)
        return sum(count * (count - 1) / 2 for count in counts)
    raise ValueError(f"unsupported legacy observation: {observable}")


def certify_morphic_recurrence(substitution, observable, recurrence, seed_symbol="A") -> dict:
    model, schedule = compile_morphic_fold(substitution)
    certificate = certify_recurrence(
        model, fold_observation(model, observable, seed_symbol),
        recurrence.coefficients, start_index=recurrence.start_index,
    )
    certificate["orientation_schedule"] = schedule
    certificate["orientation_cycle_start"] = model.cycle_start
    certificate["substitution"] = substitution.notation
    certificate["seed_symbol"] = seed_symbol
    return certificate
