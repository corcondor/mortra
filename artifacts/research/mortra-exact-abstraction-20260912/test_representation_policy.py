"""Tests for the certificate, the ledger, the selection policy and the search.

What is asserted here is the shape of the machinery and the direction of each
gate -- that a refusal refuses, that an admission is labelled with what kind of
admission it is, that nothing is collapsed into a score, that nothing is deleted,
and that the search selects from what it measured rather than from anything
written into the test. Discovery statistics are never asserted as results.
"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sympy as sp

from math_os_prototype import fold_observable_system as F
from math_os_prototype import fold_tasks
from math_os_prototype import representation_benchmarks as B
from math_os_prototype import representation_certificate as C
from math_os_prototype import representation_evaluation as E
from math_os_prototype import representation_ledger as L
from math_os_prototype import representation_policy as P
from math_os_prototype import self_directed_search as S


def closure_record(observable=None):
    system = F.fold_system()
    found = F.acquire_closure(system, observable or F.VARIABLES[0],
                              maximum_dimension=64)
    return {"observable": found["observable"], "basis": found["basis"],
            "action_matrices": found["action_matrices"],
            "dimension": found["dimension"],
            "identity_residuals_all_zero": found["identity_residuals_all_zero"],
            "closure_scope": found["scope"]}


class CertificateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record = closure_record()
        cls.task = fold_tasks.displacement_task(axis=0)

    def test_all_four_things_are_checked_and_named(self):
        verdict = C.certify(self.record, self.task, depth=4)
        self.assertEqual([check["name"] for check in verdict["checks"]],
                         ["transition", "observable", "legality", "goal",
                          "start"])

    def test_an_admission_says_which_kind_of_admission_it_is(self):
        verdict = C.certify(self.record, self.task, depth=4)
        self.assertTrue(verdict["admissible"])
        self.assertEqual(verdict["verdict"], "admitted, proved")
        for check in verdict["checks"]:
            self.assertIn(check["kind"], ("proof", "structural",
                                          "no counterexample within depth"))

    def test_an_observable_outside_the_span_is_refused_by_decision(self):
        other = closure_record(F.VARIABLES[1])          # the closure of c2
        verdict = C.certify(other, self.task, depth=4)  # asked about c1
        self.assertFalse(verdict["admissible"])
        self.assertEqual(verdict["refused_by"], ["observable"])
        observable = next(c for c in verdict["checks"] if c["name"] == "observable")
        self.assertEqual(observable["kind"], "refusal")
        self.assertIn("rank", observable["scope"])

    def test_a_path_constraint_is_refused_with_a_counterexample(self):
        constrained = fold_tasks.displacement_task(axis=0, collision_free=True)
        verdict = C.certify(self.record, constrained, depth=4)
        self.assertFalse(verdict["admissible"])
        self.assertEqual(verdict["refused_by"], ["legality"])
        witness = next(c for c in verdict["checks"]
                       if c["name"] == "legality")["counterexample"]
        self.assertNotEqual(witness["word_a"], witness["word_b"])
        self.assertNotEqual(witness["value_a"], witness["value_b"])
        self.assertEqual(witness["observation"], witness["observation"])

    def test_that_counterexample_is_a_real_pair_of_words(self):
        """The witness is re-run here rather than trusted from the record."""
        constrained = fold_tasks.displacement_task(axis=0, collision_free=True)
        verdict = C.certify(self.record, constrained, depth=4)
        witness = next(c for c in verdict["checks"]
                       if c["name"] == "legality")["counterexample"]
        closure = F.closure_from_record(self.record)
        observe = C.compiled_observation(closure)
        left = observe(fold_tasks.run_word(witness["word_a"]))
        right = observe(fold_tasks.run_word(witness["word_b"]))
        self.assertEqual(left, right, "the two words really do share Phi")
        self.assertEqual(len(witness["word_a"]), len(witness["word_b"]),
                         "and the pair lives inside one layer, which is the "
                         "only place the DP ever merges")
        label = witness["label"]
        self.assertNotEqual(
            constrained.legal_word(witness["word_a"] + label),
            constrained.legal_word(witness["word_b"] + label),
            "and the named label really does differ in legality")

    def test_a_refused_representation_is_not_used_at_all(self):
        constrained = fold_tasks.displacement_task(axis=0, collision_free=True)
        verdict = C.certify(self.record, constrained, depth=4)
        record = B.fold_search_comparison("s", self.record, {}, task=constrained,
                                          length=4, certificate=verdict)
        self.assertTrue(record["refused"])
        self.assertNotIn("primitive_reduction", record,
                         "nothing was measured, because nothing was run")
        self.assertIsNotNone(record["counterexample"])


class AttributionTests(unittest.TestCase):
    @staticmethod
    def rung(primitive, wall, nodes=None):
        return {"primitive_calls": primitive, "derivative_calls": 0,
                "fold_step_calls": primitive, "search_nodes": nodes,
                "wall_time": wall}

    def test_the_four_causes_are_marginal_steps_that_add_to_the_total(self):
        found = E.attribute({
            "naive": self.rung(1000, 1.0, 1000),
            "memoised": self.rung(900, 0.9, 900),
            "mathematical": self.rung(500, 0.5, 500),
            "generic_search": self.rung(200, 0.2, 200),
            "representation": self.rung(50, 0.1, 50)})
        self.assertEqual(found["memoisation_reduction"]["primitive_calls"], 100)
        self.assertEqual(found["mathematical_reduction"]["primitive_calls"], 400)
        self.assertEqual(found["generic_search_reduction"]["primitive_calls"], 300)
        self.assertEqual(found["representation_reduction"]["primitive_calls"], 150)
        self.assertEqual(found["total"]["primitive_calls"], 950)
        self.assertTrue(found["marginals_add_up_to_total"]["primitive_calls"])

    def test_an_absent_rung_is_absent_rather_than_zero(self):
        found = E.attribute({"naive": self.rung(100, 1.0),
                             "representation": self.rung(10, 0.1)})
        self.assertIsNone(found["mathematical_reduction"])
        self.assertIsNone(found["generic_search_reduction"])
        self.assertIn("mathematical", found["rungs_absent"])
        self.assertEqual(found["representation_reduction"]["from_rung"], "naive")

    def test_the_representation_gets_credit_only_for_its_own_step(self):
        """Where an existing route already saves it, the column is small."""
        found = E.attribute({"naive": self.rung(1000, 1.0),
                             "mathematical": self.rung(60, 0.1),
                             "representation": self.rung(50, 0.09)})
        self.assertEqual(found["mathematical_reduction"]["primitive_calls"], 940)
        self.assertEqual(found["representation_reduction"]["primitive_calls"], 10)

    def test_a_ladder_without_a_naive_rung_is_refused(self):
        with self.assertRaises(ValueError):
            E.attribute({"representation": self.rung(1, 0.1)})


class BreakEvenTests(unittest.TestCase):
    def test_the_three_are_separate_and_the_joint_stays_on_one_target(self):
        found = E.break_evens(acquisition_primitive_calls=100,
                              representation_bits=1000, bits_saved_per_task=60,
                              saving_against_naive=50,
                              saving_against_best_baseline=10,
                              best_baseline_rung="mathematical")
        self.assertEqual(found["compute_break_even_reuse_count"], 2)
        self.assertEqual(
            found["compute_break_even_reuse_count_against_best_baseline"], 10)
        self.assertEqual(found["description_break_even_task_count"], 17)
        self.assertEqual(found["joint_break_even_against_naive"], 17)
        self.assertEqual(found["joint_break_even_against_best_baseline"], 17)

    def test_the_joint_uses_the_compute_figure_when_that_is_the_later_one(self):
        """compute(best)=168 with description=10 gives a joint of 168."""
        found = E.break_evens(acquisition_primitive_calls=669,
                              representation_bits=3448,
                              bits_saved_per_task=376,
                              saving_against_naive=192,
                              saving_against_best_baseline=4,
                              best_baseline_rung="mathematical")
        self.assertEqual(
            found["compute_break_even_reuse_count_against_best_baseline"], 168)
        self.assertEqual(found["description_break_even_task_count"], 10)
        self.assertEqual(found["joint_break_even_against_best_baseline"], 168)
        self.assertEqual(found["joint_break_even_against_naive"], 10,
                         "the naive joint is a different target and is not "
                         "mixed with the best-baseline one")

    def test_a_none_carries_a_reason_and_is_not_a_claim_about_the_future(self):
        found = E.break_evens(acquisition_primitive_calls=100,
                              representation_bits=10, bits_saved_per_task=5,
                              saving_against_naive=50,
                              saving_against_best_baseline=-39,
                              best_baseline_rung="mathematical")
        self.assertIsNone(
            found["compute_break_even_reuse_count_against_best_baseline"])
        reason = found["reasons"]["compute_vs_best"]
        self.assertIn("no crossing under the present steady-state model", reason)
        self.assertIn("does not establish that it never repays", reason)

    def test_no_saving_against_the_best_baseline_reports_none(self):
        found = E.break_evens(acquisition_primitive_calls=100,
                              representation_bits=10, bits_saved_per_task=5,
                              saving_against_naive=50,
                              saving_against_best_baseline=0)
        self.assertEqual(found["compute_break_even_reuse_count"], 2)
        self.assertIsNone(
            found["compute_break_even_reuse_count_against_best_baseline"])
        self.assertIn("exactly zero", found["reasons"]["compute_vs_best"])


class ProvenanceTests(unittest.TestCase):
    def test_the_nodes_that_disappeared_are_named_not_just_counted(self):
        before = E.measure(lambda: B.kinematic_fold_run("GCCGCC"))
        after = E.measure(lambda: {"value": "0"})
        found = E.eliminated_nodes(before, after)
        self.assertEqual(found["nodes_removed"], 6)
        self.assertTrue(found["complete"])
        keys = list(found["removed"])
        self.assertTrue(all(k.startswith("fold_step:apply_fold_generator:")
                            for k in keys))
        self.assertEqual(sum(e["removed"] for e in found["removed"].values()), 6)

    def test_a_node_that_appears_only_afterwards_is_reported_as_added(self):
        before = E.measure(lambda: {"value": 1})
        after = E.measure(lambda: B.kinematic_fold_run("AC"))
        found = E.eliminated_nodes(before, after)
        self.assertEqual(found["nodes_removed"], 0)
        self.assertEqual(found["nodes_added"], 2)


class LedgerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record = closure_record()
        cls.task = fold_tasks.displacement_task(axis=0)
        cls.certificate = C.certify(cls.record, cls.task, depth=4)
        cls.evaluation = B.fold_search_comparison(
            "probe", cls.record, {"acquisition_primitive_calls": 100},
            task=cls.task, length=4, certificate=cls.certificate)
        cls.representation = {"kind": "observation representation",
                              "observable": cls.record["observable"],
                              "basis": cls.record["basis"],
                              "dimension": cls.record["dimension"],
                              "action_matrices": cls.record["action_matrices"]}

    def _book(self):
        book = L.Ledger()
        book.observe(self.representation, self.evaluation,
                     certificate=self.certificate,
                     acquisition={"acquisition_primitive_calls": 100})
        return book

    def test_the_nine_components_are_kept_and_kept_apart(self):
        book = self._book()
        entry = list(book.entries.values())[0]
        measurement = entry["measurements"][0]
        for component in ("description_gain_bits", "state_dimension_reduction",
                          "primitive_elimination", "search_reduction",
                          "sequential_depth_reduction", "measured_wall_time",
                          "certificate_scope", "break_evens", "provenance",
                          "attribution"):
            self.assertIn(component, measurement)
        self.assertIn("acquisition_cost", entry)
        self.assertIn("count", entry["reuse"])

    def test_the_certificate_scope_says_which_kind_of_admission_it_was(self):
        book = self._book()
        scope = list(book.entries.values())[0]["measurements"][0]["certificate_scope"]
        kinds = {check["name"]: check["kind"] for check in scope["checks"]}
        self.assertEqual(kinds["observable"], "proof")
        self.assertEqual(kinds["legality"], "proof")
        self.assertTrue(scope["admissible"])

    def test_provenance_is_kept_against_the_best_baseline_as_well(self):
        book = self._book()
        provenance = list(book.entries.values())[0]["measurements"][0]["provenance"]
        self.assertIn("against_naive", provenance)
        self.assertIn("against_best_baseline", provenance)
        self.assertGreaterEqual(provenance["against_naive"]["nodes_removed"],
                                provenance["against_best_baseline"]["nodes_removed"])

    def test_there_is_no_score_anywhere_in_an_entry(self):
        book = self._book()
        text = str(book.state())
        for forbidden in ("'score'", "'utility'", "'total_score'"):
            self.assertNotIn(forbidden, text)

    def test_going_unused_makes_an_entry_dormant_and_never_removes_it(self):
        book = self._book()
        identifier = list(book.entries)[0]
        for _ in range(9):
            book.advance(idle_cycles=8)
        entry = book.entries[identifier]
        self.assertEqual(entry["status"], "dormant")
        self.assertFalse(entry["deleted"])
        self.assertIn("never deleted", entry["deletion_policy"])
        self.assertTrue(entry["measurements"], "the measurements are still there")

    def test_using_it_again_wakes_it_up(self):
        book = self._book()
        for _ in range(9):
            book.advance(idle_cycles=8)
        book.observe(self.representation, self.evaluation)
        entry = list(book.entries.values())[0]
        self.assertEqual(entry["status"], "active")
        self.assertIsNone(entry["dormant_since"])
        self.assertEqual(len(entry["measurements"]), 2)

    def test_a_refusal_is_kept_too_because_it_says_where_not_to_use_it(self):
        book = L.Ledger()
        constrained = fold_tasks.displacement_task(axis=0, collision_free=True)
        refusal = C.certify(self.record, constrained, depth=4)
        book.note_certificate(self.representation, refusal)
        entry = list(book.entries.values())[0]
        self.assertEqual(entry["certificates"][0]["refused_by"], ["legality"])
        self.assertEqual(book.admissible_for(constrained.name), [])

    def test_the_state_round_trips_and_a_tampered_one_is_refused(self):
        book = self._book()
        state = book.state()
        restored = L.Ledger.restore(state)
        self.assertEqual(restored.entries, book.entries)
        state["cycle"] = 999
        with self.assertRaises(ValueError):
            L.Ledger.restore(state)


class PolicyTests(unittest.TestCase):
    @staticmethod
    def entry(identifier, **objectives):
        measurement = {
            "task": "t",
            "description_gain_bits": objectives.get("bits", 0),
            "state_dimension_reduction": {"before": 12, "after": 4,
                                          "difference": 8,
                                          "ratio": objectives.get("state", 3.0)},
            "primitive_elimination": {"before": objectives.get("prim_before", 100),
                                      "after": 0, "eliminated": {},
                                      "derivative_calls_before": 0,
                                      "derivative_calls_after": 0,
                                      "derivative_request_calls_before": 0,
                                      "derivative_request_calls_after": 0},
            "search_reduction": {"candidates_before": 100, "candidates_after": 1,
                                 "nodes_before": objectives.get("nodes", 100),
                                 "nodes_after": 1,
                                 "rejected_before": 0, "rejected_after": 0,
                                 "units": ""},
            "sequential_depth_reduction": {"before": 10, "after": 10,
                                           "ratio": 1.0,
                                           "not_a_success_condition": ""},
            "measured_wall_time": {"before": 1.0, "after": 0.5, "saved": 0.5},
            "attribution": None, "break_evens": {}, "provenance": {}}
        return {"id": identifier, "kind": "observation representation",
                "representation": {"observable": identifier, "dimension": 4},
                "measurements": [measurement],
                "acquisition_cost": {"acquisition_primitive_calls":
                                     objectives.get("cost", 10)},
                "certificates": [{"task": "t", "admissible":
                                  objectives.get("admissible", True),
                                  "refused_by": objectives.get("refused_by", [])}],
                "reuse": {"count": 1, "successes": objectives.get("uses", 1),
                          "failures": 0, "heldout_successes": 0, "tasks": ["t"],
                          "last_used_cycle": 0},
                "status": objectives.get("status", "active"),
                "dormant_since": None, "deleted": False, "deletion_policy": ""}

    def test_a_representation_that_loses_on_bits_but_wins_on_search_survives(self):
        """The case the request names: do not discard it for the bits alone."""
        compressor = self.entry("compressor", bits=5000, nodes=100)
        searcher = self.entry("searcher", bits=-3000, nodes=100000)
        result = P.select([compressor, searcher], task="t")
        chosen = {row["observable"]: row["front"] for row in result["selected"]}
        self.assertEqual(chosen["compressor"], 1)
        self.assertEqual(chosen["searcher"], 1,
                         "neither beats the other on every component, so both "
                         "are on the first front")

    def test_something_beaten_on_everything_falls_to_a_later_front(self):
        strong = self.entry("strong", bits=100, nodes=1000, prim_before=1000,
                            cost=1, uses=5)
        weak = self.entry("weak", bits=10, nodes=100, prim_before=100,
                          cost=50, uses=1)
        result = P.select([strong, weak], task="t")
        fronts = {row["observable"]: row["front"] for row in result["selected"]}
        self.assertEqual(fronts["strong"], 1)
        self.assertEqual(fronts["weak"], 2)

    def test_a_component_neither_measured_is_skipped_not_counted_as_a_tie(self):
        left = {"description_gain_bits": 10, "search_nodes_eliminated": None}
        right = {"description_gain_bits": 5, "search_nodes_eliminated": 10_000}
        self.assertTrue(P.dominates(left, right),
                        "only the comparable components decide")
        self.assertFalse(P.dominates(right, left))

    def test_a_representation_without_an_admitting_certificate_is_not_offered(self):
        good = self.entry("good")
        bad = self.entry("bad", admissible=False, refused_by=["legality"])
        result = P.select([good, bad], task="t")
        self.assertEqual([row["observable"] for row in result["selected"]],
                         ["good"])
        self.assertEqual(result["not_admissible"][0]["id"], "bad")
        self.assertIn("legality", result["not_admissible"][0]["reason"])

    def test_dormancy_moves_within_a_front_and_does_not_change_the_front(self):
        active = self.entry("active", bits=10, nodes=100)
        sleepy = self.entry("sleepy", bits=-10, nodes=100000, status="dormant")
        result = P.select([active, sleepy], task="t")
        rows = result["selected"]
        self.assertEqual([row["front"] for row in rows], [1, 1])
        self.assertEqual(rows[-1]["observable"], "sleepy")
        self.assertEqual(rows[-1]["status"], "dormant")

    def test_the_order_names_itself_as_a_frontier_and_not_a_total(self):
        result = P.select([self.entry("a")], task="t")
        self.assertIn("Pareto", result["order"])
        self.assertIn("no total", result["order"])


class SelfDirectedSearchTests(unittest.TestCase):
    """One task, handed in, worked through with nothing picked by hand."""

    @classmethod
    def setUpClass(cls):
        cls.task = fold_tasks.displacement_task(axis=0)
        cls.trace, cls.book = S.solve(cls.task, degree=1, probe_length=4,
                                      verify_lengths=(4, 5, 6),
                                      answer_lengths=(9,),
                                      certificate_depth=3)

    def test_the_premise_was_re_proved_rather_than_assumed(self):
        self.assertTrue(self.trace["premise"]["exact"])
        self.assertEqual(self.trace["premise"]["identities_checked"],
                         self.trace["premise"]["frames_checked"] * 4)

    def test_the_candidates_came_off_the_grammar_and_were_not_supplied(self):
        offered = self.trace["candidates_offered"]
        self.assertEqual(offered, list(F.VARIABLE_NAMES),
                         "degree one is exactly the state coordinates, in the "
                         "grammar's own order")
        self.assertGreater(len(offered), 1)

    def test_most_candidates_were_refused_so_the_gate_is_doing_work(self):
        refused = self.trace["refused_by_certificate"]
        self.assertGreater(len(refused), 0)
        self.assertTrue(all(row["refused_by"] for row in refused))
        self.assertLess(len(self.trace["admitted"]),
                        len(self.trace["candidates_offered"]))

    def test_the_choice_came_from_the_measurements_by_pareto_front(self):
        selection = self.trace["selection"]
        self.assertIn("Pareto", selection["order"])
        self.assertEqual(self.trace["selected"]["front"], 1)
        chosen = self.trace["selected"]["observable"]
        self.assertIn(chosen, self.trace["admitted"] + [S.EXISTING_ROUTE],
                      "either a learned representation or the existing exact "
                      "route; choosing the existing one is a correct run")

    def test_the_existing_exact_route_competed_for_the_task(self):
        names = {row["observable"] for row in self.trace["selection"]["offered"]}
        self.assertIn(S.EXISTING_ROUTE, names,
                      "it is a candidate, not only something to measure against")

    def test_the_tie_break_was_measured_over_the_declared_workload(self):
        found = self.trace["tie_break_workload"]
        self.assertEqual(found["lengths"],
                         [a["length"] for a in self.trace["answers"]])
        for name, row in found["measured"].items():
            self.assertIn("total_wall_time", row)
            self.assertIn("workload_nodes", row)
        self.assertIn("wall time", found["rule"])
        winner = self.trace["selected"]["observable"]
        best = min(found["measured"],
                   key=lambda n: found["measured"][n]["total_wall_time"])
        self.assertEqual(winner, best,
                         "the stated rule is the one that was applied")

    def test_where_the_units_disagree_that_is_recorded_not_settled_quietly(self):
        found = self.trace["tie_break_workload"]
        if found["units_disagree"]:
            self.assertIsNotNone(found["units_disagree_note"])
            self.assertNotEqual(found["order_by_wall_time"][0],
                                found["order_by_workload_nodes"][0])
        else:
            self.assertIsNone(found["units_disagree_note"])

    def test_the_answer_agrees_with_independent_enumeration_where_it_can(self):
        self.assertTrue(self.trace["all_checks_agree"])
        for check in self.trace["verification"]:
            self.assertEqual(check["by_enumeration"], check["by_representation"])
            self.assertTrue(check["distributions_agree"],
                            "the whole distribution matches, not only the total")
            self.assertEqual(check["by_enumeration"]["total_words"],
                             4 ** check["length"])

    def test_it_answers_where_enumeration_was_not_run(self):
        answer = self.trace["answers"][0]
        self.assertEqual(answer["answer"]["total_words"], 4 ** answer["length"])
        self.assertFalse(answer["enumerated"])
        self.assertLess(answer["search_nodes"], answer["words_this_stands_for"])
        self.assertIsNotNone(answer["answer"]["v_max"])
        self.assertGreater(answer["answer"]["count_max"], 0)

    def test_that_longer_answer_is_labelled_as_resting_on_the_certificate(self):
        self.assertIn("NOT enumerated", self.trace["scope"])
        self.assertTrue(
            "rest on the certificate" in self.trace["scope"]
            or "needs no certificate" in self.trace["scope"],
            "a learned route rests on its certificate; the existing exact route "
            "says why it needs none")

    def test_the_ledger_kept_every_candidate_it_looked_at(self):
        kept = len(self.book.entries)
        seen = (len(self.trace["span_classes"])
                + len(self.trace["refused_by_certificate"]))
        self.assertEqual(kept, seen,
                         "one entry per distinct space, plus every refusal with "
                         "its reason")

    def test_candidates_spanning_one_space_are_counted_as_one(self):
        classes = self.trace["span_classes"]
        self.assertLessEqual(len(classes), len(self.trace["admitted"]))
        self.assertEqual(sum(row["size"] for row in classes),
                         len(self.trace["admitted"]))

    def test_the_acquisition_cost_includes_the_candidates_it_rejected(self):
        cost = self.trace["acquisition_cost"]
        self.assertGreater(cost["candidates_refused_by_certificate"], 0)
        self.assertEqual(cost["candidates_enumerated"],
                         len(self.trace["candidates_offered"]))
        self.assertIn("pays for what it rejects", cost["includes"])

    def test_a_stored_representation_is_reused_without_acquiring_again(self):
        row = S.solve_from_store(self.task, self.book, verify_lengths=(),
                                 answer_lengths=(8,))
        self.assertTrue(row["reused"])
        self.assertFalse(row["acquired_again"])
        self.assertEqual(row["cost"]["proof_calls"], 0,
                         "no prover ran: the basis came out of the store")
        walked = fold_tasks.enumerate_answer(self.task, 8)["answer"]
        self.assertEqual(row["answers"][0]["answer"], walked)

    def test_a_task_it_cannot_serve_is_refused_rather_than_answered_wrongly(self):
        constrained = fold_tasks.displacement_task(axis=0, collision_free=True)
        trace, _ = S.solve(constrained, degree=1, probe_length=3,
                           verify_lengths=(3,), answer_lengths=(),
                           certificate_depth=3)
        self.assertIn("stopped", trace)
        self.assertEqual(trace["admitted"], [])
        self.assertTrue(all("legality" in row["refused_by"]
                            or "observable" in row["refused_by"]
                            for row in trace["refused_by_certificate"]))
        self.assertIn("this grammar", trace["stopping_point"]["exact"],
                      "the stopping point is scoped to what was searched")


if __name__ == "__main__":
    unittest.main()
