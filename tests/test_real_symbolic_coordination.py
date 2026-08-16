from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RealSymbolicCoordinationArtifactTest(unittest.TestCase):
    def test_strict_exchange_has_two_independent_certificates(self) -> None:
        report = json.loads(
            (ROOT / "data" / "real-symbolic-coordination-imo-ag-30-relation-expanded-2026-08-16.json")
            .read_text(encoding="utf-8")
        )
        self.assertEqual(report["summary"]["baseline_unresolved"], 13)
        self.assertEqual(report["summary"]["translated"], 13)
        self.assertEqual(report["summary"]["translation_unsupported"], 0)
        self.assertEqual(
            report["summary"]["strict_exchange_proved_names"],
            ["2008_p1a", "2012_p5"],
        )
        self.assertEqual(report["summary"]["strict_portfolio_solved"], 19)
        self.assertAlmostEqual(report["summary"]["strict_portfolio_score"], 19 / 30)
        self.assertEqual(report["summary"]["strict_false_accepts"], 0)
        self.assertEqual(
            report["summary"]["one_sided_proved_names"],
            ["2008_p1b", "2009_p2"],
        )
        for name in ("2008_p1a", "2012_p5"):
            result = report["results"][name]
            self.assertTrue(result["gclc"]["proved"])
            self.assertEqual(result["exact"]["status"], "proved")
            self.assertTrue(result["typed_goal_agreement"])
            self.assertTrue(result["strict_exchange_proved"])

    def test_typed_local_control_reduces_dispatch(self) -> None:
        report = json.loads(
            (ROOT / "data" / "real-symbolic-coordination-equal-dispatch-2026-08-16.json")
            .read_text(encoding="utf-8")
        )
        global_mode = report["equal_budget"]["global_blackboard"]
        local_mode = report["equal_budget"]["typed_local_sheaf"]
        self.assertGreater(
            local_mode["success_probability"],
            global_mode["success_probability"],
        )
        self.assertLess(
            report["full_coverage"]["typed_local_sheaf_agent_calls"],
            report["full_coverage"]["global_blackboard_agent_calls"],
        )


if __name__ == "__main__":
    unittest.main()
