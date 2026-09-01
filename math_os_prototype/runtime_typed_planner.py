"""Small typed proof-program planner used by cold runtime synthesis.

Only primitive contracts are registered.  Completed problem routes, problem
identifiers, and expected answers are not part of the planner state.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from itertools import product
import json
from typing import Any, Callable, Iterable


@dataclass(frozen=True)
class RuntimeFact:
    id: str
    sort: str
    value: Any
    dependencies: tuple[str, ...]
    depth: int
    certificate_step: dict[str, Any] | None = None


@dataclass(frozen=True)
class PrimitiveResult:
    value: Any
    certificate_step: dict[str, Any]


PrimitiveExecutor = Callable[[tuple[RuntimeFact, ...]], PrimitiveResult | None]


@dataclass(frozen=True)
class RuntimePrimitive:
    name: str
    source_sorts: tuple[str, ...]
    target_sort: str
    execute: PrimitiveExecutor


@dataclass(frozen=True)
class RuntimePlan:
    goals: dict[str, RuntimeFact]
    facts: tuple[RuntimeFact, ...]
    proof_program: tuple[dict[str, Any], ...]
    states_explored: int
    open_goal_sorts: tuple[str, ...]

    @property
    def complete(self) -> bool:
        return not self.open_goal_sorts


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _fact_id(sort: str, value: Any, dependencies: tuple[str, ...]) -> str:
    payload = _canonical([sort, value, dependencies]).encode("utf-8")
    return f"fact.{hashlib.sha256(payload).hexdigest()[:20]}"


def initial_fact(sort: str, value: Any) -> RuntimeFact:
    return RuntimeFact(
        id=_fact_id(sort, value, ()),
        sort=sort,
        value=value,
        dependencies=(),
        depth=0,
    )


def _relevant_primitives(
    primitives: tuple[RuntimePrimitive, ...],
    goal_sorts: tuple[str, ...],
) -> tuple[RuntimePrimitive, ...]:
    needed = set(goal_sorts)
    changed = True
    while changed:
        changed = False
        for primitive in primitives:
            if primitive.target_sort not in needed:
                continue
            for source in primitive.source_sorts:
                if source not in needed:
                    needed.add(source)
                    changed = True
    return tuple(primitive for primitive in primitives if primitive.target_sort in needed)


def _proof_program(
    goals: Iterable[RuntimeFact],
    facts_by_id: dict[str, RuntimeFact],
) -> tuple[dict[str, Any], ...]:
    visited: set[str] = set()
    steps: list[dict[str, Any]] = []

    def visit(fact: RuntimeFact) -> None:
        if fact.id in visited:
            return
        for dependency in fact.dependencies:
            visit(facts_by_id[dependency])
        visited.add(fact.id)
        if fact.certificate_step is not None:
            steps.append(fact.certificate_step)

    for goal in goals:
        visit(goal)
    return tuple(steps)


def synthesize_typed_plan(
    initial_facts: Iterable[RuntimeFact],
    primitives: Iterable[RuntimePrimitive],
    goal_sorts: Iterable[str],
    *,
    max_depth: int = 12,
    max_states: int = 2048,
) -> RuntimePlan:
    """Enumerate well-typed primitive compositions until all goals are built."""

    facts = list(initial_facts)
    primitive_tuple = tuple(primitives)
    goals_tuple = tuple(dict.fromkeys(goal_sorts))
    relevant = _relevant_primitives(primitive_tuple, goals_tuple)
    facts_by_id = {fact.id: fact for fact in facts}
    seen_values = {(fact.sort, _canonical(fact.value)) for fact in facts}
    attempted: set[tuple[str, tuple[str, ...]]] = set()
    states_explored = len(facts)

    while states_explored < max_states:
        by_sort: dict[str, list[RuntimeFact]] = {}
        for fact in facts:
            by_sort.setdefault(fact.sort, []).append(fact)
        goal_map = {
            sort: min(by_sort[sort], key=lambda fact: fact.depth)
            for sort in goals_tuple
            if by_sort.get(sort)
        }
        if len(goal_map) == len(goals_tuple):
            program = _proof_program(goal_map.values(), facts_by_id)
            return RuntimePlan(
                goals=goal_map,
                facts=tuple(facts),
                proof_program=program,
                states_explored=states_explored,
                open_goal_sorts=(),
            )

        changed = False
        for primitive in relevant:
            source_rows = [by_sort.get(sort, []) for sort in primitive.source_sorts]
            if any(not rows for rows in source_rows):
                continue
            combinations = product(*source_rows) if source_rows else [()]
            for arguments in combinations:
                dependency_ids = tuple(argument.id for argument in arguments)
                attempt_key = (primitive.name, dependency_ids)
                if attempt_key in attempted:
                    continue
                attempted.add(attempt_key)
                depth = max((argument.depth for argument in arguments), default=-1) + 1
                if depth > max_depth:
                    continue
                result = primitive.execute(tuple(arguments))
                states_explored += 1
                if result is None:
                    if states_explored >= max_states:
                        break
                    continue
                value_key = (primitive.target_sort, _canonical(result.value))
                if value_key in seen_values:
                    continue
                fact = RuntimeFact(
                    id=_fact_id(primitive.target_sort, result.value, dependency_ids),
                    sort=primitive.target_sort,
                    value=result.value,
                    dependencies=dependency_ids,
                    depth=depth,
                    certificate_step={"rule": primitive.name, **result.certificate_step},
                )
                facts.append(fact)
                facts_by_id[fact.id] = fact
                seen_values.add(value_key)
                changed = True
                if states_explored >= max_states:
                    break
            if states_explored >= max_states:
                break
        if not changed:
            break

    by_sort: dict[str, list[RuntimeFact]] = {}
    for fact in facts:
        by_sort.setdefault(fact.sort, []).append(fact)
    goal_map = {
        sort: min(by_sort[sort], key=lambda fact: fact.depth)
        for sort in goals_tuple
        if by_sort.get(sort)
    }
    return RuntimePlan(
        goals=goal_map,
        facts=tuple(facts),
        proof_program=_proof_program(goal_map.values(), facts_by_id),
        states_explored=states_explored,
        open_goal_sorts=tuple(sort for sort in goals_tuple if sort not in goal_map),
    )
