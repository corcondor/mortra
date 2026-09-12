"""Measurement noninterference and single-factor controls; no target answer input."""
from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from scripts.measure_persistent_learning import Theory, read, digest
from scripts.observe_theory_run import Observer
from scripts.measure_theory_bottleneck import make_configs, compare_inputs
from scripts.analyze_theory_bottleneck import used_rules, match_counts

ROOT = Path(__file__).resolve().parents[1]
CONFIG = {"domain": {"kind": "differential_ring", "variables": ["u", "v"],
          "operations": ["add", "mul", "neg", "diff"]},
          "seed": 20260913, "budget": {"cycles": 80, "seconds": 60}}


def deterministic(value):
    if isinstance(value, dict):
        return {k: deterministic(v) for k, v in value.items() if k not in {"seconds", "sha256"}}
    if isinstance(value, list): return [deterministic(v) for v in value]
    return value


class BottleneckTests(unittest.TestCase):
    def test_observer_does_not_change_math_policy_or_results(self):
        plain = Theory(CONFIG).run()
        with tempfile.TemporaryDirectory() as directory:
            observer = Observer(Path(directory)/"observed", cycles=[20], proof_calls=[2])
            try:
                with ExitStack() as stack:
                    observer.attach(stack)
                    measured = Theory(CONFIG).run()
            finally:
                observer.close()
            self.assertEqual(deterministic(plain), deterministic(measured))
            self.assertTrue((observer.output/"proof-2.json").exists())
            self.assertTrue((observer.output/"cycle-20.json").exists())
            checkpoint = read(observer.output/"proof-2.json")
            self.assertEqual(checkpoint["costs"]["certification"]["proof_calls"], 2)

    def test_only_term_cap_changes_in_sweep(self):
        plan = read(ROOT/"configs/theory-bottleneck-study.json")
        configs = make_configs(plan)
        compare_inputs(configs, plan)
        self.assertEqual(len(configs), 11)
        configs["theory-ring-size-12"]["budget"]["concepts"] += 1
        with self.assertRaises(ValueError): compare_inputs(configs, plan)

    def test_scheduler_control_changes_only_cycles(self):
        plan = read(ROOT/"configs/theory-bottleneck-study.json")
        configs = make_configs(plan)
        configs["theory-fold-frames-extended"]["budget"]["seconds"] += 1
        with self.assertRaises(ValueError): compare_inputs(configs, plan)

    def test_posthoc_usefulness_does_not_mutate_knowledge(self):
        state = Theory(CONFIG).run()
        before = digest(state)
        useful = used_rules(state, {"rows": []})
        self.assertTrue(useful <= {r["theorem"] for r in state["rewrite_rules"]})
        self.assertEqual(before, digest(state))

    def test_profile_no_rules_has_no_matches(self):
        state = Theory(CONFIG).snapshot()
        term = state["concepts"][next(iter(state["concepts"]))]["definition"]
        suite = [{"left": {"op": "neg", "args": [{"op": "neg", "args": [term]}]},
                  "right": term, "kind": "equality"}]
        result = match_counts(state, suite)
        self.assertEqual(result["rule_inspections"], 0)
        self.assertEqual(result["accepted_replacements"], 0)


if __name__ == "__main__": unittest.main()
