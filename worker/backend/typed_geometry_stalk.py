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
    allow_repeated_inputs: bool = False


@dataclass(frozen=True)
class TypedConstructionCandidate:
    family: str
    inputs: tuple[str, ...]
    structural_rank: tuple[object, ...]

    @property
    def key(self) -> str:
        return f"{self.family}({','.join(self.inputs)})"


@dataclass(frozen=True)
class CandidateGateAudit:
    mode: str
    input_count: int
    retained_count: int
    rejected_count: int
    target_channels: tuple[str, ...]
    reachable_channels: tuple[str, ...]
    retained_by_family: tuple[tuple[str, int], ...]
    rejected_by_family: tuple[tuple[str, int], ...]
    fail_open_reason: str | None = None


@dataclass(frozen=True)
class CandidateGateResult:
    candidates: tuple[TypedConstructionCandidate, ...]
    audit: CandidateGateAudit


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
    ConstructionFamily("on_line", 2, "all", ("coll",)),
    ConstructionFamily("on_pline", 3, "ordered", ("para",)),
    ConstructionFamily("on_tline", 3, "ordered", ("perp",)),
    ConstructionFamily("on_bline", 2, "all", ("cong", "eqangle")),
    ConstructionFamily("on_circle", 2, "ordered", ("cong",)),
    ConstructionFamily("on_circum", 3, "all", ("cyclic",)),
    ConstructionFamily("on_dia", 2, "all", ("perp",)),
    ConstructionFamily(
        "intersection_lp", 5, "line_relation", ("coll", "para"), True
    ),
    ConstructionFamily(
        "intersection_pp", 6, "relation_pair", ("para",), True
    ),
    ConstructionFamily(
        "intersection_lt", 5, "line_relation", ("coll", "perp"), True
    ),
    ConstructionFamily(
        "intersection_tt", 6, "relation_pair", ("perp",), True
    ),
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


def gate_candidates_by_relation_reachability(
    candidates: Sequence[TypedConstructionCandidate],
    *,
    families: Sequence[ConstructionFamily],
    reachable_channels: Iterable[str],
    target_channels: Iterable[str],
    mode: str = "relation-reachability",
) -> CandidateGateResult:
    """Reject schemas that cannot feed any currently open relation type.

    The gate reasons only over declared construction outputs and the native
    theorem relation graph.  It does not inspect benchmark IDs, answers, or
    numerical coordinates.  Missing declarations fail open because absence
    of type evidence is not a proof of irrelevance.
    """

    if mode not in {"off", "relation-reachability"}:
        raise ValueError(f"unknown candidate gate mode: {mode}")
    family_map = {family.name: family for family in families}
    reachable = {str(channel).lower() for channel in reachable_channels}
    targets = tuple(sorted({str(channel).lower() for channel in target_channels}))

    def counts(items: Sequence[TypedConstructionCandidate]) -> tuple[tuple[str, int], ...]:
        values: dict[str, int] = {}
        for item in items:
            values[item.family] = values.get(item.family, 0) + 1
        return tuple(sorted(values.items()))

    original = tuple(candidates)
    if mode == "off":
        return CandidateGateResult(
            original,
            CandidateGateAudit(
                mode,
                len(original),
                len(original),
                0,
                targets,
                tuple(sorted(reachable)),
                counts(original),
                (),
            ),
        )
    if not reachable:
        return CandidateGateResult(
            original,
            CandidateGateAudit(
                mode,
                len(original),
                len(original),
                0,
                targets,
                (),
                counts(original),
                (),
                "no_relation_reachability_evidence",
            ),
        )

    retained: list[TypedConstructionCandidate] = []
    rejected: list[TypedConstructionCandidate] = []
    for candidate in original:
        family = family_map.get(candidate.family)
        outputs = (
            {channel.lower() for channel in family.output_channels}
            if family is not None
            else set()
        )
        if not outputs or outputs.intersection(reachable):
            retained.append(candidate)
        else:
            rejected.append(candidate)

    if original and not retained:
        return CandidateGateResult(
            original,
            CandidateGateAudit(
                mode,
                len(original),
                len(original),
                0,
                targets,
                tuple(sorted(reachable)),
                counts(original),
                (),
                "all_candidates_lacked_reachability_evidence",
            ),
        )
    return CandidateGateResult(
        tuple(retained),
        CandidateGateAudit(
            mode,
            len(original),
            len(retained),
            len(rejected),
            targets,
            tuple(sorted(reachable)),
            counts(retained),
            counts(rejected),
        ),
    )


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
    if family.symmetry == "line_relation":
        lines = tuple(combinations(points, 2))
        for line in lines:
            for anchor in points:
                for relation_line in lines:
                    if anchor not in relation_line:
                        yield (*line, anchor, *relation_line)
        return
    if family.symmetry == "relation_pair":
        lines = tuple(combinations(points, 2))
        relations = tuple(
            (anchor, *line)
            for anchor in points
            for line in lines
            if anchor not in line
        )
        for left, right in combinations(relations, 2):
            yield (*left, *right)
        return
    raise ValueError(f"unknown construction symmetry: {family.symmetry}")


