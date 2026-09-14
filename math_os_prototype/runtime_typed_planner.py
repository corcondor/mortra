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


@dataclass(frozen=True)
class RankedAlternative:
    """Scheduling metadata only; invoking still uses the existing executor."""

    invoke: Callable[[], PrimitiveResult | None]
    priority: tuple = ()

    def __call__(self):
        return self.invoke()


PrimitiveExecutor = Callable[[tuple[RuntimeFact, ...]], PrimitiveResult | None]


@dataclass(frozen=True)
class RuntimePrimitive:
    name: str
    source_sorts: tuple[str, ...]
    target_sort: str
    execute: PrimitiveExecutor
    alternatives: Callable[[tuple[RuntimeFact, ...]], Iterable[Callable[[], PrimitiveResult | None]]] | None = None


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


@dataclass
class RuntimeSearchProgress:
    """Counters survive a domain budget exception; they never guide search."""

    states_explored: int = 0
    states_retained: int = 0
    applications_started: int = 0
    applications_completed: int = 0
    pending_streams: int = 0


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
    goal_predicates: dict[str, Callable[[RuntimeFact], bool]] | None = None,
    value_key: Callable[[str, Any], str] | None = None,
    fair: bool = False,
    rank_fair_rounds: bool = False,
    original_order_every: int = 4,
    fair_state_streams: bool = False,
    progress: RuntimeSearchProgress | None = None,
) -> RuntimePlan:
    """Enumerate typed compositions with optional value-sensitive goals.

    A custom value_key must be an exact congruence for the supplied primitives.
    The planner cannot infer that premise from samples. `fair` interleaves
    attempted applications, including rejected or duplicate applications.
    """

    if rank_fair_rounds and (not fair or original_order_every < 1):
        raise ValueError("ranked scheduling requires fair rounds and a positive interval")

    facts = list(initial_facts)
    primitive_tuple = tuple(primitives)
    if fair_state_streams and (not fair or any(len(p.source_sorts) != 1 for p in primitive_tuple)):
        raise ValueError("state-stream scheduling requires fair unary state actions")
    goals_tuple = tuple(dict.fromkeys(goal_sorts))
    goal_predicates = goal_predicates or {}
    value_key = value_key or (lambda sort, value: _canonical(value))
    def goals_in(by_sort):
        selected = {}
        for sort in goals_tuple:
            candidates = [f for f in by_sort.get(sort, [])
                          if sort not in goal_predicates or goal_predicates[sort](f)]
            if candidates:
                selected[sort] = min(candidates, key=lambda f: f.depth)
        return selected
    relevant = _relevant_primitives(primitive_tuple, goals_tuple)
    facts_by_id = {fact.id: fact for fact in facts}
    seen_values = {(fact.sort, value_key(fact.sort, fact.value)) for fact in facts}
    attempted: set[tuple[str, tuple[str, ...]]] = set()
    states_explored = len(facts)
    progress = progress if progress is not None else RuntimeSearchProgress()
    progress.states_explored = states_explored
    progress.states_retained = len(facts)
    progress.applications_started = progress.applications_completed = 0

    while states_explored < max_states:
        by_sort: dict[str, list[RuntimeFact]] = {}
        for fact in facts:
            by_sort.setdefault(fact.sort, []).append(fact)
        goal_map = goals_in(by_sort)
        if len(goal_map) == len(goals_tuple):
            program = _proof_program(goal_map.values(), facts_by_id)
            return RuntimePlan(
                goals=goal_map,
                facts=tuple(facts),
                proof_program=program,
                states_explored=states_explored,
                open_goal_sorts=(),
            )

        def arguments_for(primitive):
            source_rows = [by_sort.get(sort, []) for sort in primitive.source_sorts]
            if any(not rows for rows in source_rows):
                return
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
                if primitive.alternatives is None:
                    yield primitive, arguments, dependency_ids, depth, lambda p=primitive, a=arguments: p.execute(tuple(a))
                else:
                    # Enumerate from these actual input facts, but execute only
                    # after the shared planner has charged an application slot.
                    for invoke in primitive.alternatives(tuple(arguments)):
                        yield primitive, arguments, dependency_ids, depth, invoke

        def attempts():
            if fair_state_streams:
                # Keep each (action, state) iterator alive. Newly retained states
                # enter the next round instead of waiting for older streams to end.
                cursor, round_index, streams = 0, 0, []
                def state_attempts(primitive, fact):
                    arguments, ids = (fact,), (fact.id,)
                    depth = fact.depth + 1
                    if primitive.alternatives is None:
                        yield primitive, arguments, ids, depth, lambda: primitive.execute(arguments)
                    else:
                        for invoke in primitive.alternatives(arguments):
                            yield primitive, arguments, ids, depth, invoke
                while True:
                    for fact in facts[cursor:]:
                        for primitive in relevant:
                            key = (primitive.name, (fact.id,))
                            if (primitive.source_sorts != (fact.sort,) or key in attempted
                                    or fact.depth >= max_depth):
                                continue
                            attempted.add(key)
                            streams.append(iter(state_attempts(primitive, fact)))
                    cursor = len(facts)
                    if not streams:
                        progress.pending_streams = 0
                        return
                    alive, batch = [], []
                    for stream in streams:
                        try:
                            offer = next(stream)
                        except StopIteration:
                            continue
                        alive.append(stream)
                        if rank_fair_rounds:
                            batch.append(offer)
                        else:
                            progress.pending_streams = len(streams)
                            yield offer
                    round_index += 1
                    if rank_fair_rounds:
                        if round_index % original_order_every:
                            batch.sort(key=lambda offer: getattr(offer[-1], "priority", ()))
                        progress.pending_streams = len(alive)
                        yield from batch
                    streams = alive
                return
            streams = [iter(arguments_for(p)) for p in relevant]
            if not fair:
                for stream in streams:
                    yield from stream
                return
            # One attempted application per primitive, not one successful offer:
            # an operator producing only duplicates must not consume the budget.
            round_index = 0
            while streams:
                alive = []
                batch = []
                for stream in streams:
                    try:
                        offer = next(stream)
                        if rank_fair_rounds:
                            batch.append(offer)
                        else:
                            yield offer
                        alive.append(stream)
                    except StopIteration:
                        pass
                if rank_fair_rounds:
                    round_index += 1
                    if round_index % original_order_every:
                        batch.sort(key=lambda offer: getattr(offer[-1], "priority", ()))
                    yield from batch
                streams = alive

        changed = False
        for primitive, arguments, dependency_ids, depth, invoke in attempts():
            if states_explored >= max_states:
                break
            progress.applications_started += 1
            result = invoke()
            progress.applications_completed += 1
            states_explored += 1
            progress.states_explored = states_explored
            if result is None:
                if states_explored >= max_states:
                    break
                continue
            result_key = (primitive.target_sort, value_key(primitive.target_sort, result.value))
            if result_key in seen_values:
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
            progress.states_retained = len(facts)
            facts_by_id[fact.id] = fact
            seen_values.add(result_key)
            changed = True
            if primitive.target_sort in goal_predicates and goal_predicates[primitive.target_sort](fact):
                current = {}
                for f in facts:
                    current.setdefault(f.sort, []).append(f)
                reached = goals_in(current)
                if len(reached) == len(goals_tuple):
                    return RuntimePlan(goals=reached, facts=tuple(facts),
                        proof_program=_proof_program(reached.values(), facts_by_id),
                        states_explored=states_explored, open_goal_sorts=())
            if states_explored >= max_states:
                break
        if not changed:
            break

    by_sort: dict[str, list[RuntimeFact]] = {}
    for fact in facts:
        by_sort.setdefault(fact.sort, []).append(fact)
    goal_map = goals_in(by_sort)
    return RuntimePlan(
        goals=goal_map,
        facts=tuple(facts),
        proof_program=_proof_program(goal_map.values(), facts_by_id),
        states_explored=states_explored,
        open_goal_sorts=tuple(sort for sort in goals_tuple if sort not in goal_map),
    )
