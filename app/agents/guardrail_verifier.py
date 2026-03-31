from typing import Any

from app.agents.base import BaseAgent
from app.schemas.common import AgentResult, Recommendation


class GuardrailVerifierAgent(BaseAgent):
    name = "guardrail_verifier"

    @staticmethod
    def _reason_for_field(field: str) -> str:
        reason_map = {
            "annual_revenue": "Income verification not found; affordability assessment cannot be validated.",
            "net_income": "Net income is unavailable; repayment surplus cannot be assessed.",
            "debt_service_coverage_ratio": "Debt obligations unavailable, DSCR cannot be computed.",
            "debt_to_income_ratio": "Debt-to-income ratio evidence missing; leverage policy cannot be evaluated.",
            "credit_score": "Credit bureau score not found; credit policy threshold cannot be tested.",
            "existing_debt": "Existing debt obligations unavailable; borrower leverage is incomplete.",
            "requested_amount": "Requested loan amount not found; policy comparators cannot be evaluated.",
            "uploaded_documents": "No borrower credit case documents were provided for extraction and validation.",
            "borrower_document_not_in_payload": "Borrower document was entered in UI but not included in backend payload.",
            "borrower_document_evidence_unavailable": "Borrower document existed but retrieval returned only policy evidence.",
            "policy_or_regulatory_evidence_unavailable": "No policy or regulatory evidence was retrieved.",
            "credit_score_unlinked_to_borrower_evidence": "Credit score could not be linked to a borrower document snippet.",
            "debt_to_income_unlinked_to_borrower_evidence": "Debt-to-income ratio could not be linked to a borrower document snippet.",
            "document_text_extraction": "Document uploaded but no usable text extracted.",
            "policy_rules": "No policy rules were provided, so compliance checks cannot be executed.",
        }
        return reason_map.get(field, f"Required underwriting evidence for {field} is missing.")

    @staticmethod
    def _actions_for_field(field: str) -> list[str]:
        action_map = {
            "annual_revenue": ["Collect income verification (pay stubs, tax return, bank statement)."],
            "net_income": ["Obtain a borrower financial statement with net income disclosure."],
            "debt_service_coverage_ratio": ["Collect monthly debt payment schedule to compute DSCR."],
            "debt_to_income_ratio": ["Obtain debt obligations and verified income to recompute DTI."],
            "credit_score": ["Pull a current credit bureau report and attach score evidence."],
            "existing_debt": ["Collect complete liabilities statement from borrower or bureau source."],
            "requested_amount": ["Confirm and document requested loan amount in application package."],
            "uploaded_documents": ["Request core case documents: application, financial statement, credit report."],
            "borrower_document_not_in_payload": ["Check UI request builder and confirm documents array is sent to API."],
            "borrower_document_evidence_unavailable": ["Inspect retrieval inputs; include borrower documents in retrieval corpus."],
            "policy_or_regulatory_evidence_unavailable": ["Attach policy/regulatory corpus and verify retrieval filters."],
            "credit_score_unlinked_to_borrower_evidence": ["Provide a bureau extract snippet containing credit score evidence."],
            "debt_to_income_unlinked_to_borrower_evidence": ["Provide a borrower financial statement snippet with DTI evidence."],
            "document_text_extraction": ["Re-upload machine-readable document or provide OCR output."],
            "policy_rules": ["Attach policy corpus with active underwriting rules before re-run."],
        }
        return action_map.get(field, [f"Provide validated evidence for {field} and re-run case."])

    def run(self, state: dict[str, Any]) -> AgentResult:
        claims = state.get("key_claims", [])
        citations = state.get("citations", [])
        citation_ids = {c["citation_id"] for c in citations}
        uncertainty_reasons = list(state.get("uncertainty_reasons", []))
        missing_information = list(state.get("missing_information", []))
        policy_checks = state.get("policy_checks", [])
        request = state.get("request")

        validation_errors: list[str] = []

        for claim in claims:
            evidence_ids = claim.get("evidence_ids", [])
            if not evidence_ids:
                validation_errors.append(f"Claim {claim.get('claim_id')} has no evidence_ids.")
                continue
            unknown_evidence = [ev for ev in evidence_ids if ev not in citation_ids and not ev.startswith("doc:") and ev != "applicant_data"]
            if unknown_evidence:
                validation_errors.append(
                    f"Claim {claim.get('claim_id')} references unknown evidence ids: {unknown_evidence}"
                )

        contradictory_flags = state.get("contradiction_flags", [])
        if contradictory_flags:
            uncertainty_reasons.append("Contradictory inputs detected in extracted metrics.")

        # Translate generic missing fields into analyst-readable operational blockers.
        blocking_map: dict[str, list[str]] = {}
        if request:
            for policy_doc in [*request.policy_corpus, *request.regulatory_corpus]:
                for rule in policy_doc.rules:
                    blocking_map.setdefault(rule.metric, []).append(rule.rule_id)

        missing_details: list[dict[str, Any]] = []
        for field in missing_information:
            missing_details.append(
                {
                    "field": field,
                    "reason": self._reason_for_field(field),
                    "blocking_rules": blocking_map.get(field, []),
                }
            )

        # If docs are uploaded but not parseable, make that explicit.
        if request and request.documents and not request.uploaded_documents:
            missing_details.append(
                {
                    "field": "borrower_document_not_in_payload",
                    "reason": self._reason_for_field("borrower_document_not_in_payload"),
                    "blocking_rules": [],
                }
            )

        if request and request.uploaded_documents:
            usable_docs = [
                d
                for d in request.uploaded_documents
                if d.content and not d.content.lower().startswith("[binary_document:")
            ]
            if not usable_docs:
                missing_details.append(
                    {
                        "field": "document_text_extraction",
                        "reason": self._reason_for_field("document_text_extraction"),
                        "blocking_rules": [],
                    }
                )

        # Include policy UNKNOWN checks as explicit blockers.
        for check in policy_checks:
            if check.get("status") == "UNKNOWN":
                missing_details.append(
                    {
                        "field": f"rule:{check.get('rule_id')}",
                        "reason": f"No evidence supporting policy rule {check.get('rule_id')}.",
                        "blocking_rules": [check.get("rule_id")],
                    }
                )

        metric_evidence_map = state.get("metric_evidence_map", {})
        if state.get("metrics", {}).get("credit_score") is not None and "credit_score" not in metric_evidence_map:
            missing_details.append(
                {
                    "field": "credit_score_unlinked_to_borrower_evidence",
                    "reason": self._reason_for_field("credit_score_unlinked_to_borrower_evidence"),
                    "blocking_rules": [],
                }
            )
        if state.get("metrics", {}).get("debt_to_income_ratio") is not None and "debt_to_income_ratio" not in metric_evidence_map:
            missing_details.append(
                {
                    "field": "debt_to_income_unlinked_to_borrower_evidence",
                    "reason": self._reason_for_field("debt_to_income_unlinked_to_borrower_evidence"),
                    "blocking_rules": [],
                }
            )

        # Deduplicate missing details by field + reason.
        dedup = {}
        for item in missing_details:
            key = f"{item['field']}::{item['reason']}"
            if key not in dedup:
                dedup[key] = item
        missing_details = list(dedup.values())

        analyst_next_actions: list[str] = []
        for item in missing_details:
            field = item["field"]
            base_field = field.replace("rule:", "") if field.startswith("rule:") else field
            if field.startswith("rule:"):
                analyst_next_actions.append(f"Collect evidence required to evaluate policy rule {base_field}.")
            else:
                analyst_next_actions.extend(self._actions_for_field(base_field))

        # Add standard control action when escalated.
        analyst_next_actions.append("Re-run case after evidence package is complete and policy checks are resolvable.")
        analyst_next_actions = list(dict.fromkeys(analyst_next_actions))

        recommendation = state.get("recommendation", Recommendation.ABSTAIN)
        if validation_errors:
            recommendation = Recommendation.ABSTAIN
            uncertainty_reasons.extend(validation_errors)

        blocking_fields = {
            "uploaded_documents",
            "document_text_extraction",
            "policy_rules",
        }
        blocking_gaps = [
            item
            for item in missing_details
            if item.get("blocking_rules")
            or item.get("field") in blocking_fields
            or str(item.get("field", "")).startswith("rule:")
        ]

        if blocking_gaps and recommendation != Recommendation.ABSTAIN:
            recommendation = Recommendation.ABSTAIN
            uncertainty_reasons.append("Case escalated due to unresolved underwriting evidence gaps.")

        return AgentResult(
            payload={
                "recommendation": recommendation,
                "guardrail_passed": not validation_errors,
                "missing_information_details": missing_details,
                "analyst_next_actions": analyst_next_actions,
            },
            missing_information=missing_information,
            uncertainty_reasons=uncertainty_reasons,
        )
