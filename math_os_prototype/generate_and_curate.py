"""Generate → check → keep loop.

Claude does not author problems here. This is plumbing that (1) runs MathOS's
composition/fusion generators, (2) passes every candidate through the objective
world-novelty + difficulty checker, and (3) keeps only the ones that are BOTH
new to the world AND genuinely hard. "どんどん生成して、チェッカーで残す。"

The kept set is the curated MathOS pool; everything else is discarded.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

try:
    from math_os_prototype.concept_tree_synthesis import synthesize as gen_concept_tree
    from math_os_prototype.geometry_fusion_synthesis import synthesize as gen_geometry
    from math_os_prototype.world_novelty_check import (
        difficulty,
        load_jukenmath_hashes,
        load_world_corpus,
        world_novelty,
    )
    from math_os_prototype.jukenmath_full_audit import surface_ngrams
except ImportError:  # pragma: no cover
    from concept_tree_synthesis import synthesize as gen_concept_tree
    from geometry_fusion_synthesis import synthesize as gen_geometry
    from world_novelty_check import (
        difficulty,
        load_jukenmath_hashes,
        load_world_corpus,
        world_novelty,
    )
    from jukenmath_full_audit import surface_ngrams


HERE = Path(__file__).resolve().parent
HARD_BANDS = ("A_olympiad", "B_hard_university")


def _normalize(problem: dict[str, Any], source: str) -> dict[str, Any]:
    lift = problem.get("lift_certificate") or {}
    return {
        "candidate_id": problem.get("candidate_id") or problem.get("tree_signature"),
        "source": source,
        "domain": problem.get("domain", "unknown"),
        "statement_tex": problem.get("statement_tex", ""),
        "answer_tex": problem.get("answer_tex", ""),
        "solution_tex": problem.get("solution_tex", ""),
        "morphism_chain": lift.get("morphism_chain", []),
        "verification": problem.get("verification", {}),
    }


def collect_candidates() -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for name, gen in (
        ("concept_tree", gen_concept_tree),
        ("geometry_fusion", gen_geometry),
    ):
        report = gen()
        for problem in report.get("problems", []):
            candidates.append(_normalize(problem, name))
    return candidates


def curate(target: int | None = None, require_novel: bool = True) -> dict[str, Any]:
    candidates = collect_candidates()
    world = load_world_corpus()
    world_grams = [(r["source"], surface_ngrams(r["statement"])) for r in world]
    juken = load_jukenmath_hashes()

    kept: list[dict[str, Any]] = []
    rejected = {"not_novel": 0, "too_easy": 0}
    for cand in candidates:
        nov = world_novelty(cand["statement_tex"], world_grams, juken)
        diff = difficulty(cand)
        cand["assessment"] = {
            "world_novel": nov["world_novel"],
            "max_jaccard": nov["max_surface_jaccard"],
            "exact_jukenmath_collision": nov["exact_jukenmath_collision"],
            "difficulty_band": diff["band"],
            "difficulty_score": diff["score"],
            "fusion": diff["fusion"],
            "unusual_fusions": diff["unusual_fusions"],
        }
        if require_novel and not nov["world_novel"]:
            rejected["not_novel"] += 1
            continue
        if diff["band"] not in HARD_BANDS:
            rejected["too_easy"] += 1
            continue
        kept.append(cand)

    kept.sort(key=lambda c: -c["assessment"]["difficulty_score"])
    if target is not None:
        kept = kept[:target]

    from collections import Counter

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "loop": "generate -> world-novelty + difficulty check -> keep novel & hard",
        "summary": {
            "candidates": len(candidates),
            "kept": len(kept),
            "rejected_not_novel": rejected["not_novel"],
            "rejected_too_easy": rejected["too_easy"],
            "kept_bands": dict(
                Counter(c["assessment"]["difficulty_band"] for c in kept)
            ),
            "world_corpus_size": len(world),
        },
        "problems": kept,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=int, default=None)
    parser.add_argument("--allow-known", action="store_true", help="keep even if not world-novel")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = curate(target=args.target, require_novel=not args.allow_known)
    if args.output:
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
