"""The execution boundary: full expansion, and what it must refuse.

Both grammars are exercised. The local rewrite expansion the learner uses is
checked to be unchanged, because silencing its "leave an unknown call standing"
behaviour would break the scoring it exists for.

The stored H2 shape is used here only to reproduce the defect and hold it fixed.
Its success in this file is a regression check, never a discovery.
"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from math_os_prototype import library_compression as L
from math_os_prototype.fold_library_bridge import program, validate_fold, word


def hyper(a, b=()):
    return {"op": "hyper", "a": list(a), "b": list(b)}


def call(index, **arguments):
    return {"op": "use", "abstraction": index, "arguments": dict(arguments)}


def then(head, tail):
    return {"op": "then", "head": head, "tail": tail}


F0 = {"series_parameter": "f0"}
F1 = {"series_parameter": "f1"}
END = {"op": "end"}

# --- series grammar -------------------------------------------------------
S_DIFF = {"op": "diff", "child": F0}            # depth 1
S_TWICE = call(0, f0=call(0, f0=F0))            # depth 2: the body is a call
S_THRICE = call(1, f0=F0)                       # depth 3: the body calls depth 2
SERIES = L.definition_table({0: S_DIFF, 1: S_TWICE, 2: S_THRICE})

# --- fold grammar ---------------------------------------------------------
FOLD_PAIR = then({"op": "A"}, then({"op": "G"}, F0))   # depth 1
FOLD_TWICE = call(0, f0=call(0, f0=F0))                # depth 2
FOLD_THRICE = call(1, f0=F0)                           # depth 3
FOLD = L.definition_table({0: FOLD_PAIR, 1: FOLD_TWICE, 2: FOLD_THRICE})


class PrimitiveTests(unittest.TestCase):
    def test_a_term_with_no_call_is_returned_unchanged_series(self):
        term = {"op": "mul", "left": hyper([1]),
                "right": {"op": "diff", "child": hyper([2])}}
        self.assertEqual(L.expand_for_execution(term, SERIES), term)

    def test_a_term_with_no_call_is_returned_unchanged_fold(self):
        term = program("AGCT")
        with L.grammar(validate_fold):
            self.assertEqual(L.expand_for_execution(term, FOLD), term)


class OneLevelTests(unittest.TestCase):
    def test_depth_one_agrees_with_the_local_expansion_series(self):
        node = call(0, f0=hyper([1]))
        self.assertEqual(L.expand_for_execution(node, SERIES),
                         L.expand(node, SERIES))
        self.assertEqual(L.expand_for_execution(node, SERIES),
                         {"op": "diff", "child": hyper([1])})

    def test_depth_one_agrees_with_the_local_expansion_fold(self):
        node = call(0, f0=END)
        with L.grammar(validate_fold):
            self.assertEqual(L.expand_for_execution(node, FOLD),
                             L.expand(node, FOLD))
            self.assertEqual(word(L.expand_for_execution(node, FOLD)), "AG")


class DeepTests(unittest.TestCase):
    """The defect: a body that is itself a call used to be left standing."""

    def test_two_levels_expand_where_the_local_rewrite_stops_series(self):
        node = call(1, f0=hyper([1]))
        self.assertTrue(L.calls_in(L.expand(node, SERIES)),
                        "the local rewrite leaves the inner call standing")
        full = L.expand_for_execution(node, SERIES)
        self.assertEqual(L.calls_in(full), [])
        self.assertEqual(full, {"op": "diff",
                                "child": {"op": "diff", "child": hyper([1])}})

    def test_three_levels_expand_series(self):
        full = L.expand_for_execution(call(2, f0=hyper([1])), SERIES)
        self.assertEqual(L.calls_in(full), [])
        self.assertEqual(full, {"op": "diff",
                                "child": {"op": "diff", "child": hyper([1])}})

    def test_two_and_three_levels_expand_fold(self):
        with L.grammar(validate_fold):
            self.assertTrue(L.calls_in(L.expand(call(1, f0=END), FOLD)))
            self.assertEqual(word(L.expand_for_execution(call(1, f0=END), FOLD)),
                             "AGAG")
            self.assertEqual(word(L.expand_for_execution(call(2, f0=END), FOLD)),
                             "AGAG")


class ArgumentCallTests(unittest.TestCase):
    def test_a_call_inside_an_argument_is_driven_out_series(self):
        full = L.expand_for_execution(call(0, f0=call(0, f0=hyper([1]))), SERIES)
        self.assertEqual(L.calls_in(full), [])
        self.assertEqual(full, {"op": "diff",
                                "child": {"op": "diff", "child": hyper([1])}})

    def test_a_call_inside_an_argument_is_driven_out_fold(self):
        with L.grammar(validate_fold):
            full = L.expand_for_execution(call(0, f0=call(0, f0=END)), FOLD)
            self.assertEqual(word(full), "AGAG")

    def test_repeating_a_name_in_an_argument_is_not_a_cycle(self):
        deep = call(0, f0=call(0, f0=call(0, f0=hyper([1]))))
        self.assertEqual(L.calls_in(L.expand_for_execution(deep, SERIES)), [])


class IdempotenceTests(unittest.TestCase):
    def test_expanding_a_full_expansion_again_changes_nothing_series(self):
        once = L.expand_for_execution(call(1, f0=hyper([1])), SERIES)
        self.assertEqual(L.expand_for_execution(once, SERIES), once)

    def test_expanding_a_full_expansion_again_changes_nothing_fold(self):
        with L.grammar(validate_fold):
            once = L.expand_for_execution(call(1, f0=END), FOLD)
            self.assertEqual(L.expand_for_execution(once, FOLD), once)


class RefusalTests(unittest.TestCase):
    def test_an_unresolved_name_is_refused(self):
        with self.assertRaises(L.ExpansionError) as caught:
            L.expand_for_execution(call(9, f0=hyper([1])), SERIES)
        self.assertIn("does not hold", str(caught.exception))

    def test_a_missing_or_extra_argument_is_refused(self):
        with self.assertRaises(L.ExpansionError):
            L.expand_for_execution(call(0), SERIES)
        with self.assertRaises(L.ExpansionError):
            L.expand_for_execution(call(0, f0=hyper([1]), f1=hyper([2])), SERIES)

    def test_a_definition_reached_from_its_own_body_is_refused(self):
        cyclic = L.definition_table({0: call(1, f0=F0), 1: call(0, f0=F0)})
        with self.assertRaises(L.ExpansionError) as caught:
            L.expand_for_execution(call(0, f0=hyper([1])), cyclic)
        self.assertIn("its own body", str(caught.exception))

    def test_a_step_budget_never_returns_a_partial_expansion(self):
        with self.assertRaises(L.ExpansionError) as caught:
            L.expand_for_execution(call(2, f0=hyper([1])), SERIES, steps=3)
        self.assertIn("partial expansion is not a result", str(caught.exception))

    def test_an_unbound_hole_is_refused(self):
        with self.assertRaises(L.ExpansionError) as caught:
            L.expand_for_execution(call(0, f0=F1), SERIES)
        self.assertIn("unbound holes", str(caught.exception))

    def test_the_domain_validate_still_has_the_last_word(self):
        # a fold body handed a series program is a term of neither language
        with L.grammar(validate_fold):
            with self.assertRaises((ValueError, TypeError)):
                L.expand_for_execution(call(0, f0=hyper([1])), FOLD)


class LocalRewriteUnchangedTests(unittest.TestCase):
    """`expand` is the learner check and must keep leaving unknowns standing."""

    def test_an_unknown_call_is_still_left_standing_by_expand(self):
        partial = L.definition_table({0: S_DIFF})
        node = call(7, f0=hyper([1]))
        self.assertEqual(L.expand(node, partial), node)

    def test_utility_still_round_trips_through_the_local_expansion(self):
        corpus = [{"id": "a", "program": {"op": "diff", "child": hyper([1])}},
                  {"id": "b", "program": {"op": "diff", "child": hyper([2])}}]
        verdict = L.utility(corpus, S_DIFF, index=0)
        # what matters here is the round trip, not the sign: whether this
        # abstraction pays is the objective's business and is left alone
        # a site that does not expand back is recorded as a failure and its row
        # is reset to zero sites, so a clean round trip is: sites, no failures
        self.assertEqual(verdict["failures"], [],
                         "no rewritten site failed to expand back")
        self.assertTrue(any(row["sites"] for row in verdict["rewritten"]),
                        "the template should match this corpus")


class StoredDefectTests(unittest.TestCase):
    """Reproduces the stored failing shape. A regression check, not a discovery."""

    H0_BODY = then(F0, then(F1, then({"series_parameter": "f2"},
                   then({"series_parameter": "f3"},
                        then({"series_parameter": "f4"},
                             then({"series_parameter": "f5"}, END))))))
    H2_BODY = call(0, f0={"op": "G"}, f1={"op": "A"}, f2={"op": "G"},
                   f3={"op": "A"}, f4={"op": "G"}, f5=F0)

    def test_the_stored_shape_used_to_stop_and_now_runs(self):
        table = L.definition_table({0: self.H0_BODY, 2: self.H2_BODY})
        node = call(2, f0=program("AG"))
        with L.grammar(validate_fold):
            self.assertTrue(L.calls_in(L.expand(node, table)),
                            "this is what used to reach the kinematics")
            full = L.expand_for_execution(node, table)
            self.assertEqual(L.calls_in(full), [])
            self.assertEqual(word(full), "GAGAGAG")


if __name__ == "__main__":
    unittest.main()
