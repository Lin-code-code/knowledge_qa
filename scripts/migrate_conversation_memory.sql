-- 企业级会话记忆迁移，重复执行安全。
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE TABLE IF NOT EXISTS conversation_topics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    topic_label VARCHAR(256) NOT NULL DEFAULT '服装咨询',
    summary TEXT NOT NULL DEFAULT '',
    last_intent VARCHAR(64),
    scope_label VARCHAR(16) NOT NULL DEFAULT 'IN',
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0,
    status VARCHAR(16) NOT NULL DEFAULT 'active',
    summary_version INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_topics_one_active
    ON conversation_topics (conversation_id)
    WHERE status = 'active';

CREATE INDEX IF NOT EXISTS idx_topics_conversation_status
    ON conversation_topics (conversation_id, status, updated_at DESC);

ALTER TABLE messages ADD COLUMN IF NOT EXISTS topic_id UUID;
ALTER TABLE messages ADD COLUMN IF NOT EXISTS turn_id UUID;
ALTER TABLE messages ADD COLUMN IF NOT EXISTS intent VARCHAR(64);
ALTER TABLE messages ADD COLUMN IF NOT EXISTS scope_label VARCHAR(16);
ALTER TABLE messages ADD COLUMN IF NOT EXISTS is_refusal BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE messages ADD COLUMN IF NOT EXISTS memory_eligible BOOLEAN NOT NULL DEFAULT TRUE;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_messages_topic_id'
    ) THEN
        ALTER TABLE messages
            ADD CONSTRAINT fk_messages_topic_id
            FOREIGN KEY (topic_id) REFERENCES conversation_topics(id) ON DELETE SET NULL;
    END IF;
END $$;

INSERT INTO conversation_topics (conversation_id, topic_label, status)
SELECT c.id, '历史会话', 'active'
FROM conversations c
WHERE NOT EXISTS (
    SELECT 1 FROM conversation_topics t WHERE t.conversation_id = c.id
);

UPDATE messages m
SET topic_id = t.id
FROM conversation_topics t
WHERE m.conversation_id = t.conversation_id
  AND m.topic_id IS NULL
  AND t.status = 'active';

WITH numbered AS (
    SELECT
        id,
        conversation_id,
        md5(
            conversation_id::text || ':' ||
            (((row_number() OVER (
                PARTITION BY conversation_id ORDER BY created_at, id
            ) - 1) / 2)::text)
        )::uuid AS generated_turn_id
    FROM messages
    WHERE turn_id IS NULL
)
UPDATE messages m
SET turn_id = n.generated_turn_id
FROM numbered n
WHERE m.id = n.id;

UPDATE messages
SET scope_label = COALESCE(scope_label, 'IN'),
    intent = COALESCE(intent, 'legacy'),
    is_refusal = CASE
        WHEN content LIKE '%暂无法回答该问题%' THEN TRUE
        ELSE is_refusal
    END,
    memory_eligible = CASE
        WHEN content LIKE '%暂无法回答该问题%' THEN FALSE
        ELSE memory_eligible
    END;

CREATE INDEX IF NOT EXISTS idx_messages_topic_turn_created
    ON messages (topic_id, turn_id, created_at DESC);

CREATE TABLE IF NOT EXISTS memory_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(64) NOT NULL,
    memory_type VARCHAR(32) NOT NULL DEFAULT 'preference',
    memory_key VARCHAR(64) NOT NULL,
    content TEXT NOT NULL,
    source_message_id BIGINT,
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0,
    expires_at TIMESTAMPTZ,
    status VARCHAR(16) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_memory_user_key UNIQUE (user_id, memory_key)
);

CREATE INDEX IF NOT EXISTS idx_memory_user_active
    ON memory_items (user_id, status, expires_at);
