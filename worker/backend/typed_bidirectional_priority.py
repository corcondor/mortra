"""One finite priority queue for typed backward and forward proof search."""

from __future__ import annotations

from dataclasses import dataclass
import heapq
import time
from typing import Iterable, Mapping, Sequence

from worker.backend.geometry_proof_hypergraph import Atom, Theorem
from worker.backend.typed_candidate_alignment import (
    ProofDAGMeetAlignment,
    align_candidate_cone_to_proof_branches,
)
from worker.backend.typed_open_proof_dag import (
    CandidateForwardCone,
    OpenProofDAG,
    compile_candidate_forward_cone,
    compile_open_proof_dag,
)


@dataclass(frozen=True)
class UnifiedCandidateResult:
    candidate_key: str
    alignment: ProofDAGMeetAlignment
    explored_forward_depth: int
    search_states: int
    task_count: int

    @property
    def has_closed_structural_residual(self) -> bool:
        return (
            self.alignment.has_meet
            and self.alignment.best_structural_residual_count == 0
        )

    @property
    def has_residual_reduction(self) -> bool:
        return self.alignment.has_residual_reduction

    @property
    def rank(self) -> tuple[object, ...]:
        if not (
            self.has_closed_structural_residual or self.has_residual_reduction
        ):
            return (2,)
        return (
            0 if self.has_closed_structural_residual else 1,
            self.alignment.best_structural_residual_count or 0,
            self.alignment.best_residual_size or 0,
            self.alignment.best_residual_hole_count or 0,
            (self.alignment.best_forward_depth or 0)
            + (self.alignment.best_backward_depth or 0),
            -self.alignment.meet_count,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "candidate_key": self.candidate_key,
            "explored_forward_depth": self.explored_forward_depth,
            "search_states": self.search_states,
            "task_count": self.task_count,
            "has_closed_structural_residual": self.has_closed_structural_residual,
            "has_residual_reduction": self.has_residual_reduction,
            "rank": list(self.rank),
            "alignment": self.alignment.to_dict(),
        }


@dataclass(frozen=True)
class UnifiedBidirectionalAudit:
    task_count: int
    backward_task_count: int
    forward_task_count: int
    backward_search_states: int
    forward_search_states: int
    max_backward_depth_reached: int
    max_forward_depth_reached: int
    queue_peak: int
    truncated: bool
    wall_time_exhausted: bool
    elapsed_seconds: float
    task_trace: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "task_count": self.task_count,
            "backward_task_count": self.backward_task_count,
            "forward_task_count": self.forward_task_count,
            "backward_search_states": self.backward_search_states,
            "forward_search_states": self.forward_search_states,
            "max_backward_depth_reached": self.max_backward_depth_reached,
            "max_forward_depth_reached": self.max_forward_depth_reached,
            "queue_peak": self.queue_peak,
            "truncated": self.truncated,
            "wall_time_exhausted": self.wall_time_exhausted,
            "elapsed_seconds": self.elapsed_seconds,
            "task_trace": list(self.task_trace),
        }


@dataclass(frozen=True)
class UnifiedBidirectionalSearch:
    candidates: Mapping[str, UnifiedCandidateResult]
    proof_dags: tuple[OpenProofDAG, ...]
    forward_cones: Mapping[str, CandidateForwardCone]
    audit: UnifiedBidirectionalAudit


@dataclass(frozen=True)
class IterativeDeepeningStage:
    depth: int
    per_task_search_states: int
    max_total_search_states: int
    max_tasks: int
    typed_meet_candidates: tuple[str, ...]
    diagnosis: str
    audit: UnifiedBidirectionalAudit

    def to_dict(self) -> dict[str, object]:
        return {
            "depth": self.depth,
            "per_task_search_states": self.per_task_search_states,
            "max_total_search_states": self.max_total_search_states,
            "max_tasks": self.max_tasks,
            "typed_meet_candidates": list(self.typed_meet_candidates),
            "diagnosis": self.diagnosis,
            "audit": self.audit.to_dict(),
        }


@dataclass(frozen=True)
class IterativeDeepeningSearch:
    search: UnifiedBidirectionalSearch
    stages: tuple[IterativeDeepeningStage, ...]
    stop_reason: str

    @property
    def candidates(self) -> Mapping[str, UnifiedCandidateResult]:
        return self.search.candidates

    @property
    def audit(self) -> UnifiedBidirectionalAudit:
        return self.search.audit

    def to_dict(self) -> dict[str, object]:
        return {
            "stop_reason": self.stop_reason,
            "stages": [stage.to_dict() for stage in self.stages],
        }


