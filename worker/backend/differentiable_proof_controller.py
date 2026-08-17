"""Small differentiable controller for exact symbolic proof search.

The controller is deliberately outside the truth path.  It receives only
bounded, label-free measurements of an already evaluated symbolic search
state and returns a priority.  A native verifier must still replay every
certificate before a theorem is accepted.

Six local stalks form a star-shaped constant sheaf over one shared utility
coordinate.  Their private proposals are reconciled by scaled consensus ADMM.
All feature weights and stalk trusts are positive, so increasing a feature
whose declared meaning is "more proof progress" cannot lower that stalk's
proposal.  This makes the learned policy small and auditable.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


STRUCTURAL_FEATURES = tuple(f"rank_quality_{index}" for index in range(17))
FEATURE_GROUPS: dict[str, tuple[str, ...]] = {
    "structure": STRUCTURAL_FEATURES,
    "closure": (
        "goal_deductions",
        "target_assertions",
        "relation_support",
        "near_goal_relations",
        "all_deductions",
    ),
    "transition": (
        "transition_potential",
        "transition_channel_coverage",
        "frontier_distance_quality",
        "frontier_goal_overlap",
        "frontier_witness_count",
    ),
    "obligation": (
        "backward_obligation_count",
        "open_demand_quality",
    ),
    "algebra": (
        "ar_supported_goals",
        "ar_closed_goals",
        "ar_support_quality",
        "ar_l1_quality",
        "ar_known_rank",
    ),
    "cost": (
        "elapsed_quality",
        "deduction_cost_quality",
        "valid_state",
    ),
}
FEATURE_NAMES = tuple(
    feature for features in FEATURE_GROUPS.values() for feature in features
)
FORBIDDEN_INPUTS = frozenset(
    {
        "problem_id",
        "problem_name",
        "point_name",
        "entity_label",
        "numeric_value",
        "answer",
        "known_auxiliary",
        "theorem_name",
        "family_name",
    }
)
SCHEMA_VERSION = "mortra-differentiable-proof-controller-v2"
MAX_DISAGREEMENT_PENALTY = 0.25


def _get(value: object, name: str, default: Any) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _has(value: object, name: str) -> bool:
    if isinstance(value, Mapping):
        return name in value
    return hasattr(value, name)


def _bounded_count(value: object) -> float:
    number = max(float(value or 0.0), 0.0)
    logged = math.log1p(number)
    return logged / (1.0 + logged)


def _inverse_count(value: object) -> float:
    return 1.0 / (1.0 + max(float(value or 0.0), 0.0))


def _signed_quality(value: object) -> float:
    """Map a lower-is-better rank component to a bounded higher-is-better value."""

    number = -float(value or 0.0)
    squashed = number / (1.0 + abs(number))
    return 0.5 * (1.0 + squashed)


def _last_step(record: object) -> object | None:
    steps = _get(record, "steps", ()) or ()
    return steps[-1] if steps else None


def extract_controller_features(record: object) -> dict[str, float]:
    """Extract invariant progress features from a SearchRecord-like value.

    Entity labels, construction-family names, problem identifiers and literal
    numbers from the original theorem are never inspected.  Structural ranks
    are numeric measurements computed from typed incidence and role graphs.
    """

    features = {name: 0.0 for name in FEATURE_NAMES}
    step = _last_step(record)
    structural_rank: Sequence[object] = (
        _get(step, "structural_rank", ()) if step is not None else ()
    ) or ()
    for index, name in enumerate(STRUCTURAL_FEATURES):
        value = structural_rank[index] if index < len(structural_rank) else 0.0
        if isinstance(value, (int, float)):
            features[name] = _signed_quality(value)

    features["goal_deductions"] = _bounded_count(
        _get(record, "goal_deduction_count", 0)
    )
    features["target_assertions"] = _bounded_count(
        _get(record, "relation_target_assertion_count", 0)
    )
    features["relation_support"] = _bounded_count(
        _get(record, "relation_support_weight", 0)
    )
    features["near_goal_relations"] = _bounded_count(
        _get(record, "relation_near_goal_count", 0)
    )
    features["all_deductions"] = _bounded_count(
        _get(record, "all_deduction_count", 0)
    )
    features["transition_potential"] = _bounded_count(
        _get(record, "relation_transition_potential", 0.0)
    )
    features["transition_channel_coverage"] = _bounded_count(
        _get(record, "relation_transition_channel_coverage", 0)
    )

    witnesses = _get(record, "frontier_witnesses", ()) or ()
    distances = [float(_get(item, "distance_to_goal", 1_000_000)) for item in witnesses]
    overlaps = [float(_get(item, "goal_support_overlap", 0)) for item in witnesses]
    features["frontier_distance_quality"] = (
        _inverse_count(min(distances)) if distances else 0.0
    )
    features["frontier_goal_overlap"] = _bounded_count(max(overlaps, default=0.0))
    features["frontier_witness_count"] = _bounded_count(len(witnesses))

    obligations = _get(record, "backward_obligations", ()) or ()
    demands = _get(record, "open_relation_demands", ()) or ()
    features["backward_obligation_count"] = _bounded_count(len(obligations))
    features["open_demand_quality"] = _inverse_count(len(demands)) if obligations else 0.0

    # Older trace schemas do not contain algebraic-residual measurements.
    # Missing is epistemic uncertainty, not a perfect zero residual.
    if _has(record, "ar_supported_goal_count"):
        features["ar_supported_goals"] = _bounded_count(
            _get(record, "ar_supported_goal_count", 0)
        )
        features["ar_closed_goals"] = _bounded_count(
            _get(record, "ar_closed_goal_count", 0)
        )
        features["ar_support_quality"] = _inverse_count(
            _get(record, "ar_residual_support_size", 0)
        )
        features["ar_l1_quality"] = _inverse_count(
            _get(record, "ar_residual_l1_weight", 0.0)
        )
        features["ar_known_rank"] = _bounded_count(
            _get(record, "ar_known_rank", 0)
        )
    else:
        for name in FEATURE_GROUPS["algebra"]:
            features[name] = 0.5
    features["elapsed_quality"] = _inverse_count(_get(record, "elapsed_seconds", 0.0))
    features["deduction_cost_quality"] = _inverse_count(
        _get(record, "all_deduction_count", 0)
    )
    features["valid_state"] = 0.0 if _get(record, "error", None) else 1.0
    return features


def softplus(value: float) -> float:
    if value > 30.0:
        return value
    if value < -30.0:
        return math.exp(value)
    return math.log1p(math.exp(value))


def sigmoid(value: float) -> float:
    if value >= 0.0:
        inverse = math.exp(-value)
        return 1.0 / (1.0 + inverse)
    exponent = math.exp(value)
    return exponent / (1.0 + exponent)


@dataclass(frozen=True)
class ConsensusTrace:
    iteration: int
    consensus: float
    primal_residual: float
    dual_residual: float


@dataclass(frozen=True)
class ControllerScore:
    score: float
    consensus: float
    disagreement: float
    local_scores: Mapping[str, float]
    trace: tuple[ConsensusTrace, ...]


@dataclass(frozen=True)
class ControllerParameters:
    raw_weights: Mapping[str, tuple[float, ...]]
    biases: Mapping[str, float]
    trust_logits: Mapping[str, float]
    log_rho: float = 0.0
    risk_logit: float = -2.0
    iterations: int = 12

    @classmethod
    def uniform(cls) -> "ControllerParameters":
        raw = 0.541324854612918  # softplus(raw) == 1
        return cls(
            raw_weights={
                name: tuple(raw for _ in features)
                for name, features in FEATURE_GROUPS.items()
            },
            biases={name: 0.0 for name in FEATURE_GROUPS},
            trust_logits={name: raw for name in FEATURE_GROUPS},
        )

    @property
    def parameter_count(self) -> int:
        return (
            sum(len(values) for values in self.raw_weights.values())
            + len(self.biases)
            + len(self.trust_logits)
            + 2
        )

    def validate(self) -> None:
        if set(self.raw_weights) != set(FEATURE_GROUPS):
            raise ValueError("controller stalk set does not match the feature schema")
        if set(self.biases) != set(FEATURE_GROUPS):
            raise ValueError("controller bias set does not match the feature schema")
        if set(self.trust_logits) != set(FEATURE_GROUPS):
            raise ValueError("controller trust set does not match the feature schema")
        for name, features in FEATURE_GROUPS.items():
            if len(self.raw_weights[name]) != len(features):
                raise ValueError(f"wrong weight count for stalk {name}")
        if self.iterations < 1:
            raise ValueError("ADMM iteration count must be positive")


class DifferentiableProofController:
    """Monotone local circuits plus an unrolled scalar consensus ADMM cell."""

    def __init__(self, parameters: ControllerParameters | None = None) -> None:
        self.parameters = parameters or ControllerParameters.uniform()
        self.parameters.validate()

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "DifferentiableProofController":
        if payload.get("schema") != SCHEMA_VERSION:
            raise ValueError("unsupported differentiable controller schema")
        if set(payload.get("feature_names", ())) != set(FEATURE_NAMES):
            raise ValueError("controller feature schema mismatch")
        forbidden = FORBIDDEN_INPUTS.intersection(payload.get("feature_names", ()))
        if forbidden:
            raise ValueError(f"forbidden memorization features: {sorted(forbidden)}")
        raw_weights = {
            str(name): tuple(float(value) for value in values)
            for name, values in dict(payload["raw_weights"]).items()  # type: ignore[arg-type]
        }
        parameters = ControllerParameters(
            raw_weights=raw_weights,
            biases={
                str(name): float(value)
                for name, value in dict(payload["biases"]).items()  # type: ignore[arg-type]
            },
            trust_logits={
                str(name): float(value)
                for name, value in dict(payload["trust_logits"]).items()  # type: ignore[arg-type]
            },
            log_rho=float(payload["log_rho"]),
            risk_logit=float(payload["risk_logit"]),
            iterations=int(payload.get("iterations", 12)),
        )
        return cls(parameters)

    @classmethod
    def load(cls, path: Path) -> "DifferentiableProofController":
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if "controller" in payload:
            payload = payload["controller"]
        return cls.from_dict(payload)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": SCHEMA_VERSION,
            "truth_plane": "native_certificate_replay_only",
            "feature_names": list(FEATURE_NAMES),
            "forbidden_inputs": sorted(FORBIDDEN_INPUTS),
            "feature_groups": {
                name: list(features) for name, features in FEATURE_GROUPS.items()
            },
            "raw_weights": {
                name: list(values) for name, values in self.parameters.raw_weights.items()
            },
            "biases": dict(self.parameters.biases),
            "trust_logits": dict(self.parameters.trust_logits),
            "log_rho": self.parameters.log_rho,
            "risk_logit": self.parameters.risk_logit,
            "iterations": self.parameters.iterations,
            "parameter_count": self.parameters.parameter_count,
        }

    def local_scores(self, features: Mapping[str, float]) -> dict[str, float]:
        output: dict[str, float] = {}
        for stalk, names in FEATURE_GROUPS.items():
            weights = [softplus(value) for value in self.parameters.raw_weights[stalk]]
            normalizer = max(sum(weights), 1e-12)
            evidence = sum(
                weight * min(max(float(features.get(name, 0.0)), 0.0), 1.0)
                for weight, name in zip(weights, names)
            ) / normalizer
            output[stalk] = sigmoid(evidence + self.parameters.biases[stalk])
        return output

    def score_features(self, features: Mapping[str, float]) -> ControllerScore:
        local = self.local_scores(features)
        names = tuple(FEATURE_GROUPS)
        proposals = [local[name] for name in names]
        trusts = [
            softplus(self.parameters.trust_logits[name]) + 0.05 for name in names
        ]
        rho = softplus(self.parameters.log_rho) + 0.05
        z = sum(proposals) / len(proposals)
        dual = [0.0 for _ in proposals]
        trace: list[ConsensusTrace] = []
        for iteration in range(1, self.parameters.iterations + 1):
            previous = z
            private = [
                (trust * proposal + rho * (z - multiplier)) / (trust + rho)
                for trust, proposal, multiplier in zip(trusts, proposals, dual)
            ]
            z = sum(value + multiplier for value, multiplier in zip(private, dual)) / len(private)
            dual = [
                multiplier + value - z
                for multiplier, value in zip(dual, private)
            ]
            primal = math.sqrt(sum((value - z) ** 2 for value in private))
            trace.append(
                ConsensusTrace(
                    iteration=iteration,
                    consensus=z,
                    primal_residual=primal,
                    dual_residual=rho * abs(z - previous),
                )
            )
        disagreement = math.sqrt(
            sum((value - sum(proposals) / len(proposals)) ** 2 for value in proposals)
            / len(proposals)
        )
        # The disagreement gate is a bounded abstention prior.  Leaving it
        # unbounded lets a tiny training split dominate all local evidence
        # after a schema/distribution shift.
        risk = MAX_DISAGREEMENT_PENALTY * sigmoid(self.parameters.risk_logit)
        score = z - risk * disagreement
        return ControllerScore(score, z, disagreement, local, tuple(trace))

    def score_record(self, record: object) -> ControllerScore:
        return self.score_features(extract_controller_features(record))
