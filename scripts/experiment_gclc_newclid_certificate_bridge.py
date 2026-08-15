"""Run native GCLC proofs and replay their obligations through exact polynomials."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from newclid.problem import PredicateConstruction

from scripts.reproduce_gclc_methods import run_method
from worker.backend.gclc_newclid_bridge import lower_gclc_to_newclid


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--native-timeout-seconds", type=int, default=120)
    args = parser.parse_args()
    executable = args.source_root / "build" / "Release" / "gclc.exe"
    sample_root = args.source_root / "samples" / "samples_prover"
    inputs = (
        sample_root / "thm_midpoint.gcl",
        sample_root / "thm_orthocenter.gcl",
        sample_root / "thm_Gauss.gcl",
        sample_root / "other_samples" / "thm_Pappus.gcl",
        sample_root / "other_samples" / "thm_PappusHexagon.gcl",
    )
    cases = []
    for path in inputs:
        source = path.read_text(encoding="utf-8", errors="replace")
        obligation = lower_gclc_to_newclid(source)
        native_runs = [
            run_method(
                executable,
                path,
                flag,
                method,
                prover_timeout_seconds=args.native_timeout_seconds,
            )
            for flag, method in (("-w", "wu"), ("-g", "groebner"))
        ]
        canonical_newclid = str(
            PredicateConstruction.from_str(obligation.newclid_predicate)
        )
        cases.append(
            {
                "name": path.stem,
                "native_runs": native_runs,
                "obligation": asdict(obligation),
                "newclid_canonical_predicate": canonical_newclid,
                "roundtrip_accepted": (
                    all(run["proved"] for run in native_runs)
                    and obligation.exact_replay
                    and bool(canonical_newclid)
                ),
                "portfolio_roundtrip_accepted": (
                    any(run["proved"] for run in native_runs)
                    and obligation.exact_replay
                    and bool(canonical_newclid)
                ),
            }
        )
    summary = {
        "case_count": len(cases),
        "gclc_native_proved": sum(
            all(run["proved"] for run in case["native_runs"]) for case in cases
        ),
        "exact_polynomial_replayed": sum(
            case["obligation"]["exact_replay"] for case in cases
        ),
        "newclid_lowered": sum(bool(case["newclid_canonical_predicate"]) for case in cases),
        "roundtrip_accepted": sum(case["roundtrip_accepted"] for case in cases),
        "portfolio_roundtrip_accepted": sum(
            case["portfolio_roundtrip_accepted"] for case in cases
        ),
        "native_method_proved": {
            method: sum(
                next(
                    run["proved"]
                    for run in case["native_runs"]
                    if run["method"] == method
                )
                for case in cases
            )
            for method in ("wu", "groebner")
        },
        "verification_methods": {
            method: sum(
                case["obligation"]["verification_method"] == method for case in cases
            )
            for method in sorted(
                {case["obligation"]["verification_method"] for case in cases}
            )
        },
    }
    report = {
        "experiment": "gclc_to_newclid_concrete_certificate_bridge",
        "generated_at": datetime.now(UTC).isoformat(),
        "uses_llm": False,
        "protocol": {
            "native_methods": ["wu", "groebner"],
            "native_prover_timeout_seconds": args.native_timeout_seconds,
            "independent_replay": (
                "exact Groebner ideal-membership or typed rational construction "
                "elimination with explicit nonzero denominators"
            ),
            "accepted_channels": ["coll", "para", "perp", "cong"],
            "strict_acceptance": (
                "both native GCLC methods + exact replay + Newclid syntax"
            ),
            "portfolio_acceptance": (
                "at least one native GCLC method + independent exact replay + "
                "Newclid syntax"
            ),
        },
        "summary": summary,
        "cases": cases,
        "claim_scope": (
            "Concrete certificate roundtrip on supported GCLC constructions. "
            "The certificate is not yet injected into a previously unsolved IMO problem."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if summary["roundtrip_accepted"] == len(cases) else 1


if __name__ == "__main__":
    raise SystemExit(main())
