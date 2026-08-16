from worker.backend.geometry_proof_hypergraph import Atom
from worker.backend.jgex_local_relation_stalk import (
    JGEXRelationStalkAdapter,
    extract_jgex_relation_stalk,
)
from worker.backend.symbolic_sheaf_coordination import (
    ExactSheafCoordinator,
    PredicateSignature,
    TypedVocabulary,
)


def test_on_aline_is_exchanged_as_a_typed_equal_angle_without_expansion() -> None:
    stalk = extract_jgex_relation_stalk(
        "a b c = triangle a b c; x = on_aline x a b b a c ? coll a b x"
    )
    assert stalk.relation_counts == {"eqangle": 1}
    certificate = stalk.certificates[0]
    assert certificate.replayed
    assert certificate.conclusions == (
        Atom("eqangle", ("a", "x", "a", "b", "a", "b", "a", "c")),
    )


def test_cc_tangent_intersection_hides_four_points_behind_one_boundary_atom() -> None:
    text = (
        "o a u = triangle o a u; w b v = triangle w b v; "
        "x y z i = cc_tangent x y z i o a w b; "
        "k = on_line k x y, on_line k z i ? coll o w k"
    )
    stalk = extract_jgex_relation_stalk(text)
    homothety = next(
        item
        for item in stalk.certificates
        if item.rule_name == "external_tangent_intersection_to_homothety"
    )
    assert homothety.hidden_points == ("x", "y", "z", "i")
    assert homothety.replayed
    assert homothety.native_kind == "polynomial_ideal_identity"

    all_atoms = (
        *stalk.source_atoms,
        *(
            conclusion
            for certificate in stalk.certificates
            for conclusion in certificate.conclusions
        ),
    )
    entities = {argument for atom in all_atoms for argument in atom.arguments}
    signatures = {
        atom.predicate: PredicateSignature(
            atom.predicate,
            ("Point",) * len(atom.arguments),
        )
        for atom in all_atoms
    }
    coordinator = ExactSheafCoordinator(
        TypedVocabulary(
            signatures=signatures,
            entity_sorts={entity: "Point" for entity in entities},
        ),
        (JGEXRelationStalkAdapter(stalk),),
    )
    result = coordinator.solve(
        stalk.source_atoms,
        homothety.conclusions[0],
    )
    assert result.solved
    assert result.replayed
    assert result.proof_slice()[0].native_payload["kind"] == "polynomial_ideal_identity"

    ratio = next(
        item.conclusions[0]
        for item in stalk.certificates
        if item.rule_name == "external_homothety_to_radius_ratio"
    )
    ratio_result = coordinator.solve(stalk.source_atoms, ratio)
    assert ratio_result.solved and ratio_result.replayed
    assert [item.rule_name for item in ratio_result.proof_slice()] == [
        "external_tangent_intersection_to_homothety",
        "external_homothety_to_radius_ratio",
    ]


def test_point_renaming_preserves_stalk_rule_shape() -> None:
    first = extract_jgex_relation_stalk(
        "a b c = triangle a b c; x = on_aline x a b b a c ? coll a b x"
    )
    second = extract_jgex_relation_stalk(
        "p q r = triangle p q r; y = on_aline y p q q p r ? coll p q y"
    )
    assert [item.rule_name for item in first.certificates] == [
        item.rule_name for item in second.certificates
    ]
    assert [len(item.conclusions[0].arguments) for item in first.certificates] == [
        len(item.conclusions[0].arguments) for item in second.certificates
    ]
