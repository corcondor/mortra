"""Dynamic multi-family typed construction search for Newclid obligations.

Dataset auxiliary clauses are removed before search.  Candidate terms are
enumerated from a fixed typed grammar and ranked by graph distance to the goal
support.  Exact Yuclid closure growth supplies the CEGIS/beam feedback.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _bootstrap_runtime() -> object | None:
    if "--yuclid-exe" in sys.argv:
        index = sys.argv.index("--yuclid-exe")
        yuclid_dir = str(Path(sys.argv[index + 1]).resolve().parent)
        os.environ["PATH"] = yuclid_dir + os.pathsep + os.environ.get("PATH", "")
    if "--runtime-path" not in sys.argv:
        return None
    index = sys.argv.index("--runtime-path")
    runtime_path = str(Path(sys.argv[index + 1]).resolve())
    os.environ["PATH"] = runtime_path + os.pathsep + os.environ.get("PATH", "")
    if sys.platform == "win32" and hasattr(os, "add_dll_directory"):
        return os.add_dll_directory(runtime_path)
    return None


_DLL_DIRECTORY = _bootstrap_runtime()

from newclid.jgex.clause import JGEXClause
from newclid.jgex.constructions import ALL_JGEX_CONSTRUCTIONS
from newclid.jgex.definition import JGEXDefinition
from newclid.jgex.formulation import JGEXFormulation, jgex_formulation_from_txt_file
from newclid.jgex.problem_builder import JGEXProblemBuilder
from newclid.jgex.to_newclid import add_clause_to_problem
from newclid.all_rules import DEFAULT_RULES

from worker.backend.jgex_legacy_normalizer import normalize_legacy_formulation
from worker.backend.incremental_prefix_state import (
    PrefixStateCache,
    replay_prefix_state,
)
from worker.backend.generated_construction_action import (
    normalize_construction_actions,
    verify_construction_action_certificate,
)
from worker.backend.geometry_relation_channels import (
    AssertionKey,
    RelationFrontierWitness,
    backward_relation_distances,
    yuclid_assertion_keys,
    yuclid_relation_frontier,
    yuclid_relation_metrics,
)
from worker.backend.geometry_proof_hypergraph import (
    Atom,
    BackwardObligation,
    Theorem,
    euclidean_relation_theorems,
    stratify_backward_obligations,
    synthesize_backward_obligations,
)
from worker.backend.geometry_ar_residual import yuclid_ar_residual
from worker.backend.differentiable_proof_controller import (
    DifferentiableProofController,
    softplus,
)
from worker.backend.typed_candidate_alignment import (
    UNREACHABLE_DISTANCE,
    align_candidate_atoms,
    align_candidate_cone_to_proof_branches,
    align_candidate_groups_lazily,
    candidate_directly_satisfies_obligation,
    instantiate_relation_templates,
)
from worker.backend.typed_construction_contracts import (
    ContractSynthesisAudit,
    TypedConstructionContract,
    assess_construction_requirements,
    synthesize_contract_candidates,
)
from worker.backend.typed_construction_cegis import (
    TypedConstructionProposal,
    rank_construction_proposals,
)
from worker.backend.typed_open_proof_dag import (
    NativeProofDAGIncrement,
    NativeProofDAGProgress,
    OpenProofDAG,
    assess_native_proof_dag_progress,
    OpenProofBranch,
    compile_candidate_forward_cone,
    compile_open_proof_dag,
    native_proof_dag_increment,
)
from worker.backend.typed_bidirectional_priority import (
    search_bidirectionally_iterative,
)
from worker.backend.numerical_incidence_auxiliary import (
    NumericalIncidenceAtlas,
    NumericalIncidenceProfile,
)
from worker.backend.native_formal_obligation_sheaf import (
    build_candidate_local_view,
    build_mmt_candidate_local_view,
    candidate_theory_assignment,
    capability_preserving_candidate_order,
    coordinate_candidate_scores,
    coordinate_mmt_candidate_scores,
)
from worker.backend.mortra_unified_architecture import (
    unified_geometry_architecture_manifest,
)
from worker.backend.typed_geometry_stalk import (
    DEFAULT_POINT_FAMILIES,
    EXTENDED_POINT_FAMILIES,
    ConstructionFamily,
    TypedConstructionCandidate,
    augment_incidence_graph,
    augment_semantic_role_graph,
    augment_semantic_role_weights,
    balanced_stratified_beam,
    construction_semantic_edges,
    construction_semantic_weighted_edges,
    enumerate_typed_candidates,
    gate_candidates_by_relation_reachability,
    goal_relevant_families,
    prioritize_morphism_orbit,
    proof_hypergraph_point_relevance,
    relevance_ordered_schema_quota_fill,
    required_category_score_fill,
    schema_first_score_fill,
    schema_quota_score_fill,
)


DEFINITIONS = JGEXDefinition.to_dict(ALL_JGEX_CONSTRUCTIONS)
POLYNOMIAL_RELATION_CHANNELS = frozenset({"coll", "para", "perp", "cong"})


def _ordinal_preferences(
    candidates: list[TypedConstructionCandidate],
    ranks: dict[str, tuple[object, ...]],
) -> dict[str, float]:
    """Turn an ordering into scale-free local preferences without labels."""

    ordered_ranks = sorted({ranks[candidate.key] for candidate in candidates})
    if not ordered_ranks:
        return {}
    denominator = max(1, len(ordered_ranks) - 1)
    score_by_rank = {
        rank: 1.0 - index / denominator
        for index, rank in enumerate(ordered_ranks)
    }
    return {
        candidate.key: score_by_rank[ranks[candidate.key]]
        for candidate in candidates
    }


def construction_relation_atoms(
    family: str,
    output: str,
    inputs: tuple[str, ...],
) -> tuple[Atom, ...]:
    """Instantiate the formal conclusion atoms declared by a JGEX construction."""

    definition = DEFINITIONS[family]
    templates: list[Atom] = []
    for clause in definition.clauses:
        for construction in clause.constructions:
            tokens = tuple(str(construction.string).split())
            if tokens:
                templates.append(Atom(tokens[0], tokens[1:]))
    return instantiate_relation_templates(
        tuple(map(str, definition.args)),
        templates,
        (output, *inputs),
    )


def construction_requirement_atoms(
    family: str,
    output: str,
    inputs: tuple[str, ...],
) -> tuple[Atom, ...]:
    """Instantiate the declared existence/nondegeneracy side conditions."""

    definition = DEFINITIONS[family]
    templates = tuple(
        Atom(tokens[0], tokens[1:])
        for construction in definition.requirements.constructions
        if (tokens := tuple(str(construction.string).split()))
    )
    return instantiate_relation_templates(
        tuple(map(str, definition.args)),
        templates,
        (output, *inputs),
    )


def typed_construction_contracts(
    families: tuple[ConstructionFamily, ...],
) -> tuple[TypedConstructionContract, ...]:
    """Expose JGEX definitions as alpha-renamable construction contracts."""

    contracts: list[TypedConstructionContract] = []
    for family in families:
        output_variable = "?OUT"
        input_variables = tuple(
            f"?INPUT{index}" for index in range(family.input_arity)
        )
        contracts.append(
            TypedConstructionContract(
                family=family,
                output_variable=output_variable,
                input_variables=input_variables,
                relation_atoms=construction_relation_atoms(
                    family.name,
                    output_variable,
                    input_variables,
                ),
                requirement_atoms=construction_requirement_atoms(
                    family.name,
                    output_variable,
                    input_variables,
                ),
            )
        )
    return tuple(contracts)


@dataclass(frozen=True)
class ConstructionStep:
    family: str
    output: str
    inputs: tuple[str, ...]
    structural_rank: tuple[object, ...] = ()

    @property
    def key(self) -> str:
        return f"{self.family}({','.join(self.inputs)})->{self.output}"


def construction_path_from_payload(
    payload: list[dict[str, Any]],
) -> tuple[ConstructionStep, ...]:
    """Restore an enumerated construction path without re-enumerating it."""

    return tuple(
        ConstructionStep(
            family=str(item["family"]),
            output=str(item["output"]),
            inputs=tuple(str(value) for value in item.get("inputs", ())),
        )
        for item in payload
    )


def construction_path_to_payload(
    path: tuple[ConstructionStep, ...],
) -> list[dict[str, Any]]:
    """Persist an enumerated path in a stable, JSON-safe representation."""

    return [
        {
            "family": step.family,
            "output": step.output,
            "inputs": list(step.inputs),
        }
        for step in path
    ]


@dataclass(frozen=True)
class SearchRecord:
    steps: tuple[ConstructionStep, ...]
    solved: bool
    all_deduction_count: int
    goal_deduction_count: int
    relation_target_assertion_count: int
    relation_support_weight: int
    relation_near_goal_count: int
    relation_transition_potential: float
    relation_transition_channel_coverage: int
    relation_channel_counts: tuple[tuple[str, int], ...]
    frontier_witnesses: tuple[RelationFrontierWitness, ...]
    backward_obligations: tuple[BackwardObligation, ...]
    open_relation_demands: tuple[Atom, ...]
    ar_supported_goal_count: int
    ar_closed_goal_count: int
    ar_residual_support_size: int
    ar_residual_l1_weight: float
    ar_known_rank: int
    proof_dag_progress: NativeProofDAGProgress
    proof_dag_increment: NativeProofDAGIncrement
    elapsed_seconds: float
    error: str | None = None
    right_censored: bool = False


def _atom_from_dict(payload: dict[str, Any]) -> Atom:
    return Atom(
        str(payload["predicate"]),
        tuple(map(str, payload.get("arguments", ()))),
    )


def search_record_from_dict(payload: dict[str, Any]) -> SearchRecord:
    """Restore a verified candidate record from an atomic progress checkpoint."""

    return SearchRecord(
        steps=tuple(
            ConstructionStep(
                family=str(step["family"]),
                output=str(step["output"]),
                inputs=tuple(map(str, step.get("inputs", ()))),
                structural_rank=tuple(step.get("structural_rank", ())),
            )
            for step in payload.get("steps", ())
        ),
        solved=bool(payload.get("solved")),
        all_deduction_count=int(payload.get("all_deduction_count", 0)),
        goal_deduction_count=int(payload.get("goal_deduction_count", 0)),
        relation_target_assertion_count=int(
            payload.get("relation_target_assertion_count", 0)
        ),
        relation_support_weight=int(payload.get("relation_support_weight", 0)),
        relation_near_goal_count=int(payload.get("relation_near_goal_count", 0)),
        relation_transition_potential=float(
            payload.get("relation_transition_potential", 0.0)
        ),
        relation_transition_channel_coverage=int(
            payload.get("relation_transition_channel_coverage", 0)
        ),
        relation_channel_counts=tuple(
            (str(item[0]), int(item[1]))
            for item in payload.get("relation_channel_counts", ())
        ),
        frontier_witnesses=tuple(
            RelationFrontierWitness(
                channel=str(item["channel"]),
                points=tuple(map(str, item.get("points", ()))),
                support=tuple(map(str, item.get("support", ()))),
                distance_to_goal=int(item.get("distance_to_goal", 0)),
                goal_support_overlap=int(item.get("goal_support_overlap", 0)),
                rule=str(item.get("rule", "")),
                proof_reference=str(item.get("proof_reference", "")),
            )
            for item in payload.get("frontier_witnesses", ())
        ),
        backward_obligations=tuple(
            BackwardObligation(
                theorem=str(item["theorem"]),
                goal=_atom_from_dict(item["goal"]),
                matched_premises=tuple(
                    _atom_from_dict(atom)
                    for atom in item.get("matched_premises", ())
                ),
                open_premises=tuple(
                    _atom_from_dict(atom) for atom in item.get("open_premises", ())
                ),
                substitution=tuple(
                    (str(pair[0]), str(pair[1]))
                    for pair in item.get("substitution", ())
                ),
                unbound_variables=tuple(
                    map(str, item.get("unbound_variables", ()))
                ),
            )
            for item in payload.get("backward_obligations", ())
        ),
        open_relation_demands=tuple(
            _atom_from_dict(item) for item in payload.get("open_relation_demands", ())
        ),
        ar_supported_goal_count=int(payload.get("ar_supported_goal_count", 0)),
        ar_closed_goal_count=int(payload.get("ar_closed_goal_count", 0)),
        ar_residual_support_size=int(payload.get("ar_residual_support_size", 0)),
        ar_residual_l1_weight=float(payload.get("ar_residual_l1_weight", 0.0)),
        ar_known_rank=int(payload.get("ar_known_rank", 0)),
        proof_dag_progress=NativeProofDAGProgress(
            **{
                key: int(value)
                for key, value in payload.get("proof_dag_progress", {}).items()
            }
        ),
        proof_dag_increment=NativeProofDAGIncrement(
            **{
                key: int(value)
                for key, value in payload.get("proof_dag_increment", {}).items()
            }
        ),
        elapsed_seconds=float(payload.get("elapsed_seconds", 0.0)),
        error=payload.get("error"),
        right_censored=bool(payload.get("right_censored", False)),
    )


def formulation_structure(
    formulation: JGEXFormulation,
) -> tuple[
    set[str],
    dict[str, set[str]],
    dict[str, set[str]],
    dict[tuple[str, str], int],
    dict[str, int],
]:
    points = {str(point) for point in formulation.points}
    graph: dict[str, set[str]] = defaultdict(set)
    role_graph: dict[str, set[str]] = defaultdict(set)
    role_weights: dict[tuple[str, str], int] = {}
    for clause in formulation.setup_clauses:
        clause_points = {str(point) for point in clause.points}
        for construction in clause.constructions:
            arguments = tuple(
                str(argument)
                for argument in construction.args
                if str(argument) and str(argument)[0].isalpha()
            )
            clause_points.update(arguments)
            raw_name = getattr(construction, "name", "")
            if hasattr(raw_name, "value"):
                raw_name = raw_name.value
            for left, right in construction_semantic_edges(str(raw_name), arguments):
                role_graph[left].add(right)
                role_graph[right].add(left)
            for left, right, weight in construction_semantic_weighted_edges(
                str(raw_name), arguments
            ):
                key = tuple(sorted((left, right)))
                role_weights[key] = max(role_weights.get(key, 0), weight)
        for left in clause_points:
            for right in clause_points:
                if left != right:
                    graph[left].add(right)
    goal_multiplicity: dict[str, int] = defaultdict(int)
    for goal in formulation.goals:
        for argument in goal.args:
            goal_multiplicity[str(argument)] += 1
    for point in points:
        graph.setdefault(point, set())
        role_graph.setdefault(point, set())
    return points, graph, role_graph, role_weights, goal_multiplicity


def _rule_atom(construction: Any) -> Atom:
    arguments = tuple(
        f"?{value}" if value and value[0].isalpha() else value
        for value in map(str, construction.variables)
    )
    return Atom(str(construction.name), arguments)


def native_rule_theorems() -> tuple[Theorem, ...]:
    """Expose explicit Newclid rules plus universal Euclidean AR morphisms."""

    theorems: list[Theorem] = []
    for rule in sorted(DEFAULT_RULES, key=lambda item: item.id):
        premises = tuple(_rule_atom(item) for item in rule.premises)
        for index, conclusion in enumerate(rule.conclusions):
            theorems.append(
                Theorem(
                    f"{rule.id}:{index}",
                    premises,
                    _rule_atom(conclusion),
                )
            )
    return (*theorems, *euclidean_relation_theorems())


def formulation_goal_atoms(formulation: JGEXFormulation) -> tuple[Atom, ...]:
    goals: list[Atom] = []
    for goal in formulation.goals:
        raw_name = getattr(goal, "name", None)
        if hasattr(raw_name, "value"):
            raw_name = raw_name.value
        if not raw_name:
            raw_name = str(goal).split()[0]
        goals.append(Atom(str(raw_name), tuple(map(str, goal.args))).canonical())
    return tuple(goals)


def proof_state_obligations(
    payload: dict[str, Any],
    goals: tuple[Atom, ...],
    theorems: tuple[Theorem, ...],
    *,
    max_results: int = 24,
) -> tuple[tuple[BackwardObligation, ...], tuple[Atom, ...]]:
    facts = tuple(Atom(predicate, points) for predicate, points in yuclid_assertion_keys(payload))
    obligations: list[BackwardObligation] = []
    for goal in goals:
        expanded = synthesize_backward_obligations(
            facts,
            goal,
            theorems,
            max_open_premises=4,
            max_states_per_rule=192,
            max_results=max_results * 4,
        )
        obligations.extend(
            stratify_backward_obligations(
                expanded,
                limit=max_results,
                witness_fraction=0.25,
            )
        )
    ranked = tuple(obligations[:max_results])
    demands: list[Atom] = []
    seen: set[Atom] = set()
    for obligation in ranked:
        for premise in obligation.open_premises:
            if premise not in seen:
                seen.add(premise)
                demands.append(premise)
    return ranked, tuple(demands[:max_results])


def proof_hypergraph_relevance(
    payload: dict[str, Any],
    goal_support: set[str],
) -> dict[str, float]:
    """Score points by goal overlap in the saturated proof hypergraph.

    This uses only deductions produced from the visible setup.  Dataset
    auxiliary clauses and known solutions are absent.  A deduction contributes
    |support intersection goal| / |support| to every point in its support.
    """

    deductions = payload.get("all_deductions", [])
    if not isinstance(deductions, list):
        return {}
    return proof_hypergraph_point_relevance(deductions, goal_support)


def next_point_name(points: set[str]) -> str:
    for letter in "abcdefghijklmnopqrstuvwxyz":
        if letter not in points:
            return letter
    for index in range(1, 1000):
        for letter in "abcdefghijklmnopqrstuvwxyz":
            candidate = f"{letter}{index}"
            if candidate not in points:
                return candidate
    raise RuntimeError("point alphabet exhausted")


def branch_seed(seed: int, steps: tuple[ConstructionStep, ...]) -> int:
    payload = str(seed) + "|" + "|".join(step.key for step in steps)
    return int.from_bytes(hashlib.sha256(payload.encode()).digest()[:8], "big")


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    """Persist a checkpoint without exposing a partially written JSON file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    # Avoid duplicating a large proof trace as one in-memory JSON string.
    encoder = json.JSONEncoder(indent=2)
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        for chunk in encoder.iterencode(payload):
            stream.write(chunk)
        stream.write("\n")
    for attempt in range(8):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == 7:
                raise
            # Windows can briefly lock a checkpoint while the monitor reads it.
            time.sleep(0.01 * (2**attempt))


