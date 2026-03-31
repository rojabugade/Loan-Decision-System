CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS document_chunks (
    id BIGSERIAL PRIMARY KEY,
    doc_id VARCHAR(128) NOT NULL,
    source_type VARCHAR(32) NOT NULL,
    jurisdiction VARCHAR(32),
    product_type VARCHAR(64),
    content TEXT NOT NULL,
    embedding vector(1536)
);

CREATE INDEX IF NOT EXISTS idx_document_chunks_doc_id ON document_chunks (doc_id);
CREATE INDEX IF NOT EXISTS idx_document_chunks_scope ON document_chunks (jurisdiction, product_type, source_type);
CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding_cosine
    ON document_chunks
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
