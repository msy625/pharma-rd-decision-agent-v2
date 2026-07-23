import os
import sys
import threading
import unittest
from unittest.mock import patch

from deepinsight.core.grounded_qa_usage_guard import (
    DEFAULT_GLOBAL_LIMIT,
    DEFAULT_MAX_CONCURRENCY,
    DEFAULT_PER_CLIENT_LIMIT,
    DEFAULT_WINDOW_SECONDS,
    GroundedQAUsageConfig,
    GroundedQAUsageGuard,
    grounded_qa_usage_config_from_env,
)


class FakeClock:
    def __init__(self, value=1000.0):
        self.value = value

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


class GroundedQAUsageGuardTest(unittest.TestCase):
    def test_01_default_config_is_safely_disabled(self):
        with patch.dict(os.environ, {}, clear=True):
            config = grounded_qa_usage_config_from_env()
        self.assertFalse(config.llm_enabled)
        self.assertEqual(config.per_client_limit, DEFAULT_PER_CLIENT_LIMIT)
        self.assertEqual(config.global_limit, DEFAULT_GLOBAL_LIMIT)
        self.assertEqual(config.window_seconds, DEFAULT_WINDOW_SECONDS)
        self.assertEqual(config.max_concurrency, DEFAULT_MAX_CONCURRENCY)

    def test_02_enabled_accepts_only_explicit_true_values(self):
        for value in ["true", "TRUE", "1", "yes", "on"]:
            with self.subTest(value=value), patch.dict(os.environ, {"GROUNDED_QA_LLM_ENABLED": value}, clear=True):
                self.assertTrue(grounded_qa_usage_config_from_env().llm_enabled)
        for value in ["false", "0", "enabled", ""]:
            with self.subTest(value=value), patch.dict(os.environ, {"GROUNDED_QA_LLM_ENABLED": value}, clear=True):
                self.assertFalse(grounded_qa_usage_config_from_env().llm_enabled)

    def test_03_invalid_numeric_config_falls_back_to_defaults(self):
        with patch.dict(
            os.environ,
            {
                "GROUNDED_QA_LLM_PER_CLIENT_LIMIT": "0",
                "GROUNDED_QA_LLM_GLOBAL_LIMIT": "100000",
                "GROUNDED_QA_LLM_WINDOW_SECONDS": "bad",
                "GROUNDED_QA_LLM_MAX_CONCURRENCY": "-2",
            },
            clear=True,
        ):
            config = grounded_qa_usage_config_from_env()
        self.assertEqual(config.per_client_limit, DEFAULT_PER_CLIENT_LIMIT)
        self.assertEqual(config.global_limit, DEFAULT_GLOBAL_LIMIT)
        self.assertEqual(config.window_seconds, DEFAULT_WINDOW_SECONDS)
        self.assertEqual(config.max_concurrency, DEFAULT_MAX_CONCURRENCY)

    def test_04_per_client_limit_returns_retry_after(self):
        clock = FakeClock()
        guard = GroundedQAUsageGuard(
            GroundedQAUsageConfig(True, per_client_limit=1, global_limit=10, window_seconds=120, max_concurrency=2),
            clock=clock,
        )
        first = guard.acquire("client-a")
        guard.release(first)
        second = guard.acquire("client-a")
        self.assertFalse(second.allowed)
        self.assertEqual(second.reason, "per_client_limit")
        self.assertGreaterEqual(second.retry_after, 1)

    def test_05_global_limit_returns_retry_after(self):
        clock = FakeClock()
        guard = GroundedQAUsageGuard(
            GroundedQAUsageConfig(True, per_client_limit=10, global_limit=1, window_seconds=120, max_concurrency=2),
            clock=clock,
        )
        first = guard.acquire("client-a")
        guard.release(first)
        second = guard.acquire("client-b")
        self.assertFalse(second.allowed)
        self.assertEqual(second.reason, "global_limit")
        self.assertGreaterEqual(second.retry_after, 1)

    def test_06_concurrency_limit_and_release(self):
        guard = GroundedQAUsageGuard(
            GroundedQAUsageConfig(True, per_client_limit=10, global_limit=10, window_seconds=120, max_concurrency=1)
        )
        first = guard.acquire("client-a")
        self.assertTrue(first.allowed)
        blocked = guard.acquire("client-b")
        self.assertFalse(blocked.allowed)
        self.assertEqual(blocked.reason, "concurrency_limit")
        guard.release(first)
        allowed = guard.acquire("client-b")
        self.assertTrue(allowed.allowed)
        guard.release(allowed)

    def test_07_window_expiry_restores_limits_and_prunes(self):
        clock = FakeClock()
        guard = GroundedQAUsageGuard(
            GroundedQAUsageConfig(True, per_client_limit=1, global_limit=10, window_seconds=60, max_concurrency=2),
            clock=clock,
        )
        first = guard.acquire("client-a")
        guard.release(first)
        self.assertFalse(guard.acquire("client-a").allowed)
        clock.advance(61)
        second = guard.acquire("client-a")
        self.assertTrue(second.allowed)
        guard.release(second)
        self.assertLessEqual(guard.snapshot()["client_window_count"], 1)

    def test_08_release_is_safe_after_exception_path(self):
        guard = GroundedQAUsageGuard(
            GroundedQAUsageConfig(True, per_client_limit=10, global_limit=10, window_seconds=120, max_concurrency=1)
        )
        decision = guard.acquire("client-a")
        try:
            raise RuntimeError("simulated")
        except RuntimeError:
            guard.release(decision)
        self.assertEqual(guard.snapshot()["in_flight"], 0)
        next_decision = guard.acquire("client-b")
        self.assertTrue(next_decision.allowed)
        guard.release(next_decision)

    def test_09_import_does_not_load_model_or_vector_modules(self):
        blocked = {"openai", "chromadb", "sentence_transformers", "torch"}
        before = {name for name in blocked if name in sys.modules}
        import deepinsight.core.grounded_qa_usage_guard  # noqa: F401

        after = {name for name in blocked if name in sys.modules}
        self.assertEqual(after - before, set())

    def test_10_guard_is_thread_safe(self):
        guard = GroundedQAUsageGuard(
            GroundedQAUsageConfig(True, per_client_limit=200, global_limit=200, window_seconds=120, max_concurrency=20)
        )
        decisions = []
        lock = threading.Lock()

        def worker(index):
            decision = guard.acquire(f"client-{index}")
            with lock:
                decisions.append(decision.allowed)
            guard.release(decision)

        threads = [threading.Thread(target=worker, args=(index,)) for index in range(25)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertTrue(any(decisions))
        self.assertEqual(guard.snapshot()["in_flight"], 0)


if __name__ == "__main__":
    unittest.main()
