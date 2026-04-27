# app/agents/_rebalance_agent.py

from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.agents._base import AgentResult, BaseAgent
from app.core._logging import get_logger
from app.models._employee_profile import EmployeeProfile
from app.models._task import Task
from app.models._task_assignment import TaskAssignment
from app.services._assignment_engine import AssignmentEngine

logger = get_logger(__name__)


class RebalanceAgent(BaseAgent):
    agent_name = "rebalance_agent"
    role = "rebalancing"
    stage = "rebalancing"

    def __init__(self, db: Session):
        self.db = db
        self.assignment_engine = AssignmentEngine(db)

    def run(self, shared_context: Dict[str, Any]) -> AgentResult:
        project_id = shared_context["project_id"]
        llm_service = shared_context.get("llm_service")

        suggestions = self.assignment_engine.suggest_reassignments(project_id)

        tasks = self.db.query(Task).filter(Task.project_id == project_id).all()
        unassigned = []
        for task in tasks:
            active = self.db.query(TaskAssignment).filter(
                TaskAssignment.task_id == task.id,
                TaskAssignment.status.in_(["pending", "accepted", "in-progress"]),
            ).first()
            if not active and task.status in ["pending", "running", "blocked"]:
                unassigned.append({
                    "task_id": task.id,
                    "title": task.description,
                    "status": task.status,
                    "estimated_hours": task.estimated_time,
                    "required_skills": task.required_skills,
                })

        # Collect employee workload data for this project's tenant
        tenant_id = tasks[0].tenant_id if tasks else None
        employee_loads = []
        if tenant_id:
            employees = self.db.query(EmployeeProfile).filter(
                EmployeeProfile.tenant_id == tenant_id,
            ).all()
            for emp in employees:
                load_pct = round((emp.current_load or 0) / max(emp.max_capacity or 1, 1) * 100, 1)
                employee_loads.append({
                    "employee_id": emp.id,
                    "availability_status": emp.availability_status,
                    "current_load_hours": emp.current_load,
                    "max_capacity_hours": emp.max_capacity,
                    "load_percent": load_pct,
                    "overloaded": load_pct >= 100,
                    "skills": list((emp.skills or {}).keys())[:8],
                })

        overloaded = [e for e in employee_loads if e["overloaded"]]
        available_capacity = sum(
            max(0, e["max_capacity_hours"] - e["current_load_hours"])
            for e in employee_loads
        )
        total_unassigned_hours = sum(t.get("estimated_hours") or 0 for t in unassigned)

        workload_context = {
            "project_id": project_id,
            "unassigned_tasks": unassigned,
            "reassignment_suggestions": suggestions,
            "team_load": employee_loads,
            "overloaded_employees": overloaded,
            "available_capacity_hours": available_capacity,
            "unassigned_work_hours": total_unassigned_hours,
            "capacity_deficit": max(0, total_unassigned_hours - available_capacity),
        }

        llm_result: Dict[str, Any] = {}
        if llm_service and llm_service.enabled:
            try:
                llm_result = llm_service.suggest_workload_rebalance(workload_context)
                logger.info(
                    f"RebalanceAgent LLM: rebalance_needed={llm_result.get('rebalance_needed')}, "
                    f"severity={llm_result.get('severity')}, overloaded={len(overloaded)}"
                )
            except Exception as exc:
                logger.warning(f"RebalanceAgent LLM call failed: {exc}")

        if llm_result.get("severity"):
            rebalance_needed = llm_result.get("rebalance_needed", bool(suggestions or unassigned))
            reasoning = f"LLM workload analysis: {llm_result.get('narrative', '')}"
            confidence = 0.90 if not rebalance_needed else 0.74
        else:
            rebalance_needed = bool(suggestions or unassigned)
            reasoning = "Rule-based workload evaluation (LLM unavailable)"
            confidence = 0.8 if not suggestions else 0.72

        output_payload = {
            "reassignment_suggestions": suggestions,
            "unassigned_active_tasks": unassigned,
            "overloaded_employees": overloaded,
            "rebalance_needed": rebalance_needed,
            "llm_narrative": llm_result.get("narrative", ""),
            "llm_severity": llm_result.get("severity", ""),
            "llm_actions": llm_result.get("actions", []),
            "admin_alert": llm_result.get("admin_alert", False),
            "admin_message": llm_result.get("admin_message", ""),
            "capacity_summary": {
                "available_hours": available_capacity,
                "unassigned_hours": total_unassigned_hours,
                "deficit_hours": max(0, total_unassigned_hours - available_capacity),
                "overloaded_count": len(overloaded),
            },
        }

        return AgentResult(
            agent_name=self.agent_name,
            role=self.role,
            stage=self.stage,
            confidence=confidence,
            reasoning=reasoning,
            output_payload=output_payload,
            requires_human_review=bool(unassigned) or llm_result.get("admin_alert", False),
        )