def build_branch(base_problem: Any, steps: tuple[ConstructionStep, ...], *, seed: int) -> Any:
    problem = base_problem.model_copy(deep=True)
    rng = np.random.default_rng(branch_seed(seed, steps))
    for step in steps:
        clause_text = (
            f"{step.output} = {step.family} {step.output} "
            + " ".join(step.inputs)
        )
        clause = JGEXClause.from_str(clause_text)[0]
        problem, _ = add_clause_to_problem(problem, clause, DEFINITIONS, rng, 5)
    return problem


def extend_prefix_branch(
    parent_problem: Any,
    step: ConstructionStep,
    path: tuple[ConstructionStep, ...],
    *,
    seed: int,
) -> Any:
    problem = parent_problem.model_copy(deep=True)
    rng = np.random.default_rng(branch_seed(seed, path))
    clause = construction_clause(step)
    problem, _ = add_clause_to_problem(problem, clause, DEFINITIONS, rng, 5)
    return problem


def build_prefix_stable_branch(
    base_problem: Any,
    steps: tuple[ConstructionStep, ...],
    *,
    seed: int,
) -> Any:
    return replay_prefix_state(
        base_problem,
        steps,
        transition=lambda parent, step, path: extend_prefix_branch(
            parent, step, path, seed=seed
        ),
    )


def construction_clause(step: ConstructionStep) -> JGEXClause:
    return JGEXClause.from_str(
        f"{step.output} = {step.family} {step.output} " + " ".join(step.inputs)
    )[0]


def augment_formulation(
    formulation: JGEXFormulation, steps: tuple[ConstructionStep, ...]
) -> JGEXFormulation:
    """Return the visible problem plus synthesized clauses, never dataset auxiliaries."""

    return JGEXFormulation(
        name=formulation.name,
        setup_clauses=formulation.setup_clauses
        + tuple(construction_clause(step) for step in steps),
        auxiliary_clauses=(),
        goals=formulation.goals,
    )


def evaluate_steps(
    base_problem: Any,
    steps: tuple[ConstructionStep, ...],
    *,
    seed: int,
    yuclid_exe: Path,
    ar_profile: str,
    goal_channels: set[str],
    goal_support: set[str],
    baseline_assertion_keys: set[AssertionKey],
    transition_distances: dict[str, int],
    goal_atoms: tuple[Atom, ...],
    rule_theorems: tuple[Theorem, ...],
    proof_dag_branches: tuple[OpenProofBranch, ...],
    parent_proof_dag_progress: NativeProofDAGProgress,
    obligation_guided: bool,
    yuclid_timeout_seconds: float | None = None,
    prepared_problem: Any | None = None,
) -> SearchRecord:
    from worker.backend.yuclid_native_verifier import (
        YuclidTimeoutError,
        verify_problem,
    )

    started = time.perf_counter()
    try:
        problem = (
            prepared_problem
            if prepared_problem is not None
            else build_branch(base_problem, steps, seed=seed)
        )
        verification = verify_problem(
            problem,
            yuclid_exe=yuclid_exe,
            ar_profile=ar_profile,
            timeout_seconds=yuclid_timeout_seconds,
        )
        relation_metrics = yuclid_relation_metrics(
            verification.payload,
            goal_channels=goal_channels,
            goal_support=goal_support,
            excluded_assertion_keys=baseline_assertion_keys,
            exclude_direct_construction=True,
            transition_distances=transition_distances,
        )
        frontier = yuclid_relation_frontier(
            verification.payload,
            goal_support=goal_support,
            transition_distances=transition_distances,
            excluded_assertion_keys=baseline_assertion_keys,
        )
        obligations, demands = (
            proof_state_obligations(verification.payload, goal_atoms, rule_theorems)
            if obligation_guided
            else ((), ())
        )
        ar_residual = yuclid_ar_residual(
            verification.payload,
            ((atom.predicate, atom.arguments) for atom in goal_atoms),
        )
        proof_dag_progress = assess_native_proof_dag_progress(
            (
                Atom(predicate, points)
                for predicate, points in yuclid_assertion_keys(
                    verification.payload
                )
            ),
            proof_dag_branches,
            baseline_facts=(
                Atom(predicate, points)
                for predicate, points in baseline_assertion_keys
            ),
        )
        proof_dag_increment = native_proof_dag_increment(
            parent_proof_dag_progress,
            proof_dag_progress,
        )
        return SearchRecord(
            steps,
            verification.solved,
            verification.all_deduction_count,
            verification.goal_deduction_count,
            relation_metrics.target_assertion_count,
            relation_metrics.target_support_weight,
            relation_metrics.near_goal_assertion_count,
            relation_metrics.transition_potential,
            relation_metrics.transition_channel_coverage,
            relation_metrics.channel_counts,
            frontier,
            obligations,
            demands,
            ar_residual.supported_goal_count,
            ar_residual.closed_goal_count,
            ar_residual.residual_support_size,
            ar_residual.residual_l1_weight,
            ar_residual.known_rank,
            proof_dag_progress,
            proof_dag_increment,
            time.perf_counter() - started,
        )
    except Exception as exc:
        return SearchRecord(
            steps,
            False,
            0,
            0,
            0,
            0,
            0,
            0.0,
            0,
            tuple(),
            tuple(),
            tuple(),
            tuple(),
            0,
            0,
            0,
            0.0,
            0,
            NativeProofDAGProgress(0, 0, 0, -1, 0, 0, 0, 0, 0),
            NativeProofDAGIncrement(0, 0, 0, 0, 0, 0),
            time.perf_counter() - started,
            error=str(exc),
            right_censored=isinstance(exc, YuclidTimeoutError),
        )


