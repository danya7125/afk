-- Таблица истории чатов МФЦ.
-- Приложение также создаёт её автоматически при запуске.

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
