from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass

from app.core.cache import RedisCache
from app.core.config import settings
from app.core.logging import get_logger
from app.retrieval.pgvector_store import PgvectorStore
from app.schemas.common import Citation
from app.schemas.input import PolicyDocument, UploadedDocument

logger = get_logger("retrieval")


@dataclass
class RetrievalResult:
    retrieval_run_id: str
    citations: list[Citation]
    cache_hit: bool = False
    borrower_citation_count: int = 0
    policy_citation_count: int = 0


class HybridRetrievalEngine:
    """
    MVP retrieval abstraction with pgvector-ready shape.

    In production this class should:
    - run vector similarity on pgvector indexed chunks
    - apply metadata filters in SQL
    - rerank candidates with a cross-encoder
    """

    def __init__(self, cache: RedisCache | None = None, pgvector_store: PgvectorStore | None = None):
        self.cache = cache
        self.pgvector_store = pgvector_store

    @staticmethod
    def _rank_score(query: str, content: str) -> float:
        query_tokens = set(query.lower().split())
        content_tokens = set(content.lower().split())
        if not query_tokens:
            return 0.0
        return len(query_tokens.intersection(content_tokens)) / len(query_tokens)

    @staticmethod
    def _cache_key(
        query: str,
        metadata_filters: dict[str, str],
        top_k: int,
        borrower_documents: list[UploadedDocument],
    ) -> str:
        borrower_signature = [
            {
                "doc_id": d.doc_id,
                "file_name": d.file_name,
                "mime_type": d.mime_type,
                "content_hash": hashlib.sha256((d.content or "").encode("utf-8")).hexdigest()[:12],
            }
            for d in borrower_documents
        ]
        material = {
            "query": query,
            "metadata_filters": metadata_filters,
            "top_k": top_k,
            "borrower_signature": borrower_signature,
        }
        raw = json.dumps(material, sort_keys=True)
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]
        return f"retrieval:{digest}"

    def retrieve(
        self,
        query: str,
        borrower_documents: list[UploadedDocument],
        policy_documents: list[PolicyDocument],
        regulatory_documents: list[PolicyDocument],
        metadata_filters: dict[str, str],
        top_k: int = 8,
    ) -> RetrievalResult:
        cache_key = self._cache_key(query, metadata_filters, top_k, borrower_documents)

        if self.cache:
            cached = self.cache.get_json(cache_key)
            if cached:
                citations = [Citation(**c) for c in cached.get("citations", [])]
                return RetrievalResult(
                    retrieval_run_id=cached.get("retrieval_run_id", f"retr_{uuid.uuid4().hex[:12]}"),
                    citations=citations,
                    cache_hit=True,
                    borrower_citation_count=cached.get("borrower_citation_count", 0),
                    policy_citation_count=cached.get("policy_citation_count", len(citations)),
                )

        corpus = [*policy_documents, *regulatory_documents]

        filtered = []
        for doc in corpus:
            jurisdiction = metadata_filters.get("jurisdiction")
            product_type = metadata_filters.get("product_type")
            if jurisdiction and doc.jurisdiction and doc.jurisdiction != jurisdiction:
                continue
            if product_type and doc.product_type and doc.product_type != product_type:
                continue
            filtered.append(doc)

        # Primary: corpus-based retrieval in MVP API payload.
        ranked_docs = sorted(
            filtered,
            key=lambda d: self._rank_score(query, d.content),
            reverse=True,
        )

        # Secondary: database retrieval via pgvector-ready store when available.
        extra_chunks = []
        if self.pgvector_store:
            extra_chunks = self.pgvector_store.retrieve_text_chunks(
                metadata_filters=metadata_filters,
                top_k=max(top_k - len(ranked_docs), 0),
            )

        # Borrower documents are always considered retrieval candidates.
        borrower_ranked = sorted(
            borrower_documents,
            key=lambda d: self._rank_score(query, d.content or ""),
            reverse=True,
        )

        selected = ranked_docs[:top_k]
        citations = []
        borrower_citation_count = 0
        policy_citation_count = 0

        # Add borrower citations first to guarantee case-evidence grounding in final panel.
        for idx, doc in enumerate(borrower_ranked[: min(3, top_k)], start=1):
            if not doc.content:
                continue
            excerpt = doc.content[:400]
            excerpt_hash = hashlib.sha256(excerpt.encode("utf-8")).hexdigest()[:16]
            citations.append(
                Citation(
                    citation_id=f"cit_borrower_{idx}",
                    doc_id=doc.doc_id,
                    location="borrower_doc:0-400",
                    excerpt_hash=excerpt_hash,
                )
            )
            borrower_citation_count += 1

        for idx, doc in enumerate(selected, start=1):
            excerpt = doc.content[:400]
            excerpt_hash = hashlib.sha256(excerpt.encode("utf-8")).hexdigest()[:16]
            citations.append(
                Citation(
                    citation_id=f"cit_{idx}",
                    doc_id=doc.doc_id,
                    location="content:0-400",
                    excerpt_hash=excerpt_hash,
                )
            )
            policy_citation_count += 1

        base_idx = len(citations)
        for idx, chunk in enumerate(extra_chunks, start=1):
            excerpt = chunk.content[:400]
            excerpt_hash = hashlib.sha256(excerpt.encode("utf-8")).hexdigest()[:16]
            citations.append(
                Citation(
                    citation_id=f"cit_db_{base_idx + idx}",
                    doc_id=chunk.doc_id,
                    location="db_chunk:0-400",
                    excerpt_hash=excerpt_hash,
                )
            )

        retrieval_run_id = f"retr_{uuid.uuid4().hex[:12]}"

        if self.cache and citations:
            self.cache.set_json(
                key=cache_key,
                value={
                    "retrieval_run_id": retrieval_run_id,
                    "citations": [c.model_dump() for c in citations],
                    "borrower_citation_count": borrower_citation_count,
                    "policy_citation_count": policy_citation_count,
                },
                ttl_seconds=settings.retrieval_cache_ttl_seconds,
            )

        logger.info(
            "retrieval_completed",
            retrieval_run_id=retrieval_run_id,
            cache_used=bool(self.cache),
            citation_count=len(citations),
            borrower_citation_count=borrower_citation_count,
            policy_citation_count=policy_citation_count,
        )

        return RetrievalResult(
            retrieval_run_id=retrieval_run_id,
            citations=citations,
            borrower_citation_count=borrower_citation_count,
            policy_citation_count=policy_citation_count,
        )
