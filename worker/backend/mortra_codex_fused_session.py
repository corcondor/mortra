"""Synchronous MORTRA/Codex research-session state machine.

MORTRA emits one typed observation and then blocks.  Codex must answer with a
typed intervention before MORTRA evaluates the current tree and emits the next
observation.  The process and ledger remain open across every round; no timer,
queue, or second Codex task participates in the protocol.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from worker.backend.mortra_research_dialogue import (
    ResearchDialogueEntry,
    ResearchDialogueLedger,
    canonical_json,
    payload_sha256,
)


TRANSPORT = "synchronous-jsonl-stdio-v1"
_FORBIDDEN_HYPOTHESIS_KEYS = frozenset(
    {
        "benchmark_membership",
        "expected_answer",
        "problem_id",
        "problem_name",
    }
)
_REQUIRED_HYPOTHESIS_KEYS = frozenset(
    {
        "intervention_class",
        "morphism_sequence",
        "predicted_shared_effect",
        "target_obligation_signature",
    }
)


def _walk_keys(value: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            keys.add(str(key))
            keys.update(_walk_keys(child))
    elif isinstance(value, (list, tuple)):
        for child in value:
            keys.update(_walk_keys(child))
    return keys


def validate_typed_hypothesis(
    payload: dict[str, Any],
    *,
    frozen_problem_names: tuple[str, ...],
) -> None:
    missing = sorted(_REQUIRED_HYPOTHESIS_KEYS - set(payload))
    if missing:
        raise ValueError(f"typed hypothesis is missing fields: {missing}")
    forbidden_keys = sorted(_FORBIDDEN_HYPOTHESIS_KEYS & _walk_keys(payload))
    if forbidden_keys:
        raise ValueError(
            f"typed hypothesis contains forbidden conditioning keys: {forbidden_keys}"
        )
    encoded = canonical_json(payload)
    leaked_names = sorted(name for name in frozen_problem_names if name in encoded)
    if leaked_names:
        raise ValueError(
            "typed hypothesis is conditioned on frozen problem identifiers: "
            f"{leaked_names}"
        )
    morphisms = payload["morphism_sequence"]
    if not isinstance(morphisms, list) or not morphisms:
        raise ValueError("morphism_sequence must be a non-empty list")


def compare_snapshots(
    baseline: dict[str, Any],
    treatment: dict[str, Any],
    *,
    intervention_source_sha256: dict[str, str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    baseline_problems = dict(baseline["problems"])
    treatment_problems = dict(treatment["problems"])
    if set(baseline_problems) != set(treatment_problems):
        raise ValueError("control and treatment problem sets differ")

    names = sorted(baseline_problems)
    new_solves = [
        name
        for name in names
        if not bool(baseline_problems[name]["solved"])
        and bool(treatment_problems[name]["solved"])
    ]
    regressions = [
        name
        for name in names
        if bool(baseline_problems[name]["solved"])
        and not bool(treatment_problems[name]["solved"])
    ]
    ambiguous = [
        name for name in names if bool(treatment_problems[name]["ambiguous"])
    ]
    certificate_failures = [
        name
        for name in names
        if bool(treatment_problems[name]["solved"])
        and not treatment_problems[name].get("certificate_sha256")
    ]
    experiment = {
        "transport": TRANSPORT,
        "design": "same-process-blocking-paired-control-treatment",
        "uses_external_llm_inside_mortra": False,
        "uses_expected_answer": False,
        "baseline_snapshot_sha256": payload_sha256(baseline),
        "treatment_snapshot_sha256": payload_sha256(treatment),
        "intervention_source_sha256": dict(sorted(intervention_source_sha256.items())),
        "summary": {
            "evaluated": len(names),
            "new_exact_solves": len(new_solves),
            "regressions": len(regressions),
            "ambiguous": len(ambiguous),
            "certificate_hash_failures": len(certificate_failures),
        },
        "sets": {
            "new_exact_solves": new_solves,
            "regressions": regressions,
            "ambiguous": ambiguous,
            "certificate_hash_failures": certificate_failures,
            "remaining_unproved": [
                name for name in names if not bool(treatment_problems[name]["solved"])
            ],
        },
        "control": baseline,
        "treatment": treatment,
    }
    accepted = (
        bool(new_solves)
        and not regressions
        and not ambiguous
        and not certificate_failures
    )
    decision = {
        "accepted": accepted,
        "status": "accepted" if accepted else "rejected_no_strict_gain",
        "evidence": experiment["summary"],
        "next_stop_obligations": experiment["sets"]["remaining_unproved"],
    }
    return experiment, decision


@dataclass
class FusedResearchSession:
    ledger: ResearchDialogueLedger
    ledger_path: Path
    frozen_problem_names: tuple[str, ...]

    def _latest_incomplete_cycle(self) -> tuple[ResearchDialogueEntry, ...]:
        if not self.ledger.entries:
            return ()
        fingerprint = self.ledger.entries[-1].cycle_fingerprint
        entries = self.ledger.cycle_entries(fingerprint)
        if any(entry.kind == "decision" for entry in entries):
            return ()
        return entries

    def begin_cycle(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        incomplete = self._latest_incomplete_cycle()
        if incomplete:
            observation = next(
                entry for entry in incomplete if entry.kind == "cohort_observation"
            )
            return self._observation_event(observation)

        turn = sum(entry.kind == "decision" for entry in self.ledger.entries)
        fingerprint = payload_sha256(
            {
                "transport": TRANSPORT,
                "turn": turn,
                "snapshot_sha256": payload_sha256(snapshot),
                "previous_head_sha256": self.ledger.to_dict()["head_sha256"],
            }
        )
        observation = self.ledger.append(
            role="mortra",
            kind="cohort_observation",
            cycle_fingerprint=fingerprint,
            payload={
                "transport": TRANSPORT,
                "turn": turn,
                "snapshot": snapshot,
            },
        )
        self.ledger.save(self.ledger_path)
        return self._observation_event(observation)

    def _observation_event(self, entry: ResearchDialogueEntry) -> dict[str, Any]:
        cycle = self.ledger.cycle_entries(entry.cycle_fingerprint)
        waiting_for = (
            "evaluate"
            if any(item.kind == "typed_hypothesis" for item in cycle)
            else "typed_hypothesis"
        )
        return {
            "protocol": TRANSPORT,
            "event": "mortra_observation",
            "cycle_fingerprint": entry.cycle_fingerprint,
            "waiting_for": waiting_for,
            "ledger_head_sha256": self.ledger.to_dict()["head_sha256"],
            "payload": entry.payload,
        }

    def submit_hypothesis(
        self,
        *,
        cycle_fingerprint: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        validate_typed_hypothesis(
            payload,
            frozen_problem_names=self.frozen_problem_names,
        )
        cycle = self.ledger.cycle_entries(cycle_fingerprint)
        if not cycle or any(entry.kind == "decision" for entry in cycle):
            raise ValueError("cycle is missing or already closed")
        existing = next(
            (entry for entry in cycle if entry.kind == "typed_hypothesis"),
            None,
        )
        if existing:
            if existing.payload != payload:
                raise ValueError("cycle already contains a different hypothesis")
            entry = existing
        else:
            entry = self.ledger.append(
                role="codex",
                kind="typed_hypothesis",
                cycle_fingerprint=cycle_fingerprint,
                payload=payload,
            )
            self.ledger.save(self.ledger_path)
        return {
            "protocol": TRANSPORT,
            "event": "codex_hypothesis_accepted",
            "cycle_fingerprint": cycle_fingerprint,
            "hypothesis_sha256": payload_sha256(payload),
            "entry_sha256": entry.entry_sha256,
            "waiting_for": "evaluate",
        }

    def close_cycle(
        self,
        *,
        cycle_fingerprint: str,
        treatment_snapshot: dict[str, Any],
        intervention_source_sha256: dict[str, str],
    ) -> dict[str, Any]:
        cycle = self.ledger.cycle_entries(cycle_fingerprint)
        if not cycle:
            raise ValueError("unknown cycle")
        if not any(entry.kind == "typed_hypothesis" for entry in cycle):
            raise ValueError("cycle has no Codex hypothesis")
        existing_decision = next(
            (entry for entry in cycle if entry.kind == "decision"),
            None,
        )
        if existing_decision:
            return {
                "protocol": TRANSPORT,
                "event": "mortra_evaluation",
                "cycle_fingerprint": cycle_fingerprint,
                "decision": existing_decision.payload,
                "resumed": True,
            }
        observation = next(
            entry for entry in cycle if entry.kind == "cohort_observation"
        )
        baseline = dict(observation.payload["snapshot"])
        experiment, decision = compare_snapshots(
            baseline,
            treatment_snapshot,
            intervention_source_sha256=intervention_source_sha256,
        )
        self.ledger.append(
            role="mortra",
            kind="controlled_experiment",
            cycle_fingerprint=cycle_fingerprint,
            payload=experiment,
        )
        decision_entry = self.ledger.append(
            role="governor",
            kind="decision",
            cycle_fingerprint=cycle_fingerprint,
            payload=decision,
        )
        self.ledger.save(self.ledger_path)
        return {
            "protocol": TRANSPORT,
            "event": "mortra_evaluation",
            "cycle_fingerprint": cycle_fingerprint,
            "decision": decision,
            "decision_entry_sha256": decision_entry.entry_sha256,
            "resumed": False,
        }


__all__ = [
    "FusedResearchSession",
    "TRANSPORT",
    "compare_snapshots",
    "validate_typed_hypothesis",
]
