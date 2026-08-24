import sympy as sp

from worker.backend.bounded_macaulay_membership import (
    certify_bounded_macaulay_membership,
    verify_bounded_macaulay_certificate,
)


def test_constant_multiplier_certificate_replays() -> None:
    x, y, z = sp.symbols("x y z")
    result = certify_bounded_macaulay_membership(
        (x - y, y - z),
        (x, y, z),
        x - z,
    )

    assert result.proved and result.replayed
    assert result.multiplier_degree == 0
    assert result.replay_residual == "0"
    assert verify_bounded_macaulay_certificate(result)


def test_linear_multiplier_certificate_replays() -> None:
    x, y = sp.symbols("x y")
    result = certify_bounded_macaulay_membership(
        (x - y,),
        (x, y),
        x**2 - y**2,
    )

    assert result.proved and result.replayed
    assert result.multiplier_degree == 1
    assert sp.expand(sp.sympify(result.multipliers[0]) - (x + y)) == 0
    assert verify_bounded_macaulay_certificate(result)


def test_nonmember_stays_open() -> None:
    x, y = sp.symbols("x y")
    result = certify_bounded_macaulay_membership(
        (x - y,),
        (x, y),
        x + y,
    )

    assert not result.proved
    assert result.status == "open_within_degree_bound"


def test_serialized_membership_tampering_is_rejected() -> None:
    x, y = sp.symbols("x y")
    result = certify_bounded_macaulay_membership((x - y,), (x, y), x - y)
    tampered = {
        **result.__dict__,
        "goal_polynomial": "x + y",
    }

    assert not verify_bounded_macaulay_certificate(tampered)
