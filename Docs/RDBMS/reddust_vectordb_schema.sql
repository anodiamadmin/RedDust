-- ============================================================================
-- RAG KNOWLEDGE BASE
-- ============================================================================

-- Stores embedded knowledge chunks for RAG retrieval.
-- content_hash is a generated MD5 column used for deduplication — raw content
-- cannot be btree-indexed when chunks exceed ~2704 bytes (Postgres limit).
CREATE TABLE IF NOT EXISTS anodiam_knowledge (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain       TEXT NOT NULL,
    content      TEXT NOT NULL,
    content_hash TEXT GENERATED ALWAYS AS (md5(content)) STORED,
    embedding    VECTOR(1536),
    metadata     JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT anodiam_knowledge_domain_content_hash_key UNIQUE (domain, content_hash)
);

CREATE INDEX IF NOT EXISTS ix_anodiam_knowledge_domain
    ON anodiam_knowledge (domain);