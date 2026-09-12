"""Handwritten fixtures for the session entry point; never discovery statistics.

What is asserted here is that the loop keeps what it acquired and stops for a
stated reason. Nothing here asserts that anything in particular is discovered.
"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from math_os_prototype.acquisition_report import holes_of, render, report
from math_os_prototype.acquisition_session import (
    DEFAULTS, Session, adopt_library, configure, corpus_from_history,
    definition_depths, proposer_state, restore_proposer, uses_in)


def hyper(a, b=()):
    return {"op": "hyper", "a": list(a), "b": list(b)}


BASE = {"seeds": [hyper([1])], "state_names": ["u", "v"],
        "parameter_names": ["c"],
        "max_seconds": 60, "max_traced_lines": 10_000_000, "max_cycles": 1}


class ConfigurationTests(unittest.TestCase):
    def test_every_cap_is_required(self):
        for cap in ("max_seconds", "max_traced_lines", "max_cycles"):
            with self.assertRaises(ValueError) as caught:
                configure(dict(BASE, **{cap: 0}))
            self.assertIn(cap, str(caught.exception))

    def test_a_session_needs_a_seed(self):
        with self.assertRaises(ValueError):
            configure(dict(BASE, seeds=[]))

    def test_an_unknown_key_is_refused_rather_than_ignored(self):
        with self.assertRaises(ValueError):
            configure(dict(BASE, cost_model="bytes"))

    def test_the_defaults_name_every_setting(self):
        self.assertEqual(set(configure(BASE)), set(DEFAULTS))


class CarriedStateTests(unittest.TestCase):
    """`Driver.state()` carries none of this, which is why the session does."""

    def setUp(self):
        self.config = configure(BASE)
        self.proposer = restore_proposer(self.config)

    def test_the_proposer_state_covers_what_the_driver_drops(self):
        payload = proposer_state(self.proposer)
        for field in ("candidates", "records", "acquisitions", "library",
                      "drafted", "enumerated_ids", "sweeps", "presentations"):
            self.assertIn(field, payload)

    def test_a_round_trip_keeps_the_queue_the_cursor_and_the_library(self):
        self.proposer._sweeps = 7
        self.proposer._drafted = {self.proposer._enumerated[0]["id"]}
        self.proposer.candidates = [{"id": "x", "kind": "relation"}]
        self.proposer.records = [{"features": []}]
        library = [{"index": 0, "id": "abc", "utility_bits": 10,
                    "template": {"op": "diff", "child": {"series_parameter": "f0"}}}]
        adopt_library(self.proposer, library)

        restored = restore_proposer(self.config, proposer_state(self.proposer))
        self.assertEqual(restored._sweeps, 7)
        self.assertEqual(restored._drafted, self.proposer._drafted)
        self.assertEqual(restored.candidates, [{"id": "x", "kind": "relation"}])
        self.assertEqual(len(restored.records), 1)
        self.assertEqual(len(restored.library), 1)
        self.assertEqual(restored.definitions["sha256"],
                         self.proposer.definitions["sha256"])

    def test_a_tampered_state_is_refused(self):
        payload = proposer_state(self.proposer)
        payload["sweeps"] = 99
        with self.assertRaises(ValueError):
            restore_proposer(self.config, payload)

    def test_adopting_a_library_does_not_rebuild_the_proposer(self):
        self.proposer.candidates = [{"id": "keep-me"}]
        self.proposer._sweeps = 3
        enumerated = list(self.proposer._enumerated)
        adopt_library(self.proposer, [
            {"index": 0, "id": "abc", "utility_bits": 4,
             "template": {"op": "diff", "child": {"series_parameter": "f0"}}}])
        self.assertEqual(self.proposer.candidates, [{"id": "keep-me"}])
        self.assertEqual(self.proposer._sweeps, 3)
        self.assertEqual(self.proposer._enumerated, enumerated)
        self.assertEqual(len(self.proposer.library), 1)
        self.assertEqual(self.proposer.jobs.versions["definitions"],
                         self.proposer.definitions["sha256"])


class StoppingTests(unittest.TestCase):
    def test_a_cap_always_produces_a_reason(self):
        session = Session(dict(BASE, max_cycles=1))
        self.assertIsNotNone(session.should_stop(0, 0) or "not yet")
        session.cycles = [{"accepted_count": 1, "compression_bits": 100,
                           "spent_lines": 0}]
        self.assertIn("cycle cap", session.should_stop(0, 0))
        self.assertIn("wall-clock", session.should_stop(10_000, 0))
        self.assertIn("compute cap", session.should_stop(0, 10 ** 12))

    def test_barren_cycles_are_a_setting_not_an_exhaustion_claim(self):
        session = Session(dict(BASE, max_cycles=99, barren_cycles=2,
                               min_compression_bits=5))
        session.cycles = [{"accepted_count": 0, "compression_bits": 0,
                           "spent_lines": 0}] * 2
        reason = session.should_stop(0, 0)
        self.assertIn("consecutive cycles", reason)
        self.assertIn("operational condition", session.state()["stop_note"])
        self.assertIn("not a proof", session.state()["stop_note"])

    def test_a_productive_cycle_resets_the_barren_count(self):
        session = Session(dict(BASE, max_cycles=99, barren_cycles=2))
        session.cycles = [{"accepted_count": 0, "compression_bits": 0, "spent_lines": 0},
                          {"accepted_count": 2, "compression_bits": 0, "spent_lines": 0},
                          {"accepted_count": 0, "compression_bits": 0, "spent_lines": 0}]
        self.assertIsNone(session.should_stop(0, 0))


class CorpusTests(unittest.TestCase):
    def test_the_corpus_is_what_the_run_produced_each_program_once(self):
        session = Session(BASE)
        session.proposer.records = [
            {"features": [{"program": hyper([1])}, {"program": hyper([2])}]},
            {"features": [{"program": hyper([1])}]}]
        corpus = corpus_from_history(session.driver, session.proposer)
        self.assertEqual(len(corpus), 2)
        self.assertTrue(all(entry["proved"] for entry in corpus))
        self.assertTrue(all("source" in entry for entry in corpus))


class ReportTests(unittest.TestCase):
    def test_a_definition_is_printed_as_a_term_with_its_arguments(self):
        template = {"op": "mul",
                    "left": {"op": "poly", "coefficients": [0, 1]},
                    "right": {"op": "diff", "child": {"series_parameter": "f0"}}}
        self.assertEqual(render(template), "(poly[0,1] * D(<f0>))")
        self.assertEqual(holes_of(template), ["f0"])

    def test_a_call_is_printed_with_what_it_expands_to(self):
        call = {"op": "use", "abstraction": 1,
                "arguments": {"f0": hyper([1])}}
        self.assertEqual(render(call), "H1(f0=hyper(1;))")

    def test_the_report_is_generated_from_the_saved_state_alone(self):
        session = Session(BASE)
        session.cycles = [{
            "cycle": 0, "allowance": 1, "seconds": 0.1, "spent_lines": 5,
            "sweeps": [{"sweep": 0, "attempted": ["a"], "attempted_kinds": ["relation"],
                        "accepted": "t0", "candidates_exhausted": False,
                        "undrafted": 3, "spent_lines": 5}],
            "accepted_count": 1, "corpus_programs": 2, "corpus_bits": 100,
            "compression_bits": 7,
            "library": [{"index": 0, "id": "abc", "utility_bits": 7,
                         "definition_bits": 3, "programs_touched": 2,
                         "template": {"op": "diff",
                                      "child": {"series_parameter": "f0"}}}],
            "learn_rounds": [], "follow_up_calls": [], "pending": ["p1"]}]
        session.stop_reason = "cycle cap reached (1)"
        text = report(session.state())
        for expected in ("a[relation]", "D(<f0>)", "['f0']", "+7 bits",
                         "cycle cap reached (1)", "GRAPH", "pending"):
            self.assertIn(expected, text)


class DependencyDepthTests(unittest.TestCase):
    """Depth is read off the bodies, with no name or id mentioned."""

    def test_a_body_of_primitives_is_depth_one(self):
        library = [{"index": 0, "template": {"op": "diff",
                                             "child": {"series_parameter": "f0"}}}]
        self.assertEqual(definition_depths(library), {0: 1})

    def test_each_learned_layer_adds_one(self):
        library = [
            {"index": 0, "template": {"op": "diff",
                                      "child": {"series_parameter": "f0"}}},
            {"index": 1, "template": {"op": "use", "abstraction": 0,
                                      "arguments": {"f0": {"series_parameter": "f0"}}}},
            {"index": 2, "template": {"op": "use", "abstraction": 1,
                                      "arguments": {"f0": {"series_parameter": "f0"}}}}]
        self.assertEqual(definition_depths(library), {0: 1, 1: 2, 2: 3})

    def test_a_reference_the_library_does_not_hold_adds_nothing(self):
        library = [{"index": 0, "template": {"op": "use", "abstraction": 7,
                                             "arguments": {}}}]
        self.assertEqual(definition_depths(library), {0: 1})

    def test_uses_in_finds_every_call_in_a_body(self):
        body = {"op": "add",
                "left": {"op": "use", "abstraction": 0, "arguments": {}},
                "right": {"op": "use", "abstraction": 3, "arguments": {}}}
        self.assertEqual(sorted(uses_in(body)), [0, 3])


class FairEnumerationTests(unittest.TestCase):
    """Every definition that still has a candidate is offered one first.

    Stated without naming a definition: the property is that no entry can be
    starved by another entry's product being large.
    """

    def setUp(self):
        from math_os_prototype import library_compression as L
        self.L = L
        # three definitions, the first with the widest product by far
        self.library = [
            {"index": 0, "template": {"op": "add",
                                      "left": {"series_parameter": "f0"},
                                      "right": {"series_parameter": "f1"}}},
            {"index": 1, "template": {"op": "diff",
                                      "child": {"series_parameter": "f0"}}},
            {"index": 2, "template": {"op": "scale", "factor": "2",
                                      "child": {"series_parameter": "f0"}}}]
        self.pool = [hyper([n]) for n in range(1, 7)]

    def test_no_definition_is_starved_by_another_ones_product(self):
        offered = self.L.call_candidates(self.library, self.pool, limit=9)
        reached = sorted({entry["definition"] for entry in offered})
        self.assertEqual(reached, [0, 1, 2])

    def test_one_offer_each_before_any_second_offer(self):
        offered = self.L.call_candidates(self.library, self.pool, limit=3)
        self.assertEqual([entry["definition"] for entry in offered], [0, 1, 2])

    def test_an_exhausted_definition_drops_out_without_blocking(self):
        library = self.library[:2] + [
            {"index": 9, "template": {"op": "poly", "coefficients": [1]}}]
        offered = self.L.call_candidates(library, self.pool, limit=6)
        # index 9 has no hole at all, so it offers nothing and the others continue
        self.assertEqual(sorted({e["definition"] for e in offered}), [0, 1])
        self.assertEqual(len(offered), 6)

    def test_deduplication_and_exclusion_still_mean_what_they_meant(self):
        from math_os_prototype.holonomic_route_discovery import key
        twice = self.library[1:2] + [dict(self.library[1], index=5)]
        offered = self.L.call_candidates(twice, self.pool, limit=12)
        expansions = [key(self.L.instantiate_term(
            next(e for e in twice if e["index"] == entry["definition"])["template"],
            entry["call"]["arguments"])) for entry in offered]
        self.assertEqual(len(expansions), len(set(expansions)))
        first = self.L.call_candidates(twice, self.pool, limit=1)
        again = self.L.call_candidates(
            twice, self.pool, limit=12,
            exclude=[key(self.L.instantiate_term(twice[0]["template"],
                                                 first[0]["call"]["arguments"]))])
        self.assertNotIn(first[0]["id"], [entry["id"] for entry in again])


class ElapsedTimeTests(unittest.TestCase):
    """The cap counts compute, not the time a saved session sat on disk."""

    def test_a_fresh_session_starts_from_zero(self):
        self.assertEqual(Session(BASE).elapsed_seconds, 0.0)

    def test_the_state_carries_accumulated_seconds_not_a_timestamp(self):
        session = Session(BASE)
        session.elapsed_seconds = 12.5
        state = session.state()
        self.assertEqual(state["elapsed_seconds"], 12.5)
        self.assertNotIn("started", state)

    def test_a_restored_session_resumes_from_the_accumulated_value(self):
        session = Session(dict(BASE, max_cycles=99))
        session.elapsed_seconds = 7.0
        restored = Session.restore(session.state())
        self.assertEqual(restored.elapsed_seconds, 7.0)
        # and the cap is judged against that, not against how long ago it ran
        self.assertIsNone(restored.should_stop(7.0, 0))
        self.assertIn("wall-clock", restored.should_stop(10_000, 0))


if __name__ == "__main__":
    unittest.main()
