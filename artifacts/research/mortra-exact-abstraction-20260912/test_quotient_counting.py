"""Regression tests for the counting lemma, the contract domain, and the series.

Each of these exists because getting it wrong gives an answer that looks right.
They are fixtures, not discovery statistics.
"""
from pathlib import Path
import itertools
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sympy as sp

from math_os_prototype import differential_representation as R
from math_os_prototype import fold_observable_system as F
from math_os_prototype import fold_tasks as T
from math_os_prototype import quotient_counting as Q
from math_os_prototype import representation_certificate as C
from math_os_prototype.holonomic_route_discovery import coefficients
from math_os_prototype.rigid_fold_problem_discovery import build_square_fold_chain


class MultiplicityTests(unittest.TestCase):
    """Two labels reaching the same successor must contribute twice."""

    ALPHABET = ("a", "b", "c")

    @staticmethod
    def collapsing_step(state, symbol):
        # 'a' and 'b' both land on the same successor; 'c' goes elsewhere
        return (state[0] + (0 if symbol in "ab" else 1),)

    def _count(self, length, **kwargs):
        return Q.layered_count(start=(0,), step=self.collapsing_step,
                               legal=lambda s, g: True, value=lambda s: s[0],
                               alphabet=self.ALPHABET, length=length, **kwargs)

    def test_a_collapsing_label_pair_is_counted_twice_not_once(self):
        found = self._count(1)
        self.assertEqual(found["distribution"], {"0": 2, "1": 1})
        self.assertEqual(found["answer"]["total_words"], 3,
                         "three labels, three words of length one")

    def test_the_total_stays_the_number_of_words_at_every_length(self):
        for length in range(5):
            self.assertEqual(self._count(length)["answer"]["total_words"],
                             len(self.ALPHABET) ** length, f"length {length}")

    def test_the_dp_reproduces_the_enumeration_exactly(self):
        for length in range(5):
            walked = Q.enumerate_count(
                start=(0,), step=self.collapsing_step, legal=lambda s, g: True,
                value=lambda s: s[0], alphabet=self.ALPHABET, length=length)
            merged = self._count(length)
            self.assertEqual(walked["answer"], merged["answer"], f"length {length}")
            self.assertEqual(walked["distribution"], merged["distribution"])

    def test_deduplicating_successors_would_have_given_the_wrong_count(self):
        """The mistake this test exists to catch, shown to be a mistake."""
        wrong = {}
        for state in [(0,)]:
            for successor in {self.collapsing_step(state, g)
                              for g in self.ALPHABET}:     # a set: the bug
                wrong[successor] = wrong.get(successor, 0) + 1
        self.assertEqual(sum(wrong.values()), 2)
        self.assertNotEqual(sum(wrong.values()),
                            self._count(1)["answer"]["total_words"])


class LegalityTests(unittest.TestCase):
    def test_an_illegal_step_contributes_nothing(self):
        found = Q.layered_count(
            start=(0,), step=lambda s, g: (s[0] + 1,),
            legal=lambda s, g: g != "b", value=lambda s: s[0],
            alphabet=("a", "b"), length=3)
        self.assertEqual(found["answer"]["total_words"], 1)
        self.assertEqual(found["illegal_steps"], 3)

    def test_no_legal_word_leaves_the_maximum_undefined_not_zero(self):
        found = Q.layered_count(
            start=(0,), step=lambda s, g: (s[0] + 1,),
            legal=lambda s, g: False, value=lambda s: s[0],
            alphabet=("a",), length=2)
        self.assertIsNone(found["answer"]["v_max"])
        self.assertEqual(found["answer"]["count_max"], 0)
        self.assertIn("undefined", found["answer"]["undefined_because"])


class LayerTests(unittest.TestCase):
    """States of different depths must never be merged, nor compared."""

    @staticmethod
    def returning_step(state, symbol):
        return ((state[0] + 1) % 2,)

    def test_a_state_that_recurs_at_another_depth_is_not_merged_with_it(self):
        found = Q.layered_count(start=(0,), step=self.returning_step,
                                legal=lambda s, g: True, value=lambda s: s[0],
                                alphabet=("a", "b"), length=4)
        self.assertEqual(found["answer"]["total_words"], 16,
                         "returning to an earlier state does not lose words")
        self.assertEqual(found["states_per_layer"], [1, 1, 1, 1, 1])

    def test_the_certificate_compares_only_words_of_equal_length(self):
        task = T.displacement_task(axis=0)
        grouped = C.layers(task, 3)
        self.assertEqual(sorted(grouped), [0, 1, 2, 3])
        for level, words in grouped.items():
            self.assertTrue(all(len(word) == level for word, _ in words))


