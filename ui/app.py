import json
import os
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
ANALYZE_ENDPOINT = "/v1/cases/analyze"

STAGES = [
    "document_classifier",
    "metric_extractor",
    "evidence_retrieval",
    "policy_validator",
    "decision_synthesis",
    "guardrail_verifier",
]

DEFAULT_POLICY = {
    "doc_id": "POL-STD-01",
    "title": "Standard Credit Policy",
    "content": "Minimum credit score 700. Maximum DTI 0.43. Minimum annual revenue 50000. Minimum DSCR 1.20.",
    "jurisdiction": "US",
    "product_type": "SME_TERM_LOAN",
    "rules": [
        {"rule_id": "R-CREDIT-700", "metric": "credit_score", "operator": ">=", "threshold": 700, "source_doc_id": "POL-STD-01"},
        {"rule_id": "R-DTI-43", "metric": "debt_to_income_ratio", "operator": "<=", "threshold": 0.43, "source_doc_id": "POL-STD-01"},
        {"rule_id": "R-REV-50K", "metric": "annual_revenue", "operator": ">=", "threshold": 50000, "source_doc_id": "POL-STD-01"},
        {"rule_id": "R-DSCR-120", "metric": "debt_service_coverage_ratio", "operator": ">=", "threshold": 1.2, "source_doc_id": "POL-STD-01"},
    ],
}


def init_state() -> None:
    st.session_state.setdefault("documents", [])
    st.session_state.setdefault("decision", None)
    st.session_state.setdefault("case_runs", [])
    st.session_state.setdefault("last_request", None)


