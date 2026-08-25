"""Certificate-preserving evaluation across MORTRA geometry backends.

Search-policy ablations are diagnostics.  They must not erase a theorem that
another exact backend has already certified.  This module audits the native
certificate formats currently emitted by Yuclid/Newclid and GCLC/Wu, then
scores their set union together with the frozen certified capability ledger.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping


_CERTIFIED_TRUTH_PLANES = {
    "set union of audited native proof certificates",
    "audited proof artifact with matching certificate file hash",
}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve(root: Path, value: object) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else root / path


@dataclass(frozen=True)
class CertificateAudit:
    problem: str
    agent: str
    artifact: str
    claimed_solved: bool
    admitted: bool
    certificate_kind: str | None
    proof_path: str | None
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "problem": self.problem,
            "agent": self.agent,
            "artifact": self.artifact,
            "claimed_solved": self.claimed_solved,
            "admitted": self.admitted,
            "certificate_kind": self.certificate_kind,
            "proof_path": self.proof_path,
            "reason": self.reason,
        }


def load_certified_union(path: Path) -> tuple[int, frozenset[str]]:
    """Load a frozen capability ledger without accepting answer-only claims."""

    payload = _load(path)
    truth_plane = str(payload.get("protocol", {}).get("truth_plane", ""))
    if truth_plane not in _CERTIFIED_TRUTH_PLANES:
        raise ValueError(f"not a certified geometry union: {truth_plane!r}")
    names = frozenset(map(str, payload.get("sets", {}).get("primary_union", ())))
    total = int(payload.get("summary", {}).get("total", 0))
    if total <= 0 or len(names) > total:
        raise ValueError("certified union has an inconsistent total")
    reported = payload.get("summary", {}).get("primary_certified_solved")
    if reported is not None and int(reported) != len(names):
        raise ValueError("certified union count does not match primary_union")
    return total, names


def _audit_newclid_json(
    proof_path: Path,
    certificate: Mapping[str, Any],
) -> tuple[bool, str]:
    proof = _load(proof_path)
    if proof.get("status") != "solved":
        return False, "newclid_proof_status_is_not_solved"
    if not proof.get("deductions_for_goal"):
        return False, "newclid_proof_has_no_goal_deduction"
    source = str(certificate.get("source", ""))
    if source not in {
        "baseline",
        "search_attempt",
        "native_replay",
        "formalgeo_native_replay",
    }:
        return False, f"unsupported_newclid_certificate_source:{source}"
    return True, "replayed_newclid_certificate"


def _audit_exact_json(
    proof_path: Path,
    certificate: Mapping[str, Any],
) -> tuple[bool, str]:
    """Audit MORTRA's replayable exact-elimination certificate."""

    proof = _load(proof_path)
    if proof.get("status") != "proved":
        return False, "exact_proof_status_is_not_proved"
    exact = proof.get("certificate")
    if not isinstance(exact, Mapping):
        return False, "exact_proof_has_no_certificate"

    basis = tuple(map(str, exact.get("groebner_basis", ())))
    unit_ideal = basis in {("1",), ("-1",)}

    checks = {
        "exact_replay": exact.get("exact_replay") is True,
        "zero_remainder": str(exact.get("remainder", "")) == "0",
        "certificate_hash": (
            bool(exact.get("certificate_sha256"))
            and exact.get("certificate_sha256")
            == certificate.get("proof_sha256")
        ),
        "nonvacuous_construction": (
            not unit_ideal and exact.get("vacuous_unit_ideal") is not True
        ),
    }

    local_lemmas = exact.get("local_lemma_certificates", ())
    if not isinstance(local_lemmas, list):
        checks["local_lemma_shape"] = False
    else:
        checks["local_lemma_replay"] = all(
            isinstance(item, Mapping)
            and item.get("replayed") is True
            and str(item.get("forward_residual", "")) == "0"
            and str(item.get("reverse_residual", "")) == "0"
            for item in local_lemmas
        )

    structural_lemmas = exact.get("structural_lemma_certificates", ())
    if not isinstance(structural_lemmas, list):
        checks["structural_lemma_shape"] = False
    else:
        checks["structural_lemma_replay"] = all(
            isinstance(item, Mapping)
            and item.get("replayed") is True
            and item.get("composition_replayed") is True
            and bool(item.get("composition_certificate_sha256"))
            and all(
                str(residual) == "0"
                for residual in item.get("replay_residuals", ())
            )
            for item in structural_lemmas
        )

    local_elimination = exact.get("local_elimination")
    if isinstance(local_elimination, Mapping):
        checks["local_elimination_replay"] = (
            local_elimination.get("exact_replay") is True
        )

    transports = exact.get("nonzero_condition_transports", [])
    if not isinstance(transports, list):
        checks["nonzero_condition_transport_shape"] = False
    else:
        checks["nonzero_condition_transport_replay"] = all(
            isinstance(item, Mapping)
            and item.get("replayed") is True
            and str(item.get("replay_residual", "")) == "0"
            and bool(item.get("source_polynomial"))
            and bool(item.get("target_polynomial"))
            and bool(item.get("pivot_coefficient"))
            and bool(item.get("certificate_sha256"))
            for item in transports
        )

    # Certificates emitted after the consistency audit must carry their own
    # human-readable solution projection.  The text is not an independent
    # proof, but its certificate hash guarantees that every displayed step is
    # tied to the replayed machine certificate.
    if "construction_consistency" in exact:
        solution = proof.get("solution")
        checks["solution_artifact"] = (
            isinstance(solution, Mapping)
            and solution.get("status") == "verified"
            and solution.get("certificate_sha256")
            == exact.get("certificate_sha256")
            and bool(solution.get("solution_sha256"))
            and isinstance(solution.get("steps"), list)
            and len(solution.get("steps", ())) >= 2
        )

    failed = sorted(name for name, ok in checks.items() if not ok)
    if failed:
        return False, "exact_certificate_failed:" + ",".join(failed)
    source = str(certificate.get("source", ""))
    if source not in {"jgex_exact_elimination", "baseline_jgex_exact"}:
        return False, f"unsupported_exact_certificate_source:{source}"
    return True, "replayed_jgex_exact_certificate"


