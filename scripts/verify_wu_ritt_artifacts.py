"""公開するWu--Ritt成果物の証明書ハッシュと枝被覆を再監査する。"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from worker.backend.wu_rtm_support import audit_wu_rtm_support  # noqa: E402


def _read_json(path: Path) -> dict[str, object]:
    raw = gzip.decompress(path.read_bytes()) if path.suffix == ".gz" else path.read_bytes()
    return json.loads(raw.decode("utf-8"))


def _verify_step(step: dict[str, object]) -> bool:
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
    return (
        step.get("replayed") is True
        and step.get("replay_residual") == "0"
        and hashlib.sha256(material.encode()).hexdigest()
        == step.get("certificate_sha256")
    )


def _reductions(proof: dict[str, object]) -> list[dict[str, object]]:
    characteristic = proof["characteristic"]
    assert isinstance(characteristic, dict)
    reductions = [
        reduction
        for round_payload in characteristic["rounds"]
        for reduction in round_payload["reductions"]
    ]
    reductions.extend(characteristic["input_reductions"])
    if proof.get("goal_reduction") is not None:
        reductions.append(proof["goal_reduction"])
    return reductions


def verify_proof_artifact(path: Path, problem: str) -> None:
    payload = _read_json(path)
    proof = payload["results"][problem]["proof"]
    characteristic = proof["characteristic"]
    reductions = _reductions(proof)
    steps = [step for reduction in reductions for step in reduction["steps"]]
    assert characteristic["basic_set_mode"] == "weak"
    assert characteristic["characteristic_set_verified"] is True
    assert proof["conditional_goal_proved"] is True
    assert steps and all(_verify_step(step) for step in steps)
    audit = audit_wu_rtm_support(proof)
    assert audit.all_references_resolved
    assert audit.all_certificates_replayed
    assert audit.goal_support_width == audit.hypothesis_count


def verify_standard_ablation(path: Path, problem: str) -> None:
    payload = _read_json(path)
    proof = payload["results"][problem]["proof"]
    characteristic = proof["characteristic"]
    steps = [step for reduction in _reductions(proof) for step in reduction["steps"]]
    assert characteristic["basic_set_mode"] == "standard"
    assert characteristic["characteristic_set_verified"] is False
    assert proof["conditional_goal_proved"] is False
    assert proof["stopped_reason"] == "term_budget"
    assert characteristic["maximum_term_count"] > 20_000
    assert steps and all(_verify_step(step) for step in steps)


def verify_localization_ablations(
    parameter_path: Path,
    goal_cone_path: Path,
    problem: str,
) -> None:
    parameter = _read_json(parameter_path)
    assert parameter["results"][problem]["status"] == "timeout"
    goal_cone = _read_json(goal_cone_path)
    result = goal_cone["results"][problem]
    proof = result["proof"]
    characteristic = proof["characteristic"]
    steps = [step for reduction in _reductions(proof) for step in reduction["steps"]]
    assert result["input"]["dropped_equation_indices"] == []
    assert characteristic["characteristic_set_verified"] is False
    assert proof["stopped_reason"] == "timeout"
    assert steps and all(_verify_step(step) for step in steps)


def _closed(branch_id: str, branches: dict[str, dict[str, object]]) -> bool:
    branch = branches[branch_id]
    if branch["status"] in {
        "proved",
        "proved_regular_locus",
        "empty_characteristic",
        "empty_by_input_ndg",
    }:
        return True
    return bool(branch["status"] == "split" and branch["child_ids"]) and all(
        _closed(child_id, branches) for child_id in branch["child_ids"]
    )


def verify_decomposition_artifact(path: Path, problem: str) -> None:
    payload = _read_json(path)
    result = payload["results"][problem]
    decomposition = result["decomposition"]
    branches = {item["branch_id"]: item for item in decomposition["branches"]}
    assert result["cover_verified"] is True
    assert decomposition["rank_decrease_violations"] == 0
    assert decomposition["all_computed_identities_replayed"] is True
    assert decomposition["coverage_complete"] == _closed("B0", branches)
    for branch in branches.values():
        if branch["status"] != "split":
            continue
        regular_id, *zero_ids = branch["child_ids"]
        regular = branches[regular_id]
        assert regular["locus"] == "regular"
        assert set(branch["regularity_factors"]).issubset(regular["nonzero_factors"])
        required = set(branch["system_polynomials"]) | set(branch["characteristic_set"])
        for factor, child_id in zip(branch["regularity_factors"], zero_ids, strict=True):
            child = branches[child_id]
            assert required.issubset(child["system_polynomials"])
            assert factor in child["system_polynomials"]
            assert factor in child["zero_factors"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--standard-artifact", type=Path, required=True)
    parser.add_argument("--proof-artifact", type=Path, required=True)
    parser.add_argument("--parameter-field-artifact", type=Path, required=True)
    parser.add_argument("--goal-cone-artifact", type=Path, required=True)
    parser.add_argument("--decomposition-artifact", type=Path, required=True)
    parser.add_argument("--problem", required=True)
    args = parser.parse_args()
    verify_standard_ablation(args.standard_artifact, args.problem)
    verify_localization_ablations(
        args.parameter_field_artifact,
        args.goal_cone_artifact,
        args.problem,
    )
    verify_proof_artifact(args.proof_artifact, args.problem)
    verify_decomposition_artifact(args.decomposition_artifact, args.problem)
    print("Wu--Ritt artifacts verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
