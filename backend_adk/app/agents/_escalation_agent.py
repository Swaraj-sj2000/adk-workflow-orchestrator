# app/agents/_escalation_agent.py

from typing import Any, Dict, List

from app.agents._base import AgentResult, BaseAgent


class EscalationAgent(BaseAgent):
    agent_name = "escalation_agent"
    role = "escalation"
    stage = "escalation"

    def run(self, shared_context: Dict[str, Any]) -> AgentResult:
        risk = shared_context["risk"]
        execution_coordination = shared_context["execution_coordination"]
        staffing = shared_context["staffing"]

        reasons: List[str] = []
        escalation_items: List[Dict[str, Any]] = []

        if risk.get("risk_level") == "high":
            reasons.append("Overall risk level is high")
            escalation_items.append(
                {
                    "scope": "project",
                    "severity": "high",
                    "reason": "Project-level risk requires admin review before autonomous execution expands",
                }
            )

        if staffing.get("under_staffed_task_count", 0) > 0:
            reasons.append("One or more tasks lack a strong staffing recommendation")
            escalation_items.append(
                {
                    "scope": "staffing",
                    "severity": "high",
                    "reason": f"{staffing['under_staffed_task_count']} task(s) need human staffing input",
                }
            )

        if execution_coordination.get("review_required_task_count", 0) > 0:
            escalation_items.append(
                {
                    "scope": "execution_queue",
                    "severity": "medium",
                    "reason": f"{execution_coordination['review_required_task_count']} task(s) are not safe for fully autonomous start",
                }
            )

        requires_review = len(escalation_items) > 0
        decision = "human_review_required" if requires_review else "continue_autonomously"

        return AgentResult(
            agent_name=self.agent_name,
            role=self.role,
            stage=self.stage,
            confidence=0.88 if requires_review or execution_coordination.get("autonomous_task_count", 0) > 0 else 0.55,
            reasoning="Applied explicit escalation policy to determine whether the workflow can continue autonomously",
            output_payload={
                "decision": decision,
                "reasons": reasons,
                "items": escalation_items,
            },
            requires_human_review=requires_review,
        )
