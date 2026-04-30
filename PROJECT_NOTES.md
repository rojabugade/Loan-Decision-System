# Project Notes: Credit Decision Operator Console

This document is a deep reference for the project in this repository. It explains what the system does, how the pieces fit together, how data moves through the stack, and how to use the API and UI with concrete examples.

## 1. What This Project Is

This is a regulated credit decision support application. It is not a fully autonomous lender. It is an internal operator console that helps an analyst or underwriting team:

- collect borrower information,
- upload supporting documents,
- evaluate policy rules,
- inspect evidence and citations,
- see why a case was approved, reviewed, declined, or abstained,
- trace the workflow for audit purposes.

The design goal is to keep the system explainable and operationally useful. That means the app should not just return a final answer. It should also show the evidence path, the policy checks, the missing fields, and the suggested analyst next actions.

## 2. High-Level Architecture

The project is split into a few major layers:

- UI layer: Streamlit operator console in [ui/app.py](ui/app.py)
- API layer: FastAPI app and routes in [app/main.py](app/main.py) and [app/api/routes.py](app/api/routes.py)
- Workflow layer: Orchestrated multi-agent pipeline in [app/orchestration/workflow.py](app/orchestration/workflow.py)
- Agent layer: Specialized steps such as classification, extraction, retrieval, validation, synthesis, and guardrails
- Schema layer: Strongly typed request and response models in [app/schemas/input.py](app/schemas/input.py) and [app/schemas/output.py](app/schemas/output.py)
- Retrieval layer: Hybrid retrieval and caching in [app/retrieval/hybrid.py](app/retrieval/hybrid.py)
- Infrastructure layer: config, cache, database, logging, and deployment config

The main idea is:

1. The UI collects case details and documents.
2. The UI sends a case payload to the FastAPI backend.
3. The backend runs the workflow through the agent pipeline.
4. The workflow returns a final decision object with citations, checks, risk factors, and audit metadata.
5. The UI renders the decision in separate operational views.

## 3. Main Runtime Flow

A typical case runs through this sequence:

1. The analyst enters case data in the Streamlit form.
2. The UI builds a payload with applicant data, documents, policy corpus, and metadata filters.
3. The payload is posted to `POST /v1/cases/analyze`.
4. The backend validates and normalizes the request.
5. The workflow executes these stages:
   - Document classification
   - Metric extraction
   - Evidence retrieval
   - Policy validation
   - Decision synthesis
   - Guardrail verification
6. The backend returns a `FinalDecision` object.
7. The UI displays the result in tabs or pages such as Decision Output, Evidence Explainability, and Human Review.

This is intentionally deterministic in structure, even when the content is evidence-driven. The system aims to make the reasoning visible instead of opaque.

## 4. UI Behavior

The Streamlit app in [ui/app.py](ui/app.py) is the operator console.

### 4.1 Case Intake

The Case Intake page collects:

- case ID,
- applicant ID,
- jurisdiction,
- product type,
- requested amount,
- annual revenue,
- net income,
- existing debt,
- debt-to-income ratio,
- DSCR,
- credit score,
- employment status,
- manual document content,
- uploaded files.

The UI supports both manual document entry and file uploads. Uploaded files are parsed when possible. Text-like files are decoded into plain text; binary files are stored as a trace placeholder.

Example of a manual document entry:

```text
Balance Sheet and Income Statement. Annual revenue 120000, debt 20000, credit score 715.
```

### 4.2 Workflow Visibility

This page shows each workflow stage and its status. It is meant for operational transparency. If the workflow has already run, the UI shows the real node status and latency. If not, the UI shows the default pending state.

This is useful for answering questions like:

- Did retrieval run?
- Did policy validation complete?
- Was the case escalated?
- How long did each stage take?

### 4.3 Decision Output

This page shows the most important final outputs:

- recommendation,
- confidence,
- policy checks,
- risk factors,
- key claims,
- missing information,
- uncertainty reasons.

This is the place to inspect the final underwriting result.

### 4.4 Evidence Explainability

This page is for tracing claims back to citations. It shows:

