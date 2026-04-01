# app/agents/_rebalance_agent.py

from typing import Any, Dict

from sqlalchemy.orm import Session

from app.agents._base import AgentResult, BaseAgent
from app.models._task import Task
from app.models._task_assignment import TaskAssignment
from app.services._assignment_engine import AssignmentEngine


class RebalanceAgent(BaseAgent):
    agent_name = "rebalance_agent"
    role = "rebalancing"
    stage = "rebalancing"

    def __init__(self, db: Session):
        self.db = db
        self.assignment_engine = AssignmentEngine(db)

    def run(self, shared_context: Dict[str, Any]) -> AgentResult:
        project_id = shared_context["project_id"]
        suggestions = self.assignment_engine.suggest_reassignments(project_id)

        tasks = self.db.query(Task).filter(Task.project_id == project_id).all()
        unassigned = []
        for task in tasks:
            active = self.db.query(TaskAssignment).filter(
                TaskAssignment.task_id == task.id,
                TaskAssignment.status.in_(["pending", "accepted", "in-progress"]),
            ).first()
            if not active and task.status in ["pending", "running", "blocked"]:
                unassigned.append(
                    {
                        "task_id": task.id,
                        "title": task.description,
                        "status": task.status,
                    }
                )

        output_payload = {
            "reassignment_suggestions": suggestions,
            "unassigned_active_tasks": unassigned,
            "rebalance_needed": bool(suggestions or unassigned),
        }

        return AgentResult(
            agent_name=self.agent_name,
            role=self.role,
            stage=self.stage,
            confidence=0.8 if not suggestions else 0.72,
            reasoning="Evaluated whether live execution state suggests reassignment or staffing follow-up",
            output_payload=output_payload,
            requires_human_review=bool(unassigned),
        )
