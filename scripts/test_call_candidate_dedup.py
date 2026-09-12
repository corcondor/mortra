"""Already-held constructions must not consume the candidate slots.

The fixture is the shape that actually occurred: a call whose expansion splices
whole terms into a body, so the same fold word comes back nested while the
corpus holds it flat. Comparing the terms as written makes it look new.

Nothing here prefers a word or a definition; the fixture is a regression case.
"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from math_os_prototype import library_compression as L
from math_os_prototype.fold_library_bridge import program, validate_fold, word
from math_os_prototype.holonomic_route_discovery import key


def then(head, tail):
    return {"op": "then", "head": head, "tail": tail}


F0, F1 = {"series_parameter": "f0"}, {"series_parameter": "f1"}
#: a two-argument concatenation, the shape the learner actually produced
JOIN = then(F0, F1)
TABLE = L.definition_table({0: JOIN})
LIBRARY = [{"index": 0, "id": "join", "template": JOIN, "utility_bits": 1}]


def flatten(term):
    try:
        return program(word(term))
    except (ValueError, TypeError):
        return term


class RepresentationTests(unittest.TestCase):
    def test_the_same_word_is_written_two_ways(self):
        flat = program("AGAGAG")
        with L.grammar(validate_fold):
            nested = L.expand_for_execution(
                {"op": "use", "abstraction": 0,
                 "arguments": {"f0": program("AGAG"), "f1": program("AG")}}, TABLE)
            self.assertEqual(word(nested), word(flat))
            self.assertNotEqual(key(nested), key(flat),
                                "this inequality is the defect")
            self.assertEqual(key(flatten(nested)), key(flat))


class SlotTests(unittest.TestCase):
    """A slot spent on something already held is a slot not spent on anything."""

    def setUp(self):
        self.pool = [program(w) for w in ("AG", "AGAG", "AGAGAG", "C", "CC")]
        # the corpus already holds everything the join of two pool entries makes
        self.held = [key(program(a + b))
                     for a in ("AG", "AGAG", "AGAGAG") for b in ("AG", "AGAG")]

    def test_without_normalisation_held_words_fill_every_slot(self):
        with L.grammar(validate_fold):
            offered = L.call_candidates(LIBRARY, self.pool, limit=4,
                                        exclude=self.held, table=TABLE)
            words = [word(L.expand_for_execution(o["call"], TABLE))
                     for o in offered]
        already = [w for w in words if key(program(w)) in self.held]
        self.assertEqual(len(offered), 4)
        self.assertTrue(already, "the defect: held words take the slots")

    def test_with_normalisation_no_slot_goes_to_a_held_word(self):
        with L.grammar(validate_fold):
            offered = L.call_candidates(LIBRARY, self.pool, limit=4,
                                        exclude=self.held, table=TABLE,
                                        normalise=flatten)
            words = [word(L.expand_for_execution(o["call"], TABLE))
                     for o in offered]
        for w in words:
            self.assertNotIn(key(program(w)), self.held,
                             f"{w} was already held and still took a slot")

    def test_skipping_a_held_word_moves_on_to_the_next_combination(self):
        with L.grammar(validate_fold):
            offered = L.call_candidates(LIBRARY, self.pool, limit=4,
                                        exclude=self.held, table=TABLE,
                                        normalise=flatten)
        self.assertEqual(len(offered), 4, "the budget still produced a full set")
        self.assertEqual(len({o["id"] for o in offered}), 4)

    def test_two_routes_to_one_construction_are_recorded_not_counted(self):
        revisits = []
        with L.grammar(validate_fold):
            offered = L.call_candidates(LIBRARY, self.pool, limit=4,
                                        exclude=self.held, table=TABLE,
                                        normalise=flatten, revisits=revisits)
        self.assertTrue(revisits, "the held words were reached and recorded")
        self.assertFalse({r["id"] for r in revisits} & {o["id"] for o in offered},
                         "a revisit is not also counted as a new construction")
        for entry in revisits:
            self.assertIn("already held", entry["reason"])

    def test_the_scan_is_bounded(self):
        with L.grammar(validate_fold):
            offered = L.call_candidates(LIBRARY, self.pool, limit=100,
                                        exclude=self.held, table=TABLE,
                                        normalise=flatten, scan=3)
        self.assertLessEqual(len(offered), 3,
                             "no more than the scan budget may be examined")

    def test_the_default_normalisation_changes_nothing(self):
        with L.grammar(validate_fold):
            plain = L.call_candidates(LIBRARY, self.pool, limit=4, table=TABLE)
            same = L.call_candidates(LIBRARY, self.pool, limit=4, table=TABLE,
                                     normalise=None)
        self.assertEqual([o["id"] for o in plain], [o["id"] for o in same])


class SeriesUnaffectedTests(unittest.TestCase):
    """The series grammar writes each program one way; the default must hold."""

    def test_the_series_path_is_unchanged(self):
        template = {"op": "diff", "child": {"series_parameter": "f0"}}
        library = [{"index": 0, "id": "d", "template": template, "utility_bits": 1}]
        pool = [{"op": "hyper", "a": [n], "b": []} for n in (1, 2, 3)]
        offered = L.call_candidates(library, pool, limit=3)
        self.assertEqual(len(offered), 3)
        self.assertEqual(len({o["id"] for o in offered}), 3)


if __name__ == "__main__":
    unittest.main()
