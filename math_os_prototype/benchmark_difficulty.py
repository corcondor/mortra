"""MathOS の旧難易度特徴量を、固定参照集合上で診断する。

比べる相手は 2 つ:

  * 版を固定した手作り問題スナップショット
  * 過去問コーパス（東大・京大ほか、約28,000問）

人手採否に対する観測 AUC は 0.086 であり、難しさ・品質のゲートとしては
無効である。ここでの値は特徴量の分布を再現可能に観測するためだけに使う。
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path
from typing import Any

try:
    from math_os_prototype.difficulty_reference import (
        DIFFICULTY_GATING_ENABLED,
        extract_problem_statement,
        load_fixed_reference,
    )
    from math_os_prototype.world_novelty_check import (
        difficulty, load_world_corpus,
    )
except ImportError:  # pragma: no cover
    from difficulty_reference import (
        DIFFICULTY_GATING_ENABLED,
        extract_problem_statement,
        load_fixed_reference,
    )
    from world_novelty_check import (
        difficulty, load_world_corpus,
    )

HERE = Path(__file__).resolve().parent
POOL = HERE / "problem_synthesis" / "entrance_exam_pool.json"


def score_of(statement: str, solution: str = "") -> float:
    statement = extract_problem_statement(statement)
    return float(difficulty({
        "statement_tex": statement,
        "solution_tex": solution,
    }).get("score", 0.0))


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round(q * (len(ordered) - 1)))))
    return ordered[index]


def describe(name: str, values: list[float]) -> dict[str, Any]:
    if not values:
        return {"name": name, "count": 0}
    return {
        "name": name,
        "count": len(values),
        "median": statistics.median(values),
        "p75": percentile(values, 0.75),
        "p90": percentile(values, 0.90),
        "p99": percentile(values, 0.99),
        "max": max(values),
    }


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")

    pool = json.loads(POOL.read_text(encoding="utf-8"))
    mathos = [
        score_of(p.get("statement_tex") or "", p.get("solution_tex") or "")
        for p in pool["problems"]
    ]

    fixed_reference, reference_metadata = load_fixed_reference()
    handmade = [
        score_of(item.get("statement", ""), item.get("solution", ""))
        for item in fixed_reference
    ]

    world = load_world_corpus()
    past = []
    for item in world:
        try:
            past.append(score_of(item.get("statement", "")))
        except ValueError:
            continue

    rows = [
        describe("MathOS 生成", mathos),
        describe("手作りの難問", handmade),
        describe("過去問", past),
    ]

    print("旧難易度特徴量の分布（診断専用・配信ゲート無効）")
    print(
        f"固定参照: {reference_metadata['version']} / "
        f"{reference_metadata['count']}問 / "
        f"sha256={reference_metadata['sha256']}"
    )
    print(f"{'集合':<14}{'問題数':>8}{'中央値':>9}{'75%':>8}{'90%':>8}{'99%':>8}{'最大':>8}")
    for row in rows:
        if not row["count"]:
            print(f"{row['name']:<14}{'—':>8}")
            continue
        print(
            f"{row['name']:<14}{row['count']:>8}"
            f"{row['median']:>9.2f}{row['p75']:>8.2f}{row['p90']:>8.2f}"
            f"{row['p99']:>8.2f}{row['max']:>8.2f}"
        )

    print()
    for reference, label in ((handmade, "手作りの難問"), (past, "過去問")):
        if not reference or not mathos:
            continue
        for q, tag in ((0.5, "中央値"), (0.75, "75%点"), (0.9, "90%点")):
            threshold = percentile(reference, q)
            above = sum(1 for value in mathos if value >= threshold)
            print(
                f"  {label}の{tag}({threshold:.2f}) を超える MathOS の問題: "
                f"{above}/{len(mathos)} ({above / len(mathos):.0%})"
            )
        print()

    # 射の連鎖の深さも並べておく（生成側にしかない指標）
    depths = [
        len((p.get("lift_certificate") or {}).get("morphism_chain") or [])
        for p in pool["problems"]
    ]
    if depths:
        print(f"射の連鎖の深さ: 中央値 {statistics.median(depths):.0f} / "
              f"最大 {max(depths)} / 平均 {statistics.mean(depths):.1f}")

    print()
    print("読み方: 人手採否に対する観測 AUC は 0.086（逆相関）。")
    print("        AUC 0.7 以上で再較正されるまで削除・配信判定に使わない。")
    print(f"        現在のゲート状態: {DIFFICULTY_GATING_ENABLED}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