def enterprise_theme() -> None:
    st.markdown(
        """
        <style>
            @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');
            html, body, [class*="css"] {
                font-family: 'IBM Plex Sans', sans-serif;
            }
            .block-container {
                padding-top: 1.2rem;
                padding-bottom: 2rem;
                max-width: 1400px;
            }
            .hero-card {
                background: linear-gradient(120deg, #f6f9fc 0%, #e9f4ff 100%);
                border: 1px solid #d1e3f8;
                border-radius: 14px;
                padding: 18px;
                margin-bottom: 12px;
            }
            .status-pill {
                border-radius: 999px;
                padding: 4px 10px;
                font-size: 12px;
                font-weight: 600;
                display: inline-block;
                margin-right: 6px;
            }
            .status-completed { background: #dff5e5; color: #17552a; }
            .status-running { background: #fff0d6; color: #7a4b00; }
            .status-pending { background: #eceff3; color: #445064; }
            .status-failed { background: #ffe2e0; color: #8f2118; }
            .status-abstained, .status-escalated { background: #ffe9cc; color: #8c4c00; }
            .section-title {
                font-size: 1.03rem;
                margin-top: 0.4rem;
                margin-bottom: 0.6rem;
                font-weight: 700;
                color: #18324a;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def load_demo_case() -> dict:
    demo_path = Path(__file__).resolve().parent.parent / "demo" / "case_approve.json"
    if demo_path.exists():
        return json.loads(demo_path.read_text(encoding="utf-8"))
    return {
        "case_id": "CASE-UI-001",
        "applicant_data": {
            "applicant_id": "APPL-UI-001",
            "annual_revenue": 120000,
            "net_income": 25000,
            "debt_service_coverage_ratio": 1.35,
            "debt_to_income_ratio": 0.34,
            "credit_score": 715,
            "existing_debt": 20000,
            "requested_amount": 35000,
            "extra_fields": {},
        },
        "uploaded_documents": [],
        "policy_corpus": [DEFAULT_POLICY],
        "regulatory_corpus": [],
        "metadata_filters": {"jurisdiction": "US", "product_type": "SME_TERM_LOAN"},
    }


def parse_uploaded_file(uploaded_file) -> tuple[str, str]:
    mime_type = uploaded_file.type or "application/octet-stream"
    raw_bytes = uploaded_file.getvalue()

    if mime_type in {"text/plain", "application/json", "text/csv"}:
        try:
            return raw_bytes.decode("utf-8"), mime_type
        except UnicodeDecodeError:
            return raw_bytes.decode("latin-1", errors="ignore"), mime_type

    # For binary formats, keep a trace placeholder and let analyst attach extracted text manually if needed.
    return f"[BINARY_DOCUMENT:{uploaded_file.name}:size={len(raw_bytes)}]", mime_type


def api_analyze(payload: dict) -> tuple[dict | None, str | None, float]:
    start = time.perf_counter()
    try:
        response = requests.post(f"{API_BASE_URL}{ANALYZE_ENDPOINT}", json=payload, timeout=60)
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        if response.status_code != 200:
            return None, f"HTTP {response.status_code}: {response.text}", elapsed_ms
        return response.json(), None, elapsed_ms
    except requests.RequestException as exc:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        return None, str(exc), elapsed_ms


def build_case_payload() -> dict:
    applicant = {
        "applicant_id": st.session_state.get("applicant_id", "APPL-001"),
        "annual_revenue": st.session_state.get("annual_revenue"),
        "net_income": st.session_state.get("net_income"),
        "debt_service_coverage_ratio": st.session_state.get("dscr"),
        "debt_to_income_ratio": st.session_state.get("dti"),
        "credit_score": st.session_state.get("credit_score"),
        "existing_debt": st.session_state.get("existing_debt"),
        "requested_amount": st.session_state.get("requested_amount"),
        "extra_fields": {
            "employment_status": st.session_state.get("employment_status", "Unknown")
        },
    }

    policy = {
        **DEFAULT_POLICY,
        "jurisdiction": st.session_state.get("jurisdiction", "US"),
        "product_type": st.session_state.get("product_type", "SME_TERM_LOAN"),
    }

    ui_documents = st.session_state.get("documents", [])
    documents = [
        {
            "document_id": d.get("doc_id"),
            "file_name": d.get("file_name"),
            "mime_type": d.get("mime_type"),
            "text": d.get("content", ""),
        }
        for d in ui_documents
    ]

    return {
        "case_id": st.session_state.get("case_id", "CASE-UI-001"),
        "applicant_id": st.session_state.get("applicant_id", "APPL-001"),
        "product_type": st.session_state.get("product_type", "SME_TERM_LOAN"),
        "jurisdiction": st.session_state.get("jurisdiction", "US"),
        "requested_amount": st.session_state.get("requested_amount"),
        "applicant_data": {
            "annual_revenue": applicant.get("annual_revenue"),
            "net_income": applicant.get("net_income"),
            "existing_debt": applicant.get("existing_debt"),
            "debt_to_income_ratio": applicant.get("debt_to_income_ratio"),
            "dscr": applicant.get("debt_service_coverage_ratio"),
            "credit_score": applicant.get("credit_score"),
            "employment_status": applicant.get("extra_fields", {}).get("employment_status"),
            "applicant_id": applicant.get("applicant_id"),
            "requested_amount": applicant.get("requested_amount"),
        },
        "documents": documents,
        "uploaded_documents": ui_documents,
        "policy_corpus": [policy],
        "regulatory_corpus": [],
        "metadata_filters": {
            "jurisdiction": st.session_state.get("jurisdiction", "US"),
            "product_type": st.session_state.get("product_type", "SME_TERM_LOAN"),
        },
    }


def _doc_exists(doc_id: str, file_name: str) -> bool:
    for existing in st.session_state.get("documents", []):
        if existing.get("doc_id") == doc_id or existing.get("file_name") == file_name:
            return True
    return False


def render_case_intake() -> None:
    st.markdown('<div class="section-title">Case Intake</div>', unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.text_input("Case ID", value=st.session_state.get("case_id", "CASE-UI-001"), key="case_id")
        st.text_input("Applicant ID", value=st.session_state.get("applicant_id", "APPL-UI-001"), key="applicant_id")
        st.selectbox("Jurisdiction", ["US", "UK", "EU", "IN"], index=0, key="jurisdiction")
    with c2:
        st.selectbox("Product Type", ["SME_TERM_LOAN", "PERSONAL_LOAN", "WORKING_CAPITAL"], index=0, key="product_type")
        st.number_input("Requested Amount", min_value=0.0, value=float(st.session_state.get("requested_amount", 35000.0) or 0), key="requested_amount")
        st.selectbox("Employment Status", ["Full-time", "Contract", "Self-employed", "Unknown"], index=0, key="employment_status")
    with c3:
        st.number_input("Annual Revenue", min_value=0.0, value=float(st.session_state.get("annual_revenue", 120000.0) or 0), key="annual_revenue")
        st.number_input("Net Income", min_value=0.0, value=float(st.session_state.get("net_income", 25000.0) or 0), key="net_income")
        st.number_input("Existing Debt", min_value=0.0, value=float(st.session_state.get("existing_debt", 20000.0) or 0), key="existing_debt")

    c4, c5 = st.columns(2)
    with c4:
        st.number_input("Debt To Income Ratio", min_value=0.0, max_value=2.0, value=float(st.session_state.get("dti", 0.34) or 0), step=0.01, key="dti")
    with c5:
        st.number_input("DSCR", min_value=0.0, max_value=5.0, value=float(st.session_state.get("dscr", 1.35) or 0), step=0.01, key="dscr")
    st.number_input("Credit Score", min_value=300, max_value=850, value=int(st.session_state.get("credit_score", 715) or 715), key="credit_score")

    st.markdown('<div class="section-title">Document Upload and Registry</div>', unsafe_allow_html=True)
    d1, d2 = st.columns([1, 2])
    with d1:
        uploader_role = st.selectbox("Uploader", ["Applicant", "Loan Officer", "Analyst"], index=0, key="uploader_role")
        doc_id = st.text_input("Document ID", value="DOC-UI-001", key="new_doc_id")
        file_name = st.text_input("File Name", value="financial_statement.txt", key="new_file_name")
        mime_type = st.selectbox("MIME Type", ["text/plain", "application/pdf", "application/json"], index=0, key="new_mime_type")
    with d2:
        content = st.text_area(
            "Document Text",
            value="Balance Sheet and Income Statement. Annual revenue 120000, debt 20000, credit score 715.",
            key="new_doc_content",
            height=160,
        )
        uploaded_files = st.file_uploader(
            "Upload Case Documents",
            type=["txt", "json", "csv", "pdf"],
            accept_multiple_files=True,
            help="Applicants or loan officers can upload files here. Text formats are parsed directly.",
            key="uploaded_case_files",
        )

    if st.button("Add Document", type="secondary"):
        st.session_state.documents.append(
            {
                "doc_id": doc_id,
                "file_name": file_name,
                "mime_type": mime_type,
                "content": content,
                "metadata": {
                    "source": "ui_upload",
                    "uploader_role": uploader_role,
                    "uploaded_at": datetime.utcnow().isoformat(),
                },
            }
        )
        st.success(f"Added document {doc_id}")

    if uploaded_files:
        newly_added = 0
        for upl in uploaded_files:
            parsed_content, parsed_mime = parse_uploaded_file(upl)
            generated_id = f"DOC-UPL-{abs(hash(upl.name)) % 1_000_000:06d}"
            if _doc_exists(generated_id, upl.name):
                continue
            st.session_state.documents.append(
                {
                    "doc_id": generated_id,
                    "file_name": upl.name,
                    "mime_type": parsed_mime,
                    "content": parsed_content,
                    "metadata": {
                        "source": "file_upload",
                        "uploader_role": uploader_role,
                        "uploaded_at": datetime.utcnow().isoformat(),
                    },
                }
            )
            newly_added += 1
        if newly_added > 0:
            st.success(f"Added {newly_added} uploaded file(s)")

    if st.session_state.documents:
        st.dataframe(pd.DataFrame(st.session_state.documents), use_container_width=True, hide_index=True)

    controls = st.columns([1, 1, 5])
    with controls[0]:
        if st.button("Load Demo Case"):
            demo_case = load_demo_case()
            st.session_state.case_id = demo_case["case_id"]
            app_data = demo_case["applicant_data"]
            st.session_state.applicant_id = app_data["applicant_id"]
            st.session_state.annual_revenue = app_data["annual_revenue"]
            st.session_state.net_income = app_data["net_income"]
            st.session_state.dscr = app_data["debt_service_coverage_ratio"]
            st.session_state.dti = app_data["debt_to_income_ratio"]
            st.session_state.credit_score = app_data["credit_score"]
            st.session_state.existing_debt = app_data["existing_debt"]
            st.session_state.requested_amount = app_data["requested_amount"]
            st.session_state.documents = demo_case["uploaded_documents"]
            st.session_state.jurisdiction = demo_case["metadata_filters"]["jurisdiction"]
            st.session_state.product_type = demo_case["metadata_filters"]["product_type"]
            st.rerun()
    with controls[1]:
        if st.button("Run Case Analysis", type="primary"):
            payload = build_case_payload()
            st.session_state.last_request = payload
            decision, error, elapsed_ms = api_analyze(payload)
            if error:
                st.error(error)
            else:
                st.session_state.decision = decision
                st.session_state.case_runs.insert(
                    0,
                    {
                        "case_id": decision.get("case_id"),
                        "recommendation": decision.get("recommendation"),
                        "confidence": decision.get("confidence"),
                        "timestamp": datetime.utcnow().isoformat(),
                        "api_total_latency_ms": decision.get("workflow_execution", {}).get("api_total_latency_ms", elapsed_ms),
                        "abstained": decision.get("recommendation") == "ABSTAIN",
                    },
                )
                st.success("Case analysis completed")


def render_workflow_visibility(decision: dict | None) -> None:
    st.markdown('<div class="section-title">Workflow Visibility</div>', unsafe_allow_html=True)

    if not decision:
        st.info("Run a case to view stage-level statuses.")
        for stage in STAGES:
            st.write(f"- {stage}: pending")
        return

    workflow_execution = decision.get("workflow_execution", {})
    nodes = workflow_execution.get("nodes", [])
    if not nodes:
        nodes = [{"node": stage, "status": "completed", "latency_ms": None} for stage in STAGES]

    for node in nodes:
        status = (node.get("status") or "pending").lower()
        css_class = f"status-{status}"
        st.markdown(
            f"<span class='status-pill {css_class}'>{status.upper()}</span> <strong>{node.get('node')}</strong>"
            + (f" - {node.get('latency_ms')} ms" if node.get("latency_ms") is not None else ""),
            unsafe_allow_html=True,
        )


def render_decision_view(decision: dict | None) -> None:
    st.markdown('<div class="section-title">Decision Output</div>', unsafe_allow_html=True)
    if not decision:
        st.info("No decision yet.")
        return

    top = st.columns([1.1, 1.1, 1.2, 1.2])
    top[0].metric("Recommendation", decision.get("recommendation", "N/A"))
    top[1].metric("Confidence", f"{decision.get('confidence', 0.0):.2f}")
    top[2].metric("Policy Checks", len(decision.get("policy_checks", [])))
    top[3].metric("Risk Factors", len(decision.get("risk_factors", [])))

    t1, t2 = st.columns(2)
    with t1:
        st.subheader("Policy Checks")
        st.dataframe(pd.DataFrame(decision.get("policy_checks", [])), use_container_width=True, hide_index=True)
        st.subheader("Risk Factors")
        st.dataframe(pd.DataFrame(decision.get("risk_factors", [])), use_container_width=True, hide_index=True)
    with t2:
        st.subheader("Key Claims")
        st.dataframe(pd.DataFrame(decision.get("key_claims", [])), use_container_width=True, hide_index=True)
        st.subheader("Missing Information")
        missing_details = decision.get("missing_information_details", [])
        if missing_details:
            st.dataframe(pd.DataFrame(missing_details), use_container_width=True, hide_index=True)
        else:
            st.write(decision.get("missing_information", []))
        st.subheader("Uncertainty Reasons")
        st.write(decision.get("uncertainty_reasons", []))


def render_evidence_view(decision: dict | None) -> None:
    st.markdown('<div class="section-title">Evidence and Explainability</div>', unsafe_allow_html=True)
    if not decision:
        st.info("Run a case to inspect citations and evidence links.")
        return

    citations = decision.get("citations", [])
    st.subheader("Citations Panel")
    st.dataframe(pd.DataFrame(citations), use_container_width=True, hide_index=True)

    claims = decision.get("key_claims", [])
    policy_checks = decision.get("policy_checks", [])

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Claim to Evidence Mapping")
        for claim in claims:
            st.write(f"- {claim.get('claim_id')}: {claim.get('evidence_ids')}")
    with c2:
        st.subheader("Policy Check to Evidence Mapping")
        for check in policy_checks:
            st.write(f"- {check.get('rule_id')}: {check.get('evidence_ids')}")


def render_audit_traceability(decision: dict | None) -> None:
    st.markdown('<div class="section-title">Audit and Traceability</div>', unsafe_allow_html=True)
    if not decision:
        st.info("Run a case to view trace metadata and execution summary.")
        return

    trace = decision.get("trace", {})
    workflow_execution = decision.get("workflow_execution", {})

    meta_cols = st.columns(4)
    meta_cols[0].metric("Model Version", trace.get("model_version", "N/A"))
    meta_cols[1].metric("Prompt Version", trace.get("prompt_version", "N/A"))
    meta_cols[2].metric("Retrieval Run ID", trace.get("retrieval_run_id", "N/A"))
    meta_cols[3].metric("Timestamp", trace.get("timestamp", "N/A"))

    st.subheader("Workflow Node Execution Summary")
    st.dataframe(pd.DataFrame(workflow_execution.get("nodes", [])), use_container_width=True, hide_index=True)

    st.subheader("Diagnostic Integrity")
    d_cols = st.columns(4)
    d_cols[0].metric("Schema Validation", "PASS" if workflow_execution.get("schema_validation_passed") else "FAIL")
    d_cols[1].metric("Evidence Coverage", f"{workflow_execution.get('evidence_coverage', 0.0):.2f}")
    d_cols[2].metric("Unsupported Claims", workflow_execution.get("unsupported_claims", 0))
    d_cols[3].metric("API Total Latency (ms)", workflow_execution.get("api_total_latency_ms", 0.0))


def render_human_review(decision: dict | None) -> None:
    st.markdown('<div class="section-title">Human Review Queue</div>', unsafe_allow_html=True)
    if not decision:
        st.info("Run a case to generate escalation guidance.")
        return

    rec = decision.get("recommendation")
    missing = decision.get("missing_information", [])
    missing_details = decision.get("missing_information_details", [])
    uncertainty = decision.get("uncertainty_reasons", [])
    analyst_next_actions = decision.get("analyst_next_actions", [])

    if rec in {"ABSTAIN", "REVIEW"}:
        st.warning(f"Case escalated with recommendation {rec}.")
        st.markdown("### Why escalated")
        st.write(uncertainty if uncertainty else ["Guardrail escalation triggered"])
        st.markdown("### What is missing")
        if missing_details:
            st.dataframe(pd.DataFrame(missing_details), use_container_width=True, hide_index=True)
        else:
            st.write(missing if missing else ["No explicit missing fields captured"])
        st.markdown("### Analyst next actions")
        st.write(
            analyst_next_actions
            if analyst_next_actions
            else [
                "Obtain missing borrower financial statements or bureau data.",
                "Verify policy exceptions and attach approval rationale.",
                "Re-run case after evidence set is complete.",
            ]
        )
    else:
        st.success("Case does not require escalation. Analyst can proceed with maker-checker approval.")


def render_monitoring() -> None:
    st.markdown('<div class="section-title">Monitoring and Operator View</div>', unsafe_allow_html=True)

    runs = st.session_state.get("case_runs", [])
    if not runs:
        st.info("No case runs yet. Execute at least one case.")
        return

    df = pd.DataFrame(runs)
    abstain_rate = round((df["abstained"].sum() / len(df)) * 100, 2)

    m1, m2, m3 = st.columns(3)
    m1.metric("Recent Case Runs", len(df))
    m2.metric("Abstain Rate", f"{abstain_rate}%")
    m3.metric("Avg API Latency (ms)", round(df["api_total_latency_ms"].mean(), 2))

    st.subheader("Recent Runs")
    st.dataframe(df[["timestamp", "case_id", "recommendation", "confidence", "api_total_latency_ms"]], use_container_width=True, hide_index=True)


def main() -> None:
    st.set_page_config(page_title="Credit Decision Operator Console", page_icon="🏦", layout="wide")
    init_state()
    enterprise_theme()

    st.markdown(
        """
        <div class="hero-card">
            <h2 style="margin:0;color:#102a43;">Credit Decision Operator Console</h2>
            <div style="margin-top:6px;color:#334e68;">Internal underwriting support UI with workflow transparency, evidence linkage, and auditability.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.header("Navigation")
        page = st.radio(
            "View",
            [
                "Case Intake",
                "Workflow Visibility",
                "Decision Output",
                "Evidence Explainability",
                "Audit Traceability",
                "Human Review",
                "Monitoring",
            ],
        )
        st.caption(f"Backend: {API_BASE_URL}")

    decision = st.session_state.get("decision")

    if page == "Case Intake":
        render_case_intake()
    elif page == "Workflow Visibility":
        render_workflow_visibility(decision)
    elif page == "Decision Output":
        render_decision_view(decision)
    elif page == "Evidence Explainability":
        render_evidence_view(decision)
    elif page == "Audit Traceability":
        render_audit_traceability(decision)
    elif page == "Human Review":
        render_human_review(decision)
    else:
        render_monitoring()


if __name__ == "__main__":
    main()
