from fastapi.testclient import TestClient

from app.main import app


def test_analyze_case_returns_structured_response():
    client = TestClient(app)
    payload = {
        "case_id": "CASE-1001",
        "applicant_data": {
            "applicant_id": "APPL-1",
            "annual_revenue": 1500000,
            "net_income": 200000,
            "debt_service_coverage_ratio": 1.5,
            "debt_to_income_ratio": 0.35,
            "credit_score": 720,
            "existing_debt": 300000,
            "requested_amount": 200000,
        },
        "uploaded_documents": [
            {
                "doc_id": "DOC-1",
                "file_name": "financials-2025.pdf",
                "mime_type": "application/pdf",
                "content": "Balance Sheet and Income Statement FY2025",
                "metadata": {"source": "customer_upload"},
            }
        ],
        "policy_corpus": [
            {
                "doc_id": "POL-1",
                "title": "Commercial Lending Policy",
                "content": "Minimum credit score 680 and DSCR >= 1.2",
                "jurisdiction": "US",
                "product_type": "SME_TERM_LOAN",
                "rules": [
                    {
                        "rule_id": "R-CREDIT-680",
                        "metric": "credit_score",
                        "operator": ">=",
                        "threshold": 680,
                        "source_doc_id": "POL-1",
                    },
                    {
                        "rule_id": "R-DSCR-12",
                        "metric": "debt_service_coverage_ratio",
                        "operator": ">=",
                        "threshold": 1.2,
                        "source_doc_id": "POL-1",
                    },
                ],
            }
        ],
        "regulatory_corpus": [],
        "metadata_filters": {
            "jurisdiction": "US",
            "product_type": "SME_TERM_LOAN",
        },
    }

    response = client.post("/v1/cases/analyze", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["case_id"] == "CASE-1001"
    assert body["recommendation"] in {"APPROVE", "REVIEW", "DECLINE", "ABSTAIN"}
    assert "trace" in body
    assert isinstance(body["policy_checks"], list)


def test_analyze_case_accepts_target_ui_shape_documents_array():
    client = TestClient(app)
    payload = {
        "case_id": "CASE-UI-001",
        "applicant_id": "APPL-UI-001",
        "product_type": "SME_TERM_LOAN",
        "jurisdiction": "US",
        "requested_amount": 35000,
        "applicant_data": {
            "annual_revenue": 120000,
            "net_income": 25000,
            "existing_debt": 20000,
            "debt_to_income_ratio": 0.34,
            "dscr": 1.35,
            "credit_score": 715,
            "employment_status": "Full-time",
        },
        "documents": [
            {
                "document_id": "DOC-UI-001",
                "file_name": "financial_statement.txt",
                "mime_type": "text/plain",
                "text": "Balance Sheet and Income Statement. Annual revenue 120000, debt 20000, credit score 715.",
            }
        ],
        "policy_corpus": [
            {
                "doc_id": "POL-1",
                "title": "Commercial Lending Policy",
                "content": "Minimum credit score 680 and DSCR >= 1.2",
                "jurisdiction": "US",
                "product_type": "SME_TERM_LOAN",
                "rules": [
                    {
                        "rule_id": "R-CREDIT-680",
                        "metric": "credit_score",
                        "operator": ">=",
                        "threshold": 680,
                        "source_doc_id": "POL-1",
                    },
                    {
                        "rule_id": "R-DSCR-12",
                        "metric": "debt_service_coverage_ratio",
                        "operator": ">=",
                        "threshold": 1.2,
                        "source_doc_id": "POL-1",
                    },
                ],
            }
        ],
        "regulatory_corpus": [],
        "metadata_filters": {
            "jurisdiction": "US",
            "product_type": "SME_TERM_LOAN",
        },
    }

    response = client.post("/v1/cases/analyze", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["case_id"] == "CASE-UI-001"
    assert len(body["citations"]) >= 1
