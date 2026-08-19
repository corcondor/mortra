"""Mine corpus lift failures into structural gaps.

This is a diagnostic tool, not a solver.  It reads a corpus lift protocol output
and groups rejected / lifted-but-unexecuted records by missing mathematical
structure.  The report is meant to drive synthetic/minimal-pair generation
without adding benchmark-id branches.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path("math_os_prototype/corpus_lift_public_1000_25families.json")
DEFAULT_OUTPUT = Path("math_os_prototype/failure_mining_report.json")


@dataclass(frozen=True)
class FailureCluster:
    cluster_id: str
    symptom: str
    likely_missing_structure: str
    next_action: str
    examples: list[dict[str, Any]]
    count: int = 0


CLUSTER_RULES: list[tuple[str, str, str, str, str]] = [
    (
        "state_event_arithmetic",
        r"\b(how many|how much|total|left|remain|remaining|altogether|each|more|less|spent|cost|earn|gave|bought|sold|per day|per week)\b",
        "quantity/state/event composition was not lifted",
        "Build StateEventGraph with owner/object/time and additive/multiplicative transitions.",
        "rejected",
    ),
    (
        "tex_algebra_equation",
        r"(\$|\\frac|\\lceil|\\sqrt|\\log|\^|_).*(solve|find|evaluate|value|positive difference|minimum|maximum)",
        "TeX expression was not normalized into algebraic constraints",
        "Add TeX-to-Expression AST before family detection; do not branch by problem text.",
        "rejected",
    ),
    (
        "integer_number_theory",
        r"\b(prime|integer|divisible|gcd|lcm|multiple|factor|modulo|remainder|least common multiple|greatest common divisor)\b",
        "integer constraints / divisibility morphisms were not lifted",
        "Add IntegerConstraintGraph: divisibility, factorization, gcd/lcm, modular equality.",
        "rejected",
    ),
    (
        "geometry_locus_metric",
        r"\b(triangle|circle|ellipse|parabola|hyperbola|area|perimeter|angle|distance|graph|coordinate plane|asy)\b",
        "geometry object/constraint chart was not expressive enough",
        "Add coordinate geometry chart with conic/line/circle constraints and optimization hooks.",
        "rejected",
    ),
    (
        "finite_probability_counting",
        r"\b(probability|random|cards|dice|ways|choose|arrangements|permutations|deck)\b",
        "finite counting/probability event algebra was not lifted",
        "Add finite sample-space/event combinatorics and exact probability backend contracts.",
        "rejected",
    ),
    (
        "function_sequence_recurrence",
        r"\b(sequence|recurrence|fibonacci|arithmetic progression|geometric progression|function f|f\(|a_n)\b",
        "sequence/function recurrence chart was not lifted",
        "Add recurrence/function equation IR with indexed observations.",
        "rejected",
    ),
    (
        "proof_inequality",
        r"\b(prove|show|inequality|positive real|for all|for every|maximum|minimum|least|greatest)\b",
        "proof/optimization goal lacked theorem-search representation",
        "Add Prove/Optimize query with inequalities, domain constraints, and verifier obligations.",
        "rejected",
    ),
    (
        "lifted_no_backend",
        r".*",
        "LiftCertificate existed but backend contract could not execute",
        "Inspect constraints for that family and widen backend input grammar without changing family semantics.",
        "lifted_no_backend",
    ),
    (
        "answered_wrong",
        r".*",
        "Backend produced a checked-wrong answer",
        "Tighten verifier gate or narrow the family trigger before increasing coverage.",
        "wrong",
    ),
]


def mine_failures(protocol_result: dict[str, Any], *, examples_per_cluster: int = 5) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    records = protocol_result.get("records", []) or []
    for record in records:
        cluster_id = classify_record(record)
        if cluster_id is None:
            continue
        buckets[cluster_id].append(record)

    clusters = []
    for cluster_id, items in sorted(buckets.items(), key=lambda item: (-len(item[1]), item[0])):
        clusters.append(build_cluster(cluster_id, items, examples_per_cluster=examples_per_cluster))

    return {
        "objective": "group corpus failures by missing structure, not by benchmark id or answer",
        "input_counts": protocol_result.get("counts", {}),
        "input_rates": protocol_result.get("rates", {}),
        "cluster_counts": {cluster["cluster_id"]: cluster["count"] for cluster in clusters},
        "clusters": clusters,
    }


def classify_record(record: dict[str, Any]) -> str | None:
    if record.get("wrong"):
        return "answered_wrong"
    if record.get("lifted") and not record.get("backend_executed"):
        return "lifted_no_backend"
    if not record.get("rejected"):
        return None
    text = str(record.get("text_preview") or "").lower()
    for cluster_id, pattern, _missing, _action, symptom in CLUSTER_RULES:
        if symptom != "rejected":
            continue
        if re.search(pattern, text):
            return cluster_id
    return "other_rejected"


def build_cluster(cluster_id: str, records: list[dict[str, Any]], *, examples_per_cluster: int) -> dict[str, Any]:
    rule = next((item for item in CLUSTER_RULES if item[0] == cluster_id), None)
    if rule:
        _cluster, _pattern, missing, action, symptom = rule
    else:
        missing = "no high-confidence structural gap rule matched"
        action = "Sample manually and decide whether this is a new family or frontend normalization gap."
        symptom = "rejected"
    by_source = Counter(str(record.get("source") or "") for record in records)
    by_subset = Counter(f"{record.get('source')}:{record.get('subset')}" for record in records)
    examples = [
        {
            "source": record.get("source"),
            "subset": record.get("subset"),
            "index": record.get("index"),
            "lift_families": record.get("lift_families"),
            "answer": record.get("answer"),
            "expected": record.get("expected"),
            "text_preview": record.get("text_preview"),
        }
        for record in records[:examples_per_cluster]
    ]
    return asdict(
        FailureCluster(
            cluster_id=cluster_id,
            symptom=symptom,
            likely_missing_structure=missing,
            next_action=action,
            examples=examples,
            count=len(records),
        )
    ) | {
        "by_source": dict(by_source.most_common()),
        "top_subsets": dict(by_subset.most_common(10)),
        "minimal_pair_seed_ideas": minimal_pair_ideas(cluster_id),
    }


def minimal_pair_ideas(cluster_id: str) -> list[str]:
    return {
        "state_event_arithmetic": [
            "A has n objects; B gives A q objects; query A.",
            "A has n objects; A gives B q objects; query A.",
            "A buys packs with k objects each; query total objects.",
        ],
        "tex_algebra_equation": [
            "Solve b^x=N and log_b(x)=k with TeX and plain-text variants.",
            "Normalize \\frac, powers, roots, floors, ceilings into one Expression AST.",
        ],
        "integer_number_theory": [
            "a is divisible by m; find residue / possible values under bounds.",
            "gcd/lcm constraints with swapped variables and numeric perturbations.",
        ],
        "geometry_locus_metric": [
            "Point on conic; optimize distance to origin.",
            "Two lines/circles; query intersection/area/radius under coordinate transforms.",
        ],
        "finite_probability_counting": [
            "Complement event, at-least event, exactly-k event over finite uniform samples.",
            "Cards/dice/selection statements with same event under surface changes.",
        ],
        "function_sequence_recurrence": [
            "Listed arithmetic/geometric sequences and recurrence definitions.",
            "Function equations with evaluation query f(n).",
        ],
        "proof_inequality": [
            "Polynomial inequality proof with domain constraints.",
            "Optimization query under positive real constraints.",
        ],
        "lifted_no_backend": [
            "For each lifted family, generate variants of the same constraint grammar seen in corpus.",
        ],
        "answered_wrong": [
            "Generate adversarial near-misses that share words but differ in query/role.",
        ],
    }.get(cluster_id, ["Sample manually; no automatic minimal-pair seed yet."])


def write_outputs(result: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    output.with_name(output.stem + "_report.md").write_text(render_report(result, output), encoding="utf-8")


def render_report(result: dict[str, Any], output: Path) -> str:
    lines = [
        "# Failure Mining Report",
        "",
        result["objective"],
        "",
        "## Cluster Counts",
        "",
        "| cluster | count |",
        "|---|---:|",
    ]
    for cluster, count in result["cluster_counts"].items():
        lines.append(f"| `{cluster}` | {count} |")
    for cluster in result["clusters"]:
        lines.extend(
            [
                "",
                f"## {cluster['cluster_id']}",
                "",
                f"- count: {cluster['count']}",
                f"- symptom: `{cluster['symptom']}`",
                f"- missing: {cluster['likely_missing_structure']}",
                f"- next: {cluster['next_action']}",
                f"- by_source: `{cluster['by_source']}`",
                "",
                "Examples:",
            ]
        )
        for example in cluster["examples"]:
            preview = str(example.get("text_preview") or "").replace("\n", " ")[:220]
            lines.append(f"- {example.get('source')}:{example.get('subset')}#{example.get('index')} - {preview}")
    lines.extend(["", "## Files", "", f"- json: `{output}`", f"- report: `{output.with_name(output.stem + '_report.md')}`"])
    return "\n".join(lines) + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Mine corpus lift failures by missing structure.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--examples-per-cluster", type=int, default=5)
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    protocol_result = json.loads(args.input.read_text(encoding="utf-8"))
    result = mine_failures(protocol_result, examples_per_cluster=args.examples_per_cluster)
    write_outputs(result, args.output)
    print(json.dumps({"cluster_counts": result["cluster_counts"]}, ensure_ascii=False, indent=2))
    print(f"json: {args.output}")
    print(f"report: {args.output.with_name(args.output.stem + '_report.md')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
