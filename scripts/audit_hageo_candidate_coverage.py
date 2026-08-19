"""Audit whether certified development paths are expressible by the grammar.

This is a coverage diagnostic, not a solver.  It reads only explicitly supplied
development traces and never uses a held-out auxiliary construction to rank or
generate candidates.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.experiment_newclid_construction_stalk import (  # noqa: E402
    ConstructionStep,
    EXTENDED_POINT_FAMILIES,
    JGEXFormulation,
    JGEXProblemBuilder,
    augment_incidence_graph,
    augment_semantic_role_graph,
    augment_semantic_role_weights,
    extend_prefix_branch,
    formulation_structure,
    jgex_formulation_from_txt_file,
    normalize_legacy_formulation,
)
from worker.backend.typed_geometry_stalk import (  # noqa: E402
    equivalent_construction_inputs,
    enumerate_typed_candidates,
)


STEP_PATTERN = re.compile(
    r"^(?P<family>[^()]+)\((?P<inputs>.*)\)->(?P<output>[^()]+)$"
)


def split_of(identifier: str) -> str:
    bucket = int.from_bytes(hashlib.sha256(identifier.encode()).digest()[:8], "big") % 10
    if bucket < 6:
        return "dev"
    if bucket < 8:
        return "calibration"
    return "held_out"


def parse_step(value: str) -> ConstructionStep:
    match = STEP_PATTERN.match(value)
    if match is None:
        raise ValueError(f"invalid construction step: {value}")
    raw_inputs = match.group("inputs")
    inputs = tuple(item for item in raw_inputs.split(",") if item)
    return ConstructionStep(
        match.group("family"),
        match.group("output"),
        inputs,
    )


def solved_paths(artifact: dict[str, Any]) -> tuple[tuple[ConstructionStep, ...], ...]:
    raw_paths: list[list[str]] = []
    if artifact.get("solved") and artifact.get("solved_path"):
        raw_paths.append(list(artifact["solved_path"]))
    for attempt in artifact.get("attempt_results", ()):
        if attempt.get("solved") and attempt.get("path"):
            raw_paths.append(list(attempt["path"]))
    unique: dict[tuple[str, ...], tuple[ConstructionStep, ...]] = {}
    for path in raw_paths:
        key = tuple(path)
        unique.setdefault(key, tuple(parse_step(item) for item in path))
    return tuple(unique.values())


def audit_path(
    raw: JGEXFormulation,
    path: tuple[ConstructionStep, ...],
    *,
    seed: int,
    per_family_limit: int,
) -> dict[str, Any]:
    family_by_name = {family.name: family for family in EXTENDED_POINT_FAMILIES}
    builder = JGEXProblemBuilder(np.random.default_rng(seed))
    setup_only = JGEXFormulation(
        name=raw.name,
        setup_clauses=raw.setup_clauses,
        auxiliary_clauses=(),
        goals=raw.goals,
    )
    formulation, normalization = normalize_legacy_formulation(
        setup_only, builder.jgex_defs
    )
    current_problem = (
        builder.with_problem(formulation).include_auxiliary_clauses(False).build()
    )
    base_points, base_graph, base_role_graph, base_role_weights, goal_multiplicity = (
        formulation_structure(formulation)
    )
    prefix: tuple[ConstructionStep, ...] = ()
    step_results: list[dict[str, Any]] = []
    for step in path:
        generated = {item.output for item in prefix}
        points = base_points | generated
        graph = augment_incidence_graph(
            base_graph, tuple((item.output, item.inputs) for item in prefix)
        )
        role_graph = augment_semantic_role_graph(
            base_role_graph,
            tuple((item.family, item.output, item.inputs) for item in prefix),
        )
        role_weights = augment_semantic_role_weights(
            base_role_weights,
            tuple((item.family, item.output, item.inputs) for item in prefix),
        )
        coordinates = {
            str(point.name): (float(point.num.x), float(point.num.y))
            for point in current_problem.points
        }
        candidates = enumerate_typed_candidates(
            points=tuple(points),
            graph=graph,
            goal_multiplicity=goal_multiplicity,
            generated_points=generated,
            used_keys={f"{item.family}({','.join(item.inputs)})" for item in prefix},
            families=EXTENDED_POINT_FAMILIES,
            per_family_limit=per_family_limit,
            ranking="structural",
            seed=seed,
            coordinates=coordinates,
            role_graph=role_graph,
            role_weights=role_weights,
        )
        family = family_by_name.get(step.family)
        grammar_encodable = (
            family is not None
            and len(step.inputs) == family.input_arity
            and set(step.inputs) <= points
            and (
                family.allow_repeated_inputs
                or len(set(step.inputs)) == len(step.inputs)
            )
        )
        enumerated = any(
            candidate.family == step.family
            and family is not None
            and equivalent_construction_inputs(
                family, candidate.inputs, step.inputs
            )
            for candidate in candidates
        )
        executable = False
        error: str | None = None
        if grammar_encodable:
            try:
                next_prefix = (*prefix, step)
                current_problem = extend_prefix_branch(
                    current_problem,
                    step,
                    next_prefix,
                    seed=seed,
                )
                executable = True
                prefix = next_prefix
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
        step_results.append(
            {
                "step": step.key,
                "family": step.family,
                "grammar_encodable": grammar_encodable,
                "enumerated_under_budget": enumerated,
                "executable": executable,
                "candidate_count": len(candidates),
                "error": error,
            }
        )
        if not executable:
            break
    return {
        "normalization": asdict(normalization),
        "path_length": len(path),
        "grammar_coverage": sum(item["grammar_encodable"] for item in step_results),
        "budgeted_enumeration_coverage": sum(
            item["enumerated_under_budget"] for item in step_results
        ),
        "execution_coverage": sum(item["executable"] for item in step_results),
        "steps": step_results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--trace", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--split", choices=("dev", "calibration"), default="dev")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--per-family-limit", type=int, default=32)
    args = parser.parse_args()

    formulations = jgex_formulation_from_txt_file(args.dataset.resolve())
    results: list[dict[str, Any]] = []
    seen: set[tuple[str, tuple[str, ...]]] = set()
    for trace_path in args.trace:
        artifact = json.loads(trace_path.read_text(encoding="utf-8"))
        problem_name = str(artifact.get("problem_name") or artifact.get("problem"))
        if problem_name not in formulations:
            raise KeyError(f"trace problem is absent from dataset: {problem_name}")
        observed_split = split_of(problem_name)
        if observed_split != args.split:
            raise ValueError(
                f"trace {problem_name} belongs to {observed_split}, not {args.split}"
            )
        paths = solved_paths(artifact)
        if not paths:
            raise ValueError(f"trace has no solved construction path: {trace_path}")
        for path in paths:
            key = (problem_name, tuple(item.key for item in path))
            if key in seen:
                continue
            seen.add(key)
            results.append(
                {
                    "problem_name": problem_name,
                    "trace": trace_path.resolve().relative_to(ROOT).as_posix(),
                    **audit_path(
                        formulations[problem_name],
                        path,
                        seed=args.seed,
                        per_family_limit=args.per_family_limit,
                    ),
                }
            )
    step_results = [step for result in results for step in result["steps"]]
    family_counts = Counter(step["family"] for step in step_results)
    report = {
        "experiment": "hageo_candidate_coverage_certified_development_paths",
        "protocol": {
            "uses_external_llm": False,
            "uses_expected_answers": False,
            "uses_dataset_auxiliary_clauses_for_search": False,
            "split": args.split,
            "per_family_limit": args.per_family_limit,
            "purpose": "coverage_audit_only_not_training_or_heldout_scoring",
        },
        "summary": {
            "paths": len(results),
            "steps": len(step_results),
            "grammar_coverage": sum(step["grammar_encodable"] for step in step_results),
            "budgeted_enumeration_coverage": sum(
                step["enumerated_under_budget"] for step in step_results
            ),
            "execution_coverage": sum(step["executable"] for step in step_results),
            "family_counts": dict(sorted(family_counts.items())),
        },
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
