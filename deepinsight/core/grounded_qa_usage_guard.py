"""In-process usage guard for public grounded QA LLM calls.

This module is intentionally dependency-light. It does not import OpenAI,
Chroma, model runtimes, or legacy app modules.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
import threading
import time
from typing import Callable


DEFAULT_LLM_ENABLED = False
DEFAULT_PER_CLIENT_LIMIT = 5
DEFAULT_GLOBAL_LIMIT = 30
DEFAULT_WINDOW_SECONDS = 600
DEFAULT_MAX_CONCURRENCY = 2

MIN_LIMIT = 1
MAX_LIMIT = 1_000
MIN_WINDOW_SECONDS = 60
MAX_WINDOW_SECONDS = 86_400
MIN_CONCURRENCY = 1
MAX_CONCURRENCY = 20
ANONYMOUS_CLIENT_ID = "anonymous"

_TRUE_VALUES = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class GroundedQAUsageConfig:
    llm_enabled: bool = DEFAULT_LLM_ENABLED
    per_client_limit: int = DEFAULT_PER_CLIENT_LIMIT
    global_limit: int = DEFAULT_GLOBAL_LIMIT
    window_seconds: int = DEFAULT_WINDOW_SECONDS
    max_concurrency: int = DEFAULT_MAX_CONCURRENCY


@dataclass(frozen=True)
class UsageDecision:
    allowed: bool
    reason: str = ""
    retry_after: int = 0
    permit_acquired: bool = False


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in _TRUE_VALUES


def _bounded_int_env(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name)
    try:
        value = int(str(raw).strip()) if raw is not None else default
    except (TypeError, ValueError):
        return default
    if value < minimum or value > maximum:
        return default
    return value


def grounded_qa_usage_config_from_env() -> GroundedQAUsageConfig:
    """Read non-secret usage guard settings with safe defaults."""
    return GroundedQAUsageConfig(
        llm_enabled=_bool_env("GROUNDED_QA_LLM_ENABLED", DEFAULT_LLM_ENABLED),
        per_client_limit=_bounded_int_env(
            "GROUNDED_QA_LLM_PER_CLIENT_LIMIT",
            DEFAULT_PER_CLIENT_LIMIT,
            MIN_LIMIT,
            MAX_LIMIT,
        ),
        global_limit=_bounded_int_env(
            "GROUNDED_QA_LLM_GLOBAL_LIMIT",
            DEFAULT_GLOBAL_LIMIT,
            MIN_LIMIT,
            MAX_LIMIT,
        ),
        window_seconds=_bounded_int_env(
            "GROUNDED_QA_LLM_WINDOW_SECONDS",
            DEFAULT_WINDOW_SECONDS,
            MIN_WINDOW_SECONDS,
            MAX_WINDOW_SECONDS,
        ),
        max_concurrency=_bounded_int_env(
            "GROUNDED_QA_LLM_MAX_CONCURRENCY",
            DEFAULT_MAX_CONCURRENCY,
            MIN_CONCURRENCY,
            MAX_CONCURRENCY,
        ),
    )


class GroundedQAUsageGuard:
    """Thread-safe fixed-window limits plus a process-wide concurrency cap."""

    def __init__(
        self,
        config: GroundedQAUsageConfig | None = None,
        *,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.config = config or grounded_qa_usage_config_from_env()
        self._clock = clock or time.monotonic
        self._lock = threading.Lock()
        self._client_windows: dict[str, tuple[float, int]] = {}
        self._global_window: tuple[float, int] | None = None
        self._in_flight = 0

    def acquire(self, client_id: str | None) -> UsageDecision:
        client_key = self._client_key(client_id)
        now = self._clock()
        with self._lock:
            self._prune_expired(now)
            if self._in_flight >= self.config.max_concurrency:
                return UsageDecision(False, "concurrency_limit", retry_after=1)

            global_start, global_count = self._active_global_window(now)
            if global_count >= self.config.global_limit:
                return UsageDecision(
                    False,
                    "global_limit",
                    retry_after=self._retry_after(now, global_start),
                )

            client_start, client_count = self._active_client_window(client_key, now)
            if client_count >= self.config.per_client_limit:
                return UsageDecision(
                    False,
                    "per_client_limit",
                    retry_after=self._retry_after(now, client_start),
                )

            self._client_windows[client_key] = (client_start, client_count + 1)
            self._global_window = (global_start, global_count + 1)
            self._in_flight += 1
            return UsageDecision(True, permit_acquired=True)

    def release(self, decision: UsageDecision | None) -> None:
        if not decision or not decision.permit_acquired:
            return
        with self._lock:
            self._in_flight = max(0, self._in_flight - 1)

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return {
                "client_window_count": len(self._client_windows),
                "in_flight": self._in_flight,
            }

    @staticmethod
    def _client_key(client_id: str | None) -> str:
        text = str(client_id or "").strip()
        return text or ANONYMOUS_CLIENT_ID

    def _active_global_window(self, now: float) -> tuple[float, int]:
        if self._global_window is None:
            return now, 0
        start, count = self._global_window
        if now - start >= self.config.window_seconds:
            return now, 0
        return start, count

    def _active_client_window(self, client_key: str, now: float) -> tuple[float, int]:
        start, count = self._client_windows.get(client_key, (now, 0))
        if now - start >= self.config.window_seconds:
            return now, 0
        return start, count

    def _retry_after(self, now: float, window_start: float) -> int:
        remaining = self.config.window_seconds - int(now - window_start)
        return max(1, remaining)

    def _prune_expired(self, now: float) -> None:
        expired = [
            client_key
            for client_key, (start, _count) in self._client_windows.items()
            if now - start >= self.config.window_seconds
        ]
        for client_key in expired:
            self._client_windows.pop(client_key, None)
        if self._global_window and now - self._global_window[0] >= self.config.window_seconds:
            self._global_window = None
