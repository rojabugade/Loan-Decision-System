from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, TypedDict

try:
    from langgraph.graph import END, START, StateGraph
except ImportError:
    START = "__start__"
    END = "__end__"

    class _CompiledFallbackGraph:
        def __init__(self, nodes: dict[str, Any], edges: dict[str, str]):
            self.nodes = nodes
            self.edges = edges

        def invoke(self, state: dict[str, Any]) -> dict[str, Any]:
            current = self.edges.get(START)
            current_state = dict(state)
            while current and current != END:
                node_fn = self.nodes[current]
                current_state = node_fn(current_state)
                current = self.edges.get(current)
            return current_state

    class StateGraph:
        def __init__(self, _state_type):
            self._nodes: dict[str, Any] = {}
            self._edges: dict[str, str] = {}

        def add_node(self, name: str, fn):
            self._nodes[name] = fn

        def add_edge(self, source: str, target: str):
            self._edges[source] = target

        def compile(self):
            return _CompiledFallbackGraph(self._nodes, self._edges)

from app.agents.decision_synthesis import DecisionSynthesisAgent
from app.agents.document_classifier import DocumentClassifierAgent
from app.agents.evidence_retrieval import EvidenceRetrievalAgent
from app.agents.guardrail_verifier import GuardrailVerifierAgent
from app.agents.metric_extractor import MetricExtractorAgent
from app.agents.policy_validator import PolicyValidatorAgent
from app.core.cache import RedisCache
from app.core.config import settings
from app.core.logging import get_logger
from app.retrieval.hybrid import HybridRetrievalEngine
from app.retrieval.pgvector_store import PgvectorStore
from app.schemas.common import Recommendation, TraceMetadata
from app.schemas.input import AnalyzeCaseRequest
from app.schemas.output import FinalDecision

logger = get_logger("workflow")


class WorkflowState(TypedDict, total=False):
    request: AnalyzeCaseRequest
    case_id: str
    document_classifications: list[dict[str, Any]]
    metrics: dict[str, float | int | None]
    metric_evidence_map: dict[str, list[str]]
    citations: list[dict[str, str]]
    retrieval_run_id: str
    retrieval_cache_hit: bool
    policy_checks: list[dict[str, Any]]
    risk_factors: list[dict[str, Any]]
    key_claims: list[dict[str, Any]]
    recommendation: Recommendation
    confidence: float
    missing_information: list[str]
    missing_information_details: list[dict[str, Any]]
    uncertainty_reasons: list[str]
    analyst_next_actions: list[str]
    contradiction_flags: list[str]
    guardrail_passed: bool
    node_latency_ms: dict[str, float]
    node_status: dict[str, str]


