import sympy as sp
from dataclasses import replace

from worker.backend.certified_wu_characteristic import (
    certified_sparse_wu_characteristic_proof,
)
from worker.backend.wu_polynomial_stalk import (
    _micro_identities_from_step,
    _replay_micro_identity,
    _replay_identity_in_sparse_ring,
    coordinate_wu_polynomial_stalk,
)
from worker.backend.wu_polynomial_stalk import classify_regularity_obligations


def test_wu_stalk_replays_composed_identity_without_regularities() -> None:
    x, y, z = sp.symbols("x y z")
    result = certified_sparse_wu_characteristic_proof(
        (y - x, z - y**2),
        (x, y, z),
        z - x**2,
        timeout_seconds=10,
    )
    report = coordinate_wu_polynomial_stalk(result)
    assert report.goal_certificate_available
    assert report.conditional_goal_solved
    assert report.conditional_goal_replayed
    assert report.unconditional_goal_solved
    assert report.rejected_certificate_count == 0


def test_wu_stalk_marks_nonzero_initial_as_conditional() -> None:
    a, x = sp.symbols("a x")
    result = certified_sparse_wu_characteristic_proof(
        (a * x,),
        (a, x),
        x,
        timeout_seconds=10,
    )
    report = coordinate_wu_polynomial_stalk(result)
    assert report.regularity_assumption_count == 1
    assert report.conditional_goal_solved
    assert report.conditional_goal_replayed
    assert not report.unconditional_goal_solved


def test_wu_stalk_exchanges_oversized_identity_by_content_address() -> None:
    x, y, z = sp.symbols("x y z")
    result = certified_sparse_wu_characteristic_proof(
        (y - x, z - y**2),
        (x, y, z),
        z - x**2,
        timeout_seconds=10,
    )
    report = coordinate_wu_polynomial_stalk(
        result,
        max_identity_characters=1,
    )
    assert report.oversized_certificate_count > 0
    assert report.content_addressed_fallback_certificate_count > 0
    assert report.conditional_goal_solved


def test_oversized_identity_does_not_parse_its_regularity() -> None:
    a, x = sp.symbols("a x")
    result = certified_sparse_wu_characteristic_proof(
        (a * x,),
        (a, x),
        x,
        timeout_seconds=10,
    )
    oversized = replace(
        result,
        goal_steps=(
            replace(
                result.goal_steps[0],
                multiplier="(" + "+".join("a" for _ in range(1000)) + ")",
                nonzero_obligation="this must never be parsed",
            ),
        ),
    )
    report = coordinate_wu_polynomial_stalk(
        oversized,
        max_identity_characters=10,
    )
    assert report.eligible_certificate_count == 0
    assert report.oversized_certificate_count == 1


def test_wu_stalk_rejects_a_tampered_polynomial_identity() -> None:
    a, x = sp.symbols("a x")
    result = certified_sparse_wu_characteristic_proof(
        (a * x,),
        (a, x),
        x,
        timeout_seconds=10,
    )
    tampered = replace(
        result,
        goal_steps=(replace(result.goal_steps[0], quotient="0"),),
    )
    report = coordinate_wu_polynomial_stalk(tampered)
    assert report.rejected_certificate_count == 1
    assert not report.conditional_goal_solved


def test_regularity_matching_is_factor_based_not_text_based() -> None:
    discharged, open_items = classify_regularity_obligations(
        ("Ne(4*a**2*b, 0)", "Ne(c, 0)"),
        ("-2*a != 0", "b**3 != 0"),
    )
    assert discharged == ("Ne(4*a**2*b, 0)",)
    assert open_items == ("Ne(c, 0)",)


def test_wu_stalk_reports_input_discharged_regularity() -> None:
    a, x = sp.symbols("a x")
    result = certified_sparse_wu_characteristic_proof(
        (a * x,),
        (a, x),
        x,
        timeout_seconds=10,
    )
    report = coordinate_wu_polynomial_stalk(
        result,
        known_nonzero_conditions=("2*a**3 != 0",),
    )
    assert report.discharged_regularity_count == 1
    assert report.open_regularity_count == 0
    assert report.discharged_regularity_obligations == ("Ne(a, 0)",)
    assert report.open_regularity_obligations == ()
    assert report.input_conditioned_goal_solved
    assert not report.unconditional_goal_solved


def test_iterative_certificate_parser_handles_deep_addition_without_ast() -> None:
    a, x = sp.symbols("a x")
    result = certified_sparse_wu_characteristic_proof(
        (a * x,),
        (a, x),
        x,
        timeout_seconds=10,
    )
    step = result.goal_steps[0]
    zero = "+".join("0" for _ in range(2_000))
    deep = replace(step, quotient=f"{step.quotient}+{zero}")
    assert _replay_identity_in_sparse_ring(deep)


def test_oversized_quotient_certificate_is_exchanged_as_micro_obligations() -> None:
    x, y, z = sp.symbols("x y z")
    result = certified_sparse_wu_characteristic_proof(
        (y - x, z - y**2),
        (x, y, z),
        z - x**2,
        timeout_seconds=10,
    )
    goal_step = result.goal_steps[0]
    bloated = replace(
        goal_step,
        quotient=goal_step.quotient + "+" + "+".join("0" for _ in range(5_000)),
    )
    result = replace(result, goal_steps=(bloated, *result.goal_steps[1:]))
    report = coordinate_wu_polynomial_stalk(
        result,
        max_identity_characters=2_000,
    )
    assert report.oversized_certificate_count == 1
    assert report.expanded_micro_certificate_count > 0
    assert report.skipped_micro_certificate_count == 0
    assert report.content_addressed_fallback_certificate_count == 0
    assert report.conditional_goal_solved


def test_micro_obligations_replay_exactly_in_both_directions() -> None:
    a, x = sp.symbols("a x")
    result = certified_sparse_wu_characteristic_proof(
        (a * x,),
        (a, x),
        x,
        timeout_seconds=10,
    )
    step = result.goal_steps[0]
    forward = _micro_identities_from_step(step, direction="forward")
    backward = _micro_identities_from_step(step, direction="backward")
    assert forward
    assert tuple(reversed(forward))[0].previous == backward[0].previous
    assert all(_replay_micro_identity(identity) for identity in (*forward, *backward))


def test_oversized_conditional_micro_chain_uses_input_regularity() -> None:
    a, x = sp.symbols("a x")
    result = certified_sparse_wu_characteristic_proof(
        (a * x,),
        (a, x),
        x,
        timeout_seconds=10,
    )
    step = result.goal_steps[0]
    bloated = replace(
        step,
        quotient=step.quotient + "+" + "+".join("0" for _ in range(5_000)),
    )
    report = coordinate_wu_polynomial_stalk(
        replace(result, goal_steps=(bloated,)),
        known_nonzero_conditions=("a != 0",),
        max_identity_characters=2_000,
    )
    assert report.expanded_micro_certificate_count > 0
    assert report.discharged_regularity_count == 1
    assert report.open_regularity_count == 0
    assert report.input_conditioned_goal_solved
