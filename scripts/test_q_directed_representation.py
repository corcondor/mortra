"""Development fixtures, not autonomous discovery results."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sympy as sp
from math_os_prototype import fold_observable_system as F
from math_os_prototype import fold_tasks as T
from math_os_prototype import representation_certificate as C
from math_os_prototype import representation_ledger as L
from math_os_prototype import representation_reuse as R
from math_os_prototype import self_directed_search as S
from math_os_prototype import representation_benchmarks as B


class DirectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.system = F.fold_system()
        cls.premise = F.verify_step(cls.system)

    def record(self, task):
        found = S.acquire_task_closure(self.system, task, 64)
        return S._closure_record(found, self.premise)

    def test_task_expression_not_named_coordinate(self):
        q = (2*F.VARIABLES[1] - F.VARIABLES[2])/3
        task = replace(T.displacement_task(), observable_expression=q,
                       value=lambda s: sp.Rational(1, 3)*(2*s[1]-s[2]))
        record = self.record(task)
        cert = C.certify(record, task, depth=2, premise=self.premise)
        self.assertTrue(cert["admissible"])
        for n in (0, 1, 3, 4):
            actual = B.represented_rung(F.closure_from_record(record), cert, task, n)
            expected = T.enumerate_answer(task, n)
            self.assertEqual(actual["value"], expected["answer"])
            self.assertEqual(actual["distribution"], expected["distribution"])

    def test_several_required_observables_are_closed_together(self):
        task = replace(T.displacement_task(), required_observables=(F.VARIABLES[2],))
        closure = F.closure_from_record(self.record(task))
        for q in (task.observable_expression, *task.required_observables):
            self.assertTrue(C.span_membership(closure, q)["member"])
        self.assertEqual(len(closure["_basis"]), 8)

    def test_dimension_cap_is_not_silently_truncated(self):
        found = S.acquire_task_closure(self.system, T.displacement_task(), 2)
        self.assertFalse(found["closed"])

    def test_zero_and_missing_observables_are_explicit_refusals(self):
        for q in (sp.S.Zero, None):
            found = S.acquire_task_closure(self.system, replace(T.displacement_task(),
                                                               observable_expression=q), 64)
            self.assertFalse(found["closed"])

    def test_new_route_does_not_enumerate_observable_candidates(self):
        with patch.object(F, "candidate_observables", side_effect=AssertionError("enumeration")):
            trace, _ = S.solve(T.sum_of_centre_task(), route="q-directed",
                               probe_length=2, certificate_depth=3,
                               verify_lengths=(2,), answer_lengths=(4,))
        self.assertEqual(len(trace["candidates_offered"]), 1)
        self.assertEqual(trace["costs"]["acquisition"]["prover_calls"], 1)
        self.assertTrue(trace["all_checks_agree"])

    def test_finite_frame_sample_is_not_a_closed_domain(self):
        self.assertFalse(F.verify_step(self.system, depth=0)["frames_closed"])

    def test_collision_task_refuses_q_space_and_uses_exact_fallback(self):
        trace, _ = S.solve(T.displacement_task(collision_free=True), route="q-directed",
                           probe_length=2, certificate_depth=3,
                           verify_lengths=(3,), answer_lengths=(4,))
        self.assertTrue(trace["fallback"])
        self.assertTrue(trace["all_checks_agree"])
        self.assertIn("legality", trace["refused_by_certificate"][0]["refused_by"])


class ReuseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.task = T.displacement_task()
        cls.system = F.fold_system()
        cls.premise = F.verify_step(cls.system)
        cls.record = S._closure_record(S.acquire_task_closure(cls.system, cls.task, 64), cls.premise)
        cls.rep = S._representation_of(cls.record)
        cls.cert = C.certify(cls.record, cls.task, depth=3, premise=cls.premise)

    def book(self):
        book = L.Ledger()
        book.note_certificate(self.rep, self.cert)
        return book

    def test_renamed_task_and_changed_start_reuse_without_any_acquisition(self):
        task = T.displacement_task(name="unseen display name", start_word="AG")
        with tempfile.TemporaryDirectory() as tmp:
            path = self.book().save(Path(tmp)/"ledger.json")
            book = L.Ledger.load(path)
            with patch.object(F, "fold_system", side_effect=AssertionError("system rebuild")), \
                 patch.object(F, "acquire_closure", side_effect=AssertionError("acquire")), \
                 patch.object(C, "certify", side_effect=AssertionError("recertify")), \
                 patch.object(S, "acquire_task_closure", side_effect=AssertionError("direct acquire")):
                row = S.solve_from_store(task, book, verify_lengths=(3,), answer_lengths=(8,))
        self.assertTrue(row["reused"])
        self.assertFalse(row["acquired_again"])
        self.assertEqual(row["cost"]["proof_calls"], 0)
        self.assertTrue(row["all_checks_agree"])

    def test_lookup_is_first_in_normal_q_route(self):
        with patch.object(F, "fold_system", side_effect=AssertionError("acquisition")):
            trace, _ = S.solve(T.displacement_task(name="renamed"), route="q-directed",
                               ledger=self.book(), verify_lengths=(2,), answer_lengths=(5,))
        self.assertTrue(trace["reused"])
        self.assertEqual(trace["costs"]["acquisition"]["prover_calls"], 0)
        self.assertIn("stored certificate: all_finite_words", S.render(trace))
        self.assertNotIn("exact=None", S.render(trace))

    def test_another_readout_inside_the_space_uses_stored_matrices(self):
        q = 3*F.VARIABLES[0]/2
        task = replace(self.task, observable_expression=q,
                       value=lambda s: sp.Rational(3, 2)*s[0], name="different quantity")
        row = S.solve_from_store(task, self.book(), verify_lengths=(4,), answer_lengths=(6,))
        self.assertTrue(row["reused"])
        self.assertTrue(row["all_checks_agree"])
        self.assertNotEqual(row["readout"], self.cert["readout"])

    def test_same_name_different_contract_must_not_reuse(self):
        changed = [replace(self.task, alphabet=("A", "C")),
                   replace(self.task, coefficient_field="GF(7)"),
                   replace(self.task, step=lambda s, g: s),
                   replace(self.task, observable_expression=F.VARIABLES[1]),
                   replace(self.task, required_observables=(F.VARIABLES[1],)),
                   replace(self.task, legal_always=False, legal_step=lambda s, g: g != "T"),
                   replace(self.task, goal_from_state=lambda s: s[1] == 0),
                   replace(self.task, counted="end states")]
        changed.append(replace(self.task, value=lambda s: s[1]))
        for task in changed:
            self.assertFalse(S.solve_from_store(task, self.book(), answer_lengths=(4,))["reused"])

    def test_invalid_initial_frame_is_outside_proof_domain(self):
        task = replace(self.task, seed_state=(0,)*12)
        self.assertFalse(S.solve_from_store(task, self.book(), answer_lengths=(4,))["reused"])

    def test_certificate_bound_blocks_longer_n_and_new_start(self):
        cert = deepcopy(self.cert)
        cert["coverage"].update(kind="bounded_from_seed", maximum_length=2)
        R.ensure_scope(cert, self.task, 2)
        with self.assertRaises(ValueError):
            B.represented_rung(F.closure_from_record(self.record), cert, self.task, 3)
        with self.assertRaises(ValueError):
            R.ensure_scope(cert, T.displacement_task(start_word="A"), 1)

    def test_old_task_name_only_certificate_is_not_used(self):
        book = self.book()
        next(iter(book.entries.values()))["certificates"][0].pop("reuse_key")
        self.assertFalse(S.solve_from_store(self.task, book)["reused"])

    def test_certificate_cannot_be_attached_to_different_matrices(self):
        book = self.book()
        next(iter(book.entries.values()))["representation"]["action_matrices"]["A"][0][0] = "2"
        self.assertFalse(S.solve_from_store(self.task, book)["reused"])

    def test_an_unbound_action_cannot_obtain_a_proved_certificate(self):
        task = replace(self.task, step=lambda state, symbol: state)
        cert = C.certify(self.record, task, depth=2, premise=self.premise)
        self.assertFalse(cert["admissible"])
        self.assertIn("transition", cert["refused_by"])


if __name__ == "__main__":
    unittest.main()
