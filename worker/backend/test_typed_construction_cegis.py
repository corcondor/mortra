from worker.backend.geometry_proof_hypergraph import Atom
from worker.backend.geometry_representation_atlas import (
    certified_equivalent_relations,
)
from worker.backend.typed_construction_cegis import (
    TypedConstructionProposal,
    run_residual_construction_cegis,
)
from worker.backend.typed_lemma_cegis import LemmaVerification


def _length_equation_for(atom: Atom) -> Atom:
    return next(
        item.target
        for item in certified_equivalent_relations(atom)
        if item.target.predicate == "lequation"
    )


def test_residual_reducing_cross_chart_candidate_is_verified_and_promoted() -> None:
    perpendicular = Atom("perp", ("x", "p", "a", "b"))
    demand = _length_equation_for(perpendicular)
    proposal = TypedConstructionProposal(
        "on_tline(p,a,b)",
        "on_tline",
        ("p", "a", "b"),
        (perpendicular,),
    )

    result = run_residual_construction_cegis(
        (),
        ((demand,),),
        (proposal,),
        verifier=lambda _item: LemmaVerification(
            "proved", "native-yuclid", "certificate-x"
        ),
    )

    assert result.baseline.selected_rank[0] == 1
    assert len(result.accepted) == 1
    assert result.accepted[0].after_rank == (0, 0, 0)


def test_nonprogress_candidate_never_reaches_expensive_verifier() -> None:
    calls = []
    proposal = TypedConstructionProposal(
        "on_line(a,b)",
        "on_line",
        ("a", "b"),
        (Atom("coll", ("x", "a", "b")),),
    )

    def verify(item):
        calls.append(item.key)
        return LemmaVerification("proved", "must-not-run", "bad")

    result = run_residual_construction_cegis(
        (),
        ((Atom("perp", ("p", "q", "r", "s")),),),
        (proposal,),
        verifier=verify,
    )

    assert calls == []
    assert result.accepted == ()
    assert len(result.skipped_no_residual_progress) == 1


def test_counterexample_prevents_promotion_despite_residual_reduction() -> None:
    perpendicular = Atom("perp", ("x", "p", "a", "b"))
    proposal = TypedConstructionProposal(
        "on_tline(p,a,b)",
        "on_tline",
        ("p", "a", "b"),
        (perpendicular,),
    )

    result = run_residual_construction_cegis(
        (),
        ((_length_equation_for(perpendicular),),),
        (proposal,),
        verifier=lambda _item: LemmaVerification(
            "proved", "must-not-win", "bad"
        ),
        counterexample_oracle=lambda _item: LemmaVerification(
            "counterexample", "finite-model", counterexample="a=b"
        ),
    )

    assert result.accepted == ()
    assert len(result.rejected_counterexamples) == 1


def test_open_requirement_never_reaches_verifier() -> None:
    calls = []
    perpendicular = Atom("perp", ("x", "p", "a", "b"))
    proposal = TypedConstructionProposal(
        "on_tline(p,a,b)",
        "on_tline",
        ("p", "a", "b"),
        (perpendicular,),
        (Atom("diff", ("a", "b")),),
    )

    result = run_residual_construction_cegis(
        (),
        ((_length_equation_for(perpendicular),),),
        (proposal,),
        verifier=lambda item: calls.append(item.key),
    )

    assert calls == []
    assert result.accepted == ()
    assert result.trials[0].open_requirements == (Atom("diff", ("a", "b")),)
    assert len(result.skipped_no_residual_progress) == 1


def test_proved_requirement_keeps_candidate_executable() -> None:
    perpendicular = Atom("perp", ("x", "p", "a", "b"))
    proposal = TypedConstructionProposal(
        "on_tline(p,a,b)",
        "on_tline",
        ("p", "a", "b"),
        (perpendicular,),
        (Atom("diff", ("a", "b")),),
    )

    result = run_residual_construction_cegis(
        (Atom("ncoll", ("a", "b", "p")),),
        ((_length_equation_for(perpendicular),),),
        (proposal,),
        verifier=lambda _item: LemmaVerification(
            "proved", "native-yuclid", "certificate-known-requirement"
        ),
    )

    assert len(result.accepted) == 1
    assert result.trials[0].requirements_satisfied
