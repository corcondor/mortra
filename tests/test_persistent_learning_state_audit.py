"""Guard the post-run audit boundary, not a new learning capability."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from math_os_prototype.representation_progress import digest
from math_os_prototype.theory_formation import Theory
from scripts.audit_persistent_learning_state import inspect_state, portable_seal


CONFIG = {"domain": {"kind": "differential_ring", "variables": ["u", "v"],
                      "operations": ["add", "mul", "neg", "diff"]},
          "seed": 1, "budget": {"cycles": 1, "seconds": 60}}


class AuditTests(unittest.TestCase):
    def test_portable_source_paths_do_not_ignore_content(self):
        self.assertEqual(portable_seal({"a/b.py": "hash"}), portable_seal({r"a\b.py": "hash"}))
        self.assertNotEqual(portable_seal({"a/b.py": "changed"}), portable_seal({r"a\b.py": "hash"}))
        with self.assertRaises(ValueError):
            portable_seal({"a/b.py": "hash", r"a\b.py": "hash"})

    def test_never_advances_or_mutates_snapshot(self):
        state = Theory(CONFIG).run(cycles=1)
        original = deepcopy(state)
        with patch.object(Theory, "step", side_effect=AssertionError("must not execute")), \
             patch.object(Theory, "run", side_effect=AssertionError("must not resume")), \
             patch.object(Theory, "settle", side_effect=AssertionError("must not solve")), \
             patch.object(Theory, "acquire", side_effect=AssertionError("must not acquire")):
            result = inspect_state(state)
        self.assertEqual(state, original)
        self.assertEqual(result["executed_steps"], 0)
        self.assertFalse(result["capability_growth_measured"])

    def test_damaged_seal_rejected(self):
        state = Theory(CONFIG).run(cycles=1)
        state["cycle"] += 1
        with self.assertRaisesRegex(ValueError, "seal mismatch"):
            inspect_state(state)

    def test_missing_dependency_is_reported(self):
        state = Theory(CONFIG).run(cycles=1)
        state["proof_dependencies"]["test"] = ["missing"]
        state.pop("sha256")
        state["sha256"] = digest(state)
        result = inspect_state(state)
        self.assertEqual(result["scope_or_dependency_issues"][0]["kind"], "dependency_not_earlier")


if __name__ == "__main__":
    unittest.main()
