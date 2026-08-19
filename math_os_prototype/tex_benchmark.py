"""Benchmark Math OS on TeX problem collections."""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import queue
import re
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

try:
    from math_os_prototype.reasoning_pipeline import run_reasoning_pipeline
except ImportError:
    from reasoning_pipeline import run_reasoning_pipeline


ANSWER_MARKERS = (
    r"\\textbf\{【解答】\}",
    r"\\textbf\{解答\}",
    r"\\noindent\s*\\textbf\{【解答】\}",
    r"\\section\*\{解答\}",
    r"\\subsection\*\{解説・解答\}",
    r"\\subsubsection\*\{【解答】\}",
)


@dataclass
class TexProblem:
    source: str
    title: str
    index: int
    text: str
    line: int


@dataclass
class BenchmarkRecord:
    source: str
    title: str
    index: int
    line: int
    domain: str
    domain_confidence: float
    route: str
    intent: str
    strategy: str
    verification: str
    answer: str | None
    status: str
    warning: str | None
    elapsed_seconds: float
    text_preview: str


def extract_tex_problems(path: Path) -> list[TexProblem]:
    if path.suffix.lower() == ".pdf":
        return extract_numbered_pdf_problems(path)
    text = path.read_text(encoding="utf-8", errors="replace")
    problems = extract_itembox_problems(text, path.name)
    exercise_problems = extract_exercise_problems(text, path.name)
    if exercise_problems:
        problems.extend(exercise_problems)
    return sorted(problems, key=lambda item: (item.line, item.index))


def extract_numbered_pdf_problems(path: Path) -> list[TexProblem]:
    """Extract a contest's numbered problem section without using its answers."""
    try:
        import fitz
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("PyMuPDF is required to benchmark PDF problem sets") from exc
    document = fitz.open(path)
    text = "\n".join(page.get_text() for page in document)
    exam_headings = list(re.finditer(r"(?m)^\s*([１２３４５６７８９])\s*\n\s*[（(]\s*\d+\s*点\s*[）)]", text))
    if exam_headings:
        numeral = {char: index for index, char in enumerate("０１２３４５６７８９")}
        problems: list[TexProblem] = []
        for position, match in enumerate(exam_headings):
            end = exam_headings[position + 1].start() if position + 1 < len(exam_headings) else len(text)
            body = re.sub(r"\s+", " ", text[match.end():end]).strip()
            index = numeral[match.group(1)]
            problems.append(TexProblem(
                source=path.name, title=f"問題{index}", index=index, text=body,
                line=line_number(text, match.start()),
            ))
        return problems
    # Contest appendices often restart numbering after an explicit terminator.
    main = re.split(r"(?m)^\s*以上\s*$", text, maxsplit=1)[0]
    matches = list(re.finditer(r"(?m)^\s*(1[0-9]|[1-9])\.\s+", main))
    problems: list[TexProblem] = []
    for position, match in enumerate(matches):
        end = matches[position + 1].start() if position + 1 < len(matches) else len(main)
        body = re.sub(r"\s+", " ", main[match.end():end]).strip()
        if not is_meaningful_problem(body):
            continue
        index = int(match.group(1))
        problems.append(TexProblem(
            source=path.name,
            title=f"問題{index}",
            index=index,
            text=body,
            line=line_number(main, match.start()),
        ))
    return problems


def extract_itembox_problems(text: str, source: str) -> list[TexProblem]:
    pattern = re.compile(
        r"\\begin\{itembox\}(?:\[[^\]]*\])?\{(?P<title>[^}]*)\}(?P<body>.*?)\\end\{itembox\}",
        re.DOTALL,
    )
    problems: list[TexProblem] = []
    for index, match in enumerate(pattern.finditer(text), start=1):
        title = clean_tex(match.group("title"))
        if "問題" not in title:
            continue
        body = strip_answer_tail(match.group("body"))
        problem_text = prepare_tex_problem_text(body)
        if not is_meaningful_problem(problem_text):
            continue
        problems.append(
            TexProblem(
                source=source,
                title=title,
                index=index,
                text=problem_text,
                line=line_number(text, match.start()),
            )
        )
    return problems


