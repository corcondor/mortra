"""Tests of the evaluator, not additions to MORTRA's mathematical capabilities."""
import unittest
from copy import deepcopy

from scripts.measure_persistent_learning import (Theory, Domain, make_suite, evaluate,
    metrics, descendants, final_comparison, term)


CONFIG = {"domain": {"kind": "differential_ring", "variables": ["u", "v"],
                     "operations": ["add", "mul", "neg", "diff"]},
          "seed": 21, "budget": {"cycles": 10, "term_size": 9}}


class MeasurementTests(unittest.TestCase):
    def test_fixed_questions_are_outside_training_syntax(self):
        a = make_suite(CONFIG, 12, 2)
        self.assertEqual(a, make_suite(CONFIG, 12, 2))
        self.assertEqual(len(a), 16)
        self.assertTrue(all(x["origin"] == "external_evaluation" for x in a))

    def test_empty_knowledge_is_a_real_baseline(self):
        state = Theory(CONFIG).snapshot()
        suite = make_suite(CONFIG, 12, 1)
        d = Domain(CONFIG["domain"])
        oracle = {t["id"]: d.settle(t["left"], t["right"]) for t in suite}
        result = evaluate(state, suite, oracle)
        self.assertEqual(result["summary"]["solved_count"], 8)
        self.assertEqual(result["summary"]["total_prover_calls"], 8)
        self.assertEqual(result["summary"]["cross_task_reuse_count"], 0)

    def test_each_evaluation_task_is_isolated(self):
        state = Theory(CONFIG).snapshot()
        original = deepcopy(state)
        x = term("var", name="u")
        left = term("add", x, term("const", value="0"))
        suite = [{"id": str(i), "family": "debug", "left": left, "right": x, "kind": "equality"} for i in range(2)]
        result = evaluate(state, suite, {str(i): {"status": "proved"} for i in range(2)})
        self.assertEqual([r["prover_calls"] for r in result["rows"]], [1, 1])
        self.assertEqual(state, original)

    def test_known_development_rule_can_be_ablated_without_changing_truth(self):
        e = Theory(CONFIG)
        x = term("var", name="u")
        e.conjecture(term("add", x, term("const", value="0")), x)
        e.settle(next(iter(e.state["conjectures"])))
        state = e.snapshot()
        suite = [{"id": "debug", "family": "debug", "left": term("add", x, term("const", value="0")), "right": x, "kind": "equality"}]
        oracle = {"debug": {"status": "proved"}}
        on = evaluate(state, suite, oracle, repeats=2)
        off = evaluate(state, suite, oracle, disabled=set(state["theorems"]))
        self.assertEqual(on["summary"]["total_prover_calls"], 0)
        self.assertEqual(off["summary"]["total_prover_calls"], 1)
        self.assertEqual(final_comparison(off, on)["tasks_with_fewer_prover_calls"], ["debug"])

    def test_disabled_descendants_follow_actual_dependencies(self):
        state = {"proof_dependencies": {"A": [], "B": ["A"], "C": ["B"], "D": []}}
        self.assertEqual(descendants(state, "A"), {"A", "B", "C"})

    def test_wrong_oracle_is_not_a_success(self):
        state = Theory(CONFIG).snapshot()
        suite = make_suite(CONFIG, 12, 1)[:1]
        with self.assertRaises(AssertionError):
            evaluate(state, suite, {suite[0]["id"]: {"status": "disproved"}})

    def test_archive_counts_are_not_capability_scores(self):
        row = metrics(Theory(CONFIG).snapshot())
        self.assertEqual(row["new_semantic_representations"], 0)
        self.assertEqual(row["maximum_dependency_depth"], 0)
        self.assertIsNone(row["near_duplicate_rate"])
        self.assertNotIn("intelligence", row)


if __name__ == "__main__":
    unittest.main()
