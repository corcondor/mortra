"""Artificial boundary cases, not autonomous mathematical acquisitions."""
from copy import deepcopy
from unittest.mock import patch
import unittest

from test_theory_dsl import config
from test_theory_semantic_edit import define, call
from math_os_prototype import library_compression as lib
from math_os_prototype.theory_domain import term
from math_os_prototype.theory_formation import Theory
from math_os_prototype.temporal_utility import OBJECTIVES
from math_os_prototype.representation_progress import digest


def engine(**options):
    return Theory(config(), corpus_refresh=True, semantic_edits=True,
                  temporal_options=dict(active_capacity=1, shadow_interval=2,
                    search_interval=100, experiences=100, **options))


class TemporalTests(unittest.TestCase):
    def test_old_future_equations_cannot_leak_into_frozen_window(self):
        from math_os_prototype.theory_semantic_edit import discover
        e = engine()
        v, t = e.vocabulary, e.vocabulary.temporal
        d = define(e, term("neg", term("neg", lib.program_hole(0))))
        t.sync()
        p = call(d, term("var", name="x"))
        expected = v.evaluate(p)[0]
        v.state["semantic_relations"].extend(discover(v, d)["relations"])
        cold = t.execute(p, t.choose("all"), expected, relation_ids=[])
        current = t.execute(p, t.choose("all"), expected)
        self.assertFalse(cold["semantic_edits"])
        self.assertTrue(current["semantic_edits"])
        self.assertTrue(cold["solved"] and current["solved"])

    def test_inactive_archive_can_become_active_without_new_acquisition(self):
        e = engine()
        t = e.vocabulary.temporal
        define(e, term("neg", lib.program_hole(0)))
        define(e, term("add", lib.program_hole(0), lib.program_hole(0)))
        t.sync()
        active = t.state["active"][0]
        other = next(k for k in t.state["entries"] if k != active)
        for k in (active, other):
            t.state["entries"][k]["future"] = [dict.fromkeys(OBJECTIVES, 0)]
        t.state["entries"][other]["future"][0]["description_gain"] = 1
        t.reconsider()
        self.assertEqual(t.state["active"], [other])
        self.assertIn(active, t.state["entries"])

    def test_no_use_baseline_can_dominate_bad_measured_operation(self):
        e = engine()
        t = e.vocabulary.temporal
        define(e, term("neg", lib.program_hole(0)))
        t.sync()
        key = t.state["active"][0]
        row = dict.fromkeys(OBJECTIVES, None)
        row.update(description_gain=0, matching_gain=-1)
        t.state["entries"][key]["future"] = [row]
        t.reconsider()
        self.assertEqual(t.state["active"], [])
        self.assertIn(key, t.state["entries"])

    def test_common_producer_is_not_changed_by_observation(self):
        a = Theory(config(), corpus_refresh=True, semantic_edits=True)
        b = engine()
        a.run(cycles=15)
        b.run(cycles=15)
        self.assertEqual(a.state["dsl"]["seen_programs"], b.state["dsl"]["seen_programs"])
        self.assertEqual([d["id"] for d in a.state["dsl"]["definitions"]],
                         [d["id"] for d in b.state["dsl"]["definitions"]])

    def test_causal_split_and_inactive_probe(self):
        e = engine()
        v, t = e.vocabulary, e.vocabulary.temporal
        x = term("var", name="x")
        d = define(e, term("neg", lib.program_hole(0)))
        t.sync()
        k = "definition:"+d["id"]
        self.assertEqual(t.state["entries"][k]["acquired_after"], v.state["experience_count"])
        with self.assertRaises(ValueError):
            t.add_future(k, v.state["experience_count"], "any", "c", {}, {})
        start = v.state["experience_count"]
        for i in range(4):
            p = term("add", x, term("const", value=str(i+3)))
            v.record(p, p)
        self.assertGreater(t.state["sequence"], start)
        self.assertTrue(t.state["future_evidence"])
        for row in t.state["future_evidence"]:
            self.assertGreater(row["sequence"], row["acquired_after"])
            self.assertNotIn(row["source"], t.state["entries"][row["operation"]]["acquisition_sample"])
        before = deepcopy(t.state)
        v.record(p, p)
        self.assertEqual(t.state, before)

    def test_pareto_does_not_scalarize_or_fill_missing(self):
        e = engine()
        t = e.vocabulary.temporal
        for body in (term("neg", lib.program_hole(0)), term("add", lib.program_hole(0), lib.program_hole(0))):
            define(e, body)
        t.sync()
        a, b = list(t.state["entries"].values())
        a["future"] = [dict.fromkeys(OBJECTIVES, 0)]
        b["future"] = [dict.fromkeys(OBJECTIVES, 0)]
        a["future"][0]["description_gain"] = 9
        b["future"][0]["description_gain"] = 10
        b["future"][0]["search_gain"] = 2
        self.assertEqual(t.choose("temporal"), [b["key"]])
        a["future"][0]["search_gain"] = 3
        self.assertIn(t.choose("temporal")[0], [a["key"], b["key"]])
        b["future"] = []
        self.assertTrue(all(v is None for v in t.vector(b).values()))

    def test_semantics_preserved_when_dependency_inactive(self):
        e = engine()
        v, t = e.vocabulary, e.vocabulary.temporal
        d = define(e, term("neg", lib.program_hole(0)))
        h = define(e, call(d, call(d, lib.program_hole(0))))
        t.sync()
        keys = t.choose("all")
        disabled = t.disabled_closure(keys, ["definition:"+d["id"]])
        self.assertNotIn("definition:"+h["id"], disabled)
        p = call(h, term("var", name="x"))
        expected = v.evaluate(p)[0]
        result = t.execute(p, disabled, expected)
        self.assertTrue(result["solved"])
        self.assertFalse(result["used"])
        self.assertTrue(v.state["definitions"])

    def test_registered_bodies_cannot_mutate(self):
        e = engine()
        d = define(e, term("neg", lib.program_hole(0)))
        e.vocabulary.temporal.sync()
        d["template"] = term("const", value="1")
        with self.assertRaisesRegex(ValueError, "changed"):
            e.vocabulary.temporal.sync()

    def test_restore_cursor_and_selection(self):
        e = engine()
        define(e, term("neg", lib.program_hole(0)))
        e.vocabulary.temporal.sync()
        restored = Theory(config(), **e.flags, state=e.snapshot())
        self.assertEqual(restored.vocabulary.temporal.state, e.vocabulary.temporal.state)
        self.assertEqual(restored.vocabulary.temporal.choose("temporal"), e.vocabulary.temporal.choose("temporal"))
        with self.assertRaises(ValueError):
            Theory(config(), corpus_refresh=True, semantic_edits=True,
                   temporal_options={"active_capacity": 2}, state=e.snapshot())

    def test_external_queries_cannot_update_selection(self):
        e = engine()
        x = term("var", name="x")
        d = define(e, term("neg", lib.program_hole(0)))
        e.vocabulary.temporal.sync()
        task = {"id": "development-only", "scope": e.domain.scope,
                "values": list(map(str, e.domain.evaluate(term("neg", x)))),
                "budget": {"states": 40, "depth": 8, "program_size": 100, "expanded_size": 100, "work": 10000}}
        before = digest(e.state)
        r = e.vocabulary.solve_observation(task, operation_keys=[], execution_mode="edited")
        self.assertTrue(r["solved"])
        self.assertFalse(any(s.startswith("definition:") for s in r["enabled_operations"]))
        self.assertEqual(digest(e.state), before)
        task["requirements"] = {"collision_free": True}
        with self.assertRaises(ValueError):
            e.vocabulary.solve_observation(task, operation_keys=["definition:"+d["id"]])

    def test_representation_recurrence_lowering_and_measurement(self):
        e = engine()
        x = term("var", name="x")
        cid = e.add_concept(term("neg", x), [])
        e.acquire(cid)
        rid = next(iter(e.state["representations"]))
        e.derive(rid, "a")
        t, v = e.vocabulary.temporal, e.vocabulary
        pid = next(iter(e.state["procedures"]))
        for p in (term("represented", term("word", letters=["a", "b"]), binding=rid),
                  term("recurrence", term("natural", value=7), procedure=pid)):
            expected = v.evaluate(p)[0]
            yes, no = t.execute(p, t.choose("all"), expected), t.execute(p, [], expected)
            self.assertTrue(yes["solved"] and no["solved"])
            self.assertFalse(no["used"])
        self.assertNotIn("recurrence:"+pid, t.disabled_closure(t.choose("all"), ["representation:"+rid]))

    def test_unchanged_input_does_not_reselect_and_budget_stops(self):
        e = engine()
        t, v = e.vocabulary.temporal, e.vocabulary
        t.reconsider()
        before = t.state["version"]
        t.reconsider()
        self.assertEqual(t.state["version"], before)
        p = term("var", name="x")
        t.observe(p, p, 101)
        self.assertIn("experience_budget", t.state["exhausted"])
        self.assertLessEqual(t.state["sequence"], 100)


if __name__ == "__main__":
    unittest.main()
