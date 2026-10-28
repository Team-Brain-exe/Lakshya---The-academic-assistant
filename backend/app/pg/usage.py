"""UsageStore on Postgres: every AI call and tool call goes to agent_logs."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Sequence

from sqlalchemy import text

from ..services.usage import UsageEntry


class PostgresUsageStore:
    def __init__(self, conn: Any) -> None:
        self.conn = conn

    def record(self, entry: UsageEntry) -> None:
        self.conn.execute(
            text(
                "INSERT INTO agent_logs (user_id, role, kind, step, model, tool_name, "
                "prompt_tokens, completion_tokens, total_tokens, latency_ms, args, result_summary, error) "
                "VALUES (:uid, :role, :kind, :step, :model, :tool, :pt, :ct, :tt, :lat, "
                "CAST(:args AS jsonb), :res, :err)"
            ),
            {
                "uid": entry.user_id,
                "role": entry.role,
                "kind": entry.kind,
                "step": entry.step,
                "model": entry.model,
                "tool": entry.tool_name,
                "pt": entry.prompt_tokens,
                "ct": entry.completion_tokens,
                "tt": entry.total_tokens,
                "lat": entry.latency_ms,
                "args": json.dumps(entry.args) if entry.args is not None else None,
                "res": entry.result_summary,
                "err": entry.error,
            },
        )

    def list_entries(
        self, from_time: datetime | None = None, to_time: datetime | None = None
    ) -> Sequence[UsageEntry]:
        where, params = [], {}
        if from_time is not None:
            where.append("created_at >= :f")
            params["f"] = from_time
        if to_time is not None:
            where.append("created_at <= :t")
            params["t"] = to_time
        clause = (" WHERE " + " AND ".join(where)) if where else ""
        rows = self.conn.execute(
            text(
                "SELECT id, kind, step, user_id, role, model, tool_name, prompt_tokens, "
                "completion_tokens, total_tokens, latency_ms, result_summary, error, created_at "
                f"FROM agent_logs{clause}"
            ),
            params,
        ).mappings().fetchall()
        return [
            UsageEntry(
                id=str(r["id"]),
                kind=r["kind"],
                step=r["step"] or "other",
                user_id=str(r["user_id"]) if r["user_id"] else None,
                role=r["role"],
                model=r["model"],
                tool_name=r["tool_name"],
                prompt_tokens=r["prompt_tokens"] or 0,
                completion_tokens=r["completion_tokens"] or 0,
                total_tokens=r["total_tokens"] or 0,
                latency_ms=r["latency_ms"],
                result_summary=r["result_summary"],
                error=r["error"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    def summary(self, from_time: datetime | None = None, to_time: datetime | None = None) -> list[dict[str, Any]]:
        """Totals per step, computed in SQL so the cost page stays fast as the log grows."""
        where, params = [], {}
        if from_time is not None:
            where.append("created_at >= :f")
            params["f"] = from_time
        if to_time is not None:
            where.append("created_at <= :t")
            params["t"] = to_time
        clause = (" WHERE " + " AND ".join(where)) if where else ""
        rows = self.conn.execute(
            text(
                "SELECT COALESCE(step, 'other') AS step, count(*) AS calls, "
                "COALESCE(sum(prompt_tokens), 0) AS pt, COALESCE(sum(completion_tokens), 0) AS ct, "
                "COALESCE(sum(total_tokens), 0) AS tt "
                f"FROM agent_logs{clause} GROUP BY 1 ORDER BY tt DESC, step"
            ),
            params,
        ).fetchall()
        return [
            {
                "step": r[0],
                "calls": int(r[1]),
                "prompt_tokens": int(r[2]),
                "completion_tokens": int(r[3]),
                "total_tokens": int(r[4]),
            }
            for r in rows
        ]
