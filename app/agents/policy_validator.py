from typing import Any

from app.agents.base import BaseAgent
from app.schemas.common import AgentResult, PolicyCheck, PolicyStatus, RiskFactor, Severity


def _evaluate_operator(metric_value: float | int | None, operator: str, threshold: float) -> PolicyStatus:
    if metric_value is None:
        return PolicyStatus.UNKNOWN

    if operator == ">=":
        return PolicyStatus.PASS if metric_value >= threshold else PolicyStatus.FAIL
    if operator == "<=":
        return PolicyStatus.PASS if metric_value <= threshold else PolicyStatus.FAIL
    if operator == ">":
        return PolicyStatus.PASS if metric_value > threshold else PolicyStatus.FAIL
    if operator == "<":
        return PolicyStatus.PASS if metric_value < threshold else PolicyStatus.FAIL
    if operator == "==":
        return PolicyStatus.PASS if metric_value == threshold else PolicyStatus.FAIL

    return PolicyStatus.UNKNOWN


class PolicyValidatorAgent(BaseAgent):
    name = "policy_validator"

    def run(self, state: dict[str, Any]) -> AgentResult:
        request = state["request"]
        metrics = state.get("metrics", {})

        checks: list[PolicyCheck] = []
        risks: list[RiskFactor] = []

        for doc in [*request.policy_corpus, *request.regulatory_corpus]:
            for rule in doc.rules:
                metric_value = metrics.get(rule.metric)
                status = _evaluate_operator(metric_value, rule.operator, rule.threshold)
                evidence_ids = [f"doc:{rule.source_doc_id}"]

                checks.append(
                    PolicyCheck(
                        rule_id=rule.rule_id,
                        status=status,
                        evidence_ids=evidence_ids,
                    )
                )

                if status == PolicyStatus.FAIL:
                    risks.append(
                        RiskFactor(
                            factor_code=f"RULE_FAIL_{rule.rule_id}",
                            severity=Severity.HIGH,
                            evidence_ids=evidence_ids,
                        )
                    )
                elif status == PolicyStatus.UNKNOWN:
                    risks.append(
                        RiskFactor(
                            factor_code=f"RULE_UNKNOWN_{rule.rule_id}",
                            severity=Severity.MEDIUM,
                            evidence_ids=evidence_ids,
                        )
                    )

        missing = []
        if not checks:
            missing.append("policy_rules")

        return AgentResult(
            payload={
                "policy_checks": [c.model_dump() for c in checks],
                "risk_factors": [r.model_dump() for r in risks],
            },
            missing_information=missing,
        )
