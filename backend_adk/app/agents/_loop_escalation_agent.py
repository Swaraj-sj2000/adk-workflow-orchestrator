# app/agents/_loop_escalation_agent.py

from typing import Any, Dict, List

from app.agents._base import AgentResult, BaseAgent


class LoopEscalationAgent(BaseAgent):
    agent_name = "loop_escalation_agent"
    role = "loop_escalation"
    stage = "loop_escalation"

    def run(self, shared_context: Dict[str, Any]) -> AgentResult:
        delivery_review = shared_context["delivery_review"]
        rebalance = shared_context["rebalance"]

        items: List[Dict[str, Any]] = []
        risk_level = delivery_review["risk_summary"]["risk_level"]
        if risk_level in ["high", "critical"]:
            items.append(
                {
                    "scope": "project_delivery",
                    "severity": risk_level,
                    "reason": f"Project delivery risk is {risk_level}",
                }
            )

        if rebalance["unassigned_active_tasks"]:
            items.append(
                {
                    "scope": "staffing_gap",
                    "severity": "high",
                    "reason": f"{len(rebalance['unassigned_active_tasks'])} active task(s) lack a live assignment",
                }
            )

        if rebalance["reassignment_suggestions"]:
            items.append(
                {
                    "scope": "rebalancing",
                    "severity": "medium",
                    "reason": f"{len(rebalance['reassignment_suggestions'])} reassignment suggestion(s) need review",
                }
            )

        decision = "human_review_required" if items else "continue_autonomously"
        return AgentResult(
            agent_name=self.agent_name,
            role=self.role,
            stage=self.stage,
            confidence=0.86 if items or risk_level == "low" else 0.7,
            reasoning="Applied escalation policy to the live project execution loop",
            output_payload={
                "decision": decision,
                "items": items,
            },
            requires_human_review=bool(items),
        )
