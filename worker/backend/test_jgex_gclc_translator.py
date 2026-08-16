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

    def test_point_renaming_preserves_the_morphism_program(self) -> None:
        first = translate_jgex_to_gclc(
            "a b c = triangle a b c; d = on_circle d a b ? cyclic a b c d"
        )
        renamed = translate_jgex_to_gclc(
            "p q r = triangle p q r; s = on_circle s p q ? cyclic p q r s"
        )

        def commands(source: str) -> tuple[str, ...]:
            return tuple(line.split(maxsplit=1)[0] for line in source.splitlines())

        self.assertEqual(commands(first.source), commands(renamed.source))
        self.assertEqual(first.construction_vocabulary, renamed.construction_vocabulary)
        self.assertEqual(first.goal_channel, renamed.goal_channel)
        self.assertNotEqual(first.source_sha256, renamed.source_sha256)

    def test_goal_key_respects_relation_symmetry(self) -> None:
        self.assertEqual(
            canonical_typed_goal_key("cong", ("o", "q", "o", "p")),
            canonical_typed_goal_key("cong", ("p", "o", "q", "o")),
        )
        self.assertEqual(
            canonical_typed_goal_key("para", ("a", "b", "c", "d")),
            canonical_typed_goal_key("para", ("d", "c", "b", "a")),
        )
        self.assertEqual(
            canonical_typed_goal_key("cyclic", ("a", "b", "c", "d", "e")),
            canonical_typed_goal_key("cyclic", ("e", "c", "a", "d", "b")),
        )

    def test_cyclic_goal_is_a_low_degree_angle_identity(self) -> None:
        result = translate_jgex_to_gclc(
            "a b c = triangle a b c; d = on_circle d a b ? cyclic a b c d"
        )
        self.assertEqual(result.goal_channel, "cyclic")
        self.assertIn("pythagoras_difference3", result.source)
        self.assertNotIn("mortra_cyclic_center_", result.source)
        self.assertIn("signed_area3", result.source)
        self.assertIn("prove { equal", result.source)

    def test_angle_line_uses_a_direct_similarity_construction(self) -> None:
        result = translate_jgex_to_gclc(
            "a b c = triangle a b c; d e f = triangle d e f; "
            "x = on_aline x a b c d e, on_line x b f ? coll b x f"
        )
        self.assertIn("mortra_similarity_source_perp_axis_", result.source)
        self.assertIn("intersec2 mortra_similarity_source_perp_", result.source)
        self.assertIn("parallel mortra_para_", result.source)
        self.assertIn("translate mortra_similarity_image_", result.source)
        self.assertNotIn("rotate", result.source)
        self.assertNotIn("turtle", result.source)

    def test_equal_angle_circle_is_built_from_tangent_chord_structure(self) -> None:
        result = translate_jgex_to_gclc(
            "a b c = triangle a b c; d e f = triangle d e f; "
            "x = eqangle3 x a b d e f, on_line x b c ? coll b c x"
        )
        self.assertIn("mortra_eqangle_center_", result.source)
        self.assertIn("circle mortra_circle_", result.source)
        self.assertIn("intersec2 x", result.source)

    def test_circle_tangents_are_constructed_from_homothety(self) -> None:
        problem = (
            "o a u = triangle o a u; w b v = triangle w b v; "
            "x y z i = cc_tangent x y z i o a w b ? perp x o x y"
        )
        result = translate_jgex_to_gclc(problem, sketch_seed=0)
        alternate = translate_jgex_to_gclc(problem, sketch_seed=1)
        self.assertIn("mortra_tangent_homothety_center_", result.source)
        self.assertIn("mortra_tangent_contact_chord_", result.source)
        self.assertNotIn("mortra_tangent_diameter_center_", result.source)
        self.assertRegex(
            result.source,
            r"translate mortra_tangent_radius_difference_\d+ "
            r"mortra_tangent_aligned_radius_\d+ a o",
        )
        self.assertRegex(
            alternate.source,
            r"translate mortra_tangent_radius_difference_\d+ "
            r"mortra_tangent_opposite_radius_\d+ a o",
        )
        self.assertNotEqual(result.source_sha256, alternate.source_sha256)
        self.assertIn("foot y w", result.source)
        self.assertIn("foot i w", result.source)


if __name__ == "__main__":
    unittest.main()
