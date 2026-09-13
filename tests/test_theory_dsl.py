"""Known development fixtures; not fed to autonomous acquisition runs."""
from copy import deepcopy
import unittest
from unittest.mock import patch
import sympy as sp

from math_os_prototype import library_compression as lib
from math_os_prototype.theory_domain import term, Domain
from math_os_prototype.theory_formation import Theory
from math_os_prototype.theory_spaces import canonical_space, readout, materialize


def config():
    return {"domain": {"kind": "finite_table", "states": [0, 1, 2],
        "actions": {"a": [1, 2, 0], "b": [0, 2, 1]},
        "sensors": {"x": [0, 1, 2]}, "operations": ["pull", "neg", "add", "eq", "not", "and"]},
        "seed": 77, "budget": {"cycles": 25, "seconds": 120, "shared_spaces": 1,
        "representations": 1, "definitions": 3, "library_interval": 12, "library_pairs": 120}}


class Spaces(unittest.TestCase):
    def test_interpreter_cache_keeps_integrity_checks(self):
        e = Theory(config())
        cid = e.add_concept(term("neg", term("var", name="x")), [])
        e.acquire(cid)
        rid = next(iter(e.state["representations"]))
        p = term("represented", term("word", letters=["a", "b"]), binding=rid)
        a, cold = e.vocabulary.evaluate(p)
        b, warm = e.vocabulary.evaluate(p)
        self.assertEqual(a, b)
        self.assertEqual(cold["representation_compiles"], 1)
        self.assertEqual(warm["representation_cache_hits"], 1)
        self.assertEqual(warm["matrix_multiply_adds"], 0)
        space = next(iter(e.state["observable_spaces"].values()))
        space["basis"][0] = "999"
        with self.assertRaises(ValueError): e.vocabulary.evaluate(p)

    def test_same_span_has_separate_readouts_without_closure(self):
        e = Theory(config())
        x = term("var", name="x")
        c = e.add_concept(term("pull", x, label="a"), [])
        e.acquire(c)
        other = e.add_concept(term("neg", term("pull", x, label="a")), [])
        with patch.object(e.domain, "acquire", side_effect=AssertionError("reacquired")):
            e.acquire(other)
        self.assertEqual(len(e.state["observable_spaces"]), 1)
        self.assertEqual(len(e.state["representations"]), 2)
        self.assertEqual(e.state["costs"]["acquisition"]["closure_calls"], 1)
        for r in e.state["representations"].values():
            self.assertNotIn("basis", r)
            self.assertIn("basis", materialize(e.state, r["id"]))

    def test_basis_change_actions_and_readout(self):
        d = Domain(config()["domain"])
        a = d.acquire(term("var", name="x"), 8)
        canonical = canonical_space(d, a)
        n = a["dimension"]
        change = sp.eye(n)
        change[0, 0] = 2
        changed = deepcopy(a)
        changed["basis"] = [str(x) for x in change*sp.Matrix(a["basis"])]
        changed["action_matrices"] = {g: [[str(x) for x in row] for row in
            (change*sp.Matrix(m)*change.inv()).tolist()] for g, m in a["action_matrices"].items()}
        other = canonical_space(d, changed)
        self.assertEqual(canonical["id"], other["id"])
        self.assertEqual(canonical["action_matrices"], other["action_matrices"])
        self.assertEqual(readout(d, canonical, term("var", name="x")),
                         readout(d, other, term("var", name="x")))

    def test_rank_not_identity_and_scope_refusal(self):
        spec = config()["domain"]
        spec["actions"] = {"a": [0, 1, 2]}
        spec["sensors"]["y"] = [1, 0, 0]
        d = Domain(spec)
        x, y = term("var", name="x"), term("var", name="y")
        a, b = [canonical_space(d, d.acquire(t, 8)) for t in [x, y]]
        self.assertEqual(a["dimension"], b["dimension"])
        self.assertNotEqual(a["id"], b["id"])
        self.assertIsNone(readout(d, a, y))
        with self.assertRaises(ValueError): readout(d, a, x, requirements={"legality": "collision-free"})
        changed = deepcopy(spec)
        changed["actions"]["a"] = [1, 2, 0]
        with self.assertRaises(ValueError): readout(Domain(changed), a, x)
        a["basis"][0] = "999"
        with self.assertRaises(ValueError): readout(d, a, x)

    def test_executable_space_on_unseen_words_all_states(self):
        e = Theory(config())
        cid = e.add_concept(term("neg", term("var", name="x")), [])
        e.acquire(cid)
        rid = next(iter(e.state["representations"]))
        for word in [[], ["a", "b"], ["b", "a", "a", "b"]]:
            p = term("represented", term("word", letters=word), binding=rid)
            with patch.object(e.domain, "acquire", side_effect=AssertionError("reacquired")):
                actual, cost = e.vocabulary.evaluate(p)
            self.assertEqual(actual, e.domain.evaluate(e.vocabulary.primitive(p)))
            self.assertEqual(cost["representation_calls"], 1)
            with self.assertRaises(ValueError):
                e.vocabulary.evaluate(p, requirements={"goal": "unrepresented history"})


