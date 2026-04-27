# app/agents/_delivery_review_agent.py

from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.agents._base import AgentResult, BaseAgent
from app.core._logging import get_logger
from app.models._task import Task
from app.models._task_progress import TaskProgress
from app.services._monitoring_service import MonitoringService

logger = get_logger(__name__)


class DeliveryReviewAgent(BaseAgent):
    agent_name = "delivery_review_agent"
    role = "delivery_review"
    stage = "delivery_review"

    def __init__(self, db: Session):
        self.monitoring_service = MonitoringService(db)

    def run(self, shared_context: Dict[str, Any]) -> AgentResult:
        project_id = shared_context["project_id"]
        llm_service = shared_context.get("llm_service")
        db: Session = shared_context.get("db") or self.monitoring_service.db

        health = self.monitoring_service.check_project_health(project_id)
        risk_summary = self.monitoring_service.get_risk_summary(project_id)

        # Collect proof-of-work evidence for completed subtasks
        proof_items = []
        if db:
            subtasks_with_proof = (
                db.query(Task, TaskProgress)
                .join(TaskProgress, TaskProgress.task_id == Task.id)
                .filter(
                    Task.project_id == project_id,
                    Task.parent_task_id.isnot(None),
                    Task.status == "done",
                )
                .all()
            )
            for task, progress in subtasks_with_proof:
                if progress.proof_note or progress.proof_url:
                    proof_items.append({
                        "task_id": task.id,
                        "task": task.description,
                        "proof_note": progress.proof_note,
                        "proof_url": progress.proof_url,
                    })

        blockers = []
        for item in health.get("blocked_tasks", []):
            blockers.append({
                "task_id": item["task_id"],
                "reason": "Blocked by unmet dependency chain",
                "blocked_by": item["blocked_by"],
            })

        # Build LLM context
        delivery_context = {
            "project_id": project_id,
            "health": {
                "overall_progress": health.get("overall_progress"),
                "overdue_tasks": health.get("overdue_tasks", []),
                "overloaded_employees": health.get("overloaded_employees", []),
                "blocked_task_count": len(blockers),
                "blocked_tasks": blockers,
            },
            "risk_summary": {
                "level": risk_summary.get("risk_level"),
                "needs_intervention": risk_summary.get("needs_intervention"),
                "active_risks": risk_summary.get("risks", [])[:5],
            },
            "proof_of_work": proof_items,
        }

        llm_result: Dict[str, Any] = {}
        if llm_service and llm_service.enabled:
            try:
                llm_result = llm_service.review_delivery_health(delivery_context)
                logger.info(
                    f"DeliveryReviewAgent LLM: status={llm_result.get('health_status')}, "
                    f"requires_human={llm_result.get('requires_human')}"
                )
            except Exception as exc:
                logger.warning(f"DeliveryReviewAgent LLM call failed: {exc}")

        if llm_result.get("health_status"):
            requires_human_review = llm_result.get("requires_human", False)
            confidence = 0.90 if not requires_human_review else 0.72
            reasoning = f"LLM delivery review: {llm_result.get('narrative', 'Analysis complete')}"
        else:
            requires_human_review = risk_summary.get("needs_intervention", False)
            confidence = 0.84 if not requires_human_review else 0.68
            reasoning = "Rule-based delivery review (LLM unavailable): health, delays, overload, dependency checks"

        output_payload = {
            "health": health,
            "risk_summary": risk_summary,
            "delivery_blockers": blockers,
            "proof_of_work": proof_items,
            "llm_narrative": llm_result.get("narrative", ""),
            "llm_health_status": llm_result.get("health_status", ""),
            "priority_actions": llm_result.get("priority_actions", []),
            "human_reason": llm_result.get("human_reason", ""),
        }

        return AgentResult(
            agent_name=self.agent_name,
            role=self.role,
            stage=self.stage,
            confidence=confidence,
            reasoning=reasoning,
            output_payload=output_payload,
            requires_human_review=requires_human_review,
        )
