import unittest

from deepinsight.core.evidence_decision_brief_service import EvidenceDecisionBriefService


class EvidenceDecisionBriefServiceTest(unittest.TestCase):
    def setUp(self):
        self.service = EvidenceDecisionBriefService()

    def test_brief_contains_twelve_decision_sections_and_traceable_conclusions(self):
        brief = self.service.build_brief("阿斯利康")
        for key in [
            "subject", "executive_summary", "overview", "clinical_evidence", "evidence_evolution",
            "timeline", "regulatory_status", "evidence_strength", "evidence_gaps",
            "risks_and_limitations", "next_evidence_directions", "citations", "metadata",
        ]:
            self.assertIn(key, brief)
        self.assertEqual(len(brief["citations"]), 8)
        self.assertTrue(all(item["source_ids"] for item in brief["executive_summary"][:2]))
        self.assertTrue(all(item["evidence_status"] in {"verified_fact", "structured_summary", "insufficient_evidence"} for item in brief["executive_summary"]))

    def test_regulatory_and_gap_sections_preserve_evidence_boundaries(self):
        brief = self.service.build_brief("百济神州")
        self.assertTrue(brief["regulatory_status"])
        self.assertTrue(brief["evidence_gaps"])
        self.assertTrue(all(item["evidence_status"] == "insufficient_evidence" for item in brief["evidence_gaps"]))
        combined = "\n".join(item["text"] for item in brief["executive_summary"])
        for forbidden in ["值得投资", "成功率", "疗效最好", "企业实力更强"]:
            self.assertNotIn(forbidden, combined)

    def test_unknown_company_is_explicit_error(self):
        with self.assertRaisesRegex(ValueError, "未知企业"):
            self.service.build_brief("不存在企业")


if __name__ == "__main__":
    unittest.main()
