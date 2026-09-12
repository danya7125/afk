from __future__ import annotations

import json
from typing import Any

from ..db import get_connection

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS chat_history (
    id BIGSERIAL PRIMARY KEY,
    session_id UUID NOT NULL,
    category_id VARCHAR(100),
    category_name VARCHAR(255),
    service_id TEXT,
    service_name TEXT,
    user_message TEXT NOT NULL,
    ai_response TEXT NOT NULL,
    matched_services JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_chat_history_session_created
    ON chat_history (session_id, created_at, id);

CREATE INDEX IF NOT EXISTS idx_chat_history_session_category
    ON chat_history (session_id, category_id, created_at, id);
"""


class ChatHistoryRepository:
    def ensure_table(self) -> None:
        with get_connection() as conn:
            conn.execute(_CREATE_TABLE_SQL)

    def add(
        self,
        *,
        session_id: str,
        category_id: str | None,
        category_name: str | None,
        service_id: str | None,
        service_name: str | None,
        user_message: str,
        ai_response: str,
        matched_services: list[dict[str, Any]] | None = None,
    ) -> int:
        with get_connection() as conn:
            row = conn.execute(
                """
                INSERT INTO chat_history (
                    session_id,
                    category_id,
                    category_name,
                    service_id,
                    service_name,
                    user_message,
                    ai_response,
                    matched_services
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                RETURNING id
                """,
                (
                    session_id,
                    category_id,
                    category_name,
                    service_id,
                    service_name,
                    user_message,
                    ai_response,
                    json.dumps(matched_services or [], ensure_ascii=False),
                ),
            ).fetchone()
        if not row:
            raise RuntimeError("Не удалось сохранить историю чата")
        return int(row["id"])

    def list_for_session(
        self,
        session_id: str,
        *,
        category_id: str = "",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        params: list[Any] = [session_id]
        where = ["session_id = %s"]

        if category_id:
            where.append("category_id = %s")
            params.append(category_id)

        params.append(limit)
        with get_connection() as conn:
            rows = conn.execute(
                f"""
                SELECT
                    id,
                    session_id,
                    category_id,
                    category_name,
                    service_id,
                    service_name,
                    user_message,
                    ai_response,
                    matched_services,
                    created_at
                FROM chat_history
                WHERE {' AND '.join(where)}
                ORDER BY created_at ASC, id ASC
                LIMIT %s
                """,
                params,
            ).fetchall()

        return [dict(row) for row in rows]

    def clear_session(self, session_id: str, *, category_id: str = "") -> None:
        params: list[Any] = [session_id]
        where = ["session_id = %s"]

        if category_id:
            where.append("category_id = %s")
            params.append(category_id)

        with get_connection() as conn:
            conn.execute(
                f"DELETE FROM chat_history WHERE {' AND '.join(where)}",
                params,
            )
