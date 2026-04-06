# app/agents/_execution_coordinator_agent.py

from typing import Any, Dict, List

from app.agents._base import AgentResult, BaseAgent


class ExecutionCoordinatorAgent(BaseAgent):
    agent_name = "execution_coordinator_agent"
    role = "execution_coordination"
    stage = "execution_coordination"

    def run(self, shared_context: Dict[str, Any]) -> AgentResult:
        execution_plan = shared_context["execution_plan"]
        staffing = shared_context["staffing"]
        risk = shared_context["risk"]

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

            task_queue.append(
                {
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
                }
            )

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

        confidence = 0.79 if task_queue and risk.get("risk_level") != "high" else 0.6 if task_queue else 0.2
        return AgentResult(
            agent_name=self.agent_name,
            role=self.role,
            stage=self.stage,
            confidence=confidence,
            reasoning="Translated planning, staffing, and risk outputs into an execution-ready queue with autonomous vs review-required boundaries",
            output_payload=output_payload,
            requires_human_review=output_payload["review_required_task_count"] > 0 and risk.get("risk_level") == "high",
        )
