"""LLM-free auxiliary-construction search over AlphaGeometry2 DDAR.

The search space is finite at every depth.  Candidates are generated from a
typed Euclidean construction grammar, rejected numerically when degenerate,
and accepted only when the symbolic DDAR backend proves the original goal.
"""

from __future__ import annotations

import contextlib
import io
import itertools
from dataclasses import dataclass
from fractions import Fraction
from typing import Any

import numpy as np


EPS = 1e-8
GRAMMAR_INVENTORY = (
    "line_intersection",
    "parallel_line_intersection",
    "perpendicular_line_intersection",
    "line_circle_intersection",
    "midpoint",
    "perpendicular_foot",
    "reflection",
    "equilateral_vertex",
    "circumcenter",
    "internal_division",
    "angle_bisector_point",
)


@dataclass(frozen=True)
class ConstructionCandidate:
    kind: str
    value: tuple[float, float]
    predicates: tuple[tuple[str, tuple[str, ...], tuple[int | float, ...]], ...]
    source_points: tuple[str, ...]
    score_hint: int

    @property
    def signature(self) -> tuple[Any, ...]:
        return (
            self.kind,
            round(self.value[0], 9),
            round(self.value[1], 9),
            self.predicates,
        )


@dataclass
class SearchState:
    problem: Any
    constructions: list[dict[str, Any]]
    goal_gap: int
    derived_size: int


def evaluate_problem(problem: Any, DDAR: type) -> tuple[bool, int, int, int]:
    engine = DDAR(problem.points)
    for predicate in problem.preds:
        engine.force_pred(predicate)
    trace = io.StringIO()
    with contextlib.redirect_stdout(trace):
        engine.deduction_closure(progress_dot=True)
    proved = bool(engine.check_pred(problem.goal))
    gap = 0 if proved else predicate_gap(engine, problem.goal)
    derived_size = (
        len(engine.lines)
        + len(engine.circles)
        + len(engine.known_similar)
        + len(engine.pair_to_line)
    )
    return proved, gap, derived_size, trace.getvalue().count(".")


def predicate_gap(engine: Any, predicate: Any) -> int:
    """Count unresolved linear atoms in the goal after DDAR elimination."""
    try:
        if predicate.name in ("angeq", "para", "perp", "s_angle", "aconst", "eqangle"):
            value = engine.elim_angle.simplify(engine.pred_to_angle(predicate))
            return max(1, len(value.comb.d))
        if predicate.name in ("distmeq", "cong", "eqratio", "rconst"):
            value = engine.elim_dist_mul.simplify(engine.pred_to_dist_mul(predicate))
            return max(1, len(value.comb.d))
        if predicate.name == "distseq":
            value = engine.elim_dist_add.simplify(engine.pred_to_dist_add(predicate))
            return max(1, len(value.comb.d))
    except Exception:
        pass
    return 1


