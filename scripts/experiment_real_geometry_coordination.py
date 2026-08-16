"""Run real Newclid -> GCLC -> exact-certificate coordination on IMO-AG-30.

This experiment intentionally separates two claims:

* portfolio union: at least one symbolic engine proves the problem;
* strict exchange: GCLC proves a mechanically translated obligation and the
  independent JGEX polynomial backend replays the original typed goal.

No problem identifier, known answer, or auxiliary construction is used by the
translator or either backend.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from newclid.jgex.formulation import JGEXFormulation, jgex_formulation_from_txt_file

from reproduce_gclc_methods import git_value, run_method
from experiment_jgex_exact_unsolved_set import _run_isolated
from worker.backend.jgex_gclc_translator import (
    canonical_typed_goal_key,
    translate_jgex_to_gclc,
)


DEFAULT_NEWCLID = Path.home() / ".cache" / "mortra-research-sources" / "Newclid"
DEFAULT_GCLC = Path.home() / ".cache" / "mortra-research-sources" / "gclc"


def _setup_only(problem: JGEXFormulation) -> str:
    return str(
        JGEXFormulation(
            name=problem.name,
            setup_clauses=problem.setup_clauses,
            auxiliary_clauses=(),
            goals=problem.goals,
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_NEWCLID / "newclid" / "problems_datasets" / "imo.txt",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=ROOT / "data" / "yuclid-imo-ag-30-all-ar-2026-08-15.json",
    )
    parser.add_argument("--gclc-root", type=Path, default=DEFAULT_GCLC)
    parser.add_argument("--gclc-executable", type=Path)
    parser.add_argument("--gclc-timeout-seconds", type=int, default=30)
    parser.add_argument("--sketch-attempts", type=int, default=5)
    parser.add_argument("--exact-timeout-seconds", type=float, default=90.0)
    parser.add_argument("--problems", nargs="*")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "real-symbolic-coordination-imo-ag-30-2026-08-16.json",
    )
    args = parser.parse_args()

    executable = args.gclc_executable or (
        args.gclc_root / "build" / "Release" / "gclc.exe"
    )
    if not executable.is_file():
        raise FileNotFoundError(executable)

    problems = jgex_formulation_from_txt_file(args.dataset)
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    baseline_results = baseline["results"]
    selected = [
        name
        for name, result in baseline_results.items()
        if result["status"] != "solved" and name in problems
    ]
    if args.problems:
        requested = set(args.problems)
        selected = [name for name in selected if name in requested]

    results: dict[str, dict] = {}
    for index, name in enumerate(selected, start=1):
        print(f"[{index}/{len(selected)}] {name}", flush=True)
        text = _setup_only(problems[name])
        started = time.perf_counter()
        try:
            translation = translate_jgex_to_gclc(text, sketch_seed=0)
        except ValueError as error:
            results[name] = {
                "status": "translation_unsupported",
                "reason": str(error),
                "elapsed_seconds": time.perf_counter() - started,
            }
            print(f"  unsupported: {error}", flush=True)
            continue

        sketch_runs = []
        gclc_runs = []
        accepted_translation = translation
        for sketch_seed in range(args.sketch_attempts):
            candidate = translate_jgex_to_gclc(text, sketch_seed=sketch_seed)
            with tempfile.TemporaryDirectory(prefix="mortra-jgex-gclc-") as directory:
                input_path = Path(directory) / f"{name}.gcl"
                input_path.write_text(candidate.source, encoding="utf-8")
                attempt_runs = [
                    run_method(
                        executable,
                        input_path,
                        flag,
                        method,
                        prover_timeout_seconds=args.gclc_timeout_seconds,
                    )
                    for flag, method in (("-w", "wu"), ("-g", "groebner"))
                ]
            sketch_runs.append(
                {
                    "sketch_seed": sketch_seed,
                    "source_sha256": candidate.source_sha256,
                    "runs": attempt_runs,
                }
            )
            gclc_runs = attempt_runs
            accepted_translation = candidate
            bad_definition = all(
                "bad definition" in run["transcript"].lower()
                for run in attempt_runs
            )
            if not bad_definition:
                break

        translation = accepted_translation

        gclc_proved = any(run["proved"] for run in gclc_runs)
        exact = _run_isolated(text, args.exact_timeout_seconds)
        exact_certificate = exact.get("certificate") or {}
        typed_goal_agreement = canonical_typed_goal_key(
            str(exact_certificate.get("channel", "")),
            tuple(exact_certificate.get("points", ())),
        ) == canonical_typed_goal_key(
            translation.goal_channel,
            translation.goal_points,
        )
        strict_exchange_proved = bool(
            gclc_proved
            and exact.get("status") == "proved"
            and typed_goal_agreement
        )
        result = {
            "status": "strict_exchange_proved" if strict_exchange_proved else "unproved",
            "translation": {
                "construction_vocabulary": translation.construction_vocabulary,
                "goal_channel": translation.goal_channel,
                "goal_points": translation.goal_points,
                "source_sha256": translation.source_sha256,
                "source": translation.source,
            },
            "gclc": {
                "proved": gclc_proved,
                "runs": gclc_runs,
                "sketch_attempts": sketch_runs,
            },
            "exact": exact,
            "typed_goal_agreement": typed_goal_agreement,
            "strict_exchange_proved": strict_exchange_proved,
            "elapsed_seconds": time.perf_counter() - started,
        }
        results[name] = result
        print(
            "  gclc="
            f"{gclc_proved} exact={exact.get('status')} "
            f"agreement={typed_goal_agreement} strict={strict_exchange_proved}",
            flush=True,
        )

    translated = [
        result
        for result in results.values()
        if "translation" in result
    ]
    gclc_proved_names = sorted(
        name
        for name, result in results.items()
        if result.get("gclc", {}).get("proved")
    )
    exact_proved_names = sorted(
        name
        for name, result in results.items()
        if result.get("exact", {}).get("status") == "proved"
    )
    strict_names = sorted(
        name for name, result in results.items() if result.get("strict_exchange_proved")
    )
    baseline_solved = int(baseline["scores"]["original_imo_ag_30"]["solved"])
    strict_portfolio = baseline_solved + len(strict_names)
    report = {
        "experiment": "real-symbolic-coordination-imo-ag-30",
        "generated_at": datetime.now(UTC).isoformat(),
        "uses_llm": False,
        "uses_problem_specific_solver_logic": False,
        "dataset_auxiliary_clauses_hidden": True,
        "coordination_protocol": [
            "Yuclid saturation exposes an unresolved typed goal",
            "JGEX structure is mechanically translated to GCLC",
            "GCLC Wu and Groebner agents attempt the same goal",
            "the independent JGEX polynomial backend replays the original goal",
            "strict acceptance requires native proof, exact replay, and typed-goal agreement",
        ],
        "environment": {
            "gclc_repository": "https://github.com/janicicpredrag/gclc",
            "gclc_commit": git_value(args.gclc_root, "rev-parse", "HEAD"),
            "gclc_executable": str(executable),
        },
        "budget": {
            "gclc_methods": ["wu", "groebner"],
            "gclc_timeout_seconds_per_method": args.gclc_timeout_seconds,
            "maximum_numeric_sketch_attempts": args.sketch_attempts,
            "exact_timeout_seconds_per_problem": args.exact_timeout_seconds,
        },
        "summary": {
            "baseline_unresolved_selected": len(selected),
            "translated": len(translated),
            "translation_unsupported": len(selected) - len(translated),
            "gclc_proved": len(gclc_proved_names),
            "exact_proved": len(exact_proved_names),
            "strict_exchange_proved": len(strict_names),
            "gclc_proved_names": gclc_proved_names,
            "exact_proved_names": exact_proved_names,
            "strict_exchange_proved_names": strict_names,
            "baseline_solved": baseline_solved,
            "strict_portfolio_solved": strict_portfolio,
            "total": 30,
            "strict_portfolio_score": strict_portfolio / 30,
        },
        "results": results,
        "claim_scope": (
            "This is real certificate exchange between external symbolic engines, "
            "not yet a reproduction of end-to-end learned Sheaf-ADMM. The strict "
            "score counts only goals proved by GCLC and replayed independently."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
