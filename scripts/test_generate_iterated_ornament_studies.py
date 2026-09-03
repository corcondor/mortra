from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from math_os_prototype.spatial_visual_basis import SpatialBuilder, new_morphism_count, semantic_hash
from scripts.generate_iterated_ornament_studies import (
    HEX_PROGRAMS,
    _rotation_residual,
    build_all,
    generate,
)


class IteratedOrnamentStudiesTest(unittest.TestCase):
    def test_reflection_is_an_existing_distance_preserving_construction(self) -> None:
        builder = SpatialBuilder("reflection-test", "test", {})
        builder.point("p", (1.25, -0.75, 2.0))
        builder.reflected_point("q", "p", plane_normal=(0.0, 1.0, 0.0))
        figure = builder.build()

        self.assertTrue(np.allclose(figure.points["q"], (1.25, 0.75, 2.0)))
        self.assertIn("reflect", figure.operations_used)
        self.assertEqual(new_morphism_count(figure), 0)

    def test_two_generators_produce_eight_complex_distinct_figures(self) -> None:
        figures = build_all()
        self.assertEqual(len(figures), 8)
        self.assertEqual(len({semantic_hash(figure) for _, _, figure in figures}), 8)
        self.assertEqual({figure.family for _, _, figure in figures}, {"orbit_index_map", "triangular_lattice_word"})
        self.assertTrue(all(new_morphism_count(figure) == 0 for _, _, figure in figures))
        self.assertTrue(all(len(figure.construction_trace) > 100 for _, _, figure in figures))

    def test_hex_programs_match_their_declared_rotational_order(self) -> None:
        programs = {program.study_id: program for program in HEX_PROGRAMS}
        for study_id, _, figure in build_all():
            if study_id not in programs:
                continue
            residual = _rotation_residual(figure, programs[study_id].rotational_order)
            self.assertLessEqual(residual, 1e-9, study_id)

    def test_small_renders_are_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first = generate(Path(first_dir), size=280)
            second = generate(Path(second_dir), size=280)
            self.assertTrue(first["passed"], first["checks"])
            self.assertTrue(second["passed"], second["checks"])
            self.assertEqual(
                [record["image_sha256"] for record in first["records"]],
                [record["image_sha256"] for record in second["records"]],
            )


if __name__ == "__main__":
    unittest.main()
