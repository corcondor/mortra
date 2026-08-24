from worker.backend.geometry_proof_hypergraph import Atom
from worker.backend.typed_relation_separator import (
    certify_typed_relation_separator,
)


SOURCE = (
    "a b c = triangle a b c; d = free d; e = free e; f = free f "
    "? cong a b e f"
)


def test_typed_congruence_chain_produces_replayable_separator_certificate() -> None:
    result = certify_typed_relation_separator(
        SOURCE,
        Atom("cong", ("a", "b", "e", "f")),
        (
            Atom("cong", ("a", "b", "c", "d")),
            Atom("cong", ("c", "d", "e", "f")),
        ),
        max_pairs=200,
        max_basis_size=64,
    )

    assert result.status == "proved"
    assert result.exact_replay
    assert result.macaulay_attempts[0].certificate.proved
    assert result.macaulay_attempts[0].certificate.replayed
    assert result.macaulay_attempts[0].certificate.multiplier_degree == 0


def test_unrelated_typed_fact_does_not_claim_a_proof() -> None:
    result = certify_typed_relation_separator(
        SOURCE,
        Atom("cong", ("a", "b", "e", "f")),
        (Atom("coll", ("a", "b", "c")),),
        max_pairs=50,
        max_basis_size=32,
    )

    assert result.status == "open"
    assert not result.exact_replay
    assert result.membership is None
    assert result.proof_dag is None


def test_nondegeneracy_saturation_is_explicit_and_replayed() -> None:
    result = certify_typed_relation_separator(
        (
            "a b c = triangle a b c; d = on_line d a b; "
            "e = on_line e a b ? coll a d e"
        ),
        Atom("coll", ("a", "d", "e")),
        (
            Atom("coll", ("a", "b", "d")),
            Atom("coll", ("a", "b", "e")),
        ),
        enable_local_projection=True,
    )

    accepted = next(
        item for item in result.macaulay_attempts if item.certificate.proved
    )
    assert result.exact_replay
    assert accepted.saturation_multiplier != "1"
    assert accepted.saturation_assumptions_used
    assert accepted.certificate.replay_residual == "0"
    assert result.local_elimination is not None
    assert result.local_elimination.exact_replay


def test_selection_is_invariant_to_native_fact_order() -> None:
    facts = (
        Atom("cong", ("a", "b", "c", "d")),
        Atom("cong", ("c", "d", "e", "f")),
        Atom("coll", ("a", "b", "c")),
    )
    forward = certify_typed_relation_separator(
        SOURCE,
        Atom("cong", ("a", "b", "e", "f")),
        facts,
    )
    reverse = certify_typed_relation_separator(
        SOURCE,
        Atom("cong", ("a", "b", "e", "f")),
        tuple(reversed(facts)),
    )

    assert forward.exact_replay and reverse.exact_replay
    assert forward.certificate_sha256 == reverse.certificate_sha256


def test_local_projection_is_opt_in_after_negative_frozen_ablation() -> None:
    result = certify_typed_relation_separator(
        (
            "a b c = triangle a b c; d = on_line d a b; "
            "e = on_line e a b ? coll a d e"
        ),
        Atom("coll", ("a", "d", "e")),
        (
            Atom("coll", ("a", "b", "d")),
            Atom("coll", ("a", "b", "e")),
        ),
    )

    assert result.status == "proved"
    assert result.local_elimination is None


def test_centered_circle_is_lowered_to_radius_congruences_with_provenance() -> None:
    result = certify_typed_relation_separator(
        (
            "o a b = triangle o a b; c = free c "
            "? cong o b o c"
        ),
        Atom("cong", ("o", "b", "o", "c")),
        (Atom("circle", ("o", "a", "b", "c")),),
    )

    assert result.status == "proved"
    assert result.exact_replay
    assert {
        premise.derivation for premise in result.selected_native_premises
    } == {"circle_radius_congruence"}
    assert {
        premise.source_atom for premise in result.selected_native_premises
    } == {"circle o a b c"}


def test_centered_circle_suppresses_redundant_cyclic_determinant() -> None:
    result = certify_typed_relation_separator(
        (
            "o a b = triangle o a b; c = free c; d = free d "
            "? cong o b o c"
        ),
        Atom("cong", ("o", "b", "o", "c")),
        (
            Atom("circle", ("o", "a", "b", "c")),
            Atom("circle", ("o", "a", "c", "d")),
            Atom("cyclic", ("a", "b", "c", "d")),
        ),
    )

    assert result.status == "proved"
    assert all(
        premise.predicate != "cyclic"
        for premise in result.selected_native_premises
    )


def test_tautological_congruence_is_not_selected() -> None:
    result = certify_typed_relation_separator(
        SOURCE,
        Atom("cong", ("a", "b", "e", "f")),
        (
            Atom("cong", ("a", "b", "a", "b")),
            Atom("coll", ("a", "b", "c")),
        ),
    )

    assert all(
        premise.atom != "cong a b a b"
        for premise in result.selected_native_premises
    )


def test_polynomially_equivalent_native_relations_are_quotiented() -> None:
    result = certify_typed_relation_separator(
        (
            "a b c = triangle a b c; d = on_line d a b "
            "? coll a b d"
        ),
        Atom("coll", ("a", "b", "d")),
        (
            Atom("coll", ("a", "b", "c")),
            Atom("para", ("a", "b", "a", "c")),
        ),
    )

    polynomials = [
        premise.polynomial for premise in result.selected_native_premises
    ]
    assert len(polynomials) == len(set(polynomials))