def _audit_exact_chart_json(
    proof_path: Path,
    certificate: Mapping[str, Any],
) -> tuple[bool, str]:
    """Audit a structural exact-chart proof and its application replay."""

    proof = _load(proof_path)
    selected = proof.get("selected")
    if not isinstance(selected, Mapping):
        return False, "exact_chart_has_no_selected_proof"
    chart = selected.get("certificate")
    application = selected.get("application")
    if not isinstance(chart, Mapping) or not isinstance(application, Mapping):
        return False, "exact_chart_has_no_replay_payload"
    residuals = chart.get("replay_residuals")
    if not isinstance(residuals, Mapping):
        return False, "exact_chart_has_no_residual_map"

    chart_hash = str(chart.get("certificate_sha256", ""))
    checks = {
        "portfolio_solved": proof.get("solved") is True,
        "portfolio_not_conditional": proof.get("conditional") is False,
        "portfolio_not_ambiguous": proof.get("ambiguous") is False,
        "selected_proved": selected.get("proof_status") == "proved",
        "no_undischarged_obligations": not selected.get(
            "undischarged_obligations", ()
        ),
        "chart_replayed": chart.get("replayed") is True,
        "chart_domain_discharged": chart.get("all_conditions_discharged") is True,
        "nonempty_zero_residuals": bool(residuals)
        and all(str(value) == "0" for value in residuals.values()),
        "application_replayed": application.get("replayed") is True,
        "application_domain_discharged": not application.get(
            "undischarged_nondegeneracy_obligations", ()
        ),
        "certificate_hash_chain": bool(chart_hash)
        and selected.get("chart_certificate_sha256") == chart_hash
        and application.get("chart_certificate_sha256") == chart_hash
        and certificate.get("proof_sha256") == chart_hash,
        "source_hash_chain": bool(proof.get("source_sha256"))
        and selected.get("source_sha256") == proof.get("source_sha256")
        and application.get("source_sha256") == proof.get("source_sha256")
        and certificate.get("input_sha256") == proof.get("source_sha256"),
        "theorem_chain": bool(selected.get("theorem"))
        and selected.get("theorem") == chart.get("theorem")
        and selected.get("theorem") == application.get("theorem"),
    }
    failed = sorted(name for name, ok in checks.items() if not ok)
    if failed:
        return False, "exact_chart_failed:" + ",".join(failed)
    if str(certificate.get("source", "")) != "jgex_exact_chart":
        return False, "unsupported_exact_chart_certificate_source"
    return True, "replayed_jgex_exact_chart_certificate"


