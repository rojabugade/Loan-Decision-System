from typing import Any

from app.agents.base import BaseAgent
from app.core.config import settings
from app.retrieval.hybrid import HybridRetrievalEngine
from app.schemas.common import AgentResult


class EvidenceRetrievalAgent(BaseAgent):
    name = "evidence_retrieval"

    def __init__(self, retrieval_engine: HybridRetrievalEngine):
        self.retrieval_engine = retrieval_engine

    def run(self, state: dict[str, Any]) -> AgentResult:
        request = state["request"]
        metrics = state.get("metrics", {})
        query = (
            f"credit case {request.case_id} metrics "
            + " ".join([f"{k}:{v}" for k, v in metrics.items() if v is not None])
        ).strip()

        retrieval_result = self.retrieval_engine.retrieve(
            query=query,
            borrower_documents=request.uploaded_documents,
            policy_documents=request.policy_corpus,
            regulatory_documents=request.regulatory_corpus,
            metadata_filters=request.metadata_filters,
            top_k=settings.retrieval_top_k,
        )

        missing = []
        if not retrieval_result.citations:
            missing.append("policy_or_regulatory_evidence_unavailable")
        if request.uploaded_documents and retrieval_result.borrower_citation_count == 0:
            missing.append("borrower_document_evidence_unavailable")

        return AgentResult(
            payload={
                "citations": [c.model_dump() for c in retrieval_result.citations],
                "retrieval_run_id": retrieval_result.retrieval_run_id,
                "retrieval_cache_hit": retrieval_result.cache_hit,
                "borrower_evidence_count": retrieval_result.borrower_citation_count,
                "policy_evidence_count": retrieval_result.policy_citation_count,
            },
            missing_information=missing,
        )
