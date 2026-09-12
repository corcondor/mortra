"""Generic exhausted-active-set regression; no production concept IDs."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from math_os_prototype.theory_formation import Theory
from math_os_prototype.theory_domain import term
from math_os_prototype.representation_progress import digest
from scripts.measure_persistent_learning import evaluate


CONFIG = {"domain": {"kind": "differential_ring", "variables": ["u", "v"],
                      "operations": ["add", "mul", "neg", "diff"]},
          "seed": 1, "budget": {"cycles": 100, "seconds": 60, "active_concepts": 6}}


class FrontierTests(unittest.TestCase):
    def dormant(self):
        engine = Theory(CONFIG)
        t = term("var", name="u")
        for _ in range(5):
            t = term("diff", t)
            engine.add_concept(t, [])
        engine.state["expanded"] = list(engine.state["active_concepts"])
        return engine

    def test_existing_refresh_reactivates_without_learning(self):
        e = self.dormant()
        old_archive = deepcopy(e.state["concepts"])
        dormant = set(old_archive)-set(e.state["active_concepts"])
        with patch.object(e, "refresh_active", wraps=e.refresh_active) as refresh:
            options = e.actions()
        self.assertEqual(refresh.call_count, 1)
        self.assertIn("invent", [a["kind"] for a in options])
        self.assertTrue(dormant & set(e.state["active_concepts"]))
        self.assertEqual(e.state["concepts"], old_archive)
        self.assertEqual(e.state["cycle"], 0)

    def test_pending_terms_are_not_reordered(self):
        e = self.dormant()
        pending = [{"term": term("neg", term("var", name="u")), "parents": []}]
        e.state["pending_terms"] = deepcopy(pending)
        with patch.object(e, "refresh_active", side_effect=AssertionError("not empty")):
            e.actions()
        self.assertEqual(e.state["pending_terms"], pending)

    def test_complete_archive_still_stops(self):
        e = self.dormant()
        e.state["expanded"] = list(e.state["concepts"])
        self.assertEqual(e.actions(), [])
        self.assertEqual(e.actions(), [])

    def test_existing_policy_selects_the_reactivated_parent(self):
        e = self.dormant()
        e.actions()
        chosen = next(cid for cid in e.state["active_concepts"] if cid not in e.state["expanded"])
        self.assertTrue(e.step())
        self.assertIn(chosen, e.state["expanded"])
        self.assertEqual(e.state["decisions"][-1]["policy"], "least_visited_then_cost")
        self.assertEqual(e.state["events"][-1]["actor"], "MORTRA")

    def test_candidate_budget_still_blocks_invent(self):
        e = self.dormant()
        e.state["seen"] = ["seen"]*e.budget["candidates"]
        self.assertNotIn("invent", [a["kind"] for a in e.actions()])


class ChallengeBudgetTests(unittest.TestCase):
    def test_resource_limit_is_enforced_before_proving(self):
        e = Theory(CONFIG)
        x = term("var", name="u")
        lhs = term("add", x, term("const", value="0"))
        suite = [{"id": "audit", "family": "audit", "left": lhs, "right": x, "kind": "equality"}]
        oracle = {"audit": {"status": "proved"}}
        initial = e.snapshot()
        result = evaluate(initial, suite, oracle, proof_node_budget=2)
        self.assertEqual(result["rows"][0]["status"], "budget_exceeded")
        self.assertEqual(result["summary"]["total_prover_calls"], 0)
        self.assertFalse(result["rows"][0]["certificate"]["proof_was_executed"])
        e.conjecture(lhs, x)
        e.settle(next(iter(e.state["conjectures"])))
        learned = e.snapshot()
        before = digest(learned)
        result = evaluate(learned, suite, oracle, proof_node_budget=2)
        self.assertEqual(result["rows"][0]["status"], "proved")
        self.assertEqual(result["summary"]["total_prover_calls"], 0)
        self.assertEqual(digest(learned), before)
        self.assertEqual(evaluate(initial, suite, oracle)["summary"]["solved_count"], 1)


if __name__ == "__main__":
    unittest.main()