def _alignment_quality(alignment: ProofDAGMeetAlignment | None) -> tuple[int, ...]:
    if alignment is None or not alignment.has_meet:
        return (2, 10**6, 10**6, 10**6)
    return (
        0 if alignment.best_structural_residual_count == 0 else 1,
        alignment.best_structural_residual_count or 0,
        alignment.best_residual_size or 0,
        alignment.best_residual_hole_count or 0,
    )


def search_bidirectionally(
    facts: Iterable[Atom],
    goals: Sequence[Atom],
    candidate_groups: Mapping[str, Sequence[Atom]],
    theorems: Sequence[Theorem],
    *,
    max_backward_depth: int = 2,
    max_forward_depth: int = 2,
    max_backward_branches: int = 96,
    max_forward_fragments: int = 48,
    per_task_search_states: int = 500,
    max_total_search_states: int = 20_000,
    max_tasks: int = 256,
    max_wall_seconds: float | None = None,
    initial_proof_dags: Sequence[OpenProofDAG] = (),
) -> UnifiedBidirectionalSearch:
    """Allocate both search directions through one deterministic typed queue.

    Queue priorities depend only on proof residuals, depth, and stable keys.
    The returned meets are scheduling evidence, never theorem acceptance.
    """

    if min(max_backward_depth, max_forward_depth) < 1:
        raise ValueError("search depths must be positive")
    if min(
        max_backward_branches,
        max_forward_fragments,
        per_task_search_states,
        max_total_search_states,
        max_tasks,
    ) < 1:
        raise ValueError("search budgets must be positive")
    if max_wall_seconds is not None and max_wall_seconds <= 0:
        raise ValueError("max_wall_seconds must be positive")

    started = time.perf_counter()
    deadline: float | None = None

    def wall_expired() -> bool:
        return deadline is not None and time.perf_counter() >= deadline

    def remaining_wall_seconds() -> float | None:
        if deadline is None:
            return None
        return max(1e-9, deadline - time.perf_counter())

    def fair_task_wall_seconds() -> float | None:
        remaining = remaining_wall_seconds()
        if remaining is None:
            return None
        remaining_slots = max(
            1,
            min(max_tasks - tasks + 1, len(queue) + 1),
        )
        return max(1e-9, remaining / remaining_slots)

    fact_tuple = tuple(facts)
    theorem_tuple = tuple(theorems)
    canonical_goals = tuple(goal.canonical() for goal in goals)
    candidate_atoms = {
        key: tuple(atom.canonical() for atom in atoms)
        for key, atoms in candidate_groups.items()
    }
    queue: list[tuple[tuple[object, ...], int, str, str, int]] = []
    serial = 0

    def enqueue(
        priority: tuple[object, ...],
        direction: str,
        key: str,
        depth: int,
    ) -> None:
        nonlocal serial
        serial += 1
        heapq.heappush(queue, (priority, serial, direction, key, depth))

    seeded_dags = {
        str(goal_index): dag
        for goal_index, goal in enumerate(canonical_goals)
        for dag in initial_proof_dags
        if dag.goal.canonical() == goal
    }
    for goal_index, _goal in enumerate(canonical_goals):
        if str(goal_index) not in seeded_dags:
            enqueue(
                (0, 0, 0, 0, 0, 1, "backward", str(goal_index)),
                "backward",
                str(goal_index),
                1,
            )
    for key in sorted(candidate_atoms):
        enqueue(
            (1, 2, 10**6, 10**6, 10**6, 1, "forward", key),
            "forward",
            key,
            1,
        )

    dags: dict[str, OpenProofDAG] = dict(seeded_dags)
    cones: dict[str, CandidateForwardCone] = {}
    alignments: dict[str, ProofDAGMeetAlignment] = {}
    forward_depths: dict[str, int] = {}
    candidate_states = {key: 0 for key in candidate_atoms}
    candidate_tasks = {key: 0 for key in candidate_atoms}
    deferred_forward: set[tuple[str, int]] = set()
    backward_states = 0
    forward_states = 0
    backward_tasks = 0
    forward_tasks = 0
    tasks = 0
    queue_peak = len(queue)
    trace: list[str] = []
    truncated = False

    def branches() -> tuple[object, ...]:
        return tuple(
            branch
            for key in sorted(dags, key=int)
            for branch in dags[key].open_branches
        )

    def realign() -> None:
        open_branches = branches()
        if not open_branches:
            return
        for key, cone in cones.items():
            alignment = align_candidate_cone_to_proof_branches(
                cone, open_branches
            )
            previous = alignments.get(key)
            if _alignment_quality(alignment) < _alignment_quality(previous):
                alignments[key] = alignment

    # Every candidate first exposes its direct typed postconditions. This root
    # pass is finite and cheap, so expensive theorem expansion by an early
    # candidate cannot hide a direct meet from a later candidate.
    for key, atoms in candidate_atoms.items():
        cone = compile_candidate_forward_cone(
            (),
            atoms,
            (),
            max_rule_depth=0,
            max_fragments=max_forward_fragments,
            max_search_states=max(1, len(atoms)),
        )
        cones[key] = cone
        candidate_states[key] += cone.search_states
        forward_states += cone.search_states
    realign()
    if max_wall_seconds is not None:
        deadline = time.perf_counter() + max_wall_seconds

    while queue and tasks < max_tasks:
        if wall_expired():
            truncated = True
            break
        if backward_states + forward_states >= max_total_search_states:
            truncated = True
            break
        _priority, _serial, direction, key, depth = heapq.heappop(queue)
        if direction == "forward" and not branches():
            # A shallow backward pass can end before it exposes an open proof
            # branch.  Do not consume the candidate permanently: a deeper
            # backward pass may expose the exact premises it must target.
            deferred_forward.add((key, depth))
            continue
        remaining = max_total_search_states - backward_states - forward_states
        state_budget = max(1, min(per_task_search_states, remaining))
        tasks += 1
        trace.append(f"{direction}:{key}:d{depth}")
        task_wall_seconds = fair_task_wall_seconds()

        if direction == "backward":
            goal = canonical_goals[int(key)]
            dag = compile_open_proof_dag(
                fact_tuple,
                goal,
                theorem_tuple,
                max_rule_depth=depth,
                max_branches=max_backward_branches,
                max_search_states=state_budget,
                max_wall_seconds=task_wall_seconds,
            )
            dags[key] = dag
            backward_states += dag.search_states
            backward_tasks += 1
            realign()
            if branches() and deferred_forward:
                for candidate_key, candidate_depth in sorted(deferred_forward):
                    enqueue(
                        (
                            1,
                            2,
                            10**6,
                            10**6,
                            10**6,
                            candidate_depth,
                            "forward",
                            candidate_key,
                        ),
                        "forward",
                        candidate_key,
                        candidate_depth,
                    )
                deferred_forward.clear()
            if depth < max_backward_depth:
                frontier_size = min(
                    (len(branch.frontier) for branch in dag.open_branches),
                    default=10**6,
                )
                enqueue(
                    (
                        2,
                        1,
                        frontier_size,
                        frontier_size,
                        0,
                        depth + 1,
                        "backward",
                        key,
                    ),
                    "backward",
                    key,
                    depth + 1,
                )
        else:
            open_branches = branches()
            if not open_branches:
                continue
            targets = tuple(
                atom for branch in open_branches for atom in branch.frontier
            )
            cone = compile_candidate_forward_cone(
                fact_tuple,
                candidate_atoms[key],
                theorem_tuple,
                targets=targets,
                max_rule_depth=depth,
                max_fragments=max_forward_fragments,
                max_search_states=state_budget,
                max_wall_seconds=task_wall_seconds,
            )
            cones[key] = cone
            forward_states += cone.search_states
            forward_tasks += 1
            candidate_states[key] += cone.search_states
            candidate_tasks[key] += 1
            forward_depths[key] = depth
            alignment = align_candidate_cone_to_proof_branches(
                cone, open_branches
            )
            previous = alignments.get(key)
            if _alignment_quality(alignment) < _alignment_quality(previous):
                alignments[key] = alignment
            best = alignments.get(key, alignment)
            if (
                depth < max_forward_depth
                and not (
                    best.has_meet
                    and best.best_structural_residual_count == 0
                )
            ):
                enqueue(
                    (
                        2,
                        *_alignment_quality(best),
                        depth + 1,
                        "forward",
                        key,
                    ),
                    "forward",
                    key,
                    depth + 1,
                )
        queue_peak = max(queue_peak, len(queue))

    if queue:
        truncated = True
    if wall_expired():
        truncated = True

    empty_alignment = align_candidate_cone_to_proof_branches(
        CandidateForwardCone((), (), 0, 0, 0, 0, False),
        (),
    )
    results = {
        key: UnifiedCandidateResult(
            candidate_key=key,
            alignment=alignments.get(key, empty_alignment),
            explored_forward_depth=forward_depths.get(key, 0),
            search_states=candidate_states[key],
            task_count=candidate_tasks[key],
        )
        for key in sorted(candidate_atoms)
    }
    return UnifiedBidirectionalSearch(
        candidates=results,
        proof_dags=tuple(dags[key] for key in sorted(dags, key=int)),
        forward_cones=cones,
        audit=UnifiedBidirectionalAudit(
            task_count=tasks,
            backward_task_count=backward_tasks,
            forward_task_count=forward_tasks,
            backward_search_states=backward_states,
            forward_search_states=forward_states,
            max_backward_depth_reached=max(
                (dag.max_rule_depth for dag in dags.values()), default=0
            ),
            max_forward_depth_reached=max(forward_depths.values(), default=0),
            queue_peak=queue_peak,
            truncated=truncated,
            wall_time_exhausted=wall_expired(),
            elapsed_seconds=time.perf_counter() - started,
            task_trace=tuple(trace),
        ),
    )


