"""Tests for the evaluation layer. Fixtures, never discovery statistics.

What is asserted is that the instrument works in both directions -- that it
fires when the primitive is called and reads zero when it is not -- and that the
comparison keeps its components apart. No number produced by a run is asserted
as a result.
"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sympy as sp

from math_os_prototype import differential_representation as R
from math_os_prototype import fold_observable_system as F
from math_os_prototype import representation_benchmarks as B
from math_os_prototype import representation_evaluation as E

X = R.X
EXPONENTIAL = {"op": "hyper", "a": ["1"], "b": ["1"]}
GEOMETRIC = {"op": "hyper", "a": ["1", "1"], "b": ["1"]}
PRODUCT = {"op": "mul", "left": EXPONENTIAL, "right": GEOMETRIC}


class InstrumentTests(unittest.TestCase):
    """A zero is only evidence if the same instrument fires on a positive."""

    def test_it_fires_when_the_derivative_primitive_is_called(self):
        seen = E.measure(lambda: str(sp.diff(sp.exp(X) / (1 - X), X, 4)))
        self.assertGreater(seen["derivative_calls"], 0)
        self.assertEqual(seen["derivative_request_calls"], 1)
        self.assertIn("Expr.diff", seen["trace_sample"])

    def test_the_method_spelling_is_counted_too(self):
        seen = E.measure(lambda: str((sp.exp(X) / (1 - X)).diff(X)))
        self.assertGreater(seen["derivative_calls"], 0)
        self.assertEqual(seen["derivative_request_calls"], 0,
                         "expr.diff(...) is not a sympy.diff request")

    def test_a_run_that_takes_no_derivative_reads_zero(self):
        seen = E.measure(lambda: str(sp.expand((1 + X) ** 3)))
        self.assertEqual(seen["derivative_calls"], 0)
        self.assertNotIn("Expr.diff", seen["trace_sample"])

    def test_a_binding_copied_by_from_import_is_still_counted(self):
        """`from x import f` copies the reference; both copies must count once."""
        seen = E.measure(lambda: R.recurrence_polynomials(EXPONENTIAL))
        self.assertEqual(seen["proof_calls"], 1,
                         "differential_representation calls its own imported "
                         "binding of annihilator")

    def test_the_originals_come_back_afterwards(self):
        before = sp.Expr.diff
        E.measure(lambda: str(sp.diff(sp.sin(X), X)))
        self.assertIs(sp.Expr.diff, before)

    def test_the_fold_primitive_is_counted(self):
        seen = E.measure(lambda: B.kinematic_fold_run("ACGT"))
        self.assertEqual(seen["fold_step_calls"], 4)


class CacheSeparationTests(unittest.TestCase):
    """Memoisation is measured apart from what the representation removed."""

    def test_a_cold_run_reports_no_hits_and_a_warm_one_does(self):
        from math_os_prototype.holonomic_route_discovery import coefficients
        cold = E.measure(lambda: len(coefficients(PRODUCT, 20)), cold=True)
        warm = E.measure(lambda: len(coefficients(PRODUCT, 20)), cold=False)
        self.assertEqual(cold["cache_hits"]["coefficients"], 0)
        self.assertGreater(warm["cache_hits"]["coefficients"], 0)

    def test_both_sides_of_a_comparison_ran_cold(self):
        record = B.differential_comparison("t", PRODUCT, sp.exp(X) / (1 - X),
                                           upto=8, check_terms=8)
        self.assertTrue(record["primitive_reduction"]["caches_cold_on_both_sides"])
        self.assertIsNotNone(record["recomputation_reduction"]["memoisation_only"])


class DifferentialRepresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record = R.acquire(PRODUCT, check_terms=16)

    def test_the_acquisition_carries_its_own_check(self):
        self.assertTrue(self.record["verification"]["exact"])
        self.assertEqual(self.record["verification"]["failing_indices"], [])
        self.assertIn("never through the annihilating operator",
                      self.record["verification"]["checked_against"])

    def test_the_record_stores_no_answer(self):
        stored = set(self.record)
        self.assertIn("recurrence_polynomials", stored)
        self.assertIn("seed_coefficients", stored)
        self.assertEqual(len(self.record["seed_coefficients"]),
                         self.record["first_solvable_index"])

    def test_a_tampered_record_is_caught_by_the_same_check(self):
        broken = dict(self.record)
        broken["seed_coefficients"] = ["2"] + list(self.record["seed_coefficients"][1:])
        self.assertFalse(R.verify(broken, PRODUCT, terms=16)["exact"])

    def test_the_matrix_action_and_the_unrolling_are_the_same_numbers(self):
        scalar = R.series_from_record(self.record, 18)["values"]
        matrix = R.jet_by_matrix_action(self.record, 18)["values"]
        self.assertEqual([sp.cancel(a - b) for a, b in zip(scalar, matrix)],
                         [0] * 18)

    def test_the_companion_matrix_has_the_window_dimension(self):
        matrix = R.companion_matrix(self.record, 7)
        self.assertEqual(matrix.shape, (self.record["order"], self.record["order"]))

    def test_the_values_match_the_closed_form_taken_independently(self):
        closed = sp.exp(X) / (1 - X)
        expression = closed
        for order in range(9):
            self.assertEqual(sp.expand(expression.subs(X, 0)),
                             R.derivative_values(self.record, order)["values"][order],
                             f"order {order}")
            expression = sp.diff(expression, X)

    def test_using_the_representation_enters_no_derivative_primitive(self):
        """The claim the whole comparison rests on, read off the trace."""
        seen = E.measure(lambda: {"value": [str(v) for v in
                                            R.derivative_values(self.record, 20)["values"]]})
        self.assertEqual(seen["derivative_calls"], 0)
        self.assertEqual(seen["derivative_request_calls"], 0)
        self.assertNotIn("Expr.diff", seen["trace_sample"])


class PowerTests(unittest.TestCase):
    def test_squaring_gives_the_same_matrix_with_less_depth(self):
        matrix = sp.Matrix([[1, 1], [0, 1]])
        found = E.power_by_squaring(matrix, 16, identity=sp.eye(2))
        self.assertEqual(found["value"], matrix ** 16)
        self.assertLess(found["depth"], 16)

    def test_a_zero_exponent_is_the_identity(self):
        found = E.power_by_squaring(sp.Matrix([[2]]), 0, identity=sp.eye(1))
        self.assertEqual(found["value"], sp.eye(1))
        self.assertEqual(found["multiplications"], 0)


class AssemblyTests(unittest.TestCase):
    BASE = {"primitive_calls": 100, "derivative_calls": 90, "simplify_calls": 5,
            "solver_calls": 0, "proof_calls": 0, "fold_step_calls": 5,
            "derivative_request_calls": 3, "trace_sample": ["Expr.diff"],
            "wall_time": 1.0, "peak_memory": 10, "cache_hits": {},
            "cold_caches": True, "sequential_depth": 40,
            "candidates_generated": None, "search_nodes": None,
            "rejected_candidates": None, "flop_proxy": None,
            "nodes": {"derivative:Expr.diff:Mul": {
                "kind": "derivative", "label": "Expr.diff", "signature": "Mul",
                "count": 90, "first_positions": [0]}},
            "nodes_truncated": False}

    def _record(self, **overrides):
        after = dict(self.BASE, primitive_calls=10, derivative_calls=0,
                     simplify_calls=10, trace_sample=[], sequential_depth=20)
        after.update(overrides)
        return E.evaluate("t", baseline=self.BASE, represented=after,
                          acquisition={"acquisition_primitive_calls": 450},
                          raw_description_bits=1000, representation_bits=300,
                          conditional_description_bits=100,
                          raw_state_dimension=12, representation_dimension=4)

    def test_break_even_is_the_acquisition_over_the_per_use_saving(self):
        record = self._record()
        self.assertEqual(
            record["cumulative"]["break_evens"]["compute_break_even_reuse_count"], 5)

    def test_no_saving_reports_no_break_even_rather_than_a_large_one(self):
        record = self._record(primitive_calls=100)
        self.assertIsNone(
            record["cumulative"]["break_evens"]["compute_break_even_reuse_count"])

    def test_a_component_that_got_worse_is_kept_with_its_sign(self):
        record = self._record()
        self.assertEqual(
            record["primitive_reduction"]["eliminated_by_representation"]["simplify_calls"],
            -5, "the representation used more simplification, and that is recorded")

    def test_the_depth_ratio_is_recorded_and_not_treated_as_a_verdict(self):
        record = self._record(sequential_depth=80)
        self.assertLess(record["execution_depth"]["depth_reduction_ratio"], 1)
        self.assertIn("not penalised",
                      record["execution_depth"]["not_a_success_condition"])
        self.assertEqual(
            record["cumulative"]["break_evens"]["compute_break_even_reuse_count"],
            5, "a worse depth does not change what the calls say")

    def test_a_negative_description_gain_still_reports_where_it_turns(self):
        record = E.evaluate("t", baseline=self.BASE, represented=dict(self.BASE),
                            acquisition={},
                            raw_description_bits=200, representation_bits=3000,
                            conditional_description_bits=100,
                            raw_state_dimension=12, representation_dimension=4)
        compression = record["description_compression"]
        self.assertLess(compression["net_description_gain_bits"], 0)
        self.assertEqual(compression["description_break_even_task_count"], 30)

    def test_every_component_is_its_own_section(self):
        record = self._record()
        for section in ("description_compression", "state_reduction",
                        "primitive_reduction", "recomputation_reduction",
                        "search_reduction", "execution_depth", "real_cost",
                        "acquisition_cost", "reuse", "cumulative"):
            self.assertIn(section, record)
        self.assertNotIn("score", record)
        self.assertNotIn("total", record)


class ComparisonTests(unittest.TestCase):
    """The three comparisons, at sizes small enough to run in a test."""

    @classmethod
    def setUpClass(cls):
        system = F.fold_system()
        found = F.acquire_closure(system, F.VARIABLES[0], maximum_dimension=64)
        cls.closure_record = {"observable": found["observable"],
                              "basis": found["basis"],
                              "action_matrices": found["action_matrices"],
                              "identity_residuals_all_zero":
                                  found["identity_residuals_all_zero"],
                              "closure_scope": found["scope"]}
        cls.cost = {"acquisition_primitive_calls": 669, "acquisition_time": 1.0}
        from math_os_prototype import fold_tasks
        from math_os_prototype import representation_certificate as certificates
        cls.task = fold_tasks.displacement_task(axis=0)
        cls.certificate = certificates.certify(cls.closure_record, cls.task,
                                               depth=4, premise=F.verify_step(system))

    def test_the_differential_comparison_agrees_and_eliminates_the_derivative(self):
        record = B.differential_comparison("d", PRODUCT, sp.exp(X) / (1 - X),
                                           upto=12, check_terms=8)
        self.assertTrue(record["agreement"]["all_agree"])
        primitive = record["primitive_reduction"]
        self.assertGreater(primitive["derivative_calls_before"], 0)
        self.assertEqual(primitive["derivative_calls_after"], 0)
        self.assertNotIn("Expr.diff", primitive["trace_sample_after"])
        self.assertGreater(record["reuse"]["heldout_successes"], 0)
        self.assertEqual(record["reuse"]["failed_reuses"], 0)

    def test_the_fold_repeat_comparison_reduces_depth_and_agrees(self):
        record = B.fold_repeat_comparison(
            "f", self.closure_record, self.cost, block="GCC", repeats=16,
            extra_tasks=(("AG", 5),))
        self.assertTrue(record["agreement"]["agree"])
        self.assertTrue(all(task["agree"]
                            for task in record["agreement"]["held_out_tasks"]))
        depth = record["execution_depth"]
        self.assertEqual(depth["sequential_depth_before"], 48)
        self.assertLess(depth["sequential_depth_after"], 48)
        self.assertEqual(record["primitive_reduction"]["fold_step_calls_after"], 0)

    def test_the_fold_search_comparison_carries_multiplicity_so_the_answers_match(self):
        record = B.fold_search_comparison("s", self.closure_record, self.cost,
                                          task=self.task, length=5,
                                          certificate=self.certificate,
                                          heldout_lengths=(4,))
        self.assertTrue(record["agreement"]["agree"])
        self.assertEqual(record["agreement"]["naive_answer"]["total_words"],
                         len(F.ALPHABET) ** 5)
        search = record["search_reduction"]
        self.assertLess(search["candidates_generated_after"],
                        search["candidates_generated_before"])
        self.assertEqual(search["rejected_candidates_after"],
                         search["rejected_candidates_before"],
                         "rejection is counted in words on both sides")

    def test_the_control_arm_separates_merging_from_the_representation(self):
        record = B.fold_search_comparison("s", self.closure_record, self.cost,
                                          task=self.task, length=5,
                                          certificate=self.certificate)
        control = record["attribution_control"]
        self.assertTrue(control["agrees_with_naive"])
        self.assertLess(control["search_nodes"],
                        record["search_reduction"]["search_nodes_before"],
                        "merging alone already helps")
        self.assertLess(record["search_reduction"]["search_nodes_after"],
                        control["search_nodes"],
                        "and the representation helps further, which is what "
                        "the control arm is there to attribute")

    def test_the_premise_of_the_differential_comparison_is_checked_first(self):
        with self.assertRaises(AssertionError):
            B.differential_comparison("wrong", PRODUCT, sp.exp(X), upto=4,
                                      check_terms=8)


class GraphTests(unittest.TestCase):
    def test_the_picture_has_its_three_stages(self):
        text = E.ascii_graphs("t", raw=["a"], representation=["b"], reduced=["c"])
        self.assertIn("raw computation graph", text)
        self.assertIn("learned representation", text)
        self.assertIn("reduced computation graph", text)


if __name__ == "__main__":
    unittest.main()
