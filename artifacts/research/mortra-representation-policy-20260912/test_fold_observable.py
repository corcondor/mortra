"""Fixtures for the fold observation representation. Never discovery statistics.

The known coordinates are used here as debugging fixtures, not as results: what
is asserted is that the correspondence is exact, that the grammar is the stated
one, and that the three downstream routes agree with the kinematics.
"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sympy as sp
from math_os_prototype import fold_observable_system as F
from math_os_prototype.fold_observable_domain import FoldObservableDomain


class StepCorrespondenceTests(unittest.TestCase):
    """`encode(apply_fold_generator(x, g)) = M_g encode(x)`, not on samples."""

    @classmethod
    def setUpClass(cls):
        cls.system = F.fold_system()

    def test_the_one_step_identity_is_exact_over_every_reachable_frame(self):
        verdict = F.verify_step(self.system, depth=4)
        self.assertTrue(verdict["exact"])
        self.assertEqual(verdict["failures"], [])
        self.assertEqual(verdict["identities_checked"],
                         verdict["frames_checked"] * verdict["letters"])
        self.assertIn("symbolic", verdict["centre"])

    def test_the_centre_is_symbolic_so_every_integer_centre_is_covered(self):
        # if the check had used a fixed centre, a wrong offset could still pass
        centre = sp.symbols("x1 x2 x3")
        frame = F.reachable_frames(1)[0]
        from math_os_prototype.rigid_fold_problem_discovery import (
            FOLD_GENERATORS, apply_fold_generator)
        _, moved = apply_fold_generator(frame, tuple(centre), FOLD_GENERATORS[0])
        self.assertTrue(any(sp.sympify(component).free_symbols
                            for component in moved))

    def test_sampled_words_are_a_regression_not_the_proof(self):
        ok, failed = F.agrees_with_kinematics(self.system, ["ACGT", "AAGGCCTT"])
        self.assertTrue(ok, failed)


class GrammarTests(unittest.TestCase):
    """The candidate space is exactly what the docstring says it is."""

    def test_the_default_offers_monomials_only(self):
        offered = F.candidate_observables(degree=2, max_terms=1)
        for candidate in offered:
            self.assertEqual(len(sp.expand(candidate).as_ordered_terms()), 1)

    def test_degree_one_offers_every_state_coordinate_and_nothing_else(self):
        self.assertEqual([str(c) for c in F.candidate_observables(degree=1)],
                         list(F.VARIABLE_NAMES))

    def test_a_higher_degree_reaches_repeats_and_mixed_products(self):
        offered = {str(c) for c in F.candidate_observables(degree=2)}
        self.assertIn("c1**2", offered)
        self.assertIn("F11*c1", offered)

    def test_more_terms_enumerates_sums_with_the_declared_coefficients(self):
        offered = F.candidate_observables(degree=1, max_terms=2,
                                          coefficients=(1, -1), limit=40)
        sums = [c for c in offered if len(sp.expand(c).as_ordered_terms()) > 1]
        self.assertTrue(sums)
        for candidate in sums:
            for term in sp.expand(candidate).as_ordered_terms():
                self.assertIn(sp.sympify(term).as_coeff_Mul()[0], (1, -1))

    def test_the_order_is_fixed_so_a_limit_truncates_rather_than_selects(self):
        self.assertEqual([str(c) for c in F.candidate_observables(degree=2, limit=5)],
                         [str(c) for c in F.candidate_observables(degree=2)][:5])


class ClosureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.system = F.fold_system()

    def test_a_closure_carries_its_identity_check_and_its_scope(self):
        found = F.acquire_closure(self.system, F.VARIABLES[0], maximum_dimension=64)
        self.assertTrue(found["closed"])
        self.assertTrue(found["identity_residuals_all_zero"])
        self.assertIn("all finite words", found["scope"])
        self.assertEqual(len(found["basis"]), found["dimension"])

    def test_a_dimension_cap_refuses_rather_than_truncating(self):
        found = F.acquire_closure(self.system, F.VARIABLES[0], maximum_dimension=2)
        self.assertFalse(found["closed"])
        self.assertIn("maximum_dimension", found["reason"])


class DownstreamTests(unittest.TestCase):
    """Three different computations, each checked against the kinematics."""

    @classmethod
    def setUpClass(cls):
        system = F.fold_system()
        found = F.acquire_closure(system, F.VARIABLES[0], maximum_dimension=64)
        # go through the record, the way the session does
        cls.closure = F.closure_from_record({
            "observable": found["observable"], "basis": found["basis"],
            "action_matrices": found["action_matrices"]})

    def test_a_record_can_be_read_back_and_used(self):
        self.assertTrue(self.closure["closed"])
        self.assertEqual(len(self.closure["_basis"]), 4)
        self.assertEqual(sorted(self.closure["_matrices"]), list(F.ALPHABET))

    def test_a_named_word_is_the_letters_matrices_in_word_order(self):
        for word in ("GCC", "ACGT", "TTTAGCCC"):
            self.assertEqual(F.apply_word(self.closure, word),
                             F.observed(self.closure, word), word)

    def test_a_block_repeated_is_the_block_matrix_to_that_power(self):
        for repeats in range(1, 5):
            self.assertEqual(F.apply_block_power(self.closure, "GCC", repeats),
                             F.observed(self.closure, "GCC" * repeats))

    def test_the_total_over_all_words_is_the_matrix_sum_to_that_power(self):
        for length in (1, 2, 3):
            self.assertEqual(F.sum_over_all_words(self.closure, length),
                             F.brute_force_sum(self.closure, length))

    def test_that_total_is_over_every_word_not_the_collision_free_ones(self):
        """The set summed over is every word, and the two sets are not the same.

        What is asserted is the scope, not a difference in the number. For some
        observable the colliding words can contribute zero and the two totals
        coincide -- that happens here at length 4 -- so asserting they differ
        would be asserting something untrue.
        """
        from math_os_prototype.rigid_fold_problem_discovery import build_square_fold_chain
        import itertools
        length = 4
        every = [w for w in itertools.product(F.ALPHABET, repeat=length)]
        clean = [w for w in every
                 if not build_square_fold_chain(
                     "".join(w)).proper_intersection_pairs]
        self.assertLess(len(clean), len(every),
                        "the collision-free words are a proper subset here")
        every_total = sum(F.observed(self.closure, "".join(w)) for w in every)
        self.assertEqual(F.sum_over_all_words(self.closure, length), every_total,
                         "the matrix-sum route totals EVERY word")
        clean_total = sum(F.observed(self.closure, "".join(w)) for w in clean)
        # recorded, not asserted either way: for this observable they coincide
        self.assertEqual(F.sum_over_all_words(self.closure, length) - clean_total,
                         every_total - clean_total)


class RepeatLawTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.system = F.fold_system()
        cls.closure = F.acquire_closure(cls.system, F.VARIABLES[0],
                                        maximum_dimension=64)

    def test_a_law_that_holds_reports_its_own_checks(self):
        law = F.prove_repeat_law(self.closure, "GCC", cap=16)
        self.assertTrue(law["proved"])
        self.assertTrue(law["base_case_exact"])
        self.assertTrue(law["all_steps_exact"])
        self.assertFalse(law["fit_used_as_proof"])
        self.assertEqual(law["scope"], "all_finite_words")

    def test_a_law_that_does_not_hold_is_refused_with_a_reason(self):
        law = F.prove_repeat_law(self.closure, "AG", cap=16)
        self.assertFalse(law["proved"])
        self.assertIsNotNone(law["reason"])

    def test_a_refused_law_does_not_demote_the_closure(self):
        self.assertTrue(self.closure["closed"])
        self.assertTrue(self.closure["identity_residuals_all_zero"])


class RecurrenceTests(unittest.TestCase):
    """The other existing prover, used where its premises fit."""

    @classmethod
    def setUpClass(cls):
        cls.closure = F.acquire_closure(F.fold_system(), F.VARIABLES[0],
                                        maximum_dimension=64)

    def test_it_applies_where_the_affine_law_refuses(self):
        block = "AG"
        self.assertFalse(F.prove_repeat_law(self.closure, block, cap=16)["proved"])
        recurrence = F.prove_repeat_recurrence(self.closure, block)
        self.assertTrue(recurrence["proved"])
        self.assertTrue(recurrence["residuals_all_zero"])
        self.assertGreater(recurrence["order"], 0)

    def test_the_unrolled_recurrence_matches_the_kinematics(self):
        for block in ("AG", "AAAG", "ACGT"):
            recurrence = F.prove_repeat_recurrence(self.closure, block)
            if not recurrence["proved"]:
                continue
            for count in range(0, 9):
                self.assertEqual(
                    F.recurrence_values(recurrence, self.closure, block, count),
                    F.observed(self.closure, block * count),
                    f"{block} at {count}")

    def test_it_is_refused_with_a_reason_where_its_premises_do_not_fit(self):
        recurrence = F.prove_repeat_recurrence(self.closure, "GCC")
        self.assertFalse(recurrence["proved"])
        self.assertIn("sequence", recurrence["reason"])

    def test_neither_prover_failing_demotes_the_closure(self):
        self.assertTrue(self.closure["closed"])
        self.assertTrue(self.closure["identity_residuals_all_zero"])


class DomainTests(unittest.TestCase):
    BASE = {"domain": "fold_observable", "observable_degree": 1,
            "observables_per_cycle": 2, "fold_min": 3,
            "fold_counts_per_cycle": 1, "fold_beam_width": 8,
            "prediction_repeats": 2, "sum_length": 2}

    def test_the_cursor_and_the_premise_survive_a_round_trip(self):
        domain = FoldObservableDomain(self.BASE)
        domain.search(self.BASE, 0)
        state = domain.state()
        restored = FoldObservableDomain.restore(self.BASE, state)
        self.assertEqual(restored.cursor, domain.cursor)
        self.assertEqual(restored.blocks, domain.blocks)
        self.assertTrue(restored.step_verification["exact"])
        self.assertEqual(len(restored.acquisitions), len(domain.acquisitions))

    def test_a_tampered_state_is_refused(self):
        domain = FoldObservableDomain(self.BASE)
        state = domain.state()
        state["cursor"] = 99
        with self.assertRaises(ValueError):
            FoldObservableDomain.restore(self.BASE, state)

    def test_the_prediction_is_recorded_before_the_kinematics_agrees(self):
        domain = FoldObservableDomain(self.BASE)
        domain.search(self.BASE, 0)
        offered = domain.follow_ups(self.BASE, [])
        self.assertTrue(offered)
        for entry in offered:
            row = entry["prediction"]
            self.assertIn(row["mode"], ("word", "block_power", "recurrence",
                                        "sum_over_all_words"))
            self.assertTrue(row["agree"], row)


class DomainEvaluationTests(unittest.TestCase):
    """Every acquired representation carries what it actually saved."""

    BASE = dict(DomainTests.BASE, observables_per_cycle=1,
                evaluation_repeats=8, evaluation_search_length=5)

    @classmethod
    def setUpClass(cls):
        cls.domain = FoldObservableDomain(cls.BASE)
        cls.domain.search(cls.BASE, 0)
        cls.record = cls.domain.acquisitions[0]

    def test_the_acquisition_prices_itself_and_names_the_shared_premise(self):
        cost = self.record["acquisition_cost"]
        self.assertGreater(cost["acquisition_primitive_calls"], 0)
        self.assertEqual(cost["acquisition_proof_calls"], 1)
        self.assertIn("paid", cost["shared_premise"])

    def test_each_representation_carries_its_own_evaluation(self):
        found = self.record["evaluation"]
        for task in ("repeat", "search"):
            self.assertIn("primitive_reduction", found[task])
            self.assertEqual(found[task]["representation"]["observable"],
                             self.record["observable"])

    def test_the_two_paths_agree_and_the_primitive_really_was_not_called(self):
        found = self.record["evaluation"]
        self.assertTrue(found["repeat"]["agreement"]["agree"])
        self.assertTrue(found["search"]["agreement"]["agree"])
        for task in ("repeat", "search"):
            primitive = found[task]["primitive_reduction"]
            self.assertGreater(primitive["fold_step_calls_before"], 0)
            self.assertEqual(primitive["fold_step_calls_after"], 0)
            self.assertEqual(primitive["trace_sample_after"], [])

    def test_nothing_is_collapsed_into_a_score(self):
        found = self.record["evaluation"]["repeat"]
        self.assertNotIn("score", found)
        for section in ("description_compression", "state_reduction",
                        "primitive_reduction", "recomputation_reduction",
                        "execution_depth", "real_cost", "acquisition_cost",
                        "reuse", "cumulative"):
            self.assertIn(section, found)

    def test_the_evaluation_survives_the_state_round_trip(self):
        state = self.domain.state()
        restored = FoldObservableDomain.restore(self.BASE, state)
        self.assertEqual(restored.acquisitions[0]["evaluation"],
                         self.record["evaluation"])

    def test_it_can_be_switched_off_without_changing_the_acquisition(self):
        quiet = FoldObservableDomain(dict(self.BASE,
                                          evaluate_representations=False))
        quiet.search(quiet.config, 0)
        self.assertNotIn("evaluation", quiet.acquisitions[0])
        self.assertEqual(quiet.acquisitions[0]["basis"], self.record["basis"])


if __name__ == "__main__":
    unittest.main()
