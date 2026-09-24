"""
MORTRA Predictive Perception
============================

Self-generates observation symbols from raw numeric observations by asking a
single question:

    Which distinctions in present/past sensory input are justified because
    they improve prediction of the action-conditioned change of the world?

This is NOT a neural network and NOT a supervised semantic classifier.
The "labels" are the observed future responses themselves.

The implementation uses a predictive MDL/BIC decision tree:

    history of raw observations/actions
        -> generated discrete symbol
        -> action-conditioned response model

No goal, reward, q, fixed symbol count, fixed tree depth, fixed history depth,
or task-specific object labels are used.

Why action-conditioned DELTA prediction?
----------------------------------------
Predicting y - x rather than y reduces pressure to encode purely persistent
appearance (background texture, color offset, cosmetic state) when it does not
change the causal response to an action. This is a deliberate behavioral
inductive bias, not a task-specific solution.

Statistical model
-----------------
Within each generated symbol and action, the normalized response delta is
modeled by a Gaussian with a fitted mean and globally standardized variance.
For a candidate sensory/history split we compare the Bayesian Information
Criterion (BIC):

    BIC = SSE + k * log(N)

(up to an additive/multiplicative constant common to all candidate trees).

A split is accepted iff it strictly decreases BIC. Thus:
- split thresholds come from observed data midpoints,
- the number of symbols is data-selected,
- no user similarity threshold is needed,
- history depth is selected only if lagged information earns its complexity
  cost by improving future-response prediction.

This is a reference implementation. It makes a finite-sample/model-class
assumption: axis-aligned predicates over raw/history features and a
piecewise-constant Gaussian response model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Hashable, Iterable, List, Optional, Sequence, Tuple
import math
import numpy as np


@dataclass
class Episode:
    observations: List[np.ndarray]
    actions: List[Hashable]

    def validate(self) -> None:
        if len(self.observations) != len(self.actions) + 1:
            raise ValueError(
                "len(observations) must equal len(actions)+1"
            )


@dataclass(frozen=True)
class FeatureSpec:
    kind: str           # "obs" | "prev_obs" | "prev_action"
    lag: int            # 0 for current observation
    index: int          # observation dimension or action code index

    def label(self) -> str:
        if self.kind == "obs":
            return f"obs[{self.index}]"
        if self.kind == "prev_obs":
            return f"obs[t-{self.lag}][{self.index}]"
        return f"action[t-{self.lag}] == code[{self.index}]"


@dataclass
class _Leaf:
    leaf_id: int
    row_indices: np.ndarray
    action_means: Dict[int, np.ndarray]


@dataclass
class _Node:
    spec: FeatureSpec
    threshold: float
    missing_left: bool
    left: Any
    right: Any


Tree = _Leaf | _Node


@dataclass
class FitReport:
    n_transitions: int
    raw_dimension: int
    max_observed_history: int
    generated_symbols: int
    tree_depth: int
    selected_history_depth: int
    selected_features: List[str]
    bic_before: float
    bic_after: float
    accepted_splits: int


class PredictiveMDLSymbolizer:
    """
    Predictive symbol induction from raw transitions.

    The tree is learned greedily, but every accepted split has an exact local
    BIC improvement under the stated model class.
    """

    def __init__(self, actions: Sequence[Hashable]):
        if not actions:
            raise ValueError("actions must be non-empty")
        if len(set(actions)) != len(actions):
            raise ValueError("actions must be unique")
        self.actions = tuple(actions)
        self._a2i = {a: i for i, a in enumerate(self.actions)}
        self.episodes: List[Episode] = []

        self.tree: Optional[Tree] = None
        self.feature_specs: List[FeatureSpec] = []
        self.report: Optional[FitReport] = None

        self._feature_matrix: Optional[np.ndarray] = None
        self._feature_valid: Optional[np.ndarray] = None
        self._targets: Optional[np.ndarray] = None
        self._target_scale: Optional[np.ndarray] = None
        self._action_codes: Optional[np.ndarray] = None
        self._rows_meta: List[Tuple[int, int]] = []
        self._next_leaf_id = 0

    # ------------------------------------------------------------------
    # data
    # ------------------------------------------------------------------

    def add_episode(
        self,
        observations: Sequence[np.ndarray],
        actions: Sequence[Hashable],
    ) -> None:
        ep = Episode(
            [np.asarray(o, dtype=np.float64).reshape(-1) for o in observations],
            list(actions),
        )
        ep.validate()
        if any(a not in self._a2i for a in ep.actions):
            raise KeyError("episode contains an unknown action")
        self.episodes.append(ep)

    # ------------------------------------------------------------------
    # training
    # ------------------------------------------------------------------

    def fit(self) -> FitReport:
        if not self.episodes:
            raise ValueError("no episodes")

        X, valid, Y, A, specs, rows_meta, raw_dim, max_hist = self._build_training_arrays()
        self._feature_matrix = X
        self._feature_valid = valid
        self._targets = Y
        self._action_codes = A
        self.feature_specs = specs
        self._rows_meta = rows_meta

        # Data-derived normalization of the response variables.
        scale = np.std(Y, axis=0, ddof=0)
        scale = np.where(scale > 0.0, scale, 1.0)
        self._target_scale = scale
        Yn = Y / scale

        all_rows = np.arange(len(Y), dtype=np.int64)
        self._next_leaf_id = 0
        root = self._make_leaf(all_rows, Yn, A)

        bic_before = self._leaf_bic(root, Yn, A, total_n=len(Y))
        self.tree, accepted = self._grow(root, X, valid, Yn, A, total_n=len(Y))
        bic_after = self._tree_bic(self.tree, Yn, A, total_n=len(Y))

        selected = self._selected_specs(self.tree)
        selected_depth = max((s.lag for s in selected), default=0)

        report = FitReport(
            n_transitions=len(Y),
            raw_dimension=raw_dim,
            max_observed_history=max_hist,
            generated_symbols=len(self._leaves(self.tree)),
            tree_depth=self._tree_depth(self.tree),
            selected_history_depth=selected_depth,
            selected_features=[s.label() for s in selected],
            bic_before=float(bic_before),
            bic_after=float(bic_after),
            accepted_splits=accepted,
        )
        self.report = report
        return report

    def _grow(
        self,
        leaf: _Leaf,
        X: np.ndarray,
        valid: np.ndarray,
        Y: np.ndarray,
        A: np.ndarray,
        total_n: int,
    ) -> Tuple[Tree, int]:
        best = self._best_split(leaf, X, valid, Y, A, total_n)
        if best is None:
            return leaf, 0

        spec_idx, threshold, missing_left, left_rows, right_rows, _new_bic = best
        left_leaf = self._make_leaf(left_rows, Y, A)
        right_leaf = self._make_leaf(right_rows, Y, A)

        left_tree, n_left = self._grow(left_leaf, X, valid, Y, A, total_n)
        right_tree, n_right = self._grow(right_leaf, X, valid, Y, A, total_n)

        return (
            _Node(
                spec=self.feature_specs[spec_idx],
                threshold=float(threshold),
                missing_left=bool(missing_left),
                left=left_tree,
                right=right_tree,
            ),
            1 + n_left + n_right,
        )

    def _best_split(
        self,
        leaf: _Leaf,
        X: np.ndarray,
        valid: np.ndarray,
        Y: np.ndarray,
        A: np.ndarray,
        total_n: int,
    ):
        rows = leaf.row_indices
        if len(rows) <= 1:
            return None

        old_bic = self._leaf_bic(leaf, Y, A, total_n)
        best = None

        for j, spec in enumerate(self.feature_specs):
            row_valid = valid[rows, j]
            valid_rows = rows[row_valid]
            missing_rows = rows[~row_valid]

            if len(valid_rows) == 0:
                continue

            vals_valid = X[valid_rows, j]
            uniq = np.unique(vals_valid)
            if uniq.size <= 1:
                continue

            thresholds = (uniq[:-1] + uniq[1:]) / 2.0

            for th in thresholds:
                valid_left = valid_rows[vals_valid <= th]
                valid_right = valid_rows[vals_valid > th]

                # Missing history is not guessed. It forms an explicit routing
                # case. Because the tree is binary, evaluate both deterministic
                # assignments and let BIC select whether either is useful.
                for missing_left in (True, False):
                    if missing_left:
                        left_rows = np.concatenate([valid_left, missing_rows])
                        right_rows = valid_right
                    else:
                        left_rows = valid_left
                        right_rows = np.concatenate([valid_right, missing_rows])

                    if len(left_rows) == 0 or len(right_rows) == 0:
                        continue

                    left_leaf = self._make_leaf(
                        left_rows, Y, A, allocate_id=False
                    )
                    right_leaf = self._make_leaf(
                        right_rows, Y, A, allocate_id=False
                    )

                    new_bic = (
                        self._leaf_bic(left_leaf, Y, A, total_n)
                        + self._leaf_bic(right_leaf, Y, A, total_n)
                    )

                    # Strict improvement only. No tunable margin.
                    if not (new_bic < old_bic):
                        continue

                    candidate = (
                        j,
                        float(th),
                        bool(missing_left),
                        left_rows,
                        right_rows,
                        float(new_bic),
                    )

                    if best is None:
                        best = candidate
                    else:
                        bj, bth, bmiss, _, _, bbic = best
                        if (
                            candidate[5] < bbic
                            or (
                                candidate[5] == bbic
                                and (
                                    self.feature_specs[j].lag,
                                    j,
                                    int(not missing_left),
                                    candidate[1],
                                )
                                < (
                                    self.feature_specs[bj].lag,
                                    bj,
                                    int(not bmiss),
                                    bth,
                                )
                            )
                        ):
                            best = candidate

        return best

    # ------------------------------------------------------------------
    # inference
    # ------------------------------------------------------------------

    def encode_history(
        self,
        observations: Sequence[np.ndarray],
        actions: Sequence[Hashable],
    ) -> int:
        if self.tree is None:
            raise RuntimeError("fit() first")
        if len(observations) != len(actions) + 1:
            raise ValueError("history invariant violated")

        obs = [np.asarray(o, dtype=np.float64).reshape(-1) for o in observations]
        t = len(observations) - 1

        node = self.tree
        while isinstance(node, _Node):
            value, available = self._feature_value_from_history(
                node.spec, obs, actions, t
            )
            if not available:
                node = node.left if node.missing_left else node.right
            else:
                node = node.left if value <= node.threshold else node.right
        return node.leaf_id

    def predict_delta(
        self,
        symbol: int,
        action: Hashable,
    ) -> np.ndarray:
        if self.tree is None:
            raise RuntimeError("fit() first")
        a = self._a2i[action]
        leaf = next((l for l in self._leaves(self.tree) if l.leaf_id == symbol), None)
        if leaf is None:
            raise KeyError(symbol)
        if a not in leaf.action_means:
            raise UnknownActionResponse((symbol, action))
        assert self._target_scale is not None
        return leaf.action_means[a] * self._target_scale

    def export_tree(self) -> Dict[str, Any]:
        if self.tree is None or self.report is None:
            raise RuntimeError("fit() first")

        def rec(node: Tree):
            if isinstance(node, _Leaf):
                return {
                    "type": "leaf",
                    "symbol": node.leaf_id,
                    "n_rows": int(len(node.row_indices)),
                    "actions_seen": [
                        repr(self.actions[a]) for a in sorted(node.action_means)
                    ],
                }
            return {
                "type": "split",
                "feature": node.spec.label(),
                "lag": node.spec.lag,
                "threshold": float(node.threshold),
                "missing_goes": "left" if node.missing_left else "right",
                "left": rec(node.left),
                "right": rec(node.right),
            }

        return {
            "report": self.report.__dict__,
            "tree": rec(self.tree),
        }

    # ------------------------------------------------------------------
    # objective
    # ------------------------------------------------------------------

    def _make_leaf(
        self,
        rows: np.ndarray,
        Y: np.ndarray,
        A: np.ndarray,
        allocate_id: bool = True,
    ) -> _Leaf:
        means: Dict[int, np.ndarray] = {}
        for a in np.unique(A[rows]):
            ar = rows[A[rows] == a]
            means[int(a)] = np.mean(Y[ar], axis=0)

        if allocate_id:
            leaf_id = self._next_leaf_id
            self._next_leaf_id += 1
        else:
            leaf_id = -1

        return _Leaf(leaf_id=leaf_id, row_indices=np.asarray(rows), action_means=means)

    def _leaf_bic(
        self,
        leaf: _Leaf,
        Y: np.ndarray,
        A: np.ndarray,
        total_n: int,
    ) -> float:
        # -2 log likelihood up to constants, using globally normalized response
        # variance = 1.  Each action-conditioned mean contributes D parameters.
        sse = 0.0
        k = 0
        d = Y.shape[1]

        for a, mean in leaf.action_means.items():
            rows = leaf.row_indices[A[leaf.row_indices] == a]
            residual = Y[rows] - mean
            sse += float(np.sum(residual * residual))
            k += d

        # BIC = -2 log L + k log N, constants omitted.
        return sse + k * math.log(max(total_n, 1))

    def _tree_bic(self, node: Tree, Y: np.ndarray, A: np.ndarray, total_n: int) -> float:
        if isinstance(node, _Leaf):
            return self._leaf_bic(node, Y, A, total_n)
        return (
            self._tree_bic(node.left, Y, A, total_n)
            + self._tree_bic(node.right, Y, A, total_n)
        )

    # ------------------------------------------------------------------
    # feature construction
    # ------------------------------------------------------------------

    def _build_training_arrays(self):
        dims = {ep.observations[0].size for ep in self.episodes}
        if len(dims) != 1:
            raise ValueError("all observations must have same dimension")
        d = next(iter(dims))
        max_hist = max(len(ep.actions) for ep in self.episodes)

        specs: List[FeatureSpec] = []
        for j in range(d):
            specs.append(FeatureSpec("obs", 0, j))

        # All empirically available lags are candidates. No fixed history depth.
        for lag in range(1, max_hist + 1):
            for j in range(d):
                specs.append(FeatureSpec("prev_obs", lag, j))
            for a_idx in range(len(self.actions)):
                specs.append(FeatureSpec("prev_action", lag, a_idx))

        rows_meta: List[Tuple[int, int]] = []
        targets: List[np.ndarray] = []
        action_codes: List[int] = []

        for ep_id, ep in enumerate(self.episodes):
            ep.validate()
            for t, action in enumerate(ep.actions):
                rows_meta.append((ep_id, t))
                targets.append(ep.observations[t + 1] - ep.observations[t])
                action_codes.append(self._a2i[action])

        n = len(rows_meta)
        X = np.zeros((n, len(specs)), dtype=np.float64)
        valid = np.zeros((n, len(specs)), dtype=bool)

        for row, (ep_id, t) in enumerate(rows_meta):
            ep = self.episodes[ep_id]
            for j, spec in enumerate(specs):
                val, ok = self._feature_value_from_history(
                    spec, ep.observations[: t + 1], ep.actions[:t], t
                )
                if ok:
                    X[row, j] = val
                    valid[row, j] = True

        return (
            X,
            valid,
            np.vstack(targets),
            np.asarray(action_codes, dtype=np.int64),
            specs,
            rows_meta,
            d,
            max_hist,
        )

    def _feature_value_from_history(
        self,
        spec: FeatureSpec,
        observations: Sequence[np.ndarray],
        actions: Sequence[Hashable],
        t: int,
    ) -> Tuple[float, bool]:
        if spec.kind == "obs":
            if t >= len(observations):
                return 0.0, False
            return float(observations[t][spec.index]), True

        if spec.kind == "prev_obs":
            tau = t - spec.lag
            if tau < 0 or tau >= len(observations):
                return 0.0, False
            return float(observations[tau][spec.index]), True

        if spec.kind == "prev_action":
            tau = t - spec.lag
            if tau < 0 or tau >= len(actions):
                return 0.0, False
            return float(self._a2i[actions[tau]] == spec.index), True

        raise ValueError(spec.kind)

    # ------------------------------------------------------------------
    # tree utilities
    # ------------------------------------------------------------------

    def _leaves(self, node: Tree) -> List[_Leaf]:
        if isinstance(node, _Leaf):
            return [node]
        return self._leaves(node.left) + self._leaves(node.right)

    def _tree_depth(self, node: Tree) -> int:
        if isinstance(node, _Leaf):
            return 0
        return 1 + max(self._tree_depth(node.left), self._tree_depth(node.right))

    def _selected_specs(self, node: Tree) -> List[FeatureSpec]:
        if isinstance(node, _Leaf):
            return []
        return (
            [node.spec]
            + self._selected_specs(node.left)
            + self._selected_specs(node.right)
        )


class InsufficientHistory(RuntimeError):
    pass


class UnknownActionResponse(RuntimeError):
    pass
