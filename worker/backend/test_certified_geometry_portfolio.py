from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from worker.backend.certified_geometry_portfolio import (
    audit_geometry_artifact,
    diagnose_ablation_false_negatives,
    load_certified_union,
    score_geometry_portfolio,
)


def _write(path: Path, payload: object) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_newclid_and_gclc_certificates_form_a_capability_union(
    tmp_path: Path,
) -> None:
    newclid_proof = tmp_path / "newclid-proof.json"
    newclid_hash = _write(
        newclid_proof,
        {"status": "solved", "deductions_for_goal": [{"goal": "g"}]},
    )
    newclid_run = tmp_path / "newclid-run.json"
    _write(
        newclid_run,
        {
            "problem_name": "p1",
            "solved": True,
            "certificate": {
                "source": "native_replay",
                "proof_path": str(newclid_proof),
                "proof_file_sha256": newclid_hash,
            },
        },
    )

    gclc_proof = tmp_path / "gclc-proof.tex"
    gclc_proof.write_text("proved", encoding="utf-8")
    gclc_hash = hashlib.sha256(gclc_proof.read_bytes()).hexdigest()
    gclc_metadata = tmp_path / "gclc.json"
    _write(
        gclc_metadata,
        {
            "status": "proved",
            "input_sha256": "input",
            "proof_file_sha256": gclc_hash,
            "run": {"proved": True, "return_code": 0, "proof_sha256": gclc_hash},
        },
    )
    gclc_run = tmp_path / "gclc-run.json"
    _write(
        gclc_run,
        {
            "problem_name": "p2",
            "solved": True,
            "certificate": {
                "source": "baseline_gclc_wu",
                "input_sha256": "input",
                "proof_sha256": gclc_hash,
                "proof_path": str(gclc_proof),
                "proof_file_sha256": gclc_hash,
                "metadata_path": str(gclc_metadata),
            },
        },
    )

    audits = (
        audit_geometry_artifact("newclid", newclid_run, root=tmp_path),
        audit_geometry_artifact("gclc_wu", gclc_run, root=tmp_path),
    )
    result = score_geometry_portfolio(("p1", "p2", "p3"), audits)

    assert result["certified_solved"] == 2
    assert result["results"][0]["admitted_agents"] == ["newclid"]
    assert result["results"][1]["admitted_agents"] == ["gclc_wu"]


def test_replayed_exact_certificate_is_admitted(tmp_path: Path) -> None:
    proof = tmp_path / "exact-proof.json"
    proof_hash = _write(
        proof,
        {
            "status": "proved",
            "certificate": {
                "exact_replay": True,
                "remainder": "0",
                "certificate_sha256": "exact-certificate",
                "local_lemma_certificates": [
                    {
                        "replayed": True,
                        "forward_residual": "0",
                        "reverse_residual": "0",
                    }
                ],
                "structural_lemma_certificates": [
                    {
                        "replayed": True,
                        "composition_replayed": True,
                        "composition_certificate_sha256": "composition",
                        "replay_residuals": ["0", "0"],
                    }
                ],
                "local_elimination": {"exact_replay": True},
            },
        },
    )
    run = tmp_path / "exact-run.json"
    _write(
        run,
        {
            "problem_name": "exact-p",
            "solved": True,
            "certificate": {
                "source": "jgex_exact_elimination",
                "proof_sha256": "exact-certificate",
                "proof_path": str(proof),
                "proof_file_sha256": proof_hash,
            },
        },
    )

    audit = audit_geometry_artifact("jgex_exact", run, root=tmp_path)

    assert audit.admitted is True
    assert audit.certificate_kind == "jgex_exact_json"
    assert audit.reason == "replayed_jgex_exact_certificate"


