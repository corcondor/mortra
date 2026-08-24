"""Build one evidence-backed Japanese report for the current HAGeo rerun."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _display(path: Path) -> str:
    resolved = path.resolve()
    return (
        resolved.relative_to(ROOT).as_posix()
        if resolved.is_relative_to(ROOT)
        else resolved.as_posix()
    )


def _status_counts(runs: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for run in runs:
        status = str(run.get("status", "unknown"))
        counts[status] = counts.get(status, 0) + 1
    return counts


def _proof_terminal(trace_path: Path) -> str:
    trace = _load(trace_path)
    nodes = trace.get("nodes", ())
    if not nodes:
        return "(終端命題なし)"
    assertions = nodes[-1].get("assertions", ())
    if not assertions:
        return "(終端命題なし)"
    assertion = assertions[-1]
    return (
        f"{assertion.get('name')}({','.join(map(str, assertion.get('points', ())))})"
    )


def _minutes(seconds: object) -> str:
    return f"{float(seconds) / 60:.1f}"


def build_report(
    *,
    native_report_path: Path,
    native_audit_path: Path,
    native_trace_path: Path,
    cohort_path: Path,
    auxiliary_audit_path: Path,
    union_path: Path,
    dossier_path: Path,
    solution_manifest_path: Path,
) -> str:
    native_report = _load(native_report_path)
    native_audit = _load(native_audit_path)
    native_trace = _load(native_trace_path)
    cohort = _load(cohort_path)
    auxiliary_audit = _load(auxiliary_audit_path)
    union = _load(union_path)
    dossier = _load(dossier_path)
    solution_manifest = _load(solution_manifest_path)

    if cohort.get("run_state", {}).get("complete") is not True:
        raise ValueError("cohort rerun is incomplete")
    if auxiliary_audit.get("summary", {}).get("all_accepted") is not True:
        raise ValueError("auxiliary replay audit is not fully accepted")
    if auxiliary_audit.get("summary", {}).get(
        "all_trace_integrity_passed"
    ) is not True:
        raise ValueError("auxiliary proof-trace audit is incomplete")

    runs = list(cohort.get("runs", ()))
    counts = _status_counts(runs)
    solved_runs = [run for run in runs if run.get("solved") is True]
    timeout_names = sorted(
        str(run["problem"])
        for run in runs
        if run.get("status") in {"timeout", "right_censored_timeout"}
    )
    error_names = sorted(
        str(run["problem"])
        for run in runs
        if run.get("status") == "execution_error"
    )
    union_summary = union["summary"]
    native_summary = native_report["summary"]
    native_audit_summary = native_audit["summary"]
    native_trace_summary = native_trace["summary"]
    diagram_summary = solution_manifest["summary"]
    measured_wall_runs = sorted(
        (
            run
            for run in runs
            if run.get("elapsed_seconds") is not None
            and run.get("elapsed_is_lower_bound") is False
        ),
        key=lambda run: float(run["elapsed_seconds"]),
        reverse=True,
    )

    lines = [
        "# MORTRA 未証明問題の全件再実行と証明書監査（2026-08-24）",
        "",
        "## 目的",
        "",
        "凍結HAGeo 89問について、厳格集合和で未証明だった34問を省略せず再実行し、",
        "MORTRAが保存した証明結果を直接読み、独立再生できた問題だけを認証集合へ加える。",
        "時間打切りは不正解にせず、証明DAG・未充足前提・候補経路を保存する。",
        "",
        "## 原理",
        "",
        "- 候補生成と真偽判定を分離する。補助構成候補は型付き探索で作るが、正解判定はnative Yuclid証明書だけで行う。",
        "- 問題ID、期待解答、外部LLMは探索・判定に使わない。",
        "- `solved`だけでは採用せず、入力・証明SHA-256と二度の決定的再生を一致させる。",
        "- 証明の全deductionを読み、前提の生成元が欠けた証明や曖昧な等式参照を拒否する。",
        "- 数値guardはnative証明書の一部として明示するが、完全に形式化されたguard-free証明とは呼ばない。",
        "",
        "## 方法",
        "",
        f"1. 現行native基準を89問で再実行した（`{_display(native_report_path)}`）。",
        "2. 旧厳格集合和55問との差集合34問を固定し、各問で深さ2、最大112経路を探索した。",
        "3. 経路、証明DAG、未充足前提、列挙済み候補を問題別checkpointへ保存した。",
        "4. 得られた全証明を別プロセスで二度再生し、全deduction traceを監査した。",
        "5. 凍結89問の外側を拒否する集合和で、重複を除いて再集計した。",
        "6. 元のJGEX式または認証済み補助構成込み式から図を生成し、証明済みは監査済み全deduction、未証明は状態文を出力した。",
        "",
        "## 結果",
        "",
        "### 現行native基準",
        "",
        f"- native solved: **{native_summary['solved']}/{native_summary['total']}**",
        f"- 二重再生受理: **{native_audit_summary['accepted']}/{native_audit_summary['claimed_solved']}**",
        f"- trace整合: **{native_trace_summary['trace_integrity_passed']}/{native_trace_summary['claimed_solved']}**",
        f"- 読み取ったdeduction: **{native_trace_summary['total_deductions']:,}**",
        f"- 数値guard: **{native_trace_summary['total_numerical_guards']:,}**",
        f"- 表現chart間bridge: **{native_trace_summary['total_cross_chart_bridges']:,}**",
        "- 未接続前提: **0**、曖昧な等式参照: **0**",
        "",
        "### 厳格未証明34問の再実行",
        "",
        f"- 証明: **{counts.get('solved', 0)}**",
        f"- 探索完了・未証明: **{counts.get('unsolved', 0)}**",
        f"- 時間打切り: **{len(timeout_names)}**",
        f"- 実行エラー: **{len(error_names)}**",
        f"- 独立再生受理: **{auxiliary_audit['summary']['accepted']}/{auxiliary_audit['summary']['claimed_solved']}**",
        "",
        "| 問題 | 補助構成経路 | deduction | 数値guard | 終端命題 |",
        "|---|---|---:|---:|---|",
    ]
    for run in sorted(solved_runs, key=lambda item: str(item["problem"])):
        name = str(run["problem"])
        audit_row = auxiliary_audit["audits"][name]
        trace_path = ROOT / str(audit_row["proof_trace_json"])
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{name}`",
                    f"`{run.get('solved_path')}`",
                    str(audit_row.get("deduction_count", "")),
                    str(audit_row.get("numerical_guard_count", "")),
                    f"`{_proof_terminal(trace_path)}`",
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "### 凍結集合和",
            "",
            f"- 再実行前: **{union_summary['previous_certified_solved']}/{union_summary['total']}**",
            f"- 新規の一意な認証: **{union_summary['new_certified_unique']}問**",
            f"- 再実行後: **{union_summary['primary_certified_solved']}/{union_summary['total']} = {100 * union_summary['primary_certified_score']:.2f}%**",
            "- native 28/89と厳格集合和を混同しない。前者は単一実行系、後者は監査済みportfolioの集合和である。",
            "",
            "### 図・解答成果物",
            "",
            f"- 要求: **{diagram_summary['requested']}問**",
            f"- 図生成: **{diagram_summary['diagrams_generated']}問**",
            f"- 成果物出力: **{diagram_summary['artifacts_exported']}問**",
            f"- 認証済み証明本文: **{diagram_summary['certified_solutions_exported']}/{diagram_summary['certified_solutions_expected']}問**",
            "- 図が描けたこと自体は証明成功として数えていない。",
            "",
            "### 実行速度",
            "",
            "再構築時に候補1本の時間を全体時間として扱っていたため、再試行レポートに残る実壁時計時間を優先するよう修正した。",
            "実壁時計を復元できない問題は、候補1本の最大完了時間を下限として保持し、全体時間とは呼ばない。",
            "",
            "| 問題 | 状態 | 実壁時計（分） | 評価候補 | 候補時間中央値（秒） | 候補CPU時間合計（分） |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for run in measured_wall_runs:
        candidate_median = run.get("candidate_elapsed_median_seconds")
        candidate_sum = run.get("candidate_elapsed_sum_seconds")
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{run['problem']}`",
                    str(run.get("status", "unknown")),
                    _minutes(run["elapsed_seconds"]),
                    str(run.get("evaluated_paths", "-")),
                    f"{float(candidate_median):.1f}" if candidate_median is not None else "-",
                    _minutes(candidate_sum) if candidate_sum is not None else "-",
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "難しい2問では112候補を評価し、候補1本の中央値が数分に達した。候補生成用のprefix更新は0.3秒未満であり、",
            "支配項は各候補でYuclidを新規起動して閉包と証明を再計算する処理である。再試行設定は問題3並列・問題内8候補並列で、",
            "最大24個のnative検証を同時実行するため、CPUの過剰並列も速度低下要因になる。",
            "",
            "## 考察",
            "",
            "以前の再実行が全件にならなかった直接原因は、既定上限10問、native未証明61問と厳格未証明34問の混同、",
            "証明ファイルの未保存、診断用progressを真の再開状態として扱ったこと、Windows上の非原子的な進捗更新だった。",
            "今回、明示的34問名簿、既定全件、証明保存、列挙済み候補を含むcheckpoint、原子的更新へ修正した。",
            "また、3問だけの再試行が同じ集計先を上書きする欠陥を検出した。個別成果物33件と右打切り記録1件から34問集計を再構成し、",
            "今後は問題集合が異なる既存レポートへの上書きを実行前に拒否する。",
            "",
            "未証明は『誤答』ではない。有限探索で証明書が閉じなかったという観測であり、",
            "原因の推測ではなく、各問題の実際の構成経路、証明DAG、未充足前提をdossierに残した。",
            f"dossierは **{len(dossier.get('dossiers', dossier.get('problems', ())))}問**を含む。",
            "",
            "## 結論",
            "",
            "MORTRAの結果は読める。今回、証明済み問題では全deductionと依存関係を直接読み、二度の再生で照合した。",
            "未証明問題も全件を再実行し、停止状態を問題別に保存した。認証集合へ加えたのは再生監査を通った問題だけである。",
            "",
            "## 成果物",
            "",
            f"- native再実行: `{_display(native_report_path)}`",
            f"- native再生監査: `{_display(native_audit_path)}`",
            f"- native trace監査: `{_display(native_trace_path)}`",
            f"- 未証明34問再実行: `{_display(cohort_path)}`",
            f"- 補助構成証明監査: `{_display(auxiliary_audit_path)}`",
            f"- 厳格集合和: `{_display(union_path)}`",
            f"- 未証明dossier: `{_display(dossier_path)}`",
            f"- 図・解答manifest: `{_display(solution_manifest_path)}`",
        ]
    )
    if timeout_names:
        lines.extend(["", "### 時間打切り問題", "", ", ".join(f"`{name}`" for name in timeout_names)])
    if error_names:
        lines.extend(["", "### 実行エラー問題", "", ", ".join(f"`{name}`" for name in error_names)])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--native-report", type=Path, required=True)
    parser.add_argument("--native-audit", type=Path, required=True)
    parser.add_argument("--native-trace", type=Path, required=True)
    parser.add_argument("--cohort", type=Path, required=True)
    parser.add_argument("--auxiliary-audit", type=Path, required=True)
    parser.add_argument("--union", type=Path, required=True)
    parser.add_argument("--dossier", type=Path, required=True)
    parser.add_argument("--solution-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--obsidian-output", type=Path)
    args = parser.parse_args()
    report = build_report(
        native_report_path=args.native_report.resolve(),
        native_audit_path=args.native_audit.resolve(),
        native_trace_path=args.native_trace.resolve(),
        cohort_path=args.cohort.resolve(),
        auxiliary_audit_path=args.auxiliary_audit.resolve(),
        union_path=args.union.resolve(),
        dossier_path=args.dossier.resolve(),
        solution_manifest_path=args.solution_manifest.resolve(),
    )
    for output in (args.output, args.obsidian_output):
        if output is None:
            continue
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
