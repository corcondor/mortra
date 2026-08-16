import sympy as sp

from worker.backend.certified_buchberger import (
    certified_buchberger,
    certified_buchberger_dag,
    certify_dag_ideal_membership,
    certify_ideal_membership,
)


def test_linear_chain_produces_a_replayable_membership_certificate() -> None:
    x, y, z = sp.symbols("x y z")
    result = certified_buchberger((x - y, y - z), (x, y, z))
    proof = certify_ideal_membership(x - z, result)
    assert result.groebner_complete
    assert result.all_witnesses_replayed
    assert proof.proved and proof.replayed
    assert proof.remainder == "0"


def test_nonlinear_consequence_is_proved_without_a_problem_template() -> None:
    x, y, z = sp.symbols("x y z")
    result = certified_buchberger((x**2 - y, x - z), (x, y, z))
    proof = certify_ideal_membership(z**2 - y, result)
    assert proof.proved and proof.replayed
    assert any(item.output_basis_index is not None for item in result.steps)


def test_nonmember_keeps_a_nonzero_remainder() -> None:
    x, y = sp.symbols("x y")
    result = certified_buchberger((x - y,), (x, y))
    proof = certify_ideal_membership(x + y, result)
    assert not proof.proved
    assert proof.replayed
    assert proof.remainder != "0"


def test_budget_exhaustion_is_reported_instead_of_claiming_completeness() -> None:
    x, y = sp.symbols("x y")
    result = certified_buchberger(
        (x**2 + y, x * y + 1),
        (x, y),
        max_pairs=0,
    )
    assert not result.groebner_complete
    assert result.stopped_reason == "pair_budget"
    assert result.all_witnesses_replayed


def test_every_stored_basis_polynomial_replays_from_the_original_generators() -> None:
    x, y = sp.symbols("x y")
    result = certified_buchberger((x**2 + y, x * y + 1), (x, y))
    initial = tuple(sp.sympify(item) for item in result.initial_polynomials)
    for item in result.basis:
        reconstructed = sum(
            (
                sp.sympify(multiplier) * polynomial
                for multiplier, polynomial in zip(item.multipliers, initial)
            ),
            sp.Integer(0),
        )
        assert sp.expand(sp.sympify(item.polynomial) - reconstructed) == 0


def test_dag_certificate_avoids_flattening_and_still_proves_the_goal() -> None:
    x, y, z = sp.symbols("x y z")
    result = certified_buchberger_dag((x**2 - y, x - z), (x, y, z))
    proof = certify_dag_ideal_membership(z**2 - y, result)
    assert result.groebner_complete
    assert result.all_identities_replayed
    assert proof.proved and proof.replayed
    assert all(len(item.premises) == len(item.multipliers) for item in result.identities)


def test_dag_initial_autoreduction_preserves_the_full_ideal() -> None:
    x, y = sp.symbols("x y")
    result = certified_buchberger_dag((x, x + y), (x, y))
    proof = certify_dag_ideal_membership(y, result)
    assert result.groebner_complete
    assert proof.proved and proof.replayed


def test_dag_buchberger_stops_when_target_membership_is_certified() -> None:
    x, y = sp.symbols("x y")
    result = certified_buchberger_dag(
        (x - y, y - 1, x**3 + y**3),
        (x, y),
        max_pairs=100,
        membership_target=x - 1,
    )
    proof = certify_dag_ideal_membership(x - 1, result)
    assert result.stopped_reason == "target_membership"
    assert not result.groebner_complete
    assert proof.proved and proof.replayed


def test_complete_dag_basis_matches_sympy_on_unseen_small_ideals() -> None:
    x, y, z = sp.symbols("x y z")
    systems = (
        ((x + y - 1, x - y), (x, y), (2*x - 1, x + y)),
        ((x*y - 1, y - z), (x, y, z), (x*z - 1, x - z)),
        ((x**2 - y, y**2 - z), (x, y, z), (x**4 - z, x**2 + z)),
        ((x**2 + y**2 - 1, x - z), (x, y, z), (z**2 + y**2 - 1, x + y)),
    )
    for generators, variables, goals in systems:
        result = certified_buchberger_dag(generators, variables)
        reference = sp.groebner(generators, *variables, order="lex")
        assert result.groebner_complete
        assert result.all_identities_replayed
        for goal in goals:
            proof = certify_dag_ideal_membership(goal, result)
            assert proof.proved == reference.contains(goal)
            assert proof.replayed
