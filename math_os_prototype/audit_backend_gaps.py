"""Account for every benchmark failure by reusable backend contract.

This is an audit tool, not a solver.  It never reads expected answers when it
assigns a contract.  The output is used to decide which small typed executor
closes the largest set of currently unexecutable semantic graphs.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any


CONTRACTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("finite_domain_filter_observe", (
        "probability", "random", "ways", "arrange", "choose", "select",
        "integers", "factors", "digits", "remainder",
        "divisible", "congruence", "modulo", "least positive integer",
    )),
    ("percent_affine_state_observe", ("percent", "%", "discount", "markup")),
    ("comparison_affine_graph_observe", (
        "ratio", "more than", "less than", "fewer than", "twice as",
        "times as", "difference",
    )),
    ("typed_rate_graph_contract_observe", ("per ", "each ", "rate")),
    ("state_event_flow_observe", ("remaining", "left", "received", "sold", "spent")),
    ("aggregate_coproduct_observe", ("total", "altogether", "combined", "average")),
    ("matrix_vector_transform_observe", (
        "matrix", "vector", "projection", "determinant", "coordinates",
        "linear transformation", "dot product",
    )),
    ("geometric_constraint_invariant_measure", (
        "triangle", "circle", "square", "polygon", "parabola", "ellipse",
        "angle", "area", "volume", "radius", "tangent", "midpoint",
        "perimeter", "solid", "cube",
    )),
    ("symbolic_relation_eliminate_observe", (
        "equation", "function", "polynomial", "roots", "domain", "range",
        "log", "sqrt", "sequence", "series", "asymptote", "complex",
        "sin", "cos", "tan",
    )),
    ("calculus_limit_integral_optimize", (
        "integral", "derivative", "limit", "maximum", "minimum", "extremum",
    )),
    ("proof_search_kernel_check", ("prove", "show that", "demonstrate", "theorem")),
)


def contract_for(record: dict[str, Any]) -> str:
    text = str(record.get("problem_preview") or "").lower()
    scores = {
        name: sum(1 for marker in markers if marker in text)
        for name, markers in CONTRACTS
    }
    best_score = max(scores.values(), default=0)
    if best_score == 0:
        intent = str(record.get("intent") or "")
        if "geometry" in intent or "minkowski" in intent:
            return "geometric_constraint_invariant_measure"
        if "calculus" in intent:
            return "calculus_limit_integral_optimize"
        return "typed_semantic_graph_requires_new_lowering"
    return min(name for name, score in scores.items() if score == best_score)


def audit(payload: dict[str, Any]) -> dict[str, Any]:
    unresolved = [
        record for record in payload.get("records", [])
        if record.get("failure_layer") != "solved"
    ]
    contract_counts: Counter[str] = Counter()
    layer_contract_counts: dict[str, Counter[str]] = defaultdict(Counter)
    samples: dict[str, list[dict[str, Any]]] = defaultdict(list)
    assignments: list[dict[str, Any]] = []
    for record in unresolved:
        contract = contract_for(record)
        layer = str(record.get("failure_layer") or "unknown")
        contract_counts[contract] += 1
        layer_contract_counts[layer][contract] += 1
        assignment = {
            "case_id": record.get("case_id"),
            "problem_hash": record.get("problem_hash"),
            "partition": record.get("evaluation_partition"),
            "benchmark": record.get("benchmark"),
            "subset": record.get("subset"),
            "failure_layer": layer,
            "required_contract": contract,
            "preview": record.get("problem_preview"),
        }
        assignments.append(assignment)
        if len(samples[contract]) < 8:
            samples[contract].append(assignment)
    return {
        "schema": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_total": payload.get("total"),
        "source_exact_match": payload.get("exact_match"),
        "unresolved_total": len(unresolved),
        "accounted_total": sum(contract_counts.values()),
        "all_unresolved_accounted": len(unresolved) == sum(contract_counts.values()),
        "contract_counts": dict(contract_counts.most_common()),
        "failure_layer_contract_counts": {
            layer: dict(counts.most_common())
            for layer, counts in sorted(layer_contract_counts.items())
        },
        "samples": dict(samples),
        "assignments": assignments,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    report = audit(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key not in {"samples", "assignments"}}, ensure_ascii=False, indent=2))
    return 0 if report["all_unresolved_accounted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
