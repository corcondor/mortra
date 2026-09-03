from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.generate_origami_fold_dna_studies import generate


class GenerateOrigamiFoldDnaStudiesTest(unittest.TestCase):
    def test_small_renders_are_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first = generate(Path(first_dir), size=260, include_animation=False)
            second = generate(Path(second_dir), size=260, include_animation=False)
            self.assertTrue(first["passed"], first["checks"])
            self.assertTrue(second["passed"], second["checks"])
            self.assertEqual(
                [item["image_sha256"] for item in first["records"]],
                [item["image_sha256"] for item in second["records"]],
            )


if __name__ == "__main__":
    unittest.main()
