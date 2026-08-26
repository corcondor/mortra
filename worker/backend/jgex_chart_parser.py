"""Small, dependency-free parser for the JGEX subset used by exact charts.

Exact charts only inspect the construction graph.  Pulling the complete
Newclid runtime into this boundary made certificate replay depend on a
machine-local research environment.  This parser deliberately exposes only
the finite syntax required for structural matching: output points,
construction names and arguments, and goals.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChartConstruction:
    name: str
    args: tuple[str, ...]


@dataclass(frozen=True)
class ChartSetupClause:
    points: tuple[str, ...]
    constructions: tuple[ChartConstruction, ...]


@dataclass(frozen=True)
class ChartGoal:
    predicate: str
    args: tuple[str, ...]

    def __str__(self) -> str:
        return " ".join((self.predicate, *self.args))


@dataclass(frozen=True)
class ChartJGEXFormulation:
    setup_clauses: tuple[ChartSetupClause, ...]
    goals: tuple[ChartGoal, ...]

    @classmethod
    def from_text(cls, source: str) -> "ChartJGEXFormulation":
        if source.count("?") != 1:
            raise ValueError("JGEX chart source must contain exactly one goal separator")
        setup_text, goal_text = source.split("?", maxsplit=1)
        setup = tuple(
            _parse_setup_clause(raw)
            for raw in setup_text.split(";")
            if raw.strip()
        )
        goals = tuple(
            _parse_goal(raw) for raw in goal_text.split(",") if raw.strip()
        )
        if not setup or not goals:
            raise ValueError("JGEX chart source requires setup clauses and a goal")
        return cls(setup_clauses=setup, goals=goals)


def _tokens(raw: str, *, context: str) -> tuple[str, ...]:
    tokens = tuple(raw.strip().split())
    if not tokens:
        raise ValueError(f"empty {context}")
    return tokens


def _parse_setup_clause(raw: str) -> ChartSetupClause:
    if raw.count("=") != 1:
        raise ValueError(f"invalid JGEX setup clause: {raw.strip()}")
    output_text, construction_text = raw.split("=", maxsplit=1)
    points = _tokens(output_text, context="output point list")
    construction_items = []
    for part in construction_text.split(","):
        tokens = _tokens(part, context="construction")
        args = tokens[1:]
        # The frozen corpus contains both ``x = on_line a b`` and
        # ``x = on_line x a b``.  Multi-output constructors can likewise
        # repeat their complete output tuple.  Those names are surface syntax,
        # not mathematical inputs, so normalize them at the parser boundary.
        if len(args) >= len(points) and args[: len(points)] == points:
            args = args[len(points) :]
        construction_items.append(ChartConstruction(tokens[0], args))
    constructions = tuple(construction_items)
    if not constructions:
        raise ValueError(f"setup clause has no construction: {raw.strip()}")
    return ChartSetupClause(points=points, constructions=constructions)


def _parse_goal(raw: str) -> ChartGoal:
    tokens = _tokens(raw, context="goal")
    predicate, args = tokens[0], tokens[1:]
    if predicate == "eqangle":
        args = _canonical_equal_angles(args)
    return ChartGoal(predicate=predicate, args=args)


def _canonical_equal_angles(args: tuple[str, ...]) -> tuple[str, ...]:
    """Mirror Newclid's finite line-pair canonicalization for ``eqangle``."""
    if len(args) % 4:
        raise ValueError("eqangle requires groups of four point arguments")
    groups: list[tuple[str, str, str, str]] = []
    swapped: list[tuple[str, str, str, str]] = []
    for offset in range(0, len(args), 4):
        a, b, c, d = args[offset : offset + 4]
        if a == b or c == d:
            raise ValueError("eqangle lines require distinct defining points")
        a, b = sorted((a, b))
        c, d = sorted((c, d))
        groups.append((a, b, c, d))
        swapped.append((c, d, a, b))
    canonical = min(sorted(groups), sorted(swapped))
    return tuple(point for group in canonical for point in group)


__all__ = [
    "ChartConstruction",
    "ChartGoal",
    "ChartJGEXFormulation",
    "ChartSetupClause",
]
