"""One finite priority queue for typed backward and forward proof search."""

from __future__ import annotations

from dataclasses import dataclass
import heapq
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
    def rank(self) -> tuple[object, ...]:
        if not self.has_closed_structural_residual:
            return (1,)
        return (
            0,
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
            "task_trace": list(self.task_trace),
        }


@dataclass(frozen=True)
class UnifiedBidirectionalSearch:
    candidates: Mapping[str, UnifiedCandidateResult]
    proof_dags: tuple[OpenProofDAG, ...]
    forward_cones: Mapping[str, CandidateForwardCone]
    audit: UnifiedBidirectionalAudit


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

    for goal_index, _goal in enumerate(canonical_goals):
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

    dags: dict[str, OpenProofDAG] = {}
    cones: dict[str, CandidateForwardCone] = {}
    alignments: dict[str, ProofDAGMeetAlignment] = {}
    forward_depths: dict[str, int] = {}
    candidate_states = {key: 0 for key in candidate_atoms}
    candidate_tasks = {key: 0 for key in candidate_atoms}
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

    while queue and tasks < max_tasks:
        if backward_states + forward_states >= max_total_search_states:
            truncated = True
            break
        _priority, _serial, direction, key, depth = heapq.heappop(queue)
        remaining = max_total_search_states - backward_states - forward_states
        state_budget = max(1, min(per_task_search_states, remaining))
        tasks += 1
        trace.append(f"{direction}:{key}:d{depth}")

        if direction == "backward":
            goal = canonical_goals[int(key)]
            dag = compile_open_proof_dag(
                fact_tuple,
                goal,
                theorem_tuple,
                max_rule_depth=depth,
                max_branches=max_backward_branches,
                max_search_states=state_budget,
            )
            dags[key] = dag
            backward_states += dag.search_states
            backward_tasks += 1
            realign()
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
            task_trace=tuple(trace),
        ),
    )
