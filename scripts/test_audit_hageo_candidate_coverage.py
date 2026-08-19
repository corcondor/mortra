from __future__ import annotations

import unittest

from scripts.audit_hageo_candidate_coverage import parse_step, solved_paths
from worker.backend.typed_geometry_stalk import (
    ConstructionFamily,
    equivalent_construction_inputs,
)


class HageoCandidateCoverageTest(unittest.TestCase):
    def test_parse_step_round_trip(self) -> None:
        step = parse_step("intersection_ll(a,b,c,d)->e")
        self.assertEqual(step.family, "intersection_ll")
        self.assertEqual(step.inputs, ("a", "b", "c", "d"))
        self.assertEqual(step.output, "e")
        self.assertEqual(step.key, "intersection_ll(a,b,c,d)->e")

    def test_only_solved_attempt_paths_are_used(self) -> None:
        paths = solved_paths(
            {
                "attempt_results": [
                    {"solved": False, "path": ["midpoint(a,b)->c"]},
                    {"solved": True, "path": ["midpoint(a,b)->c"]},
                ]
            }
        )
        self.assertEqual(len(paths), 1)
        self.assertEqual(paths[0][0].family, "midpoint")

    def test_declared_symmetry_not_text_order_controls_equivalence(self) -> None:
        midpoint = ConstructionFamily("midpoint", 2, "all", ("midp",))
        reflect = ConstructionFamily("reflect", 3, "head_pair", ("cong",))
        self.assertTrue(equivalent_construction_inputs(midpoint, ("a", "b"), ("b", "a")))
        self.assertTrue(
            equivalent_construction_inputs(
                reflect, ("p", "a", "b"), ("p", "b", "a")
            )
        )
        self.assertFalse(
            equivalent_construction_inputs(
                reflect, ("p", "a", "b"), ("a", "p", "b")
            )
        )


if __name__ == "__main__":
    unittest.main()
