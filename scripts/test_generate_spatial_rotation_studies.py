from __future__ import annotations

import math
import tempfile
import unittest
from pathlib import Path

import numpy as np

from math_os_prototype.spatial_visual_basis import (
    Camera,
    edge_length_signature,
    new_morphism_count,
    project_points,
    rotate_axis_angle,
    rotate_figure,
    semantic_hash,
)
from scripts.generate_spatial_rotation_studies import BUILDERS, STUDIES, generate


class SpatialRotationStudiesTest(unittest.TestCase):
    def test_arbitrary_axis_rotation_preserves_norm_and_edge_lengths(self) -> None:
        point = (1.25, -0.75, 2.5)
        rotated_point = rotate_axis_angle(point, (2.0, -1.0, 3.0), 1.173)
        self.assertAlmostEqual(np.linalg.norm(point), np.linalg.norm(rotated_point), places=11)

        figure = BUILDERS["recursive_tetra_crown"]()
        rotated = rotate_figure(figure, (1.0, 2.0, 3.0), 0.731, "test")
        self.assertEqual(edge_length_signature(figure), edge_length_signature(rotated))
        self.assertEqual(new_morphism_count(rotated), 0)

    def test_camera_orbit_changes_projection_without_changing_semantics(self) -> None:
        figure = BUILDERS["polyhedral_orbit"]()
        identity = semantic_hash(figure)
        views = []
        for azimuth in (0, 45, 90, 135, 180):
            projected = project_points(figure, Camera(azimuth, 28, distance=10.5, focal_length=2.0))
            signature = tuple(
                (round(point.x, 8), round(point.y, 8), round(point.depth, 8))
                for _, point in sorted(projected.items())
            )
            views.append(signature)
        self.assertEqual(len(set(views)), 5)
        self.assertEqual(semantic_hash(figure), identity)

    def test_all_studies_use_existing_geometry_and_are_structurally_distinct(self) -> None:
        figures = [BUILDERS[spec.family]() for spec in STUDIES]
        self.assertEqual(len(figures), 9)
        self.assertEqual(len({semantic_hash(figure) for figure in figures}), 9)
        self.assertTrue(all(new_morphism_count(figure) == 0 for figure in figures))
        self.assertTrue(all(len(figure.points) >= 12 for figure in figures))
        self.assertTrue(all(len(figure.edges) >= 12 for figure in figures))

    def test_manifest_and_images_are_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first = generate(Path(first_dir))
            second = generate(Path(second_dir))
            self.assertTrue(first["passed"], first["checks"])
            self.assertTrue(second["passed"], second["checks"])
            first_hashes = [record["image_sha256"] for record in first["records"]]
            second_hashes = [record["image_sha256"] for record in second["records"]]
            self.assertEqual(first_hashes, second_hashes)
            self.assertLessEqual(first["rotation_invariance_max_edge_residual"], 1e-9)
            self.assertTrue(all(Path(record["path"]).exists() for record in first["records"]))
            self.assertEqual(first["arbitrary_axis_animation"]["frame_count"], 24)
            self.assertTrue(Path(first["arbitrary_axis_animation"]["path"]).exists())


if __name__ == "__main__":
    unittest.main()
