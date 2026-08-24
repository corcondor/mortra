"""Certificate-backed credit assignment for construction trajectories.

The ledger is control-plane state only.  It never accepts a theorem and it
never reads problem identifiers, expected answers, point names, or numeric
coordinates.  Credit is emitted only for constructions that occur in the
native verifier's dependency slice for a solved goal.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from typing import Any, Iterable, Mapping, Sequence


SCHEMA_VERSION = "mortra-terminal-trajectory-credit-v2"
LEGACY_SCHEMA_VERSION = "mortra-terminal-trajectory-credit-v1"


def _ledger_key_weight(key: str) -> float:
    payload = json.loads(key)
    return {
        "target_context": 0.5,
        "morphism_type": 0.25,
    }.get(payload.get("resolution"), 1.0)


def _identity_partition(values: Sequence[str]) -> tuple[int, ...]:
    identities: dict[str, int] = {}
    return tuple(
        identities.setdefault(value, len(identities)) for value in values
    )


def _structural_shape(values: Sequence[Any]) -> tuple[str, ...]:
    """Quantize identity-free graph measurements, never literal entities."""

    shape: list[str] = []
    # The construction rank stores 17 numeric graph/role measurements followed
    # by the family and literal input tuple.  The latter two are deliberately
    # excluded here.
    for value in values[:17]:
        if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            shape.append("unknown")
            continue
        number = float(value)
        if number == 0:
            shape.append("0")
            continue
        sign = "+" if number > 0 else "-"
        bucket = min(12, int(math.log2(1.0 + abs(number))))
        shape.append(f"{sign}{bucket}")
    return tuple(shape)


@dataclass(frozen=True)
class ConstructionCreditSignature:
    """Alpha-renaming-invariant context for one construction morphism."""

    family: str
    input_roles: tuple[str, ...]
    input_equalities: tuple[int, ...]
    target_predicates: tuple[str, ...]
    structural_shape: tuple[str, ...]

    @classmethod
    def from_step(
        cls,
        step: Any,
        *,
        generated_outputs: Iterable[str],
        relation_demands: Iterable[Any],
    ) -> "ConstructionCreditSignature":
        generated = {str(value) for value in generated_outputs}
        inputs = tuple(str(value) for value in getattr(step, "inputs"))
        predicates = sorted(
            {
                str(getattr(demand, "predicate", "")).lower()
                for demand in relation_demands
                if str(getattr(demand, "predicate", ""))
            }
        )
        return cls(
            family=str(getattr(step, "family")),
            input_roles=tuple(
                "generated" if value in generated else "given" for value in inputs
            ),
            input_equalities=_identity_partition(inputs),
            target_predicates=tuple(predicates),
            structural_shape=_structural_shape(
                tuple(getattr(step, "structural_rank", ()))
            ),
        )

    @property
    def key(self) -> str:
        return json.dumps(
            {
                "family": self.family,
                "input_roles": self.input_roles,
                "input_equalities": self.input_equalities,
                "target_predicates": self.target_predicates,
                "structural_shape": self.structural_shape,
            },
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )

    def scored_keys(self) -> tuple[tuple[str, float], ...]:
        """Forget context in typed stages instead of requiring exact identity."""

        context = json.dumps(
            {
                "resolution": "target_context",
                "family": self.family,
                "input_roles": self.input_roles,
                "input_equalities": self.input_equalities,
                "target_predicates": self.target_predicates,
            },
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        morphism = json.dumps(
            {
                "resolution": "morphism_type",
                "family": self.family,
                "input_roles": self.input_roles,
                "input_equalities": self.input_equalities,
            },
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        return ((self.key, 1.0), (context, 0.5), (morphism, 0.25))

    @classmethod
    def from_dict(
        cls, value: Mapping[str, Any]
    ) -> "ConstructionCreditSignature":
        return cls(
            family=str(value["family"]),
            input_roles=tuple(map(str, value["input_roles"])),
            input_equalities=tuple(map(int, value["input_equalities"])),
            target_predicates=tuple(map(str, value["target_predicates"])),
            structural_shape=tuple(map(str, value.get("structural_shape", ()))),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "family": self.family,
            "input_roles": list(self.input_roles),
            "input_equalities": list(self.input_equalities),
            "target_predicates": list(self.target_predicates),
            "structural_shape": list(self.structural_shape),
        }


@dataclass(frozen=True)
class TerminalCreditEvent:
    signature: ConstructionCreditSignature
    step_index: int
    distance_from_terminal: int
    credit: float
    proof_dependency_observed: bool
    native_certificate_replayed: bool

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "TerminalCreditEvent":
        return cls(
            signature=ConstructionCreditSignature.from_dict(value["signature"]),
            step_index=int(value["step_index"]),
            distance_from_terminal=int(value["distance_from_terminal"]),
            credit=float(value["credit"]),
            proof_dependency_observed=bool(value["proof_dependency_observed"]),
            native_certificate_replayed=bool(value["native_certificate_replayed"]),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "signature": self.signature.to_dict(),
            "signature_key": self.signature.key,
            "step_index": self.step_index,
            "distance_from_terminal": self.distance_from_terminal,
            "credit": self.credit,
            "proof_dependency_observed": self.proof_dependency_observed,
            "native_certificate_replayed": self.native_certificate_replayed,
        }


def native_goal_dependency_points(payload: Mapping[str, Any]) -> frozenset[str]:
    """Extract point dependencies from the verifier's goal proof slice."""

    points: set[str] = set()
    deductions = payload.get("deductions_for_goal", ())
    if not isinstance(deductions, Sequence) or isinstance(deductions, (str, bytes)):
        return frozenset()
    for deduction in deductions:
        if not isinstance(deduction, Mapping):
            continue
        dependencies = deduction.get("point_deps", ())
        if isinstance(dependencies, Sequence) and not isinstance(
            dependencies, (str, bytes)
        ):
            points.update(str(value) for value in dependencies)
    return frozenset(points)


