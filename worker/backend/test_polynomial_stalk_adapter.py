import sympy as sp

from worker.backend.local_polynomial_elimination import (
    eliminate_local_linear_variables,
)
from worker.backend.polynomial_stalk_adapter import (
    PolynomialEliminationStalkAdapter,
    build_polynomial_stalk,
    coordinate_polynomial_stalk,
)
from worker.backend.symbolic_sheaf_coordination import (
    ExactSheafCoordinator,
    PredicateSignature,
    TypedVocabulary,
)


def test_polynomial_certificates_are_exchanged_as_a_replayed_dag() -> None:
    x, y, z, target = sp.symbols("x y z target")
    elimination = eliminate_local_linear_variables(
        (x - y, y - z, z - target),
        (x, y, z, target),
        protected_variables=(x, target),
    )
    stalk = build_polynomial_stalk(elimination)
    entities = {
        argument
        for atom in (*stalk.initial_atoms, *stalk.derived_atoms)
        for argument in atom.arguments
    }
    coordinator = ExactSheafCoordinator(
        TypedVocabulary(
            signatures={"poly_zero": PredicateSignature("poly_zero", ("Polynomial",))},
            entity_sorts={entity: "Polynomial" for entity in entities},
        ),
        (PolynomialEliminationStalkAdapter(stalk),),
    )
    result = coordinator.solve(stalk.initial_atoms, stalk.derived_atoms[-1])
    assert result.solved and result.replayed
    assert len(result.proof_slice()) == 2
    assert all(item.native_payload["replayed"] for item in result.proof_slice())


def test_all_nontrivial_polynomial_goals_are_measured() -> None:
    x, y, z, target = sp.symbols("x y z target")
    elimination = eliminate_local_linear_variables(
        (x - y, y - z, z - target),
        (x, y, z, target),
        protected_variables=(x, target),
    )
    report = coordinate_polynomial_stalk(
        elimination,
        external_goal_polynomial="2*x - 2*target",
    )
    assert report.derived_goal_count == 2
    assert report.local_agent_count == 2
    assert report.active_agent_count == 2
    assert report.solved_goal_count == 2
    assert report.replayed_goal_count == 2
    assert report.rejected_certificate_count == 0
    assert report.maximum_proof_depth == 2
    assert report.external_goal_matched
    assert report.external_goal_solved
    assert report.external_goal_replayed
    assert report.external_goal_proof_depth == 2
