import unittest

import deepinsight.dataops.graph_data_pipeline as graph_data_pipeline


class GraphDataPipelineTests(unittest.TestCase):
    def test_graph_pipeline_has_no_synthetic_generators(self):
        self.assertFalse(hasattr(graph_data_pipeline, "build_mock_hierarchy"))
        self.assertFalse(hasattr(graph_data_pipeline, "insert_mock_legal_risks"))
        self.assertFalse(hasattr(graph_data_pipeline, "insert_mock_patents"))
        self.assertFalse(hasattr(graph_data_pipeline, "Faker"))
        self.assertFalse(hasattr(graph_data_pipeline, "random"))


if __name__ == "__main__":
    unittest.main()
