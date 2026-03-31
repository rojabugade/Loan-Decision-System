from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Recommendation(str, Enum):
    APPROVE = "APPROVE"
    REVIEW = "REVIEW"
    DECLINE = "DECLINE"
    ABSTAIN = "ABSTAIN"


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class PolicyStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


class Citation(BaseModel):
    citation_id: str
    doc_id: str
    location: str
    excerpt_hash: str


class RiskFactor(BaseModel):
    factor_code: str
    severity: Severity
    evidence_ids: list[str] = Field(default_factory=list)


class PolicyCheck(BaseModel):
    rule_id: str
    status: PolicyStatus
    evidence_ids: list[str] = Field(default_factory=list)


class KeyClaim(BaseModel):
    claim_id: str
    text: str
    evidence_ids: list[str] = Field(default_factory=list)


class MissingInformationItem(BaseModel):
    field: str
    reason: str
    blocking_rules: list[str] = Field(default_factory=list)


class TraceMetadata(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_version: str
    prompt_version: str
    retrieval_run_id: str
    timestamp: str


class AgentResult(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)
    missing_information: list[str] = Field(default_factory=list)
    uncertainty_reasons: list[str] = Field(default_factory=list)
