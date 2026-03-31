from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Integer, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, SessionLocal
from app.core.logging import get_logger

logger = get_logger("pgvector_store")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    doc_id: Mapped[str] = mapped_column(String(128), index=True)
    source_type: Mapped[str] = mapped_column(String(32), index=True)
    jurisdiction: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    product_type: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    content: Mapped[str] = mapped_column(Text)


@dataclass
class RetrievedChunk:
    doc_id: str
    content: str
    source_type: str


class PgvectorStore:
    def __init__(self):
        self._enabled = True

    @property
    def enabled(self) -> bool:
        return self._enabled

    def retrieve_text_chunks(
        self,
        metadata_filters: dict[str, str],
        top_k: int,
    ) -> list[RetrievedChunk]:
        try:
            with SessionLocal() as session:
                stmt = select(DocumentChunk)
                jurisdiction = metadata_filters.get("jurisdiction")
                product_type = metadata_filters.get("product_type")

                if jurisdiction:
                    stmt = stmt.where(DocumentChunk.jurisdiction == jurisdiction)
                if product_type:
                    stmt = stmt.where(DocumentChunk.product_type == product_type)

                stmt = stmt.limit(top_k)
                rows = session.execute(stmt).scalars().all()
                return [
                    RetrievedChunk(doc_id=r.doc_id, content=r.content, source_type=r.source_type)
                    for r in rows
                ]
        except Exception as exc:
            logger.warning("pgvector_query_failed_fallback", error=str(exc))
            return []
