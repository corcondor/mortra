"""Integration over shared, frozen episodes; evaluation cannot retrain the model."""
from collections import Counter
from dataclasses import dataclass
import time

import numpy as np

from .adapters import ResponseSymbolizer, readonly_episode
from .core import UnknownActionResponse, _Node
from .world import ObservedWorld


@dataclass
class IntegratedModel:
    perception: ResponseSymbolizer
    world: ObservedWorld
    training_symbols: tuple
    cpu_seconds: dict

    def encode_episode(self, observations, actions):
        observations, actions = readonly_episode(observations, actions)
        return tuple(self.perception.encode_history(observations[:t + 1], actions[:t])
                     for t in range(len(observations)))

    def memory_audit(self, observations, actions):
        symbols = self.encode_episode(observations, actions)
        belief = self.world.begin(symbols[0])
        records = []
        for t, symbol in enumerate(symbols):
            if t:
                belief = self.world.update(belief, actions[t - 1], symbol)
            replay = self.world.reconstruct(symbols[:t + 1], actions[:t])
            records.append({"step": t, "symbol": symbol, "belief": sorted(belief),
                            "full_history_belief": sorted(replay), "agrees": belief == replay,
                            "model_contradiction": not belief})
        return records


def fit_integrated(episodes, actions, target="delta"):
    """Only raw arrays, action IDs and episode boundaries enter fitting."""
    episodes = tuple(readonly_episode(obs, acts) for obs, acts in episodes)
    perception = ResponseSymbolizer(actions, target)
    started = time.process_time()
    for observations, controls in episodes:
        perception.add_episode(observations, controls)
    perception.fit()
    perception_cpu = time.process_time() - started
    started = time.process_time()
    encoded = tuple(tuple(perception.encode_history(obs[:t + 1], acts[:t]) for t in range(len(obs)))
                    for obs, acts in episodes)
    encoding_cpu = time.process_time() - started
    world = ObservedWorld(actions)
    started = time.process_time()
    for symbols, (_, controls) in zip(encoded, episodes, strict=True):
        world.add_episode(symbols, controls)
    world.freeze()
    return IntegratedModel(perception, world, encoded,
                           {"perception_fit": perception_cpu, "symbol_encoding": encoding_cpu,
                            "observed_world_and_quotient": time.process_time() - started})


def perception_metrics(model, episodes):
    """Common raw-unit next-observation error; no test-time fitting or thresholds."""
    started = time.process_time()
    squared_error = 0.0
    predicted_scalars = predicted_transitions = missing = 0
    lag_counts = Counter()
    missing_history_tests = 0
    observed_symbols = set()
    for observations, actions in episodes:
        observations, actions = readonly_episode(observations, actions)
        for t, action in enumerate(actions):
            obs, controls = observations[:t + 1], actions[:t]
            symbol = model.encode_history(obs, controls)
            observed_symbols.add(symbol)
            node = model.tree
            available_lag = 0
            while isinstance(node, _Node):
                value, available = model._feature_value_from_history(node.spec, obs, controls, t)
                if available:
                    available_lag = max(available_lag, node.spec.lag)
                    node = node.left if value <= node.threshold else node.right
                else:
                    missing_history_tests += 1
                    node = node.left if node.missing_left else node.right
            lag_counts[available_lag] += 1
            try:
                prediction = model.predict_response(symbol, action)
            except UnknownActionResponse:
                missing += 1
                continue
            if model.target == "delta":
                prediction = observations[t] + prediction
            error = prediction - observations[t + 1]
            squared_error += float(error @ error)
            predicted_scalars += error.size
            predicted_transitions += 1
    total = predicted_transitions + missing
    return {"target": model.target, "prediction_mse_raw_units": squared_error / predicted_scalars if predicted_scalars else None,
            "predicted_transitions": predicted_transitions, "unpredicted_transitions": missing,
            "prediction_coverage": predicted_transitions / total if total else None,
            "generated_symbols": model.report.generated_symbols, "symbols_used_on_evaluation": len(observed_symbols),
            "selected_history_depth": model.report.selected_history_depth,
            "available_history_lag_distribution": dict(lag_counts),
            "no_history_fraction": lag_counts[0] / total if total else None,
            "missing_history_predicate_evaluations": missing_history_tests,
            "cpu_seconds": time.process_time() - started,
            "scope": "frozen perception on supplied evaluation episodes; unknown action responses not imputed"}
