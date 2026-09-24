"""Threshold sweeps with reference rescoring and lazy history columns.

The reference objective, traversal, row order and tie rule are unchanged. The
sweep is a numerical screening calculation, not a mathematical certificate.
Candidates within its roundoff envelope are rescored by the original routine.
Ill-conditioned arithmetic disables screening. Equivalence tests are mandatory
before this implementation is used in an experiment.
"""
from collections.abc import Sequence
import math

import numpy as np

from .adapters import ResponseSymbolizer
from .core import FeatureSpec


class FeatureCatalog(Sequence):
    def __init__(self, dimension, actions, history):
        self.dimension, self.actions, self.history = dimension, actions, history

    def __len__(self):
        return self.dimension + self.history * (self.dimension + self.actions)

    def __getitem__(self, index):
        if isinstance(index, slice):
            return [self[i] for i in range(*index.indices(len(self)))]
        if index < 0:
            index += len(self)
        if not 0 <= index < len(self):
            raise IndexError(index)
        if index < self.dimension:
            return FeatureSpec("obs", 0, index)
        lag, offset = divmod(index - self.dimension, self.dimension + self.actions)
        kind = "prev_obs" if offset < self.dimension else "prev_action"
        return FeatureSpec(kind, lag + 1,
                           offset if kind == "prev_obs" else offset - self.dimension)


class HistoryColumns:
    """Materialize one column, not the full N by (D + H(D+A)) array."""
    def __init__(self, episodes, specs, meta, action_codes):
        self.specs = specs
        self.times = np.array([t for _, t in meta], dtype=np.int64)
        offsets = np.cumsum([0] + [len(ep.observations) for ep in episodes])
        self.positions = np.array([offsets[e] + t for e, t in meta], dtype=np.int64)
        self.observations = np.vstack([ep.observations for ep in episodes])
        self.actions = np.concatenate([
            np.array([action_codes[a] for a in ep.actions] + [-1], dtype=np.int64)
            for ep in episodes])
        self.shape = (len(meta), len(specs))
        self._cached_index = None
        self._cached = None

    def column(self, index):
        if self._cached_index != index:
            spec = self.specs[index]
            valid = self.times >= spec.lag
            positions = self.positions[valid] - spec.lag
            values = np.zeros(len(self.times), dtype=np.float64)
            if spec.kind == "prev_action":
                values[valid] = self.actions[positions] == spec.index
            else:
                values[valid] = self.observations[positions, spec.index]
            self._cached_index, self._cached = index, (values, valid)
        return self._cached

    def __getitem__(self, index):
        rows, column = index
        return self.column(column)[0][rows]


class ValidColumns:
    def __init__(self, columns):
        self.columns = columns
        self.shape = columns.shape

    def __getitem__(self, index):
        rows, column = index
        return self.columns.column(column)[1][rows]


