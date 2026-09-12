"""Development examples test kernels; they are never normal-run targets."""
import unittest
from copy import deepcopy
from unittest.mock import patch

from math_os_prototype.theory_domain import Domain, term, size
from math_os_prototype.theory_formation import Theory, configure, rewrite, assess


RING = {"domain": {"kind": "differential_ring", "variables": ["x", "y"],
                   "operations": ["add", "mul", "neg", "diff"]},
        "seed": 19, "budget": {"cycles": 50, "seconds": 90}}
FINITE = {"domain": {"kind": "finite_table", "states": [0, 1, 2],
            "actions": {"a": [1, 2, 0], "b": [0, 2, 1]},
            "sensors": {"x": [0, 1, 2]}, "operations": ["pull", "neg", "add", "eq", "not", "and"]},
          "seed": 20, "budget": {"cycles": 70, "seconds": 90, "representations": 1}}


class DomainTests(unittest.TestCase):
    def test_no_target(self):
        for forbidden in ["q", "target", "theorem", "expected_basis", "next_action"]:
            with self.subTest(forbidden=forbidden), self.assertRaises(ValueError):
                configure(dict(RING, **{forbidden: "x"}))

    def test_reject_inexact(self):
        d = Domain(RING["domain"])
        with self.assertRaises(ValueError): d.evaluate(term("const", value="0.1"))

    def test_type_safety(self):
        d = Domain(FINITE["domain"])
        p = term("eq", term("var", name="x"), term("const", value="0"))
        self.assertEqual(d.type_of(p), "predicate")
        with self.assertRaises(ValueError): d.type_of(term("add", p, p))

    def test_closed_scope(self):
        spec = deepcopy(FINITE["domain"])
        spec["actions"]["a"][0] = 3
        with self.assertRaises(ValueError): Domain(spec)

    def test_ring_identity(self):
        d, x = Domain(RING["domain"]), term("var", name="x")
        y = term("var", name="y")
        left = term("diff", term("mul", x, y))
        right = term("add", term("mul", term("diff", x), y), term("mul", x, term("diff", y)))
        result = d.settle(left, right)
        self.assertEqual(result["status"], "proved")
        self.assertEqual(result["certificate"]["residual"], "0")

    def test_probe_is_not_proof(self):
        d, x = Domain(RING["domain"]), term("var", name="x")
        square = term("mul", x, x)
        self.assertEqual(d.probe(x), d.probe(square))
        self.assertEqual(d.settle(x, square)["status"], "disproved")

    def test_finite_logic(self):
        d, x = Domain(FINITE["domain"]), term("var", name="x")
        p = term("eq", x, x)
        q = term("eq", x, term("const", value="0"))
        self.assertEqual(d.settle(q, p, "implication")["status"], "proved")
        self.assertEqual(d.settle(p, q, "implication")["status"], "disproved")

    def test_finite_closure_and_recurrence(self):
        d = Domain(FINITE["domain"])
        acquired = d.acquire(term("var", name="x"), 5)
        self.assertTrue(acquired["certificate"]["all_zero"])
        self.assertEqual(acquired["scope"]["kind"], "complete_finite_model")
        self.assertTrue(d.recurrence(acquired, "a")["certificate_passed"])
        acquired["scope"]["legality"] = "collision-free"
        with self.assertRaises(ValueError): d.recurrence(acquired, "a")

    def test_kernel_is_reused(self):
        from math_os_prototype.finite_generator_problem_dna import discover_action_observable_basis
        with patch("math_os_prototype.theory_domain.discover_action_observable_basis", wraps=discover_action_observable_basis) as wrapped:
            Domain(FINITE["domain"]).acquire(term("var", name="x"), 5)
            self.assertEqual(wrapped.call_count, 1)


