import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.finalize_geometry_proof_portfolio import main


class FinalizeGeometryProofPortfolioTest(unittest.TestCase):
    def _write(self, root: Path, name: str, payload: dict) -> Path:
        path = root / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_accepts_only_native_confirmed_construction(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = self._write(
                root,
                "baseline.json",
                {"summary": {"total": 3, "portfolio_names": ["p1"]}},
            )
            accepted = self._write(
                root,
                "p2.json",
                {
                    "problem_name": "p2",
                    "solved": True,
                    "solved_path": ["midpoint(a,b)->m"],
                    "confirmation": {
                        "solved": True,
                        "input_sha256": "input",
                        "proof_sha256": "proof",
                    },
                },
            )
            rejected = self._write(
                root,
                "p3.json",
                {"problem_name": "p3", "solved": True, "confirmation": {}},
            )
            output = root / "output.json"
            argv = [
                "finalize",
                "--baseline",
                str(baseline),
                "--construction",
                str(accepted),
                "--construction",
                str(rejected),
                "--output",
                str(output),
            ]
            with patch("sys.argv", argv):
                self.assertEqual(main(), 0)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["summary"]["portfolio_names"], ["p1", "p2"])
            self.assertEqual(payload["summary"]["portfolio_score"], 2 / 3)
            self.assertEqual(payload["rejected"][0]["problem"], "p3")

    def test_rejects_incomplete_zero_decomposition(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = self._write(
                root,
                "baseline.json",
                {"summary": {"total": 2, "portfolio_names": ["p1"]}},
            )
            wu = self._write(
                root,
                "wu.json",
                {
                    "problem_name": "p2",
                    "result": {
                        "coverage_complete": False,
                        "all_identities_replayed": True,
                        "unresolved_leaf_count": 1,
                    },
                },
            )
            output = root / "output.json"
            with patch(
                "sys.argv",
                [
                    "finalize",
                    "--baseline",
                    str(baseline),
                    "--zero-decomposition",
                    str(wu),
                    "--output",
                    str(output),
                ],
            ):
                self.assertEqual(main(), 0)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["summary"]["portfolio_solved"], 1)
            self.assertEqual(payload["rejected"][0]["source"], "wu_groebner")

    def test_accepts_complete_problem_from_multi_result_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = self._write(
                root,
                "baseline.json",
                {"summary": {"total": 2, "portfolio_names": ["p1"]}},
            )
            wu = self._write(
                root,
                "wu.json",
                {
                    "results": {
                        "p2": {
                            "decomposition": {
                                "coverage_complete": True,
                                "all_computed_identities_replayed": True,
                                "unresolved_leaf_count": 0,
                            }
                        }
                    }
                },
            )
            output = root / "output.json"
            with patch(
                "sys.argv",
                [
                    "finalize",
                    "--baseline",
                    str(baseline),
                    "--zero-decomposition",
                    str(wu),
                    "--output",
                    str(output),
                ],
            ):
                self.assertEqual(main(), 0)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["summary"]["portfolio_names"], ["p1", "p2"])


if __name__ == "__main__":
    unittest.main()