class ContractDomainTests(unittest.TestCase):
    """A counterexample has to live where the DP actually merges."""

    @classmethod
    def setUpClass(cls):
        system = F.fold_system()
        found = F.acquire_closure(system, F.VARIABLES[0], maximum_dimension=64)
        cls.record = {"observable": found["observable"], "basis": found["basis"],
                      "action_matrices": found["action_matrices"],
                      "dimension": found["dimension"],
                      "identity_residuals_all_zero":
                          found["identity_residuals_all_zero"],
                      "closure_scope": found["scope"]}

    def test_the_collision_refusal_is_between_words_of_the_same_length(self):
        task = T.displacement_task(axis=0, collision_free=True)
        verdict = C.certify(self.record, task, depth=4)
        self.assertFalse(verdict["admissible"])
        witness = next(c["counterexample"] for c in verdict["checks"]
                       if c.get("counterexample"))
        self.assertEqual(len(witness["word_a"]), len(witness["word_b"]),
                         "a cross-length pair is not something the DP ever merges")
        self.assertEqual(witness["length"], len(witness["word_a"]))

    def test_that_witness_is_real_when_rerun(self):
        task = T.displacement_task(axis=0, collision_free=True)
        verdict = C.certify(self.record, task, depth=4)
        witness = next(c["counterexample"] for c in verdict["checks"]
                       if c.get("counterexample"))
        closure = F.closure_from_record(self.record)
        observe = C.compiled_observation(closure)
        left = observe(T.run_word(witness["word_a"]))
        right = observe(T.run_word(witness["word_b"]))
        self.assertEqual(left, right, "the two words really do share Phi")
        self.assertNotEqual(
            build_square_fold_chain(witness["word_a"] + witness["label"]
                                    ).proper_intersection_pairs == (),
            build_square_fold_chain(witness["word_b"] + witness["label"]
                                    ).proper_intersection_pairs == (),
            "and applying the named label really does differ in legality")

    def test_a_refusal_here_is_about_this_representation_not_about_all(self):
        task = T.displacement_task(axis=0, collision_free=True)
        self.assertIn("panels", task.state_contract)
        verdict = C.certify(self.record, task, depth=4)
        self.assertIn("nothing about every representation",
                      verdict["task_contract"]["notes"])

    def test_the_history_sufficient_state_really_decides_legality(self):
        """Otherwise the refusal would be about a badly posed task."""
        task = T.displacement_task(axis=0, collision_free=True)
        for length in range(5):
            for letters in itertools.product("ACGT", repeat=length):
                word = "".join(letters)
                expected = not build_square_fold_chain(word).proper_intersection_pairs
                self.assertEqual(task.legal_word(word), expected, word)


class SpanTests(unittest.TestCase):
    def test_a_reordered_basis_is_the_same_space(self):
        left = {"_basis": [F.VARIABLES[0], F.VARIABLES[1]]}
        right = {"_basis": [F.VARIABLES[1], 2 * F.VARIABLES[0]]}
        self.assertTrue(C.same_span(left, right)["same"])

    def test_a_genuinely_larger_space_is_not_the_same(self):
        left = {"_basis": [F.VARIABLES[0]]}
        right = {"_basis": [F.VARIABLES[0], F.VARIABLES[1]]}
        self.assertFalse(C.same_span(left, right)["same"])


