# Credit Analysis Platform MVP (Production-Style)

Internal enterprise-style AI workflow for regulated credit decision support.

## Stack

- Python 3.11+
- FastAPI API layer
- LangGraph-style DAG orchestration (native fallback runner included)
- PostgreSQL/pgvector retrieval abstraction (MVP in-memory adapter with pgvector-ready interface)
- Redis-ready caching config
- Strict Pydantic JSON contracts
- Structured observability and evaluation hooks

## Project Structure

- app/main.py: FastAPI bootstrap
- app/api/routes.py: API endpoints
- app/core/config.py: settings and runtime thresholds
- app/core/logging.py: structured JSON logging
- app/core/cache.py: Redis cache adapter with safe fallback
- app/core/db.py: SQLAlchemy engine/session bootstrap
- app/schemas/input.py: request contracts
- app/schemas/output.py: final decision schema and typed stage outputs
- app/schemas/common.py: shared enums and common models
- app/agents/: specialized workflow agents
- app/retrieval/hybrid.py: hybrid retrieval abstraction
- app/retrieval/pgvector_store.py: pgvector-ready store adapter
- app/orchestration/workflow.py: LangGraph-style DAG and state management
- app/evaluation/hooks.py: evaluation/metrics hook point
- examples/sample_case.json: runnable input payload
- tests/test_mvp.py: API contract smoke test

## Agents

- DocumentClassifierAgent
- MetricExtractorAgent
- EvidenceRetrievalAgent
- PolicyValidatorAgent
- DecisionSynthesisAgent
- GuardrailVerifierAgent

## Workflow

1. Document classification
2. Metric extraction
3. Evidence retrieval (semantic + metadata filter abstraction)
4. Policy validation
5. Decision synthesis (APPROVE/REVIEW/DECLINE/ABSTAIN)
6. Guardrail verification (evidence-link checks, contradiction flags)
7. Audit-ready response packaging

## Guardrails Enforced

- Claims without evidence are blocked
- Missing data forces ABSTAIN
- Low confidence forces ABSTAIN
- Contradictions append uncertainty reasons
- All outputs are strict JSON and schema-validated

## Run Locally

```powershell
cd C:\Users\rojab\MyData\credit-ai-platform
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Optional: if you want native LangGraph engine instead of fallback runner:

```powershell
pip install langgraph==0.2.34
```

## Test

```powershell
cd C:\Users\rojab\MyData\credit-ai-platform
pytest -q
```

## API Usage

```powershell
curl -X POST "http://127.0.0.1:8000/v1/cases/analyze" ^
  -H "Content-Type: application/json" ^
  --data-binary "@examples/sample_case.json"
```

## Quick Demo

Run two deterministic demo cases (one complete, one missing-data abstain):

```powershell
cd C:\Users\rojab\MyData\credit-ai-platform
python demo\run_demo.py
```

Demo assets:

- `demo/case_approve.json`
- `demo/case_abstain_missing_data.json`
- `demo/run_demo.py`

## Operator UI (Streamlit)

Production-style internal analyst console:

- Case Intake (create/load case, applicant profile, document registry)
- Workflow Visibility (node statuses and node latency)
- Decision Output (recommendation, confidence, checks, risks, claims)
- Evidence Explainability (citations and evidence linkage)
- Audit Traceability (model and prompt metadata, execution diagnostics)
- Human Review (escalation reasons and analyst next actions)
- Monitoring (recent runs, abstain rate, latency trends)

Run UI:

```powershell
cd C:\Users\rojab\MyData\credit-ai-platform
python -m streamlit run ui\app.py
```

Open:

- http://localhost:8501

## Notes on Retrieval

Current retrieval uses a production-style flow with graceful degradation:

- Redis cache lookup for repeated retrieval plans
- Metadata-filtered corpus ranking from input payload documents
- Optional PostgreSQL chunk retrieval via pgvector store adapter
- Citation packaging with deterministic excerpt hashes

To fully productionize semantic retrieval:

- Add real embedding vectors and ANN index in PostgreSQL (pgvector)
- Replace token-overlap ranking with vector similarity + cross-encoder rerank
- Add ingestion pipeline for chunking, embedding, and policy version indexing

## Production Upgrade Path

- Add async workers for extraction/retrieval/evaluation stages
- Add OpenTelemetry traces and Prometheus metrics
- Add policy version registry and immutable audit ledger
- Add full RAGAS-style offline/online evaluation pipeline
- Add model registry with prompt/version pinning and release gates
- Add role-based access control and data retention policy enforcement
