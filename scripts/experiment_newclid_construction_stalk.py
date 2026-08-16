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
    backward_relation_distances,
    yuclid_assertion_keys,
    yuclid_relation_metrics,
)
from worker.backend.typed_geometry_stalk import (
    DEFAULT_POINT_FAMILIES,
    ConstructionFamily,
    TypedConstructionCandidate,
    augment_incidence_graph,
    balanced_stratified_beam,
    enumerate_typed_candidates,
    proof_hypergraph_point_relevance,
)


DEFINITIONS = JGEXDefinition.to_dict(ALL_JGEX_CONSTRUCTIONS)


@dataclass(frozen=True)
class ConstructionStep:
    family: str
    output: str
    inputs: tuple[str, ...]

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
    elapsed_seconds: float
    error: str | None = None


def formulation_structure(
    formulation: JGEXFormulation,
) -> tuple[set[str], dict[str, set[str]], dict[str, int]]:
    points = {str(point) for point in formulation.points}
    graph: dict[str, set[str]] = defaultdict(set)
    for clause in formulation.setup_clauses:
        clause_points = {str(point) for point in clause.points}
        for construction in clause.constructions:
            clause_points.update(
                str(argument)
                for argument in construction.args
                if str(argument) and str(argument)[0].isalpha()
            )
        for left in clause_points:
            for right in clause_points:
                if left != right:
                    graph[left].add(right)
    goal_multiplicity: dict[str, int] = defaultdict(int)
    for goal in formulation.goals:
        for argument in goal.args:
            goal_multiplicity[str(argument)] += 1
    return points, graph, goal_multiplicity


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
            time.perf_counter() - started,
            str(exc),
        )


def candidate_extensions(
    *,
    base_problem: Any,
    base_points: set[str],
    base_graph: dict[str, set[str]],
    goal_multiplicity: dict[str, int],
    proof_relevance: dict[str, float],
    steps: tuple[ConstructionStep, ...],
    families: tuple[ConstructionFamily, ...],
    per_family_limit: int,
    branch_limit: int,
    ranking: str,
    seed: int,
) -> list[ConstructionStep]:
    generated = {step.output for step in steps}
    points = base_points | generated
    graph = augment_incidence_graph(
        base_graph, tuple((step.output, step.inputs) for step in steps)
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
    )
    if branch_limit > 0:
        by_family: dict[str, list[TypedConstructionCandidate]] = defaultdict(list)
        for candidate in candidates:
            by_family[candidate.family].append(candidate)
        balanced: list[TypedConstructionCandidate] = []
        family_order = [family.name for family in families]
        while len(balanced) < branch_limit:
            added = False
            for family_name in family_order:
                bucket = by_family[family_name]
                if bucket:
                    balanced.append(bucket.pop(0))
                    added = True
                    if len(balanced) == branch_limit:
                        break
            if not added:
                break
        candidates = balanced
    output = next_point_name(points)
    return [
        ConstructionStep(candidate.family, output, candidate.inputs)
        for candidate in candidates
    ]


def select_diverse_beam(
    records: list[SearchRecord], beam_width: int, *, ranking: str
) -> list[SearchRecord]:
    if ranking == "relation":
        score = lambda record: (
            record.solved,
            record.relation_near_goal_count,
            record.relation_support_weight,
            record.relation_target_assertion_count,
            record.goal_deduction_count,
            record.all_deduction_count,
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
    parser.add_argument("--per-family-limit", type=int, default=8)
    parser.add_argument("--branch-limit", type=int, default=32)
    parser.add_argument("--beam-width", type=int, default=7)
    parser.add_argument("--max-depth", type=int, default=2)
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--ranking", choices=("structural", "random"), default="structural")
    parser.add_argument(
        "--beam-ranking",
        choices=("closure", "relation", "relation-transition"),
        default="closure",
    )
    parser.add_argument("--ar-profile", choices=("ratio-only", "standard", "all"), default="all")
    args = parser.parse_args()

    requested = tuple(name.strip() for name in args.families.split(",") if name.strip())
    family_map = {family.name: family for family in DEFAULT_POINT_FAMILIES}
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
    base_points, base_graph, goal_multiplicity = formulation_structure(formulation)
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

    frontier: list[tuple[ConstructionStep, ...]] = [tuple()]
    all_records: list[SearchRecord] = []
    solved_steps: tuple[ConstructionStep, ...] | None = None
    for depth in range(1, args.max_depth + 1):
        layer: list[SearchRecord] = []
        seen_paths: set[tuple[str, ...]] = set()
        candidate_paths: list[tuple[ConstructionStep, ...]] = []
        for parent in frontier:
            extensions = candidate_extensions(
                base_problem=base_problem,
                base_points=base_points,
                base_graph=base_graph,
                goal_multiplicity=goal_multiplicity,
                proof_relevance=proof_relevance,
                steps=parent,
                families=families,
                per_family_limit=args.per_family_limit,
                branch_limit=args.branch_limit,
                ranking=args.ranking,
                seed=branch_seed(args.seed, parent),
            )
            for extension in extensions:
                steps = (*parent, extension)
                signature = tuple(step.key for step in steps)
                if signature in seen_paths:
                    continue
                seen_paths.add(signature)
                candidate_paths.append(steps)
        with ThreadPoolExecutor(max_workers=max(1, args.max_workers)) as executor:
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
                ): steps
                for steps in candidate_paths
            }
            for future in as_completed(futures):
                record = future.result()
                layer.append(record)
                print(
                    f"depth={depth} solved={record.solved} "
                    f"closure={record.all_deduction_count} "
                    f"path={[step.key for step in record.steps]}",
                    flush=True,
                )
        layer.sort(key=lambda record: tuple(step.key for step in record.steps))
        all_records.extend(layer)
        solved_records = [record for record in layer if record.solved]
        if solved_records:
            solved_steps = solved_records[0].steps
        if solved_steps is not None or depth == args.max_depth:
            break
        frontier = [
            record.steps
            for record in select_diverse_beam(
                layer, args.beam_width, ranking=args.beam_ranking
            )
        ]

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
            "second_stage_ranking": (
                "yuclid_novel_nonconstruction_target_relation_diverse_beam"
                if args.beam_ranking == "relation"
                else (
                    "yuclid_native_rule_transition_potential_diverse_beam"
                    if args.beam_ranking == "relation-transition"
                    else "yuclid_closure_growth_diverse_beam"
                )
            ),
            "beam_ranking": args.beam_ranking,
            "goal_channels": sorted(goal_channels),
            "proof_hypergraph_relevance": proof_relevance,
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
        },
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
            "proof_path": proof_path.resolve().relative_to(REPO_ROOT).as_posix(),
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