def _audit_singular_lift_json(
    root: Path,
    proof_path: Path,
    certificate: Mapping[str, Any],
) -> tuple[bool, str]:
    """Audit a source-level bounded Singular lift and its terminal checkpoint."""

    proof = _load(proof_path)
    singular = proof.get("singular_certificate")
    lifted = proof.get("lifted_saturation_certificate")
    if not isinstance(singular, Mapping) or not isinstance(lifted, Mapping):
        return False, "singular_lift_has_no_certificate"

    report_copy = dict(proof)
    report_sha256 = str(report_copy.pop("report_sha256", ""))
    report_material = json.dumps(report_copy, ensure_ascii=False, sort_keys=True)
    observed_report_sha256 = hashlib.sha256(report_material.encode()).hexdigest()

    checkpoint_path = _resolve(root, proof.get("source_checkpoint", ""))
    checkpoint: Mapping[str, Any] = {}
    checkpoint_sha256 = ""
    if checkpoint_path.is_file():
        checkpoint = _load(checkpoint_path)
        checkpoint_material = "\n".join(
            (
                "terminal_groebner_system_v1",
                *map(str, checkpoint.get("input_polynomials", ())),
                "variables=" + ",".join(map(str, checkpoint.get("variables", ()))),
                "coefficient_parameters="
                + ",".join(map(str, checkpoint.get("coefficient_parameters", ()))),
                "coefficient_domain=" + str(checkpoint.get("coefficient_domain", "")),
                "goal=" + str(checkpoint.get("goal_polynomial", "")),
                *map(str, checkpoint.get("nonzero_conditions", ())),
            )
        )
        checkpoint_sha256 = hashlib.sha256(checkpoint_material.encode()).hexdigest()

    singular_material = "|".join(
        (
            str(singular.get("basis_engine", "")),
            str(singular.get("certificate_degree", "")),
            *map(str, singular.get("initial_polynomials", ())),
            str(singular.get("goal_polynomial", "")),
            *map(str, singular.get("initial_multipliers", ())),
            str(singular.get("replay_residual", "")),
        )
    )
    observed_singular_sha256 = hashlib.sha256(singular_material.encode()).hexdigest()
    factor_cover = proof.get("admissible_factor_cover", {})
    checks = {
        "report_hash": bool(report_sha256)
        and report_sha256 == observed_report_sha256
        and report_sha256 == certificate.get("proof_sha256"),
        "source_checkpoint": checkpoint_path.is_file(),
        "source_checkpoint_hash": bool(checkpoint_sha256)
        and checkpoint_sha256 == checkpoint.get("certificate_sha256")
        and checkpoint_sha256 == proof.get("source_checkpoint_sha256"),
        "no_external_llm": proof.get("uses_llm") is False,
        "no_expected_answer": proof.get("uses_expected_answer") is False,
        "no_problem_specific_logic": (
            proof.get("uses_problem_specific_solver_logic") is False
        ),
        "single_admissible_factor_branch": (
            factor_cover.get("branch_count") == 1
            and factor_cover.get("selected_branch_index") == 0
            and factor_cover.get("factorizations_replayed") is True
        ),
        "bounded_linear_engine": singular.get("basis_engine") == "bounded_linear",
        "positive_certificate_degree": int(singular.get("certificate_degree") or 0) > 0,
        "singular_status": singular.get("status") == "proved",
        "singular_proved": singular.get("proved") is True,
        "singular_replayed": singular.get("replayed") is True,
        "singular_zero_remainder": str(singular.get("remainder", "")) == "0",
        "singular_zero_replay_residual": (
            str(singular.get("replay_residual", "")) == "0"
        ),
        "singular_certificate_hash": (
            bool(singular.get("certificate_sha256"))
            and singular.get("certificate_sha256") == observed_singular_sha256
        ),
        "multiplier_arity": len(singular.get("initial_multipliers", ()))
        == len(singular.get("initial_polynomials", ()))
        > 0,
        "source_multiplier_arity": len(lifted.get("source_multipliers", ()))
        == int(proof.get("linear_elimination", {}).get("source_equation_count", 0))
        > 0,
        "lifted_replayed": lifted.get("replayed") is True,
        "lifted_zero_residual": str(lifted.get("replay_residual", "")) == "0",
        "nonzero_multiplier_proved": (
            lifted.get("multiplier_source_proved_nonzero") is True
        ),
        "strict_acceptance": proof.get("strictly_accepted") is True,
    }
    failed = sorted(name for name, ok in checks.items() if not ok)
    if failed:
        return False, "singular_lift_failed:" + ",".join(failed)
    if str(certificate.get("source", "")) != "singular_lift_exact":
        return False, "unsupported_singular_lift_certificate_source"
    return True, "replayed_source_level_singular_lift"


