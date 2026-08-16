"""証明書付きWu固定実験の主張と証明ハッシュを再監査する。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


FIXED4 = ["2008_p6", "2010_p2", "2020_p1", "2021_p3"]


def _certificate_hash(step: dict[str, object]) -> str:
    material = "|".join(
        str(step[key])
        for key in (
            "phase",
            "variable",
            "dividend",
            "divisor",
            "multiplier",
            "quotient",
            "remainder_multiplier",
            "remainder",
            "replay_residual",
        )
    )
    return hashlib.sha256(material.encode()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()
    report = json.loads(args.artifact.read_text(encoding="utf-8"))
    checks: dict[str, bool] = {
        "no_llm": report["uses_llm"] is False,
        "no_problem_specific_solver": report[
            "uses_problem_specific_solver_logic"
        ]
        is False,
        "fixed4": report["fixed_problem_names"] == FIXED4,
        "auxiliary_clauses_hidden": report["dataset_auxiliary_clauses_hidden"]
        is True,
    }
    calculated_steps = 0
    calculated_normalizations = 0
    calculated_accepted = 0
    calculated_oversized = 0
    calculated_discharged = 0
    calculated_open = 0
    calculated_input_conditioned = 0
    calculated_expanded_micro = 0
    calculated_skipped_micro = 0
    calculated_content_addressed_fallback = 0
    for name, payload in report["results"].items():
        checks[f"{name}:known_status"] = payload["status"] in {
            "completed",
            "timeout",
            "execution_error",
        }
        if payload["status"] != "completed":
            continue
        result = payload["result"]
        coordination = payload["coordination"]
        steps = (*result["triangulation_steps"], *result["goal_steps"])
        calculated_steps += len(steps)
        calculated_normalizations += sum(
            step["normalization_nonzero_obligation"] is not None
            for step in result["triangulation_steps"]
        )
        calculated_accepted += coordination["accepted_certificate_count"]
        calculated_oversized += coordination["oversized_certificate_count"]
        calculated_discharged += coordination["discharged_regularity_count"]
        calculated_open += coordination["open_regularity_count"]
        calculated_input_conditioned += int(
            coordination["input_conditioned_goal_solved"]
        )
        calculated_expanded_micro += coordination["expanded_micro_certificate_count"]
        calculated_skipped_micro += coordination["skipped_micro_certificate_count"]
        calculated_content_addressed_fallback += coordination[
            "content_addressed_fallback_certificate_count"
        ]
        checks[f"{name}:identities_replayed"] = (
            result["all_identities_replayed"] is True
            and all(step["replayed"] is True for step in steps)
            and all(step["replay_residual"] == "0" for step in steps)
        )
        checks[f"{name}:certificate_hashes"] = all(
            step["certificate_sha256"] == _certificate_hash(step)
            for step in steps
        )
        checks[f"{name}:no_rejected_exchange"] = (
            coordination["rejected_certificate_count"] == 0
        )
        checks[f"{name}:conditional_claim_guard"] = (
            not result["conditional_goal_proved"]
            or (
                result["triangularization_complete"]
                and result["final_remainder"] == "0"
                and coordination["conditional_goal_replayed"]
            )
        )
        checks[f"{name}:unconditional_claim_guard"] = (
            not result["unconditional_goal_proved"]
            or (
                result["conditional_goal_proved"]
                and not result["nonzero_obligations"]
            )
        )
        checks[f"{name}:input_conditioned_claim_guard"] = (
            not coordination["input_conditioned_goal_solved"]
            or (
                coordination["conditional_goal_solved"]
                and coordination["conditional_goal_replayed"]
                and coordination["open_regularity_count"] == 0
            )
        )
        checks[f"{name}:regularity_partition"] = (
            coordination["regularity_assumption_count"]
            == coordination["discharged_regularity_count"]
            + coordination["open_regularity_count"]
        )
        checks[f"{name}:vanished_variables_are_not_pivots"] = not (
            set(result.get("vanished_variables", []))
            & {pivot["variable"] for pivot in result["pivots"]}
        )
    summary = report["summary"]
    checks.update(
        {
            "summary:pseudo_division_steps": summary["pseudo_division_steps"]
            == calculated_steps,
            "summary:normalization_obligations": summary[
                "normalization_obligations"
            ]
            == calculated_normalizations,
            "summary:accepted_local_certificates": summary[
                "accepted_local_certificates"
            ]
            == calculated_accepted,
            "summary:oversized_local_certificates": summary[
                "oversized_local_certificates"
            ]
            == calculated_oversized,
            "summary:discharged_regularity_obligations": summary[
                "discharged_regularity_obligations"
            ]
            == calculated_discharged,
            "summary:open_regularity_obligations": summary[
                "open_regularity_obligations"
            ]
            == calculated_open,
            "summary:input_conditioned_goals_solved": summary[
                "input_conditioned_goals_solved"
            ]
            == calculated_input_conditioned,
            "summary:expanded_micro_certificates": summary[
                "expanded_micro_certificates"
            ]
            == calculated_expanded_micro,
            "summary:skipped_micro_certificates": summary[
                "skipped_micro_certificates"
            ]
            == calculated_skipped_micro,
            "summary:content_addressed_fallback_certificates": summary[
                "content_addressed_fallback_certificates"
            ]
            == calculated_content_addressed_fallback,
        }
    )
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    if not all(checks.values()):
        return 1
    print("Certified Wu artifact verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
