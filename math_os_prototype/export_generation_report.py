"""検証済みプールから公開用の日本語生成レポートを作る。"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
DEFAULT_POOL = HERE / "problem_synthesis" / "construct_pool.json"
DEFAULT_OUTPUT = HERE / "docs" / "generated" / "latest-generation-report.md"


def _band(problem: dict[str, Any]) -> str:
    difficulty = problem.get("difficulty")
    if isinstance(difficulty, dict):
        return str(difficulty.get("band", "未評価"))
    return str(difficulty or "未評価")


def _score(problem: dict[str, Any]) -> float:
    difficulty = problem.get("difficulty")
    if isinstance(difficulty, dict):
        return float(difficulty.get("score", 0))
    return 0.0


def _format_time(value: str) -> str:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime(
            "%Y-%m-%d %H:%M:%S %z"
        )
    except ValueError:
        return value


def build_report(payload: dict[str, Any]) -> str:
    problems = [p for p in payload.get("problems", []) if p.get("accepted")]
    summary = payload.get("summary", {})
    family_counts = Counter(p.get("family_id", "unknown") for p in problems)
    band_counts = Counter(_band(p) for p in problems)
    deep = [
        p
        for p in problems
        if str(p.get("family_id", "")).startswith(("deep.", "ultradeep."))
    ]
    ultradeep = [
        p
        for p in deep
        if str(p.get("family_id", "")).startswith("ultradeep.")
    ]
    representative: dict[str, dict[str, Any]] = {}
    for problem in sorted(deep, key=_score, reverse=True):
        representative.setdefault(problem["family_id"], problem)

    exact = sum(bool(p.get("verification", {}).get("exact_backend")) for p in problems)
    independent = sum(
        bool(p.get("verification", {}).get("independent_check")) for p in problems
    )
    typed = sum(
        bool(p.get("lift_certificate", {}).get("type_checked")) for p in problems
    )
    novel = sum(bool(p.get("novelty", {}).get("corpus_novel")) for p in problems)

    lines = [
        "# MathOS 自律作問・検証レポート",
        "",
        "> この文書は `problem_synthesis/construct_pool.json` から機械的に生成される。",
        "> 問題文や実績値を手作業で書き換えない。",
        "",
        "## スナップショット",
        "",
        f"- 生成日時: `{_format_time(str(payload.get('generated_at', 'unknown')))}`",
        f"- 検証済み問題インスタンス: **{len(problems)}問**",
        f"- 構造族: **{len(family_counts)}族**",
        f"- 深層族: **{len(deep)}問 / {len(representative)}族**",
        f"- うち10射以上の超深層族: **{len(ultradeep)}問 / "
        f"{len({p['family_id'] for p in ultradeep})}族**",
        f"- 世界コーパス: **{summary.get('world_corpus_size', '未記録')}問**",
        "",
        "| 難易度帯 | 問題数 |",
        "|---|---:|",
    ]
    for band, count in sorted(band_counts.items()):
        lines.append(f"| `{band}` | {count} |")

    lines.extend(
        [
            "",
            "ここで問題インスタンス数は、同じ構造族のパラメータ違いを含む。",
            "創造性・構造多様性はインスタンス数ではなく構造族数と射列で評価する。",
            "",
            "## 生成ループ",
            "",
            "```text",
            "型付き対象とパラメータを生成",
            "  → 射を合成して観測量を定義",
            "  → 専門backendで答を計算",
            "  → 独立手段で反例・計算を照合",
            "  → 世界コーパスとの衝突を検査",
            "  → 難易度を推定",
            "  → 合格候補だけを蓄積",
            "```",
            "",
            "直近ループの記録:",
            "",
            f"- 生成候補: {summary.get('run_stats', {}).get('generated', '未記録')}",
            f"- 重複棄却: {summary.get('run_stats', {}).get('dup', '未記録')}",
            f"- 新規性棄却: {summary.get('run_stats', {}).get('not_novel', '未記録')}",
            f"- 検証失敗: {summary.get('run_stats', {}).get('unverified', '未記録')}",
            f"- 今回追加: {summary.get('added_this_run', '未記録')}",
            "",
            "## 検証ゲート",
            "",
            "| ゲート | 通過 |",
            "|---|---:|",
            f"| backend計算 | {exact}/{len(problems)} |",
            f"| 独立検証 | {independent}/{len(problems)} |",
            f"| LiftCertificate型検査 | {typed}/{len(problems)} |",
            f"| コーパス新規性 | {novel}/{len(problems)} |",
            "",
            "## 深層族の生成例",
            "",
            "深層族は1問につき8個以上、超深層族は10〜12個の射を合成する。"
            "以下は各族で難易度推定値が",
            "最も高い実データであり、説明用に新しく書き直した問題ではない。",
            "",
        ]
    )

    for family, problem in sorted(representative.items()):
        lift = problem.get("lift_certificate", {})
        novelty = problem.get("novelty", {})
        verification = problem.get("verification", {})
        chain = " → ".join(lift.get("morphism_chain", []))
        lines.extend(
            [
                f"### `{family}`",
                "",
                f"- 難易度: `{_band(problem)}` / score `{_score(problem):.2f}`",
                f"- backend: `{problem.get('tool', '未記録')}`",
                f"- 独立検証: `{verification.get('method', '未記録')}`",
                f"- 最大表層類似度: `{novelty.get('maximum_surface_jaccard', '未記録')}`",
                f"- 射: `{chain}`",
                "",
                "**問題**",
                "",
                str(problem.get("statement_tex", "")),
                "",
                f"**答**: {problem.get('answer_tex', '')}",
                "",
                "<details>",
                "<summary>検証済み解法記録</summary>",
                "",
                str(problem.get("solution_tex", "")),
                "",
                "</details>",
                "",
            ]
        )

    lines.extend(
        [
            "## 解釈上の注意",
            "",
            "- `A_olympiad` などの難易度は人手採点ではなく、176問で較正した推定器の出力。",
            "- `corpus_novel=true` は登録コーパス内での衝突がないことを示し、",
            "  数学史上まったく新しいことの証明ではない。",
            "- `exact_backend` と `independent_check` は生成器の検査契約であり、",
            "  Leanによる全問の形式証明を意味しない。",
            "- したがって、正しさ・新規性・難易度を同じ一語の「良問」でまとめず、",
            "  それぞれ別の指標として追跡する。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pool", type=Path, default=DEFAULT_POOL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    payload = json.loads(args.pool.read_text(encoding="utf-8"))
    report = build_report(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    print(f"wrote {args.output} ({len(report)} chars)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
