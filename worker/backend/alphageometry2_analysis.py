"""AlphaGeometry2-style S1/S2/S3 analysis for finite symbolic search.

S1 contains facts deduced from the original premises. S2 contains additional
facts available after temporarily assuming the goal. S3 contains additional
facts that are numerically true in the supplied diagram. Only S1 is proved;
S2 and S3 are search hints and are never inserted into a proof state.
"""

from __future__ import annotations

import contextlib
import io
import itertools
from typing import Any, Iterable

import numpy as np


def analyze_problem(problem: Any, DDAR: type, *, max_facts: int = 256) -> dict[str, Any]:
    candidates = list(candidate_predicates(problem))
    s1 = symbolic_facts(problem, DDAR, candidates)
    assumed = type(problem)(
        points=list(problem.points),
        preds=[*problem.preds, problem.goal],
        goal=problem.goal,
    )
    s2_all = symbolic_facts(assumed, DDAR, candidates)
    numeric = {render(item) for item in candidates if numerically_true(item)}
    s2 = s2_all - s1
    s3 = numeric - s1 - s2
    s1_values = sorted(s1)[:max_facts]
    s2_values = sorted(s2)[:max_facts]
    s3_values = sorted(s3)[:max_facts]
    preferred = point_frequency([*s2_values, *s3_values])
    return {
        "S1": s1_values,
        "S2": s2_values,
        "S3": s3_values,
        "preferred_points": preferred,
        "analysis_text": serialize_analysis(s1_values, s2_values, s3_values),
        "soundness_boundary": "S2/S3 rank proposals only; DDAR receives original premises plus explicit constructions",
    }


def symbolic_facts(problem: Any, DDAR: type, candidates: list[Any]) -> set[str]:
    engine = DDAR(problem.points)
    try:
        for predicate in problem.preds:
            engine.force_pred(predicate)
        with contextlib.redirect_stdout(io.StringIO()):
            engine.deduction_closure(progress_dot=False)
    except (AssertionError, ValueError, ZeroDivisionError):
        return set()
    result: set[str] = set()
    for predicate in candidates:
        try:
            if engine.check_pred(predicate):
                result.add(render(predicate))
        except Exception:
            continue
    return result


def candidate_predicates(problem: Any) -> Iterable[Any]:
    predicate_type = type(problem.goal)
    points = list(problem.points)
    for triple in itertools.combinations(points, 3):
        yield predicate_type(name="coll", points=list(triple), constants=[])
    for quadruple in itertools.combinations(points, 4):
        yield predicate_type(name="cyclic", points=list(quadruple), constants=[])
    segments = list(itertools.combinations(points, 2))
    for (a, b), (c, d) in itertools.combinations(segments, 2):
        if len({a.name, b.name, c.name, d.name}) < 3:
            continue
        values = [a, b, c, d]
        for name in ("para", "perp", "cong"):
            yield predicate_type(name=name, points=values, constants=[])


def numerically_true(predicate: Any, *, tolerance: float = 1e-6) -> bool:
    values = [np.asarray(point.value, dtype=float) for point in predicate.points]
    try:
        if predicate.name == "coll":
            return abs(cross(values[1] - values[0], values[2] - values[0])) <= tolerance
        if predicate.name == "para":
            return abs(cross(values[1] - values[0], values[3] - values[2])) <= tolerance
        if predicate.name == "perp":
            return abs(float((values[1] - values[0]) @ (values[3] - values[2]))) <= tolerance
        if predicate.name == "cong":
            return abs(distance2(values[0], values[1]) - distance2(values[2], values[3])) <= tolerance
        if predicate.name == "cyclic":
            matrix = np.asarray([[p[0], p[1], p @ p, 1.0] for p in values])
            return abs(float(np.linalg.det(matrix))) <= tolerance
    except (ValueError, np.linalg.LinAlgError):
        return False
    return False


def render(predicate: Any) -> str:
    return " ".join((predicate.name, *(point.name for point in predicate.points)))


def point_frequency(facts: list[str]) -> list[str]:
    counts: dict[str, int] = {}
    for fact in facts:
        for point in fact.split()[1:]:
            counts[point] = counts.get(point, 0) + 1
    return [name for name, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0]))]


def serialize_analysis(s1: list[str], s2: list[str], s3: list[str]) -> str:
    return "\n".join((
        "S1: " + ("; ".join(s1) if s1 else "none"),
        "S2: " + ("; ".join(s2) if s2 else "none"),
        "S3: " + ("; ".join(s3) if s3 else "none"),
    ))


def cross(left: np.ndarray, right: np.ndarray) -> float:
    return float(left[0] * right[1] - left[1] * right[0])


def distance2(left: np.ndarray, right: np.ndarray) -> float:
    delta = left - right
    return float(delta @ delta)
