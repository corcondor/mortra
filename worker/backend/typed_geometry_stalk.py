"""Finite typed construction grammar for geometry proof-obligation search.

The grammar is independent of benchmark problem IDs and answers.  It only
uses point types, incidence adjacency, goal support, and the declared input
symmetries of each construction family.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from itertools import combinations, permutations
import random
from typing import Any, Callable, Hashable, Iterable, Mapping, Sequence, TypeVar


T = TypeVar("T")


@dataclass(frozen=True)
class ConstructionFamily:
    name: str
    input_arity: int
    symmetry: str
    output_channels: tuple[str, ...] = ()


@dataclass(frozen=True)
class TypedConstructionCandidate:
    family: str
    inputs: tuple[str, ...]
    structural_rank: tuple[object, ...]

    @property
    def key(self) -> str:
        return f"{self.family}({','.join(self.inputs)})"


DEFAULT_POINT_FAMILIES: tuple[ConstructionFamily, ...] = (
    ConstructionFamily("midpoint", 2, "all", ("midp", "coll", "cong")),
    ConstructionFamily("mirror", 2, "ordered", ("coll", "cong")),
    ConstructionFamily("foot", 3, "head_pair", ("perp", "coll")),
    ConstructionFamily("circle", 3, "all", ("circle",)),
    ConstructionFamily("orthocenter", 3, "all", ("perp",)),
    ConstructionFamily("reflect", 3, "head_pair", ("cong", "perp")),
    ConstructionFamily("intersection_ll", 4, "line_pair", ("coll",)),
)


EXTENDED_POINT_FAMILIES: tuple[ConstructionFamily, ...] = (
    *DEFAULT_POINT_FAMILIES,
    ConstructionFamily("angle_bisector", 3, "ordered", ("eqangle",)),
    ConstructionFamily("angle_mirror", 3, "ordered", ("eqangle",)),
    ConstructionFamily("eqdistance", 3, "ordered", ("cong",)),
    ConstructionFamily("incenter", 3, "all", ("eqangle",)),
    ConstructionFamily("excenter", 3, "ordered", ("eqangle",)),
    ConstructionFamily("shift", 3, "ordered", ("cong",)),
    ConstructionFamily("parallelogram", 3, "ordered", ("para", "cong")),
    ConstructionFamily("circumcenter", 3, "all", ("cong",)),
    ConstructionFamily("intersection_lc", 3, "ordered", ("coll", "cong")),
    ConstructionFamily("intersection_cc", 3, "ordered", ("cong",)),
    ConstructionFamily("eq_triangle", 2, "all", ("cong", "eqangle")),
    ConstructionFamily("psquare", 2, "ordered", ("cong", "perp")),
    ConstructionFamily("nsquare", 2, "ordered", ("cong", "perp")),
    ConstructionFamily("between_bound", 2, "ordered", ("coll", "obtuse_angle")),
)


def goal_relevant_families(
    families: Sequence[ConstructionFamily],
    transition_distances: Mapping[str, int],
) -> tuple[ConstructionFamily, ...]:
    """Keep construction schemas whose declared facts can feed the goal."""

    reachable = {str(channel).lower() for channel in transition_distances}
    selected = tuple(
        family
        for family in families
        if not family.output_channels or reachable.intersection(family.output_channels)
    )
    return selected or tuple(families)


def prioritize_morphism_orbit(
    candidates: Sequence[TypedConstructionCandidate],
    *,
    previous_family: str | None,
    previous_inputs: Sequence[str] = (),
) -> list[TypedConstructionCandidate]:
    """Prefer same-family substitutions that share a typed input role.

    This is a finite orbit closure over point substitutions.  It does not name
    a theorem, benchmark, or desired auxiliary point.
    """

    if previous_family is None or not previous_inputs:
        return list(candidates)
    previous = set(previous_inputs)
    return sorted(
        candidates,
        key=lambda candidate: (
            0
            if candidate.family == previous_family
            and bool(previous.intersection(candidate.inputs))
            else 1,
            -len(previous.intersection(candidate.inputs)),
            candidate.structural_rank,
        ),
    )


def _family_inputs(
    points: Sequence[str], family: ConstructionFamily
) -> Iterable[tuple[str, ...]]:
    if family.symmetry == "all":
        yield from combinations(points, family.input_arity)
        return
    if family.symmetry == "ordered":
        yield from permutations(points, family.input_arity)
        return
    if family.symmetry == "head_pair":
        for head in points:
            others = [point for point in points if point != head]
            for pair in combinations(others, 2):
                yield (head, *pair)
        return
    if family.symmetry == "line_pair":
        for quartet in combinations(points, 4):
            a, b, c, d = quartet
            yield (a, b, c, d)
            yield (a, c, b, d)
            yield (a, d, b, c)
        return
    raise ValueError(f"unknown construction symmetry: {family.symmetry}")


def goal_distances(
    graph: Mapping[str, set[str]], goal_multiplicity: Mapping[str, int]
) -> dict[str, int]:
    distances = {point: 0 for point in goal_multiplicity}
    queue = deque(distances)
    while queue:
        point = queue.popleft()
        for neighbor in graph.get(point, set()):
            if neighbor not in distances:
                distances[neighbor] = distances[point] + 1
                queue.append(neighbor)
    return distances


def proof_hypergraph_point_relevance(
    deductions: Sequence[Mapping[str, Any]],
    goal_support: set[str],
) -> dict[str, float]:
    """Rank points by their overlap with goal-bearing proof dependencies.

    Yuclid currently serializes ``point_deps`` as a JSON list.  Older proof
    artifacts used a whitespace-delimited string, so both representations are
    accepted without inspecting problem IDs, answers, or hidden auxiliaries.
    """

    scores: dict[str, float] = {}
    for deduction in deductions:
        raw_support = deduction.get("point_deps", ())
        if isinstance(raw_support, str):
            support = {point for point in raw_support.split() if point}
        elif isinstance(raw_support, Sequence):
            support = {str(point) for point in raw_support if str(point)}
        else:
            continue
        overlap = len(support & goal_support)
        if not support or overlap == 0:
            continue
        contribution = overlap / len(support)
        for point in support:
            scores[point] = scores.get(point, 0.0) + contribution
    scale = max(scores.values(), default=0.0)
    if scale == 0:
        return {}
    return {point: value / scale for point, value in scores.items()}


def stratified_beam(
    items: Sequence[T],
    *,
    score: Callable[[T], tuple[object, ...]],
    stratum: Callable[[T], Hashable],
    limit: int,
) -> list[T]:
    """Keep the best item per structural stratum, then fill by score."""

    if limit <= 0:
        return []
    ranked = sorted(items, key=score, reverse=True)
    selected: list[T] = []
    seen: set[Hashable] = set()
    for item in ranked:
        key = stratum(item)
        if key in seen:
            continue
        selected.append(item)
        seen.add(key)
        if len(selected) == limit:
            return selected
    for item in ranked:
        if item not in selected:
            selected.append(item)
            if len(selected) == limit:
                break
    return selected


def balanced_stratified_beam(
    items: Sequence[T],
    *,
    score: Callable[[T], tuple[object, ...]],
    category: Callable[[T], Hashable],
    stratum: Callable[[T], Hashable],
    limit: int,
) -> list[T]:
    """Round-robin categories while retaining one best item per stratum."""

    if limit <= 0:
        return []
    ranked = sorted(items, key=score, reverse=True)
    buckets: dict[Hashable, list[T]] = {}
    category_order: list[Hashable] = []
    seen_strata: set[Hashable] = set()
    for item in ranked:
        key = stratum(item)
        if key in seen_strata:
            continue
        seen_strata.add(key)
        group = category(item)
        if group not in buckets:
            buckets[group] = []
            category_order.append(group)
        buckets[group].append(item)
    selected: list[T] = []
    while len(selected) < limit:
        added = False
        for group in category_order:
            if buckets[group]:
                selected.append(buckets[group].pop(0))
                added = True
                if len(selected) == limit:
                    return selected
        if not added:
            break
    for item in ranked:
        if item not in selected:
            selected.append(item)
            if len(selected) == limit:
                break
    return selected


def numerical_precondition_holds(
    candidate: TypedConstructionCandidate,
    coordinates: Mapping[str, tuple[float, float]] | None,
    *,
    tolerance: float = 1e-9,
) -> bool:
    """Reject obvious degeneracies; this is never a proof acceptance rule."""

    if coordinates is None or any(point not in coordinates for point in candidate.inputs):
        return True

    def squared_distance(left: str, right: str) -> float:
        lx, ly = coordinates[left]
        rx, ry = coordinates[right]
        return (lx - rx) ** 2 + (ly - ry) ** 2

    def oriented_area(a: str, b: str, c: str) -> float:
        ax, ay = coordinates[a]
        bx, by = coordinates[b]
        cx, cy = coordinates[c]
        return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)

    if candidate.family in {"midpoint", "mirror"}:
        return squared_distance(*candidate.inputs) > tolerance**2
    if candidate.family in {"foot", "circle", "orthocenter", "reflect"}:
        return abs(oriented_area(*candidate.inputs)) > tolerance
    if candidate.family == "intersection_ll":
        a, b, c, d = candidate.inputs
        abx = coordinates[b][0] - coordinates[a][0]
        aby = coordinates[b][1] - coordinates[a][1]
        cdx = coordinates[d][0] - coordinates[c][0]
        cdy = coordinates[d][1] - coordinates[c][1]
        return abs(abx * cdy - aby * cdx) > tolerance
    return True


def augment_incidence_graph(
    base_graph: Mapping[str, set[str]],
    steps: Sequence[tuple[str, tuple[str, ...]]],
) -> dict[str, set[str]]:
    graph = {point: set(neighbors) for point, neighbors in base_graph.items()}
    for output, inputs in steps:
        graph.setdefault(output, set())
        for point in inputs:
            graph.setdefault(point, set())
            graph[output].add(point)
            graph[point].add(output)
    return graph


def enumerate_typed_candidates(
    *,
    points: Sequence[str],
    graph: Mapping[str, set[str]],
    goal_multiplicity: Mapping[str, int],
    proof_relevance: Mapping[str, float] | None = None,
    generated_points: set[str] | None = None,
    used_keys: set[str] | None = None,
    families: Sequence[ConstructionFamily] = DEFAULT_POINT_FAMILIES,
    per_family_limit: int = 8,
    ranking: str = "structural",
    seed: int = 0,
    coordinates: Mapping[str, tuple[float, float]] | None = None,
    orbit_family: str | None = None,
    orbit_inputs: Sequence[str] = (),
) -> list[TypedConstructionCandidate]:
    """Enumerate a balanced finite candidate set from typed structure only."""

    generated_points = generated_points or set()
    used_keys = used_keys or set()
    proof_relevance = proof_relevance or {}
    ordered_points = tuple(sorted(set(points)))
    distances = goal_distances(graph, goal_multiplicity)
    selected: list[TypedConstructionCandidate] = []
    for family in families:
        family_candidates: list[TypedConstructionCandidate] = []
        for inputs in _family_inputs(ordered_points, family):
            if len(set(inputs)) != len(inputs):
                continue
            key = f"{family.name}({','.join(inputs)})"
            if key in used_keys:
                continue
            pair_count = 0
            for left, right in combinations(inputs, 2):
                if right in graph.get(left, set()):
                    pair_count += 1
            input_distances = tuple(distances.get(point, 10_000) for point in inputs)
            rank: tuple[object, ...] = (
                -sum(goal_multiplicity.get(point, 0) for point in inputs),
                -sum(proof_relevance.get(point, 0.0) for point in inputs),
                sum(input_distances),
                max(input_distances),
                0 if generated_points.intersection(inputs) else 1,
                -pair_count,
                family.input_arity,
                family.name,
                inputs,
            )
            candidate = TypedConstructionCandidate(family.name, inputs, rank)
            if numerical_precondition_holds(candidate, coordinates):
                family_candidates.append(candidate)
        if ranking == "structural":
            orbit = set(orbit_inputs)
            family_candidates.sort(
                key=lambda candidate: (
                    0
                    if candidate.family == orbit_family
                    and bool(orbit.intersection(candidate.inputs))
                    else 1,
                    -len(orbit.intersection(candidate.inputs)),
                    candidate.structural_rank,
                )
            )
        elif ranking == "random":
            random.Random(f"{seed}|{family.name}").shuffle(family_candidates)
        else:
            raise ValueError(f"unknown ranking: {ranking}")
        selected.extend(family_candidates[:per_family_limit])
    if ranking == "random":
        random.Random(f"{seed}|all-families").shuffle(selected)
        return selected
    return sorted(selected, key=lambda candidate: candidate.structural_rank)


def family_by_name(name: str) -> ConstructionFamily:
    for family in DEFAULT_POINT_FAMILIES:
        if family.name == name:
            return family
    raise KeyError(name)
