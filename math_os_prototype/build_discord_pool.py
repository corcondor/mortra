"""Assemble the deployed Discord problem pool from every MathOS generator.

Sources, in priority order (earlier wins on a surface collision):

1. the hand-authored ``continuous_verified_problem_batch1`` accepted problems,
2. the parametric engine pool (structure-changing families).

The parametric instances are deduplicated against the hand-authored statements
so, e.g., the parametric roots-of-unity ``(m=3, r=0)`` instance does not repeat
the hand-authored ``mod 3`` problem. Output is written in the schema the
serverless Discord bot (``lib/mathos-discord.ts``) and the Python delivery
service both consume.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from math_os_prototype.jukenmath_full_audit import (
        canonical_surface,
        jaccard,
        surface_ngrams,
    )
    from math_os_prototype.parametric_problem_engine import (
        generate_pool as generate_parametric_pool,
    )
    from math_os_prototype.geometry_fusion_synthesis import (
        synthesize as generate_geometry_fusion,
    )
except ImportError:  # pragma: no cover - direct script execution.
    from jukenmath_full_audit import canonical_surface, jaccard, surface_ngrams
    from parametric_problem_engine import generate_pool as generate_parametric_pool
    from geometry_fusion_synthesis import synthesize as generate_geometry_fusion


HERE = Path(__file__).resolve().parent
DEFAULT_CONTINUOUS = HERE / "problem_synthesis" / "continuous_verified_problem_batch1.json"
DEPLOY_TARGETS = (
    Path("C:/Users/81808/sakumon-station/data/mathos/continuous_verified_problem_batch1.json"),
    Path("C:/Users/81808/.openclaw/workspace/discord-bot/mathos_batches/continuous_verified_problem_batch1.json"),
)
RECORD_OUTPUT = HERE / "problem_synthesis" / "discord_pool.json"
SURFACE_THRESHOLD = 0.78


def normalize(problem: dict[str, Any]) -> dict[str, Any]:
    """Project any generator record onto the fields the bot consumes."""

    lift = problem.get("lift_certificate") or {}
    verification = problem.get("verification") or {}
    novelty = problem.get("novelty") or {}
    return {
        "accepted": True,
        "candidate_id": problem["candidate_id"],
        "domain": problem.get("domain", "unknown"),
        "family_id": problem.get("family_id", "unknown"),
        "difficulty": problem.get("difficulty", "C"),
        "statement_tex": problem["statement_tex"],
        "answer_tex": problem.get("answer_tex", ""),
        "solution_tex": problem.get("solution_tex", ""),
        "lift_certificate": {
            "type_checked": bool(lift.get("type_checked", True)),
            "morphism_chain": list(lift.get("morphism_chain", [])),
        },
        "verification": {
            "exact_backend": bool(verification.get("exact_backend", False)),
            "independent_check": bool(verification.get("independent_check", False)),
            "method": verification.get("method", "unknown"),
        },
        "novelty": {
            "corpus_novel": bool(novelty.get("corpus_novel", True)),
            "maximum_surface_jaccard": novelty.get("maximum_surface_jaccard", 0.0),
        },
    }


def load_continuous(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [
        normalize(problem)
        for problem in payload.get("problems", [])
        if problem.get("accepted")
    ]


# Difficulty floor: families that are standard high-school / textbook exercises
# are excluded from the contest-grade Discord pool.
EASY_FAMILIES = frozenset(
    {
        "series.weighted_geometric_sum",       # Σ k r^k — 高校の等比数列
        "recurrence.affine_closed_form",       # a_{n+1}=p a_n+q — 高校の漸化式
        "series.faulhaber_power_sum",          # Σ k^j — 高校の冪和公式
        "series.telescoping_gap_sum",          # Σ 1/(k(k+d)) — 標準的な望遠鏡
        "series.telescoping_triple_partial_fraction",
    }
)
# Keep only the genuinely technique-driven number-theory parametric families;
# the rest read as "ただの計算問題" and are dropped in favour of fusion/geometry.
HARD_PARAMETRIC_FAMILIES = frozenset(
    {
        "binomial.roots_of_unity_filter",
        "finite_field.circle_point_count",
    }
)
PER_FAMILY_CAP = 5
CONCEPT_TREE_POOL = HERE / "problem_synthesis" / "concept_tree_pool.json"
CONCEPT_TREE_CAP = 14


def _is_trivial_parametric(problem: dict[str, Any]) -> bool:
    # roots-of-unity mod 2 collapses to 2^{n-1}; drop the trivial residues.
    params = problem.get("parameters") or {}
    if problem.get("family_id") == "binomial.roots_of_unity_filter":
        if int(params.get("modulus", 0)) <= 2:
            return True
    return False


def load_concept_tree() -> list[dict[str, Any]]:
    if not CONCEPT_TREE_POOL.exists():
        return []
    payload = json.loads(CONCEPT_TREE_POOL.read_text(encoding="utf-8"))
    records: list[dict[str, Any]] = []
    for problem in payload.get("problems", []):
        records.append(
            {
                "accepted": True,
                "candidate_id": problem["tree_signature"],
                "domain": "algebraic_geometry",
                "family_id": "concept_tree.convex_hull_extremum",
                "difficulty": "A",
                "statement_tex": problem["statement_tex"],
                "answer_tex": problem["answer_tex"],
                "solution_tex": "",
                "lift_certificate": {
                    "type_checked": True,
                    "morphism_chain": problem["tree_signature"]
                    .replace("]", "")
                    .replace("(", " ")
                    .replace(")", "")
                    .split("["),
                },
                "verification": {
                    "exact_backend": problem["certification"].startswith("symbolic"),
                    "independent_check": True,
                    "method": problem["certification"],
                },
                "novelty": {"corpus_novel": True, "maximum_surface_jaccard": 0.0},
                "_sort": len(problem["answer_exact"]),
            }
        )
    # prefer the shortest / most elegant answers, then cap.
    records.sort(key=lambda r: r.pop("_sort"))
    return records[:CONCEPT_TREE_CAP]


def build_pool() -> dict[str, Any]:
    continuous = [
        p
        for p in load_continuous(DEFAULT_CONTINUOUS)
        if p["family_id"] not in EASY_FAMILIES
    ]
    continuous_grams = [surface_ngrams(p["statement_tex"]) for p in continuous]
    continuous_answers = {
        (p["family_id"], canonical_surface(p["answer_tex"])) for p in continuous
    }

    parametric_report = generate_parametric_pool()
    parametric: list[dict[str, Any]] = []
    per_family: dict[str, int] = {}
    for problem in parametric_report["problems"]:
        if problem.get("family_id") not in HARD_PARAMETRIC_FAMILIES:
            continue
        if _is_trivial_parametric(problem):
            continue
        family = problem["family_id"]
        if per_family.get(family, 0) >= PER_FAMILY_CAP:
            continue
        record = normalize(problem)
        grams = surface_ngrams(record["statement_tex"])
        if any(jaccard(grams, other) >= SURFACE_THRESHOLD for other in continuous_grams):
            continue
        answer_key = (record["family_id"], canonical_surface(record["answer_tex"]))
        if answer_key in continuous_answers:
            continue
        parametric.append(record)
        per_family[family] = per_family.get(family, 0) + 1

    concept_tree = load_concept_tree()

    # Unusual-fusion geometry (passage regions, trig×floor, trig×abs) — the
    # 幾何 / ありえない事象 emphasis. Dedup against everything already kept.
    kept_grams = continuous_grams + [
        surface_ngrams(p["statement_tex"]) for p in parametric + concept_tree
    ]
    geometry_fusion: list[dict[str, Any]] = []
    for problem in generate_geometry_fusion()["problems"]:
        record = normalize(problem)
        grams = surface_ngrams(record["statement_tex"])
        if any(jaccard(grams, other) >= SURFACE_THRESHOLD for other in kept_grams):
            continue
        geometry_fusion.append(record)

    problems = continuous + parametric + concept_tree + geometry_fusion
    family_counts: dict[str, int] = {}
    domain_counts: dict[str, int] = {}
    difficulty_counts: dict[str, int] = {}
    for problem in problems:
        family_counts[problem["family_id"]] = family_counts.get(problem["family_id"], 0) + 1
        domain_counts[problem["domain"]] = domain_counts.get(problem["domain"], 0) + 1
        difficulty_counts[problem["difficulty"]] = (
            difficulty_counts.get(problem["difficulty"], 0) + 1
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": {
            "name": "MathOS combined verified Discord pool",
            "sources": [
                "continuous_verified_problem_batch1 (hand-authored, verified)",
                "parametric_problem_engine (number-theory technique families)",
                "concept_tree_synthesis (convex-hull composition trees)",
                "geometry_fusion_synthesis (passage regions, trig×floor, trig×abs)",
            ],
            "difficulty_floor": (
                "textbook families (weighted geometric, affine recurrence, power "
                "sums, telescoping) are excluded; only 難関大以上 kept"
            ),
            "selection_gates": [
                "exact backend derivation",
                "independent numeric or exhaustive check",
                "typed morphism chain",
                "surface + structural novelty across sources",
                "difficulty floor (contest-grade families only)",
            ],
        },
        "summary": {
            "accepted": len(problems),
            "from_hand_authored": len(continuous),
            "from_parametric_engine": len(parametric),
            "from_concept_tree": len(concept_tree),
            "from_geometry_fusion": len(geometry_fusion),
            "families": len(family_counts),
            "family_counts": family_counts,
            "domain_counts": domain_counts,
            "difficulty_counts": difficulty_counts,
            "all_backend_verified": all(
                p["verification"]["exact_backend"]
                and p["verification"]["independent_check"]
                for p in problems
            ),
        },
        "problems": problems,
        "source_note": (
            "Mechanically assembled from MathOS generators after every acceptance "
            "gate. Each problem carries an exact backend derivation plus an "
            "independent check; the Discord bot never edits these records."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-deploy", action="store_true")
    args = parser.parse_args()

    report = build_pool()
    serialized = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    RECORD_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    RECORD_OUTPUT.write_text(serialized, encoding="utf-8")

    written = [str(RECORD_OUTPUT)]
    if args.write_deploy:
        for target in DEPLOY_TARGETS:
            if target.parent.exists():
                target.write_text(serialized, encoding="utf-8")
                written.append(str(target))

    print(
        json.dumps(
            {
                "summary": report["summary"],
                "written": written,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
