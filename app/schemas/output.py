from pydantic import BaseModel, Field, field_validator

from app.schemas.common import (
    Citation,
    KeyClaim,
    MissingInformationItem,
    PolicyCheck,
    Recommendation,
    RiskFactor,
    TraceMetadata,
)


class WorkflowNodeSummary(BaseModel):
    node: str
    status: str
    latency_ms: float | None = None
    message: str | None = None


class WorkflowExecutionSummary(BaseModel):
    nodes: list[WorkflowNodeSummary] = Field(default_factory=list)
    api_total_latency_ms: float
    schema_validation_passed: bool
    evidence_coverage: float = Field(ge=0.0, le=1.0)
    unsupported_claims: int
    escalated_to_human_review: bool


class FinalDecision(BaseModel):
    case_id: str
    recommendation: Recommendation
    confidence: float = Field(ge=0.0, le=1.0)
    risk_factors: list[RiskFactor] = Field(default_factory=list)
    policy_checks: list[PolicyCheck] = Field(default_factory=list)
    key_claims: list[KeyClaim] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    missing_information_details: list[MissingInformationItem] = Field(default_factory=list)
    uncertainty_reasons: list[str] = Field(default_factory=list)
    analyst_next_actions: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    trace: TraceMetadata
    workflow_execution: WorkflowExecutionSummary | None = None

    @field_validator("confidence")
    @classmethod
    def confidence_is_numeric(cls, value: float) -> float:
        if value is None:
            raise ValueError("confidence must be present")
        return value


class DocumentClassification(BaseModel):
    doc_id: str
    document_type: str
    evidence_ids: list[str] = Field(default_factory=list)


class MetricExtraction(BaseModel):
    metrics: dict[str, float | int | None] = Field(default_factory=dict)
    evidence_map: dict[str, list[str]] = Field(default_factory=dict)


class RetrievalEvidence(BaseModel):
    citations: list[Citation] = Field(default_factory=list)
    retrieval_run_id: str


class PolicyValidationResult(BaseModel):
    policy_checks: list[PolicyCheck] = Field(default_factory=list)
    risk_factors: list[RiskFactor] = Field(default_factory=list)


class DecisionSynthesisResult(BaseModel):
    recommendation: Recommendation
    confidence: float = Field(ge=0.0, le=1.0)
    key_claims: list[KeyClaim] = Field(default_factory=list)
    uncertainty_reasons: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
