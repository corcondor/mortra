from worker.backend.geometry_proof_hypergraph import Atom
from worker.backend.geometry_representation_atlas import (
    AFFINE_CHART,
    METRIC_CHART,
    certified_equivalent_relations,
    certify_relation_equivalence,
    lift_relation,
    relation_chart_residual,
)


def _squared(coefficient: str, left: str, right: str) -> tuple[str, ...]:
    return (coefficient, left, right, "*", left, right)


def test_perpendicular_and_polarized_length_equation_share_metric_chart() -> None:
    perpendicular = Atom("perp", ("a", "b", "c", "d"))
    length_equation = Atom(
        "lequation",
        (
            *_squared("1/1", "b", "c"),
            *_squared("1/1", "a", "d"),
            *_squared("-1/1", "b", "d"),
            *_squared("-1/1", "a", "c"),
            "0",
        ),
    )

    left = lift_relation(perpendicular)
    right = lift_relation(length_equation)
    certificate = certify_relation_equivalence(perpendicular, length_equation)

    assert left is not None and right is not None
    assert left.chart == right.chart == METRIC_CHART
    assert left.replayed and right.replayed
    assert left.canonical_key == right.canonical_key
    assert certificate is not None and certificate.replayed
    assert len(certificate.certificate_sha256) == 64


def test_parallel_relation_replays_in_affine_determinant_chart() -> None:
    relation = lift_relation(Atom("para", ("a", "b", "c", "d")))

    assert relation is not None
    assert relation.chart == AFFINE_CHART
    assert relation.replayed
    assert relation.replay_residual == "0"
    assert all(feature.startswith("br(") for feature, _ in relation.coefficients)


def test_nonlinear_length_products_are_not_forced_into_linear_metric_chart() -> None:
    relation = Atom(
        "lequation",
        (
            "1/1",
            "a",
            "b",
            "*",
            "a",
            "b",
            "*",
            "c",
            "d",
            "*",
            "c",
            "d",
            "0",
        ),
    )

    assert lift_relation(relation) is None


def test_equivalent_relation_enumeration_is_exact_and_problem_independent() -> None:
    equivalents = certified_equivalent_relations(
        Atom("perp", ("p", "q", "r", "s"))
    )

    assert equivalents
    assert any(item.target.predicate == "lequation" for item in equivalents)
    assert all(item.replayed for item in equivalents)


def test_chart_residual_closes_cross_predicate_goal_without_mixing_or_branches() -> None:
    perpendicular = Atom("perp", ("a", "b", "c", "d"))
    length_equation = next(
        item.target
        for item in certified_equivalent_relations(perpendicular)
        if item.target.predicate == "lequation"
    )
    result = relation_chart_residual(
        (perpendicular,),
        (
            (length_equation,),
            (Atom("coll", ("a", "b", "c")), Atom("coll", ("a", "b", "d"))),
        ),
    )

    assert result.selected_branch_index == 0
    assert result.selected_rank == (0, 0, 0)
    assert result.branches[0].atoms[0].proved
    assert result.branches[0].atoms[0].replayed
    assert not result.branches[1].atoms[0].proved
