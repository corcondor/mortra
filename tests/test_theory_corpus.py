"""Development fixtures for evidence retention and bounded learning views."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from test_theory_dsl import config
from math_os_prototype.theory_domain import term
from math_os_prototype.theory_formation import Theory
from math_os_prototype import library_compression as lib
from math_os_prototype.theory_vocabulary import context_operations


def small(refresh=True):
    c = config()
    c["budget"].update(library_corpus=4, library_interval=2)
    return Theory(c, corpus_refresh=refresh)


def record(e, n):
    p = term("const", value=str(n))
    e.vocabulary.record(p, p, evaluated=e.domain.evaluate(p))


class CandidateSourceBudget(unittest.TestCase):
    """Handwritten structural fixtures, not a source of runtime definitions."""

    def test_source_count_is_an_upper_bound_for_every_small_generalisation(self):
        e = small()
        atoms = [term("var", name="x"), term("const", value="2"), term("const", value="3")]
        terms = atoms + [term(op, a) for op in ("neg",) for a in atoms]
        terms += [term("add", a, b) for a in terms[:6] for b in terms[:6]]
        # Fixed definition references and shared arguments participate as syntax.
        terms += [lib.use_node(0, lib.program_hole(0), {"f0": a}) for a in terms[:6]]
        with lib.grammar(e.vocabulary.accepts):
            checked = 0
            for a in terms:
                for b in terms:
                    try:
                        template, _ = lib.generalise(a, b)
                    except (ValueError, TypeError, KeyError):
                        continue
                    checked += 1
                    self.assertLessEqual(context_operations(template),
                                         min(context_operations(a), context_operations(b)))
            self.assertGreater(checked, 100)

    def test_exhaustive_admissible_set_is_preserved_and_occurrences_not_removed(self):
        e = small()
        programs = [term("neg", term("neg", term("const", value=str(n)))) for n in range(4)]
        corpus = [{"id": str(i), "program": p} for i, p in enumerate(programs*2)]
        original = deepcopy(corpus)
        with lib.grammar(e.vocabulary.accepts):
            old = lib.candidates(corpus, pairs=10000)
            new = lib.candidates(corpus, pairs=10000, source_filter=lambda t: context_operations(t) >= 2,
                                 deduplicate_sources=True)
            admissible = lambda rows: {lib.key(r["template"]) for r in rows["candidates"]
                                       if context_operations(r["template"]) >= 2}
            self.assertEqual(admissible(old), admissible(new))
            self.assertTrue(admissible(new))
            self.assertLess(new["pairs_tried"], old["pairs_tried"])
            self.assertEqual(new["source_pool"]["stop_reason"], "source_pairs_exhausted")
            self.assertGreater(new["source_pool"]["duplicates"], 0)
            template = next(r["template"] for r in new["candidates"] if context_operations(r["template"]) >= 2)
            self.assertEqual(lib.utility(corpus, template), lib.utility(original, template))
        self.assertEqual(corpus, original)

    def test_ineligible_sources_cannot_spend_the_whole_pair_budget(self):
        e = small()
        programs = [term("neg", term("const", value=str(n))) for n in range(80)]
        programs += [term("neg", term("neg", term("const", value=str(n)))) for n in range(10)]
        corpus = [{"id": str(i), "program": p} for i, p in enumerate(programs)]
        with lib.grammar(e.vocabulary.accepts):
            old = lib.learn(corpus, pairs=40, admissible=lambda t: context_operations(t) >= 2)
            new = lib.learn(corpus, pairs=40, admissible=lambda t: context_operations(t) >= 2,
                            source_filter=lambda t: context_operations(t) >= 2, deduplicate_sources=True)
        self.assertEqual(old["evaluated"], 0)
        self.assertGreater(new["evaluated"], 0)
        self.assertEqual(new["pairs_tried"], old["pairs_tried"])
        self.assertEqual(new["source_pool"]["stop_reason"], "pair_budget")
        self.assertEqual(sum(new["source_pool"][k] for k in ("excluded", "duplicates", "retained")),
                         new["source_pool"]["positions_scanned"])

    def test_normal_entry_retains_flag_and_does_not_inject_templates(self):
        e = Theory(config(), corpus_refresh=True, eligible_sources=True)
        e.run(cycles=10)
        self.assertTrue(e.state["dsl"]["attempts"])
        for a in e.state["dsl"]["attempts"]:
            self.assertIn("source_pools", a)
        restored = Theory(e.config, state=e.snapshot(), **e.flags)
        self.assertEqual(restored.flags, e.flags)
        with self.assertRaises(ValueError):
            Theory(e.config, state=e.snapshot(), corpus_refresh=True)
        for d in e.state["dsl"]["definitions"]:
            self.assertTrue(d["acquisition_sources"])
            self.assertTrue(d["source_evidence"])


class CorpusFeedback(unittest.TestCase):
    def test_refresh_keeps_bounded_view_not_a_second_full_history(self):
        e = small()
        for n in range(9):
            record(e, n)
        s = e.state["dsl"]
        self.assertEqual(s["experience_count"], 9)
        self.assertNotIn("experience_archive", s)
        self.assertFalse(s["acquisition_evidence"])
        self.assertEqual(len(s["corpus"]), 4)
        self.assertEqual([r["sequence"] for r in s["corpus"]], [6, 7, 8, 9])
        self.assertEqual(s["corpus_version"], 9)
        self.assertEqual(e.state["costs"]["corpus_feedback"]["retired"], 5)
        self.assertTrue(all(r["evaluation"]["scope"] == e.domain.scope for r in s["corpus"]))

    def test_baseline_records_rejection_without_changing_first_full_corpus(self):
        e = small(False)
        for n in range(9):
            record(e, n)
        s = e.state["dsl"]
        self.assertEqual(s["experience_count"], 9)
        self.assertEqual(s["corpus_arrivals"], 4)
        self.assertEqual([r["sequence"] for r in s["corpus"]], [1, 2, 3, 4])
        self.assertEqual(s["corpus_version"], 4)
        self.assertEqual(e.state["costs"]["corpus_feedback"]["refused_capacity"], 5)

    def test_duplicate_does_not_create_learning_eligibility(self):
        e = small()
        for n in range(4):
            record(e, n)
        e.vocabulary.learn()
        before = e.state["dsl"]["corpus_version"]
        for _ in range(9):
            record(e, 0)
        self.assertEqual(e.state["dsl"]["corpus_version"], before)
        self.assertNotIn("abstract", dict(e.vocabulary.options()))
        self.assertEqual(e.state["costs"]["corpus_feedback"]["duplicate_experiences"], 9)
        self.assertEqual(sum(r["status"] == "duplicate" for r in e.state["dsl"]["corpus_events"]), 9)

    def test_new_experience_reopens_learning_and_synthesis_after_capacity(self):
        for refresh in (False, True):
            e = small(refresh)
            cid = e.add_concept(term("neg", term("var", name="x")), [])
            e.acquire(cid)
            for n in range(4):
                record(e, n)
            e.vocabulary.learn()
            e.state["dsl"]["last_synthesis_generation"] = e.vocabulary.generation()
            for n in (4, 5):
                record(e, n)
            choices = dict(e.vocabulary.options())
            self.assertEqual("abstract" in choices, refresh)
            self.assertEqual("synthesize" in choices, refresh)
            self.assertEqual(len(e.state["dsl"]["corpus"]), 4)

    def test_resume_preserves_stream_and_refuses_condition_change(self):
        e = small()
        for n in range(7):
            record(e, n)
        state = e.snapshot()
        restored = Theory(config=e.config, corpus_refresh=True, state=state)
        for n in (7, 8, 1):
            record(e, n)
            record(restored, n)
        for field in ("corpus", "acquisition_evidence", "corpus_version", "corpus_events",
                      "corpus_arrivals", "last_learn_arrivals", "last_learn_knowledge",
                      "word_cursor", "natural_cursor", "composition_cursor", "last_synthesis_generation"):
            self.assertEqual(e.state["dsl"][field], restored.state["dsl"][field])
        with self.assertRaises(ValueError):
            Theory(e.config, state=state)

    def test_normal_loop_learns_from_post_capacity_experiences(self):
        e = small()
        e.run()
        s = e.state["dsl"]
        self.assertGreater(s["experience_count"], e.budget["library_corpus"])
        self.assertLessEqual(len(s["corpus"]), e.budget["library_corpus"])
        later = [a for a in s["attempts"] if a["corpus_arrivals"] > e.budget["library_corpus"]]
        self.assertTrue(later)
        for a in later:
            self.assertTrue(all(k in s["seen_programs"] for k in a["corpus_ids"]))
        for d in s["definitions"]:
            self.assertTrue(all(k in d["source_evidence"] for k in d["acquisition_sources"]))
            for k, ref in d["source_evidence"].items():
                self.assertEqual(s["acquisition_evidence"][ref]["id"], k)

    def test_no_candidate_attempt_is_consumed_until_relevant_knowledge_changes(self):
        e = small()
        for n in range(4):
            record(e, n)
        e.vocabulary.learn()
        self.assertIsNone(e.state["dsl"]["attempts"][-1]["accepted"])
        for _ in range(5):
            self.assertNotIn("abstract", dict(e.vocabulary.options()))
        cid = e.add_concept(term("neg", term("var", name="x")), [])
        e.acquire(cid)
        self.assertIn("abstract", dict(e.vocabulary.options()))
        e.vocabulary.learn()
        self.assertNotIn("abstract", dict(e.vocabulary.options()))

    def test_learner_edits_are_not_arrivals_and_sources_survive_fifo(self):
        c = json.loads((Path(__file__).resolve().parents[1]/"configs/theory-dsl-fold.json").read_text())
        c["budget"]["cycles"] = 40
        e = Theory(c, corpus_refresh=True, semantic_edits=True)
        e.run()
        s = e.state["dsl"]
        self.assertTrue(s["definitions"])
        self.assertGreater(s["corpus_version"], s["corpus_arrivals"])
        saved = deepcopy(s["acquisition_evidence"])
        definitions = deepcopy(s["definitions"])
        for n in range(e.budget["library_corpus"]*3):
            record(e, 10000+n)
        self.assertEqual(s["definitions"], definitions)
        self.assertEqual(s["acquisition_evidence"], saved)
        from math_os_prototype.theory_semantic_edit import validate
        for relation in s["semantic_relations"]:
            validate(e.vocabulary, relation)
        self.assertLessEqual(len(saved), e.budget["definitions"]*e.budget["library_corpus"])
        for source in saved.values():
            self.assertEqual(e.vocabulary.primitive(source["program"]), source["primitive"])
        e.vocabulary.learn()
        self.assertNotIn("abstract", dict(e.vocabulary.options()))

    def test_synthesis_empty_input_is_consumed_not_cursor_triggered(self):
        from test_theory_semantic_edit import define
        from math_os_prototype import library_compression as lib
        e = Theory(config(), corpus_refresh=True, representation_reuse=False)
        define(e, term("neg", lib.program_hole(0)))
        self.assertIn("synthesize", dict(e.vocabulary.options()))
        with patch.object(lib, "call_candidates", return_value=[]):
            e.vocabulary.synthesize()
        self.assertEqual(e.vocabulary.generation(), e.state["dsl"]["last_synthesis_generation"])
        for _ in range(4):
            self.assertNotIn("synthesize", dict(e.vocabulary.options()))

    def test_resumed_scheduler_matches_uninterrupted_program_stream(self):
        e = small()
        e.run(cycles=12)
        restored = Theory(e.config, corpus_refresh=True, state=e.snapshot())
        e.run()
        restored.run()
        self.assertEqual(e.config["seed"], restored.config["seed"])
        # The scheduler uses seeded content hashes, not a mutable PRNG stream.
        for field in ("corpus", "corpus_version", "corpus_arrivals", "experience_count",
                      "corpus_events", "word_cursor", "natural_cursor", "composition_cursor",
                      "last_learn_arrivals", "last_learn_knowledge", "last_synthesis_generation"):
            self.assertEqual(e.state["dsl"][field], restored.state["dsl"][field], field)
        self.assertEqual([r["program"] for r in e.state["dsl"]["executions"]],
                         [r["program"] for r in restored.state["dsl"]["executions"]])


if __name__ == "__main__":
    unittest.main()
