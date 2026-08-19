"""Learned LiftCertificate lifter.

The model in this file is intentionally lightweight and inspectable.  It does
not learn answers.  It learns to map problem text to the structural certificate
used by MathOS:

    family_id + morphism_chain + constraint_skeleton + query_signature
    + backend_contract

This makes the learning target explicit enough to evaluate the seven
generalization axes without turning the system into a solution memorizer.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

try:
    from math_os_prototype.category_semantics import compile_typed_semantic_graph
    from math_os_prototype.generalization_benchmark import (
        GeneralizationCase,
        generate_generalization_cases,
        generate_same_structure_pairs,
    )
    from math_os_prototype.lift_backend import solve_from_lift_certificates
    from math_os_prototype.public_benchmark import answers_match
except ImportError:  # Allows direct script execution.
    from category_semantics import compile_typed_semantic_graph
    from generalization_benchmark import GeneralizationCase, generate_generalization_cases, generate_same_structure_pairs
    from lift_backend import solve_from_lift_certificates
    from public_benchmark import answers_match


DEFAULT_OUTPUT = Path("math_os_prototype/lift_lifter_experiment.json")


@dataclass(frozen=True)
class LiftLifterExample:
    case_id: str
    family_id: str
    split: str
    transform: str
    problem: str
    expected: str
    gold_certificate: dict[str, Any]


@dataclass(frozen=True)
class LiftLifterPrediction:
    status: str
    family_id: str | None
    confidence: float
    score: float
    certificate: dict[str, Any] | None


@dataclass
class LiftLifterRecord:
    case_id: str
    split: str
    transform: str
    gold_family_id: str
    predicted_family_id: str | None
    status: str
    confidence: float
    family_match: bool
    morphism_chain_match: bool
    constraint_skeleton_match: bool
    query_signature_match: bool
    backend_contract_match: bool
    backend_executed: bool
    backend_correct: bool
    wrong: bool
    rejected: bool
    expected: str
    answer: str | None
    problem: str


def build_lift_lifter_examples(seeds: int = 8) -> list[LiftLifterExample]:
    examples: list[LiftLifterExample] = []
    for case in generate_generalization_cases(seeds=seeds):
        graph = compile_typed_semantic_graph(case.problem)
        certificate = select_gold_certificate(graph.to_dict(), case.family_id)
        if certificate is None:
            continue
        split = stratified_split_from_case(case, seeds)
        examples.append(
            LiftLifterExample(
                case_id=case.case_id,
                family_id=case.family_id,
                split=split,
                transform=case.transform,
                problem=case.problem,
                expected=case.expected,
                gold_certificate=certificate,
            )
        )
    return examples


def stratified_split_from_case(case: GeneralizationCase, seeds: int) -> str:
    try:
        seed = int(case.case_id.split(":")[1])
    except Exception:
        seed = 0
    if seeds < 5:
        return "dev" if seed == 0 else ("calib" if seed % 2 == 0 else "held_out")
    dev_cut = max(1, int(seeds * 0.6))
    calib_cut = max(dev_cut + 1, int(seeds * 0.8))
    if seed < dev_cut:
        return "dev"
    if seed < calib_cut:
        return "calib"
    return "held_out"


def select_gold_certificate(graph: dict[str, Any], family_id: str) -> dict[str, Any] | None:
    for certificate in graph.get("lift_certificates", []) or []:
        if certificate.get("family_id") == family_id and certificate.get("admissible"):
            return dict(certificate)
    return None


class SparseLiftCertificateLifter:
    def __init__(self, *, alpha: float = 0.5):
        self.alpha = alpha
        self.label_feature_counts: dict[str, Counter[str]] = {}
        self.label_totals: dict[str, int] = {}
        self.label_priors: dict[str, int] = {}
        self.vocabulary: set[str] = set()
        self.prototypes: dict[str, dict[str, Any]] = {}
        self.threshold: float = 0.0

    def fit(self, examples: list[LiftLifterExample]) -> None:
        self.label_feature_counts = defaultdict(Counter)
        self.label_totals = defaultdict(int)
        self.label_priors = defaultdict(int)
        self.vocabulary = set()
        self.prototypes = {}
        for example in examples:
            features = extract_features(example.problem)
            self.label_priors[example.family_id] += 1
            self.prototypes.setdefault(example.family_id, example.gold_certificate)
            for feature in features:
                self.label_feature_counts[example.family_id][feature] += 1
                self.label_totals[example.family_id] += 1
                self.vocabulary.add(feature)
        self.label_feature_counts = dict(self.label_feature_counts)
        self.label_totals = dict(self.label_totals)
        self.label_priors = dict(self.label_priors)

    def calibrate(self, examples: list[LiftLifterExample]) -> None:
        if not examples:
            self.threshold = 0.0
            return
        margins = sorted({self.score_margin(example.problem) for example in examples})
        candidates = [-math.inf, *margins, math.inf]
        best_threshold = 0.0
        best_score = -math.inf
        for threshold in candidates:
            score = 0.0
            for example in examples:
                prediction = self.predict(example.problem, threshold=threshold)
                if prediction.status == "rejected":
                    score -= 0.1
                elif prediction.family_id == example.family_id:
                    score += 1.0
                else:
                    score -= 2.0
            if score > best_score:
                best_score = score
                best_threshold = threshold
        self.threshold = 0.0 if best_threshold == -math.inf else best_threshold

    def predict(self, text: str, *, threshold: float | None = None) -> LiftLifterPrediction:
        scores = self.label_scores(text)
        if not scores:
            return LiftLifterPrediction("rejected", None, 0.0, -math.inf, None)
        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        best_label, best_score = ranked[0]
        second_score = ranked[1][1] if len(ranked) > 1 else best_score - 100.0
        confidence = best_score - second_score
        active_threshold = self.threshold if threshold is None else threshold
        if confidence < active_threshold:
            return LiftLifterPrediction("rejected", None, confidence, best_score, None)
        certificate = dict(self.prototypes[best_label])
        certificate["source"] = "learned_lift_lifter"
        return LiftLifterPrediction("predicted", best_label, confidence, best_score, certificate)

    def score_margin(self, text: str) -> float:
        scores = self.label_scores(text)
        ranked = sorted(scores.values(), reverse=True)
        if not ranked:
            return 0.0
        if len(ranked) == 1:
            return 100.0
        return ranked[0] - ranked[1]

    def label_scores(self, text: str) -> dict[str, float]:
        if not self.label_feature_counts:
            return {}
        features = extract_features(text)
        vocabulary_size = max(len(self.vocabulary), 1)
        total_examples = sum(self.label_priors.values())
        scores: dict[str, float] = {}
        for label, counts in self.label_feature_counts.items():
            prior = math.log(self.label_priors[label] / total_examples)
            denom = self.label_totals[label] + self.alpha * vocabulary_size
            score = prior
            for feature in features:
                score += math.log((counts.get(feature, 0) + self.alpha) / denom)
            scores[label] = score
        return scores

    def to_dict(self) -> dict[str, Any]:
        return {
            "alpha": self.alpha,
            "threshold": self.threshold,
            "labels": sorted(self.label_priors),
            "vocabulary_size": len(self.vocabulary),
            "label_priors": dict(self.label_priors),
            "prototypes": self.prototypes,
        }


def extract_features(text: str) -> list[str]:
    normalized = canonicalize_surface(text)
    tokens = re.findall(r"[a-z]+|N|[%$^()]|[+*/-]", normalized)
    features = list(tokens)
    features.extend(f"{a}_{b}" for a, b in zip(tokens, tokens[1:]))
    features.extend(f"{a}_{b}_{c}" for a, b, c in zip(tokens, tokens[1:], tokens[2:]))
    return features


def canonicalize_surface(text: str) -> str:
    normalized = text.lower()
    normalized = re.sub(r"\d+(?:/\d+)?(?:\.\d+)?", " N ", normalized)
    normalized = re.sub(r"\b\d+(?:st|nd|rd|th)\b", " N ", normalized)
    normalized = normalized.replace("\\", " ")
    normalized = re.sub(r"[^a-z0-9N%$^()+*/-]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def run_lift_lifter_experiment(seeds: int = 8) -> dict[str, Any]:
    examples = build_lift_lifter_examples(seeds=seeds)
    train = [example for example in examples if example.split == "dev"]
    calib = [example for example in examples if example.split == "calib"]
    test = [example for example in examples if example.split == "held_out"]

    model = SparseLiftCertificateLifter()
    model.fit(train)
    model.calibrate(calib)

    records = [evaluate_example(model, example) for example in examples]
    same_structure_pairs = evaluate_same_structure_pairs(model, examples, split_filter=None)
    negative_pairs = evaluate_negative_pairs(model, examples)
    result = {
        "objective": "learn problem_text -> LiftCertificate, not problem_text -> answer",
        "seeds": seeds,
        "counts": {
            "total": len(examples),
            "train_dev": len(train),
            "calib": len(calib),
            "held_out": len(test),
        },
        "model": model.to_dict(),
        "summary": summarize_lifter_records(records),
        "same_structure_pairs": same_structure_pairs,
        "negative_pairs": negative_pairs,
        "records": [asdict(record) for record in records],
    }
    result["seven_axis_summary"] = seven_axis_summary(result)
    return result


def evaluate_example(model: SparseLiftCertificateLifter, example: LiftLifterExample) -> LiftLifterRecord:
    prediction = model.predict(example.problem)
    predicted = prediction.certificate or {}
    gold = example.gold_certificate
    graph = compile_typed_semantic_graph(example.problem).to_dict()
    answer = None
    backend_executed = False
    backend_correct = False
    wrong = False
    if prediction.certificate is not None:
        graph["lift_certificates"] = [prediction.certificate]
        backend_result = solve_from_lift_certificates(graph)
        if backend_result is not None:
            backend_executed = True
            answer = str(backend_result.get("answer_exact"))
            backend_correct = answers_match(answer, example.expected)
            wrong = not backend_correct
    return LiftLifterRecord(
        case_id=example.case_id,
        split=example.split,
        transform=example.transform,
        gold_family_id=example.family_id,
        predicted_family_id=prediction.family_id,
        status=prediction.status,
        confidence=prediction.confidence,
        family_match=prediction.family_id == example.family_id,
        morphism_chain_match=list(predicted.get("morphism_chain") or []) == list(gold.get("morphism_chain") or []),
        constraint_skeleton_match=sorted(predicted.get("constraint_skeleton") or []) == sorted(gold.get("constraint_skeleton") or []),
        query_signature_match=str(predicted.get("query_signature") or "") == str(gold.get("query_signature") or ""),
        backend_contract_match=str(predicted.get("backend_contract") or "") == str(gold.get("backend_contract") or ""),
        backend_executed=backend_executed,
        backend_correct=backend_correct,
        wrong=wrong,
        rejected=prediction.status == "rejected",
        expected=example.expected,
        answer=answer,
        problem=example.problem,
    )


def evaluate_same_structure_pairs(
    model: SparseLiftCertificateLifter,
    examples: list[LiftLifterExample],
    *,
    split_filter: str | None,
) -> dict[str, Any]:
    cases = [
        GeneralizationCase(
            case_id=example.case_id,
            family_id=example.family_id,
            pair_group=":".join(example.case_id.split(":")[:2]),
            split=example.split,
            transform=example.transform,
            problem=example.problem,
            expected=example.expected,
            metadata={},
        )
        for example in examples
    ]
    pairs = generate_same_structure_pairs(cases)
    by_id = {example.case_id: example for example in examples}
    checks = []
    for pair in pairs:
        if split_filter and pair.split != split_filter:
            continue
        left = model.predict(by_id[pair.left_case_id].problem)
        right = model.predict(by_id[pair.right_case_id].problem)
        left_sig = (left.certificate or {}).get("canonical_signature")
        right_sig = (right.certificate or {}).get("canonical_signature")
        checks.append(
            {
                "pair_id": pair.pair_id,
                "split": pair.split,
                "transform": pair.transform,
                "matched": bool(left_sig and right_sig and left_sig == right_sig),
                "left_status": left.status,
                "right_status": right.status,
            }
        )
    matched = sum(item["matched"] for item in checks)
    return {
        "total": len(checks),
        "matched": matched,
        "match_rate": matched / len(checks) if checks else 0.0,
        "checks": checks,
    }


def evaluate_negative_pairs(model: SparseLiftCertificateLifter, examples: list[LiftLifterExample]) -> dict[str, Any]:
    by_seed_transform: dict[tuple[str, str], list[LiftLifterExample]] = defaultdict(list)
    for example in examples:
        parts = example.case_id.split(":")
        seed = parts[1] if len(parts) > 1 else "0"
        by_seed_transform[(seed, example.transform)].append(example)
    checks = []
    for (_seed, _transform), items in by_seed_transform.items():
        sorted_items = sorted(items, key=lambda item: item.family_id)
        for left, right in zip(sorted_items, sorted_items[1:]):
            if left.family_id == right.family_id:
                continue
            left_prediction = model.predict(left.problem)
            right_prediction = model.predict(right.problem)
            left_sig = (left_prediction.certificate or {}).get("canonical_signature")
            right_sig = (right_prediction.certificate or {}).get("canonical_signature")
            confused = bool(left_sig and right_sig and left_sig == right_sig)
            checks.append(
                {
                    "left_case_id": left.case_id,
                    "right_case_id": right.case_id,
                    "confused": confused,
                    "left_predicted": left_prediction.family_id,
                    "right_predicted": right_prediction.family_id,
                }
            )
    confused_count = sum(item["confused"] for item in checks)
    return {
        "total": len(checks),
        "confused": confused_count,
        "not_confused": len(checks) - confused_count,
        "confusion_rate": confused_count / len(checks) if checks else 0.0,
        "checks": checks,
    }


def summarize_lifter_records(records: list[LiftLifterRecord]) -> dict[str, Any]:
    return {
        "overall": summarize_record_subset(records),
        "by_split": summarize_by(records, "split"),
        "by_transform": summarize_by(records, "transform"),
        "by_family": summarize_by(records, "gold_family_id"),
    }


def summarize_by(records: list[LiftLifterRecord], attr: str) -> dict[str, Any]:
    grouped: dict[str, list[LiftLifterRecord]] = defaultdict(list)
    for record in records:
        grouped[str(getattr(record, attr))].append(record)
    return {key: summarize_record_subset(items) for key, items in sorted(grouped.items())}


def summarize_record_subset(records: list[LiftLifterRecord]) -> dict[str, Any]:
    total = len(records)
    return {
        "total": total,
        "family_id_match_rate": rate(records, "family_match"),
        "morphism_chain_match_rate": rate(records, "morphism_chain_match"),
        "constraint_skeleton_match_rate": rate(records, "constraint_skeleton_match"),
        "query_signature_match_rate": rate(records, "query_signature_match"),
        "backend_contract_match_rate": rate(records, "backend_contract_match"),
        "backend_execution_rate": rate(records, "backend_executed"),
        "backend_success_rate": rate(records, "backend_correct"),
        "wrong_rate": rate(records, "wrong"),
        "rejection_rate": rate(records, "rejected"),
    }


def rate(records: list[LiftLifterRecord], attr: str) -> float:
    return sum(bool(getattr(record, attr)) for record in records) / len(records) if records else 0.0


def seven_axis_summary(result: dict[str, Any]) -> dict[str, Any]:
    overall = result["summary"]["overall"]
    held_out = result["summary"]["by_split"].get("held_out", {})
    return {
        "1_family_id": held_out.get("family_id_match_rate", 0.0),
        "2_morphism_chain": held_out.get("morphism_chain_match_rate", 0.0),
        "3_constraint_skeleton": held_out.get("constraint_skeleton_match_rate", 0.0),
        "4_query_signature": held_out.get("query_signature_match_rate", 0.0),
        "5_backend_execution_success": held_out.get("backend_success_rate", 0.0),
        "6_surface_numeric_same_structure": result["same_structure_pairs"]["match_rate"],
        "7_negative_structure_not_confused": 1.0 - result["negative_pairs"]["confusion_rate"],
        "overall_backend_success": overall.get("backend_success_rate", 0.0),
    }


def write_outputs(result: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    with output.with_suffix(".jsonl").open("w", encoding="utf-8") as handle:
        for record in result["records"]:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    report = render_markdown_report(result, output)
    output.with_name(output.stem + "_report.md").write_text(report, encoding="utf-8")


def render_markdown_report(result: dict[str, Any], output: Path) -> str:
    lines = [
        "# LiftCertificate Lifter Experiment",
        "",
        "## Objective",
        "",
        result["objective"],
        "",
        "## Counts",
        "",
        f"- total: {result['counts']['total']}",
        f"- train/dev: {result['counts']['train_dev']}",
        f"- calib: {result['counts']['calib']}",
        f"- held_out: {result['counts']['held_out']}",
        "",
        "## Seven-Axis Held-Out Summary",
        "",
        "| axis | score |",
        "|---|---:|",
    ]
    for key, value in result["seven_axis_summary"].items():
        lines.append(f"| `{key}` | {value:.3f} |")
    lines.extend(
        [
            "",
            "## Split Summary",
            "",
            "| split | family | morphism | constraint | query | backend contract | backend success | wrong | rejected |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for split, summary in result["summary"]["by_split"].items():
        lines.append(
            "| {split} | {family:.3f} | {morphism:.3f} | {constraint:.3f} | {query:.3f} | {contract:.3f} | {backend:.3f} | {wrong:.3f} | {rejected:.3f} |".format(
                split=split,
                family=summary["family_id_match_rate"],
                morphism=summary["morphism_chain_match_rate"],
                constraint=summary["constraint_skeleton_match_rate"],
                query=summary["query_signature_match_rate"],
                contract=summary["backend_contract_match_rate"],
                backend=summary["backend_success_rate"],
                wrong=summary["wrong_rate"],
                rejected=summary["rejection_rate"],
            )
        )
    lines.extend(
        [
            "",
            "## Pair Tests",
            "",
            f"- same-structure pairs: {result['same_structure_pairs']['matched']}/{result['same_structure_pairs']['total']}",
            f"- negative pair confusion: {result['negative_pairs']['confused']}/{result['negative_pairs']['total']}",
            "",
            "## Files",
            "",
            f"- json: `{output}`",
            f"- jsonl: `{output.with_suffix('.jsonl')}`",
            f"- report: `{output.with_name(output.stem + '_report.md')}`",
        ]
    )
    return "\n".join(lines) + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Train and evaluate a LiftCertificate lifter.")
    parser.add_argument("--seeds", type=int, default=8)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    result = run_lift_lifter_experiment(seeds=args.seeds)
    write_outputs(result, args.output)
    print(json.dumps({"counts": result["counts"], "seven_axis_summary": result["seven_axis_summary"]}, ensure_ascii=False, indent=2))
    print(f"json: {args.output}")
    print(f"jsonl: {args.output.with_suffix('.jsonl')}")
    print(f"report: {args.output.with_name(args.output.stem + '_report.md')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
