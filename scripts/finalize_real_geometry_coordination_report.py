"""Consolidate raw real-agent runs and recompute typed exchange acceptance."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from newclid.jgex.formulation import JGEXFormulation, jgex_formulation_from_txt_file

from worker.backend.jgex_gclc_translator import (
    canonical_typed_goal_key,
    translate_jgex_to_gclc,
)


DEFAULT_NEWCLID = Path.home() / ".cache" / "mortra-research-sources" / "Newclid"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _setup_only(problem: JGEXFormulation) -> str:
    return str(
        JGEXFormulation(
            name=problem.name,
            setup_clauses=problem.setup_clauses,
            auxiliary_clauses=(),
            goals=problem.goals,
        )
    )


def _recompute(result: dict) -> dict:
    if "translation" not in result:
        return result
    exact = result.get("exact", {})
    certificate = exact.get("certificate") or {}
    translation = result["translation"]
    agreement = canonical_typed_goal_key(
        str(certificate.get("channel", "")),
        tuple(certificate.get("points", ())),
    ) == canonical_typed_goal_key(
        str(translation["goal_channel"]),
        tuple(translation["goal_points"]),
    )
    strict = bool(
        result.get("gclc", {}).get("proved")
        and exact.get("status") == "proved"
        and agreement
    )
    updated = dict(result)
    updated["typed_goal_agreement"] = agreement
    updated["strict_exchange_proved"] = strict
    updated["status"] = "strict_exchange_proved" if strict else "unproved"
    return updated


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--confirmation", type=Path, action="append", default=[])
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_NEWCLID / "newclid" / "problems_datasets" / "imo.txt",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=ROOT / "data" / "yuclid-imo-ag-30-native-proofs-2026-08-15.json",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    raw = json.loads(args.raw.read_text(encoding="utf-8"))
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    problems = jgex_formulation_from_txt_file(args.dataset)
    unresolved = [
        name
        for name, result in baseline["results"].items()
        if result["status"] != "solved" and name in problems
    ]
    results = {name: _recompute(result) for name, result in raw["results"].items()}
    evidence = [
        {"path": str(args.raw), "sha256": _sha256(args.raw), "role": "raw-six"}
    ]
    for confirmation_path in args.confirmation:
        confirmation = json.loads(confirmation_path.read_text(encoding="utf-8"))
        evidence.append(
            {
                "path": str(confirmation_path),
                "sha256": _sha256(confirmation_path),
                "role": "confirmation",
            }
        )
        for name, result in confirmation["results"].items():
            results[name] = _recompute(result)

    for name in unresolved:
        if name in results:
            continue
        text = _setup_only(problems[name])
        try:
            translation = translate_jgex_to_gclc(text)
        except ValueError as error:
            results[name] = {
                "status": "translation_unsupported",
                "reason": str(error),
                "runtime_attempted": False,
            }
        else:
            results[name] = {
                "status": "not_run",
                "runtime_attempted": False,
                "translation": {
                    "construction_vocabulary": translation.construction_vocabulary,
                    "goal_channel": translation.goal_channel,
                    "goal_points": translation.goal_points,
                    "source_sha256": translation.source_sha256,
                },
            }

    translated = [result for result in results.values() if "translation" in result]
    gclc_names = sorted(
        name
        for name, result in results.items()
        if result.get("gclc", {}).get("proved")
    )
    exact_names = sorted(
        name
        for name, result in results.items()
        if result.get("exact", {}).get("status") == "proved"
    )
    strict_names = sorted(
        name for name, result in results.items() if result.get("strict_exchange_proved")
    )
    baseline_solved = int(baseline["scores"]["original_imo_ag_30"]["solved"])
    independent_union = baseline_solved + len(set(gclc_names) | set(exact_names))
    strict_portfolio = baseline_solved + len(strict_names)
    summary = {
        "baseline_unresolved": len(unresolved),
        "translated": len(translated),
        "translation_unsupported": sum(
            result["status"] == "translation_unsupported"
            for result in results.values()
        ),
        "runtime_attempted": sum(
            bool(result.get("runtime_attempted", "gclc" in result))
            for result in results.values()
        ),
        "gclc_proved": len(gclc_names),
        "exact_proved_in_runtime_subset": len(exact_names),
        "strict_exchange_proved": len(strict_names),
        "gclc_proved_names": gclc_names,
        "exact_proved_names": exact_names,
        "strict_exchange_proved_names": strict_names,
        "baseline_solved": baseline_solved,
        "independent_union_solved_in_runtime_subset": independent_union,
        "strict_portfolio_solved": strict_portfolio,
        "total": 30,
        "independent_union_score_in_runtime_subset": independent_union / 30,
        "strict_portfolio_score": strict_portfolio / 30,
    }
    report = {
        "experiment": "real-symbolic-coordination-imo-ag-30-consolidated",
        "generated_at": datetime.now(UTC).isoformat(),
        "uses_llm": False,
        "uses_problem_specific_solver_logic": False,
        "dataset_auxiliary_clauses_hidden": True,
        "acceptance_rule": (
            "GCLC native proof AND independent exact replay AND relation-symmetry-aware "
            "typed goal equality"
        ),
        "source_evidence": evidence,
        "summary": summary,
        "results": {name: results[name] for name in unresolved},
        "claim_scope": (
            "The result establishes one real cross-engine certificate exchange. It is "
            "a certified cooperative cascade, not yet learned decentralized Sheaf-ADMM."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