def _singular_lift_fixture(tmp_path: Path) -> tuple[Path, Path, dict[str, object]]:
    checkpoint = {
        "schema": "mortra.terminal_groebner_system.v1",
        "input_polynomials": ["x - a"],
        "variables": ["x"],
        "coefficient_parameters": ["a"],
        "coefficient_domain": "QQ(a)",
        "goal_polynomial": "x - a",
        "nonzero_conditions": ["a != 0"],
    }
    checkpoint_material = "\n".join(
        (
            "terminal_groebner_system_v1",
            *checkpoint["input_polynomials"],
            "variables=" + ",".join(checkpoint["variables"]),
            "coefficient_parameters="
            + ",".join(checkpoint["coefficient_parameters"]),
            "coefficient_domain=" + checkpoint["coefficient_domain"],
            "goal=" + checkpoint["goal_polynomial"],
            *checkpoint["nonzero_conditions"],
        )
    )
    checkpoint_sha256 = hashlib.sha256(checkpoint_material.encode()).hexdigest()
    checkpoint["certificate_sha256"] = checkpoint_sha256
    checkpoint_path = tmp_path / "checkpoint.json"
    _write(checkpoint_path, checkpoint)

    singular = {
        "initial_polynomials": ["x - a"],
        "basis_engine": "bounded_linear",
        "certificate_degree": 1,
        "goal_polynomial": "x - a",
        "remainder": "0",
        "initial_multipliers": ["1"],
        "replay_residual": "0",
        "proved": True,
        "replayed": True,
        "status": "proved",
    }
    singular_material = "|".join(
        (
            "bounded_linear",
            "1",
            "x - a",
            "x - a",
            "1",
            "0",
        )
    )
    singular["certificate_sha256"] = hashlib.sha256(
        singular_material.encode()
    ).hexdigest()
    proof: dict[str, object] = {
        "uses_llm": False,
        "uses_expected_answer": False,
        "uses_problem_specific_solver_logic": False,
        "source_checkpoint": str(checkpoint_path),
        "source_checkpoint_sha256": checkpoint_sha256,
        "admissible_factor_cover": {
            "branch_count": 1,
            "selected_branch_index": 0,
            "factorizations_replayed": True,
        },
        "linear_elimination": {"source_equation_count": 1},
        "singular_certificate": singular,
        "lifted_saturation_certificate": {
            "source_multipliers": ["1"],
            "replay_residual": "0",
            "replayed": True,
            "multiplier_source_proved_nonzero": True,
        },
        "strictly_accepted": True,
    }
    report_material = json.dumps(proof, ensure_ascii=False, sort_keys=True)
    proof["report_sha256"] = hashlib.sha256(report_material.encode()).hexdigest()
    proof_path = tmp_path / "singular-lift-proof.json"
    proof_file_sha256 = _write(proof_path, proof)
    run = tmp_path / "singular-lift-run.json"
    _write(
        run,
        {
            "problem_name": "singular-p",
            "solved": True,
            "certificate": {
                "source": "singular_lift_exact",
                "proof_sha256": proof["report_sha256"],
                "proof_path": str(proof_path),
                "proof_file_sha256": proof_file_sha256,
            },
        },
    )
    return proof_path, run, proof


def test_source_level_singular_lift_is_admitted(tmp_path: Path) -> None:
    _, run, _ = _singular_lift_fixture(tmp_path)

    audit = audit_geometry_artifact("singular_lift", run, root=tmp_path)

    assert audit.admitted is True
    assert audit.certificate_kind == "singular_lift_json"
    assert audit.reason == "replayed_source_level_singular_lift"


def test_source_level_singular_lift_rejects_failed_reverse_replay(
    tmp_path: Path,
) -> None:
    proof_path, run, proof = _singular_lift_fixture(tmp_path)
    lifted = proof["lifted_saturation_certificate"]
    assert isinstance(lifted, dict)
    lifted["replayed"] = False
    proof.pop("report_sha256")
    report_material = json.dumps(proof, ensure_ascii=False, sort_keys=True)
    proof["report_sha256"] = hashlib.sha256(report_material.encode()).hexdigest()
    proof_file_sha256 = _write(proof_path, proof)
    run_payload = json.loads(run.read_text(encoding="utf-8"))
    run_payload["certificate"]["proof_sha256"] = proof["report_sha256"]
    run_payload["certificate"]["proof_file_sha256"] = proof_file_sha256
    _write(run, run_payload)

    audit = audit_geometry_artifact("singular_lift", run, root=tmp_path)

    assert audit.admitted is False
    assert "lifted_replayed" in audit.reason


