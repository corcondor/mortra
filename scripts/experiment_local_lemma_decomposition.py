"""Ablate monolithic elimination against typed local-lemma exchange.

The experiment is deliberately problem-ID blind inside every transformation.
Problem names only select a fixed evaluation slice.  Dataset auxiliary clauses
are removed before elaboration and proof.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import sys
import tempfile
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from newclid.jgex.formulation import (  # noqa: E402
    JGEXFormulation,
    jgex_formulation_from_txt_file,
)

from reproduce_gclc_methods import run_method  # noqa: E402
from worker.backend.jgex_exact_constraint_bridge import (  # noqa: E402
    inspect_jgex_exact_system,
    lower_jgex_to_exact_obligation,
)
from worker.backend.jgex_gclc_translator import (  # noqa: E402
    translate_jgex_to_gclc,
)


DEFAULT_NEWCLID = Path.home() / ".cache" / "mortra-research-sources" / "Newclid"
DEFAULT_GCLC = Path.home() / ".cache" / "mortra-research-sources" / "gclc"
DEFAULT_PROBLEMS = ("2008_p6", "2010_p2", "2020_p1", "2021_p3")


def _setup_only(problem: JGEXFormulation) -> str:
    return str(
        JGEXFormulation(
            name=problem.name,
            setup_clauses=problem.setup_clauses,
            auxiliary_clauses=(),
            goals=problem.goals,
        )
    )


def _exact_worker(
    text: str,
    affine: bool,
    structural: bool,
    output_path: str,
) -> None:
    try:
        obligation = lower_jgex_to_exact_obligation(
            text,
            enable_affine_local_lemmas=affine,
            enable_structural_lemmas=structural,
        )
        payload = {"status": "proved" if obligation.exact_replay else "unproved"}
        payload["certificate"] = asdict(obligation)
    except Exception as error:
        payload = {
            "status": "execution_error",
            "reason": f"{type(error).__name__}: {error}",
        }
    Path(output_path).write_text(json.dumps(payload), encoding="utf-8")


def _inspection_worker(
    text: str,
    affine: bool,
    structural: bool,
    output_path: str,
) -> None:
    try:
        analysis = inspect_jgex_exact_system(
            text,
            enable_affine_local_lemmas=affine,
            enable_structural_lemmas=structural,
        )
        payload = {"status": "completed", "analysis": asdict(analysis)}
    except Exception as error:
        payload = {
            "status": "execution_error",
            "reason": f"{type(error).__name__}: {error}",
        }
    Path(output_path).write_text(json.dumps(payload), encoding="utf-8")


def _run_exact(
    text: str,
    *,
    affine: bool,
    structural: bool,
    timeout_seconds: float,
) -> dict:
    context = mp.get_context("spawn")
    with tempfile.TemporaryDirectory(prefix="mortra-local-lemma-") as directory:
        output_path = Path(directory) / "result.json"
        process = context.Process(
            target=_exact_worker,
            args=(text, affine, structural, str(output_path)),
        )
        started = time.perf_counter()
        process.start()
        process.join(None if timeout_seconds <= 0 else timeout_seconds)
        elapsed = time.perf_counter() - started
        if timeout_seconds > 0 and process.is_alive():
            process.terminate()
            process.join(5)
            return {"status": "timeout", "elapsed_seconds": elapsed}
        if not output_path.exists():
            return {
                "status": "execution_error",
                "return_code": process.exitcode,
                "elapsed_seconds": elapsed,
            }
        result = json.loads(output_path.read_text(encoding="utf-8"))
        result["elapsed_seconds"] = elapsed
        return result


def _run_inspection(
    text: str,
    *,
    affine: bool,
    structural: bool,
    timeout_seconds: float,
) -> dict:
    context = mp.get_context("spawn")
    with tempfile.TemporaryDirectory(prefix="mortra-local-lemma-inspect-") as directory:
        output_path = Path(directory) / "result.json"
        process = context.Process(
            target=_inspection_worker,
            args=(text, affine, structural, str(output_path)),
        )
        started = time.perf_counter()
        process.start()
        process.join(None if timeout_seconds <= 0 else timeout_seconds)
        elapsed = time.perf_counter() - started
        if timeout_seconds > 0 and process.is_alive():
            process.terminate()
            process.join(5)
            return {"status": "timeout", "elapsed_seconds": elapsed}
        if not output_path.exists():
            return {
                "status": "execution_error",
                "return_code": process.exitcode,
                "elapsed_seconds": elapsed,
            }
        result = json.loads(output_path.read_text(encoding="utf-8"))
        result["elapsed_seconds"] = elapsed
        return result


def _gclc_runs(
    *,
    source: str,
    executable: Path,
    timeout_seconds: int,
) -> list[dict]:
    with tempfile.TemporaryDirectory(prefix="mortra-local-lemma-gclc-") as directory:
        path = Path(directory) / "obligation.gcl"
        path.write_text(source, encoding="utf-8")
        return [
            run_method(
                executable,
                path,
                flag,
                method,
                prover_timeout_seconds=timeout_seconds,
            )
            for flag, method in (("-w", "wu"), ("-g", "groebner"))
        ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_NEWCLID / "newclid" / "problems_datasets" / "imo.txt",
    )
    parser.add_argument("--problems", nargs="*", default=DEFAULT_PROBLEMS)
    parser.add_argument("--exact-timeout-seconds", type=float, default=60.0)
    parser.add_argument("--inspection-timeout-seconds", type=float, default=60.0)
    parser.add_argument("--gclc-timeout-seconds", type=int, default=60)
    parser.add_argument(
        "--gclc-executable",
        type=Path,
        default=DEFAULT_GCLC / "build" / "Release" / "gclc.exe",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "local-lemma-decomposition-fixed4-2026-08-16.json",
    )
    args = parser.parse_args()

    problems = jgex_formulation_from_txt_file(args.dataset)
    modes = {
        "monolithic": (False, False),
        "affine_local": (True, False),
        "affine_and_structural": (True, True),
    }
    results: dict[str, dict] = {}
    for problem_name in args.problems:
        print(f"[{problem_name}] preparing", flush=True)
        text = _setup_only(problems[problem_name])
        problem_result: dict[str, dict] = {}
        for mode_name, (affine, structural) in modes.items():
            print(f"  {mode_name}: inspect", flush=True)
            inspection = _run_inspection(
                text,
                affine=affine,
                structural=structural,
                timeout_seconds=args.inspection_timeout_seconds,
            )
            translation = translate_jgex_to_gclc(
                text,
                enable_structural_lemmas=structural,
            )
            print(f"  {mode_name}: exact", flush=True)
            exact = _run_exact(
                text,
                affine=affine,
                structural=structural,
                timeout_seconds=args.exact_timeout_seconds,
            )
            gclc: dict = {
                "source_lines": len(translation.source.splitlines()),
                "source_characters": len(translation.source),
                "local_lemma_certificates": translation.local_lemma_certificates,
            }
            # GCLC source differs only when a structural lemma was found.
            if translation.local_lemma_certificates or mode_name == "monolithic":
                print(f"  {mode_name}: GCLC", flush=True)
                runs = _gclc_runs(
                    source=translation.source,
                    executable=args.gclc_executable,
                    timeout_seconds=args.gclc_timeout_seconds,
                )
                gclc["runs"] = runs
                gclc["proved"] = any(item["proved"] for item in runs)
            problem_result[mode_name] = {
                "inspection": inspection,
                "exact": exact,
                "gclc": gclc,
            }
        results[problem_name] = problem_result

    summary = {
        mode_name: {
            "exact_proved": sum(
                result[mode_name]["exact"]["status"] == "proved"
                for result in results.values()
            ),
            "exact_timeouts": sum(
                result[mode_name]["exact"]["status"] == "timeout"
                for result in results.values()
            ),
            "inspection_completed": sum(
                result[mode_name]["inspection"]["status"] == "completed"
                for result in results.values()
            ),
            "total_variables": sum(
                result[mode_name]["inspection"]
                .get("analysis", {})
                .get("variable_count", 0)
                for result in results.values()
            ),
            "total_equations": sum(
                result[mode_name]["inspection"]
                .get("analysis", {})
                .get("equation_count", 0)
                for result in results.values()
            ),
            "total_expanded_terms": sum(
                result[mode_name]["inspection"]
                .get("analysis", {})
                .get("total_expanded_terms", 0)
                for result in results.values()
            ),
        }
        for mode_name in modes
    }
    report = {
        "experiment": "typed-local-lemma-decomposition-fixed4",
        "generated_at": datetime.now(UTC).isoformat(),
        "uses_llm": False,
        "uses_problem_specific_solver_logic": False,
        "dataset_auxiliary_clauses_hidden": True,
        "fixed_problem_names": list(args.problems),
        "hypothesis": (
            "Replacing clause-local affine variables and a typed external-tangent "
            "composition by replayable boundary lemmas reduces elimination complexity "
            "without changing the goal or using known solutions."
        ),
        "budgets": {
            "exact_seconds_per_mode_problem": args.exact_timeout_seconds,
            "inspection_seconds_per_mode_problem": args.inspection_timeout_seconds,
            "gclc_seconds_per_method": args.gclc_timeout_seconds,
        },
        "summary": summary,
        "results": results,
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
