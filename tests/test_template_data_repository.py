import unittest
import json
from pathlib import Path

from deepinsight.core.template_data_repository import TemplateDataRepository


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / "data" / "template" / "data_manifest.json").read_text(encoding="utf-8"))


class TemplateDataRepositoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repository = TemplateDataRepository(ROOT / "data" / "template")

    def test_normalized_template_is_readable(self):
        self.assertEqual(len(self.repository.load_table("sources")), MANIFEST["counts"]["sources"])
        self.assertEqual(len(self.repository.load_table("relations")), MANIFEST["counts"]["relations"])

    def test_runtime_rows_preserve_legacy_chain_identifiers(self):
        rows = self.repository.source_rows()
        source_ids = {row["source_id"] for row in rows}
        # Detached rows and rows with unresolved relations are withheld.
        self.assertEqual(len(rows), MANIFEST["counts"]["sources"])
        self.assertIn("B006", source_ids)
        self.assertIn("A005", source_ids)
        self.assertIn("SRC_MET_SURPASS2_PUB", source_ids)

    def test_template_relations_supply_query_fields(self):
        row = next(row for row in self.repository.source_rows() if row["source_id"] == "B006")
        self.assertEqual(row["company_cn"], "百济神州")
        self.assertEqual(row["parent_trial_id"], "NCT03663205")
        self.assertIn("替雷利珠单抗", row["drug_names"])
        self.assertEqual(row["is_latest_evidence"], "false")

    def test_legacy_display_title_is_preserved_for_company_sources(self):
        rows = {row["source_id"]: row for row in self.repository.source_rows()}
        expected_titles = {
            "H001": "恒瑞医药 2025 ELCC 肺癌研究相关页面",
            "H002": "恒瑞医药 2025 年年度报告摘要",
            "H003": "SHR-A1811 用于 HER2 表达、扩增或突变晚期非小细胞肺癌患者的 I/II 期临床研究",
            "H004": "SHR-1210 联合阿帕替尼治疗晚期非小细胞肺癌的 II 期研究",
            "H006": "SHR-1210 联合法米替尼或安慰剂加化疗治疗非鳞状非小细胞肺癌的 III 期研究",
            "H007": "法米替尼联合多西他赛治疗晚期非小细胞肺癌的临床研究",
            "H013": "恒瑞医药投资者演示材料中与 NSCLC、SHR-A1811 和 SHR-A2009 相关的管线信息",
            "H014": "瑞康曲妥珠单抗用于 HER2（ERBB2）激活突变既往经治不可切除局部晚期或转移性非小细胞肺癌成人患者的药品注册批准公告",
        }
        for source_id, title in expected_titles.items():
            self.assertEqual(rows[source_id]["normalized_title_zh"], title)


if __name__ == "__main__":
    unittest.main()
