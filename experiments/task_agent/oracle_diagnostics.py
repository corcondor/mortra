"""Adapters for the user's unchanged oracle diagnostics; never learned policies."""
import ast
from functools import lru_cache
import hashlib
from pathlib import Path
from types import SimpleNamespace

from .exploration import ExplorationDecision

REFERENCE = Path(__file__).parent / "data" / "oracle_scale_reference"
SOURCE_HASHES = {
    "run_oracle_headroom.py": "a46cf7d08b0a2c3fbbff0ec24c79118b26d59ac1c1c38f7396b0d551d1f9b104",
    "run_oracle_source_linear_shard.py": "b10efacbcf20fb3ebea4cd3b4f96c19e6c1a50ead3503e8675a4f9e113658900",
}


@lru_cache(None)
def reference(name="run_oracle_source_linear_shard.py"):
    """Load definitions, not the original top-level /mnt/data experiment loop."""
    path = REFERENCE / name
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SOURCE_HASHES[name]
    tree = ast.parse(raw.decode("utf-8"), filename=str(path))
    body = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.ClassDef)):
            body.append(node)
        elif isinstance(node, ast.Assign) and all(
                isinstance(t, ast.Name) and t.id in {"Q", "CAP", "ROOT", "SEEDS"}
                for t in node.targets):
            body.append(node)
    namespace = {"__name__": "frozen_user_oracle_reference", "__file__": str(path)}
    exec(compile(ast.Module(body=body, type_ignores=[]), str(path), "exec"), namespace)
    assert namespace["Q"] == 0.90 and namespace["CAP"] == 4096
    return SimpleNamespace(**namespace)


class OraclePolicy:
    def __init__(self, engine, roots, task, mode):
        if mode not in ("oracle_source", "oracle_direct"):
            raise ValueError(mode)
        self.mode = mode
        name = "run_oracle_headroom.py" if mode == "oracle_direct" else "run_oracle_source_linear_shard.py"
        self.ref = reference(name)
        self.oracle = self.ref.TrueOracle(engine, roots, task)
        self.last_telemetry = None

    def choose(self, learner, world_state, task, memory):
        if task is not self.oracle.task:
            raise ValueError("Oracle belongs to a different task")
        if self.mode == "oracle_source":
            action = self.ref.oracle_source_action(learner, world_state, task, memory, self.oracle)
        else:
            action, _ = self.oracle.action(world_state, memory)
        _, distances = self.oracle.action(world_state, memory)
        self.last_telemetry = {
            "oracle_diagnostic": True, "mode": self.mode, "selected_action": action,
            "true_remaining_distances_after_action": {
                a: d if d < 10**8 else None for a, d in distances.items()},
            "world_state": list(world_state), "memory": repr(memory),
            "oracle_world_states": len(self.oracle.states),
            "oracle_product_states": len(self.oracle.pids)}
        return ExplorationDecision(action=action, policy=self.mode,
                                   reason="unchanged user-supplied privileged diagnostic")
