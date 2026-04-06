# app/agents/_loop_communication_agent.py

from typing import Any, Dict

from app.agents._base import AgentResult, BaseAgent
from app.services._llm_service import LLMService


class LoopCommunicationAgent(BaseAgent):
    agent_name = "loop_communication_agent"
    role = "loop_communication"
    stage = "loop_communication"

    def __init__(self):
        self.llm_service = LLMService()

    def run(self, shared_context: Dict[str, Any]) -> AgentResult:
        project_state = shared_context["project_state"]
        delivery_review = shared_context["delivery_review"]
        rebalance = shared_context["rebalance"]

        context = {
            "project_name": project_state["project"]["name"],
            "completed_tasks": len([t for t in project_state["tasks"] if t["status"] == "done"]),
            "in_progress_tasks": len([t for t in project_state["tasks"] if t["status"] in ["running", "pending"]]),
            "blocked_tasks": project_state["open_blocker_count"],
        }
        summary = self.llm_service.generate_client_update(context)

        output_payload = {
            "admin_followup": {
                "subject": f"Execution Review: {project_state['project']['name']}",
                "body": summary,
            },
            "recommended_messages": [
                {
                    "audience": "admin",
                    "type": "digest",
                    "body": (
                        f"Risk level is {delivery_review['risk_summary']['risk_level']}. "
                        f"Reassignment suggestions: {len(rebalance['reassignment_suggestions'])}. "
                        f"Unassigned active tasks: {len(rebalance['unassigned_active_tasks'])}."
                    ),
                }
            ],
        }

        return AgentResult(
            agent_name=self.agent_name,
            role=self.role,
            stage=self.stage,
            confidence=0.8 if self.llm_service.enabled else 0.62,
            reasoning="Drafted loop-time follow-up messaging from the current project execution state",
            output_payload=output_payload,
            requires_human_review=False,
        )