def candidate_extensions(
    *,
    base_problem: Any,
    base_points: set[str],
    base_graph: dict[str, set[str]],
    base_role_graph: dict[str, set[str]],
    base_role_weights: dict[tuple[str, str], int],
    goal_multiplicity: dict[str, int],
    proof_relevance: dict[str, float],
    steps: tuple[ConstructionStep, ...],
    families: tuple[ConstructionFamily, ...],
    per_family_limit: int,
    branch_limit: int,
    ranking: str,
    seed: int,
    relation_demands: tuple[Atom, ...] = (),
    require_generated_input: bool = False,
    candidate_gate: str = "off",
    candidate_reachable_channels: set[str] | None = None,
    candidate_target_channels: set[str] | None = None,
    candidate_alignment: str = "off",
    candidate_relation_distances: dict[str, dict[str, int]] | None = None,
    proof_dag_branches: tuple[OpenProofBranch, ...] = (),
    proof_dags: tuple[OpenProofDAG, ...] = (),
    proof_dag_goals: tuple[Atom, ...] = (),
    proof_dag_facts: tuple[Atom, ...] = (),
    proof_dag_theorems: tuple[Theorem, ...] = (),
    candidate_cone_depth: int = 2,
    candidate_cone_fragments: int = 128,
    candidate_cone_states: int = 5_000,
    candidate_cone_initial_states: int = 64,
    candidate_promotion_limit: int = 8,
    candidate_incidence: str = "off",
    incidence_tolerance: float = 1e-7,
    incidence_oversample_per_family: int = 16,
    incidence_preselect_limit: int = 0,
    incidence_workers: int = 1,
    current_problem: Any | None = None,
    construction_seed: int = 0,
    candidate_contract_synthesis: bool = False,
    contract_candidates_per_schema: int = 32,
    contract_obligation_branches: tuple[tuple[Atom, ...], ...] = (),
    enumeration_limit_per_family: int = 0,
    candidate_cone_timeout_seconds: float = 0.0,
) -> tuple[list[ConstructionStep], dict[str, Any]]:
    extension_started = time.perf_counter()
    generated = {step.output for step in steps}
    points = base_points | generated
    graph = augment_incidence_graph(
        base_graph, tuple((step.output, step.inputs) for step in steps)
    )
    role_graph = augment_semantic_role_graph(
        base_role_graph,
        tuple((step.family, step.output, step.inputs) for step in steps),
    )
    role_weights = augment_semantic_role_weights(
        base_role_weights,
        tuple((step.family, step.output, step.inputs) for step in steps),
    )
    used = {f"{step.family}({','.join(step.inputs)})" for step in steps}
    current_problem = (
        current_problem
        if current_problem is not None
        else build_branch(
            base_problem,
            steps,
            seed=(construction_seed if candidate_incidence == "hageo" else seed),
        )
    )
    coordinates = {
        str(point.name): (float(point.num.x), float(point.num.y))
        for point in current_problem.points
    }
    output = next_point_name(points)
    enumeration_audit: dict[str, object] = {}
    candidates = enumerate_typed_candidates(
        points=tuple(points),
        graph=graph,
        goal_multiplicity=goal_multiplicity,
        proof_relevance=proof_relevance,
        generated_points=generated,
        used_keys=used,
        families=families,
        per_family_limit=(
            max(per_family_limit, incidence_oversample_per_family)
            if candidate_incidence == "hageo"
            else per_family_limit
        ),
        ranking=ranking,
        seed=seed,
        coordinates=coordinates,
        orbit_family=steps[-1].family if steps else None,
        orbit_inputs=steps[-1].inputs if steps else (),
        relation_demands=relation_demands,
        role_graph=role_graph,
        role_weights=role_weights,
        required_input_points=(generated if require_generated_input else set()),
        max_input_tuples_per_family=(
            enumeration_limit_per_family
            if enumeration_limit_per_family > 0
            else None
        ),
        audit=enumeration_audit,
    )
    contract_audit = ContractSynthesisAudit(0, 0, 0, 0, 0, 0)
    contract_candidates = ()
    contract_chart_rank_by_key: dict[str, tuple[tuple[int, int, int], bool]] = {}
    contract_requirement_gate = {
        "input_candidates": 0,
        "executable_candidates": 0,
        "held_open_candidates": 0,
        "statically_rejected_candidates": 0,
    }
    if candidate_contract_synthesis:
        contract_candidates, contract_audit = synthesize_contract_candidates(
            relation_demands,
            typed_construction_contracts(families),
            visible_entities=tuple(sorted(points)),
            output_entity=output,
            used_keys=used,
            max_candidates_per_contract=contract_candidates_per_schema,
            obligation_branches=contract_obligation_branches,
            known_facts=proof_dag_facts,
        )
        generic_candidates = [
            TypedConstructionCandidate(
                candidate.family,
                candidate.inputs,
                (1, *candidate.structural_rank),
            )
            for candidate in candidates
        ]
        synthesized_candidates = [
            TypedConstructionCandidate(
                candidate.family,
                candidate.inputs,
                (0, *candidate.rank),
            )
            for candidate in contract_candidates
        ]
        candidates_by_key: dict[str, TypedConstructionCandidate] = {}
        for candidate in (*synthesized_candidates, *generic_candidates):
            previous = candidates_by_key.get(candidate.key)
            if previous is None or candidate.structural_rank < previous.structural_rank:
                candidates_by_key[candidate.key] = candidate
        requirement_assessments = {
            candidate.key: assess_construction_requirements(
                construction_requirement_atoms(
                    candidate.family, output, candidate.inputs
                ),
                proof_dag_facts,
            )
            for candidate in candidates_by_key.values()
        }
        contract_requirement_gate = {
            "input_candidates": len(requirement_assessments),
            "executable_candidates": sum(
                item.executable for item in requirement_assessments.values()
            ),
            "held_open_candidates": sum(
                bool(item.open) and not item.contradictory
                for item in requirement_assessments.values()
            ),
            "statically_rejected_candidates": sum(
                bool(item.contradictory)
                for item in requirement_assessments.values()
            ),
        }
        candidates = [
            candidate
            for candidate in candidates_by_key.values()
            if requirement_assessments[candidate.key].executable
        ]
        if contract_obligation_branches:
            chart_ranked = rank_construction_proposals(
                proof_dag_facts,
                contract_obligation_branches,
                tuple(
                    TypedConstructionProposal(
                        key=candidate.key,
                        family=candidate.family,
                        inputs=candidate.inputs,
                        postconditions=construction_relation_atoms(
                            candidate.family, output, candidate.inputs
                        ),
                        requirements=construction_requirement_atoms(
                            candidate.family, output, candidate.inputs
                        ),
                    )
                    for candidate in candidates
                ),
            )
            contract_chart_rank_by_key = {
                proposal.key: (rank, reduced)
                for proposal, rank, reduced in chart_ranked
            }
            candidates = [
                TypedConstructionCandidate(
                    candidate.family,
                    candidate.inputs,
                    (
                        0
                        if contract_chart_rank_by_key[candidate.key][1]
                        else 1,
                        *contract_chart_rank_by_key[candidate.key][0],
                        *candidate.structural_rank,
                    ),
                )
                for candidate in candidates
            ]
    candidates = prioritize_morphism_orbit(
        candidates,
        previous_family=steps[-1].family if steps else None,
        previous_inputs=steps[-1].inputs if steps else (),
    )
    if require_generated_input and generated:
        candidates = [
            candidate
            for candidate in candidates
            if generated.intersection(candidate.inputs)
        ]
    gate_result = gate_candidates_by_relation_reachability(
        candidates,
        families=families,
        reachable_channels=candidate_reachable_channels or set(),
        target_channels=candidate_target_channels or set(),
        mode=(
            "relation-reachability"
            if candidate_gate in {"relation-reachability", "combined"}
            else "off"
        ),
    )
    candidates = list(gate_result.candidates)
    incidence_input_count = len(candidates)
    if (
        candidate_incidence == "hageo"
        and incidence_preselect_limit > 0
        and len(candidates) > incidence_preselect_limit
    ):
        if candidate_alignment in {
            "typed-atom",
            "proof-dag-priority",
            "native-formal-sheaf",
            "mmt-theory-view",
        }:
            pre_alignment = {
                candidate.key: align_candidate_atoms(
                    construction_relation_atoms(
                        candidate.family, output, candidate.inputs
                    ),
                    relation_demands,
                    candidate_relation_distances or {},
                )
                for candidate in candidates
            }
            if (
                candidate_contract_synthesis
                and candidate_alignment != "proof-dag-priority"
            ):
                candidates.sort(
                    key=lambda candidate: (
                        candidate.structural_rank,
                        pre_alignment[candidate.key].rank,
                    )
                )
            else:
                candidates.sort(
                    key=lambda candidate: (
                        pre_alignment[candidate.key].rank,
                        candidate.structural_rank,
                    )
                )
        else:
            candidates.sort(key=lambda candidate: candidate.structural_rank)
        if candidate_alignment == "proof-dag-priority":
            relevant_families = tuple(
                dict.fromkeys(candidate.family for candidate in candidates)
            )[:2]
            candidates = schema_quota_score_fill(
                candidates,
                category=lambda candidate: candidate.family,
                category_order=relevant_families,
                limit=incidence_preselect_limit,
                within_category_key=lambda candidate: candidate.structural_rank,
                quota_fraction=0.25,
            )
        else:
            candidates = schema_quota_score_fill(
                candidates,
                category=lambda candidate: candidate.family,
                category_order=[family.name for family in families],
                limit=incidence_preselect_limit,
                within_category_key=lambda candidate: candidate.structural_rank,
                quota_fraction=0.5,
            )
    incidence_by_key: dict[str, NumericalIncidenceProfile] = {}
    incidence_errors: dict[str, int] = defaultdict(int)
    incidence_started = time.perf_counter()
    if candidate_incidence == "hageo":
        if incidence_workers < 1:
            raise ValueError("incidence_workers must be positive")
        incidence_atlas = NumericalIncidenceAtlas.build(
            coordinates,
            tolerance=incidence_tolerance,
        )

        def evaluate_incidence_candidate(
            candidate: TypedConstructionCandidate,
        ) -> tuple[str, NumericalIncidenceProfile | None, str | None]:
            step = ConstructionStep(
                candidate.family,
                output,
                candidate.inputs,
                candidate.structural_rank,
            )
            try:
                candidate_problem = extend_prefix_branch(
                    current_problem,
                    step,
                    (*steps, step),
                    seed=construction_seed,
                )
                output_point = next(
                    point for point in candidate_problem.points if str(point.name) == output
                )
                output_coordinates = (
                    float(output_point.num.x),
                    float(output_point.num.y),
                )
                return (
                    candidate.key,
                    incidence_atlas.profile(
                        output_coordinates,
                        family=candidate.family,
                        inputs=candidate.inputs,
                    ),
                    None,
                )
            except Exception as exc:
                return candidate.key, None, type(exc).__name__

        if incidence_workers == 1:
            incidence_results = map(evaluate_incidence_candidate, candidates)
        else:
            executor = ThreadPoolExecutor(max_workers=incidence_workers)
            incidence_results = executor.map(evaluate_incidence_candidate, candidates)
        try:
            for candidate_key, profile, error_type in incidence_results:
                if profile is not None:
                    incidence_by_key[candidate_key] = profile
                elif error_type is not None:
                    incidence_errors[error_type] += 1
        finally:
            if incidence_workers != 1:
                executor.shutdown(wait=True)
        candidates.sort(
            key=lambda candidate: (
                incidence_by_key[candidate.key].rank
                if candidate.key in incidence_by_key
                else (2,),
                candidate.structural_rank,
            )
        )
    elif candidate_incidence != "off":
        raise ValueError(f"unknown candidate incidence mode: {candidate_incidence}")
    incidence_elapsed_seconds = time.perf_counter() - incidence_started

    def incidence_rank(candidate: TypedConstructionCandidate) -> tuple[int, ...]:
        profile = incidence_by_key.get(candidate.key)
        return profile.rank if profile is not None else ((2,) if candidate_incidence == "hageo" else ())

    unified_iterative_search = None
    if candidate_alignment == "typed-atom":
        alignment_by_key = {
            candidate.key: align_candidate_atoms(
                construction_relation_atoms(
                    candidate.family, output, candidate.inputs
                ),
                relation_demands,
                candidate_relation_distances or {},
            )
            for candidate in candidates
        }
        candidates.sort(
            key=(
                (
                    lambda candidate: (
                        candidate.structural_rank,
                        alignment_by_key[candidate.key].rank,
                        incidence_rank(candidate),
                    )
                )
                if candidate_contract_synthesis
                else (
                    lambda candidate: (
                        alignment_by_key[candidate.key].rank,
                        incidence_rank(candidate),
                        candidate.structural_rank,
                    )
                )
            )
        )
        meet_cones = {}
    elif candidate_alignment == "proof-dag-meet":
        parent_atoms = tuple(
            atom
            for step in steps
            for atom in construction_relation_atoms(
                step.family, step.output, step.inputs
            )
        )
        alignment_by_key = {}
        meet_cones = {}
        targets = tuple(
            atom for branch in proof_dag_branches for atom in branch.frontier
        )
        for candidate in candidates:
            extension_atoms = construction_relation_atoms(
                candidate.family, output, candidate.inputs
            )
            cone = compile_candidate_forward_cone(
                proof_dag_facts,
                (*parent_atoms, *extension_atoms),
                proof_dag_theorems,
                targets=targets,
                max_rule_depth=candidate_cone_depth,
                max_fragments=candidate_cone_fragments,
                max_search_states=candidate_cone_states,
            )
            meet_cones[candidate.key] = cone
            alignment_by_key[candidate.key] = (
                align_candidate_cone_to_proof_branches(
                    cone, proof_dag_branches
                )
            )
        candidates.sort(
            key=lambda candidate: (
                alignment_by_key[candidate.key].rank,
                incidence_rank(candidate),
                candidate.structural_rank,
            )
        )
    elif candidate_alignment == "proof-dag-lazy":
        parent_atoms = tuple(
            atom
            for step in steps
            for atom in construction_relation_atoms(
                step.family, step.output, step.inputs
            )
        )
        candidate_atoms_by_key = {
            candidate.key: construction_relation_atoms(
                candidate.family, output, candidate.inputs
            )
            for candidate in candidates
        }
        alignment_by_key, meet_cones = align_candidate_groups_lazily(
            (*proof_dag_facts, *parent_atoms),
            candidate_atoms_by_key,
            proof_dag_theorems,
            proof_dag_branches,
            tiebreaks={
                candidate.key: candidate.structural_rank
                for candidate in candidates
            },
            max_rule_depth=candidate_cone_depth,
            max_fragments=candidate_cone_fragments,
            initial_search_states=candidate_cone_initial_states,
            promoted_search_states=candidate_cone_states,
            promotion_limit=candidate_promotion_limit,
        )
        candidates.sort(
            key=lambda candidate: (
                alignment_by_key[candidate.key].rank,
                incidence_rank(candidate),
                candidate.structural_rank,
            )
        )
        unified_search = None
    elif candidate_alignment == "proof-dag-priority":
        parent_atoms = tuple(
            atom
            for step in steps
            for atom in construction_relation_atoms(
                step.family, step.output, step.inputs
            )
        )
        candidate_atoms_by_key = {
            candidate.key: construction_relation_atoms(
                candidate.family, output, candidate.inputs
            )
            for candidate in candidates
        }
        unified_iterative_search = search_bidirectionally_iterative(
            (*proof_dag_facts, *parent_atoms),
            proof_dag_goals,
            candidate_atoms_by_key,
            proof_dag_theorems,
            max_depth=candidate_cone_depth,
            max_backward_branches=candidate_cone_fragments,
            max_forward_fragments=candidate_cone_fragments,
            per_task_search_states=candidate_cone_states,
            max_total_search_states=(
                candidate_cone_initial_states * len(candidates)
                + candidate_cone_states * candidate_promotion_limit
                + candidate_cone_states
            ),
            max_tasks=max(
                1,
                (len(candidates) + len(proof_dag_goals))
                * candidate_cone_depth,
            ),
            max_wall_seconds=(
                candidate_cone_timeout_seconds
                if candidate_cone_timeout_seconds > 0
                else None
            ),
            initial_proof_dags=proof_dags,
        )
        unified_search = unified_iterative_search.search
        alignment_by_key = dict(unified_search.candidates)
        meet_cones = dict(unified_search.forward_cones)
        candidates.sort(
            key=lambda candidate: (
                alignment_by_key[candidate.key].rank,
                incidence_rank(candidate),
                candidate.structural_rank,
            )
        )
    elif candidate_alignment in {"native-formal-sheaf", "mmt-theory-view"}:
        # Each agent keeps a private candidate ordering.  Only candidates seen
        # by two compatible formal languages reach an edge stalk.  The ADMM
        # result controls search order only; Yuclid replay still decides truth.
        demands = relation_demands or proof_dag_goals
        alignment_by_key = {
            candidate.key: align_candidate_atoms(
                construction_relation_atoms(
                    candidate.family, output, candidate.inputs
                ),
                demands,
                candidate_relation_distances or {},
            )
            for candidate in candidates
        }
        grammar_scores = _ordinal_preferences(
            candidates,
            {candidate.key: candidate.structural_rank for candidate in candidates},
        )
        relation_scores = _ordinal_preferences(
            candidates,
            {
                candidate.key: alignment_by_key[candidate.key].rank
                for candidate in candidates
            },
        )
        typed_incidence_scores = _ordinal_preferences(
            candidates,
            {
                candidate.key: (
                    alignment_by_key[candidate.key].rank,
                    incidence_rank(candidate),
                    candidate.structural_rank,
                )
                for candidate in candidates
            },
        )
        typed_incidence_view = build_candidate_local_view(
            agent_id="typed_incidence_proposal",
            formal_language="typed relation plus numerical incidence proposal",
            scores=typed_incidence_scores,
        )
        polynomial_eligible = {
            candidate.key
            for candidate in candidates
            if {
                atom.predicate
                for atom in construction_relation_atoms(
                    candidate.family, output, candidate.inputs
                )
            }
            and {
                atom.predicate
                for atom in construction_relation_atoms(
                    candidate.family, output, candidate.inputs
                )
            }
            <= POLYNOMIAL_RELATION_CHANNELS
        }
        polynomial_scores = {
            candidate.key: 1.0 for candidate in candidates
            if candidate.key in polynomial_eligible
        }
        theory_assignments = {
            candidate.key: candidate_theory_assignment(
                candidate.key,
                family=candidate.family,
                relations=(
                    atom.predicate
                    for atom in construction_relation_atoms(
                        candidate.family, output, candidate.inputs
                    )
                ),
            )
            for candidate in candidates
        }
        local_views = [
            build_candidate_local_view(
                agent_id="tong_action",
                formal_language="typed construction action language",
                scores=grammar_scores,
            ),
            build_candidate_local_view(
                agent_id="newclid_relation",
                formal_language="Newclid relation obligations",
                scores=relation_scores,
            ),
        ]
        proof_dag_view = None
        proof_dag_search = None
        proof_dag_elapsed_seconds = 0.0
        if proof_dag_goals and proof_dag_theorems:
            # Stage the expensive bidirectional prover.  Use a schema-balanced
            # shortlist across independent trajectories, and spend only the
            # configured branch budget on strong residual matches.  Sending
            # every enumerated term to this specialist made a nominal
            # branch_limit=16 expand more than 300 proof cones before any
            # native feedback was seen.  The full candidate set remains in the
            # cheaper MMT/incidence portfolio and rotates with the attempt seed.
            proof_dag_limit = min(
                len(candidates),
                max(1, min(branch_limit, candidate_promotion_limit)),
            )
            ranked_proof_candidates = sorted(
                candidates,
                key=lambda candidate: (
                    alignment_by_key[candidate.key].rank,
                    incidence_rank(candidate),
                    candidate.structural_rank,
                ),
            )
            family_balanced_candidates = relevance_ordered_schema_quota_fill(
                ranked_proof_candidates,
                category=lambda candidate: candidate.family,
                limit=len(ranked_proof_candidates),
                within_category_key=lambda candidate: (
                    alignment_by_key[candidate.key].rank,
                    incidence_rank(candidate),
                    candidate.structural_rank,
                ),
                quota_fraction=1.0,
            )
            candidate_atoms_by_key = {
                candidate.key: construction_relation_atoms(
                    candidate.family, output, candidate.inputs
                )
                for candidate in ranked_proof_candidates
            }
            proof_dag_candidates = required_category_score_fill(
                family_balanced_candidates,
                memberships=lambda candidate: (
                    demand
                    for demand in proof_dag_goals
                    if candidate_directly_satisfies_obligation(
                        candidate_atoms_by_key[candidate.key], demand
                    )
                ),
                required_categories=proof_dag_goals,
                limit=proof_dag_limit,
            )
            parent_atoms = tuple(
                atom
                for step in steps
                for atom in construction_relation_atoms(
                    step.family, step.output, step.inputs
                )
            )
            proof_candidate_atoms = {
                candidate.key: candidate_atoms_by_key[candidate.key]
                for candidate in proof_dag_candidates
            }
            proof_dag_started = time.perf_counter()
            proof_dag_search = search_bidirectionally_iterative(
                (*proof_dag_facts, *parent_atoms),
                proof_dag_goals,
                proof_candidate_atoms,
                proof_dag_theorems,
                max_depth=candidate_cone_depth,
                max_backward_branches=candidate_cone_fragments,
                max_forward_fragments=candidate_cone_fragments,
                per_task_search_states=candidate_cone_states,
                max_total_search_states=(
                    candidate_cone_initial_states * len(proof_dag_candidates)
                    + candidate_cone_states * candidate_promotion_limit
                    + candidate_cone_states
                ),
                max_tasks=max(
                    1,
                    (len(proof_dag_candidates) + len(proof_dag_goals))
                    * candidate_cone_depth,
                ),
                max_wall_seconds=(
                    candidate_cone_timeout_seconds
                    if candidate_cone_timeout_seconds > 0
                    else None
                ),
                initial_proof_dags=proof_dags,
            )
            proof_dag_elapsed_seconds = time.perf_counter() - proof_dag_started
            proof_dag_scores = _ordinal_preferences(
                proof_dag_candidates,
                {
                    candidate.key: (
                        proof_dag_search.candidates[candidate.key].rank,
                        incidence_rank(candidate),
                        candidate.structural_rank,
                    )
                    for candidate in proof_dag_candidates
                },
            )
            proof_dag_view = build_candidate_local_view(
                agent_id="newclid_bidirectional_proof_dag",
                formal_language="Newclid typed backward/forward proof DAG",
                scores=proof_dag_scores,
            )
        if polynomial_scores:
            local_views.append(
                build_candidate_local_view(
                    agent_id="gclc_wu",
                    formal_language="GCLC/Wu polynomial relation interface",
                    scores=polynomial_scores,
                )
            )
        if incidence_by_key:
            incidence_candidates = [
                candidate for candidate in candidates if candidate.key in incidence_by_key
            ]
            incidence_scores = _ordinal_preferences(
                incidence_candidates,
                {
                    candidate.key: incidence_by_key[candidate.key].rank
                    for candidate in incidence_candidates
                },
            )
            local_views.append(
                build_candidate_local_view(
                    agent_id="hageo_incidence",
                    formal_language="HAGeo numerical incidence observations",
                    scores=incidence_scores,
                )
            )
        coordination_views = local_views
        if candidate_alignment == "mmt-theory-view":
            coordination_source_views = (
                [*local_views, proof_dag_view]
                if proof_dag_view is not None
                else local_views
            )
            coordination_views = [
                build_mmt_candidate_local_view(
                    agent_id=view.agent_id,
                    formal_language=view.formal_language,
                    scores=view.preferences,
                    assignments=theory_assignments,
                    expose_instances=True,
                    expose_morphisms=view.agent_id
                    in {"tong_action", "typed_incidence_proposal", "hageo_incidence"},
                    expose_relations=view.agent_id
                    in {
                        "newclid_relation",
                        "newclid_bidirectional_proof_dag",
                        "gclc_wu",
                        "hageo_incidence",
                    },
                )
                for view in coordination_source_views
            ]
        coordination_started = time.perf_counter()
        if candidate_alignment == "mmt-theory-view":
            coordinated_scores, sheaf_result = coordinate_mmt_candidate_scores(
                coordination_views,
                theory_assignments,
            )
        else:
            coordinated_scores, sheaf_result = coordinate_candidate_scores(local_views)
        coordination_elapsed_seconds = time.perf_counter() - coordination_started
        candidates.sort(
            key=lambda candidate: (
                -coordinated_scores.get(candidate.key, 0.0),
                alignment_by_key[candidate.key].rank,
                incidence_rank(candidate),
                candidate.structural_rank,
            )
        )
        consensus_ranking = [candidate.key for candidate in candidates]
        portfolio_views = (
            [typed_incidence_view, proof_dag_view, *local_views]
            if proof_dag_view is not None
            else [typed_incidence_view, *local_views]
        )
        portfolio_order = capability_preserving_candidate_order(
            consensus_ranking,
            portfolio_views,
        )
        if proof_dag_view is not None:
            # A bounded specialist reservation prevents consensus from erasing
            # a construction that one exact prover ranks highly.  The prefix
            # remains problem-agnostic: it is derived only from typed proof
            # obligations and contains no problem names or expected answers.
            proof_priority = sorted(
                proof_dag_view.preferences,
                key=lambda name: (
                    -float(proof_dag_view.preferences[name]),
                    name,
                ),
            )
            candidate_by_key = {candidate.key: candidate for candidate in candidates}
            proof_family_priority: list[str] = []
            proof_families: set[str] = set()
            for key in proof_priority:
                family = candidate_by_key[key].family
                if family in proof_families:
                    continue
                proof_families.add(family)
                proof_family_priority.append(key)
            typed_priority = sorted(
                typed_incidence_view.preferences,
                key=lambda name: (
                    -float(typed_incidence_view.preferences[name]),
                    name,
                ),
            )[:8]
            reserved_prefix = capability_preserving_candidate_order(
                consensus_ranking[:8],
                [
                    build_candidate_local_view(
                        agent_id="typed_incidence_proposal_prefix",
                        formal_language=typed_incidence_view.formal_language,
                        scores={
                            key: float(len(typed_priority) - index)
                            for index, key in enumerate(typed_priority)
                        },
                    ),
                    build_candidate_local_view(
                        agent_id="newclid_bidirectional_proof_dag_family_frontier",
                        formal_language=proof_dag_view.formal_language,
                        scores={
                            key: float(len(proof_family_priority) - index)
                            for index, key in enumerate(proof_family_priority)
                        },
                    )
                ],
            )
            portfolio_order = tuple(
                dict.fromkeys((*reserved_prefix, *portfolio_order))
            )
        portfolio_rank = {key: index for index, key in enumerate(portfolio_order)}
        candidates.sort(key=lambda candidate: portfolio_rank[candidate.key])
        meet_cones = {}
        unified_search = None
        last_trace = sheaf_result.trace[-1] if sheaf_result.trace else None
        native_sheaf_audit = {
            "agents": [
                {
                    "agent_id": view.agent_id,
                    "formal_language": view.formal_language,
                    "local_dimension": view.dimension,
                    "participates_in_consensus": view in local_views,
                }
                for view in portfolio_views
            ],
            "consensus_agent_ids": [view.agent_id for view in coordination_views],
            "portfolio_agent_ids": [view.agent_id for view in portfolio_views],
            "restriction_edge_count": len(sheaf_result.edges),
            "shared_candidate_count": len(coordinated_scores),
            "iterations": len(sheaf_result.trace),
            "primal_residual": (
                last_trace.primal_residual if last_trace is not None else 0.0
            ),
            "dual_residual": (
                last_trace.dual_residual if last_trace is not None else 0.0
            ),
            "sheaf_residual": (
                last_trace.sheaf_residual if last_trace is not None else 0.0
            ),
            "truth_plane": "yuclid_native_certificate_replay_only",
            "exchange_layer": (
                "openmath_terms_over_mmt_theory_views"
                if candidate_alignment == "mmt-theory-view"
                else "exact_native_candidate_channels"
            ),
            "shared_channel_kinds": sorted(
                {
                    channel.kind
                    for edge in sheaf_result.edges
                    for channel in edge.channels
                }
            ),
            "timing_seconds": {
                "proof_dag": proof_dag_elapsed_seconds,
                "coordination": coordination_elapsed_seconds,
            },
            "candidate_order": "capability_preserving_consensus_plus_local_interleave",
            "proof_dag_specialist": (
                {
                    "candidate_count": len(proof_dag_view.preferences),
                    "reserved_consensus": candidate_promotion_limit,
                    "reserved_typed_incidence": typed_priority,
                    "family_frontier": proof_family_priority,
                    "queue": proof_dag_search.audit.to_dict(),
                    "iterative_deepening": proof_dag_search.to_dict(),
                }
                if proof_dag_view is not None and proof_dag_search is not None
                else None
            ),
            "local_top_candidates": [
                {
                    "agent_id": view.agent_id,
                    "candidates": sorted(
                        view.preferences,
                        key=lambda name: (-float(view.preferences[name]), name),
                    )[:12],
                }
                for view in portfolio_views
            ],
            "top_candidates": [
                {
                    "candidate": candidate.key,
                    "consensus_score": coordinated_scores.get(candidate.key, 0.0),
                }
                for candidate in candidates[:12]
            ],
        }
    elif candidate_alignment == "off":
        alignment_by_key = {}
        meet_cones = {}
        unified_search = None
        native_sheaf_audit = None
    elif candidate_alignment != "off":
        raise ValueError(f"unknown candidate alignment: {candidate_alignment}")
    if branch_limit > 0:
        family_order = (
            list(dict.fromkeys(candidate.family for candidate in candidates))
            + [
                family.name
                for family in families
                if family.name not in {candidate.family for candidate in candidates}
            ]
            if candidate_alignment in {
                "typed-atom",
                "proof-dag-meet",
                "proof-dag-lazy",
                "proof-dag-priority",
                "native-formal-sheaf",
                "mmt-theory-view",
            }
            else [family.name for family in families]
        )
        candidates = schema_first_score_fill(
            candidates,
            category=lambda candidate: candidate.family,
            category_order=family_order,
            limit=branch_limit,
        )
    alignment_values = tuple(alignment_by_key.values())
    if candidate_alignment == "typed-atom":
        direct_match_candidates = sum(
            item.direct_match_count > 0 for item in alignment_values
        )
        reachable_candidates = sum(
            item.best_relation_distance < UNREACHABLE_DISTANCE
            for item in alignment_values
        )
    elif candidate_alignment == "proof-dag-meet":
        direct_match_candidates = sum(item.has_meet for item in alignment_values)
        reachable_candidates = direct_match_candidates
    elif candidate_alignment == "proof-dag-lazy":
        direct_match_candidates = sum(item.has_meet for item in alignment_values)
        reachable_candidates = sum(
            item.predicate_distance < UNREACHABLE_DISTANCE
            for item in alignment_values
        )
    elif candidate_alignment == "proof-dag-priority":
        direct_match_candidates = sum(
            item.alignment.has_meet for item in alignment_values
        )
        reachable_candidates = sum(
            item.has_closed_structural_residual for item in alignment_values
        )
    elif candidate_alignment in {"native-formal-sheaf", "mmt-theory-view"}:
        direct_match_candidates = sum(
            item.direct_match_count > 0 for item in alignment_values
        )
        reachable_candidates = sum(
            item.best_relation_distance < UNREACHABLE_DISTANCE
            for item in alignment_values
        )
    else:
        direct_match_candidates = 0
        reachable_candidates = 0
    extension_audit = {
        "elapsed_seconds": time.perf_counter() - extension_started,
        "mode": candidate_gate,
        "candidate_enumeration": enumeration_audit,
        "relation_reachability": asdict(gate_result.audit),
        "selected_after_branch_limit": len(candidates),
        "typed_construction_contracts": {
            "enabled": candidate_contract_synthesis,
            "truth_plane": "candidate_proposal_only_native_replay_required",
            "obligation_branch_count": len(contract_obligation_branches),
            "runtime_requirement_gate": contract_requirement_gate,
            "candidate_plans": [
                {
                    "candidate": candidate.key,
                    "matched_obligation": str(candidate.matched_obligation),
                    "residual_frontier": [
                        str(atom) for atom in candidate.residual_frontier
                    ],
                    "residual_reduction": candidate.residual_reduction,
                    "fully_closes_branch": candidate.fully_closes_branch,
                    "requirements": [
                        str(atom) for atom in candidate.requirement_atoms
                    ],
                    "open_requirements": [
                        str(atom) for atom in candidate.open_requirements
                    ],
                    "plan_certificate_sha256": (
                        candidate.plan_certificate_sha256
                    ),
                    "matched_via_chart": candidate.matched_via_chart,
                    "chart_name": candidate.chart_name,
                    "chart_certificate_sha256": (
                        candidate.chart_certificate_sha256
                    ),
                    "chart_residual_rank": list(
                        contract_chart_rank_by_key.get(
                            candidate.key, ((10**9, 10**9, 10**9), False)
                        )[0]
                    ),
                    "chart_residual_reduced": contract_chart_rank_by_key.get(
                        candidate.key, ((10**9, 10**9, 10**9), False)
                    )[1],
                }
                for candidate in contract_candidates[:12]
            ],
            **asdict(contract_audit),
        },
        "numerical_incidence": {
            "mode": candidate_incidence,
            "truth_plane": "candidate_proposal_only",
            "oversample_per_family": (
                incidence_oversample_per_family
                if candidate_incidence == "hageo"
                else per_family_limit
            ),
            "workers": incidence_workers,
            "elapsed_seconds": incidence_elapsed_seconds,
            "preselect_limit": incidence_preselect_limit,
            "input_candidates_before_preselection": incidence_input_count,
            "candidates_after_preselection": len(candidates),
            "checked_candidates": len(incidence_by_key),
            "heuristic_candidates": sum(
                profile.is_heuristic_candidate
                for profile in incidence_by_key.values()
            ),
            "build_errors": dict(sorted(incidence_errors.items())),
            "top_candidates": [
                {
                    "candidate": candidate.key,
                    **incidence_by_key[candidate.key].to_dict(),
                }
                for candidate in candidates[:12]
                if candidate.key in incidence_by_key
            ],
            "selected_candidates": [
                {
                    "candidate": candidate.key,
                    "step_key": f"{candidate.key}->{output}",
                    "family": candidate.family,
                    **incidence_by_key[candidate.key].to_dict(),
                }
                for candidate in candidates
                if candidate.key in incidence_by_key
            ],
        },
        "candidate_alignment": {
            "mode": candidate_alignment,
            "direct_match_candidates": direct_match_candidates,
            "reachable_candidates": reachable_candidates,
            "cone_truncated_candidates": sum(
                item.truncated for item in alignment_values
                if candidate_alignment == "proof-dag-lazy"
            ) if candidate_alignment == "proof-dag-lazy" else sum(
                cone.truncated for cone in meet_cones.values()
            ),
            "cone_search_states": (
                sum(item.search_states for item in alignment_values)
                if candidate_alignment in {
                    "proof-dag-lazy",
                    "proof-dag-priority",
                }
                else sum(cone.search_states for cone in meet_cones.values())
            ),
            "unified_queue": (
                unified_search.audit.to_dict()
                if candidate_alignment == "proof-dag-priority"
                and unified_search is not None
                else None
            ),
            "iterative_deepening": (
                unified_iterative_search.to_dict()
                if candidate_alignment == "proof-dag-priority"
                and unified_iterative_search is not None
                else None
            ),
            "native_formal_sheaf": (
                native_sheaf_audit
                if candidate_alignment in {"native-formal-sheaf", "mmt-theory-view"}
                else None
            ),
            "top_candidates": [
                {
                    "candidate": candidate.key,
                    **alignment_by_key[candidate.key].to_dict(),
                    **(
                        {
                            "cone_search_states": meet_cones[
                                candidate.key
                            ].search_states,
                            "cone_fragment_count": len(
                                meet_cones[candidate.key].fragments
                            ),
                            "cone_truncated": meet_cones[
                                candidate.key
                            ].truncated,
                        }
                        if candidate.key in meet_cones
                        else {}
                    ),
                }
                for candidate in candidates[:12]
                if candidate.key in alignment_by_key
            ],
        },
    }
    return [
        ConstructionStep(
            candidate.family,
            output,
            candidate.inputs,
            candidate.structural_rank,
        )
        for candidate in candidates
    ], extension_audit


