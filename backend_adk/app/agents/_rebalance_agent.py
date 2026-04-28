# app/agents/_rebalance_agent.py

import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.agents._base import AgentResult, BaseAgent
from app.core._logging import get_logger
from app.models._employee_profile import EmployeeProfile
from app.models._project import Project
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

        # ── Velocity-based deadline check ──────────────────────────────────
        deadline_extension = self._check_deadline_feasibility(project_id, tasks)

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
            "deadline_extension": deadline_extension,
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

    def _check_deadline_feasibility(self, project_id: int, tasks: List) -> Dict[str, Any]:
        """
        Velocity-based deadline check. If the projected completion date exceeds
        the project deadline, auto-extend the deadline and log the extension.
        """
        project = self.db.query(Project).filter(Project.id == project_id).first()
        if not project or not project.deadline:
            return {"extended": False, "reason": "No deadline set"}

        now = datetime.now(timezone.utc)
        deadline = project.deadline if project.deadline.tzinfo else project.deadline.replace(tzinfo=timezone.utc)
        created_at = project.created_at if project.created_at and project.created_at.tzinfo else (
            project.created_at.replace(tzinfo=timezone.utc) if project.created_at else now
        )

        total_tasks = len(tasks)
        completed_tasks = sum(1 for t in tasks if t.status in ("done", "completed", "closed"))
        remaining_tasks = total_tasks - completed_tasks

        if total_tasks == 0 or remaining_tasks == 0:
            return {"extended": False, "reason": "No remaining tasks"}

        elapsed_days = max((now - created_at).total_seconds() / 86400, 1.0)
        velocity = completed_tasks / elapsed_days  # tasks per day

        if velocity <= 0:
            # No velocity yet — estimate from team size and task hours
            total_hours = sum(t.estimated_time or 0 for t in tasks if t.status not in ("done", "completed", "closed"))
            tenant_id = tasks[0].tenant_id if tasks else None
            if tenant_id:
                employees = self.db.query(EmployeeProfile).filter(
                    EmployeeProfile.tenant_id == tenant_id,
                ).count()
            else:
                employees = 1
            daily_team_capacity = max(employees, 1) * 6  # 6 productive hours per person per day
            avg_task_hours = total_hours / max(remaining_tasks, 1)
            velocity = daily_team_capacity / max(avg_task_hours, 1)

        projected_days = remaining_tasks / max(velocity, 0.01)
        projected_completion = now + timedelta(days=projected_days)

        if projected_completion <= deadline:
            return {
                "extended": False,
                "original_deadline": deadline.isoformat(),
                "projected_completion": projected_completion.isoformat(),
                "reason": "On track — projected completion within deadline",
            }

        # Need to extend: buffer = 15%
        required_days = math.ceil(projected_days * 1.15)
        new_deadline = now + timedelta(days=required_days)
        days_extended = (new_deadline - deadline).days

        # Persist the new deadline
        project.deadline = new_deadline

        # Record the extension in custom_fields
        meta = dict(project.custom_fields or {})
        extensions = meta.get("deadline_extensions", [])
        extensions.append({
            "extended_at": now.isoformat(),
            "original_deadline": deadline.isoformat(),
            "new_deadline": new_deadline.isoformat(),
            "days_extended": days_extended,
            "reason": f"Velocity-based: projected completion {projected_completion.date()} > deadline {deadline.date()}",
            "agent": "rebalance_agent",
        })
        meta["deadline_extensions"] = extensions
        project.custom_fields = meta

        self.db.commit()

        logger.info(
            f"RebalanceAgent extended deadline for project_id={project_id}: "
            f"+{days_extended}d (velocity={velocity:.2f} tasks/day, remaining={remaining_tasks})"
        )

        return {
            "extended": True,
            "original_deadline": deadline.isoformat(),
            "new_deadline": new_deadline.isoformat(),
            "days_extended": days_extended,
            "projected_completion": projected_completion.isoformat(),
            "reason": (
                f"Projected completion ({projected_completion.date()}) exceeded deadline "
                f"({deadline.date()}). Extended by {days_extended} days."
            ),
        }