class SweepResponseSymbolizer(ResponseSymbolizer):
    def __init__(self, actions, target="delta"):
        super().__init__(actions, target)
        self.work = {"features": 0, "threshold_routes": 0,
                     "reference_rescores": 0, "unscreened_features": 0}

    def _build_training_arrays(self):
        dims = {ep.observations[0].size for ep in self.episodes}
        if len(dims) != 1:
            raise ValueError("all observations must have same dimension")
        d = next(iter(dims))
        history = max(len(ep.actions) for ep in self.episodes)
        meta, targets, actions = [], [], []
        for e, ep in enumerate(self.episodes):
            ep.validate()
            for t, action in enumerate(ep.actions):
                meta.append((e, t))
                targets.append(ep.observations[t + 1] - ep.observations[t]
                               if self.target == "delta" else ep.observations[t + 1])
                actions.append(self._a2i[action])
        specs = FeatureCatalog(d, len(self.actions), history)
        columns = HistoryColumns(self.episodes, specs, meta, self._a2i)
        return (columns, ValidColumns(columns), np.vstack(targets),
                np.asarray(actions, dtype=np.int64), specs, meta, d, history)

    @staticmethod
    def _sweep_costs(ordered_rows, missing_rows, cuts, Y, A, total_n):
        """Both missing routes, with action-conditioned sufficient statistics."""
        costs = np.zeros((len(cuts), 2))
        parameters = np.zeros((len(cuts), 2), dtype=np.int64)
        for action in np.unique(A[np.concatenate((ordered_rows, missing_rows))]):
            positions = np.flatnonzero(A[ordered_rows] == action)
            values = Y[ordered_rows[positions]]
            missing = Y[missing_rows[A[missing_rows] == action]]
            nleft = np.searchsorted(positions, cuts)
            nright = len(positions) - nleft
            prefix = np.vstack((np.zeros(Y.shape[1]), np.cumsum(values, axis=0)))
            suffix = np.vstack((np.cumsum(values[::-1], axis=0)[::-1], np.zeros(Y.shape[1])))
            squares = np.sum(values * values, axis=1)
            left_sq = np.r_[0.0, np.cumsum(squares)][nleft]
            right_sq = np.r_[np.cumsum(squares[::-1])[::-1], 0.0][nleft]
            missing_sum = np.sum(missing, axis=0)
            missing_sq = float(np.sum(missing * missing))
            for route in (0, 1):
                for is_left, count, sums, sq in (
                    (True, nleft, prefix[nleft], left_sq),
                    (False, nright, suffix[nleft], right_sq),
                ):
                    attach = is_left == (route == 0)
                    if attach:
                        count = count + len(missing)
                        sums = sums + missing_sum
                        sq = sq + missing_sq
                    present = count > 0
                    costs[present, route] += (sq[present]
                        - np.sum(sums[present] * sums[present], axis=1) / count[present])
                    parameters[present, route] += Y.shape[1]
        return costs + parameters * math.log(max(total_n, 1))

    def _best_split(self, leaf, X, valid, Y, A, total_n):
        rows = leaf.row_indices
        if len(rows) <= 1:
            return None
        old = self._leaf_bic(leaf, Y, A, total_n)
        best = None
        # Conservative accumulated floating-point screening envelope. This is
        # a numerical guard, never a confidence/similarity/acceptance threshold.
        operations = 64 * (len(rows) + Y.shape[1] + len(self.actions) + 1)
        product = operations * np.finfo(np.float64).eps
        energy = float(np.sum(np.abs(Y[rows]) ** 2))
        envelope = (product / (1 - product) * (energy + abs(old) + 1)
                    if product < 1 else math.inf)
        for j, spec in enumerate(self.feature_specs):
            self.work["features"] += 1
            mask = valid[rows, j]
            observed, missing = rows[mask], rows[~mask]
            if len(observed) < 2:
                continue
            values = X[observed, j]
            unique = np.unique(values)
            if len(unique) < 2:
                continue
            thresholds = (unique[:-1] + unique[1:]) / 2.0
            order = np.argsort(values, kind="stable")
            cuts = np.searchsorted(values[order], thresholds, side="right")
            with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
                estimates = self._sweep_costs(observed[order], missing, cuts, Y, A, total_n)
            self.work["threshold_routes"] += estimates.size
            screened = np.isfinite(estimates).all() and math.isfinite(envelope)
            if not screened:
                self.work["unscreened_features"] += 1
            for flat in np.argsort(estimates.ravel(), kind="stable"):
                index, route = divmod(int(flat), 2)
                incumbent = old if best is None else best[5]
                if screened and estimates[index, route] > incumbent + envelope:
                    break
                threshold = thresholds[index]
                left, right = observed[values <= threshold], observed[values > threshold]
                missing_left = route == 0
                if missing_left:
                    left = np.concatenate((left, missing))
                else:
                    right = np.concatenate((right, missing))
                if not len(left) or not len(right):
                    continue
                self.work["reference_rescores"] += 1
                new = (self._leaf_bic(self._make_leaf(left, Y, A, False), Y, A, total_n)
                       + self._leaf_bic(self._make_leaf(right, Y, A, False), Y, A, total_n))
                if not new < old:
                    continue
                candidate = (j, float(threshold), missing_left, left, right, float(new))
                tie = (spec.lag, j, int(not missing_left), float(threshold))
                if best is None or new < best[5] or (new == best[5] and tie < (
                        self.feature_specs[best[0]].lag, best[0], int(not best[2]), best[1])):
                    best = candidate
        return best
