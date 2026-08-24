from __future__ import annotations

from types import SimpleNamespace

import pytest

from worker.backend.terminal_trajectory_credit import (
    ConstructionCreditSignature,
    TerminalCreditEvent,
    TerminalCreditLedger,
    assign_terminal_credit,
    rank_with_terminal_credit,
)


def step(family: str, output: str, *inputs: str) -> SimpleNamespace:
    return SimpleNamespace(
        family=family,
        output=output,
        inputs=inputs,
        structural_rank=(),
        key=f"{family}({','.join(inputs)})->{output}",
    )


def demand(predicate: str, *arguments: str) -> SimpleNamespace:
    return SimpleNamespace(predicate=predicate, arguments=arguments)


def test_terminal_proof_returns_credit_to_neutral_early_construction() -> None:
    steps = (
        step("midpoint", "x", "a", "b"),
        step("intersection_ll", "y", "x", "c", "a", "d"),
    )
    payload = {
        "deductions_for_goal": [
            {"point_deps": ["a", "b", "c", "d", "x", "y"]}
        ]
    }
    events = assign_terminal_credit(
        steps,
        ((demand("perp", "a", "b", "c", "d"),),) * 2,
        solved=True,
        proof_payload=payload,
        native_certificate_replayed=True,
        discount=0.5,
    )

    assert [event.step_index for event in events] == [0, 1]
    assert [event.credit for event in events] == pytest.approx([0.5, 1.0])


def test_unsolved_or_unreplayed_terminal_cannot_create_credit() -> None:
    steps = (step("midpoint", "x", "a", "b"),)
    payload = {"deductions_for_goal": [{"point_deps": ["x"]}]}

    assert not assign_terminal_credit(
        steps,
        ((),),
        solved=False,
        proof_payload=payload,
        native_certificate_replayed=True,
    )
    assert not assign_terminal_credit(
        steps,
        ((),),
        solved=True,
        proof_payload=payload,
        native_certificate_replayed=False,
    )


def test_irrelevant_construction_is_not_credited() -> None:
    steps = (
        step("midpoint", "x", "a", "b"),
        step("free", "z", "c"),
    )
    payload = {"deductions_for_goal": [{"point_deps": ["a", "b", "x"]}]}
    events = assign_terminal_credit(
        steps,
        ((), ()),
        solved=True,
        proof_payload=payload,
        native_certificate_replayed=True,
    )

    assert [event.step_index for event in events] == [0]


def test_signature_is_invariant_to_point_renaming_and_numbers() -> None:
    first = ConstructionCreditSignature.from_step(
        step("intersection_ll", "x", "a", "g", "b", "g"),
        generated_outputs={"g"},
        relation_demands=(demand("Perp", "a", "b", "c", "d"),),
    )
    second = ConstructionCreditSignature.from_step(
        step("intersection_ll", "q99", "u17", "h2", "v23", "h2"),
        generated_outputs={"h2"},
        relation_demands=(demand("perp", "u17", "v23", "w", "z"),),
    )

    assert first == second


def test_signature_uses_structural_shape_without_literal_entities() -> None:
    first_step = step("mirror", "x", "a", "b")
    second_step = step("mirror", "q", "u", "v")
    first_step.structural_rank = (0, 1, -4.5, 8, "mirror", ("a", "b"))
    second_step.structural_rank = (0, 1, -4.5, 8, "mirror", ("u", "v"))

    first = ConstructionCreditSignature.from_step(
        first_step, generated_outputs=(), relation_demands=()
    )
    second = ConstructionCreditSignature.from_step(
        second_step, generated_outputs=(), relation_demands=()
    )

    assert first == second
    assert not any(f'"{name}"' in first.key for name in ("a", "b", "u", "v"))


def test_verified_credit_reranks_same_structure_without_changing_truth() -> None:
    preferred = step("midpoint", "x", "a", "b")
    other = step("free", "y", "c")
    signature = ConstructionCreditSignature.from_step(
        preferred,
        generated_outputs=(),
        relation_demands=(),
    )
    ledger = TerminalCreditLedger(prior_weight=1.0)
    ledger.observe(
        (
            TerminalCreditEvent(signature, 0, 0, 1.0, True, True),
        )
    )

    ranked, audit = rank_with_terminal_credit(
        [other, preferred],
        generated_outputs=(),
        relation_demands=(),
        scores=ledger.scores(),
    )

    assert ranked == [preferred, other]
    assert audit[0]["credit_score"] > 0
    assert audit[0]["rank_change"] == 1


def test_ledger_round_trip_and_merge_preserve_certificate_counts() -> None:
    signature = ConstructionCreditSignature.from_step(
        step("midpoint", "x", "a", "b"),
        generated_outputs=(),
        relation_demands=(),
    )
    first = TerminalCreditLedger(prior_weight=1.0)
    first.observe((TerminalCreditEvent(signature, 0, 0, 1.0, True, True),))
    restored = TerminalCreditLedger.from_dict(first.to_dict())
    restored.merge(first)

    payload = restored.to_dict()
    assert payload["event_count"] == 2
    assert payload["entries"][0]["credit_sum"] == pytest.approx(2.0)


def test_ledger_rejects_non_native_truth_plane() -> None:
    with pytest.raises(ValueError, match="native replay"):
        TerminalCreditLedger.from_dict(
            {
                "schema": "mortra-terminal-trajectory-credit-v1",
                "truth_plane": "heuristic_score",
                "prior_weight": 2.0,
                "entries": [],
            }
        )


def test_typed_forgetting_transfers_weak_credit_across_target_contexts() -> None:
    source = ConstructionCreditSignature.from_step(
        step("foot", "x", "a", "b", "c"),
        generated_outputs=(),
        relation_demands=(demand("perp", "a", "b", "c", "x"),),
    )
    target = ConstructionCreditSignature.from_step(
        step("foot", "q", "u", "v", "w"),
        generated_outputs=(),
        relation_demands=(demand("coll", "u", "v", "q"),),
    )
    ledger = TerminalCreditLedger(prior_weight=1.0)
    ledger.observe((TerminalCreditEvent(source, 0, 0, 1.0, True, True),))

    assert ledger.score(source) == pytest.approx(0.5)
    assert ledger.score(target) == pytest.approx(0.125)
