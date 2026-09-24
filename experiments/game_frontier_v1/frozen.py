"""Load original definitions without executing the baseline's log-writing preamble."""
import ast
import hashlib
from pathlib import Path

import numpy as np

BASE_COMMIT = "483d1592e5cd0d2b23d474cc79e217b121fd1fbe"
ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "scripts/evaluate_cross_domain_generalization.py"
BASELINE_SHA256_LF = "4075ef5c0f5f6f93bf3ae4049ff9a21dd471d0ccf5a04af6ffda21b40fc5a410"


def load_baseline():
    source = BASELINE.read_text(encoding="utf-8")
    assert hashlib.sha256(source.encode()).hexdigest() == BASELINE_SHA256_LF
    names = {"StructuralLearner", "solve_fixed_field", "run_fixed_field_policy"}
    definitions = [node for node in ast.parse(source).body
                   if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names]
    assert {node.name for node in definitions} == names
    namespace = {"np": np}
    exec(compile(ast.Module(body=definitions, type_ignores=[]), str(BASELINE), "exec"), namespace)
    assert namespace["solve_fixed_field"].__defaults__ == (0.90, 300, 1e-8)
    return namespace


_core = load_baseline()
StructuralLearner = _core["StructuralLearner"]
solve_fixed_field = _core["solve_fixed_field"]
run_fixed_field_policy = _core["run_fixed_field_policy"]
