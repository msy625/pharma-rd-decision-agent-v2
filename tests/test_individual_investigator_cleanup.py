import csv
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from deepinsight.core.direction_dataset_service import DirectionDatasetService


TEMPLATE = ROOT / "data" / "template"
CONFIG = ROOT / "config" / "individual_investigator_names.json"

ORG_HINT = re.compile(
    r"Inc\b|Ltd\b|LLC|GmbH|Pharma|Bio|Therap|Technolog|Medical|Health|Hospital|Universit|"
    r"Institute|College|School|Academy|Cent(er|re)|Clinic|Foundation|Group|Network|Societ|"
    r"Associat|Agency|Ministry|Government|National|Research|Sciences|Oncology|System|"
    r"Solutions|Ventures|Partners|Medicine|Medicines|Limited|Region|Holding|Fund",
    re.I,
)


def load(name):
    with (TEMPLATE / f"{name}.csv").open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


class IndividualInvestigatorCleanupTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads(CONFIG.read_text(encoding="utf-8"))
        cls.names = set(cls.config["individuals"])
        cls.reviewed_real = set(cls.config["reviewed_real_organizations_not_in_the_list"])
        cls.orgs = load("organizations")
        cls.aliases = load("organization_aliases")
        cls.studies = load("studies")
        cls.relations = load("relations")
        cls.by_canonical = {r["canonical_name"].strip(): r for r in cls.orgs}
        cls.service = DirectionDatasetService()

    # ---- list hygiene ---------------------------------------------------
    def test_01_list_is_present_and_populated(self):
        self.assertTrue(self.names)
        self.assertEqual(len(self.names), len(self.config["individuals"]), "duplicate entries in the list")

    def test_02_listed_names_do_not_look_like_organizations(self):
        for name in self.names:
            with self.subTest(name=name):
                self.assertIsNone(ORG_HINT.search(name), f"{name!r} contains an organization keyword")

    def test_03_reviewed_real_organizations_are_documented_and_excluded(self):
        self.assertTrue(self.reviewed_real)
        self.assertFalse(self.names & self.reviewed_real, "a reviewed real organization is also listed for removal")

    # ---- removal actually happened --------------------------------------
    def test_04_no_listed_name_remains_as_an_organization(self):
        for name in self.names:
            with self.subTest(name=name):
                self.assertNotIn(name, self.by_canonical)

    def test_05_reviewed_real_organizations_are_still_present(self):
        for name in self.reviewed_real:
            with self.subTest(name=name):
                self.assertIn(name, self.by_canonical, f"{name} was removed but is a real organization")

    def test_06_no_orphan_aliases(self):
        org_ids = {r["organization_id"] for r in self.orgs}
        for alias in self.aliases:
            with self.subTest(alias=alias["alias_id"]):
                self.assertIn(alias["organization_id"], org_ids)

    def test_07_no_dangling_org_relations(self):
        org_ids = {r["organization_id"] for r in self.orgs}
        for relation in self.relations:
            if relation["relation_type"] == "source_about_org":
                with self.subTest(relation=relation["relation_id"]):
                    self.assertIn(relation["object_id"], org_ids)

    def test_08_every_study_sponsor_resolves(self):
        org_ids = {r["organization_id"] for r in self.orgs}
        for study in self.studies:
            sponsor = study["sponsor_org_id"]
            if sponsor:
                with self.subTest(study=study["study_id"]):
                    self.assertIn(sponsor, org_ids)

    def test_09_no_study_still_points_at_a_removed_org_id(self):
        """Removed ids must be gone from sponsor_org_id, not just from the org table."""
        removed_ids = {
            r["organization_id"] for r in self.service.load_table("organizations")
        }
        for study in self.studies:
            with self.subTest(study=study["study_id"]):
                if study["sponsor_org_id"]:
                    self.assertIn(study["sponsor_org_id"], removed_ids)

    # ---- runtime behaviour ----------------------------------------------
    def test_10_individuals_no_longer_appear_as_sponsors(self):
        companies = {str(r.get("company", "")) for r in self.service.records()}
        for name in self.names:
            with self.subTest(name=name):
                self.assertNotIn(name, companies)

    def test_11_sponsor_filter_options_exclude_them(self):
        options = set(self.service.filter_options()["company"])
        for name in self.names:
            with self.subTest(name=name):
                self.assertNotIn(name, options)

    def test_12_affected_studies_render_without_a_sponsor(self):
        result = self.service.query(direction_id="asthma", limit=500)
        self.assertGreater(result["total"], 0)
        for item in result["items"]:
            with self.subTest(record=item["record_id"]):
                self.assertIsInstance(item["company"], str)

    # ---- idempotency -----------------------------------------------------
    def test_13_removal_script_is_idempotent(self):
        before = {
            name: (TEMPLATE / f"{name}.csv").read_text(encoding="utf-8")
            for name in ("organizations", "organization_aliases", "relations", "studies")
        }
        result = subprocess.run(
            [sys.executable, "scripts/drop_individual_investigators.py"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("nothing to remove", result.stdout)
        for name, content in before.items():
            with self.subTest(table=name):
                self.assertEqual((TEMPLATE / f"{name}.csv").read_text(encoding="utf-8"), content)

    def test_14_report_mode_writes_nothing(self):
        before = (TEMPLATE / "organizations.csv").read_text(encoding="utf-8")
        result = subprocess.run(
            [sys.executable, "scripts/drop_individual_investigators.py", "--report"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("nothing written", result.stdout)
        self.assertEqual((TEMPLATE / "organizations.csv").read_text(encoding="utf-8"), before)


if __name__ == "__main__":
    unittest.main()