def test_new_exact_certificate_requires_linked_readable_solution(tmp_path: Path) -> None:
    proof = tmp_path / "modern-exact-proof.json"
    proof_hash = _write(
        proof,
        {
            "status": "proved",
            "certificate": {
                "exact_replay": True,
                "construction_consistency": "not_refuted_by_exact_constraints",
                "vacuous_unit_ideal": False,
                "remainder": "0",
                "groebner_basis": ["x"],
                "certificate_sha256": "modern",
                "local_lemma_certificates": [],
                "structural_lemma_certificates": [],
            },
        },
    )
    run = tmp_path / "modern-run.json"
    _write(
        run,
        {
            "problem_name": "modern",
            "solved": True,
            "certificate": {
                "source": "jgex_exact_elimination",
                "proof_sha256": "modern",
                "proof_path": str(proof),
                "proof_file_sha256": proof_hash,
            },
        },
    )

    audit = audit_geometry_artifact("jgex_exact", run, root=tmp_path)

    assert audit.admitted is False
    assert "solution_artifact" in audit.reason


@pytest.mark.parametrize(
    ("certificate_change", "expected_failure"),
    (
        ({"remainder": "1"}, "zero_remainder"),
        (
            {
                "structural_lemma_certificates": [
                    {
                        "replayed": True,
                        "composition_replayed": False,
                        "composition_certificate_sha256": "composition",
                        "replay_residuals": ["0", "0"],
                    }
                ]
            },
            "structural_lemma_replay",
        ),
    ),
)
def test_exact_certificate_rejects_incomplete_replay(
    tmp_path: Path,
    certificate_change: dict[str, object],
    expected_failure: str,
) -> None:
    exact_certificate: dict[str, object] = {
        "exact_replay": True,
        "remainder": "0",
        "certificate_sha256": "exact-certificate",
        "local_lemma_certificates": [],
        "structural_lemma_certificates": [],
    }
    exact_certificate.update(certificate_change)
    proof = tmp_path / "bad-exact-proof.json"
    proof_hash = _write(
        proof,
        {"status": "proved", "certificate": exact_certificate},
    )
    run = tmp_path / "bad-exact-run.json"
    _write(
        run,
        {
            "problem_name": "bad-exact-p",
            "solved": True,
            "certificate": {
                "source": "jgex_exact_elimination",
                "proof_sha256": "exact-certificate",
                "proof_path": str(proof),
                "proof_file_sha256": proof_hash,
            },
        },
    )

    audit = audit_geometry_artifact("jgex_exact", run, root=tmp_path)

    assert audit.admitted is False
    assert expected_failure in audit.reason


def test_unsolved_agent_does_not_erase_frozen_certified_solve(tmp_path: Path) -> None:
    run = tmp_path / "unsolved.json"
    _write(run, {"problem_name": "known", "solved": False})
    audit = audit_geometry_artifact("proof_dag", run, root=tmp_path)

    result = score_geometry_portfolio(
        ("known",),
        (audit,),
        baseline_names=("known",),
    )

    assert result["certified_solved"] == 1
    assert result["results"][0]["solved"] is True
    assert result["results"][0]["baseline_union"] is True


def test_diagnostic_ablation_cannot_be_reported_as_system_failure() -> None:
    ablation = {
        "records": [
            {
                "problem": "known",
                "native_baseline_solved": False,
                "goals": [
                    {
                        "control": {"solved_frontier": False},
                        "treatment": {"solved_frontier": False},
                    }
                ],
            }
        ]
    }
    portfolio = {
        "results": [{"problem": "known", "solved": True}],
    }

    assert diagnose_ablation_false_negatives(ablation, portfolio) == ["known"]


def test_rejects_answer_claim_without_a_replayed_certificate(tmp_path: Path) -> None:
    run = tmp_path / "claim.json"
    _write(run, {"problem_name": "p", "solved": True})

    audit = audit_geometry_artifact("agent", run, root=tmp_path)

    assert audit.admitted is False
    assert audit.reason == "solved_claim_has_no_certificate"


def test_loads_only_audited_capability_ledgers(tmp_path: Path) -> None:
    valid = tmp_path / "valid.json"
    _write(
        valid,
        {
            "protocol": {
                "truth_plane": "audited proof artifact with matching certificate file hash"
            },
            "summary": {"total": 3, "primary_certified_solved": 1},
            "sets": {"primary_union": ["p"]},
        },
    )
    assert load_certified_union(valid) == (3, frozenset({"p"}))

    invalid = tmp_path / "invalid.json"
    _write(
        invalid,
        {
            "protocol": {"truth_plane": "answer lookup"},
            "summary": {"total": 1},
            "sets": {"primary_union": ["p"]},
        },
    )
    with pytest.raises(ValueError, match="not a certified geometry union"):
        load_certified_union(invalid)
