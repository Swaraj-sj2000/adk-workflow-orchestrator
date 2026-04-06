# app/agents/_risk_agent.py

from typing import Any, Dict, List

from app.agents._base import AgentResult, BaseAgent


class RiskAgent(BaseAgent):
    agent_name = "risk_agent"
    role = "risk_analysis"
    stage = "risk"

    def run(self, shared_context: Dict[str, Any]) -> AgentResult:
        execution_plan = shared_context["execution_plan"]
        staffing = shared_context["staffing"]
        risks: List[Dict[str, Any]] = []

        complexity = execution_plan.get("project_complexity", 0.7)
        if complexity >= 0.8:
            risks.append(
                {
                    "type": "complexity",
                    "severity": "high",
                    "reason": "Project complexity is high and may require tighter review loops",
                }
            )

        if staffing.get("under_staffed_task_count", 0) > 0:
            risks.append(
                {
                    "type": "staffing_gap",
                    "severity": "high",
                    "reason": f"{staffing['under_staffed_task_count']} task(s) do not have a strong staffing recommendation",
                }
            )

        for rec in staffing.get("staffing_recommendations", []):
            owner = rec.get("recommended_owner")
            if owner and owner["current_load"] / max(owner["max_capacity"], 1) >= 0.85:
                risks.append(
                    {
                        "type": "load_pressure",
                        "severity": "medium",
                        "task_sequence": rec["task_sequence"],
                        "reason": "Top candidate is already near capacity",
                    }
                )

        risk_level = "low"
        if any(r["severity"] == "high" for r in risks):
            risk_level = "high"
        elif risks:
            risk_level = "medium"

        return AgentResult(
            agent_name=self.agent_name,
            role=self.role,
            stage=self.stage,
            confidence=0.76 if risk_level != "high" else 0.62,
            reasoning="Assessed pre-execution delivery risk using complexity, staffing coverage, and capacity pressure",
            output_payload={
                "risk_level": risk_level,
                "risks": risks,
                "requires_escalation": risk_level == "high",
            },
            requires_human_review=risk_level == "high",
        )
