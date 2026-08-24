"""Build evidence-only dossiers for every unresolved HAGeo rerun item."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _step_text(step: dict[str, Any]) -> str:
    inputs = ",".join(str(item) for item in step.get("inputs", ()))
    return f"{step.get('family', '?')}({inputs})->{step.get('output', '?')}"


def _atom_text(atom: dict[str, Any]) -> str:
    arguments = ",".join(str(item) for item in atom.get("arguments", ()))
    return f"{atom.get('predicate', '?')}({arguments})"


def _record_rank(record: dict[str, Any]) -> tuple[Any, ...]:
    dag = record.get("proof_dag_progress") or {}
    return (
        int(record.get("goal_deduction_count", 0)),
        int(dag.get("structurally_closed_branch_count", 0)),
        int(dag.get("progressed_branch_count", 0)),
        int(dag.get("max_exact_covered_atoms", 0)),
        int(record.get("ar_closed_goal_count", 0)),
        int(record.get("relation_target_assertion_count", 0)),
        int(record.get("relation_near_goal_count", 0)),
        -int(dag.get("best_structural_residual_count", 10**9)),
        -float(record.get("ar_residual_l1_weight", 10**9)),
        int(record.get("all_deduction_count", 0)),
    )


def _open_premises(record: dict[str, Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for obligation in record.get("backward_obligations", ()) or ():
        for atom in obligation.get("open_premises", ()) or ():
            rendered = _atom_text(atom)
            if rendered not in seen:
                seen.add(rendered)
                result.append(rendered)
    return result


def _open_predicates(records: Iterable[dict[str, Any]]) -> list[list[Any]]:
    counts: Counter[str] = Counter()
    for record in records:
        for demand in record.get("open_relation_demands", ()) or ():
            predicate = str(demand.get("predicate", "?"))
            counts[predicate] += 1
    return [[name, count] for name, count in counts.most_common()]


def _frontier(record: dict[str, Any], *, limit: int = 8) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for witness in (record.get("frontier_witnesses", ()) or ())[:limit]:
        rows.append(
            {
                "relation": _atom_text(
                    {
                        "predicate": witness.get("channel", "?"),
                        "arguments": witness.get("points", ()),
                    }
                ),
                "rule": witness.get("rule"),
                "distance_to_goal": witness.get("distance_to_goal"),
                "goal_support_overlap": witness.get("goal_support_overlap"),
                "proof_reference": witness.get("proof_reference"),
            }
        )
    return rows


def _source_formulation(native_result: dict[str, Any]) -> str:
    source = ROOT / str(native_result["input_path"])
    return source.read_text(encoding="utf-8").strip() if source.is_file() else ""


def build_dossier(
    run: dict[str, Any],
    *,
    native_results: dict[str, Any],
) -> dict[str, Any]:
    name = str(run["problem"])
    native = native_results[name]
    artifact_path_raw = run.get("artifact") or run.get("checkpoint")
    artifact_path = ROOT / str(artifact_path_raw)
    artifact = _load(artifact_path)
    records = list(artifact.get("records", ()) or ())
    ranked = sorted(records, key=_record_rank, reverse=True)
    best = ranked[0] if ranked else {}
    visible = artifact.get("visible_formulation") or _source_formulation(native)
    top_attempts = []
    for record in ranked[:3]:
        dag = record.get("proof_dag_progress") or {}
        top_attempts.append(
            {
                "path": [_step_text(step) for step in record.get("steps", ()) or ()],
                "goal_deduction_count": record.get("goal_deduction_count", 0),
                "all_deduction_count": record.get("all_deduction_count", 0),
                "proof_dag": dag,
                "ar_closed_goal_count": record.get("ar_closed_goal_count", 0),
                "ar_residual_l1_weight": record.get("ar_residual_l1_weight"),
                "open_premises": _open_premises(record)[:12],
                "frontier_witnesses": _frontier(record),
                "right_censored": bool(record.get("right_censored")),
                "error": record.get("error"),
            }
        )
    return {
        "problem": name,
        "status": run.get("status"),
        "interpretation": (
            "right_censored; no mathematical failure conclusion"
            if run.get("status") == "right_censored_timeout"
            else "search completed without a native solved certificate"
        ),
        "visible_formulation": visible,
        "native_baseline": {
            "status": native.get("status"),
            "input_path": native.get("input_path"),
            "input_sha256": native.get("input_sha256"),
            "proof_path": native.get("proof_path"),
            "proof_sha256": native.get("proof_sha256"),
            "all_deduction_count": native.get("all_deduction_count", 0),
            "goal_deduction_count": native.get("deduction_count", 0),
        },
        "auxiliary_search": {
            "artifact": str(artifact_path_raw),
            "artifact_sha256": run.get("artifact_sha256")
            or run.get("checkpoint_sha256"),
            "scheduled_paths": artifact.get("scheduled_path_count"),
            "evaluated_paths": run.get("evaluated_paths")
            or artifact.get("evaluated_path_count")
            or len(records),
            "elapsed_seconds": run.get("elapsed_seconds"),
            "open_predicate_frequency": _open_predicates(records),
            "best_observed_attempts": top_attempts,
        },
    }


def _markdown(dossiers: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    lines = [
        "# HAGeo current rerun: unresolved dossiers",
        "",
        "## 判定規約",
        "",
        "- `completed_unsolved` は不正解ではなく、今回の有限探索で証明書が閉じなかったことだけを表す。",
        "- `right_censored_timeout` は時間打切りであり、数学的な失敗判定には使わない。",
        "- 原因名は推測せず、実際の補助構成、証明DAG、未充足前提だけを記録する。",
        "",
        "## 集計",
        "",
        f"- 未証明 dossier: {summary['unresolved_total']}問",
        f"- 探索完了・証明書なし: {summary['completed_unsolved']}問",
        f"- 時間打切り: {summary['right_censored_timeout']}問",
        "",
    ]
    for dossier in dossiers:
        auxiliary = dossier["auxiliary_search"]
        lines.extend(
            [
                f"## {dossier['problem']}",
                "",
                f"- 状態: `{dossier['status']}`",
                f"- 解釈: {dossier['interpretation']}",
                f"- 探索候補: {auxiliary['evaluated_paths']}",
                f"- 経過秒: {auxiliary['elapsed_seconds']}",
                f"- 入力: `{dossier['native_baseline']['input_sha256']}`",
                "",
                "```text",
                str(dossier["visible_formulation"]),
                "```",
                "",
            ]
        )
        for index, attempt in enumerate(auxiliary["best_observed_attempts"], start=1):
            dag = attempt["proof_dag"]
            path = " -> ".join(attempt["path"]) or "(補助構成なし)"
            lines.extend(
                [
                    f"### 観測上位 {index}",
                    "",
                    f"- 構成経路: `{path}`",
                    f"- 全演繹: {attempt['all_deduction_count']}",
                    f"- ゴール演繹: {attempt['goal_deduction_count']}",
                    f"- 進展DAG枝: {dag.get('progressed_branch_count', 0)}",
                    f"- 構造的に閉じた枝: {dag.get('structurally_closed_branch_count', 0)}",
                    f"- 最小残余前提数: {dag.get('best_structural_residual_count')}",
                    "- 未充足前提:",
                ]
            )
            premises = attempt["open_premises"]
            lines.extend(f"  - `{premise}`" for premise in premises)
            if not premises:
                lines.append("  - 記録なし")
            lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--native-report", type=Path, required=True)
    parser.add_argument("--aux-report", type=Path, required=True)
    parser.add_argument("--json-output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, required=True)
    args = parser.parse_args()

    native = _load(args.native_report.resolve())
    auxiliary = _load(args.aux_report.resolve())
    unresolved_runs = [run for run in auxiliary["runs"] if not run.get("solved")]
    dossiers = [
        build_dossier(run, native_results=native["results"])
        for run in unresolved_runs
    ]
    statuses = Counter(str(item["status"]) for item in dossiers)
    summary = {
        "unresolved_total": len(dossiers),
        "completed_unsolved": statuses["unsolved"],
        "right_censored_timeout": statuses["right_censored_timeout"],
        "execution_error": statuses["error"],
    }
    payload = {
        "experiment": "hageo_current_unresolved_evidence_dossiers",
        "protocol": {
            "uses_external_llm": False,
            "diagnosis_policy": "record evidence; do not infer a cause label",
        },
        "summary": summary,
        "dossiers": dossiers,
    }
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    args.markdown_output.write_text(
        _markdown(dossiers, summary), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
