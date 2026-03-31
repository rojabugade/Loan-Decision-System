import re
from typing import Any

from app.agents.base import BaseAgent
from app.schemas.common import AgentResult


class MetricExtractorAgent(BaseAgent):
    name = "metric_extractor"

    @staticmethod
    def _to_number(raw: str) -> float:
        normalized = raw.replace(",", "").replace("$", "").strip()
        return float(normalized)

    def _extract_from_documents(self, request) -> tuple[dict[str, float | int | None], dict[str, list[str]]]:
        patterns = {
            "annual_revenue": [r"annual\s+(income|revenue)\s*[:\-]?\s*\$?([\d,]+(?:\.\d+)?)"],
            "net_income": [r"net\s+income\s*[:\-]?\s*\$?([\d,]+(?:\.\d+)?)"],
            "debt_service_coverage_ratio": [r"\bdscr\b\s*[:\-]?\s*([\d.]+)"],
            "debt_to_income_ratio": [r"debt\s*[- ]?to\s*[- ]?income\s*ratio\s*[:\-]?\s*([\d.]+)"],
            "credit_score": [r"credit\s+score\s*[:\-]?\s*([\d]{3})"],
            "existing_debt": [r"existing\s+debt\s*[:\-]?\s*\$?([\d,]+(?:\.\d+)?)"],
            "requested_amount": [r"loan\s+amount\s+requested\s*[:\-]?\s*\$?([\d,]+(?:\.\d+)?)"],
        }

        extracted: dict[str, float | int | None] = {k: None for k in patterns}
        evidence_map: dict[str, list[str]] = {}

        for doc in request.uploaded_documents:
            text = (doc.content or "").lower()
            if not text or text.startswith("[binary_document:"):
                continue

            for field, field_patterns in patterns.items():
                if extracted[field] is not None:
                    continue

                for pattern in field_patterns:
                    match = re.search(pattern, text)
                    if not match:
                        continue

                    value_str = match.group(2) if field == "annual_revenue" and len(match.groups()) > 1 else match.group(1)
                    if field == "credit_score":
                        extracted[field] = int(value_str)
                    else:
                        extracted[field] = self._to_number(value_str)

                    evidence_map[field] = [f"doc:{doc.doc_id}"]
                    break

        return extracted, evidence_map

    def run(self, state: dict[str, Any]) -> AgentResult:
        request = state["request"]
        applicant = request.applicant_data
        applicant_payload = applicant.model_dump()

        parsed_metrics, parsed_evidence = self._extract_from_documents(request)

        metrics: dict[str, float | int | None] = {
            "annual_revenue": applicant.annual_revenue if applicant.annual_revenue is not None else parsed_metrics["annual_revenue"],
            "net_income": applicant.net_income if applicant.net_income is not None else parsed_metrics["net_income"],
            "debt_service_coverage_ratio": (
                applicant.debt_service_coverage_ratio
                if applicant.debt_service_coverage_ratio is not None
                else parsed_metrics["debt_service_coverage_ratio"]
            ),
            "debt_to_income_ratio": (
                applicant.debt_to_income_ratio
                if applicant.debt_to_income_ratio is not None
                else parsed_metrics["debt_to_income_ratio"]
            ),
            "credit_score": applicant.credit_score if applicant.credit_score is not None else parsed_metrics["credit_score"],
            "existing_debt": applicant.existing_debt if applicant.existing_debt is not None else parsed_metrics["existing_debt"],
            "requested_amount": applicant.requested_amount if applicant.requested_amount is not None else parsed_metrics["requested_amount"],
        }

        evidence_map: dict[str, list[str]] = {}
        for key, value in metrics.items():
            if value is not None:
                if key in parsed_evidence and applicant_payload.get(key) is None:
                    evidence_map[key] = parsed_evidence[key]
                else:
                    evidence_map[key] = ["applicant_data"]

        missing = [key for key, value in metrics.items() if value is None]

        return AgentResult(
            payload={
                "metrics": metrics,
                "metric_evidence_map": evidence_map,
            },
            missing_information=missing,
        )
