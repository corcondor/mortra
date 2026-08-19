"""Benchmark MathOS solver on generated curriculum items.

This closes the loop:

    problem synthesis -> verified curriculum item -> solver input -> normal-form judging

The key point is that grading uses algebraic normal forms, not answer strings.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

try:
    from math_os_prototype.math_os import MathIR, run_pipeline
    from math_os_prototype.problem_phase_synthesis import (
        canonical_envelope_relation,
        canonical_region_inequality,
    )
    from math_os_prototype.reasoning_pipeline import extract_answer
except ImportError:  # Allows direct script execution.
    from math_os import MathIR, run_pipeline
    from problem_phase_synthesis import canonical_envelope_relation, canonical_region_inequality
    from reasoning_pipeline import extract_answer


DEFAULT_CURRICULUM = Path("C:/Users/81808/.openclaw/workspace/math_os_prototype/problem_synthesis/geometry_sweep_repair1.json")
DEFAULT_OUTPUT = Path("C:/Users/81808/.openclaw/workspace/math_os_prototype/problem_synthesis/synthetic_curriculum_benchmark.json")


@dataclass
class CurriculumBenchmarkRow:
    index: int
    mode: str
    task: str
    source: str
    input_text: str
    expected_normal_form: str
    predicted_answer: str | None
    predicted_normal_form: str | None
    correct: bool
    status: str
    intent: str
    route: str
    tool_statuses: list[dict[str, Any]]
    failure_layer: str | None
    notes: list[str]


def load_curriculum(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get("curriculum_items", [])
    if not items:
        raise ValueError(f"No curriculum_items found in {path}")
    return items


def run_curriculum_benchmark(items: list[dict[str, Any]], *, modes: list[str], limit: int | None) -> dict[str, Any]:
    selected = items[:limit] if limit is not None else items
    rows: list[CurriculumBenchmarkRow] = []
    for index, item in enumerate(selected, start=1):
        for mode in modes:
            input_text = input_for_mode(item, mode)
            ir = run_pipeline(input_text)
            predicted_answer = extract_answer(ir)
            predicted_normal = normalize_solver_answer(ir, item["task"], predicted_answer)
            expected_normal = item["normal_form"]["normal_form"]
            correct = predicted_normal == expected_normal
            status = "correct" if correct else "wrong" if predicted_answer else "abstain"
            rows.append(
                CurriculumBenchmarkRow(
                    index=index,
                    mode=mode,
                    task=item["task"],
                    source=item["source"],
                    input_text=input_text,
                    expected_normal_form=expected_normal,
                    predicted_answer=predicted_answer,
                    predicted_normal_form=predicted_normal,
                    correct=correct,
                    status=status,
                    intent=ir.intent,
                    route=ir.route,
                    tool_statuses=[
                        {
                            "name": call.name,
                            "status": call.status,
                            "error": call.error,
                        }
                        for call in ir.tool_calls
                    ],
                    failure_layer=None if correct else classify_failure(ir, predicted_answer, predicted_normal),
                    notes=ir.notes,
                )
            )
    return summarize_rows(rows)


def input_for_mode(item: dict[str, Any], mode: str) -> str:
    if mode == "dsl":
        return item["dsl"]
    if mode == "tex":
        return item["input_tex"]
    if mode == "tex_mutation":
        expr = latexish_expression_from_dsl(item["dsl"])
        if item["task"] == "region":
            body = f"$t\\in\\mathbb{{R}}$ とする。曲線 \\( y={expr} \\) が通る点全体の領域を求めよ。"
        else:
            body = f"$t\\in\\mathbb{{R}}$ とする。曲線族 \\( y={expr} \\) の包絡線を求めなさい。"
        return body
    if mode == "full_tex":
        expr = latexish_expression_from_dsl(item["dsl"])
        task_text = "通過領域を求めよ" if item["task"] == "region" else "包絡線を求めよ"
        return (
            "\\documentclass[11pt]{article}\n"
            "\\usepackage{amsmath,amssymb}\n"
            "\\begin{document}\n"
            "\\begin{itemize}\n"
            "\\item $t\\in\\mathbb{R}$ とする。曲線族\n"
            "\\[\n"
            f"y={expr}\n"
            "\\]\n"
            f"について，その{task_text}。\n"
            "\\end{itemize}\n"
            "\\end{document}\n"
        )
    raise ValueError(f"unsupported mode: {mode}")


def latexish_expression_from_dsl(dsl: str) -> str:
    marker = "family y ="
    if marker not in dsl:
        raise ValueError(f"cannot extract family from DSL: {dsl}")
    expr = dsl.split(marker, 1)[1].split("; param", 1)[0].strip()
    expr = expr.replace("**2", "^2")
    expr = expr.replace("*", "")
    return expr


def normalize_solver_answer(ir: MathIR, expected_task: str, predicted_answer: str | None) -> str | None:
    geometry_result = extract_geometry_result(ir)
    if geometry_result is not None:
        if expected_task == "region":
            closed_form = geometry_result.get("closed_form", {})
            inequality = closed_form.get("inequality")
            if inequality:
                return canonical_region_inequality(inequality)["normal_form"]
        if expected_task == "envelope":
            relation = geometry_result.get("envelope_relation")
            if relation:
                return canonical_envelope_relation(f"{relation} = 0")["normal_form"]
    if not predicted_answer:
        return None
    try:
        if expected_task == "region":
            return canonical_region_inequality(predicted_answer)["normal_form"]
        if expected_task == "envelope":
            return canonical_envelope_relation(predicted_answer)["normal_form"]
    except Exception:
        return None
    return None


def extract_geometry_result(ir: MathIR) -> dict[str, Any] | None:
    for call in ir.tool_calls:
        if call.name != "geometry.dsl" or not isinstance(call.result, dict):
            continue
        result = call.result.get("result")
        if isinstance(result, dict):
            return result
    return None


def classify_failure(ir: MathIR, predicted_answer: str | None, predicted_normal: str | None) -> str:
    if not ir.tool_calls:
        return "parser_or_lifter"
    if all(call.status != "executed" for call in ir.tool_calls):
        return "backend_not_executed"
    if any(call.status == "failed" for call in ir.tool_calls):
        return "backend_failed"
    if predicted_answer is None:
        return "answer_extraction"
    if predicted_normal is None:
        return "normalization"
    return "semantic_mismatch"


def summarize_rows(rows: list[CurriculumBenchmarkRow]) -> dict[str, Any]:
    by_mode: dict[str, Counter[str]] = defaultdict(Counter)
    by_task: dict[str, Counter[str]] = defaultdict(Counter)
    by_failure: Counter[str] = Counter()
    for row in rows:
        by_mode[row.mode][row.status] += 1
        by_task[f"{row.mode}:{row.task}"][row.status] += 1
        if row.failure_layer:
            by_failure[row.failure_layer] += 1

    def metrics(counter: Counter[str]) -> dict[str, Any]:
        total = sum(counter.values())
        correct = counter.get("correct", 0)
        answered = correct + counter.get("wrong", 0)
        return {
            "total": total,
            "correct": correct,
            "wrong": counter.get("wrong", 0),
            "abstain": counter.get("abstain", 0),
            "exact_rate": round(correct / total, 4) if total else 0.0,
            "precision": round(correct / answered, 4) if answered else 0.0,
        }

    total_counter = Counter(row.status for row in rows)
    return {
        "summary": {
            "overall": metrics(total_counter),
            "by_mode": {mode: metrics(counter) for mode, counter in sorted(by_mode.items())},
            "by_task": {task: metrics(counter) for task, counter in sorted(by_task.items())},
            "failure_layers": dict(by_failure),
        },
        "rows": [asdict(row) for row in rows],
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Synthetic Curriculum Solver Benchmark")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    for name, data in report["summary"]["by_mode"].items():
        lines.append(
            f"- {name}: {data['correct']}/{data['total']} "
            f"exact={data['exact_rate']} precision={data['precision']} "
            f"wrong={data['wrong']} abstain={data['abstain']}"
        )
    lines.append("")
    lines.append("## By Task")
    lines.append("")
    for name, data in report["summary"]["by_task"].items():
        lines.append(
            f"- {name}: {data['correct']}/{data['total']} "
            f"exact={data['exact_rate']} wrong={data['wrong']} abstain={data['abstain']}"
        )
    lines.append("")
    lines.append("## Failure Layers")
    lines.append("")
    if report["summary"]["failure_layers"]:
        for layer, count in sorted(report["summary"]["failure_layers"].items()):
            lines.append(f"- {layer}: {count}")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Interpretation")
    lines.append("")
    lines.append(
        "This benchmark checks whether generated, verified problems can be fed back "
        "to the ordinary MathOS solver.  The DSL mode isolates backend correctness; "
        "the TeX mode additionally tests LaTeX/NL parsing and lifting.  A correct "
        "answer requires algebraic normal-form equality, not string equality."
    )
    return "\n".join(lines) + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark solver on generated curriculum items.")
    parser.add_argument("--curriculum", type=Path, default=DEFAULT_CURRICULUM)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--modes",
        default="tex,dsl",
        help="Comma-separated modes: tex,dsl,tex_mutation,full_tex",
    )
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    modes = [mode.strip() for mode in args.modes.split(",") if mode.strip()]
    items = load_curriculum(args.curriculum)
    report = run_curriculum_benchmark(items, modes=modes, limit=args.limit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path = args.output.with_name(args.output.stem + "_report.md")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": True,
                "output": str(args.output),
                "report": str(md_path),
                "summary": report["summary"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
