"""Export a compact, reproducible audit for the public research dashboard."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent


def _rank(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=values.__getitem__)
    ranks = [0.0] * len(values)
    cursor = 0
    while cursor < len(order):
        end = cursor
        while end + 1 < len(order) and values[order[end + 1]] == values[order[cursor]]:
            end += 1
        rank = (cursor + end + 2) / 2
        for index in range(cursor, end + 1):
            ranks[order[index]] = rank
        cursor = end + 1
    return ranks


def _correlation(left: list[float], right: list[float]) -> float:
    left_mean = statistics.mean(left)
    right_mean = statistics.mean(right)
    numerator = sum((x - left_mean) * (y - right_mean) for x, y in zip(left, right))
    left_norm = sum((x - left_mean) ** 2 for x in left)
    right_norm = sum((y - right_mean) ** 2 for y in right)
    denominator = math.sqrt(left_norm * right_norm)
    return numerator / denominator if denominator else 0.0


def _depth(problem: dict[str, Any]) -> int:
    return len(problem.get("lift_certificate", {}).get("morphism_chain", []))


def build_report() -> dict[str, Any]:
    pool = json.loads((ROOT / "problem_synthesis" / "entrance_exam_pool.json").read_text(encoding="utf-8"))
    unresolved = json.loads((ROOT / "problem_synthesis" / "unresolved_candidates.json").read_text(encoding="utf-8"))
    problems = pool["problems"]

    depths = [_depth(problem) for problem in problems]
    scores = [float(problem.get("difficulty_score", 0)) for problem in problems]
    statement_lengths = [float(len(problem.get("statement_tex", ""))) for problem in problems]
    source_counts = Counter(problem.get("source_generator", "unknown") for problem in problems)
    composition = [problem for problem in problems if problem.get("source_generator") == "closure_composition"]
    stage_counts = Counter(int(problem.get("parameters", {}).get("stages", 0)) for problem in composition)
    proof_graph_count = sum(
        bool(problem.get("proof_graph") or problem.get("proof_dag")) for problem in problems
    )
    chains_count = sum(bool(problem.get("lift_certificate", {}).get("morphism_chain")) for problem in problems)
    verified_count = sum(
        bool(problem.get("verification", {}).get("exact_backend"))
        and bool(problem.get("verification", {}).get("independent_check"))
        for problem in problems
    )

    auc_values = {
        problem.get("quality_annotations", {}).get("observed_human_auc")
        for problem in problems
        if problem.get("quality_annotations", {}).get("observed_human_auc") is not None
    }
    human_auc = min(auc_values) if auc_values else None
    high_depth = sorted(problems, key=lambda problem: (-_depth(problem), problem.get("family_id", "")))[:8]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "pool": "problem_synthesis/entrance_exam_pool.json",
            "unresolved": "problem_synthesis/unresolved_candidates.json",
        },
        "summary": {
            "problems": len(problems),
            "families": pool.get("summary", {}).get("families", 0),
            "verified": verified_count,
            "morphism_chains": chains_count,
            "proof_graphs": proof_graph_count,
            "unresolved": unresolved.get("summary", {}).get("retained", 0),
            "unresolved_depth_floor": unresolved.get("summary", {}).get("current_depth_floor", 0),
            "reference_corpus": unresolved.get("summary", {}).get("reference_corpus_size", 0),
            "human_runtime_corpus": unresolved.get("summary", {}).get("current_runtime_corpus_size", 0),
            "human_difficulty_auc": human_auc,
            "excluded_non_interacting_compositions": pool.get("summary", {})
            .get("rejected", {})
            .get("non_interacting_composition", 0),
        },
        "structure": {
            "source_counts": dict(source_counts),
            "depth_distribution": dict(sorted(Counter(depths).items())),
            "depth_median": statistics.median(depths),
            "depth_p90": sorted(depths)[math.ceil(len(depths) * 0.9) - 1],
            "depth_max": max(depths),
            "depth_10_or_more": sum(depth >= 10 for depth in depths),
            "composition_count": len(composition),
            "composition_stage_counts": dict(sorted(stage_counts.items())),
            "single_scalar_bridge_count": sum(
                "bridge_value" in problem.get("parameters", {}) for problem in composition
            ),
        },
        "measurement_audit": {
            "depth_vs_legacy_score_pearson": round(_correlation(depths, scores), 3),
            "depth_vs_statement_length_pearson": round(_correlation(depths, statement_lengths), 3),
            "legacy_score_vs_statement_length_pearson": round(_correlation(scores, statement_lengths), 3),
            "legacy_score_vs_statement_length_spearman": round(
                _correlation(_rank(scores), _rank(statement_lengths)), 3
            ),
        },
        "representation": {
            "implemented": "linear_morphism_chain",
            "missing": ["proof_dependency_dag", "lemma_dependencies", "failed_branches", "alternative_proofs"],
        },
        "high_depth_examples": [
            {
                "family_id": problem.get("family_id"),
                "domain": problem.get("domain"),
                "source_generator": problem.get("source_generator"),
                "statement_tex": problem.get("statement_tex"),
                "answer_tex": problem.get("answer_tex"),
                "morphisms": problem.get("lift_certificate", {}).get("morphism_chain", []),
                "verification_method": problem.get("verification", {}).get("method"),
            }
            for problem in high_depth
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "problem_synthesis" / "research_progress.json")
    args = parser.parse_args()
    report = build_report()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
