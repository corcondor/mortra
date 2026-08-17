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
    synthesize_backward_obligations,
)
from worker.backend.geometry_ar_residual import yuclid_ar_residual
from worker.backend.differentiable_proof_controller import (
    DifferentiableProofController,
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
    goal_relevant_families,
    prioritize_morphism_orbit,
    proof_hypergraph_point_relevance,
    schema_first_score_fill,
)


DEFINITIONS = JGEXDefinition.to_dict(ALL_JGEX_CONSTRUCTIONS)


@dataclass(frozen=True)
class ConstructionStep:
    family: str
    output: str
    inputs: tuple[str, ...]
    structural_rank: tuple[object, ...] = ()

    @property
    def key(self) -> str:
        return f"{self.family}({','.join(self.inputs)})->{self.output}"


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
    elapsed_seconds: float
    error: str | None = None


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
    """Expose Newclid's published rule bank as typed Horn hyperedges."""

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
    return tuple(theorems)


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
        obligations.extend(
            synthesize_backward_obligations(
                facts,
                goal,
                theorems,
                max_open_premises=4,
                max_states_per_rule=192,
                max_results=max_results,
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
    obligation_guided: bool,
) -> SearchRecord:
    from worker.backend.yuclid_native_verifier import verify_problem

    started = time.perf_counter()
    try:
        problem = build_branch(base_problem, steps, seed=seed)
        verification = verify_problem(
            problem, yuclid_exe=yuclid_exe, ar_profile=ar_profile
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
            time.perf_counter() - started,
            str(exc),
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
) -> list[ConstructionStep]:
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
    current_problem = build_branch(base_problem, steps, seed=seed)
    coordinates = {
        str(point.name): (float(point.num.x), float(point.num.y))
        for point in current_problem.points
    }
    candidates = enumerate_typed_candidates(
        points=tuple(points),
        graph=graph,
        goal_multiplicity=goal_multiplicity,
        proof_relevance=proof_relevance,
        generated_points=generated,
        used_keys=used,
        families=families,
        per_family_limit=per_family_limit,
        ranking=ranking,
        seed=seed,
        coordinates=coordinates,
        orbit_family=steps[-1].family if steps else None,
        orbit_inputs=steps[-1].inputs if steps else (),
        relation_demands=relation_demands,
        role_graph=role_graph,
        role_weights=role_weights,
        required_input_points=(generated if require_generated_input else set()),
    )
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
    if branch_limit > 0:
        family_order = [family.name for family in families]
        candidates = schema_first_score_fill(
            candidates,
            category=lambda candidate: candidate.family,
            category_order=family_order,
            limit=branch_limit,
        )
    output = next_point_name(points)
    return [
        ConstructionStep(
            candidate.family,
            output,
            candidate.inputs,
            candidate.structural_rank,
        )
        for candidate in candidates
    ]


def select_diverse_beam(
    records: list[SearchRecord],
    beam_width: int,
    *,
    ranking: str,
    controller: DifferentiableProofController | None = None,
) -> list[SearchRecord]:
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
    from worker.backend.yuclid_native_verifier import verify_problem

    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--problem-name", required=True)
    parser.add_argument("--yuclid-exe", type=Path, required=True)
    parser.add_argument("--runtime-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
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
    parser.add_argument("--per-family-limit", type=int, default=8)
    parser.add_argument("--branch-limit", type=int, default=32)
    parser.add_argument("--beam-width", type=int, default=7)
    parser.add_argument("--max-depth", type=int, default=2)
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--obligation-guided",
        action="store_true",
        help="Recompute point-level missing theorem premises after every branch.",
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
            "differentiable-consensus",
            "consensus-portfolio",
        ),
        default="closure",
    )
    parser.add_argument(
        "--controller",
        type=Path,
        help="Frozen differentiable controller artifact for learned beam policies.",
    )
    parser.add_argument("--ar-profile", choices=("ratio-only", "standard", "all"), default="all")
    args = parser.parse_args()
    controller = (
        DifferentiableProofController.load(args.controller.resolve())
        if args.controller is not None
        else None
    )
    if args.beam_ranking in {
        "differentiable-consensus",
        "consensus-portfolio",
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
        base_problem, yuclid_exe=args.yuclid_exe.resolve(), ar_profile=args.ar_profile
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
    baseline_obligations, baseline_demands = (
        proof_state_obligations(baseline.payload, goal_atoms, rule_theorems)
        if args.obligation_guided
        else ((), ())
    )
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

    frontier: list[tuple[tuple[ConstructionStep, ...], tuple[Atom, ...]]] = [
        (tuple(), baseline_demands)
    ]
    all_records: list[SearchRecord] = []
    solved_steps: tuple[ConstructionStep, ...] | None = None
    for depth in range(1, args.max_depth + 1):
        layer: list[SearchRecord] = []
        seen_paths: set[tuple[str, ...]] = set()
        candidate_paths: list[tuple[ConstructionStep, ...]] = []
        for parent, parent_demands in frontier:
            extensions = candidate_extensions(
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
                branch_limit=args.branch_limit,
                ranking=args.ranking,
                seed=branch_seed(args.seed, parent),
                relation_demands=parent_demands,
                require_generated_input=args.require_generated_input_after_first,
            )
            for extension in extensions:
                steps = (*parent, extension)
                signature = tuple(step.key for step in steps)
                if signature in seen_paths:
                    continue
                seen_paths.add(signature)
                candidate_paths.append(steps)
        batch_size = max(1, args.max_workers)
        layer_solved = False
        with ThreadPoolExecutor(max_workers=batch_size) as executor:
            for batch_start in range(0, len(candidate_paths), batch_size):
                batch = candidate_paths[batch_start : batch_start + batch_size]
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
                        obligation_guided=args.obligation_guided,
                    ): steps
                    for steps in batch
                }
                batch_records = [future.result() for future in as_completed(futures)]
                batch_records.sort(
                    key=lambda record: tuple(step.key for step in record.steps)
                )
                for record in batch_records:
                    layer.append(record)
                    print(
                        f"depth={depth} solved={record.solved} "
                        f"closure={record.all_deduction_count} "
                        f"path={[step.key for step in record.steps]}",
                        flush=True,
                    )
                if any(record.solved for record in batch_records):
                    layer_solved = True
                    break
        if layer_solved:
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
        "frontier-pareto": "yuclid_native_frontier_and_structural_pareto_beam",
        "frontier": "yuclid_native_frontier_witness_diverse_beam",
        "closure": "yuclid_closure_growth_diverse_beam",
        "differentiable-consensus": "frozen_differentiable_consensus_diverse_beam",
        "consensus-portfolio": "half_exact_residual_half_differentiable_consensus_beam",
    }
    artifact: dict[str, Any] = {
        "experiment": "newclid_dynamic_typed_construction_stalk_no_llm",
        "protocol": {
            "uses_external_llm": False,
            "uses_dataset_auxiliary_clauses": False,
            "uses_problem_id_in_search": False,
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
            "goal_channels": sorted(goal_channels),
            "proof_hypergraph_relevance": proof_relevance,
            "same_morphism_input_orbit_priority": True,
            "obligation_guided": args.obligation_guided,
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
            "branch_limit": args.branch_limit,
            "beam_width": args.beam_width,
            "max_depth": args.max_depth,
            "max_workers": args.max_workers,
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
        "records": [asdict(record) for record in all_records],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if solved_steps is not None:
        confirmation = verify_problem(
            build_branch(base_problem, solved_steps, seed=args.seed),
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
            "proof_sha256": confirmation.proof_sha256,
            "proof_path": proof_path.resolve().relative_to(ROOT).as_posix(),
        }
    args.output.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "solved": artifact["solved"],
                "solved_path": artifact["solved_path"],
                "evaluated_paths": artifact["evaluated_paths"],
                "error_count": artifact["error_count"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