def _audit_gclc_tex(
    root: Path,
    proof_path: Path,
    certificate: Mapping[str, Any],
) -> tuple[bool, str]:
    metadata_value = certificate.get("metadata_path")
    if not metadata_value:
        return False, "gclc_certificate_has_no_metadata"
    metadata_path = _resolve(root, metadata_value)
    if not metadata_path.is_file():
        return False, "gclc_metadata_is_missing"
    metadata = _load(metadata_path)
    run = metadata.get("run") or {}
    observed = _sha256(proof_path)
    checks = {
        "status": metadata.get("status") == "proved",
        "proved": run.get("proved") is True,
        "return_code": run.get("return_code") == 0,
        "metadata_proof_hash": metadata.get("proof_file_sha256") == observed,
        "run_proof_hash": run.get("proof_sha256") == observed,
        "certificate_proof_hash": certificate.get("proof_sha256") == observed,
        "input_hash": metadata.get("input_sha256") == certificate.get("input_sha256"),
    }
    failed = sorted(name for name, ok in checks.items() if not ok)
    if failed:
        return False, "gclc_certificate_failed:" + ",".join(failed)
    source = str(certificate.get("source", ""))
    if source not in {"baseline_gclc_wu", "gclc_wu", "gclc_wu_replay"}:
        return False, f"unsupported_gclc_certificate_source:{source}"
    return True, "replayed_gclc_wu_certificate"


