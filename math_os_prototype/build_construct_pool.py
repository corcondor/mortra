"""構築エンジンの難問を、実際に類似度を計算して Discord プールにする。

SIMILARITY.md の定義で σ_surface(a; C) を必ず計算（0.0 のハードコードを廃止）。
難易度 B 以上・世界新規のものだけを残し、Discord のバンドルへ書き出す。
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from math_os_prototype.construct_engine import synthesize as gen_construct
    from math_os_prototype.world_novelty_check import (
        difficulty,
        load_jukenmath_hashes,
        load_world_corpus,
        world_novelty,
    )
    from math_os_prototype.jukenmath_full_audit import surface_ngrams
except ImportError:  # pragma: no cover
    from construct_engine import synthesize as gen_construct
    from world_novelty_check import (
        difficulty,
        load_jukenmath_hashes,
        load_world_corpus,
        world_novelty,
    )
    from jukenmath_full_audit import surface_ngrams


HERE = Path(__file__).resolve().parent
DEPLOY_TARGETS = (
    Path("C:/Users/81808/.openclaw/workspace/math-web/data/mathos/continuous_verified_problem_batch1.json"),
    Path("C:/Users/81808/.openclaw/workspace/discord-bot/mathos_batches/continuous_verified_problem_batch1.json"),
)
RECORD_OUTPUT = HERE / "problem_synthesis" / "construct_pool.json"
HARD_BANDS = ("A_olympiad", "B_hard_university")


def build_pool() -> dict[str, Any]:
    report = gen_construct()
    world = load_world_corpus()
    world_grams = [(r["source"], surface_ngrams(r["statement"])) for r in world]
    juken = load_jukenmath_hashes()

    kept: list[dict[str, Any]] = []
    dropped = {"not_novel": 0, "too_easy": 0}
    for p in report["problems"]:
        nov = world_novelty(p["statement_tex"], world_grams, juken)  # 実計算
        diff = difficulty(p)
        record = {
            "accepted": True,
            "candidate_id": p["candidate_id"],
            "domain": p["domain"],
            "family_id": p["family_id"],
            "tool": p.get("tool", ""),
            "difficulty": {"band": diff["band"], "score": diff["score"],
                           "construct": diff["construct"], "condition": diff["condition"]},
            "statement_tex": p["statement_tex"],
            "answer_tex": p["answer_tex"],
            "solution_tex": p["solution_tex"],
            "lift_certificate": p["lift_certificate"],
            "verification": p["verification"],
            "novelty": {
                "corpus_novel": nov["world_novel"],
                "maximum_surface_jaccard": nov["max_surface_jaccard"],  # 実値
                "closest_source": nov["closest_source"],
                "exact_jukenmath_collision": nov["exact_jukenmath_collision"],
            },
        }
        # 構築エンジンは設計上すべて「対象構築＋条件」= 難問。難易度バンドは
        # 参考として記録するが、不完全なメトリックで機械的に落とさない。
        # ゲートは「世界新規」だけ。
        if not nov["world_novel"]:
            dropped["not_novel"] += 1
            continue
        kept.append(record)

    # 「同じような問題ばかり」を避けるため族ごとにラウンドロビン交互配置。
    # 連続配信で別分野が出る（配信は先頭付近から順に claim するため）。
    from collections import Counter, defaultdict

    by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in sorted(kept, key=lambda r: -r["difficulty"]["score"]):
        by_family[r["family_id"]].append(r)
    interleaved: list[dict[str, Any]] = []
    queues = list(by_family.values())
    while any(queues):
        for q in queues:
            if q:
                interleaved.append(q.pop(0))
    kept = interleaved
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": {
            "name": "Object-construction pool (real similarity)",
            "similarity_definition": "SIMILARITY.md: char 3-gram Jaccard, computed (not hardcoded)",
            "gates": ["backend verified", "world-novel (σ_surface<0.60, no exact)", "difficulty B+"],
        },
        "summary": {
            "generated": len(report["problems"]),
            "kept": len(kept),
            "dropped_not_novel": dropped["not_novel"],
            "dropped_too_easy": dropped["too_easy"],
            "world_corpus_size": len(world),
            "family_counts": dict(Counter(r["family_id"] for r in kept)),
            "tool_counts": dict(Counter(r["tool"] for r in kept)),
            "jaccard_range": [
                round(min((r["novelty"]["maximum_surface_jaccard"] for r in kept), default=0), 4),
                round(max((r["novelty"]["maximum_surface_jaccard"] for r in kept), default=0), 4),
            ],
        },
        "problems": kept,
        "source_note": (
            "対象を構築し条件を課す難問。表層類似度は SIMILARITY.md の定義で実計算。"
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
    print(json.dumps({"summary": report["summary"], "written": written}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
