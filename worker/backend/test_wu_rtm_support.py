from dataclasses import asdict

import sympy as sp

from worker.backend.wu_ritt_characteristic import certified_wu_ritt_goal_proof
from worker.backend.wu_rtm_support import audit_wu_rtm_support


def test_rtm_support_excludes_an_independent_hypothesis_from_goal_core() -> None:
    x, y, z, w = sp.symbols("x y z w")
    proof = certified_wu_ritt_goal_proof(
        (x - y, y - z, w - 1),
        (w, z, y, x),
        x - z,
        basic_set_mode="weak",
    )
    audit = audit_wu_rtm_support(proof)

    assert proof.conditional_goal_proved
    assert audit.all_references_resolved
    assert audit.all_certificates_replayed
    assert audit.goal_support_width < audit.hypothesis_count
    assert 2 not in audit.goal_support_indices
    goal_obligations = tuple(
        item for item in audit.local_obligations if item.phase == "goal"
    )
    assert all(
        set(item.direct_hypothesis_indices).issubset(item.hypothesis_indices)
        for item in goal_obligations
    )


def test_rtm_support_mapping_roundtrip_matches_dataclass() -> None:
    x, y = sp.symbols("x y")
    proof = certified_wu_ritt_goal_proof(
        (x - y, y - 1),
        (x, y),
        x - 1,
        basic_set_mode="weak",
    )

    assert audit_wu_rtm_support(proof) == audit_wu_rtm_support(asdict(proof))
