"""Inject certified homothety boundary facts into the native Newclid prover."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path


def _bootstrap_runtime() -> object | None:
    if "--runtime-path" in sys.argv:
        index = sys.argv.index("--runtime-path")
        runtime_path = str(Path(sys.argv[index + 1]).resolve())
    else:
        runtime_path = str(
            Path.home()
            / ".cache"
            / "mortra-research-sources"
            / "boost_1_88_dlls"
            / "app"
            / "lib64-msvc-14.3"
        )
    if "--yuclid-exe" in sys.argv:
        index = sys.argv.index("--yuclid-exe")
        yuclid_bin = str(Path(sys.argv[index + 1]).resolve().parent)
    else:
        yuclid_bin = str(
            Path.home()
            / ".cache"
            / "mortra-research-sources"
            / "Newclid"
            / ".venv"
            / "Scripts"
        )
    os.environ["PATH"] = os.pathsep.join(
        (yuclid_bin, runtime_path, os.environ.get("PATH", ""))
    )
    if sys.platform == "win32" and hasattr(os, "add_dll_directory"):
        return os.add_dll_directory(runtime_path)
    return None


_DLL_DIRECTORY = _bootstrap_runtime()

import numpy as np  # noqa: E402
from newclid.jgex.formulation import (  # noqa: E402
    JGEXFormulation,
    jgex_formulation_from_txt_file,
)
from newclid.jgex.problem_builder import JGEXProblemBuilder  # noqa: E402
from newclid.problem import PredicateConstruction  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from worker.backend.jgex_legacy_normalizer import (  # noqa: E402
    normalize_legacy_formulation,
)
from worker.backend.jgex_local_relation_stalk import (  # noqa: E402
    extract_jgex_relation_stalk,
)
from worker.backend.yuclid_native_verifier import verify_problem  # noqa: E402


DEFAULT_NEWCLID = Path.home() / ".cache" / "mortra-research-sources" / "Newclid"
DEFAULT_RUNTIME = (
    Path.home()
    / ".cache"
    / "mortra-research-sources"
    / "boost_1_88_dlls"
    / "app"
    / "lib64-msvc-14.3"
)


def _render_atom(atom) -> str:
    return " ".join((atom.predicate, *atom.arguments))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_NEWCLID / "newclid" / "problems_datasets" / "imo.txt",
    )
    parser.add_argument("--problem-name", default="2008_p6")
    parser.add_argument(
        "--yuclid-exe",
        type=Path,
        default=DEFAULT_NEWCLID / ".venv" / "Scripts" / "yuclid.exe",
    )
    parser.add_argument("--runtime-path", type=Path, default=DEFAULT_RUNTIME)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "newclid-homothety-exchange-2008-p6-2026-08-16.json",
    )
    args = parser.parse_args()

    raw = jgex_formulation_from_txt_file(args.dataset)[args.problem_name]
    raw = JGEXFormulation(
        name=raw.name,
        setup_clauses=raw.setup_clauses,
        auxiliary_clauses=(),
        goals=raw.goals,
    )
    builder = JGEXProblemBuilder(np.random.default_rng(args.seed))
    normalized, normalization = normalize_legacy_formulation(raw, builder.jgex_defs)
    stalk = extract_jgex_relation_stalk(str(normalized))
    derived = {
        certificate.conclusions[0].predicate: certificate
        for certificate in stalk.certificates
        if certificate.rule_name
        in {
            "external_homothety_to_center_collinearity",
            "external_homothety_to_radius_ratio",
        }
    }
    if set(derived) != {"coll", "eqratio"}:
        raise RuntimeError("certified homothety boundary facts were not extracted")

    modes = {
        "baseline": (),
        "collinearity_only": ("coll",),
        "ratio_only": ("eqratio",),
        "collinearity_and_ratio": ("coll", "eqratio"),
    }
    base_problem = (
        JGEXProblemBuilder(np.random.default_rng(args.seed))
        .with_problem(normalized)
        .include_auxiliary_clauses(False)
        .build()
    )
    results: dict[str, dict] = {}
    for mode, predicates in modes.items():
        injected_assumptions = tuple(
            PredicateConstruction.from_str(
                _render_atom(derived[predicate].conclusions[0])
            )
            for predicate in predicates
        )
        problem = base_problem.with_new(
            new_assumptions=injected_assumptions,
        )
        verification = verify_problem(
            problem,
            yuclid_exe=args.yuclid_exe.resolve(),
            ar_profile="all",
        )
        results[mode] = {
            "injected_relations": list(predicates),
            "injected_facts": [
                _render_atom(derived[predicate].conclusions[0])
                for predicate in predicates
            ],
            "solved": verification.solved,
            "status": verification.status,
            "elapsed_seconds": verification.elapsed_seconds,
            "all_deduction_count": verification.all_deduction_count,
            "goal_deduction_count": verification.goal_deduction_count,
            "proof_sha256": verification.proof_sha256,
        }

    report = {
        "experiment": "newclid-certified-homothety-boundary-exchange",
        "generated_at": datetime.now(UTC).isoformat(),
        "uses_llm": False,
        "uses_problem_specific_solver_logic": False,
        "dataset_auxiliary_clauses_hidden": True,
        "problem_name_is_evaluation_selection_only": args.problem_name,
        "normalization": asdict(normalization),
        "certificates": {
            predicate: asdict(certificate) for predicate, certificate in derived.items()
        },
        "results": results,
        "claim_scope": (
            "Only independently replayed homothety boundary relations are injected. "
            "The experiment measures whether they help the unchanged native prover."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(results, ensure_ascii=False, indent=2))
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
