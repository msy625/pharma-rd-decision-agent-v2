import threading
import unittest
from unittest.mock import Mock, patch

import deepinsight.core.cache_tools as cache_tools
from deepinsight.core.cache_tools import SemanticCache
from deepinsight.core.ui_common import render_html_component


class _FakeEmbedding:
    def tolist(self):
        return [1.0, 0.0, 0.0]


class _FakeModel:
    def encode(self, text, normalize_embeddings=True):
        return _FakeEmbedding()


class _FakeClient:
    def get_or_create_collection(self, name, metadata):
        return Mock()


class StartupAndComponentTests(unittest.TestCase):
    def test_semantic_cache_constructor_does_not_load_sentence_transformer(self):
        with patch("deepinsight.core.cache_tools.importlib.import_module") as import_module:
            cache = SemanticCache()

        import_module.assert_not_called()
        self.assertIsNone(cache.model)
        self.assertIsNone(cache.collection)

    def test_semantic_cache_loads_model_once_for_concurrent_embedding(self):
        fake_module = Mock()
        fake_module.SentenceTransformer.side_effect = lambda model_name: _FakeModel()
        cache = SemanticCache()

        fake_chromadb = Mock()
        fake_chromadb.EphemeralClient.return_value = _FakeClient()
        original_chromadb = cache_tools.chromadb
        cache_tools.chromadb = fake_chromadb
        try:
            with patch("deepinsight.core.cache_tools.importlib.import_module", return_value=fake_module):
                threads = [threading.Thread(target=cache._embed, args=(f"query-{index}",)) for index in range(8)]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join()
        finally:
            cache_tools.chromadb = original_chromadb

        fake_module.SentenceTransformer.assert_called_once_with("all-MiniLM-L6-v2")

    def test_render_html_component_falls_back_to_caption(self):
        with patch("deepinsight.core.ui_common.components.html", side_effect=RuntimeError("boom")), patch("deepinsight.core.ui_common.st.caption") as caption:
            result = render_html_component("<script></script>", fallback_text="组件不可用")

        self.assertIsNone(result)
        caption.assert_called_once_with("组件不可用")


if __name__ == "__main__":
    unittest.main()
