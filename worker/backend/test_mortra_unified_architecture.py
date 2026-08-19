from __future__ import annotations

import copy
import unittest

from worker.backend.mortra_unified_architecture import (
    unified_geometry_architecture_manifest,
    validate_unified_geometry_architecture,
)


class MortraUnifiedArchitectureTest(unittest.TestCase):
    def test_manifest_keeps_control_truth_and_acceleration_contracts_together(self) -> None:
        manifest = unified_geometry_architecture_manifest()
        validate_unified_geometry_architecture(manifest)
        self.assertIn("hageo_numerical_incidence", manifest["proposal_plane"]["agents"])
        self.assertEqual(
            manifest["coordination_plane"]["method"],
            "differentiable_heterogeneous_sheaf_admm",
        )
        self.assertFalse(manifest["execution_plane"]["changes_mathematical_truth"])

    def test_priority_cannot_be_promoted_to_truth(self) -> None:
        manifest = copy.deepcopy(unified_geometry_architecture_manifest())
        manifest["truth_plane"]["accepts_priority_without_certificate"] = True
        with self.assertRaises(ValueError):
            validate_unified_geometry_architecture(manifest)
