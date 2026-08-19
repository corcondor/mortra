"""Lightweight corpus protocol for LiftCertificate coverage.

This runner is intentionally separate from the full reasoning benchmark.  It
does not run retrieval, explanation generation, or the legacy surface-template
pipeline.  It observes:

    text -> TypedSemanticGraph -> LiftCertificate -> certified backend

The goal is to process many public/TeX problems quickly while recording where
the abstract lifting layer fires, abstains, answers, or answers incorrectly.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import queue
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

try:
    from math_os_prototype.category_semantics import compile_typed_semantic_graph
    from math_os_prototype.lift_backend import solve_from_lift_certificates
    from math_os_prototype.public_benchmark import (
        PublicBenchmarkCase,
        answers_match,
        load_aqua_cases,
        load_asdiv_cases,
        load_gsm8k_cases,
        load_math_cases,
        load_mawps_cases,
        load_multiarith_cases,
        load_svamp_cases,
    )
    from math_os_prototype.tex_benchmark import extract_tex_problems
except ImportError:  # Allows direct script execution.
    from category_semantics import compile_typed_semantic_graph
    from lift_backend import solve_from_lift_certificates
    from public_benchmark import (
        PublicBenchmarkCase,
        answers_match,
        load_aqua_cases,
        load_asdiv_cases,
        load_gsm8k_cases,
        load_math_cases,
        load_mawps_cases,
        load_multiarith_cases,
        load_svamp_cases,
    )
    from tex_benchmark import extract_tex_problems


DEFAULT_OUTPUT = Path("math_os_prototype/corpus_lift_protocol.json")
FROZEN_SELF_AUTHORED_STEMS = {"全問題", "zenmondai", "all_problems_selfauthored"}


@dataclass(frozen=True)
class CorpusCase:
    source: str
    subset: str
    index: int
    problem: str
    expected: str | None = None
    line: int | None = None


@dataclass
class CorpusLiftRecord:
    source: str
    subset: str
    index: int
    line: int | None
    graph_status: str
    lifted: bool
    lift_families: list[str]
    certificate_signatures: list[str]
    backend_executed: bool
    answer: str | None
    expected: str | None
    exact_match: bool | None
    wrong: bool
    rejected: bool
    elapsed_seconds: float
    error: str | None
    text_preview: str


def load_public_cases(args: argparse.Namespace) -> list[CorpusCase]:
    cases: list[CorpusCase] = []
    if args.gsm8k:
        cases.extend(convert_public_cases(load_gsm8k_cases(args.gsm8k)))
    if args.math_per_config:
        cases.extend(convert_public_cases(load_math_cases(args.math_per_config)))
    if args.svamp:
        cases.extend(convert_public_cases(load_svamp_cases(args.svamp)))
    if args.asdiv:
        cases.extend(convert_public_cases(load_asdiv_cases(args.asdiv)))
    if args.aqua:
        cases.extend(convert_public_cases(load_aqua_cases(args.aqua)))
    if args.multiarith:
        cases.extend(convert_public_cases(load_multiarith_cases(args.multiarith)))
    if args.mawps:
        cases.extend(convert_public_cases(load_mawps_cases(args.mawps)))
    return cases


def convert_public_cases(cases: list[PublicBenchmarkCase]) -> list[CorpusCase]:
    return [
        CorpusCase(
            source=case.benchmark,
            subset=case.subset,
            index=case.index,
            problem=case.problem,
            expected=case.expected,
        )
        for case in cases
    ]


def is_frozen_selfauthored_source(path: Path) -> bool:
    return path.stem.strip().lower() in FROZEN_SELF_AUTHORED_STEMS


def load_tex_cases(
    paths: list[Path],
    *,
    limit_per_file: int | None = None,
    allow_frozen_final_eval: bool = False,
) -> list[CorpusCase]:
    cases: list[CorpusCase] = []
    for path in paths:
        if is_frozen_selfauthored_source(path) and not allow_frozen_final_eval:
            raise ValueError(
                f"{path.name} is frozen for final validation and cannot be used in development; "
                "pass allow_frozen_final_eval=True only for the final run"
            )
        problems = extract_tex_problems(path)
        if limit_per_file is not None:
            problems = problems[:limit_per_file]
        for problem in problems:
            cases.append(
                CorpusCase(
                    source=f"TeX:{problem.source}",
                    subset=problem.title,
                    index=problem.index,
                    line=problem.line,
                    problem=problem.text,
                )
            )
    return cases


def evaluate_case(case: CorpusCase) -> CorpusLiftRecord:
    start = time.perf_counter()
    try:
        graph = compile_typed_semantic_graph(case.problem).to_dict()
        admissible = [cert for cert in graph.get("lift_certificates", []) or [] if cert.get("admissible")]
        backend_result = solve_from_lift_certificates(graph) if admissible else None
        answer = str(backend_result.get("answer_exact")) if backend_result else None
        exact = answers_match(answer, case.expected) if case.expected is not None else None
        return CorpusLiftRecord(
            source=case.source,
            subset=case.subset,
            index=case.index,
            line=case.line,
            graph_status=str(graph.get("status") or ""),
            lifted=bool(admissible),
            lift_families=sorted({str(cert.get("family_id")) for cert in admissible if cert.get("family_id")}),
            certificate_signatures=sorted(
                {str(cert.get("canonical_signature")) for cert in admissible if cert.get("canonical_signature")}
            ),
            backend_executed=backend_result is not None,
            answer=answer,
            expected=case.expected,
            exact_match=exact,
            wrong=bool(answer is not None and exact is False),
            rejected=not bool(admissible),
            elapsed_seconds=round(time.perf_counter() - start, 4),
            error=None,
            text_preview=case.problem[:260],
        )
    except Exception as exc:
        return CorpusLiftRecord(
            source=case.source,
            subset=case.subset,
            index=case.index,
            line=case.line,
            graph_status="error",
            lifted=False,
            lift_families=[],
            certificate_signatures=[],
            backend_executed=False,
            answer=None,
            expected=case.expected,
            exact_match=False if case.expected is not None else None,
            wrong=False,
            rejected=True,
            elapsed_seconds=round(time.perf_counter() - start, 4),
            error=str(exc),
            text_preview=case.problem[:260],
        )


def evaluate_case_with_timeout(case: CorpusCase, timeout: float) -> CorpusLiftRecord:
    result_queue: mp.Queue = mp.Queue(maxsize=1)
    process = mp.Process(target=_worker, args=(asdict(case), result_queue))
    process.start()
    process.join(timeout)
    if process.is_alive():
        process.terminate()
        process.join(2)
        return CorpusLiftRecord(
            source=case.source,
            subset=case.subset,
            index=case.index,
            line=case.line,
            graph_status="timeout",
            lifted=False,
            lift_families=[],
            certificate_signatures=[],
            backend_executed=False,
            answer=None,
            expected=case.expected,
            exact_match=False if case.expected is not None else None,
            wrong=False,
            rejected=True,
            elapsed_seconds=round(timeout, 4),
            error=f"case_timeout_after_{timeout:g}s",
            text_preview=case.problem[:260],
        )
    try:
        return CorpusLiftRecord(**result_queue.get_nowait())
    except queue.Empty:
        record = evaluate_case(case)
        record.error = "case_worker_returned_no_record"
        return record


def _worker(case_dict: dict[str, Any], result_queue: mp.Queue) -> None:
    result_queue.put(asdict(evaluate_case(CorpusCase(**case_dict))))


def run_corpus_lift_protocol(
    cases: list[CorpusCase],
    *,
    case_timeout: float | None = None,
    max_cases: int | None = None,
) -> dict[str, Any]:
    if max_cases is not None:
        cases = cases[:max_cases]
    records: list[CorpusLiftRecord] = []
    for case in cases:
        if case_timeout and case_timeout > 0:
            records.append(evaluate_case_with_timeout(case, case_timeout))
        else:
            records.append(evaluate_case(case))
    return summarize(records)


def summarize(records: list[CorpusLiftRecord]) -> dict[str, Any]:
    total = len(records)
    lifted = sum(record.lifted for record in records)
    executed = sum(record.backend_executed for record in records)
    comparable = [record for record in records if record.expected is not None]
    correct = sum(record.exact_match is True for record in comparable)
    wrong = sum(record.wrong for record in records)
    rejected = sum(record.rejected for record in records)
    errors = sum(record.error is not None for record in records)
    return {
        "protocol": [
            "compile_typed_semantic_graph",
            "extract_admissible_LiftCertificate",
            "certified_backend_execution",
            "answer_check_when_gold_available",
            "provenance_by_family_and_signature",
        ],
        "scope_note": (
            "Public/TeX corpora usually lack gold LiftCertificate labels, so this reports coverage, "
            "backend success, wrong answers, and rejection. The full seven-axis match is measured on "
            "generated same-structure families."
        ),
        "counts": {
            "total": total,
            "lifted": lifted,
            "backend_executed": executed,
            "comparable": len(comparable),
            "correct": correct,
            "wrong": wrong,
            "rejected": rejected,
            "errors": errors,
        },
        "rates": {
            "lift_rate": lifted / total if total else 0.0,
            "backend_execution_rate": executed / total if total else 0.0,
            "backend_success_rate": correct / len(comparable) if comparable else 0.0,
            "precision_answered": correct / executed if executed else 0.0,
            "wrong_rate_answered": wrong / executed if executed else 0.0,
            "rejection_rate": rejected / total if total else 0.0,
            "error_rate": errors / total if total else 0.0,
        },
        "by_source": summarize_by(records, "source"),
        "by_family": summarize_family(records),
        "records": [asdict(record) for record in records],
    }


def summarize_by(records: list[CorpusLiftRecord], attr: str) -> dict[str, Any]:
    grouped: dict[str, list[CorpusLiftRecord]] = defaultdict(list)
    for record in records:
        grouped[str(getattr(record, attr))].append(record)
    return {key: summarize_small(items) for key, items in sorted(grouped.items())}


def summarize_family(records: list[CorpusLiftRecord]) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    executed: Counter[str] = Counter()
    correct: Counter[str] = Counter()
    wrong: Counter[str] = Counter()
    for record in records:
        families = record.lift_families or ["<none>"]
        for family in families:
            counts[family] += 1
            executed[family] += int(record.backend_executed)
            correct[family] += int(record.exact_match is True)
            wrong[family] += int(record.wrong)
    return {
        family: {
            "total": counts[family],
            "backend_executed": executed[family],
            "correct": correct[family],
            "wrong": wrong[family],
        }
        for family in sorted(counts)
    }


def summarize_small(records: list[CorpusLiftRecord]) -> dict[str, Any]:
    total = len(records)
    lifted = sum(record.lifted for record in records)
    executed = sum(record.backend_executed for record in records)
    comparable = [record for record in records if record.expected is not None]
    correct = sum(record.exact_match is True for record in comparable)
    wrong = sum(record.wrong for record in records)
    return {
        "total": total,
        "lifted": lifted,
        "backend_executed": executed,
        "correct": correct,
        "wrong": wrong,
        "lift_rate": lifted / total if total else 0.0,
        "backend_execution_rate": executed / total if total else 0.0,
        "backend_success_rate": correct / len(comparable) if comparable else 0.0,
        "wrong_rate_answered": wrong / executed if executed else 0.0,
    }


def write_outputs(result: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    jsonl_path = output.with_suffix(".jsonl")
    with jsonl_path.open("w", encoding="utf-8") as handle:
        for record in result["records"]:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    output.with_name(output.stem + "_report.md").write_text(render_report(result, output, jsonl_path), encoding="utf-8")


def render_report(result: dict[str, Any], output: Path, jsonl_path: Path) -> str:
    counts = result["counts"]
    rates = result["rates"]
    lines = [
        "# Corpus Lift Protocol",
        "",
        "## Scope",
        "",
        result["scope_note"],
        "",
        "## Counts",
        "",
    ]
    for key, value in counts.items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Rates", "", "| metric | value |", "|---|---:|"])
    for key, value in rates.items():
        lines.append(f"| `{key}` | {value:.3f} |")
    lines.extend(["", "## Source Summary", "", "| source | total | lifted | backend | correct | wrong | lift rate | wrong/answered |", "|---|---:|---:|---:|---:|---:|---:|---:|"])
    for source, item in result["by_source"].items():
        lines.append(
            "| {source} | {total} | {lifted} | {backend} | {correct} | {wrong} | {lift_rate:.3f} | {wrong_answered:.3f} |".format(
                source=source,
                total=item["total"],
                lifted=item["lifted"],
                backend=item["backend_executed"],
                correct=item["correct"],
                wrong=item["wrong"],
                lift_rate=item["lift_rate"],
                wrong_answered=item["wrong_rate_answered"],
            )
        )
    lines.extend(["", "## Family Summary", "", "| family | total | backend | correct | wrong |", "|---|---:|---:|---:|---:|"])
    for family, item in result["by_family"].items():
        lines.append(
            f"| `{family}` | {item['total']} | {item['backend_executed']} | {item['correct']} | {item['wrong']} |"
        )
    lines.extend(["", "## Files", "", f"- json: `{output}`", f"- jsonl: `{jsonl_path}`"])
    return "\n".join(lines) + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run lightweight LiftCertificate coverage on public/TeX corpora.")
    parser.add_argument("--gsm8k", type=int, default=0)
    parser.add_argument("--math-per-config", type=int, default=0)
    parser.add_argument("--svamp", type=int, default=0)
    parser.add_argument("--asdiv", type=int, default=0)
    parser.add_argument("--aqua", type=int, default=0)
    parser.add_argument("--multiarith", type=int, default=0)
    parser.add_argument("--mawps", type=int, default=0)
    parser.add_argument("--tex", nargs="*", type=Path, default=[])
    parser.add_argument("--tex-limit-per-file", type=int, default=None)
    parser.add_argument("--allow-frozen-final-eval", action="store_true")
    parser.add_argument("--max-cases", type=int, default=None)
    parser.add_argument("--case-timeout", type=float, default=None)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    cases = load_public_cases(args)
    if args.tex:
        cases.extend(
            load_tex_cases(
                args.tex,
                limit_per_file=args.tex_limit_per_file,
                allow_frozen_final_eval=args.allow_frozen_final_eval,
            )
        )
    result = run_corpus_lift_protocol(cases, case_timeout=args.case_timeout, max_cases=args.max_cases)
    write_outputs(result, args.output)
    print(json.dumps({"counts": result["counts"], "rates": result["rates"]}, ensure_ascii=False, indent=2))
    print(f"json: {args.output}")
    print(f"jsonl: {args.output.with_suffix('.jsonl')}")
    print(f"report: {args.output.with_name(args.output.stem + '_report.md')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
