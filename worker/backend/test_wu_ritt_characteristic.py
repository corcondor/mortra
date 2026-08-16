import sympy as sp

from worker.backend.wu_ritt_characteristic import (
    certified_wu_ritt_characteristic_set,
    certified_wu_ritt_goal_proof,
)


def test_characteristic_set_completes_beyond_one_pass_triangularization() -> None:
    a, x = sp.symbols("a x")
    result = certified_wu_ritt_characteristic_set(
        (a * x, (1 - a) * x),
        (a, x),
        timeout_seconds=10,
    )

    assert result.characteristic_set_verified
    assert result.completion_reached
    assert result.all_input_remainders_zero
    assert result.vanishing_consequence_verified
    assert result.all_identities_replayed
    assert result.stopped_reason is None


def test_goal_proof_exposes_initial_instead_of_promoting_conditional_result() -> None:
    a, x = sp.symbols("a x")
    result = certified_wu_ritt_goal_proof(
        (a * x,),
        (a, x),
        x,
        timeout_seconds=10,
    )

    assert result.conditional_goal_proved
    assert result.regularity_initials == ("a",)
    assert not result.inconsistent_system
    assert result.all_identities_replayed


def test_nonconsequence_is_not_promoted() -> None:
    a, x = sp.symbols("a x")
    result = certified_wu_ritt_goal_proof(
        (a * x,),
        (a, x),
        a,
        timeout_seconds=10,
    )

    assert not result.conditional_goal_proved
    assert result.goal_remainder != "0"


def test_inconsistent_constant_characteristic_set_closes_vacuously() -> None:
    x = sp.symbols("x")
    result = certified_wu_ritt_goal_proof(
        (x, x - 1),
        (x,),
        x**2 + 7,
        timeout_seconds=10,
    )

    assert result.characteristic.characteristic_set_verified
    assert result.inconsistent_system
    assert result.conditional_goal_proved


def test_independent_variable_can_be_localized_into_coefficient_field() -> None:
    u, x = sp.symbols("u x")
    result = certified_wu_ritt_goal_proof(
        (u * x,),
        (u, x),
        x,
        coefficient_variables=(u,),
        timeout_seconds=10,
    )

    assert result.characteristic.characteristic_set_verified
    assert result.characteristic.coefficient_parameters == ("u",)
    assert result.regularity_initials == ("u",)
    assert result.conditional_goal_proved


def test_weak_basic_set_is_a_verified_alternative_not_a_problem_patch() -> None:
    a, x, y = sp.symbols("a x y")
    result = certified_wu_ritt_goal_proof(
        (a * x, y - x, (1 - a) * x),
        (a, x, y),
        y,
        basic_set_mode="weak",
        timeout_seconds=10,
    )

    assert result.characteristic.basic_set_mode == "weak"
    assert result.characteristic.characteristic_set_verified
    assert result.conditional_goal_proved
    assert result.all_identities_replayed


def test_timeout_is_enforced_before_a_long_reduction_can_start() -> None:
    x, y = sp.symbols("x y")
    result = certified_wu_ritt_goal_proof(
        (x**8 + y, x**7 - y),
        (x, y),
        x + y,
        timeout_seconds=1e-9,
    )

    assert result.stopped_reason == "timeout"
    assert not result.conditional_goal_proved
