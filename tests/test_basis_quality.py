"""Development ablations; no fixture is normal acquisition evidence."""
import unittest
from test_theory_dsl import config
from math_os_prototype.theory_domain import Domain, term
from math_os_prototype.theory_formation import Theory
from scripts.verify_basis_quality import action_reconstruction, scalar_reconstruction, necessity_certificate


class BasisTests(unittest.TestCase):
    def test_zero_representation_slots_are_a_real_disabled_path(self):
        c = config()
        c["budget"].update(representations=0, shared_spaces=0)
        e = Theory(c)
        e.run(cycles=10)
        self.assertFalse(e.state["representations"])
        self.assertFalse(e.state["dsl"]["recurrence_operations"])
        self.assertTrue(all(p["kind"] != "certified_scalar_recurrence" for p in e.state["procedures"].values()))

    def test_boolean_necessity_is_exhaustion_not_random_samples(self):
        d = Domain(config()["domain"])
        for removed in ("eq", "not", "and"):
            self.assertTrue(necessity_certificate(d, removed)["passed"])

    def test_symbolic_operator_search_is_bounded_and_never_claims_failed_necessity(self):
        r = scalar_reconstruction(Theory(config()), "neg", 40)
        self.assertLessEqual(r["search_nodes"], 40)
        self.assertEqual(r["status"], "unresolved within fixed search budget")
    def test_exclusions_are_enforced_by_type_checker_and_seeds(self):
        for op in ("var", "const", "neg", "pull:a"):
            d = Domain(config()["domain"], primitive_exclusions=[op])
            cases = {"var": term("var", name="x"), "const": term("const", value="0"),
                "neg": term("neg", term("var", name="x")), "pull:a": term("pull", term("var", name="x"), label="a")}
            with self.assertRaises(ValueError): d.type_of(cases[op])
            self.assertFalse(any(p["op"] == op for p in d.seeds()))
            self.assertNotEqual(d.key, Domain(config()["domain"]).key)

    def test_predicate_task_uses_exact_normal_verifier(self):
        e = Theory(config())
        x = term("var", name="x")
        p = term("eq", x, term("const", value="0"))
        t = {"id": "dev", "scope": e.domain.scope, "result_type": "predicate",
             "values": list(map(str, e.domain.evaluate(p))),
             "budget": {"states": 100, "depth": 12, "program_size": 100, "expanded_size": 100}}
        r = e.vocabulary.solve_observation(t, acquired=False)
        self.assertTrue(r["solved"])
        t["values"] = ["0", "1", "1"]
        with self.assertRaises(ValueError): e.vocabulary.solve_observation(t)

    def test_missing_equality_is_not_restored_by_predicate_fallback(self):
        e = Theory(config(), primitive_exclusions=["eq"])
        t = {"id": "dev", "scope": e.domain.scope, "result_type": "predicate", "values": ["True"]*3,
             "budget": {"states": 50, "depth": 12, "program_size": 100, "expanded_size": 100}}
        r = e.vocabulary.solve_observation(t, acquired=False)
        self.assertFalse(r["solved"])

    def test_normal_acquisition_is_sealed_with_excluded_operation(self):
        e = Theory(config(), primitive_exclusions=["neg"])
        e.run(cycles=3)
        restored = Theory(config(), **e.flags, state=e.snapshot())
        self.assertEqual(e.domain.operations, restored.domain.operations)
        with self.assertRaises(ValueError): Theory(config(), state=e.snapshot())

    def test_action_equivalence_is_a_total_map_not_sample_outputs(self):
        d = Domain({"kind": "fold_frames", "operations": ["pull", "neg"]})
        r = action_reconstruction(d, "pull:A", 512)
        self.assertTrue(r["found"])
        self.assertEqual(r["map"], r["target_map"])
        self.assertNotIn("A", str(r["body"]))


if __name__ == "__main__": unittest.main()
