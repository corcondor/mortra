"""Discover exact problems from a finite vocabulary of rigid square folds.

The four letters are serialization only.  Each letter selects one of two
boundary hinges of the current unit square and one of the two quarter-turn
directions.  The geometry is expressed entirely by frame changes, translation,
inner products, and polynomial observations.

Coordinates are doubled.  Thus every panel centre and corner stays integral,
while the physical coordinates are obtained by dividing by two.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from fractions import Fraction
from itertools import product
from math import comb, log1p
from typing import Iterable, Literal, Mapping, Sequence

from math_os_prototype.typed_substitution_grammar import (
    UniformSubstitutionGrammar,
    expand_emitted_tokens,
    iterate_emitted_summaries,
)


Vec3 = tuple[int, int, int]
Frame3 = tuple[Vec3, Vec3, Vec3]
Monomial = tuple[int, int, int]
AttachmentEdge = Literal["u", "v"]

IDENTITY_FRAME: Frame3 = ((1, 0, 0), (0, 1, 0), (0, 0, 1))


@dataclass(frozen=True)
class FoldGenerator:
    symbol: str
    attachment_edge: AttachmentEdge
    fold_sign: int

    @property
    def mountain_valley(self) -> str:
        return "M" if self.fold_sign > 0 else "V"


FOLD_GENERATORS: tuple[FoldGenerator, ...] = (
    FoldGenerator("A", "u", 1),
    FoldGenerator("C", "u", -1),
    FoldGenerator("G", "v", 1),
    FoldGenerator("T", "v", -1),
)
GENERATOR_BY_SYMBOL = {generator.symbol: generator for generator in FOLD_GENERATORS}


@dataclass(frozen=True)
class SquarePanel:
    index: int
    incoming_symbol: str | None
    doubled_center: Vec3
    frame: Frame3
    doubled_corners: tuple[Vec3, Vec3, Vec3, Vec3]


@dataclass(frozen=True)
class FoldChain:
    word: str
    panels: tuple[SquarePanel, ...]
    proper_intersection_pairs: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class CollisionFreeFoldSearchResult:
    """A deterministic beam-search result with exact geometric certificates."""

    chain: FoldChain
    beam_width: int
    explored_candidate_count: int
    rejected_intersection_count: int
    distinct_orientation_count: int
    distinct_center_count: int
    doubled_extents: Vec3
    scatter_area_isotropy: float
    scatter_volume_isotropy: float
    generator_counts: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class UniformFoldSubstitution:
    """Compatibility wrapper for the four-terminal rigid-fold adapter."""

    images: tuple[tuple[str, str], tuple[str, str], tuple[str, str], tuple[str, str]]

    def __post_init__(self) -> None:
        self.grammar

    @property
    def grammar(self) -> UniformSubstitutionGrammar:
        return UniformSubstitutionGrammar(tuple(GENERATOR_BY_SYMBOL), self.images)

    def image(self, symbol: str) -> tuple[str, str]:
        return self.grammar.image(symbol)  # type: ignore[return-value]

    @property
    def notation(self) -> tuple[str, ...]:
        return tuple(
            f"{symbol}->{''.join(self.image(symbol))}"
            for symbol in self.grammar.alphabet
        )


@dataclass(frozen=True)
class MorphicFoldSearchResult:
    """A collision-free fold chain encoded by a short uniform substitution."""

    substitution: UniformFoldSubstitution
    seed_symbol: str
    generation_count: int
    chain: FoldChain
    examined_substitution_count: int
    collision_free_substitution_count: int
    distinct_orientation_count: int
    distinct_center_count: int
    doubled_extents: Vec3
    scatter_area_isotropy: float
    scatter_volume_isotropy: float
    generator_counts: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class FoldWordSummary:
    """Exact affine and second-moment summary of an arbitrarily long fold word."""

    step_count: int
    end_frame: Frame3
    doubled_end_center: Vec3
    doubled_center_sum: Vec3
    doubled_center_squared_sum: int
    panel_frame_counts: tuple[tuple[Frame3, int], ...]


@dataclass(frozen=True)
class MorphicFoldObservables:
    generations: tuple[int, ...]
    step_counts: tuple[int, ...]
    endpoint_distance_second: tuple[Fraction, ...]
    endpoint_height_second: tuple[Fraction, ...]
    panel_center_distance_second_sum: tuple[Fraction, ...]
    horizontal_panel_counts: tuple[int, ...]
    parallel_panel_pair_counts: tuple[int, ...]


@dataclass(frozen=True)
class _FoldSearchNode:
    word: str
    frame: Frame3
    center: Vec3
    panels: tuple[SquarePanel, ...]
    visited_frames: frozenset[Frame3]
    visited_centers: frozenset[Vec3]
    minimum: Vec3
    maximum: Vec3
    coordinate_sums: Vec3
    coordinate_products: tuple[int, int, int, int, int, int]
    generator_counts: tuple[int, int, int, int]
    score: float


@dataclass(frozen=True)
class PolynomialMomentSequences:
    maximum_degree: int
    reachable_orientation_counts: tuple[int, ...]
    word_counts: tuple[int, ...]
    doubled_distance_second: tuple[int, ...]
    doubled_vertical_second: tuple[int, ...]
    doubled_distance_fourth: tuple[int, ...]
    doubled_vertical_fourth: tuple[int, ...]
    doubled_normal_offset_fourth: tuple[int, ...]
    projected_area_square: tuple[int, ...]


@dataclass(frozen=True)
class LinearRecurrence:
    """a[n+k] = sum(coefficients[i] * a[n+i], i=0..k-1)."""

    coefficients: tuple[Fraction, ...]
    start_index: int = 0

    @property
    def order(self) -> int:
        return len(self.coefficients)

    def holds(self, sequence: Sequence[Fraction]) -> bool:
        k = self.order
        return all(
            sequence[index + k]
            == sum(self.coefficients[offset] * sequence[index + offset] for offset in range(k))
            for index in range(self.start_index, len(sequence) - k)
        )


@dataclass(frozen=True)
class ExponentialPolynomialTerm:
    root: int
    polynomial_coefficients: tuple[Fraction, ...]

    def evaluate(self, n: int) -> Fraction:
        polynomial = sum(value * n**degree for degree, value in enumerate(self.polynomial_coefficients))
        return polynomial * self.root**n


@dataclass(frozen=True)
class ExactClosedForm:
    terms: tuple[ExponentialPolynomialTerm, ...]
    start_index: int

    def evaluate(self, n: int) -> Fraction:
        if n < self.start_index:
            raise ValueError("closed form is not certified below its start index")
        return sum((term.evaluate(n) for term in self.terms), Fraction(0))


@dataclass(frozen=True)
class DiscoveredFoldProblem:
    problem_id: str
    observable: str
    domain: str
    statement_tex: str
    answer_tex: str
    recurrence: LinearRecurrence
    closed_form: ExactClosedForm
    exact_samples: tuple[Fraction, ...]
    interestingness_score: int
    proof_operations: tuple[str, ...]


@dataclass(frozen=True)
class DiscoveredMorphicFoldProblem:
    """An exact question cut from one recursively described folded solid."""

    problem_id: str
    observable: str
    domain: str
    minimum_generation: int
    statement_tex: str
    answer_tex: str
    solution_tex: str
    recurrence: LinearRecurrence
    closed_form: ExactClosedForm
    exact_samples: tuple[Fraction, ...]
    proof_operations: tuple[str, ...]
    recurrence_certificate: dict | None = None


def _add(left: Vec3, right: Vec3) -> Vec3:
    return tuple(left[index] + right[index] for index in range(3))  # type: ignore[return-value]


def _scale(scalar: int, vector: Vec3) -> Vec3:
    return tuple(scalar * value for value in vector)  # type: ignore[return-value]


def _dot(left: Vec3, right: Vec3) -> int:
    return sum(left[index] * right[index] for index in range(3))


def _cross(left: Vec3, right: Vec3) -> Vec3:
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def validate_frame(frame: Frame3) -> None:
    u, v, normal = frame
    if any(_dot(axis, axis) != 1 for axis in frame):
        raise ValueError("a panel frame must consist of signed coordinate unit vectors")
    if _dot(u, v) or _dot(v, normal) or _dot(normal, u):
        raise ValueError("a panel frame must be orthogonal")
    if _cross(u, v) != normal:
        raise ValueError("a panel frame must be right handed")


def apply_fold_generator(
    frame: Frame3,
    doubled_center: Vec3,
    generator: FoldGenerator,
) -> tuple[Frame3, Vec3]:
    """Attach one unit square and fold it by a signed right angle."""

    validate_frame(frame)
    if generator.fold_sign not in (-1, 1):
        raise ValueError("fold_sign must be either -1 or 1")
    u, v, normal = frame
    sign = generator.fold_sign
    if generator.attachment_edge == "u":
        # The shared edge is centred at p+u/2 and is parallel to v.
        next_u = _scale(-sign, normal)
        next_frame: Frame3 = (next_u, v, _scale(sign, u))
        displacement = _add(u, next_u)
    elif generator.attachment_edge == "v":
        # The shared edge is centred at p+v/2 and is parallel to u.
        next_v = _scale(sign, normal)
        next_frame = (u, next_v, _scale(-sign, v))
        displacement = _add(v, next_v)
    else:  # pragma: no cover - guarded by the literal type
        raise ValueError(f"unknown attachment edge: {generator.attachment_edge}")
    validate_frame(next_frame)
    return next_frame, _add(doubled_center, displacement)


def _panel(index: int, symbol: str | None, center: Vec3, frame: Frame3) -> SquarePanel:
    u, v, _ = frame
    corners = (
        _add(_add(center, u), v),
        _add(_add(center, _scale(-1, u)), v),
        _add(_add(center, _scale(-1, u)), _scale(-1, v)),
        _add(_add(center, u), _scale(-1, v)),
    )
    return SquarePanel(index, symbol, center, frame, corners)


def _normal_axis(panel: SquarePanel) -> int:
    return next(index for index, value in enumerate(panel.frame[2]) if value)


def _open_overlap(first: tuple[int, int], second: tuple[int, int]) -> bool:
    return min(first[1], second[1]) > max(first[0], second[0])


def _properly_intersects(first: SquarePanel, second: SquarePanel) -> bool:
    """Test relative-interior intersection for axis-aligned unit panels."""

    first_normal = _normal_axis(first)
    second_normal = _normal_axis(second)
    first_axes = [axis for axis in range(3) if axis != first_normal]
    second_axes = [axis for axis in range(3) if axis != second_normal]
    first_ranges = {axis: (first.doubled_center[axis] - 1, first.doubled_center[axis] + 1) for axis in first_axes}
    second_ranges = {axis: (second.doubled_center[axis] - 1, second.doubled_center[axis] + 1) for axis in second_axes}

    if first_normal == second_normal:
        if first.doubled_center[first_normal] != second.doubled_center[second_normal]:
            return False
        return all(_open_overlap(first_ranges[axis], second_ranges[axis]) for axis in first_axes)

    common_axis = next(axis for axis in range(3) if axis not in (first_normal, second_normal))
    second_plane = second.doubled_center[second_normal]
    first_plane = first.doubled_center[first_normal]
    return (
        first_ranges[second_normal][0] < second_plane < first_ranges[second_normal][1]
        and second_ranges[first_normal][0] < first_plane < second_ranges[first_normal][1]
        and _open_overlap(first_ranges[common_axis], second_ranges[common_axis])
    )


def build_square_fold_chain(word: str) -> FoldChain:
    if set(word) - set(GENERATOR_BY_SYMBOL):
        raise ValueError("a fold word may contain only A, C, G, and T")
    frame = IDENTITY_FRAME
    center = (0, 0, 0)
    panels = [_panel(0, None, center, frame)]
    intersections: list[tuple[int, int]] = []
    for index, symbol in enumerate(word, start=1):
        frame, center = apply_fold_generator(frame, center, GENERATOR_BY_SYMBOL[symbol])
        current = _panel(index, symbol, center, frame)
        for earlier in panels[:-1]:
            if _properly_intersects(earlier, current):
                intersections.append((earlier.index, current.index))
        panels.append(current)
    return FoldChain(word, tuple(panels), tuple(intersections))


def _try_build_collision_free_chain(word: str) -> FoldChain | None:
    """Build a chain, stopping as soon as a proper panel crossing appears."""

    frame = IDENTITY_FRAME
    center = (0, 0, 0)
    panels = [_panel(0, None, center, frame)]
    for index, symbol in enumerate(word, start=1):
        frame, center = apply_fold_generator(frame, center, GENERATOR_BY_SYMBOL[symbol])
        current = _panel(index, symbol, center, frame)
        if any(_properly_intersects(earlier, current) for earlier in panels[:-1]):
            return None
        panels.append(current)
    return FoldChain(word, tuple(panels), ())


def expand_uniform_fold_substitution(
    substitution: UniformFoldSubstitution,
    *,
    seed_symbol: str = "A",
    generation_count: int,
) -> str:
    """Expand a short composition grammar without adding geometric primitives."""

    return "".join(expand_emitted_tokens(
        substitution.grammar,
        {symbol: (symbol,) for symbol in substitution.grammar.alphabet},
        seed_symbol=seed_symbol,
        generation_count=generation_count,
    ))


def expand_mapped_fold_substitution(
    grammar: UniformSubstitutionGrammar,
    terminal_emissions: Mapping[str, Sequence[str]],
    *,
    seed_symbol: str,
    generation_count: int,
) -> str:
    """Compile an arbitrary finite grammar alphabet to rigid-fold terminals."""

    terminals = expand_emitted_tokens(
        grammar,
        terminal_emissions,
        seed_symbol=seed_symbol,
        generation_count=generation_count,
    )
    unknown = set(terminals) - set(GENERATOR_BY_SYMBOL)
    if unknown:
        raise ValueError(f"unknown rigid-fold terminals: {sorted(unknown)}")
    return "".join(terminals)


def _frame_apply(frame: Frame3, vector: Vec3) -> Vec3:
    return tuple(
        sum(vector[basis] * frame[basis][axis] for basis in range(3))
        for axis in range(3)
    )  # type: ignore[return-value]


def _compose_frames(first: Frame3, second: Frame3) -> Frame3:
    composed: Frame3 = tuple(_frame_apply(first, axis) for axis in second)  # type: ignore[assignment]
    validate_frame(composed)
    return composed


def _summarize_single_generator(generator: FoldGenerator) -> FoldWordSummary:
    frame, center = apply_fold_generator(IDENTITY_FRAME, (0, 0, 0), generator)
    return FoldWordSummary(
        step_count=1,
        end_frame=frame,
        doubled_end_center=center,
        doubled_center_sum=center,
        doubled_center_squared_sum=_dot(center, center),
        panel_frame_counts=((frame, 1),),
    )


def compose_fold_word_summaries(
    first: FoldWordSummary,
    second: FoldWordSummary,
) -> FoldWordSummary:
    """Summarize concatenation using only affine composition and inner products."""

    transformed_end = _frame_apply(first.end_frame, second.doubled_end_center)
    transformed_sum = _frame_apply(first.end_frame, second.doubled_center_sum)
    end_center = _add(first.doubled_end_center, transformed_end)
    center_sum = _add(
        first.doubled_center_sum,
        _add(_scale(second.step_count, first.doubled_end_center), transformed_sum),
    )
    center_squared_sum = (
        first.doubled_center_squared_sum
        + second.doubled_center_squared_sum
        + second.step_count * _dot(first.doubled_end_center, first.doubled_end_center)
        + 2 * _dot(first.doubled_end_center, transformed_sum)
    )
    frame_counts = dict(first.panel_frame_counts)
    for frame, count in second.panel_frame_counts:
        transformed_frame = _compose_frames(first.end_frame, frame)
        frame_counts[transformed_frame] = frame_counts.get(transformed_frame, 0) + count
    return FoldWordSummary(
        step_count=first.step_count + second.step_count,
        end_frame=_compose_frames(first.end_frame, second.end_frame),
        doubled_end_center=end_center,
        doubled_center_sum=center_sum,
        doubled_center_squared_sum=center_squared_sum,
        panel_frame_counts=tuple(sorted(frame_counts.items())),
    )


def iterate_uniform_fold_summaries(
    substitution: UniformFoldSubstitution,
    *,
    seed_symbol: str = "A",
    maximum_generation: int,
) -> tuple[FoldWordSummary, ...]:
    """Evaluate exponentially long substitution words in constant state space."""

    return iterate_mapped_fold_summaries(
        substitution.grammar,
        {symbol: (symbol,) for symbol in substitution.grammar.alphabet},
        seed_symbol=seed_symbol,
        maximum_generation=maximum_generation,
    )


def iterate_mapped_fold_summaries(
    grammar: UniformSubstitutionGrammar,
    terminal_emissions: Mapping[str, Sequence[str]],
    *,
    seed_symbol: str,
    maximum_generation: int,
) -> tuple[FoldWordSummary, ...]:
    """Summarize long fold programs whose grammar alphabet has arbitrary size."""

    emitted = {
        terminal
        for values in terminal_emissions.values()
        for terminal in values
    }
    unknown = emitted - set(GENERATOR_BY_SYMBOL)
    if unknown:
        raise ValueError(f"unknown rigid-fold terminals: {sorted(unknown)}")
    terminal_summaries = {
        symbol: _summarize_single_generator(generator)
        for symbol, generator in GENERATOR_BY_SYMBOL.items()
    }
    return iterate_emitted_summaries(
        grammar,
        terminal_emissions,
        terminal_summaries,
        compose_fold_word_summaries,
        seed_symbol=seed_symbol,
        maximum_generation=maximum_generation,
    )


def enumerate_morphic_fold_observables(
    substitution: UniformFoldSubstitution,
    *,
    seed_symbol: str = "A",
    maximum_generation: int,
) -> MorphicFoldObservables:
    """Extract exact candidate-question quantities from one recursive solid family."""

    summaries = iterate_uniform_fold_summaries(
        substitution,
        seed_symbol=seed_symbol,
        maximum_generation=maximum_generation,
    )
    endpoint_distance: list[Fraction] = []
    endpoint_height: list[Fraction] = []
    center_distance: list[Fraction] = []
    horizontal_counts: list[int] = []
    parallel_pairs: list[int] = []
    for summary in summaries:
        endpoint_distance.append(Fraction(_dot(summary.doubled_end_center, summary.doubled_end_center), 4))
        endpoint_height.append(Fraction(summary.doubled_end_center[2] ** 2, 4))
        center_distance.append(Fraction(summary.doubled_center_squared_sum, 4))
        frame_counts = dict(summary.panel_frame_counts)
        frame_counts[IDENTITY_FRAME] = frame_counts.get(IDENTITY_FRAME, 0) + 1
        horizontal_counts.append(
            sum(count for frame, count in frame_counts.items() if abs(frame[2][2]) == 1)
        )
        normal_axis_counts = [0, 0, 0]
        for frame, count in frame_counts.items():
            normal_axis_counts[next(axis for axis, value in enumerate(frame[2]) if value)] += count
        parallel_pairs.append(sum(count * (count - 1) // 2 for count in normal_axis_counts))
    return MorphicFoldObservables(
        generations=tuple(range(maximum_generation + 1)),
        step_counts=tuple(summary.step_count for summary in summaries),
        endpoint_distance_second=tuple(endpoint_distance),
        endpoint_height_second=tuple(endpoint_height),
        panel_center_distance_second_sum=tuple(center_distance),
        horizontal_panel_counts=tuple(horizontal_counts),
        parallel_panel_pair_counts=tuple(parallel_pairs),
    )


def _substitution_from_index(index: int) -> UniformFoldSubstitution:
    if not 0 <= index < 4**8:
        raise ValueError("substitution index is outside the two-uniform search space")
    symbols = "ACGT"
    digits: list[str] = []
    for _ in range(8):
        digits.append(symbols[index % 4])
        index //= 4
    digits.reverse()
    return UniformFoldSubstitution(
        tuple(tuple(digits[offset : offset + 2]) for offset in range(0, 8, 2))  # type: ignore[arg-type]
    )


def _chain_spatial_statistics(
    chain: FoldChain,
) -> tuple[int, int, Vec3, float, float, tuple[tuple[str, int], ...]]:
    frames = {panel.frame for panel in chain.panels}
    centers = {panel.doubled_center for panel in chain.panels}
    coordinates = tuple(panel.doubled_center for panel in chain.panels)
    minimum = tuple(min(point[axis] for point in coordinates) for axis in range(3))
    maximum = tuple(max(point[axis] for point in coordinates) for axis in range(3))
    extents = tuple(maximum[axis] - minimum[axis] for axis in range(3))
    sx = sum(point[0] for point in coordinates)
    sy = sum(point[1] for point in coordinates)
    sz = sum(point[2] for point in coordinates)
    products = (
        sum(point[0] ** 2 for point in coordinates),
        sum(point[1] ** 2 for point in coordinates),
        sum(point[2] ** 2 for point in coordinates),
        sum(point[0] * point[1] for point in coordinates),
        sum(point[0] * point[2] for point in coordinates),
        sum(point[1] * point[2] for point in coordinates),
    )
    area_isotropy, volume_isotropy, _, _ = _scatter_quality(
        len(coordinates),
        (sx, sy, sz),
        products,
    )
    counts = tuple((symbol, chain.word.count(symbol)) for symbol in "ACGT")
    return len(frames), len(centers), extents, area_isotropy, volume_isotropy, counts


def search_collision_free_uniform_fold_substitution(
    generation_count: int = 7,
    *,
    seed_symbol: str = "A",
    maximum_candidates: int = 4**8,
) -> MorphicFoldSearchResult:
    """Find a spatial fold chain whose 128-step description stays short.

    The complete search space has only ``4**8`` two-uniform grammars.  Geometry
    remains fixed; the search varies only the eight symbols in the four rewrite
    rules.  Candidates that do not use all four generators are discarded before
    the exact intersection test.
    """

    if generation_count < 1:
        raise ValueError("generation_count must be positive")
    if not 1 <= maximum_candidates <= 4**8:
        raise ValueError("maximum_candidates must lie between 1 and 4**8")

    best: tuple[tuple[float, ...], UniformFoldSubstitution, FoldChain, tuple[object, ...]] | None = None
    examined = 0
    collision_free = 0
    # Multiplication by an odd number permutes all 16-bit grammar indices.  This
    # gives a deterministic but non-lexicographic prefix when a bounded search is
    # requested.
    for ordinal in range(maximum_candidates):
        substitution = _substitution_from_index((ordinal * 40503 + 17317) % 4**8)
        examined += 1
        if set(symbol for image in substitution.images for symbol in image) != set("ACGT"):
            continue
        word = expand_uniform_fold_substitution(
            substitution,
            seed_symbol=seed_symbol,
            generation_count=generation_count,
        )
        if set(word) != set("ACGT"):
            continue
        chain = _try_build_collision_free_chain(word)
        if chain is None:
            continue
        collision_free += 1
        statistics = _chain_spatial_statistics(chain)
        orientations, centers, extents, area_isotropy, volume_isotropy, counts = statistics
        balance = max(count for _, count in counts) - min(count for _, count in counts)
        ranking = (
            volume_isotropy,
            area_isotropy,
            orientations,
            centers,
            min(extents),
            -balance,
        )
        if best is None or ranking > best[0]:
            best = (ranking, substitution, chain, statistics)

    if best is None:
        raise RuntimeError("no collision-free uniform substitution was found")
    _, substitution, chain, statistics = best
    orientations, centers, extents, area_isotropy, volume_isotropy, counts = statistics
    return MorphicFoldSearchResult(
        substitution=substitution,
        seed_symbol=seed_symbol,
        generation_count=generation_count,
        chain=chain,
        examined_substitution_count=examined,
        collision_free_substitution_count=collision_free,
        distinct_orientation_count=orientations,
        distinct_center_count=centers,
        doubled_extents=extents,
        scatter_area_isotropy=area_isotropy,
        scatter_volume_isotropy=volume_isotropy,
        generator_counts=counts,
    )


def _stable_search_jitter(seed: int, word: str) -> float:
    digest = hashlib.blake2b(f"{seed}:{word}".encode("ascii"), digest_size=8).digest()
    return int.from_bytes(digest, "big") / (2**64 - 1)


def _fold_search_score(
    *,
    word: str,
    visited_frames: frozenset[Frame3],
    visited_centers: frozenset[Vec3],
    minimum: Vec3,
    maximum: Vec3,
    coordinate_sums: Vec3,
    coordinate_products: tuple[int, int, int, int, int, int],
    generator_counts: tuple[int, int, int, int],
    seed: int,
) -> float:
    extents = tuple(maximum[axis] - minimum[axis] for axis in range(3))
    used_generators = sum(count > 0 for count in generator_counts)
    balance = max(generator_counts) - min(generator_counts)
    area_isotropy, volume_isotropy, scatter_area, scatter_volume = _scatter_quality(
        len(visited_centers),
        coordinate_sums,
        coordinate_products,
    )
    return (
        58 * len(visited_frames)
        + 12 * len(visited_centers)
        + 260 * area_isotropy
        + 1_400 * volume_isotropy
        + 7 * log1p(scatter_area)
        + 7 * log1p(scatter_volume)
        + 2 * min(extents)
        - 0.75 * sum(extents)
        + 14 * used_generators
        - balance
        + 0.35 * _stable_search_jitter(seed, word)
    )


def _scatter_quality(
    point_count: int,
    coordinate_sums: Vec3,
    coordinate_products: tuple[int, int, int, int, int, int],
) -> tuple[float, float, int, int]:
    """Return scale-free area and volume spread from an exact scatter matrix."""

    sx, sy, sz = coordinate_sums
    sxx, syy, szz, sxy, sxz, syz = coordinate_products
    xx = point_count * sxx - sx * sx
    yy = point_count * syy - sy * sy
    zz = point_count * szz - sz * sz
    xy = point_count * sxy - sx * sy
    xz = point_count * sxz - sx * sz
    yz = point_count * syz - sy * sz
    trace = xx + yy + zz
    scatter_area = max(0, xx * yy - xy * xy) + max(0, xx * zz - xz * xz) + max(0, yy * zz - yz * yz)
    scatter_volume = max(
        0,
        xx * (yy * zz - yz * yz)
        - xy * (xy * zz - xz * yz)
        + xz * (xy * yz - xz * yy),
    )
    if not trace:
        return 0.0, 0.0, scatter_area, scatter_volume
    area_isotropy = min(1.0, 3 * scatter_area / trace**2)
    volume_isotropy = min(1.0, 27 * scatter_volume / trace**3)
    return area_isotropy, volume_isotropy, scatter_area, scatter_volume


def search_collision_free_fold_chain(
    fold_count: int,
    *,
    beam_width: int = 64,
    seed: int = 20260904,
) -> CollisionFreeFoldSearchResult:
    """Search long A/C/G/T chains while rejecting exact final-state crossings.

    The search vocabulary is fixed to ``FOLD_GENERATORS``.  Beam search changes
    only the composition order; it does not introduce a motif-specific fold.
    Relative-interior intersections with non-adjacent panels are rejected at
    every extension.  Boundary contact is allowed.
    """

    if fold_count < 0:
        raise ValueError("fold_count must be non-negative")
    if beam_width < 1:
        raise ValueError("beam_width must be positive")

    root_panel = _panel(0, None, (0, 0, 0), IDENTITY_FRAME)
    root = _FoldSearchNode(
        word="",
        frame=IDENTITY_FRAME,
        center=(0, 0, 0),
        panels=(root_panel,),
        visited_frames=frozenset((IDENTITY_FRAME,)),
        visited_centers=frozenset(((0, 0, 0),)),
        minimum=(0, 0, 0),
        maximum=(0, 0, 0),
        coordinate_sums=(0, 0, 0),
        coordinate_products=(0, 0, 0, 0, 0, 0),
        generator_counts=(0, 0, 0, 0),
        score=0.0,
    )
    frontier = [root]
    explored = 0
    rejected = 0

    for panel_index in range(1, fold_count + 1):
        deduplicated: dict[tuple[Vec3, Frame3, str], _FoldSearchNode] = {}
        for node in frontier:
            for generator_index, generator in enumerate(FOLD_GENERATORS):
                explored += 1
                next_frame, next_center = apply_fold_generator(node.frame, node.center, generator)
                next_panel = _panel(panel_index, generator.symbol, next_center, next_frame)
                if any(_properly_intersects(earlier, next_panel) for earlier in node.panels[:-1]):
                    rejected += 1
                    continue

                word = node.word + generator.symbol
                visited_frames = node.visited_frames | {next_frame}
                visited_centers = node.visited_centers | {next_center}
                minimum = tuple(min(node.minimum[axis], next_center[axis]) for axis in range(3))
                maximum = tuple(max(node.maximum[axis], next_center[axis]) for axis in range(3))
                x, y, z = next_center
                coordinate_sums = (
                    node.coordinate_sums[0] + x,
                    node.coordinate_sums[1] + y,
                    node.coordinate_sums[2] + z,
                )
                products = node.coordinate_products
                coordinate_products = (
                    products[0] + x * x,
                    products[1] + y * y,
                    products[2] + z * z,
                    products[3] + x * y,
                    products[4] + x * z,
                    products[5] + y * z,
                )
                counts = list(node.generator_counts)
                counts[generator_index] += 1
                generator_counts = tuple(counts)
                score = _fold_search_score(
                    word=word,
                    visited_frames=visited_frames,
                    visited_centers=visited_centers,
                    minimum=minimum,
                    maximum=maximum,
                    coordinate_sums=coordinate_sums,
                    coordinate_products=coordinate_products,
                    generator_counts=generator_counts,
                    seed=seed,
                )
                candidate = _FoldSearchNode(
                    word=word,
                    frame=next_frame,
                    center=next_center,
                    panels=node.panels + (next_panel,),
                    visited_frames=visited_frames,
                    visited_centers=visited_centers,
                    minimum=minimum,
                    maximum=maximum,
                    coordinate_sums=coordinate_sums,
                    coordinate_products=coordinate_products,
                    generator_counts=generator_counts,
                    score=score,
                )
                key = (next_center, next_frame, word[-8:])
                previous = deduplicated.get(key)
                if previous is None or candidate.score > previous.score:
                    deduplicated[key] = candidate

        if not deduplicated:
            raise RuntimeError(f"no collision-free extension remained at fold {panel_index}")
        frontier = sorted(
            deduplicated.values(),
            key=lambda node: (node.score, node.word),
            reverse=True,
        )[:beam_width]

    best = max(frontier, key=lambda node: (node.score, node.word))
    chain = FoldChain(best.word, best.panels, ())
    extents = tuple(best.maximum[axis] - best.minimum[axis] for axis in range(3))
    area_isotropy, volume_isotropy, _, _ = _scatter_quality(
        len(best.visited_centers),
        best.coordinate_sums,
        best.coordinate_products,
    )
    return CollisionFreeFoldSearchResult(
        chain=chain,
        beam_width=beam_width,
        explored_candidate_count=explored,
        rejected_intersection_count=rejected,
        distinct_orientation_count=len(best.visited_frames),
        distinct_center_count=len(best.visited_centers),
        doubled_extents=extents,
        scatter_area_isotropy=area_isotropy,
        scatter_volume_isotropy=volume_isotropy,
        generator_counts=tuple(
            (generator.symbol, best.generator_counts[index])
            for index, generator in enumerate(FOLD_GENERATORS)
        ),
    )


def _monomials(maximum_degree: int) -> tuple[Monomial, ...]:
    return tuple(
        (x_degree, y_degree, z_degree)
        for x_degree in range(maximum_degree + 1)
        for y_degree in range(maximum_degree + 1 - x_degree)
        for z_degree in range(maximum_degree + 1 - x_degree - y_degree)
    )


def _translate_moments(
    moments: Mapping[Monomial, int],
    displacement: Vec3,
    monomials: Sequence[Monomial],
) -> dict[Monomial, int]:
    translated: dict[Monomial, int] = {}
    dx, dy, dz = displacement
    for x_degree, y_degree, z_degree in monomials:
        value = 0
        for i in range(x_degree + 1):
            for j in range(y_degree + 1):
                for k in range(z_degree + 1):
                    value += (
                        comb(x_degree, i)
                        * comb(y_degree, j)
                        * comb(z_degree, k)
                        * dx ** (x_degree - i)
                        * dy ** (y_degree - j)
                        * dz ** (z_degree - k)
                        * moments[(i, j, k)]
                    )
        translated[(x_degree, y_degree, z_degree)] = value
    return translated


def enumerate_polynomial_moments(
    maximum_generation: int,
    *,
    maximum_degree: int = 4,
    generators: Sequence[FoldGenerator] = FOLD_GENERATORS,
) -> PolynomialMomentSequences:
    """Aggregate all words by orientation, preserving moments exactly."""

    if maximum_generation < 0:
        raise ValueError("maximum_generation must be non-negative")
    if maximum_degree < 4:
        raise ValueError("the problem extractor requires moments through degree four")
    symbols = [generator.symbol for generator in generators]
    if len(symbols) != len(set(symbols)):
        raise ValueError("generator symbols must be distinct")

    monomials = _monomials(maximum_degree)
    zero = {monomial: 0 for monomial in monomials}
    zero[(0, 0, 0)] = 1
    states: dict[Frame3, dict[Monomial, int]] = {IDENTITY_FRAME: zero}

    orientation_counts: list[int] = []
    word_counts: list[int] = []
    distance_second: list[int] = []
    vertical_second: list[int] = []
    distance_fourth: list[int] = []
    vertical_fourth: list[int] = []
    normal_offset_fourth: list[int] = []
    projected_area_square: list[int] = []

    for _generation in range(maximum_generation + 1):
        totals = {monomial: sum(state[monomial] for state in states.values()) for monomial in monomials}
        orientation_counts.append(len(states))
        word_counts.append(totals[(0, 0, 0)])
        distance_second.append(totals[(2, 0, 0)] + totals[(0, 2, 0)] + totals[(0, 0, 2)])
        vertical_second.append(totals[(0, 0, 2)])
        distance_fourth.append(
            totals[(4, 0, 0)]
            + totals[(0, 4, 0)]
            + totals[(0, 0, 4)]
            + 2 * (totals[(2, 2, 0)] + totals[(2, 0, 2)] + totals[(0, 2, 2)])
        )
        vertical_fourth.append(totals[(0, 0, 4)])

        normal_fourth = 0
        projection_square = 0
        for frame, state in states.items():
            normal_axis = next(index for index, value in enumerate(frame[2]) if value)
            normal_fourth += state[((4, 0, 0), (0, 4, 0), (0, 0, 4))[normal_axis]]
            projection_square += state[(0, 0, 0)] * frame[2][2] ** 2
        normal_offset_fourth.append(normal_fourth)
        projected_area_square.append(projection_square)

        next_states: dict[Frame3, dict[Monomial, int]] = {}
        for frame, state in states.items():
            for generator in generators:
                next_frame, next_center = apply_fold_generator(frame, (0, 0, 0), generator)
                translated = _translate_moments(state, next_center, monomials)
                target = next_states.setdefault(next_frame, {monomial: 0 for monomial in monomials})
                for monomial in monomials:
                    target[monomial] += translated[monomial]
        states = next_states

    return PolynomialMomentSequences(
        maximum_degree=maximum_degree,
        reachable_orientation_counts=tuple(orientation_counts),
        word_counts=tuple(word_counts),
        doubled_distance_second=tuple(distance_second),
        doubled_vertical_second=tuple(vertical_second),
        doubled_distance_fourth=tuple(distance_fourth),
        doubled_vertical_fourth=tuple(vertical_fourth),
        doubled_normal_offset_fourth=tuple(normal_offset_fourth),
        projected_area_square=tuple(projected_area_square),
    )


def brute_force_observables(maximum_generation: int) -> dict[str, tuple[int, ...]]:
    """Independent word expansion used only as a small-generation oracle."""

    results = {
        "doubled_distance_second": [],
        "doubled_vertical_second": [],
        "doubled_distance_fourth": [],
        "projected_area_square": [],
    }
    for generation in range(maximum_generation + 1):
        values = {key: 0 for key in results}
        for symbols in product(GENERATOR_BY_SYMBOL, repeat=generation):
            frame = IDENTITY_FRAME
            center = (0, 0, 0)
            for symbol in symbols:
                frame, center = apply_fold_generator(frame, center, GENERATOR_BY_SYMBOL[symbol])
            norm_square = _dot(center, center)
            values["doubled_distance_second"] += norm_square
            values["doubled_vertical_second"] += center[2] ** 2
            values["doubled_distance_fourth"] += norm_square**2
            values["projected_area_square"] += frame[2][2] ** 2
        for key in results:
            results[key].append(values[key])
    return {key: tuple(values) for key, values in results.items()}


def _solve_unique_linear_system(
    rows: Sequence[Sequence[Fraction]],
    values: Sequence[Fraction],
) -> tuple[Fraction, ...] | None:
    if not rows or len(rows) != len(values):
        return None
    variable_count = len(rows[0])
    matrix = [list(row) + [value] for row, value in zip(rows, values, strict=True)]
    pivot_row = 0
    pivot_columns: list[int] = []
    for column in range(variable_count):
        pivot = next((row for row in range(pivot_row, len(matrix)) if matrix[row][column]), None)
        if pivot is None:
            continue
        matrix[pivot_row], matrix[pivot] = matrix[pivot], matrix[pivot_row]
        scale = matrix[pivot_row][column]
        matrix[pivot_row] = [entry / scale for entry in matrix[pivot_row]]
        for row in range(len(matrix)):
            if row == pivot_row or not matrix[row][column]:
                continue
            factor = matrix[row][column]
            matrix[row] = [matrix[row][index] - factor * matrix[pivot_row][index] for index in range(variable_count + 1)]
        pivot_columns.append(column)
        pivot_row += 1
        if pivot_row == len(matrix):
            break
    if any(all(not row[column] for column in range(variable_count)) and row[-1] for row in matrix):
        return None
    if len(pivot_columns) != variable_count:
        return None
    solution = [Fraction(0) for _ in range(variable_count)]
    for row, column in enumerate(pivot_columns):
        solution[column] = matrix[row][-1]
    return tuple(solution)


def discover_linear_recurrence(
    sequence: Sequence[int | Fraction],
    *,
    max_order: int = 16,
    start_index: int = 0,
) -> LinearRecurrence:
    values = tuple(Fraction(value) for value in sequence)
    for order in range(1, min(max_order, (len(values) - start_index) // 2) + 1):
        rows = [
            values[index : index + order]
            for index in range(start_index, len(values) - order)
        ]
        right = [values[index + order] for index in range(start_index, len(values) - order)]
        solution = _solve_unique_linear_system(rows, right)
        if solution is None:
            continue
        recurrence = LinearRecurrence(solution, start_index)
        if recurrence.holds(values):
            return recurrence
    raise ValueError("no uniquely determined recurrence was found within max_order")


def discover_integer_root_closed_form(
    sequence: Sequence[int | Fraction],
    recurrence: LinearRecurrence,
) -> ExactClosedForm:
    """Solve a recurrence when its characteristic roots are all integral."""

    import sympy as sp

    x = sp.Symbol("x")
    polynomial = x**recurrence.order - sum(
        sp.Rational(coefficient.numerator, coefficient.denominator) * x**index
        for index, coefficient in enumerate(recurrence.coefficients)
    )
    roots = sp.roots(polynomial, x)
    if sum(roots.values()) != recurrence.order:
        raise ValueError("the characteristic polynomial did not split")
    if any(not root.is_Integer for root in roots):
        raise ValueError("the closed-form extractor currently certifies integral roots only")

    basis = [(int(root), degree) for root, multiplicity in roots.items() for degree in range(multiplicity)]
    start = recurrence.start_index
    rows: list[list[Fraction]] = []
    right: list[Fraction] = []
    for n in range(start, start + len(basis)):
        rows.append([Fraction(n**degree * root**n) for root, degree in basis])
        right.append(Fraction(sequence[n]))
    coefficients = _solve_unique_linear_system(rows, right)
    if coefficients is None:
        raise ValueError("the exponential-polynomial coefficients were not unique")

    grouped: list[ExponentialPolynomialTerm] = []
    cursor = 0
    for root, multiplicity in roots.items():
        values = tuple(coefficients[cursor + degree] for degree in range(multiplicity))
        grouped.append(ExponentialPolynomialTerm(int(root), values))
        cursor += multiplicity
    result = ExactClosedForm(tuple(grouped), start)
    if any(result.evaluate(n) != Fraction(sequence[n]) for n in range(start, len(sequence))):
        raise ValueError("the discovered closed form failed exact replay")
    return result


def _scale_sequence(sequence: Iterable[int], denominator: int) -> tuple[Fraction, ...]:
    return tuple(Fraction(value, denominator) for value in sequence)


def _closed_form_latex(closed_form: ExactClosedForm) -> str:
    import sympy as sp

    n = sp.Symbol("n", integer=True, nonnegative=True)
    expression = 0
    for term in closed_form.terms:
        polynomial = sum(
            sp.Rational(value.numerator, value.denominator) * n**degree
            for degree, value in enumerate(term.polynomial_coefficients)
        )
        expression += polynomial * sp.Integer(term.root) ** n
    return sp.latex(sp.collect(sp.expand(expression), [sp.Integer(2) ** n, sp.Integer(4) ** n]))


def discover_eventual_linear_recurrence(
    sequence: Sequence[int | Fraction],
    *,
    maximum_start_index: int = 12,
    maximum_order: int = 16,
    fitting_term_count: int | None = None,
) -> LinearRecurrence:
    """Find the simplest eventual recurrence and verify it on held-out terms."""

    values = tuple(Fraction(value) for value in sequence)
    if fitting_term_count is None:
        fitting_term_count = max(8, (2 * len(values)) // 3)
    if not 4 <= fitting_term_count < len(values):
        raise ValueError("fitting_term_count must leave at least one held-out term")
    candidates: list[LinearRecurrence] = []
    fitting_values = values[:fitting_term_count]
    for start_index in range(min(maximum_start_index, fitting_term_count - 2) + 1):
        try:
            recurrence = discover_linear_recurrence(
                fitting_values,
                max_order=maximum_order,
                start_index=start_index,
            )
        except ValueError:
            continue
        if recurrence.holds(values):
            candidates.append(recurrence)
    if not candidates:
        raise ValueError("no eventual recurrence survived the held-out exact terms")
    return min(candidates, key=lambda recurrence: (recurrence.order, recurrence.start_index))


def _morphic_recurrence_solution(
    *,
    observable: str,
    sequence: Sequence[Fraction],
    recurrence: LinearRecurrence,
    closed_form: ExactClosedForm,
    certificate: dict,
) -> str:
    """Render the checked general certificate, never a substitution-specific proof."""
    import sympy as sp

    if not certificate.get("passed"):
        raise ValueError("an all-generation recurrence certificate is required")
    n = sp.Symbol("n", integer=True, nonnegative=True)
    term = sp.Function("X")
    right = sum(
        sp.Rational(coefficient.numerator, coefficient.denominator) * term(n + index)
        for index, coefficient in enumerate(recurrence.coefficients)
    )
    relation = sp.latex(sp.Eq(term(n + recurrence.order), right))
    initials = r",\quad ".join(
        rf"X_{{{index}}}={sp.latex(sp.Rational(sequence[index].numerator, sequence[index].denominator))}"
        for index in range(recurrence.start_index, recurrence.start_index + recurrence.order)
    )
    return (
        r"以下は有限次元の線形代数による計算機証明であり、高校範囲の解答への変換は未評価である。"
        r"各部分列の長さ、終点、中心座標の和、距離の二乗和、法線方向別の板数について、"
        r"二つの部分列を続けたときの更新式を厳密に合成する。"
        rf"四つの終座標系をまとめた状態は第 {certificate['orientation_cycle_start']} 世代以降、"
        rf"{certificate['period']} 世代ごとに同じになる。"
        rf"目的量を含む {certificate['lift_dimension']} 個の単項式は、"
        r"各周期段階の更新により互いの線形結合になる。係数行列は証明記録に保存した。"
        rf"候補の漸化式 \[{relation}\] の残差について、各周期段階で"
        rf" {certificate['lift_dimension']} 個の連続する値が厳密にゼロになる。"
        r"周期分の係数行列の積にケーリー・ハミルトンの定理を適用すると、"
        r"その後の残差もすべてゼロである。周期に入る前の必要な値も個別に確認した。"
        rf"したがってこの漸化式は \(n\ge {recurrence.start_index}\) で成り立つ。"
        rf"初期値 \[{initials}\] と特性方程式から"
        rf"\[X_n={_closed_form_latex(closed_form)}\quad(n\ge {recurrence.start_index})\]"
        r"を得る。この証明は中心や法線の量に関するものであり、折りの途中の衝突を判定するものではない。"
    )


def discover_morphic_fold_problem_candidates(
    substitution: UniformFoldSubstitution,
    *,
    seed_symbol: str = "A",
    maximum_generation: int = 40,
) -> tuple[DiscoveredMorphicFoldProblem, ...]:
    """Certify a legacy fixed question catalog; this is not goal-free generation."""

    from math_os_prototype.morphic_fold_certificate import certify_morphic_recurrence

    observables = enumerate_morphic_fold_observables(
        substitution,
        seed_symbol=seed_symbol,
        maximum_generation=maximum_generation,
    )
    specifications = (
        (
            "morphic-endpoint-distance",
            "endpoint_distance_second",
            "空間図形・数列",
            observables.endpoint_distance_second,
            r"OP_n^2",
            "第2世代以降の終板の中心を追跡し、終点距離の二乗を求めよ。",
        ),
        (
            "morphic-endpoint-height",
            "endpoint_height_second",
            "空間図形・数列",
            observables.endpoint_height_second,
            r"z_n^2",
            r"終板の中心の高さを \(z_n\) とするとき、その二乗を求めよ。",
        ),
        (
            "morphic-panel-radius-sum",
            "panel_center_distance_second_sum",
            "空間図形・数列",
            observables.panel_center_distance_second_sum,
            r"\sum_{P\in\mathcal P_n}OP^2",
            r"全ての板の中心集合を \(\mathcal P_n\) とするとき、原点からの距離の二乗和を求めよ。",
        ),
        (
            "morphic-horizontal-panels",
            "horizontal_panel_counts",
            "空間図形・数列・場合の数",
            tuple(Fraction(value) for value in observables.horizontal_panel_counts),
            r"H_n",
            r"最初の板と平行な板の枚数を \(H_n\) とするとき、\(H_n\) を求めよ。",
        ),
        (
            "morphic-parallel-pairs",
            "parallel_panel_pair_counts",
            "空間図形・数列・場合の数",
            tuple(Fraction(value) for value in observables.parallel_panel_pair_counts),
            r"Q_n",
            r"互いに平行な二枚の板の選び方を \(Q_n\) 通りとするとき、\(Q_n\) を求めよ。",
        ),
    )
    rewrite_tex = r",\quad ".join(
        f"{symbol}\\mapsto {''.join(substitution.image(symbol))}"
        for symbol in "ACGT"
    )
    common_statement = (
        r"最初の単位正方形の中心を \(O\)、辺方向の単位ベクトルを "
        r"\(\boldsymbol e_x,\boldsymbol e_y\) とし、法線を \(\boldsymbol e_z\) とする。"
        r"現在の板の中心を \(\boldsymbol p\)、局所軸を "
        r"\((\boldsymbol u,\boldsymbol v,\boldsymbol w)\) とするとき、"
        r"次の四操作で新しい単位正方形を一枚つなぐ。"
        r"\["
        r"\begin{array}{c|c|c}"
        r"&\text{新しい中心}&\text{新しい局所軸}\\ \hline "
        r"A&\boldsymbol p+(\boldsymbol u-\boldsymbol w)/2&(-\boldsymbol w,\boldsymbol v,\boldsymbol u)\\"
        r"C&\boldsymbol p+(\boldsymbol u+\boldsymbol w)/2&(\boldsymbol w,\boldsymbol v,-\boldsymbol u)\\"
        r"G&\boldsymbol p+(\boldsymbol v+\boldsymbol w)/2&(\boldsymbol u,\boldsymbol w,-\boldsymbol v)\\"
        r"T&\boldsymbol p+(\boldsymbol v-\boldsymbol w)/2&(\boldsymbol u,-\boldsymbol w,\boldsymbol v)"
        r"\end{array}"
        r"\]"
        r"さらに置換 "
        + rf"\[{rewrite_tex}\]"
        + rf"を定める。\(W_n=\sigma^n({seed_symbol})\) の文字を左から実行してできる折り板を考える。"
    )

    candidates: list[DiscoveredMorphicFoldProblem] = []
    seen_sequences: set[tuple[Fraction, ...]] = set()
    for problem_id, observable, domain, sequence, query, question in specifications:
        exact_sequence = tuple(Fraction(value) for value in sequence)
        if exact_sequence in seen_sequences:
            continue
        seen_sequences.add(exact_sequence)
        recurrence = discover_eventual_linear_recurrence(exact_sequence)
        certificate = certify_morphic_recurrence(substitution, observable, recurrence, seed_symbol)
        if not certificate["passed"]:
            raise ValueError(f"recurrence rejected for {observable}: {certificate['counterexamples']}")
        closed_form = discover_integer_root_closed_form(exact_sequence, recurrence)
        minimum_generation = recurrence.start_index
        candidates.append(
            DiscoveredMorphicFoldProblem(
                problem_id=problem_id,
                observable=observable,
                domain=domain,
                minimum_generation=minimum_generation,
                statement_tex=(
                    common_statement
                    + rf"\(n\ge {minimum_generation}\) とする。"
                    + question
                ),
                answer_tex=(
                    f"{query}={_closed_form_latex(closed_form)}"
                    f"\\quad(n\\ge {minimum_generation})"
                ),
                solution_tex=_morphic_recurrence_solution(
                    observable=observable,
                    sequence=exact_sequence,
                    recurrence=recurrence,
                    closed_form=closed_form,
                    certificate=certificate,
                ),
                recurrence=recurrence,
                closed_form=closed_form,
                exact_samples=exact_sequence[:16],
                proof_operations=(
                    "UniformSubstitutionExpansion",
                    "AffineFoldSummaryComposition",
                    "OrientationStateQuotient",
                    "ExactObservableEnumeration",
                    "ExactMonomialClosure",
                    "PeriodicResidualCayleyHamiltonCertificate",
                    "IntegerRootClosedForm",
                    "FixedCatalogQuestion",
                ),
                recurrence_certificate=certificate,
            )
        )
    return tuple(sorted(candidates, key=lambda candidate: (candidate.recurrence.order, candidate.problem_id)))


def discover_fold_problem_candidates(maximum_generation: int = 24) -> tuple[DiscoveredFoldProblem, ...]:
    """Mine, deduplicate, and rank exact exam-style observables."""

    moments = enumerate_polynomial_moments(maximum_generation)
    specifications = (
        (
            "endpoint-distance-second",
            "endpoint_distance_second_moment",
            "空間図形・数列・確率",
            _scale_sequence(moments.doubled_distance_second, 4),
            0,
            r"\displaystyle\sum_{w\in\{A,C,G,T\}^n}OP_w^2",
        ),
        (
            "endpoint-height-second",
            "endpoint_height_second_moment",
            "空間図形・数列・確率",
            _scale_sequence(moments.doubled_vertical_second, 4),
            0,
            r"\displaystyle\sum_{w\in\{A,C,G,T\}^n}z_w^2",
        ),
        (
            "endpoint-distance-fourth",
            "endpoint_distance_fourth_moment",
            "空間図形・数列・確率",
            _scale_sequence(moments.doubled_distance_fourth, 16),
            1,
            r"\displaystyle\sum_{w\in\{A,C,G,T\}^n}OP_w^4",
        ),
        (
            "projection-parallel-count",
            "final_panel_projection_square_sum",
            "空間図形・確率",
            tuple(Fraction(value) for value in moments.projected_area_square),
            0,
            r"\displaystyle\sum_{w\in\{A,C,G,T\}^n}S_w^2",
        ),
    )

    candidates: list[DiscoveredFoldProblem] = []
    seen_sequences: set[tuple[Fraction, ...]] = set()
    for problem_id, observable, domain, sequence, start_index, query in specifications:
        if sequence in seen_sequences:
            continue
        seen_sequences.add(sequence)
        recurrence = discover_linear_recurrence(sequence, start_index=start_index)
        closed_form = discover_integer_root_closed_form(sequence, recurrence)
        answer = _closed_form_latex(closed_form)
        alternating = any(term.root < 0 for term in closed_form.terms)
        nonzero_terms = sum(any(coefficient for coefficient in term.polynomial_coefficients) for term in closed_form.terms)
        score = 4 * recurrence.order + 3 * nonzero_terms + (5 if alternating else 0)
        statement = (
            "単位正方形の板を一枚置く。現在の板の局所座標軸を "
            r"\(\boldsymbol u,\boldsymbol v\)、法線を \(\boldsymbol n\) とする。"
            r"辺の選択と山折り・谷折りを表す四操作 \(A,C,G,T\) により、"
            "選んだ辺に新しい単位正方形を継ぎ、直角に折る。"
            r"\(n\) 回の操作列 \(w\in\{A,C,G,T\}^n\) ごとに最後の板の中心を \(P_w\) とする。"
            f"次を求めよ。\\[{query}\\]"
        )
        candidates.append(
            DiscoveredFoldProblem(
                problem_id=problem_id,
                observable=observable,
                domain=domain,
                statement_tex=statement,
                answer_tex=answer,
                recurrence=recurrence,
                closed_form=closed_form,
                exact_samples=sequence[:12],
                interestingness_score=score,
                proof_operations=(
                    "LocalFrameElaboration",
                    "FourFoldExpansion",
                    "SignedPermutationOrientationQuotient",
                    "PolynomialMomentLift",
                    "ExactRecurrenceDiscovery",
                    "PremiseMinimization",
                    "HighSchoolRecurrenceProof",
                ),
            )
        )
    return tuple(sorted(candidates, key=lambda candidate: (-candidate.interestingness_score, candidate.problem_id)))


def ablate_generators(maximum_generation: int = 10) -> dict[str, tuple[int, ...]]:
    """Remove one letter at a time and expose whether it changes the geometry."""

    return {
        generator.symbol: enumerate_polynomial_moments(
            maximum_generation,
            generators=tuple(candidate for candidate in FOLD_GENERATORS if candidate != generator),
        ).doubled_distance_second
        for generator in FOLD_GENERATORS
    }
