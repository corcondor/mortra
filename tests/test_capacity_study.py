from copy import deepcopy
import unittest
from scripts.analyze_capacity_study import CONTROL, check_pair, lineage, read


class CapacityMeasurementTests(unittest.TestCase):
    def test_committed_plans_are_single_factor(self):
        a = read(CONTROL/"configs/persistent-learning-capacity-128.json")
        b = read(CONTROL/"configs/persistent-learning-capacity-256.json")
        check_pair(a, b)
        b["seed"] += 1
        with self.assertRaises(ValueError):
            check_pair(a, b)

    def test_lineage_is_read_only_and_validates_provenance(self):
        s = {"concepts": {"a": {"parents": [], "born": 0},
                          "b": {"parents": ["a"], "born": 2},
                          "c": {"parents": ["b"], "born": 3}}}
        original = deepcopy(s)
        self.assertEqual(lineage(s)["maximum_recorded_concept_depth"], 2)
        self.assertEqual(s, original)
        s["concepts"]["a"]["parents"] = ["c"]
        with self.assertRaises(ValueError):
            lineage(s)


if __name__ == "__main__":
    unittest.main()