def equivalent_construction_inputs(
    family: ConstructionFamily,
    left: Sequence[str],
    right: Sequence[str],
) -> bool:
    """Compare construction inputs modulo the symmetry declared by the grammar."""

    left = tuple(left)
    right = tuple(right)
    if len(left) != family.input_arity or len(right) != family.input_arity:
        return False
    if family.symmetry == "ordered":
        return left == right
    if family.symmetry == "all":
        return sorted(left) == sorted(right)
    if family.symmetry == "head_pair":
        return left[0] == right[0] and sorted(left[1:]) == sorted(right[1:])
    if family.symmetry == "line_pair":
        left_lines = {frozenset(left[:2]), frozenset(left[2:])}
        right_lines = {frozenset(right[:2]), frozenset(right[2:])}
        return left_lines == right_lines
    if family.symmetry == "line_relation":
        return (
            frozenset(left[:2]) == frozenset(right[:2])
            and left[2] == right[2]
            and frozenset(left[3:]) == frozenset(right[3:])
        )
    if family.symmetry == "relation_pair":
        left_relations = {
            (left[0], frozenset(left[1:3])),
            (left[3], frozenset(left[4:6])),
        }
        right_relations = {
            (right[0], frozenset(right[1:3])),
            (right[3], frozenset(right[4:6])),
        }
        return left_relations == right_relations
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


def schema_first_score_fill(
    candidates: Sequence[T],
    *,
    category: Callable[[T], Hashable],
    category_order: Sequence[Hashable],
    limit: int,
) -> list[T]:
    """Reserve one item per schema, then spend remaining budget by score order."""

    if limit <= 0:
        return []
    buckets: dict[Hashable, list[T]] = {key: [] for key in category_order}
    for candidate in candidates:
        buckets.setdefault(category(candidate), []).append(candidate)
    selected: list[T] = []
    for key in category_order:
        if buckets.get(key):
            selected.append(buckets[key].pop(0))
            if len(selected) == limit:
                return selected
    for candidate in candidates:
        if candidate not in selected:
            selected.append(candidate)
            if len(selected) == limit:
                break
    return selected


