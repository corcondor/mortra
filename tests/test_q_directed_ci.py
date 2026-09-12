"""Verifier regressions use synthetic fixtures, not MORTRA discovery evidence."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import verify_q_directed_ci as ci


def costs():
    return {p: {k: 0 for k in ("prover_calls", "task_certifier_calls", "search_nodes", "wall_time")}
            for p in ("acquisition", "certification")}


class VerificationGates(unittest.TestCase):
    def test_missing_enumeration_is_not_success(self):
        with self.assertRaises(ValueError):
            ci.check_small({"verification": [], "all_checks_agree": True}, [3, 5])

    def test_disagreement_fails(self):
        trace = {"verification": [{"length": 3, "answers_agree": False}],
                 "all_checks_agree": True}
        with self.assertRaises(ValueError):
            ci.check_small(trace, [3])

    def test_reacquisition_cannot_hide_in_zero_exit(self):
        for phase in ("acquisition", "certification"):
            for key in ("prover_calls", "task_certifier_calls", "search_nodes", "wall_time"):
                record = {"costs": costs(), "candidates_offered": []}
                record["costs"][phase][key] = 1
                with self.assertRaises(ValueError):
                    ci.no_acquisition(record)

    def test_offered_candidates_fail_reuse(self):
        with self.assertRaises(ValueError):
            ci.no_acquisition({"costs": costs(), "candidates_offered": ["fixture"]})

    def test_stop_with_an_answer_fails(self):
        with self.assertRaises(ValueError):
            ci.check_stopped({"stopped": "incompatible", "reused": False,
                              "answers": [{"answer": 1}], "costs": costs()})

    def test_empty_stopped_trace_fails(self):
        with self.assertRaises(ValueError):
            ci.check_stopped({})

    def test_proper_refusal_is_accepted(self):
        ci.check_stopped({"stopped": "incompatible", "reused": False,
                          "answers": [], "candidates_offered": [], "costs": costs()})

    def test_short_certificate_cannot_license_long_reuse(self):
        row = {"reused": True, "acquired_again": False, "from_entry": "fresh",
               "cost": {"proof_calls": 0, "task_certifier_calls": 0}, "costs": costs(),
               "reuse_contract": {"scope": {"kind": "bounded_from_seed"}}}
        with self.assertRaises(ValueError):
            ci.check_reuse(row, {"fresh"})

    def test_wrong_source_store_fails(self):
        row = {"reused": True, "acquired_again": False, "from_entry": "historical"}
        with self.assertRaises(ValueError):
            ci.check_reuse(row, {"fresh"})

    def test_counterexample_must_be_same_layer(self):
        row = {"fallback": True, "selected": {"basis": None}, "admitted": [],
               "refused_by_certificate": [{"refused_by": ["legality"], "counterexample": {
                   "check": "legality", "length": 3, "word_a": "AAA", "word_b": "AAAA",
                   "value_a": "True", "value_b": "False"}}]}
        with self.assertRaises(ValueError):
            ci.check_refusal(row)
        row["refused_by_certificate"][0]["counterexample"]["word_b"] = "AAT"
        self.assertEqual(len(ci.check_refusal(row)), 1)
        invalid = deepcopy(row)
        invalid["selected"]["basis"] = ["fixture"]
        with self.assertRaises(ValueError):
            ci.check_refusal(invalid)


if __name__ == "__main__":
    unittest.main()