- citation records,
- claim-to-evidence mapping,
- policy-check-to-evidence mapping.

This is important because the system should not just say "approve" or "review". It should show why the answer was reached.

### 4.5 Audit Traceability

This page shows metadata about the run, such as:

- model version,
- prompt version,
- retrieval run ID,
- timestamp,
- workflow node execution summary,
- schema validation status,
- evidence coverage,
- unsupported claim count,
- total API latency.

This is meant for audit and governance teams.

### 4.6 Human Review

This page is for escalated cases. It shows:

- why the case was escalated,
- what is missing,
- what analyst actions are recommended.

This is useful when the system cannot confidently decide or when evidence is incomplete.

### 4.7 Monitoring

This page summarizes recent runs:

- number of cases processed,
- abstain rate,
- average latency,
- recent run history.

It is a lightweight operator monitoring surface.

## 5. API Contract

### 5.1 Endpoint

The main API endpoint is:

```http
POST /v1/cases/analyze
```

Health check:

```http
GET /v1/health
```

### 5.2 Request Shape

The request model in [app/schemas/input.py](app/schemas/input.py) is intentionally flexible.

It supports:

- a target shape with `documents[]`,
- a legacy shape with `uploaded_documents[]`,
- top-level `applicant_id`, `requested_amount`, `jurisdiction`, and `product_type` fields.

The validator normalizes the payload so both forms work.

### 5.3 Request Example

This is a practical request payload:

```json
{
  "case_id": "CASE-1001",
  "applicant_id": "APPL-1",
  "product_type": "SME_TERM_LOAN",
  "jurisdiction": "US",
  "requested_amount": 200000,
  "applicant_data": {
    "applicant_id": "APPL-1",
    "annual_revenue": 1500000,
    "net_income": 200000,
    "debt_service_coverage_ratio": 1.5,
    "debt_to_income_ratio": 0.35,
    "credit_score": 720,
    "existing_debt": 300000,
    "requested_amount": 200000
  },
  "uploaded_documents": [
    {
      "doc_id": "DOC-1",
      "file_name": "financials-2025.pdf",
      "mime_type": "application/pdf",
      "content": "Balance Sheet and Income Statement FY2025",
      "metadata": {
        "source": "customer_upload"
      }
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
          "source_doc_id": "POL-1"
        },
        {
          "rule_id": "R-DSCR-12",
          "metric": "debt_service_coverage_ratio",
          "operator": ">=",
          "threshold": 1.2,
          "source_doc_id": "POL-1"
        }
      ]
    }
  ],
  "regulatory_corpus": [],
  "metadata_filters": {
    "jurisdiction": "US",
    "product_type": "SME_TERM_LOAN"
  }
}
```

### 5.4 Response Shape

The backend returns a `FinalDecision` model defined in [app/schemas/output.py](app/schemas/output.py).

Core fields:

- `case_id`
- `recommendation`
- `confidence`
- `risk_factors`
- `policy_checks`
- `key_claims`
- `missing_information`
- `missing_information_details`
- `uncertainty_reasons`
- `analyst_next_actions`
- `citations`
- `trace`
- `workflow_execution`

Example response skeleton:

```json
{
  "case_id": "CASE-1001",
  "recommendation": "APPROVE",
  "confidence": 0.86,
  "policy_checks": [
    {
      "rule_id": "R-CREDIT-680",
      "status": "PASS"
    }
  ],
  "citations": [
    {
      "doc_id": "DOC-1",
      "snippet": "Balance Sheet and Income Statement FY2025"
    }
  ],
  "workflow_execution": {
    "api_total_latency_ms": 124.8,
    "schema_validation_passed": true,
    "evidence_coverage": 1.0,
    "unsupported_claims": 0,
    "escalated_to_human_review": false
  }
}
```

## 6. How Request Normalization Works

The input schema does more than validation. It also normalizes common variations.

### 6.1 DSCR Alias

If the UI or caller sends `dscr`, the validator maps it to `debt_service_coverage_ratio`.

Why this matters:

- UI forms often use short labels.
- Policy evaluation uses canonical field names.
- Without normalization, the workflow could miss DSCR-related decisions.