class CreditWorkflow:
    def __init__(self):
        self.document_classifier = DocumentClassifierAgent()
        self.metric_extractor = MetricExtractorAgent()
        self.redis_cache = RedisCache()
        self.pgvector_store = PgvectorStore()
        self.evidence_retrieval = EvidenceRetrievalAgent(
            HybridRetrievalEngine(cache=self.redis_cache, pgvector_store=self.pgvector_store)
        )
        self.policy_validator = PolicyValidatorAgent()
        self.decision_synthesis = DecisionSynthesisAgent()
        self.guardrail_verifier = GuardrailVerifierAgent()
        self.graph = self._build_graph()

    def _timed_run(self, node_name: str, fn, state: WorkflowState) -> tuple[dict[str, Any], float]:
        start = time.perf_counter()
        result = fn(state)
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.info("workflow_node_completed", node=node_name, latency_ms=elapsed_ms, case_id=state["case_id"])
        return result, elapsed_ms

    def _merge_agent_result(self, state: WorkflowState, result: dict[str, Any]) -> WorkflowState:
        payload = result.payload
        next_state = dict(state)
        next_state.update(payload)
        next_state["missing_information"] = sorted(
            set(next_state.get("missing_information", []) + result.missing_information)
        )
        next_state["uncertainty_reasons"] = list(
            dict.fromkeys(next_state.get("uncertainty_reasons", []) + result.uncertainty_reasons)
        )
        return next_state

    def _node_document_classifier(self, state: WorkflowState) -> WorkflowState:
        req = state["request"]
        logger.info(
            "workflow_input_documents",
            case_id=state["case_id"],
            borrower_document_count=len(req.uploaded_documents),
        )
        result, latency_ms = self._timed_run("document_classifier", self.document_classifier.run, state)
        next_state = self._merge_agent_result(state, result)
        next_state.setdefault("node_latency_ms", {})["document_classifier"] = latency_ms
        next_state.setdefault("node_status", {})["document_classifier"] = "completed"
        logger.info(
            "workflow_document_classification_summary",
            case_id=state["case_id"],
            classified_document_count=len(next_state.get("document_classifications", [])),
        )
        return next_state

    def _node_metric_extractor(self, state: WorkflowState) -> WorkflowState:
        result, latency_ms = self._timed_run("metric_extractor", self.metric_extractor.run, state)

        metrics = result.payload.get("metrics", {})
        contradiction_flags = []
        if metrics.get("requested_amount") is not None and metrics.get("annual_revenue") is not None:
            if metrics["requested_amount"] > metrics["annual_revenue"] * 2:
                contradiction_flags.append("requested_amount_significantly_exceeds_revenue")

        next_state = self._merge_agent_result(state, result)
        next_state["contradiction_flags"] = contradiction_flags
        next_state.setdefault("node_latency_ms", {})["metric_extractor"] = latency_ms
        next_state.setdefault("node_status", {})["metric_extractor"] = "completed"
        extracted_borrower_evidence_count = len(
            [e for e in next_state.get("metric_evidence_map", {}).values() if any(x.startswith("doc:") for x in e)]
        )
        logger.info(
            "workflow_metric_extraction_summary",
            case_id=state["case_id"],
            extracted_metric_count=len([v for v in next_state.get("metrics", {}).values() if v is not None]),
            extracted_borrower_evidence_count=extracted_borrower_evidence_count,
        )
        return next_state

    def _node_evidence_retrieval(self, state: WorkflowState) -> WorkflowState:
        result, latency_ms = self._timed_run("evidence_retrieval", self.evidence_retrieval.run, state)
        next_state = self._merge_agent_result(state, result)
        next_state.setdefault("node_latency_ms", {})["evidence_retrieval"] = latency_ms
        next_state.setdefault("node_status", {})["evidence_retrieval"] = "completed"
        logger.info(
            "workflow_retrieval_summary",
            case_id=state["case_id"],
            borrower_evidence_count=next_state.get("borrower_evidence_count", 0),
            policy_evidence_count=next_state.get("policy_evidence_count", 0),
            final_citation_count=len(next_state.get("citations", [])),
            retrieved_doc_ids=[c.get("doc_id") for c in next_state.get("citations", [])],
        )
        return next_state

    def _node_policy_validator(self, state: WorkflowState) -> WorkflowState:
        result, latency_ms = self._timed_run("policy_validator", self.policy_validator.run, state)
        next_state = self._merge_agent_result(state, result)
        next_state.setdefault("node_latency_ms", {})["policy_validator"] = latency_ms
        next_state.setdefault("node_status", {})["policy_validator"] = "completed"
        return next_state

    def _node_decision_synthesis(self, state: WorkflowState) -> WorkflowState:
        result, latency_ms = self._timed_run("decision_synthesis", self.decision_synthesis.run, state)
        next_state = self._merge_agent_result(state, result)
        next_state.setdefault("node_latency_ms", {})["decision_synthesis"] = latency_ms
        next_state.setdefault("node_status", {})["decision_synthesis"] = "completed"
        return next_state

    def _node_guardrail_verifier(self, state: WorkflowState) -> WorkflowState:
        result, latency_ms = self._timed_run("guardrail_verifier", self.guardrail_verifier.run, state)
        next_state = self._merge_agent_result(state, result)
        next_state.setdefault("node_latency_ms", {})["guardrail_verifier"] = latency_ms
        next_state.setdefault("node_status", {})["guardrail_verifier"] = "completed"
        return next_state

    def _build_graph(self):
        graph_builder = StateGraph(WorkflowState)
        graph_builder.add_node("document_classifier", self._node_document_classifier)
        graph_builder.add_node("metric_extractor", self._node_metric_extractor)
        graph_builder.add_node("evidence_retrieval", self._node_evidence_retrieval)
        graph_builder.add_node("policy_validator", self._node_policy_validator)
        graph_builder.add_node("decision_synthesis", self._node_decision_synthesis)
        graph_builder.add_node("guardrail_verifier", self._node_guardrail_verifier)

        graph_builder.add_edge(START, "document_classifier")
        graph_builder.add_edge("document_classifier", "metric_extractor")
        graph_builder.add_edge("metric_extractor", "evidence_retrieval")
        graph_builder.add_edge("evidence_retrieval", "policy_validator")
        graph_builder.add_edge("policy_validator", "decision_synthesis")
        graph_builder.add_edge("decision_synthesis", "guardrail_verifier")
        graph_builder.add_edge("guardrail_verifier", END)

        return graph_builder.compile()

    def run(self, request: AnalyzeCaseRequest) -> FinalDecision:
        run_start = time.perf_counter()
        initial_state: WorkflowState = {
            "request": request,
            "case_id": request.case_id,
            "missing_information": [],
            "missing_information_details": [],
            "uncertainty_reasons": [],
            "analyst_next_actions": [],
            "node_latency_ms": {},
            "node_status": {},
        }

        final_state = self.graph.invoke(initial_state)

        recommendation = final_state.get("recommendation", Recommendation.ABSTAIN)
        confidence = float(final_state.get("confidence", 0.0))
        missing_info = final_state.get("missing_information", [])
        uncertainty = final_state.get("uncertainty_reasons", [])

        logger.info(
            "workflow_final_summary",
            case_id=request.case_id,
            recommendation=str(recommendation),
            missing_information_count=len(missing_info),
            final_citation_count=len(final_state.get("citations", [])),
        )

        trace = TraceMetadata(
            model_version=settings.model_version,
            prompt_version=settings.prompt_version,
            retrieval_run_id=final_state.get("retrieval_run_id", "retrieval_unavailable"),
            timestamp=datetime.now(tz=timezone.utc).isoformat(),
        )

        claim_count = len(final_state.get("key_claims", []))
        supported_claims = len([c for c in final_state.get("key_claims", []) if c.get("evidence_ids")])
        unsupported_claims = claim_count - supported_claims
        evidence_coverage = 1.0 if claim_count == 0 else round(supported_claims / claim_count, 4)

        node_order = [
            "document_classifier",
            "metric_extractor",
            "evidence_retrieval",
            "policy_validator",
            "decision_synthesis",
            "guardrail_verifier",
        ]
        node_status = final_state.get("node_status", {})
        node_latency_ms = final_state.get("node_latency_ms", {})

        workflow_nodes = []
        for node in node_order:
            status = node_status.get(node, "pending")
            if node == "decision_synthesis" and recommendation == Recommendation.ABSTAIN:
                status = "abstained"
            if node == "guardrail_verifier" and uncertainty:
                status = "escalated"

            workflow_nodes.append(
                {
                    "node": node,
                    "status": status,
                    "latency_ms": node_latency_ms.get(node),
                    "message": None,
                }
            )

        api_total_latency_ms = round((time.perf_counter() - run_start) * 1000, 2)

        workflow_execution = {
            "nodes": workflow_nodes,
            "api_total_latency_ms": api_total_latency_ms,
            "schema_validation_passed": True,
            "evidence_coverage": evidence_coverage,
            "unsupported_claims": unsupported_claims,
            "escalated_to_human_review": recommendation in {Recommendation.ABSTAIN, Recommendation.REVIEW},
        }

        return FinalDecision(
            case_id=request.case_id,
            recommendation=recommendation,
            confidence=confidence,
            risk_factors=final_state.get("risk_factors", []),
            policy_checks=final_state.get("policy_checks", []),
            key_claims=final_state.get("key_claims", []),
            missing_information=missing_info,
            missing_information_details=final_state.get("missing_information_details", []),
            uncertainty_reasons=uncertainty,
            analyst_next_actions=final_state.get("analyst_next_actions", []),
            citations=final_state.get("citations", []),
            trace=trace,
            workflow_execution=workflow_execution,
        )