def _causal_step_indices(
    steps: Sequence[Any], dependency_points: frozenset[str]
) -> tuple[int, ...]:
    """Close native proof dependencies backwards through generated inputs."""

    output_to_index = {
        str(getattr(step, "output")): index for index, step in enumerate(steps)
    }
    active = {
        index
        for output, index in output_to_index.items()
        if output in dependency_points
    }
    frontier = list(active)
    while frontier:
        index = frontier.pop()
        for value in getattr(steps[index], "inputs"):
            parent = output_to_index.get(str(value))
            if parent is not None and parent not in active:
                active.add(parent)
                frontier.append(parent)
    return tuple(sorted(active))


def assign_terminal_credit(
    steps: Sequence[Any],
    relation_demands_by_step: Sequence[Sequence[Any]],
    *,
    solved: bool,
    proof_payload: Mapping[str, Any] | None,
    native_certificate_replayed: bool,
    discount: float = 0.85,
) -> tuple[TerminalCreditEvent, ...]:
    """Return credit only for a replayed terminal proof and its causal slice."""

    if not 0.0 < discount <= 1.0:
        raise ValueError("discount must be in (0, 1]")
    if (
        not solved
        or not native_certificate_replayed
        or proof_payload is None
        or len(steps) != len(relation_demands_by_step)
    ):
        return ()
    dependency_points = native_goal_dependency_points(proof_payload)
    active = _causal_step_indices(steps, dependency_points)
    if not active:
        return ()
    terminal_index = max(active)
    generated: list[str] = []
    events: list[TerminalCreditEvent] = []
    for index, (step, demands) in enumerate(
        zip(steps, relation_demands_by_step, strict=True)
    ):
        signature = ConstructionCreditSignature.from_step(
            step,
            generated_outputs=generated,
            relation_demands=demands,
        )
        if index in active:
            distance = terminal_index - index
            events.append(
                TerminalCreditEvent(
                    signature=signature,
                    step_index=index,
                    distance_from_terminal=distance,
                    credit=discount**distance,
                    proof_dependency_observed=True,
                    native_certificate_replayed=True,
                )
            )
        generated.append(str(getattr(step, "output")))
    return tuple(events)


