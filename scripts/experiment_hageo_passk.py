"""Independent HAGeo-style N-round auxiliary construction attempts.

Unlike the layer-wise beam experiment, every attempt keeps its own construction
trajectory for N rounds and calls DDAR only for the completed trajectory.  This
matches the experimental unit in HAGeo's Pass@K protocol without using a neural
model, dataset auxiliary clauses, problem identifiers, or expected answers.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import platform
import random
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from itertools import product
from pathlib import Path
from threading import BoundedSemaphore
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Importing this module also installs the Yuclid/Boost runtime paths from this
# script's identical command-line arguments.
from scripts.experiment_newclid_construction_stalk import (  # noqa: E402
    ConstructionStep,
    EXTENDED_POINT_FAMILIES,
    JGEXFormulation,
    JGEXProblemBuilder,
    backward_relation_distances,
    augment_formulation,
    branch_seed,
    build_branch,
    candidate_extensions,
    construction_requirement_atoms,
    construction_relation_atoms,
    extend_prefix_branch,
    formulation_goal_atoms,
    formulation_structure,
    jgex_formulation_from_txt_file,
    native_rule_theorems,
    normalize_legacy_formulation,
    proof_hypergraph_relevance,
    proof_state_obligations,
    yuclid_assertion_keys,
    DEFAULT_RULES,
)
from scripts.reproduce_gclc_methods import run_method  # noqa: E402
from newclid.problem import PredicateConstruction  # noqa: E402
from worker.backend.geometry_ar_residual import yuclid_ar_residual  # noqa: E402
from worker.backend.geometry_backend_options import (  # noqa: E402
    EXACT_SPECIALIST_REPRESENTATIONS,
    remaining_stage_seconds,
)
from worker.backend.geometry_proof_hypergraph import (  # noqa: E402
    Atom,
    BidirectionalHypergraphProver,
    synthesize_backward_obligations,
)
from worker.backend.formalgeo_runtime_bridge import (  # noqa: E402
    FormalGeoElaborationError,
    FormalGeoRuntimeConfig,
    run_formalgeo_bridge,
    run_formalgeo_goal_exchange,
)
from worker.backend.hageo_mmt_certificate_bridge import (  # noqa: E402
    coordinate_hageo_certificates,
    goal_conditioned_proof_basis,
    shared_argument_sorts,
)
from worker.backend.hageo_search_control import (  # noqa: E402
    candidate_policy_spec,
    candidate_made_causal_progress,
    candidate_pool,
    next_relation_demands,
    proof_residual_order_key,
    proof_dag_search_roots,
    relation_demand_transition,
    rank_biased_shortlist,
    mixed_credit_residual_shortlist,
    obligation_conditioned_credit_ranking,
    obligation_conditioned_selection_key,
    verified_obligation_credit,
)
from worker.backend.jgex_gclc_translator import (  # noqa: E402
    SUPPORTED_GOALS,
    translate_jgex_to_gclc,
)
from worker.backend.jgex_formalgeo_translator import (  # noqa: E402
    translate_jgex_to_formalgeo,
)
from worker.backend.jgex_exact_constraint_bridge import (  # noqa: E402
    inspect_jgex_exact_system,
)
from worker.backend.terminal_trajectory_credit import (  # noqa: E402
    TerminalCreditEvent,
    TerminalCreditLedger,
    assign_terminal_credit,
    rank_with_terminal_credit,
)
from worker.backend.typed_candidate_alignment import (  # noqa: E402
    candidate_directly_satisfies_obligation,
    obligation_signature,
)
from worker.backend.typed_construction_contracts import (  # noqa: E402
    carry_construction_requirements,
    reduce_obligation_branches,
)
from worker.backend.typed_open_proof_dag import compile_open_proof_dag  # noqa: E402
from worker.backend.wolfram_polynomial_certificate import (  # noqa: E402
    certify_jgex_with_wolfram,
)
from worker.backend.typed_relation_separator import (  # noqa: E402
    relation_is_informative,
    relation_is_nondegenerate,
)
from worker.backend.polynomial_relation_reelaborator import (  # noqa: E402
    certify_polynomial_ideal_relations,
    reelaborate_polynomial_lemmas,
    verify_typed_relation_ideal_certificate,
    verify_typed_relation_certificate,
)
from worker.backend.yuclid_native_verifier import verify_problem  # noqa: E402


PROOF_DAG_STAGE_ONE = {
    "per_family_candidates": 4,
    # Iterative deepening executes depth 1 first and escalates only when no
    # typed forward/backward meet exists.  This is a resource ceiling, not a
    # claim that every proof has depth three.
    "depth": 3,
    "fragments": 16,
    "initial_states_per_candidate": 16,
    "states_per_task": 64,
    "reserved_consensus": 4,
    "reserved_family_frontier": True,
}
GCLC_METHOD_FLAGS = {"area": "-a", "wu": "-w", "groebner": "-g"}
REELABORATABLE_RELATIONS = SUPPORTED_GOALS | {"eqratio", "midp", "lequation"}


def _ground_executable_obligation_branches(
    obligation_branches: tuple[tuple[Atom, ...], ...],
) -> tuple[tuple[Atom, ...], ...]:
    """Keep only complete ground AND branches that the exact chart can lower."""

    accepted: list[tuple[Atom, ...]] = []
    for branch in obligation_branches:
        canonical = tuple(dict.fromkeys(atom.canonical() for atom in branch))
        if canonical and all(
            atom.predicate in REELABORATABLE_RELATIONS
            and not any(argument.startswith("?") for argument in atom.arguments)
            and relation_is_nondegenerate(atom)
            and relation_is_informative(atom)
            for atom in canonical
        ):
            accepted.append(canonical)
    return tuple(dict.fromkeys(accepted))


def _ground_reelaboration_demands(
    formulation: JGEXFormulation,
    obligation_branches: tuple[tuple[Atom, ...], ...],
    goal_atoms: tuple[Atom, ...],
    *,
    max_hole_candidates: int = 256,
) -> tuple[tuple[Atom, ...], tuple[Atom, ...]]:
    """Ground typed holes coherently inside each finite AND branch."""

    explicit = tuple(
        dict.fromkeys(
            atom.canonical()
            for branch in (*obligation_branches, goal_atoms)
            for atom in branch
            if atom.predicate in REELABORATABLE_RELATIONS
            and not any(argument.startswith("?") for argument in atom.arguments)
            and relation_is_nondegenerate(atom)
            and relation_is_informative(atom)
        )
    )
    if max_hole_candidates <= 0:
        return explicit, ()
    analysis = inspect_jgex_exact_system(
        str(formulation).strip(), representation="relational"
    )
    points = tuple(point for point, _ in analysis.point_coordinates)
    synthesized: dict[Atom, None] = {}
    for branch in obligation_branches:
        variables = tuple(
            sorted(
                {
                    argument
                    for atom in branch
                    for argument in atom.arguments
                    if argument.startswith("?")
                }
            )
        )
        if not variables or len(variables) > 2:
            continue
        for values in product(points, repeat=len(variables)):
            if len(values) > 1 and len(set(values)) != len(values):
                continue
            substitution = dict(zip(variables, values, strict=True))
            for atom in branch:
                if atom.predicate not in REELABORATABLE_RELATIONS:
                    continue
                grounded = Atom(
                    atom.predicate,
                    tuple(substitution.get(argument, argument) for argument in atom.arguments),
                ).canonical()
                if (
                    any(argument.startswith("?") for argument in grounded.arguments)
                    or not relation_is_nondegenerate(grounded)
                    or not relation_is_informative(grounded)
                ):
                    continue
                synthesized.setdefault(grounded, None)
                if len(synthesized) >= max_hole_candidates:
                    return explicit, tuple(synthesized)
    return explicit, tuple(synthesized)


def _gclc_methods(value: str) -> tuple[str, ...]:
    methods = tuple(item.strip().lower() for item in value.split(",") if item.strip())
    unknown = tuple(item for item in methods if item not in GCLC_METHOD_FLAGS)
    if not methods or unknown:
        raise argparse.ArgumentTypeError(
            "GCLC methods must be a comma-separated subset of area,wu,groebner"
        )
    return tuple(dict.fromkeys(methods))


def _gclc_run_timed_out(run: dict[str, Any]) -> bool:
    """Recognize both the process hard stop and GCLC's internal timer."""

    if run.get("timed_out"):
        return True
    if run.get("external_timeout_reached") or run.get("internal_timeout_reached"):
        return True
    return "conjecture not proved - timeout" in str(
        run.get("transcript", "")
    ).lower()


def _gclc_run_diagnostic(run: dict[str, Any]) -> dict[str, Any]:
    """Keep compact, auditable prover telemetry without embedding full logs."""

    transcript_lines = tuple(
        line.strip()
        for line in str(run.get("transcript", "")).splitlines()
        if line.strip()
    )
    polynomial_line = next(
        (
            line
            for line in transcript_lines
            if "largest polynomial" in line.lower()
        ),
        None,
    )
    conclusion_line = next(
        (line for line in transcript_lines if "conjecture" in line.lower()),
        None,
    )
    return {
        "method": run.get("method"),
        "proved": bool(run.get("proved")),
        "timed_out": _gclc_run_timed_out(run),
        "external_timeout_reached": bool(run.get("external_timeout_reached")),
        "internal_timeout_reached": bool(
            run.get("internal_timeout_reached")
            or (
                "conjecture not proved - timeout"
                in str(run.get("transcript", "")).lower()
            )
        ),
        "elapsed_seconds": run.get("elapsed_seconds"),
        "polynomial_scale": polynomial_line,
        "conclusion": conclusion_line,
        "execution_error": run.get("execution_error"),
    }


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _gclc_goal_construction(atom: Atom) -> PredicateConstruction | None:
    """Type-check a ground relation at the Newclid/GCLC boundary."""

    if atom.predicate.lower() not in SUPPORTED_GOALS:
        return None
    if any(argument.startswith("?") for argument in atom.arguments):
        return None
    try:
        return PredicateConstruction.from_str(
            f"{atom.predicate} {' '.join(atom.arguments)}"
        )
    except (TypeError, ValueError):
        return None


def _formulation_with_goal(
    formulation: JGEXFormulation,
    atom: Atom,
) -> JGEXFormulation | None:
    goal = _gclc_goal_construction(atom)
    if goal is None:
        return None
    return JGEXFormulation(
        name=formulation.name,
        setup_clauses=formulation.setup_clauses,
        auxiliary_clauses=formulation.auxiliary_clauses,
        goals=(goal,),
    )


def _passes_gclc_numerical_incidence(
    formulation: JGEXFormulation,
    atom: Atom,
    *,
    samples: int,
) -> tuple[bool, list[str]]:
    """Reject relations that fail in deterministic independent JGEX models."""

    if samples <= 0:
        return True, []
    candidate = _formulation_with_goal(formulation, atom)
    if candidate is None:
        return False, ["invalid_typed_goal"]
    errors: list[str] = []
    for sample_index in range(samples):
        builder = JGEXProblemBuilder(
            np.random.default_rng(0x4D4F5254 + sample_index)
        )
        try:
            (
                builder.with_problem(candidate)
                .include_auxiliary_clauses(True)
                .build(max_attempts_to_satisfy_goals_numerically=3)
            )
        except Exception as exc:
            errors.append(f"{type(exc).__name__}: {exc}")
            return False, errors
    return True, errors


def _gclc_executable_obligation_branches(
    facts: tuple[Atom, ...],
    branches: tuple[tuple[Atom, ...], ...],
    theorems: tuple[Any, ...],
    *,
    max_branches: int = 64,
    max_rule_depth: int = 3,
    deadline: float | None = None,
) -> tuple[tuple[Atom, ...], ...]:
    """Lower typed AND/OR obligations to GCLC's finite relation interface."""

    queue = [(branch, 0) for branch in branches[:max_branches]]
    seen: set[tuple[Atom, ...]] = set()
    executable: list[tuple[Atom, ...]] = []
    while queue and len(seen) < max_branches:
        if deadline is not None and time.perf_counter() >= deadline:
            break
        raw_branch, depth = queue.pop(0)
        branch = tuple(atom.canonical() for atom in raw_branch)
        if not branch or branch in seen:
            continue
        seen.add(branch)
        invalid_ground = next(
            (
                atom
                for atom in branch
                if atom.predicate.lower() in SUPPORTED_GOALS
                and not any(arg.startswith("?") for arg in atom.arguments)
                and _gclc_goal_construction(atom) is None
            ),
            None,
        )
        if invalid_ground is not None:
            continue
        if all(_gclc_goal_construction(atom) is not None for atom in branch):
            executable.append(branch)
            continue

        target_index = next(
            (
                index
                for index, atom in enumerate(branch)
                if atom.predicate.lower() not in SUPPORTED_GOALS
            ),
            None,
        )
        if target_index is None:
            continue
        if depth >= max_rule_depth:
            continue
        target = branch[target_index]
        obligations = synthesize_backward_obligations(
            facts,
            target,
            theorems,
            max_open_premises=4,
            max_states_per_rule=64,
            max_results=max_branches,
            deadline=deadline,
        )
        for obligation in obligations:
            frontier = tuple(
                atom.canonical() for atom in obligation.open_premises
            )
            if not frontier:
                continue
            candidate = tuple(
                dict.fromkeys(
                    (
                        *branch[:target_index],
                        *frontier,
                        *branch[target_index + 1 :],
                    )
                )
            )
            if candidate != branch and candidate not in seen:
                queue.append((candidate, depth + 1))
                if len(queue) + len(seen) >= max_branches:
                    break
    return tuple(dict.fromkeys(executable))[:max_branches]


