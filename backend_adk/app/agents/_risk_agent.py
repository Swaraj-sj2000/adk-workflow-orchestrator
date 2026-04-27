# app/agents/_risk_agent.py

from typing import Any, Dict, List

from app.agents._base import AgentResult, BaseAgent
from app.core._logging import get_logger

logger = get_logger(__name__)


class RiskAgent(BaseAgent):
    agent_name = "risk_agent"
    role = "risk_analysis"
    stage = "risk"

    def run(self, shared_context: Dict[str, Any]) -> AgentResult:
        execution_plan = shared_context["execution_plan"]
        staffing = shared_context["staffing"]
        llm_service = shared_context.get("llm_service")

        # Build structured context for LLM analysis
        risk_context = {
            "project_title": execution_plan.get("project_title", ""),
            "project_complexity": execution_plan.get("project_complexity", 0.7),
            "task_count": len(execution_plan.get("tasks", [])),
            "tasks": [
                {
                    "sequence": t.get("sequence"),
                    "title": t.get("title"),
                    "difficulty": t.get("difficulty"),
                    "urgency": t.get("urgency"),
                    "estimated_hours": t.get("estimated_time"),
                    "required_skills": t.get("required_skills"),
                }
                for t in execution_plan.get("tasks", [])[:8]
            ],
            "staffing_summary": {
                "under_staffed_tasks": staffing.get("under_staffed_task_count", 0),
                "total_tasks": len(staffing.get("staffing_recommendations", [])),
                "recommendations": [
                    {
                        "task_sequence": r.get("task_sequence"),
                        "top_candidate_score": r.get("recommended_owner", {}).get("score") if r.get("recommended_owner") else None,
                        "top_candidate_load_pct": (
                            round(r["recommended_owner"]["current_load"] / max(r["recommended_owner"]["max_capacity"], 1) * 100, 1)
                            if r.get("recommended_owner") and r["recommended_owner"].get("max_capacity")
                            else None
                        ),
                    }
                    for r in staffing.get("staffing_recommendations", [])
                ],
            },
        }

        llm_result: Dict[str, Any] = {}
        if llm_service and llm_service.enabled:
            try:
                llm_result = llm_service.analyze_project_risks(risk_context)
                logger.info(f"RiskAgent LLM analysis: risk_level={llm_result.get('risk_level')}, risks_found={len(llm_result.get('risks', []))}")
            except Exception as exc:
                logger.warning(f"RiskAgent LLM call failed, using rule-based fallback: {exc}")

        # Use LLM result if valid, otherwise fall back to rule-based
        if llm_result.get("risks") and llm_result.get("risk_level"):
            risks = llm_result["risks"]
            risk_level = llm_result["risk_level"]
            narrative = llm_result.get("narrative", "")
            reasoning = f"LLM-powered risk analysis: {narrative}" if narrative else "LLM risk analysis completed"
        else:
            # Rule-based fallback
            risks: List[Dict[str, Any]] = []
            complexity = execution_plan.get("project_complexity", 0.7)
            if complexity >= 0.8:
                risks.append({
                    "type": "complexity",
                    "severity": "high",
                    "reason": "Project complexity is high and may require tighter review loops",
                })

            if staffing.get("under_staffed_task_count", 0) > 0:
                risks.append({
                    "type": "staffing_gap",
                    "severity": "high",
                    "reason": f"{staffing['under_staffed_task_count']} task(s) do not have a strong staffing recommendation",
                })

            for rec in staffing.get("staffing_recommendations", []):
                owner = rec.get("recommended_owner")
                if owner and owner["current_load"] / max(owner["max_capacity"], 1) >= 0.85:
                    risks.append({
                        "type": "load_pressure",
                        "severity": "medium",
                        "task_sequence": rec["task_sequence"],
                        "reason": "Top candidate is already near capacity",
                    })

            risk_level = "low"
            if any(r["severity"] == "high" for r in risks):
                risk_level = "high"
            elif risks:
                risk_level = "medium"

            reasoning = "Rule-based risk assessment (LLM unavailable): complexity, staffing coverage, and capacity pressure"

        return AgentResult(
            agent_name=self.agent_name,
            role=self.role,
            stage=self.stage,
            confidence=0.88 if llm_result.get("risk_level") else (0.76 if risk_level != "high" else 0.62),
            reasoning=reasoning,
            output_payload={
                "risk_level": risk_level,
                "risks": risks,
                "narrative": llm_result.get("narrative", ""),
                "requires_escalation": risk_level == "high",
            },
            requires_human_review=risk_level == "high",
        )