def schema_quota_score_fill(
    candidates: Sequence[T],
    *,
    category: Callable[[T], Hashable],
    category_order: Sequence[Hashable],
    limit: int,
    within_category_key: Callable[[T], object] | None = None,
    quota_fraction: float = 1.0,
) -> list[T]:
    """Reserve a finite local prefix per schema, then fill by global score.

    Global proof relevance and local construction coverage are distinct axes.
    ``within_category_key`` prevents a global relation score from erasing a
    structurally early candidate inside an otherwise useful schema.
    """

    if limit <= 0:
        return []
    if not 0.0 <= quota_fraction <= 1.0:
        raise ValueError("quota_fraction must be between zero and one")
    ordered_categories = tuple(dict.fromkeys(category_order))
    reserved = int(limit * quota_fraction)
    quota = (
        max(1, reserved // max(1, len(ordered_categories)))
        if reserved > 0
        else 0
    )
    buckets: dict[Hashable, list[T]] = {key: [] for key in ordered_categories}
    for candidate in candidates:
        buckets.setdefault(category(candidate), []).append(candidate)
    if within_category_key is not None:
        for values in buckets.values():
            values.sort(key=within_category_key)
    selected: list[T] = []
    for index in range(quota):
        for key in ordered_categories:
            values = buckets.get(key, ())
            if index < len(values):
                selected.append(values[index])
                if len(selected) == limit:
                    return selected
    for candidate in candidates:
        if candidate not in selected:
            selected.append(candidate)
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


def construction_semantic_edges(
    name: str,
    arguments: Sequence[str],
) -> tuple[tuple[str, str], ...]:
    """Return typed point-pairs that denote an actual geometric object role."""

    return tuple(
        (left, right)
        for left, right, _ in construction_semantic_weighted_edges(name, arguments)
    )


def construction_semantic_weighted_edges(
    name: str,
    arguments: Sequence[str],
) -> tuple[tuple[str, str, int], ...]:
    """Return semantic role edges with a finite type-derived specificity."""

    args = tuple(arguments)
    index_pairs: tuple[tuple[int, int], ...]
    if name == "angle_bisector" and len(args) >= 4:
        index_pairs = ((0, 2), (1, 2), (2, 3))
    elif name == "on_aline" and len(args) >= 6:
        index_pairs = ((0, 1), (1, 2), (3, 4), (4, 5))
    elif name in {"on_pline", "on_tline"} and len(args) >= 4:
        index_pairs = ((0, 1), (2, 3))
    elif name == "intersection_ll" and len(args) >= 5:
        index_pairs = (
            (0, 1),
            (0, 2),
            (1, 2),
            (0, 3),
            (0, 4),
            (3, 4),
        )
    elif name in {"midpoint", "mirror", "on_line", "between_bound"}:
        index_pairs = tuple(combinations(range(len(args)), 2))
    elif name == "foot" and len(args) >= 4:
        index_pairs = ((0, 1), (0, 2), (0, 3), (2, 3))
    elif name in {"reflect", "on_dia"} and len(args) >= 3:
        index_pairs = ((0, 1), (1, 2))
    elif name in {
        "triangle",
        "orthocenter",
        "incenter",
        "excenter",
        "circumcenter",
        "circle",
        "on_circum",
    }:
        index_pairs = tuple(combinations(range(len(args)), 2))
    elif args:
        index_pairs = tuple((0, index) for index in range(1, len(args)))
    else:
        index_pairs = ()
    weighted: list[tuple[str, str, int]] = []
    for left, right in index_pairs:
        if left >= len(args) or right >= len(args) or args[left] == args[right]:
            continue
        weight = 2
        if name == "angle_bisector":
            weight = 4 if (left, right) == (0, 2) else 2
        elif name == "on_aline":
            weight = 3 if (left, right) == (0, 1) else 2
        elif name in {"on_line", "midpoint", "mirror"}:
            weight = 3
        elif name == "intersection_ll":
            weight = 4 if left == 0 else 3
        elif name == "triangle":
            weight = 1
        elif name in {"circle", "circumcenter", "incenter", "excenter"}:
            weight = 3 if left == 0 else 1
        weighted.append((args[left], args[right], weight))
    return tuple(weighted)


def augment_semantic_role_graph(
    base_graph: Mapping[str, set[str]],
    steps: Sequence[tuple[str, str, tuple[str, ...]]],
) -> dict[str, set[str]]:
    graph = {point: set(neighbors) for point, neighbors in base_graph.items()}
    for family, output, inputs in steps:
        graph.setdefault(output, set())
        for left, right in construction_semantic_edges(family, (output, *inputs)):
            graph.setdefault(left, set()).add(right)
            graph.setdefault(right, set()).add(left)
    return graph


def augment_semantic_role_weights(
    base_weights: Mapping[tuple[str, str], int],
    steps: Sequence[tuple[str, str, tuple[str, ...]]],
) -> dict[tuple[str, str], int]:
    weights = dict(base_weights)
    for family, output, inputs in steps:
        for left, right, weight in construction_semantic_weighted_edges(
            family, (output, *inputs)
        ):
            key = tuple(sorted((left, right)))
            weights[key] = max(weights.get(key, 0), weight)
    return weights


def _construction_role_pairs(
    family: ConstructionFamily,
    input_count: int,
) -> tuple[tuple[int, int], ...]:
    if family.name == "intersection_ll":
        return ((0, 1), (2, 3))
    if family.name in {"foot", "reflect"}:
        return ((1, 2),)
    if family.symmetry == "line_relation":
        return ((0, 1), (3, 4))
    if family.symmetry == "relation_pair":
        return ((1, 2), (4, 5))
    if family.name in {"on_pline", "on_tline"}:
        return ((1, 2),)
    if family.name in {"on_line", "on_bline", "on_circle", "on_dia"}:
        return ((0, 1),)
    return tuple(combinations(range(input_count), 2))


def _generated_role_signature(
    family: ConstructionFamily,
    inputs: Sequence[str],
    generated_points: set[str],
) -> tuple[str, ...]:
    positions = {index for index, point in enumerate(inputs) if point in generated_points}
    if not positions:
        return ("none",)
    if family.symmetry == "head_pair":
        roles = []
        if 0 in positions:
            roles.append("head")
        if positions.intersection({1, 2}):
            roles.append("pair")
        return tuple(roles)
    if family.symmetry == "line_pair":
        roles = []
        if positions.intersection({0, 1}):
            roles.append("line1")
        if positions.intersection({2, 3}):
            roles.append("line2")
        return tuple(roles)
    return tuple(f"arg{index}" for index in sorted(positions))


def _role_balanced_prefix(
    candidates: Sequence[TypedConstructionCandidate],
    family: ConstructionFamily,
    generated_points: set[str],
    limit: int,
) -> list[TypedConstructionCandidate]:
    if limit <= 0 or not generated_points:
        return list(candidates[:limit])
    buckets: dict[tuple[str, ...], list[TypedConstructionCandidate]] = {}
    order: list[tuple[str, ...]] = []
    for candidate in candidates:
        signature = _generated_role_signature(
            family, candidate.inputs, generated_points
        )
        if signature not in buckets:
            buckets[signature] = []
            order.append(signature)
        buckets[signature].append(candidate)
    selected: list[TypedConstructionCandidate] = []
    while len(selected) < limit:
        progressed = False
        for signature in order:
            if buckets[signature]:
                selected.append(buckets[signature].pop(0))
                progressed = True
                if len(selected) == limit:
                    return selected
        if not progressed:
            break
    return selected


def construction_role_adjacency_count(
    family: ConstructionFamily,
    inputs: Sequence[str],
    graph: Mapping[str, set[str]],
) -> int:
    """Count only adjacencies that occupy an input line/object role."""

    pairs = _construction_role_pairs(family, len(inputs))
    return sum(inputs[right] in graph.get(inputs[left], set()) for left, right in pairs)


def construction_role_adjacency_weight(
    family: ConstructionFamily,
    inputs: Sequence[str],
    weights: Mapping[tuple[str, str], int],
) -> int:
    return sum(
        weights.get(tuple(sorted((inputs[left], inputs[right]))), 0)
        for left, right in _construction_role_pairs(family, len(inputs))
    )


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
    relation_demands: Sequence[object] = (),
    role_graph: Mapping[str, set[str]] | None = None,
    role_weights: Mapping[tuple[str, str], int] | None = None,
    required_input_points: set[str] | None = None,
) -> list[TypedConstructionCandidate]:
    """Enumerate a balanced finite candidate set from typed structure only."""

    generated_points = generated_points or set()
    used_keys = used_keys or set()
    proof_relevance = proof_relevance or {}
    distances = goal_distances(graph, goal_multiplicity)
    ordered_points = tuple(
        sorted(
            set(points),
            key=lambda point: (
                -goal_multiplicity.get(point, 0),
                -proof_relevance.get(point, 0.0),
                0 if point in generated_points else 1,
                distances.get(point, 10_000),
                point,
            ),
        )
    )
    normalized_demands = tuple(
        (
            str(getattr(demand, "predicate", "")).lower(),
            tuple(str(item) for item in getattr(demand, "arguments", ())),
        )
        for demand in relation_demands
    )
    role_graph = role_graph or graph
    role_weights = role_weights or {}
    required_input_points = required_input_points or set()
    orbit = set(orbit_inputs)
    selected: list[TypedConstructionCandidate] = []
    for family in families:
        family_candidates: list[TypedConstructionCandidate] = []
        family_points = (
            ordered_points[:10] if family.input_arity >= 5 else ordered_points
        )
        def ranked_candidate(inputs: tuple[str, ...]) -> TypedConstructionCandidate:
            pair_count = 0
            for left, right in combinations(inputs, 2):
                if right in graph.get(left, set()):
                    pair_count += 1
            role_pair_count = construction_role_adjacency_count(
                family, inputs, role_graph
            )
            role_pair_weight = construction_role_adjacency_weight(
                family, inputs, role_weights
            )
            role_pair_density = role_pair_weight / max(
                1, len(_construction_role_pairs(family, len(inputs)))
            )
            novel_input_count = (
                len(set(inputs) - orbit - generated_points) if orbit else 0
            )
            generated_roles = _generated_role_signature(
                family, inputs, generated_points
            )
            generated_role_priority = (
                0
                if family.symmetry != "head_pair" or "pair" in generated_roles
                else 1
            )
            goal_point_count = sum(
                goal_multiplicity.get(point, 0) for point in inputs
            )
            initial_goal_rank = (
                0
                if generated_points or goal_point_count
                else 1
            )
            input_distances = tuple(distances.get(point, 10_000) for point in inputs)
            demand_rank = (
                min(
                    (
                        0 if predicate in family.output_channels else 1,
                        -len(
                            set(inputs)
                            & {
                                point
                                for point in arguments
                                if point and not point.startswith("?")
                            }
                        ),
                        len(
                            {
                                point
                                for point in arguments
                                if point and not point.startswith("?")
                            }
                            - set(inputs)
                        ),
                    )
                    for predicate, arguments in normalized_demands
                )
                if normalized_demands
                else (1, 0, 0)
            )
            rank: tuple[object, ...] = (
                0 if generated_points.intersection(inputs) else 1,
                generated_role_priority,
                0 if not orbit or novel_input_count else 1,
                -role_pair_density,
                -role_pair_weight,
                -role_pair_count,
                initial_goal_rank,
                -sum(proof_relevance.get(point, 0.0) for point in inputs),
                0 if goal_point_count else 1,
                demand_rank[0],
                -pair_count,
                -goal_point_count,
                demand_rank[1],
                demand_rank[2],
                sum(input_distances),
                max(input_distances),
                family.input_arity,
                family.name,
                inputs,
            )
            return TypedConstructionCandidate(family.name, inputs, rank)

        for inputs in _family_inputs(family_points, family):
            if not family.allow_repeated_inputs and len(set(inputs)) != len(inputs):
                continue
            if required_input_points and not required_input_points.intersection(inputs):
                continue
            key = f"{family.name}({','.join(inputs)})"
            if key in used_keys:
                continue
            # HAGeo Pass@K uses seeded random ranking.  Its shuffle and role
            # balancing only inspect the family and input tuple, so computing
            # the expensive 19-field structural rank for every rejected tuple
            # is unnecessary.  The selected prefix is ranked below, preserving
            # the exact candidate order and downstream tie-break semantics.
            candidate = (
                TypedConstructionCandidate(family.name, inputs, ())
                if ranking == "random"
                else ranked_candidate(inputs)
            )
            if numerical_precondition_holds(candidate, coordinates):
                family_candidates.append(candidate)
        if ranking == "structural":
            family_candidates.sort(
                key=lambda candidate: (
                    0
                    if candidate.family == orbit_family
                    and bool(orbit.intersection(candidate.inputs))
                    else 1,
                    candidate.structural_rank,
                    -len(orbit.intersection(candidate.inputs)),
                )
            )
        elif ranking == "random":
            random.Random(f"{seed}|{family.name}").shuffle(family_candidates)
        else:
            raise ValueError(f"unknown ranking: {ranking}")
        prefix = _role_balanced_prefix(
            family_candidates,
            family,
            generated_points,
            per_family_limit,
        )
        selected.extend(
            ranked_candidate(candidate.inputs) if ranking == "random" else candidate
            for candidate in prefix
        )
    if ranking == "random":
        random.Random(f"{seed}|all-families").shuffle(selected)
        return selected
    return sorted(selected, key=lambda candidate: candidate.structural_rank)


def family_by_name(name: str) -> ConstructionFamily:
    for family in DEFAULT_POINT_FAMILIES:
        if family.name == name:
            return family
    raise KeyError(name)