Example:

```json
{
  "applicant_data": {
    "applicant_id": "APPL-1",
    "dscr": 1.35
  }
}
```

becomes:

```json
{
  "applicant_data": {
    "applicant_id": "APPL-1",
    "debt_service_coverage_ratio": 1.35
  }
}
```

### 6.2 Documents Alias

If a caller sends `documents[]` instead of `uploaded_documents[]`, the request validator converts the list into the canonical uploaded-document model.

This lets the UI and API evolve without breaking the backend contract.

### 6.3 Top-Level Field Merging

The request validator also merges top-level fields like:

- `applicant_id`
- `requested_amount`
- `jurisdiction`
- `product_type`

into the nested structures where needed.

This is useful because some callers prefer a flat payload while others prefer structured nested objects.

## 7. Workflow Stages In Detail

The workflow in [app/orchestration/workflow.py](app/orchestration/workflow.py) is the backbone of the system.

### 7.1 Document Classification

This stage identifies document type and tracks evidence IDs.

Purpose:

- separate borrower docs from policy docs,
- create a simple document taxonomy,
- attach evidence references early.

### 7.2 Metric Extraction

This stage extracts numeric facts from the input.

Typical metrics:

- annual revenue,
- net income,
- existing debt,
- requested amount,
- DSCR,
- debt-to-income ratio,
- credit score.

Why it matters:

Policy validation depends on normalized numeric values. If the system cannot extract these metrics, it may abstain or escalate.

### 7.3 Evidence Retrieval

This stage retrieves supporting evidence from borrower documents and policy corpus.

Key behavior:

- borrower documents are included in retrieval,
- policy documents are also included,
- citations are ordered so borrower evidence is visible,
- caching uses a borrower signature so new uploads do not get stale results.

This stage is what turns raw case data into explainable evidence.

### 7.4 Policy Validation

This stage evaluates policy rules such as:

- credit score >= threshold,
- debt-to-income ratio <= threshold,
- annual revenue >= threshold,
- DSCR >= threshold.

The result is a set of policy checks with pass/fail statuses.

### 7.5 Decision Synthesis

This stage determines the final recommendation.

Typical outcomes:

- `APPROVE` if the checks pass and evidence is sufficient,
- `DECLINE` if policy failures are deterministic,
- `REVIEW` if missing information needs analyst input,
- `ABSTAIN` if evidence is insufficient or uncertain.

### 7.6 Guardrail Verification

This stage checks that claims are supported by evidence and creates analyst-facing missing-information details.

It is meant to prevent unsupported or vague outputs.

## 8. Decision Logic Conceptually

The decision logic is not just a score threshold. It is a policy and evidence decision.

A simple mental model:

- If policy is clearly broken, decline.
- If policy is clearly satisfied, approve.
- If the evidence is incomplete, review or abstain.
- If a claim cannot be supported, do not present it as fact.

Example:

If a case has:

- credit score 720,
- DSCR 1.5,
- DTI 0.35,
- annual revenue 1.5M,
- policy requires credit score 680, DSCR 1.2, DTI 0.43, revenue 50K,

then the case should generally approve.

If instead DSCR is missing, the workflow may move to review or abstain depending on whether the missing fact blocks policy evaluation.

## 9. Retrieval Notes

The retrieval layer in [app/retrieval/hybrid.py](app/retrieval/hybrid.py) is designed to behave like a production system even though this is still a lightweight MVP.

### 9.1 What It Does

- fetches candidate evidence,
- ranks borrower and policy content,
- creates citations,
- caches retrieval runs,
- avoids stale policy-only retrieval results by including borrower content in the cache signature.

### 9.2 Why Caching Matters

If the user uploads new documents, the system must not reuse an old retrieval result that was computed without those documents. That is why the borrower document hash must be part of the cache key.

### 9.3 Example

Borrower document:

```text
Annual revenue 120000, debt 20000, credit score 715. DSCR 1.35.
```

Policy document:

```text
Minimum credit score 700. Maximum DTI 0.43. Minimum DSCR 1.20.
```

