# app/agents/_execution_coordinator_agent.py

from typing import Any, Dict, List

from app.agents._base import AgentResult, BaseAgent
from app.core._logging import get_logger

logger = get_logger(__name__)


class ExecutionCoordinatorAgent(BaseAgent):
    agent_name = "execution_coordinator_agent"
    role = "execution_coordination"
    stage = "execution_coordination"

    def run(self, shared_context: Dict[str, Any]) -> AgentResult:
        execution_plan = shared_context["execution_plan"]
        staffing = shared_context["staffing"]
        risk = shared_context["risk"]
        llm_service = shared_context.get("llm_service")

        staffing_by_sequence = {
            item["task_sequence"]: item for item in staffing.get("staffing_recommendations", [])
        }

        task_queue: List[Dict[str, Any]] = []
        autonomous_task_count = 0

        for task in execution_plan.get("tasks", []):
            recommendation = staffing_by_sequence.get(task["sequence"], {})
            owner = recommendation.get("recommended_owner")
            owner_confidence = owner["score"] if owner else 0.0

            can_start_autonomously = bool(
                owner
                and owner_confidence >= 0.65
                and risk.get("risk_level") != "high"
            )
            if can_start_autonomously:
                autonomous_task_count += 1

            task_queue.append({
                "task_sequence": task["sequence"],
                "task_title": task["title"],
                "execution_mode": "autonomous" if can_start_autonomously else "review_required",
                "recommended_owner": owner,
                "owner_confidence": owner_confidence,
                "dependencies": [
                    dep["depends_on_sequence"]
                    for dep in execution_plan.get("dependencies", [])
                    if dep["task_sequence"] == task["sequence"]
                ],
            })

        # Try LLM for intelligent next_actions
        next_actions: List[str] = []
        llm_used = False
        if llm_service and llm_service.enabled:
            try:
                coordinator_context = {
                    "project_title": execution_plan.get("project_title", ""),
                    "risk_level": risk.get("risk_level"),
                    "risk_narrative": risk.get("narrative", ""),
                    "autonomous_task_count": autonomous_task_count,
                    "review_required_count": len(task_queue) - autonomous_task_count,
                    "total_tasks": len(task_queue),
                    "task_queue_summary": [
                        {
                            "sequence": t["task_sequence"],
                            "title": t["task_title"],
                            "mode": t["execution_mode"],
                            "owner_confidence": round(t["owner_confidence"], 2),
                        }
                        for t in task_queue
                    ],
                    "under_staffed_tasks": staffing.get("under_staffed_task_count", 0),
                }
                next_actions = llm_service.generate_coordinator_actions(coordinator_context)
                if next_actions:
                    llm_used = True
                    logger.info(f"ExecutionCoordinatorAgent LLM: {len(next_actions)} actions generated")
            except Exception as exc:
                logger.warning(f"ExecutionCoordinatorAgent LLM call failed: {exc}")

        if not next_actions:
            # Rule-based fallback
            next_actions = [
                "Issue assignment offers for autonomous-ready tasks",
                "Hold review for tasks marked review_required",
                "Monitor early execution signals before rebalancing",
            ]
            if risk.get("risk_level") == "high":
                next_actions.insert(0, "Pause full autonomous execution until escalation review is complete")

        output_payload = {
            "task_queue": task_queue,
            "autonomous_task_count": autonomous_task_count,
            "review_required_task_count": len(task_queue) - autonomous_task_count,
            "execution_strategy": "parallel_where_safe",
            "next_actions": next_actions,
        }

        confidence = 0.85 if (llm_used and task_queue) else (0.79 if task_queue and risk.get("risk_level") != "high" else 0.6 if task_queue else 0.2)
        reasoning = (
            f"LLM-coordinated execution: {autonomous_task_count}/{len(task_queue)} tasks can start autonomously"
            if llm_used
            else "Rule-based execution coordination (LLM unavailable)"
        )

        return AgentResult(
            agent_name=self.agent_name,
            role=self.role,
            stage=self.stage,
            confidence=confidence,
            reasoning=reasoning,
            output_payload=output_payload,
            requires_human_review=output_payload["review_required_task_count"] > 0 and risk.get("risk_level") == "high",
        )
