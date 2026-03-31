from typing import Any

from app.agents.base import BaseAgent
from app.schemas.common import AgentResult
from app.schemas.output import DocumentClassification


class DocumentClassifierAgent(BaseAgent):
    name = "document_classifier"

    _mime_mapping = {
        "application/pdf": "FINANCIAL_STATEMENT",
        "text/csv": "BANK_TRANSACTION_EXPORT",
        "application/json": "STRUCTURED_FINANCIAL_DATA",
        "text/plain": "UNSTRUCTURED_MEMO",
    }

    def run(self, state: dict[str, Any]) -> AgentResult:
        documents = state["request"].uploaded_documents
        results: list[DocumentClassification] = []

        for doc in documents:
            content_l = doc.content.lower()
            detected_type = self._mime_mapping.get(doc.mime_type or "", "UNKNOWN")
            if "balance sheet" in content_l or "income statement" in content_l:
                detected_type = "FINANCIAL_STATEMENT"
            elif "bureau" in content_l or "credit report" in content_l:
                detected_type = "CREDIT_REPORT"
            elif "tax" in content_l:
                detected_type = "TAX_RETURN"

            results.append(
                DocumentClassification(
                    doc_id=doc.doc_id,
                    document_type=detected_type,
                    evidence_ids=[f"doc:{doc.doc_id}"],
                )
            )

        missing = []
        if not results:
            missing.append("uploaded_documents")

        return AgentResult(payload={"document_classifications": [r.model_dump() for r in results]}, missing_information=missing)