Retrieval should surface both:

- the borrower statement as evidence,
- the policy rule as the governing constraint.

## 10. Guardrails and Missing Information

The guardrail verifier produces more than a yes/no result. It generates operational guidance.

### 10.1 Missing Information Details

This is useful when a case cannot be resolved from the current inputs.

Example:

- field: `debt_service_coverage_ratio`
- reason: Debt obligations unavailable, DSCR cannot be computed.
- blocking_rules: `R-DSCR-12`

### 10.2 Analyst Next Actions

Examples:

- collect missing borrower financial statements,
- verify policy exceptions,
- rerun the case after missing evidence is attached.

This turns the output into an actionable work queue item instead of just a generic error.

## 11. Example End-to-End Scenario

### Scenario A: Approve

Input:

- credit score = 720
- DSCR = 1.5
- DTI = 0.35
- annual revenue = 1.5M
- requested amount = 200K
- documents include financial statements
- policy thresholds are satisfied

Expected outcome:

- recommendation: `APPROVE`
- confidence: high
- policy checks: mostly PASS
- citations: borrower document + policy document
- missing info: none

### Scenario B: Review

Input:

- credit score present
- annual revenue present
- DSCR missing
- policy requires DSCR

Expected outcome:

- recommendation: `REVIEW` or `ABSTAIN`
- missing information details should identify DSCR as blocking
- analyst next actions should request the missing debt information

### Scenario C: Decline

Input:

- credit score below threshold
- DTI above threshold
- DSCR below threshold

Expected outcome:

- recommendation: `DECLINE`
- policy checks show deterministic failures
- citations support the failed metrics

## 12. Example API Call

```powershell
curl -X POST "http://127.0.0.1:8000/v1/cases/analyze" ^
  -H "Content-Type: application/json" ^
  --data-binary "@examples/sample_case.json"
```

If the backend is running and the sample payload is valid, the API returns a structured `FinalDecision` response.

## 13. Local Development

Typical local run steps:

```powershell
cd C:\Users\rojab\MyData\credit-ai-platform
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Run the UI separately:

```powershell
python -m streamlit run ui\app.py
```

## 14. Deployment Notes

### 14.1 Streamlit UI

The UI can be deployed independently as long as `API_BASE_URL` points to a public backend.

### 14.2 FastAPI Backend

The backend needs a public hosting target such as Render, Cloud Run, Railway, or a tunnel URL.

### 14.3 Environment Variable

The UI reads:

```text
API_BASE_URL
```

Example:

```text
https://loan-decision-api.onrender.com
```

## 15. What Is Implemented vs Future Work

Implemented in the repository:

- API request/response schemas,
- workflow orchestration,
- decision output,
- evidence/citation support,
- Streamlit operator UI,
- document upload support,
- request normalization,
- monitoring page,
- audit traceability page,
- human review guidance.

Planned or intentionally left as future work:

- full OpenTelemetry tracing,
- Prometheus metrics,
- immutable audit ledger,
- policy version registry,
- full RAGAS evaluation stack,
- more advanced embedding-based retrieval,
- role-based access control.

## 16. Useful File Map

- [app/main.py](app/main.py): FastAPI bootstrap
- [app/api/routes.py](app/api/routes.py): routes and health endpoint
- [app/orchestration/workflow.py](app/orchestration/workflow.py): main workflow
- [app/retrieval/hybrid.py](app/retrieval/hybrid.py): retrieval and caching
- [app/schemas/input.py](app/schemas/input.py): request normalization
- [app/schemas/output.py](app/schemas/output.py): response contract
- [ui/app.py](ui/app.py): Streamlit operator console
- [examples/sample_case.json](examples/sample_case.json): sample request payload
- [tests/test_mvp.py](tests/test_mvp.py): smoke tests

## 17. Final Mental Model

Think of this system as a controlled underwriting assistant:

- the UI collects case facts,
- the backend normalizes and validates them,
- the workflow finds evidence,
- the policy layer tests the facts against rules,
- the guardrail layer prevents unsupported claims,
- the final output is an explainable decision with traceability.

That is the core design of the repository.
