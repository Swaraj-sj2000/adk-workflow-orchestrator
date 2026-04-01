# app/agents/_project_observer_agent.py

from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.agents._base import AgentResult, BaseAgent
from app.models._blocker import Blocker
from app.models._project import Project
from app.models._task import Task
from app.models._task_assignment import TaskAssignment
from app.models._task_progress import TaskProgress


class ProjectObserverAgent(BaseAgent):
    agent_name = "project_observer_agent"
    role = "project_state_observation"
    stage = "project_observation"

    def __init__(self, db: Session):
        self.db = db

    def run(self, shared_context: Dict[str, Any]) -> AgentResult:
        project_id = shared_context["project_id"]
        project = self.db.query(Project).filter(Project.id == project_id).first()
        tasks = self.db.query(Task).filter(Task.project_id == project_id).order_by(Task.id.asc()).all()
        task_ids = [task.id for task in tasks]
        assignments = self.db.query(TaskAssignment).filter(TaskAssignment.task_id.in_(task_ids)).all() if task_ids else []
        blockers = self.db.query(Blocker).filter(Blocker.task_id.in_(task_ids), Blocker.status == "open").all() if task_ids else []
        progress_rows = self.db.query(TaskProgress).filter(TaskProgress.task_id.in_(task_ids)).all() if task_ids else []
        progress_by_task = {row.task_id: row for row in progress_rows}

        task_snapshots: List[Dict[str, Any]] = []
        for task in tasks:
            latest_assignment = next((a for a in sorted(assignments, key=lambda item: item.assigned_at, reverse=True) if a.task_id == task.id), None)
            task_snapshots.append(
                {
                    "task_id": task.id,
                    "title": task.description,
                    "status": task.status,
                    "difficulty": task.difficulty,
                    "urgency": task.urgency,
                    "estimated_time": task.estimated_time,
                    "latest_assignment": {
                        "employee_id": latest_assignment.employee_id,
                        "status": latest_assignment.status,
                        "confidence": latest_assignment.assignment_confidence,
                    } if latest_assignment else None,
                    "progress": {
                        "completion_percentage": progress_by_task[task.id].completion_percentage,
                        "actual_hours_spent": progress_by_task[task.id].actual_hours_spent,
                        "estimated_hours_remaining": progress_by_task[task.id].estimated_hours_remaining,
                        "is_on_track": bool(progress_by_task[task.id].is_on_track),
                    } if task.id in progress_by_task else None,
                }
            )

        output_payload = {
            "project": {
                "id": project.id if project else project_id,
                "name": project.name if project else f"Project {project_id}",
                "status": project.status if project else "unknown",
                "progress": project.progress if project else 0,
                "priority": project.priority if project else "unknown",
            },
            "task_count": len(tasks),
            "open_blocker_count": len(blockers),
            "tasks": task_snapshots,
        }

        return AgentResult(
            agent_name=self.agent_name,
            role=self.role,
            stage=self.stage,
            confidence=0.92 if project else 0.2,
            reasoning="Observed the current persisted project, task, assignment, blocker, and progress state",
            output_payload=output_payload,
            requires_human_review=project is None,
        )
