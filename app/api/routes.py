from fastapi import APIRouter

from app.evaluation.hooks import emit_decision_metrics
from app.orchestration.workflow import CreditWorkflow
from app.schemas.input import AnalyzeCaseRequest
from app.schemas.output import FinalDecision

router = APIRouter(prefix="/v1", tags=["credit-analysis"])
workflow = CreditWorkflow()


@router.post("/cases/analyze", response_model=FinalDecision)
def analyze_case(request: AnalyzeCaseRequest) -> FinalDecision:
    decision = workflow.run(request)
    emit_decision_metrics(decision)
    return decision


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
