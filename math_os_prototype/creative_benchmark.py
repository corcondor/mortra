"""MathOS-CreativeBench v0.

This benchmark evaluates mathematical problem posing without treating solver
failure as creativity by itself.  Machine-verifiable evidence and human
judgments are kept separate.  A creative composite is intentionally omitted
until blind human ratings are available.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from statistics import mean
from typing import Any, Iterable


DEFAULT_MATHOS_REPORT = Path(
    "C:/Users/81808/.openclaw/workspace/math_os_prototype/problem_synthesis/geometry_sweep_repair1.json"
)
DEFAULT_OUTPUT = Path(
    "C:/Users/81808/.openclaw/workspace/math_os_prototype/problem_synthesis/creative_benchmark_v0.json"
)
ALLOWED_RIGHTS_BASES = {
    "self_authored",
    "permission",
    "licensed",
    "public_domain",
    "research_excerpt",
}
RATING_FIELDS = ("naturalness", "elegance", "surprise", "pedagogical_value")


@dataclass(frozen=True)
class CreativeProblemRecord:
    record_id: str
    source_kind: str
    author_system: str
    domain: str
    task: str
    statement_tex: str
    answer: str | None = None
    solution: str | None = None
    family_id: str | None = None
    strategy: str | None = None
    proof_obligations: list[str] = field(default_factory=list)
    normal_form: str | None = None
    verification: dict[str, Any] = field(default_factory=dict)
    generation_trace: list[dict[str, Any]] = field(default_factory=list)
    difficulty: dict[str, Any] = field(default_factory=dict)
    rights_basis: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["structural_signature"] = structural_signature(self)
        return data


@dataclass(frozen=True)
class HumanRating:
    problem_id: str
    rater_id: str
    rater_group: str
    naturalness: float
    elegance: float
    surprise: float
    pedagogical_value: float
    source_guess: str | None = None
    source_confidence: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_mathos_report(path: Path) -> list[CreativeProblemRecord]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    family = payload.get("family") or {}
    family_id = str(family.get("name") or path.stem)
    trace_by_dsl: dict[str, dict[str, Any]] = {}
    for trace in payload.get("traces", []) or []:
        final = trace.get("final") or {}
        dsl = str((final.get("params") or {}).get("dsl") or "")
        if dsl:
            trace_by_dsl[dsl] = trace

    records: list[CreativeProblemRecord] = []
    for index, item in enumerate(payload.get("curriculum_items", []) or [], start=1):
        dsl = str(item.get("dsl") or "")
        trace = trace_by_dsl.get(dsl, {})
        final = trace.get("final") or {}
        difficulty = dict(final.get("difficulty") or item.get("difficulty") or {})
        normal = item.get("normal_form") or {}
        parse_status = str(normal.get("parse_status") or "")
        item_verification = dict(item.get("verification") or {})
        verified = (
            bool(item.get("expected_answer"))
            and parse_status == "ok"
            and item_verification.get("status", "verified") == "verified"
        )
        domain = infer_domain(item)
        task = str(item.get("task") or "unknown")
        item_family_id = str(item.get("family_id") or family_id)
        records.append(
            CreativeProblemRecord(
                record_id=f"mathos:{path.stem}:{index:04d}",
                source_kind="system",
                author_system="MathOS",
                domain=domain,
                task=task,
                statement_tex=str(item.get("input_tex") or ""),
                answer=str(item.get("expected_answer") or "") or None,
                family_id=item_family_id,
                strategy=str(item.get("strategy") or "") or None,
                proof_obligations=[str(value) for value in item.get("proof_obligations", []) or []],
                normal_form=str(normal.get("normal_form") or "") or None,
                verification={
                    "status": "verified" if verified else "unverified",
                    "method": "algebraic_normal_form",
                    "parse_status": parse_status,
                },
                generation_trace=list(trace.get("steps") or []),
                difficulty=difficulty,
                rights_basis="self_authored",
                metadata={
                    "source_report": str(path),
                    "dsl": dsl,
                    "match_group": str(
                        item.get("match_group") or mathos_match_group(domain, task)
                    ),
                    "lift_certificate": item.get("lift_certificate"),
                    "backend_trace": item.get("backend_trace"),
                },
            )
        )
    return records


def load_human_jsonl(path: Path, *, require_rights: bool = True) -> list[CreativeProblemRecord]:
    records: list[CreativeProblemRecord] = []
    for line_number, row in enumerate(read_jsonl(path), start=1):
        rights_basis = str(row.get("rights_basis") or "") or None
        if require_rights and rights_basis not in ALLOWED_RIGHTS_BASES:
            raise ValueError(
                f"{path}:{line_number}: rights_basis must be one of {sorted(ALLOWED_RIGHTS_BASES)}"
            )
        record_id = str(row.get("record_id") or row.get("id") or "")
        statement = str(row.get("statement_tex") or row.get("problem_tex") or "")
        if not record_id or not statement:
            raise ValueError(f"{path}:{line_number}: record_id and statement_tex are required")
        records.append(
            CreativeProblemRecord(
                record_id=record_id,
                source_kind="human",
                author_system=str(row.get("author_system") or "human"),
                domain=str(row.get("domain") or "unknown"),
                task=str(row.get("task") or "unknown"),
                statement_tex=statement,
                answer=_optional_text(row.get("answer")),
                solution=_optional_text(row.get("solution")),
                family_id=_optional_text(row.get("family_id")),
                strategy=_optional_text(row.get("strategy")),
                proof_obligations=[str(value) for value in row.get("proof_obligations", []) or []],
                normal_form=_optional_text(row.get("normal_form")),
                verification=dict(row.get("verification") or {}),
                generation_trace=list(row.get("generation_trace") or []),
                difficulty=dict(row.get("difficulty") or {}),
                rights_basis=rights_basis,
                metadata=dict(row.get("metadata") or {}),
            )
        )
    return records


def load_ratings_jsonl(path: Path) -> list[HumanRating]:
    ratings: list[HumanRating] = []
    for line_number, row in enumerate(read_jsonl(path), start=1):
        values = {name: float(row[name]) for name in RATING_FIELDS}
        if any(value < 1 or value > 5 for value in values.values()):
            raise ValueError(f"{path}:{line_number}: ratings must be in [1,5]")
        ratings.append(
            HumanRating(
                problem_id=str(row["problem_id"]),
                rater_id=sha256(str(row["rater_id"]).encode("utf-8")).hexdigest()[:16],
                rater_group=str(row.get("rater_group") or "unspecified"),
                source_guess=_optional_text(row.get("source_guess")),
                source_confidence=float(row["source_confidence"])
                if row.get("source_confidence") is not None
                else None,
                **values,
            )
        )
    return ratings


def build_creative_benchmark(
    records: list[CreativeProblemRecord],
    *,
    ratings: list[HumanRating] | None = None,
    seed: int = 20260722,
    expected_human_count: int | None = None,
    expected_system_count: int | None = None,
) -> dict[str, Any]:
    ensure_unique_ids(records)
    ratings = ratings or []
    rating_aggregates = aggregate_ratings(ratings)
    human_records = [record for record in records if record.source_kind == "human"]
    system_records = [record for record in records if record.source_kind == "system"]
    scored_records = [
        score_record(record, human_references=human_records, ratings=rating_aggregates.get(record.record_id))
        for record in records
    ]
    blind = build_blind_pairs(human_records, system_records, seed=seed)
    source_summary = summarize_sources(scored_records)
    dataset_completeness = human_dataset_completeness(
        observed=len(human_records),
        expected=expected_human_count,
    )
    system_dataset_completeness = human_dataset_completeness(
        observed=len(system_records),
        expected=expected_system_count,
    )
    limitations = [
        "Structural novelty is corpus-relative and cannot prove historical originality.",
        "Feature correlations with discomfort are descriptive, not causal; intervention studies are required.",
    ]
    if not human_records:
        limitations.insert(
            0,
            "No human-vs-system conclusion is valid until rights-cleared human records are loaded.",
        )
    if not ratings:
        limitations.append(
            "No single creativity score is emitted without blind human ratings."
        )
    return {
        "benchmark": "MathOS-CreativeBench",
        "version": "0.2.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "principles": {
            "validity_is_gate": True,
            "solver_failure_is_not_creativity": True,
            "machine_and_human_evidence_are_separate": True,
            "creative_composite_available": bool(ratings),
        },
        "summary": {
            "records": len(records),
            "human_records": len(human_records),
            "system_records": len(system_records),
            "ratings": len(ratings),
            "blind_pairs": len(blind["public_pairs"]),
            "sources": source_summary,
            "human_dataset_completeness": dataset_completeness,
            "system_dataset_completeness": system_dataset_completeness,
            "pairing_coverage": pairing_coverage(human_records, system_records),
        },
        "records": scored_records,
        "blind_pairs": blind["public_pairs"],
        "blind_pair_key": blind["private_key"],
        "rating_aggregates": rating_aggregates,
        "discomfort_analysis": analyze_discomfort_drivers(scored_records, rating_aggregates),
        "limitations": limitations,
    }


def score_record(
    record: CreativeProblemRecord,
    *,
    human_references: list[CreativeProblemRecord],
    ratings: dict[str, Any] | None,
) -> dict[str, Any]:
    features = objective_features(record)
    validity_status = normalize_verification_status(record.verification.get("status"))
    validity = {
        "valid": True,
        "invalid": False,
        "unknown": None,
    }[validity_status]
    structural_novelty = novelty_against(record, human_references, structural=True)
    surface_novelty = novelty_against(record, human_references, structural=False)
    evidence = {
        "validity_gate": validity,
        "validity_status": validity_status,
        "structural_novelty_against_human": structural_novelty,
        "surface_novelty_against_human": surface_novelty,
        "condition_necessity": record.metadata.get("condition_ablation"),
        "difficulty": record.difficulty or None,
        "repair_trace_available": bool(record.generation_trace),
        "human_ratings": ratings,
    }
    creative_composite = None
    if validity is True and ratings:
        human_mean = mean(float(ratings[name]) for name in RATING_FIELDS)
        novelty = structural_novelty if structural_novelty is not None else 0.0
        creative_composite = round(20.0 * human_mean * (0.5 + 0.5 * novelty), 3)
    return {
        "problem": record.to_dict(),
        "objective_features": features,
        "evidence": evidence,
        "creative_composite": creative_composite,
        "score_coverage": {
            "machine": round(sum(value is not None for value in evidence.values()) / len(evidence), 3),
            "human": 1.0 if ratings else 0.0,
        },
    }


def objective_features(record: CreativeProblemRecord) -> dict[str, Any]:
    text = record.statement_tex
    numeric_literals = re.findall(r"(?<![A-Za-z])[-+]?\d+(?:/\d+)?", text)
    subproblem_markers = re.findall(r"(?:\(\d+\)|（\d+）)", text)
    condition_markers = re.findall(
        r"(?:とする|満たす|ただし|subject to|where|assume|for every|存在)",
        text,
        flags=re.IGNORECASE,
    )
    return {
        "statement_characters": len(text),
        "math_atom_count": len(re.findall(r"[A-Za-z]+|\\[A-Za-z]+|\d+", text)),
        "numeric_literal_count": len(numeric_literals),
        "subproblem_count": len(subproblem_markers),
        "condition_marker_count": len(condition_markers),
        "proof_obligation_count": len(record.proof_obligations),
        "repair_step_count": len(record.generation_trace),
        "structural_signature": structural_signature(record),
        "structure_certified": structure_is_certified(record),
    }


def structural_signature(record: CreativeProblemRecord) -> str:
    payload = "|".join(
        [
            record.domain,
            record.family_id or "family:unknown",
            record.task,
            record.strategy or "strategy:unknown",
            *sorted(canonical_tokens(" ".join(record.proof_obligations))),
        ]
    )
    return sha256(payload.encode("utf-8")).hexdigest()[:20]


def novelty_against(
    record: CreativeProblemRecord,
    references: list[CreativeProblemRecord],
    *,
    structural: bool,
) -> float | None:
    candidates = [reference for reference in references if reference.record_id != record.record_id]
    if structural:
        if not structure_is_certified(record):
            return None
        candidates = [reference for reference in candidates if structure_is_certified(reference)]
    if not candidates:
        return None
    if structural:
        source = structural_tokens(record)
        similarities = [jaccard(source, structural_tokens(reference)) for reference in candidates]
    else:
        source = character_ngrams(record.statement_tex)
        similarities = [jaccard(source, character_ngrams(reference.statement_tex)) for reference in candidates]
    return round(1.0 - max(similarities, default=0.0), 4)


def structural_tokens(record: CreativeProblemRecord) -> set[str]:
    return set(
        canonical_tokens(
            " ".join(
                [
                    record.domain,
                    record.family_id or "",
                    record.task,
                    record.strategy or "",
                    *record.proof_obligations,
                ]
            )
        )
    )


def structure_is_certified(record: CreativeProblemRecord) -> bool:
    if record.source_kind == "system":
        return (
            record.verification.get("status") == "verified"
            and bool(record.family_id)
            and bool(record.normal_form)
        )
    if record.metadata.get("structure_certified") is True:
        return True
    return bool(record.metadata.get("lift_certificates"))


def canonical_tokens(text: str) -> list[str]:
    normalized = re.sub(r"-?\d+(?:\.\d+)?(?:/\d+)?", " CONST ", text.lower())
    normalized = re.sub(r"\b[a-z]\b", " VAR ", normalized)
    return re.findall(r"[a-z_]+|[\u3040-\u30ff\u3400-\u9fff]+", normalized)


def character_ngrams(text: str, n: int = 3) -> set[str]:
    compact = re.sub(r"\s+", "", text.lower())
    compact = re.sub(r"\d+", "#", compact)
    return {compact[index : index + n] for index in range(max(0, len(compact) - n + 1))}


def build_blind_pairs(
    human_records: list[CreativeProblemRecord],
    system_records: list[CreativeProblemRecord],
    *,
    seed: int,
) -> dict[str, list[dict[str, Any]]]:
    rng = random.Random(seed)
    available = list(human_records)
    public_pairs: list[dict[str, Any]] = []
    private_key: list[dict[str, Any]] = []
    for system in sorted(system_records, key=lambda item: item.record_id):
        matches = [
            human
            for human in available
            if blind_match_group(human) == blind_match_group(system)
        ]
        if not matches:
            continue
        human = min(matches, key=lambda item: difficulty_distance(system, item))
        available.remove(human)
        left, right = (human, system) if rng.random() < 0.5 else (system, human)
        pair_id = sha256(f"{seed}:{human.record_id}:{system.record_id}".encode("utf-8")).hexdigest()[:16]
        public_pairs.append(
            {
                "pair_id": pair_id,
                "domain": system.domain,
                "task": system.task,
                "match_group": blind_match_group(system),
                "problem_a": left.statement_tex,
                "problem_b": right.statement_tex,
                "rating_fields": list(RATING_FIELDS) + ["overall_preference", "source_guess"],
            }
        )
        private_key.append(
            {
                "pair_id": pair_id,
                "problem_a_id": left.record_id,
                "problem_a_source": left.source_kind,
                "problem_b_id": right.record_id,
                "problem_b_source": right.source_kind,
            }
        )
    return {"public_pairs": public_pairs, "private_key": private_key}


def pairing_coverage(
    human_records: list[CreativeProblemRecord],
    system_records: list[CreativeProblemRecord],
) -> dict[str, Any]:
    human = Counter(blind_match_group(record) for record in human_records)
    system = Counter(blind_match_group(record) for record in system_records)
    shared = sorted(set(human) & set(system))
    potential_pairs = sum(min(human[group], system[group]) for group in shared)
    return {
        "human_match_groups": dict(sorted(human.items())),
        "system_match_groups": dict(sorted(system.items())),
        "shared_match_groups": shared,
        "potential_pairs": potential_pairs,
        "human_records_without_match": len(human_records) - potential_pairs,
        "system_records_without_match": len(system_records) - potential_pairs,
        "human_only_groups": sorted(set(human) - set(system)),
        "system_only_groups": sorted(set(system) - set(human)),
    }


def aggregate_ratings(ratings: list[HumanRating]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[HumanRating]] = defaultdict(list)
    for rating in ratings:
        grouped[rating.problem_id].append(rating)
    output: dict[str, dict[str, Any]] = {}
    for problem_id, rows in grouped.items():
        output[problem_id] = {
            "count": len(rows),
            **{name: round(mean(getattr(row, name) for row in rows), 3) for name in RATING_FIELDS},
            "source_guess_human_rate": round(
                sum(row.source_guess == "human" for row in rows if row.source_guess) /
                max(1, sum(bool(row.source_guess) for row in rows)),
                3,
            ),
        }
    return output


def analyze_discomfort_drivers(
    scored_records: list[dict[str, Any]],
    ratings: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    rows = []
    for scored in scored_records:
        problem_id = scored["problem"]["record_id"]
        rating = ratings.get(problem_id)
        if not rating:
            continue
        rows.append((scored["objective_features"], 6.0 - float(rating["naturalness"])))
    if len(rows) < 5:
        return {
            "status": "insufficient_ratings",
            "rated_problems": len(rows),
            "minimum_required": 5,
            "note": "Correlations are descriptive; controlled ablations are required for causal claims.",
        }
    feature_names = (
        "statement_characters",
        "math_atom_count",
        "numeric_literal_count",
        "subproblem_count",
        "condition_marker_count",
        "proof_obligation_count",
        "repair_step_count",
    )
    discomfort = [value for _, value in rows]
    correlations = []
    for name in feature_names:
        values = [float(features[name]) for features, _ in rows]
        correlation = pearson(values, discomfort)
        if correlation is not None:
            correlations.append({"feature": name, "pearson_r": round(correlation, 4)})
    correlations.sort(key=lambda item: abs(item["pearson_r"]), reverse=True)
    return {
        "status": "descriptive_only",
        "rated_problems": len(rows),
        "correlations": correlations,
        "note": "Run matched interventions before interpreting a feature as a cause of discomfort.",
    }


def summarize_sources(scored_records: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for scored in scored_records:
        grouped[scored["problem"]["source_kind"]].append(scored)
    summary = {}
    for source, rows in grouped.items():
        status_counts = Counter(row["evidence"]["validity_status"] for row in rows)
        valid = status_counts["valid"]
        invalid = status_counts["invalid"]
        unknown = status_counts["unknown"]
        adjudicated = valid + invalid
        signatures = {row["objective_features"]["structural_signature"] for row in rows}
        certified_rows = [row for row in rows if row["objective_features"]["structure_certified"]]
        certified_signatures = {
            row["objective_features"]["structural_signature"] for row in certified_rows
        }
        summary[source] = {
            "count": len(rows),
            "valid": valid,
            "invalid": invalid,
            "unknown": unknown,
            "adjudicated": adjudicated,
            "validity_rate": round(valid / adjudicated, 4) if adjudicated else None,
            "unique_structural_signatures": len(signatures),
            "structural_signature_ratio": round(len(signatures) / len(rows), 4) if rows else 0.0,
            "structural_signature_counts": dict(
                Counter(row["objective_features"]["structural_signature"] for row in rows)
            ),
            "certified_structure_count": len(certified_rows),
            "uncertified_structure_count": len(rows) - len(certified_rows),
            "unique_certified_structural_signatures": len(certified_signatures),
            "certified_structural_signature_ratio": (
                round(len(certified_signatures) / len(certified_rows), 4)
                if certified_rows
                else None
            ),
            "mean_statement_characters": round(
                mean(row["objective_features"]["statement_characters"] for row in rows), 3
            ),
        }
    return summary


def normalize_verification_status(value: Any) -> str:
    status = str(value or "").strip().lower()
    if status in {"verified", "valid", "passed", "pass"}:
        return "valid"
    if status in {"invalid", "failed", "fail", "rejected"}:
        return "invalid"
    return "unknown"


def human_dataset_completeness(*, observed: int, expected: int | None) -> dict[str, Any]:
    if expected is None:
        return {
            "expected": None,
            "observed": observed,
            "missing": None,
            "excess": None,
            "complete": None,
        }
    if expected < 0:
        raise ValueError("expected_human_count must be non-negative")
    return {
        "expected": expected,
        "observed": observed,
        "missing": max(0, expected - observed),
        "excess": max(0, observed - expected),
        "complete": observed == expected,
    }


def difficulty_distance(left: CreativeProblemRecord, right: CreativeProblemRecord) -> float:
    return abs(difficulty_value(left) - difficulty_value(right))


def blind_match_group(record: CreativeProblemRecord) -> str:
    explicit = str(record.metadata.get("match_group") or "").strip()
    return explicit or f"{record.domain}:{record.task}"


def mathos_match_group(domain: str, task: str) -> str:
    if domain == "geometry" and task == "region":
        return "geometry:2d:region"
    if domain == "geometry" and task == "envelope":
        return "geometry:2d:curve"
    if domain == "geometry" and task == "locus":
        return "geometry:2d:curve"
    return f"{domain}:{task}"


def difficulty_value(record: CreativeProblemRecord) -> float:
    if record.difficulty.get("raw") is not None:
        return float(record.difficulty["raw"])
    levels = {"d": 1.0, "c": 2.0, "b": 3.0, "a": 4.0, "s": 5.0, "easy": 1.0, "medium": 2.5, "hard": 4.0}
    return levels.get(str(record.difficulty.get("level") or "").lower(), 0.0)


def pearson(left: list[float], right: list[float]) -> float | None:
    if len(left) != len(right) or len(left) < 2:
        return None
    left_mean = mean(left)
    right_mean = mean(right)
    numerator = sum((x - left_mean) * (y - right_mean) for x, y in zip(left, right))
    left_scale = math.sqrt(sum((x - left_mean) ** 2 for x in left))
    right_scale = math.sqrt(sum((y - right_mean) ** 2 for y in right))
    if left_scale == 0 or right_scale == 0:
        return None
    return numerator / (left_scale * right_scale)


def jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    return len(left & right) / max(1, len(left | right))


def ensure_unique_ids(records: Iterable[CreativeProblemRecord]) -> None:
    ids = [record.record_id for record in records]
    duplicates = [record_id for record_id, count in Counter(ids).items() if count > 1]
    if duplicates:
        raise ValueError(f"duplicate record IDs: {duplicates}")


def infer_domain(item: dict[str, Any]) -> str:
    source = str(item.get("source") or "")
    if "geometry" in source or item.get("task") in {"region", "envelope", "locus"}:
        return "geometry"
    return str(item.get("domain") or "unknown")


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            yield json.loads(line)


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    completeness = summary["human_dataset_completeness"]
    system_completeness = summary["system_dataset_completeness"]
    pairing = summary["pairing_coverage"]
    lines = [
        f"# MathOS-CreativeBench v{report['version']}",
        "",
        f"Generated: {report['generated_at']}",
        "",
        "## Coverage",
        "",
        f"- records: {summary['records']}",
        f"- human records: {summary['human_records']}",
        f"- system records: {summary['system_records']}",
        f"- blind pairs: {summary['blind_pairs']}",
        f"- human ratings: {summary['ratings']}",
        (
            "- human dataset target: not fixed"
            if completeness["expected"] is None
            else f"- human dataset target: {completeness['observed']}/{completeness['expected']} "
            f"(complete={str(completeness['complete']).lower()})"
        ),
        (
            "- system dataset target: not fixed"
            if system_completeness["expected"] is None
            else f"- system dataset target: {system_completeness['observed']}/"
            f"{system_completeness['expected']} "
            f"(complete={str(system_completeness['complete']).lower()})"
        ),
        f"- structurally eligible blind pairs: {pairing['potential_pairs']}",
        "",
        "## Source Summary",
        "",
    ]
    for source, values in sorted(summary["sources"].items()):
        validity_rate = values["validity_rate"]
        validity_text = "n/a" if validity_rate is None else f"{validity_rate:.3f}"
        lines.extend(
            [
                f"### {source}",
                "",
                (
                    f"- validity: valid={values['valid']}, invalid={values['invalid']}, "
                    f"unknown={values['unknown']}, adjudicated rate={validity_text}"
                ),
                f"- structural signatures: {values['unique_structural_signatures']}/{values['count']}",
                (
                    f"- certified structures: {values['certified_structure_count']}/{values['count']}; "
                    f"unique certified signatures={values['unique_certified_structural_signatures']}"
                ),
                f"- provisional/unlifted structures: {values['uncertified_structure_count']}",
                f"- signature counts: {json.dumps(values['structural_signature_counts'], sort_keys=True)}",
                f"- mean statement characters: {values['mean_statement_characters']}",
                "",
            ]
        )
    lines.extend(
        [
            "## Pairing Coverage",
            "",
            f"- shared match groups: {len(pairing['shared_match_groups'])}",
            f"- human records without an eligible system match: {pairing['human_records_without_match']}",
            f"- system records without an eligible human match: {pairing['system_records_without_match']}",
            f"- human-only groups: {json.dumps(pairing['human_only_groups'], ensure_ascii=False)}",
            f"- system-only groups: {json.dumps(pairing['system_only_groups'], ensure_ascii=False)}",
            "",
            "## Interpretation",
            "",
            "Validity, structural diversity, and process evidence are machine-measured.",
            "Elegance, surprise, pedagogical value, and felt naturalness require blind human ratings.",
            "No human-vs-system conclusion or creativity composite is reported without those ratings.",
            "",
            "## Limitations",
            "",
        ]
    )
    lines.extend(f"- {value}" for value in report["limitations"])
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run MathOS-CreativeBench v0.")
    parser.add_argument("--mathos-report", action="append", type=Path, default=[])
    parser.add_argument("--human-jsonl", type=Path)
    parser.add_argument("--ratings-jsonl", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--seed", type=int, default=20260722)
    parser.add_argument("--expected-human-count", type=int)
    parser.add_argument("--expected-system-count", type=int)
    parser.add_argument(
        "--require-complete-human-set",
        action="store_true",
        help="Write the report but exit with status 2 when the human set is incomplete.",
    )
    parser.add_argument(
        "--require-complete-system-set",
        action="store_true",
        help="Write the report but exit with status 2 when the system set is incomplete.",
    )
    args = parser.parse_args()

    report_paths = args.mathos_report or [DEFAULT_MATHOS_REPORT]
    records = [record for path in report_paths for record in load_mathos_report(path)]
    if args.human_jsonl:
        records.extend(load_human_jsonl(args.human_jsonl))
    ratings = load_ratings_jsonl(args.ratings_jsonl) if args.ratings_jsonl else []
    report = build_creative_benchmark(
        records,
        ratings=ratings,
        seed=args.seed,
        expected_human_count=args.expected_human_count,
        expected_system_count=args.expected_system_count,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path = args.output.with_suffix(".md")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    public_pairs_path = args.output.with_name(f"{args.output.stem}_blind_pairs.json")
    public_pairs_path.write_text(
        json.dumps(report["blind_pairs"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "markdown": str(markdown_path),
                "blind_pairs": str(public_pairs_path),
                "summary": report["summary"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if args.require_complete_human_set:
        complete = report["summary"]["human_dataset_completeness"]["complete"]
        if complete is not True:
            return 2
    if args.require_complete_system_set:
        complete = report["summary"]["system_dataset_completeness"]["complete"]
        if complete is not True:
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