def search_auxiliary_constructions(
    problem: Any,
    *,
    AGProblem: type,
    DDAR: type,
    max_depth: int = 2,
    beam_width: int = 8,
    max_attempts: int = 96,
    allowed_kinds: set[str] | None = None,
    preferred_points: set[str] | None = None,
    tree_name: str = "classic",
) -> dict[str, Any]:
    proved, gap, derived, rounds = evaluate_problem(problem, DDAR)
    if proved:
        return search_result(
            tree_name=tree_name,
            status="proved",
            proved=True,
            baseline_proved=True,
            attempts=0,
            depth=0,
            constructions=[],
            goal_gap=0,
            derived_size=derived,
            closure_rounds=rounds,
            attempt_trace=[],
        )

    frontier = [SearchState(problem, [], gap, derived)]
    seen_states: set[tuple[Any, ...]] = set()
    attempts = 0
    attempt_trace: list[dict[str, Any]] = []
    best = frontier[0]
    for depth in range(1, max_depth + 1):
        next_states: list[SearchState] = []
        for state in frontier:
            candidates = generate_candidates(
                state.problem,
                allowed_kinds=allowed_kinds,
                preferred_points=preferred_points,
            )
            for candidate in candidates:
                if attempts >= max_attempts:
                    break
                state_signature = tuple(item["signature"] for item in state.constructions) + (candidate.signature,)
                if state_signature in seen_states:
                    continue
                seen_states.add(state_signature)
                attempts += 1
                extended, record = apply_candidate(state.problem, candidate, AGProblem, len(state.constructions) + 1)
                try:
                    solved, candidate_gap, candidate_derived, candidate_rounds = evaluate_problem(extended, DDAR)
                except Exception as error:
                    attempt_trace.append({
                        "attempt": attempts,
                        "depth": depth,
                        "kind": candidate.kind,
                        "source_points": list(candidate.source_points),
                        "status": "rejected",
                        "reason": type(error).__name__,
                    })
                    continue
                constructions = [*state.constructions, record]
                candidate_state = SearchState(extended, constructions, candidate_gap, candidate_derived)
                attempt_trace.append({
                    "attempt": attempts,
                    "depth": depth,
                    "kind": candidate.kind,
                    "source_points": list(candidate.source_points),
                    "goal_gap_before": state.goal_gap,
                    "goal_gap_after": candidate_gap,
                    "derived_size_before": state.derived_size,
                    "derived_size_after": candidate_derived,
                    "closure_rounds": candidate_rounds,
                    "status": "proved" if solved else "retained_for_ranking",
                })
                if rank_state(candidate_state) < rank_state(best):
                    best = candidate_state
                if solved:
                    return search_result(
                        tree_name=tree_name,
                        status="proved",
                        proved=True,
                        baseline_proved=False,
                        attempts=attempts,
                        depth=depth,
                        constructions=constructions,
                        goal_gap=0,
                        derived_size=candidate_derived,
                        closure_rounds=candidate_rounds,
                        attempt_trace=attempt_trace,
                    )
                next_states.append(candidate_state)
            if attempts >= max_attempts:
                break
        if not next_states or attempts >= max_attempts:
            break
        next_states.sort(key=rank_state)
        frontier = next_states[:beam_width]

    return search_result(
        tree_name=tree_name,
        status="unproved",
        proved=False,
        baseline_proved=False,
        attempts=attempts,
        depth=len(best.constructions),
        constructions=best.constructions,
        goal_gap=best.goal_gap,
        derived_size=best.derived_size,
        closure_rounds=0,
        attempt_trace=attempt_trace,
    )


def rank_state(state: SearchState) -> tuple[int, int, int]:
    return (state.goal_gap, -state.derived_size, len(state.constructions))


