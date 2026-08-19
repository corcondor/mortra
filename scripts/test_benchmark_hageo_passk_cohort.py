from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from scripts.benchmark_hageo_passk_cohort import (
    ROOT,
    _artifact_result,
    _build_report,
)


class CohortCheckpointTest(unittest.TestCase):
    def setUp(self) -> None:
        self.args = SimpleNamespace(
            rounds=6,
            attempts=8,
            seed=0,
            per_family_limit=4,
            incidence_oversample_per_family=16,
            candidate_limit=64,
        )

    def test_resume_artifact_and_partial_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "data") as temporary:
            path = Path(temporary) / "p.json"
            path.write_text(
                json.dumps(
                    {
                        "problem_name": "p",
                        "solved": True,
                        "completed_attempts": 8,
                        "unique_paths": 8,
                        "right_censored_shards": 0,
                        "execution_error_shards": 0,
                        "protocol": {"rounds_n": 6, "attempts_k": 8, "seed": 0},
                    }
                ),
                encoding="utf-8",
            )
            result = _artifact_result(
                "p", path, args=self.args, elapsed_seconds=0.0, reused=True
            )
            report = _build_report(
                ["p", "q"], [result], args=self.args, started=time.perf_counter()
            )
        self.assertTrue(result["reused"])
        self.assertEqual(report["summary"]["completed_problems"], 1)
        self.assertEqual(report["summary"]["missing_problems"], 1)
        self.assertFalse(report["summary"]["complete"])
        self.assertEqual(report["missing_names"], ["q"])

    def test_resume_rejects_protocol_mismatch(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "data") as temporary:
            path = Path(temporary) / "p.json"
            path.write_text(
                json.dumps(
                    {
                        "problem_name": "p",
                        "solved": False,
                        "completed_attempts": 4,
                        "unique_paths": 4,
                        "right_censored_shards": 0,
                        "execution_error_shards": 0,
                        "protocol": {"rounds_n": 4, "attempts_k": 4, "seed": 0},
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "incompatible resume artifact"):
                _artifact_result(
                    "p", path, args=self.args, elapsed_seconds=0.0, reused=True
                )


if __name__ == "__main__":
    unittest.main()