def audit_geometry_artifact(
    agent: str,
    artifact_path: Path,
    *,
    root: Path,
) -> CertificateAudit:
    """Audit one direct backend artifact against its native proof file."""

    artifact_path = artifact_path.resolve()
    payload = _load(artifact_path)
    problem = str(payload.get("problem_name") or artifact_path.stem)
    claimed_solved = bool(payload.get("solved"))
    relative_artifact = (
        artifact_path.relative_to(root).as_posix()
        if artifact_path.is_relative_to(root)
        else artifact_path.as_posix()
    )
    if not claimed_solved:
        return CertificateAudit(
            problem,
            agent,
            relative_artifact,
            False,
            False,
            None,
            None,
            "backend_reported_unsolved",
        )
    certificate = payload.get("certificate")
    if not isinstance(certificate, Mapping):
        return CertificateAudit(
            problem,
            agent,
            relative_artifact,
            True,
            False,
            None,
            None,
            "solved_claim_has_no_certificate",
        )
    proof_value = certificate.get("proof_path")
    if not proof_value:
        return CertificateAudit(
            problem,
            agent,
            relative_artifact,
            True,
            False,
            None,
            None,
            "certificate_has_no_proof_path",
        )
    proof_path = _resolve(root, proof_value)
    display_proof = (
        proof_path.relative_to(root).as_posix()
        if proof_path.is_relative_to(root)
        else proof_path.as_posix()
    )
    if not proof_path.is_file():
        return CertificateAudit(
            problem,
            agent,
            relative_artifact,
            True,
            False,
            None,
            display_proof,
            "certificate_proof_file_is_missing",
        )
    observed_hash = _sha256(proof_path)
    if observed_hash != str(certificate.get("proof_file_sha256", "")):
        return CertificateAudit(
            problem,
            agent,
            relative_artifact,
            True,
            False,
            None,
            display_proof,
            "certificate_proof_hash_mismatch",
        )

    suffix = proof_path.suffix.lower()
    if suffix == ".json":
        proof_payload = _load(proof_path)
        if proof_payload.get("solved") is True and isinstance(
            proof_payload.get("selected"), Mapping
        ):
            admitted, reason = _audit_exact_chart_json(proof_path, certificate)
            kind = "jgex_exact_chart_json"
        elif proof_payload.get("strictly_accepted") is True and isinstance(
            proof_payload.get("singular_certificate"), Mapping
        ):
            admitted, reason = _audit_singular_lift_json(
                root, proof_path, certificate
            )
            kind = "singular_lift_json"
        elif proof_payload.get("status") == "proved" and isinstance(
            proof_payload.get("certificate"), Mapping
        ):
            admitted, reason = _audit_exact_json(proof_path, certificate)
            kind = "jgex_exact_json"
        else:
            admitted, reason = _audit_newclid_json(proof_path, certificate)
            kind = "newclid_json"
    elif suffix == ".tex":
        admitted, reason = _audit_gclc_tex(root, proof_path, certificate)
        kind = "gclc_wu_tex"
    else:
        admitted, reason = False, f"unsupported_proof_format:{suffix}"
        kind = None
    return CertificateAudit(
        problem,
        agent,
        relative_artifact,
        True,
        admitted,
        kind,
        display_proof,
        reason,
    )


def score_geometry_portfolio(
    problem_names: Iterable[str],
    audits: Iterable[CertificateAudit],
    *,
    baseline_names: Iterable[str] = (),
) -> dict[str, object]:
    """Score the union; a failed specialist can never erase another proof."""

    problems = tuple(dict.fromkeys(map(str, problem_names)))
    baseline = frozenset(map(str, baseline_names))
    rows = tuple(audits)
    results: list[dict[str, object]] = []
    for problem in problems:
        admitted_agents = sorted(
            {row.agent for row in rows if row.problem == problem and row.admitted}
        )
        baseline_admitted = problem in baseline
        results.append(
            {
                "problem": problem,
                "solved": baseline_admitted or bool(admitted_agents),
                "baseline_union": baseline_admitted,
                "admitted_agents": admitted_agents,
                "rejected_claims": sorted(
                    {
                        row.agent
                        for row in rows
                        if row.problem == problem
                        and row.claimed_solved
                        and not row.admitted
                    }
                ),
            }
        )
    solved = sum(bool(row["solved"]) for row in results)
    return {
        "total": len(results),
        "certified_solved": solved,
        "certified_score": solved / len(results) if results else None,
        "results": results,
    }


def diagnose_ablation_false_negatives(
    ablation: Mapping[str, Any],
    portfolio: Mapping[str, Any],
) -> list[str]:
    """Find certified solves hidden by a setup-only diagnostic ablation."""

    portfolio_solved = {
        str(row["problem"])
        for row in portfolio.get("results", ())
        if row.get("solved")
    }
    diagnostic_unsolved = {
        str(record["problem"])
        for record in ablation.get("records", ())
        if not record.get("native_baseline_solved")
        and not any(
            goal.get("control", {}).get("solved_frontier")
            or goal.get("treatment", {}).get("solved_frontier")
            for goal in record.get("goals", ())
        )
    }
    return sorted(portfolio_solved & diagnostic_unsolved)
