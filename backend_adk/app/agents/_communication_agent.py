# app/agents/_communication_agent.py

from typing import Any, Dict, List

from app.agents._base import AgentResult, BaseAgent
from app.db._database import SessionLocal
from app.models._client_profile import ClientProfile
from app.models._employee_profile import EmployeeProfile
from app.models._project import Project
from app.models._user import User
from app.services._email_service import EmailService
from app.services._llm_service import LLMService


class CommunicationAgent(BaseAgent):
    agent_name = "communication_agent"
    role = "communication"
    stage = "communication"

    def __init__(self):
        self.llm_service = LLMService()

    def _deliver_messages(
        self,
        project_id: int | None,
        project_name: str,
        admin_summary: Dict[str, Any],
        client_update: Dict[str, Any],
        assignment_messages: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        delivery_results: Dict[str, Any] = {
            "admin_summary": False,
            "client_update_draft": False,
            "assignment_messages": {},
        }
        if not project_id:
            return delivery_results

        db = SessionLocal()
        try:
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                return delivery_results

            admin_user = db.query(User).filter(User.id == project.admin_id).first()
            if admin_user:
                delivery_results["admin_summary"] = EmailService.send_email(
                    to_email=admin_user.email,
                    subject=admin_summary["subject"],
                    html_body=f"<p>{admin_summary['body']}</p>",
                    tenant_id=project.tenant_id,
                    template_name="workflow_admin_summary",
                )

            if project.client_id:
                client_profile = db.query(ClientProfile).filter(ClientProfile.id == project.client_id).first()
                client_user = db.query(User).filter(User.id == client_profile.user_id).first() if client_profile else None
                if client_user:
                    delivery_results["client_update_draft"] = EmailService.send_email(
                        to_email=client_user.email,
                        subject=client_update["subject"],
                        html_body=f"<p>{client_update['body']}</p>",
                        tenant_id=project.tenant_id,
                        template_name="workflow_client_update",
                    )

            for message in assignment_messages:
                audience = message.get("audience", "")
                if not audience.startswith("employee:"):
                    continue
                employee_profile_id = audience.split(":", 1)[1]
                employee = db.query(EmployeeProfile).filter(EmployeeProfile.id == int(employee_profile_id)).first()
                employee_user = db.query(User).filter(User.id == employee.user_id).first() if employee else None
                delivered = False
                if employee_user:
                    delivered = EmailService.send_task_assignment_email(
                        to_email=employee_user.email,
                        employee_name=employee_user.full_name or employee_user.email,
                        task_description=message.get("task_title") or message["subject"],
                        project_name=project_name,
                        deadline=message.get("deadline") or "Not specified",
                        estimated_hours=float(message.get("estimated_hours") or 0.0),
                    )
                delivery_results["assignment_messages"][str(message.get("task_sequence"))] = delivered

            return delivery_results
        finally:
            db.close()

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
                    "task_title": item["task_title"],
                    "estimated_hours": item.get("estimated_hours") or 0.0,
                    "deadline": item.get("deadline"),
                }
            )

        admin_context = {
            "project_name": execution_plan["project_title"],
            "completed_tasks": 0,
            "in_progress_tasks": execution_coordination.get("autonomous_task_count", 0),
            "blocked_tasks": execution_coordination.get("review_required_task_count", 0),
        }
        admin_summary = self.llm_service.generate_client_update(admin_context)

        admin_summary_payload = {
            "channel": "digest",
            "audience": "admin",
            "subject": f"Workflow Summary: {execution_plan['project_title']}",
            "body": admin_summary,
        }
        client_update_payload = {
            "channel": "email",
            "audience": "client",
            "subject": f"Planning Update: {execution_plan['project_title']}",
            "body": (
                f"We have generated {len(execution_plan.get('tasks', []))} planned tasks, "
                f"identified {staffing.get('available_employee_count', 0)} available candidate employees, "
                f"and classified current delivery risk as {risk.get('risk_level', 'unknown')}."
            ),
        }
        delivery_results = self._deliver_messages(
            shared_context.get("project_id"),
            execution_plan["project_title"],
            admin_summary_payload,
            client_update_payload,
            assignment_messages,
        )

        output_payload = {
            "admin_summary": {
                **admin_summary_payload,
                "delivery_status": "sent" if delivery_results["admin_summary"] else "drafted",
            },
            "assignment_messages": assignment_messages,
            "client_update_draft": {
                **client_update_payload,
                "delivery_status": "sent" if delivery_results["client_update_draft"] else "drafted",
            },
            "delivery_results": delivery_results,
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
