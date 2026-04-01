# app/agents/_delivery_review_agent.py

from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.agents._base import AgentResult, BaseAgent
from app.services._monitoring_service import MonitoringService


class DeliveryReviewAgent(BaseAgent):
    agent_name = "delivery_review_agent"
    role = "delivery_review"
    stage = "delivery_review"

    def __init__(self, db: Session):
        self.monitoring_service = MonitoringService(db)

    def run(self, shared_context: Dict[str, Any]) -> AgentResult:
        project_id = shared_context["project_id"]
        health = self.monitoring_service.check_project_health(project_id)
        risk_summary = self.monitoring_service.get_risk_summary(project_id)

        blockers = []
        for item in health.get("blocked_tasks", []):
            blockers.append(
                {
                    "task_id": item["task_id"],
                    "reason": "Blocked by unmet dependency chain",
                    "blocked_by": item["blocked_by"],
                }
            )

        output_payload = {
            "health": health,
            "risk_summary": risk_summary,
            "delivery_blockers": blockers,
        }

        requires_human_review = risk_summary.get("needs_intervention", False)
        confidence = 0.84 if not requires_human_review else 0.68
        return AgentResult(
            agent_name=self.agent_name,
            role=self.role,
            stage=self.stage,
            confidence=confidence,
            reasoning="Reviewed project delivery state using health, delays, overload, and dependency checks",
            output_payload=output_payload,
            requires_human_review=requires_human_review,
        )
