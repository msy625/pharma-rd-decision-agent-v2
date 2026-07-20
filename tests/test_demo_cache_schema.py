import re
import unittest

from deepinsight.demo.demo_cache import build_cache_payload, get_chat_cache


class DemoCacheSchemaTests(unittest.TestCase):
    def test_build_cache_payload_adds_source_metadata_from_result(self):
        result = {
            "sources": [{"type": "sql", "label": "结构化事实"}, {"type": "vector", "label": "年报切片"}],
            "sql_rows": [{"company_name": "甲公司"}],
            "chunks": [{"text": "chunk"}],
        }

        payload = build_cache_payload("chat", "case", result, question="q")

        self.assertEqual(payload["schema_version"], 2)
        self.assertEqual(payload["source_count"], 4)
        self.assertEqual(payload["source_types"], ["sql", "vector"])
        self.assertTrue(payload["is_cached"])
        self.assertRegex(payload["generated_at"], re.compile(r".*[+-]\d\d:\d\d$"))

    def test_old_cache_files_remain_readable(self):
        self.assertIsNone(get_chat_cache("__not_a_preset_question__"))


if __name__ == "__main__":
    unittest.main()
