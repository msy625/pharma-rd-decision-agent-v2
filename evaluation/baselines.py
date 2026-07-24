"""Reproducible offline baselines using the production-service adapters."""

from __future__ import annotations

from time import perf_counter
from typing import Any, Callable

from evaluation.adapters import NormalizedResult, ProductionServiceAdapters, RESULT_FIELDS


BASELINE_NAMES = ["keyword_contains", "structured_no_chain", "grounded_qa_local"]


class OfflineBaseline:
    def __init__(self, name: str, operation: Callable[[dict[str, Any]], NormalizedResult]) -> None:
        self.name = name
        self.operation = operation

    def run(self, case: dict[str, Any]) -> dict[str, Any]:
        started = perf_counter()
        try:
            result = self.operation(case)
        except Exception as exc:  # The runner records a case-level failure instead of aborting the suite.
            result = NormalizedResult(error=f"{type(exc).__name__}: {exc}")
        result.latency_ms = (perf_counter() - started) * 1000
        payload = result.to_dict()
        if list(payload) != RESULT_FIELDS:
            raise RuntimeError("Normalized baseline result protocol changed unexpectedly")
        return payload


def build_baselines(
    adapters: ProductionServiceAdapters | None = None,
    names: list[str] | None = None,
) -> list[OfflineBaseline]:
    adapters = adapters or ProductionServiceAdapters()
    operations = {
        "keyword_contains": adapters.keyword_contains,
        "structured_no_chain": adapters.structured_no_chain,
        "grounded_qa_local": adapters.grounded_qa_local,
    }
    selected = names or BASELINE_NAMES
    unknown = [name for name in selected if name not in operations]
    if unknown:
        raise ValueError(f"Unknown baselines: {', '.join(unknown)}")
    return [OfflineBaseline(name, operations[name]) for name in selected]
