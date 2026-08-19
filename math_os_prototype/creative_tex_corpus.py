"""Build a rights-scoped CreativeBench corpus from a structured TeX document.

The importer treats ``itembox`` environments before the answer section as
problem units.  It never uses displayed problem numbers as identifiers because
real collections often contain duplicated or renumbered labels.  Stable IDs are
derived from source ID, ordinal position, and statement hash instead.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable

try:
    from math_os_prototype.category_semantics import compile_typed_semantic_graph
    from math_os_prototype.creative_benchmark import (
        ALLOWED_RIGHTS_BASES,
        CreativeProblemRecord,
    )
    from math_os_prototype.domain_registry import DomainIR, DomainRegistry
    from math_os_prototype.formal_language import compile_formal_ir
    from math_os_prototype.typed_definition_kernel import compile_typed_definition_ir
except ImportError:  # Allows direct execution from the package directory.
    from category_semantics import compile_typed_semantic_graph
    from creative_benchmark import ALLOWED_RIGHTS_BASES, CreativeProblemRecord
    from domain_registry import DomainIR, DomainRegistry
    from formal_language import compile_formal_ir
    from typed_definition_kernel import compile_typed_definition_ir


ITEMBOX_PATTERN = re.compile(
    r"\\begin\{itembox\}(?:\[[^\]]*\])?\{(?P<label>[^{}]*)\}"
    r"(?P<body>.*?)\\end\{itembox\}",
    flags=re.DOTALL,
)
ANSWER_SECTION_MARKERS = (
    r"\fbox{解答編}",
    r"\section*{問題1解答}",
)
THREE_DIMENSION_MARKERS = (
    "xyz",
    "空間",
    "立体",
    "球体",
    "球面",
    "体積",
    "正多面体",
    "十二面体",
)
TWO_DIMENSION_MARKERS = (
    "xy",
    "平面",
    "三角形",
    "円",
    "曲線",
    "放物線",
    "面積",
    "複素数平面",
)


@dataclass(frozen=True)
class TexProblemBlock:
    ordinal: int
    label: str
    statement_tex: str
    statement_hash: str


def strip_tex_comments(text: str) -> str:
    lines = [re.sub(r"(?<!\\)%.*$", "", line) for line in text.splitlines()]
    return "\n".join(lines)


def problem_section(text: str) -> str:
    positions = [text.find(marker) for marker in ANSWER_SECTION_MARKERS]
    valid = [position for position in positions if position >= 0]
    return text[: min(valid)] if valid else text


def extract_itembox_problems(text: str) -> list[TexProblemBlock]:
    source = problem_section(strip_tex_comments(text))
    blocks: list[TexProblemBlock] = []
    for match in ITEMBOX_PATTERN.finditer(source):
        label = re.sub(r"\s+", " ", match.group("label")).strip()
        if not label.startswith("問題"):
            continue
        statement = match.group("body").strip()
        if not statement:
            continue
        digest = sha256(canonical_statement(statement).encode("utf-8")).hexdigest()
        blocks.append(
            TexProblemBlock(
                ordinal=len(blocks) + 1,
                label=label,
                statement_tex=statement,
                statement_hash=digest,
            )
        )
    return blocks


def canonical_statement(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def analyze_problem_block(
    block: TexProblemBlock,
    *,
    source_id: str,
    source_path: Path,
    rights_basis: str,
    author_system: str,
    registry: DomainRegistry,
) -> CreativeProblemRecord:
    domain_ir = registry.analyze(block.statement_tex)
    semantic_error: str | None = None
    typed_ir = compile_typed_definition_ir(block.statement_tex)
    formal_ir = compile_formal_ir(block.statement_tex)
    try:
        graph = compile_typed_semantic_graph(
            block.statement_tex,
            typed_definition_ir=typed_ir.to_dict(),
            formal_ir=formal_ir.to_dict(),
        )
        graph_data = graph.to_dict()
        certificates = sorted(
            (item for item in graph.lift_certificates if item.admissible),
            key=lambda item: (
                -len(item.morphism_chain),
                item.family_id,
                item.canonical_signature(),
            ),
        )
    except Exception as exc:  # Corpus import must preserve failures for audit.
        graph = None
        graph_data = {}
        certificates = []
        semantic_error = f"{type(exc).__name__}: {exc}"

    certificate = certificates[0] if certificates else None
    fingerprint = semantic_fingerprint(graph_data, domain_ir)
    family_id = certificate.family_id if certificate else f"semantic:{domain_ir.domain}:{fingerprint}"
    strategy = (
        " -> ".join(certificate.morphism_chain)
        if certificate
        else fallback_strategy(graph_data, domain_ir)
    )
    query = first_query(graph_data)
    obligations = unique_strings(
        [
            *domain_ir.verification,
            *(
                graph.constraint_ir().obligations
                if graph is not None
                else ["typed semantic graph must compile before verification"]
            ),
        ]
    )
    record_id = (
        f"tex:{source_id}:{block.ordinal:04d}:{block.statement_hash[:12]}"
    )
    return CreativeProblemRecord(
        record_id=record_id,
        source_kind="human",
        author_system=author_system,
        domain=domain_ir.domain,
        task=domain_ir.operation,
        statement_tex=block.statement_tex,
        family_id=family_id,
        strategy=strategy,
        proof_obligations=obligations,
        normal_form=certificate.canonical_signature() if certificate else fingerprint,
        verification={
            "status": "pending",
            "method": "independent verification not yet attached",
            "semantic_compile": "failed" if semantic_error else graph_data.get("status", "unknown"),
        },
        rights_basis=rights_basis,
        metadata={
            "source_id": source_id,
            "source_path": str(source_path),
            "problem_label": block.label,
            "source_ordinal": block.ordinal,
            "statement_sha256": block.statement_hash,
            "domain_confidence": domain_ir.confidence,
            "domain_status": domain_ir.status,
            "domain_candidates": domain_ir.candidates,
            "match_group": (
                f"lift:{certificate.family_id}"
                if certificate
                else infer_match_group(domain_ir, block.statement_tex, query)
            ),
            "surface_match_group": infer_match_group(
                domain_ir, block.statement_tex, query
            ),
            "semantic_status": graph_data.get("status", "failed"),
            "semantic_error": semantic_error,
            "typed_definition_status": typed_ir.status,
            "typed_definitions": sorted(
                str(item.get("canonical") or "unknown")
                for item in typed_ir.definitions_used
            ),
            "formal_ir_status": formal_ir.status,
            "semantic_object_sorts": sorted(
                {str(item.get("sort") or "Unknown") for item in graph_data.get("objects", [])}
            ),
            "semantic_morphisms": sorted(
                {str(item.get("name") or "unknown") for item in graph_data.get("morphisms", [])}
            ),
            "query": query,
            "lift_certificates": [item.to_dict() for item in certificates],
            "answer_section_imported": False,
            "rights_scope": "user-identified self-authored TeX corpus"
            if rights_basis == "self_authored"
            else rights_basis,
        },
    )


def semantic_fingerprint(graph: dict[str, Any], domain_ir: DomainIR) -> str:
    payload = {
        "domain": domain_ir.domain,
        "operation": domain_ir.operation,
        "object_sorts": sorted(
            str(item.get("sort") or "Unknown") for item in graph.get("objects", [])
        ),
        "morphisms": sorted(
            (
                str(item.get("name") or "unknown"),
                tuple(str(value) for value in item.get("domain", []) or []),
                str(item.get("codomain") or "Unknown"),
            )
            for item in graph.get("morphisms", [])
        ),
        "constraint_kinds": sorted(
            str(item.get("kind") or "unknown") for item in graph.get("constraints", [])
        ),
        "queries": sorted(
            (
                str(item.get("kind") or "unknown"),
                str(item.get("sort") or "Unknown"),
            )
            for item in graph.get("queries", [])
        ),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode("utf-8")).hexdigest()[:20]


def fallback_strategy(graph: dict[str, Any], domain_ir: DomainIR) -> str:
    morphisms = sorted(
        {str(item.get("name") or "") for item in graph.get("morphisms", []) if item.get("name")}
    )
    return " -> ".join(morphisms[:8]) or domain_ir.operation


def first_query(graph: dict[str, Any]) -> dict[str, Any]:
    queries = graph.get("queries", []) or []
    return dict(queries[0]) if queries else {}


def infer_match_group(
    domain_ir: DomainIR,
    statement: str,
    query: dict[str, Any],
) -> str:
    compact = statement.lower().replace(" ", "")
    if domain_ir.domain == "geometry":
        dimension = infer_geometry_dimension(compact)
        output = infer_geometry_output(compact, domain_ir.operation)
        return f"geometry:{dimension}:{output}"
    query_kind = str(query.get("kind") or domain_ir.operation)
    query_sort = str(query.get("sort") or "Unknown")
    if domain_ir.domain in {"number_theory", "combinatorics"}:
        output = "proof" if query_kind == "prove" else "solution_set"
        return f"{domain_ir.domain}:discrete:{output}"
    if "数列" in compact or "漸化式" in compact:
        output = "closed_form" if "一般項" in compact else domain_ir.operation
        return f"{domain_ir.domain}:sequence:{output}"
    return f"{domain_ir.domain}:{domain_ir.operation}:{query_sort}"


def infer_geometry_dimension(compact: str) -> str:
    if any(marker in compact for marker in THREE_DIMENSION_MARKERS):
        return "3d"
    if any(marker in compact for marker in TWO_DIMENSION_MARKERS):
        return "2d"
    return "unspecified"


def infer_geometry_output(compact: str, operation: str) -> str:
    if "体積" in compact:
        return "solid_volume"
    if "面積" in compact:
        return "area"
    if "軌跡" in compact or operation == "locus":
        return "curve"
    if "通過領域" in compact or operation == "passing_region":
        return "region"
    if operation == "optimize":
        return "scalar_optimum"
    if "存在" in compact:
        return "existence_prop"
    return operation


def unique_strings(values: Iterable[str]) -> list[str]:
    output: list[str] = []
    for value in values:
        text = str(value)
        if text and text not in output:
            output.append(text)
    return output


def select_stratified(
    records: list[CreativeProblemRecord],
    *,
    limit: int | None,
    seed: int,
) -> list[CreativeProblemRecord]:
    if limit is None or limit >= len(records):
        return list(records)
    if limit <= 0:
        return []

    grouped: dict[str, list[CreativeProblemRecord]] = defaultdict(list)
    for record in records:
        grouped[record.domain].append(record)
    domains = sorted(grouped)
    allocations = {domain: 0 for domain in domains}

    if limit >= len(domains):
        for domain in domains:
            allocations[domain] = 1
    remaining = limit - sum(allocations.values())
    capacities = {
        domain: len(grouped[domain]) - allocations[domain] for domain in domains
    }
    total_capacity = sum(capacities.values())
    remainders: list[tuple[float, str]] = []
    if remaining > 0 and total_capacity > 0:
        for domain in domains:
            exact = remaining * capacities[domain] / total_capacity
            addition = min(capacities[domain], int(exact))
            allocations[domain] += addition
            remainders.append((exact - addition, domain))
        left = limit - sum(allocations.values())
        for _, domain in sorted(remainders, key=lambda item: (-item[0], item[1])):
            if left <= 0:
                break
            if allocations[domain] < len(grouped[domain]):
                allocations[domain] += 1
                left -= 1

    selected: list[CreativeProblemRecord] = []
    for domain in domains:
        ranked = sorted(
            grouped[domain],
            key=lambda record: sha256(
                f"{seed}:{record.record_id}".encode("utf-8")
            ).hexdigest(),
        )
        selected.extend(ranked[: allocations[domain]])
    return sorted(
        selected,
        key=lambda record: int(record.metadata.get("source_ordinal") or 0),
    )


def build_tex_corpus(
    path: Path,
    *,
    source_id: str,
    rights_basis: str,
    author_system: str,
    limit: int | None,
    seed: int,
    fixed_record_ids: list[str] | None = None,
) -> tuple[list[CreativeProblemRecord], dict[str, Any]]:
    if rights_basis not in ALLOWED_RIGHTS_BASES:
        raise ValueError(f"rights_basis must be one of {sorted(ALLOWED_RIGHTS_BASES)}")
    text = path.read_text(encoding="utf-8")
    blocks = extract_itembox_problems(text)
    registry = DomainRegistry()
    records = [
        analyze_problem_block(
            block,
            source_id=source_id,
            source_path=path,
            rights_basis=rights_basis,
            author_system=author_system,
            registry=registry,
        )
        for block in blocks
    ]
    if fixed_record_ids is not None:
        by_id = {record.record_id: record for record in records}
        missing_ids = [record_id for record_id in fixed_record_ids if record_id not in by_id]
        if missing_ids:
            raise ValueError(f"fixed selection contains missing record IDs: {missing_ids}")
        selected = [by_id[record_id] for record_id in fixed_record_ids]
        selection_mode = "fixed_record_ids"
    else:
        selected = select_stratified(records, limit=limit, seed=seed)
        selection_mode = "domain_stratified_hash"
    label_counts = Counter(block.label for block in blocks)
    duplicate_labels = {
        label: count for label, count in sorted(label_counts.items()) if count > 1
    }
    report = {
        "corpus": "MathOS CreativeBench TeX import",
        "source_id": source_id,
        "source_path": str(path),
        "source_sha256": sha256(path.read_bytes()).hexdigest(),
        "rights_basis": rights_basis,
        "answer_section_imported": False,
        "extracted_problem_count": len(records),
        "selected_problem_count": len(selected),
        "selection_limit": limit,
        "selection_seed": seed,
        "selection_mode": selection_mode,
        "duplicate_display_labels": duplicate_labels,
        "all_domain_counts": dict(Counter(record.domain for record in records)),
        "selected_domain_counts": dict(Counter(record.domain for record in selected)),
        "all_task_counts": dict(Counter(record.task for record in records)),
        "selected_task_counts": dict(Counter(record.task for record in selected)),
        "semantic_compile_failures": sum(
            bool(record.metadata.get("semantic_error")) for record in records
        ),
        "classified_count": sum(
            record.metadata.get("domain_status") == "classified" for record in records
        ),
        "lifted_count": sum(
            bool(record.metadata.get("lift_certificates")) for record in records
        ),
        "selected_lifted_count": sum(
            bool(record.metadata.get("lift_certificates")) for record in selected
        ),
        "selected_unlifted_count": sum(
            not bool(record.metadata.get("lift_certificates")) for record in selected
        ),
        "selected_certificate_family_counts": dict(
            Counter(
                record.family_id
                for record in selected
                if record.metadata.get("lift_certificates")
            )
        ),
        "unique_family_count_all": len({record.family_id for record in records}),
        "unique_family_count_selected": len({record.family_id for record in selected}),
        "selected_record_ids": [record.record_id for record in selected],
    }
    return selected, report


def write_jsonl(path: Path, records: Iterable[CreativeProblemRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(
        json.dumps(record.to_dict(), ensure_ascii=False, sort_keys=True)
        for record in records
    )
    path.write_text(payload + ("\n" if payload else ""), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Import itembox problems from a TeX corpus.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--source-id")
    parser.add_argument("--author-system", default="human")
    parser.add_argument("--rights-basis", required=True, choices=sorted(ALLOWED_RIGHTS_BASES))
    parser.add_argument("--limit", type=int, default=54)
    parser.add_argument("--seed", type=int, default=20260722)
    parser.add_argument(
        "--fixed-selection-report",
        type=Path,
        help="Reuse selected_record_ids from an earlier import report.",
    )
    args = parser.parse_args()

    fixed_record_ids = None
    if args.fixed_selection_report:
        fixed_payload = json.loads(args.fixed_selection_report.read_text(encoding="utf-8"))
        fixed_record_ids = [str(value) for value in fixed_payload["selected_record_ids"]]

    records, report = build_tex_corpus(
        args.input,
        source_id=args.source_id or args.input.stem,
        rights_basis=args.rights_basis,
        author_system=args.author_system,
        limit=args.limit,
        seed=args.seed,
        fixed_record_ids=fixed_record_ids,
    )
    write_jsonl(args.output, records)
    report_path = args.report or args.output.with_suffix(".report.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "report": str(report_path),
                **{
                    key: report[key]
                    for key in (
                        "extracted_problem_count",
                        "selected_problem_count",
                        "duplicate_display_labels",
                        "selected_domain_counts",
                        "semantic_compile_failures",
                        "classified_count",
                        "lifted_count",
                        "selected_lifted_count",
                        "selected_unlifted_count",
                        "unique_family_count_selected",
                    )
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
