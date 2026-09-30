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
CONFIG = ROOT / "config" / "organization_names_zh.json"
HARVEST_PREFIX = "ORG_HARVEST_"
ZH_DISPLAY = re.compile(r"^.+（.+）$")


def load(name):
    with (TEMPLATE / f"{name}.csv").open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


class OrganizationNamesZhTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads(CONFIG.read_text(encoding="utf-8"))
        cls.rules = cls.config["rules"]
        cls.orgs = load("organizations")
        cls.aliases = load("organization_aliases")
        cls.by_id = {r["organization_id"]: r for r in cls.orgs}
        cls.service = DirectionDatasetService()

    # ---- dictionary integrity ------------------------------------------
    def test_01_dictionary_rules_are_complete(self):
        self.assertTrue(self.rules)
        for rule in self.rules:
            with self.subTest(rule=rule.get("id")):
                self.assertTrue(rule.get("id"))
                self.assertTrue(rule.get("match"))
                self.assertTrue(rule.get("zh"))
                self.assertTrue(rule.get("short_en"))
                self.assertTrue(rule.get("category"))

    def test_02_rule_ids_and_patterns_are_unique(self):
        ids = [r["id"] for r in self.rules]
        self.assertEqual(len(ids), len(set(ids)))
        patterns = [r["match"] for r in self.rules]
        self.assertEqual(len(patterns), len(set(patterns)))

    def test_03_every_rule_pattern_compiles(self):
        for rule in self.rules:
            with self.subTest(rule=rule["id"]):
                re.compile(rule["match"])

    def test_04_chinese_names_are_actually_chinese(self):
        for rule in self.rules:
            with self.subTest(rule=rule["id"]):
                self.assertTrue(
                    any("\u4e00" <= ch <= "\u9fff" for ch in rule["zh"]),
                    f"{rule['id']} zh value contains no Chinese characters: {rule['zh']!r}",
                )

    # ---- applied data ---------------------------------------------------
    def test_05_localized_display_names_follow_the_convention(self):
        localized = [r for r in self.orgs if r["organization_id"].startswith(HARVEST_PREFIX) and r["display_name"] != r["canonical_name"]]
        self.assertTrue(localized)
        for row in localized:
            with self.subTest(org=row["organization_id"]):
                self.assertRegex(row["display_name"], ZH_DISPLAY)

    def test_06_canonical_name_is_never_rewritten(self):
        """canonical_name is the join key for facts/relations, so it must stay original."""
        rules = [(re.compile(r["match"]), r) for r in self.rules]
        for row in self.orgs:
            if not row["organization_id"].startswith(HARVEST_PREFIX):
                continue
            name = row["canonical_name"]
            matched = next((r for rx, r in rules if rx.search(name)), None)
            with self.subTest(org=row["organization_id"]):
                if matched:
                    self.assertEqual(row["display_name"], f"{matched['zh']}（{matched['short_en']}）")
                else:
                    self.assertEqual(row["display_name"], name)

    def test_07_no_invented_names(self):
        """Every harvest org is either rule-derived or keeps its own original name."""
        allowed = {f"{r['zh']}（{r['short_en']}）" for r in self.rules}
        for row in self.orgs:
            if not row["organization_id"].startswith(HARVEST_PREFIX):
                continue
            with self.subTest(org=row["organization_id"]):
                self.assertIn(row["display_name"], allowed | {row["canonical_name"]})

    def test_08_every_localized_org_has_a_zh_alias(self):
        rules = [(re.compile(r["match"]), r) for r in self.rules]
        localized = [
            r
            for r in self.orgs
            if r["organization_id"].startswith(HARVEST_PREFIX) and r["display_name"] != r["canonical_name"]
        ]
        self.assertTrue(localized)
        zh_aliases = {
            a["organization_id"]: a
            for a in self.aliases
            if a["language"] == "zh" and a["alias_type"] == "display_name"
        }
        for row in localized:
            rule = next((r for rx, r in rules if rx.search(row["canonical_name"])), None)
            alias = zh_aliases.get(row["organization_id"])
            with self.subTest(org=row["organization_id"]):
                self.assertIsNotNone(rule)
                self.assertIsNotNone(alias, f"{row['organization_id']} has no zh alias")
                # Compare against the rule, not by splitting display_name: some
                # Chinese names legitimately contain parentheses of their own.
                self.assertEqual(alias["alias"], rule["zh"])
                self.assertTrue(alias["alias_id"].endswith("_ZH"))

    def test_09_english_alias_is_still_present(self):
        for row in self.orgs:
            if not row["organization_id"].startswith(HARVEST_PREFIX):
                continue
            with self.subTest(org=row["organization_id"]):
                canonical_alias = f"ALIAS_{row['organization_id']}_CANONICAL"
                self.assertIn(canonical_alias, {a["alias_id"] for a in self.aliases})

    def test_10_alias_ids_are_unique(self):
        ids = [a["alias_id"] for a in self.aliases]
        self.assertEqual(len(ids), len(set(ids)))

    def test_11_localization_script_is_idempotent(self):
        before = {
            name: (TEMPLATE / f"{name}.csv").read_text(encoding="utf-8")
            for name in ("organizations", "organization_aliases")
        }
        result = subprocess.run(
            [sys.executable, "scripts/localize_organization_names.py"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("files written: 0", result.stdout)
        for name, content in before.items():
            with self.subTest(table=name):
                self.assertEqual((TEMPLATE / f"{name}.csv").read_text(encoding="utf-8"), content)

    # ---- service integration -------------------------------------------
    def test_12_service_exposes_chinese_company_names(self):
        records = [r for r in self.service.records() if r.get("company")]
        self.assertTrue(records)
        chinese = [r for r in records if any("\u4e00" <= ch <= "\u9fff" for ch in str(r["company"]))]
        self.assertTrue(chinese, "no record exposes a Chinese company name")

    def test_13_service_keeps_the_english_name_for_search(self):
        records = [r for r in self.service.records() if r.get("company")]
        for record in records:
            if str(record["company"]).startswith(("辉瑞", "诺华")):
                with self.subTest(record=record["record_id"]):
                    self.assertTrue(record.get("company_en"))

    def test_14_search_works_in_both_languages(self):
        for needle in ("Pfizer", "辉瑞"):
            with self.subTest(needle=needle):
                result = self.service.query(text=needle, limit=1)
                self.assertGreater(result["total"], 0)

    def test_15_company_filter_accepts_either_language(self):
        by_en = self.service.query(company="Novartis", limit=1)
        by_zh = self.service.query(company="诺华", limit=1)
        self.assertGreater(by_en["total"], 0)
        self.assertEqual(by_en["total"], by_zh["total"])

    def test_16_untouched_organizations_keep_their_english_display_name(self):
        untouched = [
            r
            for r in self.orgs
            if r["organization_id"].startswith(HARVEST_PREFIX) and r["display_name"] == r["canonical_name"]
        ]
        self.assertTrue(untouched)
        for row in untouched[:50]:
            with self.subTest(org=row["organization_id"]):
                self.assertFalse(any("\u4e00" <= ch <= "\u9fff" for ch in row["display_name"]))


    def test_17_zh_alias_follows_its_english_alias(self):
        """Chinese rows must sit next to their English pair, not be buried at the end.

        Appending them made the CSV preview on GitHub (and the first screenful of
        the file) show English only, which is not what a reviewer expects.
        """
        positions = {row["alias_id"]: index for index, row in enumerate(self.aliases)}
        checked = 0
        for row in self.orgs:
            if not row["organization_id"].startswith(HARVEST_PREFIX):
                continue
            canonical_id = f"ALIAS_{row['organization_id']}_CANONICAL"
            zh_id = f"ALIAS_{row['organization_id']}_ZH"
            if zh_id in positions and canonical_id in positions:
                with self.subTest(org=row["organization_id"]):
                    self.assertEqual(
                        positions[zh_id],
                        positions[canonical_id] + 1,
                        f"{zh_id} is not adjacent to {canonical_id}",
                    )
                checked += 1
        self.assertGreater(checked, 0)


if __name__ == "__main__":
    unittest.main()
