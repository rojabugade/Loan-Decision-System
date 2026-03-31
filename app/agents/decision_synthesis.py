from typing import Any

from app.agents.base import BaseAgent
from app.core.config import settings
from app.schemas.common import AgentResult, KeyClaim, PolicyStatus, Recommendation


class DecisionSynthesisAgent(BaseAgent):
    name = "decision_synthesis"

    def run(self, state: dict[str, Any]) -> AgentResult:
        policy_checks = state.get("policy_checks", [])
        risk_factors = state.get("risk_factors", [])
        citations = state.get("citations", [])
        missing_information = list(state.get("missing_information", []))
        uncertainty_reasons = list(state.get("uncertainty_reasons", []))

        failed = [c for c in policy_checks if c["status"] == PolicyStatus.FAIL]
        unknown = [c for c in policy_checks if c["status"] == PolicyStatus.UNKNOWN]

        recommendation = Recommendation.REVIEW
        confidence = 0.75

        if failed:
            recommendation = Recommendation.DECLINE
            confidence = 0.82
        elif not citations:
            recommendation = Recommendation.ABSTAIN
            confidence = 0.0
            uncertainty_reasons.append("No supporting citations available for deterministic decision.")
        elif unknown:
            recommendation = Recommendation.ABSTAIN
            confidence = 0.0
            uncertainty_reasons.append("Policy checks unresolved due to missing evidence.")
        elif missing_information:
            recommendation = Recommendation.REVIEW
            confidence = 0.62
            uncertainty_reasons.append("Some non-blocking borrower data is missing; analyst review required.")
        else:
            recommendation = Recommendation.APPROVE
            confidence = 0.86

        if confidence < settings.low_confidence_threshold and recommendation != Recommendation.ABSTAIN:
            recommendation = Recommendation.ABSTAIN
            uncertainty_reasons.append("Confidence below configured threshold.")

        key_claims: list[KeyClaim] = []
        if failed:
            key_claims.append(
                KeyClaim(
                    claim_id="claim_policy_failure",
                    text="One or more mandatory policy rules failed.",
                    evidence_ids=failed[0]["evidence_ids"],
                )
            )
        elif recommendation == Recommendation.APPROVE and policy_checks:
            key_claims.append(
                KeyClaim(
                    claim_id="claim_policy_pass",
                    text="All evaluated policy rules passed.",
                    evidence_ids=policy_checks[0]["evidence_ids"],
                )
            )
        elif recommendation == Recommendation.ABSTAIN:
            key_claims = []

        return AgentResult(
            payload={
                "recommendation": recommendation,
                "confidence": confidence,
                "key_claims": [c.model_dump() for c in key_claims],
                "risk_factors": risk_factors,
            },
            missing_information=missing_information,
            uncertainty_reasons=uncertainty_reasons,
        )
