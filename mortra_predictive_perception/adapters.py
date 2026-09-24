"""Isolated adapters; never execute a legacy experiment at import time."""
from __future__ import annotations

import ast
from collections import defaultdict, deque
import hashlib
import math
from pathlib import Path
import random
from types import SimpleNamespace

import numpy as np

from .core import PredictiveMDLSymbolizer


class ResponseSymbolizer(PredictiveMDLSymbolizer):
    """Change only the response target; retain reference fitting and routing."""

    def __init__(self, actions, target="delta"):
        if target not in ("delta", "absolute"):
            raise ValueError("target must be delta or absolute")
        super().__init__(actions)
        self.target = target

    def _build_training_arrays(self):
        arrays = super()._build_training_arrays()
        if self.target == "delta":
            return arrays
        X, valid, _, actions, specs, meta, dimension, history = arrays
        targets = np.vstack([self.episodes[e].observations[t + 1] for e, t in meta])
        return X, valid, targets, actions, specs, meta, dimension, history

    def predict_response(self, symbol, action):
        # The reference method returns the fitted target in its original units.
        return super().predict_delta(symbol, action)


def load_legacy_visual(path):
    """Compile original definitions without top-level logging or benchmark runs.

    Every selected AST node keeps its original source location and body. Only
    its import-time environment is supplied here. No learner method is patched.
    """
    path = Path(path).resolve()
    raw = path.read_bytes()
    tree = ast.parse(raw, filename=str(path))
    names = {"MicroGame", "render_visual_frame", "extract_visual_descriptor",
             "VisualStateConstructor", "solve_fixed_field"}
    nodes = [node for node in tree.body
             if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names]
    if {node.name for node in nodes} != names:
        raise ValueError("Legacy visual source does not contain the expected definitions")
    constants = {target.id: ast.literal_eval(node.value)
                 for node in tree.body if isinstance(node, ast.Assign)
                 for target in node.targets
                 if isinstance(target, ast.Name) and target.id in {"NUM_ACTIONS", "ACTIONS"}}
    if constants.keys() != {"NUM_ACTIONS", "ACTIONS"}:
        raise ValueError("Legacy visual action declarations are missing")
    namespace = {"__name__": "mortra_legacy_visual_definitions", "np": np,
                 "math": math, "random": random, "defaultdict": defaultdict,
                 "deque": deque, **constants}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), namespace)
    return SimpleNamespace(**{name: namespace[name] for name in names},
                           source_sha256=hashlib.sha256(raw).hexdigest(),
                           source_path=str(path), imported_definition_names=sorted(names))


def readonly_episode(observations, actions):
    """Own the input arrays so learners cannot mutate a shared saved trajectory."""
    result = tuple(np.array(o, dtype=np.float64, copy=True).reshape(-1) for o in observations)
    actions = tuple(actions)
    if len(result) != len(actions) + 1 or not result:
        raise ValueError("An episode needs one more observation than actions")
    if len({o.shape for o in result}) != 1 or any(not np.isfinite(o).all() for o in result):
        raise ValueError("Raw observations must be finite vectors of one dimension")
    for observation in result:
        observation.flags.writeable = False
    return result, actions
