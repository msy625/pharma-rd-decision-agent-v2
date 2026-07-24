import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from deepinsight.core.rd_event_timeline_service import RDEventTimelineService


class RDEventTimelineServiceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.service = RDEventTimelineService()
        cls.core_events = cls.service.build_events()
        cls.all_events = cls.service.build_events(include_auxiliary=True)
        cls.by_id = {event["source_id"]: event for event in cls.all_events}

    def test_01_company_aliases_are_normalized_by_existing_profile_service(self):
        self.assertEqual(self.service.normalize_company("恒瑞医药")["canonical_name"], "恒瑞医药")
        for alias in ["百济神州", "BeOne Medicines", "BeiGene"]:
            self.assertEqual(self.service.normalize_company(alias)["canonical_name"], "百济神州")
        self.assertEqual(self.service.normalize_company("AstraZeneca")["canonical_name"], "阿斯利康")

    def test_02_dynamic_dated_core_auxiliary_and_undated_baseline(self):
        timeline = self.service.build_timeline()
        self.assertEqual(timeline["summary"]["total_source_count"], 39)
        self.assertEqual(timeline["summary"]["dated_source_count"], 16)
        self.assertEqual(timeline["summary"]["core_event_count"], 15)
        self.assertEqual(timeline["summary"]["auxiliary_event_count"], 1)
        self.assertEqual(timeline["summary"]["undated_source_count"], 23)
        self.assertEqual(len(self.core_events), 15)
        self.assertEqual(len(self.all_events), 16)
        self.assertEqual(len(self.service.undated_sources()), 23)

    def test_03_company_core_counts_and_default_auxiliary_visibility(self):
        hengrui = self.service.build_timeline(company_name="恒瑞医药")
        beone = self.service.build_timeline(company_name="BeOne Medicines")
        astrazeneca = self.service.build_timeline(company_name="AstraZeneca")
        self.assertEqual(hengrui["summary"]["core_event_count"], 2)
        self.assertEqual(beone["summary"]["core_event_count"], 9)
        self.assertEqual(beone["summary"]["auxiliary_event_count"], 1)
        self.assertEqual(astrazeneca["summary"]["core_event_count"], 4)
        self.assertEqual(astrazeneca["summary"]["undated_source_count"], 4)
        self.assertNotIn("B014", {event["source_id"] for event in beone["events"]})
        with_auxiliary = self.service.build_timeline(company_name="百济神州", include_auxiliary=True)
        self.assertIn("B014", {event["source_id"] for event in with_auxiliary["events"]})

    def test_04_event_type_distribution_is_computed_from_events(self):
        counts = {item["key"]: item["count"] for item in self.service.event_type_distribution()}
        self.assertEqual(
            counts,
            {
                "company_disclosure": 2,
                "registration_authorisation": 1,
                "interim_analysis": 3,
                "final_analysis": 2,
                "combined_analysis_publication": 1,
                "formal_authorisation": 1,
                "regulatory_opinion": 1,
                "source_publication": 4,
            },
        )
        auxiliary = self.service.event_type_distribution([self.by_id["B014"]])
        self.assertEqual(auxiliary, [{"key": "evidence_update", "label": "证据版本更新", "count": 1}])

    def test_05_verified_and_generated_times_never_become_event_dates(self):
        fake = {
            "source_id": "X001",
            "company": "恒瑞医药",
            "company_cn": "恒瑞医药",
            "source_type": "公司正式公告",
            "url": "https://example.invalid/x001",
            "verified_at": "2026-07-23",
            "generated_at": "2026-07-23T12:00:00Z",
        }
        with patch.object(self.service.source_registry_service, "load_rows", return_value=[fake]):
            self.assertEqual(self.service.build_events(include_auxiliary=True), [])
        for event in self.all_events:
            self.assertNotIn(event["date"]["field"], {"verified_at", "generated_at", "source_last_updated"})

    def test_06_month_precision_is_preserved_without_fake_day(self):
        event = self.by_id["H013"]
        self.assertEqual(event["date"]["value"], "2026-01")
        self.assertEqual(event["date"]["precision"], "month")
        self.assertEqual(event["date"]["original_value"], "2026年1月")

    def test_07_each_source_id_generates_at_most_one_event(self):
        source_ids = [event["source_id"] for event in self.all_events]
        event_ids = [event["event_id"] for event in self.all_events]
        self.assertEqual(len(source_ids), len(set(source_ids)))
        self.assertEqual(event_ids, [f"source:{source_id}" for source_id in source_ids])

    def test_08_b015_is_initial_eu_authorisation_not_page_update_or_trial_approval(self):
        event = self.by_id["B015"]
        self.assertEqual(event["date"]["value"], "2023-09-15")
        self.assertEqual(event["date"]["field"], "publication_date")
        self.assertEqual(event["source_last_updated"], "2026-05-27")
        self.assertEqual(event["event_type"], "formal_authorisation")
        self.assertIn("Tevimbra欧盟初始许可", event["title"])
        self.assertEqual(event["chain_id"], "regulatory:tevimbra-eu-nsclc")
        self.assertEqual(event["trial_id"], "")
        self.assertFalse(event["is_trial_evidence"])

    def test_09_b016_is_chmp_positive_opinion_not_final_approval(self):
        event = self.by_id["B016"]
        self.assertEqual(event["date"]["value"], "2025-07-24")
        self.assertEqual(event["event_type"], "regulatory_opinion")
        self.assertIn("CHMP积极意见，非最终批准", event["title"])
        self.assertIn("NCT04379635", event["related_trial_ids"])
        self.assertFalse(event["is_trial_evidence"])

    def test_10_rationale_304_has_forward_and_reverse_version_links(self):
        b006, b007 = self.by_id["B006"], self.by_id["B007"]
        self.assertEqual(b006["date"]["value"], "2021-05-23")
        self.assertEqual(b006["version_status"], "historical")
        self.assertEqual(b006["superseded_by_source_id"], "B007")
        self.assertEqual(b007["date"]["value"], "2024-09-25")
        self.assertEqual(b007["version_status"], "latest")
        self.assertEqual(b007["supersedes_source_id"], "B006")

    def test_11_rationale_307_has_forward_and_reverse_version_links(self):
        b008, b009 = self.by_id["B008"], self.by_id["B009"]
        self.assertEqual(b008["date"]["value"], "2021-05-01")
        self.assertEqual(b008["version_status"], "historical")
        self.assertEqual(b008["superseded_by_source_id"], "B009")
        self.assertEqual(b009["date"]["value"], "2024-09-25")
        self.assertEqual(b009["version_status"], "latest")
        self.assertEqual(b009["supersedes_source_id"], "B008")

    def test_12_b010_generates_one_combined_event(self):
        events = [event for event in self.all_events if event["source_id"] == "B010"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "combined_analysis_publication")

    def test_13_same_trial_event_count_and_unique_trial_count_are_separate(self):
        rationale_304 = self.service.build_timeline(trial_id="NCT03663205")
        self.assertEqual(rationale_304["summary"]["event_count"], 2)
        self.assertEqual(rationale_304["summary"]["unique_trial_count"], 1)
        rationale_315 = self.service.build_timeline(trial_id="NCT04379635")
        self.assertEqual({event["source_id"] for event in rationale_315["events"]}, {"B011", "B016"})
        self.assertEqual(rationale_315["summary"]["unique_trial_count"], 1)
        self.assertNotIn("B015", {event["source_id"] for event in rationale_315["events"]})

    def test_14_company_trial_drug_event_type_and_year_filters(self):
        self.assertEqual(len(self.service.events_by_company("恒瑞医药")), 2)
        self.assertEqual({event["source_id"] for event in self.service.events_by_trial("NCT03663205")}, {"B006", "B007"})
        self.assertIn("B015", {event["source_id"] for event in self.service.events_by_drug("TEVIMBRA")})
        final_events = self.service.build_timeline(event_type="final_analysis")
        self.assertEqual({event["source_id"] for event in final_events["events"]}, {"B007", "B009"})
        year_events = self.service.build_timeline(year=2024)
        self.assertEqual({event["source_id"] for event in year_events["events"]}, {"A006", "B007", "B009", "B011"})

    def test_15_undated_sources_support_company_trial_and_drug_filters(self):
        self.assertEqual(len(self.service.undated_sources(company_name="恒瑞医药")), 13)
        self.assertEqual(
            {item["source_id"] for item in self.service.undated_sources(trial_id="NCT04379635")},
            {"B012", "B013"},
        )
        self.assertTrue(self.service.undated_sources(drug_name="SHR-A2009"))


if __name__ == "__main__":
    unittest.main()
