"""Finite SKEST-style ensemble over the MathOS auxiliary grammar."""

from __future__ import annotations

from typing import Any

from alphageometry2_analysis import analyze_problem
from alphageometry2_auxiliary_search import GRAMMAR_INVENTORY, search_auxiliary_constructions


TREE_CONFIGURATIONS = (
    ("classic", None, 2, 12, 96),
    ("incidence", {"line_intersection", "parallel_line_intersection", "perpendicular_line_intersection"}, 3, 8, 96),
    ("metric", {"midpoint", "perpendicular_foot", "reflection", "circumcenter"}, 3, 8, 96),
    ("circle", {"line_circle_intersection", "circumcenter", "equilateral_vertex"}, 3, 8, 96),
    ("deep_narrow", set(GRAMMAR_INVENTORY), 4, 4, 128),
    ("shallow_wide", set(GRAMMAR_INVENTORY), 1, 32, 128),
)


def ensemble_search(
    problem: Any,
    *,
    AGProblem: type,
    DDAR: type,
    max_depth: int = 4,
    beam_width: int = 16,
    max_attempts: int = 384,
) -> dict[str, Any]:
    analysis = analyze_problem(problem, DDAR)
    preferred = set(analysis["preferred_points"][:8])
    remaining = max_attempts
    trees: list[dict[str, Any]] = []
    best: dict[str, Any] | None = None
    for name, kinds, depth, width, attempts in TREE_CONFIGURATIONS:
        if remaining <= 0:
            break
        result = search_auxiliary_constructions(
            problem,
            AGProblem=AGProblem,
            DDAR=DDAR,
            max_depth=min(max_depth, depth),
            beam_width=min(beam_width, width),
            max_attempts=min(remaining, attempts),
            allowed_kinds=kinds,
            preferred_points=preferred,
            tree_name=name,
        )
        consumed = int(result.get("attempts", 0))
        remaining -= consumed
        trees.append({
            "name": name,
            "proved": result["proved"],
            "attempts": consumed,
            "depth": result.get("depth", 0),
            "goal_gap": result.get("goal_gap"),
        })
        if best is None or rank(result) < rank(best):
            best = result
        if result["proved"]:
            break
    assert best is not None
    return {
        **best,
        "proposal_engine": "finite_SKEST_style_ensemble",
        "search_algorithm": "multi-tree distributions with shared S1/S2/S3 analysis",
        "analysis": analysis,
        "trees": trees,
        "attempt_budget": max_attempts,
        "attempts_used": max_attempts - remaining,
        "uses_language_model": False,
    }


def rank(result: dict[str, Any]) -> tuple[int, int, int]:
    return (
        0 if result.get("proved") else 1,
        int(result.get("goal_gap", 1_000_000)),
        -int(result.get("derived_size", 0)),
    )
