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
        "coordination_plane": {
            "method": "differentiable_heterogeneous_sheaf_admm",
            "variables": ["x_local", "z_consensus", "u_disagreement"],
            "learned_values": ["positive_agent_trust", "rho"],
            "authority": "search priority and budget only",
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
