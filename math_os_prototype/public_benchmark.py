"""Run MathOS against small public benchmark samples.

The runner deliberately separates three metrics:
1. typed_kernel_ok: the problem compiles into typed definitions.
2. answered: MathOS returned any answer.
3. exact_match: returned answer matches the dataset answer by simple exact/numeric checks.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing as mp
import queue
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

try:
    import sympy as sp
except ImportError:  # pragma: no cover
    sp = None

try:
    from math_os_prototype.reasoning_pipeline import run_reasoning_pipeline
    from math_os_prototype.typed_definition_kernel import compile_typed_definition_ir
    from math_os_prototype.web_app import extract_answer_from_pipeline_data
except ImportError:
    from reasoning_pipeline import run_reasoning_pipeline
    from typed_definition_kernel import compile_typed_definition_ir
    from web_app import extract_answer_from_pipeline_data


MATH_CONFIGS = (
    "algebra",
    "counting_and_probability",
    "geometry",
    "intermediate_algebra",
    "number_theory",
    "prealgebra",
    "precalculus",
)


@dataclass
class PublicBenchmarkCase:
    benchmark: str
    subset: str
    index: int
    problem: str
    expected: str | None
    level: str | None = None


@dataclass
class PublicBenchmarkRecord:
    benchmark: str
    subset: str
    index: int
    domain: str
    intent: str
    typed_status: str
    verification: str
    expected: str | None
    answer: str | None
    exact_match: bool | None
    error: str | None
    problem_preview: str
    case_id: str
    problem_hash: str
    evaluation_partition: str
    level: str | None
    failure_layer: str = "unknown"
    semantic_morphism_count: int = 0
    backend_obligation_count: int = 0
    planned_tool_count: int = 0
    executable_tool_count: int = 0
    executed_tool_count: int = 0


def classify_failure_layer(
    *,
    typed_status: str,
    answer: str | None,
    exact_match: bool | None,
    tool_calls: list[dict[str, Any]],
) -> str:
    """Locate the first observable pipeline layer that blocks a correct answer."""
    if exact_match is True:
        return "solved"
    if typed_status != "type_checked":
        return "elaboration_or_type_gap"
    if not answer:
        if not tool_calls:
            return "strategy_or_morphism_gap"
        if not any(bool(call.get("executable")) for call in tool_calls):
            return "morphism_to_backend_gap"
        if any(call.get("error") for call in tool_calls):
            return "backend_execution_gap"
        return "answer_extraction_or_abstention"
    return "semantic_or_strategy_error"


def problem_hash(case: PublicBenchmarkCase) -> str:
    payload = json.dumps(
        [case.benchmark, case.subset, case.index, case.problem],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def case_identity(case: PublicBenchmarkCase) -> tuple[str, str, str]:
    digest = problem_hash(case)
    bucket = int(digest[:8], 16) % 100
    partition = "dev" if bucket < 20 else "calibration" if bucket < 30 else "held_out"
    return f"{case.benchmark}:{case.subset}:{case.index}", digest, partition


def benchmark_manifest(cases: list[PublicBenchmarkCase]) -> str:
    joined = "\n".join(problem_hash(case) for case in cases)
    return hashlib.sha256(joined.encode("ascii")).hexdigest()


def fetch_hf_rows(dataset: str, config: str, split: str, length: int, offset: int = 0) -> list[dict[str, Any]]:
    if length > 100:
        rows: list[dict[str, Any]] = []
        remaining = length
        cursor = offset
        while remaining > 0:
            batch_length = min(100, remaining)
            batch = fetch_hf_rows(dataset, config, split, batch_length, cursor)
            rows.extend(batch)
            if len(batch) < batch_length:
                break
            cursor += batch_length
            remaining -= batch_length
        return rows
    query = urllib.parse.urlencode(
        {
            "dataset": dataset,
            "config": config,
            "split": split,
            "offset": offset,
            "length": length,
        }
    )
    url = f"https://datasets-server.huggingface.co/rows?{query}"
    cache_dir = Path("math_os_prototype/.hf_rows_cache")
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_key = re.sub(r"[^A-Za-z0-9_.-]+", "_", f"{dataset}_{config}_{split}_{offset}_{length}")
    cache_path = cache_dir / f"{cache_key}.json"
    if cache_path.exists():
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    else:
        last_error: Exception | None = None
        for attempt in range(5):
            try:
                with urllib.request.urlopen(url, timeout=60) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                cache_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
                break
            except urllib.error.HTTPError as error:
                last_error = error
                if error.code not in {429, 500, 502, 503, 504}:
                    raise
                time.sleep(2**attempt)
        else:
            assert last_error is not None
            raise last_error
    return [item["row"] for item in payload.get("rows", [])]


def load_gsm8k_cases(limit: int) -> list[PublicBenchmarkCase]:
    rows = fetch_hf_rows("openai/gsm8k", "main", "test", limit)
    cases = []
    for index, row in enumerate(rows):
        cases.append(
            PublicBenchmarkCase(
                benchmark="GSM8K",
                subset="test",
                index=index,
                problem=row["question"],
                expected=extract_gsm8k_answer(row["answer"]),
            )
        )
    return cases


def load_math_cases(per_config: int) -> list[PublicBenchmarkCase]:
    cases: list[PublicBenchmarkCase] = []
    for config in MATH_CONFIGS:
        rows = fetch_hf_rows("EleutherAI/hendrycks_math", config, "test", per_config)
        for index, row in enumerate(rows):
            cases.append(
                PublicBenchmarkCase(
                    benchmark="MATH",
                    subset=config,
                    index=index,
                    problem=row["problem"],
                    expected=extract_boxed_answer(row.get("solution", "")),
                    level=str(row.get("level")) if row.get("level") is not None else None,
                )
            )
    return cases


def load_svamp_cases(limit: int) -> list[PublicBenchmarkCase]:
    rows = fetch_hf_rows("ChilleD/SVAMP", "default", "test", limit)
    cases = []
    for index, row in enumerate(rows):
        cases.append(
            PublicBenchmarkCase(
                benchmark="SVAMP",
                subset=str(row.get("Type") or "test"),
                index=index,
                problem=row.get("question_concat") or f"{row.get('Body', '')} {row.get('Question', '')}".strip(),
                expected=normalize_answer(row.get("Answer")),
            )
        )
    return cases


def load_asdiv_cases(limit: int) -> list[PublicBenchmarkCase]:
    rows = fetch_hf_rows("yimingzhang/asdiv", "default", "test", limit)
    cases = []
    for index, row in enumerate(rows):
        cases.append(
            PublicBenchmarkCase(
                benchmark="ASDiv",
                subset="test",
                index=index,
                problem=normalize_asdiv_prompt(row["text"]),
                expected=normalize_answer(row.get("label")),
            )
        )
    return cases


def load_aqua_cases(limit: int) -> list[PublicBenchmarkCase]:
    rows = fetch_hf_rows("hails/agieval-aqua-rat", "default", "test", limit)
    cases = []
    for index, row in enumerate(rows):
        gold = row.get("gold") or []
        choices = row.get("choices") or []
        expected = None
        if gold and choices:
            expected = normalize_aqua_choice(choices[int(gold[0])])
        cases.append(
            PublicBenchmarkCase(
                benchmark="AQuA-RAT",
                subset="test",
                index=index,
                problem=row["query"],
                expected=expected,
            )
        )
    return cases


def load_multiarith_cases(limit: int) -> list[PublicBenchmarkCase]:
    rows = fetch_hf_rows("ChilleD/MultiArith", "default", "test", limit)
    cases = []
    for index, row in enumerate(rows):
        cases.append(
            PublicBenchmarkCase(
                benchmark="MultiArith",
                subset="test",
                index=index,
                problem=row["question"].strip(),
                expected=normalize_answer(row.get("final_ans")),
            )
        )
    return cases


def load_mawps_cases(limit: int) -> list[PublicBenchmarkCase]:
    rows = fetch_hf_rows("MU-NLPC/Calc-mawps", "default", "test", limit)
    cases = []
    for index, row in enumerate(rows):
        cases.append(
            PublicBenchmarkCase(
                benchmark="MAWPS",
                subset="test",
                index=index,
                problem=row["question"],
                expected=normalize_answer(row.get("result")),
            )
        )
    return cases


def run_public_benchmark(
    *,
    gsm8k: int = 0,
    math_per_config: int = 0,
    svamp: int = 0,
    asdiv: int = 0,
    aqua: int = 0,
    multiarith: int = 0,
    mawps: int = 0,
    live_retrieval: bool = False,
    external_tools: bool = False,
    allow_surface_morphisms: bool = False,
    case_timeout: float | None = None,
    workers: int = 1,
    evaluation_partition: str | None = None,
) -> dict[str, Any]:
    cases: list[PublicBenchmarkCase] = []
    if gsm8k:
        cases.extend(load_gsm8k_cases(gsm8k))
    if math_per_config:
        cases.extend(load_math_cases(math_per_config))
    if svamp:
        cases.extend(load_svamp_cases(svamp))
    if asdiv:
        cases.extend(load_asdiv_cases(asdiv))
    if aqua:
        cases.extend(load_aqua_cases(aqua))
    if multiarith:
        cases.extend(load_multiarith_cases(multiarith))
    if mawps:
        cases.extend(load_mawps_cases(mawps))

    source_manifest = benchmark_manifest(cases)
    if evaluation_partition is not None:
        if evaluation_partition not in {"dev", "calibration", "held_out"}:
            raise ValueError(f"unknown evaluation partition: {evaluation_partition}")
        cases = [case for case in cases if case_identity(case)[2] == evaluation_partition]

    started = time.perf_counter()
    worker_count = max(1, int(workers))
    if case_timeout and case_timeout > 0:
        if worker_count > 1:
            records = run_cases_with_persistent_workers(
                cases,
                live_retrieval=live_retrieval,
                external_tools=external_tools,
                allow_surface_morphisms=allow_surface_morphisms,
                timeout=case_timeout,
                workers=worker_count,
            )
        else:
            records = [
                run_case_with_timeout(
                    case,
                    live_retrieval=live_retrieval,
                    external_tools=external_tools,
                    allow_surface_morphisms=allow_surface_morphisms,
                    timeout=case_timeout,
                )
                for case in cases
            ]
    else:
        # In-process solver state is not assumed to be thread-safe.
        records = [
            run_case(
                case,
                live_retrieval=live_retrieval,
                external_tools=external_tools,
                allow_surface_morphisms=allow_surface_morphisms,
            )
            for case in cases
        ]
    result = summarize(records)
    result["protocol"] = {
        "schema": 2,
        "manifest_sha256": source_manifest,
        "evaluated_manifest_sha256": benchmark_manifest(cases),
        "evaluation_partition": evaluation_partition or "all",
        "partition_rule": "sha256(case) mod 100: dev=0..19, calibration=20..29, held_out=30..99",
        "case_timeout_seconds": case_timeout,
        "workers": worker_count,
        "live_retrieval": live_retrieval,
        "external_tools": external_tools,
        "allow_surface_morphisms": allow_surface_morphisms,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }
    return result


def run_case(
    case: PublicBenchmarkCase,
    *,
    live_retrieval: bool = False,
    external_tools: bool = False,
    allow_surface_morphisms: bool = False,
) -> PublicBenchmarkRecord:
    case_id, digest, partition = case_identity(case)
    try:
        typed_ir = compile_typed_definition_ir(case.problem)
        result = run_reasoning_pipeline(
            case.problem,
            external_tools=external_tools,
            live_retrieval=live_retrieval,
            allow_specialized=allow_surface_morphisms,
        )
        data = json.loads(result.to_json())
        answer = extract_answer_from_pipeline_data(data)
        match = answers_match(answer, case.expected) if case.expected is not None else None
        tool_calls = list((data.get("tool_execution") or {}).get("tool_calls") or [])
        semantic_morphisms = list((data.get("semantic_graph") or {}).get("morphisms") or [])
        backend_obligations = list(
            (data.get("typed_definition_ir") or {}).get("backend_obligations") or []
        )
        return PublicBenchmarkRecord(
            benchmark=case.benchmark,
            subset=case.subset,
            index=case.index,
            domain=data["domain_ir"]["domain"],
            intent=data["parser"]["intent"],
            typed_status=typed_ir.status,
            verification=data["verification"]["status"],
            expected=case.expected,
            answer=answer,
            exact_match=match,
            error=None,
            problem_preview=case.problem[:220],
            case_id=case_id,
            problem_hash=digest,
            evaluation_partition=partition,
            level=case.level,
            failure_layer=classify_failure_layer(
                typed_status=typed_ir.status,
                answer=answer,
                exact_match=match,
                tool_calls=tool_calls,
            ),
            semantic_morphism_count=len(semantic_morphisms),
            backend_obligation_count=len(backend_obligations),
            planned_tool_count=len(tool_calls),
            executable_tool_count=sum(
                bool(call.get("executable")) for call in tool_calls
            ),
            executed_tool_count=sum(
                call.get("result") is not None and not call.get("error")
                for call in tool_calls
            ),
        )
    except Exception as exc:
        return error_record(case, str(exc))


def run_case_with_timeout(
    case: PublicBenchmarkCase,
    *,
    live_retrieval: bool = False,
    external_tools: bool = False,
    allow_surface_morphisms: bool = False,
    timeout: float,
) -> PublicBenchmarkRecord:
    result_queue: mp.Queue = mp.Queue(maxsize=1)
    process = mp.Process(
        target=_case_worker,
        args=(case, live_retrieval, external_tools, allow_surface_morphisms, result_queue),
    )
    process.start()
    process.join(timeout)
    if process.is_alive():
        process.terminate()
        process.join(2)
        return error_record(case, f"case_timeout_after_{timeout:g}s", verification="timeout")
    try:
        payload = result_queue.get_nowait()
    except queue.Empty:
        return error_record(case, "case_worker_returned_no_record")
    return PublicBenchmarkRecord(**payload)


def _case_worker(
    case: PublicBenchmarkCase,
    live_retrieval: bool,
    external_tools: bool,
    allow_surface_morphisms: bool,
    result_queue: mp.Queue,
) -> None:
    record = run_case(
        case,
        live_retrieval=live_retrieval,
        external_tools=external_tools,
        allow_surface_morphisms=allow_surface_morphisms,
    )
    result_queue.put(asdict(record))


def _persistent_case_worker(
    slot: int,
    input_queue: mp.Queue,
    output_queue: mp.Queue,
    live_retrieval: bool,
    external_tools: bool,
    allow_surface_morphisms: bool,
) -> None:
    output_queue.put(("ready", slot, None, None))
    while True:
        payload = input_queue.get()
        if payload is None:
            return
        position, case = payload
        record = run_case(
            case,
            live_retrieval=live_retrieval,
            external_tools=external_tools,
            allow_surface_morphisms=allow_surface_morphisms,
        )
        output_queue.put(("result", slot, position, asdict(record)))


def run_cases_with_persistent_workers(
    cases: list[PublicBenchmarkCase],
    *,
    live_retrieval: bool,
    external_tools: bool,
    allow_surface_morphisms: bool,
    timeout: float,
    workers: int,
) -> list[PublicBenchmarkRecord]:
    """Run isolated reusable workers and replace only a worker that times out."""
    if not cases:
        return []
    context = mp.get_context("spawn")
    output_queue = context.Queue()
    slots: dict[int, dict[str, Any]] = {}
    results: list[PublicBenchmarkRecord | None] = [None] * len(cases)
    next_position = 0
    completed = 0

    def start_worker(slot: int) -> None:
        input_queue = context.Queue(maxsize=1)
        process = context.Process(
            target=_persistent_case_worker,
            args=(
                slot,
                input_queue,
                output_queue,
                live_retrieval,
                external_tools,
                allow_surface_morphisms,
            ),
        )
        process.start()
        slots[slot] = {
            "process": process,
            "queue": input_queue,
            "ready": False,
            "position": None,
            "started": None,
        }

    def stop_worker(slot: int, *, force: bool = False) -> None:
        state = slots[slot]
        process: mp.Process = state["process"]
        if process.is_alive() and not force:
            state["queue"].put(None)
            process.join(2)
        if process.is_alive():
            process.terminate()
            process.join(2)
        state["queue"].close()

    def assign(slot: int) -> None:
        nonlocal next_position
        state = slots[slot]
        if not state["ready"] or state["position"] is not None or next_position >= len(cases):
            return
        position = next_position
        next_position += 1
        state["position"] = position
        state["started"] = time.monotonic()
        state["queue"].put((position, cases[position]))

    for slot in range(min(workers, len(cases))):
        start_worker(slot)

    try:
        while completed < len(cases):
            try:
                kind, slot, position, payload = output_queue.get(timeout=0.05)
            except queue.Empty:
                kind = None
            if kind == "ready":
                slots[slot]["ready"] = True
                assign(slot)
            elif kind == "result" and position is not None:
                if results[position] is None:
                    results[position] = PublicBenchmarkRecord(**payload)
                    completed += 1
                slots[slot]["position"] = None
                slots[slot]["started"] = None
                assign(slot)

            now = time.monotonic()
            for slot, state in list(slots.items()):
                position = state["position"]
                started = state["started"]
                process: mp.Process = state["process"]
                timed_out = position is not None and started is not None and now - started > timeout
                died = state["ready"] and not process.is_alive() and position is not None
                if not timed_out and not died:
                    continue
                if results[position] is None:
                    reason = f"case_timeout_after_{timeout:g}s" if timed_out else "case_worker_exited"
                    verification = "timeout" if timed_out else "error"
                    results[position] = error_record(cases[position], reason, verification=verification)
                    completed += 1
                stop_worker(slot, force=True)
                if next_position < len(cases):
                    start_worker(slot)
    finally:
        for slot in list(slots):
            stop_worker(slot)
        output_queue.close()

    return [record for record in results if record is not None]


def error_record(case: PublicBenchmarkCase, error: str, *, verification: str = "error") -> PublicBenchmarkRecord:
    case_id, digest, partition = case_identity(case)
    return PublicBenchmarkRecord(
        benchmark=case.benchmark,
        subset=case.subset,
        index=case.index,
        domain="error",
        intent="error",
        typed_status="error",
        verification=verification,
        expected=case.expected,
        answer=None,
        exact_match=False if case.expected is not None else None,
        error=error,
        problem_preview=case.problem[:220],
        case_id=case_id,
        problem_hash=digest,
        evaluation_partition=partition,
        level=case.level,
    )


def summarize(records: list[PublicBenchmarkRecord]) -> dict[str, Any]:
    total = len(records)
    typed_ok = sum(record.typed_status == "type_checked" for record in records)
    answered = sum(bool(record.answer) for record in records)
    comparable = [record for record in records if record.expected is not None]
    exact = sum(record.exact_match is True for record in comparable)
    answered_comparable = [record for record in comparable if bool(record.answer)]
    wrong = sum(record.exact_match is False for record in answered_comparable)
    abstained = sum(not bool(record.answer) for record in comparable)
    timeouts = sum(record.verification == "timeout" for record in records)
    by_benchmark: dict[str, dict[str, int]] = {}
    for record in records:
        bucket = by_benchmark.setdefault(record.benchmark, {
            "total": 0, "typed_ok": 0, "answered": 0, "exact": 0,
            "wrong": 0, "abstained": 0, "timeouts": 0,
        })
        bucket["total"] += 1
        bucket["typed_ok"] += int(record.typed_status == "type_checked")
        bucket["answered"] += int(bool(record.answer))
        bucket["exact"] += int(record.exact_match is True)
        bucket["wrong"] += int(bool(record.answer) and record.exact_match is False)
        bucket["abstained"] += int(not bool(record.answer))
        bucket["timeouts"] += int(record.verification == "timeout")
    failure_intents: dict[str, int] = {}
    failure_layers: Counter[str] = Counter()
    for record in records:
        if record.exact_match is True:
            continue
        key = f"{record.typed_status}|{record.intent}|{record.verification}"
        failure_intents[key] = failure_intents.get(key, 0) + 1
        failure_layers[record.failure_layer] += 1
    by_partition: dict[str, dict[str, int]] = {}
    for record in records:
        bucket = by_partition.setdefault(record.evaluation_partition, {"total": 0, "answered": 0, "exact": 0, "wrong": 0})
        bucket["total"] += 1
        bucket["answered"] += int(bool(record.answer))
        bucket["exact"] += int(record.exact_match is True)
        bucket["wrong"] += int(bool(record.answer) and record.exact_match is False)
    return {
        "total": total,
        "typed_kernel_ok": typed_ok,
        "typed_kernel_ok_rate": typed_ok / total if total else 0.0,
        "answered": answered,
        "answered_rate": answered / total if total else 0.0,
        "comparable": len(comparable),
        "exact_match": exact,
        "exact_match_rate": exact / len(comparable) if comparable else 0.0,
        "answer_precision": exact / len(answered_comparable) if answered_comparable else 0.0,
        "wrong": wrong,
        "abstained": abstained,
        "timeouts": timeouts,
        "failure_layers": dict(failure_layers.most_common()),
        "coverage": {
            "semantic_morphisms_total": sum(
                record.semantic_morphism_count for record in records
            ),
            "backend_obligations_total": sum(
                record.backend_obligation_count for record in records
            ),
            "planned_tool_calls": sum(record.planned_tool_count for record in records),
            "executable_tool_calls": sum(
                record.executable_tool_count for record in records
            ),
            "executed_tool_calls": sum(record.executed_tool_count for record in records),
        },
        "by_benchmark": by_benchmark,
        "by_partition": by_partition,
        "top_failure_stages": dict(sorted(failure_intents.items(), key=lambda item: (-item[1], item[0]))[:30]),
        "records": [asdict(record) for record in records],
    }


def extract_gsm8k_answer(answer: str) -> str | None:
    match = re.search(r"####\s*([^\n]+)", answer)
    return normalize_answer(match.group(1)) if match else None


def extract_boxed_answer(solution: str) -> str | None:
    marker = r"\boxed{"
    answers: list[str] = []
    cursor = 0
    while True:
        start = solution.find(marker, cursor)
        if start < 0:
            break
        index = start + len(marker)
        depth = 1
        while index < len(solution) and depth:
            if solution[index] == "{" and (index == 0 or solution[index - 1] != "\\"):
                depth += 1
            elif solution[index] == "}" and (index == 0 or solution[index - 1] != "\\"):
                depth -= 1
            index += 1
        if depth == 0:
            answers.append(solution[start + len(marker):index - 1])
        cursor = max(index, start + len(marker))
    return normalize_answer(answers[-1]) if answers else None


def normalize_asdiv_prompt(text: str) -> str:
    text = re.sub(r"^\s*Question:\s*", "", text.strip())
    text = re.sub(r"\s*Answer:\s*$", "", text.strip())
    return text.strip()


def normalize_aqua_choice(choice: str) -> str:
    choice = re.sub(r"^\([A-E]\)\s*", "", choice.strip())
    return normalize_answer(choice) or choice.strip()


def answers_match(answer: str | None, expected: str | None) -> bool:
    if not answer or expected is None:
        return False
    answer_norm = normalize_answer(answer)
    expected_norm = normalize_answer(expected)
    if answer_norm == expected_norm:
        return True
    answer_vector = parse_vector_answer(answer_norm)
    expected_vector = parse_vector_answer(expected_norm)
    if answer_vector is not None and expected_vector is not None:
        return answer_vector == expected_vector
    answer_tuple = parse_coordinate_tuple(answer_norm)
    expected_tuple = parse_coordinate_tuple(expected_norm)
    if answer_tuple is not None and expected_tuple is not None:
        return answer_tuple == expected_tuple
    answer_equation = parse_equation_answer(answer_norm)
    expected_equation = parse_equation_answer(expected_norm)
    if answer_equation is not None and expected_equation is not None:
        if canonical_polynomial_constraint(answer_equation) == canonical_polynomial_constraint(expected_equation):
            return True
    answer_labels = parse_label_set(answer_norm)
    expected_labels = parse_label_set(expected_norm)
    if answer_labels is not None and expected_labels is not None:
        return answer_labels == expected_labels
    answer_scalar_set = parse_scalar_set_answer(answer_norm)
    expected_scalar_set = parse_scalar_set_answer(expected_norm)
    if answer_scalar_set is not None and expected_scalar_set is not None:
        return answer_scalar_set == expected_scalar_set
    if sp is None:
        return False
    answer_set = parse_interval_set(answer)
    expected_set = parse_interval_set(expected)
    if answer_set is not None and expected_set is not None:
        return answer_set == expected_set
    try:
        a = sp.sympify(clean_for_sympy(answer_norm))
        b = sp.sympify(clean_for_sympy(expected_norm))
        return bool(sp.simplify(a - b) == 0)
    except Exception:
        return False


def normalize_answer(value: str | None) -> str | None:
    if value is None:
        return None
    raw = str(value).strip()
    value = raw
    value = value.strip("$ ")
    value = re.sub(r"\\[!,;:]", "", value)
    value = re.sub(r"(?<=\d),(?=\d{3}(?:\D|$))", "", value)
    value = value.replace("\\%", "%")
    value = value.replace("Бу", "sqrt")
    value = re.sub(r"^\\boxed\{(.+)\}$", r"\1", value)
    value = re.sub(r"^\([A-E]\)\s*", "", value)
    return value.strip()


def parse_vector_answer(value: str | None) -> tuple[Any, ...] | None:
    if value is None or sp is None:
        return None
    source = str(value).strip()
    matrix_match = re.fullmatch(r"Matrix\(\[([^\]]+)\]\)", source)
    if matrix_match:
        entries = matrix_match.group(1).split(",")
    else:
        latex_match = re.fullmatch(
            r"\\begin\{(?:p|b)?matrix\}(.*?)\\end\{(?:p|b)?matrix\}",
            source,
            flags=re.DOTALL,
        )
        if not latex_match:
            return None
        entries = re.split(r"\\\\", latex_match.group(1))
    try:
        return tuple(sp.simplify(sp.sympify(clean_for_sympy(item.strip()))) for item in entries if item.strip())
    except Exception:
        return None


def parse_coordinate_tuple(value: str | None) -> tuple[Any, ...] | None:
    if value is None or sp is None:
        return None
    source = str(value).strip().replace(r"\left", "").replace(r"\right", "")
    if not (source.startswith("(") and source.endswith(")")):
        return None
    entries = [item.strip() for item in source[1:-1].split(",")]
    if len(entries) < 2 or any(not item for item in entries):
        return None
    try:
        return tuple(sp.simplify(sp.sympify(clean_for_sympy(item))) for item in entries)
    except Exception:
        return None


def parse_equation_answer(value: str | None) -> Any | None:
    if value is None or sp is None:
        return None
    source = str(value).strip().replace(r"\left", "").replace(r"\right", "")
    if source.count("=") != 1:
        return None
    left, right = source.split("=", 1)
    try:
        return sp.expand(sp.sympify(clean_for_sympy(left)) - sp.sympify(clean_for_sympy(right)))
    except Exception:
        return None


def canonical_polynomial_constraint(expression: Any) -> Any:
    symbols = sorted(expression.free_symbols, key=lambda item: item.name)
    try:
        return sp.Poly(expression, *symbols).monic().as_expr()
    except Exception:
        return sp.simplify(expression)


def parse_label_set(value: str | None) -> frozenset[str] | None:
    if value is None:
        return None
    source = re.sub(r"^\\text\{(.*)\}$", r"\1", str(value).strip())
    if not re.fullmatch(r"[A-Z](?:\s*,\s*[A-Z])+", source):
        return None
    return frozenset(re.findall(r"[A-Z]", source))


def parse_scalar_set_answer(value: str | None) -> frozenset[Any] | None:
    if value is None or sp is None:
        return None
    source = str(value).strip()
    if source.startswith("[") and source.endswith("]"):
        source = source[1:-1]
    elif "," not in source:
        return None
    entries = [item.strip().strip("'\"") for item in source.split(",")]
    if len(entries) < 2 or any(not item for item in entries):
        return None
    try:
        return frozenset(sp.simplify(sp.sympify(clean_for_sympy(item))) for item in entries)
    except Exception:
        return None


def parse_interval_set(value: str | None) -> Any | None:
    if value is None or sp is None:
        return None
    source = str(value).strip().strip("$ ")
    source = source.replace(r"\left", "").replace(r"\right", "")
    source = re.sub(r"^[A-Za-z]\s*(?:\\in|in|∈)\s*", "", source)
    source = source.replace("\\infty", "oo").replace("∞", "oo")
    source = re.sub(r"\\sqrt\{([^{}]+)\}", r"sqrt(\1)", source)
    source = re.sub(r"\\(?:dfrac|tfrac|frac)\s*\{([^{}]+)\}\s*\{([^{}]+)\}", r"(\1)/(\2)", source)
    source = re.sub(r"\\(?:dfrac|tfrac|frac)\s*([+-]?\d+)\s*([+-]?\d+)", r"(\1)/(\2)", source)
    source = source.replace("\\cup", " U ").replace("∪", " U ")
    if source.startswith(("Interval", "Union", "FiniteSet")):
        try:
            return sp.sympify(source, locals={"Interval": sp.Interval, "Union": sp.Union, "FiniteSet": sp.FiniteSet, "oo": sp.oo})
        except Exception:
            return None
    parts = [part.strip() for part in re.split(r"\s+U\s+", source)]
    intervals: list[Any] = []
    for part in parts:
        if len(part) < 3 or part[0] not in "([" or part[-1] not in ")]":
            return None
        split_at = top_level_comma(part[1:-1])
        if split_at is None:
            return None
        left_bracket, right_bracket = part[0], part[-1]
        lower_text = part[1:-1][:split_at].strip()
        upper_text = part[1:-1][split_at + 1 :].strip()
        lower_text = lower_text.replace("-oo", "-oo")
        try:
            lower = sp.sympify(lower_text, locals={"oo": sp.oo})
            upper = sp.sympify(upper_text, locals={"oo": sp.oo})
        except Exception:
            return None
        try:
            intervals.append(
                sp.Interval(lower, upper, left_open=left_bracket == "(", right_open=right_bracket == ")")
            )
        except Exception:
            return None
    return sp.Union(*intervals) if intervals else None


def top_level_comma(source: str) -> int | None:
    depth = 0
    for index, char in enumerate(source):
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        elif char == "," and depth == 0:
            return index
    return None


def clean_for_sympy(value: str) -> str:
    value = value.replace("–", "-").replace("−", "-")
    value = value.replace("^", "**")
    value = value.replace("\\dfrac", "\\frac")
    value = value.replace("\\frac", "frac")
    value = re.sub(r"frac\{([^{}]+)\}\{([^{}]+)\}", r"(\1)/(\2)", value)
    value = re.sub(r"frac(-?\d+)(-?\d+)", r"(\1)/(\2)", value)
    value = value.replace("\\sqrt", "sqrt")
    value = re.sub(r"sqrt\{([^{}]+)\}", r"sqrt(\1)", value)
    value = re.sub(r"(?<=\d)\s*(?=sqrt\()", "*", value)
    value = value.replace("√", "sqrt")
    value = value.replace("Бу", "sqrt")
    value = re.sub(r"sqrt\s*([0-9]+)", r"sqrt(\1)", value)
    value = value.replace("\\pi", "pi")
    value = re.sub(r"(?<=\d)\s*(?=pi\b)", "*", value)
    value = re.sub(r"\bi\b", "I", value)
    value = re.sub(r"(?<=\d)(?=\()", "*", value)
    value = re.sub(r"(?<=\d)(?=[abcxyz])", "*", value)
    value = re.sub(r"(?<=[abcxyz])(?=[abcxyz])", "*", value)
    value = re.sub(r"(?<=\d)(?=sqrt)", "*", value)
    return value


def write_outputs(result: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    with output.with_suffix(".jsonl").open("w", encoding="utf-8") as handle:
        for record in result["records"]:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run MathOS on public benchmark samples.")
    parser.add_argument("--gsm8k", type=int, default=0)
    parser.add_argument("--math-per-config", type=int, default=0)
    parser.add_argument("--svamp", type=int, default=0)
    parser.add_argument("--asdiv", type=int, default=0)
    parser.add_argument("--aqua", type=int, default=0)
    parser.add_argument("--multiarith", type=int, default=0)
    parser.add_argument("--mawps", type=int, default=0)
    parser.add_argument("--live-retrieval", action="store_true")
    parser.add_argument("--external-tools", action="store_true")
    parser.add_argument(
        "--allow-surface-morphisms",
        action="store_true",
        help="Enable direct surface-morphism adapters as an ablation, not as the cold MathOS path.",
    )
    parser.add_argument("--case-timeout", type=float, default=None, help="Optional per-problem timeout in seconds.")
    parser.add_argument("--workers", type=int, default=1, help="Concurrent killable case controllers (requires --case-timeout).")
    parser.add_argument("--evaluation-partition", choices=("dev", "calibration", "held_out"), default=None)
    parser.add_argument("--output", type=Path, default=Path("math_os_prototype/public_benchmark_results.json"))
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    result = run_public_benchmark(
        gsm8k=args.gsm8k,
        math_per_config=args.math_per_config,
        svamp=args.svamp,
        asdiv=args.asdiv,
        aqua=args.aqua,
        multiarith=args.multiarith,
        mawps=args.mawps,
        live_retrieval=args.live_retrieval,
        external_tools=args.external_tools,
        allow_surface_morphisms=args.allow_surface_morphisms,
        case_timeout=args.case_timeout,
        workers=args.workers,
        evaluation_partition=args.evaluation_partition,
    )
    write_outputs(result, args.output)
    print(json.dumps({key: value for key, value in result.items() if key != "records"}, ensure_ascii=False, indent=2))
    print(f"records: {args.output}")
    print(f"jsonl: {args.output.with_suffix('.jsonl')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
