from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from scripts.experiment_hageo_passk import (
    _contract_diverse_shortlist,
    _is_circular_goal_transport,
    _reelaborated_relation_atoms,
    _run_reelaborated_relation_exchange,
)
from scripts.experiment_newclid_construction_stalk import (
    ConstructionStep,
    construction_path_from_payload,
    construction_path_to_payload,
    construction_requirement_atoms,
    write_json_atomic,
)
from worker.backend.geometry_proof_hypergraph import (
    Atom,
    euclidean_relation_theorems,
)
from worker.backend.construction_block_proof_dag import (
    certify_construction_block_proof_dag,
)
from worker.backend.jgex_exact_constraint_bridge import (
    inspect_jgex_relation_polynomials,
)
from newclid.jgex.formulation import JGEXFormulation


def test_atomic_checkpoint_retries_transient_windows_lock(
    tmp_path: Path, monkeypatch,
) -> None:
    target = tmp_path / "progress.json"
    original_replace = Path.replace
    attempts = 0

    def flaky_replace(source: Path, destination: Path) -> Path:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise PermissionError("transient reader lock")
        return original_replace(source, destination)

    monkeypatch.setattr(Path, "replace", flaky_replace)

    write_json_atomic(target, {"stage": "candidate_verification"})

    assert attempts == 3
    assert json.loads(target.read_text(encoding="utf-8")) == {
        "stage": "candidate_verification"
    }


def test_enumerated_construction_path_survives_checkpoint_roundtrip() -> None:
    path = (
        ConstructionStep("midpoint", "g", ("a", "b")),
        ConstructionStep("circle", "h", ("g", "a", "c")),
    )

    restored = construction_path_from_payload(construction_path_to_payload(path))

    assert restored == path


def test_reversible_parallel_transport_is_not_proof_progress() -> None:
    assert _is_circular_goal_transport(
        (Atom("para", ("a", "g", "i", "o")),),
        ((Atom("perp", ("a", "g", "m", "n")),),),
        (Atom("perp", ("i", "o", "m", "n")),),
        euclidean_relation_theorems(),
    )


def test_unrelated_residual_is_not_mislabeled_as_circular() -> None:
    assert not _is_circular_goal_transport(
        (Atom("para", ("a", "g", "i", "o")),),
        ((Atom("cyclic", ("a", "g", "m", "n")),),),
        (Atom("perp", ("i", "o", "m", "n")),),
        euclidean_relation_theorems(),
    )


def test_contract_shortlist_reserves_distinct_relation_channels() -> None:
    pool = [
        ConstructionStep("on_pline", "g", ("a", "i", "o")),
        ConstructionStep("midpoint", "g", ("i", "a")),
        ConstructionStep("on_tline", "g", ("a", "m", "n")),
    ]
    obligations = (
        Atom("para", ("?C", "?D", "i", "o")),
        Atom("perp", ("?C", "?D", "m", "n")),
    )

    selected = _contract_diverse_shortlist(pool, obligations, count=2)

    assert [candidate.family for _, candidate in selected] == [
        "on_pline",
        "on_tline",
    ]


def test_jgex_construction_requirements_are_exposed_as_typed_atoms() -> None:
    assert construction_requirement_atoms(
        "on_line", "x", ("a", "b")
    ) == (Atom("diff", ("a", "b")),)
    assert construction_requirement_atoms(
        "intersection_ll", "x", ("a", "b", "c", "d")
    ) == (
        Atom("npara", ("a", "b", "c", "d")),
        Atom("ncoll", ("a", "b", "c", "d")),
    )


def test_replayed_polynomial_relation_crosses_the_worker_boundary() -> None:
    source = "a b c = triangle a b c; m = midpoint m a b ? coll a m b"
    certificate = certify_construction_block_proof_dag(source)

    recovered = _reelaborated_relation_atoms(
        JGEXFormulation.from_text(source),
        asdict(certificate),
    )

    assert any(
        atom.predicate == "coll" and set(atom.arguments) == {"a", "b", "m"}
        for atom, _, _ in recovered
    )


def test_open_obligation_drives_polynomial_relation_exchange() -> None:
    source = "a b c = triangle a b c; m = midpoint m a b ? coll a m b"
    formulation = JGEXFormulation.from_text(source)
    goal = Atom("coll", ("a", "m", "b")).canonical()
    polynomial = inspect_jgex_relation_polynomials(
        source,
        ((goal.predicate, goal.arguments),),
        representation="relational",
    )[0].polynomial
    # Deliberately omit precomputed typed certificates. The exchange must
    # recover the atom from the currently open obligation itself.
    exact_result = {
        "certificate": {
            "local_elimination_nodes": [
                {
                    "node_id": "local:test",
                    "replayed": True,
                    "output_polynomials": [polynomial],
                    "relation_certificates": [],
                }
            ],
            "separator_nodes": [],
            "root": {
                "node_id": "root",
                "remaining_polynomials": [],
                "relation_certificates": [],
            },
            "all_local_certificates_replayed": True,
        }
    }

    result = _run_reelaborated_relation_exchange(
        formulation,
        exact_result=exact_result,
        native_facts=(),
        goal_atoms=(goal,),
        rule_theorems=euclidean_relation_theorems(),
        obligation_branches=((goal,),),
    )

    assert result["solved"] is True
    assert result["targeted_obligation_lemmas"] == 1
    assert result["certified_lemmas"] == 1


def test_relation_exchange_skips_native_reproof_without_certificate() -> None:
    source = "a b c = triangle a b c ? coll a b c"
    formulation = JGEXFormulation.from_text(source)
    goal = Atom("coll", ("a", "b", "c")).canonical()

    result = _run_reelaborated_relation_exchange(
        formulation,
        exact_result={"status": "disabled"},
        native_facts=(Atom("diff", ("a", "b")),),
        goal_atoms=(goal,),
        rule_theorems=euclidean_relation_theorems(),
        obligation_branches=((goal,),),
    )

    assert result["status"] == "no_certified_relations"
    assert result["solved"] is False
    assert result["certified_lemmas"] == 0
    assert result["hypergraph_proofs"] == []


def test_typed_holes_are_grounded_before_polynomial_exchange() -> None:
    source = (
        "a c e = triangle a c e; f = free f; p = free p; q = free q "
        "? perp a c p q"
    )
    formulation = JGEXFormulation.from_text(source)
    hidden = Atom("perp", ("e", "f", "a", "c")).canonical()
    goal = Atom("perp", ("a", "c", "p", "q")).canonical()
    polynomial = inspect_jgex_relation_polynomials(
        source,
        ((hidden.predicate, hidden.arguments),),
        representation="relational",
    )[0].polynomial
    exact_result = {
        "certificate": {
            "local_elimination_nodes": [
                {
                    "node_id": "local:hole",
                    "replayed": True,
                    "output_polynomials": [polynomial],
                    "typed_relation_certificates": [],
                }
            ],
            "separator_nodes": [],
            "root": {"remaining_polynomials": []},
            "all_local_certificates_replayed": True,
        }
    }

    result = _run_reelaborated_relation_exchange(
        formulation,
        exact_result=exact_result,
        native_facts=(),
        goal_atoms=(goal,),
        rule_theorems=euclidean_relation_theorems(),
        obligation_branches=((Atom("perp", ("?C", "?D", "a", "c")),),),
    )

    assert result["hole_candidate_count"] > 0
    assert result["targeted_obligation_lemmas"] >= 1
    assert any(item["atom"] == "perp(a,c,e,f)" for item in result["atoms"])