class Definitions(unittest.TestCase):
    def test_planner_duplicates_obey_budget_and_do_not_starve_operators(self):
        from math_os_prototype.runtime_typed_planner import (
            initial_fact, RuntimePrimitive, PrimitiveResult, synthesize_typed_plan)
        facts = [initial_fact("n", n) for n in range(3)]
        operations = [RuntimePrimitive("duplicates", ("n", "n"), "n", lambda a: PrimitiveResult(0, {})),
                      RuntimePrimitive("other", (), "n", lambda a: PrimitiveResult(9, {}))]
        options = {"max_states": 5, "goal_predicates": {"n": lambda f: f.value == 9}}
        sequential = synthesize_typed_plan(facts, operations, ["n"], **options)
        self.assertLessEqual(sequential.states_explored, 5)
        self.assertFalse(sequential.complete)
        fair = synthesize_typed_plan(facts, operations, ["n"], fair=True, **options)
        self.assertTrue(fair.complete)
        self.assertEqual(fair.states_explored, 5)

    def test_value_goal_is_not_satisfied_by_any_fact_of_same_sort(self):
        from math_os_prototype.runtime_typed_planner import (
            initial_fact, RuntimePrimitive, PrimitiveResult, synthesize_typed_plan)
        step = RuntimePrimitive("successor", ("n",), "n", lambda a: PrimitiveResult(a[0].value+1, {}))
        plan = synthesize_typed_plan([initial_fact("n", 0)], [step], ["n"],
            max_states=5, goal_predicates={"n": lambda f: f.value == 3})
        self.assertTrue(plan.complete)
        self.assertEqual(plan.goals["n"].value, 3)

    def test_query_synthesizes_without_witness_or_archive_mutation(self):
        e = Theory(config())
        task = {"id": "development-only", "scope": e.domain.scope, "values": ["0", "-1", "-2"],
                "budget": {"states": 128, "depth": 3, "program_size": 7, "expanded_size": 20}}
        with patch.object(e.domain, "acquire", side_effect=AssertionError("query learned")), \
             patch.object(e.domain, "settle", side_effect=AssertionError("query reproved")):
            answer = e.vocabulary.solve_observation(task, acquired=False)
        self.assertTrue(answer["solved"])
        self.assertTrue(answer["archive_unchanged"])
        self.assertEqual(e.domain.evaluate(e.vocabulary.primitive(answer["program"])), (0, -1, -2))
        with self.assertRaises(ValueError):
            e.vocabulary.solve_observation(dict(task, witness=term("var", name="x")))
        with self.assertRaises(ValueError):
            e.vocabulary.solve_observation(dict(task, requirements={"legality": "collision-free"}))

    def test_typed_leaf_argument_preserves_natural_domain(self):
        e = Theory(config())
        cid = e.add_concept(term("neg", term("var", name="x")), [])
        e.acquire(cid)
        rid = next(iter(e.state["representations"]))
        e.derive(rid, "a")
        pid = next(iter(e.state["dsl"]["recurrence_operations"]))
        examples = [term("neg", term("recurrence", term("natural", value=n), procedure=pid))
                    for n in (2, 7)]
        with lib.grammar(e.vocabulary.accepts):
            body, samples = lib.generalise(*examples)
        signature = e.vocabulary.signature(body, samples)
        self.assertEqual(signature["parameters"], {"f0": "natural"})

    def test_runtime_observation_composes_with_domain_operations(self):
        e = Theory(config())
        cid = e.add_concept(term("neg", term("var", name="x")), [])
        e.acquire(cid)
        rid = next(iter(e.state["representations"]))
        p = term("represented", term("word", letters=["a", "b"]), binding=rid)
        candidates = list(e.domain.compose(p, [p], type_of=e.vocabulary.accepts))
        for q in candidates:
            self.assertEqual(e.vocabulary.evaluate(q)[0], e.domain.evaluate(e.vocabulary.primitive(q)))
        self.assertTrue(any(q["op"] == "add" for q in candidates))

    def test_operation_alias_not_compositional_acquisition(self):
        from math_os_prototype.theory_vocabulary import context_operations
        hole = lib.program_hole(0)
        self.assertEqual(context_operations(term("neg", hole)), 1)
        self.assertEqual(context_operations(term("add", hole, term("neg", hole))), 2)

    def test_call_arguments_are_not_free_under_size_budget(self):
        from math_os_prototype.theory_vocabulary import program_size
        x = term("var", name="x")
        call = {"op": "use", "abstraction": 0, "arguments": {"f0": term("add", x, x)}}
        self.assertEqual(program_size(call), 4)

    def test_argument_lists_are_traversed_and_detached(self):
        from math_os_prototype.holonomic_relation_reuse import occurrences, replace_at
        x = term("var", name="x")
        shared = term("neg", x)
        root = term("add", shared, shared)
        paths = dict(occurrences(root))
        self.assertEqual(paths[("args", 0, "args", 0)], x)
        replacement = term("const", value="9")
        changed = replace_at(root, ("args", 0, "args", 0), replacement)
        self.assertEqual(changed["args"][1], shared)
        self.assertEqual(root["args"][0], shared)

    def test_anti_unification_shares_repeated_pairs(self):
        e = Theory(config())
        x, y = term("var", name="x"), term("neg", term("var", name="x"))
        with lib.grammar(e.vocabulary.accepts):
            body, samples = lib.generalise(term("add", x, x), term("add", y, y))
            self.assertEqual(lib.holes(body), ["f0"])
            self.assertEqual(body["args"][0], body["args"][1])
            self.assertFalse(lib.match_term(body, term("add", x, y), {}))

    def test_independent_pairs_remain_independent(self):
        e = Theory(config())
        x = term("var", name="x")
        nx = term("neg", x)
        with lib.grammar(e.vocabulary.accepts):
            body, _ = lib.generalise(term("add", x, nx), term("add", nx, x))
        self.assertEqual(len(lib.holes(body)), 2)

    def test_persistence_and_exact_call_expansion(self):
        e = Theory(config())
        e.run(cycles=25)
        restored = Theory(config(), state=e.snapshot())
        self.assertEqual(e.vocabulary.table(), restored.vocabulary.table())
        for row in restored.state["dsl"]["corpus"]:
            self.assertEqual(restored.vocabulary.primitive(row["program"]), row["primitive"])
        with self.assertRaises(ValueError):
            restored.vocabulary.expand({"op": "use", "abstraction": 999, "arguments": {}})

    def test_no_dsl_does_not_delete_dependencies(self):
        e = Theory(config(), dsl_reuse=False)
        e.run(cycles=25)
        self.assertFalse(e.state["dsl"]["executions"])
        for row in e.state["dsl"]["corpus"]:
            self.assertEqual(e.vocabulary.primitive(row["program"]), row["primitive"])


if __name__ == "__main__":
    unittest.main()
