"""再現用の補助構成探索artifactとYuclid証明を監査する。"""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path


def _path_key(record: dict[str, object]) -> list[str]:
    rows: list[str] = []
    for step in record["steps"]:
        rows.append(
            f"{step['family']}({','.join(step['inputs'])})->{step['output']}"
        )
    return rows


def _read_json(path: Path) -> dict[str, object]:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            return json.load(handle)
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _proof_path(artifact: Path) -> Path:
    if artifact.name.endswith(".json.gz"):
        return artifact.with_name(artifact.name[: -len(".json.gz")] + ".proof.json.gz")
    return artifact.with_suffix(".proof.json")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()
    report = _read_json(args.artifact)
    protocol = report["protocol"]
    records = report["records"]
    checks: dict[str, bool] = {
        "no_external_llm": protocol["uses_external_llm"] is False,
        "no_dataset_auxiliary_clauses": protocol[
            "uses_dataset_auxiliary_clauses"
        ]
        is False,
        "no_problem_id_in_search": protocol["uses_problem_id_in_search"] is False,
        "baseline_unsolved": report["baseline"]["solved"] is False,
        "evaluated_path_count": report["evaluated_paths"] == len(records),
        "error_count": report["error_count"]
        == sum(record["error"] is not None for record in records),
    }
    if report["solved"]:
        solved_path = report["solved_path"]
        checks["solved_record_exists"] = any(
            record["solved"] and _path_key(record) == solved_path
            for record in records
        )
        confirmation = report.get("confirmation", {})
        checks["confirmation_solved"] = (
            confirmation.get("solved") is True
            and confirmation.get("status") == "solved"
            and confirmation.get("goal_deduction_count", 0) > 0
        )
        proof = _read_json(_proof_path(args.artifact))
        checks["proof_json_solved"] = (
            proof.get("status") == "solved"
            and len(proof.get("deductions_for_goal", []))
            == confirmation.get("goal_deduction_count")
        )
    else:
        checks["no_false_confirmation"] = report.get("confirmation") is None
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    if not all(checks.values()):
        return 1
    print("Newclid construction-stalk artifact verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
