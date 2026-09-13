"""Development fixtures, never normal-run targets or acquired definitions."""
from copy import deepcopy
from unittest.mock import patch
import unittest

from test_theory_dsl import config
from math_os_prototype import library_compression as lib
from math_os_prototype.theory_domain import term
from math_os_prototype.theory_formation import Theory
from math_os_prototype.theory_semantic_edit import SymbolicScope, discover, validate


def define(e, body, names=("f0",)):
    index = len(e.state["dsl"]["definitions"])
    d = {"index": index, "id": lib.definition_id(body), "template": body,
         "signature": {"parameters": {n: "scalar" for n in names}, "result": "scalar"},
         "scope": deepcopy(e.domain.scope), "dependencies": list(map(str, lib.calls_in(body))),
         "depth": 1, "born": 0, "reuse_count": 0, "utility_bits": 0}
    e.state["dsl"]["definitions"].append(d)
    return d


def call(d, *args):
    return {"op": "use", "abstraction": d["index"],
            "arguments": dict(zip(d["signature"]["parameters"], args))}


class SemanticEditing(unittest.TestCase):
    def test_general_symbolic_projection_and_originals_immutable(self):
        e = Theory(config(), semantic_edits=True)
        u, x = lib.program_hole(0), term("var", name="x")
        shifted = x
        for _ in range(3):
            shifted = term("pull", shifted, label="a")
        h = define(e, term("add", u, shifted))
        g = define(e, term("add", term("neg", x), call(h, u)))
        original = deepcopy(e.state["dsl"]["definitions"])
        record = discover(e.vocabulary, g)
        projection = next(r for r in record["relations"] if r["kind"] == "projection")
        self.assertEqual(projection["right"], u)
        self.assertEqual(len(projection["proof"]["free_variables"]), 3)
        e.state["dsl"]["semantic_relations"].extend(record["relations"])
        value = term("pull", term("neg", x), label="b")
        result, proofs = e.vocabulary.edit(call(g, value))
        self.assertEqual(result, value)
        self.assertTrue(proofs)
        self.assertEqual(original, e.state["dsl"]["definitions"])
        self.assertNotIn(g, e.vocabulary.active_definitions(True))
        self.assertIn(g, e.vocabulary.active_definitions(False))
        self.assertEqual(e.vocabulary.evaluate(result)[0], e.vocabulary.evaluate(call(g, value))[0])
        with self.assertRaises(ValueError):
            e.vocabulary.evaluate(result, requirements={"legality": "collision-free"})

    def test_one_argument_or_one_state_agreement_is_not_proof(self):
        e = Theory(config())
        u = lib.program_hole(0)
        scope = SymbolicScope(e.vocabulary, {"parameters": {"f0": "scalar"}, "result": "scalar"})
        self.assertFalse(scope.equal(term("pull", u, label="a"), u)[0])
        self.assertFalse(scope.equal(term("add", u, term("var", name="x")), u)[0])

    def test_independent_parameters_are_not_identified(self):
        e = Theory(config())
        u, v = lib.program_hole(0), lib.program_hole(1)
        scope = SymbolicScope(e.vocabulary, {"parameters": {"f0": "scalar", "f1": "scalar"}, "result": "scalar"})
        self.assertFalse(scope.equal(term("add", u, term("neg", v)), term("const", value="0"))[0])
        self.assertTrue(scope.equal(term("add", u, term("neg", u)), term("const", value="0"))[0])

    def test_argument_pullback_and_nonlinear_identity(self):
        c = config()
        c["domain"]["operations"].append("mul")
        e = Theory(c)
        u = lib.program_hole(0)
        scope = SymbolicScope(e.vocabulary, {"parameters": {"f0": "scalar"}, "result": "scalar"})
        left = term("mul", term("add", u, u), u)
        right = term("add", term("mul", u, u), term("mul", u, u))
        self.assertTrue(scope.equal(left, right)[0])

    def test_scope_and_dependency_tampering_refused(self):
        e = Theory(config())
        u = lib.program_hole(0)
        d = define(e, term("add", u, term("const", value="0")))
        r = discover(e.vocabulary, d)["relations"][0]
        validate(e.vocabulary, r)
        changed = deepcopy(r)
        changed["right"] = term("const", value="9")
        with self.assertRaises(ValueError): validate(e.vocabulary, changed)
        d["template"] = term("neg", u)
        with self.assertRaises(ValueError): validate(e.vocabulary, r)

    def test_usage_metadata_does_not_change_a_mathematical_dependency(self):
        e = Theory(config())
        cid = e.add_concept(term("neg", term("var", name="x")), [])
        e.acquire(cid)
        rid = next(iter(e.state["representations"]))
        d = define(e, term("add", lib.program_hole(0),
                   term("represented", term("word", letters=[]), binding=rid)))
        record = discover(e.vocabulary, d)
        self.assertTrue(record["relations"])
        e.state["representations"][rid]["reuse_count"] += 10
        for r in record["relations"]:
            validate(e.vocabulary, r)

    def test_modulo_abstraction_retains_syntactic_and_semantic_evidence(self):
        c = {"domain": {"kind": "fold_frames", "operations": ["pull", "add", "mul", "neg", "eq", "not", "and"]},
             "seed": 20260913, "budget": {"cycles": 40, "seconds": 120, "term_size": 12, "concepts": 128,
             "active_concepts": 24, "candidates": 4000, "batch": 12, "representations": 3,
             "dimension": 24, "shared_spaces": 1, "definitions": 8, "library_pairs": 3000,
             "library_corpus": 512, "library_interval": 32, "expanded_size": 40, "word_length": 6}}
        e = Theory(c, semantic_edits=True)
        e.run()
        self.assertTrue(e.state["dsl"]["semantic_uses"])
        self.assertTrue(any(d.get("semantic_sources") for d in e.state["dsl"]["definitions"]))
        for row in e.state["dsl"]["corpus"]:
            self.assertEqual(e.vocabulary.primitive(row["program"]), row["primitive"])
            for original in row.get("semantic_history", []):
                self.assertEqual(e.domain.evaluate(original["primitive"]), e.domain.evaluate(row["primitive"]))
                self.assertTrue(original["edits"])
        restored = Theory(c, semantic_edits=True, state=e.snapshot())
        self.assertEqual(e.vocabulary.active_definitions(True), restored.vocabulary.active_definitions(True))

    def test_unsupported_word_argument_is_not_specialized(self):
        e = Theory(config())
        with self.assertRaises(ValueError):
            SymbolicScope(e.vocabulary, {"parameters": {"f0": "action_word"}, "result": "scalar"})

    def test_linear_equivalent_body_is_derived(self):
        e = Theory(config())
        x, u = term("var", name="x"), lib.program_hole(0)
        rolled = x
        for _ in range(3): rolled = term("pull", rolled, label="a")
        d = define(e, term("add", u, term("neg", rolled)))
        records = discover(e.vocabulary, d)
        self.assertIn(term("add", u, term("neg", x)), [r["right"] for r in records["relations"]])

    def test_no_original_action_in_shape_or_certified_execution(self):
        e = Theory(config())
        cid = e.add_concept(term("neg", term("var", name="x")), [])
        e.acquire(cid)
        rid = next(iter(e.state["representations"]))
        e.derive(rid, "a")
        pid = next(iter(e.state["dsl"]["recurrence_operations"]))
        p = term("recurrence", term("natural", value=101), procedure=pid)
        costs = {}
        def charge(k, n): costs[k] = costs.get(k, 0)+n
        with patch.object(e.vocabulary, "primitive", side_effect=AssertionError("original replay")):
            self.assertEqual(e.vocabulary.execution_shape(p, charge=charge), 1)
            actual, _ = e.vocabulary.evaluate(p, charge=charge)
        self.assertEqual(costs.get("model_action_steps", 0), 0)
        self.assertEqual(actual, e.domain.evaluate(e.vocabulary.primitive(p, charge=charge)))
        self.assertEqual(costs["model_action_steps"], 101)

    def test_queries_charge_replay_separately(self):
        e = Theory(config())
        task = {"id": "unit", "scope": e.domain.scope, "values": ["0", "-1", "-2"],
                "budget": {"states": 128, "depth": 64, "program_size": 4096,
                           "expanded_size": 4096, "work": 1_000_000}}
        row = e.vocabulary.solve_observation(task)
        self.assertTrue(row["solved"])
        self.assertGreater(row["independent_replay_work"]["used"], 0)
        self.assertEqual(row["normal_work_used"]+row["independent_replay_work"]["used"], row["work"]["used"])

    def test_query_reuses_equations_without_reproving(self):
        e = Theory(config())
        u = lib.program_hole(0)
        d = define(e, term("add", u, term("const", value="0")))
        e.state["dsl"]["semantic_relations"].extend(discover(e.vocabulary, d)["relations"])
        task = {"id": "unit", "scope": e.domain.scope, "values": ["0", "-1", "-2"],
                "budget": {"states": 128, "depth": 64, "program_size": 4096,
                           "expanded_size": 4096, "work": 1_000_000}}
        with patch.object(SymbolicScope, "equal", side_effect=AssertionError("reproved")):
            b = e.vocabulary.solve_observation(task, execution_mode="edited")
            c = e.vocabulary.solve_observation(task, execution_mode="certified")
        self.assertTrue(b["solved"])
        self.assertEqual(b["archive_digest"], c["archive_digest"])
        self.assertEqual(b["costs"]["prover_calls"], 0)


if __name__ == "__main__":
    unittest.main()
