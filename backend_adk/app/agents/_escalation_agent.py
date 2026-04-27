# app/agents/_escalation_agent.py

from typing import Any, Dict, List

from app.agents._base import AgentResult, BaseAgent
from app.core._logging import get_logger
from app.db._database import SessionLocal
from app.models._project import Project
from app.models._user import User
from app.services._email_service import EmailService

logger = get_logger(__name__)


class EscalationAgent(BaseAgent):
    agent_name = "escalation_agent"
    role = "escalation"
    stage = "escalation"

    def run(self, shared_context: Dict[str, Any]) -> AgentResult:
        risk = shared_context["risk"]
        execution_coordination = shared_context["execution_coordination"]
        staffing = shared_context["staffing"]
        project_id = shared_context.get("project_id")
        workflow_run_id = shared_context.get("workflow_run_id")
        llm_service = shared_context.get("llm_service")

        # Build context for LLM
        escalation_context = {
            "risk_level": risk.get("risk_level"),
            "risk_narrative": risk.get("narrative", ""),
            "risks": risk.get("risks", []),
            "autonomous_task_count": execution_coordination.get("autonomous_task_count", 0),
            "review_required_task_count": execution_coordination.get("review_required_task_count", 0),
            "total_tasks": len(execution_coordination.get("task_queue", [])),
            "under_staffed_tasks": staffing.get("under_staffed_task_count", 0),
            "execution_strategy": execution_coordination.get("execution_strategy", ""),
        }

        llm_result: Dict[str, Any] = {}
        if llm_service and llm_service.enabled:
            try:
                llm_result = llm_service.analyze_escalation(escalation_context)
                logger.info(
                    f"EscalationAgent LLM decision: {llm_result.get('decision')}, "
                    f"confidence={llm_result.get('confidence')}"
                )
            except Exception as exc:
                logger.warning(f"EscalationAgent LLM call failed, using rule-based fallback: {exc}")

        # Use LLM result if valid
        if llm_result.get("decision"):
            decision = llm_result["decision"]
            reasons = llm_result.get("reasons", [])
            narrative = llm_result.get("narrative", "")
            requires_review = decision == "human_review_required"
            escalation_items: List[Dict[str, Any]] = [
                {"scope": "llm_analysis", "severity": "high" if requires_review else "low", "reason": r}
                for r in reasons
            ]
            confidence = llm_result.get("confidence", 0.88)
            reasoning = f"LLM escalation decision: {narrative}" if narrative else "LLM escalation analysis"
        else:
            # Rule-based fallback
            reasons: List[str] = []
            escalation_items: List[Dict[str, Any]] = []

            if risk.get("risk_level") == "high":
                reasons.append("Overall risk level is high")
                escalation_items.append({
                    "scope": "project",
                    "severity": "high",
                    "reason": "Project-level risk requires admin review before autonomous execution expands",
                })

            if staffing.get("under_staffed_task_count", 0) > 0:
                reasons.append("One or more tasks lack a strong staffing recommendation")
                escalation_items.append({
                    "scope": "staffing",
                    "severity": "high",
                    "reason": f"{staffing['under_staffed_task_count']} task(s) need human staffing input",
                })

            if execution_coordination.get("review_required_task_count", 0) > 0:
                escalation_items.append({
                    "scope": "execution_queue",
                    "severity": "medium",
                    "reason": f"{execution_coordination['review_required_task_count']} task(s) are not safe for fully autonomous start",
                })

            requires_review = len(escalation_items) > 0
            decision = "human_review_required" if requires_review else "continue_autonomously"
            confidence = 0.88 if requires_review or execution_coordination.get("autonomous_task_count", 0) > 0 else 0.55
            reasoning = "Rule-based escalation policy (LLM unavailable)"

        # Send alerts when escalation required
        alerts_sent = 0
        if requires_review and project_id:
            db = SessionLocal()
            try:
                project = db.query(Project).filter(Project.id == project_id).first()
                if project:
                    recipients = (
                        db.query(User)
                        .filter(User.tenant_id == project.tenant_id, User.role.in_(["admin", "ceo"]))
                        .all()
                    )
                    reason_text = (
                        "; ".join(reasons) if reasons
                        else "; ".join(item["reason"] for item in escalation_items)
                        or llm_result.get("narrative", "Workflow review required")
                    )
                    for user in recipients:
                        if EmailService.send_escalation_alert_email(
                            to_email=user.email,
                            recipient_name=user.full_name or user.email,
                            project_name=project.name,
                            reason=reason_text,
                            workflow_run_id=workflow_run_id or 0,
                        ):
                            alerts_sent += 1
            finally:
                db.close()

        return AgentResult(
            agent_name=self.agent_name,
            role=self.role,
            stage=self.stage,
            confidence=confidence,
            reasoning=reasoning,
            output_payload={
                "decision": decision,
                "reasons": reasons if reasons else llm_result.get("reasons", []),
                "narrative": llm_result.get("narrative", ""),
                "items": escalation_items,
                "alerts_sent": alerts_sent,
            },
            requires_human_review=requires_review,
        )
