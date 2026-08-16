from __future__ import annotations

import unittest

from worker.backend.jgex_gclc_translator import (
    canonical_typed_goal_key,
    translate_jgex_to_gclc,
)


class JGEXGCLCTranslatorTest(unittest.TestCase):
    def test_midpoint_theorem_uses_only_structure(self) -> None:
        result = translate_jgex_to_gclc(
            "a b c = triangle a b c; m = midpoint m a b; "
            "n = midpoint n a c ? para m n b c"
        )
        self.assertIn("midpoint m a b", result.source)
        self.assertIn("midpoint n a c", result.source)
        self.assertRegex(
            result.source,
            r"prove \{ parallel (?:m n b c|b c m n) \}",
        )
        self.assertEqual(result.goal_channel, "para")

    def test_right_triangle_and_foot_are_constructive(self) -> None:
        result = translate_jgex_to_gclc(
            "c a b = r_triangle c a b; d = foot d c a b ? cong a d d b"
        )
        self.assertIn("perp mortra_perp_", result.source)
        self.assertIn("foot d c", result.source)
        self.assertIn("prove { equal", result.source)
        self.assertIn("{ segment a d }", result.source)
        self.assertIn("{ segment b d }", result.source)

    def test_compound_line_circle_locus_is_intersection(self) -> None:
        result = translate_jgex_to_gclc(
            "a b c = triangle a b c; o = circle o a b c; "
            "x = on_line x a b, on_circle x o a ? cong o x o a"
        )
        self.assertIn("intersec2 x", result.source)
        self.assertIn("circle mortra_circle_", result.source)

    def test_unknown_construction_is_rejected_not_memorized(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported compound loci"):
            translate_jgex_to_gclc(
                "a b = segment a b; x = impossible x a b ? coll a b x"
            )

    def test_goal_key_respects_relation_symmetry(self) -> None:
        self.assertEqual(
            canonical_typed_goal_key("cong", ("o", "q", "o", "p")),
            canonical_typed_goal_key("cong", ("p", "o", "q", "o")),
        )
        self.assertEqual(
            canonical_typed_goal_key("para", ("a", "b", "c", "d")),
            canonical_typed_goal_key("para", ("d", "c", "b", "a")),
        )


if __name__ == "__main__":
    unittest.main()
