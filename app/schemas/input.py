from pydantic import BaseModel, Field, model_validator


class CaseDocument(BaseModel):
    document_id: str
    file_name: str
    mime_type: str | None = None
    text: str = ""


class UploadedDocument(BaseModel):
    doc_id: str
    file_name: str
    mime_type: str | None = None
    content: str = ""
    metadata: dict[str, str] = Field(default_factory=dict)


class ApplicantData(BaseModel):
    applicant_id: str
    annual_revenue: float | None = None
    net_income: float | None = None
    debt_service_coverage_ratio: float | None = None
    debt_to_income_ratio: float | None = None
    credit_score: int | None = None
    existing_debt: float | None = None
    requested_amount: float | None = None
    extra_fields: dict[str, str | float | int | bool] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def normalize_aliases(cls, values):
        if not isinstance(values, dict):
            return values

        if "dscr" in values and "debt_service_coverage_ratio" not in values:
            values["debt_service_coverage_ratio"] = values["dscr"]

        employment_status = values.pop("employment_status", None)
        if employment_status is not None:
            extra = values.get("extra_fields") or {}
            extra["employment_status"] = employment_status
            values["extra_fields"] = extra

        return values


class PolicyRule(BaseModel):
    rule_id: str
    metric: str
    operator: str
    threshold: float
    source_doc_id: str
    jurisdiction: str | None = None
    product_type: str | None = None


class PolicyDocument(BaseModel):
    doc_id: str
    title: str
    content: str
    jurisdiction: str | None = None
    product_type: str | None = None
    source_type: str = "policy"
    rules: list[PolicyRule] = Field(default_factory=list)


class AnalyzeCaseRequest(BaseModel):
    case_id: str
    applicant_data: ApplicantData
    uploaded_documents: list[UploadedDocument] = Field(default_factory=list)
    documents: list[CaseDocument] = Field(default_factory=list)
    applicant_id: str | None = None
    product_type: str | None = None
    jurisdiction: str | None = None
    requested_amount: float | None = None
    policy_corpus: list[PolicyDocument] = Field(default_factory=list)
    regulatory_corpus: list[PolicyDocument] = Field(default_factory=list)
    metadata_filters: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def normalize_request_shape(cls, values):
        if not isinstance(values, dict):
            return values

        # Map target shape documents -> uploaded_documents
        docs = values.get("documents") or []
        uploaded_docs = values.get("uploaded_documents") or []
        if docs and not uploaded_docs:
            values["uploaded_documents"] = [
                {
                    "doc_id": d.get("document_id") or d.get("doc_id") or f"DOC-{idx+1}",
                    "file_name": d.get("file_name") or f"document_{idx+1}.txt",
                    "mime_type": d.get("mime_type") or "text/plain",
                    "content": d.get("text") or d.get("content") or "",
                    "metadata": d.get("metadata") or {},
                }
                for idx, d in enumerate(docs)
            ]

        # Build applicant_data from top-level target fields if needed.
        applicant_data = values.get("applicant_data") or {}
        top_applicant_id = values.get("applicant_id")
        top_requested = values.get("requested_amount")

        if top_applicant_id and "applicant_id" not in applicant_data:
            applicant_data["applicant_id"] = top_applicant_id
        if top_requested is not None and "requested_amount" not in applicant_data:
            applicant_data["requested_amount"] = top_requested

        if applicant_data:
            values["applicant_data"] = applicant_data

        # Normalize metadata filters from top-level shape.
        filters = values.get("metadata_filters") or {}
        if values.get("jurisdiction") and "jurisdiction" not in filters:
            filters["jurisdiction"] = values["jurisdiction"]
        if values.get("product_type") and "product_type" not in filters:
            filters["product_type"] = values["product_type"]
        values["metadata_filters"] = filters

        return values