class TerminalCreditLedger:
    """Aggregate positive proof evidence without turning it into truth."""

    def __init__(self, *, prior_weight: float = 2.0) -> None:
        if prior_weight <= 0:
            raise ValueError("prior_weight must be positive")
        self.prior_weight = float(prior_weight)
        self._credit: dict[str, float] = {}
        self._support: dict[str, int] = {}
        self._event_count = 0

    def observe(self, events: Iterable[TerminalCreditEvent]) -> None:
        for event in events:
            if not (
                event.native_certificate_replayed
                and event.proof_dependency_observed
                and math.isfinite(event.credit)
                and event.credit > 0
            ):
                continue
            self._event_count += 1
            for key, _ in event.signature.scored_keys():
                self._credit[key] = self._credit.get(key, 0.0) + event.credit
                self._support[key] = self._support.get(key, 0) + 1

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "TerminalCreditLedger":
        """Load only the certificate-backed ledger schema emitted by MORTRA."""

        schema = value.get("schema")
        if schema not in {SCHEMA_VERSION, LEGACY_SCHEMA_VERSION}:
            raise ValueError("unsupported terminal-credit ledger schema")
        if value.get("truth_plane") != "native_certificate_replay_only":
            raise ValueError("terminal-credit ledger lacks the native replay boundary")
        ledger = cls(prior_weight=float(value.get("prior_weight", 2.0)))
        entries = value.get("entries", ())
        if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)):
            raise ValueError("terminal-credit entries must be a sequence")
        for entry in entries:
            if not isinstance(entry, Mapping):
                raise ValueError("terminal-credit entry must be a mapping")
            key = str(entry["signature_key"])
            credit = float(entry["credit_sum"])
            support = int(entry["certificate_support"])
            if not key or not math.isfinite(credit) or credit <= 0 or support <= 0:
                raise ValueError("invalid terminal-credit entry")
            keys = (key,)
            if schema == LEGACY_SCHEMA_VERSION:
                signature_payload = json.loads(key)
                signature = ConstructionCreditSignature.from_dict(signature_payload)
                keys = tuple(item[0] for item in signature.scored_keys())
            for projected_key in keys:
                ledger._credit[projected_key] = (
                    ledger._credit.get(projected_key, 0.0) + credit
                )
                ledger._support[projected_key] = (
                    ledger._support.get(projected_key, 0) + support
                )
        ledger._event_count = int(
            value.get("event_count", sum(ledger._support.values()))
        )
        return ledger

    def merge(self, other: "TerminalCreditLedger") -> None:
        """Combine independent certificate evidence under one fixed prior."""

        if not math.isclose(self.prior_weight, other.prior_weight):
            raise ValueError("cannot merge ledgers with different prior weights")
        for key, credit in other._credit.items():
            self._credit[key] = self._credit.get(key, 0.0) + credit
            self._support[key] = self._support.get(key, 0) + other._support[key]
        self._event_count += other._event_count

    def score(self, signature: ConstructionCreditSignature) -> float:
        return max(
            weight
            * self._credit.get(key, 0.0)
            / (self.prior_weight + self._support.get(key, 0))
            for key, weight in signature.scored_keys()
        )

    def scores(self) -> dict[str, float]:
        return {
            key: self._credit[key] / (self.prior_weight + self._support[key])
            for key in self._credit
        }

    def to_dict(self) -> dict[str, object]:
        scores = self.scores()
        return {
            "schema": SCHEMA_VERSION,
            "truth_plane": "native_certificate_replay_only",
            "forbidden_inputs": [
                "problem_id",
                "expected_answer",
                "point_identity",
                "numeric_coordinate",
                "dataset_auxiliary_clause",
            ],
            "prior_weight": self.prior_weight,
            "signature_count": len(scores),
            "event_count": self._event_count,
            "entries": [
                {
                    "signature_key": key,
                    "credit_sum": self._credit[key],
                    "certificate_support": self._support[key],
                    "posterior_score": scores[key],
                    "transfer_weight": _ledger_key_weight(key),
                    "score": scores[key] * _ledger_key_weight(key),
                }
                for key in sorted(scores)
            ],
        }


def rank_with_terminal_credit(
    pool: Sequence[Any],
    *,
    generated_outputs: Iterable[str],
    relation_demands: Iterable[Any],
    scores: Mapping[str, float],
) -> tuple[list[Any], list[dict[str, object]]]:
    """Stable reranking: terminal credit breaks ties ahead of static rank."""

    generated = tuple(generated_outputs)
    demands = tuple(relation_demands)
    audited: list[tuple[int, Any, ConstructionCreditSignature, float]] = []
    for index, step in enumerate(pool):
        signature = ConstructionCreditSignature.from_step(
            step,
            generated_outputs=generated,
            relation_demands=demands,
        )
        score = max(
            weight * float(scores.get(key, 0.0))
            for key, weight in signature.scored_keys()
        )
        audited.append((index, step, signature, score))
    audited.sort(key=lambda item: (-item[3], item[0]))
    return (
        [item[1] for item in audited],
        [
            {
                "candidate": str(getattr(step, "key")),
                "original_rank": index,
                "credit_rank": credit_rank,
                "rank_change": index - credit_rank,
                "credit_score": score,
                "signature": signature.to_dict(),
            }
            for credit_rank, (index, step, signature, score) in enumerate(audited)
        ],
    )