class StateTests(unittest.TestCase):
    def test_rewrite_decreases(self):
        d = Domain(RING["domain"])
        x = term("var", name="x")
        nx = term("neg", term("neg", x))
        rule = {"left": nx, "right": x, "theorem": "test", "scope": d.scope}
        out, deps, _ = rewrite(term("mul", nx, nx), [rule], d.scope)
        self.assertEqual(out, term("mul", x, x))
        self.assertEqual(deps, ["test"])
        self.assertLess(size(out), size(term("mul", nx, nx)))
        with self.assertRaises(ValueError): rewrite(x, [dict(rule, left=x, right=nx)], d.scope)

    def test_wrong_scope_refused(self):
        d = Domain(RING["domain"])
        x = term("var", name="x")
        with self.assertRaises(ValueError):
            rewrite(x, [{"scope": {}}], d.scope)

    def test_universal_substitution_uses_existing_matcher(self):
        e = Theory(RING)
        x, y = term("var", name="x"), term("var", name="y")
        e.conjecture(term("add", x, term("const", value="0")), x)
        e.settle(next(iter(e.state["conjectures"])))
        square = term("mul", y, y)
        out, deps, _ = rewrite(term("add", square, term("const", value="0")),
                               e.rules(), e.domain.scope, e.domain)
        self.assertEqual(out, square)
        self.assertTrue(deps)

    def test_pattern_preserves_shared_variable_bindings(self):
        e = Theory(RING)
        x, y = term("var", name="x"), term("var", name="y")
        e.conjecture(term("add", term("mul", x, y), term("neg", term("mul", y, x))),
                     term("const", value="0"))
        e.settle(next(iter(e.state["conjectures"])))
        a, b = term("diff", x), term("mul", y, y)
        candidate = term("add", term("mul", a, b), term("neg", term("mul", b, a)))
        out, deps, _ = rewrite(candidate, e.rules(), e.domain.scope, e.domain)
        self.assertEqual(out, term("const", value="0"))
        self.assertTrue(deps)

    def test_finite_theorem_never_becomes_universal_pattern(self):
        e = Theory(FINITE)
        x = term("var", name="x")
        e.conjecture(term("pull", term("pull", x, label="b"), label="b"), x)
        e.settle(next(iter(e.state["conjectures"])))
        self.assertTrue(e.rules())
        self.assertTrue(all(not r.get("universal_pattern") for r in e.rules()))

    def test_resume_and_archive(self):
        e = Theory(RING)
        first = e.run(cycles=10)
        resumed = Theory(RING, state=first)
        second = resumed.run(cycles=10)
        self.assertEqual(second["cycle"], 20)
        self.assertTrue(set(first["concepts"]) <= set(second["concepts"]))
        first["cycle"] = 99
        with self.assertRaises(ValueError): Theory(RING, state=first)

    def test_resume_configuration_refused(self):
        state = Theory(RING).snapshot()
        with self.assertRaises(ValueError): Theory(dict(RING, seed=21), state=state)
        with self.assertRaises(ValueError): Theory(RING, theorem_reuse=False, state=state)

    def test_no_fake_algorithm_claim(self):
        result = assess(Theory(RING).run(cycles=2))
        self.assertFalse(result["new_general_algorithm_demonstrated"])
        self.assertEqual(result["external_unseen_tasks_evaluated"], 0)

    def test_no_target_run_generates_both_outcomes(self):
        e = Theory(RING)
        s = e.run(cycles=50)
        self.assertTrue(s["conjectures"])
        self.assertTrue(s["theorems"])
        self.assertTrue(s["counterexamples"])
        self.assertEqual(s["human_inputs_after_start"], 0)

    def test_theorem_ablation(self):
        e = Theory(RING, theorem_reuse=False)
        e.run(cycles=30)
        self.assertFalse(e.rules())
        self.assertTrue(e.state["theorems"])
        self.assertEqual(e.state["costs"].get("search", {}).get("proof_calls_avoided", 0), 0)

    def test_depth_with_actual_closure_dependency(self):
        s = Theory(FINITE).run(cycles=70)
        result = assess(s)
        self.assertGreaterEqual(result["max_proof_depth"], 2)
        uses = [x for x in s["downstream"] if x["kind"] == "new_length_from_stored_recurrence"]
        self.assertTrue(uses)
        self.assertTrue(all(x["agree"] for x in uses))

    def test_comparison_requires_paired_certified_reuse(self):
        from scripts.verify_theory_formation import compare, replay
        learned = Theory(FINITE).run(cycles=70)
        baseline = Theory(FINITE, theorem_reuse=False).run(cycles=70)
        repeated = Theory(FINITE, representation_reuse=False).run(cycles=70)
        self.assertTrue(replay(learned)["passed"])
        result = compare(learned, baseline, repeated)
        self.assertGreater(result["certified_closure_reproofs_avoided"], 0)
        self.assertEqual(result["representation_reacquisition_calls_with_reuse"], 0)
        corrupted = deepcopy(repeated)
        for r in corrupted["representations"].values():
            r["readout"] = ["999"] * len(r["readout"])
        self.assertEqual(compare(learned, baseline, corrupted)["certified_closure_reproofs_avoided"], 0)

    def test_replay_refuses_bad_stored_readout(self):
        from scripts.verify_theory_formation import replay
        from math_os_prototype.representation_progress import digest
        state = Theory(FINITE).run(cycles=70)
        for r in state["representations"].values():
            r["readout"] = ["999"] * len(r["readout"])
        state.pop("sha256")
        state["sha256"] = digest(state)
        self.assertFalse(replay(state)["passed"])


if __name__ == "__main__":
    unittest.main()