def extract_exercise_problems(text: str, source: str) -> list[TexProblem]:
    heading_pattern = re.compile(r"\\textbf\{\\large\s*【演習問題\s*([^】]+)】\}[^\\n]*(?:\\par)?")
    matches = list(heading_pattern.finditer(text))
    problems: list[TexProblem] = []
    for index, match in enumerate(matches, start=1):
        start = match.end()
        end = matches[index].start() if index < len(matches) else len(text)
        segment = strip_answer_tail(text[start:end])
        problem_text = extract_fbox_payload(segment) or segment
        problem_text = prepare_tex_problem_text(problem_text)
        if not is_meaningful_problem(problem_text):
            continue
        problems.append(
            TexProblem(
                source=source,
                title=f"演習問題{clean_tex(match.group(1))}",
                index=index,
                text=problem_text,
                line=line_number(text, match.start()),
            )
        )
    return problems


def extract_fbox_payload(segment: str) -> str | None:
    minipage = re.search(r"\\begin\{minipage\}(?:\{[^}]*\})?(?P<body>.*?)\\end\{minipage\}", segment, re.DOTALL)
    if minipage:
        return minipage.group("body")
    fbox = re.search(r"\\fbox\s*\{(?P<body>.*?)\}\s*(?:\\vskip|\\vspace|\\noindent|$)", segment, re.DOTALL)
    return fbox.group("body") if fbox else None


def strip_answer_tail(text: str) -> str:
    cut = len(text)
    for marker in ANSWER_MARKERS:
        match = re.search(marker, text)
        if match:
            cut = min(cut, match.start())
    return text[:cut]


