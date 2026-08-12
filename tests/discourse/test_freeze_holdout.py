import importlib.util
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "freeze_holdout", ROOT / "scripts" / "freeze_holdout.py"
)
freeze_holdout = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(freeze_holdout)


class FrozenPartitionTest(unittest.TestCase):
    def frozen(self, entries):
        return {
            "count": len(entries),
            "digest": freeze_holdout.digest(entries),
            "ids": [entry["id"] for entry in entries],
        }

    def test_newly_ingested_records_remain_unassigned(self):
        original = [{"id": "a"}, {"id": "b"}]
        result = freeze_holdout.verify_frozen_partition(
            original + [{"id": "new"}], self.frozen(original)
        )
        self.assertTrue(result["valid"])
        self.assertEqual(result["extra"], ["new"])

    def test_missing_frozen_record_invalidates_split(self):
        original = [{"id": "a"}, {"id": "b"}]
        result = freeze_holdout.verify_frozen_partition(
            [{"id": "a"}], self.frozen(original)
        )
        self.assertFalse(result["valid"])
        self.assertEqual(result["missing"], ["b"])

    def test_manifest_digest_mismatch_invalidates_split(self):
        original = [{"id": "a"}]
        frozen = self.frozen(original)
        frozen["digest"] = "not-the-digest"
        result = freeze_holdout.verify_frozen_partition(original, frozen)
        self.assertFalse(result["valid"])


if __name__ == "__main__":
    unittest.main()
