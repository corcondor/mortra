"""Recognition representation policy and self-improvement for geometric reading.

Controls the active bundle of geometric predicates, structural features, and
frame references used during character description and reading. Implements
Pareto-optimal policy selection over validation deformations and persistence.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from fractions import Fraction
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from math_os_prototype import geometry_raster as raster
from math_os_prototype import geometry_reading as reading


@dataclass(frozen=True)
class RecognitionPolicy:
    """Active feature bundle configuration for geometric character reading."""
    policy_id: str
    use_relations: bool
    use_structure: bool
    frame: bool
    grid: int = 1
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> RecognitionPolicy:
        return cls(
            policy_id=str(d.get("policy_id", "custom")),
            use_relations=bool(d.get("use_relations", True)),
            use_structure=bool(d.get("use_structure", True)),
            frame=bool(d.get("frame", True)),
            grid=int(d.get("grid", 1)),
            description=str(d.get("description", "")),
        )


# Default starting policy (Model A: Full relations + structure + frame)
DEFAULT_POLICY = RecognitionPolicy(
    policy_id="model_a_full",
    use_relations=True,
    use_structure=True,
    frame=True,
    grid=1,
    description="Full relational invariants, structural topology, and reference frame",
)

# Candidate policies for self-improvement search
CANDIDATE_POLICIES = [
    RecognitionPolicy(
        policy_id="model_a_full",
        use_relations=True,
        use_structure=True,
        frame=True,
        grid=1,
        description="Full relations, structure, and frame",
    ),
    RecognitionPolicy(
        policy_id="model_b_structure_only",
        use_relations=False,
        use_structure=True,
        frame=False,
        grid=1,
        description="Pure structure only (holes, degrees, stroke count)",
    ),
    RecognitionPolicy(
        policy_id="model_c_relations_only",
        use_relations=True,
        use_structure=False,
        frame=True,
        grid=1,
        description="Pure relations and frame (no topology counts)",
    ),
    RecognitionPolicy(
        policy_id="model_d_unframed_relations",
        use_relations=True,
        use_structure=True,
        frame=False,
        grid=1,
        description="Relations and structure without reference frame",
    ),
]


def evaluate_policy_on_dataset(
    policy: RecognitionPolicy,
    reference_alphabet: Mapping[str, Any],
    eval_letters: Mapping[str, Any],
    *,
    scale: int = 8,
    radius: Fraction = Fraction(3, 8),
) -> dict[str, Any]:
    """Measure the accuracy, average margin, and description size of a policy."""
    rad = radius * scale
    lib = reading.library_from(
        reference_alphabet,
        grid=policy.grid,
        use_relations=policy.use_relations,
        use_structure=policy.use_structure,
        frame=policy.frame,
    )

    correct = 0
    total = len(eval_letters)
    total_margin = 0.0
    total_predicates = sum(sum(desc.values()) for desc in lib.values())
    avg_predicates_per_letter = total_predicates / max(1, len(lib))

    for char, strokes in eval_letters.items():
        segs = [
            (
                (Fraction(a[0]) * scale, Fraction(a[1]) * scale),
                (Fraction(b[0]) * scale, Fraction(b[1]) * scale),
            )
            for a, b in raster.polyline_segments(strokes)
        ]
        xs = [v for a, b in segs for v in (a[0], b[0])]
        ys = [v for a, b in segs for v in (a[1], b[1])]
        w = int(max(xs) - min(xs) + 2 * scale)
        h = int(max(ys) - min(ys) + 2 * scale)
        moved = [
            (
                (a[0] - min(xs) + scale, a[1] - min(ys) + scale),
                (b[0] - min(xs) + scale, b[1] - min(ys) + scale),
            )
            for a, b in segs
        ]
        bm = raster.render(moved, rad, w, h)

        res = reading.read(
            bm,
            lib,
            grid=policy.grid,
            use_relations=policy.use_relations,
            use_structure=policy.use_structure,
            frame=policy.frame,
        )
        if res["letter"] == char:
            correct += 1
        total_margin += float(res["margin"])

    accuracy = correct / max(1, total)
    mean_margin = total_margin / max(1, total)

    return {
        "policy_id": policy.policy_id,
        "accuracy": accuracy,
        "correct": correct,
        "total": total,
        "mean_margin": mean_margin,
        "avg_predicates": avg_predicates_per_letter,
    }


def train_recognition_policy(
    reference_alphabet: Mapping[str, Any],
    validation_letters: Mapping[str, Any],
    current_policy: RecognitionPolicy | None = None,
) -> tuple[RecognitionPolicy, dict[str, Any]]:
    """Train/select the optimal recognition policy using Pareto dominance over validation data.

    Objectives:
    - Maximize validation accuracy
    - Minimize average predicate count (compression / compactness)
    - Maximize recognition margin
    """
    current = current_policy or DEFAULT_POLICY
    results = []

    for candidate in CANDIDATE_POLICIES:
        eval_res = evaluate_policy_on_dataset(candidate, reference_alphabet, validation_letters)
        results.append((candidate, eval_res))

    # Pareto comparison: candidate A beats candidate B if:
    # A.accuracy >= B.accuracy and A.avg_predicates <= B.avg_predicates and A.mean_margin >= B.mean_margin
    # with at least one strict inequality.
    best_candidate = current
    best_score = (-1.0, 999999.0, -1.0)  # (accuracy, -avg_predicates, mean_margin)

    # Ranking: prioritize accuracy above threshold, then compactness, then margin
    for cand, metrics in results:
        # Score tuple: (accuracy, -predicates/1000, margin)
        score = (metrics["accuracy"], -metrics["avg_predicates"] / 1000.0, metrics["mean_margin"])
        if score > best_score:
            best_score = score
            best_candidate = cand

    updated = best_candidate.policy_id != current.policy_id

    training_report = {
        "previous_policy": current.to_dict(),
        "selected_policy": best_candidate.to_dict(),
        "policy_updated": updated,
        "candidates_evaluated": [
            {"policy": c.to_dict(), "metrics": m} for c, m in results
        ],
    }

    return best_candidate, training_report


def save_recognition_policy(policy: RecognitionPolicy, path: Path | str) -> None:
    """Save policy checkpoint to a JSON file."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(policy.to_dict(), f, indent=2)


def load_recognition_policy(path: Path | str) -> RecognitionPolicy:
    """Load policy checkpoint from a JSON file, falling back to DEFAULT_POLICY if missing."""
    p = Path(path)
    if not p.exists():
        return DEFAULT_POLICY
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return RecognitionPolicy.from_dict(data)
