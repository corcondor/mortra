"""Manifold / Fold Hypothesis Evaluator (PART I).

In accordance with MORTRA principles:
- Does NOT evaluate Fold success merely by 'dimension reduction'.
- Evaluates Fold success by:
    1. Semantic preservation (preserves equivalences and task contracts)
    2. Operation simplification (F o T_i ≈ T'_i o F with cost(T'_i) < cost(T_i))
    3. Search reduction (effective search distance / transformation cost reduction)
    4. Held-out transfer (generalization to unseen states)
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Callable, Sequence

import numpy as np


@dataclass(frozen=True)
class FoldCommutationCheck:
    operation_name: str
    commutation_error: float
    is_exact_commutation: bool
    cost_before: float
    cost_after: float
    cost_reduction_ratio: float


@dataclass(frozen=True)
class FoldEvaluationReport:
    fold_name: str
    semantic_preservation_score: float
    commutation_checks: list[FoldCommutationCheck]
    average_commutation_error: float
    effective_transformation_cost_reduction: float
    search_nodes_reduction_ratio: float
    held_out_transfer_success: bool
    verdict: str  # 'successful_fold', 'partial_fold', 'failed_fold'


class ManifoldFoldEvaluator:
    """Evaluates whether a learned Fold operation simplifies operators and search."""

    def evaluate_fold(
        self,
        fold_name: str,
        fold_fn: Callable[[np.ndarray], np.ndarray],
        operations_before: list[tuple[str, Callable[[np.ndarray], np.ndarray], float]],
        operations_after: list[Callable[[np.ndarray], np.ndarray], float],
        test_states: list[np.ndarray],
        held_out_states: list[np.ndarray],
        baseline_search_cost: float = 100.0,
        folded_search_cost: float = 28.0,
    ) -> FoldEvaluationReport:
        commutation_results = []
        errors = []

        for (op_name, t_before, cost_b), (t_after, cost_a) in zip(operations_before, operations_after):
            op_errors = []
            for x in test_states:
                # Left side: F(T_before(x))
                lhs = fold_fn(t_before(x))
                # Right side: T_after(F(x))
                rhs = t_after(fold_fn(x))
                err = float(np.linalg.norm(lhs - rhs) / (np.linalg.norm(lhs) + 1e-12))
                op_errors.append(err)

            avg_op_err = float(np.mean(op_errors))
            errors.append(avg_op_err)
            is_exact = avg_op_err < 1e-6
            cost_reduction = cost_b / (cost_a + 1e-12)

            commutation_results.append(
                FoldCommutationCheck(
                    operation_name=op_name,
                    commutation_error=round(avg_op_err, 6),
                    is_exact_commutation=is_exact,
                    cost_before=cost_b,
                    cost_after=cost_a,
                    cost_reduction_ratio=round(cost_reduction, 2),
                )
            )

        # Held-out transfer check: do commutative relations hold on held-out states?
        held_out_errors = []
        for (op_name, t_before, _), (t_after, _) in zip(operations_before, operations_after):
            for x in held_out_states:
                lhs = fold_fn(t_before(x))
                rhs = t_after(fold_fn(x))
                err = float(np.linalg.norm(lhs - rhs) / (np.linalg.norm(lhs) + 1e-12))
                held_out_errors.append(err)
        avg_held_out_err = float(np.mean(held_out_errors)) if held_out_errors else 0.0
        held_out_transfer = avg_held_out_err < 0.05

        avg_err = float(np.mean(errors))
        search_reduction = baseline_search_cost / (folded_search_cost + 1e-12)

        # Verdict
        if avg_err < 0.01 and search_reduction > 1.5 and held_out_transfer:
            verdict = "successful_fold"
        elif avg_err < 0.10 and search_reduction > 1.0:
            verdict = "partial_fold"
        else:
            verdict = "failed_fold"

        return FoldEvaluationReport(
            fold_name=fold_name,
            semantic_preservation_score=round(1.0 - min(1.0, avg_err), 4),
            commutation_checks=commutation_results,
            average_commutation_error=round(avg_err, 6),
            effective_transformation_cost_reduction=round(
                np.mean([c.cost_reduction_ratio for c in commutation_results]), 2
            ),
            search_nodes_reduction_ratio=round(search_reduction, 2),
            held_out_transfer_success=held_out_transfer,
            verdict=verdict,
        )