def generate_candidates(
    problem: Any,
    *,
    allowed_kinds: set[str] | None = None,
    preferred_points: set[str] | None = None,
) -> list[ConstructionCandidate]:
    all_points = list(problem.points)
    point_names = {point.name for point in all_points}
    goal_names = {point.name for point in problem.goal.points}
    premise_frequency: dict[str, int] = {name: 0 for name in point_names}
    for predicate in problem.preds:
        for point in predicate.points:
            premise_frequency[point.name] = premise_frequency.get(point.name, 0) + 1
    points = select_active_points(all_points, goal_names, premise_frequency)

    candidates: list[ConstructionCandidate] = []
    lines = list(itertools.combinations(points, 2))
    ratios = construction_ratios(problem)
    for (a, b), (c, d) in itertools.combinations(lines, 2):
        value = line_intersection(a.value, b.value, c.value, d.value)
        if value is None or near_existing(value, all_points):
            continue
        candidates.append(candidate(
            "line_intersection",
            value,
            (("coll", ("$", a.name, b.name), ()), ("coll", ("$", c.name, d.name), ())),
            (a.name, b.name, c.name, d.name),
            goal_names,
            premise_frequency,
        ))

    for a, b in lines:
        value = (np.asarray(a.value, dtype=float) + np.asarray(b.value, dtype=float)) / 2
        if near_existing(value, all_points):
            continue
        candidates.append(candidate(
            "midpoint",
            value,
            (("coll", (a.name, "$", b.name), ()), ("cong", (a.name, "$", "$", b.name), ())),
            (a.name, b.name),
            goal_names,
            premise_frequency,
        ))

        reflected_ab = 2 * np.asarray(b.value, dtype=float) - np.asarray(a.value, dtype=float)
        if not near_existing(reflected_ab, all_points):
            candidates.append(candidate(
                "reflection",
                reflected_ab,
                (("coll", ("$", a.name, b.name), ()), ("cong", (b.name, a.name, b.name, "$"), ())),
                (a.name, b.name),
                goal_names,
                premise_frequency,
            ))
        reflected_ba = 2 * np.asarray(a.value, dtype=float) - np.asarray(b.value, dtype=float)
        if not near_existing(reflected_ba, all_points):
            candidates.append(candidate(
                "reflection",
                reflected_ba,
                (("coll", ("$", b.name, a.name), ()), ("cong", (a.name, b.name, a.name, "$"), ())),
                (b.name, a.name),
                goal_names,
                premise_frequency,
            ))
        for value in equilateral_vertices(a.value, b.value):
            if near_existing(value, all_points):
                continue
            candidates.append(candidate(
                "equilateral_vertex",
                value,
                (("cong", ("$", a.name, a.name, b.name), ()), ("cong", ("$", b.name, a.name, b.name), ())),
                (a.name, b.name),
                goal_names,
                premise_frequency,
            ))

        for ratio in ratios:
            for left, right in ((a, b), (b, a)):
                value = internal_division(left.value, right.value, ratio)
                if near_existing(value, all_points):
                    continue
                candidates.append(candidate(
                    "internal_division",
                    value,
                    (
                        ("coll", (left.name, "$", right.name), ()),
                        ("rconst", (left.name, "$", "$", right.name), (ratio,)),
                        ("distseq", (left.name, "$", "$", right.name, left.name, right.name), (1, 1, -1)),
                    ),
                    (left.name, right.name),
                    goal_names,
                    premise_frequency,
                ))

    for vertex, first, second in itertools.permutations(points, 3):
        if first.name > second.name:
            continue
        value = angle_bisector_point(vertex.value, first.value, second.value)
        if value is None or near_existing(value, all_points):
            continue
        candidates.append(candidate(
            "angle_bisector_point",
            value,
            (("eqangle", (
                vertex.name, first.name, vertex.name, "$",
                vertex.name, "$", vertex.name, second.name,
            ), ()),),
            (vertex.name, first.name, second.name),
            goal_names,
            premise_frequency,
        ))

    for p in points:
        for a, b in lines:
            if p in (a, b):
                continue
            value = perpendicular_foot(p.value, a.value, b.value)
            if value is None or near_existing(value, all_points):
                continue
            candidates.append(candidate(
                "perpendicular_foot",
                value,
                (("coll", ("$", a.name, b.name), ()), ("perp", (p.name, "$", a.name, b.name), ())),
                (p.name, a.name, b.name),
                goal_names,
                premise_frequency,
            ))


    for p in points:
        for a, b in lines:
            direction = np.asarray(b.value, dtype=float) - np.asarray(a.value, dtype=float)
            if float(direction @ direction) <= EPS:
                continue
            for c, d in lines:
                if {c.name, d.name} == {a.name, b.name}:
                    continue
                for kind, through_direction, relation in (
                    ("parallel_line_intersection", direction, "para"),
                    ("perpendicular_line_intersection", np.asarray([-direction[1], direction[0]]), "perp"),
                ):
                    value = line_intersection(c.value, d.value, p.value, np.asarray(p.value, dtype=float) + through_direction)
                    if value is None or near_existing(value, all_points):
                        continue
                    candidates.append(candidate(
                        kind,
                        value,
                        (("coll", ("$", c.name, d.name), ()), (relation, (p.name, "$", a.name, b.name), ())),
                        (p.name, a.name, b.name, c.name, d.name),
                        goal_names,
                        premise_frequency,
                    ))

    for a, b in lines:
        for center in points:
            for radius_point in points:
                if center is radius_point:
                    continue
                for value in line_circle_intersections(a.value, b.value, center.value, radius_point.value):
                    if near_existing(value, all_points):
                        continue
                    candidates.append(candidate(
                        "line_circle_intersection",
                        value,
                        (("coll", ("$", a.name, b.name), ()), ("cong", (center.name, "$", center.name, radius_point.name), ())),
                        (a.name, b.name, center.name, radius_point.name),
                        goal_names,
                        premise_frequency,
                    ))

    for a, b, c in itertools.combinations(points, 3):
        value = circumcenter(a.value, b.value, c.value)
        if value is None or near_existing(value, all_points):
            continue
        candidates.append(candidate(
            "circumcenter",
            value,
            (("cong", ("$", a.name, "$", b.name), ()), ("cong", ("$", b.name, "$", c.name), ())),
            (a.name, b.name, c.name),
            goal_names,
            premise_frequency,
        ))

    unique: dict[tuple[Any, ...], ConstructionCandidate] = {}
    for item in candidates:
        unique.setdefault(item.signature, item)
    values = unique.values()
    if allowed_kinds is not None:
        values = (item for item in values if item.kind in allowed_kinds)
    preferred_points = preferred_points or set()
    return sorted(
        values,
        key=lambda item: (
            -len(set(item.source_points) & preferred_points),
            -item.score_hint,
            item.kind,
            item.signature,
        ),
    )


