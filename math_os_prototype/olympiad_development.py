"""Structure-first development protocol for the MathNet olympiad corpus.

The protocol deliberately keeps corpus answers and worked solutions outside
the solver input.  They are evaluation and post-failure audit data, not
surface rules.  Splits are assigned from a number-free structural signature so
that parameter variants do not leak across development and evaluation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

try:
    from math_os_prototype.category_semantics import compile_typed_semantic_graph
    from math_os_prototype.lift_backend import solve_from_lift_certificates
    from math_os_prototype.public_benchmark import answers_match, fetch_hf_rows
    from math_os_prototype.typed_definition_kernel import compile_typed_definition_ir
    from math_os_prototype.worker_kernel_adapter import evaluate_with_worker
except ImportError:  # Allows direct script execution.
    from category_semantics import compile_typed_semantic_graph
    from lift_backend import solve_from_lift_certificates
    from public_benchmark import answers_match, fetch_hf_rows
    from typed_definition_kernel import compile_typed_definition_ir
    from worker_kernel_adapter import evaluate_with_worker


DATASET = "weylmann/MathNet"
CONFIG = "all"
SPLIT = "train"
DEFAULT_OUTPUT = Path("artifacts/olympiad/mathnet_development.json")

# This vocabulary is only a structural observation alphabet.  It does not map
# a phrase to an answer or select a problem-specific solution procedure.
STRUCTURAL_FEATURES: dict[str, tuple[str, ...]] = {
    "affine": ("affine", "collinear", "midpoint", "centroid"),
    "angle": ("angle", "perpendicular", "parallel", "cyclic"),
    "arithmetic_function": ("gcd", "lcm", "divisor", "totient"),
    "combinatorial": ("color", "graph", "subset", "permutation", "partition"),
    "congruence": ("congruent", "modulo", "remainder", "residue"),
    "convexity": ("convex", "concave", "jensen"),
    "extremum": ("maximum", "minimum", "largest", "smallest"),
    "function": ("function", "functional equation", "injective", "surjective"),
    "incidence": ("intersect", "tangent", "circle", "triangle", "polygon"),
    "inequality": ("inequality", "at least", "at most", "positive"),
    "integral": ("integral", "differentiate", "derivative"),
    "iteration": ("sequence", "recurrence", "iterate", "periodic"),
    "polynomial": ("polynomial", "root", "coefficient"),
    "prime": ("prime", "composite", "coprime"),
    "probability": ("probability", "random", "expected"),
    "projection": ("projection", "distance", "orthogonal"),
    "quantifier": ("for all", "every", "there exists", "prove that", "find all"),
    "set": ("set", "union", "intersection", "element"),
    "valuation": ("valuation", "power of", "divisible"),
}

LATEX_OPERATORS = re.compile(
    r"\\(?:sum|prod|int|lim|gcd|lcm|binom|floor|ceil|sqrt|log|sin|cos|tan|det|mod)\b"
)
IMAGE_MARKER = re.compile(r"!\[[^\]]*\]\([^)]*\)")
NUMBER = re.compile(r"(?<![A-Za-z])[-+]?\d+(?:[.,]\d+)?")
SPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class OlympiadCase:
    corpus_id: str
    problem: str
    expected: str | None
    country: str
    competition: str
    topics: tuple[str, ...]
    language: str | None
    problem_type: str
    structure_cluster_id: str
    partition: str


@dataclass
class OlympiadRecord:
    corpus_id_hash: str
    country: str
    competition: str
    topics: list[str]
    language: str | None
    problem_type: str
    structure_cluster_id: str
    partition: str
    graph_status: str
    typed_status: str
    sort_names: list[str]
    morphism_names: list[str]
    constraint_count: int
    query_signatures: list[str]
    lift_families: list[str]
    backend_theories: list[str]
    backend_executed: bool
    answer: str | None
    exact_match: bool | None
    failure_layer: str
    elapsed_seconds: float
    error: str | None
    problem_preview: str


@dataclass
class WorkerOlympiadRecord:
    corpus_id_hash: str
    country: str
    competition: str
    topics: list[str]
    language: str | None
    problem_type: str
    structure_cluster_id: str
    partition: str
    atlas: str
    atlas_size: int
    status: str
    root_sorts: list[str]
    query_sorts: list[str]
    morphism_names: list[str]
    parse_count: int
    constraint_count: int
    states_explored: int
    exhausted: bool
    goal_count: int
    first_goal_morphisms: list[str]
    lowering_status: str
    execution_status: str | None
    answer: str | None
    exact_match: bool | None
    elapsed_seconds: float
    error: str | None
    problem_preview: str


def canonical_problem(text: str) -> str:
    text = IMAGE_MARKER.sub(" ", text)
    text = text.replace("\u2212", "-").replace("\u00a0", " ")
    return SPACE.sub(" ", text).strip()


def structural_signature(
    problem: str,
    *,
    topics: Iterable[str] = (),
    problem_type: str = "",
) -> str:
    """Return a number-free, answer-free signature used only for splitting."""
    normalized = canonical_problem(problem).lower()
    number_free = NUMBER.sub("<n>", normalized)
    features = sorted(
        name
        for name, surfaces in STRUCTURAL_FEATURES.items()
        if any(surface in number_free for surface in surfaces)
    )
    operators = sorted(set(LATEX_OPERATORS.findall(number_free)))
    topic_roots = sorted({topic.split(">", 1)[0].strip().lower() for topic in topics if topic.strip()})
    payload = {
        "features": features,
        "operators": operators,
        "problem_type": problem_type.strip().lower(),
        "topic_roots": topic_roots,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("ascii")
    ).hexdigest()[:20]


def partition_for_cluster(cluster_id: str) -> str:
    bucket = int(cluster_id[:8], 16) % 100
    if bucket < 80:
        return "development"
    if bucket < 90:
        return "calibration"
    return "research_holdout"


def row_to_case(row: dict[str, Any]) -> OlympiadCase:
    problem = canonical_problem(str(row.get("problem_markdown") or ""))
    topics = tuple(str(item) for item in row.get("topics_flat") or [])
    problem_type = str(row.get("problem_type") or "")
    cluster_id = structural_signature(problem, topics=topics, problem_type=problem_type)
    return OlympiadCase(
        corpus_id=str(row.get("id") or ""),
        problem=problem,
        expected=str(row["final_answer"]) if row.get("final_answer") not in {None, ""} else None,
        country=str(row.get("country") or "unknown"),
        competition=str(row.get("competition") or "unknown"),
        topics=topics,
        language=str(row["language"]) if row.get("language") else None,
        problem_type=problem_type,
        structure_cluster_id=cluster_id,
        partition=partition_for_cluster(cluster_id),
    )


def load_mathnet_cases(
    *,
    limit: int,
    offset: int = 0,
    partitions: set[str] | None = None,
) -> list[OlympiadCase]:
    rows = fetch_hf_rows(DATASET, CONFIG, SPLIT, limit, offset)
    cases = [row_to_case(row) for row in rows]
    if partitions is not None:
        cases = [case for case in cases if case.partition in partitions]
    return cases


def _query_signatures(graph: dict[str, Any]) -> list[str]:
    return sorted(
        {
            f"{query.get('kind')}:{query.get('sort') or 'Unknown'}:{query.get('target')}"
            for query in graph.get("queries") or []
        }
    )


def _backend_theories(typed: dict[str, Any]) -> list[str]:
    return sorted(
        {
            str(item.get("theory") or item.get("backend") or item.get("kind") or "unknown")
            for item in typed.get("backend_obligations") or []
        }
    )


def classify_gap(
    graph: dict[str, Any],
    typed: dict[str, Any],
    admissible: list[dict[str, Any]],
    backend_result: dict[str, Any] | None,
    exact: bool | None,
) -> str:
    if exact is True:
        return "solved"
    if not graph.get("queries"):
        return "query_elaboration_gap"
    if not graph.get("constraints"):
        return "constraint_elaboration_gap"
    if typed.get("status") != "type_checked":
        return "type_elaboration_gap"
    if not graph.get("morphisms"):
        return "morphism_extraction_gap"
    if not admissible:
        return "lift_certificate_gap"
    if not typed.get("backend_obligations"):
        return "executable_constraint_gap"
    if backend_result is None:
        return "backend_contract_gap"
    if exact is False:
        return "semantic_or_verification_error"
    return "answer_without_comparable_gold"


def evaluate_case(case: OlympiadCase) -> OlympiadRecord:
    started = time.perf_counter()
    try:
        # Only the statement enters these compilers.  corpus_id, final_answer,
        # and worked solutions are deliberately unavailable to the pipeline.
        graph = compile_typed_semantic_graph(case.problem).to_dict()
        typed = compile_typed_definition_ir(case.problem).to_dict()
        admissible = [item for item in graph.get("lift_certificates") or [] if item.get("admissible")]
        backend_result = solve_from_lift_certificates(graph) if admissible else None
        answer = str(backend_result.get("answer_exact")) if backend_result else None
        exact = answers_match(answer, case.expected) if answer is not None and case.expected is not None else None
        return OlympiadRecord(
            corpus_id_hash=hashlib.sha256(case.corpus_id.encode("utf-8")).hexdigest()[:16],
            country=case.country,
            competition=case.competition,
            topics=list(case.topics),
            language=case.language,
            problem_type=case.problem_type,
            structure_cluster_id=case.structure_cluster_id,
            partition=case.partition,
            graph_status=str(graph.get("status") or ""),
            typed_status=str(typed.get("status") or ""),
            sort_names=sorted({str(item.get("name")) for item in graph.get("sorts") or [] if item.get("name")}),
            morphism_names=sorted(
                {str(item.get("name")) for item in graph.get("morphisms") or [] if item.get("name")}
            ),
            constraint_count=len(graph.get("constraints") or []),
            query_signatures=_query_signatures(graph),
            lift_families=sorted(
                {str(item.get("family_id")) for item in admissible if item.get("family_id")}
            ),
            backend_theories=_backend_theories(typed),
            backend_executed=backend_result is not None,
            answer=answer,
            exact_match=exact,
            failure_layer=classify_gap(graph, typed, admissible, backend_result, exact),
            elapsed_seconds=round(time.perf_counter() - started, 4),
            error=None,
            problem_preview=case.problem[:320],
        )
    except Exception as exc:
        return OlympiadRecord(
            corpus_id_hash=hashlib.sha256(case.corpus_id.encode("utf-8")).hexdigest()[:16],
            country=case.country,
            competition=case.competition,
            topics=list(case.topics),
            language=case.language,
            problem_type=case.problem_type,
            structure_cluster_id=case.structure_cluster_id,
            partition=case.partition,
            graph_status="error",
            typed_status="error",
            sort_names=[],
            morphism_names=[],
            constraint_count=0,
            query_signatures=[],
            lift_families=[],
            backend_theories=[],
            backend_executed=False,
            answer=None,
            exact_match=None,
            failure_layer="runtime_error",
            elapsed_seconds=round(time.perf_counter() - started, 4),
            error=str(exc),
            problem_preview=case.problem[:320],
        )


def evaluate_worker_cases(
    cases: list[OlympiadCase],
    *,
    atlases: tuple[str, ...] = ("unified",),
    max_depth: int = 7,
    max_states: int = 10_000,
) -> list[WorkerOlympiadRecord]:
    """Evaluate statements with the same Worker kernel used by the web app."""
    started = time.perf_counter()
    requests = [
        {
            # A positional token is sufficient for correlation. Corpus IDs,
            # answers, solutions, labels and competitions never enter Worker.
            "id": f"case-{case_index}",
            "statement": case.problem,
            "atlas": atlas,
            "max_depth": max_depth,
            "max_states": max_states,
        }
        for case_index, case in enumerate(cases)
        for atlas in atlases
    ]
    outputs = evaluate_with_worker(requests)
    elapsed = (time.perf_counter() - started) / max(len(outputs), 1)
    records: list[WorkerOlympiadRecord] = []
    for index, output in enumerate(outputs):
        case = cases[index // len(atlases)]
        atlas = atlases[index % len(atlases)]
        analysis = output.get("language_analysis") or {}
        first_goal = output.get("first_goal") or {}
        execution = output.get("execution") or {}
        certificate = execution.get("certificate") or {}
        execution_answer = (
            str(certificate.get("value"))
            if certificate.get("status") == "proved" and certificate.get("value") is not None
            else None
        )
        exact = (
            answers_match(execution_answer, case.expected)
            if execution_answer is not None and case.expected is not None
            else None
        )
        records.append(
            WorkerOlympiadRecord(
                corpus_id_hash=hashlib.sha256(case.corpus_id.encode("utf-8")).hexdigest()[:16],
                country=case.country,
                competition=case.competition,
                topics=list(case.topics),
                language=case.language,
                problem_type=case.problem_type,
                structure_cluster_id=case.structure_cluster_id,
                partition=case.partition,
                atlas=atlas,
                atlas_size=int(output.get("atlas_size") or 0),
                status=str(output.get("status") or "runtime_error"),
                root_sorts=sorted(str(item) for item in output.get("root_sorts") or []),
                query_sorts=sorted(str(item) for item in output.get("query_sorts") or []),
                morphism_names=sorted(set(str(item) for item in output.get("morphisms") or [])),
                parse_count=int(analysis.get("parse_count") or 0),
                constraint_count=len(analysis.get("constraints") or []),
                states_explored=int(output.get("states_explored") or 0),
                exhausted=bool(output.get("exhausted")),
                goal_count=int(output.get("goal_count") or 0),
                first_goal_morphisms=[
                    str(step.get("morphism"))
                    for step in first_goal.get("steps") or []
                    if step.get("morphism")
                ],
                lowering_status=str(execution.get("status") or "not_lowered"),
                execution_status=(str(certificate.get("status")) if certificate.get("status") else None),
                answer=execution_answer,
                exact_match=exact,
                elapsed_seconds=round(elapsed, 4),
                error=None,
                problem_preview=case.problem[:320],
            )
        )
    return records


def summarize_worker(records: list[WorkerOlympiadRecord]) -> dict[str, Any]:
    per_atlas: dict[str, dict[str, Any]] = {}
    for atlas in sorted({record.atlas for record in records}):
        subset = [record for record in records if record.atlas == atlas]
        statuses = Counter(record.status for record in subset)
        resolved = sum(record.status != "query_unresolved" for record in subset)
        reached = statuses["goal_reached"]
        lowered = sum(record.lowering_status == "lowered" for record in subset)
        executed = sum(record.execution_status == "proved" for record in subset)
        exact = sum(record.exact_match is True for record in subset)
        per_atlas[atlas] = {
            "atlas_size": max((record.atlas_size for record in subset), default=0),
            "total": len(subset),
            "query_resolved": resolved,
            "goal_reached": reached,
            "query_resolution_rate": resolved / len(subset) if subset else 0.0,
            "goal_reach_rate": reached / len(subset) if subset else 0.0,
            "lowered": lowered,
            "executed": executed,
            "exact": exact,
            "lowering_rate": lowered / len(subset) if subset else 0.0,
            "execution_rate": executed / len(subset) if subset else 0.0,
            "exact_rate": exact / len(subset) if subset else 0.0,
            "statuses": dict(statuses),
            "states_explored": sum(record.states_explored for record in subset),
        }
    comparison: dict[str, Any] | None = None
    if "core" in per_atlas and "unified" in per_atlas:
        comparison = {
            "goal_reached_delta": per_atlas["unified"]["goal_reached"] - per_atlas["core"]["goal_reached"],
            "goal_reach_rate_delta": per_atlas["unified"]["goal_reach_rate"] - per_atlas["core"]["goal_reach_rate"],
        }
    return {
        "dataset": {"id": DATASET, "config": CONFIG, "split": SPLIT},
        "engine": "authoritative-typescript-worker",
        "metric_scope": {
            "goal_reached": "typed reachability only; this is not an exact solve",
            "lowered": "typed constraints were converted to concrete backend inputs",
            "executed": "the backend returned a proof certificate and value",
            "exact": "the executed value matched evaluation-only gold",
        },
        "data_contract": {
            "worker_input": ["problem_markdown"],
            "evaluation_only": ["final_answer"],
            "post_failure_audit_only": ["solutions_markdown", "topics_flat"],
            "forbidden_worker_inputs": ["corpus id", "solutions_markdown", "final_answer", "competition"],
        },
        "partition_rule": "sha256(number-free structural signature): development 80%, calibration 10%, research_holdout 10%",
        "reachability": per_atlas,
        "comparison": comparison,
        "records": [asdict(record) for record in records],
    }
def summarize(records: list[OlympiadRecord]) -> dict[str, Any]:
    failure_layers = Counter(record.failure_layer for record in records)
    topic_failures: dict[str, Counter[str]] = defaultdict(Counter)
    for record in records:
        roots = {topic.split(">", 1)[0].strip() for topic in record.topics} or {"<unlabelled>"}
        for root in roots:
            topic_failures[root][record.failure_layer] += 1
    frontier = []
    for topic, counts in topic_failures.items():
        for layer, count in counts.items():
            if layer != "solved":
                frontier.append({"topic": topic, "failure_layer": layer, "count": count})
    frontier.sort(key=lambda item: (-item["count"], item["topic"], item["failure_layer"]))
    answered = [record for record in records if record.answer is not None]
    comparable = [record for record in records if record.exact_match is not None]
    correct = sum(record.exact_match is True for record in records)
    return {
        "dataset": {"id": DATASET, "config": CONFIG, "split": SPLIT},
        "data_contract": {
            "solver_input": ["problem_markdown"],
            "evaluation_only": ["final_answer"],
            "post_failure_audit_only": ["solutions_markdown", "topics_flat"],
            "forbidden_solver_inputs": ["id", "solutions_markdown", "final_answer", "competition"],
        },
        "partition_rule": "sha256(number-free structural signature): development 80%, calibration 10%, research_holdout 10%",
        "counts": {
            "total": len(records),
            "answered": len(answered),
            "comparable": len(comparable),
            "correct": correct,
            "errors": sum(record.error is not None for record in records),
            "unique_structure_clusters": len({record.structure_cluster_id for record in records}),
        },
        "rates": {
            "answer_rate": len(answered) / len(records) if records else 0.0,
            "exact_rate_comparable": correct / len(comparable) if comparable else 0.0,
        },
        "failure_layers": dict(failure_layers.most_common()),
        "morphism_gap_frontier": frontier[:50],
        "records": [asdict(record) for record in records],
    }


def write_outputs(result: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    report = output.with_name(output.stem + "_report.md")
    counts = result["counts"]
    lines = [
        "# MathNet Olympiad Development Protocol",
        "",
        "## Data isolation",
        "",
        "- Solver input: problem statement only",
        "- Final answer: scoring only",
        "- Worked solution and topic labels: post-failure audit only",
        "- Self-authored `全問題.tex`: excluded; reserved for final validation",
        "",
        "## Counts",
        "",
    ]
    lines.extend(f"- {key}: {value}" for key, value in counts.items())
    lines.extend(["", "## Failure layers", "", "| layer | count |", "|---|---:|"])
    lines.extend(f"| `{key}` | {value} |" for key, value in result["failure_layers"].items())
    lines.extend(["", "## Morphism gap frontier", "", "| topic | gap | count |", "|---|---|---:|"])
    lines.extend(
        f"| {item['topic']} | `{item['failure_layer']}` | {item['count']} |"
        for item in result["morphism_gap_frontier"][:25]
    )
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_worker_outputs(result: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# MathNet Worker Kernel Development Protocol",
        "",
        "This report measures typed goal reachability. It does not call a reached goal an exact solve.",
        "",
        "| atlas | rules | total | query resolved | goal reached | lowered | executed | exact |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for atlas, metrics in result["reachability"].items():
        lines.append(
            f"| {atlas} | {metrics['atlas_size']} | {metrics['total']} | "
            f"{metrics['query_resolved']} | {metrics['goal_reached']} | {metrics['lowered']} | "
            f"{metrics['executed']} | {metrics['exact']} |"
        )
    if result.get("comparison"):
        lines.extend(["", f"Unified - core reach delta: {result['comparison']['goal_reached_delta']}"])
    output.with_name(output.stem + "_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the structure-first MathNet development protocol.")
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument(
        "--partition",
        choices=("development", "calibration", "research_holdout"),
        default="development",
    )
    parser.add_argument("--finalize-holdout", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--engine", choices=("worker", "legacy-python"), default="worker")
    parser.add_argument("--compare-core", action="store_true")
    parser.add_argument("--max-depth", type=int, default=7)
    parser.add_argument("--max-states", type=int, default=10_000)
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    if args.partition == "research_holdout" and not args.finalize_holdout:
        raise SystemExit("research_holdout is frozen; pass --finalize-holdout for a one-time evaluation")
    cases = load_mathnet_cases(limit=args.limit, offset=args.offset, partitions={args.partition})
    if args.engine == "legacy-python":
        records = [evaluate_case(case) for case in cases]
        result = summarize(records)
        write_outputs(result, args.output)
        summary = {"counts": result["counts"], "failure_layers": result["failure_layers"]}
    else:
        atlases = ("core", "unified") if args.compare_core else ("unified",)
        worker_records = evaluate_worker_cases(
            cases,
            atlases=atlases,
            max_depth=args.max_depth,
            max_states=args.max_states,
        )
        result = summarize_worker(worker_records)
        write_worker_outputs(result, args.output)
        summary = {"reachability": result["reachability"], "comparison": result["comparison"]}
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