def select_diverse_beam(
    records: list[SearchRecord],
    beam_width: int,
    *,
    ranking: str,
    controller: DifferentiableProofController | None = None,
) -> list[SearchRecord]:
    if ranking in {
        "native-formal-sheaf",
        "native-formal-sheaf-portfolio",
        "unified-formal-sheaf-portfolio",
    }:
        valid = [record for record in records if record.error is None]
        if not valid:
            return []

        def record_key(record: SearchRecord) -> str:
            return "|".join(step.key for step in record.steps)

        def ordinal_scores(quality) -> dict[str, float]:
            values = {record_key(record): quality(record) for record in valid}
            levels = sorted(set(values.values()), reverse=True)
            denominator = max(1, len(levels) - 1)
            score_by_level = {
                level: 1.0 - index / denominator
                for index, level in enumerate(levels)
            }
            return {key: score_by_level[value] for key, value in values.items()}

        structural_scores = ordinal_scores(
            lambda record: tuple(
                -float(value) for value in record.steps[-1].structural_rank[:7]
            )
        )
        relation_scores = ordinal_scores(
            lambda record: (
                record.solved,
                record.relation_near_goal_count,
                record.relation_support_weight,
                record.relation_target_assertion_count,
                record.relation_transition_potential,
            )
        )
        algebra_scores = ordinal_scores(
            lambda record: (
                record.solved,
                record.ar_closed_goal_count,
                -record.ar_residual_support_size,
                -record.ar_residual_l1_weight,
                record.ar_known_rank,
            )
        )
        obligation_scores = ordinal_scores(
            lambda record: (
                record.solved,
                -len(record.open_relation_demands),
                -len(record.backward_obligations),
                record.goal_deduction_count,
            )
        )
        transition_scores = ordinal_scores(
            lambda record: (
                record.solved,
                record.relation_transition_potential,
                record.relation_transition_channel_coverage,
                -min(
                    (item.distance_to_goal for item in record.frontier_witnesses),
                    default=10**6,
                ),
            )
        )
        resource_scores = ordinal_scores(
            lambda record: (
                record.solved,
                -record.elapsed_seconds,
                -record.all_deduction_count,
            )
        )
        if ranking == "unified-formal-sheaf-portfolio":
            if controller is None:
                raise ValueError(f"{ranking} requires a differentiable controller")
            learned_local = {
                record_key(record): controller.score_record(record).local_scores
                for record in valid
            }
            structural_scores = {
                key: scores["structure"] for key, scores in learned_local.items()
            }
            relation_scores = {
                key: scores["closure"] for key, scores in learned_local.items()
            }
            transition_scores = {
                key: scores["transition"] for key, scores in learned_local.items()
            }
            algebra_scores = {
                key: scores["algebra"] for key, scores in learned_local.items()
            }
            obligation_scores = {
                key: scores["obligation"] for key, scores in learned_local.items()
            }
            resource_scores = {
                key: scores["cost"] for key, scores in learned_local.items()
            }
        polynomial_eligible = {
            record_key(record)
            for record in valid
            if {
                atom.predicate
                for atom in construction_relation_atoms(
                    record.steps[-1].family,
                    record.steps[-1].output,
                    record.steps[-1].inputs,
                )
            }
            <= POLYNOMIAL_RELATION_CHANNELS
        }
        views = [
            build_candidate_local_view(
                agent_id="tong_action",
                formal_language="typed construction action language",
                scores=structural_scores,
            ),
            build_candidate_local_view(
                agent_id="newclid_relation",
                formal_language="Newclid DD relation closure",
                scores=relation_scores,
            ),
            build_candidate_local_view(
                agent_id="newclid_ar",
                formal_language="Newclid algebraic-rule residual",
                scores=algebra_scores,
            ),
            build_candidate_local_view(
                agent_id="sygus_obligation",
                formal_language="typed open-obligation synthesis",
                scores=obligation_scores,
            ),
        ]
        if polynomial_eligible:
            views.append(
                build_candidate_local_view(
                    agent_id="gclc_wu",
                    formal_language="GCLC/Wu polynomial interface",
                    scores=algebra_scores,
                    eligible_candidates=polynomial_eligible,
                )
            )
        trust_by_agent = None
        rho = 1.0
        if ranking == "unified-formal-sheaf-portfolio":
            views.extend(
                (
                    build_candidate_local_view(
                        agent_id="newclid_transition",
                        formal_language="Newclid typed relation transitions",
                        scores=transition_scores,
                    ),
                    build_candidate_local_view(
                        agent_id="resource_scheduler",
                        formal_language="proof-circuit execution cost",
                        scores=resource_scores,
                    ),
                )
            )
            learned_trust = {
                name: softplus(value) + 0.05
                for name, value in controller.parameters.trust_logits.items()
            }
            trust_by_agent = {
                "tong_action": learned_trust["structure"],
                "newclid_relation": learned_trust["closure"],
                "newclid_transition": learned_trust["transition"],
                "newclid_ar": learned_trust["algebra"],
                "sygus_obligation": learned_trust["obligation"],
                "resource_scheduler": learned_trust["cost"],
            }
            if polynomial_eligible:
                trust_by_agent["gclc_wu"] = learned_trust["algebra"]
            rho = softplus(controller.parameters.log_rho) + 0.05
        coordinated_scores, _result = coordinate_candidate_scores(
            views,
            rho=rho,
            trust_by_agent=trust_by_agent,
        )
        sheaf_ranked = balanced_stratified_beam(
            valid,
            score=lambda record: (
                record.solved,
                coordinated_scores.get(record_key(record), 0.0),
            ),
            category=lambda record: record.steps[-1].family,
            stratum=lambda record: (
                tuple(step.key for step in record.steps[:-1]),
                record.steps[-1].family,
            ),
            limit=beam_width,
        )
        if ranking == "native-formal-sheaf":
            return sheaf_ranked

        # Preserve half of the exact residual policy.  Self-organization must
        # add capability before it is allowed to remove a proven search path.
        exact_budget = (beam_width + 1) // 2
        selected = select_diverse_beam(
            records,
            exact_budget,
            ranking="ar-residual-pareto",
        )
        for record in sheaf_ranked:
            if record not in selected:
                selected.append(record)
                if len(selected) == beam_width:
                    break
        return selected[:beam_width]
    if ranking in {"differentiable-consensus", "consensus-portfolio"}:
        if controller is None:
            raise ValueError(f"{ranking} requires a differentiable controller")
        valid = [record for record in records if record.error is None]
        common = {
            "category": lambda record: record.steps[-1].family,
            "stratum": lambda record: (
                tuple(step.key for step in record.steps[:-1]),
                record.steps[-1].family,
            ),
        }
        learned_score = lambda record: (
            record.solved,
            controller.score_record(record).score,
        )
        if ranking == "differentiable-consensus":
            return balanced_stratified_beam(
                valid,
                score=learned_score,
                limit=beam_width,
                **common,
            )

        # Capability-preserving portfolio: retain half of the exact residual
        # policy and let the differentiable circuit control the other half.
        exact_budget = (beam_width + 1) // 2
        learned_budget = beam_width - exact_budget
        selected = select_diverse_beam(
            records,
            exact_budget,
            ranking="ar-residual-pareto",
        )
        for record in balanced_stratified_beam(
            valid,
            score=learned_score,
            limit=max(learned_budget, 1),
            **common,
        ):
            if record not in selected:
                selected.append(record)
                if len(selected) == beam_width:
                    break
        if len(selected) < beam_width:
            for record in select_diverse_beam(
                records,
                beam_width,
                ranking="ar-residual-pareto",
            ):
                if record not in selected:
                    selected.append(record)
                    if len(selected) == beam_width:
                        break
        return selected[:beam_width]
    if ranking == "ar-residual-pareto":
        ar_score = lambda record: (
            record.solved,
            record.ar_closed_goal_count,
            -record.ar_residual_support_size,
            -record.ar_residual_l1_weight,
            record.relation_transition_potential,
        )
        frontier_score = lambda record: (
            record.solved,
            -min(
                (item.distance_to_goal for item in record.frontier_witnesses),
                default=10**6,
            ),
            max(
                (item.goal_support_overlap for item in record.frontier_witnesses),
                default=0,
            ),
            len(record.frontier_witnesses),
        )
        structural_score = lambda record: tuple(
            -float(value) for value in record.steps[-1].structural_rank[:7]
        )
        valid = [record for record in records if record.error is None]
        common = {
            "category": lambda record: record.steps[-1].family,
            "stratum": lambda record: (
                tuple(step.key for step in record.steps[:-1]),
                record.steps[-1].family,
            ),
        }
        structural_budget = (beam_width + 1) // 2
        remaining_budget = beam_width - structural_budget
        selected: list[SearchRecord] = []
        for record in sorted(valid, key=structural_score, reverse=True)[
            :structural_budget
        ]:
            selected.append(record)
        for score, budget in (
            (ar_score, (remaining_budget + 1) // 2),
            (frontier_score, remaining_budget // 2),
        ):
            for record in balanced_stratified_beam(
                valid, score=score, limit=budget, **common
            ):
                if record not in selected:
                    selected.append(record)
        if len(selected) < beam_width:
            for record in balanced_stratified_beam(
                valid, score=ar_score, limit=beam_width, **common
            ):
                if record not in selected:
                    selected.append(record)
                    if len(selected) == beam_width:
                        break
        return selected[:beam_width]
    if ranking == "proof-dag-residual":
        def proof_dag_score(record: SearchRecord) -> tuple[object, ...]:
            progress = record.proof_dag_progress
            increment = record.proof_dag_increment
            residual = progress.best_structural_residual_count
            return (
                record.solved,
                increment.newly_structurally_closed_branch_count,
                increment.newly_progressed_branch_count,
                increment.unique_exact_covered_atoms_gain,
                increment.max_exact_covered_atoms_gain,
                increment.support_overlap_gain,
                increment.support_improved_branch_count_gain,
                progress.structurally_closed_branch_count,
                -residual if residual >= 0 else -(10**6),
                progress.progressed_branch_count,
                progress.max_exact_covered_atoms,
                progress.unique_exact_covered_atoms,
                progress.support_improved_branch_count,
                progress.max_support_overlap_gain,
                progress.total_support_overlap_gain,
                record.relation_transition_potential,
            )

        return balanced_stratified_beam(
            [record for record in records if record.error is None],
            score=proof_dag_score,
            category=lambda record: record.steps[-1].family,
            stratum=lambda record: (
                tuple(step.key for step in record.steps[:-1]),
                record.steps[-1].family,
            ),
            limit=beam_width,
        )
    if ranking == "frontier-pareto":
        frontier_score = lambda record: (
            record.solved,
            -min(
                (item.distance_to_goal for item in record.frontier_witnesses),
                default=10**6,
            ),
            max(
                (item.goal_support_overlap for item in record.frontier_witnesses),
                default=0,
            ),
            len(record.frontier_witnesses),
            record.relation_transition_potential,
        )
        structural_score = lambda record: tuple(
            -float(value) for value in record.steps[-1].structural_rank[:7]
        )
        relation_budget = (beam_width + 1) // 2
        structural_budget = beam_width - relation_budget
        common = {
            "category": lambda record: record.steps[-1].family,
            "stratum": lambda record: (
                tuple(step.key for step in record.steps[:-1]),
                record.steps[-1].family,
            ),
        }
        selected = balanced_stratified_beam(
            [record for record in records if record.error is None],
            score=frontier_score,
            limit=relation_budget,
            **common,
        )
        structural = balanced_stratified_beam(
            [record for record in records if record.error is None],
            score=structural_score,
            limit=structural_budget,
            **common,
        )
        for record in structural:
            if record not in selected:
                selected.append(record)
        if len(selected) < beam_width:
            remainder = balanced_stratified_beam(
                [record for record in records if record.error is None],
                score=frontier_score,
                limit=beam_width,
                **common,
            )
            for record in remainder:
                if record not in selected:
                    selected.append(record)
                    if len(selected) == beam_width:
                        break
        return selected[:beam_width]
    if ranking == "relation":
        score = lambda record: (
            record.solved,
            record.relation_near_goal_count,
            record.relation_support_weight,
            record.relation_target_assertion_count,
            record.goal_deduction_count,
            record.all_deduction_count,
        )
    elif ranking == "frontier":
        score = lambda record: (
            record.solved,
            -min(
                (item.distance_to_goal for item in record.frontier_witnesses),
                default=10**6,
            ),
            max(
                (item.goal_support_overlap for item in record.frontier_witnesses),
                default=0,
            ),
            len(record.frontier_witnesses),
            record.relation_transition_potential,
            record.goal_deduction_count,
        )
    elif ranking == "relation-transition":
        score = lambda record: (
            record.solved,
            record.relation_transition_potential,
            record.relation_transition_channel_coverage,
            record.goal_deduction_count,
            record.all_deduction_count,
        )
    elif ranking == "closure":
        score = lambda record: (
            record.solved,
            record.goal_deduction_count,
            record.all_deduction_count,
        )
    else:
        raise ValueError(f"unknown beam ranking: {ranking}")
    # Preserve one candidate for every parent-path x next-family stratum before
    # filling by raw score.  Closure size alone systematically over-selects
    # repeated high-yield constructions (for example mirror after mirror) and
    # removes mixed construction chains before the next CEGIS round.
    return balanced_stratified_beam(
        [record for record in records if record.error is None],
        score=score,
        category=lambda record: record.steps[-1].family,
        stratum=lambda record: (
            tuple(step.key for step in record.steps[:-1]),
            record.steps[-1].family,
        ),
        limit=beam_width,
    )


def main() -> None:
    from worker.backend.yuclid_native_verifier import YuclidTimeoutError, verify_problem

    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--problem-name", required=True)
    parser.add_argument("--yuclid-exe", type=Path, required=True)
    parser.add_argument("--runtime-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--resume-progress",
        action="store_true",
        help="Restore verified candidate records from OUTPUT.progress.json.",
    )
    parser.add_argument(
        "--families",
        default=",".join(family.name for family in DEFAULT_POINT_FAMILIES),
    )
    parser.add_argument(
        "--family-set",
        choices=("core", "extended"),
        default="core",
        help="Named problem-independent construction grammar.",
    )
    parser.add_argument(
        "--goal-directed-families",
        action="store_true",
        help="Discard schemas whose declared output channels cannot reach the goal.",
    )
    parser.add_argument(
        "--candidate-gate",
        choices=(
            "off",
            "relation-reachability",
            "executable-precondition",
            "combined",
        ),
        default="off",
        help="Apply relation reachability and/or executable construction preflight.",
    )
    parser.add_argument(
        "--candidate-alignment",
        choices=(
            "off",
            "typed-atom",
            "proof-dag-meet",
            "proof-dag-lazy",
            "proof-dag-priority",
            "native-formal-sheaf",
            "mmt-theory-view",
        ),
        default="off",
        help=(
            "Rank by flat atoms, a fixed proof-DAG meet, or a residual-guided "
            "lazy proof-DAG meet, or one bidirectional priority queue."
        ),
    )
    parser.add_argument("--proof-dag-depth", type=int, default=2)
    parser.add_argument("--proof-dag-branches", type=int, default=128)
    parser.add_argument("--proof-dag-states", type=int, default=20_000)
    parser.add_argument(
        "--proof-dag-timeout-seconds",
        type=float,
        default=0.0,
        help=(
            "Truncate proof-DAG scheduling compilation after this wall time; "
            "zero leaves it unbounded. Native proof acceptance is unaffected."
        ),
    )
    parser.add_argument("--candidate-cone-depth", type=int, default=2)
    parser.add_argument("--candidate-cone-fragments", type=int, default=128)
    parser.add_argument("--candidate-cone-states", type=int, default=5_000)
    parser.add_argument("--candidate-cone-initial-states", type=int, default=64)
    parser.add_argument("--candidate-promotion-limit", type=int, default=8)
    parser.add_argument(
        "--candidate-cone-timeout-seconds",
        type=float,
        default=0.0,
        help=(
            "Truncate candidate/proof-DAG alignment after this wall time; "
            "zero leaves it unbounded. Native proof acceptance is unaffected."
        ),
    )
    parser.add_argument(
        "--candidate-incidence",
        choices=("off", "hageo"),
        default="off",
        help=(
            "Use numerical line/circle incidence only to prioritize auxiliary "
            "construction proposals; proof acceptance remains symbolic."
        ),
    )
    parser.add_argument("--incidence-tolerance", type=float, default=1e-7)
    parser.add_argument("--incidence-oversample-per-family", type=int, default=16)
    parser.add_argument(
        "--branch-build-mode",
        choices=("legacy", "prefix-replay", "incremental"),
        default="legacy",
        help="Choose whole-path replay or prefix-stable incremental state reuse.",
    )
    parser.add_argument("--per-family-limit", type=int, default=8)
    parser.add_argument(
        "--enumeration-limit-per-family",
        type=int,
        default=0,
        help=(
            "Inspect at most this many typed input tuples per construction family; "
            "zero keeps exhaustive family enumeration. Truncation is audited."
        ),
    )
    parser.add_argument("--branch-limit", type=int, default=32)
    parser.add_argument(
        "--generated-action-quotient",
        action="store_true",
        help=(
            "Deduplicate alpha-renamed, symmetry-equivalent construction DAG "
            "states and spend the same verification budget on the next ranked states."
        ),
    )
    parser.add_argument(
        "--generated-action-oversample-factor",
        type=int,
        default=4,
        help="Candidate oversampling used only before generated-action deduplication.",
    )
    parser.add_argument("--beam-width", type=int, default=7)
    parser.add_argument("--max-depth", type=int, default=2)
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument(
        "--yuclid-timeout-seconds",
        type=float,
        default=0.0,
        help=(
            "Right-censor one candidate after this many seconds; zero keeps "
            "the verifier unbounded. Timeouts are never counted as wrong proofs."
        ),
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--obligation-guided",
        action="store_true",
        help="Recompute point-level missing theorem premises after every branch.",
    )
    parser.add_argument(
        "--candidate-contract-synthesis",
        action="store_true",
        help=(
            "Compile coherent typed proof obligations into finite construction "
            "contracts. Candidate truth still requires native certificate replay."
        ),
    )
    parser.add_argument(
        "--contract-candidates-per-schema",
        type=int,
        default=32,
        help="Finite candidate cap for each typed construction contract.",
    )
    parser.add_argument(
        "--require-generated-input-after-first",
        action="store_true",
        help="Require every later morphism to consume at least one synthesized point.",
    )
    parser.add_argument("--ranking", choices=("structural", "random"), default="structural")
    parser.add_argument(
        "--beam-ranking",
        choices=(
            "closure",
            "relation",
            "relation-transition",
            "frontier",
            "frontier-pareto",
            "ar-residual-pareto",
            "native-formal-sheaf",
            "native-formal-sheaf-portfolio",
            "unified-formal-sheaf-portfolio",
            "differentiable-consensus",
            "consensus-portfolio",
            "proof-dag-residual",
        ),
        default="closure",
    )
    parser.add_argument(
        "--controller",
        type=Path,
        help="Frozen differentiable controller artifact for learned beam policies.",
    )
    parser.add_argument("--ar-profile", choices=("ratio-only", "standard", "all"), default="all")
    parser.add_argument(
        "--progress",
        choices=("all", "summary", "none"),
        default="all",
        help="Control console output; artifacts always retain the complete trace.",
    )
    args = parser.parse_args()
    progress_output = args.output.with_suffix(".progress.json")
    resume_payload: dict[str, Any] | None = None
    resume_record_payloads: list[dict[str, Any]] = []
    resume_scheduled_path_payloads: list[list[dict[str, Any]]] = []
    resume_scheduled_depth: int | None = None
    resume_checkpoint_sha256: str | None = None
    if args.resume_progress and progress_output.is_file():
        checkpoint_bytes = progress_output.read_bytes()
        resume_payload = json.loads(checkpoint_bytes)
        if resume_payload.get("problem_name") != args.problem_name:
            raise ValueError("resume checkpoint belongs to a different problem")
        resume_record_payloads = [
            item
            for item in resume_payload.get("records", ())
            if not item.get("right_censored")
        ]
        resume_scheduled_path_payloads = list(
            resume_payload.get("scheduled_paths", ())
        )
        raw_resume_depth = resume_payload.get("depth")
        resume_scheduled_depth = (
            int(raw_resume_depth)
            if raw_resume_depth is not None and resume_scheduled_path_payloads
            else None
        )
        resume_checkpoint_sha256 = hashlib.sha256(checkpoint_bytes).hexdigest()
        if not resume_record_payloads and args.output.is_file():
            completed_bytes = args.output.read_bytes()
            completed_payload = json.loads(completed_bytes)
            if completed_payload.get("problem_name") != args.problem_name:
                raise ValueError("resume artifact belongs to a different problem")
            resume_record_payloads = list(completed_payload.get("records", ()))
            resume_checkpoint_sha256 = hashlib.sha256(completed_bytes).hexdigest()
    experiment_started_at = time.perf_counter()

    def checkpoint(
        stage: str,
        *,
        status: str = "running",
        **details: Any,
    ) -> None:
        if resume_record_payloads and "records" not in details:
            details = {
                "resumed_record_count": len(resume_record_payloads),
                "records": resume_record_payloads,
                **details,
            }
        write_json_atomic(
            progress_output,
            {
                "status": status,
                "stage": stage,
                "problem_name": args.problem_name,
                "elapsed_seconds": time.perf_counter() - experiment_started_at,
                **details,
            },
        )

    checkpoint("runtime_initialization")
    controller = (
        DifferentiableProofController.load(args.controller.resolve())
        if args.controller is not None
        else None
    )
    if args.beam_ranking in {
        "differentiable-consensus",
        "consensus-portfolio",
        "unified-formal-sheaf-portfolio",
    } and controller is None:
        parser.error(f"--beam-ranking {args.beam_ranking} requires --controller")

    available_families = (
        EXTENDED_POINT_FAMILIES if args.family_set == "extended" else DEFAULT_POINT_FAMILIES
    )
    requested = tuple(name.strip() for name in args.families.split(",") if name.strip())
    if args.family_set == "extended" and args.families == ",".join(
        family.name for family in DEFAULT_POINT_FAMILIES
    ):
        requested = tuple(family.name for family in EXTENDED_POINT_FAMILIES)
    family_map = {family.name: family for family in available_families}
    unknown = sorted(set(requested) - set(family_map))
    if unknown:
        raise ValueError(f"unknown families: {unknown}")
    families = tuple(family_map[name] for name in requested)

    checkpoint("input_elaboration")
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
    checkpoint("baseline_native_verification")
    try:
        baseline = verify_problem(
            base_problem,
            yuclid_exe=args.yuclid_exe.resolve(),
            ar_profile=args.ar_profile,
            timeout_seconds=(
                args.yuclid_timeout_seconds
                if args.yuclid_timeout_seconds > 0
                else None
            ),
        )
    except YuclidTimeoutError as exc:
        checkpoint(
            "baseline_native_verification",
            status="right_censored",
            right_censored_count=1,
            timeout_seconds=exc.timeout_seconds,
            truth_plane="no_result",
        )
        if args.progress != "none":
            print(
                "baseline native verification was right-censored; "
                f"checkpoint={progress_output}",
                flush=True,
            )
        return
    checkpoint(
        "baseline_native_verification_completed",
        baseline_solved=baseline.solved,
        baseline_all_deduction_count=baseline.all_deduction_count,
        baseline_goal_deduction_count=baseline.goal_deduction_count,
    )
    baseline_assertion_keys = yuclid_assertion_keys(baseline.payload)
    (
        base_points,
        base_graph,
        base_role_graph,
        base_role_weights,
        goal_multiplicity,
    ) = formulation_structure(formulation)
    goal_channels = set()
    for goal in formulation.goals:
        raw_name = getattr(goal, "name", None)
        if hasattr(raw_name, "value"):
            raw_name = raw_name.value
        if not raw_name:
            raw_name = str(goal).split()[0]
        goal_channels.add(str(raw_name))
    goal_support = set(goal_multiplicity)
    proof_relevance = proof_hypergraph_relevance(
        baseline.payload,
        goal_support,
    )
    goal_atoms = formulation_goal_atoms(formulation)
    baseline_ar_residual = yuclid_ar_residual(
        baseline.payload,
        ((atom.predicate, atom.arguments) for atom in goal_atoms),
    )
    rule_theorems = native_rule_theorems()
    baseline_facts = tuple(
        Atom(predicate, points)
        for predicate, points in yuclid_assertion_keys(baseline.payload)
    )
    checkpoint("open_proof_dag_compilation")
    proof_dags = (
        tuple(
            compile_open_proof_dag(
                baseline_facts,
                goal,
                rule_theorems,
                max_rule_depth=args.proof_dag_depth,
                max_branches=args.proof_dag_branches,
                max_search_states=args.proof_dag_states,
                max_wall_seconds=(
                    args.proof_dag_timeout_seconds
                    if args.proof_dag_timeout_seconds > 0
                    else None
                ),
            )
            for goal in goal_atoms
        )
        if (
            args.candidate_alignment in {
                "proof-dag-meet",
                "proof-dag-lazy",
                "proof-dag-priority",
                "native-formal-sheaf",
                "mmt-theory-view",
            }
            or args.beam_ranking == "proof-dag-residual"
        )
        else ()
    )
    proof_dag_branches = tuple(
        branch for dag in proof_dags for branch in dag.open_branches
    )
    baseline_obligations, baseline_demands = (
        proof_state_obligations(baseline.payload, goal_atoms, rule_theorems)
        if args.obligation_guided
        else ((), ())
    )
    checkpoint(
        "open_proof_dag_compilation_completed",
        proof_dag_count=len(proof_dags),
        open_branch_count=len(proof_dag_branches),
        open_demand_count=len(baseline_demands),
    )
    contract_obligation_branches = tuple(
        tuple(branch.frontier)
        for branch in proof_dag_branches
        if branch.frontier
    )
    if not contract_obligation_branches and baseline_demands:
        contract_obligation_branches = (tuple(baseline_demands),)
    if not contract_obligation_branches and goal_atoms:
        contract_obligation_branches = (tuple(goal_atoms),)
    rule_channels = [
        (
            [premise.name for premise in rule.premises],
            [conclusion.name for conclusion in rule.conclusions],
        )
        for rule in DEFAULT_RULES
    ]
    transition_distances = backward_relation_distances(
        rule_channels,
        goal_channels=goal_channels,
    )
    if args.goal_directed_families:
        families = goal_relevant_families(families, transition_distances)

    prefix_cache = PrefixStateCache(
        base_problem,
        key=lambda step: step.key,
        transition=lambda parent, step, path: extend_prefix_branch(
            parent, step, path, seed=args.seed
        ),
    )
    baseline_proof_dag_progress = assess_native_proof_dag_progress(
        baseline_facts,
        proof_dag_branches,
        baseline_facts=baseline_facts,
    )
    progress_by_path: dict[tuple[str, ...], NativeProofDAGProgress] = {
        (): baseline_proof_dag_progress
    }
    resumed_records = tuple(
        search_record_from_dict(item) for item in resume_record_payloads
    )

    resumed_scheduled_paths = (
        tuple(
            construction_path_from_payload(item)
            for item in resume_scheduled_path_payloads
        )
        if resume_scheduled_depth is not None
        else ()
    )
    resumed_records_by_depth: dict[int, list[SearchRecord]] = defaultdict(list)
    for record in resumed_records:
        resumed_records_by_depth[len(record.steps)].append(record)
        progress_by_path[tuple(step.key for step in record.steps)] = (
            record.proof_dag_progress
        )
    frontier: list[tuple[tuple[ConstructionStep, ...], tuple[Atom, ...]]] = [
        (tuple(), baseline_demands)
    ]
    all_records: list[SearchRecord] = []
    candidate_gate_audits: list[dict[str, Any]] = []
    preflight_checked_count = 0
    preflight_retained_count = 0
    preflight_rejected_by_error: dict[str, int] = defaultdict(int)
    solved_steps: tuple[ConstructionStep, ...] | None = None
    seen_generated_action_states: set[str] = set()
    generated_action_audit: dict[str, Any] = {
        "enabled": bool(args.generated_action_quotient),
        "quotient": (
            "alpha-renaming+declared-input-symmetry+independent-action-order"
        ),
        "oversample_factor": (
            max(1, args.generated_action_oversample_factor)
            if args.generated_action_quotient
            else 1
        ),
        "normalized_candidate_paths": 0,
        "certificate_replay_failures": 0,
        "invalid_paths": 0,
        "equivalent_paths_skipped": 0,
        "scheduled_unique_paths": 0,
        "not_claimed": [
            "numeric-branch-equivalence",
            "generated-point-coordinate-equality",
            "numeric-branch-search-completeness",
            "native-proof-outcome-equivalence",
        ],
    }
    if args.generated_action_quotient:
        for record in resumed_records:
            normalized = normalize_construction_actions(record.steps)
            if normalized.certificate is not None:
                seen_generated_action_states.add(
                    normalized.certificate.semantic_state_key
                )
    for depth in range(1, args.max_depth + 1):
        layer: list[SearchRecord] = list(resumed_records_by_depth.get(depth, ()))
        restored_signatures = {
            tuple(step.key for step in record.steps) for record in layer
        }
        checkpoint(
            "candidate_enumeration",
            depth=depth,
            frontier_count=len(frontier),
            evaluated_path_count=len(all_records) + len(layer),
        )
        seen_paths: set[tuple[str, ...]] = set()
        candidate_paths: list[tuple[ConstructionStep, ...]] = []
        if resume_scheduled_depth == depth:
            candidate_paths = [
                path
                for path in resumed_scheduled_paths
                if tuple(step.key for step in path) not in restored_signatures
            ]
            seen_paths.update(
                tuple(step.key for step in path) for path in candidate_paths
        )
        for parent, parent_demands in (() if resume_scheduled_depth == depth else frontier):
            try:
                if args.branch_build_mode == "incremental":
                    current_problem = prefix_cache.build(parent)
                elif args.branch_build_mode == "prefix-replay":
                    current_problem = build_prefix_stable_branch(
                        base_problem, parent, seed=args.seed
                    )
                else:
                    current_problem = None
            except Exception as exc:
                candidate_gate_audits.append(
                    {
                        "depth": depth,
                        "parent_path": [step.key for step in parent],
                        "status": "invalid_parent_prefix_rejected",
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
                continue
            candidate_target_channels = {
                demand.predicate.lower() for demand in parent_demands
            } or {channel.lower() for channel in goal_channels}
            candidate_reachable_channels = set(
                backward_relation_distances(
                    rule_channels,
                    goal_channels=candidate_target_channels,
                )
            )
            candidate_relation_distances = (
                {
                    target: backward_relation_distances(
                        rule_channels,
                        goal_channels={target},
                    )
                    for target in candidate_target_channels
                }
                if args.candidate_alignment
                in {"typed-atom", "native-formal-sheaf", "mmt-theory-view"}
                else {}
            )
            extensions, gate_audit = candidate_extensions(
                base_problem=base_problem,
                base_points=base_points,
                base_graph=base_graph,
                base_role_graph=base_role_graph,
                base_role_weights=base_role_weights,
                goal_multiplicity=goal_multiplicity,
                proof_relevance=proof_relevance,
                steps=parent,
                families=families,
                per_family_limit=args.per_family_limit,
                branch_limit=(
                    args.branch_limit
                    * max(1, args.generated_action_oversample_factor)
                    if args.generated_action_quotient
                    else args.branch_limit
                ),
                ranking=args.ranking,
                seed=branch_seed(args.seed, parent),
                relation_demands=parent_demands,
                require_generated_input=args.require_generated_input_after_first,
                candidate_gate=args.candidate_gate,
                candidate_reachable_channels=candidate_reachable_channels,
                candidate_target_channels=candidate_target_channels,
                candidate_alignment=args.candidate_alignment,
                candidate_relation_distances=candidate_relation_distances,
                proof_dag_branches=proof_dag_branches,
                proof_dags=proof_dags,
                proof_dag_goals=goal_atoms,
                proof_dag_facts=baseline_facts,
                proof_dag_theorems=rule_theorems,
                candidate_cone_depth=args.candidate_cone_depth,
                candidate_cone_fragments=args.candidate_cone_fragments,
                candidate_cone_states=args.candidate_cone_states,
                candidate_cone_initial_states=args.candidate_cone_initial_states,
                candidate_promotion_limit=args.candidate_promotion_limit,
                candidate_incidence=args.candidate_incidence,
                incidence_tolerance=args.incidence_tolerance,
                incidence_oversample_per_family=(
                    args.incidence_oversample_per_family
                ),
                current_problem=current_problem,
                construction_seed=args.seed,
                candidate_contract_synthesis=args.candidate_contract_synthesis,
                contract_candidates_per_schema=(
                    args.contract_candidates_per_schema
                ),
                contract_obligation_branches=contract_obligation_branches,
                enumeration_limit_per_family=args.enumeration_limit_per_family,
                candidate_cone_timeout_seconds=(
                    args.candidate_cone_timeout_seconds
                ),
            )
            candidate_gate_audits.append(
                {
                    "depth": depth,
                    "parent_path": [step.key for step in parent],
                    **gate_audit,
                }
            )
            parent_scheduled = 0
            for extension in extensions:
                steps = (*parent, extension)
                signature = tuple(step.key for step in steps)
                if signature in seen_paths or signature in restored_signatures:
                    continue
                if args.generated_action_quotient:
                    generated_action_audit["normalized_candidate_paths"] += 1
                    normalized = normalize_construction_actions(steps)
                    if normalized.certificate is None:
                        generated_action_audit["invalid_paths"] += 1
                        continue
                    if verify_construction_action_certificate(
                        normalized.certificate
                    ):
                        generated_action_audit["certificate_replay_failures"] += 1
                        continue
                    state_key = normalized.certificate.semantic_state_key
                    if state_key in seen_generated_action_states:
                        generated_action_audit["equivalent_paths_skipped"] += 1
                        continue
                    seen_generated_action_states.add(state_key)
                seen_paths.add(signature)
                candidate_paths.append(steps)
                parent_scheduled += 1
                generated_action_audit["scheduled_unique_paths"] += 1
                if parent_scheduled >= args.branch_limit:
                    break
        checkpoint(
            "candidate_verification",
            depth=depth,
            scheduled_path_count=len(candidate_paths),
            evaluated_path_count=len(all_records) + len(layer),
            current_depth_evaluated_path_count=len(layer),
            prior_depth_evaluated_path_count=len(all_records),
            resumed_path_count=len(restored_signatures),
            resumed_scheduled_paths=resume_scheduled_depth == depth,
            scheduled_paths=[
                construction_path_to_payload(path) for path in candidate_paths
            ],
            records=[asdict(record) for record in (*all_records, *layer)],
        )
        batch_size = max(1, args.max_workers)
        layer_solved = any(record.solved for record in layer)
        if layer_solved:
            candidate_paths = []
        with ThreadPoolExecutor(max_workers=batch_size) as executor:
            for batch_start in range(0, len(candidate_paths), batch_size):
                batch = candidate_paths[batch_start : batch_start + batch_size]
                prepared_problems: dict[tuple[str, ...], Any] = {}
                if args.candidate_gate in {"executable-precondition", "combined"}:
                    executable_batch: list[tuple[ConstructionStep, ...]] = []
                    for steps in batch:
                        preflight_checked_count += 1
                        try:
                            if args.branch_build_mode == "incremental":
                                prepared_problem = prefix_cache.build(steps)
                            elif args.branch_build_mode == "prefix-replay":
                                prepared_problem = build_prefix_stable_branch(
                                    base_problem, steps, seed=args.seed
                                )
                            else:
                                prepared_problem = build_branch(
                                    base_problem, steps, seed=args.seed
                                )
                        except Exception as exc:
                            preflight_rejected_by_error[type(exc).__name__] += 1
                        else:
                            signature = tuple(step.key for step in steps)
                            prepared_problems[signature] = (
                                prepared_problem.model_copy(deep=True)
                                if args.branch_build_mode == "incremental"
                                else prepared_problem
                            )
                            executable_batch.append(steps)
                            preflight_retained_count += 1
                    batch = executable_batch
                if not batch:
                    continue
                futures = {
                    executor.submit(
                        evaluate_steps,
                        base_problem,
                        steps,
                        seed=args.seed,
                        yuclid_exe=args.yuclid_exe.resolve(),
                        ar_profile=args.ar_profile,
                        goal_channels=goal_channels,
                        goal_support=goal_support,
                        baseline_assertion_keys=baseline_assertion_keys,
                        transition_distances=transition_distances,
                        goal_atoms=goal_atoms,
                        rule_theorems=rule_theorems,
                        proof_dag_branches=proof_dag_branches,
                        parent_proof_dag_progress=progress_by_path[
                            tuple(step.key for step in steps[:-1])
                        ],
                        obligation_guided=args.obligation_guided,
                        yuclid_timeout_seconds=(
                            args.yuclid_timeout_seconds
                            if args.yuclid_timeout_seconds > 0
                            else None
                        ),
                        prepared_problem=prepared_problems.get(
                            tuple(step.key for step in steps)
                        ),
                    ): steps
                    for steps in batch
                }
                batch_records = [future.result() for future in as_completed(futures)]
                batch_records.sort(
                    key=lambda record: tuple(step.key for step in record.steps)
                )
                for record in batch_records:
                    layer.append(record)
                    progress_by_path[
                        tuple(step.key for step in record.steps)
                    ] = record.proof_dag_progress
                    if args.progress == "all":
                        print(
                            f"depth={depth} solved={record.solved} "
                            f"closure={record.all_deduction_count} "
                            f"path={[step.key for step in record.steps]}",
                            flush=True,
                        )
                completed_records = [*all_records, *layer]
                write_json_atomic(
                    progress_output,
                    {
                        "status": "running",
                        "stage": "candidate_verification",
                        "problem_name": args.problem_name,
                        "depth": depth,
                        "scheduled_path_count": len(candidate_paths),
                        "evaluated_path_count": len(completed_records),
                        "current_depth_evaluated_path_count": len(layer),
                        "prior_depth_evaluated_path_count": len(all_records),
                        "scheduled_paths": [
                            construction_path_to_payload(path)
                            for path in candidate_paths
                        ],
                        "right_censored_count": sum(
                            record.right_censored for record in completed_records
                        ),
                        "records": [asdict(record) for record in completed_records],
                    },
                )
                if any(record.solved for record in batch_records):
                    layer_solved = True
                    break
        if layer_solved and args.progress != "none":
            print(f"depth={depth} native proof found; stopping unused candidates", flush=True)
        layer.sort(key=lambda record: tuple(step.key for step in record.steps))
        all_records.extend(layer)
        solved_records = [record for record in layer if record.solved]
        if solved_records:
            solved_steps = solved_records[0].steps
        if solved_steps is not None or depth == args.max_depth:
            break
        frontier = [
            (record.steps, record.open_relation_demands)
            for record in select_diverse_beam(
                layer,
                args.beam_width,
                ranking=args.beam_ranking,
                controller=controller,
            )
        ]

    second_stage_descriptions = {
        "relation": "yuclid_novel_nonconstruction_target_relation_diverse_beam",
        "relation-transition": "yuclid_native_rule_transition_potential_diverse_beam",
        "ar-residual-pareto": "exact_ar_residual_frontier_structural_pareto_beam",
        "native-formal-sheaf": "heterogeneous_native_local_view_sheaf_admm_beam",
        "native-formal-sheaf-portfolio": (
            "half_exact_residual_half_heterogeneous_native_sheaf_beam"
        ),
        "unified-formal-sheaf-portfolio": (
            "half_exact_residual_half_differentiable_heterogeneous_formal_language_sheaf_beam"
        ),
        "frontier-pareto": "yuclid_native_frontier_and_structural_pareto_beam",
        "frontier": "yuclid_native_frontier_witness_diverse_beam",
        "closure": "yuclid_closure_growth_diverse_beam",
        "differentiable-consensus": "frozen_differentiable_consensus_diverse_beam",
        "consensus-portfolio": "half_exact_residual_half_differentiable_consensus_beam",
        "proof-dag-residual": (
            "exact_native_closure_progress_on_coherent_open_proof_dag_branches"
        ),
    }
    measured_candidate_gate_audits = [
        audit
        for audit in candidate_gate_audits
        if "relation_reachability" in audit
    ]
    invalid_parent_prefix_audits = [
        audit
        for audit in candidate_gate_audits
        if audit.get("status") == "invalid_parent_prefix_rejected"
    ]
    artifact: dict[str, Any] = {
        "experiment": "newclid_dynamic_typed_construction_stalk_no_llm",
        "protocol": {
            "uses_external_llm": False,
            "uses_dataset_auxiliary_clauses": False,
            "uses_problem_id_in_search": False,
            "resume": {
                "enabled": args.resume_progress,
                "checkpoint_sha256": resume_checkpoint_sha256,
                "restored_verified_record_count": len(resumed_records),
            },
            "families": [asdict(family) for family in families],
            "first_stage_ranking": (
                "goal_support_incidence"
                if args.ranking == "structural"
                else "seeded_random"
            ),
            "ranking": args.ranking,
            "second_stage_ranking": second_stage_descriptions[args.beam_ranking],
            "beam_ranking": args.beam_ranking,
            "differentiable_controller": (
                {
                    "path": str(args.controller.resolve()),
                    "parameter_count": controller.parameters.parameter_count,
                    "truth_plane": "native_certificate_replay_only",
                }
                if controller is not None and args.controller is not None
                else None
            ),
            "unified_architecture": (
                unified_geometry_architecture_manifest()
                if args.beam_ranking == "unified-formal-sheaf-portfolio"
                else None
            ),
            "goal_channels": sorted(goal_channels),
            "candidate_gate": args.candidate_gate,
            "candidate_alignment": args.candidate_alignment,
            "candidate_incidence": {
                "mode": args.candidate_incidence,
                "tolerance": args.incidence_tolerance,
                "oversample_per_family": args.incidence_oversample_per_family,
                "truth_plane": "candidate_proposal_only",
            },
            "proof_dag_budget": {
                "depth": args.proof_dag_depth,
                "branches_per_goal": args.proof_dag_branches,
                "states_per_goal": args.proof_dag_states,
                "wall_seconds_per_goal": args.proof_dag_timeout_seconds,
            },
            "candidate_forward_cone_budget": {
                "depth": args.candidate_cone_depth,
                "fragments": args.candidate_cone_fragments,
                "states": args.candidate_cone_states,
                "wall_seconds": args.candidate_cone_timeout_seconds,
            },
            "branch_build_mode": args.branch_build_mode,
            "proof_hypergraph_relevance": proof_relevance,
            "same_morphism_input_orbit_priority": True,
            "obligation_guided": args.obligation_guided,
            "typed_construction_contracts": {
                "enabled": args.candidate_contract_synthesis,
                "candidates_per_schema": args.contract_candidates_per_schema,
                "obligation_branch_count": len(contract_obligation_branches),
                "truth_plane": "native_certificate_replay_only",
            },
            "require_generated_input_after_first": (
                args.require_generated_input_after_first
            ),
            "baseline_backward_obligations": [
                item.to_dict() for item in baseline_obligations
            ],
            "baseline_open_relation_demands": [
                {"predicate": item.predicate, "arguments": list(item.arguments)}
                for item in baseline_demands
            ],
            "backward_relation_distances": transition_distances,
            "per_family_limit": args.per_family_limit,
            "enumeration_limit_per_family": args.enumeration_limit_per_family,
            "branch_limit": args.branch_limit,
            "generated_action_quotient": generated_action_audit,
            "beam_width": args.beam_width,
            "max_depth": args.max_depth,
            "max_workers": args.max_workers,
            "yuclid_timeout_seconds": args.yuclid_timeout_seconds,
            "seed": args.seed,
            "ar_profile": args.ar_profile,
        },
        "problem_name": args.problem_name,
        "normalization": asdict(normalization),
        "baseline": {
            "solved": baseline.solved,
            "all_deduction_count": baseline.all_deduction_count,
            "goal_deduction_count": baseline.goal_deduction_count,
            "ar_residual": asdict(baseline_ar_residual),
        },
        "visible_formulation": str(formulation),
        "constructed_formulation": (
            str(augment_formulation(formulation, solved_steps))
            if solved_steps is not None
            else None
        ),
        "solved": solved_steps is not None,
        "solved_path": [step.key for step in solved_steps] if solved_steps else None,
        "evaluated_paths": len(all_records),
        "error_count": sum(record.error is not None for record in all_records),
        "right_censored_count": sum(
            record.right_censored for record in all_records
        ),
        "candidate_gate": {
            "mode": args.candidate_gate,
            "enumerated_candidates": sum(
                audit["relation_reachability"]["input_count"]
                for audit in measured_candidate_gate_audits
            ),
            "retained_candidates": sum(
                audit["selected_after_branch_limit"]
                for audit in measured_candidate_gate_audits
            ) - sum(preflight_rejected_by_error.values()),
            "relation_retained_candidates": sum(
                audit["relation_reachability"]["retained_count"]
                for audit in measured_candidate_gate_audits
            ),
            "rejected_candidates": sum(
                audit["relation_reachability"]["rejected_count"]
                for audit in measured_candidate_gate_audits
            ) + sum(preflight_rejected_by_error.values()),
            "selected_after_branch_limit": sum(
                audit["selected_after_branch_limit"]
                for audit in measured_candidate_gate_audits
            ),
            "preflight_checked_count": preflight_checked_count,
            "preflight_retained_count": preflight_retained_count,
            "preflight_rejected_count": sum(
                preflight_rejected_by_error.values()
            ),
            "preflight_rejected_by_error": tuple(
                sorted(preflight_rejected_by_error.items())
            ),
            "fail_open_count": sum(
                audit["relation_reachability"]["fail_open_reason"] is not None
                for audit in measured_candidate_gate_audits
            ),
            "invalid_parent_prefix_count": len(invalid_parent_prefix_audits),
            "audits": candidate_gate_audits,
        },
        "candidate_alignment": {
            "mode": args.candidate_alignment,
            "direct_match_candidates": sum(
                audit["candidate_alignment"]["direct_match_candidates"]
                for audit in measured_candidate_gate_audits
            ),
            "reachable_candidates": sum(
                audit["candidate_alignment"]["reachable_candidates"]
                for audit in measured_candidate_gate_audits
            ),
            "cone_truncated_candidates": sum(
                audit["candidate_alignment"]["cone_truncated_candidates"]
                for audit in measured_candidate_gate_audits
            ),
            "cone_search_states": sum(
                audit["candidate_alignment"]["cone_search_states"]
                for audit in measured_candidate_gate_audits
            ),
            "proof_dags": [dag.to_dict() for dag in proof_dags],
        },
        "candidate_incidence": {
            "mode": args.candidate_incidence,
            "checked_candidates": sum(
                audit["numerical_incidence"]["checked_candidates"]
                for audit in measured_candidate_gate_audits
            ),
            "heuristic_candidates": sum(
                audit["numerical_incidence"]["heuristic_candidates"]
                for audit in measured_candidate_gate_audits
            ),
            "build_errors": dict(
                sorted(
                    (
                        error,
                        sum(
                            audit["numerical_incidence"]["build_errors"].get(
                                error, 0
                            )
                            for audit in measured_candidate_gate_audits
                        ),
                    )
                    for error in {
                        key
                        for audit in measured_candidate_gate_audits
                        for key in audit["numerical_incidence"]["build_errors"]
                    }
                )
            ),
            "truth_plane": "yuclid_native_certificate_replay_only",
        },
        "prefix_state_cache": asdict(prefix_cache.audit),
        "records": [asdict(record) for record in all_records],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if solved_steps is not None:
        if args.branch_build_mode == "incremental":
            confirmation_problem = prefix_cache.build(solved_steps).model_copy(
                deep=True
            )
        elif args.branch_build_mode == "prefix-replay":
            confirmation_problem = build_prefix_stable_branch(
                base_problem, solved_steps, seed=args.seed
            )
        else:
            confirmation_problem = build_branch(
                base_problem, solved_steps, seed=args.seed
            )
        confirmation = verify_problem(
            confirmation_problem,
            yuclid_exe=args.yuclid_exe.resolve(),
            ar_profile=args.ar_profile,
        )
        proof_path = args.output.with_suffix(".proof.json")
        proof_path.write_text(
            json.dumps(confirmation.payload, indent=2) + "\n", encoding="utf-8"
        )
        artifact["confirmation"] = {
            "solved": confirmation.solved,
            "status": confirmation.status,
            "all_deduction_count": confirmation.all_deduction_count,
            "goal_deduction_count": confirmation.goal_deduction_count,
            "input_sha256": confirmation.input_sha256,
            "proof_sha256": confirmation.proof_sha256,
            "proof_path": proof_path.resolve().relative_to(ROOT).as_posix(),
        }
    write_json_atomic(args.output, artifact)
    write_json_atomic(
        progress_output,
        {
            "status": "completed",
            "problem_name": args.problem_name,
            "solved": artifact["solved"],
            "evaluated_path_count": artifact["evaluated_paths"],
            "right_censored_count": artifact["right_censored_count"],
            "final_artifact": args.output.resolve().relative_to(ROOT).as_posix(),
        },
    )
    if args.progress != "none":
        print(
            json.dumps(
                {
                    "solved": artifact["solved"],
                    "solved_path": artifact["solved_path"],
                    "evaluated_paths": artifact["evaluated_paths"],
                    "error_count": artifact["error_count"],
                    "candidate_gate": artifact["candidate_gate"],
                    "candidate_alignment": artifact["candidate_alignment"],
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