def select_active_points(
    points: list[Any],
    goal_names: set[str],
    premise_frequency: dict[str, int],
    *,
    budget: int = 8,
) -> list[Any]:
    """Bound each search layer while retaining every goal point."""
    ordered = sorted(
        points,
        key=lambda point: (
            point.name not in goal_names,
            -premise_frequency.get(point.name, 0),
            point.name,
        ),
    )
    selected = ordered[:max(budget, len(goal_names))]
    selected_names = {point.name for point in selected}
    for point in points:
        if point.name in goal_names and point.name not in selected_names:
            selected.append(point)
    return selected


def candidate(
    kind: str,
    value: np.ndarray,
    predicates: tuple[tuple[str, tuple[str, ...], tuple[int | float, ...]], ...],
    source_points: tuple[str, ...],
    goal_names: set[str],
    premise_frequency: dict[str, int],
) -> ConstructionCandidate:
    unique_sources = set(source_points)
    score = 4 * len(unique_sources & goal_names) + sum(premise_frequency.get(name, 0) for name in unique_sources)
    return ConstructionCandidate(
        kind=kind,
        value=(float(value[0]), float(value[1])),
        predicates=predicates,
        source_points=tuple(source_points),
        score_hint=score,
    )


def apply_candidate(problem: Any, item: ConstructionCandidate, AGProblem: type, ordinal: int) -> tuple[Any, dict[str, Any]]:
    point_type = type(problem.points[0])
    predicate_type = type(problem.goal)
    name = unused_name({point.name for point in problem.points}, f"aux{ordinal}")
    new_point = point_type(name=name, value=np.asarray(item.value, dtype=float))
    mapping = {point.name: point for point in problem.points}
    mapping[name] = new_point
    predicates = []
    rendered = []
    for predicate_name, names, constants in item.predicates:
        resolved_names = tuple(name if value == "$" else value for value in names)
        predicates.append(predicate_type(
            name=predicate_name,
            points=[mapping[value] for value in resolved_names],
            constants=list(constants),
        ))
        rendered.append(" ".join((predicate_name, *resolved_names, *map(str, constants))))
    extended = AGProblem(
        points=[*problem.points, new_point],
        preds=[*problem.preds, *predicates],
        goal=problem.goal,
    )
    record = {
        "name": name,
        "kind": item.kind,
        "value": list(item.value),
        "predicates": rendered,
        "source_points": list(item.source_points),
        "signature": item.signature,
        "numeric_validation": "passed",
    }
    return extended, record


def line_intersection(a: np.ndarray, b: np.ndarray, c: np.ndarray, d: np.ndarray) -> np.ndarray | None:
    direction1 = np.asarray(b, dtype=float) - np.asarray(a, dtype=float)
    direction2 = np.asarray(d, dtype=float) - np.asarray(c, dtype=float)
    matrix = np.column_stack((direction1, -direction2))
    determinant = float(np.linalg.det(matrix))
    if abs(determinant) <= EPS:
        return None
    parameters = np.linalg.solve(matrix, np.asarray(c, dtype=float) - np.asarray(a, dtype=float))
    value = np.asarray(a, dtype=float) + parameters[0] * direction1
    if abs(cross2d(direction1, value - np.asarray(a, dtype=float))) > 1e-6:
        return None
    if abs(cross2d(direction2, value - np.asarray(c, dtype=float))) > 1e-6:
        return None
    return value


def cross2d(left: np.ndarray, right: np.ndarray) -> float:
    return float(left[0] * right[1] - left[1] * right[0])