def _write_lemma_exchange_certificate(
    output: Path,
    payload: dict[str, Any],
    *,
    suffix: str,
    source: str,
) -> dict[str, Any]:
    """Persist every local certificate plus the terminal typed proof DAG."""

    path = output.with_suffix(suffix)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    proof_material = {
        "lemma_certificates": sorted(
            str(item.get("proof_sha256") or item.get("certificate_sha256"))
            for item in payload.get("lemmas", ())
            if item.get("proof_sha256") or item.get("certificate_sha256")
        ),
        "hypergraph_proofs": payload.get("hypergraph_proofs", ()),
    }
    return {
        "source": source,
        "proof_sha256": hashlib.sha256(
            json.dumps(proof_material, sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "proof_path": path.resolve().relative_to(ROOT).as_posix(),
        "proof_file_sha256": _file_sha256(path),
    }


def _reproducibility_manifest(
    *,
    dataset: Path,
    yuclid_exe: Path,
    runtime_path: Path,
    gclc_exe: Path | None = None,
    wolfram_exe: Path | None = None,
) -> dict[str, Any]:
    """Fingerprint the exact search and verification inputs used by a run."""

    source_paths = (
        Path(__file__).resolve(),
        ROOT / "scripts" / "experiment_newclid_construction_stalk.py",
        ROOT / "scripts" / "run_gclc_wu_specialist.py",
        ROOT / "scripts" / "run_jgex_exact_specialist.py",
        ROOT / "worker" / "backend" / "hageo_search_control.py",
        ROOT / "worker" / "backend" / "geometry_proof_hypergraph.py",
        ROOT / "worker" / "backend" / "formalgeo_runtime_bridge.py",
        ROOT / "worker" / "backend" / "jgex_formalgeo_translator.py",
        ROOT / "scripts" / "run_formalgeo_runtime.py",
        ROOT / "worker" / "backend" / "hageo_mmt_certificate_bridge.py",
        ROOT / "worker" / "backend" / "jgex_exact_constraint_bridge.py",
        ROOT / "worker" / "backend" / "typed_relation_separator.py",
        ROOT / "worker" / "backend" / "bounded_macaulay_membership.py",
        ROOT / "worker" / "backend" / "local_polynomial_elimination.py",
        ROOT / "worker" / "backend" / "typed_construction_contracts.py",
        ROOT / "worker" / "backend" / "typed_candidate_alignment.py",
        ROOT / "worker" / "backend" / "typed_bidirectional_priority.py",
        ROOT / "worker" / "backend" / "typed_open_proof_dag.py",
        ROOT / "worker" / "backend" / "wolfram_polynomial_certificate.py",
        ROOT / "worker" / "backend" / "yuclid_native_verifier.py",
    )
    newclid_spec = importlib.util.find_spec("newclid")
    return {
        "python": {
            "executable": Path(sys.executable).resolve().as_posix(),
            "version": platform.python_version(),
            "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
        },
        "dataset": {
            "path": dataset.resolve().as_posix(),
            "sha256": _file_sha256(dataset.resolve()),
        },
        "yuclid": {
            "path": yuclid_exe.resolve().as_posix(),
            "sha256": _file_sha256(yuclid_exe.resolve()),
        },
        "gclc": (
            {
                "path": gclc_exe.resolve().as_posix(),
                "sha256": _file_sha256(gclc_exe.resolve()),
            }
            if gclc_exe is not None
            else None
        ),
        "wolfram": (
            {
                "path": wolfram_exe.resolve().as_posix(),
                "sha256": _file_sha256(wolfram_exe.resolve()),
            }
            if wolfram_exe is not None
            else None
        ),
        "runtime_path": runtime_path.resolve().as_posix(),
        "newclid_module": (
            Path(newclid_spec.origin).resolve().as_posix()
            if newclid_spec is not None and newclid_spec.origin
            else None
        ),
        "mortra_sources": {
            path.resolve().relative_to(ROOT).as_posix(): _file_sha256(path)
            for path in source_paths
        },
    }


def _goal_channels(formulation: JGEXFormulation) -> set[str]:
    channels: set[str] = set()
    for goal in formulation.goals:
        name = getattr(goal, "name", None)
        if hasattr(name, "value"):
            name = name.value
        channels.add(str(name or str(goal).split()[0]).lower())
    return channels


def _rank_biased_choice(
    pool: list[ConstructionStep],
    *,
    rng: random.Random,
    temperature: float,
) -> ConstructionStep:
    """Sample a ranked finite pool while preserving independent trajectories.

    ``temperature=0`` is greedy.  Positive temperature uses a geometric rank
    distribution; no problem identifier, answer, or construction literal is
    inspected here.
    """

    if not pool:
        raise ValueError("candidate pool must not be empty")
    if temperature < 0:
        raise ValueError("rank temperature must be nonnegative")
    if temperature == 0 or len(pool) == 1:
        return pool[0]
    continuation = math.exp(-1.0 / temperature)
    weights = [continuation**index for index in range(len(pool))]
    return rng.choices(pool, weights=weights, k=1)[0]


def _contract_diverse_shortlist(
    pool: list[ConstructionStep],
    obligations: tuple[Atom, ...],
    *,
    count: int,
) -> list[tuple[int, ConstructionStep]]:
    """Reserve one candidate per open relation channel before rank fill."""

    selected: list[tuple[int, ConstructionStep]] = []
    used: set[str] = set()
    for predicate in dict.fromkeys(
        atom.canonical().predicate for atom in obligations
    ):
        for index, candidate in enumerate(pool):
            if candidate.key in used:
                continue
            atoms = construction_relation_atoms(
                candidate.family,
                candidate.output,
                candidate.inputs,
            )
            if any(
                demand.canonical().predicate == predicate
                and candidate_directly_satisfies_obligation(atoms, demand)
                for demand in obligations
            ):
                selected.append((index, candidate))
                used.add(candidate.key)
                break
        if len(selected) >= count:
            return selected
    for index, candidate in enumerate(pool):
        if candidate.key in used:
            continue
        selected.append((index, candidate))
        if len(selected) >= count:
            break
    return selected


def _is_circular_goal_transport(
    candidate_atoms: tuple[Atom, ...],
    residual_branches: tuple[tuple[Atom, ...], ...],
    goals: tuple[Atom, ...],
    theorems: tuple[Any, ...],
) -> bool:
    """Detect a reversible renaming of the still-unproved original goal."""

    prover = BidirectionalHypergraphProver(theorems)
    for branch in residual_branches:
        if not branch or any(
            argument.startswith("?")
            for atom in branch
            for argument in atom.arguments
        ):
            continue
        forward = all(
            prover.prove((*candidate_atoms, *branch), goal, max_rounds=6)
            is not None
            for goal in goals
        )
        backward = all(
            prover.prove((*candidate_atoms, *goals), atom, max_rounds=6)
            is not None
            for atom in branch
        )
        if forward and backward:
            return True
    return False


def _proof_residual(
    payload: dict[str, Any],
    *,
    goal_atoms: tuple[Any, ...],
    rule_theorems: tuple[Any, ...],
) -> dict[str, Any]:
    residual, _, _ = _proof_residual_state(
        payload,
        goal_atoms=goal_atoms,
        rule_theorems=rule_theorems,
    )
    return residual


def _proof_residual_state(
    payload: dict[str, Any],
    *,
    goal_atoms: tuple[Any, ...],
    rule_theorems: tuple[Any, ...],
    parent_demands: tuple[Any, ...] = (),
    parent_proved_atoms: tuple[Any, ...] = (),
    contract_frontier: bool = False,
) -> tuple[
    dict[str, Any],
    tuple[Any, ...],
    tuple[tuple[Any, ...], ...],
]:
    """Return metrics, flat atoms, and coherent AND/OR obligation branches."""

    obligations, demands = proof_state_obligations(
        payload, goal_atoms, rule_theorems
    )
    obligation_branches = tuple(
        tuple(obligation.open_premises)
        for obligation in obligations
        if obligation.open_premises
    )
    ar = yuclid_ar_residual(
        payload,
        ((atom.predicate, atom.arguments) for atom in goal_atoms),
    )
    residual = {
        "open_relation_demands": len(demands),
        "backward_obligations": len(obligations),
        "ar_supported_goals": ar.supported_goal_count,
        "ar_closed_goals": ar.closed_goal_count,
        "ar_residual_support": ar.residual_support_size,
        "ar_residual_l1": ar.residual_l1_weight,
        "ar_known_rank": ar.known_rank,
    }
    proved_atoms = tuple(
        Atom(predicate, points)
        for predicate, points in yuclid_assertion_keys(payload)
    )
    if contract_frontier:
        base_demands = tuple(demands)
        demands = _typed_contract_frontier(
            proved_atoms,
            goal_atoms,
            rule_theorems,
            base_demands=demands,
        )
        base_keys = {item.canonical() for item in base_demands}
        obligation_branches = (
            *obligation_branches,
            *(
                (item,)
                for item in demands
                if item.canonical() not in base_keys
            ),
        )
        residual["open_relation_demands"] = len(demands)
        residual["contract_frontier_witnesses"] = sum(
            obligation_signature(item).requires_witness for item in demands
        )
    residual.update(
        relation_demand_transition(
            parent_demands,
            demands,
            proved=proved_atoms,
            parent_proved=parent_proved_atoms,
        )
    )
    return residual, demands, obligation_branches


def _typed_contract_frontier(
    facts: tuple[Atom, ...],
    goals: tuple[Atom, ...],
    theorems: tuple[Any, ...],
    *,
    base_demands: tuple[Atom, ...],
    max_demands: int = 64,
) -> tuple[Atom, ...]:
    """Find witness-bearing frontiers after bounded AND/OR decomposition."""

    if any(obligation_signature(item).requires_witness for item in base_demands):
        return tuple(dict.fromkeys(base_demands))[:max_demands]
    basis = goal_conditioned_proof_basis(
        facts,
        goals,
        theorems,
        point_radius=1,
        max_facts=192,
        max_obligations=32,
    )
    witness_frontier: list[Atom] = []
    for goal in goals:
        dag = compile_open_proof_dag(
            basis,
            goal,
            theorems,
            max_rule_depth=3,
            max_branches=64,
            max_search_states=2_500,
        )
        witness_frontier.extend(
            atom
            for atom in dag.unique_frontier_atoms
            if obligation_signature(atom).requires_witness
        )
    ordered = tuple(
        dict.fromkeys(
            (
                *base_demands,
                *sorted(
                    witness_frontier,
                    key=lambda atom: (
                        len(obligation_signature(atom).holes),
                        -len(obligation_signature(atom).known_entities),
                        atom.predicate,
                        atom.arguments,
                    ),
                ),
            )
        )
    )
    return ordered[:max_demands]


def _expand_contract_obligation_branches(
    facts: tuple[Atom, ...],
    branches: tuple[tuple[Atom, ...], ...],
    theorems: tuple[Any, ...],
    *,
    max_branches: int = 64,
    allow_ground_residual: bool = False,
) -> tuple[tuple[Atom, ...], ...]:
    """Replace a ground residual atom by coherent theorem-premise branches."""

    expanded: list[tuple[Atom, ...]] = []
    for branch in branches:
        if any(
            obligation_signature(atom).requires_witness for atom in branch
        ):
            expanded.append(branch)
            continue
        branch_expanded = False
        for goal_index, goal in enumerate(branch):
            basis = goal_conditioned_proof_basis(
                facts,
                (goal,),
                theorems,
                point_radius=1,
                max_facts=192,
                max_obligations=32,
            )
            dag = compile_open_proof_dag(
                basis,
                goal,
                theorems,
                max_rule_depth=3,
                max_branches=max_branches,
                max_search_states=2_500,
            )
            for proof_branch in dag.open_branches:
                if not any(
                    obligation_signature(atom).requires_witness
                    for atom in proof_branch.frontier
                ) and not allow_ground_residual:
                    continue
                candidate = tuple(
                    dict.fromkeys(
                        (
                            *branch[:goal_index],
                            *proof_branch.frontier,
                            *branch[goal_index + 1 :],
                        )
                    )
                )
                expanded.append(candidate)
                branch_expanded = True
                if len(expanded) >= max_branches:
                    break
            if len(expanded) >= max_branches:
                break
        if not branch_expanded:
            expanded.append(branch)
        if len(expanded) >= max_branches:
            break
    return tuple(dict.fromkeys(expanded))[:max_branches]


def _relation_demand_trace(demands: tuple[Any, ...]) -> list[str]:
    return [
        f"{atom.predicate}({','.join(map(str, atom.arguments))})"
        for atom in demands
    ]


def _reelaborated_relation_atoms(
    formulation: JGEXFormulation,
    certificate: dict[str, Any] | None,
) -> tuple[tuple[Atom, dict[str, Any], str], ...]:
    """Replay exact polynomial-to-relation certificates from a worker."""

    if not isinstance(certificate, dict):
        return ()
    source = str(formulation).strip()
    records: dict[Atom, tuple[dict[str, Any], str]] = {}

    def collect(node: Any, node_id: str, *, replayed: bool) -> None:
        if not replayed or not isinstance(node, dict):
            return
        for raw in node.get("typed_relation_certificates", ()):
            if not isinstance(raw, dict):
                continue
            try:
                atom = Atom(
                    str(raw["predicate"]),
                    tuple(map(str, raw["arguments"])),
                ).canonical()
            except (KeyError, TypeError):
                continue
            if (
                atom.predicate not in REELABORATABLE_RELATIONS
                or any(argument.startswith("?") for argument in atom.arguments)
                or not relation_is_nondegenerate(atom)
                or not verify_typed_relation_certificate(source, raw)
            ):
                continue
            records.setdefault(atom, (raw, node_id))

    for key in ("local_elimination_nodes", "separator_nodes"):
        for node in certificate.get(key, ()):
            if isinstance(node, dict):
                collect(
                    node,
                    str(node.get("node_id", key)),
                    replayed=node.get("replayed") is True,
                )
    root = certificate.get("root")
    collect(
        root,
        str(root.get("node_id", "root")) if isinstance(root, dict) else "root",
        replayed=certificate.get("all_local_certificates_replayed") is True,
    )
    return tuple(
        (atom, payload, node_id)
        for atom, (payload, node_id) in records.items()
    )


def _run_reelaborated_relation_exchange(
    formulation: JGEXFormulation,
    *,
    exact_result: dict[str, Any],
    native_facts: tuple[Atom, ...],
    goal_atoms: tuple[Atom, ...],
    rule_theorems: tuple[Any, ...],
    obligation_branches: tuple[tuple[Atom, ...], ...] = (),
    ideal_max_multiplier_degree: int = 0,
) -> dict[str, Any]:
    """Replay recovered atoms in Newclid's typed theorem hypergraph."""

    recovered = list(_reelaborated_relation_atoms(
        formulation,
        exact_result.get("certificate"),
    ))
    certificate = exact_result.get("certificate")
    targeted_count = 0
    targeted_polynomial_count = 0
    targeted_demand_count = 0
    targeted_candidate_comparisons = 0
    ideal_membership_lemmas = 0
    hole_candidate_count = 0
    demanded_atoms: tuple[Atom, ...] = ()
    explicit_demanded_atoms: tuple[Atom, ...] = ()
    polynomial_sources: dict[str, str] = {}
    if isinstance(certificate, dict) and obligation_branches:
        for key in ("local_elimination_nodes", "separator_nodes"):
            for node in certificate.get(key, ()):
                if not isinstance(node, dict) or node.get("replayed") is not True:
                    continue
                node_id = str(node.get("node_id", key))
                for polynomial in node.get("output_polynomials", ()):
                    polynomial_sources.setdefault(str(polynomial), node_id)
        root = certificate.get("root")
        if (
            isinstance(root, dict)
            and certificate.get("all_local_certificates_replayed") is True
        ):
            for polynomial in root.get("remaining_polynomials", ()):
                polynomial_sources.setdefault(str(polynomial), "root")
        explicit_demanded_atoms, hole_demands = _ground_reelaboration_demands(
            formulation,
            obligation_branches,
            goal_atoms,
        )
        hole_candidate_count = len(hole_demands)
        demanded_atoms = tuple(
            dict.fromkeys((*explicit_demanded_atoms, *hole_demands))
        )
        if polynomial_sources and demanded_atoms:
            targeted_polynomial_count = len(polynomial_sources)
            targeted_demand_count = len(demanded_atoms)
            targeted_candidate_comparisons = (
                targeted_polynomial_count * targeted_demand_count
            )
            targeted = reelaborate_polynomial_lemmas(
                str(formulation).strip(),
                polynomial_sources,
                max_points=8,
                max_candidates_per_lemma=len(demanded_atoms),
                include_high_arity=True,
                candidate_atoms=demanded_atoms,
            )
            existing = {item[0] for item in recovered}
            for item in targeted:
                for typed_certificate in item.certificates:
                    atom = Atom(
                        typed_certificate.predicate,
                        typed_certificate.arguments,
                    ).canonical()
                    if atom in existing:
                        continue
                    recovered.append(
                        (
                            atom,
                            asdict(typed_certificate),
                            polynomial_sources[item.lemma_polynomial],
                        )
                    )
                    existing.add(atom)
                    targeted_count += 1
            ideal_generators = tuple(
                polynomial
                for polynomial, node_id in polynomial_sources.items()
                if node_id != "root"
            )
            ideal_certificates = certify_polynomial_ideal_relations(
                str(formulation).strip(),
                ideal_generators,
                explicit_demanded_atoms,
                max_multiplier_degree=ideal_max_multiplier_degree,
                max_matrix_columns=2_048,
                max_matrix_rows=4_096,
            )
            for ideal_certificate in ideal_certificates:
                serialized = asdict(ideal_certificate)
                if not verify_typed_relation_ideal_certificate(
                    str(formulation).strip(), serialized
                ):
                    continue
                atom = Atom(
                    ideal_certificate.predicate,
                    ideal_certificate.arguments,
                ).canonical()
                if atom in existing:
                    continue
                recovered.append((atom, serialized, "ideal:local-separator"))
                existing.add(atom)
                ideal_membership_lemmas += 1
    atoms = tuple(item[0] for item in recovered)
    if not atoms:
        # This stage is a certificate exchange, not a second unbounded copy of
        # native deduction.  With no recovered relation, replaying the native
        # closure through every hypergraph theorem cannot attribute progress
        # to polynomial re-elaboration and can explode during premise joins.
        return {
            "status": "no_certified_relations",
            "solved": False,
            "source": "polynomial_relation_reelaboration",
            "certified_lemmas": 0,
            "targeted_obligation_lemmas": targeted_count,
            "targeted_polynomial_count": targeted_polynomial_count,
            "targeted_demand_count": targeted_demand_count,
            "targeted_candidate_comparisons": targeted_candidate_comparisons,
            "ideal_membership_lemmas": ideal_membership_lemmas,
            "ideal_max_multiplier_degree": ideal_max_multiplier_degree,
            "hole_candidate_count": hole_candidate_count,
            "atoms": [],
            "hypergraph_proofs": [],
        }
    prover = BidirectionalHypergraphProver(rule_theorems)
    proofs = tuple(
        prover.prove((*native_facts, *atoms), goal, max_rounds=6)
        for goal in goal_atoms
    )
    solved = bool(proofs) and all(proof is not None for proof in proofs)
    return {
        "status": "proved" if solved else "open",
        "solved": solved,
        "source": "polynomial_relation_reelaboration",
        "certified_lemmas": len(atoms),
        "targeted_obligation_lemmas": targeted_count,
        "targeted_polynomial_count": targeted_polynomial_count,
        "targeted_demand_count": targeted_demand_count,
        "targeted_candidate_comparisons": targeted_candidate_comparisons,
        "ideal_membership_lemmas": ideal_membership_lemmas,
        "ideal_max_multiplier_degree": ideal_max_multiplier_degree,
        "hole_candidate_count": hole_candidate_count,
        "atoms": [
            {
                "atom": f"{atom.predicate}({','.join(atom.arguments)})",
                "source_node_id": node_id,
                "certificate_sha256": certificate.get("certificate_sha256"),
            }
            for atom, certificate, node_id in recovered
        ],
        "hypergraph_proofs": [
            proof.to_dict() for proof in proofs if proof is not None
        ],
    }


def _run_exact_specialist(
    formulation: JGEXFormulation,
    *,
    timeout_seconds: float,
    representation: str,
    max_saturation_rounds: int,
    verification_semaphore: BoundedSemaphore,
    goal: Atom | None = None,
    native_facts: tuple[Atom, ...] = (),
    guidance_atoms: tuple[Atom, ...] = (),
    guidance_branches: tuple[tuple[Atom, ...], ...] = (),
) -> dict[str, Any]:
    """Run exact elimination out of process so timeout is enforceable."""

    if timeout_seconds <= 0:
        return {"status": "disabled"}
    effective_goal = goal
    if representation == "typed_relation_separator" and effective_goal is None:
        source_goals = formulation_goal_atoms(formulation)
        if len(source_goals) != 1:
            return {
                "status": "unsupported",
                "reason": "typed relation separator requires exactly one goal",
            }
        effective_goal = source_goals[0]
    with tempfile.TemporaryDirectory(prefix="mortra-jgex-exact-terminal-") as raw:
        directory = Path(raw)
        input_path = directory / "problem.txt"
        output_path = directory / "result.json"
        native_facts_path = directory / "native-facts.json"
        guidance_relations_path = directory / "guidance-relations.json"
        guidance_branches_path = directory / "guidance-branches.json"
        input_path.write_text(str(formulation), encoding="utf-8")
        command = [
            sys.executable,
            "-B",
            str(ROOT / "scripts" / "run_jgex_exact_specialist.py"),
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--representation",
            representation,
            "--max-saturation-rounds",
            str(max_saturation_rounds),
        ]
        if representation not in {
            "typed_relation_separator",
            "construction_block_dag",
        }:
            command.append("--enable-affine-local-lemmas")
        if effective_goal is not None:
            command.extend(
                [
                    "--goal",
                    (
                        f"{effective_goal.predicate} "
                        f"{' '.join(effective_goal.arguments)}"
                    ),
                ]
            )
        if representation == "typed_relation_separator":
            native_facts_path.write_text(
                json.dumps(
                    [
                        {
                            "predicate": fact.predicate,
                            "arguments": list(fact.arguments),
                        }
                        for fact in native_facts
                    ],
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            command.extend(["--native-facts", str(native_facts_path)])
        if representation == "construction_block_dag" and guidance_atoms:
            guidance_relations_path.write_text(
                json.dumps(
                    [
                        {
                            "predicate": atom.predicate,
                            "arguments": list(atom.arguments),
                        }
                        for atom in guidance_atoms
                    ],
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            command.extend(
                ["--guidance-relations", str(guidance_relations_path)]
            )
        if representation == "construction_block_dag" and guidance_branches:
            guidance_branches_path.write_text(
                json.dumps(
                    [
                        [
                            {
                                "predicate": atom.predicate,
                                "arguments": list(atom.arguments),
                            }
                            for atom in branch
                        ]
                        for branch in guidance_branches
                    ],
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            command.extend(
                ["--guidance-branches", str(guidance_branches_path)]
            )
        started = time.perf_counter()
        try:
            with verification_semaphore:
                completed = subprocess.run(
                    command,
                    cwd=ROOT,
                    check=False,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=timeout_seconds,
                    env={**os.environ, "PYTHONHASHSEED": "0"},
                )
        except subprocess.TimeoutExpired:
            checkpoint = None
            if output_path.is_file():
                try:
                    checkpoint = json.loads(output_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    checkpoint = None
            return {
                "status": "right_censored_timeout",
                "elapsed_seconds": time.perf_counter() - started,
                "checkpoint": checkpoint,
            }
        if completed.returncode != 0 or not output_path.is_file():
            return {
                "status": "execution_error",
                "return_code": completed.returncode,
                "stderr_tail": completed.stderr[-2000:],
                "elapsed_seconds": time.perf_counter() - started,
            }
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        payload["elapsed_seconds"] = time.perf_counter() - started
        payload["input_sha256"] = hashlib.sha256(
            input_path.read_bytes()
        ).hexdigest()
        return payload


def _run_gclc_specialist(
    formulation: JGEXFormulation,
    *,
    gclc_exe: Path | None,
    methods: tuple[str, ...],
    timeout_seconds: int,
    verification_semaphore: BoundedSemaphore,
    goal: Atom | None = None,
) -> dict[str, Any]:
    """Run an ordered GCLC prover portfolio and retain the first certificate."""

    if gclc_exe is None or timeout_seconds <= 0:
        return {"status": "disabled"}
    started = time.perf_counter()
    deadline = started + timeout_seconds
    if goal is not None:
        target_formulation = _formulation_with_goal(formulation, goal)
        if target_formulation is None:
            return {
                "status": "unsupported",
                "reason": "invalid or unsupported typed GCLC goal",
                "elapsed_seconds": time.perf_counter() - started,
            }
        formulation = target_formulation
    source_text = str(formulation)
    try:
        translation = translate_jgex_to_gclc(
            source_text,
            enable_structural_lemmas=True,
            goal_local=goal is not None,
        )
    except ValueError as exc:
        return {
            "status": "unsupported",
            "reason": str(exc),
            "elapsed_seconds": time.perf_counter() - started,
        }
    except Exception as exc:
        return {
            "status": "execution_error",
            "reason": f"{type(exc).__name__}: {exc}",
            "elapsed_seconds": time.perf_counter() - started,
        }

    with tempfile.TemporaryDirectory(prefix="mortra-gclc-terminal-") as raw:
        directory = Path(raw)
        source_path = directory / "obligation.gcl"
        source_path.write_text(translation.source, encoding="utf-8")
        method_runs: list[dict[str, Any]] = []
        selected_run: dict[str, Any] | None = None
        selected_proof_path: Path | None = None
        for method in methods:
            remaining = remaining_stage_seconds(deadline)
            if remaining <= 0:
                method_runs.append(
                    {
                        "method": method,
                        "proved": False,
                        "external_timeout_reached": True,
                        "reason": "gclc_portfolio_stage_budget_exhausted",
                    }
                )
                break
            proof_path = directory / f"proof-{method}.tex"
            try:
                with verification_semaphore:
                    run = run_method(
                        gclc_exe.resolve(),
                        source_path,
                        GCLC_METHOD_FLAGS[method],
                        method,
                        prover_timeout_seconds=max(1, math.ceil(remaining)),
                        proof_output=proof_path,
                    )
            except Exception as exc:
                run = {
                    "method": method,
                    "proved": False,
                    "external_timeout_reached": False,
                    "execution_error": f"{type(exc).__name__}: {exc}",
                }
            method_runs.append(run)
            if run.get("proved") and proof_path.is_file():
                selected_run = run
                selected_proof_path = proof_path
                break
        run = selected_run or method_runs[-1]
        # If one sound prover is stopped, another inapplicable or failed
        # method cannot turn the unfinished portfolio into a disproof.
        any_timed_out = any(_gclc_run_timed_out(item) for item in method_runs)
        payload = {
            "status": (
                "proved"
                if selected_run is not None
                else "right_censored_timeout"
                if any_timed_out
                else "unproved"
            ),
            "translation": {
                "source_sha256": hashlib.sha256(
                    translation.source.encode("utf-8")
                ).hexdigest(),
                "source_lines": len(translation.source.splitlines()),
                "original_clause_count": translation.original_clause_count,
                "translated_clause_count": translation.translated_clause_count,
                "local_lemma_certificates": translation.local_lemma_certificates,
            },
            "run": run,
            "method_runs": method_runs,
            "selected_method": (
                selected_run["method"] if selected_run is not None else None
            ),
            "elapsed_seconds": time.perf_counter() - started,
            "input_sha256": hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
        }
        if selected_run is not None and selected_proof_path is not None:
            payload["proof_text"] = selected_proof_path.read_text(
                encoding="utf-8", errors="replace"
            )
            payload["proof_file_sha256"] = _file_sha256(selected_proof_path)
        return payload


def _run_wolfram_polynomial_specialist(
    formulation: JGEXFormulation,
    *,
    wolfram_exe: Path | None,
    timeout_seconds: int,
    preprocessing: str,
    reduction_mode: str,
    saturation_mode: str,
    max_saturation_factors: int,
    goal: Atom,
) -> dict[str, Any]:
    """Search for a Wolfram cofactor witness and replay it in SymPy."""

    if wolfram_exe is None or timeout_seconds <= 0:
        return {"status": "disabled", "source": "wolfram_polynomial_certificate"}
    target = _formulation_with_goal(formulation, goal)
    if target is None:
        return {
            "status": "unsupported",
            "source": "wolfram_polynomial_certificate",
            "reason": "invalid or unsupported typed polynomial goal",
        }
    try:
        certificate = certify_jgex_with_wolfram(
            str(target),
            executable=wolfram_exe,
            timeout_seconds=timeout_seconds,
            preprocessing=preprocessing,
            reduction_mode=reduction_mode,
            saturation_mode=saturation_mode,
            max_saturation_factors=max_saturation_factors,
        )
    except Exception as exc:
        return {
            "status": "execution_error",
            "source": "wolfram_polynomial_certificate",
            "reason": f"{type(exc).__name__}: {exc}",
        }
    return {
        "status": certificate.status,
        "source": "wolfram_polynomial_certificate",
        "elapsed_seconds": certificate.elapsed_seconds,
        "input_sha256": hashlib.sha256(str(target).encode()).hexdigest(),
        "certificate": asdict(certificate),
    }


def _run_gclc_lemma_exchange(
    formulation: JGEXFormulation,
    *,
    obligation_branches: tuple[tuple[Atom, ...], ...],
    native_facts: tuple[Atom, ...],
    goal_atoms: tuple[Atom, ...],
    rule_theorems: tuple[Any, ...],
    lemma_limit: int,
    gclc_exe: Path | None,
    methods: tuple[str, ...],
    timeout_seconds: int,
    verification_semaphore: BoundedSemaphore,
    incidence_samples: int = 0,
    wolfram_exe: Path | None = None,
    wolfram_timeout_seconds: int = 0,
    wolfram_preprocessing: str = "local_relational",
    wolfram_reduction_mode: str = "extended_groebner",
    wolfram_saturation_mode: str = "none",
    wolfram_max_saturation_factors: int = 12,
) -> dict[str, Any]:
    """Certify small open obligations, then replay them in the typed proof DAG.

    The candidate language is the finite GCLC relation interface.  Candidates
    must be ground atoms from a coherent open branch; benchmark identifiers,
    expected answers, and dataset auxiliary clauses are never consulted.  A
    proved local relation is evidence, not a terminal answer: every original
    goal must still close under the public theorem hypergraph.
    """

    stage_started = time.perf_counter()
    gclc_deadline = stage_started + timeout_seconds
    wolfram_deadline = stage_started + wolfram_timeout_seconds
    gclc_enabled = gclc_exe is not None and timeout_seconds > 0
    wolfram_enabled = wolfram_exe is not None and wolfram_timeout_seconds > 0
    if lemma_limit <= 0 or not (gclc_enabled or wolfram_enabled):
        return {"status": "disabled", "solved": False, "lemmas": []}

    executable_branches = _gclc_executable_obligation_branches(
        native_facts,
        obligation_branches,
        rule_theorems,
        deadline=max(gclc_deadline, wolfram_deadline),
    )
    goal_keys = {goal.canonical() for goal in goal_atoms}
    native_keys = {fact.canonical() for fact in native_facts}
    raw_candidates = tuple(
        dict.fromkeys(
            atom.canonical()
            for branch in executable_branches
            for atom in branch
            if _gclc_goal_construction(atom) is not None
            and atom.canonical() not in native_keys
        )
    )[: max(lemma_limit, lemma_limit * 8)]
    incidence_records: list[dict[str, Any]] = []
    selected_candidates: list[Atom] = []
    for atom in raw_candidates:
        passed, errors = _passes_gclc_numerical_incidence(
            formulation,
            atom,
            samples=incidence_samples,
        )
        incidence_records.append(
            {
                "atom": f"{atom.predicate}({','.join(atom.arguments)})",
                "passed": passed,
                "errors": errors,
            }
        )
        if passed:
            selected_candidates.append(atom)
            if len(selected_candidates) >= lemma_limit:
                break
    candidates = tuple(selected_candidates)
    prover = BidirectionalHypergraphProver(rule_theorems)

    certified: list[Atom] = []
    lemma_records: list[dict[str, Any]] = []
    for atom in candidates:
        gclc_result: dict[str, Any] | None = None
        wolfram_result: dict[str, Any] | None = None
        # The native verifier already tried the benchmark goal.  Repeating a
        # deep Python closure here can run for minutes outside the specialist
        # timeout.  Preserve only a small precheck for intermediate lemmas;
        # original goals are delegated directly to GCLC/Wolfram.
        typed_proof = (
            None
            if atom.canonical() in goal_keys
            else prover.prove(
                native_facts,
                atom,
                max_rounds=3,
                deadline=max(gclc_deadline, wolfram_deadline),
            )
        )
        if typed_proof is not None:
            result = {
                "status": "proved",
                "source": "typed_theorem_hypergraph",
                "hypergraph_proof": typed_proof.to_dict(),
                "elapsed_seconds": 0.0,
            }
        else:
            gclc_remaining = remaining_stage_seconds(gclc_deadline)
            gclc_result = (
                _run_gclc_specialist(
                    formulation,
                    gclc_exe=gclc_exe,
                    methods=methods,
                    timeout_seconds=max(1, math.ceil(gclc_remaining)),
                    verification_semaphore=verification_semaphore,
                    goal=atom,
                )
                if gclc_enabled and gclc_remaining > 0
                else {
                    "status": "right_censored_timeout",
                    "source": "gclc_local_relation",
                    "reason": "gclc_lemma_stage_budget_exhausted",
                    "elapsed_seconds": 0.0,
                }
            )
            gclc_result.setdefault("source", "gclc_local_relation")
            wolfram_remaining = remaining_stage_seconds(wolfram_deadline)
            wolfram_result = (
                _run_wolfram_polynomial_specialist(
                    formulation,
                    wolfram_exe=wolfram_exe,
                    timeout_seconds=max(1, math.ceil(wolfram_remaining)),
                    preprocessing=wolfram_preprocessing,
                    reduction_mode=wolfram_reduction_mode,
                    saturation_mode=wolfram_saturation_mode,
                    max_saturation_factors=wolfram_max_saturation_factors,
                    goal=atom,
                )
                if gclc_result.get("status") != "proved"
                and wolfram_enabled
                and wolfram_remaining > 0
                else {"status": "skipped_after_gclc_proof"}
                if gclc_result.get("status") == "proved"
                else {
                    "status": "right_censored_timeout",
                    "source": "wolfram_polynomial_certificate",
                    "reason": "wolfram_lemma_stage_budget_exhausted",
                    "elapsed_seconds": 0.0,
                }
                if wolfram_enabled
                else {"status": "disabled"}
            )
            result = (
                wolfram_result
                if wolfram_result.get("status") == "proved"
                else gclc_result
            )
            if (
                result.get("status") != "proved"
                and "right_censored_timeout"
                in {
                    gclc_result.get("status"),
                    wolfram_result.get("status"),
                }
            ):
                result = {**result, "status": "right_censored_timeout"}
            result["portfolio_diagnostics"] = {
                "gclc": {
                    "status": gclc_result.get("status"),
                    "elapsed_seconds": gclc_result.get("elapsed_seconds"),
                },
                "wolfram": {
                    "status": wolfram_result.get("status"),
                    "elapsed_seconds": wolfram_result.get("elapsed_seconds"),
                    "preprocessing": wolfram_preprocessing,
                    "reduction_mode": wolfram_reduction_mode,
                    "saturation_mode": wolfram_saturation_mode,
                    "max_saturation_factors": wolfram_max_saturation_factors,
                },
            }
        if result.get("status") == "proved":
            certified.append(atom)
        record = {
            "atom": f"{atom.predicate}({','.join(atom.arguments)})",
            "status": result.get("status"),
            "source": result.get("source", "gclc_local_relation"),
            "elapsed_seconds": result.get("elapsed_seconds"),
            "input_sha256": result.get("input_sha256"),
            "selected_method": result.get("selected_method"),
            "proof_sha256": (
                result.get("run", {}).get("proof_sha256")
                if isinstance(result.get("run"), dict)
                else None
            ),
            "proof_file_sha256": result.get("proof_file_sha256"),
            "translation": (
                gclc_result.get("translation")
                if isinstance(gclc_result, dict)
                else result.get("translation")
            ),
            "method_diagnostics": [
                _gclc_run_diagnostic(run)
                for run in (
                    gclc_result.get("method_runs", ())
                    if isinstance(gclc_result, dict)
                    else result.get("method_runs", ())
                )
                if isinstance(run, dict)
            ],
            "portfolio_diagnostics": result.get("portfolio_diagnostics"),
            "wolfram_certificate": (
                wolfram_result.get("certificate")
                if isinstance(wolfram_result, dict)
                else None
            ),
        }
        if result.get("proof_text"):
            record["proof_text"] = result["proof_text"]
        if result.get("hypergraph_proof"):
            record["hypergraph_proof"] = result["hypergraph_proof"]
        lemma_records.append(record)

    proofs = (
        tuple(
            prover.prove(
                (*native_facts, *certified),
                goal,
                max_rounds=3,
                deadline=max(gclc_deadline, wolfram_deadline),
            )
            for goal in goal_atoms
        )
        if certified
        else tuple(None for _ in goal_atoms)
    )
    solved = bool(proofs) and all(proof is not None for proof in proofs)
    stage_exhausted = (
        (gclc_enabled and remaining_stage_seconds(gclc_deadline) <= 0)
        or (wolfram_enabled and remaining_stage_seconds(wolfram_deadline) <= 0)
    )
    return {
        "status": (
            "proved"
            if solved
            else "right_censored_timeout"
            if stage_exhausted
            else "open"
        ),
        "solved": solved,
        "eligible_ground_obligations": len(candidates),
        "source_obligation_branches": len(obligation_branches),
        "executable_obligation_branches": len(executable_branches),
        "certified_lemmas": len(certified),
        "numerical_incidence": {
            "samples": incidence_samples,
            "checked": len(incidence_records),
            "accepted": len(candidates),
            "records": incidence_records,
        },
        "lemmas": lemma_records,
        "hypergraph_proofs": [
            proof.to_dict() for proof in proofs if proof is not None
        ],
    }


def _run_exact_lemma_exchange(
    formulation: JGEXFormulation,
    *,
    obligation_branches: tuple[tuple[Atom, ...], ...],
    native_facts: tuple[Atom, ...],
    goal_atoms: tuple[Atom, ...],
    rule_theorems: tuple[Any, ...],
    lemma_limit: int,
    timeout_seconds: float,
    representation: str,
    max_saturation_rounds: int,
    verification_semaphore: BoundedSemaphore,
) -> dict[str, Any]:
    """Exchange replayed exact lemmas with the typed theorem prover.

    Only ground atoms from a currently open coherent branch are eligible.
    An exact lemma is not an answer by itself: MORTRA reports a solve only
    when the native facts, replayed lemmas, and public theorem rules close
    every original goal in a replayable hypergraph proof.
    """

    if lemma_limit <= 0:
        return {"status": "disabled", "solved": False, "lemmas": []}
    stage_started = time.perf_counter()
    deadline = stage_started + timeout_seconds
    candidates = tuple(
        dict.fromkeys(
            atom.canonical()
            for branch in obligation_branches
            for atom in branch
            if not any(argument.startswith("?") for argument in atom.arguments)
            and atom.predicate in (SUPPORTED_GOALS | {"eqratio", "midp"})
            and relation_is_nondegenerate(atom)
        )
    )[:lemma_limit]
    prover = BidirectionalHypergraphProver(rule_theorems)
    goal_keys = {goal.canonical() for goal in goal_atoms}

    certified: list[Atom] = []
    raw_results: list[tuple[Atom, dict[str, Any]]] = []
    reelaborated: dict[Atom, tuple[dict[str, Any], str]] = {}
    for atom in candidates:
        # The native verifier already rejected the original goal.  Re-running
        # an unrestricted Python hypergraph closure here duplicates work and
        # is not covered by the exact-backend timeout.  Only small intermediate
        # obligations get a bounded typed precheck; original goals go directly
        # to the interruptible exact backend.
        typed_proof = (
            None
            if atom.canonical() in goal_keys
            else prover.prove(
                native_facts,
                atom,
                max_rounds=3,
                deadline=deadline,
            )
        )
        if typed_proof is not None:
            result = {
                "status": "proved",
                "source": "typed_theorem_hypergraph",
                "hypergraph_proof": typed_proof.to_dict(),
                "elapsed_seconds": 0.0,
            }
        elif timeout_seconds > 0:
            remaining = remaining_stage_seconds(deadline)
            result = (
                _run_exact_specialist(
                    formulation,
                    timeout_seconds=remaining,
                    representation=representation,
                    max_saturation_rounds=max_saturation_rounds,
                    verification_semaphore=verification_semaphore,
                    goal=atom,
                    native_facts=native_facts,
                )
                if remaining > 0
                else {
                    "status": "right_censored_timeout",
                    "reason": "exact_lemma_stage_budget_exhausted",
                    "elapsed_seconds": 0.0,
                }
            )
        else:
            result = {
                "status": "exact_disabled",
                "source": "typed_theorem_hypergraph",
                "elapsed_seconds": 0.0,
            }
        raw_results.append((atom, result))
        if result.get("status") == "proved":
            certified.append(atom)
        for recovered, recovered_certificate, node_id in (
            _reelaborated_relation_atoms(
                formulation,
                result.get("certificate"),
            )
        ):
            reelaborated.setdefault(
                recovered,
                (recovered_certificate, node_id),
            )

    certified = list(
        dict.fromkeys((*certified, *reelaborated.keys()))
    )

    proofs = (
        tuple(
            prover.prove(
                (*native_facts, *certified),
                goal,
                max_rounds=3,
                deadline=deadline,
            )
            for goal in goal_atoms
        )
        if certified
        else tuple(None for _ in goal_atoms)
    )
    solved = bool(proofs) and all(proof is not None for proof in proofs)
    lemma_records = []
    for atom, result in raw_results:
        certificate = result.get("certificate")
        record = {
            "atom": f"{atom.predicate}({','.join(atom.arguments)})",
            "status": result.get("status"),
            "reason": result.get("reason"),
            "return_code": result.get("return_code"),
            "stderr_tail": result.get("stderr_tail"),
            "source": result.get("source", "jgex_exact_elimination"),
            "elapsed_seconds": result.get("elapsed_seconds"),
            "input_sha256": result.get("input_sha256"),
            "certificate_sha256": (
                certificate.get("certificate_sha256")
                if isinstance(certificate, dict)
                else None
            ),
            "checkpoint": result.get("checkpoint"),
            "related_native_facts": _relation_demand_trace(
                tuple(
                    sorted(
                        (
                            fact.canonical()
                            for fact in native_facts
                            if fact.predicate in {atom.predicate, "para", "perp"}
                            and len(
                                set(fact.arguments) & set(atom.arguments)
                            )
                            >= 2
                        ),
                        key=lambda item: (item.predicate, item.arguments),
                    )[:24]
                )
            ),
        }
        if isinstance(certificate, dict) and result.get("status") == "proved":
            record["certificate"] = certificate
        elif isinstance(certificate, dict):
            record["diagnostic"] = {
                key: certificate.get(key)
                for key in (
                    "target_atom",
                    "target_polynomial",
                    "native_fact_basis_sha256",
                    "selection_policy",
                    "selected_native_premises",
                    "selected_construction_equations",
                    "variables",
                    "local_elimination",
                    "macaulay_attempts",
                    "stages",
                    "exact_replay",
                    "certificate_sha256",
                )
            }
        if solved and result.get("hypergraph_proof"):
            record["hypergraph_proof"] = result["hypergraph_proof"]
        lemma_records.append(record)
    lemma_records.extend(
        {
            "atom": f"{atom.predicate}({','.join(atom.arguments)})",
            "status": "proved",
            "source": "polynomial_relation_reelaboration",
            "certificate_sha256": certificate.get("certificate_sha256"),
            "source_node_id": node_id,
            "certificate": certificate,
        }
        for atom, (certificate, node_id) in reelaborated.items()
    )
    stage_exhausted = remaining_stage_seconds(deadline) <= 0
    return {
        "status": (
            "proved"
            if solved
            else "right_censored_timeout"
            if stage_exhausted
            else "open"
        ),
        "solved": solved,
        "eligible_ground_obligations": len(candidates),
        "certified_lemmas": len(certified),
        "reelaborated_lemmas": len(reelaborated),
        "lemmas": lemma_records,
        "hypergraph_proofs": [
            proof.to_dict() for proof in proofs if proof is not None
        ],
    }


def _attempt(
    *,
    attempt_index: int,
    seed: int,
    rounds: int,
    base_formulation: JGEXFormulation,
    base_problem: Any,
    base_points: set[str],
    base_graph: dict[str, set[str]],
    base_role_graph: dict[str, set[str]],
    base_role_weights: dict[tuple[str, str], int],
    goal_multiplicity: dict[str, int],
    proof_relevance: dict[str, float],
    relation_demands: tuple[Any, ...],
    relation_obligation_branches: tuple[tuple[Any, ...], ...],
    reachable_channels: set[str],
    target_channels: set[str],
    relation_distances: dict[str, dict[str, int]],
    goal_atoms: tuple[Any, ...],
    baseline_facts: tuple[Any, ...],
    rule_theorems: tuple[Any, ...],
    per_family_limit: int,
    incidence_oversample_per_family: int,
    incidence_preselect_limit: int,
    incidence_workers: int,
    candidate_limit: int,
    yuclid_exe: Path,
    ar_profile: str,
    candidate_policy: str,
    rank_temperature: float,
    incremental_prefix: bool,
    feedback_candidates: int,
    feedback_workers: int,
    trajectory_credit_scores: dict[str, float],
    verification_semaphore: BoundedSemaphore,
    exact_specialist_timeout_seconds: float,
    exact_specialist_representation: str,
    exact_specialist_saturation_rounds: int,
    exact_lemma_limit: int,
    gclc_exe: Path | None,
    gclc_methods: tuple[str, ...],
    gclc_timeout_seconds: int,
    gclc_lemma_limit: int,
    gclc_incidence_samples: int,
    wolfram_exe: Path | None,
    wolfram_timeout_seconds: int,
    wolfram_preprocessing: str,
    wolfram_reduction_mode: str,
    wolfram_saturation_mode: str,
    wolfram_max_saturation_factors: int,
) -> dict[str, Any]:
    started = time.perf_counter()
    policy = candidate_policy_spec(candidate_policy)
    structured_policy = policy.structured
    alignment_mode = policy.alignment_mode
    mmt_exact_enabled = candidate_policy in {
        "mmt-sheaf",
        "mmt-hageo",
        "mmt-hageo-lite",
    }
    attempt_seed = seed + 1_000_003 * attempt_index
    rng = random.Random(attempt_seed)
    steps: tuple[ConstructionStep, ...] = ()
    rounds_trace: list[dict[str, Any]] = []
    trajectory_relation_demands: list[tuple[Any, ...]] = []
    current_problem = base_problem.model_copy(deep=True)
    last_verification = None
    verification_calls = 0
    active_relation_demands = relation_demands
    active_obligation_branches = relation_obligation_branches
    active_reachable_channels = reachable_channels
    active_target_channels = target_channels
    active_relation_distances = relation_distances
    active_proof_facts = tuple(baseline_facts)
    active_native_facts = tuple(baseline_facts)
    exchanged_fact_keys = {item.canonical() for item in active_proof_facts}
    rule_channels = [
        (
            [premise.name for premise in rule.premises],
            [conclusion.name for conclusion in rule.conclusions],
        )
        for rule in DEFAULT_RULES
    ]

    try:
        for round_index in range(rounds):
            if (
                policy.typed_contract_synthesis
                and active_obligation_branches
                and not policy.ground_residual_synthesis
                and not any(
                    obligation_signature(atom).requires_witness
                    for branch in active_obligation_branches
                    for atom in branch
                )
            ):
                expanded_branches = _expand_contract_obligation_branches(
                    active_native_facts,
                    active_obligation_branches,
                    rule_theorems,
                )
                if not any(
                    obligation_signature(atom).requires_witness
                    for branch in expanded_branches
                    for atom in branch
                ) and not policy.ground_residual_synthesis:
                    return {
                        "attempt": attempt_index,
                        "status": "deductive_frontier_no_construction",
                        "solved": False,
                        "rounds_completed": round_index,
                        "path": [step.key for step in steps],
                        "rounds": rounds_trace,
                        "open_obligation_branches": [
                            _relation_demand_trace(tuple(branch))
                            for branch in active_obligation_branches
                        ],
                        "elapsed_seconds": time.perf_counter() - started,
                    }
                active_obligation_branches = expanded_branches
                active_relation_demands = tuple(
                    dict.fromkeys(
                        atom
                        for branch in active_obligation_branches
                        for atom in branch
                    )
                )
            candidate_proof_facts = active_proof_facts
            if policy.ground_residual_synthesis:
                candidate_proof_facts = goal_conditioned_proof_basis(
                    active_proof_facts,
                    goal_atoms,
                    rule_theorems,
                    point_radius=1,
                    max_facts=32,
                    max_obligations=32,
                )
            relation_demands_in = active_relation_demands
            obligation_branches_in = active_obligation_branches
            extensions, audit = candidate_extensions(
                base_problem=base_problem,
                base_points=base_points,
                base_graph=base_graph,
                base_role_graph=base_role_graph,
                base_role_weights=base_role_weights,
                goal_multiplicity=goal_multiplicity,
                proof_relevance=proof_relevance,
                steps=steps,
                families=EXTENDED_POINT_FAMILIES,
                per_family_limit=per_family_limit,
                branch_limit=candidate_limit,
                ranking=(
                    "structural" if structured_policy else "random"
                ),
                seed=branch_seed(attempt_seed + round_index, steps),
                relation_demands=active_relation_demands,
                require_generated_input=False,
                candidate_gate="executable-precondition",
                candidate_reachable_channels=active_reachable_channels,
                candidate_target_channels=active_target_channels,
                candidate_alignment=alignment_mode,
                candidate_relation_distances=(
                    active_relation_distances if structured_policy else None
                ),
                # The lite condition isolates MMT transport from the much more
                # expensive bidirectional proof-DAG specialist.  It is an
                # ablation, not a different truth criterion.
                proof_dag_goals=(
                    proof_dag_search_roots(
                        goal_atoms,
                        active_relation_demands,
                        ground_residual_synthesis=(
                            policy.ground_residual_synthesis
                        ),
                    )
                    if structured_policy and candidate_policy != "mmt-hageo-lite"
                    else ()
                ),
                proof_dag_facts=(
                    candidate_proof_facts if structured_policy else ()
                ),
                proof_dag_theorems=(
                    rule_theorems if structured_policy else ()
                ),
                candidate_cone_depth=PROOF_DAG_STAGE_ONE["depth"],
                candidate_cone_fragments=PROOF_DAG_STAGE_ONE["fragments"],
                candidate_cone_states=PROOF_DAG_STAGE_ONE["states_per_task"],
                candidate_cone_initial_states=PROOF_DAG_STAGE_ONE[
                    "initial_states_per_candidate"
                ],
                candidate_promotion_limit=PROOF_DAG_STAGE_ONE[
                    "reserved_consensus"
                ],
                candidate_incidence="hageo",
                incidence_oversample_per_family=incidence_oversample_per_family,
                incidence_preselect_limit=incidence_preselect_limit,
                incidence_workers=incidence_workers,
                current_problem=current_problem,
                construction_seed=attempt_seed,
                candidate_contract_synthesis=policy.typed_contract_synthesis,
                contract_obligation_branches=obligation_branches_in,
            )
            typed_plan_supported_keys = {
                str(item.get("candidate"))
                for item in audit.get("candidate_alignment", {}).get(
                    "top_candidates", ()
                )
                if item.get("has_closed_structural_residual")
                or item.get("has_residual_reduction")
            }
            base_pool = candidate_pool(
                extensions,
                audit,
                hard_incidence_gate=policy.hard_incidence_gate,
                preserve_family_frontier=policy.preserve_family_frontier,
                family_order=[family.name for family in EXTENDED_POINT_FAMILIES],
            )
            pool = base_pool
            terminal_credit_ranking: list[dict[str, object]] = []
            if policy.terminal_credit:
                pool, terminal_credit_ranking = rank_with_terminal_credit(
                    pool,
                    generated_outputs=(step.output for step in steps),
                    relation_demands=relation_demands_in,
                    scores=trajectory_credit_scores,
                )
            obligation_matches_by_candidate: dict[str, list[str]] = {}
            obligation_credit_ranking: list[dict[str, object]] = []
            if policy.obligation_conditioned_credit:
                for candidate in base_pool:
                    candidate_atoms = construction_relation_atoms(
                        candidate.family,
                        candidate.output,
                        candidate.inputs,
                    )
                    matched = [
                        (
                            f"{demand.canonical().predicate}"
                            f"({','.join(demand.canonical().arguments)})"
                        )
                        for demand in relation_demands_in
                        if candidate_directly_satisfies_obligation(
                            candidate_atoms,
                            demand,
                        )
                    ]
                    if matched:
                        obligation_matches_by_candidate[candidate.key] = matched
                obligation_credit_ranking = obligation_conditioned_credit_ranking(
                    terminal_credit_ranking,
                    obligation_matches_by_candidate,
                )
            if not pool:
                return {
                    "attempt": attempt_index,
                    "status": "no_executable_candidate",
                    "solved": False,
                    "rounds_completed": round_index,
                    "path": [step.key for step in steps],
                    "rounds": rounds_trace,
                    "elapsed_seconds": time.perf_counter() - started,
                }
            feedback_trace: list[dict[str, Any]] = []
            shortlist_channels: list[dict[str, str]] = []
            observed_relation_demands = active_relation_demands
            residual_feedback_applied = False
            if structured_policy and feedback_candidates > 0:
                credited_prefix = sum(
                    float(item["credit_score"]) > 0.0
                    for item in terminal_credit_ranking
                )
                if policy.terminal_credit_mix:
                    shortlist, shortlist_channels = mixed_credit_residual_shortlist(
                        base_pool,
                        (
                            obligation_credit_ranking
                            if policy.obligation_conditioned_credit
                            else terminal_credit_ranking
                        ),
                        count=min(feedback_candidates, len(base_pool)),
                        rng=rng,
                        temperature=(
                            0.0 if attempt_index == 0 else rank_temperature
                        ),
                        trajectory_index=attempt_index,
                        credit_slots=policy.terminal_credit_mix,
                    )
                    if policy.obligation_conditioned_credit:
                        shortlist_channels = [
                            {
                                **item,
                                "channel": (
                                    "obligation_credit_probe"
                                    if item["channel"] == "terminal_credit"
                                    else item["channel"]
                                ),
                            }
                            for item in shortlist_channels
                        ]
                else:
                    shortlist = (
                        _contract_diverse_shortlist(
                            pool,
                            relation_demands_in,
                            count=min(feedback_candidates, len(pool)),
                        )
                        if policy.typed_contract_synthesis
                        else rank_biased_shortlist(
                            pool,
                            count=min(feedback_candidates, len(pool)),
                            rng=rng,
                            temperature=(
                                0.0
                                if attempt_index == 0
                                else rank_temperature
                            ),
                            trajectory_index=attempt_index,
                            protected_prefix=min(
                                feedback_candidates,
                                credited_prefix,
                            ),
                        )
                    )
                    shortlist_channels = [
                        {
                            "candidate": str(getattr(candidate, "key")),
                            "channel": (
                                "terminal_credit"
                                if position < min(
                                    feedback_candidates, credited_prefix
                                )
                                else "residual_frontier"
                            ),
                        }
                        for position, (_, candidate) in enumerate(shortlist)
                    ]
                shortlist_channel_by_key = {
                    item["candidate"]: item["channel"]
                    for item in shortlist_channels
                }

                direct_match_counts = {
                    key: len(value)
                    for key, value in obligation_matches_by_candidate.items()
                }

                def evaluate_candidate(index_and_step):
                    index, candidate = index_and_step
                    candidate_steps = (*steps, candidate)
                    try:
                        candidate_problem = (
                            extend_prefix_branch(
                                current_problem,
                                candidate,
                                candidate_steps,
                                seed=attempt_seed,
                            )
                            if incremental_prefix
                            else build_branch(
                                base_problem,
                                candidate_steps,
                                seed=attempt_seed,
                            )
                        )
                        with verification_semaphore:
                            verification = verify_problem(
                                candidate_problem,
                                yuclid_exe=yuclid_exe,
                                ar_profile=ar_profile,
                            )
                        (
                            residual,
                            candidate_demands,
                            candidate_obligation_branches,
                        ) = _proof_residual_state(
                            verification.payload,
                            goal_atoms=goal_atoms,
                            rule_theorems=rule_theorems,
                            parent_demands=relation_demands_in,
                            parent_proved_atoms=active_native_facts,
                            contract_frontier=(
                                policy.typed_contract_synthesis
                                and not policy.ground_residual_synthesis
                            ),
                        )
                        branch_reduction = reduce_obligation_branches(
                            construction_relation_atoms(
                                candidate.family,
                                candidate.output,
                                candidate.inputs,
                            ),
                            obligation_branches_in,
                        )
                        branch_reduction = carry_construction_requirements(
                            branch_reduction,
                            construction_requirement_atoms(
                                candidate.family,
                                candidate.output,
                                candidate.inputs,
                            ),
                            active_native_facts,
                        )
                        residual["circular_goal_transport"] = (
                            _is_circular_goal_transport(
                                construction_relation_atoms(
                                    candidate.family,
                                    candidate.output,
                                    candidate.inputs,
                                ),
                                branch_reduction.progressed_branches,
                                goal_atoms,
                                rule_theorems,
                            )
                        )
                        return (
                            index,
                            candidate,
                            candidate_problem,
                            verification,
                            residual,
                            candidate_demands,
                            candidate_obligation_branches,
                            branch_reduction,
                            None,
                        )
                    except Exception as exc:
                        return (
                            index,
                            candidate,
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            f"{type(exc).__name__}: {exc}",
                        )

                with ThreadPoolExecutor(max_workers=feedback_workers) as executor:
                    evaluations = list(
                        executor.map(evaluate_candidate, shortlist)
                    )
                verification_calls += len(evaluations)
                successful = [item for item in evaluations if item[3] is not None]
                if successful and policy.typed_contract_synthesis:
                    causal = [
                        item
                        for item in successful
                        if candidate_made_causal_progress(
                            solved=item[3].solved,
                            ground_residual_synthesis=(
                                policy.ground_residual_synthesis
                            ),
                            matched_obligation_atoms=(
                                item[7].matched_atom_count
                            ),
                            closed_parent_demands=int(
                                item[4].get("closed_parent_demands", 0)
                            ),
                            circular_goal_transport=bool(
                                item[4].get("circular_goal_transport", False)
                            ),
                            typed_plan_supported=(
                                item[1].key in typed_plan_supported_keys
                            ),
                        )
                    ]
                    if not causal:
                        return {
                            "attempt": attempt_index,
                            "status": "no_causal_contract_candidate",
                            "solved": False,
                            "rounds_completed": round_index,
                            "path": [step.key for step in steps],
                            "rounds": rounds_trace,
                            "open_obligation_branches": [
                                _relation_demand_trace(tuple(branch))
                                for branch in obligation_branches_in
                            ],
                            "evaluated_candidates": [
                                {
                                    "candidate": item[1].key,
                                        "matched_atom_count": (
                                            item[7].matched_atom_count
                                        ),
                                        "closed_parent_demands": item[4].get(
                                            "closed_parent_demands", 0
                                        ),
                                        "typed_plan_supported": (
                                            item[1].key
                                            in typed_plan_supported_keys
                                        ),
                                        "circular_goal_transport": item[4].get(
                                            "circular_goal_transport", False
                                        ),
                                }
                                for item in successful
                            ],
                            "candidate_alignment": audit.get(
                                "candidate_alignment", {}
                            ),
                            "elapsed_seconds": time.perf_counter() - started,
                        }
                    successful = causal
                if successful:
                    if policy.obligation_conditioned_credit:
                        selected = min(
                            successful,
                            key=lambda item: obligation_conditioned_selection_key(
                                solved=item[3].solved,
                                residual=item[4],
                                verified_credit=verified_obligation_credit(
                                    selection_channel=shortlist_channel_by_key.get(
                                        item[1].key, "residual_frontier"
                                    ),
                                    matched_obligations=obligation_matches_by_candidate.get(
                                        item[1].key, ()
                                    ),
                                    residual=item[4],
                                ),
                                static_rank=item[0],
                            ),
                        )
                    else:
                        selected = min(
                            successful,
                            key=lambda item: (
                                not item[3].solved,
                                *(
                                    (
                                        -item[7].fully_closed_branch_count,
                                        -item[7].matched_atom_count,
                                    )
                                    if policy.typed_contract_synthesis
                                    else ()
                                ),
                                proof_residual_order_key(item[4]),
                                item[0],
                            ),
                        )
                    (
                        _,
                        chosen,
                        current_problem,
                        last_verification,
                        selected_residual,
                        selected_demands,
                        selected_obligation_branches,
                        selected_branch_reduction,
                        _,
                    ) = selected
                    if (
                        policy.typed_contract_synthesis
                        and selected_branch_reduction.progressed_branches
                    ):
                        selected_obligation_branches = (
                            selected_branch_reduction.progressed_branches
                        )
                        selected_demands = tuple(
                            dict.fromkeys(
                                atom
                                for branch in selected_obligation_branches
                                for atom in branch
                            )
                        )
                        selected_residual.update(
                            {
                                "persistent_branch_feedback_applied": True,
                                "persistent_branch_count": len(
                                    selected_obligation_branches
                                ),
                                "persistent_branch_matched_atoms": (
                                    selected_branch_reduction.matched_atom_count
                                ),
                                "persistent_branch_fully_closed": (
                                    selected_branch_reduction.fully_closed_branch_count
                                ),
                            }
                        )
                    active_native_facts = tuple(
                        Atom(predicate, points)
                        for predicate, points in yuclid_assertion_keys(
                            last_verification.payload
                        )
                    )
                    selected_residual["typed_plan_supported"] = (
                        chosen.key in typed_plan_supported_keys
                    )
                    selected_residual["progress_kind"] = (
                        "native_parent_obligation_closure"
                        if selected_residual.get("closed_parent_demands", 0)
                        else "provisional_typed_plan_native_replay_pending"
                        if chosen.key in typed_plan_supported_keys
                        else "direct_witness_branch_reduction"
                    )
                    if mmt_exact_enabled:
                        native_facts = tuple(
                            Atom(predicate, points)
                            for predicate, points in yuclid_assertion_keys(
                                last_verification.payload
                            )
                        )
                        exchange = coordinate_hageo_certificates(
                            native_facts,
                            goal_atoms,
                            rule_theorems,
                            initial_open_demands=tuple(selected_demands or ()),
                        )
                        # Keep the complete native state only inside the exact
                        # closure check.  The next search round receives the
                        # bounded goal-conditioned basis plus newly replayed
                        # facts; carrying thousands of unrelated native facts
                        # makes every proof-DAG task rescan the full closure.
                        for fact in exchange.accepted_facts:
                            canonical = fact.canonical()
                            if canonical not in exchanged_fact_keys:
                                exchanged_fact_keys.add(canonical)
                                active_proof_facts = (*active_proof_facts, canonical)
                        # MMT is a capability-preserving late specialist.  It
                        # may refine the next residual only when it actually
                        # proves a new shared fact; an empty exchange must not
                        # replace the native Newclid residual.
                        if exchange.made_goal_progress:
                            selected_demands = exchange.open_demands
                            selected_obligation_branches = tuple(
                                (item,) for item in selected_demands
                            )
                        selected_residual.update(
                            {
                                "mmt_solved": exchange.solved,
                                "mmt_replayed": exchange.replayed,
                                "mmt_derived_facts": len(exchange.derived_facts),
                                "mmt_carried_proof_facts": len(active_proof_facts),
                                "mmt_open_relation_demands": len(
                                    exchange.open_demands
                                ),
                                "mmt_residual_applied": bool(
                                    exchange.made_goal_progress
                                ),
                                "mmt_certificate_exchange": exchange.to_audit(),
                            }
                        )
                    steps = (*steps, chosen)
                    observed_relation_demands = tuple(selected_demands or ())
                    active_obligation_branches = tuple(
                        selected_obligation_branches or ()
                    )
                    if not last_verification.solved:
                        active_relation_demands = next_relation_demands(
                            active_relation_demands,
                            observed_relation_demands,
                            feedback_enabled=policy.residual_feedback,
                        )
                    if policy.residual_feedback and not last_verification.solved:
                        active_target_channels = {
                            atom.predicate.lower()
                            for atom in active_relation_demands
                        } or target_channels
                        active_reachable_channels = set(
                            backward_relation_distances(
                                rule_channels,
                                goal_channels=active_target_channels,
                            )
                        )
                        active_relation_distances = {
                            target: backward_relation_distances(
                                rule_channels,
                                goal_channels={target},
                            )
                            for target in active_target_channels
                        }
                        residual_feedback_applied = True
                else:
                    chosen = _rank_biased_choice(
                        base_pool if policy.terminal_credit_mix else pool,
                        rng=rng,
                        temperature=rank_temperature,
                    )
                    steps = (*steps, chosen)
                    current_problem = build_branch(
                        base_problem, steps, seed=attempt_seed
                    )
                    last_verification = None
                feedback_trace = [
                    {
                        "candidate": candidate.key,
                        "static_rank": index,
                        "selection_channel": shortlist_channel_by_key.get(
                            candidate.key, "residual_frontier"
                        ),
                        "matched_obligations": obligation_matches_by_candidate.get(
                            candidate.key, []
                        ),
                        "obligation_credit_verified": bool(
                            residual
                            and verified_obligation_credit(
                                selection_channel=shortlist_channel_by_key.get(
                                    candidate.key, "residual_frontier"
                                ),
                                matched_obligations=obligation_matches_by_candidate.get(
                                    candidate.key, ()
                                ),
                                residual=residual,
                            )
                        ),
                        "solved": bool(verification and verification.solved),
                        "proof_residual": residual,
                        "branch_reduction": (
                            {
                                "matched_atom_count": branch_reduction.matched_atom_count,
                                "progressed_branch_count": len(
                                    branch_reduction.progressed_branches
                                ),
                                "fully_closed_branch_count": (
                                    branch_reduction.fully_closed_branch_count
                                ),
                                "progressed_branches": [
                                    _relation_demand_trace(tuple(branch))
                                    for branch in branch_reduction.progressed_branches
                                ],
                            }
                            if branch_reduction is not None
                            else None
                        ),
                        "error": error,
                        "selected": candidate == chosen,
                    }
                    for (
                        index,
                        candidate,
                        _,
                        verification,
                        residual,
                        _,
                        _,
                        branch_reduction,
                        error,
                    ) in evaluations
                ]
            else:
                chosen = (
                    _rank_biased_choice(
                        pool,
                        rng=rng,
                        temperature=rank_temperature,
                    )
                    if structured_policy
                    else rng.choice(pool)
                )
                steps = (*steps, chosen)
                current_problem = (
                    extend_prefix_branch(
                        current_problem,
                        chosen,
                        steps,
                        seed=attempt_seed,
                    )
                    if incremental_prefix
                    else build_branch(base_problem, steps, seed=attempt_seed)
                )
                last_verification = None
            trajectory_relation_demands.append(tuple(relation_demands_in))
            incidence = audit["numerical_incidence"]
            sheaf = audit["candidate_alignment"].get("native_formal_sheaf")
            rounds_trace.append(
                {
                    "round": round_index + 1,
                    "candidate_extension_seconds": audit["elapsed_seconds"],
                    "enumerated": audit["relation_reachability"]["input_count"],
                    "incidence_checked": incidence["checked_candidates"],
                    "heuristic_candidates": incidence["heuristic_candidates"],
                    "typed_construction_contracts": audit[
                        "typed_construction_contracts"
                    ],
                    "eligible_pool": len(pool),
                    "ranked_candidates": [step.key for step in pool],
                    "terminal_credit_ranking": terminal_credit_ranking,
                    "obligation_credit_ranking": obligation_credit_ranking,
                    "shortlist_channels": shortlist_channels,
                    "chosen": chosen.key,
                    "relation_demands_in": _relation_demand_trace(
                        relation_demands_in
                    ),
                    "obligation_branches_in": [
                        _relation_demand_trace(tuple(branch))
                        for branch in obligation_branches_in
                    ],
                    "relation_demands_observed": _relation_demand_trace(
                        observed_relation_demands
                    ),
                    "relation_demands_next": _relation_demand_trace(
                        active_relation_demands
                    ),
                    "residual_feedback_applied": residual_feedback_applied,
                    "native_feedback": feedback_trace,
                    "coordination": (
                        {
                            "agents": len(sheaf["agents"]),
                            "consensus_agents": len(
                                sheaf["consensus_agent_ids"]
                            ),
                            "restriction_edges": sheaf["restriction_edge_count"],
                            "shared_candidates": sheaf["shared_candidate_count"],
                            "primal_residual": sheaf["primal_residual"],
                            "dual_residual": sheaf["dual_residual"],
                            "sheaf_residual": sheaf["sheaf_residual"],
                            "exchange_layer": sheaf["exchange_layer"],
                            "shared_channel_kinds": sheaf["shared_channel_kinds"],
                            "local_top_candidates": sheaf[
                                "local_top_candidates"
                            ],
                            "proof_dag_specialist": sheaf[
                                "proof_dag_specialist"
                            ],
                            "timing_seconds": sheaf["timing_seconds"],
                            "incidence_seconds": incidence[
                                "elapsed_seconds"
                            ],
                        }
                        if sheaf is not None
                        else None
                    ),
                }
            )
            if last_verification is not None and last_verification.solved:
                break

        result = last_verification
        if result is None:
            with verification_semaphore:
                result = verify_problem(
                    current_problem,
                    yuclid_exe=yuclid_exe,
                    ar_profile=ar_profile,
                )
            verification_calls += 1
        final_formulation = augment_formulation(base_formulation, steps)
        final_native_facts = tuple(
            Atom(predicate, points)
            for predicate, points in yuclid_assertion_keys(result.payload)
        )
        exact_lemma_exchange = (
            {"status": "native_already_solved", "solved": True, "lemmas": []}
            if result.solved
            else _run_exact_lemma_exchange(
                final_formulation,
                obligation_branches=active_obligation_branches,
                native_facts=final_native_facts,
                goal_atoms=goal_atoms,
                rule_theorems=rule_theorems,
                lemma_limit=exact_lemma_limit,
                timeout_seconds=exact_specialist_timeout_seconds,
                representation=exact_specialist_representation,
                max_saturation_rounds=exact_specialist_saturation_rounds,
                verification_semaphore=verification_semaphore,
            )
        )
        lemma_exchange_solved = bool(exact_lemma_exchange.get("solved"))
        gclc_lemma_exchange = (
            {"status": "native_already_solved", "solved": True, "lemmas": []}
            if result.solved
            else {"status": "skipped_after_exact_lemma_exchange", "solved": False, "lemmas": []}
            if lemma_exchange_solved
            else _run_gclc_lemma_exchange(
                final_formulation,
                obligation_branches=active_obligation_branches,
                native_facts=final_native_facts,
                goal_atoms=goal_atoms,
                rule_theorems=rule_theorems,
                lemma_limit=gclc_lemma_limit,
                gclc_exe=gclc_exe,
                methods=gclc_methods,
                timeout_seconds=gclc_timeout_seconds,
                verification_semaphore=verification_semaphore,
                incidence_samples=gclc_incidence_samples,
                wolfram_exe=wolfram_exe,
                wolfram_timeout_seconds=wolfram_timeout_seconds,
                wolfram_preprocessing=wolfram_preprocessing,
                wolfram_reduction_mode=wolfram_reduction_mode,
                wolfram_saturation_mode=wolfram_saturation_mode,
                wolfram_max_saturation_factors=wolfram_max_saturation_factors,
            )
        )
        gclc_lemma_solved = bool(gclc_lemma_exchange.get("solved"))
        gclc_specialist = (
            {"status": "native_already_solved"}
            if result.solved
            else {"status": "skipped_after_lemma_exchange"}
            if lemma_exchange_solved or gclc_lemma_solved
            else _run_gclc_specialist(
                final_formulation,
                gclc_exe=gclc_exe,
                methods=gclc_methods,
                timeout_seconds=gclc_timeout_seconds,
                verification_semaphore=verification_semaphore,
            )
        )
        gclc_solved = gclc_specialist.get("status") == "proved"
        exact_specialist = (
            {"status": "native_already_solved"}
            if result.solved
            else {"status": "skipped_after_prior_specialist"}
            if lemma_exchange_solved or gclc_lemma_solved or gclc_solved
            else _run_exact_specialist(
                final_formulation,
                timeout_seconds=exact_specialist_timeout_seconds,
                representation=exact_specialist_representation,
                max_saturation_rounds=exact_specialist_saturation_rounds,
                verification_semaphore=verification_semaphore,
                native_facts=final_native_facts,
                guidance_atoms=tuple(
                    dict.fromkeys(
                        atom
                        for branch in _ground_executable_obligation_branches(
                            active_obligation_branches
                        )
                        for atom in branch
                    )
                ),
                guidance_branches=_ground_executable_obligation_branches(
                    active_obligation_branches
                ),
            )
        )
        exact_solved = exact_specialist.get("status") == "proved"
        exact_relation_exchange = (
            {"status": "prior_specialist_solved", "solved": True, "atoms": []}
            if (
                result.solved
                or lemma_exchange_solved
                or gclc_lemma_solved
                or gclc_solved
                or exact_solved
            )
            else _run_reelaborated_relation_exchange(
                final_formulation,
                exact_result=exact_specialist,
                native_facts=final_native_facts,
                goal_atoms=goal_atoms,
                rule_theorems=rule_theorems,
                obligation_branches=active_obligation_branches,
            )
        )
        exact_relation_solved = bool(exact_relation_exchange.get("solved"))
        portfolio_solved = bool(
            result.solved
            or lemma_exchange_solved
            or gclc_lemma_solved
            or gclc_solved
            or exact_solved
            or exact_relation_solved
        )
        terminal_credit_events = assign_terminal_credit(
            steps,
            trajectory_relation_demands,
            solved=portfolio_solved,
            proof_payload=result.payload,
            native_certificate_replayed=bool(
                result.solved and result.proof_sha256
            ),
        )
        return {
            "attempt": attempt_index,
            "status": (
                "solved_native"
                if result.solved
                else "solved_exact_lemma_exchange"
                if lemma_exchange_solved
                else "solved_gclc_lemma_exchange"
                if gclc_lemma_solved
                else "solved_gclc_wu"
                if gclc_solved
                else "solved_exact_specialist"
                if exact_solved
                else "solved_polynomial_relation_exchange"
                if exact_relation_solved
                else "unsolved"
            ),
            "solved": portfolio_solved,
            "proof_source": (
                "yuclid_native"
                if result.solved
                else "jgex_exact_lemma_exchange"
                if lemma_exchange_solved
                else "gclc_typed_lemma_exchange"
                if gclc_lemma_solved
                else "gclc_wu"
                if gclc_solved
                else "jgex_exact_elimination"
                if exact_solved
                else "polynomial_relation_reelaboration"
                if exact_relation_solved
                else None
            ),
            "rounds_completed": len(steps),
            "path": [step.key for step in steps],
            "rounds": rounds_trace,
            "verification_calls": verification_calls,
            "all_deduction_count": result.all_deduction_count,
            "goal_deduction_count": result.goal_deduction_count,
            "closure_signatures": [
                item.to_dict() for item in result.closure_signatures
            ],
            "goal_signatures": [
                item.to_dict() for item in result.goal_signatures
            ],
            "typed_goal_signatures": [
                {
                    "predicate": atom.predicate,
                    "argument_sorts": list(
                        shared_argument_sorts(
                            atom.predicate,
                            len(atom.arguments),
                        )
                    ),
                    "arguments": list(atom.arguments),
                }
                for atom in goal_atoms
            ],
            "deduction_rule_counts": [
                {"rule": rule, "count": count}
                for rule, count in result.deduction_rule_counts
            ],
            "input_sha256": result.input_sha256,
            "proof_sha256": result.proof_sha256,
            "proof": result.payload if result.solved else None,
            "exact_specialist": exact_specialist,
            "exact_relation_exchange": exact_relation_exchange,
            "exact_lemma_exchange": exact_lemma_exchange,
            "gclc_lemma_exchange": gclc_lemma_exchange,
            "gclc_specialist": gclc_specialist,
            "terminal_credit_events": [
                event.to_dict() for event in terminal_credit_events
            ],
            "proof_residual": _proof_residual(
                result.payload,
                goal_atoms=goal_atoms,
                rule_theorems=rule_theorems,
            ),
            "final_relation_demands": _relation_demand_trace(
                active_relation_demands
            ),
            "final_obligation_branches": [
                _relation_demand_trace(tuple(branch))
                for branch in active_obligation_branches
            ],
            "elapsed_seconds": time.perf_counter() - started,
        }
    except Exception as exc:
        return {
            "attempt": attempt_index,
            "status": "execution_error",
            "solved": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "rounds_completed": len(steps),
            "path": [step.key for step in steps],
            "rounds": rounds_trace,
            "elapsed_seconds": time.perf_counter() - started,
        }


def _write_progress(output: Path, payload: dict[str, Any]) -> None:
    """Publish an atomic progress snapshot for UI and worker monitoring."""

    path = output.with_suffix(".progress.json")
    temporary = path.with_suffix(path.suffix + ".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _contains_right_censored_timeout(payload: Any) -> bool:
    """Detect an unfinished sound proof branch without interpreting its content."""

    if isinstance(payload, dict):
        if payload.get("status") == "right_censored_timeout":
            return True
        if payload.get("timed_out") is True:
            return True
        return any(_contains_right_censored_timeout(value) for value in payload.values())
    if isinstance(payload, (list, tuple)):
        return any(_contains_right_censored_timeout(value) for value in payload)
    return False


def _load_terminal_credit_ledger(path: Path) -> TerminalCreditLedger:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and payload.get("terminal_credit_ledger") is not None:
        payload = payload["terminal_credit_ledger"]
    if not isinstance(payload, dict):
        raise ValueError("terminal-credit input must contain a ledger object")
    return TerminalCreditLedger.from_dict(payload)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--problem-name", required=True)
    parser.add_argument("--yuclid-exe", type=Path, required=True)
    parser.add_argument("--runtime-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rounds", type=int, default=6)
    parser.add_argument("--attempts", type=int, default=64)
    parser.add_argument("--attempt-offset", type=int, default=0)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--per-family-limit", type=int, default=8)
    parser.add_argument("--incidence-oversample-per-family", type=int, default=32)
    parser.add_argument("--incidence-preselect-limit", type=int, default=0)
    parser.add_argument("--incidence-workers", type=int, default=1)
    parser.add_argument("--candidate-limit", type=int, default=0)
    parser.add_argument(
        "--candidate-policy",
        choices=(
            "random",
            "typed-sheaf",
            "mmt-sheaf",
            "mmt-hageo",
            "mmt-hageo-lite",
            "residual-static",
            "residual-feedback",
            "residual-portfolio",
            "terminal-credit",
            "terminal-credit-mixed",
            "obligation-credit-mixed",
            "contract-portfolio",
            "residual-construction",
        ),
        default="random",
    )
    parser.add_argument("--rank-temperature", type=float, default=2.0)
    parser.add_argument("--incremental-prefix", action="store_true")
    parser.add_argument("--feedback-candidates", type=int, default=0)
    parser.add_argument("--feedback-workers", type=int, default=1)
    parser.add_argument(
        "--max-verification-concurrency",
        type=int,
        default=0,
        help=(
            "Global Yuclid concurrency across all trajectories; zero uses "
            "--feedback-workers."
        ),
    )
    parser.add_argument(
        "--exact-specialist-timeout-seconds",
        type=float,
        default=0.0,
        help="Terminal JGEX exact-elimination budget per trajectory; zero disables it.",
    )
    parser.add_argument(
        "--formalgeo-timeout-seconds",
        type=float,
        default=0.0,
        help=(
            "Official FormalGeo backward-decomposition budget per goal; zero "
            "disables it. Returned obligations still require Newclid/GCLC replay."
        ),
    )
    parser.add_argument("--formalgeo-max-facts", type=int, default=12)
    parser.add_argument("--formalgeo-max-elaborations", type=int, default=2)
    parser.add_argument("--formalgeo-max-rounds", type=int, default=2)
    parser.add_argument("--formalgeo-seed-branches", type=int, default=4)
    parser.add_argument(
        "--exact-specialist-representation",
        choices=EXACT_SPECIALIST_REPRESENTATIONS,
        default="goal_local_relational",
    )
    parser.add_argument(
        "--exact-specialist-saturation-rounds",
        type=int,
        default=1,
    )
    parser.add_argument(
        "--exact-lemma-limit",
        type=int,
        default=0,
        help=(
            "Maximum ground residual obligations certified before terminal "
            "elimination; zero disables certificate exchange."
        ),
    )
    parser.add_argument("--gclc-exe", type=Path)
    parser.add_argument("--gclc-methods", type=_gclc_methods, default=("wu",))
    parser.add_argument(
        "--gclc-timeout-seconds",
        type=int,
        default=0,
        help="Terminal GCLC/Wu proof budget; zero disables it.",
    )
    parser.add_argument(
        "--gclc-lemma-limit",
        type=int,
        default=0,
        help=(
            "Maximum ground residual relations certified by GCLC before the "
            "terminal proof; zero disables typed certificate exchange."
        ),
    )
    parser.add_argument(
        "--gclc-incidence-samples",
        type=int,
        default=0,
        help=(
            "Independent deterministic numerical models required before a "
            "local GCLC obligation is attempted; zero disables the proposal gate."
        ),
    )
    parser.add_argument("--wolfram-exe", type=Path)
    parser.add_argument(
        "--wolfram-timeout-seconds",
        type=int,
        default=0,
        help=(
            "Wolfram extended-Groebner budget for a GCLC-censored typed local "
            "obligation; zero disables the certificate-search fallback."
        ),
    )
    parser.add_argument(
        "--wolfram-preprocessing",
        choices=("local_relational", "relational", "explicit"),
        default="local_relational",
    )
    parser.add_argument(
        "--wolfram-reduction-mode",
        choices=("direct", "extended_groebner"),
        default="extended_groebner",
    )
    parser.add_argument(
        "--wolfram-saturation-mode",
        choices=("none", "single", "cumulative"),
        default="none",
    )
    parser.add_argument("--wolfram-max-saturation-factors", type=int, default=12)
    parser.add_argument("--credit-ledger-input", type=Path)
    parser.add_argument("--freeze-credit-ledger", action="store_true")
    parser.add_argument("--ar-profile", choices=("ratio-only", "standard", "all"), default="all")
    args = parser.parse_args()
    if (
        args.rounds < 1
        or args.attempts < 1
        or args.rank_temperature < 0
        or args.incidence_workers < 1
        or args.incidence_preselect_limit < 0
        or args.feedback_candidates < 0
        or args.feedback_workers < 1
        or args.max_verification_concurrency < 0
        or args.formalgeo_timeout_seconds < 0
        or args.formalgeo_max_facts < 1
        or args.formalgeo_max_elaborations < 1
        or args.formalgeo_max_rounds < 1
        or args.formalgeo_seed_branches < 1
        or args.exact_specialist_timeout_seconds < 0
        or args.exact_specialist_saturation_rounds < 0
        or args.exact_lemma_limit < 0
        or args.gclc_timeout_seconds < 0
        or args.gclc_lemma_limit < 0
        or args.gclc_incidence_samples < 0
        or args.wolfram_timeout_seconds < 0
        or args.wolfram_max_saturation_factors < 0
    ):
        parser.error("--rounds and --attempts must be positive")
    if (
        args.candidate_policy
        in {
            "residual-static",
            "residual-feedback",
            "residual-portfolio",
            "terminal-credit",
            "terminal-credit-mixed",
            "obligation-credit-mixed",
            "contract-portfolio",
            "residual-construction",
        }
        and args.feedback_candidates < 1
    ):
        parser.error("residual policies require --feedback-candidates >= 1")
    policy_spec = candidate_policy_spec(args.candidate_policy)
    if args.credit_ledger_input and not policy_spec.terminal_credit:
        parser.error("--credit-ledger-input requires a terminal-credit policy")
    if args.freeze_credit_ledger and not args.credit_ledger_input:
        parser.error("--freeze-credit-ledger requires --credit-ledger-input")
    if policy_spec.terminal_credit_mix and args.feedback_candidates < 2:
        parser.error("mixed terminal-credit policies require --feedback-candidates >= 2")

    credit_ledger = (
        _load_terminal_credit_ledger(args.credit_ledger_input.resolve())
        if args.credit_ledger_input
        else TerminalCreditLedger()
    )
    credit_input_sha256 = (
        hashlib.sha256(args.credit_ledger_input.resolve().read_bytes()).hexdigest()
        if args.credit_ledger_input
        else None
    )

    started = time.perf_counter()

    def publish_stage(stage: str, **details: Any) -> None:
        _write_progress(
            args.output,
            {
                "status": "running",
                "problem_name": args.problem_name,
                "phase": "baseline_portfolio",
                "stage": stage,
                "completed_attempts": 0,
                "total_attempts": args.attempts,
                "elapsed_seconds": time.perf_counter() - started,
                **details,
            },
        )

    formulations = jgex_formulation_from_txt_file(args.dataset.resolve())
    raw = formulations[args.problem_name]
    raw = JGEXFormulation(
        name=raw.name,
        setup_clauses=raw.setup_clauses,
        auxiliary_clauses=(),
        goals=raw.goals,
    )
    builder = JGEXProblemBuilder(np.random.default_rng(args.seed))
    formulation, normalization = normalize_legacy_formulation(raw, builder.jgex_defs)
    base_problem = builder.with_problem(formulation).include_auxiliary_clauses(False).build()
    baseline = verify_problem(
        base_problem,
        yuclid_exe=args.yuclid_exe.resolve(),
        ar_profile=args.ar_profile,
    )
    publish_stage("native_verifier_complete", solved=bool(baseline.solved))
    verification_semaphore = BoundedSemaphore(
        args.max_verification_concurrency or args.feedback_workers
    )
    baseline_gclc: dict[str, Any] = {"status": "pending"}
    baseline_gclc_lemma_exchange: dict[str, Any] = {
        "status": "pending",
        "solved": False,
        "lemmas": [],
    }
    baseline_portfolio_solved = bool(baseline.solved)
    base_points, base_graph, base_role_graph, base_role_weights, goal_multiplicity = (
        formulation_structure(formulation)
    )
    goal_atoms = formulation_goal_atoms(formulation)
    rules = native_rule_theorems()
    baseline_facts = tuple(
        Atom(predicate, points)
        for predicate, points in yuclid_assertion_keys(baseline.payload)
    )
    baseline_mmt_exchange = None
    if candidate_policy_spec(args.candidate_policy).alignment_mode == "mmt-theory-view":
        baseline_obligations, native_relation_demands = proof_state_obligations(
            baseline.payload,
            goal_atoms,
            rules,
        )
        baseline_mmt_exchange = coordinate_hageo_certificates(
            baseline_facts,
            goal_atoms,
            rules,
            initial_open_demands=native_relation_demands,
        )
        baseline_facts = baseline_mmt_exchange.accepted_facts
        relation_demands = baseline_mmt_exchange.open_demands
        relation_obligation_branches = tuple(
            (item,) for item in relation_demands
        )
    else:
        baseline_obligations, relation_demands = proof_state_obligations(
            baseline.payload,
            goal_atoms,
            rules,
        )
        relation_obligation_branches = tuple(
            tuple(obligation.open_premises)
            for obligation in baseline_obligations
            if obligation.open_premises
        )
    initial_policy = candidate_policy_spec(args.candidate_policy)
    if (
        initial_policy.typed_contract_synthesis
        and not initial_policy.ground_residual_synthesis
    ):
        base_demand_keys = {
            item.canonical() for item in relation_demands
        }
        relation_demands = _typed_contract_frontier(
            baseline_facts,
            goal_atoms,
            rules,
            base_demands=relation_demands,
        )
        relation_obligation_branches = (
            *relation_obligation_branches,
            *(
                (item,)
                for item in relation_demands
                if item.canonical() not in base_demand_keys
            ),
        )
    baseline_formalgeo_exchanges: list[dict[str, Any]] = []
    if not baseline.solved and args.formalgeo_timeout_seconds > 0:
        formalgeo_config = FormalGeoRuntimeConfig.detect(
            timeout_seconds=args.formalgeo_timeout_seconds
        )
        formalgeo_branches: list[tuple[Atom, ...]] = []
        for goal in goal_atoms:
            try:
                translation = translate_jgex_to_formalgeo(formulation, goal)
            except FormalGeoElaborationError as exc:
                # The local typed-fact chart is a conservative fallback for a
                # JGEX constructor not yet covered by the full DAG translator.
                exchange = run_formalgeo_goal_exchange(
                    baseline_facts,
                    goal,
                    max_facts=args.formalgeo_max_facts,
                    max_elaborations=args.formalgeo_max_elaborations,
                    max_rounds=args.formalgeo_max_rounds,
                    config=formalgeo_config,
                )
                exchange_audit = exchange.to_dict()
                exchange_audit.update(
                    {
                        "mode": "typed_fact_chart_fallback",
                        "full_jgex_error": str(exc),
                    }
                )
                baseline_formalgeo_exchanges.append(exchange_audit)
                formalgeo_branches.extend(exchange.obligation_branches)
                continue

            result = run_formalgeo_bridge(
                (),
                goal,
                max_rounds=args.formalgeo_max_rounds,
                config=formalgeo_config,
                seed_offsets=tuple(
                    100 * index for index in range(args.formalgeo_seed_branches)
                ),
                elaboration_override=translation.elaboration,
            )
            baseline_formalgeo_exchanges.append(
                {
                    "mode": "full_jgex_construction_dag",
                    "translation": translation.to_dict(),
                    "runtime": result.to_dict(),
                    "official_solved": result.root_solved,
                    "accepted_as_mortra_solution": False,
                    "acceptance_rule": (
                        "official FormalGeo proof is recorded; MORTRA score "
                        "still requires Newclid/GCLC certificate replay"
                    ),
                }
            )
            formalgeo_branches.extend(result.open_branches)
        if formalgeo_branches:
            relation_obligation_branches = tuple(
                dict.fromkeys((*relation_obligation_branches, *formalgeo_branches))
            )
            relation_demands = tuple(
                dict.fromkeys(
                    (
                        *relation_demands,
                        *(
                            atom
                            for branch in formalgeo_branches
                            for atom in branch
                        ),
                    )
                )
            )
    publish_stage(
        "formalgeo_exchange_complete",
        exchange_count=len(baseline_formalgeo_exchanges),
    )
    baseline_exact_lemma_exchange = (
        {"status": "native_already_solved", "solved": True, "lemmas": []}
        if baseline.solved
        else _run_exact_lemma_exchange(
            formulation,
            obligation_branches=relation_obligation_branches,
            native_facts=baseline_facts,
            goal_atoms=goal_atoms,
            rule_theorems=rules,
            lemma_limit=args.exact_lemma_limit,
            timeout_seconds=args.exact_specialist_timeout_seconds,
            representation=args.exact_specialist_representation,
            max_saturation_rounds=args.exact_specialist_saturation_rounds,
            verification_semaphore=verification_semaphore,
        )
    )
    baseline_exact_lemma_solved = bool(
        baseline_exact_lemma_exchange.get("solved")
    )
    publish_stage(
        "exact_lemma_exchange_complete",
        result_status=baseline_exact_lemma_exchange.get("status"),
        solved=baseline_exact_lemma_solved,
    )
    baseline_gclc_lemma_exchange = (
        {"status": "native_already_solved", "solved": True, "lemmas": []}
        if baseline.solved
        else {"status": "skipped_after_exact_lemma_exchange", "solved": False, "lemmas": []}
        if baseline_exact_lemma_solved
        else _run_gclc_lemma_exchange(
            formulation,
            obligation_branches=relation_obligation_branches,
            native_facts=baseline_facts,
            goal_atoms=goal_atoms,
            rule_theorems=rules,
            lemma_limit=args.gclc_lemma_limit,
            gclc_exe=args.gclc_exe.resolve() if args.gclc_exe else None,
            methods=args.gclc_methods,
            timeout_seconds=args.gclc_timeout_seconds,
            verification_semaphore=verification_semaphore,
            incidence_samples=args.gclc_incidence_samples,
            wolfram_exe=args.wolfram_exe.resolve() if args.wolfram_exe else None,
            wolfram_timeout_seconds=args.wolfram_timeout_seconds,
            wolfram_preprocessing=args.wolfram_preprocessing,
            wolfram_reduction_mode=args.wolfram_reduction_mode,
            wolfram_saturation_mode=args.wolfram_saturation_mode,
            wolfram_max_saturation_factors=args.wolfram_max_saturation_factors,
        )
    )
    baseline_gclc_lemma_solved = bool(
        baseline_gclc_lemma_exchange.get("solved")
    )
    publish_stage(
        "gclc_lemma_exchange_complete",
        result_status=baseline_gclc_lemma_exchange.get("status"),
        solved=baseline_gclc_lemma_solved,
    )
    baseline_gclc = (
        {"status": "native_already_solved"}
        if baseline.solved
        else {"status": "skipped_after_exact_lemma_exchange"}
        if baseline_exact_lemma_solved
        else {"status": "skipped_after_lemma_exchange"}
        if baseline_gclc_lemma_solved
        else _run_gclc_specialist(
            formulation,
            gclc_exe=args.gclc_exe.resolve() if args.gclc_exe else None,
            methods=args.gclc_methods,
            timeout_seconds=args.gclc_timeout_seconds,
            verification_semaphore=verification_semaphore,
        )
    )
    publish_stage(
        "gclc_terminal_complete",
        result_status=baseline_gclc.get("status"),
        solved=baseline_gclc.get("status") == "proved",
    )
    baseline_exact_specialist = (
        {"status": "prior_specialist_solved"}
        if (
            baseline.solved
            or baseline_exact_lemma_solved
            or baseline_gclc_lemma_solved
            or baseline_gclc.get("status") == "proved"
        )
        else _run_exact_specialist(
            formulation,
            timeout_seconds=args.exact_specialist_timeout_seconds,
            representation=args.exact_specialist_representation,
            max_saturation_rounds=args.exact_specialist_saturation_rounds,
            verification_semaphore=verification_semaphore,
            native_facts=baseline_facts,
            guidance_atoms=tuple(
                dict.fromkeys(
                    atom
                    for branch in _ground_executable_obligation_branches(
                        relation_obligation_branches
                    )
                    for atom in branch
                )
            ),
            guidance_branches=_ground_executable_obligation_branches(
                relation_obligation_branches
            ),
        )
    )
    baseline_exact_solved = baseline_exact_specialist.get("status") == "proved"
    publish_stage(
        "exact_terminal_complete",
        result_status=baseline_exact_specialist.get("status"),
        solved=baseline_exact_solved,
    )
    baseline_exact_relation_exchange = (
        {"status": "prior_specialist_solved", "solved": True, "atoms": []}
        if (
            baseline.solved
            or baseline_exact_lemma_solved
            or baseline_gclc_lemma_solved
            or baseline_gclc.get("status") == "proved"
            or baseline_exact_solved
        )
        else _run_reelaborated_relation_exchange(
            formulation,
            exact_result=baseline_exact_specialist,
            native_facts=baseline_facts,
            goal_atoms=goal_atoms,
            rule_theorems=rules,
            obligation_branches=relation_obligation_branches,
        )
    )
    baseline_exact_relation_solved = bool(
        baseline_exact_relation_exchange.get("solved")
    )
    publish_stage(
        "relation_reelaboration_complete",
        result_status=baseline_exact_relation_exchange.get("status"),
        solved=baseline_exact_relation_solved,
    )
    baseline_portfolio_solved = bool(
        baseline.solved
        or baseline_exact_lemma_solved
        or baseline_gclc_lemma_solved
        or baseline_gclc.get("status") == "proved"
        or baseline_exact_solved
        or baseline_exact_relation_solved
    )
    goal_support = set(goal_multiplicity)
    proof_relevance = proof_hypergraph_relevance(baseline.payload, goal_support)
    target_channels = {atom.predicate.lower() for atom in relation_demands} or _goal_channels(formulation)
    rule_channels = [
        ([premise.name for premise in rule.premises], [conclusion.name for conclusion in rule.conclusions])
        for rule in DEFAULT_RULES
    ]
    reachable_channels = set(
        backward_relation_distances(rule_channels, goal_channels=target_channels)
    )
    relation_distances = {
        target: backward_relation_distances(
            rule_channels,
            goal_channels={target},
        )
        for target in target_channels
    }

    attempts: list[dict[str, Any]] = []
    if not baseline_portfolio_solved:
        kwargs = {
            "seed": args.seed,
            "rounds": args.rounds,
            "base_formulation": formulation,
            "base_problem": base_problem,
            "base_points": base_points,
            "base_graph": base_graph,
            "base_role_graph": base_role_graph,
            "base_role_weights": base_role_weights,
            "goal_multiplicity": goal_multiplicity,
            "proof_relevance": proof_relevance,
            "relation_demands": relation_demands,
            "relation_obligation_branches": relation_obligation_branches,
            "reachable_channels": reachable_channels,
            "target_channels": target_channels,
            "relation_distances": relation_distances,
            "goal_atoms": goal_atoms,
            "baseline_facts": baseline_facts,
            "rule_theorems": rules,
            "per_family_limit": args.per_family_limit,
            "incidence_oversample_per_family": args.incidence_oversample_per_family,
            "incidence_preselect_limit": args.incidence_preselect_limit,
            "incidence_workers": args.incidence_workers,
            "candidate_limit": args.candidate_limit,
            "yuclid_exe": args.yuclid_exe.resolve(),
            "ar_profile": args.ar_profile,
            "candidate_policy": args.candidate_policy,
            "rank_temperature": args.rank_temperature,
            "incremental_prefix": args.incremental_prefix,
            "feedback_candidates": args.feedback_candidates,
            "feedback_workers": args.feedback_workers,
            "trajectory_credit_scores": {},
            "verification_semaphore": verification_semaphore,
            "exact_specialist_timeout_seconds": (
                args.exact_specialist_timeout_seconds
            ),
            "exact_specialist_representation": (
                args.exact_specialist_representation
            ),
            "exact_specialist_saturation_rounds": (
                args.exact_specialist_saturation_rounds
            ),
            "exact_lemma_limit": args.exact_lemma_limit,
            "gclc_exe": args.gclc_exe.resolve() if args.gclc_exe else None,
            "gclc_methods": args.gclc_methods,
            "gclc_timeout_seconds": args.gclc_timeout_seconds,
            "gclc_lemma_limit": args.gclc_lemma_limit,
            "gclc_incidence_samples": args.gclc_incidence_samples,
            "wolfram_exe": (
                args.wolfram_exe.resolve() if args.wolfram_exe else None
            ),
            "wolfram_timeout_seconds": args.wolfram_timeout_seconds,
            "wolfram_preprocessing": args.wolfram_preprocessing,
            "wolfram_reduction_mode": args.wolfram_reduction_mode,
            "wolfram_saturation_mode": args.wolfram_saturation_mode,
            "wolfram_max_saturation_factors": args.wolfram_max_saturation_factors,
        }
        def publish_result(result: dict[str, Any]) -> None:
            attempts.append(result)
            _write_progress(
                args.output,
                {
                    "status": "running",
                    "problem_name": args.problem_name,
                    "completed_attempts": len(attempts),
                    "total_attempts": args.attempts,
                    "solved_attempts": sum(item["solved"] for item in attempts),
                    "latest_attempt": result["attempt"],
                    "latest_status": result["status"],
                    "terminal_credit_signatures": len(credit_ledger.scores()),
                    "elapsed_seconds": time.perf_counter() - started,
                },
            )

        attempt_indices = list(
            range(args.attempt_offset, args.attempt_offset + args.attempts)
        )
        if candidate_policy_spec(args.candidate_policy).terminal_credit:
            # Credit learned in one wave is visible to the next wave.  Results
            # are folded into the ledger by attempt index, so worker timing
            # cannot change the experiment.
            wave_size = max(1, args.workers)
            for start in range(0, len(attempt_indices), wave_size):
                wave = attempt_indices[start : start + wave_size]
                wave_kwargs = {
                    **kwargs,
                    "trajectory_credit_scores": credit_ledger.scores(),
                }
                with ThreadPoolExecutor(max_workers=wave_size) as executor:
                    futures = {
                        executor.submit(
                            _attempt, attempt_index=index, **wave_kwargs
                        ): index
                        for index in wave
                    }
                    wave_results = [
                        future.result() for future in as_completed(futures)
                    ]
                for result in sorted(
                    wave_results, key=lambda item: item["attempt"]
                ):
                    if not args.freeze_credit_ledger:
                        credit_ledger.observe(
                            TerminalCreditEvent.from_dict(event)
                            for event in result.get("terminal_credit_events", ())
                        )
                    publish_result(result)
        else:
            with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
                futures = {
                    executor.submit(_attempt, attempt_index=index, **kwargs): index
                    for index in attempt_indices
                }
                for future in as_completed(futures):
                    publish_result(future.result())
        attempts.sort(key=lambda item: item["attempt"])
    solved_attempts = [item for item in attempts if item["solved"]]
    first_solved = solved_attempts[0] if solved_attempts else None
    solved = baseline_portfolio_solved or bool(solved_attempts)
    right_censored_sources = {
        "baseline_formalgeo_exchange": _contains_right_censored_timeout(
            baseline_formalgeo_exchanges
        ),
        "baseline_exact_lemma_exchange": _contains_right_censored_timeout(
            baseline_exact_lemma_exchange
        ),
        "baseline_gclc_lemma_exchange": _contains_right_censored_timeout(
            baseline_gclc_lemma_exchange
        ),
        "baseline_gclc_specialist": _contains_right_censored_timeout(baseline_gclc),
        "baseline_exact_specialist": _contains_right_censored_timeout(
            baseline_exact_specialist
        ),
        "search_attempts": _contains_right_censored_timeout(attempts),
    }
    artifact = {
        "experiment": "hageo_independent_n_round_pass_at_k_no_llm",
        "artifact_schema_version": 2,
        "reproducibility": _reproducibility_manifest(
            dataset=args.dataset,
            yuclid_exe=args.yuclid_exe,
            runtime_path=args.runtime_path,
            gclc_exe=args.gclc_exe,
            wolfram_exe=args.wolfram_exe,
        ),
        "protocol": {
            "uses_external_llm": False,
            "uses_dataset_auxiliary_clauses": False,
            "uses_problem_id_in_search": False,
            "uses_expected_answer": False,
            "trajectory_policy": (
                "hageo_incidence_gate_then_mmt_theory_view_ranking"
                if args.candidate_policy in {"mmt-hageo", "mmt-hageo-lite"}
                else "mmt_theory_view_ranked_stratified_trajectories"
                if args.candidate_policy == "mmt-sheaf"
                else "typed_obligation_ranked_stratified_trajectories"
                if args.candidate_policy == "typed-sheaf"
                else "typed_atom_static_residual_native_feedback"
                if args.candidate_policy == "residual-static"
                else "typed_atom_closed_loop_residual_native_feedback"
                if args.candidate_policy == "residual-feedback"
                else "typed_atom_open_incidence_residual_portfolio"
                if args.candidate_policy == "residual-portfolio"
                else "typed_atom_terminal_certificate_credit"
                if args.candidate_policy == "terminal-credit"
                else "typed_atom_one_credit_plus_residual_portfolio"
                if args.candidate_policy == "terminal-credit-mixed"
                else "typed_atom_obligation_unification_verified_credit_portfolio"
                if args.candidate_policy == "obligation-credit-mixed"
                else "typed_contract_reverse_unification_residual_portfolio"
                if args.candidate_policy == "contract-portfolio"
                else "typed_residual_bidirectional_construction_synthesis"
                if args.candidate_policy == "residual-construction"
                else "independent_seeded_numerical_incidence_sampling"
            ),
            "ddAR_calls": (
                "baseline_plus_native_shortlist_feedback_with_terminal_reuse"
                if args.feedback_candidates
                else "baseline_plus_one_terminal_call_per_complete_attempt"
            ),
            "rounds_n": args.rounds,
            "attempts_k": args.attempts,
            "attempt_offset": args.attempt_offset,
            "workers": args.workers,
            "seed": args.seed,
            "per_family_limit": args.per_family_limit,
            "incidence_oversample_per_family": args.incidence_oversample_per_family,
            "incidence_preselect_limit": args.incidence_preselect_limit,
            "incidence_workers": args.incidence_workers,
            "candidate_limit": args.candidate_limit,
            "candidate_policy": args.candidate_policy,
            "rank_temperature": args.rank_temperature,
            "incremental_prefix": args.incremental_prefix,
            "feedback_candidates": args.feedback_candidates,
            "feedback_workers": args.feedback_workers,
            "max_verification_concurrency": (
                args.max_verification_concurrency or args.feedback_workers
            ),
            "exact_specialist_timeout_seconds": (
                args.exact_specialist_timeout_seconds
            ),
            "formalgeo_timeout_seconds": args.formalgeo_timeout_seconds,
            "formalgeo_max_facts": args.formalgeo_max_facts,
            "formalgeo_max_elaborations": args.formalgeo_max_elaborations,
            "formalgeo_max_rounds": args.formalgeo_max_rounds,
            "formalgeo_seed_branches": args.formalgeo_seed_branches,
            "exact_specialist_representation": (
                args.exact_specialist_representation
            ),
            "exact_specialist_saturation_rounds": (
                args.exact_specialist_saturation_rounds
            ),
            "exact_lemma_limit": args.exact_lemma_limit,
            "gclc_exe": (
                args.gclc_exe.resolve().as_posix() if args.gclc_exe else None
            ),
            "gclc_timeout_seconds": args.gclc_timeout_seconds,
            "gclc_methods": args.gclc_methods,
            "gclc_lemma_limit": args.gclc_lemma_limit,
            "gclc_incidence_samples": args.gclc_incidence_samples,
            "wolfram_exe": (
                args.wolfram_exe.resolve().as_posix() if args.wolfram_exe else None
            ),
            "wolfram_timeout_seconds": args.wolfram_timeout_seconds,
            "wolfram_preprocessing": args.wolfram_preprocessing,
            "wolfram_reduction_mode": args.wolfram_reduction_mode,
            "wolfram_saturation_mode": args.wolfram_saturation_mode,
            "wolfram_max_saturation_factors": args.wolfram_max_saturation_factors,
            "ar_profile": args.ar_profile,
            "proof_dag_specialist_budget": PROOF_DAG_STAGE_ONE,
            "truth_plane": (
                "native_or_typed_exchange_or_gclc_or_replayed_wolfram_cofactor_or_terminal_exact_replay"
                if args.exact_specialist_timeout_seconds > 0
                or args.gclc_timeout_seconds > 0
                or args.wolfram_timeout_seconds > 0
                else "yuclid_native_certificate_replay_only"
            ),
            "terminal_credit_control_only": bool(
                candidate_policy_spec(args.candidate_policy).terminal_credit
            ),
            "terminal_credit_ledger_input": (
                args.credit_ledger_input.resolve().as_posix()
                if args.credit_ledger_input
                else None
            ),
            "terminal_credit_ledger_input_sha256": credit_input_sha256,
            "terminal_credit_ledger_frozen": bool(args.freeze_credit_ledger),
        },
        "problem_name": args.problem_name,
        "normalization": asdict(normalization),
        "baseline_solved": baseline.solved,
        "baseline_portfolio_solved": baseline_portfolio_solved,
        "baseline_formalgeo_exchange": baseline_formalgeo_exchanges,
        "baseline_exact_lemma_exchange": baseline_exact_lemma_exchange,
        "baseline_gclc_lemma_exchange": baseline_gclc_lemma_exchange,
        "baseline_gclc_specialist": baseline_gclc,
        "baseline_exact_specialist": baseline_exact_specialist,
        "baseline_exact_relation_exchange": baseline_exact_relation_exchange,
        "baseline_proof_residual": _proof_residual(
            baseline.payload,
            goal_atoms=goal_atoms,
            rule_theorems=rules,
        ),
        "mmt_exact_coordination": (
            baseline_mmt_exchange.to_audit()
            if baseline_mmt_exchange is not None
            else None
        ),
        "solved": solved,
        "pass_at_k": solved,
        "right_censored": not solved and any(right_censored_sources.values()),
        "right_censored_sources": right_censored_sources,
        "first_solved_attempt": first_solved["attempt"] if first_solved else None,
        "unique_paths": len({tuple(item["path"]) for item in attempts}),
        "completed_attempts": sum(item["rounds_completed"] == args.rounds for item in attempts),
        "execution_errors": sum(item["status"] == "execution_error" for item in attempts),
        "elapsed_seconds": time.perf_counter() - started,
        "attempt_results": attempts,
        "terminal_credit_ledger": (
            credit_ledger.to_dict()
            if candidate_policy_spec(args.candidate_policy).terminal_credit
            else None
        ),
    }
    if baseline.solved or (
        first_solved is not None
        and first_solved.get("proof_source") == "yuclid_native"
    ):
        proof_path = args.output.with_suffix(".proof.json")
        proof_path.parent.mkdir(parents=True, exist_ok=True)
        proof_payload = (
            baseline.payload if baseline.solved else first_solved["proof"]
        )
        input_sha256 = (
            baseline.input_sha256 if baseline.solved else first_solved["input_sha256"]
        )
        proof_sha256 = (
            baseline.proof_sha256 if baseline.solved else first_solved["proof_sha256"]
        )
        proof_path.write_text(
            json.dumps(proof_payload, indent=2) + "\n",
            encoding="utf-8",
        )
        artifact["certificate"] = {
            "source": "baseline" if baseline.solved else "search_attempt",
            "input_sha256": input_sha256,
            "proof_sha256": proof_sha256,
            "proof_path": proof_path.resolve().relative_to(ROOT).as_posix(),
            "proof_file_sha256": hashlib.sha256(proof_path.read_bytes()).hexdigest(),
        }
    elif baseline_exact_lemma_solved:
        artifact["certificate"] = _write_lemma_exchange_certificate(
            args.output,
            baseline_exact_lemma_exchange,
            suffix=".exact-exchange.json",
            source="baseline_exact_typed_lemma_exchange",
        )
        baseline_exact_lemma_exchange["certificate_path"] = artifact[
            "certificate"
        ]["proof_path"]
        for lemma in baseline_exact_lemma_exchange["lemmas"]:
            lemma.pop("certificate", None)
    elif baseline_gclc_lemma_solved:
        artifact["certificate"] = _write_lemma_exchange_certificate(
            args.output,
            baseline_gclc_lemma_exchange,
            suffix=".gclc-exchange.json",
            source="baseline_gclc_typed_lemma_exchange",
        )
        baseline_gclc_lemma_exchange["certificate_path"] = artifact[
            "certificate"
        ]["proof_path"]
        for lemma in baseline_gclc_lemma_exchange["lemmas"]:
            lemma.pop("proof_text", None)
    elif baseline_gclc.get("status") == "proved":
        proof_text = baseline_gclc.pop("proof_text")
        proof_path = args.output.with_suffix(".gclc-proof.tex")
        metadata_path = args.output.with_suffix(".gclc.json")
        proof_path.parent.mkdir(parents=True, exist_ok=True)
        proof_path.write_text(proof_text, encoding="utf-8")
        metadata_path.write_text(
            json.dumps(baseline_gclc, indent=2) + "\n",
            encoding="utf-8",
        )
        artifact["certificate"] = {
            "source": f"baseline_gclc_{baseline_gclc['selected_method']}",
            "input_sha256": baseline_gclc["input_sha256"],
            "proof_sha256": baseline_gclc["run"]["proof_sha256"],
            "proof_path": proof_path.resolve().relative_to(ROOT).as_posix(),
            "proof_file_sha256": hashlib.sha256(
                proof_path.read_bytes()
            ).hexdigest(),
            "metadata_path": metadata_path.resolve().relative_to(ROOT).as_posix(),
        }
        baseline_gclc["certificate_path"] = artifact["certificate"][
            "proof_path"
        ]
    elif (
        first_solved is not None
        and first_solved.get("proof_source") == "jgex_exact_lemma_exchange"
    ):
        exchange_payload = first_solved["exact_lemma_exchange"]
        exchange_path = args.output.with_suffix(".exchange.json")
        exchange_path.parent.mkdir(parents=True, exist_ok=True)
        exchange_path.write_text(
            json.dumps(exchange_payload, indent=2) + "\n",
            encoding="utf-8",
        )
        certificate_hashes = sorted(
            str(item["certificate_sha256"])
            for item in exchange_payload["lemmas"]
            if item.get("certificate_sha256")
        )
        exchange_proof_sha256 = hashlib.sha256(
            json.dumps(
                {
                    "lemma_certificate_sha256": certificate_hashes,
                    "hypergraph_proofs": exchange_payload["hypergraph_proofs"],
                },
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        artifact["certificate"] = {
            "source": "jgex_exact_lemma_exchange",
            "proof_sha256": exchange_proof_sha256,
            "proof_path": exchange_path.resolve().relative_to(ROOT).as_posix(),
            "proof_file_sha256": hashlib.sha256(
                exchange_path.read_bytes()
            ).hexdigest(),
        }
        first_solved["exact_lemma_exchange"]["certificate_path"] = artifact[
            "certificate"
        ]["proof_path"]
        for lemma in first_solved["exact_lemma_exchange"]["lemmas"]:
            lemma.pop("certificate", None)
    elif (
        first_solved is not None
        and first_solved.get("proof_source") == "gclc_typed_lemma_exchange"
    ):
        exchange_payload = first_solved["gclc_lemma_exchange"]
        artifact["certificate"] = _write_lemma_exchange_certificate(
            args.output,
            exchange_payload,
            suffix=".gclc-exchange.json",
            source="gclc_typed_lemma_exchange",
        )
        first_solved["gclc_lemma_exchange"]["certificate_path"] = artifact[
            "certificate"
        ]["proof_path"]
        for lemma in first_solved["gclc_lemma_exchange"]["lemmas"]:
            lemma.pop("proof_text", None)
    elif (
        first_solved is not None
        and first_solved.get("proof_source") == "gclc_wu"
    ):
        gclc_payload = first_solved["gclc_specialist"]
        proof_text = gclc_payload.pop("proof_text")
        proof_path = args.output.with_suffix(".gclc-proof.tex")
        metadata_path = args.output.with_suffix(".gclc.json")
        proof_path.parent.mkdir(parents=True, exist_ok=True)
        proof_path.write_text(proof_text, encoding="utf-8")
        metadata_path.write_text(
            json.dumps(gclc_payload, indent=2) + "\n",
            encoding="utf-8",
        )
        artifact["certificate"] = {
            "source": "gclc_wu",
            "input_sha256": gclc_payload["input_sha256"],
            "proof_sha256": gclc_payload["run"]["proof_sha256"],
            "proof_path": proof_path.resolve().relative_to(ROOT).as_posix(),
            "proof_file_sha256": hashlib.sha256(
                proof_path.read_bytes()
            ).hexdigest(),
            "metadata_path": metadata_path.resolve().relative_to(ROOT).as_posix(),
        }
        first_solved["gclc_specialist"]["certificate_path"] = artifact[
            "certificate"
        ]["proof_path"]
    elif first_solved is not None:
        exact_payload = first_solved["exact_specialist"]["certificate"]
        exact_path = args.output.with_suffix(".exact.json")
        exact_path.parent.mkdir(parents=True, exist_ok=True)
        exact_path.write_text(
            json.dumps(exact_payload, indent=2) + "\n",
            encoding="utf-8",
        )
        artifact["certificate"] = {
            "source": "jgex_exact_elimination",
            "input_sha256": first_solved["exact_specialist"]["input_sha256"],
            "proof_sha256": exact_payload["certificate_sha256"],
            "proof_path": exact_path.resolve().relative_to(ROOT).as_posix(),
            "proof_file_sha256": hashlib.sha256(exact_path.read_bytes()).hexdigest(),
        }
        first_solved["exact_specialist"]["certificate_path"] = artifact[
            "certificate"
        ]["proof_path"]
        first_solved["exact_specialist"].pop("certificate", None)
    for item in attempts:
        item.pop("proof", None)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    _write_progress(
        args.output,
        {
            "status": "completed",
            "problem_name": args.problem_name,
            "completed_attempts": len(attempts),
            "total_attempts": args.attempts,
            "solved_attempts": len(solved_attempts),
            "solved": artifact["solved"],
            "artifact": args.output.resolve().relative_to(ROOT).as_posix(),
            "elapsed_seconds": artifact["elapsed_seconds"],
        },
    )
    print(
        json.dumps(
            {
                "problem": args.problem_name,
                "rounds": args.rounds,
                "attempts": args.attempts,
                "solved": artifact["solved"],
                "unique_paths": artifact["unique_paths"],
                "elapsed_seconds": artifact["elapsed_seconds"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
