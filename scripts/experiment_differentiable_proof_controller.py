"""Train and test MORTRA's small differentiable proof-search controller.

This script consumes native Newclid/Yuclid search traces.  Labels are derived
only from replayed solved paths.  Problem identifiers are used to construct a
held-out split, never as model inputs.  The trained controller can prioritize
search, but cannot certify a theorem.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from worker.backend.differentiable_proof_controller import (  # noqa: E402
    FEATURE_GROUPS,
    FEATURE_NAMES,
    MAX_DISAGREEMENT_PENALTY,
    SCHEMA_VERSION,
    ControllerParameters,
    DifferentiableProofController,
    extract_controller_features,
)


@dataclass(frozen=True)
class RankingGroup:
    problem: str
    depth: int
    solved_depth: int
    records: tuple[Mapping[str, object], ...]
    positive_index: int

    @property
    def nonterminal(self) -> bool:
        return self.depth < self.solved_depth


def step_key(step: Mapping[str, object]) -> str:
    inputs = ",".join(str(item) for item in step.get("inputs", ()))
    return f"{step.get('family')}({inputs})->{step.get('output')}"


def record_path(record: Mapping[str, object]) -> tuple[str, ...]:
    return tuple(step_key(step) for step in record.get("steps", ()))  # type: ignore[arg-type]


def load_groups(paths: Sequence[Path]) -> tuple[RankingGroup, ...]:
    groups: list[RankingGroup] = []
    for path in paths:
        with path.open("r", encoding="utf-8") as handle:
            artifact = json.load(handle)
        if not artifact.get("solved") or not artifact.get("solved_path"):
            continue
        problem = str(artifact.get("problem_name") or path.stem)
        solved_path = tuple(str(item) for item in artifact["solved_path"])
        by_depth: dict[int, list[Mapping[str, object]]] = {}
        for record in artifact.get("records", ()):  # type: ignore[assignment]
            if record.get("error"):
                continue
            path_key = record_path(record)
            if not path_key:
                continue
            by_depth.setdefault(len(path_key), []).append(record)
        for depth, records in sorted(by_depth.items()):
            if depth > len(solved_path):
                continue
            prefix = solved_path[:depth]
            positive = [
                index for index, record in enumerate(records) if record_path(record) == prefix
            ]
            if len(positive) != 1:
                continue
            groups.append(
                RankingGroup(
                    problem=problem,
                    depth=depth,
                    solved_depth=len(solved_path),
                    records=tuple(records),
                    positive_index=positive[0],
                )
            )
    return tuple(groups)


def feature_vector(record: Mapping[str, object]) -> tuple[float, ...]:
    values = extract_controller_features(record)
    return tuple(values[name] for name in FEATURE_NAMES)


def _torch_model(seed: int, iterations: int, architecture: str):
    try:
        import torch
    except ImportError as exc:  # pragma: no cover - exercised by the experiment host
        raise RuntimeError("PyTorch is required only for controller training") from exc

    torch.manual_seed(seed)
    torch.set_default_dtype(torch.float64)
    feature_index = {name: index for index, name in enumerate(FEATURE_NAMES)}
    group_indices = {
        name: torch.tensor([feature_index[item] for item in features], dtype=torch.long)
        for name, features in FEATURE_GROUPS.items()
    }
    names = tuple(FEATURE_GROUPS)

    class TorchConsensusController(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            raw = 0.541324854612918
            self.raw_weights = torch.nn.ParameterList(
                [
                    torch.nn.Parameter(torch.full((len(FEATURE_GROUPS[name]),), raw))
                    for name in names
                ]
            )
            self.biases = torch.nn.Parameter(torch.zeros(len(names)))
            self.trust_logits = torch.nn.Parameter(torch.full((len(names),), raw))
            self.log_rho = torch.nn.Parameter(torch.tensor(0.0))
            self.risk_logit = torch.nn.Parameter(torch.tensor(-2.0))
            if architecture == "trust-only":
                # Keep every local mathematical score fixed.  Only the six
                # stalk reliabilities and the two consensus controls learn.
                # This is the strict interpretation of "differentiable
                # coordination only": no feature/rule weight can encode a
                # proof pattern.
                for parameter in self.raw_weights:
                    parameter.requires_grad_(False)
                self.biases.requires_grad_(False)

        def forward(self, values):
            proposals = []
            for index, name in enumerate(names):
                weights = torch.nn.functional.softplus(self.raw_weights[index])
                local = values.index_select(1, group_indices[name])
                evidence = (local * weights).sum(dim=1) / weights.sum().clamp_min(1e-12)
                proposals.append(torch.sigmoid(evidence + self.biases[index]))
            proposal = torch.stack(proposals, dim=1)
            trust = torch.nn.functional.softplus(self.trust_logits) + 0.05
            rho = torch.nn.functional.softplus(self.log_rho) + 0.05
            consensus = proposal.mean(dim=1)
            dual = torch.zeros_like(proposal)
            for _ in range(iterations):
                private = (
                    trust.unsqueeze(0) * proposal
                    + rho * (consensus.unsqueeze(1) - dual)
                ) / (trust.unsqueeze(0) + rho)
                consensus = (private + dual).mean(dim=1)
                dual = dual + private - consensus.unsqueeze(1)
            disagreement = torch.sqrt(
                ((proposal - proposal.mean(dim=1, keepdim=True)) ** 2).mean(dim=1)
                + 1e-12
            )
            risk = MAX_DISAGREEMENT_PENALTY * torch.sigmoid(self.risk_logit)
            return consensus - risk * disagreement

        def export(self) -> ControllerParameters:
            return ControllerParameters(
                raw_weights={
                    name: tuple(float(value) for value in self.raw_weights[index].detach())
                    for index, name in enumerate(names)
                },
                biases={
                    name: float(self.biases[index].detach())
                    for index, name in enumerate(names)
                },
                trust_logits={
                    name: float(self.trust_logits[index].detach())
                    for index, name in enumerate(names)
                },
                log_rho=float(self.log_rho.detach()),
                risk_logit=float(self.risk_logit.detach()),
                iterations=iterations,
            )

    model = TorchConsensusController()
    trainable = sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)
    return torch, model, trainable


def _flatten_groups(groups: Sequence[RankingGroup]):
    features: list[tuple[float, ...]] = []
    pairs: list[tuple[int, int]] = []
    pair_weights: list[float] = []
    for group in groups:
        offset = len(features)
        features.extend(feature_vector(record) for record in group.records)
        positive = offset + group.positive_index
        negatives = [
            offset + index
            for index in range(len(group.records))
            if index != group.positive_index
        ]
        pairs.extend((positive, negative) for negative in negatives)
        # Do not let a problem with a larger enumerated frontier dominate.
        pair_weights.extend(1.0 / max(len(negatives), 1) for _ in negatives)
    return features, pairs, pair_weights


def pairwise_accuracy(
    controller: DifferentiableProofController,
    groups: Sequence[RankingGroup],
) -> float:
    total = 0
    correct = 0
    for group in groups:
        scores = [controller.score_record(record).score for record in group.records]
        positive = scores[group.positive_index]
        for index, score in enumerate(scores):
            if index == group.positive_index:
                continue
            total += 1
            correct += positive > score
    return correct / total if total else 0.0


def fit_controller(
    groups: Sequence[RankingGroup],
    *,
    validation: Sequence[RankingGroup] = (),
    seed: int,
    epochs: int,
    learning_rate: float,
    iterations: int,
    architecture: str,
) -> tuple[DifferentiableProofController, dict[str, object]]:
    torch, model, trainable_parameter_count = _torch_model(
        seed, iterations, architecture
    )
    vectors, pairs, pair_weights = _flatten_groups(groups)
    if not pairs:
        raise ValueError("training requires at least one positive/negative proof-prefix pair")
    values = torch.tensor(vectors)
    positive = torch.tensor([item[0] for item in pairs], dtype=torch.long)
    negative = torch.tensor([item[1] for item in pairs], dtype=torch.long)
    weights = torch.tensor(pair_weights)
    weights = weights / weights.sum().clamp_min(1e-12)
    trainable_parameters = [
        parameter for parameter in model.parameters() if parameter.requires_grad
    ]
    optimizer = torch.optim.Adam(trainable_parameters, lr=learning_rate)
    best_state = None
    best_metric = (-math.inf, -math.inf, -math.inf)
    history: list[dict[str, float]] = []
    for epoch in range(1, epochs + 1):
        optimizer.zero_grad()
        scores = model(values)
        difference = scores.index_select(0, positive) - scores.index_select(0, negative)
        ranking_loss = (
            torch.nn.functional.softplus(-difference * 6.0) * weights
        ).sum()
        regularizer = 1e-4 * sum(
            (parameter**2).mean() for parameter in trainable_parameters
        )
        loss = ranking_loss + regularizer
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=5.0)
        optimizer.step()

        if epoch == 1 or epoch % 25 == 0 or epoch == epochs:
            exported = DifferentiableProofController(model.export())
            train_accuracy = pairwise_accuracy(exported, groups)
            validation_accuracy = (
                pairwise_accuracy(exported, validation) if validation else train_accuracy
            )
            history.append(
                {
                    "epoch": float(epoch),
                    "loss": float(loss.detach()),
                    "train_pairwise_accuracy": train_accuracy,
                    "validation_pairwise_accuracy": validation_accuracy,
                }
            )
            metric = (validation_accuracy, train_accuracy, -float(loss.detach()))
            if metric > best_metric:
                best_metric = metric
                best_state = {
                    name: value.detach().clone() for name, value in model.state_dict().items()
                }
    if best_state is not None:
        model.load_state_dict(best_state)
    controller = DifferentiableProofController(model.export())
    return controller, {
        "architecture": architecture,
        "trainable_parameter_count": trainable_parameter_count,
        "serialized_parameter_count": controller.parameters.parameter_count,
        "epochs": epochs,
        "learning_rate": learning_rate,
        "pair_count": len(pairs),
        "group_count": len(groups),
        "best_validation_pairwise_accuracy": best_metric[0],
        "best_train_pairwise_accuracy": best_metric[1],
        "history": history,
    }


def _rank_from_order(order: Sequence[int], positive_index: int) -> int:
    return order.index(positive_index) + 1


def _structural_key(record: Mapping[str, object]) -> tuple[float, ...]:
    steps = record.get("steps", ())
    step = steps[-1] if steps else {}  # type: ignore[index]
    rank = step.get("structural_rank", ())  # type: ignore[union-attr]
    return tuple(float(value) for value in rank[:17] if isinstance(value, (int, float)))


def _legacy_key(record: Mapping[str, object]) -> tuple[float, ...]:
    witnesses = record.get("frontier_witnesses", ()) or ()
    distances = [float(item.get("distance_to_goal", 1_000_000)) for item in witnesses]
    overlaps = [float(item.get("goal_support_overlap", 0)) for item in witnesses]
    return (
        -float(record.get("ar_closed_goal_count", 0) or 0),
        float(record.get("ar_residual_support_size", 0) or 0),
        float(record.get("ar_residual_l1_weight", 0.0) or 0.0),
        -float(record.get("relation_transition_potential", 0.0) or 0.0),
        min(distances, default=1_000_000),
        -max(overlaps, default=0.0),
        *_structural_key(record),
    )


def evaluate_ranking(
    controller: DifferentiableProofController,
    groups: Sequence[RankingGroup],
    *,
    random_trials: int = 200,
    seed: int = 0,
) -> dict[str, object]:
    methods = ("structural", "closure", "legacy_pareto", "differentiable_consensus")
    ranks: dict[str, list[float]] = {name: [] for name in methods}
    nonterminal_ranks: dict[str, list[float]] = {name: [] for name in methods}
    random_ranks: list[float] = []
    random_nonterminal: list[float] = []
    records: list[dict[str, object]] = []
    for group_index, group in enumerate(groups):
        indices = list(range(len(group.records)))
        orders = {
            "structural": sorted(indices, key=lambda index: _structural_key(group.records[index])),
            "closure": sorted(
                indices,
                key=lambda index: (
                    -float(group.records[index].get("goal_deduction_count", 0) or 0),
                    -float(group.records[index].get("all_deduction_count", 0) or 0),
                    _structural_key(group.records[index]),
                ),
            ),
            "legacy_pareto": sorted(indices, key=lambda index: _legacy_key(group.records[index])),
            "differentiable_consensus": sorted(
                indices,
                key=lambda index: controller.score_record(group.records[index]).score,
                reverse=True,
            ),
        }
        group_ranks = {
            method: _rank_from_order(order, group.positive_index)
            for method, order in orders.items()
        }
        for method, rank in group_ranks.items():
            ranks[method].append(float(rank))
            if group.nonterminal:
                nonterminal_ranks[method].append(float(rank))
        rng = random.Random(seed + group_index * 104729)
        trial_ranks = []
        for _ in range(random_trials):
            order = indices.copy()
            rng.shuffle(order)
            trial_ranks.append(float(_rank_from_order(order, group.positive_index)))
        random_rank = sum(trial_ranks) / len(trial_ranks)
        random_ranks.append(random_rank)
        if group.nonterminal:
            random_nonterminal.append(random_rank)
        records.append(
            {
                "problem": group.problem,
                "depth": group.depth,
                "solved_depth": group.solved_depth,
                "candidate_count": len(group.records),
                "nonterminal": group.nonterminal,
                "ranks": {**group_ranks, "random_mean": random_rank},
            }
        )

    def summarize(values: Sequence[float]) -> dict[str, float | int]:
        if not values:
            return {"groups": 0, "mrr": 0.0, "mean_rank": 0.0, "hit_at_8": 0.0}
        return {
            "groups": len(values),
            "mrr": sum(1.0 / value for value in values) / len(values),
            "mean_rank": sum(values) / len(values),
            "hit_at_8": sum(value <= 8.0 for value in values) / len(values),
        }

    summary = {method: summarize(values) for method, values in ranks.items()}
    summary["random_mean"] = summarize(random_ranks)
    nonterminal = {
        method: summarize(values) for method, values in nonterminal_ranks.items()
    }
    nonterminal["random_mean"] = summarize(random_nonterminal)
    return {"all_prefixes": summary, "nonterminal_prefixes": nonterminal, "groups": records}


def cross_validate(
    groups: Sequence[RankingGroup],
    *,
    seed: int,
    epochs: int,
    learning_rate: float,
    iterations: int,
    architecture: str,
) -> dict[str, object]:
    problems = sorted({group.problem for group in groups})
    folds: list[dict[str, object]] = []
    heldout_groups: list[tuple[DifferentiableProofController, RankingGroup]] = []
    for fold_index, problem in enumerate(problems):
        train = [
            group
            for group in groups
            if group.problem != problem and group.nonterminal
        ]
        test = [group for group in groups if group.problem == problem]
        if not train:
            continue
        controller, training = fit_controller(
            train,
            seed=seed + fold_index,
            epochs=epochs,
            learning_rate=learning_rate,
            iterations=iterations,
            architecture=architecture,
        )
        evaluation = evaluate_ranking(controller, test, seed=seed + fold_index)
        folds.append({"heldout_problem": problem, "training": training, "evaluation": evaluation})
        heldout_groups.extend((controller, group) for group in test)

    # Aggregate the held-out score from each fold without ever fitting on that problem.
    aggregate_records = []
    for controller, group in heldout_groups:
        evaluation = evaluate_ranking(controller, [group], random_trials=500, seed=seed)
        aggregate_records.extend(evaluation["groups"])

    def aggregate(section: str, method: str) -> dict[str, float | int]:
        selected = [
            item for item in aggregate_records if section == "all" or item["nonterminal"]
        ]
        values = [
            float(item["ranks"][method])
            for item in selected
        ]
        return {
            "groups": len(values),
            "mrr": sum(1.0 / value for value in values) / len(values) if values else 0.0,
            "mean_rank": sum(values) / len(values) if values else 0.0,
            "hit_at_8": sum(value <= 8.0 for value in values) / len(values) if values else 0.0,
        }

    methods = ("structural", "closure", "legacy_pareto", "differentiable_consensus", "random_mean")
    return {
        "fold_count": len(folds),
        "aggregate": {
            "all_prefixes": {method: aggregate("all", method) for method in methods},
            "nonterminal_prefixes": {
                method: aggregate("nonterminal", method) for method in methods
            },
        },
        "folds": folds,
    }


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts", type=Path, nargs="+", required=True)
    parser.add_argument("--heldout-problem", default="2020_p1")
    parser.add_argument("--calibration-problem", default="2008_p6")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=400)
    parser.add_argument("--learning-rate", type=float, default=0.025)
    parser.add_argument("--admm-iterations", type=int, default=12)
    parser.add_argument(
        "--architecture",
        choices=("full", "trust-only"),
        default="trust-only",
        help="Train all 51 values, or only six stalk trusts plus rho/risk.",
    )
    parser.add_argument("--seed", type=int, default=20260818)
    parser.add_argument("--cross-validate", action="store_true")
    args = parser.parse_args()

    paths = tuple(path.resolve() for path in args.artifacts)
    groups = load_groups(paths)
    train_all = [
        group
        for group in groups
        if group.problem not in {args.heldout_problem, args.calibration_problem}
    ]
    # Beam selection is called only while the proof is still open.  Completed
    # terminal records are evaluated, but are not learning targets.
    train = [group for group in train_all if group.nonterminal]
    calibration_all = [
        group for group in groups if group.problem == args.calibration_problem
    ]
    calibration = [group for group in calibration_all if group.nonterminal]
    heldout = [group for group in groups if group.problem == args.heldout_problem]
    if not train or not heldout:
        raise ValueError("the frozen split needs nonempty train and held-out groups")
    controller, training = fit_controller(
        train,
        validation=calibration,
        seed=args.seed,
        epochs=args.epochs,
        learning_rate=args.learning_rate,
        iterations=args.admm_iterations,
        architecture=args.architecture,
    )
    artifact: dict[str, object] = {
        "experiment": "mortra_differentiable_exact_proof_controller",
        "created_at": datetime.now(UTC).isoformat(),
        "protocol": {
            "uses_external_llm": False,
            "truth_plane": "native_certificate_replay_only",
            "control_plane": "monotone_local_circuits_plus_unrolled_consensus_admm",
            "trainable_architecture": args.architecture,
            "problem_id_is_model_input": False,
            "entity_labels_are_model_inputs": False,
            "numeric_problem_values_are_model_inputs": False,
            "known_auxiliary_points_are_model_inputs": False,
            "theorem_or_construction_names_are_model_inputs": False,
            "schema": SCHEMA_VERSION,
            "seed": args.seed,
        },
        "split": {
            "train_problems": sorted({group.problem for group in train}),
            "calibration_problems": sorted(
                {group.problem for group in calibration_all}
            ),
            "heldout_problems": sorted({group.problem for group in heldout}),
            "train_groups": len(train),
            "calibration_groups": len(calibration),
            "heldout_groups": len(heldout),
            "training_objective": "nonterminal_proof_prefix_ranking_only",
        },
        "sources": [
            {"path": str(path), "sha256": sha256(path)} for path in paths
        ],
        "training": training,
        "controller": controller.to_dict(),
        "train_evaluation": evaluate_ranking(controller, train, seed=args.seed),
        "calibration_evaluation": evaluate_ranking(
            controller, calibration, seed=args.seed + 1
        ),
        "heldout_evaluation": evaluate_ranking(controller, heldout, seed=args.seed + 2),
    }
    if args.cross_validate:
        artifact["leave_one_problem_out"] = cross_validate(
            groups,
            seed=args.seed + 100,
            epochs=max(200, args.epochs // 2),
            learning_rate=args.learning_rate,
            iterations=args.admm_iterations,
            architecture=args.architecture,
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        json.dump(artifact, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({
        "output": str(args.output),
        "architecture": args.architecture,
        "trainable_parameter_count": training["trainable_parameter_count"],
        "serialized_parameter_count": controller.parameters.parameter_count,
        "split": artifact["split"],
        "heldout": artifact["heldout_evaluation"],
        "cross_validation": (
            artifact.get("leave_one_problem_out", {}).get("aggregate")  # type: ignore[union-attr]
            if args.cross_validate
            else None
        ),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
