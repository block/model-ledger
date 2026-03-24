"""FeedbackCorpus — query interface over observation feedback history."""

from __future__ import annotations

from collections import Counter
from typing import Any

from model_ledger.core.observations import FeedbackEvent


class FeedbackCorpus:
    def __init__(self, backend: Any) -> None:
        self._backend = backend

    def query(
        self,
        *,
        verdict: str | None = None,
        reason_code: str | None = None,
        observation_ref: str | None = None,
    ) -> list[FeedbackEvent]:
        events = self._backend.list_feedback_events()
        if verdict:
            events = [e for e in events if e.verdict == verdict]
        if reason_code:
            events = [e for e in events if e.reason_code == reason_code]
        if observation_ref:
            events = [e for e in events if e.observation_ref == observation_ref]
        return events

    def summary_stats(self) -> dict[str, Any]:
        events = self._backend.list_feedback_events()
        return {
            "total": len(events),
            "by_verdict": dict(Counter(e.verdict for e in events)),
            "by_reason_code": dict(Counter(e.reason_code for e in events)),
            "by_stage": dict(Counter(e.stage for e in events)),
        }
