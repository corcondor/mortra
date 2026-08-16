import sympy as sp

from worker.backend.chordal_buchberger_elimination import (
    eliminate_with_certified_chordal_buchberger,
)
from worker.backend.chordal_polynomial_stalk import (
    coordinate_chordal_polynomial_stalk,
)


def test_local_clique_certificates_are_exchanged_into_a_global_proof() -> None:
    x, y, z, target = sp.symbols("x y z target")
    elimination = eliminate_with_certified_chordal_buchberger(
        (x - y, y - z, z - target),
        (x, y, z, target),
        protected_variables=(x, target),
        goal_polynomial=x - target,
    )
    report = coordinate_chordal_polynomial_stalk(elimination)
    assert report.goal_certificate_available
    assert report.goal_solved and report.goal_replayed
    assert report.active_agent_count >= 2
    assert report.proof_depth >= 2
    assert report.rejected_certificate_count == 0


def test_unproved_goal_never_becomes_a_coordinator_fact() -> None:
    x, y = sp.symbols("x y")
    elimination = eliminate_with_certified_chordal_buchberger(
        (x - y,),
        (x, y),
        protected_variables=(y,),
        goal_polynomial=y + 1,
    )
    report = coordinate_chordal_polynomial_stalk(elimination)
    assert not report.goal_certificate_available
    assert not report.goal_solved
    assert not report.goal_replayed
