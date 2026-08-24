import sympy as sp
import pytest
from dataclasses import asdict

from worker.backend.geometry_proof_hypergraph import Atom
from worker.backend.jgex_exact_constraint_bridge import (
    inspect_jgex_relation_polynomials,
)
from worker.backend.polynomial_relation_reelaborator import (
    certify_polynomial_ideal_relations,
    certified_atoms,
    reelaborate_polynomial_lemmas,
    verify_typed_relation_ideal_certificate,
    verify_typed_relation_certificate,
)


def _polynomial(
    text: str,
    predicate: str,
    arguments: tuple[str, ...],
) -> str:
    return inspect_jgex_relation_polynomials(
        text,
        ((predicate, arguments),),
        representation="relational",
    )[0].polynomial


def test_forward_replay_recovers_a_typed_collinearity_atom() -> None:
    text = "a b c = triangle a b c; m = midpoint m a b ? coll a m b"
    lemma = _polynomial(text, "coll", ("a", "m", "b"))

    result = reelaborate_polynomial_lemmas(
        text,
        (lemma,),
        include_high_arity=False,
    )[0]

    assert result.status == "reelaborated"
    assert any(
        atom.predicate == "coll" and set(atom.arguments) == {"a", "b", "m"}
        for atom in certified_atoms((result,))
    )
    assert all(item.exact_replay for item in result.certificates)
    assert all(len(item.certificate_sha256) == 64 for item in result.certificates)
    certificate = result.certificates[0]
    assert verify_typed_relation_certificate(text, certificate)
    tampered = {**asdict(certificate), "predicate": "perp"}
    assert not verify_typed_relation_certificate(text, tampered)
    tampered_conditions = {
        **asdict(certificate),
        "nonzero_conditions": (*certificate.nonzero_conditions, "x != 0"),
    }
    assert not verify_typed_relation_certificate(text, tampered_conditions)


def test_a_pure_power_preserves_the_same_zero_relation() -> None:
    text = "a b c = triangle a b c; m = midpoint m a b ? coll a m b"
    lemma = sp.sstr(sp.expand(sp.sympify(_polynomial(text, "coll", ("a", "m", "b"))) ** 2))

    result = reelaborate_polynomial_lemmas(
        text,
        (lemma,),
        include_high_arity=False,
    )[0]

    assert any(
        item.predicate == "coll" and item.equivalence_mode == "radical_associate"
        for item in result.certificates
    )


def test_a_product_of_distinct_factors_is_not_split_into_a_false_atom() -> None:
    text = (
        "a = free a; b = free b; c = free c; d = free d "
        "? coll a b c"
    )
    first = sp.sympify(_polynomial(text, "coll", ("a", "b", "c")))
    second = sp.sympify(_polynomial(text, "perp", ("a", "b", "c", "d")))
    product = sp.sstr(sp.expand(first * second))

    result = reelaborate_polynomial_lemmas(
        text,
        (product,),
        include_high_arity=False,
    )[0]

    assert result.status == "no_exact_typed_match"
    assert result.certificates == ()


def test_demand_directed_reelaboration_only_checks_open_typed_atoms() -> None:
    text = "a b c = triangle a b c; m = midpoint m a b ? coll a m b"
    demanded = (
        # The high-arity atom exercises the same demand path used for open
        # eqangle obligations without enumerating every 8-point relation.
        Atom("eqangle", ("a", "b", "a", "c", "a", "m", "b", "m")),
        Atom("coll", ("a", "m", "b")),
    )

    result = reelaborate_polynomial_lemmas(
        text,
        (_polynomial(text, "coll", ("a", "m", "b")),),
        max_points=8,
        max_candidates_per_lemma=len(demanded),
        include_high_arity=True,
        candidate_atoms=demanded,
    )[0]

    assert result.candidates_considered == 2
    assert {item.predicate for item in result.certificates} == {"coll"}


def test_newclid_squared_length_equation_reelaborates_as_typed_relation() -> None:
    text = "a b c = triangle a b c; d = free d ? perp a b c d"
    perpendicular = _polynomial(text, "perp", ("a", "b", "c", "d"))
    pythagoras = Atom(
        "lequation",
        (
            "1/1", "a", "c", "*", "a", "c",
            "1/1", "b", "d", "*", "b", "d",
            "-1/1", "a", "d", "*", "a", "d",
            "-1/1", "b", "c", "*", "b", "c", "0",
        ),
    )

    result = reelaborate_polynomial_lemmas(
        text,
        (perpendicular,),
        max_points=8,
        max_candidates_per_lemma=1,
        include_high_arity=True,
        candidate_atoms=(pythagoras,),
    )[0]

    assert result.candidates_considered == 1
    assert [item.predicate for item in result.certificates] == ["lequation"]
    assert verify_typed_relation_certificate(text, result.certificates[0])


def test_odd_length_power_is_rejected_without_branch_assumption() -> None:
    text = "a b c = triangle a b c ? cong a b a c"
    with pytest.raises(ValueError, match="odd length power"):
        inspect_jgex_relation_polynomials(
            text,
            (("lequation", ("1/1", "a", "b", "-1/1", "a", "c", "0")),),
            representation="relational",
        )


def test_nonpolynomial_length_candidate_does_not_abort_other_demands() -> None:
    text = "a b c = triangle a b c; m = midpoint m a b ? coll a m b"
    result = reelaborate_polynomial_lemmas(
        text,
        (_polynomial(text, "coll", ("a", "m", "b")),),
        candidate_atoms=(
            Atom("lequation", ("1/1", "a", "b", "-1/1", "a", "c", "0")),
            Atom("coll", ("a", "m", "b")),
        ),
    )[0]

    assert {item.predicate for item in result.certificates} == {"coll"}


def test_relation_is_recovered_from_a_replayed_lemma_ideal() -> None:
    text = "a b c = triangle a b c; d = free d ? perp a b c d"
    target = sp.expand(sp.sympify(_polynomial(text, "perp", ("a", "b", "c", "d"))))
    terms = sp.Add.make_args(target)
    generators = (sp.sstr(terms[0]), sp.sstr(sp.expand(target - terms[0])))

    certificates = certify_polynomial_ideal_relations(
        text,
        generators,
        (Atom("perp", ("a", "b", "c", "d")),),
    )

    assert len(certificates) == 1
    assert certificates[0].macaulay_certificate.multiplier_degree == 0
    assert verify_typed_relation_ideal_certificate(text, certificates[0])
    assert not verify_typed_relation_ideal_certificate(
        text,
        {**asdict(certificates[0]), "predicate": "para"},
    )
