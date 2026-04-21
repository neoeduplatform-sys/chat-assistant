-- ============================================================================
-- Migration 003: Conversation Memory (3-layer model)
-- ============================================================================
-- Purpose: Persist chat history (layer A) and rolling summaries (layer B)
-- scoped by (user_id, course_id). Layer C (RAG) is unchanged.
--
-- Idempotent: safe to re-run. Drops nothing, only creates IF NOT EXISTS.
--
-- Run in Supabase SQL Editor (or via your migration runner).
-- ============================================================================


-- ----------------------------------------------------------------------------
-- 1. chat_conversations
-- ----------------------------------------------------------------------------
-- One active thread per (user_id, course_id).

CREATE TABLE IF NOT EXISTS public.chat_conversations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     TEXT NOT NULL,
    course_id   TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chat_conversations_user_course_unique UNIQUE (user_id, course_id)
);

CREATE INDEX IF NOT EXISTS idx_chat_conversations_user_course
    ON public.chat_conversations (user_id, course_id);


-- ----------------------------------------------------------------------------
-- 2. chat_messages
-- ----------------------------------------------------------------------------
-- Literal user/assistant messages for a conversation, chronological.

CREATE TABLE IF NOT EXISTS public.chat_messages (
    id              BIGSERIAL PRIMARY KEY,
    conversation_id UUID NOT NULL REFERENCES public.chat_conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL,
    content         TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chat_messages_role_check CHECK (role IN ('user', 'assistant'))
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_conversation_created
    ON public.chat_messages (conversation_id, created_at DESC);


-- ----------------------------------------------------------------------------
-- 3. user_course_memory (layer B — rolling summary)
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.user_course_memory (
    user_id                         TEXT NOT NULL,
    course_id                       TEXT NOT NULL,
    summary                         TEXT NOT NULL DEFAULT '',
    message_count_at_last_summary   INTEGER NOT NULL DEFAULT 0,
    updated_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, course_id)
);


-- ----------------------------------------------------------------------------
-- 4. updated_at triggers
-- ----------------------------------------------------------------------------
-- Reuse update_updated_at_column() if migration 001 created it; create otherwise.

CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_chat_conversations_updated_at ON public.chat_conversations;
CREATE TRIGGER trg_chat_conversations_updated_at
    BEFORE UPDATE ON public.chat_conversations
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

DROP TRIGGER IF EXISTS trg_user_course_memory_updated_at ON public.user_course_memory;
CREATE TRIGGER trg_user_course_memory_updated_at
    BEFORE UPDATE ON public.user_course_memory
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


-- ----------------------------------------------------------------------------
-- 5. Atomic helper: fetch-or-create a conversation
-- ----------------------------------------------------------------------------
-- Returns the conversation row for (user_id, course_id), creating it if absent.
-- INSERT ... ON CONFLICT keeps this safe under concurrent first-turn requests.

CREATE OR REPLACE FUNCTION public.get_or_create_conversation(
    p_user_id   TEXT,
    p_course_id TEXT
)
RETURNS SETOF public.chat_conversations
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    INSERT INTO public.chat_conversations (user_id, course_id)
    VALUES (p_user_id, p_course_id)
    ON CONFLICT (user_id, course_id)
    DO UPDATE SET updated_at = NOW()
    RETURNING *;
END;
$$;


-- ----------------------------------------------------------------------------
-- 6. Permissions
-- ----------------------------------------------------------------------------

GRANT ALL ON public.chat_conversations   TO service_role, postgres;
GRANT ALL ON public.chat_messages        TO service_role, postgres;
GRANT ALL ON public.user_course_memory   TO service_role, postgres;
GRANT USAGE, SELECT ON SEQUENCE public.chat_messages_id_seq TO service_role, postgres;


-- ----------------------------------------------------------------------------
-- Done.
-- Verification:
--   SELECT COUNT(*) FROM public.chat_conversations;
--   SELECT COUNT(*) FROM public.chat_messages;
--   SELECT COUNT(*) FROM public.user_course_memory;
-- ----------------------------------------------------------------------------
