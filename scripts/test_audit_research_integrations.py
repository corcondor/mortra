from __future__ import annotations

import unittest

from scripts.audit_research_integrations import ROOT, SOURCES, audit


class ResearchIntegrationAuditTests(unittest.TestCase):
    def test_runtime_claims_have_code_evidence(self) -> None:
        report = audit(ROOT / "missing-source-checkouts")
        for source in report["sources"]:
            if source["integration"] in {
                "native-runtime",
                "native-runtime-bridge",
                "library-runtime",
            }:
                self.assertTrue(source["evidence"])
                self.assertTrue(all(item["exists"] for item in source["evidence"]))

    def test_checkout_never_implies_complete_reverse_engineering(self) -> None:
        report = audit(ROOT / "missing-source-checkouts")
        self.assertFalse(report["summary"]["complete_reverse_engineering_claim"])
        self.assertTrue(report["protocol"]["clone_is_not_integration"])
        self.assertGreater(len(SOURCES), 10)

    def test_score_claims_require_existing_artifacts(self) -> None:
        report = audit(ROOT.parent.parent / ".cache" / "missing-source-checkouts")
        for source in report["sources"]:
            if source["score_claim_supported"]:
                self.assertTrue(source["benchmark_artifacts"])
                self.assertTrue(
                    all(item["exists"] for item in source["benchmark_artifacts"])
                )

    def test_integrated_core_methods_have_paper_traceability(self) -> None:
        report = audit(ROOT / "missing-source-checkouts")
        core = {
            source["name"]: source
            for source in report["sources"]
            if source["name"] in {
                "AlphaGeometry",
                "FormalGeo",
                "GCLC",
                "HAGeo",
                "Newclid/Yuclid",
                "Sheaf-ADMM",
            }
        }
        self.assertEqual(len(core), 6)
        self.assertTrue(all(source["paper_method"] for source in core.values()))
        self.assertEqual(core["FormalGeo"]["integration"], "native-runtime-bridge")
        self.assertTrue(core["FormalGeo"]["runtime_claim_supported"])
        self.assertFalse(core["FormalGeo"]["score_claim_supported"])


if __name__ == "__main__":
    unittest.main()
