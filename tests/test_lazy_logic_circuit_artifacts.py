from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class LazyLogicCircuitArtifactTest(unittest.TestCase):
    def load(self, name: str) -> dict:
        return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))

    def test_cross_domain_lazy_compilation_preserves_replay(self) -> None:
        report = self.load("lazy-logic-circuit-heldout-2026-08-17.json")
        summary = report["summary"]["overall"]
        self.assertEqual(summary["exhaustive_solved"], 400)
        self.assertEqual(summary["lazy_solved"], 400)
        self.assertEqual(summary["lazy_negative_abstained"], 400)
        self.assertGreater(summary["match_reduction_rate"], 0.80)
        self.assertGreater(summary["gate_reduction_rate"], 0.90)

    def test_real_jgex_certificates_remain_native_replayable(self) -> None:
        report = self.load("lazy-jgex-relation-benchmark-2026-08-17.json")
        summary = report["summary"]
        self.assertEqual(summary["local_goal_total"], 20)
        self.assertEqual(summary["current_local_replayed"], 20)
        self.assertEqual(summary["lazy_circuit_local_replayed"], 20)
        self.assertEqual(summary["matched_negative_abstained"], 20)
        self.assertEqual(summary["global_imo_strict_portfolio_before_and_after"], 19)

    def test_global_benchmark_is_reported_without_score_inflation(self) -> None:
        yuclid = self.load("yuclid-imo-ag-30-lazy-circuit-control-2026-08-17.json")
        strict = self.load(
            "real-symbolic-coordination-lazy-circuit-control-2026-08-17.json"
        )
        self.assertEqual(
            yuclid["scores"]["original_imo_ag_30"]["solved"],
            17,
        )
        self.assertEqual(strict["summary"]["strict_exchange_proved"], 2)
        self.assertEqual(strict["summary"]["strict_portfolio_solved"], 19)


if __name__ == "__main__":
    unittest.main()
