"""Outcome-trained ordering of research actions, separate from certification.

This is a shared linear UCB model, not a theorem generator or a difficulty
estimator. Only pre-execution structural measurements enter the model. The
caller retains all mathematical objects and checks each selected action.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np
from math_os_prototype.representation_progress import TARGET as PROGRESS_TARGET, validate_evidence


SCHEMA = "mortra.research-action-policy.v3"
REWARD_DEFINITIONS = {
    "compiled_candidate": "at least one exact problem candidate compiled",
    "new_verified_relation": "at least one new relation verified beyond current certified rewrites; not literature novelty",
    PROGRESS_TARGET: "positive certified semantic description savings including definition cost on a subsequent fixed-size training probe",
}
FEATURE_NAMES = (
    "bias", "alphabet_size", "state_dimension_present", "state_dimension",
    "unbounded_composition", "observation_degree_present", "observation_degree",
    "observation_term_count_present", "observation_term_count",
    "construction_container_count", "observation_container_count",
)


def _count_feature(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("structural counts must be nonnegative finite numbers")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError("structural counts must be nonnegative finite numbers")
    return math.log1p(number) / (1.0 + math.log1p(number))


def _containers(value: object) -> int:
    # Names, expression strings, coefficient values and labels are not features.
    if isinstance(value, Mapping):
        return 1 + sum(_containers(item) for item in value.values())
    if isinstance(value, (tuple, list)):
        return 1 + sum(_containers(item) for item in value)
    return 0


def structural_action_features(
    alphabet_size: int,
    metrics: Mapping[str, object],
    construction_payload: Mapping[str, object],
    observation_payload: Mapping[str, object],
) -> tuple[float, ...]:
    """Allowlist measurements; never pass an adapter or private result to policy."""
    def measured(payload: Mapping[str, object], key: str) -> tuple[float, float]:
        return (1.0, _count_feature(payload[key])) if key in payload else (0.0, 0.0)

    unbounded = metrics.get("unbounded_composition", False)
    if not isinstance(unbounded, bool):
        raise ValueError("unbounded_composition must be boolean")
    return (
        1.0, _count_feature(alphabet_size),
        *measured(metrics, "state_dimension"), float(unbounded),
        *measured(observation_payload, "degree"),
        *measured(observation_payload, "term_count"),
        _count_feature(_containers(construction_payload)),
        _count_feature(_containers(observation_payload)),
    )


def _vector(features: Sequence[float], size: int = len(FEATURE_NAMES)) -> np.ndarray:
    vector = np.asarray(features, dtype=float)
    if vector.shape != (size,) or not np.isfinite(vector).all():
        raise ValueError("invalid research action feature vector")
    if np.any(vector < 0) or np.any(vector > 1) or vector[0] != 1:
        raise ValueError("research action features must be bounded with unit bias")
    return vector


@dataclass
class ResearchActionPolicy:
    environment_fingerprint: str
    exploration: float = 0.5
    feedback: list[dict[str, object]] = field(default_factory=list)
    feature_names: tuple[str, ...] = FEATURE_NAMES
    reward_target: str = "compiled_candidate"

    def __post_init__(self) -> None:
        if not self.environment_fingerprint:
            raise ValueError("policy needs an execution-environment fingerprint")
        if self.reward_target not in REWARD_DEFINITIONS:
            raise ValueError("unknown research reward target")
        if not math.isfinite(self.exploration) or self.exploration < 0:
            raise ValueError("exploration must be nonnegative and finite")
        self.feature_names = tuple(self.feature_names)
        if (
            self.feature_names[:len(FEATURE_NAMES)] != FEATURE_NAMES
            or len(set(self.feature_names)) != len(self.feature_names)
            or any(not isinstance(name, str) or not name for name in self.feature_names)
        ):
            raise ValueError("invalid policy feature vocabulary")
        rows = self.feedback
        self.feedback = []
        self._a = np.eye(len(self.feature_names))
        self._b = np.zeros(len(self.feature_names))
        self._seen: set[tuple[str, str]] = set()
        for row in rows:
            self.observe(**row)

    def scores(self, features: Sequence[Sequence[float]]) -> list[float]:
        if not features:
            return []
        x = np.stack([_vector(row, len(self.feature_names)) for row in features])
        theta = np.linalg.solve(self._a, self._b)
        variance = np.sum(x * np.linalg.solve(self._a, x.T).T, axis=1)
        return (x @ theta + self.exploration * np.sqrt(np.maximum(0, variance))).tolist()

    def observe(
        self, *, features: Sequence[float], reward: float,
        source_domain: str, pair_id: str, evidence: Mapping[str, object],
    ) -> bool:
        vector = _vector(features, len(self.feature_names))
        if not isinstance(source_domain, str) or not source_domain:
            raise ValueError("feedback needs source provenance")
        if not isinstance(pair_id, str) or not pair_id:
            raise ValueError("feedback needs an executed pair identifier")
        if self.reward_target == PROGRESS_TARGET:
            if type(reward) not in (int, float) or not math.isfinite(reward) or not 0 <= reward <= 1:
                raise ValueError("description progress reward must lie in [0,1]")
        elif reward not in (0.0, 1.0):
            raise ValueError("research reward is binary")
        if not isinstance(evidence, Mapping) or evidence.get("executed") is not True:
            raise ValueError("unexecuted hypotheses are not learning feedback")
        if self.reward_target == PROGRESS_TARGET:
            validate_evidence(evidence, reward)
        elif self.reward_target == "compiled_candidate":
            count = evidence.get("compiled_candidate_count")
        else:
            count = evidence.get("verified_new_relation_count")
            hashes = evidence.get("certificate_hashes")
            if (not isinstance(hashes, list) or type(count) is not int or len(hashes) != count
                    or any(not isinstance(h, str) or len(h) != 64
                           or any(c not in "0123456789abcdef" for c in h) for h in hashes)):
                raise ValueError("verified-relation feedback needs certificate references")
        if self.reward_target != PROGRESS_TARGET and (type(count) is not int or count < 0 or bool(count) != bool(reward)):
            raise ValueError("reward must match the executed result")
        key = (source_domain, pair_id)
        if key in self._seen:
            return False
        self._seen.add(key)
        self._a += np.outer(vector, vector)
        self._b += float(reward) * vector
        self.feedback.append({
            "features": vector.tolist(), "reward": float(reward),
            "source_domain": source_domain, "pair_id": pair_id,
            "evidence": deepcopy(dict(evidence)),
        })
        return True

    def assert_holdout(self, source_domain: str) -> None:
        if any(row["source_domain"] == source_domain for row in self.feedback):
            raise ValueError("held-out source already occurs in policy training feedback")

    def reencode_feedback(self, feature_names, features_by_pair) -> None:
        """Transactionally rebuild the model without changing observed outcomes."""
        if set(features_by_pair) != self._seen:
            raise ValueError("representation refinement must preserve every feedback record")
        replacement = ResearchActionPolicy(self.environment_fingerprint, self.exploration,
                                           feature_names=tuple(feature_names), reward_target=self.reward_target)
        for row in self.feedback:
            replacement.observe(**{
                **row,
                "features": features_by_pair[(row["source_domain"], row["pair_id"])],
            })
        self.__dict__.update(replacement.__dict__)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": SCHEMA, "feature_names": list(self.feature_names),
            "environment_fingerprint": self.environment_fingerprint,
            "exploration": self.exploration, "feedback": deepcopy(self.feedback),
            "reward_target": self.reward_target,
            "reward_definition": REWARD_DEFINITIONS[self.reward_target],
            "reward_is_novelty_or_difficulty": False,
        }

    def digest(self) -> str:
        payload = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)

    @classmethod
    def load(cls, path: Path, *, environment_fingerprint: str) -> "ResearchActionPolicy":
        from math_os_prototype.shared_json import read
        payload = read(path)
        return cls.from_dict(payload, environment_fingerprint=environment_fingerprint)

    @classmethod
    def from_dict(cls, payload, *, environment_fingerprint: str) -> "ResearchActionPolicy":
        if payload.get("schema") not in {SCHEMA, "mortra.research-action-policy.v1", "mortra.research-action-policy.v2"}:
            raise ValueError("unsupported research action policy")
        if payload.get("environment_fingerprint") != environment_fingerprint:
            raise ValueError("policy execution environment changed; retrain or explicitly migrate")
        target = payload.get("reward_target", "compiled_candidate")
        if target not in REWARD_DEFINITIONS or payload.get("reward_definition") != REWARD_DEFINITIONS[target]:
            raise ValueError("research reward definition changed")
        return cls(environment_fingerprint, payload["exploration"], payload["feedback"],
                   tuple(payload["feature_names"]), target)