def perpendicular_foot(p: np.ndarray, a: np.ndarray, b: np.ndarray) -> np.ndarray | None:
    direction = np.asarray(b, dtype=float) - np.asarray(a, dtype=float)
    denominator = float(direction @ direction)
    if denominator <= EPS:
        return None
    parameter = float((np.asarray(p, dtype=float) - np.asarray(a, dtype=float)) @ direction / denominator)
    value = np.asarray(a, dtype=float) + parameter * direction
    if abs(float((np.asarray(p, dtype=float) - value) @ direction)) > 1e-6:
        return None
    return value


def equilateral_vertices(a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    midpoint = (a + b) / 2
    direction = b - a
    offset = np.asarray([-direction[1], direction[0]]) * (3 ** 0.5 / 2)
    return midpoint + offset, midpoint - offset


def construction_ratios(problem: Any) -> tuple[int, ...]:
    values = {2}
    for predicate_item in [*problem.preds, problem.goal]:
        if predicate_item.name != "rconst" or not predicate_item.constants:
            continue
        value = Fraction(predicate_item.constants[0])
        if value.denominator == 1 and 1 < value.numerator <= 8:
            values.add(value.numerator)
    return tuple(sorted(values))


def internal_division(a: np.ndarray, b: np.ndarray, ratio: int) -> np.ndarray:
    """Return P on AB with AP/PB = ratio."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    return (a + ratio * b) / (ratio + 1)


def angle_bisector_point(vertex: np.ndarray, first: np.ndarray, second: np.ndarray) -> np.ndarray | None:
    vertex = np.asarray(vertex, dtype=float)
    left = np.asarray(first, dtype=float) - vertex
    right = np.asarray(second, dtype=float) - vertex
    left_norm = float(np.linalg.norm(left))
    right_norm = float(np.linalg.norm(right))
    if left_norm <= EPS or right_norm <= EPS:
        return None
    direction = left / left_norm + right / right_norm
    if float(direction @ direction) <= EPS:
        return None
    return vertex + direction


def line_circle_intersections(
    a: np.ndarray,
    b: np.ndarray,
    center: np.ndarray,
    radius_point: np.ndarray,
) -> tuple[np.ndarray, ...]:
    a = np.asarray(a, dtype=float)
    direction = np.asarray(b, dtype=float) - a
    center = np.asarray(center, dtype=float)
    radius_squared = float(np.sum((np.asarray(radius_point, dtype=float) - center) ** 2))
    denominator = float(direction @ direction)
    if denominator <= EPS or radius_squared <= EPS:
        return ()
    relative = a - center
    linear = 2 * float(relative @ direction)
    constant = float(relative @ relative) - radius_squared
    discriminant = linear * linear - 4 * denominator * constant
    if discriminant < -EPS:
        return ()
    if abs(discriminant) <= EPS:
        parameters = (-linear / (2 * denominator),)
    else:
        root = discriminant ** 0.5
        parameters = ((-linear + root) / (2 * denominator), (-linear - root) / (2 * denominator))
    return tuple(a + parameter * direction for parameter in parameters)


def circumcenter(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> np.ndarray | None:
    a, b, c = map(lambda value: np.asarray(value, dtype=float), (a, b, c))
    matrix = 2 * np.vstack((b - a, c - a))
    if abs(float(np.linalg.det(matrix))) <= EPS:
        return None
    rhs = np.asarray([b @ b - a @ a, c @ c - a @ a], dtype=float)
    value = np.linalg.solve(matrix, rhs)
    distances = [float(np.linalg.norm(value - point)) for point in (a, b, c)]
    if max(distances) - min(distances) > 1e-6:
        return None
    return value


def near_existing(value: np.ndarray, points: list[Any]) -> bool:
    return any(float(np.linalg.norm(np.asarray(point.value, dtype=float) - value)) <= 1e-7 for point in points)


def unused_name(existing: set[str], seed: str) -> str:
    if seed not in existing:
        return seed
    index = 2
    while f"{seed}_{index}" in existing:
        index += 1
    return f"{seed}_{index}"


def search_result(**values: Any) -> dict[str, Any]:
    return {
        **values,
        "backend": "google-deepmind/alphageometry2-DDAR",
        "proposal_engine": "finite_typed_construction_grammar",
        "construction_grammar": list(GRAMMAR_INVENTORY),
        "uses_language_model": False,
    }
