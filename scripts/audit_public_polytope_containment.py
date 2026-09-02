from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from time import perf_counter

import sympy as sp

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.solve import solve_public_problem

UNIT_MAXIMUM = sp.sqrt(6) / (sp.sqrt(6) + 2 * sp.sqrt(2) + 3)

CASES = (
    {
        "id": "production_wording_unit_edge",
        "statement": "一辺が1である正四面体に完全に含むことができる立方体の一辺の大きさの最大値を求めよ。",
        "edge": sp.Integer(1),
        "expected_status": 200,
    },
    {
        "id": "unseen_wording_edge_two",
        "statement": "一辺の長さが2の正四面体の内部に収まる立方体の一辺の最大値を求めよ。",
        "edge": sp.Integer(2),
        "expected_status": 200,
    },
    {
        "id": "unseen_tex_fraction_edge",
        "statement": r"一辺が$\frac{7}{3}$である正四面体の中に入る立方体の辺長の最大値を求めよ。",
        "edge": sp.Rational(7, 3),
        "expected_status": 200,
    },
    {
        "id": "unseen_decimal_edge",
        "statement": "1辺が1.5の正四面体の内部に入る立方体の辺長の最大値を求めよ。",
        "edge": sp.Rational(3, 2),
        "expected_status": 200,
    },
    {
        "id": "reject_nonpositive_edge",
        "statement": "一辺が-1である正四面体の中に入る立方体の辺長の最大値を求めよ。",
        "expected_status": 422,
    },
    {
        "id": "reject_missing_edge",
        "statement": "正四面体の中に入る立方体の辺長の最大値を求めよ。",
        "expected_status": 422,
    },
)


def _audit_case(case: dict[str, object]) -> dict[str, object]:
    started = perf_counter()
    status, payload = solve_public_problem(str(case["statement"]))
    elapsed_ms = round((perf_counter() - started) * 1000, 3)
    record: dict[str, object] = {
        "id": case["id"],
        "statement": case["statement"],
        "status": status,
        "expected_status": case["expected_status"],
        "elapsed_ms": elapsed_ms,
        "status_matches": status == case["expected_status"],
    }
    if status != 200:
        record["error"] = payload.get("error")
        record["passed"] = record["status_matches"]
        return record

    card = payload["cards"][0]
    certificate = card["execution_certificate"]
    witness = certificate["witness"]
    dependency = witness["trusted_theorem_dependencies"][0]
    actual = sp.sympify(witness["maximum_side"])
    expected = sp.sympify(case["edge"]) * UNIT_MAXIMUM
    exact_residual = sp.simplify(actual - expected)
    encoded = json.dumps(card, ensure_ascii=False, sort_keys=True, default=str)
    checks = {
        "exact_answer": exact_residual == 0,
        "cold_contract": certificate.get("cold_generalization_validated") is True,
        "current_input_bound": certificate.get("registered_completed_route_used")
        is False,
        "published_theorem_dependency": dependency.get("registry_integrity_valid")
        is True,
        "diagram_present": "tikzpicture" in str(card.get("diagram_tikz") or ""),
        "solution_present": len(str(card.get("solution_tex") or "")) > 200,
        "no_replacement_character": "\ufffd" not in encoded,
        "no_external_llm": payload.get("uses_external_llm") is False,
    }
    record.update(
        {
            "answer_tex": card["answer_tex"],
            "answer_exact": sp.sstr(actual),
            "expected_exact": sp.sstr(expected),
            "exact_residual": sp.sstr(exact_residual),
            "theorem_id": dependency["theorem_id"],
            "registry_record_sha256": dependency["registry_record_sha256"],
            "statement_sha256": certificate["statement_sha256"],
            "answer_tex_sha256": certificate["answer_tex_sha256"],
            "checks": checks,
            "passed": bool(record["status_matches"] and all(checks.values())),
        }
    )
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT
        / "artifacts"
        / "test-results"
        / "public-polytope-containment-20260902"
        / "report.json",
    )
    args = parser.parse_args()

    records = [_audit_case(case) for case in CASES]
    passed = sum(record["passed"] is True for record in records)
    report = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "public single-problem API; four valid current inputs and two rejection controls",
        "uses_external_llm": False,
        "case_count": len(records),
        "passed_count": passed,
        "all_passed": passed == len(records),
        "cases": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {key: report[key] for key in ("case_count", "passed_count", "all_passed")}
        )
    )
    print(args.output)
    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