def _gap_diagnosis(search: UnifiedBidirectionalSearch) -> str:
    if any(
        candidate.has_closed_structural_residual
        for candidate in search.candidates.values()
    ):
        return "typed_forward_backward_meet"
    if not any(dag.branches for dag in search.proof_dags):
        return "theorem_conclusion_vocabulary_gap"
    if not any(cone.fragments for cone in search.forward_cones.values()):
        return "construction_semantics_gap"
    if search.audit.truncated:
        return "resource_ceiling_before_typed_meet"
    return "no_typed_meet_in_current_theory"


def search_bidirectionally_iterative(
    facts: Iterable[Atom],
    goals: Sequence[Atom],
    candidate_groups: Mapping[str, Sequence[Atom]],
    theorems: Sequence[Theorem],
    *,
    max_depth: int = 4,
    max_backward_branches: int = 96,
    max_forward_fragments: int = 48,
    per_task_search_states: int = 500,
    max_total_search_states: int = 20_000,
    max_tasks: int = 256,
    max_wall_seconds: float | None = None,
    initial_proof_dags: Sequence[OpenProofDAG] = (),
) -> IterativeDeepeningSearch:
    """Increase proof depth only after every shallower typed search fails.

    The ceiling is a resource bound, not an assumed proof depth.  Every stage
    restarts deterministically, so a shallow proof is never delayed by deeper
    enumeration and a failed stage leaves an auditable diagnosis.
    """

    if max_depth < 1:
        raise ValueError("max_depth must be positive")
    if max_wall_seconds is not None and max_wall_seconds <= 0:
        raise ValueError("max_wall_seconds must be positive")
    started = time.perf_counter()
    deadline = (
        started + max_wall_seconds if max_wall_seconds is not None else None
    )
    stages: list[IterativeDeepeningStage] = []
    last: UnifiedBidirectionalSearch | None = None
    root_task_count = max(1, len(goals) + len(candidate_groups))
    for depth in range(1, max_depth + 1):
        stage_wall_seconds = (
            max(1e-9, deadline - time.perf_counter())
            if deadline is not None
            else None
        )
        scale = 1 << (max_depth - depth)
        stage_total = max(1, max_total_search_states // scale)
        stage_tasks = max(1, max_tasks // scale)
        # A nominal depth is meaningless if the first breadth layer consumes
        # the whole state budget.  Reserve enough task slots for every root at
        # every requested level, then cap each task so the final level remains
        # reachable.  Individual compilers may use fewer states and return the
        # unused budget naturally.
        fair_task_count = max(1, min(stage_tasks, root_task_count * depth))
        fair_state_cap = max(1, stage_total // fair_task_count)
        stage_per_task = max(
            1,
            min(per_task_search_states // scale, fair_state_cap),
        )
        current = search_bidirectionally(
            facts,
            goals,
            candidate_groups,
            theorems,
            max_backward_depth=depth,
            max_forward_depth=depth,
            max_backward_branches=max_backward_branches,
            max_forward_fragments=max_forward_fragments,
            per_task_search_states=stage_per_task,
            max_total_search_states=stage_total,
            max_tasks=stage_tasks,
            max_wall_seconds=stage_wall_seconds,
            initial_proof_dags=initial_proof_dags,
        )
        last = current
        typed_meets = tuple(
            sorted(
                key
                for key, candidate in current.candidates.items()
                if candidate.has_closed_structural_residual
            )
        )
        diagnosis = _gap_diagnosis(current)
        stages.append(
            IterativeDeepeningStage(
                depth=depth,
                per_task_search_states=stage_per_task,
                max_total_search_states=stage_total,
                max_tasks=stage_tasks,
                typed_meet_candidates=typed_meets,
                diagnosis=diagnosis,
                audit=current.audit,
            )
        )
        if typed_meets:
            return IterativeDeepeningSearch(
                search=current,
                stages=tuple(stages),
                stop_reason="typed_meet_found_native_replay_required",
            )
        if deadline is not None and time.perf_counter() >= deadline:
            return IterativeDeepeningSearch(
                search=current,
                stages=tuple(stages),
                stop_reason="wall_time_ceiling_before_typed_meet",
            )
    assert last is not None
    return IterativeDeepeningSearch(
        search=last,
        stages=tuple(stages),
        stop_reason=_gap_diagnosis(last),
    )