class ReadoutTests(unittest.TestCase):
    """The reduced DP must evaluate the certified read-out, not basis slot zero."""

    def test_a_rational_readout_is_kept_exact_not_rounded(self):
        """A read-out of 3/4 and 1/4 rounded to integers becomes a constant."""
        system = F.fold_system()
        found = F.acquire_closure(system, F.VARIABLES[9] + F.VARIABLES[0],
                                  maximum_dimension=64)
        record = {"observable": found["observable"], "basis": found["basis"],
                  "action_matrices": found["action_matrices"],
                  "dimension": found["dimension"],
                  "identity_residuals_all_zero":
                      found["identity_residuals_all_zero"],
                  "closure_scope": found["scope"]}
        verdict = C.certify(record, T.displacement_task(axis=0), depth=3)
        routes = C.abstract_routes(F.closure_from_record(record), verdict,
                                   T.displacement_task(axis=0))
        observe = C.compiled_observation(F.closure_from_record(record))
        for word in ("", "A", "AG", "GCC"):
            state = T.run_word(word)
            carried = routes["start_from"](state, observe)
            self.assertEqual(sp.nsimplify(routes["value"](carried)), state[0],
                             f"the read-out must reproduce c1 at {word!r}")

    def test_the_witness_is_only_carried_when_something_needs_it(self):
        """Otherwise the reduced run calls the update it is meant to replace."""
        system = F.fold_system()
        found = F.acquire_closure(system, F.VARIABLES[0], maximum_dimension=64)
        record = {"observable": found["observable"], "basis": found["basis"],
                  "action_matrices": found["action_matrices"],
                  "dimension": found["dimension"],
                  "identity_residuals_all_zero":
                      found["identity_residuals_all_zero"],
                  "closure_scope": found["scope"]}
        task = T.displacement_task(axis=0)
        verdict = C.certify(record, task, depth=3)
        routes = C.abstract_routes(F.closure_from_record(record), verdict, task)
        self.assertFalse(routes["carries_witness"])
        self.assertTrue(routes["readout_is_linear"])

    def test_the_readout_is_the_coefficients_not_the_first_coordinate(self):
        system = F.fold_system()
        shifted = F.VARIABLES[9] + F.VARIABLES[0]        # F31 + c1
        found = F.acquire_closure(system, shifted, maximum_dimension=64)
        record = {"observable": found["observable"], "basis": found["basis"],
                  "action_matrices": found["action_matrices"],
                  "dimension": found["dimension"],
                  "identity_residuals_all_zero":
                      found["identity_residuals_all_zero"],
                  "closure_scope": found["scope"]}
        task = T.displacement_task(axis=0)                # evaluates c1
        verdict = C.certify(record, task, depth=3)
        if not verdict["admissible"]:
            self.skipTest("this closure does not determine c1; nothing to check")
        self.assertNotEqual(verdict["readout"], ["1", "0", "0", "0"],
                            "the first basis element is not c1 here")
        from math_os_prototype import representation_benchmarks as B
        closure = F.closure_from_record(record)
        for length in (3, 4):
            walked = T.enumerate_answer(task, length)["answer"]
            reduced = B.represented_rung(closure, verdict, task, length)["value"]
            self.assertEqual(walked, reduced,
                             "the read-out, not slot zero, is what is evaluated")


class SeriesTests(unittest.TestCase):
    """Degenerate and variable-coefficient cases in the differential route."""

    ZERO = {"op": "poly", "coefficients": ["0"]}
    EXPONENTIAL = {"op": "hyper", "a": ["1"], "b": ["1"]}

    def test_the_zero_series_is_handled_or_refused_with_a_reason(self):
        try:
            record = R.acquire(self.ZERO, check_terms=12)
        except (ValueError, AssertionError) as refusal:
            self.assertTrue(str(refusal))
            return
        values = R.series_from_record(record, 12)["values"]
        self.assertEqual([sp.expand(v) for v in values], [0] * 12)

    def test_a_variable_coefficient_recurrence_is_n_dependent(self):
        """`exp(x**2)`: the companion matrix must change with the index."""
        program = {"op": "pullback", "child": self.EXPONENTIAL,
                   "numerator": ["0", "0", "1"], "denominator": ["1"]}
        record = R.acquire(program, check_terms=20)
        polynomials = [sp.sympify(p) for p in record["recurrence_polynomials"]]
        self.assertTrue(any(p.free_symbols for p in polynomials),
                        "the recurrence coefficients depend on the index")
        first = R.companion_matrix(record, 4)
        second = R.companion_matrix(record, 5)
        self.assertNotEqual(first, second,
                            "a constant matrix power would be the wrong shape "
                            "of claim for a variable-coefficient recurrence")

    def test_the_unrolled_series_matches_the_independent_route(self):
        program = {"op": "pullback", "child": self.EXPONENTIAL,
                   "numerator": ["0", "0", "1"], "denominator": ["1"]}
        record = R.acquire(program, check_terms=20)
        unrolled = R.series_from_record(record, 20)["values"]
        reference = coefficients(program, 20)
        self.assertEqual([sp.cancel(a - b) for a, b in zip(unrolled, reference)],
                         [0] * 20)

    def test_the_singular_indices_are_carried_as_seeds_not_derived(self):
        record = R.acquire(self.EXPONENTIAL, check_terms=12)
        leading = sp.sympify(record["recurrence_polynomials"][0])
        start = record["first_solvable_index"]
        self.assertEqual(len(record["seed_coefficients"]), start)
        for index in range(start):
            if leading.free_symbols:
                self.assertEqual(sp.simplify(leading.subs(R.N, index)), 0,
                                 "a seed index is one the recurrence cannot solve")


if __name__ == "__main__":
    unittest.main()
