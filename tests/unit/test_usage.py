"""Unit tests for usage logging and token-cost aggregation."""

import unittest
from datetime import datetime, timedelta, timezone

from app.services.usage import (
    InMemoryUsageStore,
    aggregate_usage_by_step,
    get_usage_summary,
    log_ai_call,
    log_tool_call,
)


class UsageLoggingTests(unittest.TestCase):
    def setUp(self):
        self.store = InMemoryUsageStore()
        self.base_time = datetime(2026, 10, 10, 12, 0, 0, tzinfo=timezone.utc)

    def test_log_ai_call_records_tokens(self):
        entry = log_ai_call(
            self.store,
            step="tagging",
            model="nemotron-nano",
            prompt_tokens=450,
            completion_tokens=80,
            user_id="user-1",
            role="faculty",
            latency_ms=120,
        )
        self.assertEqual(entry.kind, "ai_call")
        self.assertEqual(entry.step, "tagging")
        self.assertEqual(entry.prompt_tokens, 450)
        self.assertEqual(entry.completion_tokens, 80)
        self.assertEqual(entry.total_tokens, 530)
        self.assertEqual(len(self.store.entries), 1)

    def test_log_tool_call_records_tool_name(self):
        entry = log_tool_call(
            self.store,
            tool_name="find_weak_COs",
            step="agent",
            user_id="user-1",
            role="faculty",
            args={"subject_id": "subj-1"},
            result_summary="Identified CO3 below target",
        )
        self.assertEqual(entry.kind, "tool_call")
        self.assertEqual(entry.tool_name, "find_weak_COs")
        self.assertEqual(entry.total_tokens, 0)
        self.assertEqual(len(self.store.entries), 1)

    def test_aggregate_usage_by_step(self):
        # 2 tagging calls
        log_ai_call(self.store, step="tagging", model="nano", prompt_tokens=100, completion_tokens=20)
        log_ai_call(self.store, step="tagging", model="nano", prompt_tokens=200, completion_tokens=30)
        # 1 generation call
        log_ai_call(self.store, step="generation", model="super", prompt_tokens=500, completion_tokens=150)
        # 2 agent tool calls
        log_tool_call(self.store, tool_name="schedule_event", step="agent")
        log_tool_call(self.store, tool_name="list_events", step="agent")

        summaries = aggregate_usage_by_step(self.store.entries)
        by_step = {s.step: s for s in summaries}

        self.assertEqual(by_step["generation"].calls, 1)
        self.assertEqual(by_step["generation"].total_tokens, 650)

        self.assertEqual(by_step["tagging"].calls, 2)
        self.assertEqual(by_step["tagging"].prompt_tokens, 300)
        self.assertEqual(by_step["tagging"].completion_tokens, 50)
        self.assertEqual(by_step["tagging"].total_tokens, 350)

        self.assertEqual(by_step["agent"].calls, 2)
        self.assertEqual(by_step["agent"].total_tokens, 0)

    def test_get_usage_summary_with_time_filter(self):
        t1 = self.base_time
        t2 = self.base_time + timedelta(hours=2)
        t3 = self.base_time + timedelta(days=2)

        log_ai_call(self.store, step="qa", model="super", prompt_tokens=50, completion_tokens=20, created_at=t1)
        log_ai_call(self.store, step="qa", model="super", prompt_tokens=60, completion_tokens=30, created_at=t2)
        log_ai_call(self.store, step="qa", model="super", prompt_tokens=100, completion_tokens=50, created_at=t3)

        # Query only within the first day
        summary = get_usage_summary(
            self.store,
            from_time=self.base_time - timedelta(minutes=10),
            to_time=self.base_time + timedelta(days=1),
        )
        self.assertEqual(len(summary), 1)
        self.assertEqual(summary[0]["calls"], 2)
        self.assertEqual(summary[0]["total_tokens"], 160)


if __name__ == "__main__":
    unittest.main()