def clean_tex(text: str) -> str:
    text = re.sub(r"(?<!\\)%.*", "", text)
    text = re.sub(r"\\(?:vspace|vskip|hspace)\*?\{[^}]*\}", " ", text)
    text = re.sub(r"\\(?:left|right)([()[\]{}|.])", r"\1", text)
    text = replace_compact_frac(text)
    text = replace_simple_frac(text)
    text = replace_simple_command_arg(text, "sqrt", "sqrt")
    text = re.sub(r"\\sqrt\s*([A-Za-z0-9]+)", r"sqrt(\1)", text)
    text = replace_simple_command_arg(text, "cInv", "arccos")
    command_words = {
        "int": " integral ",
        "iint": " double_integral ",
        "lim": " limit ",
        "sum": " sum ",
        "prod": " product ",
        "cos": " cos",
        "sin": " sin",
        "tan": " tan",
        "log": " log",
        "exp": " exp",
        "pi": "pi",
        "theta": "theta",
        "alpha": "alpha",
        "beta": "beta",
        "rho": "rho",
        "infty": "infinity",
        "to": " to ",
        "in": " in ",
        "equiv": " equiv ",
        "pmod": " mod ",
        "mod": " mod ",
        "leq": " <= ",
        "geq": " >= ",
        "leqq": " <= ",
        "geqq": " >= ",
        "neq": " != ",
        "cdot": "*",
        "times": "*",
    }
    for command, word in command_words.items():
        text = re.sub(rf"\\{command}(?![A-Za-z])", word, text)
    replacements = {
        r"\par": "\n",
        r"\\": "\n",
        r"\,": " ",
        r"\quad": " ",
        r"\qquad": " ",
        r"\displaystyle": "",
        r"\noindent": "",
        r"\baselineskip": "",
        r"\slash": "/",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"\\begin\{[^}]+\}(?:\[[^\]]*\])?(?:\{[^}]*\})?", "\n", text)
    text = re.sub(r"\\end\{[^}]+\}", "\n", text)
    text = re.sub(r"\\(?:textbf|large|Huge|bfseries|mathrm|mathbf|mathcal|texorpdfstring)\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?", " ", text)
    text = re.sub(r"[{}]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def prepare_tex_problem_text(text: str) -> str:
    """Remove document layout while preserving TeX mathematical syntax."""
    text = re.sub(r"(?<!\\)%.*", "", text)
    text = re.sub(r"\\(?:vspace|vskip|hspace)\*?\{[^}]*\}", " ", text)
    text = re.sub(r"\\(?:noindent|displaystyle|baselineskip|bfseries|large|Huge)\b", " ", text)
    text = re.sub(r"\\(?:begin|end)\{(?:center|flushleft|flushright|minipage|enumerate|itemize)\}(?:\{[^}]*\})?", "\n", text)
    text = re.sub(r"\\(?:textbf|mathrm|mathbf|mathcal)\{([^{}]*)\}", r"\1", text)
    text = text.replace(r"\par", "\n")
    # Keep \\ inside aligned equations and matrices; the LaTeX frontend owns it.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def replace_simple_frac(text: str) -> str:
    pattern = re.compile(r"\\frac\s*\{([^{}]+)\}\s*\{([^{}]+)\}")
    previous = None
    while previous != text:
        previous = text
        text = pattern.sub(r"(\1)/(\2)", text)
    return text


def replace_compact_frac(text: str) -> str:
    return re.sub(r"\\frac\s*([A-Za-z0-9])\s*([A-Za-z0-9])", r"(\1)/(\2)", text)


def replace_simple_command_arg(text: str, command: str, replacement: str) -> str:
    pattern = re.compile(rf"\\{command}\s*\{{([^{{}}]+)\}}")
    previous = None
    while previous != text:
        previous = text
        text = pattern.sub(rf"{replacement}(\1)", text)
    return text


def is_meaningful_problem(text: str) -> bool:
    if len(text) < 12:
        return False
    skip_words = ("難易度", "目標取り組み時間")
    return not all(word in text for word in skip_words)


def line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def run_tex_benchmark(
    paths: list[Path],
    *,
    limit: int | None = None,
    external_tools: bool = False,
    live_retrieval: bool = False,
    allow_specialized: bool = False,
    case_timeout: float | None = None,
) -> dict[str, Any]:
    problems: list[TexProblem] = []
    for path in paths:
        problems.extend(extract_tex_problems(path))
    if limit is not None:
        problems = problems[:limit]

    records = [
        run_tex_problem_with_timeout(
            problem,
            external_tools=external_tools,
            live_retrieval=live_retrieval,
            allow_specialized=allow_specialized,
            timeout=case_timeout,
        )
        for problem in problems
    ]

    return summarize_records(records, len(problems))


def run_tex_problem(
    problem: TexProblem,
    *,
    external_tools: bool,
    live_retrieval: bool,
    allow_specialized: bool,
) -> BenchmarkRecord:
    start = time.perf_counter()
    try:
        result = run_reasoning_pipeline(
            problem.text,
            external_tools=external_tools,
            live_retrieval=live_retrieval,
            allow_specialized=allow_specialized,
        )
        elapsed = time.perf_counter() - start
        answer = extract_answer_from_pipeline_dict(json.loads(result.to_json()))
        warning = "; ".join(result.verification.get("warnings", [])) or None
        strategy = result.strategies[0]["name"] if result.strategies else "none"
        status = classify_status(
            result.verification["status"], answer, result.domain_ir["domain"],
            result.parser["intent"], strategy, problem.text,
        )
        return BenchmarkRecord(
            source=problem.source, title=problem.title, index=problem.index, line=problem.line,
            domain=result.domain_ir["domain"], domain_confidence=float(result.domain_ir["confidence"]),
            route=result.parser["route"], intent=result.parser["intent"], strategy=strategy,
            verification=result.verification["status"], answer=answer, status=status, warning=warning,
            elapsed_seconds=round(elapsed, 4), text_preview=problem.text[:240],
        )
    except Exception as exc:
        return tex_error_record(problem, str(exc), time.perf_counter() - start)


def tex_error_record(problem: TexProblem, warning: str, elapsed: float, *, verification: str = "failed") -> BenchmarkRecord:
    return BenchmarkRecord(
        source=problem.source, title=problem.title, index=problem.index, line=problem.line,
        domain="error", domain_confidence=0.0, route="error", intent="error", strategy="error",
        verification=verification, answer=None, status="timeout" if verification == "timeout" else "error",
        warning=warning, elapsed_seconds=round(elapsed, 4), text_preview=problem.text[:240],
    )


def run_tex_problem_with_timeout(
    problem: TexProblem,
    *,
    external_tools: bool,
    live_retrieval: bool,
    allow_specialized: bool,
    timeout: float | None,
) -> BenchmarkRecord:
    if timeout is None or timeout <= 0:
        return run_tex_problem(
            problem, external_tools=external_tools, live_retrieval=live_retrieval,
            allow_specialized=allow_specialized,
        )
    started = time.perf_counter()
    result_queue: mp.Queue = mp.Queue(maxsize=1)
    process = mp.Process(
        target=_tex_problem_worker,
        args=(problem, external_tools, live_retrieval, allow_specialized, result_queue),
    )
    process.start()
    process.join(timeout)
    if process.is_alive():
        process.terminate()
        process.join(2)
        return tex_error_record(problem, f"case_timeout_after_{timeout:g}s", time.perf_counter() - started, verification="timeout")
    try:
        return BenchmarkRecord(**result_queue.get_nowait())
    except queue.Empty:
        return tex_error_record(problem, "case_worker_returned_no_record", time.perf_counter() - started)


def _tex_problem_worker(
    problem: TexProblem,
    external_tools: bool,
    live_retrieval: bool,
    allow_specialized: bool,
    result_queue: mp.Queue,
) -> None:
    result_queue.put(asdict(run_tex_problem(
        problem, external_tools=external_tools, live_retrieval=live_retrieval,
        allow_specialized=allow_specialized,
    )))


def extract_answer_from_pipeline_dict(data: dict[str, Any]) -> str | None:
    text = data.get("explanation", "")
    for line in text.splitlines():
        if line.startswith("Answer:"):
            return line.split(":", 1)[1].strip()
    return None


def classify_status(
    verification: str,
    answer: str | None,
    domain: str = "unknown",
    intent: str = "",
    strategy: str = "",
    problem_text: str = "",
) -> str:
    if answer in {None, "", "[]", "{}", "None"}:
        answer = None
    if domain != "algebra" and "cas_symbolic_algebra" in intent:
        return "partial_plan"
    if verification == "verified" and answer:
        return "verified_answer"
    if strategy.endswith("_domain_plan") and domain not in {"algebra", "calculus", "geometry", "convex_geometry"}:
        return "partial_plan"
    if "面積" in problem_text and "geometry_nl_to_dsl_region" in intent:
        return "partial_plan"
    if verification == "verified":
        return "verified_no_answer"
    if verification == "partial":
        return "partial_plan"
    return verification or "unknown"


def summarize_records(records: list[BenchmarkRecord], total: int) -> dict[str, Any]:
    by_status = Counter(record.status for record in records)
    by_domain = Counter(record.domain for record in records)
    by_source = defaultdict(Counter)
    by_domain_status = defaultdict(Counter)
    for record in records:
        by_source[record.source][record.status] += 1
        by_domain_status[record.domain][record.status] += 1
    domain_success_rates = {
        domain: {
            "total": sum(counter.values()),
            "verified_answer": counter.get("verified_answer", 0),
            "verified_answer_rate": counter.get("verified_answer", 0) / sum(counter.values()) if sum(counter.values()) else 0.0,
        }
        for domain, counter in sorted(by_domain_status.items())
    }
    weak_domains = [
        {"domain": domain, "count": count}
        for domain, count in by_domain.most_common()
        if domain not in {"geometry", "convex_geometry", "algebra", "calculus"}
    ][:10]
    return {
        "total": total,
        "by_status": dict(by_status),
        "by_domain": dict(by_domain),
        "by_source": {source: dict(counter) for source, counter in by_source.items()},
        "by_domain_status": {domain: dict(counter) for domain, counter in by_domain_status.items()},
        "domain_success_rates": domain_success_rates,
        "verified_answer_rate": by_status["verified_answer"] / total if total else 0.0,
        "records": [asdict(record) for record in records],
        "weak_domains": weak_domains,
    }


def write_outputs(result: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    jsonl_path = output.with_suffix(".jsonl")
    with jsonl_path.open("w", encoding="utf-8") as handle:
        for record in result["records"]:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark Math OS on TeX problem files.")
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--external-tools", action="store_true")
    parser.add_argument("--live-retrieval", action="store_true")
    parser.add_argument("--case-timeout", type=float, default=None)
    parser.add_argument(
        "--allow-specialized",
        action="store_true",
        help="Enable legacy benchmark-specific adapters. Off by default for cold benchmarks.",
    )
    parser.add_argument("--output", type=Path, default=Path("math_os_prototype/tex_benchmark_results.json"))
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    result = run_tex_benchmark(
        args.paths,
        limit=args.limit,
        external_tools=args.external_tools,
        live_retrieval=args.live_retrieval,
        allow_specialized=args.allow_specialized,
        case_timeout=args.case_timeout,
    )
    write_outputs(result, args.output)
    print(json.dumps({k: v for k, v in result.items() if k != "records"}, ensure_ascii=False, indent=2))
    print(f"records: {args.output}")
    print(f"jsonl: {args.output.with_suffix('.jsonl')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
