from __future__ import annotations

from copy import deepcopy
import unittest

import sympy as sp

try:
    from math_os_prototype.polytope_containment import (
        published_theorem_dependency,
        regular_tetrahedron_cube_containment,
        validate_published_theorem_dependency,
    )
except ImportError:
    from polytope_containment import (
        published_theorem_dependency,
        regular_tetrahedron_cube_containment,
        validate_published_theorem_dependency,
    )


THEOREM_ID = "croft.1980.regular_cube_in_regular_tetrahedron"


class PolytopeContainmentTests(unittest.TestCase):
    def test_published_theorem_record_is_hash_bound(self) -> None:
        dependency = published_theorem_dependency(THEOREM_ID)

        self.assertTrue(validate_published_theorem_dependency(dependency))
        self.assertEqual(len(dependency["registry_record_sha256"]), 64)

        mutated = deepcopy(dependency)
        mutated["claim"]["maximum_inner_edge"] = "1/3"
        self.assertFalse(validate_published_theorem_dependency(mutated))

    def test_current_edge_is_scaled_and_replayed_exactly(self) -> None:
        expected_unit = sp.sqrt(6) / (sp.sqrt(6) + 2 * sp.sqrt(2) + 3)

        for edge in (sp.Integer(1), sp.Integer(2), sp.Rational(7, 3)):
            with self.subTest(edge=edge):
                certificate = regular_tetrahedron_cube_containment(edge)
                actual = sp.sympify(certificate["maximum_side"])
                self.assertEqual(sp.simplify(actual - edge * expected_unit), 0)
                self.assertEqual(
                    certificate["query_parameters"]["outer_edge"], sp.sstr(edge)
                )
                self.assertEqual(len(certificate["cube_vertices"]), 8)
                self.assertEqual(len(certificate["tetrahedron_vertices"]), 4)
                self.assertEqual(certificate["face_contact_residual"], ["0"] * 4)
                self.assertTrue(all(certificate["proof_obligations"].values()))

    def test_machine_replay_and_external_global_proof_are_not_conflated(self) -> None:
        certificate = regular_tetrahedron_cube_containment(1)

        self.assertEqual(
            certificate["proof_basis"],
            "published_global_theorem_with_exact_current_input_replay",
        )
        self.assertIn(
            "containment of all eight cube vertices",
            certificate["machine_replay_scope"],
        )
        self.assertEqual(
            certificate["external_proof_scope"],
            ["global upper bound over every cube orientation and translation"],
        )
        self.assertNotIn(
            "global_support_lower_bound_instantiated",
            certificate["proof_obligations"],
        )

    def test_nonpositive_edge_is_rejected(self) -> None:
        for edge in (0, -1):
            with self.subTest(edge=edge):
                with self.assertRaises(ValueError):
                    regular_tetrahedron_cube_containment(edge)


if __name__ == "__main__":
    unittest.main()
