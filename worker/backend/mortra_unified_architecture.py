"""Auditable contract for MORTRA's unified exact/differentiable architecture.

This module is deliberately declarative.  It prevents experiment artifacts
from describing HAGeo proposal, formal-language agents, differentiable
coordination, certificate replay, and hardware acceleration as unrelated
features.  Acceleration targets are execution backends, never truth sources.
"""

from __future__ import annotations

from typing import Any


SCHEMA = "mortra-unified-symbolic-geometry-v1"


def unified_geometry_architecture_manifest() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "knowledge_plane": {
            "method": "openmath_terms_over_mmt_theory_graph",
            "object_level": "typed terms and applications",
            "statement_level": "proof obligations and replayable certificates",
            "theory_level": "interface theories and meaning-preserving views",
            "native_languages_remain_distinct": True,
        },
        "proposal_plane": {
            "agents": [
                "hageo_numerical_incidence",
                "tong_typed_construction",
            ],
            "contract": "typed construction candidates only",
        },
        "local_formal_languages": [
            "newclid_dd_relation_closure",
            "newclid_typed_relation_transition",
            "newclid_ar_residual",
            "gclc_wu_polynomial_obligation",
            "sygus_typed_open_obligation",
            "proof_circuit_execution_cost",
        ],
        "interface_theory_views": {
            "hageo_numerical_incidence": "geometry_construction_and_relation_symbols",
            "tong_typed_construction": "geometry_construction_symbols",
            "newclid_dd_relation_closure": "euclidean_relation_symbols",
            "gclc_wu_polynomial_obligation": "polynomialized_relation_symbols",
        },
        "certificate_exchange": {
            "method": "verify_native_then_push_to_mmt_then_pull_to_recipient",
            "native_certificate_is_preserved": True,
            "numerical_proposals_are_not_truth": True,
        },
        "coordination_plane": {
            "active_method": "exact_mmt_certificate_exchange",
            "experimental_method": "typed_symbolic_sheaf_admm",
            "variables": ["x_local", "z_consensus", "u_disagreement"],
            "learned_values": ["positive_agent_trust", "rho"],
            "authority": "search priority and budget only",
            "enabled_in_default_scoring": False,
            "evidence_state": "no_additional_certified_solve_on_frozen_ablation",
        },
        "truth_plane": {
            "method": "typed_native_certificate_replay",
            "accepts_priority_without_certificate": False,
        },
        "capability_preservation": {
            "method": "full_exact_agent_plus_coordinated_agents_certificate_union",
            "half_beam_is_not_full_capability_preservation": True,
        },
        "execution_plane": {
            "risc_v": [
                "typed instruction scheduling",
                "nondegeneracy branch control",
                "certificate replay orchestration",
            ],
            "fpga": [
                "sparse restriction and coboundary products",
                "fixed point ADMM updates",
                "bitset relation closure",
                "bounded polynomial microkernels",
            ],
            "changes_mathematical_truth": False,
        },
    }


def validate_unified_geometry_architecture(manifest: dict[str, Any]) -> None:
    if manifest.get("schema") != SCHEMA:
        raise ValueError("unsupported unified architecture schema")
    truth = manifest.get("truth_plane", {})
    if truth.get("accepts_priority_without_certificate") is not False:
        raise ValueError("control-plane priority must not bypass certificate replay")
    execution = manifest.get("execution_plane", {})
    if execution.get("changes_mathematical_truth") is not False:
        raise ValueError("hardware acceleration must preserve proof semantics")
    preservation = manifest.get("capability_preservation", {})
    if preservation.get("half_beam_is_not_full_capability_preservation") is not True:
        raise ValueError("the architecture must disclose half-beam capability loss")
    knowledge = manifest.get("knowledge_plane", {})
    if knowledge.get("native_languages_remain_distinct") is not True:
        raise ValueError("MMT views must not erase native formal-language semantics")
    coordination = manifest.get("coordination_plane", {})
    if coordination.get("enabled_in_default_scoring") is not False:
        raise ValueError(
            "experimental coordination needs a frozen score gain before default enablement"
        )
