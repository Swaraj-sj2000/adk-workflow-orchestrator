# app/agents/_communication_agent.py

from typing import Any, Dict, List

from app.agents._base import AgentResult, BaseAgent
from app.services._llm_service import LLMService


class CommunicationAgent(BaseAgent):
    agent_name = "communication_agent"
    role = "communication"
    stage = "communication"

    def __init__(self):
        self.llm_service = LLMService()

    def run(self, shared_context: Dict[str, Any]) -> AgentResult:
        execution_plan = shared_context["execution_plan"]
        execution_coordination = shared_context["execution_coordination"]
        risk = shared_context["risk"]
        staffing = shared_context["staffing"]

        assignment_messages: List[Dict[str, Any]] = []
        for item in execution_coordination.get("task_queue", []):
            owner = item.get("recommended_owner")
            if not owner:
                continue
            assignment_messages.append(
                {
                    "channel": "ticket",
                    "audience": f"employee:{owner['employee_profile_id']}",
                    "subject": f"Assignment Proposal: {item['task_title']}",
                    "body": (
                        f"You are the recommended owner for '{item['task_title']}' "
                        f"with confidence {owner['score']:.2f}. "
                        f"Execution mode: {item['execution_mode']}."
                    ),
                    "task_sequence": item["task_sequence"],
                }
            )

        admin_context = {
            "project_name": execution_plan["project_title"],
            "completed_tasks": 0,
            "in_progress_tasks": execution_coordination.get("autonomous_task_count", 0),
            "blocked_tasks": execution_coordination.get("review_required_task_count", 0),
        }
        admin_summary = self.llm_service.generate_client_update(admin_context)

        output_payload = {
            "admin_summary": {
                "channel": "digest",
                "audience": "admin",
                "subject": f"Workflow Summary: {execution_plan['project_title']}",
                "body": admin_summary,
            },
            "assignment_messages": assignment_messages,
            "client_update_draft": {
                "channel": "email",
                "audience": "client",
                "subject": f"Planning Update: {execution_plan['project_title']}",
                "body": (
                    f"We have generated {len(execution_plan.get('tasks', []))} planned tasks, "
                    f"identified {staffing.get('available_employee_count', 0)} available candidate employees, "
                    f"and classified current delivery risk as {risk.get('risk_level', 'unknown')}."
                ),
            },
        }

        confidence = 0.82 if self.llm_service.enabled else 0.64
        return AgentResult(
            agent_name=self.agent_name,
            role=self.role,
            stage=self.stage,
            confidence=confidence,
            reasoning="Drafted communications for owners, admins, and clients from the current workflow state",
            output_payload=output_payload,
            requires_human_review=False,
        )
